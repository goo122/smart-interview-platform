import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MarketingHomePage from "@/pages/marketing/MarketingHomePage";
import { ROUTES } from "@/lib/constants";
import chatReducer from "@/store/slices/chatSlice";
import userReducer from "@/store/slices/userSlice";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

const createStore = (isAuthenticated: boolean) =>
  configureStore({
    reducer: {
      user: userReducer,
      chat: chatReducer,
    },
    preloadedState: {
      user: {
        currentUser: isAuthenticated
          ? {
              id: 1,
              username: "tester",
            }
          : null,
        isAuthenticated,
        loading: false,
        error: null,
        authEpoch: isAuthenticated ? 1 : 0,
      },
      chat: {
        messages: [],
        isStreaming: false,
        error: null,
        currentSessionId: null,
        currentSessionTitle: null,
        pendingOutbound: null,
        activeStreamRequestId: null,
        activeStreamSessionId: null,
        activeStreamMessageId: null,
      },
    },
  });

const renderPage = (isAuthenticated: boolean) => {
  const store = createStore(isAuthenticated);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

  return render(<MarketingHomePage />, { wrapper });
};

describe("MarketingHomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("navigates to interview intro for authenticated users", () => {
    renderPage(true);

    fireEvent.click(screen.getAllByRole("button", { name: "立即体验" })[0]);

    expect(navigateMock).toHaveBeenCalledWith(ROUTES.interviewIntro);
  });

  it("redirects unauthenticated users to auth with interview intro fallback", () => {
    renderPage(false);

    fireEvent.click(screen.getAllByRole("button", { name: "立即体验" })[0]);

    expect(navigateMock).toHaveBeenCalledWith(ROUTES.auth, {
      state: {
        from: {
          pathname: ROUTES.interviewIntro,
        },
      },
    });
  });
});
