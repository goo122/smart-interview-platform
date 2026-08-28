import { cn } from "@/lib/utils";
import { useSidebarFooterController } from "@/hooks/layout/useSidebarFooterController";
import SidebarGuestEntry from "@/components/layout/sidebar/SidebarGuestEntry";
import SidebarUserMenu from "@/components/layout/sidebar/SidebarUserMenu";

type SidebarFooterProps = {
  isCollapsed?: boolean;
};

export default function SidebarFooter({ isCollapsed }: SidebarFooterProps) {
  const { isAuthenticated, currentUser, userInitials, handleLogout } =
    useSidebarFooterController();

  return (
    <div className={cn("px-2 pb-4 pt-2 border-t border-slate-200 bg-slate-50")}>
      {isAuthenticated ? (
        <SidebarUserMenu
          isCollapsed={isCollapsed}
          avatar={currentUser?.avatar}
          username={currentUser?.username}
          mail={currentUser?.mail}
          phone={currentUser?.phone}
          userInitials={userInitials}
          onLogout={handleLogout}
        />
      ) : (
        <SidebarGuestEntry isCollapsed={isCollapsed} />
      )}
    </div>
  );
}
