const AUTH_TOKEN_KEY = "token";
const REFRESH_TOKEN_KEY = "refresh_token";

export const AUTH_SESSION_EXPIRED_EVENT = "xunzhi:auth-session-expired";

export const getAuthToken = (): string | null => {
  try {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) return null;
    const normalized = token.trim();
    return normalized || null;
  } catch {
    return null;
  }
};

export const setAuthToken = (token: string) => {
  const normalized = token.trim();
  if (!normalized) return;
  localStorage.setItem(AUTH_TOKEN_KEY, normalized);
};

export const setRefreshToken = (token: string) => {
  const normalized = token.trim();
  if (!normalized) return;
  localStorage.setItem(REFRESH_TOKEN_KEY, normalized);
};

export const getRefreshToken = (): string | null => {
  try {
    const token = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!token) return null;
    const normalized = token.trim();
    return normalized || null;
  } catch {
    return null;
  }
};

export const clearAuthToken = () => {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

export const notifyAuthSessionExpired = () => {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_EXPIRED_EVENT));
  }
};
