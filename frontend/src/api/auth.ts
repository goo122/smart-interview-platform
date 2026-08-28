import { apiClient, requestData } from "@/api/client";
import type {
  LoginRequest,
  MessageResponse,
  RefreshRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
} from "@/api/generated";
import { tokenStore } from "@/lib/tokenStore";

export const authApi = {
  login: async (payload: LoginRequest) => {
    const tokens = await requestData(apiClient.post<TokenResponse>("/v1/auth/login", payload));
    tokenStore.setTokens(tokens.access_token, tokens.refresh_token);
    return tokens;
  },
  register: (payload: RegisterRequest) =>
    requestData(apiClient.post<UserResponse>("/v1/auth/register", payload)),
  refresh: (payload: RefreshRequest) =>
    requestData(apiClient.post<TokenResponse>("/v1/auth/refresh", payload)),
  me: () => requestData(apiClient.get<UserResponse>("/v1/auth/me")),
  logout: async () => {
    const refreshToken = tokenStore.getRefreshToken();
    try {
      if (refreshToken) {
        await requestData(
          apiClient.post<MessageResponse>("/v1/auth/logout", {
            refresh_token: refreshToken,
          }),
        );
      }
    } finally {
      tokenStore.clear();
    }
  },
};
