const ACCESS_TOKEN_KEY = "xunzhi.access_token";
const REFRESH_TOKEN_KEY = "xunzhi.refresh_token";

const read = (key: string): string | null => {
  try {
    const value = localStorage.getItem(key)?.trim();
    return value || null;
  } catch {
    return null;
  }
};

export const tokenStore = {
  getAccessToken: () => read(ACCESS_TOKEN_KEY),
  getRefreshToken: () => read(REFRESH_TOKEN_KEY),
  setTokens: (accessToken: string, refreshToken: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken.trim());
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken.trim());
  },
  clear: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};
