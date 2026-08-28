import type { AxiosAdapter, AxiosResponse } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { apiClient, resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { AuthPage } from "@/pages/AuthPage";
import { AuthProvider } from "@/features/auth/context";
import { tokenStore } from "@/lib/tokenStore";

const user = {
  id: "00000000-0000-0000-0000-000000000001",
  username: "testuser",
  email: "test@example.com",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function response<T>(config: Parameters<AxiosAdapter>[0], data: T): AxiosResponse<T> {
  return { data, status: 200, statusText: "OK", headers: {}, config };
}

afterEach(() => {
  tokenStore.clear();
  resetApiClientForTests();
});

describe("AuthPage", () => {
  it("submits JSON login credentials and navigates after loading the current user", async () => {
    let loginPayload: unknown;
    const adapter: AxiosAdapter = async (config) => {
      if ((config.url ?? "").includes("/v1/auth/login")) {
        loginPayload = JSON.parse(String(config.data));
        return response(config, {
          access_token: "access-token",
          refresh_token: "refresh-token",
          token_type: "bearer",
          expires_in: 1800,
        });
      }
      if ((config.url ?? "").includes("/v1/auth/me")) return response(config, user);
      return response(config, {});
    };
    setApiAdapterForTests(adapter);

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/auth"]}>
            <Routes>
              <Route path="/auth" element={<AuthPage />} />
              <Route path="/" element={<div>home-page</div>} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByPlaceholderText("name@example.com"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("请输入密码"), {
      target: { value: "secure-password" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "登录进入" }));

    await waitFor(() => expect(screen.getByText("home-page")).toBeInTheDocument());
    expect(loginPayload).toEqual({ account: "test@example.com", password: "secure-password" });
    expect(apiClient.defaults.baseURL).toBe("/api");
  });
});
