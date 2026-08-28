import asyncio
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

    async def generate(self, request: QuestionGenerationRequest) -> GeneratedQuestionSet:
        structured_model = self._model.with_structured_output(GeneratedQuestionSet)
        prompt = (
            "你是严谨的技术面试题生成器。只根据给定岗位和参考资料生成问题，"
            "不得编造来源。\n"
            f"岗位：{request.job_title}\n"
            f"岗位描述：{request.job_description}\n"
            f"面试类型：{request.interview_type}\n"
            f"难度：{request.difficulty}\n"
            f"题目数量：{request.question_count}\n"
            f"允许的来源编号：{', '.join(request.source_ids)}\n"
            f"参考资料：\n{request.context_prompt}"
        )
        result = await structured_model.ainvoke(prompt)
        return GeneratedQuestionSet.model_validate(result)
