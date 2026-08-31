from app.core.exceptions import AppError
from app.workers.queue import RetryableTaskError


class InterviewNotFoundError(AppError):
    status_code = 404
    code = "interview_not_found"


class InvalidInterviewRequestError(AppError):
    status_code = 400
    code = "invalid_interview_request"


class InterviewRequestAlreadyExistsError(AppError):
    status_code = 409
    code = "interview_request_exists"


class InvalidInterviewTransitionError(AppError):
    status_code = 409
    code = "invalid_interview_transition"


class InterviewFinishWithoutCompletedAnswersError(InvalidInterviewTransitionError):
    code = "interview_finish_without_completed_answers"


class InterviewPreparationError(AppError):
    status_code = 422
    code = "interview_preparation_failed"


class InterviewKnowledgeUnavailableError(InterviewPreparationError):
    code = "interview_knowledge_unavailable"


class InterviewQuestionValidationError(InterviewPreparationError):
    code = "interview_questions_invalid"


class InterviewPreparationInProgressError(InvalidInterviewTransitionError):
    code = "interview_preparation_in_progress"


class InterviewPreparationQueueUnavailableError(AppError):
    status_code = 503
    code = "interview_preparation_queue_unavailable"


class RetryableInterviewPreparationError(RetryableTaskError):
    """Signal that an ARQ interview-preparation delivery should be retried."""


class InterviewTurnNotFoundError(AppError):
    status_code = 404
    code = "interview_turn_not_found"


class InterviewAnswerError(AppError):
    status_code = 400
    code = "invalid_interview_answer"


class InterviewAnswerConflictError(AppError):
    status_code = 409
    code = "interview_answer_conflict"


class InterviewEvaluationQueueUnavailableError(AppError):
    status_code = 503
    code = "interview_evaluation_queue_unavailable"


class InterviewEvaluationError(AppError):
    status_code = 422
    code = "interview_evaluation_failed"


class InterviewEvaluationValidationError(InterviewEvaluationError):
    code = "interview_evaluation_invalid"
