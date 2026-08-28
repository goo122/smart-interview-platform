export type AppEnvSource = Partial<
  Record<"VITE_API_BASE_URL" | "VITE_API_TARGET" | "VITE_WS_BASE_URL", string>
>;

export type ResolvedAppEnv = {
  apiBaseUrl: string;
  apiTarget: string;
  wsBaseUrl: string | null;
};

const DEFAULT_API_BASE_URL = "/api";
const DEFAULT_API_TARGET = "http://localhost:8000";

const trimValue = (value?: string | null) => value?.trim() ?? "";

export const normalizeBaseUrl = (value: string) => value.replace(/\/+$/, "");

export const resolveApiBaseUrl = (value?: string | null) => {
  const trimmed = trimValue(value);
  return normalizeBaseUrl(trimmed || DEFAULT_API_BASE_URL);
};

export const resolveApiTarget = (value?: string | null) => {
  const trimmed = trimValue(value);
  return trimmed || DEFAULT_API_TARGET;
};

export const resolveWsBaseUrl = (value?: string | null) => {
  const trimmed = trimValue(value);
  if (!trimmed) {
    return null;
  }
  return normalizeBaseUrl(trimmed);
};

type LocationLike = {
  protocol: string;
  host: string;
};

export const resolveRuntimeWsBaseUrl = (
  location: LocationLike,
  configuredWsBase?: string | null,
) => {
  if (configuredWsBase) {
    return configuredWsBase;
  }
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}`;
};

const getMetaEnvSource = (): AppEnvSource => {
  const meta = import.meta as ImportMeta & { env?: AppEnvSource };
  return meta.env ?? {};
};

export const resolveAppEnv = (source: AppEnvSource = getMetaEnvSource()) => {
  return {
    apiBaseUrl: resolveApiBaseUrl(source.VITE_API_BASE_URL),
    apiTarget: resolveApiTarget(source.VITE_API_TARGET),
    wsBaseUrl: resolveWsBaseUrl(source.VITE_WS_BASE_URL),
  } satisfies ResolvedAppEnv;
};
