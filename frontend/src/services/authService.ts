import service from "@/lib/request";
import {
  clearAuthToken,
  getRefreshToken,
  setAuthToken,
  setRefreshToken,
} from "@/lib/authToken";
import { AppError, ErrorCode } from "@/lib/errors";
import type {
  ResultBoolean,
  ResultVoid,
  UserActualRespDTO,
  UserLoginReqDTO,
  UserRegisterReqDTO,
  UserRespDTO,
} from "@/types/auth";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const toNumber = (value: unknown): number | undefined => {
  if (typeof value === "number") return Number.isNaN(value) ? undefined : value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? undefined : parsed;
  }
  return undefined;
};

const toString = (value: unknown): string | undefined => {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  return undefined;
};

type FastApiTokenResponse = {
  access_token?: string;
  refresh_token?: string;
};

type FastApiUserResponse = {
  id?: string;
  username?: string;
  email?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
};

const normalizeUser = (raw: unknown): UserRespDTO | null => {
  if (!isRecord(raw)) return null;

  const username = toString(raw.username) || "";
  if (!username) return null;

  return {
    id: toNumber(raw.id),
    username,
    realName: toString(raw.realName ?? raw.real_name),
    phone: toString(raw.phone),
    mail: toString(raw.mail ?? raw.email),
    avatar: toString(raw.avatar),
    deletionTime: toNumber(raw.deletionTime ?? raw.deletion_time),
    createTime: toString(raw.createTime ?? raw.create_time),
    updateTime: toString(raw.updateTime ?? raw.update_time),
    delFlag: toNumber(raw.delFlag ?? raw.del_flag) as 0 | 1 | undefined,
  };
};

export const authService = {
  login: async (data: UserLoginReqDTO) => {
    const payload = await service.post<FastApiTokenResponse>("/v1/auth/login", {
      account: data.username ?? "",
      password: data.password ?? "",
    });
    const token = payload.access_token?.trim() || null;
    const refreshToken = payload.refresh_token?.trim() || null;
    if (token) setAuthToken(token);
    if (refreshToken) setRefreshToken(refreshToken);

    const rawUser = await service.get<FastApiUserResponse>("/v1/auth/me");
    const user = normalizeUser(rawUser);
    if (!user) {
      throw new Error("Login succeeded but user info is missing");
    }
    if (!token) {
      throw new Error("Login succeeded but token is missing");
    }
    return user;
  },

  register: (data: UserRegisterReqDTO) => {
    return service.post<ResultVoid>("/v1/auth/register", {
      username: data.username ?? "",
      email: data.email ?? "",
      password: data.password ?? "",
    });
  },

  checkLogin: async () => {
    const payload = await service.get<FastApiUserResponse>("/v1/auth/me");
    const user = normalizeUser(payload);
    if (!user) {
      throw new AppError(ErrorCode.UNAUTHORIZED, "User is not logged in");
    }
    return user;
  },

  logout: async () => {
    try {
      const refreshToken = getRefreshToken();
      if (!refreshToken) return;
      return await service.post<ResultVoid>("/v1/auth/logout", {
        refresh_token: refreshToken,
      });
    } finally {
      clearAuthToken();
    }
  },

  getUser: (username: string) => {
    return service.get<UserRespDTO>(`/xunzhi/v1/users/${username}`);
  },

  getUserActual: (username: string) => {
    return service.get<UserActualRespDTO>(
      `/xunzhi/v1/users/actual/${username}`,
    );
  },

  hasUsername: (username: string) => {
    return service.get<ResultBoolean>("/xunzhi/v1/users/has-username", {
      params: { username },
    });
  },
};
