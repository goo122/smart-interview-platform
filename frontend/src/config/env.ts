const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "") || "/";

export const frontendEnv = {
  apiBaseUrl: trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || "/api"),
  apiTarget: import.meta.env.VITE_API_TARGET || "http://localhost:8000",
} as const;
