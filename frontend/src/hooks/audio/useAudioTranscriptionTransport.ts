import { useCallback, useEffect, useMemo, useRef } from "react";
import { AudioToTextWebSocket } from "@/services/audioToTextWs";

type UseAudioTranscriptionTransportParams = {
  userId: string | null;
  onReplace: (text: string) => void;
  onArchive: (text: string) => void;
  onError: (message: string) => void;
};

export function useAudioTranscriptionTransport({
  userId,
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

  const disconnect = useCallback(() => {
    const transport = transportRef.current;
    transportRef.current = null;

    if (!transport) {
      return;
    }

    try {
      transport.sendCommand("stop_transcription");
    } catch (error) {
      console.error("Failed to send stop command", error);
    }

    transport.disconnect();
  }, []);

  const connect = useCallback(() => {
    if (!userId) {
      throw new Error("Audio transcription requires a valid user id");
    }

    disconnect();

    const transport = new AudioToTextWebSocket(userId);
    transport.onConnected = () => {
      transport.sendCommand("start_transcription");
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
  }, [disconnect, userId]);

  const sendAudioChunk = useCallback((data: ArrayBuffer) => {
    transportRef.current?.sendAudio(data);
  }, []);

  useEffect(() => disconnect, [disconnect]);

  return useMemo(
    () => ({
      connect,
      disconnect,
      sendAudioChunk,
    }),
    [connect, disconnect, sendAudioChunk],
  );
}
