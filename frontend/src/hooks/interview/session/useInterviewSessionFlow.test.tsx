import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ROUTES } from "@/lib/constants";
import { AUTO_SAVE_SUCCESS_TEXT } from "@/hooks/interview/session/interviewSessionFlow.shared";
import { useInterviewSessionFlow } from "@/hooks/interview/session/useInterviewSessionFlow";

const navigateMock = vi.fn();
const useParamsMock = vi.fn();
const invalidateQueriesMock = vi.fn();

const storageState = {
  interviewerSessionId: null as string | null,
  setInterviewerSessionId: vi.fn(),
  clearStoredSession: vi.fn(),
};

const getCurrentQuestionMock = vi.fn();
const answerInterviewQuestionMock = vi.fn();
const finishInterviewSessionMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useParams: () => useParamsMock(),
  };
});

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesMock,
  }),
}));

vi.mock("@/hooks/interview/session/useInterviewSessionStorage", () => ({
  useInterviewSessionStorage: () => storageState,
}));

vi.mock("@/services/interviewService", () => ({
  interviewService: {
    getCurrentQuestion: (...args: unknown[]) => getCurrentQuestionMock(...args),
    answerInterviewQuestion: (...args: unknown[]) =>
      answerInterviewQuestionMock(...args),
    finishInterviewSession: (...args: unknown[]) =>
      finishInterviewSessionMock(...args),
  },
}));

const renderSessionFlow = () =>
  renderHook(() =>
    useInterviewSessionFlow({
      id: 1,
      username: "tester",
    }),
  );

describe("useInterviewSessionFlow", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();

    storageState.interviewerSessionId = null;
    storageState.setInterviewerSessionId = vi.fn((nextValue: string | null) => {
      storageState.interviewerSessionId = nextValue;
    });
    storageState.clearStoredSession = vi.fn(() => {
      storageState.interviewerSessionId = null;
    });

    useParamsMock.mockReturnValue({});
    invalidateQueriesMock.mockResolvedValue(undefined);
    getCurrentQuestionMock.mockResolvedValue({
      isSuccess: true,
      nextQuestion: "Initial question",
      nextQuestionNumber: "Q1",
      isFollowUp: false,
      followUpCount: 0,
      finished: false,
    });
    answerInterviewQuestionMock.mockResolvedValue({
      isSuccess: true,
      feedback: "Feedback content",
      nextQuestion: "Next question",
      nextQuestionNumber: "Q2",
      isFollowUp: false,
      followUpCount: 0,
      finished: false,
    });
    finishInterviewSessionMock.mockResolvedValue(undefined);
  });

  it("syncs the route session into storage and loads the current question", async () => {
    useParamsMock.mockReturnValue({
      sessionId: "route-session",
    });

    renderSessionFlow();

    await waitFor(() => {
      expect(storageState.setInterviewerSessionId).toHaveBeenCalledWith(
        "route-session",
      );
      expect(getCurrentQuestionMock).toHaveBeenCalledWith("route-session");
    });
  });

  it("does not restore a stored session automatically when the route is empty", async () => {
    storageState.interviewerSessionId = "stored-session";

    const { result } = renderSessionFlow();

    await waitFor(() => {
      expect(result.current.interviewerSessionId).toBeNull();
    });

    expect(navigateMock).not.toHaveBeenCalled();
    expect(getCurrentQuestionMock).not.toHaveBeenCalled();
  });

  it("does not append a next-question message when syncNextQuestion finishes the interview", async () => {
    getCurrentQuestionMock.mockResolvedValue({
      isSuccess: true,
      nextQuestion: "Should not be appended",
      nextQuestionNumber: "Q9",
      finished: true,
      totalScore: 91,
    });

    const { result } = renderSessionFlow();

    await act(async () => {
      await result.current.syncNextQuestion("session-1");
    });

    expect(result.current.isInterviewFinished).toBe(true);
    expect(result.current.totalInterviewScore).toBe(91);
    expect(result.current.messages).toHaveLength(1);
  });

  it("outputs user message, feedback, and next question in order after a successful answer", async () => {
    useParamsMock.mockReturnValue({
      sessionId: "session-1",
    });

    const { result } = renderSessionFlow();

    await waitFor(() => {
      expect(
        result.current.messages.some(
          (message) => message.content === "Initial question",
        ),
      ).toBe(true);
    });

    await act(async () => {
      result.current.setInput("My answer");
    });

    await act(async () => {
      await result.current.handleSend();
    });

    const contents = result.current.messages.map((message) => message.content);
    const userIndex = contents.indexOf("My answer");
    const feedbackIndex = contents.indexOf("Feedback content");
    const nextQuestionIndex = contents.indexOf("Next question");

    expect(userIndex).toBeGreaterThan(-1);
    expect(feedbackIndex).toBeGreaterThan(userIndex);
    expect(nextQuestionIndex).toBeGreaterThan(feedbackIndex);
    expect(result.current.interviewError).toBeNull();
  });

  it("shows follow-up message marker when backend returns a follow-up question", async () => {
    useParamsMock.mockReturnValue({
      sessionId: "session-1",
    });
    answerInterviewQuestionMock.mockResolvedValue({
      isSuccess: true,
      feedback: "请补充细节",
      nextQuestion: "你刚提到缓存一致性，具体如何保证？",
      nextQuestionNumber: "1-F1",
      isFollowUp: true,
      followUpCount: 1,
      finished: false,
    });

    const { result } = renderSessionFlow();

    await waitFor(() => {
      expect(
        result.current.messages.some(
          (message) => message.content === "Initial question",
        ),
      ).toBe(true);
    });

    await act(async () => {
      result.current.setInput("我会先讲设计目标");
    });

    await act(async () => {
      await result.current.handleSend();
    });

    expect(
      result.current.messages.some(
        (message) =>
          message.content.includes("【追问第 1 轮】") &&
          message.content.includes("具体如何保证"),
      ),
    ).toBe(true);
    expect(result.current.isCurrentQuestionFollowUp).toBe(true);
    expect(result.current.currentFollowUpCount).toBe(1);
  });

  it("blocks submission when current question number is missing", async () => {
    useParamsMock.mockReturnValue({
      sessionId: "session-1",
    });
    getCurrentQuestionMock.mockResolvedValue({
      isSuccess: true,
      nextQuestion: "Question without number",
      nextQuestionNumber: null,
      finished: false,
    });

    const { result } = renderSessionFlow();

    await waitFor(() => {
      expect(
        result.current.messages.some(
          (message) => message.content === "Question without number",
        ),
      ).toBe(true);
    });

    await act(async () => {
      result.current.setInput("answer without question number");
    });

    await act(async () => {
      await result.current.handleSend();
    });

    expect(answerInterviewQuestionMock).not.toHaveBeenCalled();
    expect(result.current.interviewError).toBe(
      "当前题号缺失，请先等待题目加载完成后再提交。",
    );
    expect(
      result.current.messages.some(
        (message) =>
          message.content === "当前题号缺失，请先等待题目加载完成后再提交。",
      ),
    ).toBe(true);
  });

  it("stops the thinking indicator and appends an error message when answer submission fails", async () => {
    useParamsMock.mockReturnValue({
      sessionId: "session-1",
    });
    answerInterviewQuestionMock.mockResolvedValue({
      isSuccess: false,
      errorMessage: "Submit failed",
    });

    const { result } = renderSessionFlow();

    await waitFor(() => {
      expect(
        result.current.messages.some(
          (message) => message.content === "Initial question",
        ),
      ).toBe(true);
    });

    await act(async () => {
      result.current.setInput("Bad answer");
    });

    await act(async () => {
      await result.current.handleSend();
    });

    expect(result.current.interviewError).toBe("Submit failed");
    expect(
      result.current.messages.some(
        (message) =>
          message.variant === "progress" || message.status === "streaming",
      ),
    ).toBe(false);

    const lastMessage = result.current.messages.at(-1);
    expect(lastMessage?.content).toBe("Submit failed");
    expect(lastMessage?.status).toBe("error");
  });

  it("auto-finishes only once after the interview is finished", async () => {
    useParamsMock.mockReturnValue({
      sessionId: "session-1",
    });
    answerInterviewQuestionMock.mockResolvedValue({
      isSuccess: true,
      feedback: "Final feedback",
      finished: true,
      totalScore: 95,
    });

    const { result, rerender } = renderSessionFlow();

    await waitFor(() => {
      expect(
        result.current.messages.some(
          (message) => message.content === "Initial question",
        ),
      ).toBe(true);
    });

    await act(async () => {
      result.current.setInput("Final answer");
    });

    await act(async () => {
      await result.current.handleSend();
    });

    await waitFor(() => {
      expect(finishInterviewSessionMock).toHaveBeenCalledTimes(1);
      expect(
        result.current.messages.some(
          (message) => message.content === AUTO_SAVE_SUCCESS_TEXT,
        ),
      ).toBe(true);
    });

    rerender();

    await waitFor(() => {
      expect(finishInterviewSessionMock).toHaveBeenCalledTimes(1);
    });

    expect(invalidateQueriesMock).toHaveBeenCalled();
  });

  it("clears the stored session and navigates to the report page with sessionId on end", async () => {
    useParamsMock.mockReturnValue({
      sessionId: "session-1",
    });

    const { result } = renderSessionFlow();

    await waitFor(() => {
      expect(
        result.current.messages.some(
          (message) => message.content === "Initial question",
        ),
      ).toBe(true);
    });

    await act(async () => {
      await result.current.handleEndInterview();
    });

    expect(finishInterviewSessionMock).toHaveBeenCalledWith("session-1");
    expect(storageState.setInterviewerSessionId).toHaveBeenCalledWith(null);
    expect(storageState.clearStoredSession).toHaveBeenCalledTimes(1);
    expect(navigateMock).toHaveBeenCalledWith(
      `${ROUTES.interviewReport}?sessionId=session-1`,
      {
        state: {
          sessionId: "session-1",
        },
      },
    );
  });
});
