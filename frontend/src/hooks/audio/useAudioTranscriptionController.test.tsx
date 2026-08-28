import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAudioTranscriptionController } from "@/hooks/audio/useAudioTranscriptionController";

const transportState = {
  connect: vi.fn(),
  disconnect: vi.fn(),
  sendAudioChunk: vi.fn(),
  params: null as null | {
    userId: string | null;
    onReplace: (text: string) => void;
    onArchive: (text: string) => void;
    onError: (message: string) => void;
  },
};

const streamState = {
  start: vi.fn(),
  stop: vi.fn(),
  params: null as null | {
    sampleRate: number;
    onChunk: (data: ArrayBuffer) => void;
    onError: (error: unknown) => void;
  },
};

vi.mock("@/hooks/audio/useAudioTranscriptionTransport", () => ({
  useAudioTranscriptionTransport: (params: typeof transportState.params) => {
    transportState.params = params;
    return {
      connect: transportState.connect,
      disconnect: transportState.disconnect,
      sendAudioChunk: transportState.sendAudioChunk,
    };
  },
}));

vi.mock("@/hooks/audio/useMicrophonePcmStream", () => ({
  useMicrophonePcmStream: (params: typeof streamState.params) => {
    streamState.params = params;
    return {
      start: streamState.start,
      stop: streamState.stop,
    };
  },
}));

const currentUser = {
  id: 1,
  username: "tester",
} as const;

describe("useAudioTranscriptionController", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    transportState.params = null;
    streamState.params = null;
    streamState.start.mockResolvedValue(undefined);
    streamState.stop.mockResolvedValue(undefined);
  });

  it("cleans up transport and microphone when startRecording fails", async () => {
    streamState.start.mockRejectedValueOnce(new Error("mic denied"));

    const { result, unmount } = renderHook(() =>
      useAudioTranscriptionController(currentUser),
    );

    await act(async () => {
      await result.current.startRecording();
    });

    expect(transportState.connect).toHaveBeenCalledTimes(1);
    expect(transportState.disconnect).toHaveBeenCalled();
    expect(streamState.stop).toHaveBeenCalled();
    expect(result.current.isRecording).toBe(false);
    expect(result.current.error).toBe(
      "Unable to access microphone or connect to transcription",
    );

    await act(async () => {
      unmount();
    });
  });

  it("stops the runtime and exposes the error when the transport fails", async () => {
    const { result, unmount } = renderHook(() =>
      useAudioTranscriptionController(currentUser),
    );

    await act(async () => {
      await result.current.startRecording();
    });

    await act(async () => {
      transportState.params?.onError("socket broke");
    });

    await waitFor(() => {
      expect(transportState.disconnect).toHaveBeenCalled();
      expect(streamState.stop).toHaveBeenCalled();
      expect(result.current.isRecording).toBe(false);
      expect(result.current.error).toBe("socket broke");
    });

    await act(async () => {
      unmount();
    });
  });

  it("does not clean up an active session during the rerender caused by startRecording", async () => {
    const { result, unmount } = renderHook(() =>
      useAudioTranscriptionController(currentUser),
    );

    await act(async () => {
      await result.current.startRecording();
    });

    expect(result.current.isRecording).toBe(true);
    expect(transportState.connect).toHaveBeenCalledTimes(1);
    expect(transportState.disconnect).not.toHaveBeenCalled();
    expect(streamState.stop).not.toHaveBeenCalled();

    await act(async () => {
      unmount();
    });
  });

  it("keeps stopRecording idempotent", async () => {
    const { result, unmount } = renderHook(() =>
      useAudioTranscriptionController(currentUser),
    );

    await act(async () => {
      result.current.stopRecording();
      result.current.stopRecording();
    });

    await waitFor(() => {
      expect(transportState.disconnect).toHaveBeenCalledTimes(1);
      expect(streamState.stop).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      unmount();
    });
  });

  it("merges partial and final transcription events through the reducer", async () => {
    const { result, unmount } = renderHook(() =>
      useAudioTranscriptionController(currentUser),
    );

    act(() => {
      transportState.params?.onReplace("partial answer");
    });

    expect(result.current.currentSentence).toBe("partial answer");
    expect(result.current.transcription).toBe("partial answer");

    act(() => {
      transportState.params?.onArchive("final answer");
    });

    expect(result.current.currentSentence).toBe("");
    expect(result.current.historySentences).toEqual(["final answer"]);
    expect(result.current.transcription).toBe("final answer");

    await act(async () => {
      unmount();
    });
  });
});
