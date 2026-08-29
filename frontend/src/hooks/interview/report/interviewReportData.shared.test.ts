import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildInterviewReportViewModel,
  fetchInterviewReportQueryData,
} from "@/hooks/interview/report/interviewReportData.shared";
import { interviewService } from "@/services/interviewService";
import { AppError, ErrorCode } from "@/lib/errors";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("buildInterviewReportViewModel", () => {
  it("computes estimated composite score from record fields", () => {
    const viewModel = buildInterviewReportViewModel({
      id: 1,
      userId: 1,
      sessionId: "session-1",
      resumeScore: 80,
      interviewScore: 90,
      radarChart: {
        radarMetrics: [
          { label: "Communication", value: 81 },
          { label: "Delivery", value: 89 },
        ],
      },
      interviewSuggestions: "Focus on ownership\nAdd metrics",
    });

    expect(viewModel.resumeScore).toBe(80);
    expect(viewModel.interviewScore).toBe(90);
    expect(viewModel.compositeScore).toBe(85);
    expect(viewModel.isCompositeEstimated).toBe(true);
    expect(viewModel.radarPoints).toEqual([
      { label: "Communication", value: 81 },
      { label: "Delivery", value: 89 },
    ]);
    expect(viewModel.sortedSuggestions).toEqual([
      "Focus on ownership",
      "Add metrics",
    ]);
    expect(viewModel.reviewFeedback).toEqual({
      overallComment: null,
      highlights: [],
      improvementTips: [],
      nextActions: ["Focus on ownership", "Add metrics"],
    });
  });

  it("falls back to record and snapshot data, and dedupes qa reviews", () => {
    const viewModel = buildInterviewReportViewModel({
      id: 2,
      userId: 1,
      sessionId: "session-2",
      totalScore: 93,
      interviewSuggestionsMap: {
        "2": "Second",
        "1": "First",
      },
      qaReviews: [
        {
          question: "Q1",
          answer: "A1",
          score: 88,
        },
      ],
      sessionSnapshotJson: JSON.stringify({
        radarScores: {
          Communication: 78,
          Delivery: 83,
        },
        qaReviews: [
          {
            question: "Q1",
            answer: "A1",
            score: 88,
          },
          {
            question: "Q2",
            answer: "A2",
            score: 91,
          },
        ],
        interviewDirection: "frontend",
      }),
    });

    expect(viewModel.compositeScore).toBe(93);
    expect(viewModel.isCompositeEstimated).toBe(false);
    expect(viewModel.sortedSuggestions).toEqual(["First", "Second"]);
    expect(viewModel.radarPoints).toEqual([
      { label: "Communication", value: 78 },
      { label: "Delivery", value: 83 },
    ]);
    expect(viewModel.qaReviews).toEqual([
      {
        question: "Q1",
        answer: "A1",
        score: 88,
      },
      {
        question: "Q2",
        answer: "A2",
        score: 91,
      },
    ]);
    expect(viewModel.interviewDirection).toBe("frontend");
    expect(viewModel.reviewFeedback).toEqual({
      overallComment: null,
      highlights: [],
      improvementTips: [],
      nextActions: ["First", "Second"],
    });
  });

  it("reads structured review feedback from the report payload", () => {
    const viewModel = buildInterviewReportViewModel({
      id: 3,
      userId: 1,
      sessionId: "session-3",
      reviewFeedback: {
        overallComment: "overall",
        highlights: ["highlight 1"],
        improvementTips: ["tip 1"],
        nextActions: ["next 1"],
      },
    });

    expect(viewModel.reviewFeedback).toEqual({
      overallComment: "overall",
      highlights: ["highlight 1"],
      improvementTips: ["tip 1"],
      nextActions: ["next 1"],
    });
  });

  it("parses follow-up metadata from playback items", () => {
    const viewModel = buildInterviewReportViewModel({
      id: 4,
      userId: 1,
      sessionId: "session-4",
      playbackItems: [
        {
          questionNumber: "1",
          question: "Q1",
          answer: "A1",
          score: 86,
          isFollowUp: false,
        },
        {
          questionNumber: "1-F1",
          question: "Q1 follow-up",
          answer: "A1 follow-up",
          score: 80,
          feedback: "need more details",
          isFollowUp: true,
          followUpCount: 1,
          followUpNeeded: true,
        },
      ],
    });

    expect(viewModel.qaReviews).toEqual([
      {
        questionNumber: "1",
        question: "Q1",
        answer: "A1",
        score: 86,
        isFollowUp: false,
      },
      {
        questionNumber: "1-F1",
        question: "Q1 follow-up",
        answer: "A1 follow-up",
        score: 80,
        feedback: "need more details",
        isFollowUp: true,
        followUpCount: 1,
        followUpNeeded: true,
      },
    ]);
  });

  it("prefers record.radarChart over top-level and snapshot radar data", () => {
    const viewModel = buildInterviewReportViewModel({
      id: 5,
      userId: 1,
      sessionId: "session-5",
      radarChart: {
        radarMetrics: [
          { label: "Chart A", value: 82 },
          { label: "Chart B", value: 76 },
        ],
      },
      radarPoints: [
        { label: "Top-level A", value: 20 },
        { label: "Top-level B", value: 25 },
      ],
      sessionSnapshotJson: JSON.stringify({
        radarScores: {
          "Snapshot A": 33,
          "Snapshot B": 44,
        },
      }),
    });

    expect(viewModel.radarPoints).toEqual([
      { label: "Chart A", value: 82 },
      { label: "Chart B", value: 76 },
    ]);
  });

  it("falls back to top-level record radar when radarChart is missing", () => {
    const viewModel = buildInterviewReportViewModel({
      id: 6,
      userId: 1,
      sessionId: "session-6",
      radarPoints: [
        { label: "Top-level A", value: 71 },
        { label: "Top-level B", value: 79 },
      ],
    });

    expect(viewModel.radarPoints).toEqual([
      { label: "Top-level A", value: 71 },
      { label: "Top-level B", value: 79 },
    ]);
  });

  it("falls back to snapshot radar when record radar is missing", () => {
    const viewModel = buildInterviewReportViewModel({
      id: 7,
      userId: 1,
      sessionId: "session-7",
      sessionSnapshotJson: JSON.stringify({
        radarScores: {
          "Snapshot A": 68,
          "Snapshot B": 74,
        },
      }),
    });

    expect(viewModel.radarPoints).toEqual([
      { label: "Snapshot A", value: 68 },
      { label: "Snapshot B", value: 74 },
    ]);
  });
});

describe("fetchInterviewReportQueryData", () => {
  const report = {
    reportId: "report-100",
    sessionId: "session-100",
    status: "READY",
    jobTitle: "Java 开发工程师",
    interviewType: "TECHNICAL",
    difficulty: "MEDIUM",
    overallScore: 86,
    dimensionScores: {
      technical: 88,
      relevance: 84,
      clarity: 82,
      depth: 85,
    },
    radarData: [
      { dimension: "technical", score: 88 },
      { dimension: "relevance", score: 84 },
    ],
    summary: "整体表现稳定。",
    strengths: ["基础扎实"],
    weaknesses: ["细节不足"],
    suggestedImprovements: ["补充实现细节"],
    actionPlan: ["复习并发编程"],
    recommendedLevel: "中级",
    items: [
      {
        id: "item-1",
        turnId: "turn-1",
        parentTurnId: null,
        sequence: 1,
        turnType: "PRIMARY",
        question: "请介绍线程池。",
        answer: "线程池用于复用线程。",
        scores: { overall: 86 },
        strengths: ["概念正确"],
        weaknesses: [],
        feedback: "可以补充拒绝策略。",
        suggestedImprovements: ["补充参数说明"],
        sources: [],
        createdAt: "2026-08-29T00:00:00Z",
      },
      {
        id: "item-2",
        turnId: "turn-2",
        parentTurnId: "turn-1",
        sequence: 2,
        turnType: "FOLLOW_UP",
        question: "有哪些拒绝策略？",
        answer: "有 AbortPolicy 等。",
        scores: { overall: 80 },
        strengths: [],
        weaknesses: [],
        feedback: "回答正确。",
        suggestedImprovements: [],
        sources: [],
        createdAt: "2026-08-29T00:01:00Z",
      },
    ],
    aggregationVersion: "v1",
    generatedBy: "HYBRID",
    createdAt: "2026-08-29T00:00:00Z",
    updatedAt: "2026-08-29T00:02:00Z",
    completedAt: "2026-08-29T00:02:00Z",
    failureCode: null,
    failureMessage: null,
  };

  it("uses the FastAPI report query on success", async () => {
    const getReportSpy = vi
      .spyOn(interviewService, "getInterviewReportBySessionId")
      .mockResolvedValue(report);
    const generateSpy = vi.spyOn(
      interviewService,
      "generateInterviewReport",
    );

    const result = await fetchInterviewReportQueryData("session-100");

    expect(result.record).toMatchObject({
      sessionId: "session-100",
      interviewScore: 86,
      compositeScore: 86,
      radarDimensions: [
        { label: "技术能力", value: 88 },
        { label: "回答相关性", value: 84 },
      ],
      reviewFeedback: {
        overallComment: "整体表现稳定。",
        highlights: ["基础扎实"],
        improvementTips: ["补充实现细节"],
        nextActions: ["复习并发编程"],
      },
    });
    expect(result.record?.qaReviews).toEqual([
      expect.objectContaining({
        questionNumber: "1",
        isFollowUp: false,
        score: 86,
      }),
      expect.objectContaining({
        questionNumber: "1-F1",
        isFollowUp: true,
        score: 80,
      }),
    ]);
    expect(getReportSpy).toHaveBeenCalledTimes(1);
    expect(generateSpy).not.toHaveBeenCalled();
  });

  it("generates the report when it does not exist yet", async () => {
    const getReportSpy = vi
      .spyOn(interviewService, "getInterviewReportBySessionId")
      .mockRejectedValueOnce(
        new AppError(ErrorCode.RESOURCE_NOT_FOUND, "not found"),
      );
    const generateSpy = vi
      .spyOn(interviewService, "generateInterviewReport")
      .mockResolvedValue({ ...report, sessionId: "session-101" });

    const result = await fetchInterviewReportQueryData("session-101");

    expect(result.record?.sessionId).toBe("session-101");
    expect(getReportSpy).toHaveBeenCalledTimes(1);
    expect(generateSpy).toHaveBeenCalledWith("session-101");
  });

  it("does not generate a report for authorization failures", async () => {
    vi.spyOn(interviewService, "getInterviewReportBySessionId").mockRejectedValueOnce(
      new AppError(ErrorCode.UNAUTHORIZED, "sign in again"),
    );
    const generateSpy = vi.spyOn(
      interviewService,
      "generateInterviewReport",
    );

    await expect(fetchInterviewReportQueryData("session-102")).rejects.toMatchObject({
      code: ErrorCode.UNAUTHORIZED,
    });
    expect(generateSpy).not.toHaveBeenCalled();
  });
});
