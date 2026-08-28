import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { ROUTES } from "@/lib/constants";
import type {
  AuthFormData,
  AuthMode,
} from "@/hooks/auth/useAuthPageController";

type AuthFormCardProps = {
  mode: AuthMode;
  formData: AuthFormData;
  errorMessage: string;
  isSubmitting: boolean;
  onSwitchMode: (mode: AuthMode) => void;
  onInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: () => void;
};

export default function AuthFormCard({
  mode,
  formData,
  errorMessage,
  isSubmitting,
  onSwitchMode,
  onInputChange,
  onSubmit,
}: AuthFormCardProps) {
  const isLogin = mode === "login";

  return (
    <Card className="p-8 border-slate-100 shadow-sm">
      <div className="flex items-center gap-2 rounded-full bg-slate-100 p-1">
        <Button
          type="button"
          variant={isLogin ? "default" : "ghost"}
          className={cn("flex-1 rounded-full", !isLogin && "text-slate-500")}
          onClick={() => onSwitchMode("login")}
        >
          登录
        </Button>
        <Button
          type="button"
          variant={!isLogin ? "default" : "ghost"}
          className={cn("flex-1 rounded-full", isLogin && "text-slate-500")}
          onClick={() => onSwitchMode("register")}
        >
          注册
        </Button>
      </div>

      <div className="mt-6 space-y-4">
        <div className="space-y-2">
          <label className="text-xs text-slate-500">用户名</label>
          <Input
            name="username"
            placeholder="输入你的用户名"
            value={formData.username}
            onChange={onInputChange}
          />
        </div>
        {!isLogin && (
          <div className="space-y-2">
            <label className="text-xs text-slate-500">邮箱</label>
            <Input
              name="email"
              type="email"
              placeholder="输入你的邮箱"
              value={formData.email}
              onChange={onInputChange}
            />
          </div>
        )}
        <div className="space-y-2">
          <label className="text-xs text-slate-500">密码</label>
          <Input
            name="password"
            type="password"
            placeholder="输入密码"
            value={formData.password}
            onChange={onInputChange}
          />
        </div>
        {!isLogin && (
          <div className="space-y-2">
            <label className="text-xs text-slate-500">确认密码</label>
            <Input
              name="confirmPassword"
              type="password"
              placeholder="再次输入密码"
              value={formData.confirmPassword}
              onChange={onInputChange}
            />
          </div>
        )}

        {errorMessage && (
          <div className="text-xs text-red-500 mt-2">{errorMessage}</div>
        )}
      </div>

      <Button
        className="w-full mt-6 rounded-full"
        onClick={onSubmit}
        disabled={isSubmitting}
      >
        {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {isLogin ? "登录进入" : "注册并开始"}
      </Button>

      <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
        <span>登录即代表同意服务条款与隐私政策</span>
        <Link to={ROUTES.home} className="text-slate-500 hover:text-slate-700">
          返回首页
        </Link>
      </div>
    </Card>
  );
}
