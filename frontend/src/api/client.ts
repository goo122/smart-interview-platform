import axios, {
  AxiosError,
  type AxiosAdapter,
  type InternalAxiosRequestConfig,
} from "axios";
import { apiErrorFromResponse } from "@/api/errors";
import { frontendEnv } from "@/config/env";
import { tokenStore } from "@/lib/tokenStore";
import type { RefreshRequest, TokenResponse } from "@/api/generated";

type AuthRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
  _skipAuthRefresh?: boolean;
};

export const apiClient = axios.create({
  baseURL: frontendEnv.apiBaseUrl,
  timeout: 15000,
  headers: { Accept: "application/json" },
});

const refreshClient = axios.create({
  baseURL: frontendEnv.apiBaseUrl,
  timeout: 10000,
  headers: { Accept: "application/json" },
});

let refreshPromise: Promise<string | null> | null = null;

const shouldSkipRefresh = (config: AuthRequestConfig) =>
  ["/auth/login", "/auth/register", "/auth/refresh"].some((path) => config.url?.includes(path)) ||
  config._skipAuthRefresh;

const isPublicAuthRequest = (config: InternalAxiosRequestConfig) =>
  ["/auth/login", "/auth/register", "/auth/refresh"].some((path) => config.url?.includes(path));

const refreshAccessToken = async (): Promise<string | null> => {
  const refreshToken = tokenStore.getRefreshToken();
  if (!refreshToken) return null;

  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const payload: RefreshRequest = { refresh_token: refreshToken };
        const response = await refreshClient.post<TokenResponse>(
          "/v1/auth/refresh",
          payload,
        );
        tokenStore.setTokens(response.data.access_token, response.data.refresh_token);
        return response.data.access_token;
      } catch {
        tokenStore.clear();
        return null;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
};

apiClient.interceptors.request.use((config) => {
  const token = tokenStore.getAccessToken();
  if (token && !config.headers.Authorization && !isPublicAuthRequest(config)) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<unknown>) => {
    const config = error.config as AuthRequestConfig | undefined;
    if (!config || error.response?.status !== 401 || config._retry || shouldSkipRefresh(config)) {
      if (error.response) {
        return Promise.reject(apiErrorFromResponse(error.response.status, error.response.data));
      }
      return Promise.reject(error);
    }

    config._retry = true;
    const accessToken = await refreshAccessToken();
    if (!accessToken) {
      return Promise.reject(apiErrorFromResponse(401, { error: { code: "invalid_refresh_token" } }));
    }
    config.headers.Authorization = `Bearer ${accessToken}`;
    return apiClient(config);
  },
);

export const requestData = async <T>(request: Promise<{ data: T }>): Promise<T> =>
  (await request).data;

export const resetApiClientForTests = () => {
  refreshPromise = null;
  apiClient.defaults.adapter = undefined;
  refreshClient.defaults.adapter = undefined;
};

export const setApiAdapterForTests = (adapter: AxiosAdapter | undefined) => {
  apiClient.defaults.adapter = adapter;
  refreshClient.defaults.adapter = adapter;
};
