import { useEffect, useRef } from "react";
import { interviewService } from "@/services/interviewService";

type UseInterviewDemeanorPollingParams = {
  sessionId: string | null;
  enabled: boolean;
  captureFrame: () => Promise<Blob | null>;
};

const DEMEANOR_POLLING_INTERVAL_MS = 5000;

export function useInterviewDemeanorPolling({
  sessionId,
  enabled,
  captureFrame,
}: UseInterviewDemeanorPollingParams) {
  const isUploadingRef = useRef(false);

  useEffect(() => {
    if (!enabled || !sessionId) {
      return;
    }

    let cancelled = false;

    const uploadFrame = async () => {
      if (cancelled || isUploadingRef.current) {
        return;
      }

      isUploadingRef.current = true;
      try {
        const frame = await captureFrame();
        if (cancelled || !frame) {
          return;
        }

        await interviewService.evaluateInterviewDemeanor({
          sessionId,
          userPhoto: frame,
        });
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to evaluate interview demeanor:", error);
        }
      } finally {
        isUploadingRef.current = false;
      }
    };

    void uploadFrame();
    const timerId = window.setInterval(() => {
      void uploadFrame();
    }, DEMEANOR_POLLING_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timerId);
    };
  }, [captureFrame, enabled, sessionId]);
}
