import type { SpeechCapabilitiesResponse } from "@/api/generated";
import service from "@/lib/request";

export type SpeechCapabilities = SpeechCapabilitiesResponse;

export const speechService = {
  getCapabilities: () =>
    service.get<SpeechCapabilities>("/xunzhi/v1/speech/capabilities"),
};
