import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useInterviewUploadStage } from "@/hooks/interview/resume/useInterviewUploadStage";

describe("useInterviewUploadStage", () => {
  it("changes stages only when the preparation flow reports them", () => {
    const { result } = renderHook(() => useInterviewUploadStage());

    act(() => result.current.startUploadStage());
    expect(result.current.resumeUploadStage).toBe(0);

    act(() => result.current.setUploadStage(1));
    expect(result.current.resumeUploadStage).toBe(1);

    act(() => result.current.setUploadStage(2));
    expect(result.current.resumeUploadStage).toBe(2);

    act(() => result.current.finishUploadStage());
    expect(result.current.isResumeUploading).toBe(false);
  });

  it("does not create timer-driven stage changes", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useInterviewUploadStage());

    try {
      act(() => result.current.startUploadStage());
      vi.advanceTimersByTime(1800);
      expect(result.current.resumeUploadStage).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
