import { describe, expect, it } from "vitest";
import {
  createInitialAudioTranscriptionState,
  getMergedAudioTranscription,
  reduceAudioTranscriptionState,
  resolveAudioTranscriptionEvent,
} from "@/lib/audioTranscription";

describe("audio transcription packet handling", () => {
  it("treats transcription packets as replace events", () => {
    expect(
      resolveAudioTranscriptionEvent({
        type: "transcription",
        data: "  partial text  ",
      }),
    ).toEqual({
      kind: "replace",
      text: "partial text",
    });

    expect(
      resolveAudioTranscriptionEvent({
        updateAction: "replace",
        data: "snapshot",
      }),
    ).toEqual({
      kind: "replace",
      text: "snapshot",
    });
  });

  it("treats final packets as archive events", () => {
    expect(
      resolveAudioTranscriptionEvent({
        type: "final",
        data: "  final text  ",
      }),
    ).toEqual({
      kind: "archive",
      text: "final text",
    });

    expect(
      resolveAudioTranscriptionEvent({
        updateAction: "archive",
        data: "result",
      }),
    ).toEqual({
      kind: "archive",
      text: "result",
    });
  });

  it("overwrites live text on replace instead of appending", () => {
    const initialState = createInitialAudioTranscriptionState();
    const firstState = reduceAudioTranscriptionState(initialState, {
      kind: "replace",
      text: "first partial",
    });
    const secondState = reduceAudioTranscriptionState(firstState, {
      kind: "replace",
      text: "second partial",
    });

    expect(secondState.liveText).toBe("second partial");
    expect(secondState.finalText).toBe("");
    expect(getMergedAudioTranscription(secondState)).toBe("second partial");
  });

  it("archives final text and clears live text", () => {
    const initialState = createInitialAudioTranscriptionState();
    const liveState = reduceAudioTranscriptionState(initialState, {
      kind: "replace",
      text: "partial answer",
    });
    const archivedState = reduceAudioTranscriptionState(liveState, {
      kind: "archive",
      text: "final answer",
    });

    expect(archivedState.liveText).toBe("");
    expect(archivedState.finalText).toBe("final answer");
    expect(getMergedAudioTranscription(archivedState)).toBe("final answer");
  });

  it("falls back to live text when archive payload is empty", () => {
    const initialState = createInitialAudioTranscriptionState();
    const liveState = reduceAudioTranscriptionState(initialState, {
      kind: "replace",
      text: "partial answer",
    });
    const archivedState = reduceAudioTranscriptionState(liveState, {
      kind: "archive",
      text: "",
    });

    expect(archivedState.liveText).toBe("");
    expect(archivedState.finalText).toBe("partial answer");
  });

  it("deduplicates repeated final packets", () => {
    const initialState = createInitialAudioTranscriptionState();
    const onceArchived = reduceAudioTranscriptionState(initialState, {
      kind: "archive",
      text: "same final",
    });
    const twiceArchived = reduceAudioTranscriptionState(onceArchived, {
      kind: "archive",
      text: "same final",
    });

    expect(twiceArchived.liveText).toBe("");
    expect(twiceArchived.finalText).toBe("same final");
  });

  it("keeps archived text when the next replace packet is a new segment", () => {
    const initialState = createInitialAudioTranscriptionState();
    const archivedState = reduceAudioTranscriptionState(initialState, {
      kind: "archive",
      text: "first final segment",
    });
    const nextSegmentState = reduceAudioTranscriptionState(archivedState, {
      kind: "replace",
      text: "second segment partial",
    });

    expect(nextSegmentState.finalText).toBe("first final segment");
    expect(nextSegmentState.liveText).toBe("second segment partial");
    expect(getMergedAudioTranscription(nextSegmentState)).toBe(
      "first final segment\n\nsecond segment partial",
    );
  });

  it("ignores empty replace packets instead of clearing captured text", () => {
    const initialState = createInitialAudioTranscriptionState();
    const capturedState = reduceAudioTranscriptionState(initialState, {
      kind: "archive",
      text: "captured final segment",
    });
    const afterEmptyReplace = reduceAudioTranscriptionState(capturedState, {
      kind: "replace",
      text: "   ",
    });

    expect(afterEmptyReplace).toEqual(capturedState);
  });

  it("resets state when transcription session restarts", () => {
    expect(
      resolveAudioTranscriptionEvent({
        type: "transcription_started",
      }),
    ).toEqual({
      kind: "reset",
    });
  });
});
