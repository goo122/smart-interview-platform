import asyncio
from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.ai.evaluation import (
    InterviewAnswerEvaluatorPort,
    InterviewEvaluationRequest,
    StructuredInterviewEvaluation,
)
from app.ai.followup import (
    FollowUpQuestionGeneratorPort,
    FollowUpQuestionRequest,
    GeneratedFollowUpQuestion,
)
from app.core.exceptions import AppError
from app.modules.interview.context import (
    InterviewEvaluationContext,
    InterviewEvaluationContextProviderPort,
)
from app.modules.interview.domain import (
    FollowUpDecision,
    InterviewEvaluation,
    InterviewQuestion,
    InterviewSession,
    InterviewStatus,
    InterviewTurn,
    TurnStatus,
)
from app.modules.interview.exceptions import (
    InterviewEvaluationError,
    InterviewEvaluationValidationError,
)
from app.modules.interview.follow_up import FollowUpPolicy
from app.modules.interview.repository import InterviewRepository


class InterviewAnswerGraphState(TypedDict, total=False):
    user_id: UUID
    session_id: UUID
    turn_id: UUID
    session: InterviewSession
    turn: InterviewTurn
    answer_content: str
    question: InterviewQuestion | None
    recent_answers: tuple[str, ...]
    has_next_question: bool
    context: InterviewEvaluationContext
    evaluation_request: InterviewEvaluationRequest
    raw_evaluation: StructuredInterviewEvaluation
    evaluation: InterviewEvaluation
    decision: FollowUpDecision
    follow_up: GeneratedFollowUpQuestion | None
    skip: bool


class InterviewAnswerWorkflow:
    """LangGraph orchestration for evaluation and deterministic turn progression."""

    def __init__(
        self,
        repository: InterviewRepository,
        context_provider: InterviewEvaluationContextProviderPort,
        evaluator: InterviewAnswerEvaluatorPort,
        follow_up_generator: FollowUpQuestionGeneratorPort,
        policy: FollowUpPolicy,
    ) -> None:
        self._repository = repository
        self._context_provider = context_provider
        self._evaluator = evaluator
        self._follow_up_generator = follow_up_generator
        self._policy = policy
        self._graph = self._build_graph()

    async def evaluate(
        self,
        user_id: UUID,
        session_id: UUID,
        turn_id: UUID,
        answer_content: str,
    ) -> InterviewSession:
        state: InterviewAnswerGraphState = {
            "user_id": user_id,
            "session_id": session_id,
            "turn_id": turn_id,
            "answer_content": answer_content,
        }
        try:
            await self._graph.ainvoke(state)
        except asyncio.CancelledError:
            try:
                await self._repository.fail_evaluation(
                    session_id,
                    turn_id,
                    user_id,
                    "INTERVIEW_EVALUATION_CANCELLED",
                    "Interview evaluation was cancelled",
                )
            finally:
                raise
        except AppError as exc:
            await self._fail(state, exc.code, exc.message)
        except Exception:
            await self._fail(
                state,
                "INTERVIEW_EVALUATION_FAILED",
                "Interview evaluation failed",
            )
        session = await self._repository.get_for_user(session_id, user_id)
        if session is None:
            raise InterviewEvaluationError("Interview session not found after evaluation")
        return session

    def _build_graph(self) -> Any:
        builder = StateGraph(InterviewAnswerGraphState)
        builder.add_node("load_session_and_turn", self._load_session_and_turn)
        builder.add_node("validate_answer", self._validate_answer)
        builder.add_node("mark_evaluating", self._mark_evaluating)
        builder.add_node("build_evaluation_context", self._build_evaluation_context)
        builder.add_node("evaluate_answer", self._evaluate_answer)
        builder.add_node("validate_evaluation", self._validate_evaluation)
        builder.add_node("apply_follow_up_policy", self._apply_follow_up_policy)
        builder.add_node("generate_follow_up_question", self._generate_follow_up_question)
        builder.add_node("persist_evaluation", self._persist_evaluation)
        builder.add_node("complete_current_turn", self._complete_current_turn)
        builder.add_node("create_next_turn", self._create_next_turn)
        builder.add_node("complete_or_continue_session", self._complete_or_continue_session)
        builder.add_edge(START, "load_session_and_turn")
        builder.add_edge("load_session_and_turn", "validate_answer")
        builder.add_conditional_edges(
            "validate_answer",
            lambda state: "end" if state.get("skip") else "continue",
            {"end": END, "continue": "mark_evaluating"},
        )
        builder.add_edge("mark_evaluating", "build_evaluation_context")
        builder.add_edge("build_evaluation_context", "evaluate_answer")
        builder.add_edge("evaluate_answer", "validate_evaluation")
        builder.add_edge("validate_evaluation", "apply_follow_up_policy")
        builder.add_conditional_edges(
            "apply_follow_up_policy",
            lambda state: "follow_up" if state["decision"].should_follow_up else "persist",
            {"follow_up": "generate_follow_up_question", "persist": "persist_evaluation"},
        )
        builder.add_edge("generate_follow_up_question", "persist_evaluation")
        builder.add_edge("persist_evaluation", "complete_current_turn")
        builder.add_edge("complete_current_turn", "create_next_turn")
        builder.add_edge("create_next_turn", "complete_or_continue_session")
        builder.add_edge("complete_or_continue_session", END)
        return builder.compile()

    async def _load_session_and_turn(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        session = await self._repository.get_for_user(state["session_id"], state["user_id"])
        turn = await self._repository.get_turn_for_user(state["turn_id"], state["user_id"])
        if session is None or turn is None or turn.session_id != session.id:
            raise InterviewEvaluationError("Interview turn not found")
        state["session"] = session
        state["turn"] = turn
        state["skip"] = turn.status in {
            TurnStatus.COMPLETED,
            TurnStatus.FAILED,
            TurnStatus.SKIPPED,
        }
        if not state["skip"]:
            questions = await self._repository.list_questions(session.id)
            state["question"] = next(
                (question for question in questions if question.id == turn.question_id), None
            )
            state["has_next_question"] = any(
                question.sequence == session.current_question_index + 2
                for question in questions
            )
            state["recent_answers"] = tuple(
                await self._repository.recent_answers(session.id, turn.sequence)
            )
        return state

    async def _validate_answer(self, state: InterviewAnswerGraphState) -> InterviewAnswerGraphState:
        if state.get("skip"):
            return state
        session = state["session"]
        turn = state["turn"]
        if session.status != InterviewStatus.IN_PROGRESS:
            raise InterviewEvaluationError("Interview is not in progress")
        if turn.status != TurnStatus.EVALUATING:
            raise InterviewEvaluationError("Interview turn is not ready for evaluation")
        if not state["answer_content"].strip():
            raise InterviewEvaluationError("Answer must not be empty")
        return state

    async def _mark_evaluating(self, state: InterviewAnswerGraphState) -> InterviewAnswerGraphState:
        return state

    async def _build_evaluation_context(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        session = state["session"]
        turn = state["turn"]
        question = state.get("question")
        state["context"] = await self._context_provider.build(
            user_id=state["user_id"],
            knowledge_base_id=session.knowledge_base_id,
            job_title=session.job_title,
            job_description=session.job_description,
            question=turn.question_content,
            expected_points=tuple(question.expected_points) if question else (),
            source_summary=question.source_summary if question else None,
            answer=state["answer_content"],
            follow_up_depth=turn.follow_up_depth,
            recent_answers=state.get("recent_answers", ()),
        )
        state["evaluation_request"] = InterviewEvaluationRequest(
            job_title=session.job_title,
            job_description=session.job_description,
            question=turn.question_content,
            expected_points=tuple(question.expected_points) if question else (),
            answer=state["answer_content"],
            follow_up_depth=turn.follow_up_depth,
            context_prompt=state["context"].prompt,
            recent_answers=state.get("recent_answers", ()),
        )
        return state

    async def _evaluate_answer(self, state: InterviewAnswerGraphState) -> InterviewAnswerGraphState:
        last_error: ValidationError | None = None
        for _attempt in range(2):
            try:
                result = await self._evaluator.evaluate(state["evaluation_request"])
                state["raw_evaluation"] = StructuredInterviewEvaluation.model_validate(result)
                return state
            except ValidationError as exc:
                last_error = exc
        if last_error is not None:
            raise InterviewEvaluationValidationError(
                "AI evaluation output is invalid"
            ) from last_error
        raise InterviewEvaluationValidationError("AI evaluation output is invalid")

    async def _validate_evaluation(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        raw = StructuredInterviewEvaluation.model_validate(state["raw_evaluation"])
        state["evaluation"] = InterviewEvaluation(
            id=uuid4(),
            turn_id=state["turn_id"],
            overall_score=raw.overall_score,
            technical_score=raw.technical_score,
            relevance_score=raw.relevance_score,
            clarity_score=raw.clarity_score,
            depth_score=raw.depth_score,
            strengths=list(raw.strengths),
            weaknesses=list(raw.weaknesses),
            feedback=raw.feedback,
            suggested_improvements=list(raw.suggested_improvements),
            llm_should_follow_up=raw.should_follow_up,
            follow_up_focus=raw.follow_up_focus,
            follow_up_question=None,
            created_at=datetime.now(UTC),
        )
        return state

    async def _apply_follow_up_policy(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        state["decision"] = self._policy.decide(
            state["raw_evaluation"],
            follow_up_depth=state["turn"].follow_up_depth,
            follow_up_count=await self._repository.count_follow_ups(state["session_id"]),
            answer_length=len(state["answer_content"].strip()),
            has_next_question=state.get("has_next_question", True),
        )
        return state

    async def _generate_follow_up_question(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        evaluation = state["evaluation"]
        question = state.get("question")
        request = FollowUpQuestionRequest(
            original_question=state["turn"].question_content,
            answer=state["answer_content"],
            focus=evaluation.follow_up_focus or "澄清技术方案和结果",
            expected_points=tuple(question.expected_points) if question else (),
        )
        last_error: ValidationError | None = None
        for _attempt in range(2):
            try:
                generated = await self._follow_up_generator.generate(request)
                follow_up = GeneratedFollowUpQuestion.model_validate(generated)
                existing_turns = await self._repository.list_turns(
                    state["session_id"], state["user_id"]
                )
                normalized = follow_up.content.casefold()
                if any(turn.question_content.casefold() == normalized for turn in existing_turns):
                    raise InterviewEvaluationValidationError("Generated follow-up is duplicated")
                state["follow_up"] = follow_up
                evaluation.follow_up_question = follow_up.content
                return state
            except ValidationError as exc:
                last_error = exc
        if last_error is not None:
            raise InterviewEvaluationValidationError(
                "AI follow-up output is invalid"
            ) from last_error
        raise InterviewEvaluationValidationError("AI follow-up output is invalid")

    async def _persist_evaluation(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        await self._repository.persist_evaluation_and_progress(
            state["session_id"],
            state["turn_id"],
            state["user_id"],
            state["evaluation"],
            state["decision"].reason,
            state["decision"].should_follow_up,
        )
        return state

    async def _complete_current_turn(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        return state

    async def _create_next_turn(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        return state

    async def _complete_or_continue_session(
        self, state: InterviewAnswerGraphState
    ) -> InterviewAnswerGraphState:
        return state

    async def _fail(
        self, state: InterviewAnswerGraphState, failure_code: str, failure_message: str
    ) -> InterviewSession:
        return await self._repository.fail_evaluation(
            state["session_id"],
            state["turn_id"],
            state["user_id"],
            failure_code,
            failure_message,
        )
