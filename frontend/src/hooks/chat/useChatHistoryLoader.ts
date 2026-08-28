import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CHAT_HISTORY_LOADING_TITLE,
  normalizeHistoryMessages,
} from "@/hooks/chat/chatRuntime.shared";
import { aiService } from "@/services/aiService";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  hydrateChatSession,
  resetChatRuntime,
} from "@/store/slices/chatSlice";

type UseChatHistoryLoaderOptions = {
  routeSessionId: string | null;
  hasPendingInitialQuery: boolean;
  cancelActiveStream: () => void;
  navigateToChatRoot: (options?: { replace?: boolean }) => void;
};

export function useChatHistoryLoader({
  routeSessionId,
  hasPendingInitialQuery,
  cancelActiveStream,
  navigateToChatRoot,
}: UseChatHistoryLoaderOptions) {
  const dispatch = useAppDispatch();
  const { currentSessionId, messages } = useAppSelector((state) => state.chat);

  const shouldLoadHistory = useMemo(
    () =>
      Boolean(routeSessionId) &&
      !hasPendingInitialQuery &&
      (currentSessionId !== routeSessionId || messages.length === 0),
    [currentSessionId, hasPendingInitialQuery, messages.length, routeSessionId],
  );

  useEffect(() => {
    if (!routeSessionId || !shouldLoadHistory) {
      return;
    }

    cancelActiveStream();
    dispatch(
      hydrateChatSession({
        sessionId: routeSessionId,
        title: CHAT_HISTORY_LOADING_TITLE,
        messages: [],
      }),
    );
  }, [cancelActiveStream, dispatch, routeSessionId, shouldLoadHistory]);

  const historyQuery = useQuery({
    queryKey: ["chat-history", routeSessionId],
    enabled: shouldLoadHistory && Boolean(routeSessionId),
    queryFn: () => aiService.getConversationHistory(routeSessionId as string),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!routeSessionId || !historyQuery.data) {
      return;
    }

    dispatch(
      hydrateChatSession({
        sessionId: routeSessionId,
        title: routeSessionId,
        messages: normalizeHistoryMessages(historyQuery.data),
      }),
    );
  }, [dispatch, historyQuery.data, routeSessionId]);

  useEffect(() => {
    if (!routeSessionId || !historyQuery.error) {
      return;
    }

    console.error("Failed to load history:", historyQuery.error);
    dispatch(resetChatRuntime());
    navigateToChatRoot({
      replace: true,
    });
  }, [dispatch, historyQuery.error, navigateToChatRoot, routeSessionId]);

  return {
    isHistoryLoading:
      shouldLoadHistory && (historyQuery.isLoading || historyQuery.isFetching),
  };
}
