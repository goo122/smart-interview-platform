import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { StrictMode, type PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { InterviewReportResponse } from "@/api/generated";
import { AppError, ErrorCode } from "@/lib/errors";

const mocks = vi.hoisted(() => ({
  getReport: vi.fn(),
  generateReport: vi.fn(),
}));

vi.mock("@/services/interviewService", () => ({
  interviewService: {
    getInterviewReportBySessionId: (...args: unknown[]) =>
      mocks.getReport(...args),
    generateInterviewReport: (...args: unknown[]) =>
      mocks.generateReport(...args),
  },
}));

import { useInterviewReportData } from "@/hooks/interview/report/useInterviewReportData";

const makeReport = (
  status: string,
  failureMessage: string | null = null,
): InterviewReportResponse => ({
  reportId: "report-1",
  sessionId: "session-1",
  status,
  jobTitle: "后端工程师",
  interviewType: "TECHNICAL",
  difficulty: "MEDIUM",
  overallScore: status === "READY" ? 80 : 0,
  dimensionScores: {},
  radarData: [],
  summary: status === "READY" ? "报告摘要" : "",
  strengths: [],
  weaknesses: [],
  suggestedImprovements: [],
  actionPlan: [],
  recommendedLevel: null,
  items: [],
  aggregationVersion: status === "READY" ? "v1" : "pending",
  generatedBy: "RULES",
  createdAt: "2026-08-31T00:00:00Z",
  updatedAt: "2026-08-31T00:00:00Z",
  completedAt: status === "READY" ? "2026-08-31T00:01:00Z" : null,
  failureCode: null,
  failureMessage,
  resumeScore: null,
  resumeEvaluation: null,
});

const createWrapper = () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const wrapper = ({ children }: PropsWithChildren) => (
    <StrictMode>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </StrictMode>
  );
  return { client, wrapper };
};

describe("useInterviewReportData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a missing report only once under StrictMode", async () => {
    mocks.getReport.mockRejectedValueOnce(
      new AppError(ErrorCode.RESOURCE_NOT_FOUND, "not found"),
    );
    mocks.generateReport.mockResolvedValue(makeReport("READY"));
    const { client, wrapper } = createWrapper();

    const { result } = renderHook(() => useInterviewReportData("session-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isReportReady).toBe(true));

    expect(mocks.getReport).toHaveBeenCalledTimes(1);
    expect(mocks.generateReport).toHaveBeenCalledTimes(1);
    client.clear();
  });

  it("polls a pending report until it becomes ready", async () => {
    mocks.getReport
      .mockResolvedValueOnce(makeReport("PENDING"))
      .mockResolvedValueOnce(makeReport("GENERATING"))
      .mockResolvedValueOnce(makeReport("READY"));
    const { client, wrapper } = createWrapper();
    const { result } = renderHook(() => useInterviewReportData("session-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.reportStatus).toBe("PENDING"));
    expect(result.current.isReportReady).toBe(false);
    expect(result.current.isRecordLoading).toBe(true);

    await waitFor(() => expect(result.current.isReportReady).toBe(true), {
      timeout: 4_000,
    });
    expect(mocks.getReport).toHaveBeenCalledTimes(3);
    expect(mocks.generateReport).not.toHaveBeenCalled();
    client.clear();
  });

  it("stops polling after unmount", async () => {
    mocks.getReport.mockResolvedValue(makeReport("PENDING"));
    const { client, wrapper } = createWrapper();
    const { result, unmount } = renderHook(
      () => useInterviewReportData("session-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.reportStatus).toBe("PENDING"));
    const callsBeforeUnmount = mocks.getReport.mock.calls.length;
    unmount();

    await new Promise((resolve) => setTimeout(resolve, 1_700));
    expect(mocks.getReport).toHaveBeenCalledTimes(callsBeforeUnmount);
    client.clear();
  });

  it("shows a failed report as an error with a retryable state", async () => {
    mocks.getReport.mockResolvedValue(
      makeReport("FAILED", "报告生成暂时失败，请重试。"),
    );
    const { client, wrapper } = createWrapper();
    const { result } = renderHook(() => useInterviewReportData("session-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.recordError).toBeTruthy());

    expect(result.current.isReportReady).toBe(false);
    expect(result.current.isReportGenerating).toBe(false);
    expect(result.current.recordError).toBe("报告生成暂时失败，请重试。");
    client.clear();
  });
});
