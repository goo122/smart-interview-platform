import type {
  InterviewDifficulty,
  InterviewEvaluationResponse,
  InterviewSessionResponse,
  InterviewTurnResponse,
  InterviewType,
} from "@/api/generated";

export type InterviewStatus =
  | "CREATED"
  | "PREPARING"
  | "READY"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type TurnStatus = "WAITING_ANSWER" | "EVALUATING" | "COMPLETED" | "FAILED";
export type TurnType = "PRIMARY" | "FOLLOW_UP";

export type InterviewSession = InterviewSessionResponse & { status: InterviewStatus };
export type InterviewTurn = InterviewTurnResponse & {
  status: TurnStatus;
  turnType: TurnType;
};
export type InterviewEvaluation = InterviewEvaluationResponse;

export const interviewTypeLabels: Record<InterviewType, string> = {
  TECHNICAL: "技术面",
  BEHAVIORAL: "行为面",
  MIXED: "综合面",
};

export const difficultyLabels: Record<InterviewDifficulty, string> = {
  EASY: "基础",
  MEDIUM: "中等",
  HARD: "进阶",
};

export const statusLabels: Record<InterviewStatus, string> = {
  CREATED: "已创建",
  PREPARING: "准备中",
  READY: "可以开始",
  IN_PROGRESS: "进行中",
  COMPLETED: "已完成",
  FAILED: "准备失败",
  CANCELLED: "已取消",
};

export const isTerminalSession = (status: InterviewStatus) =>
  status === "COMPLETED" || status === "FAILED" || status === "CANCELLED";

export const isPreparationStatus = (status: InterviewStatus) =>
  status === "CREATED" || status === "PREPARING";

