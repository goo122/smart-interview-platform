import { describe, expect, it, vi } from "vitest";
import service from "@/lib/request";
import { AppError, ErrorCode } from "@/lib/errors";
import { knowledgeApi } from "@/features/knowledge/api";
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

describe("interviewService.resolveInterviewRole", () => {
  it("requests the resume role inferred by the backend", async () => {
    const postSpy = vi.spyOn(service, "post").mockResolvedValue({
      jobTitle: "Python 后端开发工程师",
      jobDescription: "围绕 Python 后端开发工程师的岗位职责进行综合评估。",
      confidence: 92,
      inferred: true,
      inferenceVersion: "resume-role-v1",
    });

    try {
      const result = await interviewService.resolveInterviewRole("knowledge-1");
      expect(result.jobTitle).toBe("Python 后端开发工程师");
      expect(postSpy).toHaveBeenCalledWith(
        "/xunzhi/v1/interview/resolve-role",
        { knowledgeBaseId: "knowledge-1" },
        { timeout: 180_000 },
      );
    } finally {
      postSpy.mockRestore();
    }
  });
});

describe("interviewService.prepareInterviewSessionFromResume", () => {
  it("skips role inference when the caller supplies both job fields", async () => {
    const file = new File(["resume"], "candidate.pdf", {
      type: "application/pdf",
    });
    const stages: number[] = [];
    const createBaseSpy = vi.spyOn(knowledgeApi, "createBase").mockResolvedValue({
      id: "knowledge-1",
    } as never);
    const uploadDocumentSpy = vi
      .spyOn(knowledgeApi, "uploadDocument")
      .mockResolvedValue({ id: "document-1" } as never);
    const listDocumentsSpy = vi
      .spyOn(knowledgeApi, "listDocuments")
      .mockResolvedValue({
        records: [{ id: "document-1", status: "READY" }],
      } as never);
    const resolveRoleSpy = vi
      .spyOn(interviewService, "resolveInterviewRole")
      .mockResolvedValue({
        jobTitle: "不应使用的岗位",
        jobDescription: "不应使用的岗位描述",
        confidence: 0,
        inferred: true,
        inferenceVersion: "resume-role-v1",
      });
    const createSessionSpy = vi
      .spyOn(interviewService, "createInterviewSession")
      .mockResolvedValue({ sessionId: "session-1", status: "PREPARING" });
    const getSessionSpy = vi
      .spyOn(interviewService, "getInterviewSession")
      .mockResolvedValue({
        sessionId: "session-1",
        status: "READY",
        canStart: true,
      } as never);
    const startSessionSpy = vi
      .spyOn(interviewService, "startInterviewSession")
      .mockResolvedValue({ sessionId: "session-1", status: "IN_PROGRESS" } as never);

    try {
      const result = await interviewService.prepareInterviewSessionFromResume(file, {
        requestId: "request-1",
        jobTitle: "Java 后端工程师",
        jobDescription: "负责 Java 服务和系统设计",
        onPreparationStage: (stage) => stages.push(stage),
      });

      expect(result.sessionId).toBe("session-1");
      expect(resolveRoleSpy).not.toHaveBeenCalled();
      expect(createSessionSpy).toHaveBeenCalledWith({
        knowledgeBaseId: "knowledge-1",
        jobTitle: "Java 后端工程师",
        jobDescription: "负责 Java 服务和系统设计",
        interviewType: "TECHNICAL",
        difficulty: "MEDIUM",
        questionCount: 5,
        requestId: "request-1",
      });
      expect(stages).toEqual([0, 1, 2, 2]);
    } finally {
      createBaseSpy.mockRestore();
      uploadDocumentSpy.mockRestore();
      listDocumentsSpy.mockRestore();
      resolveRoleSpy.mockRestore();
      createSessionSpy.mockRestore();
      getSessionSpy.mockRestore();
      startSessionSpy.mockRestore();
    }
  });
});

describe("interviewService reports", () => {
  it("uses the FastAPI report read and generation endpoints", async () => {
    const report = { sessionId: "session-1", status: "READY" };
    const getSpy = vi.spyOn(service, "get").mockResolvedValue(report);
    const postSpy = vi.spyOn(service, "post").mockResolvedValue(report);

    try {
      await interviewService.getInterviewReportBySessionId("session-1");
      await interviewService.generateInterviewReport("session-1");

      expect(getSpy).toHaveBeenCalledWith(
        "/xunzhi/v1/interview/sessions/session-1/report",
        { timeout: 180_000 },
      );
      expect(postSpy).toHaveBeenCalledWith(
        "/xunzhi/v1/interview/sessions/session-1/report",
        {},
        { timeout: 180_000 },
      );
    } finally {
      getSpy.mockRestore();
      postSpy.mockRestore();
    }
  });

  it("loads history from the FastAPI report list", async () => {
    const getSpy = vi.spyOn(service, "get").mockResolvedValue({
      records: [
        {
          sessionId: "session-1",
          status: "READY",
          overallScore: 86,
          jobTitle: "Java 开发工程师",
          createdAt: "2026-08-29T00:00:00Z",
          updatedAt: "2026-08-29T00:01:00Z",
          completedAt: "2026-08-29T00:01:00Z",
        },
      ],
      total: 1,
      size: 20,
      current: 1,
      pages: 1,
    });

    try {
      const page = await interviewService.pageInterviewRecords({
        pageNum: 1,
        pageSize: 20,
      });

      expect(getSpy).toHaveBeenCalledWith("/xunzhi/v1/interview/reports", {
        params: { current: 1, size: 20 },
      });
      expect(page.records[0]).toMatchObject({
        sessionId: "session-1",
        interviewScore: 86,
        interviewDirection: "Java 开发工程师",
      });
    } finally {
      getSpy.mockRestore();
    }
  });
});

describe("interviewService.finishInterviewSession", () => {
  it("uses the dedicated finish endpoint with request deduplication", async () => {
    const postSpy = vi.spyOn(service, "post").mockResolvedValue({
      sessionId: "session-1",
      status: "COMPLETED",
    });

    try {
      await interviewService.finishInterviewSession("session-1");

      expect(postSpy).toHaveBeenCalledWith(
        "/xunzhi/v1/interview/sessions/session-1/finish",
        {},
        {
          timeout: 180_000,
          requestPolicy: {
            key: "interview-finish:session-1",
            dedupe: "join",
          },
        },
      );
    } finally {
      postSpy.mockRestore();
    }
  });
});

describe("interviewService.restoreInterviewSession", () => {
  it("forwards persisted resume evaluation metadata", async () => {
    const getSpy = vi.spyOn(service, "get").mockResolvedValue({
      sessionId: "session-resume",
      status: "READY",
      interviewType: "TECHNICAL",
      resumeScore: 86,
      resumeEvaluation: {
        status: "COMPLETED",
        overallScore: 86,
        suggestions: ["补充量化结果"],
        gaps: ["缺少指标"],
        summary: "匹配度良好",
      },
    });

    try {
      const restored = await interviewService.restoreInterviewSession(
        "session-resume",
      );
      expect(restored.resumeScore).toBe(86);
      expect(restored.suggestions).toEqual({ "1": "补充量化结果" });
      expect(restored.resumeEvaluation?.gaps).toEqual(["缺少指标"]);
    } finally {
      getSpy.mockRestore();
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
