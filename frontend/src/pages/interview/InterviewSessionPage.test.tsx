import type { AxiosAdapter, AxiosResponse } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { tokenStore } from "@/lib/tokenStore";
import { InterviewSessionPage } from "@/pages/interview/InterviewSessionPage";

const session = { id: "s", sessionId: "s", userId: "secret", knowledgeBaseId: "kb", jobTitle: "后端工程师", interviewType: "TECHNICAL", difficulty: "MEDIUM", questionCount: 3, status: "READY", currentQuestionIndex: 0, preparationProgress: 100, canStart: true, version: 1, requestId: null, failureCode: null, failureMessage: null, createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z", preparedAt: "2026-01-01T00:00:00Z", startedAt: null, finishedAt: null };
const turn = { turnId: "t", sessionId: "s", questionId: "q", parentTurnId: null, turnType: "PRIMARY", question: "请介绍一下你做过的异步项目。", sequence: 1, followUpDepth: 0, status: "WAITING_ANSWER", canAnswer: true, answer: null, answerRequestId: null, answeredAt: null, evaluation: null, createdAt: "2026-01-01T00:00:00Z", evaluatedAt: null };
const response = <T,>(config: Parameters<AxiosAdapter>[0], data: T): AxiosResponse<T> => ({ data, status: 200, statusText: "OK", headers: {}, config });

afterEach(() => { vi.restoreAllMocks(); tokenStore.clear(); resetApiClientForTests(); });

describe("InterviewSessionPage", () => {
  it("starts a READY session and restores the current turn", async () => {
    tokenStore.setTokens("access", "refresh");
    let started = false;
    setApiAdapterForTests(async (config) => {
      const url = config.url ?? "";
      if (url.endsWith("/sessions/s") && config.method === "get") return response(config, { ...session, status: started ? "IN_PROGRESS" : "READY", canStart: !started });
      if (url.endsWith("/sessions/s/start")) { started = true; return response(config, { ...session, status: "IN_PROGRESS", canStart: false }); }
      if (url.endsWith("/sessions/s/current-turn")) return response(config, turn);
      if (url.endsWith("/sessions/s/turns")) return response(config, [turn]);
      return response(config, {});
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/interview/s"]}><Routes><Route path="/interview/:sessionId" element={<InterviewSessionPage />} /></Routes></MemoryRouter></QueryClientProvider>);
    fireEvent.click(await screen.findByRole("button", { name: "开始面试" }));
    expect(await screen.findByText("请介绍一下你做过的异步项目。", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("PRIMARY · 基础题")).toBeInTheDocument();
  });
});
