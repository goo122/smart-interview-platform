import { type ChatRole } from "@/lib/constants";

export const CHAT_MESSAGE_STATUS = {
  idle: "idle",
  streaming: "streaming",
  done: "done",
  error: "error",
} as const;

export const CHAT_MESSAGE_VARIANT = {
  default: "default",
  feedback: "feedback",
  followUp: "followUp",
  system: "system",
  progress: "progress",
} as const;

export type ChatMessageStatus =
  (typeof CHAT_MESSAGE_STATUS)[keyof typeof CHAT_MESSAGE_STATUS];

export type ChatMessageVariant =
  (typeof CHAT_MESSAGE_VARIANT)[keyof typeof CHAT_MESSAGE_VARIANT];

export type ChatMessageTts = {
  text?: string;
  autoPlay?: boolean;
  cacheKey?: string;
};

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  reasoning?: string;
  timestamp: number;
  status?: ChatMessageStatus;
  variant?: ChatMessageVariant;
  tts?: ChatMessageTts;
  progressSteps?: string[];
  activeProgressStep?: number;
};
