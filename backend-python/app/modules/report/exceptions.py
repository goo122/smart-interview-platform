from app.core.exceptions import AppError


class ReportNotFoundError(AppError):
    status_code = 404
    code = "interview_report_not_found"


class ReportSessionNotCompletedError(AppError):
    status_code = 409
    code = "interview_report_session_not_completed"


class ReportWithoutCompletedAnswersError(ReportSessionNotCompletedError):
    code = "interview_report_without_completed_answers"


class ReportGenerationError(AppError):
    status_code = 422
    code = "interview_report_generation_failed"


class ReportQueueUnavailableError(AppError):
    status_code = 503
    code = "interview_report_queue_unavailable"


class ReportLeaseLostError(RuntimeError):
    """Raised when a worker no longer owns the report generation lease."""
