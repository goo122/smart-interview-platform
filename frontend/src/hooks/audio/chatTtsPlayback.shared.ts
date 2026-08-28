import { AppError, ErrorCode } from "@/lib/errors";
import { xunfeiTtsService } from "@/services/xunfeiTtsService";

export const INTERVIEW_QUESTION_TTS_REQUEST = Object.freeze({
  vcn: "x4_mingge",
  language: "zh",
  speed: 50,
  volume: 50,
  pitch: 50,
  rhy: 0,
  audioEncoding: "lame",
  sampleRate: 16000,
  timeoutSeconds: 90,
  pollIntervalMs: 1500,
});

export const isAbortError = (error: unknown) =>
  error instanceof AppError
    ? error.code === ErrorCode.ABORTED
    : error instanceof DOMException
      ? error.name === "AbortError"
      : error instanceof Error && error.name === "AbortError";

export const normalizeBase64Audio = (value: string) =>
  value
    .trim()
    .replace(/^data:audio\/[a-zA-Z0-9.+-]+;base64,/, "")
    .replace(/\s+/g, "")
    .replace(/-/g, "+")
    .replace(/_/g, "/");

export type SynthesizedTtsTask = Awaited<
  ReturnType<typeof xunfeiTtsService.synthesize>
>;
