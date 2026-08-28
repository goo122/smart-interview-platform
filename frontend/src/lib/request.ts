import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
} from "axios";
import { resolveAppEnv } from "@/config/env";
import {
  AppError,
  ErrorCode,
  type ErrorCode as ErrorCodeValue,
} from "@/lib/errors";
import { getAuthToken } from "@/lib/authToken";

export interface BaseResponse<T = unknown> {
  code: string;
  message: string | null;
  data: T;
  requestId: string | null;
  success: boolean;
}

export type ApiResponse<T = unknown> = BaseResponse<T>;

export type RequestDedupeStrategy =
  | "off"
  | "join"
  | "cancel-previous"
  | "reject";

export type RequestPolicy = {
  key?: string;
  dedupe?: RequestDedupeStrategy;
  debounceMs?: number;
};

export type AppRequestConfig<D = unknown> = AxiosRequestConfig<D> & {
  requestPolicy?: RequestPolicy;
};

export interface HttpClient {
  get<T>(url: string, config?: AppRequestConfig): Promise<T>;
  delete<T>(url: string, config?: AppRequestConfig): Promise<T>;
  post<T, D = unknown>(
    url: string,
    data?: D,
    config?: AppRequestConfig<D>,
  ): Promise<T>;
  put<T, D = unknown>(
    url: string,
    data?: D,
    config?: AppRequestConfig<D>,
  ): Promise<T>;
  patch<T, D = unknown>(
    url: string,
    data?: D,
    config?: AppRequestConfig<D>,
  ): Promise<T>;
}

export const getApiBaseUrl = () => resolveAppEnv().apiBaseUrl;

const AUTH_FREE_API_PATHS = new Set([
  "/xunzhi/v1/users/login",
  "/xunzhi/v1/users/register",
  "/xunzhi/v1/users/check-login",
  "/v1/auth/login",
  "/v1/auth/register",
  "/v1/auth/refresh",
]);

const trimQueryAndHash = (path: string) => {
  const queryIndex = path.indexOf("?");
  const hashIndex = path.indexOf("#");
  const stopIndexes = [queryIndex, hashIndex].filter((index) => index >= 0);
  if (stopIndexes.length === 0) {
    return path;
  }
  return path.slice(0, Math.min(...stopIndexes));
};

const normalizeRequestPath = (url?: string) => {
  if (!url) {
    return "";
  }

  if (url.startsWith("http://") || url.startsWith("https://")) {
    try {
      const parsed = new URL(url);
      return trimQueryAndHash(parsed.pathname || "");
    } catch {
      return "";
    }
  }

  const baseUrl = getApiBaseUrl();
  const normalizedRelative = url.startsWith("/") ? url : `/${url}`;
  if (normalizedRelative.startsWith(baseUrl)) {
    return trimQueryAndHash(normalizedRelative.slice(baseUrl.length));
  }

  return trimQueryAndHash(normalizedRelative);
};

export const requiresAuthTokenForRequest = (url?: string) => {
  const path = normalizeRequestPath(url);
  if (!path.startsWith("/xunzhi/v1/") && !path.startsWith("/v1/")) {
    return false;
  }
  return !AUTH_FREE_API_PATHS.has(path);
};

export const assertRequestAuthorized = (url: string | undefined) => {
  const token = getAuthToken();
  if (requiresAuthTokenForRequest(url) && !token) {
    throw new AppError(
      ErrorCode.UNAUTHORIZED,
      "Unauthorized. Please sign in again.",
    );
  }
  return token;
};

export const buildApiUrl = (
  path: string,
  query?: Record<string, string | number | boolean | null | undefined>,
) => {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const baseUrl = `${getApiBaseUrl()}${normalizedPath}`;

  if (!query) {
    return baseUrl;
  }

  const searchParams = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    searchParams.set(key, String(value));
  });

  const queryString = searchParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

export const mapBusinessCode = (code: string | undefined): ErrorCodeValue => {
  switch (code) {
    case "401":
      return ErrorCode.UNAUTHORIZED;
    case "403":
      return ErrorCode.FORBIDDEN;
    default:
      return ErrorCode.OPERATION_FAILED;
  }
};

export const isBaseResponse = <T>(
  payload: unknown,
): payload is BaseResponse<T> => {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  return "data" in payload && ("code" in payload || "success" in payload);
};

export const unwrapResponseData = <T>(payload: BaseResponse<T> | T): T => {
  if (isBaseResponse<T>(payload)) {
    if (payload.code === "0" || payload.success) {
      return payload.data;
    }

    throw new AppError(
      mapBusinessCode(payload.code),
      payload.message || "Request failed",
      payload,
    );
  }

  return payload;
};

export const unwrapResponse = <T>(
  response: AxiosResponse<BaseResponse<T> | T>,
): T => {
  return unwrapResponseData(response.data);
};

export const mapAxiosErrorToAppError = (error: AxiosError): AppError => {
  if (axios.isCancel(error)) {
    return new AppError(ErrorCode.ABORTED, "Request was cancelled", error);
  }

  if (error.response) {
    switch (error.response.status) {
      case 400:
        return new AppError(
          ErrorCode.INVALID_PARAMS,
          "Invalid request parameters",
          error,
        );
      case 401:
        return new AppError(
          ErrorCode.UNAUTHORIZED,
          "Unauthorized. Please sign in again.",
          error,
        );
      case 403:
        return new AppError(ErrorCode.FORBIDDEN, "Permission denied", error);
      case 404:
        return new AppError(
          ErrorCode.RESOURCE_NOT_FOUND,
          "Requested resource not found",
          error,
        );
      case 500:
        return new AppError(
          ErrorCode.UNKNOWN_ERROR,
          "Internal server error",
          error,
        );
      default:
        return new AppError(
          ErrorCode.UNKNOWN_ERROR,
          `Request failed with status ${error.response.status}`,
          error,
        );
    }
  }

  if (error.code === "ECONNABORTED") {
    return new AppError(ErrorCode.REQUEST_TIMEOUT, "Request timeout", error);
  }

  if (typeof window !== "undefined" && !window.navigator.onLine) {
    return new AppError(
      ErrorCode.NETWORK_ERROR,
      "Network disconnected. Please check your connection.",
      error,
    );
  }

  return new AppError(
    ErrorCode.NETWORK_ERROR,
    error.message || "Network request failed",
    error,
  );
};

const stableSerialize = (
  value: unknown,
  seen = new WeakSet<object>(),
): string => {
  if (value === null || value === undefined) {
    return String(value);
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (value instanceof URLSearchParams) {
    return value.toString();
  }
  if (typeof FormData !== "undefined" && value instanceof FormData) {
    return "[form-data]";
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableSerialize(item, seen)).join(",")}]`;
  }
  if (typeof value === "object") {
    if (seen.has(value as object)) {
      return "[circular]";
    }
    seen.add(value as object);
    const record = value as Record<string, unknown>;
    const serialized = Object.keys(record)
      .sort()
      .map((key) => `${key}:${stableSerialize(record[key], seen)}`)
      .join(",");
    seen.delete(value as object);
    return `{${serialized}}`;
  }
  return String(value);
};

export const buildRequestPolicyKey = (args: {
  method: string;
  url: string;
  params?: unknown;
  data?: unknown;
  explicitKey?: string;
}) => {
  const normalizedExplicitKey = args.explicitKey?.trim();
  if (normalizedExplicitKey) {
    return normalizedExplicitKey;
  }
  const normalizedMethod = args.method.toUpperCase();
  const normalizedPath = normalizeRequestPath(args.url) || args.url;
  const serializedParams = stableSerialize(args.params);
  const serializedData = stableSerialize(args.data);
  return `${normalizedMethod}::${normalizedPath}::params=${serializedParams}::data=${serializedData}`;
};

export const resolveRequestPolicy = (
  method: string,
  requestPolicy?: RequestPolicy,
) => {
  const normalizedMethod = method.trim().toUpperCase();
  const dedupe: RequestDedupeStrategy =
    requestPolicy?.dedupe ?? (normalizedMethod === "GET" ? "join" : "off");
  const debounceMsRaw = requestPolicy?.debounceMs;
  const debounceMs =
    typeof debounceMsRaw === "number" && Number.isFinite(debounceMsRaw)
      ? Math.max(0, Math.floor(debounceMsRaw))
      : 0;

  return {
    dedupe,
    debounceMs,
    key: requestPolicy?.key?.trim() || undefined,
  };
};

type InflightRequestEntry<T = unknown> = {
  controller: AbortController;
  promise: Promise<T>;
};

type DebounceResolver<T> = {
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
};

type DebounceRequestEntry<T = unknown> = {
  timerId: ReturnType<typeof setTimeout> | null;
  run: () => Promise<T>;
  resolvers: DebounceResolver<T>[];
};

const inflightRequestMap = new Map<string, InflightRequestEntry<unknown>>();
const debounceRequestMap = new Map<string, DebounceRequestEntry<unknown>>();

const bindAbortSignal = (
  controller: AbortController,
  signal?: AxiosRequestConfig["signal"],
) => {
  if (!signal) {
    return;
  }
  if (signal.aborted) {
    controller.abort();
    return;
  }
  if (typeof (signal as AbortSignal).addEventListener === "function") {
    (signal as AbortSignal).addEventListener(
      "abort",
      () => controller.abort(),
      {
        once: true,
      },
    );
  }
};

const stripRequestPolicy = <D>(
  config?: AppRequestConfig<D>,
): AxiosRequestConfig<D> => {
  if (!config) {
    return {};
  }
  const axiosConfig = { ...config } as AxiosRequestConfig<D> & {
    requestPolicy?: RequestPolicy;
  };
  delete axiosConfig.requestPolicy;
  return axiosConfig;
};

const withDebounce = <T>(
  requestKey: string,
  debounceMs: number,
  run: () => Promise<T>,
): Promise<T> => {
  if (debounceMs <= 0) {
    return run();
  }

  const existing = debounceRequestMap.get(requestKey) as
    | DebounceRequestEntry<T>
    | undefined;

  if (existing) {
    if (existing.timerId !== null) {
      clearTimeout(existing.timerId);
    }
    existing.run = run;
    return new Promise<T>((resolve, reject) => {
      existing.resolvers.push({ resolve, reject });
      existing.timerId = setTimeout(async () => {
        const active = debounceRequestMap.get(requestKey) as
          | DebounceRequestEntry<T>
          | undefined;
        if (!active) {
          return;
        }
        debounceRequestMap.delete(requestKey);
        try {
          const result = await active.run();
          active.resolvers.forEach((entry) => entry.resolve(result));
        } catch (error) {
          active.resolvers.forEach((entry) => entry.reject(error));
        }
      }, debounceMs);
    });
  }

  const created: DebounceRequestEntry<T> = {
    timerId: null,
    run,
    resolvers: [],
  };
  debounceRequestMap.set(requestKey, created as DebounceRequestEntry<unknown>);

  return new Promise<T>((resolve, reject) => {
    created.resolvers.push({ resolve, reject });
    created.timerId = setTimeout(async () => {
      const active = debounceRequestMap.get(requestKey) as
        | DebounceRequestEntry<T>
        | undefined;
      if (!active) {
        return;
      }
      debounceRequestMap.delete(requestKey);
      try {
        const result = await active.run();
        active.resolvers.forEach((entry) => entry.resolve(result));
      } catch (error) {
        active.resolvers.forEach((entry) => entry.reject(error));
      }
    }, debounceMs);
  });
};

const withInflightDedup = <T, D>(args: {
  requestKey: string;
  dedupe: RequestDedupeStrategy;
  config?: AxiosRequestConfig<D>;
  run: (config: AxiosRequestConfig<D>) => Promise<T>;
}) => {
  const existing = inflightRequestMap.get(args.requestKey) as
    | InflightRequestEntry<T>
    | undefined;

  if (existing) {
    if (args.dedupe === "join") {
      return existing.promise;
    }
    if (args.dedupe === "reject") {
      throw new AppError(
        ErrorCode.OPERATION_FAILED,
        "Duplicate request is in progress, please retry later.",
      );
    }
    if (args.dedupe === "cancel-previous") {
      existing.controller.abort();
    }
  }

  const controller = new AbortController();
  bindAbortSignal(controller, args.config?.signal);
  const mergedConfig: AxiosRequestConfig<D> = {
    ...(args.config ?? {}),
    signal: controller.signal,
  };

  const promise = args.run(mergedConfig).finally(() => {
    const active = inflightRequestMap.get(args.requestKey);
    if (active?.promise === promise) {
      inflightRequestMap.delete(args.requestKey);
    }
  });

  if (args.dedupe !== "off") {
    inflightRequestMap.set(args.requestKey, {
      controller,
      promise,
    } as InflightRequestEntry<unknown>);
  }

  return promise;
};

export const createAxiosClient = (): AxiosInstance => {
  return axios.create({
    baseURL: getApiBaseUrl(),
    timeout: 10_000,
    headers: {
      "Content-Type": "application/json;charset=utf-8",
    },
  });
};

const axiosInstance = createAxiosClient();

axiosInstance.interceptors.request.use(
  (config) => {
    const token = assertRequestAuthorized(config.url);

    if (token) {
      const headers = new AxiosHeaders(config.headers);
      headers.set("Authorization", `Bearer ${token}`);
      config.headers = headers;
    }

    return config;
  },
  (error) =>
    Promise.reject(
      new AppError(ErrorCode.UNKNOWN_ERROR, "Failed to send request", error),
    ),
);

axiosInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => Promise.reject(mapAxiosErrorToAppError(error)),
);

const executeWithPolicy = <T, D>(args: {
  method: "GET" | "DELETE" | "POST" | "PUT" | "PATCH";
  url: string;
  data?: D;
  config?: AppRequestConfig<D>;
  run: (config: AxiosRequestConfig<D>) => Promise<T>;
}) => {
  const policy = resolveRequestPolicy(args.method, args.config?.requestPolicy);
  const requestKey = buildRequestPolicyKey({
    method: args.method,
    url: args.url,
    params: args.config?.params,
    data: args.data,
    explicitKey: policy.key,
  });
  const axiosConfig = stripRequestPolicy(args.config);

  const runWithDedupe = () =>
    withInflightDedup({
      requestKey,
      dedupe: policy.dedupe,
      config: axiosConfig,
      run: args.run,
    });

  return withDebounce(requestKey, policy.debounceMs, runWithDedupe);
};

const service: HttpClient = {
  async get<T>(url: string, config?: AppRequestConfig) {
    return executeWithPolicy<T, unknown>({
      method: "GET",
      url,
      config,
      run: async (axiosConfig) => {
        const response = await axiosInstance.get<BaseResponse<T> | T>(
          url,
          axiosConfig,
        );
        return unwrapResponse(response);
      },
    });
  },
  async delete<T>(url: string, config?: AppRequestConfig) {
    return executeWithPolicy<T, unknown>({
      method: "DELETE",
      url,
      config,
      run: async (axiosConfig) => {
        const response = await axiosInstance.delete<BaseResponse<T> | T>(
          url,
          axiosConfig,
        );
        return unwrapResponse(response);
      },
    });
  },
  async post<T, D = unknown>(
    url: string,
    data?: D,
    config?: AppRequestConfig<D>,
  ) {
    return executeWithPolicy<T, D>({
      method: "POST",
      url,
      data,
      config,
      run: async (axiosConfig) => {
        const response = await axiosInstance.post<BaseResponse<T> | T>(
          url,
          data,
          axiosConfig,
        );
        return unwrapResponse(response);
      },
    });
  },
  async put<T, D = unknown>(
    url: string,
    data?: D,
    config?: AppRequestConfig<D>,
  ) {
    return executeWithPolicy<T, D>({
      method: "PUT",
      url,
      data,
      config,
      run: async (axiosConfig) => {
        const response = await axiosInstance.put<BaseResponse<T> | T>(
          url,
          data,
          axiosConfig,
        );
        return unwrapResponse(response);
      },
    });
  },
  async patch<T, D = unknown>(
    url: string,
    data?: D,
    config?: AppRequestConfig<D>,
  ) {
    return executeWithPolicy<T, D>({
      method: "PATCH",
      url,
      data,
      config,
      run: async (axiosConfig) => {
        const response = await axiosInstance.patch<BaseResponse<T> | T>(
          url,
          data,
          axiosConfig,
        );
        return unwrapResponse(response);
      },
    });
  },
};

export default service;
