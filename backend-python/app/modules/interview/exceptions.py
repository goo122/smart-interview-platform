from app.core.exceptions import AppError


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


class InterviewPreparationError(AppError):
    status_code = 422
    code = "interview_preparation_failed"


class InterviewKnowledgeUnavailableError(InterviewPreparationError):
    code = "interview_knowledge_unavailable"


class InterviewQuestionValidationError(InterviewPreparationError):
    code = "interview_questions_invalid"


class InterviewPreparationInProgressError(InvalidInterviewTransitionError):
    code = "interview_preparation_in_progress"


class InterviewTurnNotFoundError(AppError):
    status_code = 404
    code = "interview_turn_not_found"


class InterviewAnswerError(AppError):
    status_code = 400
    code = "invalid_interview_answer"


class InterviewAnswerConflictError(AppError):
    status_code = 409
    code = "interview_answer_conflict"


class InterviewEvaluationError(AppError):
    status_code = 422
    code = "interview_evaluation_failed"


class InterviewEvaluationValidationError(InterviewEvaluationError):
    code = "interview_evaluation_invalid"
