"""Runtime selection for AI and embedding ports.

The application layer only receives the ports returned by this factory. Concrete
LangChain/OpenAI objects are kept here so business services stay provider agnostic.
"""

from dataclasses import dataclass

from pydantic import SecretStr

from app.ai.capabilities import embedding_batch_limit
from app.ai.chat import (
    ChatModelPort,
    FakeChatModel,
    LangChainChatModelAdapter,
    UnavailableChatModel,
)
from app.ai.demeanor import (
    DemeanorAnalyzerPort,
    FakeDemeanorAnalyzer,
    LangChainDemeanorAnalyzerAdapter,
    UnavailableDemeanorAnalyzer,
)
from app.ai.embedding import (
    EmbeddingPort,
    FakeEmbedding,
    LangChainEmbeddingAdapter,
    UnavailableEmbedding,
)
from app.ai.evaluation import (
    FakeInterviewAnswerEvaluator,
    InterviewAnswerEvaluatorPort,
    LangChainInterviewAnswerEvaluatorAdapter,
    StructuredInterviewEvaluation,
    UnavailableInterviewAnswerEvaluator,
)
from app.ai.followup import (
    FakeFollowUpQuestionGenerator,
    FollowUpQuestionGeneratorPort,
    LangChainFollowUpQuestionGeneratorAdapter,
    UnavailableFollowUpQuestionGenerator,
)
from app.ai.interview import (
    FakeInterviewQuestionGenerator,
    InterviewQuestionGeneratorPort,
    LangChainInterviewQuestionGeneratorAdapter,
    UnavailableInterviewQuestionGenerator,
)
from app.ai.metadata import AiModelMetadataPort, RuntimeAiModelMetadata
from app.ai.report import (
    FakeInterviewReportNarrativeGenerator,
    InterviewReportNarrativePort,
    LangChainInterviewReportNarrativeAdapter,
    RuleBasedInterviewReportNarrativeGenerator,
    UnavailableInterviewReportNarrativeGenerator,
)
from app.ai.resume import (
    FakeResumeEvaluator,
    FakeResumeRoleInference,
    LangChainResumeEvaluatorAdapter,
    LangChainResumeRoleInferenceAdapter,
    ResumeEvaluatorPort,
    ResumeRoleInferencePort,
    UnavailableResumeEvaluator,
    UnavailableResumeRoleInference,
)
from app.core.config import Settings


class AiProviderConfigurationError(RuntimeError):
    """Raised for an unsafe or incomplete provider configuration."""


@dataclass(frozen=True, slots=True)
class AiProviderBundle:
    chat_model: ChatModelPort
    interview_question_generator: InterviewQuestionGeneratorPort
    interview_answer_evaluator: InterviewAnswerEvaluatorPort
    follow_up_question_generator: FollowUpQuestionGeneratorPort
    interview_report_narrative: InterviewReportNarrativePort
    resume_evaluator: ResumeEvaluatorPort
    resume_role_inference: ResumeRoleInferencePort
    embedding: EmbeddingPort
    demeanor_analyzer: DemeanorAnalyzerPort
    model_metadata: AiModelMetadataPort


class AiProviderFactory:
    """Build all runtime ports from validated settings."""

    @classmethod
    def build(cls, settings: Settings) -> AiProviderBundle:
        cls._validate_environment(settings)
        model_metadata = RuntimeAiModelMetadata(settings)
        if (
            settings.ai_provider == "openai_compatible"
            or settings.embedding_provider == "openai_compatible"
            or settings.demeanor_analysis_provider == "openai_compatible"
        ):
            return cls._build_openai_compatible(settings, model_metadata)
        return cls._build_non_network(settings, model_metadata)

    @staticmethod
    async def validate_embedding_dimensions(
        embedding: EmbeddingPort,
        expected_dimensions: int,
        *,
        probe: bool = True,
    ) -> None:
        """Verify both the declared and returned vector dimensions."""

        if embedding.dimensions != expected_dimensions:
            raise AiProviderConfigurationError("Embedding dimensions do not match configuration")
        if not probe:
            return
        try:
            document_vectors = await embedding.embed_documents(["embedding-dimension-probe"])
            query_vector = await embedding.embed_query("embedding-dimension-probe")
        except Exception as exc:
            raise AiProviderConfigurationError("Embedding provider dimension check failed") from exc
        if not document_vectors or any(
            len(vector) != expected_dimensions for vector in document_vectors
        ):
            raise AiProviderConfigurationError("Embedding dimensions do not match configuration")
        if len(query_vector) != expected_dimensions:
            raise AiProviderConfigurationError("Embedding dimensions do not match configuration")

    @staticmethod
    def _validate_environment(settings: Settings) -> None:
        if settings.app_env.strip().lower() == "production" and (
            settings.ai_provider == "fake"
            or settings.embedding_provider == "fake"
            or settings.demeanor_analysis_provider == "fake"
        ):
            raise AiProviderConfigurationError("Fake AI providers are not allowed in production")

    @classmethod
    def _build_non_network(
        cls, settings: Settings, model_metadata: AiModelMetadataPort
    ) -> AiProviderBundle:
        if settings.ai_provider == "fake":
            evaluation_output: StructuredInterviewEvaluation | None = None
            evaluation_error: Exception | None = None
            if settings.ai_fake_mode == "follow_up":
                evaluation_output = StructuredInterviewEvaluation(
                    overall_score=80,
                    technical_score=80,
                    relevance_score=80,
                    clarity_score=78,
                    depth_score=76,
                    strengths=["回答覆盖关键技术点"],
                    weaknesses=["可以补充量化结果"],
                    feedback="回答结构清晰，可以进一步说明取舍。",
                    suggested_improvements=["补充指标和复盘过程"],
                    should_follow_up=True,
                    follow_up_focus="请具体说明技术取舍",
                )
            elif settings.ai_fake_mode == "failure":
                evaluation_error = RuntimeError("fake evaluation failure")
            answer_evaluator: InterviewAnswerEvaluatorPort = FakeInterviewAnswerEvaluator(
                output=evaluation_output, error=evaluation_error
            )
            question_generator: InterviewQuestionGeneratorPort = FakeInterviewQuestionGenerator(
                error=evaluation_error
            )
            follow_up_generator: FollowUpQuestionGeneratorPort = FakeFollowUpQuestionGenerator(
                error=evaluation_error
            )
            report_narrative: InterviewReportNarrativePort = FakeInterviewReportNarrativeGenerator(
                error=evaluation_error
            )
            resume_evaluator: ResumeEvaluatorPort = FakeResumeEvaluator(
                error=evaluation_error
            )
            resume_role_inference: ResumeRoleInferencePort = FakeResumeRoleInference(
                error=evaluation_error
            )
            demeanor_analyzer: DemeanorAnalyzerPort = (
                FakeDemeanorAnalyzer(error=evaluation_error)
                if settings.demeanor_analysis_provider == "fake"
                else UnavailableDemeanorAnalyzer()
            )
            chat_model: ChatModelPort = FakeChatModel(
                chunks=("这是开发环境的模拟回答。",), error=evaluation_error
            )
        else:
            chat_model = UnavailableChatModel()
            question_generator = UnavailableInterviewQuestionGenerator()
            answer_evaluator = UnavailableInterviewAnswerEvaluator()
            follow_up_generator = UnavailableFollowUpQuestionGenerator()
            report_narrative = (
                RuleBasedInterviewReportNarrativeGenerator()
                if settings.ai_provider == "unavailable"
                else UnavailableInterviewReportNarrativeGenerator()
            )
            resume_evaluator = UnavailableResumeEvaluator()
            resume_role_inference = UnavailableResumeRoleInference()
            demeanor_analyzer = (
                FakeDemeanorAnalyzer()
                if settings.demeanor_analysis_provider == "fake"
                else UnavailableDemeanorAnalyzer()
            )
        embedding: EmbeddingPort = (
            FakeEmbedding(settings.embedding_dimensions)
            if settings.embedding_provider == "fake"
            else UnavailableEmbedding(settings.embedding_dimensions)
        )
        return AiProviderBundle(
            chat_model,
            question_generator,
            answer_evaluator,
            follow_up_generator,
            report_narrative,
            resume_evaluator,
            resume_role_inference,
            embedding,
            demeanor_analyzer,
            model_metadata,
        )

    @classmethod
    def _build_openai_compatible(
        cls, settings: Settings, model_metadata: AiModelMetadataPort
    ) -> AiProviderBundle:
        try:
            from langchain_openai import (
                ChatOpenAI,
                OpenAIEmbeddings,
            )
        except ImportError as exc:
            raise AiProviderConfigurationError(
                "OpenAI-compatible provider dependency is not installed"
            ) from exc

        chat_model: ChatModelPort
        question_generator: InterviewQuestionGeneratorPort
        answer_evaluator: InterviewAnswerEvaluatorPort
        follow_up_generator: FollowUpQuestionGeneratorPort
        report_narrative: InterviewReportNarrativePort
        resume_evaluator: ResumeEvaluatorPort
        resume_role_inference: ResumeRoleInferencePort
        demeanor_analyzer: DemeanorAnalyzerPort
        if settings.ai_provider == "openai_compatible":
            assert settings.llm_api_key is not None
            assert settings.llm_base_url is not None
            assert settings.llm_model is not None
            model = ChatOpenAI(
                api_key=SecretStr(settings.llm_api_key),
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                temperature=0,
                timeout=settings.ai_request_timeout_seconds,
                max_retries=settings.ai_max_retries,
            )
            question_model = model
            if (
                settings.interview_question_model
                and settings.interview_question_model != settings.llm_model
            ):
                question_model = ChatOpenAI(
                    api_key=SecretStr(settings.llm_api_key),
                    base_url=settings.llm_base_url,
                    model=settings.interview_question_model,
                    temperature=0,
                    timeout=settings.ai_request_timeout_seconds,
                    max_retries=settings.ai_max_retries,
                )
            evaluation_model = model
            if (
                settings.interview_evaluation_model
                and settings.interview_evaluation_model != settings.llm_model
            ):
                evaluation_model = ChatOpenAI(
                    api_key=SecretStr(settings.llm_api_key),
                    base_url=settings.llm_base_url,
                    model=settings.interview_evaluation_model,
                    temperature=0,
                    timeout=settings.ai_request_timeout_seconds,
                    max_retries=settings.ai_max_retries,
                )
            report_model = model
            if (
                settings.final_report_model
                and settings.final_report_model != settings.llm_model
            ):
                report_model = ChatOpenAI(
                    api_key=SecretStr(settings.llm_api_key),
                    base_url=settings.llm_base_url,
                    model=settings.final_report_model,
                    temperature=0,
                    timeout=settings.ai_request_timeout_seconds,
                    max_retries=settings.ai_max_retries,
                )
            job_detection_model = model
            if (
                settings.job_detection_model
                and settings.job_detection_model != settings.llm_model
            ):
                job_detection_model = ChatOpenAI(
                    api_key=SecretStr(settings.llm_api_key),
                    base_url=settings.llm_base_url,
                    model=settings.job_detection_model,
                    temperature=0,
                    timeout=settings.ai_request_timeout_seconds,
                    max_retries=settings.ai_max_retries,
                )
            chat_model = LangChainChatModelAdapter(model)
            question_generator = LangChainInterviewQuestionGeneratorAdapter(question_model)
            answer_evaluator = LangChainInterviewAnswerEvaluatorAdapter(evaluation_model)
            follow_up_generator = LangChainFollowUpQuestionGeneratorAdapter(evaluation_model)
            report_narrative = LangChainInterviewReportNarrativeAdapter(report_model)
            resume_evaluator = LangChainResumeEvaluatorAdapter(evaluation_model)
            resume_role_inference = LangChainResumeRoleInferenceAdapter(job_detection_model)
        else:
            chat_model = UnavailableChatModel()
            question_generator = UnavailableInterviewQuestionGenerator()
            answer_evaluator = UnavailableInterviewAnswerEvaluator()
            follow_up_generator = UnavailableFollowUpQuestionGenerator()
            report_narrative = RuleBasedInterviewReportNarrativeGenerator()
            resume_evaluator = UnavailableResumeEvaluator()
            resume_role_inference = UnavailableResumeRoleInference()

        if settings.demeanor_analysis_provider == "openai_compatible":
            assert settings.llm_api_key is not None
            assert settings.llm_base_url is not None
            demeanor_model_name = settings.demeanor_analysis_model or settings.llm_model
            assert demeanor_model_name is not None
            if (
                settings.ai_provider == "openai_compatible"
                and demeanor_model_name == settings.llm_model
            ):
                demeanor_model = model
            else:
                demeanor_model = ChatOpenAI(
                    api_key=SecretStr(settings.llm_api_key),
                    base_url=settings.llm_base_url,
                    model=demeanor_model_name,
                    temperature=0,
                    timeout=settings.demeanor_analysis_request_timeout_seconds,
                    max_retries=settings.ai_max_retries,
                )
            demeanor_analyzer = LangChainDemeanorAnalyzerAdapter(demeanor_model)
        elif settings.demeanor_analysis_provider == "fake":
            demeanor_analyzer = FakeDemeanorAnalyzer()
        else:
            demeanor_analyzer = UnavailableDemeanorAnalyzer()

        if settings.embedding_provider == "openai_compatible":
            assert settings.embedding_api_key is not None
            assert settings.embedding_base_url is not None
            assert settings.embedding_model is not None
            embeddings = OpenAIEmbeddings(
                api_key=SecretStr(settings.embedding_api_key),
                base_url=settings.embedding_base_url,
                model=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
                timeout=settings.ai_request_timeout_seconds,
                max_retries=settings.ai_max_retries,
                # Keep the SDK's own batching aligned with the application
                # batch size so it cannot regroup ten-item batches into a
                # larger provider request.
                chunk_size=settings.embedding_batch_size,
                # DashScope's OpenAI-compatible endpoint expects text input;
                # LangChain's OpenAI-specific tokenization would send token IDs.
                check_embedding_ctx_length=False,
            )
            embedding: EmbeddingPort = LangChainEmbeddingAdapter(
                embeddings,
                settings.embedding_dimensions,
                max_batch_size=embedding_batch_limit(
                    settings.embedding_provider, settings.embedding_model
                ),
            )
        else:
            embedding = (
                FakeEmbedding(settings.embedding_dimensions)
                if settings.embedding_provider == "fake"
                else UnavailableEmbedding(settings.embedding_dimensions)
            )
        return AiProviderBundle(
            chat_model,
            question_generator,
            answer_evaluator,
            follow_up_generator,
            report_narrative,
            resume_evaluator,
            resume_role_inference,
            embedding,
            demeanor_analyzer,
            model_metadata,
        )
