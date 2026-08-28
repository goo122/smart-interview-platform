import sys
import types

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main
from app.ai.chat import ChatMessage, FakeChatModel, LangChainChatModelAdapter, UnavailableChatModel
from app.ai.embedding import FakeEmbedding, LangChainEmbeddingAdapter, UnavailableEmbedding
from app.ai.evaluation import (
    FakeInterviewAnswerEvaluator,
    InterviewEvaluationRequest,
    LangChainInterviewAnswerEvaluatorAdapter,
    UnavailableInterviewAnswerEvaluator,
)
from app.ai.factory import AiProviderConfigurationError, AiProviderFactory
from app.ai.followup import (
    FakeFollowUpQuestionGenerator,
    FollowUpQuestionRequest,
    LangChainFollowUpQuestionGeneratorAdapter,
    UnavailableFollowUpQuestionGenerator,
)
from app.ai.interview import (
    FakeInterviewQuestionGenerator,
    LangChainInterviewQuestionGeneratorAdapter,
    QuestionGenerationRequest,
    UnavailableInterviewQuestionGenerator,
)
from app.ai.report import (
    FakeInterviewReportNarrativeGenerator,
    InterviewReportNarrativeRequest,
    LangChainInterviewReportNarrativeAdapter,
    RuleBasedInterviewReportNarrativeGenerator,
)
from app.core.config import Settings


def test_unavailable_provider_is_safe_default() -> None:
    bundle = AiProviderFactory.build(Settings(_env_file=None))

    assert isinstance(bundle.chat_model, UnavailableChatModel)
    assert isinstance(bundle.interview_question_generator, UnavailableInterviewQuestionGenerator)
    assert isinstance(bundle.interview_answer_evaluator, UnavailableInterviewAnswerEvaluator)
    assert isinstance(bundle.follow_up_question_generator, UnavailableFollowUpQuestionGenerator)
    assert isinstance(bundle.interview_report_narrative, RuleBasedInterviewReportNarrativeGenerator)
    assert isinstance(bundle.embedding, UnavailableEmbedding)


@pytest.mark.asyncio
async def test_fake_provider_runs_the_complete_workflow() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        embedding_provider="fake",
        ai_fake_mode="follow_up",
    )
    bundle = AiProviderFactory.build(settings)
    await AiProviderFactory.validate_embedding_dimensions(
        bundle.embedding, settings.embedding_dimensions
    )

    assert isinstance(bundle.chat_model, FakeChatModel)
    assert isinstance(bundle.interview_question_generator, FakeInterviewQuestionGenerator)
    assert isinstance(bundle.interview_answer_evaluator, FakeInterviewAnswerEvaluator)
    assert isinstance(bundle.follow_up_question_generator, FakeFollowUpQuestionGenerator)
    assert isinstance(bundle.interview_report_narrative, FakeInterviewReportNarrativeGenerator)
    assert isinstance(bundle.embedding, FakeEmbedding)

    chat_chunks = [
        chunk.content
        async for chunk in bundle.chat_model.stream(
            [ChatMessage(role="user", content="请总结简历")]
        )
    ]
    assert "".join(chat_chunks)
    vectors = await bundle.embedding.embed_documents(["PDF 简历内容"])
    assert len(vectors) == 1

    question_set = await bundle.interview_question_generator.generate(
        QuestionGenerationRequest(
            job_title="Python 工程师",
            job_description="负责后端服务",
            interview_type="TECHNICAL",
            difficulty="MEDIUM",
            question_count=1,
            context_prompt="PDF 简历内容",
            source_ids=("document-1",),
        )
    )
    question = question_set.questions[0]
    evaluation = await bundle.interview_answer_evaluator.evaluate(
        InterviewEvaluationRequest(
            job_title="Python 工程师",
            job_description="负责后端服务",
            question=question.content,
            expected_points=tuple(question.expected_points),
            answer="我负责过异步 API 和数据库性能优化。",
            follow_up_depth=0,
            context_prompt="PDF 简历内容",
            recent_answers=(),
        )
    )
    assert evaluation.should_follow_up is True
    follow_up = await bundle.follow_up_question_generator.generate(
        FollowUpQuestionRequest(
            original_question=question.content,
            answer="我负责过异步 API 和数据库性能优化。",
            focus=evaluation.follow_up_focus or "请补充细节",
            expected_points=tuple(question.expected_points),
        )
    )
    narrative = await bundle.interview_report_narrative.generate(
        InterviewReportNarrativeRequest(
            job_title="Python 工程师",
            interview_type="TECHNICAL",
            difficulty="MEDIUM",
            overall_score=evaluation.overall_score,
            technical_score=evaluation.technical_score,
            relevance_score=evaluation.relevance_score,
            clarity_score=evaluation.clarity_score,
            depth_score=evaluation.depth_score,
            strengths=tuple(evaluation.strengths),
            weaknesses=tuple(evaluation.weaknesses),
            suggested_improvements=tuple(evaluation.suggested_improvements),
        )
    )
    assert follow_up.content
    assert narrative.summary


@pytest.mark.parametrize("provider", ["ai_provider", "embedding_provider"])
def test_fake_provider_is_rejected_in_production(provider: str) -> None:
    with pytest.raises(ValidationError, match="not allowed in production"):
        Settings(_env_file=None, app_env="production", **{provider: "fake"})


def test_provider_settings_are_loaded_from_app_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_AI_PROVIDER", "fake")
    monkeypatch.setenv("APP_EMBEDDING_PROVIDER", "fake")

    settings = Settings(_env_file=None)

    assert settings.ai_provider == "fake"
    assert settings.embedding_provider == "fake"


def test_fake_provider_is_wired_into_application_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, ai_provider="fake", embedding_provider="fake")
    monkeypatch.setattr(main, "get_settings", lambda: settings)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert isinstance(main.app.state.chat_model, FakeChatModel)
        assert isinstance(main.app.state.embedding, FakeEmbedding)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ai_provider": "openai_compatible"},
        {"embedding_provider": "openai_compatible"},
    ],
)
def test_openai_compatible_requires_complete_configuration(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValidationError, match="requires API key, base URL and model"):
        Settings(_env_file=None, **kwargs)


@pytest.mark.asyncio
async def test_embedding_dimension_mismatch_is_rejected() -> None:
    class WrongEmbedding(FakeEmbedding):
        async def embed_query(self, text: str) -> list[float]:
            del text
            return [0.0] * 768

    embedding = WrongEmbedding(dimensions=1536)

    with pytest.raises(AiProviderConfigurationError, match="dimensions"):
        await AiProviderFactory.validate_embedding_dimensions(embedding, 1536)


def test_openai_compatible_uses_one_shared_chat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    monkeypatch.setitem(
        sys.modules,
        "langchain_openai",
        types.SimpleNamespace(ChatOpenAI=FakeChatOpenAI, OpenAIEmbeddings=FakeOpenAIEmbeddings),
    )
    settings = Settings(
        _env_file=None,
        ai_provider="openai_compatible",
        embedding_provider="openai_compatible",
        llm_api_key="test-key",
        llm_base_url="https://llm.invalid/v1",
        llm_model="test-model",
        embedding_api_key="embedding-key",
        embedding_base_url="https://embedding.invalid/v1",
        embedding_model="embedding-model",
    )

    bundle = AiProviderFactory.build(settings)

    assert isinstance(bundle.chat_model, LangChainChatModelAdapter)
    assert isinstance(
        bundle.interview_question_generator, LangChainInterviewQuestionGeneratorAdapter
    )
    assert isinstance(
        bundle.interview_answer_evaluator, LangChainInterviewAnswerEvaluatorAdapter
    )
    assert isinstance(
        bundle.follow_up_question_generator, LangChainFollowUpQuestionGeneratorAdapter
    )
    assert isinstance(bundle.interview_report_narrative, LangChainInterviewReportNarrativeAdapter)
    assert bundle.chat_model._model is bundle.interview_question_generator._model
    assert isinstance(bundle.embedding, LangChainEmbeddingAdapter)
