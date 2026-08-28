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
  interview_not_found: "找不到这场面试，可能已被删除或无权访问",
  interview_turn_not_found: "当前问题已不可用，请刷新面试房间",
  invalid_interview_request: "面试参数不正确，请检查后重试",
  interview_request_exists: "这次面试正在创建中，请稍候",
  invalid_interview_transition: "面试状态已变化，请刷新页面",
  interview_preparation_failed: "出题准备失败，请重新创建面试",
  interview_knowledge_unavailable: "所选知识库暂不可用，请先检查简历状态",
  invalid_interview_answer: "回答内容不符合要求，请检查长度后重试",
  interview_answer_conflict: "这轮回答已提交，请等待评分结果",
  interview_evaluation_failed: "本轮评分失败，请稍后重试",
  interview_evaluation_invalid: "评分结果暂不可用，请稍后重试",
  interview_report_not_found: "面试报告尚未生成",
  interview_report_session_not_completed: "面试完成后才能生成报告",
  interview_report_generation_failed: "报告生成失败，请稍后重试",
  interview_report_queue_failed: "报告任务提交失败，请稍后重试",
  report_not_found: "面试报告尚未生成",
  report_session_not_completed: "面试完成后才能生成报告",
  report_generation_failed: "报告生成失败，请稍后重试",
  report_queue_failed: "报告任务提交失败，请稍后重试",
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
