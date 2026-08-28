import { useCallback, useEffect, useRef, useState } from "react";
import {
  CHAT_MESSAGE_STATUS,
  CHAT_MESSAGE_VARIANT,
  type ChatMessage,
} from "@/lib/chat";
import {
  FEEDBACK_STREAM_DELAY_MS,
  FEEDBACK_STREAM_STEP,
  FOLLOW_UP_STREAM_DELAY_MS,
  FOLLOW_UP_STREAM_STEP,
  THINKING_PROGRESS_STAGES,
  THINKING_PROGRESS_STEP_DELAY_MS,
} from "@/hooks/interview/session/interviewSessionFlow.shared";
import {
  createAssistantMessage,
  createUserMessage,
  createWelcomeMessage,
} from "@/hooks/interview/shared/interviewUtils";

export function useInterviewMessageStream() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    createWelcomeMessage(),
  ]);

  const lastDisplayedQuestionRef = useRef<string | null>(null);
  const activeQuestionStreamRef = useRef<{ cancelled: boolean } | null>(null);
  const thinkingMessageRef = useRef<{
    messageId: string;
    timerId: number;
  } | null>(null);

  const stopThinkingIndicator = useCallback(
    (options?: { remove?: boolean }) => {
      const activeThinking = thinkingMessageRef.current;
      if (!activeThinking) {
        return;
      }

      window.clearInterval(activeThinking.timerId);
      thinkingMessageRef.current = null;

      setMessages((prev) => {
        if (options?.remove !== false) {
          return prev.filter(
            (message) => message.id !== activeThinking.messageId,
          );
        }
        return prev.map((message) =>
          message.id === activeThinking.messageId
            ? {
                ...message,
                content:
                  message.content ||
                  THINKING_PROGRESS_STAGES[message.activeProgressStep ?? 0],
                status: CHAT_MESSAGE_STATUS.done,
              }
            : message,
        );
      });
    },
    [],
  );

  const startThinkingIndicator = useCallback(() => {
    stopThinkingIndicator();

    const thinkingMessage = createAssistantMessage(
      THINKING_PROGRESS_STAGES[0],
      {
        status: CHAT_MESSAGE_STATUS.streaming,
        variant: CHAT_MESSAGE_VARIANT.progress,
        progressSteps: [...THINKING_PROGRESS_STAGES],
        activeProgressStep: 0,
      },
    );

    setMessages((prev) => [...prev, thinkingMessage]);

    let activeStep = 0;
    const timerId = window.setInterval(() => {
      activeStep = Math.min(
        activeStep + 1,
        THINKING_PROGRESS_STAGES.length - 1,
      );

      setMessages((prev) =>
        prev.map((message) =>
          message.id === thinkingMessage.id
            ? {
                ...message,
                content: THINKING_PROGRESS_STAGES[activeStep],
                status: CHAT_MESSAGE_STATUS.streaming,
                activeProgressStep: activeStep,
              }
            : message,
        ),
      );

      if (activeStep >= THINKING_PROGRESS_STAGES.length - 1) {
        window.clearInterval(timerId);
      }
    }, THINKING_PROGRESS_STEP_DELAY_MS);

    thinkingMessageRef.current = { messageId: thinkingMessage.id, timerId };
  }, [stopThinkingIndicator]);

  const cancelActiveQuestionStream = useCallback(() => {
    if (activeQuestionStreamRef.current) {
      activeQuestionStreamRef.current.cancelled = true;
      activeQuestionStreamRef.current = null;
    }
  }, []);

  const appendAssistantMessage = useCallback(
    async (
      content: string,
      options?: {
        fakeStream?: boolean;
        variant?: ChatMessage["variant"];
        streamStep?: number;
        streamDelayMs?: number;
        tts?: ChatMessage["tts"];
      },
    ) => {
      const normalizedContent = content.trim();
      if (!normalizedContent) {
        return;
      }

      if (!options?.fakeStream) {
        setMessages((prev) => [
          ...prev,
          createAssistantMessage(normalizedContent, {
            variant: options?.variant,
            tts: options?.tts,
          }),
        ]);
        return;
      }

      cancelActiveQuestionStream();
      const streamState = { cancelled: false };
      activeQuestionStreamRef.current = streamState;
      const streamingMessage = createAssistantMessage("", {
        status: CHAT_MESSAGE_STATUS.streaming,
        variant: options?.variant,
        tts: options?.tts,
      });

      setMessages((prev) => [...prev, streamingMessage]);

      let cursor = 0;
      while (!streamState.cancelled && cursor < normalizedContent.length) {
        cursor = Math.min(
          normalizedContent.length,
          cursor + (options?.streamStep ?? FOLLOW_UP_STREAM_STEP),
        );
        const partial = normalizedContent.slice(0, cursor);
        const isDone = cursor >= normalizedContent.length;

        setMessages((prev) =>
          prev.map((message) =>
            message.id === streamingMessage.id
              ? {
                  ...message,
                  content: partial,
                  status: isDone
                    ? CHAT_MESSAGE_STATUS.done
                    : CHAT_MESSAGE_STATUS.streaming,
                }
              : message,
          ),
        );

        if (!isDone) {
          await new Promise<void>((resolve) => {
            window.setTimeout(
              resolve,
              options?.streamDelayMs ?? FOLLOW_UP_STREAM_DELAY_MS,
            );
          });
        }
      }

      if (activeQuestionStreamRef.current === streamState) {
        activeQuestionStreamRef.current = null;
      }
    },
    [cancelActiveQuestionStream],
  );

  const appendNextQuestionMessage = useCallback(
    async (
      nextQuestion: string,
      nextQuestionNumber: string | null | undefined,
      isFollowUp: boolean,
      followUpCount?: number,
      options?: { appendMessage?: boolean },
    ) => {
      if (options?.appendMessage === false) {
        return;
      }

      const displayText =
        isFollowUp && typeof followUpCount === "number" && followUpCount > 0
          ? `【追问第 ${followUpCount} 轮】${nextQuestion}`
          : nextQuestion;
      const questionKey = `${nextQuestionNumber || ""}::${nextQuestion}::${followUpCount ?? 0}`;
      if (lastDisplayedQuestionRef.current === questionKey) {
        return;
      }

      lastDisplayedQuestionRef.current = questionKey;
      await appendAssistantMessage(displayText, {
        fakeStream: true,
        variant: isFollowUp ? CHAT_MESSAGE_VARIANT.followUp : undefined,
        streamStep: isFollowUp ? FOLLOW_UP_STREAM_STEP : FEEDBACK_STREAM_STEP,
        streamDelayMs: isFollowUp
          ? FOLLOW_UP_STREAM_DELAY_MS
          : FEEDBACK_STREAM_DELAY_MS,
        tts: {
          text: nextQuestion,
          autoPlay: true,
          cacheKey: questionKey,
        },
      });
    },
    [appendAssistantMessage],
  );

  const appendSystemMessage = useCallback(
    (
      content: string,
      status: ChatMessage["status"] = CHAT_MESSAGE_STATUS.done,
    ) => {
      setMessages((prev) => [
        ...prev,
        createAssistantMessage(content, {
          variant: CHAT_MESSAGE_VARIANT.system,
          status,
        }),
      ]);
    },
    [],
  );

  const appendUserMessage = useCallback((content: string) => {
    setMessages((prev) => [...prev, createUserMessage(content)]);
  }, []);

  const appendErrorMessage = useCallback((content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        ...createAssistantMessage(content),
        status: CHAT_MESSAGE_STATUS.error,
      },
    ]);
  }, []);

  const resetMessageStream = useCallback(() => {
    stopThinkingIndicator();
    cancelActiveQuestionStream();
    lastDisplayedQuestionRef.current = null;
    setMessages([createWelcomeMessage()]);
  }, [cancelActiveQuestionStream, stopThinkingIndicator]);

  useEffect(
    () => () => {
      cancelActiveQuestionStream();
      stopThinkingIndicator();
    },
    [cancelActiveQuestionStream, stopThinkingIndicator],
  );

  return {
    messages,
    appendAssistantMessage,
    appendNextQuestionMessage,
    appendSystemMessage,
    appendUserMessage,
    appendErrorMessage,
    startThinkingIndicator,
    stopThinkingIndicator,
    cancelActiveQuestionStream,
    resetMessageStream,
  };
}
