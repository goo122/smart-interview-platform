import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import {
  createInitialAudioTranscriptionState,
  getMergedAudioTranscription,
  reduceAudioTranscriptionState,
} from "@/lib/audioTranscription";
import { useAudioTranscriptionTransport } from "@/hooks/audio/useAudioTranscriptionTransport";
import { useMicrophonePcmStream } from "@/hooks/audio/useMicrophonePcmStream";
import type { UserRespDTO } from "@/types/auth";
import type { SpeechCapabilities } from "@/services/speechService";

const AUDIO_SAMPLE_RATE = 16000;
const START_RECORDING_ERROR =
  "Unable to access microphone or connect to transcription";

const resolveAudioUserId = (currentUser: UserRespDTO | null) => {
  const normalizedUsername = currentUser?.username?.trim();
  const normalizedUserId = currentUser?.id?.trim() || null;

  return normalizedUsername || normalizedUserId || null;
};

type AudioTranscriptionControllerOptions = {
  capabilities?: SpeechCapabilities | null;
  capabilitiesLoading?: boolean;
  availabilityMessage?: string | null;
};

export function useAudioTranscriptionController(
  currentUser: UserRespDTO | null,
  options: AudioTranscriptionControllerOptions = {},
) {
  const {
    capabilities,
    capabilitiesLoading = false,
    availabilityMessage = null,
  } = options;
  const legacyController = capabilities === undefined;
  const speechAvailable = legacyController || Boolean(capabilities?.available);
  const sampleRate = capabilities?.sampleRate ?? AUDIO_SAMPLE_RATE;
  const speechAvailabilityMessage =
    availabilityMessage ||
    (capabilitiesLoading
      ? "正在检查语音转写服务..."
      : speechAvailable
        ? null
        : "当前环境未配置语音转写服务。");
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [transcriptionState, dispatchTranscription] = useReducer(
    reduceAudioTranscriptionState,
    undefined,
    createInitialAudioTranscriptionState,
  );
  const cleanupPromiseRef = useRef<Promise<void> | null>(null);
  const cleanupRef = useRef<(graceful?: boolean) => Promise<void>>(
    async () => undefined,
  );
  const activeStartTokenRef = useRef<symbol | null>(null);

  const {
    connect: connectTransport,
    disconnect: disconnectTransport,
    sendAudioChunk,
  } = useAudioTranscriptionTransport({
    userId: resolveAudioUserId(currentUser),
    sampleRate,
    audioFormat: capabilities?.audioFormat ?? "pcm_s16le",
    maxFrameBytes: capabilities?.maxFrameBytes,
    onReplace: useCallback((text: string) => {
      dispatchTranscription({
        kind: "replace",
        text,
      });
    }, []),
    onArchive: useCallback((text: string) => {
      dispatchTranscription({
        kind: "archive",
        text,
      });
    }, []),
    onError: useCallback((message: string) => {
      setError(message);
      void cleanupRef.current(false);
    }, []),
  });

  const stream = useMicrophonePcmStream({
    sampleRate,
    onChunk: sendAudioChunk,
    onError: useCallback((streamError: unknown) => {
      console.error("Microphone PCM stream failed:", streamError);
      setError(START_RECORDING_ERROR);
      void cleanupRef.current(false);
    }, []),
  });

  const { start: startStream, stop: stopStream } = stream;

  const cleanup = useCallback(async (graceful = false) => {
    if (cleanupPromiseRef.current) {
      await cleanupPromiseRef.current;
      return;
    }

    cleanupPromiseRef.current = (async () => {
      activeStartTokenRef.current = null;
      await stopStream();
      await disconnectTransport(graceful);
      setIsRecording(false);
    })();

    try {
      await cleanupPromiseRef.current;
    } finally {
      cleanupPromiseRef.current = null;
    }
  }, [disconnectTransport, stopStream]);

  useEffect(() => {
    cleanupRef.current = cleanup;
  }, [cleanup]);

  const startRecording = useCallback(async () => {
    if (!currentUser) {
      setError("User is not logged in");
      return;
    }

    if (isRecording || activeStartTokenRef.current || !speechAvailable) {
      if (!speechAvailable && !capabilitiesLoading) {
        setError(speechAvailabilityMessage || "语音转写服务不可用");
      }
      return;
    }

    try {
      const startToken = Symbol("audio-transcription-start");
      activeStartTokenRef.current = startToken;
      setError(null);
      dispatchTranscription({
        kind: "reset",
      });
      connectTransport();
      await startStream();
      if (activeStartTokenRef.current !== startToken) {
        return;
      }
      activeStartTokenRef.current = null;
      setIsRecording(true);
    } catch (startError) {
      console.error("Start recording failed:", startError);
      setError(START_RECORDING_ERROR);
      await cleanup(false);
    }
  }, [
    capabilitiesLoading,
    cleanup,
    connectTransport,
    currentUser,
    isRecording,
    speechAvailabilityMessage,
    speechAvailable,
    startStream,
  ]);

  const stopRecording = useCallback(() => {
    void cleanup(true);
  }, [cleanup]);

  useEffect(() => {
    return () => {
      void cleanup(false);
    };
  }, [cleanup]);

  return useMemo(
    () => ({
      isRecording,
      currentSentence: transcriptionState.liveText,
      historySentences: transcriptionState.finalText
        ? transcriptionState.finalText
            .split(/\n\n+/)
            .map((sentence) => sentence.trim())
            .filter(Boolean)
        : [],
      transcription: getMergedAudioTranscription(transcriptionState),
      error,
      speechAvailable,
      speechAvailabilityMessage,
      capabilitiesLoading,
      startRecording,
      stopRecording,
    }),
    [
      capabilitiesLoading,
      error,
      isRecording,
      speechAvailabilityMessage,
      speechAvailable,
      startRecording,
      stopRecording,
      transcriptionState,
    ],
  );
}
