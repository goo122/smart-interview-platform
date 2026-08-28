import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ROUTES } from "@/lib/constants";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { clearError, loginUser } from "@/store/slices/userSlice";
import { authService } from "@/services/authService";

export type AuthMode = "login" | "register";

export type AuthFormData = {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
};

const initialFormData: AuthFormData = {
  username: "",
  email: "",
  password: "",
  confirmPassword: "",
};

type AuthRedirectState = {
  from?: {
    pathname?: string;
    search?: string;
    hash?: string;
  };
};

const normalizeInAppRedirect = (value: unknown): string | null => {
  if (!value || typeof value !== "object") {
    return null;
  }

  const pathnameValue =
    "pathname" in value && typeof value.pathname === "string"
      ? value.pathname.trim()
      : "";
  if (
    !pathnameValue ||
    !pathnameValue.startsWith("/") ||
    pathnameValue.startsWith("//")
  ) {
    return null;
  }

  const searchValue =
    "search" in value && typeof value.search === "string"
      ? value.search.trim()
      : "";
  const hashValue =
    "hash" in value && typeof value.hash === "string" ? value.hash.trim() : "";

  return `${pathnameValue}${searchValue}${hashValue}`;
};

export function useAuthPageController() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [formData, setFormData] = useState<AuthFormData>(initialFormData);
  const [registerLoading, setRegisterLoading] = useState(false);
  const [localError, setLocalError] = useState("");

  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { loading, error, isAuthenticated } = useAppSelector(
    (state) => state.user,
  );

  useEffect(() => {
    if (isAuthenticated) {
      const redirectState = location.state as AuthRedirectState | null;
      const redirectPath =
        normalizeInAppRedirect(redirectState?.from) ?? ROUTES.home;
      navigate(redirectPath, { replace: true });
    }
    return () => {
      dispatch(clearError());
    };
  }, [isAuthenticated, location.state, navigate, dispatch]);

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setLocalError("");
    dispatch(clearError());
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setLocalError("");
    if (error) {
      dispatch(clearError());
    }
  };

  const handleSubmit = async () => {
    if (!formData.username || !formData.password || (mode === "register" && !formData.email)) {
      setLocalError(mode === "register" ? "请输入用户名、邮箱和密码" : "请输入用户名和密码");
      return;
    }

    if (mode === "login") {
      dispatch(
        loginUser({ username: formData.username, password: formData.password }),
      );
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setLocalError("两次输入的密码不一致");
      return;
    }

    setRegisterLoading(true);
    try {
      await authService.register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
      });
      setMode("login");
      setLocalError("");
      alert("注册成功，请登录");
    } catch (submitError: unknown) {
      const message =
        submitError instanceof Error ? submitError.message : "注册失败";
      setLocalError(message);
    } finally {
      setRegisterLoading(false);
    }
  };

  return {
    mode,
    isLogin: mode === "login",
    formData,
    loading,
    error,
    registerLoading,
    localError,
    switchMode,
    handleInputChange,
    handleSubmit,
  };
}
