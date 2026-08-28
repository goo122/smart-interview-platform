import type { AxiosAdapter, AxiosResponse } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { tokenStore } from "@/lib/tokenStore";
import { InterviewReportDetailPage } from "@/pages/interview/InterviewReportDetailPage";

const report = {
  reportId: "report-1",
  sessionId: "session-1",
  status: "READY",
  jobTitle: "后端工程师",
  interviewType: "TECHNICAL",
  difficulty: "MEDIUM",
  overallScore: 84,
  dimensionScores: { technical: 90, relevance: 82, clarity: 86, depth: 78 },
  radarData: [
    { dimension: "technical", score: 90 },
    { dimension: "relevance", score: 82 },
    { dimension: "clarity", score: 86 },
    { dimension: "depth", score: 78 },
  ],
  summary: "回答结构清晰，具备良好的服务端实践。",
  strengths: ["能清楚说明取舍"],
  weaknesses: ["边界场景覆盖不足"],
  suggestedImprovements: ["补充故障恢复案例"],
  actionPlan: ["下次回答先给出结论", "再说明验证方式"],
  recommendedLevel: "中高级",
  items: [
    {
      id: "item-2",
      turnId: "turn-2",
      parentTurnId: "turn-1",
      sequence: 2,
      turnType: "FOLLOW_UP",
      question: "如果流量继续增长，你会怎么优化？",
      answer: "我会先确认瓶颈，再选择缓存或异步化。",
      scores: { overall: 80, technical: 82, relevance: 80, clarity: 78, depth: 80 },
      strengths: ["有后续验证思路"],
      weaknesses: [],
      feedback: "追问回答覆盖了主要方向。",
      suggestedImprovements: [],
      sources: [{ sourceId: "S2", fileName: "resume.pdf", summary: "项目经历摘要" }],
      createdAt: "2026-08-28T10:01:00Z",
    },
    {
      id: "item-1",
      turnId: "turn-1",
      parentTurnId: null,
      sequence: 1,
      turnType: "PRIMARY",
      question: "请介绍一个你负责的高并发项目。",
      answer: "<script>window.__reportXss = true</script>我负责了服务拆分。",
      scores: { overall: 88, technical: 90, relevance: 86, clarity: 90, depth: 84 },
      strengths: ["结构完整"],
      weaknesses: ["可补充量化结果"],
      feedback: "回答有上下文，也说明了结果。",
      suggestedImprovements: ["补充指标"],
      sources: [{ sourceId: "S1", fileName: "resume.pdf", pageNumber: 2, summary: "<b>来源摘要</b>" }],
      createdAt: "2026-08-28T10:00:00Z",
    },
  ],
  aggregationVersion: "v1",
  generatedBy: "HYBRID",
  createdAt: "2026-08-28T10:02:00Z",
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

afterEach(() => {
  tokenStore.clear();
  resetApiClientForTests();
});

describe("InterviewReportDetailPage", () => {
  it("renders the report snapshot, radar, replay, sources, and safe text", async () => {
    tokenStore.setTokens("access", "refresh");
    setApiAdapterForTests(async (config) => response(config, report));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/interview/reports/report-1"]}>
          <Routes><Route path="/interview/reports/:reportId" element={<InterviewReportDetailPage />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("后端工程师")).toBeInTheDocument();
    expect(screen.getByText("84")).toBeInTheDocument();
    expect(screen.getAllByText("确定性评分 + AI 建议").length).toBe(2);
    expect(await screen.findByRole("table", { name: "面试能力维度分数" })).toBeInTheDocument();
    expect(screen.getByText("PRIMARY · 基础题")).toBeInTheDocument();
    expect(screen.getByText("FOLLOW_UP · 动态追问")).toBeInTheDocument();
    expect(screen.getByText("追问承接第 1 轮回答")).toBeInTheDocument();
    expect(screen.getByText("resume.pdf · 第 2 页")).toBeInTheDocument();
    expect(screen.getByText("resume.pdf")).toBeInTheDocument();
    expect(screen.getByText("<script>window.__reportXss = true</script>我负责了服务拆分。")).toBeInTheDocument();
    expect(document.querySelector("script")).not.toBeInTheDocument();
  });
});
