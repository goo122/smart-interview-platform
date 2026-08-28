import { LogOut, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

type SidebarUserMenuProps = {
  isCollapsed?: boolean;
  avatar?: string | null;
  username?: string | null;
  mail?: string | null;
  phone?: string | null;
  userInitials: string;
  onLogout: () => void;
};

export default function SidebarUserMenu({
  isCollapsed,
  avatar,
  username,
  mail,
  phone,
  userInitials,
  onLogout,
}: SidebarUserMenuProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className={cn(
            "w-full flex items-center p-2 rounded-lg transition-colors hover:bg-slate-100 outline-none",
            isCollapsed ? "justify-center" : "gap-3",
          )}
        >
          <Avatar className="h-8 w-8 border border-slate-200">
            <AvatarImage src={avatar || undefined} />
            <AvatarFallback className="bg-indigo-600 text-white text-xs font-medium">
              {userInitials}
            </AvatarFallback>
          </Avatar>
          {!isCollapsed ? (
            <div className="flex-1 text-left overflow-hidden">
              <p className="text-sm font-medium truncate text-slate-900">
                {username || "用户"}
              </p>
              <p className="text-xs truncate text-slate-500">
                {mail || phone || "已登录"}
              </p>
            </div>
          ) : null}
        </button>
      </PopoverTrigger>

      <PopoverContent
        className="w-60 p-2 mb-2"
        side={isCollapsed ? "right" : "top"}
        align={isCollapsed ? "end" : "center"}
        sideOffset={isCollapsed ? 20 : 10}
      >
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3 p-2 rounded-md bg-slate-50 mb-1">
            <Avatar className="h-10 w-10 border border-slate-200">
              <AvatarImage src={avatar || undefined} />
              <AvatarFallback className="bg-indigo-600 text-white font-medium">
                {userInitials}
              </AvatarFallback>
            </Avatar>
            <div className="overflow-hidden flex-1">
              <p className="text-sm font-medium truncate text-slate-900">
                {username || "用户"}
              </p>
              <p className="text-xs truncate text-slate-500">{mail || phone}</p>
            </div>
          </div>

          <Button
            variant="ghost"
            className="justify-start h-9 px-2 text-sm font-normal w-full"
          >
            <User className="mr-2 h-4 w-4" />
            管理账号
          </Button>

          <div className="h-px bg-slate-100 my-1" />

          <Button
            variant="ghost"
            className="justify-start h-9 px-2 text-sm font-normal text-red-600 hover:text-red-700 hover:bg-red-50 w-full"
            onClick={onLogout}
          >
            <LogOut className="mr-2 h-4 w-4" />
            退出登录
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
