import { describe, expect, it, vi } from "vitest";
import service from "@/lib/request";
import { AppError, ErrorCode } from "@/lib/errors";
import {
  buildResumeKnowledgeBaseName,
  type AnswerInterviewQuestionResult,
  interviewService,
  normalizeInterviewAnswer,
} from "@/services/interviewService";

describe("buildResumeKnowledgeBaseName", () => {
  it("uses the stable request id to avoid knowledge-base name conflicts", () => {
    const first = buildResumeKnowledgeBaseName(
      "AI应用开发工程师简历.pdf",
      "request-1234567890",
    );
    const repeated = buildResumeKnowledgeBaseName(
      "AI应用开发工程师简历.pdf",
      "request-1234567890",
    );
    const next = buildResumeKnowledgeBaseName(
      "AI应用开发工程师简历.pdf",
      "request-abcdefghij",
    );

    expect(first).toBe(repeated);
    expect(first).not.toBe(next);
  });
});

describe("normalizeInterviewAnswer", () => {
  it("keeps isFollowUp and followUpNeeded independent", () => {
    const payload = {
      is_follow_up: false,
      follow_up_needed: true,
      next_question: "请说明缓存一致性方案",
      next_question_number: "1-F1",
      follow_up_count: "1",
      finished: false,
      isSuccess: true,
    } as unknown as AnswerInterviewQuestionResult;
    const normalized = normalizeInterviewAnswer(payload);

    expect(normalized.isFollowUp).toBe(false);
    expect(normalized.followUpNeeded).toBe(true);
    expect(normalized.nextQuestionNumber).toBe("1-F1");
    expect(normalized.followUpCount).toBe(1);
  });

  it("normalizes follow-up flags and score fields from mixed naming", () => {
    const payload = {
      isFollowUp: true,
      followUpNeeded: false,
      total_score: "88",
      score_comment: "回答结构清晰",
      next_question: "继续展开事务隔离级别的选择依据",
      next_question_number: "2-F2",
      follow_up_count: 2,
      finished: "false",
    } as unknown as AnswerInterviewQuestionResult;
    const normalized = normalizeInterviewAnswer(payload);

    expect(normalized.isFollowUp).toBe(true);
    expect(normalized.followUpNeeded).toBe(false);
    expect(normalized.totalScore).toBe(88);
    expect(normalized.feedback).toBe("回答结构清晰");
    expect(normalized.nextQuestionNumber).toBe("2-F2");
    expect(normalized.followUpCount).toBe(2);
    expect(normalized.finished).toBe(false);
  });
});

describe("interviewService.createInterviewSession", () => {
  it("uses the long timeout while the backend generates questions", async () => {
    const payload = {
      knowledgeBaseId: "knowledge-base-1",
      jobTitle: "Java 高级开发工程师",
      jobDescription: "负责后端系统设计与开发",
      interviewType: "TECHNICAL" as const,
      difficulty: "MEDIUM" as const,
      questionCount: 5,
      requestId: "request-1",
    };
    const postSpy = vi.spyOn(service, "post").mockResolvedValue({
      sessionId: "session-1",
      status: "READY",
    });

    try {
      await interviewService.createInterviewSession(payload);

      expect(postSpy).toHaveBeenCalledWith(
        "/xunzhi/v1/interview/sessions",
        payload,
        { timeout: 180_000 },
      );
    } finally {
      postSpy.mockRestore();
    }
  });
});

describe("interviewService.answerInterviewQuestion", () => {
  it("rejects empty questionNumber before request", async () => {
    const error = await interviewService
      .answerInterviewQuestion({
        sessionId: "session-1",
        questionNumber: "   ",
        answerContent: "answer",
      })
      .catch((caught) => caught);

    expect(error).toBeInstanceOf(AppError);
    expect((error as AppError).code).toBe(ErrorCode.CLIENT_VALIDATION_ERROR);
  });
});
