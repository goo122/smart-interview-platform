import { render, screen } from "@testing-library/react";
import { Outlet, RouterProvider, createMemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { appRoutes } from "@/app/router";

vi.mock("@/layouts/AppLayout", () => ({
  default: function MockAppLayout() {
    return (
      <div data-testid="app-layout">
        <Outlet />
      </div>
    );
  },
}));

vi.mock("@/components/auth/AuthGuard", () => ({
  default: function MockAuthGuard() {
    return <Outlet />;
  },
}));

vi.mock("@/pages/marketing/MarketingHomePage", () => ({
  default: function MockMarketingHomePage() {
    return <div>marketing-home-page</div>;
  },
}));

vi.mock("@/pages/auth/AuthPage", () => ({
  default: function MockAuthPage() {
    return <div>auth-page</div>;
  },
}));

vi.mock("@/pages/chat/ChatPage", () => ({
  default: function MockChatPage() {
    return <div>chat-page</div>;
  },
}));

vi.mock("@/pages/interview/InterviewIntroPage", () => ({
  default: function MockInterviewIntroPage() {
    return <div>interview-intro-page</div>;
  },
}));

vi.mock("@/pages/interview/InterviewPage", () => ({
  default: function MockInterviewPage() {
    return <div>interview-page</div>;
  },
}));

vi.mock("@/pages/interview/InterviewReportPage", () => ({
  default: function MockInterviewReportPage() {
    return <div>interview-report-page</div>;
  },
}));

describe("appRoutes", () => {
  it("loads the marketing home route lazily", async () => {
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ["/"],
    });

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("marketing-home-page")).toBeDefined();
    expect(screen.getByTestId("app-layout")).toBeDefined();
  });

  it("loads the auth route lazily", async () => {
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ["/auth"],
    });

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("auth-page")).toBeDefined();
    expect(screen.getByTestId("app-layout")).toBeDefined();
  });

  it("loads authenticated chat routes lazily", async () => {
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ["/chat/session-1"],
    });

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("chat-page")).toBeDefined();
  });
});
