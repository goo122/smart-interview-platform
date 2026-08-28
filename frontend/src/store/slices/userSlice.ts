import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { clearAuthToken } from "@/lib/authToken";
import { AppError, ErrorCode } from "@/lib/errors";
import { authService } from "@/services/authService";
import type { UserLoginReqDTO, UserRespDTO } from "@/types/auth";

interface UserState {
  currentUser: UserRespDTO | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
  authEpoch: number;
}

const initialState: UserState = {
  currentUser: null,
  isAuthenticated: false,
  loading: false,
  error: null,
  authEpoch: 0,
};

const getUserIdentityKey = (user: UserRespDTO | null) => {
  if (!user) {
    return "anonymous";
  }
  return `${user.id ?? "none"}:${user.username}`;
};

type AuthStatusRejectValue = {
  message: string;
  shouldClearAuth: boolean;
};

export const loginUser = createAsyncThunk<
  UserRespDTO,
  UserLoginReqDTO,
  { rejectValue: string }
>("user/login", async (data, { rejectWithValue }) => {
  try {
    return await authService.login(data);
  } catch (error: unknown) {
    const errorMessage =
      error instanceof Error ? error.message : "Login failed";
    return rejectWithValue(errorMessage);
  }
});

export const checkAuthStatus = createAsyncThunk<
  UserRespDTO,
  void,
  { rejectValue: AuthStatusRejectValue }
>("user/checkAuth", async (_, { rejectWithValue }) => {
  try {
    return await authService.checkLogin();
  } catch (error: unknown) {
    const appError = AppError.from(error);
    return rejectWithValue({
      message: appError.message || "Failed to check authentication status",
      shouldClearAuth:
        appError.code === ErrorCode.UNAUTHORIZED ||
        appError.code === ErrorCode.FORBIDDEN,
    });
  }
});

export const logoutUser = createAsyncThunk<void, void, { rejectValue: string }>(
  "user/logout",
  async (_, { rejectWithValue }) => {
    try {
      await authService.logout();
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Logout failed";
      return rejectWithValue(errorMessage);
    }
  },
);

export const userSlice = createSlice({
  name: "user",
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loginUser.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(loginUser.fulfilled, (state, action) => {
        state.loading = false;
        state.error = null;
        state.isAuthenticated = true;
        state.currentUser = action.payload;
        state.authEpoch += 1;
      })
      .addCase(loginUser.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? "Login failed";
      })
      .addCase(checkAuthStatus.fulfilled, (state, action) => {
        const prevIdentity = getUserIdentityKey(state.currentUser);
        const nextIdentity = getUserIdentityKey(action.payload);

        state.isAuthenticated = true;
        state.currentUser = action.payload;
        state.error = null;

        if (prevIdentity !== nextIdentity) {
          state.authEpoch += 1;
        }
      })
      .addCase(checkAuthStatus.rejected, (state, action) => {
        state.loading = false;
        state.error =
          action.payload?.message ?? "Failed to check authentication status";

        if (!action.payload?.shouldClearAuth) {
          return;
        }

        clearAuthToken();
        if (state.isAuthenticated || state.currentUser) {
          state.authEpoch += 1;
        }
        state.isAuthenticated = false;
        state.currentUser = null;
      })
      .addCase(logoutUser.fulfilled, (state) => {
        state.isAuthenticated = false;
        state.currentUser = null;
        state.loading = false;
        state.error = null;
        state.authEpoch += 1;
      })
      .addCase(logoutUser.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload ?? "Logout failed";
      });
  },
});

export const { clearError } = userSlice.actions;
export default userSlice.reducer;
