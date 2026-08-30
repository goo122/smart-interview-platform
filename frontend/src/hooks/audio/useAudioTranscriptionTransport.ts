import { useCallback, useEffect, useMemo, useRef } from "react";
import { AudioToTextWebSocket } from "@/services/audioToTextWs";

type UseAudioTranscriptionTransportParams = {
  userId: string | null;
  sampleRate: number;
  audioFormat: string;
  maxFrameBytes?: number;
  onReplace: (text: string) => void;
  onArchive: (text: string) => void;
  onError: (message: string) => void;
};

export function useAudioTranscriptionTransport({
  userId,
  sampleRate,
  audioFormat,
  maxFrameBytes,
  onReplace,
  onArchive,
  onError,
}: UseAudioTranscriptionTransportParams) {
  const transportRef = useRef<AudioToTextWebSocket | null>(null);
  const onReplaceRef = useRef(onReplace);
  const onArchiveRef = useRef(onArchive);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onReplaceRef.current = onReplace;
  }, [onReplace]);

  useEffect(() => {
    onArchiveRef.current = onArchive;
  }, [onArchive]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const disconnect = useCallback(async (graceful = false) => {
    const transport = transportRef.current;
    transportRef.current = null;

    if (!transport) {
      return;
    }

    if (graceful) {
      try {
        await transport.stopTranscription();
      } catch (error) {
        console.error("Failed to finish transcription", error);
      }
    }

    transport.disconnect();
  }, []);

  const connect = useCallback(() => {
    if (!userId) {
      throw new Error("Audio transcription requires a valid user id");
    }

    void disconnect(false);

    const transport = new AudioToTextWebSocket(userId);
    transport.onConnected = () => {
      transport.sendCommand("start_transcription", {
        audio_format: {
          encoding: audioFormat,
          sample_rate: sampleRate,
          channels: 1,
        },
      });
    };
    transport.onTranscription = (text) => {
      onReplaceRef.current(text);
    };
    transport.onFinal = (text) => {
      onArchiveRef.current(text);
    };
    transport.onError = (message) => {
      onErrorRef.current(message);
    };

    transportRef.current = transport;
    transport.connect();
  }, [audioFormat, disconnect, sampleRate, userId]);

  const sendAudioChunk = useCallback((data: ArrayBuffer) => {
    if (maxFrameBytes !== undefined && data.byteLength > maxFrameBytes) {
      onErrorRef.current("单个音频帧超过允许大小。");
      return;
    }
    transportRef.current?.sendAudio(data);
  }, [maxFrameBytes]);

  useEffect(() => {
    return () => {
      void disconnect(false);
    };
  }, [disconnect, userId]);

  return useMemo(
    () => ({
      connect,
      disconnect,
      sendAudioChunk,
    }),
    [connect, disconnect, sendAudioChunk],
  );
}
