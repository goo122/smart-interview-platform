import { Link } from "react-router-dom";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";

type SidebarGuestEntryProps = {
  isCollapsed?: boolean;
};

export default function SidebarGuestEntry({
  isCollapsed,
}: SidebarGuestEntryProps) {
  return (
    <Link to={ROUTES.auth} className="block">
      <div
        className={cn(
          "flex items-center p-2 rounded-lg transition-colors hover:bg-slate-100",
          isCollapsed ? "justify-center" : "gap-3",
        )}
      >
        <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs font-medium">
          ME
        </div>
        {!isCollapsed ? (
          <div className="flex-1 overflow-hidden">
            <p className="text-sm font-medium text-slate-700">登录 / 注册</p>
          </div>
        ) : null}
      </div>
    </Link>
  );
}
