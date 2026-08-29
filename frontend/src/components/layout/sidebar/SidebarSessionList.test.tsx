import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SidebarSessionList from "@/components/layout/sidebar/SidebarSessionList";

describe("SidebarSessionList", () => {
  it("shows the server-provided model name instead of Unknown model", () => {
    render(
      <SidebarSessionList
        conversations={[
          {
            sessionId: "session-1",
            username: "tester",
            aiId: 1,
            aiName: "通义千问 qwen-plus",
            title: "简历问答",
            status: 1,
            createTime: "2026-08-29T00:00:00Z",
          },
        ]}
        activePathname="/chat/session-1"
        hasNextPage={false}
        isFetchingNextPage={false}
        onOpenSession={vi.fn()}
      />,
    );

    expect(screen.getByText(/通义千问 qwen-plus/)).toBeTruthy();
    expect(screen.queryByText("Unknown model")).toBeNull();
  });

  it("handles an empty model response without crashing", () => {
    render(
      <SidebarSessionList
        conversations={[]}
        activePathname="/chat"
        hasNextPage={false}
        isFetchingNextPage={false}
        onOpenSession={vi.fn()}
      />,
    );

    expect(screen.getByText("暂无会话记录")).toBeTruthy();
  });
});
