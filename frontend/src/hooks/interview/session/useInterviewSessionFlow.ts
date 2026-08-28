import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ROUTES } from "@/lib/constants";
import { buildReportSearch } from "@/lib/interviewReportRoute";
import { CHAT_MESSAGE_VARIANT } from "@/lib/chat";
import {
  buildInterviewProgressPatch,
  FEEDBACK_STREAM_DELAY_MS,
  FEEDBACK_STREAM_STEP,
  INTERVIEW_MESSAGE_GAP_MS,
  isInterviewResponseFailed,
  type InterviewFlowUser,
} from "@/hooks/interview/session/interviewSessionFlow.shared";
import { useInterviewAutoSave } from "@/hooks/interview/session/useInterviewAutoSave";
import { useInterviewMessageStream } from "@/hooks/interview/session/useInterviewMessageStream";
import { useInterviewProgressState } from "@/hooks/interview/session/useInterviewProgressState";
import { useInterviewRouteRecovery } from "@/hooks/interview/session/useInterviewRouteRecovery";
import { useInterviewSessionStorage } from "@/hooks/interview/session/useInterviewSessionStorage";
import { generateRequestId } from "@/hooks/interview/shared/interviewUtils";
import { interviewService } from "@/services/interviewService";

export function useInterviewSessionFlow(user: InterviewFlowUser) {
  const navigate = useNavigate();
  const params = useParams<{ sessionId?: string }>();
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [isInterviewSubmitting, setIsInterviewSubmitting] = useState(false);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [isEndingInterview, setIsEndingInterview] = useState(false);

  const {
    interviewerSessionId: storedInterviewerSessionId,
    setInterviewerSessionId: persistInterviewerSessionId,
    clearStoredSession,
  } = useInterviewSessionStorage(user);
  const routeSessionId = params.sessionId?.trim() || null;
  const interviewerSessionId = routeSessionId;

  const {
    currentQuestionNumber,
    currentQuestionContent,
    isCurrentQuestionFollowUp,
    currentFollowUpCount,
    isInterviewFinished,
    totalInterviewScore,
    applyProgressPatch,
    resetProgressState,
  } = useInterviewProgressState();

  const {
    messages,
    appendAssistantMessage,
    appendNextQuestionMessage,
    appendSystemMessage,
    appendUserMessage,
    appendErrorMessage,
    startThinkingIndicator,
    stopThinkingIndicator,
    cancelActiveQuestionStream,
    resetMessageStream,
  } = useInterviewMessageStream();

  const isReady = Boolean(interviewerSessionId) && !isInterviewFinished;

  const buildInterviewRoomPath = useCallback(
    (sessionId: string) =>
      `${ROUTES.interviewRoom}/${encodeURIComponent(sessionId)}`,
    [],
  );

  const invalidateInterviewRecords = useCallback(
    () =>
      queryClient.invalidateQueries({
        queryKey: ["interview-records"],
      }),
    [queryClient],
  );

  const setInterviewerSessionId = useCallback(
    (nextValue: string | null) => {
      persistInterviewerSessionId(nextValue);
      if (nextValue) {
        navigate(buildInterviewRoomPath(nextValue), { replace: true });
        return;
      }
      navigate(ROUTES.interviewRoom, { replace: true });
    },
    [buildInterviewRoomPath, navigate, persistInterviewerSessionId],
  );

  const clearInterviewError = useCallback(() => {
    setInterviewError(null);
  }, []);

  const syncNextQuestion = useCallback(
    async (sessionId: string, options?: { appendMessage?: boolean }) => {
      const response = await interviewService.getCurrentQuestion(sessionId);
      if (isInterviewResponseFailed(response.isSuccess)) {
        throw new Error(
          response.errorMessage || "Failed to load current interview question",
        );
      }

      const progressPatch = buildInterviewProgressPatch(response);
      applyProgressPatch(progressPatch);

      if (
        progressPatch.isInterviewFinished ||
        !progressPatch.currentQuestionContent
      ) {
        return;
      }

      await appendNextQuestionMessage(
        progressPatch.currentQuestionContent,
        progressPatch.currentQuestionNumber,
        progressPatch.isCurrentQuestionFollowUp,
        progressPatch.currentFollowUpCount,
        options,
      );
    },
    [appendNextQuestionMessage, applyProgressPatch],
  );

  useInterviewRouteRecovery({
    routeSessionId,
    storedInterviewerSessionId,
    interviewerSessionId,
    persistInterviewerSessionId,
    messages,
    syncNextQuestion,
    setInterviewError,
  });

  const { resetAutoSaveAttempt } = useInterviewAutoSave({
    interviewerSessionId,
    isInterviewFinished,
    appendSystemMessage,
    invalidateInterviewRecords,
  });

  const resetInterviewFlow = useCallback(() => {
    setInterviewerSessionId(null);
    resetProgressState();
    resetMessageStream();
    resetAutoSaveAttempt();
    setInterviewError(null);
    setInput("");
  }, [
    resetAutoSaveAttempt,
    resetMessageStream,
    resetProgressState,
    setInterviewerSessionId,
  ]);

  const pauseBetweenMessages = useCallback(async () => {
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, INTERVIEW_MESSAGE_GAP_MS);
    });
  }, []);

  const handleSend = useCallback(async () => {
    if (!isReady || isInterviewSubmitting) {
      return;
    }

    const nextInput = input.trim();
    if (!nextInput) {
      return;
    }
    const activeQuestionNumber = currentQuestionNumber?.trim();
    if (!activeQuestionNumber) {
      const message = "当前题号缺失，请先等待题目加载完成后再提交。";
      setInterviewError(message);
      appendErrorMessage(message);
      return;
    }

    setInterviewError(null);
    appendUserMessage(nextInput);
    setInput("");
    setIsInterviewSubmitting(true);
    startThinkingIndicator();

    try {
      const activeSessionId = interviewerSessionId;
      if (!activeSessionId) {
        throw new Error("Please upload and analyze resume first");
      }

      const response = await interviewService.answerInterviewQuestion({
        sessionId: activeSessionId,
        questionNumber: activeQuestionNumber,
        answerContent: nextInput,
        requestId: generateRequestId(),
      });
      stopThinkingIndicator();

      if (isInterviewResponseFailed(response.isSuccess)) {
        throw new Error(
          response.errorMessage || "Failed to submit interview answer",
        );
      }

      const progressPatch = buildInterviewProgressPatch(response);
      const feedbackText = response.feedback?.trim();
      applyProgressPatch(progressPatch);

      if (feedbackText) {
        await appendAssistantMessage(feedbackText, {
          fakeStream: true,
          variant: CHAT_MESSAGE_VARIANT.feedback,
          streamStep: FEEDBACK_STREAM_STEP,
          streamDelayMs: FEEDBACK_STREAM_DELAY_MS,
        });
      }

      if (progressPatch.currentQuestionContent) {
        if (feedbackText) {
          await pauseBetweenMessages();
        }
        await appendNextQuestionMessage(
          progressPatch.currentQuestionContent,
          progressPatch.currentQuestionNumber,
          progressPatch.isCurrentQuestionFollowUp,
          progressPatch.currentFollowUpCount,
        );
      }

      if (progressPatch.isInterviewFinished) {
        appendSystemMessage("面试已结束，正在保存记录...");
      }
    } catch (error) {
      stopThinkingIndicator();
      const message =
        error instanceof Error
          ? error.message
          : "Failed to submit answer, please retry";
      setInterviewError(message);
      appendErrorMessage(message);
    } finally {
      setIsInterviewSubmitting(false);
    }
  }, [
    appendAssistantMessage,
    appendErrorMessage,
    appendNextQuestionMessage,
    appendSystemMessage,
    appendUserMessage,
    applyProgressPatch,
    currentQuestionNumber,
    input,
    interviewerSessionId,
    isInterviewSubmitting,
    isReady,
    pauseBetweenMessages,
    startThinkingIndicator,
    stopThinkingIndicator,
  ]);

  const handleEndInterview = useCallback(async () => {
    if (isEndingInterview) {
      return;
    }
    setIsEndingInterview(true);

    const reportSessionId = interviewerSessionId;
    try {
      if (reportSessionId) {
        await interviewService.finishInterviewSession(reportSessionId);
        await invalidateInterviewRecords();
      }
    } catch (error) {
      console.error("Save interview record failed:", error);
    } finally {
      stopThinkingIndicator();
      cancelActiveQuestionStream();
      persistInterviewerSessionId(null);
      clearStoredSession();
      resetProgressState();
      resetAutoSaveAttempt();
      navigate(
        `${ROUTES.interviewReport}${buildReportSearch(reportSessionId)}`,
        {
          state: reportSessionId ? { sessionId: reportSessionId } : undefined,
        },
      );
      setIsEndingInterview(false);
    }
  }, [
    cancelActiveQuestionStream,
    clearStoredSession,
    interviewerSessionId,
    invalidateInterviewRecords,
    isEndingInterview,
    navigate,
    persistInterviewerSessionId,
    resetAutoSaveAttempt,
    resetProgressState,
    stopThinkingIndicator,
  ]);

  return {
    messages,
    input,
    setInput,
    isReady,
    isInterviewSubmitting,
    interviewError,
    isEndingInterview,
    currentQuestionNumber,
    currentQuestionContent,
    isCurrentQuestionFollowUp,
    currentFollowUpCount,
    isInterviewFinished,
    totalInterviewScore,
    interviewerSessionId,
    setInterviewerSessionId,
    clearInterviewError,
    resetInterviewFlow,
    syncNextQuestion,
    handleSend,
    handleEndInterview,
  };
}
