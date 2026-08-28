import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useChatTtsAudioCache } from "@/hooks/audio/useChatTtsAudioCache";
import type { ChatMessage } from "@/lib/chat";

const createObjectUrlMock = vi.fn(() => "blob:tts-audio");
const revokeObjectUrlMock = vi.fn();
const fetchMock = vi.fn();

const createMessage = (
  id: string,
  overrides: Partial<ChatMessage> = {},
): ChatMessage => ({
  id,
  role: "assistant",
  content: `message-${id}`,
  timestamp: Date.now(),
  tts: {
    text: `tts-${id}`,
    cacheKey: `cache-${id}`,
  },
  ...overrides,
});

describe("useChatTtsAudioCache", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", URL);
    vi.spyOn(URL, "createObjectURL").mockImplementation(createObjectUrlMock);
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(revokeObjectUrlMock);
  });

  it("uses cacheKey first and falls back to message id", () => {
    const { result } = renderHook(() => useChatTtsAudioCache());
    const withCacheKey = createMessage("m-1");
    const withoutCacheKey = createMessage("m-2", {
      tts: {
        text: "tts-m-2",
      },
    });

    expect(result.current.getPreparedAudioKey(withCacheKey)).toBe("cache-m-1");
    expect(result.current.getPreparedAudioKey(withoutCacheKey)).toBe("m-2");
  });

  it("stores and retrieves cached object urls by prepared audio key", () => {
    const { result } = renderHook(() => useChatTtsAudioCache());
    const message = createMessage("m-3");

    result.current.cacheObjectUrl(message, "blob:cached");

    expect(result.current.getCachedObjectUrl(message)).toBe("blob:cached");
  });

  it("removes and revokes a single cached object url", () => {
    const { result } = renderHook(() => useChatTtsAudioCache());
    const message = createMessage("m-3");

    result.current.cacheObjectUrl(message, "blob:cached");
    result.current.removeCachedObjectUrl(message);

    expect(revokeObjectUrlMock).toHaveBeenCalledWith("blob:cached");
    expect(result.current.getCachedObjectUrl(message)).toBeUndefined();
  });

  it("creates an object url from base64 audio", async () => {
    const { result } = renderHook(() => useChatTtsAudioCache());

    const objectUrl = await result.current.resolvePlayableAudioUrl(
      {
        completed: true,
        success: true,
        audioBase64: "QQ==",
        audioUrl: null,
      },
      new AbortController().signal,
    );

    expect(objectUrl).toBe("blob:tts-audio");
    expect(createObjectUrlMock).toHaveBeenCalledTimes(1);
  });

  it("downloads remote audio when no base64 payload is present", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      headers: {
        get: () => "audio/mpeg",
      },
      arrayBuffer: async () => new ArrayBuffer(8),
    });

    const { result } = renderHook(() => useChatTtsAudioCache());

    const objectUrl = await result.current.resolvePlayableAudioUrl(
      {
        completed: true,
        success: true,
        audioBase64: null,
        audioUrl: "https://example.com/audio.mp3",
      },
      new AbortController().signal,
    );

    expect(objectUrl).toBe("blob:tts-audio");
    expect(fetchMock).toHaveBeenCalledWith("https://example.com/audio.mp3", {
      method: "GET",
      mode: "cors",
      signal: expect.any(AbortSignal),
    });
  });

  it("revokes all prepared object urls during cleanup", () => {
    const { result } = renderHook(() => useChatTtsAudioCache());
    const first = createMessage("m-4");
    const second = createMessage("m-5");

    result.current.cacheObjectUrl(first, "blob:first");
    result.current.cacheObjectUrl(second, "blob:second");
    result.current.revokePreparedObjectUrls();

    expect(revokeObjectUrlMock).toHaveBeenCalledWith("blob:first");
    expect(revokeObjectUrlMock).toHaveBeenCalledWith("blob:second");
    expect(result.current.getCachedObjectUrl(first)).toBeUndefined();
    expect(result.current.getCachedObjectUrl(second)).toBeUndefined();
  });
});
