import { apiErrorFromResponse } from "@/api/errors";
import { refreshAccessTokenForSse } from "@/api/client";
import { frontendEnv } from "@/config/env";
import { tokenStore } from "@/lib/tokenStore";
import type { ChatPayload, ChatStreamEvent } from "@/features/chat/types";

type StreamHandlers = {
  onEvent: (event: ChatStreamEvent) => void;
};

const parseEvent = (eventName: string, data: string): ChatStreamEvent | null => {
  if (!data) return null;
  try {
    const parsed = JSON.parse(data) as unknown;
    if (eventName === "start" || eventName === "delta" || eventName === "complete" || eventName === "error") {
      return { event: eventName, data: parsed } as ChatStreamEvent;
    }
  } catch {
    // Ignore malformed server events; the request will continue until a valid terminal event arrives.
  }
  return null;
};

const consumeSse = async (
  body: ReadableStream<Uint8Array>,
  handlers: StreamHandlers,
  signal: AbortSignal,
) => {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  let dataLines: string[] = [];
  let terminal = false;
  const dispatch = () => {
    const event = parseEvent(eventName, dataLines.join("\n"));
    if (event) {
      handlers.onEvent(event);
      terminal = event.event === "complete" || event.event === "error";
    }
    eventName = "message";
    dataLines = [];
  };

  while (true) {
    if (signal.aborted) throw new DOMException("The operation was aborted", "AbortError");
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).replace(/\r$/, "");
      buffer = buffer.slice(newlineIndex + 1);
      if (!line) dispatch();
      else if (line.startsWith("event:")) eventName = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      newlineIndex = buffer.indexOf("\n");
    }
    if (done) {
      if (buffer) {
        const line = buffer.replace(/\r$/, "");
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      dispatch();
      return terminal;
    }
  }
};

const request = (baseUrl: string, sessionId: string, payload: ChatPayload, signal: AbortSignal) =>
  fetch(`${baseUrl}/xunzhi/v1/ai/sessions/${encodeURIComponent(sessionId)}/chat`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...(tokenStore.getAccessToken() ? { Authorization: `Bearer ${tokenStore.getAccessToken()}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  });

export async function streamChat(
  sessionId: string,
  payload: ChatPayload,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  let response = await request(frontendEnv.apiBaseUrl, sessionId, payload, signal);
  if (response.status === 401) {
    const accessToken = await refreshAccessTokenForSse();
    if (!accessToken) throw apiErrorFromResponse(401, { error: { code: "invalid_refresh_token" } });
    response = await request(frontendEnv.apiBaseUrl, sessionId, payload, signal);
  }
  if (!response.ok || !response.body) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw apiErrorFromResponse(response.status, body);
  }
  const completed = await consumeSse(response.body, handlers, signal);
  if (!completed) throw new Error("SSE stream ended unexpectedly");
}
