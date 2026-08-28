import { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { useChatHistoryLoader } from "@/hooks/chat/useChatHistoryLoader";
import { useChatRouteState } from "@/hooks/chat/useChatRouteState";
import { resetChatRuntime } from "@/store/slices/chatSlice";

type InitProps = {
  sendMessage: (
    content: string,
    aiId?: number,
    forceNewSession?: boolean,
  ) => Promise<void>;
  selectedModelId?: number;
  cancelActiveStream?: () => void;
};

export function useChatInitialization({
  sendMessage,
  selectedModelId,
  cancelActiveStream,
}: InitProps) {
  const dispatch = useAppDispatch();
  const {
    routeSessionId,
    hasPendingInitialQuery,
    navigateToChatRoot,
    shouldRedirectToRuntimeSession,
    navigateToSession,
    initialQuery,
    locationKey,
  } = useChatRouteState();
  const { currentSessionId } = useAppSelector((state) => state.chat);
  const handledInitialQueryKeyRef = useRef<string | null>(null);

  const { isHistoryLoading } = useChatHistoryLoader({
    routeSessionId,
    hasPendingInitialQuery,
    cancelActiveStream: cancelActiveStream ?? (() => undefined),
    navigateToChatRoot,
  });

  useEffect(() => {
    if (!shouldRedirectToRuntimeSession || !currentSessionId) {
      return;
    }

    navigateToSession(currentSessionId, {
      replace: true,
    });
  }, [currentSessionId, navigateToSession, shouldRedirectToRuntimeSession]);

  useEffect(() => {
    if (!initialQuery) {
      handledInitialQueryKeyRef.current = null;
      return;
    }

    if (handledInitialQueryKeyRef.current === locationKey) {
      return;
    }

    if (selectedModelId === undefined || selectedModelId === null) {
      return;
    }

    handledInitialQueryKeyRef.current = locationKey;
    dispatch(resetChatRuntime());
    void sendMessage(initialQuery, selectedModelId, true);
  }, [
    dispatch,
    initialQuery,
    locationKey,
    selectedModelId,
    sendMessage,
  ]);

  return {
    isHistoryLoading,
  };
}
