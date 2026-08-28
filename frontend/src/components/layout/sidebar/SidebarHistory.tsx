import { useLocation, useNavigate } from "react-router-dom";
import { SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ROUTES } from "@/lib/constants";
import {
  buildReportSearch,
  getReportSessionIdFromLocation,
} from "@/lib/interviewReportRoute";
import SidebarInterviewList from "@/components/layout/sidebar/SidebarInterviewList";
import SidebarSessionList from "@/components/layout/sidebar/SidebarSessionList";
import { useSidebarHistoryController } from "@/hooks/layout/useSidebarHistoryController";

type SidebarHistoryProps = {
  isCollapsed?: boolean;
};

export default function SidebarHistory({ isCollapsed }: SidebarHistoryProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    view,
    setView,
    conversations,
    interviewRecords,
    hasNextPage,
    hasNextInterviewPage,
    isFetchingNextPage,
    isFetchingNextInterviewPage,
    handleScroll,
  } = useSidebarHistoryController(isCollapsed);

  const activeInterviewSessionId = location.pathname.startsWith(
    ROUTES.interviewReport,
  )
    ? getReportSessionIdFromLocation(location)
    : null;

  if (isCollapsed) {
    return null;
  }

  return (
    <div className="mt-6 flex min-h-0 flex-1 flex-col overflow-hidden px-3">
      <div className="mb-2 flex shrink-0 items-center justify-between px-2 text-xs text-slate-400">
        <span>历史记录</span>
        <SlidersHorizontal className="h-3.5 w-3.5" />
      </div>

      <div className="mb-3 flex shrink-0 items-center gap-2 px-2">
        <Button
          size="sm"
          variant={view === "sessions" ? "secondary" : "ghost"}
          className="h-7 rounded-full text-xs"
          onClick={() => setView("sessions")}
        >
          历史会话
        </Button>
        <Button
          size="sm"
          variant={view === "interviews" ? "secondary" : "ghost"}
          className="h-7 rounded-full text-xs"
          onClick={() => setView("interviews")}
        >
          历史面试
        </Button>
      </div>

      <ScrollArea className="-mx-2 flex-1" onScrollCapture={handleScroll}>
        <div className="space-y-1 px-2 pb-2">
          {view === "sessions" ? (
            <SidebarSessionList
              conversations={conversations}
              activePathname={location.pathname}
              hasNextPage={hasNextPage}
              isFetchingNextPage={isFetchingNextPage}
              onOpenSession={(sessionId) =>
                navigate(`${ROUTES.chat}/${sessionId}`)
              }
            />
          ) : (
            <SidebarInterviewList
              records={interviewRecords}
              activePathname={location.pathname}
              activeSessionId={activeInterviewSessionId}
              hasNextPage={hasNextInterviewPage}
              isFetchingNextPage={isFetchingNextInterviewPage}
              onOpenRecord={(sessionId) =>
                navigate(
                  `${ROUTES.interviewReport}${buildReportSearch(sessionId)}`,
                  {
                    state: { sessionId },
                  },
                )
              }
            />
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
