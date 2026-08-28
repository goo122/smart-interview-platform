import type { AxiosAdapter, AxiosResponse } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { tokenStore } from "@/lib/tokenStore";
import { InterviewSetupPage } from "@/pages/interview/InterviewSetupPage";

const base = { id: "00000000-0000-0000-0000-000000000001", user_id: "u", name: "简历", description: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const readyDocument = { id: "d1", knowledge_base_id: base.id, original_filename: "resume.pdf", safe_filename: "resume.pdf", content_type: "application/pdf", size_bytes: 10, sha256: "hash", status: "READY", page_count: 1, chunk_count: 1, error_code: null, error_message: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", completed_at: "2026-01-01T00:00:00Z" };
const response = <T,>(config: Parameters<AxiosAdapter>[0], data: T): AxiosResponse<T> => ({ data, status: 200, statusText: "OK", headers: {}, config });

afterEach(() => { vi.restoreAllMocks(); tokenStore.clear(); resetApiClientForTests(); });

describe("InterviewSetupPage", () => {
  it("only offers knowledge bases with READY documents and keeps one create request", async () => {
    tokenStore.setTokens("access", "refresh");
    let createCalls = 0;
    let body = "";
    setApiAdapterForTests(async (config) => {
      const url = config.url ?? "";
      if (url.endsWith("/knowledge-bases") && config.method === "get") return response(config, { records: [base, { ...base, id: "00000000-0000-0000-0000-000000000002", name: "空知识库" }], total: 2, size: 50, current: 1, pages: 1 });
      if (url.includes(`/knowledge-bases/${base.id}/documents`)) return response(config, { records: [readyDocument], total: 1, size: 100, current: 1, pages: 1 });
      if (url.includes("/knowledge-bases/00000000-0000-0000-0000-000000000002/documents")) return response(config, { records: [], total: 0, size: 100, current: 1, pages: 0 });
      if (url.endsWith("/interview/sessions") && config.method === "post") { createCalls += 1; body = String(config.data); await new Promise((resolve) => setTimeout(resolve, 20)); return response(config, { id: "s", sessionId: "s", userId: "hidden", knowledgeBaseId: base.id, jobTitle: "后端", interviewType: "TECHNICAL", difficulty: "MEDIUM", questionCount: 8, status: "PREPARING", currentQuestionIndex: 0, preparationProgress: 0, canStart: false, version: 0, createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z" }); }
      return response(config, {});
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><MemoryRouter><InterviewSetupPage /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("option", { name: "简历" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "空知识库" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("简历知识库"), { target: { value: base.id } });
    expect((screen.getByLabelText("简历知识库") as HTMLSelectElement).value).toBe(base.id);
    fireEvent.change(screen.getByLabelText("岗位名称"), { target: { value: "后端工程师" } });
    fireEvent.change(screen.getByLabelText("岗位描述"), { target: { value: "负责服务端开发" } });
    const button = screen.getByRole("button", { name: "创建面试" });
    fireEvent.click(button); fireEvent.click(button);
    await waitFor(() => expect(createCalls).toBe(1));
    expect(JSON.parse(body)).not.toHaveProperty("userId");
    expect(JSON.parse(body).requestId).toBeTruthy();
  });
});
