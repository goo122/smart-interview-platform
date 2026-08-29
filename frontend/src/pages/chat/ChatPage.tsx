import { useState } from "react";
import ChatHistoryLoadingOverlay from "@/components/chat/ChatHistoryLoadingOverlay";
import ChatPageHeader from "@/components/chat/ChatPageHeader";
import ChatRoom from "@/components/chat/ChatRoom";
import SmartComposer from "@/components/chat/SmartComposer";
import { ModelSelector } from "@/components/home/ModelSelector";
import { useChatPageController } from "@/hooks/chat/useChatPageController";
import { KnowledgePanel } from "@/features/knowledge/components/KnowledgePanel";

export default function ChatPage() {
  const [knowledgeBaseId, setKnowledgeBaseId] = useState<string | null>(null);
  const { history, composer, modelSelection } = useChatPageController({
    knowledgeBaseId,
  });

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3 md:p-4">
      <KnowledgePanel
        selectedBaseId={knowledgeBaseId}
        onSelect={setKnowledgeBaseId}
      />
      <div className="min-h-0 flex-1">
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
      </div>
    </div>
  );
}
