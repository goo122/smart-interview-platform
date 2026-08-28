import { useCallback, useEffect, useRef, useState } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { useModelList } from "@/hooks/useModelList";
import { useChatHistoryLoader } from "@/hooks/chat/useChatHistoryLoader";
import { useChatRouteState } from "@/hooks/chat/useChatRouteState";
import { useChatSendFlow } from "@/hooks/chat/useChatSendFlow";
import { resetChatRuntime } from "@/store/slices/chatSlice";

export function useChatPageController() {
  const dispatch = useAppDispatch();
  const {
    routeSessionId,
    initialQuery,
    initialModel,
    hasPendingInitialQuery,
    shouldRedirectToRuntimeSession,
    locationKey,
    navigateToSession,
    navigateToChatRoot,
  } = useChatRouteState();
  const { messages, isStreaming, sendMessage, cancelActiveStream } =
    useChatSendFlow({
      routeSessionId,
      navigateToSession,
    });
  const { selectedModel, setSelectedModel, models } = useModelList(initialModel);
  const { isHistoryLoading } = useChatHistoryLoader({
    routeSessionId,
    hasPendingInitialQuery,
    cancelActiveStream,
    navigateToChatRoot,
  });
  const [input, setInput] = useState("");
  const handledInitialQueryKeyRef = useRef<string | null>(null);
  const { currentSessionId } = useAppSelector((state) => state.chat);

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

    const initialModelId = initialModel?.id ?? selectedModel?.id;
    if (initialModelId === undefined || initialModelId === null) {
      return;
    }

    handledInitialQueryKeyRef.current = locationKey;
    dispatch(resetChatRuntime());
    void sendMessage(initialQuery, initialModelId, {
      forceNewSession: true,
    });
  }, [
    dispatch,
    initialModel,
    initialQuery,
    locationKey,
    selectedModel,
    sendMessage,
  ]);

  const isComposerBlocked = isStreaming || isHistoryLoading;

  const handleSend = useCallback(() => {
    const nextInput = input.trim();
    if (!nextInput || isComposerBlocked) {
      return;
    }

    setInput("");
    void sendMessage(nextInput, selectedModel?.id);
  }, [input, isComposerBlocked, selectedModel, sendMessage]);

  return {
    history: {
      messages,
      isLoading: isHistoryLoading,
    },
    composer: {
      input,
      setInput,
      isBlocked: isComposerBlocked,
      handleSend,
    },
    modelSelection: {
      models,
      selectedModel,
      setSelectedModel,
    },
  };
}
