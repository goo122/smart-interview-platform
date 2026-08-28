import { useCallback, useEffect, useRef } from "react";
import { CHAT_MESSAGE_STATUS } from "@/lib/chat";
import {
  AUTO_SAVE_FAILED_TEXT,
  AUTO_SAVE_SUCCESS_TEXT,
} from "@/hooks/interview/session/interviewSessionFlow.shared";
import { interviewService } from "@/services/interviewService";

type UseInterviewAutoSaveParams = {
  interviewerSessionId: string | null;
  isInterviewFinished: boolean;
  appendSystemMessage: (
    content: string,
    status?: (typeof CHAT_MESSAGE_STATUS)[keyof typeof CHAT_MESSAGE_STATUS],
  ) => void;
  invalidateInterviewRecords: () => Promise<unknown>;
};

export function useInterviewAutoSave({
  interviewerSessionId,
  isInterviewFinished,
  appendSystemMessage,
  invalidateInterviewRecords,
}: UseInterviewAutoSaveParams) {
  const autoSaveAttemptedSessionRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isInterviewFinished || !interviewerSessionId) {
      return;
    }
    if (autoSaveAttemptedSessionRef.current === interviewerSessionId) {
      return;
    }

    autoSaveAttemptedSessionRef.current = interviewerSessionId;
    let cancelled = false;

    const runAutoSave = async () => {
      try {
        await interviewService.finishInterviewSession(interviewerSessionId);
        await invalidateInterviewRecords();
        if (cancelled) {
          return;
        }
        appendSystemMessage(AUTO_SAVE_SUCCESS_TEXT);
      } catch (error) {
        if (cancelled) {
          return;
        }
        console.error("Auto save interview record failed:", error);
        appendSystemMessage(AUTO_SAVE_FAILED_TEXT, CHAT_MESSAGE_STATUS.error);
      }
    };

    void runAutoSave();

    return () => {
      cancelled = true;
    };
  }, [
    appendSystemMessage,
    interviewerSessionId,
    invalidateInterviewRecords,
    isInterviewFinished,
  ]);

  const resetAutoSaveAttempt = useCallback(() => {
    autoSaveAttemptedSessionRef.current = null;
  }, []);

  return {
    resetAutoSaveAttempt,
  };
}
