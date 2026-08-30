import { useCallback, useMemo, useRef } from "react";
import type { ChatMessage } from "@/lib/chat";
import type { SynthesizedTtsTask } from "@/hooks/audio/chatTtsPlayback.shared";
import { normalizeBase64Audio } from "@/hooks/audio/chatTtsPlayback.shared";

export function useChatTtsAudioCache() {
  const preparedObjectUrlMapRef = useRef(new Map<string, string>());

  const getPreparedAudioKey = useCallback((message: ChatMessage) => {
    return message.tts?.cacheKey?.trim() || message.id;
  }, []);

  const getCachedObjectUrl = useCallback((message: ChatMessage) => {
    return preparedObjectUrlMapRef.current.get(getPreparedAudioKey(message));
  }, [getPreparedAudioKey]);

  const cacheObjectUrl = useCallback(
    (message: ChatMessage, objectUrl: string) => {
      const key = getPreparedAudioKey(message);
      const previousObjectUrl = preparedObjectUrlMapRef.current.get(key);
      if (previousObjectUrl && previousObjectUrl !== objectUrl) {
        URL.revokeObjectURL(previousObjectUrl);
      }
      preparedObjectUrlMapRef.current.set(key, objectUrl);
    },
    [getPreparedAudioKey],
  );

  const releaseUncachedObjectUrl = useCallback((objectUrl: string | null) => {
    if (!objectUrl || [...preparedObjectUrlMapRef.current.values()].includes(objectUrl)) {
      return;
    }
    URL.revokeObjectURL(objectUrl);
  }, []);

  const pruneCachedObjectUrls = useCallback(
    (messages: ChatMessage[]) => {
      const activeKeys = new Set(messages.map(getPreparedAudioKey));
      for (const [key, objectUrl] of preparedObjectUrlMapRef.current) {
        if (!activeKeys.has(key)) {
          URL.revokeObjectURL(objectUrl);
          preparedObjectUrlMapRef.current.delete(key);
        }
      }
    },
    [getPreparedAudioKey],
  );

  const removeCachedObjectUrl = useCallback(
    (message: ChatMessage) => {
      const key = getPreparedAudioKey(message);
      const objectUrl = preparedObjectUrlMapRef.current.get(key);
      if (!objectUrl) {
        return;
      }

      URL.revokeObjectURL(objectUrl);
      preparedObjectUrlMapRef.current.delete(key);
    },
    [getPreparedAudioKey],
  );

  const resolvePlayableAudioUrl = useCallback(
    async (task: SynthesizedTtsTask, signal: AbortSignal) => {
      if (task.audioBase64) {
        const normalizedBase64 = normalizeBase64Audio(task.audioBase64);
        const byteString = window.atob(normalizedBase64);
        const byteArray = new Uint8Array(byteString.length);

        for (let index = 0; index < byteString.length; index += 1) {
          byteArray[index] = byteString.charCodeAt(index);
        }

        return URL.createObjectURL(
          new Blob([byteArray], {
            type:
              task.contentType ||
              (task.audioFormat === "wav" ? "audio/wav" : "audio/mpeg"),
          }),
        );
      }

      const remoteUrl = task.audioUrl?.trim();
      if (!remoteUrl) {
        throw new Error("TTS task completed without audio payload");
      }

      const response = await fetch(remoteUrl, {
        method: "GET",
        mode: "cors",
        signal,
      });

      if (!response.ok) {
        throw new Error(
          `Failed to download synthesized audio: ${response.status}`,
        );
      }

      const contentType = response.headers.get("Content-Type")?.trim();
      const buffer = await response.arrayBuffer();
      return URL.createObjectURL(
        new Blob([buffer], {
          type:
            contentType && contentType !== "application/octet-stream"
              ? contentType
              : task.contentType ||
                (task.audioFormat === "wav" ? "audio/wav" : "audio/mpeg"),
        }),
      );
    },
    [],
  );

  const revokePreparedObjectUrls = useCallback(() => {
    preparedObjectUrlMapRef.current.forEach((objectUrl) => {
      URL.revokeObjectURL(objectUrl);
    });
    preparedObjectUrlMapRef.current.clear();
  }, []);

  return useMemo(
    () => ({
      getPreparedAudioKey,
      getCachedObjectUrl,
      cacheObjectUrl,
      removeCachedObjectUrl,
      releaseUncachedObjectUrl,
      pruneCachedObjectUrls,
      resolvePlayableAudioUrl,
      revokePreparedObjectUrls,
    }),
    [
      cacheObjectUrl,
      getCachedObjectUrl,
      getPreparedAudioKey,
      pruneCachedObjectUrls,
      removeCachedObjectUrl,
      releaseUncachedObjectUrl,
      resolvePlayableAudioUrl,
      revokePreparedObjectUrls,
    ],
  );
}
