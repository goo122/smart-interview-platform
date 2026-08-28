import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/api/auth";
import type { LoginRequest, RegisterRequest, UserResponse } from "@/api/generated";
import { toUserMessage } from "@/api/errors";
import { tokenStore } from "@/lib/tokenStore";

export type AuthStatus = "UNKNOWN" | "AUTHENTICATED" | "UNAUTHENTICATED" | "REFRESHING";

export function AuthLoading() {
  return (
    <div className="loading-screen" role="status" aria-live="polite">
      <span className="spinner" />
      <span>正在恢复登录状态…</span>
    </div>
  );
}

type AuthContextValue = {
  status: AuthStatus;
  user: UserResponse | null;
  error: string | null;
  login: (payload: LoginRequest) => Promise<UserResponse>;
  register: (payload: RegisterRequest) => Promise<UserResponse>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [tokenVersion, setTokenVersion] = useState(0);
  const [actionStatus, setActionStatus] = useState<AuthStatus>("UNKNOWN");
  const [error, setError] = useState<string | null>(null);
  const hasToken = Boolean(tokenStore.getAccessToken());
  const meQuery = useQuery({
    queryKey: ["auth", "me", tokenVersion],
    queryFn: authApi.me,
    enabled: hasToken,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  useEffect(() => {
    if (hasToken && meQuery.isError) tokenStore.clear();
  }, [hasToken, meQuery.isError]);

  const status: AuthStatus = !hasToken
    ? "UNAUTHENTICATED"
    : meQuery.isPending || meQuery.isFetching
      ? "REFRESHING"
      : meQuery.data
        ? "AUTHENTICATED"
        : meQuery.isError
          ? "UNAUTHENTICATED"
          : actionStatus;
  const visibleError = error ?? (meQuery.isError ? toUserMessage(meQuery.error) : null);

  const login = useCallback(async (payload: LoginRequest) => {
    setError(null);
    setActionStatus("REFRESHING");
    try {
      await authApi.login(payload);
      const nextVersion = tokenVersion + 1;
      setTokenVersion(nextVersion);
      const user = await queryClient.fetchQuery({
        queryKey: ["auth", "me", nextVersion],
        queryFn: authApi.me,
        retry: false,
      });
      setActionStatus("AUTHENTICATED");
      return user;
    } catch (cause) {
      tokenStore.clear();
      setActionStatus("UNAUTHENTICATED");
      const message = toUserMessage(cause);
      setError(message);
      throw cause;
    }
  }, [queryClient, tokenVersion]);

  const register = useCallback(async (payload: RegisterRequest) => {
    await authApi.register(payload);
    return login({ account: payload.email, password: payload.password });
  }, [login]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      tokenStore.clear();
      queryClient.clear();
      setTokenVersion((version) => version + 1);
      setActionStatus("UNAUTHENTICATED");
      setError(null);
    }
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: meQuery.data ?? null,
      error: visibleError,
      login,
      register,
      logout,
    }),
    [login, logout, meQuery.data, register, status, visibleError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
