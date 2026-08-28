import { CHAT_ROLES, ROUTES } from "@/lib/constants";
import { CHAT_MESSAGE_STATUS, type ChatMessage } from "@/lib/chat";
import type { AiMessageHistory, AiProperty } from "@/types/ai";

export type ChatPageLocationState = {
  initialQuery?: string;
  model?: AiProperty | null;
};

export const CHAT_HISTORY_LOADING_TITLE = "正在加载会话...";
export const CHAT_STREAM_ERROR_TEXT =
  "消息流处理中断，请稍后重试或重新发送。";

export const buildChatSessionPath = (sessionId: string) =>
  `${ROUTES.chat}/${encodeURIComponent(sessionId)}`;

export const normalizeInitialQuery = (value: unknown) => {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
};

export const normalizeHistoryMessages = (
  messages: AiMessageHistory[] | null | undefined,
): ChatMessage[] => {
  return (messages ?? [])
    .map((message) => ({
      id: message.id,
      role:
        message.messageType === 1 ? CHAT_ROLES.user : CHAT_ROLES.assistant,
      content: message.messageContent,
      reasoning: message.reasoningContent || undefined,
      timestamp: new Date(message.createTime || Date.now()).getTime(),
      status: message.errorMessage
        ? CHAT_MESSAGE_STATUS.error
        : CHAT_MESSAGE_STATUS.done,
    }))
    .sort((a, b) => a.timestamp - b.timestamp);
};

export const createRuntimeMessageId = (prefix: string) =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
