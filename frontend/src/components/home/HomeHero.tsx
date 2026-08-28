import { useAppSelector } from "@/store/hooks";
import { useMemo } from "react";

export default function HomeHero() {
  const { currentUser } = useAppSelector((state) => state.user);

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 6) return "凌晨好";
    if (hour < 12) return "早上好";
    if (hour < 18) return "下午好";
    return "晚上好";
  }, []); // 仅在挂载时计算，或者可以不加依赖每次渲染计算（因为很轻量）

  return (
    <div className="flex flex-col items-start gap-2 mb-2 w-full px-2">
      <div className="flex items-center gap-2">
        <span className="text-4xl font-semibold text-transparent bg-clip-text bg-gradient-to-r from-slate-900 to-slate-700">
          {greeting}, {currentUser?.username || "用户"}
        </span>
      </div>
      <span className="text-4xl font-semibold text-slate-300">聊点什么？</span>
    </div>
  );
}
