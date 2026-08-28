import ChatHistoryLoadingOverlay from "@/components/chat/ChatHistoryLoadingOverlay";
import ChatPageHeader from "@/components/chat/ChatPageHeader";
import ChatRoom from "@/components/chat/ChatRoom";
import SmartComposer from "@/components/chat/SmartComposer";
import { ModelSelector } from "@/components/home/ModelSelector";
import { useChatPageController } from "@/hooks/chat/useChatPageController";

export default function ChatPage() {
  const { history, composer, modelSelection } = useChatPageController();

  return (
    <ChatRoom
      header={
        <ChatPageHeader
          selectedModelName={modelSelection.selectedModel?.aiName}
        />
      }
      messages={history.messages}
      inputValue={composer.input}
      onInputChange={composer.setInput}
      onSend={composer.handleSend}
      contentOverlay={
        history.isLoading ? <ChatHistoryLoadingOverlay /> : null
      }
      customComposer={
        <SmartComposer
          value={composer.input}
          onChange={composer.setInput}
          onSend={composer.handleSend}
          disabled={composer.isBlocked}
          actions={
            modelSelection.models.length > 0 &&
            modelSelection.selectedModel && (
              <ModelSelector
                models={modelSelection.models}
                selectedModel={modelSelection.selectedModel}
                onSelect={modelSelection.setSelectedModel}
              />
            )
          }
        />
      }
    />
  );
}
