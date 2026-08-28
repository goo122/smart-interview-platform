import { apiClient, requestData } from "@/api/client";
import type {
  ChatHistoryPage,
  ChatMessageResponse,
  ConversationPage,
  ConversationResponse,
  CreateConversationRequest,
  CreateConversationResponse,
  DeleteResponse,
} from "@/api/generated";
import { streamChat } from "@/features/chat/sse";
import type { ChatPayload, ChatStreamEvent } from "@/features/chat/types";

export const chatApi = {
  listConversations: (current = 1, size = 50) =>
    requestData(
      apiClient.get<ConversationPage>("/xunzhi/v1/ai/conversations", {
        params: { current, size },
      }),
    ),
  createConversation: (payload: CreateConversationRequest = {}) =>
    requestData(apiClient.post<CreateConversationResponse>("/xunzhi/v1/ai/conversations", payload)),
  getConversation: (sessionId: string) =>
    requestData(apiClient.get<ConversationResponse>(`/xunzhi/v1/ai/conversations/${sessionId}`)),
  finishConversation: (sessionId: string) =>
    requestData(apiClient.post<ConversationResponse>(`/xunzhi/v1/ai/conversations/${sessionId}/end`)),
  deleteConversation: (sessionId: string) =>
    requestData(apiClient.delete<DeleteResponse>(`/xunzhi/v1/ai/conversations/${sessionId}`)),
  listMessages: (sessionId: string) =>
    requestData(apiClient.get<ChatMessageResponse[]>(`/xunzhi/v1/ai/history/${sessionId}`)),
  listMessagesPage: (sessionId: string, current = 1, size = 100) =>
    requestData(
      apiClient.get<ChatHistoryPage>("/xunzhi/v1/ai/history/page", {
        params: { sessionId, current, size },
      }),
    ),
  streamMessage: (
    sessionId: string,
    payload: ChatPayload,
    onEvent: (event: ChatStreamEvent) => void,
    signal: AbortSignal,
  ) => streamChat(sessionId, payload, { onEvent }, signal),
};
