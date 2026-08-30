import { memo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import ChatBubble from "@/components/chat/ChatBubble";
import { type ChatMessage } from "@/lib/chat";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { useChatTtsPlayback } from "@/hooks/audio/useChatTtsPlayback";
import { useTtsCapabilities } from "@/hooks/audio/useTtsCapabilities";
import { useAppSelector } from "@/store/hooks";

type ChatListProps = {
  messages: ChatMessage[];
  topContent?: React.ReactNode;
  assistantAvatarSrc?: string;
  className?: string;
};

function ChatList({
  messages,
  topContent,
  assistantAvatarSrc,
  className,
}: ChatListProps) {
  const scrollRef = useAutoScroll(messages);
  const { currentUser } = useAppSelector((state) => state.user);
  const ttsCapabilities = useTtsCapabilities(currentUser);
  const ttsAvailable = Boolean(ttsCapabilities.capabilities?.available);
  const {
    loadingMessageId,
    playingMessageId,
    errorMessage,
    errorMessageId,
    toggleMessagePlayback,
  } = useChatTtsPlayback(messages, { enabled: ttsAvailable });

  return (
    <ScrollArea className={className} ref={scrollRef}>
      <div className="max-w-3xl mx-auto space-y-6 pb-20 ">
        {topContent}
        {ttsCapabilities.availabilityMessage ? (
          <p className="text-xs text-slate-500" role="status">
            {ttsCapabilities.availabilityMessage}
          </p>
        ) : null}
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              layout
              initial={{ opacity: 0, y: 16, scale: 0.985, filter: "blur(4px)" }}
              animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -8, scale: 0.985, filter: "blur(3px)" }}
              transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
            >
              <ChatBubble
                role={msg.role}
                content={msg.content}
                reasoning={msg.reasoning}
                status={msg.status}
                variant={msg.variant}
                tts={msg.tts}
                isTtsLoading={loadingMessageId === msg.id}
                isTtsPlaying={playingMessageId === msg.id}
                onTtsToggle={
                  msg.tts && ttsAvailable
                    ? () => toggleMessagePlayback(msg)
                    : undefined
                }
                ttsError={errorMessageId === msg.id ? errorMessage : null}
                progressSteps={msg.progressSteps}
                activeProgressStep={msg.activeProgressStep}
                citations={msg.citations}
                assistantAvatarSrc={assistantAvatarSrc}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ScrollArea>
  );
}

export default memo(ChatList);
