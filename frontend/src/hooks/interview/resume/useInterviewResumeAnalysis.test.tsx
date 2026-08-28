import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useInterviewResumeAnalysis } from "@/hooks/interview/resume/useInterviewResumeAnalysis";

const createInterviewSessionMock = vi.fn();
const restoreInterviewSessionMock = vi.fn();
const fetchInterviewResumePreviewBlobMock = vi.fn();
const extractInterviewQuestionsMock = vi.fn();

vi.mock("@/services/interviewService", () => ({
  interviewService: {
    createInterviewSession: (...args: unknown[]) =>
      createInterviewSessionMock(...args),
    restoreInterviewSession: (...args: unknown[]) =>
      restoreInterviewSessionMock(...args),
    fetchInterviewResumePreviewBlob: (...args: unknown[]) =>
      fetchInterviewResumePreviewBlobMock(...args),
    extractInterviewQuestions: (...args: unknown[]) =>
      extractInterviewQuestionsMock(...args),
  },
}));

describe("useInterviewResumeAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    restoreInterviewSessionMock.mockResolvedValue({
      resumeFileUrl: "https://example.com/files/resume.pdf",
      resumeScore: 92,
      interviewType: "frontend",
      suggestions: {
        one: "绐佸嚭绯荤粺璁捐缁忛獙",
      },
    });
    fetchInterviewResumePreviewBlobMock.mockResolvedValue(
      new Blob(["resume"], {
        type: "application/pdf",
      }),
    );
    createInterviewSessionMock.mockResolvedValue({
      sessionId: "created-session",
      status: "DRAFT",
    });
    extractInterviewQuestionsMock.mockResolvedValue({
      isSuccess: 1,
      resumeScore: 88,
      interviewType: "frontend",
      suggestions: {
        one: "Explain architecture tradeoffs",
      },
    });
    vi.stubGlobal(
      "URL",
      Object.assign(URL, {
        createObjectURL: vi
          .fn()
          .mockReturnValueOnce("blob:resume-1")
          .mockReturnValueOnce("blob:resume-2")
          .mockReturnValueOnce("blob:resume-3"),
        revokeObjectURL: vi.fn(),
      }),
    );
  });

  it("restores remote resume preview metadata for an existing session", async () => {
    const { result } = renderHook(() =>
      useInterviewResumeAnalysis({
        interviewerSessionId: "session-1",
        setInterviewerSessionId: vi.fn(),
        syncNextQuestion: vi.fn(async () => undefined),
        resetInterviewFlow: vi.fn(),
        clearInterviewError: vi.fn(),
      }),
    );

    await waitFor(() => {
      expect(result.current.resumeName).toBe("resume.pdf");
    });

    expect(result.current.resumeScore).toBe(92);
    expect(result.current.resumePreviewSource).toBeInstanceOf(File);
    expect(fetchInterviewResumePreviewBlobMock).toHaveBeenCalledWith(
      "session-1",
    );
  });

  it("revokes preview object URLs when the session changes and on unmount", async () => {
    const { result, rerender, unmount } = renderHook(
      ({ interviewerSessionId }) =>
        useInterviewResumeAnalysis({
          interviewerSessionId,
          setInterviewerSessionId: vi.fn(),
          syncNextQuestion: vi.fn(async () => undefined),
          resetInterviewFlow: vi.fn(),
          clearInterviewError: vi.fn(),
        }),
      {
        initialProps: {
          interviewerSessionId: "session-1" as string | null,
        },
      },
    );

    await waitFor(() => {
      expect(result.current.resumeOpenPreviewUrl).toBe("blob:resume-1");
    });

    rerender({
      interviewerSessionId: "session-2",
    });

    await waitFor(() => {
      expect(result.current.resumeOpenPreviewUrl).toBe("blob:resume-2");
    });

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:resume-1");

    unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:resume-2");
  });

  it("rejects non-pdf files before creating a session", async () => {
    const { result } = renderHook(() =>
      useInterviewResumeAnalysis({
        interviewerSessionId: null,
        setInterviewerSessionId: vi.fn(),
        syncNextQuestion: vi.fn(async () => undefined),
        resetInterviewFlow: vi.fn(),
        clearInterviewError: vi.fn(),
      }),
    );

    await act(async () => {
      await result.current.handleResumeFileSelect({
        target: {
          files: [
            new File(["hello"], "resume.txt", {
              type: "text/plain",
            }),
          ],
          value: "resume.txt",
        },
      } as never);
    });

    expect(result.current.resumeUploadError).toBe("Only PDF files are supported");
    expect(createInterviewSessionMock).not.toHaveBeenCalled();
  });

  it("uploads, analyzes, restores preview, and syncs the first question on success", async () => {
    const setInterviewerSessionIdMock = vi.fn();
    const syncNextQuestionMock = vi.fn(async () => undefined);
    const resetInterviewFlowMock = vi.fn();
    const clearInterviewErrorMock = vi.fn();

    const { result } = renderHook(() =>
      useInterviewResumeAnalysis({
        interviewerSessionId: null,
        setInterviewerSessionId: setInterviewerSessionIdMock,
        syncNextQuestion: syncNextQuestionMock,
        resetInterviewFlow: resetInterviewFlowMock,
        clearInterviewError: clearInterviewErrorMock,
      }),
    );

    const pdfFile = new File(["resume"], "candidate-resume.pdf", {
      type: "application/pdf",
    });

    await act(async () => {
      await result.current.handleResumeFileSelect({
        target: {
          files: [pdfFile],
          value: "candidate-resume.pdf",
        },
      } as never);
    });

    await waitFor(() => {
      expect(setInterviewerSessionIdMock).toHaveBeenCalledWith(
        "created-session",
      );
      expect(syncNextQuestionMock).toHaveBeenCalledWith("created-session");
    });

    expect(resetInterviewFlowMock).toHaveBeenCalledTimes(1);
    expect(clearInterviewErrorMock).toHaveBeenCalledTimes(1);
    expect(createInterviewSessionMock).toHaveBeenCalledTimes(1);
    expect(extractInterviewQuestionsMock).toHaveBeenCalledWith({
      sessionId: "created-session",
      resumePdf: pdfFile,
    });
    expect(result.current.resumeScore).toBe(88);
    expect(result.current.resumeName).toBe("candidate-resume.pdf");
    expect(result.current.resumePreviewSource).toBeInstanceOf(File);
    expect(result.current.isResumeUploading).toBe(false);
  });
});
