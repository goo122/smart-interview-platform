import { useCallback, useEffect, useState } from "react";
import { AppError, ErrorCode } from "@/lib/errors";

type UseInterviewRouteRecoveryParams = {
  routeSessionId: string | null;
  storedInterviewerSessionId: string | null;
  interviewerSessionId: string | null;
  persistInterviewerSessionId: (sessionId: string | null) => void;
  getInterviewSession: (sessionId: string) => Promise<{ status?: string }>;
  waitForFirstQuestion: (sessionId: string, signal?: AbortSignal) => Promise<void>;
  startInterviewSession: (sessionId: string) => Promise<{ status?: string }>;
  syncNextQuestion: (
    sessionId: string,
    options?: { appendMessage?: boolean; signal?: AbortSignal },
  ) => Promise<void>;
  setInterviewError: (message: string | null) => void;
};

export function useInterviewRouteRecovery({
  routeSessionId,
  storedInterviewerSessionId,
  interviewerSessionId,
  persistInterviewerSessionId,
  getInterviewSession,
  waitForFirstQuestion,
  startInterviewSession,
  syncNextQuestion,
  setInterviewError,
}: UseInterviewRouteRecoveryParams) {
  const [isRecovering, setIsRecovering] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const retryRecovery = useCallback(() => setRetryCount((count) => count + 1), []);
  useEffect(() => {
    if (!routeSessionId) {
      return;
    }
    if (storedInterviewerSessionId === routeSessionId) {
      return;
    }
    persistInterviewerSessionId(routeSessionId);
  }, [persistInterviewerSessionId, routeSessionId, storedInterviewerSessionId]);

  useEffect(() => {
    if (!interviewerSessionId) {
      return;
    }

    const controller = new AbortController();
    void (async () => {
      setIsRecovering(true);
      setInterviewError(null);
      const session = await getInterviewSession(interviewerSessionId);
      controller.signal.throwIfAborted();
      if (session.status === "CREATED" || session.status === "PREPARING") {
        await waitForFirstQuestion(interviewerSessionId, controller.signal);
        if (controller.signal.aborted) {
          return;
        }
        await startInterviewSession(interviewerSessionId);
      } else if (session.status === "READY") {
        await startInterviewSession(interviewerSessionId);
      }
      if (!controller.signal.aborted) {
        await syncNextQuestion(interviewerSessionId, { signal: controller.signal });
      }
    })().catch((error) => {
      if (!controller.signal.aborted) {
        const message =
          error instanceof AppError && error.code === ErrorCode.RESOURCE_NOT_FOUND
            ? "面试不存在或无权访问，请返回面试列表。"
            : error instanceof Error
              ? error.message
              : "Failed to restore interview state";
        setInterviewError(message);
      }
    }).finally(() => {
      if (!controller.signal.aborted) setIsRecovering(false);
    });
    return () => controller.abort();
  }, [
    getInterviewSession,
    interviewerSessionId,
    retryCount,
    setInterviewError,
    startInterviewSession,
    syncNextQuestion,
    waitForFirstQuestion,
  ]);
  return { isRecovering, retryRecovery };
}
