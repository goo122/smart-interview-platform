import { useState } from "react";
import { useAiModelsQuery } from "@/hooks/useAiModelsQuery";
import type { AiProperty } from "@/types/ai";

export function useModelList(initialModel: AiProperty | null) {
  const { models } = useAiModelsQuery();
  const [selectedModelId, setSelectedModelId] = useState<number | null>(
    () => initialModel?.id ?? null,
  );

  const selectedModel: AiProperty | null = (() => {
    if (models.length === 0) {
      return initialModel;
    }

    if (selectedModelId !== null) {
      const matchedBySelected = models.find(
        (item) => item.id === selectedModelId,
      );
      if (matchedBySelected) return matchedBySelected;
    }

    if (initialModel?.id !== undefined && initialModel?.id !== null) {
      const matchedByInitial = models.find(
        (item) => item.id === initialModel.id,
      );
      if (matchedByInitial) return matchedByInitial;
    }

    return models[0];
  })();

  const setSelectedModel = (model: AiProperty) => {
    setSelectedModelId(model.id);
  };

  return {
    models,
    selectedModel,
    setSelectedModel,
  };
}
