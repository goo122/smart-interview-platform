import { useCallback, useEffect, useRef, useState } from "react";
import { CHAT_MESSAGE_STATUS, type ChatMessage } from "@/lib/chat";
import {
  INTERVIEW_QUESTION_TTS_REQUEST,
  isAbortError,
  type SynthesizedTtsTask,
} from "@/hooks/audio/chatTtsPlayback.shared";
import { useChatTtsAudioCache } from "@/hooks/audio/useChatTtsAudioCache";
import { useChatTtsAudioElement } from "@/hooks/audio/useChatTtsAudioElement";
import { xunfeiTtsService } from "@/services/xunfeiTtsService";

const isAutoplayBlockedError = (error: unknown) =>
  (error instanceof DOMException && error.name === "NotAllowedError") ||
  (error instanceof Error && error.name === "NotAllowedError");

type TtsPlaybackOptions = {
  enabled?: boolean;
};

type SynthesisRequest = {
  controller: AbortController;
  promise: Promise<SynthesizedTtsTask>;
};

export function useChatTtsPlayback(
  messages: ChatMessage[],
  { enabled = true }: TtsPlaybackOptions = {},
) {
  const loadingControllerRef = useRef<AbortController | null>(null);
  const synthesisRequestsRef = useRef(new Map<string, SynthesisRequest>());
  const autoPlayedMessageIdsRef = useRef(new Set<string>());
  const activeMessageIdRef = useRef<string | null>(null);
  const activeObjectUrlRef = useRef<string | null>(null);

  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [loadingMessageId, setLoadingMessageId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorMessageId, setErrorMessageId] = useState<string | null>(null);

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
    releaseUncachedObjectUrl,
    pruneCachedObjectUrls,
    resolvePlayableAudioUrl,
    revokePreparedObjectUrls,
    getPreparedAudioKey,
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

  const releaseActiveObjectUrl = useCallback(() => {
    releaseUncachedObjectUrl(activeObjectUrlRef.current);
    activeObjectUrlRef.current = null;
  }, [releaseUncachedObjectUrl]);

  const abortSynthesisRequests = useCallback(() => {
    for (const request of synthesisRequestsRef.current.values()) {
      request.controller.abort();
    }
    synthesisRequestsRef.current.clear();
  }, []);

  const getSynthesisTask = useCallback(
    (message: ChatMessage, text: string) => {
      const key = getPreparedAudioKey(message);
      const existingRequest = synthesisRequestsRef.current.get(key);
      if (existingRequest) {
        return existingRequest.promise;
      }

      const controller = new AbortController();
      const requestId = `message-${key}`.slice(0, 128);
      const promise = xunfeiTtsService
        .synthesize(
          {
            ...INTERVIEW_QUESTION_TTS_REQUEST,
            text,
            requestId,
          },
          { signal: controller.signal },
        )
        .catch((error: unknown) => {
          if (synthesisRequestsRef.current.get(key)?.promise === promise) {
            synthesisRequestsRef.current.delete(key);
          }
          throw error;
        });

      synthesisRequestsRef.current.set(key, { controller, promise });
      return promise;
    },
    [getPreparedAudioKey],
  );

  const refreshSynthesisTask = useCallback(
    (message: ChatMessage) => {
      const key = getPreparedAudioKey(message);
      const existingRequest = synthesisRequestsRef.current.get(key);
      existingRequest?.controller.abort();
      synthesisRequestsRef.current.delete(key);
    },
    [getPreparedAudioKey],
  );

  const stopPlayback = useCallback(() => {
    loadingControllerRef.current?.abort();
    loadingControllerRef.current = null;
    releaseActiveObjectUrl();
    resetAudioElement();
    clearPlaybackState();
  }, [clearPlaybackState, releaseActiveObjectUrl, resetAudioElement]);

  const releaseTtsResources = useCallback(() => {
    stopPlayback();
    abortSynthesisRequests();
    disposeAudioElement();
    activeObjectUrlRef.current = null;
    revokePreparedObjectUrls();
  }, [abortSynthesisRequests, disposeAudioElement, revokePreparedObjectUrls, stopPlayback]);

  const playPreparedObjectUrl = useCallback(
    async (
      messageId: string,
      objectUrl: string,
      controller: AbortController,
    ) => {
      activeObjectUrlRef.current = objectUrl;
      await playObjectUrl(objectUrl);
      if (
        controller.signal.aborted ||
        loadingControllerRef.current !== controller
      ) {
        return false;
      }
      activeMessageIdRef.current = messageId;
      setPlayingMessageId(messageId);
      setLoadingMessageId(null);
      return true;
    },
    [playObjectUrl],
  );

  const playMessage = useCallback(
    async (
      message: ChatMessage,
      options?: { userInitiated?: boolean; forceRefresh?: boolean },
    ) => {
      const ttsText = message.tts?.text?.trim() || message.content.trim();
      if (!enabled || !message.tts || !ttsText) {
        return;
      }

      const messageId = message.id;
      const controller = new AbortController();

      loadingControllerRef.current?.abort();
      loadingControllerRef.current = controller;
      releaseActiveObjectUrl();
      resetAudioElement();
      activeMessageIdRef.current = messageId;
      setLoadingMessageId(messageId);
      setPlayingMessageId(null);
      setErrorMessage(null);
      setErrorMessageId(null);

      try {
        if (options?.userInitiated) {
          await primePlaybackFromGesture();
        }

        if (options?.forceRefresh) {
          removeCachedObjectUrl(message);
          refreshSynthesisTask(message);
        }

        const cachedObjectUrl = options?.forceRefresh
          ? undefined
          : getCachedObjectUrl(message);
        if (cachedObjectUrl) {
          try {
            await playPreparedObjectUrl(messageId, cachedObjectUrl, controller);
            return;
          } catch (error) {
            if (isAbortError(error) || isAutoplayBlockedError(error)) {
              throw error;
            }
            removeCachedObjectUrl(message);
          }
        }

        const task = await getSynthesisTask(message, ttsText);
        if (
          controller.signal.aborted ||
          loadingControllerRef.current !== controller
        ) {
          return;
        }
        const objectUrl = await resolvePlayableAudioUrl(task, controller.signal);

        if (
          controller.signal.aborted ||
          loadingControllerRef.current !== controller
        ) {
          releaseUncachedObjectUrl(objectUrl);
          return;
        }

        const played = await playPreparedObjectUrl(
          messageId,
          objectUrl,
          controller,
        );
        if (!played) {
          releaseUncachedObjectUrl(objectUrl);
          return;
        }

        cacheObjectUrl(message, objectUrl);
        if (controller.signal.aborted) {
          audioRef.current?.pause();
        }
      } catch (error) {
        if (!isAbortError(error)) {
          setErrorMessage(
            isAutoplayBlockedError(error)
              ? "浏览器阻止了自动播放，请点击播放按钮重试。"
              : "语音播放失败，请稍后重试。",
          );
          setErrorMessageId(messageId);
        }

        if (
          loadingControllerRef.current === controller ||
          activeMessageIdRef.current === messageId
        ) {
          releaseActiveObjectUrl();
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
      enabled,
      getCachedObjectUrl,
      getSynthesisTask,
      playPreparedObjectUrl,
      primePlaybackFromGesture,
      releaseActiveObjectUrl,
      releaseUncachedObjectUrl,
      removeCachedObjectUrl,
      refreshSynthesisTask,
      resetAudioElement,
      resolvePlayableAudioUrl,
    ],
  );

  const toggleMessagePlayback = useCallback(
    (message: ChatMessage) => {
      if (!enabled) {
        return;
      }
      if (playingMessageId === message.id) {
        stopPlayback();
        return;
      }
      if (loadingMessageId === message.id) {
        stopPlayback();
        return;
      }
      void playMessage(message, { userInitiated: true });
    },
    [enabled, loadingMessageId, playMessage, playingMessageId, stopPlayback],
  );

  const refreshMessagePlayback = useCallback(
    (message: ChatMessage) => {
      if (!enabled) {
        return;
      }
      void playMessage(message, { userInitiated: true, forceRefresh: true });
    },
    [enabled, playMessage],
  );

  useEffect(() => {
    if (!enabled) {
      stopPlayback();
      abortSynthesisRequests();
      return;
    }

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
  }, [abortSynthesisRequests, enabled, messages, playMessage, stopPlayback]);

  useEffect(() => {
    const activeMessageId = activeMessageIdRef.current;
    if (activeMessageId && !messages.some((message) => message.id === activeMessageId)) {
      stopPlayback();
    }

    const activeKeys = new Set(messages.map(getPreparedAudioKey));
    for (const [key, request] of synthesisRequestsRef.current) {
      if (!activeKeys.has(key)) {
        request.controller.abort();
        synthesisRequestsRef.current.delete(key);
      }
    }
  }, [getPreparedAudioKey, messages, stopPlayback]);

  useEffect(() => {
    pruneCachedObjectUrls(messages);
  }, [messages, pruneCachedObjectUrls]);

  useEffect(() => {
    window.addEventListener("pagehide", releaseTtsResources);
    return () => {
      window.removeEventListener("pagehide", releaseTtsResources);
      releaseTtsResources();
    };
  }, [releaseTtsResources]);

  return {
    loadingMessageId,
    playingMessageId,
    refreshMessagePlayback,
    errorMessage,
    errorMessageId,
    ttsAvailable: enabled,
    stopPlayback,
    toggleMessagePlayback,
  };
}
