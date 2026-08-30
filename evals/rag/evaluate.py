"""Run the versioned offline RAG retrieval benchmark against PostgreSQL/pgvector."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import statistics
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND_CANDIDATES = (ROOT / "backend-python", Path("/app"))
BACKEND = next((path for path in BACKEND_CANDIDATES if (path / "app").is_dir()), None)
if BACKEND is None:
    raise RuntimeError("Backend application package was not found")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if TYPE_CHECKING:
    from app.ai.embedding import EmbeddingPort

THRESHOLDS = (0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
TOP_KS = (1, 3, 5, 8)
DEFAULT_DATASET = Path(__file__).with_name("dataset_v1.json")
DEFAULT_OUTPUT = Path(__file__).with_name("results")


class RagEvaluationError(RuntimeError):
    """Raised when the benchmark cannot complete safely."""


def _constraint_name(exc: Exception) -> str | None:
    match = re.search(r'constraint "([^"]+)"', str(getattr(exc, "orig", exc)))
    return match.group(1) if match else None


def _load_dataset(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RagEvaluationError(
            f"Unable to load evaluation dataset: {type(exc).__name__}"
        ) from exc
    if not isinstance(data, dict) or data.get("version") != "rag-eval-v1":
        raise RagEvaluationError("Unsupported evaluation dataset version")
    documents = data.get("documents")
    queries = data.get("queries")
    if not isinstance(documents, list) or not isinstance(queries, list):
        raise RagEvaluationError("Evaluation dataset must contain documents and queries")
    document_ids: set[str] = set()
    chunk_ids: set[str] = set()
    for document in documents:
        if not isinstance(document, dict) or not isinstance(document.get("id"), str):
            raise RagEvaluationError("Evaluation document metadata is invalid")
        document_id = document["id"]
        if document_id in document_ids:
            raise RagEvaluationError("Evaluation document IDs must be unique")
        document_ids.add(document_id)
        chunks = document.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise RagEvaluationError("Every evaluation document needs at least one chunk")
        for chunk in chunks:
            if not isinstance(chunk, dict) or not isinstance(chunk.get("id"), str):
                raise RagEvaluationError("Evaluation chunk metadata is invalid")
            chunk_id = chunk["id"]
            if chunk_id in chunk_ids:
                raise RagEvaluationError("Evaluation chunk IDs must be unique")
            chunk_ids.add(chunk_id)
    for query in queries:
        if not isinstance(query, dict) or not isinstance(query.get("id"), str):
            raise RagEvaluationError("Evaluation query metadata is invalid")
        if not isinstance(query.get("expected_chunk_ids"), list):
            raise RagEvaluationError("Every query needs expected_chunk_ids")
        unknown = set(query["expected_chunk_ids"]) - chunk_ids
        if unknown:
            raise RagEvaluationError("Query refers to an unknown evaluation chunk")
    return data


class _EmbeddingCache:
    def __init__(self, directory: Path, identity: str, dimensions: int) -> None:
        self._directory = directory
        self._identity = identity
        self._dimensions = dimensions
        directory.mkdir(parents=True, exist_ok=True)

    def _path(self, text: str) -> Path:
        key = hashlib.sha256(f"{self._identity}\0{text}".encode()).hexdigest()
        return self._directory / f"{key}.json"

    def load(self, text: str) -> tuple[float, ...] | None:
        try:
            value = json.loads(self._path(text).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, list) or len(value) != self._dimensions:
            return None
        if not all(isinstance(item, (int, float)) for item in value):
            return None
        return tuple(float(item) for item in value)

    def save(self, text: str, vector: Sequence[float]) -> None:
        self._path(text).write_text(json.dumps(list(vector)), encoding="utf-8")


async def _embed_all(
    embedding: EmbeddingPort,
    texts: Sequence[str],
    batch_size: int,
    cache: _EmbeddingCache | None,
) -> tuple[dict[str, tuple[float, ...]], int]:
    vectors: dict[str, tuple[float, ...]] = {}
    missing: list[str] = []
    for text in dict.fromkeys(texts):
        cached = cache.load(text) if cache is not None else None
        if cached is None:
            missing.append(text)
        else:
            vectors[text] = cached
    requests = 0
    try:
        request_budget = int(os.getenv("RAG_EVAL_MAX_EMBEDDING_REQUESTS", "10"))
    except ValueError as exc:
        raise RagEvaluationError("RAG_EVAL_MAX_EMBEDDING_REQUESTS must be an integer") from exc
    if request_budget < 1:
        raise RagEvaluationError("RAG_EVAL_MAX_EMBEDDING_REQUESTS must be positive")
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        if requests >= request_budget:
            raise RagEvaluationError("Embedding request budget would be exceeded")
        try:
            response = await embedding.embed_documents(batch)
        except Exception as exc:
            raise RagEvaluationError(f"Embedding request failed: {type(exc).__name__}") from exc
        requests += 1
        if len(response) != len(batch):
            raise RagEvaluationError("Embedding result count does not match input count")
        for text, raw_vector in zip(batch, response, strict=True):
            vector = tuple(float(value) for value in raw_vector)
            if len(vector) != embedding.dimensions:
                raise RagEvaluationError("Embedding dimensions do not match configuration")
            vectors[text] = vector
            if cache is not None:
                cache.save(text, vector)
    return vectors, requests


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _distribution(values: Sequence[float]) -> dict[str, float | None]:
    return {
        "count": float(len(values)),
        "min": min(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
        "max": max(values) if values else None,
    }


def _average(values: Sequence[float]) -> float:
    return round(statistics.fmean(values), 4) if values else 0.0


def _build_metrics(
    observations: Sequence[dict[str, Any]],
    latencies: Sequence[float],
    related_scores: Sequence[float],
    unrelated_scores: Sequence[float],
) -> dict[str, Any]:
    positive = [item for item in observations if item["should_return"]]
    negative = [item for item in observations if not item["should_return"]]
    metrics: dict[str, Any] = {}
    for cutoff in (1, 3, 5):
        recalls: list[float] = []
        precisions: list[float] = []
        reciprocal_ranks: list[float] = []
        for item in positive:
            results = item["results"][:cutoff]
            expected = set(item["expected_chunk_ids"])
            hit_count = len(expected.intersection(result["chunk_id"] for result in results))
            recalls.append(hit_count / len(expected) if expected else 0.0)
            precisions.append(hit_count / len(results) if results else 0.0)
            reciprocal_ranks.append(
                next(
                    (1.0 / index for index, result in enumerate(results, start=1)
                     if result["chunk_id"] in expected),
                    0.0,
                )
            )
        metrics[f"recall_at_{cutoff}"] = _average(recalls)
        metrics[f"precision_at_{cutoff}"] = _average(precisions)
        metrics[f"mrr_at_{cutoff}"] = _average(reciprocal_ranks)
    metrics["empty_result_accuracy"] = _average(
        [1.0 if not item["results"] else 0.0 for item in negative]
    )
    metrics["unrelated_false_positive_rate"] = _average(
        [1.0 if item["results"] else 0.0 for item in negative]
    )
    metrics["cross_user_leakage"] = sum(item["cross_user_leakage"] for item in observations)
    metrics["cross_knowledge_base_leakage"] = sum(
        item["cross_knowledge_base_leakage"] for item in observations
    )
    metrics["citation_document_accuracy"] = _average(
        [item["citation_document_accuracy"] for item in positive]
    )
    metrics["citation_page_accuracy"] = _average(
        [item["citation_page_accuracy"] for item in positive]
    )
    metrics["related_score_distribution"] = _distribution(related_scores)
    metrics["unrelated_score_distribution"] = _distribution(unrelated_scores)
    metrics["latency_ms"] = {
        "p50": _percentile(latencies, 0.50),
        "p95": _percentile(latencies, 0.95),
    }
    return metrics


async def _evaluate_database(
    database_url: str,
    dataset: dict[str, Any],
    embedding: EmbeddingPort,
    embedding_identity: str,
    batch_size: int,
    cache: _EmbeddingCache | None,
) -> tuple[dict[str, Any], int]:
    from app.infrastructure.vectorstore.retriever import PgVectorRetriever
    from app.modules.auth.models import UserModel
    from app.modules.knowledge.domain import DocumentStatus
    from app.modules.knowledge.models import (
        KnowledgeBaseModel,
        KnowledgeChunkModel,
        KnowledgeDocumentModel,
    )
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    documents = dataset["documents"]
    queries = dataset["queries"]
    run_users: dict[str, UUID] = {}
    run_bases: dict[str, UUID] = {}
    run_documents: dict[str, UUID] = {}
    run_chunks: dict[str, UUID] = {}
    chunk_meta: dict[UUID, dict[str, Any]] = {}
    all_texts: list[str] = []
    for document in documents:
        owner = document["owner_id"]
        base = document["knowledge_base_id"]
        run_users.setdefault(owner, uuid4())
        run_bases.setdefault(base, uuid4())
        run_documents[document["id"]] = uuid4()
        for chunk in document["chunks"]:
            run_chunks[chunk["id"]] = uuid4()
            all_texts.append(chunk["text"])
    all_texts.extend(query["text"] for query in queries)
    vectors, embedding_requests = await _embed_all(embedding, all_texts, batch_size, cache)

    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            for owner, user_id in run_users.items():
                session.add(
                    UserModel(
                        id=user_id,
                        username=f"rag-eval-{owner}",
                        email=f"{owner}@eval.invalid",
                        password_hash="evaluation-only",
                        is_active=True,
                    )
                )
            await session.flush()
            for base_key, base_id in run_bases.items():
                owner = next(
                    document["owner_id"]
                    for document in documents
                    if document["knowledge_base_id"] == base_key
                )
                session.add(
                    KnowledgeBaseModel(
                        id=base_id,
                        user_id=run_users[owner],
                        name=f"RAG evaluation {base_key}",
                        description="Synthetic benchmark data",
                    )
                )
            await session.flush()
            for document in documents:
                document_id = run_documents[document["id"]]
                session.add(
                    KnowledgeDocumentModel(
                        id=document_id,
                        knowledge_base_id=run_bases[document["knowledge_base_id"]],
                        original_filename=document["filename"],
                        safe_filename=document["filename"],
                        content_type="application/pdf",
                        size_bytes=1,
                        sha256=hashlib.sha256(document["id"].encode()).hexdigest(),
                        storage_path=f"/evaluation/{document['id']}.pdf",
                        status=DocumentStatus.READY.value,
                        page_count=len(document["chunks"]),
                        chunk_count=len(document["chunks"]),
                    )
                )
            await session.flush()
            for document in documents:
                document_id = run_documents[document["id"]]
                for chunk_index, chunk in enumerate(document["chunks"]):
                    chunk_id = run_chunks[chunk["id"]]
                    chunk_meta[chunk_id] = {
                        "owner_id": document["owner_id"],
                        "knowledge_base_id": document["knowledge_base_id"],
                        "document_id": document["id"],
                    }
                    session.add(
                        KnowledgeChunkModel(
                            id=chunk_id,
                            document_id=document_id,
                            chunk_index=chunk_index,
                            page_number=chunk["page"],
                            content=chunk["text"],
                            token_count=max(1, len(chunk["text"]) // 4),
                            content_hash=hashlib.sha256(chunk["text"].encode()).hexdigest(),
                            embedding=list(vectors[chunk["text"]]),
                        )
                    )
            await session.commit()
            retriever = PgVectorRetriever(session, embedding.dimensions)
            matrix: list[dict[str, Any]] = []
            for threshold in THRESHOLDS:
                for top_k in TOP_KS:
                    observations: list[dict[str, Any]] = []
                    latencies: list[float] = []
                    related_scores: list[float] = []
                    unrelated_scores: list[float] = []
                    for query in queries:
                        expected_chunks = {run_chunks[item] for item in query["expected_chunk_ids"]}
                        expected_documents = set(query["expected_document_ids"])
                        expected_pages = set(query["expected_pages"])
                        started = time.perf_counter()
                        try:
                            results = await retriever.retrieve(
                                user_id=run_users[query["owner_id"]],
                                knowledge_base_id=run_bases[query["knowledge_base_id"]],
                                query_vector=vectors[query["text"]],
                                top_k=top_k,
                                similarity_threshold=threshold,
                            )
                        except Exception as exc:
                            raise RagEvaluationError(
                                f"PostgreSQL retrieval failed: {type(exc).__name__}"
                            ) from exc
                        latencies.append((time.perf_counter() - started) * 1000)
                        result_rows: list[dict[str, Any]] = []
                        cross_user = 0
                        cross_base = 0
                        for result in results:
                            metadata = chunk_meta[result.chunk_id]
                            if metadata["owner_id"] != query["owner_id"]:
                                cross_user += 1
                            if metadata["knowledge_base_id"] != query["knowledge_base_id"]:
                                cross_base += 1
                            row = {
                                "chunk_id": result.chunk_id,
                                "document_id": metadata["document_id"],
                                "page_number": result.page_number,
                                "score": float(result.score),
                            }
                            result_rows.append(row)
                            if result.chunk_id in expected_chunks:
                                related_scores.append(float(result.score))
                            else:
                                unrelated_scores.append(float(result.score))
                        first = result_rows[0] if result_rows else None
                        observations.append(
                            {
                                "should_return": query["should_return"],
                                "expected_chunk_ids": expected_chunks,
                                "results": result_rows,
                                "cross_user_leakage": cross_user,
                                "cross_knowledge_base_leakage": cross_base,
                                "citation_document_accuracy": float(
                                    bool(first and first["document_id"] in expected_documents)
                                )
                                if query["should_return"]
                                else 0.0,
                                "citation_page_accuracy": float(
                                    bool(first and first["page_number"] in expected_pages)
                                )
                                if query["should_return"]
                                else 0.0,
                            }
                        )
                    matrix.append(
                        {
                            "similarity_threshold": threshold,
                            "top_k": top_k,
                            "metrics": _build_metrics(
                                observations, latencies, related_scores, unrelated_scores
                            ),
                        }
                    )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_(tuple(run_users.values())))
            )
            await session.commit()
    except RagEvaluationError:
        raise
    except Exception as exc:
        constraint = _constraint_name(exc)
        suffix = f" ({constraint})" if constraint else ""
        raise RagEvaluationError(
            f"Evaluation database operation failed: {type(exc).__name__}{suffix}"
        ) from exc
    finally:
        await engine.dispose()
    notes = [
        "Metrics are calculated from scoped PostgreSQL/pgvector retrieval.",
        "Precision, MRR and citation accuracy are averaged over positive queries.",
    ]
    if embedding_identity.startswith("openai_compatible"):
        notes.append(
            "Real text-embedding-v4 results use synthetic data and are an MVP baseline; "
            "they do not by themselves justify changing production defaults."
        )
    else:
        notes.append(
            "Fake mode validates the benchmark harness and is not a production "
            "threshold conclusion."
        )
    result = {
        "dataset_version": dataset["version"],
        "mode": "real" if embedding_identity.startswith("openai_compatible") else "fake",
        "embedding_identity": embedding_identity,
        "embedding_dimensions": embedding.dimensions,
        "document_count": len(documents),
        "chunk_count": sum(len(document["chunks"]) for document in documents),
        "query_count": len(queries),
        "thresholds": list(THRESHOLDS),
        "top_ks": list(TOP_KS),
        "embedding_requests": embedding_requests,
        "embedding_request_budget": int(os.getenv("RAG_EVAL_MAX_EMBEDDING_REQUESTS", "10")),
        "embedding_batch_size": batch_size,
        "matrix": matrix,
        "notes": notes,
    }
    return result, embedding_requests


def _markdown(result: dict[str, Any]) -> str:
    lines = [
        "# RAG 离线评测报告",
        "",
        (
            f"- 数据集：`{result['dataset_version']}`（{result['document_count']} 份文档，"
            f"{result['chunk_count']} 个 Chunk，{result['query_count']} 个查询）"
        ),
        (
            f"- 模式：`{result['mode']}`，Embedding 维度：{result['embedding_dimensions']}，"
            f"本次请求数：{result['embedding_requests']}"
        ),
        "- 召回、精度、MRR 和引用准确性按正向查询平均；空结果准确率和误召回率按负向查询统计。",
        "",
        (
            "| 阈值 | Top-K | Recall@5 | Precision@5 | MRR@5 | 空结果准确率 | "
            "无关误召回率 | 文档引用准确率 | 页码引用准确率 | P50 ms | P95 ms |"
        ),
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in result["matrix"]:
        metrics = item["metrics"]
        latency = metrics["latency_ms"]
        lines.append(
            f"| {item['similarity_threshold']:.1f} | {item['top_k']} | "
            f"{metrics['recall_at_5']:.3f} | {metrics['precision_at_5']:.3f} | "
            f"{metrics['mrr_at_5']:.3f} | {metrics['empty_result_accuracy']:.3f} | "
            f"{metrics['unrelated_false_positive_rate']:.3f} | "
            f"{metrics['citation_document_accuracy']:.3f} | "
            f"{metrics['citation_page_accuracy']:.3f} | "
            f"{latency['p50']:.2f} | {latency['p95']:.2f} |"
        )
    lines.append("")
    if result["mode"] == "real":
        lines.append(
            "真实 text-embedding-v4 结果仅来自合成数据 MVP 基线，不能单独作为修改生产"
            "默认参数的依据。"
        )
    else:
        lines.append(
            "Fake 基准只用于验证数据集、指标计算、PostgreSQL/pgvector 查询和权限隔离；"
            "真实 Embedding 校准需显式授权，不能由本报告推导生产阈值。"
        )
    return "\n".join(lines) + "\n"


def _build_embedding(mode: str) -> tuple[EmbeddingPort, str, int, _EmbeddingCache | None]:
    if mode == "fake":
        from app.ai.embedding import FakeEmbedding

        dimensions = int(os.getenv("APP_EMBEDDING_DIMENSIONS", "1536"))
        batch_size = int(os.getenv("APP_EMBEDDING_BATCH_SIZE", "10"))
        return FakeEmbedding(dimensions), f"fake:{dimensions}", batch_size, None
    if os.getenv("RUN_REAL_RAG_EVAL") != "1":
        raise RagEvaluationError("Real RAG evaluation requires RUN_REAL_RAG_EVAL=1")
    try:
        from app.ai.factory import AiProviderFactory
        from app.core.config import Settings

        settings = Settings()
    except Exception as exc:
        raise RagEvaluationError(
            f"Real embedding configuration is invalid: {type(exc).__name__}"
        ) from exc
    if settings.embedding_provider != "openai_compatible":
        raise RagEvaluationError(
            "Real RAG evaluation requires openai_compatible embedding provider"
        )
    if settings.embedding_model != "text-embedding-v4":
        raise RagEvaluationError("Real RAG evaluation requires text-embedding-v4")
    if settings.embedding_dimensions != 1536:
        raise RagEvaluationError("Real RAG evaluation requires 1536 dimensions")
    try:
        embedding = AiProviderFactory.build(settings).embedding
    except Exception as exc:
        raise RagEvaluationError(
            f"Real embedding provider is unavailable: {type(exc).__name__}"
        ) from exc
    cache_directory = Path(
        os.getenv(
            "RAG_EVAL_CACHE_DIR",
            str(Path(tempfile.gettempdir()) / "xunzhi-rag-eval-cache"),
        )
    )
    identity = f"openai_compatible:{settings.embedding_model}:{settings.embedding_dimensions}"
    provider_limit = embedding.max_batch_size
    batch_size = (
        min(settings.embedding_batch_size, provider_limit)
        if provider_limit is not None
        else settings.embedding_batch_size
    )
    return (
        embedding,
        identity,
        batch_size,
        _EmbeddingCache(cache_directory, identity, settings.embedding_dimensions),
    )


async def _run(args: argparse.Namespace) -> None:
    dataset = _load_dataset(Path(args.dataset))
    embedding, identity, batch_size, cache = _build_embedding(args.mode)
    database_url = args.database_url or os.getenv("APP_DATABASE_URL")
    if not database_url:
        raise RagEvaluationError("RAG_EVAL_DATABASE_URL is required")
    result, _ = await _evaluate_database(
        database_url, dataset, embedding, identity, batch_size, cache
    )
    output_directory = Path(args.output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / f"rag_eval_{args.mode}.json"
    markdown_path = output_directory / f"rag_eval_{args.mode}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(result), encoding="utf-8")
    print(
        f"RAG evaluation complete: mode={result['mode']}, queries={result['query_count']}, "
        f"embedding_requests={result['embedding_requests']}"
    )
    print(f"Reports written: {json_path.name}, {markdown_path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("fake", "real"), default=os.getenv("RAG_EVAL_MODE", "fake")
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--database-url", default=os.getenv("RAG_EVAL_DATABASE_URL"))
    parser.add_argument(
        "--output-dir", default=os.getenv("RAG_EVAL_OUTPUT_DIR", str(DEFAULT_OUTPUT))
    )
    args = parser.parse_args()
    try:
        asyncio.run(_run(args))
    except RagEvaluationError as exc:
        print(f"RAG evaluation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
