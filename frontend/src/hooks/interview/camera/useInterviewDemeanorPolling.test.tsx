import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useInterviewDemeanorPolling } from "@/hooks/interview/camera/useInterviewDemeanorPolling";

const mocks = vi.hoisted(() => ({
  getCapabilities: vi.fn(),
  evaluate: vi.fn(),
}));

vi.mock("@/services/interviewService", () => ({
  interviewService: {
    getInterviewDemeanorCapabilities: (...args: unknown[]) =>
      mocks.getCapabilities(...args),
    evaluateInterviewDemeanor: (...args: unknown[]) => mocks.evaluate(...args),
  },
}));

const renderPolling = (
  enabled = true,
  sessionId: string | null = "session-1",
  captureFrame: () => Promise<Blob | null> = async () =>
    new Blob(["frame"], { type: "image/jpeg" }),
) =>
  renderHook(() =>
    useInterviewDemeanorPolling({
      sessionId,
      enabled,
      captureFrame,
    }),
  );

describe("useInterviewDemeanorPolling", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    mocks.getCapabilities.mockResolvedValue({
      available: true,
      provider: "fake",
      maxImageBytes: 2_000_000,
      maxPixels: 8_000_000,
      minIntervalSeconds: 5,
      analysisVersion: "demeanor-v1",
    });
    mocks.evaluate.mockResolvedValue({
      overallScore: 80,
      dimensions: {
        eyeContact: 80,
        posture: 80,
        facialVisibility: 80,
        expressionNaturalness: 80,
      },
      summary: "ok",
      suggestions: ["保持稳定"],
      confidence: 80,
      provider: "fake",
      analysisVersion: "demeanor-v1",
      capturedAt: "2026-08-31T00:00:00Z",
    });
  });

  it("does not upload frames when the backend capability is unavailable", async () => {
    mocks.getCapabilities.mockResolvedValueOnce({
      available: false,
      provider: "unavailable",
      maxImageBytes: 2_000_000,
      maxPixels: 8_000_000,
      minIntervalSeconds: 5,
      analysisVersion: "demeanor-v1",
    });

    renderPolling();

    await waitFor(() => expect(mocks.getCapabilities).toHaveBeenCalledOnce());
    expect(mocks.evaluate).not.toHaveBeenCalled();
  });

  it("exposes the latest structured evaluation to the camera overlay", async () => {
    const { result } = renderPolling();

    await waitFor(() => expect(result.current.status).toBe("completed"));

    expect(result.current.latestEvaluation?.overallScore).toBe(80);
    expect(result.current.latestEvaluation?.suggestions).toEqual(["保持稳定"]);
  });

  it("does not query or capture while the camera or session is disabled", async () => {
    renderPolling(false);
    renderPolling(true, null);

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mocks.getCapabilities).not.toHaveBeenCalled();
    expect(mocks.evaluate).not.toHaveBeenCalled();
  });

  it("prevents overlapping uploads while a frame is being analyzed", async () => {
    vi.useFakeTimers();
    let resolveEvaluation: (() => void) | undefined;
    mocks.evaluate.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveEvaluation = resolve;
        }),
    );

    renderPolling();

    await act(async () => {
      await Promise.resolve();
    });
    expect(mocks.evaluate).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await Promise.resolve();
    });
    expect(mocks.evaluate).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveEvaluation?.();
      await Promise.resolve();
    });
  });

  it("stops uploading after the backend reports the provider is unavailable", async () => {
    vi.useFakeTimers();
    const unavailable = new Error("demeanor unavailable") as Error & {
      originalError: { response: { status: number } };
    };
    unavailable.originalError = { response: { status: 503 } };
    mocks.evaluate.mockRejectedValueOnce(unavailable);

    renderPolling();

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mocks.evaluate).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(15_000);
      await Promise.resolve();
    });
    expect(mocks.evaluate).toHaveBeenCalledTimes(1);
  });

  it("stops the polling timer when the page is unmounted", async () => {
    vi.useFakeTimers();
    const { unmount } = renderPolling();

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mocks.evaluate).toHaveBeenCalledTimes(1);

    unmount();
    await act(async () => {
      vi.advanceTimersByTime(15_000);
      await Promise.resolve();
    });
    expect(mocks.evaluate).toHaveBeenCalledTimes(1);
  });
});
