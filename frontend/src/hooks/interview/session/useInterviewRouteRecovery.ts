import { useEffect } from "react";
import { isMessageInWelcomeState } from "@/hooks/interview/session/interviewSessionFlow.shared";
import type { ChatMessage } from "@/lib/chat";

type UseInterviewRouteRecoveryParams = {
  routeSessionId: string | null;
  storedInterviewerSessionId: string | null;
  interviewerSessionId: string | null;
  persistInterviewerSessionId: (sessionId: string | null) => void;
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

    syncNextQuestion(interviewerSessionId).catch((error) => {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to restore interview state";
      setInterviewError(message);
    });
  }, [interviewerSessionId, messages, setInterviewError, syncNextQuestion]);
}
