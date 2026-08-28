export interface UserLoginReqDTO {
  username?: string;
  password?: string;
}

export interface UserRegisterReqDTO {
  username?: string;
  password?: string;
  email?: string;
  realName?: string;
  phone?: string;
  mail?: string;
}

// Backend table mapping: t_user
export interface UserEntity {
  id?: number;
  username: string;
  password?: string | null;
  realName?: string | null;
  phone?: string | null;
  mail?: string | null;
  deletionTime?: number | null;
  createTime?: string | null;
  updateTime?: string | null;
  delFlag?: 0 | 1 | null;
}

// Frontend-safe DTO (password removed).
export type UserRespDTO = Omit<UserEntity, "password"> & {
  avatar?: string | null;
};

export type UserActualRespDTO = UserRespDTO;
export type ResultVoid = null;
export type ResultBoolean = boolean;

// Login/check-login payload may be wrapped in different keys.
export type AuthPayloadDTO = {
  token?: string;
  user?: unknown;
  currentUser?: unknown;
  [key: string]: unknown;
};
