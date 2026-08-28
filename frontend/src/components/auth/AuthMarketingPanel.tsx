import { CheckCircle2 } from "lucide-react";
import { APP_BRAND_NAME, APP_MARKETING_TAGLINE } from "@/lib/branding";

const highlights = [
  "对话记录与资料安全保存",
  "个性化面试与题库推荐",
  "跨设备同步进度",
];

export default function AuthMarketingPanel() {
  return (
    <div className="space-y-6">
      <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
        {APP_BRAND_NAME} · {APP_MARKETING_TAGLINE}
      </div>
      <div className="space-y-3">
        <h1 className="text-4xl font-semibold tracking-tight text-slate-900">
          登录后开启高效 AI 面试体验
        </h1>
        <p className="text-lg text-slate-500">
          一站式管理面试准备、题库练习与智能对话，始终保持专注与高效。
        </p>
      </div>
      <div className="space-y-3">
        {highlights.map((item) => (
          <div
            key={item}
            className="flex items-center gap-3 text-sm text-slate-600"
          >
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
