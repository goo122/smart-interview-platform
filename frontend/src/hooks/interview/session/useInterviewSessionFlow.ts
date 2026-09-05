import { useCallback, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ROUTES } from "@/lib/constants";
import { buildReportSearch } from "@/lib/interviewReportRoute";
import { CHAT_MESSAGE_VARIANT } from "@/lib/chat";
import {
  buildInterviewProgressPatch,
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
  const endingInterviewRef = useRef(false);
  const submittingAnswerRef = useRef(false);
  const answerRequestRef = useRef<{ key: string; requestId: string } | null>(
    null,
  );

  const {
    interviewerSessionId: storedInterviewerSessionId,
    setInterviewerSessionId: persistInterviewerSessionId,
    clearStoredSession,
  } = useInterviewSessionStorage(user);
  const routeSessionId = params.sessionId?.trim() || null;
  const interviewerSessionId = routeSessionId;

  const {
    currentTurnId,
    currentQuestionNumber,
    currentQuestionContent,
    isCurrentQuestionFollowUp,
    currentFollowUpCount,
    isInterviewFinished,
    isInterviewFailed,
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
    async (
      sessionId: string,
      options?: { appendMessage?: boolean; signal?: AbortSignal },
    ) => {
      const response = options?.signal
        ? await interviewService.getCurrentQuestion(sessionId, options.signal)
        : await interviewService.getCurrentQuestion(sessionId);
      options?.signal?.throwIfAborted();
      const progressPatch = buildInterviewProgressPatch(response);
      const pendingAnswer = answerRequestRef.current;
      const questionKey = `${sessionId}:${progressPatch.currentTurnId || progressPatch.currentQuestionNumber}`;
      if (pendingAnswer && pendingAnswer.key !== questionKey) {
        setInput("");
        answerRequestRef.current = null;
      }
      applyProgressPatch(progressPatch);
      if (isInterviewResponseFailed(response.isSuccess)) {
        throw new Error(
          response.errorMessage || "Failed to load current interview question",
        );
      }

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

  const { isRecovering, retryRecovery } = useInterviewRouteRecovery({
    routeSessionId,
    storedInterviewerSessionId,
    interviewerSessionId,
    persistInterviewerSessionId,
    getInterviewSession: interviewService.getInterviewSession,
    waitForFirstQuestion: interviewService.waitForFirstQuestion,
    startInterviewSession: interviewService.startInterviewSession,
    syncNextQuestion,
    setInterviewError,
  });

  const isReady =
    Boolean(interviewerSessionId && (currentTurnId || currentQuestionNumber)) &&
    !isRecovering &&
    !interviewError &&
    !isInterviewFinished &&
    !isInterviewFailed &&
    !isEndingInterview;

  const { isAutoSaveFailed, resetAutoSaveAttempt } = useInterviewAutoSave({
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
    answerRequestRef.current = null;
  }, [
    resetAutoSaveAttempt,
    resetMessageStream,
    resetProgressState,
    setInterviewerSessionId,
  ]);

  const handleSend = useCallback(async () => {
    if (
      !isReady ||
      isInterviewSubmitting ||
      submittingAnswerRef.current ||
      endingInterviewRef.current
    ) {
      return;
    }

    const nextInput = input.trim();
    if (!nextInput) {
      return;
    }
    const activeQuestionNumber = currentQuestionNumber?.trim();
    const activeTurnId = currentTurnId?.trim();
    if (!activeQuestionNumber && !activeTurnId) {
      const message = "当前题号缺失，请先等待题目加载完成后再提交。";
      setInterviewError(message);
      appendErrorMessage(message);
      return;
    }

    setInterviewError(null);
    submittingAnswerRef.current = true;
    appendUserMessage(nextInput);
    setInput("");
    setIsInterviewSubmitting(true);
    startThinkingIndicator();

    try {
      const activeSessionId = interviewerSessionId;
      if (!activeSessionId) {
        throw new Error("Please upload and analyze resume first");
      }

      const answerKey = `${activeSessionId}:${activeTurnId || activeQuestionNumber}`;
      if (answerRequestRef.current?.key !== answerKey) {
        answerRequestRef.current = {
          key: answerKey,
          requestId: generateRequestId(),
        };
      }

      const response = await interviewService.answerInterviewQuestion({
        sessionId: activeSessionId,
        questionNumber: activeQuestionNumber,
        turnId: activeTurnId,
        answerContent: nextInput,
        requestId: answerRequestRef.current.requestId,
      });
      stopThinkingIndicator();

      const progressPatch = buildInterviewProgressPatch(response);
      applyProgressPatch(progressPatch);
      if (isInterviewResponseFailed(response.isSuccess)) {
        answerRequestRef.current = null;
        throw new Error(
          response.errorMessage || "Failed to submit interview answer",
        );
      }

      answerRequestRef.current = null;
      const feedbackText = response.feedback?.trim();

      if (feedbackText) {
        await appendAssistantMessage(feedbackText, {
          variant: CHAT_MESSAGE_VARIANT.feedback,
        });
      }

      if (progressPatch.currentQuestionContent) {
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
      setInput(nextInput);
      appendErrorMessage(message);
    } finally {
      submittingAnswerRef.current = false;
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
    currentTurnId,
    input,
    interviewerSessionId,
    isInterviewSubmitting,
    isReady,
    startThinkingIndicator,
    stopThinkingIndicator,
  ]);

  const handleEndInterview = useCallback(async () => {
    if (
      endingInterviewRef.current ||
      submittingAnswerRef.current ||
      isRecovering ||
      isEndingInterview ||
      isInterviewFailed
    ) {
      return;
    }
    const reportSessionId = interviewerSessionId;
    if (!reportSessionId) {
      const message = "当前没有可结束的面试会话。";
      setInterviewError(message);
      appendErrorMessage(message);
      return;
    }

    endingInterviewRef.current = true;
    setIsEndingInterview(true);

    try {
      if (!isInterviewFinished || isAutoSaveFailed) {
        await interviewService.finishInterviewSession(reportSessionId);
      }
      await invalidateInterviewRecords();

      stopThinkingIndicator();
      cancelActiveQuestionStream();
      answerRequestRef.current = null;
      persistInterviewerSessionId(null);
      clearStoredSession();
      resetProgressState();
      resetAutoSaveAttempt();
      navigate(`${ROUTES.interviewReport}${buildReportSearch(reportSessionId)}`, {
        state: { sessionId: reportSessionId },
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "结束面试失败，请稍后重试。";
      setInterviewError(message);
      appendErrorMessage(message);
    } finally {
      stopThinkingIndicator();
      cancelActiveQuestionStream();
      answerRequestRef.current = null;
      endingInterviewRef.current = false;
      setIsEndingInterview(false);
    }
  }, [
    appendErrorMessage,
    cancelActiveQuestionStream,
    clearStoredSession,
    interviewerSessionId,
    invalidateInterviewRecords,
    isEndingInterview,
    isRecovering,
    isInterviewFailed,
    isInterviewFinished,
    isAutoSaveFailed,
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
    isRecovering,
    retryRecovery,
    isInterviewSubmitting,
    interviewError,
    isEndingInterview,
    currentQuestionNumber,
    currentTurnId,
    currentQuestionContent,
    isCurrentQuestionFollowUp,
    currentFollowUpCount,
    isInterviewFinished,
    isInterviewFailed,
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
