import type { AxiosAdapter, AxiosResponse } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { setApiAdapterForTests, resetApiClientForTests } from "@/api/client";
import { AuthGuard } from "@/features/auth/AuthGuard";
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
  return {
    data,
    status: 200,
    statusText: "OK",
    headers: {},
    config,
  };
}

const renderGuard = (initialEntry: string) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/auth" element={<div>auth-page</div>} />
            <Route element={<AuthGuard />}>
              <Route path="/private" element={<div>private-page</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
};

afterEach(() => {
  tokenStore.clear();
  resetApiClientForTests();
});

describe("AuthGuard", () => {
  it("redirects unauthenticated users to the auth page", async () => {
    renderGuard("/private");
    expect(await screen.findByText("auth-page")).toBeInTheDocument();
  });

  it("waits for one current-user request before rendering protected content", async () => {
    tokenStore.setTokens("access-token", "refresh-token");
    let meRequests = 0;
    const adapter: AxiosAdapter = async (config) => {
      if ((config.url ?? "").includes("/v1/auth/me")) meRequests += 1;
      return response(config, user);
    };
    setApiAdapterForTests(adapter);

    renderGuard("/private");
    expect(await screen.findByText("private-page")).toBeInTheDocument();
    expect(meRequests).toBe(1);
  });
});
