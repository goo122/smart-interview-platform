import { useCallback, useMemo, useRef } from "react";

type UseChatTtsAudioElementParams = {
  onPlaybackEnded: () => void;
};

const AUDIO_READY_TIMEOUT_MS = 3_000;
const AUDIO_PLAY_TIMEOUT_MS = 3_000;
const AUDIO_UNLOCK_TIMEOUT_MS = 1_000;

const withTimeout = async <T,>(
  promise: Promise<T>,
  timeoutMs: number,
  message: string,
) =>
  await new Promise<T>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      reject(new Error(message));
    }, timeoutMs);

    promise.then(
      (value) => {
        window.clearTimeout(timeoutId);
        resolve(value);
      },
      (error) => {
        window.clearTimeout(timeoutId);
        reject(error);
      },
    );
  });

export function useChatTtsAudioElement({
  onPlaybackEnded,
}: UseChatTtsAudioElementParams) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playbackUnlockedRef = useRef(false);

  const ensureAudio = useCallback(() => {
    if (!audioRef.current) {
      const audio = new Audio();
      audio.preload = "auto";
      audio.onended = onPlaybackEnded;
      audio.onerror = onPlaybackEnded;
      audioRef.current = audio;
    }

    return audioRef.current;
  }, [onPlaybackEnded]);

  const resetAudioElement = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }

    audio.pause();
    audio.currentTime = 0;
    audio.removeAttribute("src");
    audio.load();
  }, []);

  const primePlaybackFromGesture = useCallback(async () => {
    if (playbackUnlockedRef.current) {
      return;
    }

    const audio = ensureAudio();
    const previousSrc = audio.currentSrc || audio.getAttribute("src") || "";

    try {
      audio.src =
        "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
      audio.muted = true;

      try {
        await withTimeout(
          audio.play(),
          AUDIO_UNLOCK_TIMEOUT_MS,
          "Audio unlock timed out",
        );
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          throw error;
        }
      }

      playbackUnlockedRef.current = true;
    } catch (error) {
      console.warn("Failed to unlock audio playback:", error);
    } finally {
      audio.muted = false;
      audio.pause();
      audio.currentTime = 0;
      if (previousSrc) {
        audio.src = previousSrc;
      } else {
        audio.removeAttribute("src");
      }
      audio.load();
    }
  }, [ensureAudio]);

  const waitForAudioReady = useCallback((audio: HTMLAudioElement) => {
    if (audio.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
      return Promise.resolve();
    }

    return new Promise<void>((resolve, reject) => {
      const timeoutId = window.setTimeout(() => {
        cleanup();
        reject(new Error("Audio element timed out while loading synthesized media"));
      }, AUDIO_READY_TIMEOUT_MS);

      const handleCanPlay = () => {
        cleanup();
        resolve();
      };

      const handleError = () => {
        cleanup();
        reject(new Error("Audio element failed to load synthesized media"));
      };

      const cleanup = () => {
        window.clearTimeout(timeoutId);
        audio.removeEventListener("canplaythrough", handleCanPlay);
        audio.removeEventListener("loadeddata", handleCanPlay);
        audio.removeEventListener("error", handleError);
      };

      audio.addEventListener("canplaythrough", handleCanPlay, { once: true });
      audio.addEventListener("loadeddata", handleCanPlay, { once: true });
      audio.addEventListener("error", handleError, { once: true });
      audio.load();
    });
  }, []);

  const playObjectUrl = useCallback(
    async (objectUrl: string) => {
      const audio = ensureAudio();
      audio.pause();
      audio.src = objectUrl;
      audio.currentTime = 0;
      await waitForAudioReady(audio);
      await withTimeout(
        audio.play(),
        AUDIO_PLAY_TIMEOUT_MS,
        "Audio playback timed out",
      );
    },
    [ensureAudio, waitForAudioReady],
  );

  const disposeAudioElement = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }

    audio.pause();
    audio.src = "";
    audioRef.current = null;
  }, []);

  return useMemo(
    () => ({
      audioRef,
      resetAudioElement,
      primePlaybackFromGesture,
      playObjectUrl,
      disposeAudioElement,
    }),
    [
      disposeAudioElement,
      playObjectUrl,
      primePlaybackFromGesture,
      resetAudioElement,
    ],
  );
}
