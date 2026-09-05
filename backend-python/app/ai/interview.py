import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field, field_validator


class GeneratedInterviewQuestion(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=64)
    difficulty: str = Field(min_length=1, max_length=16)
    expected_points: list[str] = Field(min_length=1, max_length=20)
    source_ids: list[str] = Field(min_length=1, max_length=20)

    @field_validator("content", "category", "difficulty", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("expected_points", "source_ids")
    @classmethod
    def strip_items(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item.strip()]
        if not cleaned:
            raise ValueError("list must contain non-empty values")
        return cleaned


class GeneratedQuestionSet(BaseModel):
    questions: list[GeneratedInterviewQuestion] = Field(min_length=1, max_length=20)


class InterviewQuestionGeneration(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=64)
    difficulty: str = Field(min_length=1, max_length=16)


class InterviewQuestionGenerationSet(BaseModel):
    questions: list[InterviewQuestionGeneration] = Field(min_length=1, max_length=20)


@dataclass(frozen=True, slots=True)
class QuestionGenerationMetrics:
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    ttft_ms: float | None
    total_latency_ms: float


@dataclass(frozen=True, slots=True)
class QuestionGenerationRequest:
    job_title: str
    job_description: str
    interview_type: str
    difficulty: str
    question_count: int
    context_prompt: str
    source_ids: tuple[str, ...]


class InterviewQuestionGeneratorPort(Protocol):
    async def generate(self, request: QuestionGenerationRequest) -> GeneratedQuestionSet: ...


class FakeInterviewQuestionGenerator:
    """Deterministic generator for tests; it never calls an external model."""

    def __init__(
        self,
        output: GeneratedQuestionSet | None = None,
        error: Exception | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.output = output
        self.error = error
        self.delay_seconds = delay_seconds
        self.calls = 0
        self.cancelled = False
        self.requests: list[QuestionGenerationRequest] = []

    async def generate(self, request: QuestionGenerationRequest) -> GeneratedQuestionSet:
        self.calls += 1
        self.requests.append(request)
        try:
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if self.error is not None:
                raise self.error
            if self.output is not None:
                return self.output
            source_id = request.source_ids[0] if request.source_ids else ""
            return GeneratedQuestionSet(
                questions=[
                    GeneratedInterviewQuestion(
                        content=(
                            f"请结合岗位要求说明你的{request.job_title}项目经验（第 {index} 题）"
                        ),
                        category="PROJECT_EXPERIENCE",
                        difficulty=request.difficulty,
                        expected_points=["说明负责范围", "说明技术方案", "说明结果与复盘"],
                        source_ids=[source_id] if source_id else [],
                    )
                    for index in range(1, request.question_count + 1)
                ]
            )
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class UnavailableInterviewQuestionGenerator:
    async def generate(self, _request: QuestionGenerationRequest) -> GeneratedQuestionSet:
        raise RuntimeError("No interview question generator is configured")


class LangChainInterviewQuestionGeneratorAdapter:
    """Adapter for a LangChain model exposing ``with_structured_output``."""

    def __init__(self, model: Any) -> None:
        self._model = model
        self.last_metrics: QuestionGenerationMetrics | None = None

    async def generate(self, request: QuestionGenerationRequest) -> GeneratedQuestionSet:
        structured_model = self._model.with_structured_output(
            InterviewQuestionGenerationSet, include_raw=True
        )
        prompt = (
            "你是严谨的技术面试题生成器。仅依据岗位和参考资料生成结构化题目，不得编造来源。\n"
            f"岗位：{request.job_title}\n"
            f"岗位描述：{request.job_description}\n"
            f"面试类型：{request.interview_type}\n"
            f"难度：{request.difficulty}\n"
            f"请生成 {request.question_count} 道互不重复的题目；"
            f"每题难度必须为 {request.difficulty}。"
            "只输出 question、category、difficulty，不生成答案、评分规则或追问。\n"
            f"参考资料：\n{request.context_prompt}"
        )
        started_at = time.perf_counter()
        result = await structured_model.ainvoke(prompt)
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        is_wrapped = isinstance(result, dict) and ("raw" in result or "parsed" in result)
        raw = result.get("raw") if is_wrapped else None
        parsed = result.get("parsed") if is_wrapped else result
        usage = getattr(raw, "usage_metadata", None) or {}
        response_metadata = getattr(raw, "response_metadata", None) or {}
        self.last_metrics = QuestionGenerationMetrics(
            model=response_metadata.get("model_name") or response_metadata.get("model"),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            ttft_ms=None,
            total_latency_ms=latency_ms,
        )
        minimal = InterviewQuestionGenerationSet.model_validate(parsed)
        source_ids = [request.source_ids[0]] if request.source_ids else []
        return GeneratedQuestionSet(
            questions=[
                GeneratedInterviewQuestion(
                    content=question.question,
                    category=question.category,
                    difficulty=question.difficulty,
                    expected_points=["说明关键决策、实施过程和验证结果"],
                    source_ids=source_ids,
                )
                for question in minimal.questions
            ]
        )
