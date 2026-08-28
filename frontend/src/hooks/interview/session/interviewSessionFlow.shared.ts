import { INTERVIEW_DEFAULTS } from "@/lib/constants";
import type { ChatMessage, ChatMessageStatus } from "@/lib/chat";
import type { AnswerInterviewQuestionResult } from "@/services/interviewService";

export type InterviewFlowUser = {
  id?: number | null;
  username?: string | null;
} | null;

export type InterviewProgressPatch = {
  currentQuestionNumber: string | null;
  currentQuestionContent: string | null;
  isCurrentQuestionFollowUp: boolean;
  currentFollowUpCount: number;
  isInterviewFinished: boolean;
  totalInterviewScore?: number | null;
};

export type InterviewFlowState = {
  messages: ChatMessage[];
  input: string;
  isInterviewSubmitting: boolean;
  interviewError: string | null;
  isEndingInterview: boolean;
  currentQuestionNumber: string | null;
  currentQuestionContent: string | null;
  isCurrentQuestionFollowUp: boolean;
  currentFollowUpCount: number;
  isInterviewFinished: boolean;
  totalInterviewScore: number | null;
};

export type InterviewMessageActions = {
  appendAssistantMessage: (
    content: string,
    options?: {
      fakeStream?: boolean;
      variant?: ChatMessage["variant"];
      streamStep?: number;
      streamDelayMs?: number;
      tts?: ChatMessage["tts"];
    },
  ) => Promise<void>;
  appendNextQuestionMessage: (
    nextQuestion: string,
    nextQuestionNumber: string | null | undefined,
    isFollowUp: boolean,
    followUpCount?: number,
    options?: { appendMessage?: boolean },
  ) => Promise<void>;
  appendSystemMessage: (content: string, status?: ChatMessageStatus) => void;
  startThinkingIndicator: () => void;
  stopThinkingIndicator: (options?: { remove?: boolean }) => void;
  cancelActiveQuestionStream: () => void;
};

export const FOLLOW_UP_STREAM_STEP = 2;
export const FOLLOW_UP_STREAM_DELAY_MS = 26;
export const THINKING_PROGRESS_STEP_DELAY_MS = 1_200;
export const THINKING_PROGRESS_STAGES = [
  "正在分析回答内容",
  "正在生成反馈结论",
  "正在准备下一题",
] as const;
export const FEEDBACK_STREAM_STEP = 2;
export const FEEDBACK_STREAM_DELAY_MS = 18;
export const INTERVIEW_MESSAGE_GAP_MS = 180;
export const AUTO_SAVE_SUCCESS_TEXT =
  "面试记录已自动保存，点击“结束面试”即可查看报告。";
export const AUTO_SAVE_FAILED_TEXT =
  "面试已结束，但自动保存失败。你可以点击“结束面试”重新保存。";

export const isInterviewResponseFailed = (isSuccess?: boolean) =>
  isSuccess === false;

export const buildInterviewProgressPatch = (
  response: AnswerInterviewQuestionResult,
): InterviewProgressPatch => {
  const isInterviewFinished = Boolean(response.finished);
  const nextQuestion =
    response.nextQuestion?.trim() || response.questionContent?.trim() || null;

  return {
    currentQuestionNumber:
      response.nextQuestionNumber || response.questionNumber || null,
    currentQuestionContent: isInterviewFinished ? null : nextQuestion,
    isCurrentQuestionFollowUp: isInterviewFinished
      ? false
      : Boolean(response.isFollowUp),
    currentFollowUpCount: isInterviewFinished
      ? 0
      : typeof response.followUpCount === "number"
        ? response.followUpCount
        : 0,
    isInterviewFinished,
    totalInterviewScore:
      typeof response.totalScore === "number" ? response.totalScore : undefined,
  };
};

export const isMessageInWelcomeState = (messages: ChatMessage[]) =>
  messages.length === 1 &&
  messages[0]?.role === "assistant" &&
  messages[0]?.content === INTERVIEW_DEFAULTS.assistantWelcomeMessage;
