import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ChatBubble from "@/components/chat/ChatBubble";

describe("ChatBubble TTS control", () => {
  it("shows a playback control when TTS is available", () => {
    const onTtsToggle = vi.fn();
    render(
      <ChatBubble
        role="assistant"
        content="请介绍一下你自己。"
        tts={{ text: "请介绍一下你自己。" }}
        onTtsToggle={onTtsToggle}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "播放题目播报" }));
    expect(onTtsToggle).toHaveBeenCalledTimes(1);
  });

  it("hides the playback control when TTS is unavailable", () => {
    render(
      <ChatBubble
        role="assistant"
        content="请介绍一下你自己。"
        tts={{ text: "请介绍一下你自己。" }}
      />,
    );

    expect(screen.queryByRole("button", { name: "播放题目播报" })).toBeNull();
  });

  it("keeps an understandable retry message for autoplay errors", () => {
    render(
      <ChatBubble
        role="assistant"
        content="请介绍一下你自己。"
        tts={{ text: "请介绍一下你自己。" }}
        onTtsToggle={vi.fn()}
        ttsError="浏览器阻止了自动播放，请点击播放按钮重试。"
      />,
    );

    expect(screen.getByRole("status").textContent).toContain("点击播放按钮重试");
  });
});
