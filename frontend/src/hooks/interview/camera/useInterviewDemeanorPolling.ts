import { useEffect, useRef, useState } from "react";
import {
  interviewService,
  type InterviewDemeanorEvaluationResult,
} from "@/services/interviewService";

type UseInterviewDemeanorPollingParams = {
  sessionId: string | null;
  enabled: boolean;
  captureFrame: () => Promise<Blob | null>;
};

const DEFAULT_DEMEANOR_POLLING_INTERVAL_MS = 5000;

export type DemeanorPollingStatus =
  | "idle"
  | "checking"
  | "analyzing"
  | "completed"
  | "unavailable"
  | "error";

const hasHttpStatus = (error: unknown, status: number) => {
  if (!error || typeof error !== "object") return false;
  const originalError = (error as { originalError?: unknown }).originalError;
  if (!originalError || typeof originalError !== "object") return false;
  const response = (originalError as { response?: unknown }).response;
  if (!response || typeof response !== "object") return false;
  return (response as { status?: unknown }).status === status;
};

export function useInterviewDemeanorPolling({
  sessionId,
  enabled,
  captureFrame,
}: UseInterviewDemeanorPollingParams) {
  const isUploadingRef = useRef(false);
  const [status, setStatus] = useState<DemeanorPollingStatus>("idle");
  const [latestEvaluation, setLatestEvaluation] =
    useState<InterviewDemeanorEvaluationResult | null>(null);

  useEffect(() => {
    if (!enabled || !sessionId) {
      setStatus("idle");
      setLatestEvaluation(null);
      return;
    }

    let cancelled = false;
    let timerId: number | undefined;
    setStatus("checking");
    setLatestEvaluation(null);

    const uploadFrame = async () => {
      if (cancelled || isUploadingRef.current) {
        return;
      }

      isUploadingRef.current = true;
      try {
        if (!cancelled) setStatus("analyzing");
        const frame = await captureFrame();
        if (cancelled || !frame) {
          return;
        }

        const evaluation = await interviewService.evaluateInterviewDemeanor({
          sessionId,
          userPhoto: frame,
        });
        if (!cancelled) {
          setLatestEvaluation(evaluation);
          setStatus("completed");
        }
      } catch (error) {
        if (!cancelled && hasHttpStatus(error, 503)) {
          cancelled = true;
          if (timerId !== undefined) window.clearInterval(timerId);
          setStatus("unavailable");
        } else if (!cancelled) {
          setStatus("error");
        }
      } finally {
        isUploadingRef.current = false;
      }
    };

    const startPolling = async () => {
      try {
        const capabilities = await interviewService.getInterviewDemeanorCapabilities();
        if (cancelled || !capabilities.available) {
          if (!cancelled) setStatus("unavailable");
          return;
        }

        void uploadFrame();
        timerId = window.setInterval(() => {
          void uploadFrame();
        }, Math.max(
          1000,
          Math.round(
            (capabilities.minIntervalSeconds || DEFAULT_DEMEANOR_POLLING_INTERVAL_MS / 1000) *
              1000,
          ),
        ));
      } catch {
        // Capability discovery is intentionally best-effort. A missing or
        // unavailable provider must never create a screenshot upload loop.
        if (!cancelled) setStatus("unavailable");
      }
    };

    void startPolling();

    return () => {
      cancelled = true;
      if (timerId !== undefined) window.clearInterval(timerId);
    };
  }, [captureFrame, enabled, sessionId]);

  return { status, latestEvaluation };
}
