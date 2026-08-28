import { CHAT_ROLES, INTERVIEW_DEFAULTS } from "@/lib/constants";
import {
  CHAT_MESSAGE_STATUS,
  CHAT_MESSAGE_VARIANT,
  type ChatMessage,
  type ChatMessageTts,
  type ChatMessageStatus,
  type ChatMessageVariant,
} from "@/lib/chat";

const interviewTypeLabelMap: Record<string, string> = {
  backend: "Backend",
  frontend: "Frontend",
  fullstack: "Fullstack",
  algorithm: "Algorithm",
  test: "Test",
  devops: "DevOps",
};

export const resolveInterviewTypeLabel = (interviewType: string | null) => {
  if (!interviewType) return "Unknown";
  const normalized = interviewType.trim().toLowerCase();
  return interviewTypeLabelMap[normalized] || interviewType;
};

export const toSuggestionList = (suggestions?: Record<string, string>) => {
  if (!suggestions) return [];
  return Object.entries(suggestions)
    .sort(([a], [b]) => {
      const numA = Number(a);
      const numB = Number(b);
      if (Number.isNaN(numA) || Number.isNaN(numB)) {
        return a.localeCompare(b, "zh-CN");
      }
      return numA - numB;
    })
    .map(([, value]) => value)
    .filter((value) => value && value.trim().length > 0);
};

type CreateAssistantMessageOptions = {
  status?: ChatMessageStatus;
  variant?: ChatMessageVariant;
  tts?: ChatMessageTts;
  progressSteps?: string[];
  activeProgressStep?: number;
};

export const createWelcomeMessage = (
  options?: CreateAssistantMessageOptions,
): ChatMessage => ({
  id: `${INTERVIEW_DEFAULTS.initialMessageId}-${Date.now()}`,
  role: CHAT_ROLES.assistant,
  content: INTERVIEW_DEFAULTS.assistantWelcomeMessage,
  timestamp: Date.now(),
  status: options?.status ?? CHAT_MESSAGE_STATUS.done,
  variant: options?.variant ?? CHAT_MESSAGE_VARIANT.system,
});

export const createAssistantMessage = (
  content: string,
  options?: CreateAssistantMessageOptions,
): ChatMessage => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  role: CHAT_ROLES.assistant,
  content,
  timestamp: Date.now(),
  status: options?.status ?? CHAT_MESSAGE_STATUS.done,
  variant: options?.variant ?? CHAT_MESSAGE_VARIANT.default,
  tts: options?.tts,
  progressSteps: options?.progressSteps,
  activeProgressStep: options?.activeProgressStep,
});

export const createUserMessage = (content: string): ChatMessage => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  role: CHAT_ROLES.user,
  content,
  timestamp: Date.now(),
  status: CHAT_MESSAGE_STATUS.done,
});

export const generateRequestId = () => {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
};
