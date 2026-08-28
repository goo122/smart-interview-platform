import { afterEach, describe, expect, it, vi } from "vitest";
import type { AxiosAdapter, AxiosResponse } from "axios";
import { resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { streamChat } from "@/features/chat/sse";
import { tokenStore } from "@/lib/tokenStore";

const streamResponse = (chunks: Uint8Array[]) => {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
};

afterEach(() => {
  vi.restoreAllMocks();
  tokenStore.clear();
  resetApiClientForTests();
});

describe("POST SSE client", () => {
  it("parses split UTF-8 chunks, multiple data lines and ordered events", async () => {
    tokenStore.setTokens("access-token", "refresh-token");
    const bytes = new TextEncoder().encode([
      "event: start\ndata: {\"conversation_id\":\"c1\",\"message_id\":\"m1\"}\n\n",
      "event: delta\ndata: {\"content\":\"你\"}\n\n",
      "event: delta\ndata: {\"content\":\"好\"}\n\n",
      "event: complete\ndata: {\"message_id\":\"m1\",\n",
      "data: \"content\":\"你好\",\"citations\":[]}\n\n",
    ].join(""));
    const split = [bytes.slice(0, 7), bytes.slice(7, 11), bytes.slice(11, 53), bytes.slice(53)];
    let request: Request | undefined;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      request = new Request(new URL(String(input), "http://localhost:8080"), init);
      return streamResponse(split);
    }));
    const events: string[] = [];
    const contents: string[] = [];
    await streamChat("c1", { inputMessage: "你好", requestId: "stable-id" }, {
      onEvent: (event) => {
        events.push(event.event);
        if (event.event === "delta") contents.push(event.data.content);
      },
    }, new AbortController().signal);

    expect(events).toEqual(["start", "delta", "delta", "complete"]);
    expect(contents.join("")).toBe("你好");
    expect(request?.method).toBe("POST");
    expect(request?.headers.get("Authorization")).toBe("Bearer access-token");
    expect(await request?.json()).toMatchObject({ inputMessage: "你好", requestId: "stable-id" });
  });

  it("re-authenticates one 401 and retries with the same request id", async () => {
    tokenStore.setTokens("expired-access", "refresh-token");
    const requests: Request[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(new URL(String(input), "http://localhost:8080"), init);
      requests.push(request);
      if (requests.length === 1) return new Response(null, { status: 401 });
      return streamResponse([new TextEncoder().encode("event: complete\ndata: {\"message_id\":\"m1\",\"content\":\"ok\"}\n\n")]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const adapter: AxiosAdapter = async (config) => {
      const data: AxiosResponse = {
        data: { access_token: "new-access", refresh_token: "new-refresh", token_type: "bearer", expires_in: 1800 },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      };
      return data;
    };
    setApiAdapterForTests(adapter);
    await streamChat("c1", { inputMessage: "再试一次", requestId: "stable-id", knowledgeBaseId: "base-1", topK: 5 }, { onEvent: vi.fn() }, new AbortController().signal);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const firstBody = await requests[0]?.json();
    const secondBody = await requests[1]?.json();
    expect(firstBody).toEqual(secondBody);
    expect(firstBody).toMatchObject({ knowledgeBaseId: "base-1", topK: 5, requestId: "stable-id" });
    expect(requests[1]?.headers.get("Authorization")).toBe("Bearer new-access");
    expect(tokenStore.getAccessToken()).toBe("new-access");
  });

  it("stops promptly when the request is aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    vi.stubGlobal("fetch", vi.fn(async () => streamResponse([])));
    await expect(streamChat("c1", { inputMessage: "stop", requestId: "id" }, { onEvent: vi.fn() }, controller.signal)).rejects.toMatchObject({ name: "AbortError" });
  });
});
