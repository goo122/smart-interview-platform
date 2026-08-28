import { isAxiosError } from "axios";

export type ApiErrorDetails = unknown;

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    details?: ApiErrorDetails;
  };
};

const messages: Record<string, string> = {
  authentication_failed: "账号或密码不正确",
  invalid_refresh_token: "登录状态已过期，请重新登录",
  user_already_exists: "用户名或邮箱已被使用",
  validation_error: "请检查填写内容",
  internal_server_error: "服务暂时不可用，请稍后再试",
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetails;

  constructor(status: number, code: string, message: string, details?: ApiErrorDetails) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const apiErrorFromResponse = (
  status: number,
  payload: unknown,
): ApiError => {
  const envelope = payload as ErrorEnvelope | null;
  const code = envelope?.error?.code || "request_failed";
  const message = messages[code] || envelope?.error?.message || "请求失败，请稍后再试";
  return new ApiError(status, code, message, envelope?.error?.details);
};

export const toUserMessage = (error: unknown): string => {
  if (error instanceof ApiError) return error.message;
  if (isAxiosError(error) && !error.response) return "网络连接失败，请检查网络后重试";
  if (error instanceof TypeError) return "网络连接失败，请检查网络后重试";
  return "操作失败，请稍后再试";
};
