"""Run the isolated RAG benchmark with Fake or explicitly authorized real embeddings."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_NAME = "interviewplatform-rag-eval"
DOCKER_FALLBACK = Path(
    r"C:\Users\李广威\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
)
ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "compose.rag-eval.yml"
OUTPUT_DIR = ROOT / "evals" / "rag" / "results"


class RagEvalGateError(RuntimeError):
    """Raised when the isolated evaluation gate cannot complete."""


def _docker_executable() -> str:
    on_path = shutil.which("docker")
    if on_path:
        return on_path
    if DOCKER_FALLBACK.is_file():
        return str(DOCKER_FALLBACK)
    raise RagEvalGateError("Docker CLI was not found on PATH or at the Docker Desktop path")


def _compose_command(docker: str, *args: str, use_env_file: bool = False) -> list[str]:
    command = [docker, "compose"]
    if use_env_file:
        command.extend(["--env-file", str(ROOT / "backend-python" / ".env")])
    command.extend(["-p", PROJECT_NAME, "-f", str(COMPOSE_FILE), *args])
    return command


def _run(
    command: list[str], *, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )


def _redact(text: str) -> str:
    redacted = re.sub(
        r"(?i)(postgres(?:ql)?(?:\+[^:]+)?://)[^@\s]+@",
        r"\1<redacted>@",
        text,
    )
    redacted = re.sub(r"(?i)(redis://)[^@\s]+@", r"\1<redacted>@", redacted)
    return re.sub(
        r"(?i)(APP_[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD))\s*=\s*[^\s]+",
        r"\1=<redacted>",
        redacted,
    )


def _require_success(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode != 0:
        detail = "\n".join((result.stdout + result.stderr).splitlines()[-8:])
        raise RagEvalGateError(f"{label} failed (exit {result.returncode})\n{_redact(detail)}")
    return result.stdout


def _statuses(docker: str, use_env_file: bool) -> dict[str, dict[str, Any]]:
    result = _run(_compose_command(docker, "ps", "--format", "json", use_env_file=use_env_file))
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        parsed = json.loads(result.stdout)
        entries = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        entries = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    return {
        entry["Service"]: entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("Service"), str)
    }


def _wait_for_health(docker: str, use_env_file: bool) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        status = _statuses(docker, use_env_file)
        if all(status.get(name, {}).get("Health") == "healthy" for name in ("postgres", "redis")):
            return
        time.sleep(2)
    raise RagEvalGateError("PostgreSQL or Redis did not become healthy before timeout")


def _run_evaluator(
    docker: str,
    mode: str,
    use_env_file: bool,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["RAG_EVAL_MODE"] = mode
    environment["RAG_EVAL_EMBEDDING_PROVIDER"] = "openai_compatible" if mode == "real" else "fake"
    if mode == "real":
        environment["RUN_REAL_RAG_EVAL"] = "1"
    result = _run(
        _compose_command(
            docker, "run", "--rm", "--no-deps", "evaluator", use_env_file=use_env_file
        ),
        environment=environment,
    )
    if result.returncode != 0:
        raise RagEvalGateError(
            f"RAG evaluator failed (exit {result.returncode})\n"
            f"{_redact((result.stdout + result.stderr)[-4000:])}"
        )
    report_path = OUTPUT_DIR / f"rag_eval_{mode}.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RagEvalGateError(
            "RAG evaluator did not produce a valid JSON report: "
            f"{type(exc).__name__}"
        ) from exc
    if not isinstance(report, dict):
        raise RagEvalGateError("RAG evaluator JSON report is invalid")
    return report


def _core_report(report: dict[str, Any]) -> dict[str, Any]:
    comparable = json.loads(json.dumps(report))
    comparable.pop("embedding_requests", None)
    for item in comparable.get("matrix", []):
        if isinstance(item, dict) and isinstance(item.get("metrics"), dict):
            item["metrics"].pop("latency_ms", None)
    return comparable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "real"), default="fake")
    args = parser.parse_args()
    if args.mode == "real" and os.getenv("RUN_REAL_RAG_EVAL") != "1":
        print("Real RAG evaluation requires RUN_REAL_RAG_EVAL=1", file=sys.stderr)
        return 1
    docker = ""
    use_env_file = args.mode == "real"
    try:
        docker = _docker_executable()
        _require_success(
            _run(_compose_command(docker, "config", "--quiet", use_env_file=use_env_file)),
            "Compose config",
        )
        _require_success(
            _run(
                _compose_command(
                    docker, "down", "-v", "--remove-orphans", use_env_file=use_env_file
                )
            ),
            "Pre-run cleanup",
        )
        _require_success(
            _run(
                _compose_command(
                    docker, "build", "migrate", "evaluator", use_env_file=use_env_file
                )
            ),
            "RAG evaluation image build",
        )
        _require_success(
            _run(
                _compose_command(
                    docker, "up", "-d", "postgres", "redis", use_env_file=use_env_file
                )
            ),
            "RAG evaluation database startup",
        )
        _wait_for_health(docker, use_env_file)
        _require_success(
            _run(
                _compose_command(
                    docker, "run", "--rm", "--no-deps", "migrate", use_env_file=use_env_file
                )
            ),
            "RAG evaluation migration",
        )
        first = _run_evaluator(docker, args.mode, use_env_file)
        if args.mode == "fake":
            second = _run_evaluator(docker, args.mode, use_env_file)
            if _core_report(first) != _core_report(second):
                raise RagEvalGateError("Fake RAG evaluation is not deterministic across two runs")
            print("Fake RAG evaluation: 2 consecutive runs are deterministic")
        print(
            f"RAG evaluation passed: mode={args.mode}, documents={first['document_count']}, "
            f"queries={first['query_count']}, embedding_requests={first['embedding_requests']}"
        )
        return 0
    except RagEvalGateError as exc:
        print(f"RAG evaluation gate FAILED: {_redact(str(exc))}", file=sys.stderr)
        return 1
    finally:
        if docker:
            cleanup = _run(
                _compose_command(
                    docker, "down", "-v", "--remove-orphans", use_env_file=use_env_file
                )
            )
            if cleanup.returncode == 0:
                print("Cleanup: RAG evaluation containers, network and volumes removed")
            else:
                print(
                    "Cleanup failed; inspect only the interviewplatform-rag-eval project",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
