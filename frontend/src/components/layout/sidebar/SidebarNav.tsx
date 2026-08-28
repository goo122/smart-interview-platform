import { Link, useLocation } from "react-router-dom";
import { MessageSquare, Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";

type SidebarNavProps = {
  isCollapsed?: boolean;
};

export default function SidebarNav({ isCollapsed }: SidebarNavProps) {
  const location = useLocation();
  const isActive = (path: string) =>
    path === ROUTES.chat
      ? location.pathname === ROUTES.chat ||
        location.pathname.startsWith(`${ROUTES.chat}/`)
      : location.pathname === path;

  return (
    <div className="px-3">
      <div className="space-y-1">
        <Link to={ROUTES.chat}>
          <Button
            variant={isActive(ROUTES.chat) ? "secondary" : "ghost"}
            className={cn(
              "w-full rounded-full",
              isCollapsed ? "justify-center" : "justify-start",
            )}
          >
            <MessageSquare className={cn("h-4 w-4", !isCollapsed && "mr-2")} />
            {!isCollapsed && "新对话"}
          </Button>
        </Link>

        <Link to={ROUTES.interviewIntro}>
          <Button
            variant={isActive(ROUTES.interviewIntro) ? "secondary" : "ghost"}
            className={cn(
              "w-full rounded-full",
              isCollapsed ? "justify-center" : "justify-start",
            )}
          >
            <Video className={cn("h-4 w-4", !isCollapsed && "mr-2")} />
            {!isCollapsed && "AI 面试"}
          </Button>
        </Link>
      </div>
    </div>
  );
}
