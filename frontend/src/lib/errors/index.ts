export const ErrorCode = {
  // Generic errors (1000-1999)
  UNKNOWN_ERROR: 1000,
  NETWORK_ERROR: 1001,
  REQUEST_TIMEOUT: 1002,
  ABORTED: 1003,

  // Auth errors (2000-2999)
  UNAUTHORIZED: 2001,
  FORBIDDEN: 2002,
  TOKEN_EXPIRED: 2003,

  // Business errors (3000-3999)
  INVALID_PARAMS: 3001,
  RESOURCE_NOT_FOUND: 3002,
  OPERATION_FAILED: 3003,

  // AI errors (4000-4999)
  AI_SERVICE_UNAVAILABLE: 4001,
  AI_QUOTA_EXCEEDED: 4002,
  AI_RESPONSE_ERROR: 4003,
  AI_STREAM_PARSING_ERROR: 4004,

  // Client errors (5000-5999)
  CLIENT_VALIDATION_ERROR: 5001,
  FILE_UPLOAD_ERROR: 5002,
  CAMERA_PERMISSION_DENIED: 5003,
  MICROPHONE_PERMISSION_DENIED: 5004,
} as const;

export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];

export const ErrorMessages: Record<ErrorCode, string> = {
  [ErrorCode.UNKNOWN_ERROR]: "Unknown error occurred. Please try again later.",
  [ErrorCode.NETWORK_ERROR]:
    "Network connection failed. Please check your connection.",
  [ErrorCode.REQUEST_TIMEOUT]: "Request timeout. Please try again later.",
  [ErrorCode.ABORTED]: "Request was cancelled.",

  [ErrorCode.UNAUTHORIZED]: "Session expired. Please sign in again.",
  [ErrorCode.FORBIDDEN]: "You do not have permission to perform this action.",
  [ErrorCode.TOKEN_EXPIRED]: "Authentication token has expired.",

  [ErrorCode.INVALID_PARAMS]: "Invalid request parameters.",
  [ErrorCode.RESOURCE_NOT_FOUND]: "Requested resource does not exist.",
  [ErrorCode.OPERATION_FAILED]: "Operation failed. Please retry.",

  [ErrorCode.AI_SERVICE_UNAVAILABLE]:
    "AI service is unavailable. Please retry later.",
  [ErrorCode.AI_QUOTA_EXCEEDED]: "AI quota exceeded.",
  [ErrorCode.AI_RESPONSE_ERROR]: "AI response failed.",
  [ErrorCode.AI_STREAM_PARSING_ERROR]: "Failed to parse AI stream response.",

  [ErrorCode.CLIENT_VALIDATION_ERROR]:
    "Client validation failed. Please check your input.",
  [ErrorCode.FILE_UPLOAD_ERROR]: "File upload failed.",
  [ErrorCode.CAMERA_PERMISSION_DENIED]:
    "Camera access denied. Please check browser permissions.",
  [ErrorCode.MICROPHONE_PERMISSION_DENIED]:
    "Microphone access denied. Please check browser permissions.",
};

export class AppError extends Error {
  public code: ErrorCode;
  public originalError?: unknown;

  constructor(code: ErrorCode, message?: string, originalError?: unknown) {
    super(message || ErrorMessages[code]);
    this.name = "AppError";
    this.code = code;
    this.originalError = originalError;
  }

  static from(
    error: unknown,
    defaultCode: ErrorCode = ErrorCode.UNKNOWN_ERROR,
  ): AppError {
    if (error instanceof AppError) {
      return error;
    }

    if (error instanceof Error) {
      if (error.name === "AbortError") {
        return new AppError(ErrorCode.ABORTED, "Request was cancelled.", error);
      }
      return new AppError(defaultCode, error.message, error);
    }

    if (typeof error === "string") {
      return new AppError(defaultCode, error);
    }

    return new AppError(defaultCode, undefined, error);
  }
}
