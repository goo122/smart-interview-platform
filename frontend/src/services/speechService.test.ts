import { beforeEach, describe, expect, it, vi } from "vitest";

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock("@/lib/request", () => ({
  default: {
    get: getMock,
  },
}));

import { speechService } from "@/services/speechService";

describe("speechService", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("queries the authenticated speech capabilities endpoint", async () => {
    const capabilities = {
      available: true,
      provider: "fake",
      audioFormat: "pcm_s16le",
      sampleRate: 16000,
      channels: 1,
      supportedAudioFormats: ["pcm_s16le"],
      supportedSampleRates: [16000],
      maxSessionSeconds: 120,
      maxFrameBytes: 65536,
      maxAudioBytes: 5242880,
    };
    getMock.mockResolvedValue(capabilities);

    await expect(speechService.getCapabilities()).resolves.toEqual(capabilities);
    expect(getMock).toHaveBeenCalledWith("/xunzhi/v1/speech/capabilities");
  });
});
