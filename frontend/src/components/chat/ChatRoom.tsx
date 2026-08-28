import { cn } from "@/lib/utils";
import ChatList from "@/components/chat/ChatList";
import ChatComposer from "@/components/chat/ChatComposer";
import { type ChatMessage } from "@/lib/chat";

type ChatRoomProps = {
  header?: React.ReactNode;
  topContent?: React.ReactNode;
  messages: ChatMessage[];
  inputValue: string;
  onInputChange: (value: string) => void;
  onSend?: () => void;
  inputPlaceholder?: string;
  inputDisabled?: boolean;
  assistantAvatarSrc?: string;
  composerLeading?: React.ReactNode;
  composerActions?: React.ReactNode;
  contentOverlay?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  customComposer?: React.ReactNode;
};

export default function ChatRoom({
  header,
  topContent,
  messages,
  inputValue,
  onInputChange,
  onSend,
  inputPlaceholder,
  inputDisabled,
  assistantAvatarSrc,
  composerLeading,
  composerActions,
  contentOverlay,
  footer,
  className,
  customComposer,
}: ChatRoomProps) {
  return (
    <div className={cn("flex flex-col h-full relative", className)}>
      {header}
      <div className="flex-1 overflow-hidden relative">
        <ChatList
          className="h-full px-4 md:px-20 py-6"
          messages={messages}
          topContent={topContent}
          assistantAvatarSrc={assistantAvatarSrc}
        />
        {contentOverlay}
      </div>
      <div className="p-4 border-t bg-white relative z-30">
        <div className="max-w-3xl mx-auto relative">
          {customComposer ? (
            customComposer
          ) : (
            <ChatComposer
              value={inputValue}
              onChange={onInputChange}
              onSend={onSend}
              placeholder={inputPlaceholder}
              disabled={inputDisabled}
              leading={composerLeading}
              actions={composerActions}
            />
          )}
          {footer}
        </div>
      </div>
    </div>
  );
}
