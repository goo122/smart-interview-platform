import { afterEach, describe, expect, it, vi } from "vitest";
import service from "@/lib/request";
import { aiService } from "@/services/aiService";

describe("aiService.getAiProperties", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps the compatibility endpoint pagination parameters", async () => {
    const getSpy = vi.spyOn(service, "get").mockResolvedValue({
      records: [
        {
          id: 1,
          aiName: "寻知开发测试模型",
          aiType: "fake",
          modelName: "fake-interview-model",
          isEnabled: 1,
          enableThinking: 0,
        },
      ],
      total: 1,
      size: 10,
      current: 2,
      pages: 1,
    });

    await aiService.getAiProperties({ current: 2, size: 10, isEnabled: 1 });

    expect(getSpy).toHaveBeenCalledWith("/xunzhi/v1/ai-properties", {
      params: { current: 2, size: 10, isEnabled: 1 },
    });
  });
});
