import { useCallback, useState, type UIEvent } from "react";
import { useConversations } from "@/hooks/useConversations";
import { useInterviewRecords } from "@/hooks/interview/records/useInterviewRecords";

export type SidebarHistoryView = "sessions" | "interviews";

export function useSidebarHistoryController(isCollapsed?: boolean) {
  const [view, setView] = useState<SidebarHistoryView>("sessions");
  const shouldFetchConversations = !isCollapsed && view === "sessions";
  const shouldFetchInterviewRecords = !isCollapsed && view === "interviews";

  const { conversations, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useConversations({
      enabled: shouldFetchConversations,
    });
  const {
    interviewRecords,
    fetchNextPage: fetchNextInterviewPage,
    hasNextPage: hasNextInterviewPage,
    isFetchingNextPage: isFetchingNextInterviewPage,
  } = useInterviewRecords({
    enabled: shouldFetchInterviewRecords,
  });

  const handleScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      const { scrollTop, clientHeight, scrollHeight } = event.currentTarget;

      if (scrollHeight - scrollTop > clientHeight * 1.5) {
        return;
      }

      if (shouldFetchConversations && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }

      if (
        shouldFetchInterviewRecords &&
        hasNextInterviewPage &&
        !isFetchingNextInterviewPage
      ) {
        fetchNextInterviewPage();
      }
    },
    [
      fetchNextInterviewPage,
      fetchNextPage,
      hasNextInterviewPage,
      hasNextPage,
      isFetchingNextInterviewPage,
      isFetchingNextPage,
      shouldFetchConversations,
      shouldFetchInterviewRecords,
    ],
  );

  return {
    view,
    setView,
    conversations,
    interviewRecords,
    hasNextPage,
    hasNextInterviewPage,
    isFetchingNextPage,
    isFetchingNextInterviewPage,
    handleScroll,
  };
}
