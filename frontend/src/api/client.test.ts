import { AxiosError, type AxiosAdapter, type AxiosResponse } from "axios";
import { afterEach, describe, expect, it } from "vitest";
import { apiClient, requestData, resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { ApiError } from "@/api/errors";
import { tokenStore } from "@/lib/tokenStore";

const response = <T>(config: Parameters<AxiosAdapter>[0], data: T, status = 200): AxiosResponse<T> => ({
  data,
  status,
  statusText: status === 200 ? "OK" : "Unauthorized",
  headers: {},
  config,
});

const unauthorized = (config: Parameters<AxiosAdapter>[0]) =>
  Promise.reject(
    new AxiosError(
      "Unauthorized",
      "ERR_BAD_REQUEST",
      config,
      undefined,
      response(config, { error: { code: "authentication_failed" } }, 401),
    ),
  );

afterEach(() => {
  tokenStore.clear();
  resetApiClientForTests();
});

describe("api client authentication", () => {
  it("adds the access token and never logs or sends it without a token", async () => {
    tokenStore.setTokens("access-token", "refresh-token");
    let authorization: unknown;
    const adapter: AxiosAdapter = async (config) => {
      authorization = config.headers.Authorization;
      return response(config, { ok: true });
    };
    setApiAdapterForTests(adapter);

    await requestData(apiClient.get("/v1/auth/me"));
    expect(authorization).toBe("Bearer access-token");

    tokenStore.clear();
    await requestData(apiClient.get("/v1/auth/me"));
    expect(authorization).toBeUndefined();
  });

  it("refreshes concurrently-expired requests through one single-flight call", async () => {
    tokenStore.setTokens("expired-access", "refresh-token");
    const attempts = new Map<string, number>();
    let refreshCalls = 0;
    const adapter: AxiosAdapter = async (config) => {
      const url = config.url ?? "";
      if (url.includes("/v1/auth/refresh")) {
        refreshCalls += 1;
        await new Promise((resolve) => setTimeout(resolve, 10));
        return response(config, {
          access_token: "new-access",
          refresh_token: "new-refresh",
          token_type: "bearer",
          expires_in: 1800,
        });
      }
      const count = (attempts.get(url) ?? 0) + 1;
      attempts.set(url, count);
      if (count === 1) return unauthorized(config);
      return response(config, { authorization: config.headers.Authorization });
    };
    setApiAdapterForTests(adapter);

    const [first, second] = await Promise.all([
      requestData(apiClient.get<{ authorization: string }>("/v1/first")),
      requestData(apiClient.get<{ authorization: string }>("/v1/second")),
    ]);

    expect(refreshCalls).toBe(1);
    expect(first.authorization).toBe("Bearer new-access");
    expect(second.authorization).toBe("Bearer new-access");
    expect(tokenStore.getRefreshToken()).toBe("new-refresh");
  });

  it("clears tokens and returns a friendly error when refresh fails", async () => {
    tokenStore.setTokens("expired-access", "revoked-refresh");
    let refreshCalls = 0;
    const adapter: AxiosAdapter = async (config) => {
      if ((config.url ?? "").includes("/v1/auth/refresh")) {
        refreshCalls += 1;
        return unauthorized(config);
      }
      return unauthorized(config);
    };
    setApiAdapterForTests(adapter);

    const request = requestData(apiClient.get("/v1/protected"));
    await expect(request).rejects.toBeInstanceOf(ApiError);
    await expect(request).rejects.toMatchObject({ status: 401, code: "invalid_refresh_token" });
    expect(refreshCalls).toBe(1);
    expect(tokenStore.getAccessToken()).toBeNull();
    expect(tokenStore.getRefreshToken()).toBeNull();
  });

  it("does not attempt refresh when there is no refresh token", async () => {
    let refreshCalls = 0;
    const adapter: AxiosAdapter = async (config) => {
      if ((config.url ?? "").includes("/v1/auth/refresh")) refreshCalls += 1;
      return unauthorized(config);
    };
    setApiAdapterForTests(adapter);

    await expect(requestData(apiClient.get("/v1/protected"))).rejects.toMatchObject({
      status: 401,
      code: "invalid_refresh_token",
    });
    expect(refreshCalls).toBe(0);
  });
});
