import service, { assertRequestAuthorized, buildApiUrl } from "@/lib/request";
import type {
  AiConversationsPageResult,
  AiMessageHistoryListResult,
  AiMessageHistoryPageResult,
  AiPropertiesPageResult,
  ChatStreamParams,
  CreateConversationParams,
  CreateConversationResponse,
  GetAiPropertiesParams,
  GetConversationsParams,
  GetHistoryMessagesPageParams,
  StreamCallbacks,
} from "@/types/ai";
import { fetchEventSource } from "@microsoft/fetch-event-source";

type StreamParseResult = {
  content?: string;
  reasoning?: string;
  done?: boolean;
};

const STREAM_DONE_MARKERS = new Set([
  "done",
  "end",
  "message_end",
  "message_stop",
  "completed",
  "complete",
  "stop",
]);

const STREAM_REASONING_MARKERS = new Set([
  "reasoning",
  "reasoning_content",
  "thinking",
  "thinking_content",
]);

const normalizeStreamMarker = (value: unknown) =>
  typeof value === "string" ? value.trim().toLowerCase() : "";

const isDoneStreamMarker = (value: unknown) =>
  STREAM_DONE_MARKERS.has(normalizeStreamMarker(value));

const isDoneStreamEvent = (value: unknown) =>
  isDoneStreamMarker(value) || normalizeStreamMarker(value) === "[done]";

const parseAiStreamChunk = (raw: string): StreamParseResult => {
  const payload = raw.trim();
  if (!payload) {
    return {};
  }

  if (payload.toUpperCase() === "[DONE]") {
    return { done: true };
  }

  try {
    const parsed = JSON.parse(payload) as Record<string, unknown>;
    const nestedData =
      typeof parsed.data === "object" &&
      parsed.data !== null &&
      !Array.isArray(parsed.data)
        ? (parsed.data as Record<string, unknown>)
        : null;
    const source = nestedData ?? parsed;
    const type = normalizeStreamMarker(source.type);

    if (
      source.done === true ||
      isDoneStreamMarker(type) ||
      isDoneStreamMarker(source.action) ||
      isDoneStreamMarker(source.event) ||
      isDoneStreamMarker(source.finish_reason)
    ) {
      return { done: true };
    }

    if (typeof source.content === "string") {
      if (STREAM_REASONING_MARKERS.has(type)) {
        return { reasoning: source.content };
      }
      return { content: source.content };
    }

    if (typeof source.reasoning === "string") {
      return { reasoning: source.reasoning };
    }
    if (typeof source.reasoning_content === "string") {
      return { reasoning: source.reasoning_content };
    }
    if (typeof source.reasoningContent === "string") {
      return { reasoning: source.reasoningContent };
    }

    const choices = source.choices;
    if (Array.isArray(choices) && choices.length > 0) {
      const firstChoice = choices[0] as Record<string, unknown>;
      const delta = firstChoice.delta as Record<string, unknown> | undefined;
      const message = firstChoice.message as
        | Record<string, unknown>
        | undefined;
      if (
        isDoneStreamMarker(firstChoice.finish_reason) ||
        firstChoice.done === true
      ) {
        return { done: true };
      }
      if (typeof delta?.reasoning === "string") {
        return { reasoning: delta.reasoning };
      }
      if (typeof delta?.reasoning_content === "string") {
        return { reasoning: delta.reasoning_content };
      }
      if (typeof delta?.content === "string") {
        return { content: delta.content };
      }
      if (typeof message?.reasoning === "string") {
        return { reasoning: message.reasoning };
      }
      if (typeof message?.reasoning_content === "string") {
        return { reasoning: message.reasoning_content };
      }
      if (typeof message?.content === "string") {
        return { content: message.content };
      }
    }

    return {};
  } catch {
    return { content: payload };
  }
};

export const aiService = {
  getAiProperties: (params?: GetAiPropertiesParams) => {
    return service.get<AiPropertiesPageResult>("/xunzhi/v1/ai-properties", {
      params: {
        ...params,
        size: 100,
      },
    });
  },

  getConversations: (params?: GetConversationsParams) => {
    return service.get<AiConversationsPageResult>(
      "/xunzhi/v1/ai/conversations",
      {
        params,
      },
    );
  },

  getConversationHistory: (sessionId: string, signal?: AbortSignal) => {
    return service.get<AiMessageHistoryListResult>(
      `/xunzhi/v1/ai/history/${sessionId}`,
      signal ? { signal } : undefined,
    );
  },

  pageHistoryMessages: (params: GetHistoryMessagesPageParams) => {
    return service.get<AiMessageHistoryPageResult>(
      "/xunzhi/v1/ai/history/page",
      {
        params,
      },
    );
  },

  createConversation: (data: CreateConversationParams) => {
    return service.post<CreateConversationResponse>(
      "/xunzhi/v1/ai/conversations",
      data,
    );
  },

  streamChat: async (
    params: ChatStreamParams,
    signal: AbortSignal,
    callbacks: StreamCallbacks,
  ) => {
    const {
      sessionId,
      userName,
      inputMessage,
      aiId,
      messageSeq,
      imageUrls,
      mediaList,
    } = params;
    const url = buildApiUrl(
      `/xunzhi/v1/ai/sessions/${encodeURIComponent(sessionId)}/chat`,
      {
        username: userName,
      },
    );
    const token = assertRequestAuthorized(
      `/xunzhi/v1/ai/sessions/${encodeURIComponent(sessionId)}/chat`,
    );

    let isComplete = false;

    await fetchEventSource(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        sessionId,
        inputMessage,
        userName,
        aiId,
        messageSeq,
        imageUrls,
        mediaList,
      }),
      signal,
      openWhenHidden: true,

      async onopen(response) {
        if (response.ok) {
          return;
        }
        if (
          response.status >= 400 &&
          response.status < 500 &&
          response.status !== 429
        ) {
          throw new Error(`Failed to send chat: ${response.statusText}`);
        }
        throw new Error(`Server error: ${response.statusText}`);
      },

      onmessage(msg) {
        if (
          isDoneStreamEvent(msg.event) ||
          msg.data.trim().toUpperCase() === "[DONE]"
        ) {
          isComplete = true;
          callbacks.onDone?.();
          return;
        }

        const parsed = parseAiStreamChunk(msg.data);
        if (parsed.done) {
          isComplete = true;
          callbacks.onDone?.();
          return;
        }
        if (parsed.reasoning) {
          callbacks.onReasoning?.(parsed.reasoning);
        }
        if (parsed.content) {
          callbacks.onMessage(parsed.content);
        }
      },

      onclose() {
        if (!isComplete) {
          callbacks.onDone?.();
        }
        throw new Error("Connection closed");
      },

      onerror(err) {
        callbacks.onError?.(err);
        throw err;
      },
    });
  },
};
