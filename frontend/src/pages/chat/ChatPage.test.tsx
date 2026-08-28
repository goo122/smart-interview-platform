import type { AxiosAdapter, AxiosResponse } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { ChatPage } from "@/pages/chat/ChatPage";
import { tokenStore } from "@/lib/tokenStore";

const conversation = {
  id: "00000000-0000-0000-0000-000000000001",
  user_id: "00000000-0000-0000-0000-000000000002",
  title: "技术准备",
  status: 1,
  statusName: "ACTIVE",
  modelName: null,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
  finishedAt: null,
  sessionId: "00000000-0000-0000-0000-000000000001",
  username: "testuser",
  aiId: null,
  aiName: null,
  messageCount: 0,
  lastMessageTime: null,
  createTime: "2026-01-01T00:00:00Z",
  updateTime: "2026-01-01T00:00:00Z",
};

function response<T>(config: Parameters<AxiosAdapter>[0], data: T): AxiosResponse<T> {
  return { data, status: 200, statusText: "OK", headers: {}, config };
}

const sse = (text: string) => new Response(text, { status: 200, headers: { "Content-Type": "text/event-stream" } });

afterEach(() => {
  vi.restoreAllMocks();
  tokenStore.clear();
  resetApiClientForTests();
});

describe("ChatPage", () => {
  it("shows history, sends a normal chat request and renders streamed content", async () => {
    tokenStore.setTokens("access", "refresh");
    setApiAdapterForTests(async (config) => {
      if ((config.url ?? "").includes("/conversations") && config.method === "get") {
        return response(config, { records: [conversation], total: 1, size: 50, current: 1, pages: 1 });
      }
      if ((config.url ?? "").includes("/history/")) return response(config, []);
      if ((config.url ?? "").includes("/knowledge-bases")) return response(config, { records: [], total: 0, size: 50, current: 1, pages: 0 });
      return response(config, {});
    });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => {
      void _input;
      void _init;
      return sse([
        "event: start\ndata: {\"conversation_id\":\"c1\",\"message_id\":\"m1\"}\n\n",
        "event: delta\ndata: {\"content\":\"你好\"}\n\n",
        "event: complete\ndata: {\"message_id\":\"m1\",\"content\":\"你好\",\"citations\":[]}\n\n",
      ].join(""));
    });
    vi.stubGlobal("fetch", fetchMock);

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[`/chat?sessionId=${conversation.sessionId}`]}><ChatPage /></MemoryRouter></QueryClientProvider>);
    const input = await screen.findByPlaceholderText(/输入你的问题/);
    fireEvent.change(input, { target: { value: "介绍一下异步编程" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(screen.getAllByText("你好").length).toBeGreaterThan(0));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(options.body))).not.toHaveProperty("knowledgeBaseId");
  });
});
