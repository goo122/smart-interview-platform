import { useEffect } from "react";
import { isMessageInWelcomeState } from "@/hooks/interview/session/interviewSessionFlow.shared";
import type { ChatMessage } from "@/lib/chat";

type UseInterviewRouteRecoveryParams = {
  routeSessionId: string | null;
  storedInterviewerSessionId: string | null;
  interviewerSessionId: string | null;
  persistInterviewerSessionId: (sessionId: string | null) => void;
  getInterviewSession: (sessionId: string) => Promise<{ status?: string }>;
  waitForFirstQuestion: (sessionId: string, signal?: AbortSignal) => Promise<void>;
  startInterviewSession: (sessionId: string) => Promise<{ status?: string }>;
  messages: ChatMessage[];
  syncNextQuestion: (
    sessionId: string,
    options?: { appendMessage?: boolean },
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
  messages,
  syncNextQuestion,
  setInterviewError,
}: UseInterviewRouteRecoveryParams) {
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
    if (!interviewerSessionId || !isMessageInWelcomeState(messages)) {
      return;
    }

    const controller = new AbortController();
    void (async () => {
      const session = await getInterviewSession(interviewerSessionId);
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
        await syncNextQuestion(interviewerSessionId);
      }
    })().catch((error) => {
      if (!controller.signal.aborted) {
        const message =
          error instanceof Error
            ? error.message
            : "Failed to restore interview state";
        setInterviewError(message);
      }
    });
    return () => controller.abort();
  }, [
    getInterviewSession,
    interviewerSessionId,
    messages,
    setInterviewError,
    startInterviewSession,
    syncNextQuestion,
    waitForFirstQuestion,
  ]);
}
