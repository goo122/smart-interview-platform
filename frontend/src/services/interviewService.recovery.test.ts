import { afterEach, describe, expect, it, vi } from "vitest";
import service from "@/lib/request";
import { AppError, ErrorCode } from "@/lib/errors";
import { interviewService } from "@/services/interviewService";

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("interview recovery from persisted state", () => {
  it("restores a completed session without requesting a nonexistent current turn", async () => {
    vi.spyOn(interviewService, "getInterviewSession").mockResolvedValue({
      status: "COMPLETED",
    } as never);
    const turn = vi
      .spyOn(interviewService, "getCurrentInterviewTurn")
      .mockRejectedValue(
        new AppError(
          ErrorCode.RESOURCE_NOT_FOUND,
          "Current interview turn not found",
        ),
      );
    const legacy = vi
      .spyOn(service, "get")
      .mockRejectedValue(new Error("No legacy endpoint"));
    await expect(
      interviewService.getCurrentQuestion("finished"),
    ).resolves.toMatchObject({
      finished: true,
      isSuccess: true,
      nextQuestion: null,
    });
    expect(turn).not.toHaveBeenCalled();
    expect(legacy).not.toHaveBeenCalled();
  });

  it("waits through evaluation and returns the adjacent follow-up without resubmitting", async () => {
    vi.useFakeTimers();
    vi.spyOn(interviewService, "getInterviewSession").mockResolvedValue({
      status: "IN_PROGRESS",
    } as never);
    const turn = vi
      .spyOn(interviewService, "getCurrentInterviewTurn")
      .mockResolvedValueOnce({
        status: "EVALUATING",
        turnId: "answered",
        question: "Old question",
        sequence: 1,
      } as never)
      .mockResolvedValue({
        status: "WAITING_ANSWER",
        canAnswer: true,
        turnId: "follow-up",
        question: "Explain that choice",
        sequence: 2,
        turnType: "FOLLOW_UP",
        followUpDepth: 1,
      } as never);
    const post = vi.spyOn(service, "post");
    let resolved = false;
    const pending = interviewService
      .getCurrentQuestion("active")
      .then((value) => {
        resolved = true;
        return value;
      });
    await vi.advanceTimersByTimeAsync(0);
    expect(resolved).toBe(false);
    await vi.advanceTimersByTimeAsync(800);
    await expect(pending).resolves.toMatchObject({
      turnId: "follow-up",
      isFollowUp: true,
    });
    expect(turn).toHaveBeenCalledTimes(2);
    expect(post).not.toHaveBeenCalled();
  });

  it.each(["FAILED", "CANCELLED"])(
    "does not expose an answerable question for %s",
    async (status) => {
      vi.spyOn(interviewService, "getInterviewSession").mockResolvedValue({
        status,
      } as never);
      const turn = vi
        .spyOn(interviewService, "getCurrentInterviewTurn")
        .mockResolvedValue({ status: "WAITING_ANSWER" } as never);
      await expect(
        interviewService.getCurrentQuestion("terminal"),
      ).resolves.toMatchObject({
        failed: true,
        isSuccess: false,
        nextQuestion: null,
      });
      expect(turn).not.toHaveBeenCalled();
    },
  );

  it("reports an inaccessible session without trying legacy routes", async () => {
    vi.spyOn(interviewService, "getInterviewSession").mockRejectedValue(
      new AppError(ErrorCode.RESOURCE_NOT_FOUND, "not found"),
    );
    const get = vi.spyOn(service, "get");
    await expect(
      interviewService.getCurrentQuestion("missing"),
    ).rejects.toThrow("面试不存在或无权访问");
    expect(get).not.toHaveBeenCalled();
  });

  it("surfaces a server failure without treating it as a missing turn", async () => {
    vi.spyOn(interviewService, "getInterviewSession").mockResolvedValue({
      status: "IN_PROGRESS",
    } as never);
    const turn = vi
      .spyOn(interviewService, "getCurrentInterviewTurn")
      .mockRejectedValue(
        new AppError(ErrorCode.OPERATION_FAILED, "Server unavailable"),
      );
    await expect(interviewService.getCurrentQuestion("active")).rejects.toThrow(
      "Server unavailable",
    );
    expect(turn).toHaveBeenCalledTimes(1);
  });

  it("waits for prefetch instead of falling back to the retired current-question endpoint", async () => {
    vi.useFakeTimers();
    vi.spyOn(interviewService, "getInterviewSession").mockResolvedValue({
      status: "IN_PROGRESS",
    } as never);
    const turn = vi
      .spyOn(interviewService, "getCurrentInterviewTurn")
      .mockRejectedValueOnce(
        new AppError(ErrorCode.RESOURCE_NOT_FOUND, "not ready"),
      )
      .mockResolvedValue({
        status: "WAITING_ANSWER",
        canAnswer: true,
        turnId: "next",
        sequence: 2,
        question: "Next",
      } as never);
    const pending = interviewService.getCurrentQuestion("active");
    await vi.advanceTimersByTimeAsync(800);
    await expect(pending).resolves.toMatchObject({ turnId: "next" });
    expect(turn).toHaveBeenCalledTimes(2);
  });

  it("stops waiting when a recovering page is left", async () => {
    vi.useFakeTimers();
    vi.spyOn(interviewService, "getInterviewSession").mockResolvedValue({
      status: "IN_PROGRESS",
    } as never);
    const turn = vi
      .spyOn(interviewService, "getCurrentInterviewTurn")
      .mockResolvedValue({ status: "EVALUATING" } as never);
    const controller = new AbortController();
    const pending = interviewService.getCurrentQuestion(
      "active",
      controller.signal,
    );
    const rejected = expect(pending).rejects.toMatchObject({
      name: "AbortError",
    });
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();
    await rejected;
    await vi.advanceTimersByTimeAsync(5000);
    expect(turn).toHaveBeenCalledTimes(1);
  });
});
