import SmartComposer from "@/components/chat/SmartComposer";
import HomeQuickActions from "@/components/home/HomeQuickActions";
import { ModelSelector } from "@/components/home/ModelSelector";
import type { AiProperty } from "@/types/ai";

type HomeComposerPanelProps = {
  query: string;
  onQueryChange: (value: string) => void;
  onSend: () => void;
  models: AiProperty[];
  selectedModel: AiProperty | null;
  onSelectModel: (model: AiProperty) => void;
};

export default function HomeComposerPanel({
  query,
  onQueryChange,
  onSend,
  models,
  selectedModel,
  onSelectModel,
}: HomeComposerPanelProps) {
  return (
    <div className="w-full space-y-3">
      <SmartComposer
        value={query}
        onChange={onQueryChange}
        onSend={onSend}
        actions={
          models.length > 0 &&
          selectedModel && (
            <ModelSelector
              models={models}
              selectedModel={selectedModel}
              onSelect={onSelectModel}
            />
          )
        }
      />
      <HomeQuickActions />
    </div>
  );
}
