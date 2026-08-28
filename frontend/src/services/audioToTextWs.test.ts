import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/authToken", () => ({
  getAuthToken: vi.fn(() => "token"),
}));

vi.mock("@/config/env", () => ({
  resolveApiBaseUrl: vi.fn(() => "/api"),
  resolveRuntimeWsBaseUrl: vi.fn(() => "ws://localhost:8080"),
  resolveWsBaseUrl: vi.fn(() => "ws://localhost:8080"),
}));

import { AudioToTextWebSocket } from "@/services/audioToTextWs";

describe("AudioToTextWebSocket message handling", () => {
  let instance: AudioToTextWebSocket;

  beforeEach(() => {
    instance = new AudioToTextWebSocket("tester");
  });

  it("ignores out-of-order transcription packets", () => {
    const onTranscription = vi.fn();
    instance.onTranscription = onTranscription;

    (
      instance as unknown as {
        handleMessage: (message: Record<string, unknown>) => void;
      }
    ).handleMessage({
      type: "transcription",
      data: "最新快照",
      timestamp: 20,
    });
    (
      instance as unknown as {
        handleMessage: (message: Record<string, unknown>) => void;
      }
    ).handleMessage({
      type: "transcription",
      data: "旧快照",
      timestamp: 10,
    });

    expect(onTranscription).toHaveBeenCalledTimes(1);
    expect(onTranscription).toHaveBeenCalledWith("最新快照");
  });

  it("deduplicates identical packets with the same timestamp", () => {
    const onTranscription = vi.fn();
    instance.onTranscription = onTranscription;

    const message = {
      type: "transcription",
      data: "重复快照",
      timestamp: 30,
    };
    (
      instance as unknown as {
        handleMessage: (incoming: typeof message) => void;
      }
    ).handleMessage(message);
    (
      instance as unknown as {
        handleMessage: (incoming: typeof message) => void;
      }
    ).handleMessage(message);

    expect(onTranscription).toHaveBeenCalledTimes(1);
  });

  it("clears the current snapshot when the server starts a new transcription session", () => {
    const onTranscription = vi.fn();
    instance.onTranscription = onTranscription;

    (
      instance as unknown as {
        handleMessage: (message: Record<string, unknown>) => void;
      }
    ).handleMessage({
      type: "transcription_started",
      timestamp: 40,
    });

    expect(onTranscription).toHaveBeenCalledWith("");
  });
});
