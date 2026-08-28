import { act, renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ROUTES } from "@/lib/constants";
import { useHomePageController } from "@/hooks/home/useHomePageController";
import { useSidebarFooterController } from "@/hooks/layout/useSidebarFooterController";
import type { ChatMessage } from "@/lib/chat";
import chatReducer from "@/store/slices/chatSlice";
import userReducer from "@/store/slices/userSlice";

const navigateMock = vi.fn();
const authLogoutMock = vi.fn();

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

vi.mock("@/hooks/useAiModelsQuery", () => ({
  useAiModelsQuery: () => ({
    models: [
      {
        id: 55,
        aiName: "Model 55",
      },
    ],
  }),
}));

vi.mock("@/services/authService", () => ({
  authService: {
    logout: () => authLogoutMock(),
    login: vi.fn(),
    checkLogin: vi.fn(),
  },
}));

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
        messages: [
          {
            id: "chat-1",
            role: "user",
            content: "stale chat",
            timestamp: 1,
            status: "done",
          },
        ] as ChatMessage[],
        isStreaming: false,
        error: null,
        currentSessionId: "session-1",
        currentSessionTitle: "Session 1",
        pendingOutbound: null,
        activeStreamRequestId: null,
        activeStreamSessionId: null,
        activeStreamMessageId: null,
      },
    },
  });

const renderWithStore = <T,>(callback: () => T) => {
  const store = createStore();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

  const rendered = renderHook(callback, {
    wrapper,
  });

  return {
    ...rendered,
    store,
  };
};

describe("chat runtime reset entrypoints", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authLogoutMock.mockResolvedValue(undefined);
  });

  it("resets the chat runtime before navigating from HomePage", async () => {
    const { result, store } = renderWithStore(() => useHomePageController());

    act(() => {
      result.current.setQuery("new topic");
    });

    await act(async () => {
      await result.current.handleSend();
    });

    expect(store.getState().chat.currentSessionId).toBeNull();
    expect(store.getState().chat.messages).toHaveLength(0);
    expect(navigateMock).toHaveBeenCalledWith(ROUTES.chat, {
      state: {
        model: {
          id: 55,
          aiName: "Model 55",
        },
        initialQuery: "new topic",
      },
    });
  });

  it("resets the chat runtime after logout before navigating to auth", async () => {
    const { result, store } = renderWithStore(() =>
      useSidebarFooterController(),
    );

    await act(async () => {
      await result.current.handleLogout();
    });

    expect(store.getState().chat.currentSessionId).toBeNull();
    expect(store.getState().chat.messages).toHaveLength(0);
    expect(navigateMock).toHaveBeenCalledWith(ROUTES.auth);
  });
});
