import type { AxiosAdapter, AxiosResponse } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { tokenStore } from "@/lib/tokenStore";
import { InterviewReportsPage } from "@/pages/interview/InterviewReportsPage";

const report = {
  reportId: "report-1",
  sessionId: "session-1",
  status: "READY",
  jobTitle: "后端工程师",
  interviewType: "TECHNICAL",
  difficulty: "MEDIUM",
  overallScore: 88,
  dimensionScores: { technical: 88, relevance: 88, clarity: 88, depth: 88 },
  radarData: [],
  summary: "总结",
  strengths: [],
  weaknesses: [],
  suggestedImprovements: [],
  actionPlan: [],
  recommendedLevel: null,
  items: [],
  aggregationVersion: "v1",
  generatedBy: "RULES",
  createdAt: "2026-08-28T10:00:00Z",
  updatedAt: "2026-08-28T10:02:00Z",
  completedAt: "2026-08-28T10:02:00Z",
  failureCode: null,
  failureMessage: null,
};

const response = <T,>(config: Parameters<AxiosAdapter>[0], data: T): AxiosResponse<T> => ({
  data,
  status: 200,
  statusText: "OK",
  headers: {},
  config,
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
}

function renderPage(initialEntries = ["/interview/reports"]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/interview/reports" element={<><InterviewReportsPage /><LocationProbe /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  tokenStore.clear();
  resetApiClientForTests();
});

describe("InterviewReportsPage", () => {
  it("shows ready scores, safe failed state, and keeps the page in the URL", async () => {
    tokenStore.setTokens("access", "refresh");
    setApiAdapterForTests(async (config) => response(config, {
      records: [report, { ...report, reportId: "report-2", status: "FAILED", overallScore: 0, failureMessage: "安全失败信息" }],
      total: 11,
      size: 10,
      current: 1,
      pages: 2,
    }));
    renderPage();

    expect((await screen.findAllByText("后端工程师")).length).toBe(2);
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("生成失败")).toBeInTheDocument();
    const failedCard = screen.getByText("生成失败").closest("article");
    expect(failedCard?.textContent ?? "").not.toContain("0 / 100");
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("current=2"));
  });

  it("offers a clear empty state", async () => {
    tokenStore.setTokens("access", "refresh");
    setApiAdapterForTests(async (config) => response(config, { records: [], total: 0, size: 10, current: 1, pages: 0 }));
    renderPage();

    expect(await screen.findByText("完成一场面试后，报告会出现在这里")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "去创建面试" })).toHaveAttribute("href", "/interview");
  });
});
