import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildInterviewReportViewModel,
  fetchInterviewReportQueryData,
} from "@/hooks/interview/report/interviewReportData.shared";
import { interviewService } from "@/services/interviewService";

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
  it("uses only record query on success", async () => {
    const record = {
      id: 100,
      userId: 1,
      sessionId: "session-100",
    };

    const getRecordSpy = vi
      .spyOn(interviewService, "getInterviewRecordBySessionId")
      .mockResolvedValue(record);
    const saveSpy = vi
      .spyOn(interviewService, "saveInterviewRecord")
      .mockResolvedValue(undefined);
    const saveRedisSpy = vi
      .spyOn(interviewService, "saveInterviewRecordFromRedis")
      .mockResolvedValue(undefined);
    const radarSpy = vi.spyOn(interviewService, "getInterviewRadarChart");

    const result = await fetchInterviewReportQueryData("session-100");

    expect(result).toEqual({ record });
    expect(getRecordSpy).toHaveBeenCalledTimes(1);
    expect(saveSpy).not.toHaveBeenCalled();
    expect(saveRedisSpy).not.toHaveBeenCalled();
    expect(radarSpy).not.toHaveBeenCalled();
  });

  it("runs save fallback chain when record query fails", async () => {
    const record = {
      id: 101,
      userId: 1,
      sessionId: "session-101",
    };

    const getRecordSpy = vi
      .spyOn(interviewService, "getInterviewRecordBySessionId")
      .mockRejectedValueOnce(new Error("not ready"))
      .mockResolvedValueOnce(record);
    const saveSpy = vi
      .spyOn(interviewService, "saveInterviewRecord")
      .mockRejectedValueOnce(new Error("save failed"));
    const saveRedisSpy = vi
      .spyOn(interviewService, "saveInterviewRecordFromRedis")
      .mockResolvedValue(undefined);
    const radarSpy = vi.spyOn(interviewService, "getInterviewRadarChart");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const result = await fetchInterviewReportQueryData("session-101");

    expect(result).toEqual({ record });
    expect(getRecordSpy).toHaveBeenCalledTimes(2);
    expect(saveSpy).toHaveBeenCalledTimes(1);
    expect(saveRedisSpy).toHaveBeenCalledTimes(1);
    expect(radarSpy).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });
});
