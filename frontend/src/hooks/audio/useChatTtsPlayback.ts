import { useCallback, useEffect, useRef, useState } from "react";
import { CHAT_MESSAGE_STATUS, type ChatMessage } from "@/lib/chat";
import {
  INTERVIEW_QUESTION_TTS_REQUEST,
  isAbortError,
} from "@/hooks/audio/chatTtsPlayback.shared";
import { useChatTtsAudioCache } from "@/hooks/audio/useChatTtsAudioCache";
import { useChatTtsAudioElement } from "@/hooks/audio/useChatTtsAudioElement";
import { xunfeiTtsService } from "@/services/xunfeiTtsService";

export function useChatTtsPlayback(messages: ChatMessage[]) {
  const loadingControllerRef = useRef<AbortController | null>(null);
  const autoPlayedMessageIdsRef = useRef(new Set<string>());
  const activeMessageIdRef = useRef<string | null>(null);
  const activeObjectUrlRef = useRef<string | null>(null);

  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [loadingMessageId, setLoadingMessageId] = useState<string | null>(null);

  const clearPlaybackState = useCallback(() => {
    activeMessageIdRef.current = null;
    activeObjectUrlRef.current = null;
    setPlayingMessageId(null);
    setLoadingMessageId(null);
  }, []);

  const {
    getCachedObjectUrl,
    cacheObjectUrl,
    removeCachedObjectUrl,
    resolvePlayableAudioUrl,
    revokePreparedObjectUrls,
  } = useChatTtsAudioCache();
  const {
    audioRef,
    resetAudioElement,
    primePlaybackFromGesture,
    playObjectUrl,
    disposeAudioElement,
  } = useChatTtsAudioElement({
    onPlaybackEnded: clearPlaybackState,
  });

  const stopPlayback = useCallback(() => {
    loadingControllerRef.current?.abort();
    loadingControllerRef.current = null;
    resetAudioElement();
    clearPlaybackState();
  }, [clearPlaybackState, resetAudioElement]);

  const playPreparedObjectUrl = useCallback(
    async (messageId: string, objectUrl: string) => {
      activeObjectUrlRef.current = objectUrl;
      await playObjectUrl(objectUrl);
      activeMessageIdRef.current = messageId;
      setPlayingMessageId(messageId);
      setLoadingMessageId(null);
    },
    [playObjectUrl],
  );

  const playMessage = useCallback(
    async (
      message: ChatMessage,
      options?: { userInitiated?: boolean; forceRefresh?: boolean },
    ) => {
      const ttsText = message.tts?.text?.trim() || message.content.trim();
      if (!message.tts || !ttsText) {
        return;
      }

      const messageId = message.id;
      const controller = new AbortController();

      loadingControllerRef.current?.abort();
      loadingControllerRef.current = controller;
      resetAudioElement();
      activeObjectUrlRef.current = null;
      activeMessageIdRef.current = messageId;
      setLoadingMessageId(messageId);
      setPlayingMessageId(null);

      try {
        if (options?.userInitiated) {
          await primePlaybackFromGesture();
        }

        if (options?.forceRefresh) {
          removeCachedObjectUrl(message);
        }

        const cachedObjectUrl = options?.forceRefresh
          ? undefined
          : getCachedObjectUrl(message);
        if (cachedObjectUrl) {
          try {
            await playPreparedObjectUrl(messageId, cachedObjectUrl);
            return;
          } catch (error) {
            if (isAbortError(error)) {
              throw error;
            }

            removeCachedObjectUrl(message);
          }
        }

        const task = await xunfeiTtsService.synthesize(
          {
            ...INTERVIEW_QUESTION_TTS_REQUEST,
            text: ttsText,
          },
          { signal: controller.signal },
        );
        const objectUrl = await resolvePlayableAudioUrl(
          task,
          controller.signal,
        );
        activeObjectUrlRef.current = objectUrl;

        if (controller.signal.aborted) {
          return;
        }

        await playPreparedObjectUrl(messageId, objectUrl);
        cacheObjectUrl(message, objectUrl);

        if (controller.signal.aborted) {
          audioRef.current?.pause();
        }
      } catch (error) {
        if (!isAbortError(error)) {
          console.error("Failed to play TTS audio:", error);
          if (
            error instanceof DOMException &&
            error.name === "NotAllowedError"
          ) {
            console.warn(
              "Audio playback was blocked by the browser. Click the play button again after the audio finishes loading.",
            );
          }
        }

        if (
          loadingControllerRef.current === controller ||
          activeMessageIdRef.current === messageId
        ) {
          clearPlaybackState();
        }
      } finally {
        if (loadingControllerRef.current === controller) {
          loadingControllerRef.current = null;
        }
      }
    },
    [
      audioRef,
      cacheObjectUrl,
      clearPlaybackState,
      getCachedObjectUrl,
      playPreparedObjectUrl,
      primePlaybackFromGesture,
      removeCachedObjectUrl,
      resetAudioElement,
      resolvePlayableAudioUrl,
    ],
  );

  const toggleMessagePlayback = useCallback(
    (message: ChatMessage) => {
      if (playingMessageId === message.id) {
        stopPlayback();
        return;
      }

      if (loadingMessageId === message.id) {
        stopPlayback();
      }

      void playMessage(message, { userInitiated: true, forceRefresh: true });
    },
    [loadingMessageId, playMessage, playingMessageId, stopPlayback],
  );

  useEffect(() => {
    const latestAutoPlayMessage = [...messages]
      .reverse()
      .find(
        (message) =>
          message.tts?.autoPlay &&
          message.status === CHAT_MESSAGE_STATUS.done &&
          !autoPlayedMessageIdsRef.current.has(message.id),
      );

    if (!latestAutoPlayMessage) {
      return;
    }

    autoPlayedMessageIdsRef.current.add(latestAutoPlayMessage.id);
    void playMessage(latestAutoPlayMessage);
  }, [messages, playMessage]);

  useEffect(() => {
    const activeMessageId = activeMessageIdRef.current;
    if (!activeMessageId) {
      return;
    }

    const stillExists = messages.some((message) => message.id === activeMessageId);
    if (!stillExists) {
      stopPlayback();
    }
  }, [messages, stopPlayback]);

  useEffect(
    () => () => {
      stopPlayback();
      disposeAudioElement();
      activeObjectUrlRef.current = null;
      revokePreparedObjectUrls();
    },
    [disposeAudioElement, revokePreparedObjectUrls, stopPlayback],
  );

  return {
    loadingMessageId,
    playingMessageId,
    stopPlayback,
    toggleMessagePlayback,
  };
}
