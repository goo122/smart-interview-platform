import type { TtsCapabilitiesResponse } from "@/api/generated";
import service from "@/lib/request";

export type TtsCapabilities = TtsCapabilitiesResponse;

export const ttsService = {
  getCapabilities: () =>
    service.get<TtsCapabilities>("/xunzhi/v1/speech/tts/capabilities"),
};
