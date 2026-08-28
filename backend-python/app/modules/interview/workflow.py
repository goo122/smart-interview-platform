import asyncio
from typing import Any, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph

from app.ai.interview import (
    GeneratedQuestionSet,
    InterviewQuestionGeneratorPort,
    QuestionGenerationRequest,
)
from app.core.exceptions import AppError
from app.modules.interview.context import InterviewContext, InterviewContextProviderPort
from app.modules.interview.domain import (
    InterviewDifficulty,
    InterviewQuestion,
    InterviewQuestionCitation,
    InterviewSession,
    utc_now,
)
from app.modules.interview.exceptions import (
    InterviewPreparationError,
    InterviewQuestionValidationError,
)
from app.modules.interview.repository import InterviewRepository


class InterviewGraphState(TypedDict, total=False):
    user_id: UUID
    session_id: UUID
    session: InterviewSession
    context: InterviewContext
    generation_request: QuestionGenerationRequest
    generated: GeneratedQuestionSet
    questions: list[InterviewQuestion]
    skip: bool


class InterviewPreparationWorkflow:
    """LangGraph-backed preparation orchestration."""

    def __init__(
        self,
        repository: InterviewRepository,
        context_provider: InterviewContextProviderPort,
        generator: InterviewQuestionGeneratorPort,
    ) -> None:
        self._repository = repository
        self._context_provider = context_provider
        self._generator = generator
        self._graph = self._build_graph()

    async def prepare(self, user_id: UUID, session_id: UUID) -> InterviewSession:
        state: InterviewGraphState = {"user_id": user_id, "session_id": session_id}
        try:
            await self._graph.ainvoke(state)
        except asyncio.CancelledError:
            try:
                await self._repository.cancel(session_id, user_id)
            except Exception as exc:
                raise RuntimeError("Interview cancellation could not be persisted") from exc
            raise
        except AppError as exc:
            return await self._fail(state, exc.code, exc.message)
        except Exception:
            return await self._fail(
                state,
                "INTERVIEW_PREPARATION_FAILED",
                "Interview preparation failed",
            )
        result = await self._repository.get_for_user(session_id, user_id)
        if result is None:
            raise InterviewPreparationError("Interview session not found after preparation")
        return result

    def _build_graph(self) -> Any:
        builder = StateGraph(InterviewGraphState)
        builder.add_node("load_session", self._load_session)
        builder.add_node("validate_knowledge_base", self._validate_knowledge_base)
        builder.add_node("mark_preparing", self._mark_preparing)
        builder.add_node("retrieve_resume_context", self._retrieve_resume_context)
        builder.add_node("build_question_generation_context", self._build_generation_context)
        builder.add_node("generate_questions", self._generate_questions)
        builder.add_node("validate_questions", self._validate_questions)
        builder.add_node("persist_questions_and_citations", self._persist_questions)
        builder.add_node("mark_ready", self._mark_ready)
        builder.add_edge(START, "load_session")
        builder.add_edge("load_session", "validate_knowledge_base")
        builder.add_edge("validate_knowledge_base", "mark_preparing")
        builder.add_conditional_edges(
            "mark_preparing",
            self._continue_after_mark_preparing,
            {"continue": "retrieve_resume_context", "end": END},
        )
        builder.add_edge("retrieve_resume_context", "build_question_generation_context")
        builder.add_edge("build_question_generation_context", "generate_questions")
        builder.add_edge("generate_questions", "validate_questions")
        builder.add_edge("validate_questions", "persist_questions_and_citations")
        builder.add_edge("persist_questions_and_citations", "mark_ready")
        builder.add_edge("mark_ready", END)
        return builder.compile()

    async def _load_session(self, state: InterviewGraphState) -> InterviewGraphState:
        session = await self._repository.get_for_user(state["session_id"], state["user_id"])
        if session is None:
            raise InterviewPreparationError("Interview session not found")
        state["session"] = session
        return state

    async def _validate_knowledge_base(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        await self._context_provider.validate_knowledge_base(
            state["user_id"], session.knowledge_base_id
        )
        return state

    async def _mark_preparing(self, state: InterviewGraphState) -> InterviewGraphState:
        session, started = await self._repository.begin_preparing(
            state["session_id"], state["user_id"]
        )
        state["session"] = session
        state["skip"] = not started
        return state

    @staticmethod
    def _continue_after_mark_preparing(state: InterviewGraphState) -> str:
        return "end" if state.get("skip") else "continue"

    async def _retrieve_resume_context(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        state["context"] = await self._context_provider.build(
            user_id=state["user_id"],
            knowledge_base_id=session.knowledge_base_id,
            job_title=session.job_title,
            job_description=session.job_description,
            difficulty=session.difficulty.value,
            question_count=session.question_count,
        )
        return state

    async def _build_generation_context(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        context = state["context"]
        state["generation_request"] = QuestionGenerationRequest(
            job_title=session.job_title,
            job_description=session.job_description,
            interview_type=session.interview_type.value,
            difficulty=session.difficulty.value,
            question_count=session.question_count,
            context_prompt=context.prompt,
            source_ids=tuple(citation.source_id for citation in context.citations),
        )
        return state

    async def _generate_questions(self, state: InterviewGraphState) -> InterviewGraphState:
        last_error: InterviewQuestionValidationError | None = None
        for _attempt in range(2):
            state["generated"] = await self._generator.generate(state["generation_request"])
            try:
                await self._validate_questions(state)
                return state
            except InterviewQuestionValidationError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        return state

    async def _validate_questions(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        context = state["context"]
        generated = state["generated"]
        if len(generated.questions) != session.question_count:
            raise InterviewQuestionValidationError("Generated question count is invalid")
        citations_by_source = {citation.source_id: citation for citation in context.citations}
        seen: set[str] = set()
        questions: list[InterviewQuestion] = []
        for index, generated_question in enumerate(generated.questions, start=1):
            normalized = " ".join(generated_question.content.split()).casefold()
            if not normalized or normalized in seen:
                raise InterviewQuestionValidationError("Generated questions must be unique")
            seen.add(normalized)
            try:
                difficulty = InterviewDifficulty(generated_question.difficulty.upper())
            except ValueError as exc:
                raise InterviewQuestionValidationError(
                    "Generated question difficulty is invalid"
                ) from exc
            if difficulty != session.difficulty:
                raise InterviewQuestionValidationError(
                    "Generated question difficulty does not match session"
                )
            if not generated_question.expected_points:
                raise InterviewQuestionValidationError("Generated expected points are empty")
            selected_citations: list[InterviewQuestionCitation] = []
            for ordinal, source_id in enumerate(dict.fromkeys(generated_question.source_ids)):
                citation = citations_by_source.get(source_id)
                if citation is None:
                    raise InterviewQuestionValidationError("Generated question source is invalid")
                selected_citations.append(
                    InterviewQuestionCitation(
                        id=uuid4(),
                        question_id=UUID(int=0),
                        chunk_id=citation.chunk_id,
                        document_id=citation.document_id,
                        source_id=citation.source_id,
                        page_number=citation.page_number,
                        score=citation.score,
                        excerpt=citation.excerpt,
                        ordinal=ordinal,
                        created_at=utc_now(),
                        document_name=citation.document_name,
                    )
                )
            question_id = uuid4()
            selected_citations = [
                InterviewQuestionCitation(
                    id=citation.id,
                    question_id=question_id,
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    source_id=citation.source_id,
                    page_number=citation.page_number,
                    score=citation.score,
                    excerpt=citation.excerpt,
                    ordinal=citation.ordinal,
                    created_at=citation.created_at,
                    document_name=citation.document_name,
                )
                for citation in selected_citations
            ]
            summary = "; ".join(
                f"{citation.document_name} p.{citation.page_number or 'unknown'}"
                for citation in context.citations
                if citation.source_id in generated_question.source_ids
            )
            questions.append(
                InterviewQuestion(
                    id=question_id,
                    session_id=session.id,
                    sequence=index,
                    content=generated_question.content,
                    category=generated_question.category,
                    difficulty=difficulty,
                    expected_points=list(generated_question.expected_points),
                    source_summary=summary or None,
                    created_at=utc_now(),
                    citations=selected_citations,
                )
            )
        state["questions"] = questions
        return state

    async def _persist_questions(self, state: InterviewGraphState) -> InterviewGraphState:
        state["session"] = await self._repository.persist_questions_and_ready(
            state["session_id"], state["user_id"], state["questions"]
        )
        return state

    async def _mark_ready(self, state: InterviewGraphState) -> InterviewGraphState:
        return state

    async def _fail(
        self, state: InterviewGraphState, failure_code: str, failure_message: str
    ) -> InterviewSession:
        return await self._repository.mark_failed(
            state["session_id"], state["user_id"], failure_code, failure_message
        )
