import { beforeEach, describe, expect, it, vi } from "vitest";

const getMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/request", () => ({
  default: { get: getMock },
}));

import { ttsService } from "@/services/ttsService";

describe("ttsService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the authenticated, secret-free TTS capabilities", async () => {
    getMock.mockResolvedValue({
      available: true,
      provider: "fake",
      supportedAudioFormats: ["wav"],
      supportedVoices: ["x4_mingge"],
      maxTextLength: 10000,
      supportsStreaming: false,
    });

    await expect(ttsService.getCapabilities()).resolves.toMatchObject({
      available: true,
      provider: "fake",
    });
    expect(getMock).toHaveBeenCalledWith(
      "/xunzhi/v1/speech/tts/capabilities",
    );
  });
});
