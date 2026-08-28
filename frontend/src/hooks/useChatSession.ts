import { useChatRouteState } from "@/hooks/chat/useChatRouteState";
import { useChatSendFlow } from "@/hooks/chat/useChatSendFlow";

export function useChatSession() {
  const routeState = useChatRouteState();
  const { messages, isStreaming, sendMessage, cancelActiveStream } =
    useChatSendFlow({
      routeSessionId: routeState.routeSessionId,
      navigateToSession: routeState.navigateToSession,
    });

  return {
    messages,
    sendMessage: (
      content: string,
      aiId?: number,
      forceNewSession?: boolean,
    ) =>
      sendMessage(content, aiId, {
        forceNewSession,
      }),
    isStreaming,
    cancelActiveStream,
  };
}
