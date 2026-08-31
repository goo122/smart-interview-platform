import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useAudioToTextComposerBridge } from "@/hooks/useAudioToText";

describe("useAudioToTextComposerBridge", () => {
  it("fills the chat input with live snapshots without submitting", () => {
    const onChange = vi.fn();
    const onSend = vi.fn();
    const { rerender } = renderHook(
      ({ isRecording, transcription, value }) =>
        useAudioToTextComposerBridge({
          enabled: true,
          isRecording,
          transcription,
          value,
          onChange,
        }),
      {
        initialProps: {
          isRecording: false,
          transcription: "",
          value: "已有文本",
        },
      },
    );

    rerender({
      isRecording: true,
      transcription: "第一版转写",
      value: "已有文本",
    });

    expect(onChange).toHaveBeenCalledWith("已有文本\n第一版转写");
    expect(onSend).not.toHaveBeenCalled();

    onChange.mockClear();
    rerender({
      isRecording: true,
      transcription: "第一版转写，更新后的完整快照",
      value: "已有文本\n第一版转写",
    });

    expect(onChange).toHaveBeenCalledWith(
      "已有文本\n第一版转写，更新后的完整快照",
    );
  });

  it("flushes a final snapshot that arrives after recording stops", () => {
    const onChange = vi.fn();
    const { rerender } = renderHook(
      ({ isRecording, transcription, value }) =>
        useAudioToTextComposerBridge({
          enabled: true,
          isRecording,
          transcription,
          value,
          onChange,
        }),
      {
        initialProps: {
          isRecording: false,
          transcription: "",
          value: "已有文本",
        },
      },
    );

    rerender({
      isRecording: true,
      transcription: "",
      value: "已有文本",
    });
    rerender({
      isRecording: false,
      transcription: "",
      value: "已有文本",
    });
    rerender({
      isRecording: false,
      transcription: "最后一段转写",
      value: "已有文本",
    });

    expect(onChange).toHaveBeenCalledWith("已有文本\n最后一段转写");
  });
});
