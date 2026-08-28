import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  CHAT_STREAM_ERROR_TEXT,
  createRuntimeMessageId,
} from "@/hooks/chat/chatRuntime.shared";
import {
  getConversationUserKey,
  getConversationsQueryKey,
} from "@/hooks/useConversations";
import { CHAT_ROLES, ROUTES } from "@/lib/constants";
import { CHAT_MESSAGE_STATUS, type ChatMessage } from "@/lib/chat";
import {
  createTextStreamLimiter,
  type TextStreamLimiter,
} from "@/lib/streamLimiter";
import { aiService } from "@/services/aiService";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  appendAssistantChunk,
  appendAssistantPlaceholder,
  appendAssistantReasoningChunk,
  appendUserMessage,
  failAssistantMessage,
  finishAssistantMessage,
  setActiveStream,
  setPendingOutbound,
  setChatRuntimeSession,
  type PendingOutbound,
} from "@/store/slices/chatSlice";

type SendMessageOptions = {
  forceNewSession?: boolean;
};

type UseChatSendFlowOptions = {
  routeSessionId: string | null;
  navigateToSession: (
    sessionId: string,
    options?: { replace?: boolean },
  ) => void;
};

export function useChatSendFlow({
  routeSessionId,
  navigateToSession,
}: UseChatSendFlowOptions) {
  const dispatch = useAppDispatch();
  const queryClient = useQueryClient();
  const { messages, isStreaming, currentSessionId, pendingOutbound } =
    useAppSelector((state) => state.chat);
  const { currentUser, authEpoch } = useAppSelector((state) => state.user);

  const abortControllerRef = useRef<AbortController | null>(null);
  const activeRequestIdRef = useRef<string | null>(null);
  const cancelActiveStreamRef = useRef<() => void>(() => undefined);

  const cancelActiveStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    activeRequestIdRef.current = null;
    if (pendingOutbound) {
      dispatch(
        finishAssistantMessage({
          id: pendingOutbound.assistantMessageId,
        }),
      );
      dispatch(setPendingOutbound(null));
    }
    dispatch(setActiveStream(null));
  }, [dispatch, pendingOutbound]);

  useEffect(() => {
    cancelActiveStreamRef.current = cancelActiveStream;
  }, [cancelActiveStream]);

  const streamMessage = useCallback(
    async (outbound: PendingOutbound) => {
      const abortController = new AbortController();
      abortControllerRef.current = abortController;
      activeRequestIdRef.current = outbound.requestId;

      let contentLimiter: TextStreamLimiter | null = null;
      let reasoningLimiter: TextStreamLimiter | null = null;
      let hasFinalizedMessage = false;

      const isActiveRequest = () =>
        activeRequestIdRef.current === outbound.requestId &&
        abortControllerRef.current === abortController;

      dispatch(
        setActiveStream({
          requestId: outbound.requestId,
          sessionId: outbound.sessionId,
          messageId: outbound.assistantMessageId,
        }),
      );

      contentLimiter = createTextStreamLimiter({
        intervalMs: 40,
        charsPerTick: 12,
        onUpdate: (nextChunk) => {
          if (!isActiveRequest()) {
            return;
          }
          dispatch(
            appendAssistantChunk({
              id: outbound.assistantMessageId,
              content: nextChunk,
            }),
          );
        },
      });

      reasoningLimiter = createTextStreamLimiter({
        intervalMs: 40,
        charsPerTick: 12,
        onUpdate: (nextChunk) => {
          if (!isActiveRequest()) {
            return;
          }
          dispatch(
            appendAssistantReasoningChunk({
              id: outbound.assistantMessageId,
              reasoning: nextChunk,
            }),
          );
        },
      });

      try {
        await aiService.streamChat(
          {
            sessionId: outbound.sessionId,
            inputMessage: outbound.content,
            userName: currentUser?.username || "Guest",
            aiId: outbound.aiId,
          },
          abortController.signal,
          {
            onMessage: (chunk) => {
              if (!isActiveRequest()) {
                return;
              }
              contentLimiter?.push(chunk);
            },
            onReasoning: (chunk) => {
              if (!isActiveRequest()) {
                return;
              }
              reasoningLimiter?.push(chunk);
            },
            onDone: () => {
              if (!isActiveRequest()) {
                return;
              }
              contentLimiter?.flush();
              reasoningLimiter?.flush();
              dispatch(
                finishAssistantMessage({
                  id: outbound.assistantMessageId,
                }),
              );
              hasFinalizedMessage = true;
              dispatch(setActiveStream(null));
              activeRequestIdRef.current = null;
              abortControllerRef.current = null;
            },
            onError: (error) => {
              if (error.message === "Connection closed") {
                return;
              }
              console.error("Stream error callback:", error);
            },
          },
        );
      } catch (error: unknown) {
        if (
          error instanceof Error &&
          (error.name === "AbortError" || error.message === "Connection closed")
        ) {
          if (!hasFinalizedMessage) {
            dispatch(
              finishAssistantMessage({
                id: outbound.assistantMessageId,
              }),
            );
            hasFinalizedMessage = true;
          }
          return;
        }

        console.error("Chat error:", error);
        dispatch(
          failAssistantMessage({
            id: outbound.assistantMessageId,
            errorMessage:
              error instanceof Error ? error.message : CHAT_STREAM_ERROR_TEXT,
          }),
        );
      } finally {
        contentLimiter?.flush();
        reasoningLimiter?.flush();
        contentLimiter?.stop();
        reasoningLimiter?.stop();

        if (abortControllerRef.current === abortController) {
          abortControllerRef.current = null;
        }
        if (activeRequestIdRef.current === outbound.requestId) {
          activeRequestIdRef.current = null;
        }
        dispatch(setActiveStream(null));
      }
    },
    [currentUser, dispatch],
  );

  const sendMessage = useCallback(
    async (content: string, aiId?: number, options?: SendMessageOptions) => {
      const nextContent = content.trim();
      if (!nextContent || isStreaming || Boolean(pendingOutbound)) {
        return;
      }

      cancelActiveStream();

      const requestId = createRuntimeMessageId("chat-request");
      const userMessage: ChatMessage = {
        id: createRuntimeMessageId("chat-user"),
        role: CHAT_ROLES.user,
        content: nextContent,
        timestamp: Date.now(),
        status: CHAT_MESSAGE_STATUS.done,
      };
      const assistantMessage: ChatMessage = {
        id: createRuntimeMessageId("chat-assistant"),
        role: CHAT_ROLES.assistant,
        content: "",
        timestamp: Date.now(),
        status: CHAT_MESSAGE_STATUS.streaming,
      };

      dispatch(appendUserMessage(userMessage));
      dispatch(appendAssistantPlaceholder(assistantMessage));

      try {
        let activeSessionId =
          options?.forceNewSession === true
            ? null
            : routeSessionId || currentSessionId;

        if (!activeSessionId) {
          const response = await aiService.createConversation({
            userName: currentUser?.username || "Guest",
            firstMessage: nextContent,
            aiId,
          });

          if (!response?.sessionId) {
            throw new Error(
              "Failed to create conversation: invalid response data",
            );
          }

          activeSessionId = response.sessionId;
          dispatch(
            setChatRuntimeSession({
              sessionId: activeSessionId,
              title:
                response.conversationTitle ||
                nextContent.slice(0, 24) ||
                activeSessionId,
            }),
          );
          navigateToSession(activeSessionId, {
            replace: true,
          });

          const userKey = getConversationUserKey(currentUser);
          await queryClient.invalidateQueries({
            queryKey: getConversationsQueryKey(userKey, authEpoch),
          });

          dispatch(
            setPendingOutbound({
              requestId,
              sessionId: activeSessionId,
              assistantMessageId: assistantMessage.id,
              content: nextContent,
              aiId,
            }),
          );
          return;
        }

        await streamMessage({
          requestId,
          sessionId: activeSessionId,
          assistantMessageId: assistantMessage.id,
          content: nextContent,
          aiId,
        });
      } catch (error: unknown) {
        console.error("Chat error:", error);
        dispatch(
          failAssistantMessage({
            id: assistantMessage.id,
            errorMessage:
              error instanceof Error ? error.message : CHAT_STREAM_ERROR_TEXT,
          }),
        );
      }
    },
    [
      authEpoch,
      cancelActiveStream,
      currentSessionId,
      currentUser,
      dispatch,
      isStreaming,
      navigateToSession,
      pendingOutbound,
      queryClient,
      routeSessionId,
      streamMessage,
    ],
  );

  useEffect(() => {
    if (!pendingOutbound || isStreaming) {
      return;
    }
    if (
      routeSessionId !== pendingOutbound.sessionId ||
      currentSessionId !== pendingOutbound.sessionId
    ) {
      return;
    }

    dispatch(setPendingOutbound(null));
    void streamMessage(pendingOutbound);
  }, [
    currentSessionId,
    dispatch,
    isStreaming,
    pendingOutbound,
    routeSessionId,
    streamMessage,
  ]);

  useEffect(() => {
    if (!pendingOutbound || !routeSessionId) {
      return;
    }
    if (routeSessionId === pendingOutbound.sessionId) {
      return;
    }

    dispatch(
      finishAssistantMessage({
        id: pendingOutbound.assistantMessageId,
      }),
    );
    dispatch(setPendingOutbound(null));
  }, [dispatch, pendingOutbound, routeSessionId]);

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined") {
        if (window.location.pathname.startsWith(ROUTES.chat)) {
          return;
        }
      }
      cancelActiveStreamRef.current();
    };
  }, []);

  return {
    messages,
    isStreaming: isStreaming || Boolean(pendingOutbound),
    sendMessage,
    cancelActiveStream,
  };
}
