import { cn } from "@/lib/utils";
import { CHAT_ROLES, type ChatRole } from "@/lib/constants";
import {
  CHAT_MESSAGE_STATUS,
  CHAT_MESSAGE_VARIANT,
  type ChatMessageTts,
  type ChatMessageStatus,
  type ChatMessageVariant,
} from "@/lib/chat";
import ChatReasoningPanel from "@/components/chat/ChatReasoningPanel";
import ChatMessageContent from "@/components/chat/ChatMessageContent";
import ChatProgressBubble from "@/components/chat/ChatProgressBubble";
import { Button } from "@/components/ui/button";
import { Loader2, Pause, Play } from "lucide-react";

type ChatBubbleProps = {
  role: ChatRole;
  content: string;
  reasoning?: string;
  assistantAvatarSrc?: string;
  status?: ChatMessageStatus;
  variant?: ChatMessageVariant;
  tts?: ChatMessageTts;
  isTtsPlaying?: boolean;
  isTtsLoading?: boolean;
  onTtsToggle?: () => void;
  progressSteps?: string[];
  activeProgressStep?: number;
};

export default function ChatBubble({
  role,
  content,
  reasoning,
  status,
  variant,
  tts,
  isTtsPlaying = false,
  isTtsLoading = false,
  onTtsToggle,
  progressSteps,
  activeProgressStep = 0,
}: ChatBubbleProps) {
  const isUser = role === CHAT_ROLES.user;
  const isStreaming = status === CHAT_MESSAGE_STATUS.streaming;
  const messageVariant = variant || CHAT_MESSAGE_VARIANT.default;
  const isFeedback =
    !isUser && messageVariant === CHAT_MESSAGE_VARIANT.feedback;
  const isFollowUp =
    !isUser && messageVariant === CHAT_MESSAGE_VARIANT.followUp;
  const isSystem = !isUser && messageVariant === CHAT_MESSAGE_VARIANT.system;
  const isProgress =
    !isUser && messageVariant === CHAT_MESSAGE_VARIANT.progress;
  const hasReasoning = !isUser && Boolean(reasoning);
  const shouldRenderMessage = isProgress || Boolean(content) || !reasoning;
  const shouldRenderTtsControl =
    !isUser && Boolean(tts?.text) && !isFeedback && !isSystem && !isProgress;

  return (
    <div
      className={cn(
        "group flex w-full gap-4",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div className="flex flex-col max-w-[80%] gap-2">
        {hasReasoning && reasoning ? (
          <ChatReasoningPanel
            reasoning={reasoning}
            isStreaming={isStreaming}
            hasContent={Boolean(content)}
          />
        ) : null}

        {shouldRenderMessage ? (
          isProgress ? (
            <ChatProgressBubble
              label={content}
              steps={progressSteps ?? []}
              activeStep={activeProgressStep}
            />
          ) : (
            <div className="relative">
              {shouldRenderTtsControl && onTtsToggle ? (
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  aria-label={
                    isTtsPlaying || isTtsLoading
                      ? "暂停题目播报"
                      : "播放题目播报"
                  }
                  className={cn(
                    "absolute left-full top-3 ml-3 h-9 w-9 rounded-full border-slate-200 bg-white text-slate-600 shadow-sm transition-all",
                    "pointer-events-none translate-x-1 opacity-0 group-hover:pointer-events-auto group-hover:translate-x-0 group-hover:opacity-100",
                    (isTtsPlaying || isTtsLoading) &&
                      "pointer-events-auto translate-x-0 opacity-100",
                  )}
                  onClick={onTtsToggle}
                >
                  {isTtsLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : isTtsPlaying ? (
                    <Pause className="h-4 w-4" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                </Button>
              ) : null}

              <div
                className={cn(
                  "px-4 py-3 rounded-2xl",
                  isUser
                    ? "bg-muted/50 text-foreground border-0"
                    : "bg-muted text-foreground border",
                  isFeedback && "border-emerald-300 bg-emerald-50 shadow-sm",
                  isFollowUp && "border-amber-200 bg-amber-50/80 shadow-sm",
                  isSystem && "border-sky-200 bg-sky-50/80 text-slate-700",
                )}
              >
                {isFeedback ? (
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-emerald-800">
                    Score Feedback
                  </p>
                ) : null}
                {isFollowUp ? (
                  <p className="mb-2 text-[11px] font-semibold tracking-wide text-amber-700">
                    追问问题
                  </p>
                ) : null}
                <ChatMessageContent
                  content={content}
                  isStreaming={isStreaming}
                  showStreamingCursor={Boolean(content) || !reasoning}
                />
              </div>
            </div>
          )
        ) : null}
      </div>
    </div>
  );
}
