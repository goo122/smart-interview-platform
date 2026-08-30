import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatMessage } from "@/lib/chat";

const mocks = vi.hoisted(() => {
  const cachedUrls = new Map<string, string>();
  const synthesize = vi.fn();
  const playObjectUrl = vi.fn();
  const primePlaybackFromGesture = vi.fn();
  const resetAudioElement = vi.fn();
  const disposeAudioElement = vi.fn();
  const releaseUncachedObjectUrl = vi.fn();
  const removeCachedObjectUrl = vi.fn((message: ChatMessage) => {
    cachedUrls.delete(message.tts?.cacheKey || message.id);
  });
  const cacheObjectUrl = vi.fn((message: ChatMessage, url: string) => {
    cachedUrls.set(message.tts?.cacheKey || message.id, url);
  });
  const getCachedObjectUrl = vi.fn((message: ChatMessage) =>
    cachedUrls.get(message.tts?.cacheKey || message.id),
  );
  return {
    cachedUrls,
    synthesize,
    playObjectUrl,
    primePlaybackFromGesture,
    resetAudioElement,
    disposeAudioElement,
    releaseUncachedObjectUrl,
    removeCachedObjectUrl,
    cacheObjectUrl,
    getCachedObjectUrl,
    audioRef: { current: { pause: vi.fn() } as unknown as HTMLAudioElement },
    pruneCachedObjectUrls: vi.fn(),
    revokePreparedObjectUrls: vi.fn(),
    resolvePlayableAudioUrl: vi.fn(async (task: { taskId?: string }) =>
      `blob:${task.taskId || "audio"}`,
    ),
  };
});

vi.mock("@/services/xunfeiTtsService", () => ({
  xunfeiTtsService: { synthesize: mocks.synthesize },
}));

vi.mock("@/hooks/audio/useChatTtsAudioCache", () => ({
  useChatTtsAudioCache: () => ({
    getCachedObjectUrl: mocks.getCachedObjectUrl,
    cacheObjectUrl: mocks.cacheObjectUrl,
    removeCachedObjectUrl: mocks.removeCachedObjectUrl,
    releaseUncachedObjectUrl: mocks.releaseUncachedObjectUrl,
    pruneCachedObjectUrls: mocks.pruneCachedObjectUrls,
    resolvePlayableAudioUrl: mocks.resolvePlayableAudioUrl,
    revokePreparedObjectUrls: mocks.revokePreparedObjectUrls,
  }),
}));

vi.mock("@/hooks/audio/useChatTtsAudioElement", () => ({
  useChatTtsAudioElement: () => ({
    audioRef: mocks.audioRef,
    resetAudioElement: mocks.resetAudioElement,
    primePlaybackFromGesture: mocks.primePlaybackFromGesture,
    playObjectUrl: mocks.playObjectUrl,
    disposeAudioElement: mocks.disposeAudioElement,
  }),
}));

import { useChatTtsPlayback } from "@/hooks/audio/useChatTtsPlayback";

const createMessage = (id: string, autoPlay = false): ChatMessage => ({
  id,
  role: "assistant",
  content: `message-${id}`,
  timestamp: Date.now(),
  status: "done",
  tts: { text: `tts-${id}`, cacheKey: `cache-${id}`, autoPlay },
});

describe("useChatTtsPlayback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.cachedUrls.clear();
    mocks.synthesize.mockResolvedValue({
      taskId: "task-1",
      completed: true,
      success: true,
      audioBase64: "UklGRg==",
      audioUrl: null,
      audioFormat: "wav",
      contentType: "audio/wav",
    });
    mocks.playObjectUrl.mockResolvedValue(undefined);
    mocks.primePlaybackFromGesture.mockResolvedValue(undefined);
  });

  it("plays, pauses, replays and reuses the cached audio", async () => {
    const message = createMessage("m-1");
    const { result } = renderHook(({ messages }) => useChatTtsPlayback(messages), {
      initialProps: { messages: [message] },
    });

    await act(async () => result.current.toggleMessagePlayback(message));
    await waitFor(() => expect(result.current.playingMessageId).toBe("m-1"));
    expect(mocks.synthesize).toHaveBeenCalledTimes(1);

    act(() => result.current.toggleMessagePlayback(message));
    expect(result.current.playingMessageId).toBeNull();

    await act(async () => result.current.toggleMessagePlayback(message));
    await waitFor(() => expect(result.current.playingMessageId).toBe("m-1"));
    expect(mocks.synthesize).toHaveBeenCalledTimes(1);
    expect(mocks.playObjectUrl).toHaveBeenCalledTimes(2);
  });

  it("stops the previous message when a new message starts", async () => {
    const first = createMessage("m-1");
    const second = createMessage("m-2");
    const { result } = renderHook(() => useChatTtsPlayback([first, second]));

    await act(async () => result.current.toggleMessagePlayback(first));
    await waitFor(() => expect(result.current.playingMessageId).toBe("m-1"));
    await act(async () => result.current.toggleMessagePlayback(second));
    await waitFor(() => expect(result.current.playingMessageId).toBe("m-2"));
    expect(mocks.resetAudioElement).toHaveBeenCalledTimes(2);
  });

  it("shows a safe error and clears loading after a playback failure", async () => {
    mocks.synthesize.mockRejectedValueOnce(new Error("provider detail"));
    const message = createMessage("m-error");
    const { result } = renderHook(() => useChatTtsPlayback([message]));

    await act(async () => result.current.toggleMessagePlayback(message));
    await waitFor(() => expect(result.current.errorMessageId).toBe("m-error"));
    expect(result.current.errorMessage).toBe("语音播放失败，请稍后重试。");
    expect(result.current.loadingMessageId).toBeNull();
    expect(result.current.playingMessageId).toBeNull();
  });

  it("reports browser autoplay blocking without treating it as a provider failure", async () => {
    mocks.playObjectUrl.mockRejectedValueOnce(
      new DOMException("blocked", "NotAllowedError"),
    );
    const message = createMessage("m-autoplay");
    const { result } = renderHook(() => useChatTtsPlayback([message]));

    await act(async () => result.current.toggleMessagePlayback(message));
    await waitFor(() => expect(result.current.errorMessageId).toBe("m-autoplay"));
    expect(result.current.errorMessage).toBe(
      "浏览器阻止了自动播放，请点击播放按钮重试。",
    );
  });

  it("does not show a normal error for an aborted request and cleans up on unmount", async () => {
    mocks.synthesize.mockRejectedValueOnce(new DOMException("aborted", "AbortError"));
    const message = createMessage("m-abort");
    const { result, unmount } = renderHook(() => useChatTtsPlayback([message]));

    await act(async () => result.current.toggleMessagePlayback(message));
    await waitFor(() => expect(result.current.loadingMessageId).toBeNull());
    expect(result.current.errorMessage).toBeNull();

    unmount();
    expect(mocks.disposeAudioElement).toHaveBeenCalled();
    expect(mocks.revokePreparedObjectUrls).toHaveBeenCalled();
  });

  it("releases audio resources when the page is hidden", () => {
    const { unmount } = renderHook(() => useChatTtsPlayback([createMessage("m-pagehide")]));

    act(() => {
      window.dispatchEvent(new Event("pagehide"));
    });

    expect(mocks.disposeAudioElement).toHaveBeenCalled();
    expect(mocks.revokePreparedObjectUrls).toHaveBeenCalled();
    unmount();
  });

  it("does not start playback while TTS capability is unavailable", async () => {
    const message = createMessage("m-unavailable", true);
    const { result } = renderHook(() =>
      useChatTtsPlayback([message], { enabled: false }),
    );

    expect(result.current.ttsAvailable).toBe(false);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mocks.synthesize).not.toHaveBeenCalled();
  });
});
