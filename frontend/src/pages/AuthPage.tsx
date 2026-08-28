import { useEffect, useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useLocation, useNavigate } from "react-router-dom";
import type { LoginRequest, RegisterRequest } from "@/api/generated";
import { toUserMessage } from "@/api/errors";
import { AuthLoading, useAuth } from "@/features/auth/context";
import {
  loginSchema,
  registerSchema,
  type LoginFormValues,
  type RegisterFormValues,
} from "@/features/auth/schemas";

type AuthMode = "login" | "register";
type LocationState = { from?: { pathname?: string; search?: string; hash?: string } };

const safeReturnPath = (state: unknown) => {
  const from = (state as LocationState | null)?.from;
  if (!from?.pathname || !from.pathname.startsWith("/")) return "/";
  return `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`;
};

export function AuthPage() {
  const { status, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<AuthMode>("login");
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "AUTHENTICATED") navigate(safeReturnPath(location.state), { replace: true });
  }, [location.state, navigate, status]);

  const loginForm = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });
  const registerForm = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) });

  if (status === "UNKNOWN" || status === "REFRESHING") return <AuthLoading />;

  const submitLogin = async (values: LoginFormValues) => {
    setServerError(null);
    try {
      await login(values satisfies LoginRequest);
    } catch (cause) {
      setServerError(toUserMessage(cause));
    }
  };

  const submitRegister = async (values: RegisterFormValues) => {
    setServerError(null);
    try {
      const payload: RegisterRequest = {
        username: values.username,
        email: values.email,
        password: values.password,
      };
      await register(payload);
    } catch (cause) {
      setServerError(toUserMessage(cause));
    }
  };

  const errorFor = (name: string, formErrors: Record<string, { message?: string } | undefined>) =>
    formErrors[name]?.message;

  return (
    <section className="auth-page">
      <div className="auth-marketing">
        <Link to="/" className="brand brand-large">
          <span className="brand-mark">寻</span>
          <span>
            <strong>寻知</strong>
            <small>智能模拟面试</small>
          </span>
        </Link>
        <p className="eyebrow">A QUIET SPACE TO PREPARE</p>
        <h1>把准备变成<br /><em>你的底气。</em></h1>
        <p>登录后继续你的练习，或创建一个账号开启新的准备旅程。</p>
        <div className="auth-points">
          <span>✓</span> 安全保存你的练习记录
          <span>✓</span> 清晰看见每一步进步
        </div>
      </div>
      <div className="auth-card">
        <div className="auth-tabs" role="tablist" aria-label="认证方式">
          <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "selected" : ""} onClick={() => { setMode("login"); setServerError(null); }}>
            登录
          </button>
          <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "selected" : ""} onClick={() => { setMode("register"); setServerError(null); }}>
            注册
          </button>
        </div>
        <div className="auth-heading">
          <h2>{mode === "login" ? "欢迎回来" : "创建你的账号"}</h2>
          <p>{mode === "login" ? "输入账号信息，继续准备。" : "只需要几步，就能开始。"}</p>
        </div>
        {mode === "login" ? (
          <form onSubmit={loginForm.handleSubmit(submitLogin)} noValidate>
            <Field label="邮箱或用户名" name="account" error={errorFor("account", loginForm.formState.errors)}>
              <input {...loginForm.register("account")} autoComplete="username" placeholder="name@example.com" />
            </Field>
            <Field label="密码" name="password" error={errorFor("password", loginForm.formState.errors)}>
              <input {...loginForm.register("password")} type="password" autoComplete="current-password" placeholder="请输入密码" />
            </Field>
            <AuthError message={serverError} />
            <button className="button button-primary submit-button" type="submit" disabled={loginForm.formState.isSubmitting}>
              {loginForm.formState.isSubmitting ? "登录中…" : "登录进入"}
            </button>
          </form>
        ) : (
          <form onSubmit={registerForm.handleSubmit(submitRegister)} noValidate>
            <Field label="用户名" name="username" error={errorFor("username", registerForm.formState.errors)}>
              <input {...registerForm.register("username")} autoComplete="username" placeholder="至少 3 个字符" />
            </Field>
            <Field label="邮箱" name="email" error={errorFor("email", registerForm.formState.errors)}>
              <input {...registerForm.register("email")} type="email" autoComplete="email" placeholder="name@example.com" />
            </Field>
            <Field label="密码" name="password" error={errorFor("password", registerForm.formState.errors)}>
              <input {...registerForm.register("password")} type="password" autoComplete="new-password" placeholder="至少 8 个字符" />
            </Field>
            <Field label="确认密码" name="confirmPassword" error={errorFor("confirmPassword", registerForm.formState.errors)}>
              <input {...registerForm.register("confirmPassword")} type="password" autoComplete="new-password" placeholder="再次输入密码" />
            </Field>
            <AuthError message={serverError} />
            <button className="button button-primary submit-button" type="submit" disabled={registerForm.formState.isSubmitting}>
              {registerForm.formState.isSubmitting ? "创建中…" : "注册并开始"}
            </button>
          </form>
        )}
        <p className="auth-legal">继续即代表你同意服务条款与隐私政策。</p>
      </div>
    </section>
  );
}

function Field({ label, name, error, children }: { label: string; name: string; error?: string; children: ReactNode }) {
  return (
    <label className="form-field" htmlFor={name}>
      <span>{label}</span>
      {children}
      {error ? <small className="field-error">{error}</small> : null}
    </label>
  );
}

function AuthError({ message }: { message: string | null }) {
  return message ? <div className="form-error" role="alert">{message}</div> : null;
}
