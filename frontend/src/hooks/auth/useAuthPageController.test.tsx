import { renderHook, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ROUTES } from "@/lib/constants";
import { useAuthPageController } from "@/hooks/auth/useAuthPageController";
import chatReducer from "@/store/slices/chatSlice";
import userReducer from "@/store/slices/userSlice";

const navigateMock = vi.fn();
const useLocationMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useLocation: () => useLocationMock(),
  };
});

const createStore = () =>
  configureStore({
    reducer: {
      user: userReducer,
      chat: chatReducer,
    },
    preloadedState: {
      user: {
        currentUser: {
          id: 1,
          username: "tester",
        },
        isAuthenticated: true,
        loading: false,
        error: null,
        authEpoch: 1,
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

const renderController = () => {
  const store = createStore();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

  return renderHook(() => useAuthPageController(), { wrapper });
};

describe("useAuthPageController redirect", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects to the in-app from path after login", async () => {
    useLocationMock.mockReturnValue({
      state: {
        from: {
          pathname: ROUTES.interviewRoom,
        },
      },
    });

    renderController();

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith(ROUTES.interviewRoom, {
        replace: true,
      });
    });
  });

  it("falls back to / when from path is unsafe", async () => {
    useLocationMock.mockReturnValue({
      state: {
        from: {
          pathname: "https://example.com",
        },
      },
    });

    renderController();

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith(ROUTES.home, {
        replace: true,
      });
    });
  });
});
