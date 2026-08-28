import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useChatTtsAudioElement } from "@/hooks/audio/useChatTtsAudioElement";

describe("useChatTtsAudioElement", () => {
  it("keeps a stable API object across rerenders", () => {
    const onPlaybackEnded = vi.fn();
    const { result, rerender } = renderHook(
      ({ nextHandler }) =>
        useChatTtsAudioElement({
          onPlaybackEnded: nextHandler,
        }),
      {
        initialProps: {
          nextHandler: onPlaybackEnded,
        },
      },
    );

    const firstValue = result.current;

    rerender({
      nextHandler: onPlaybackEnded,
    });

    expect(result.current).toBe(firstValue);
  });
});
