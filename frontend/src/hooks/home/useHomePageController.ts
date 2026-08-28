import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "@/lib/constants";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { resetChatRuntime } from "@/store/slices/chatSlice";
import { useAiModelsQuery } from "@/hooks/useAiModelsQuery";
import type { AiProperty } from "@/types/ai";

export function useHomePageController() {
  const [query, setQuery] = useState("");
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null);
  const { models } = useAiModelsQuery();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { isAuthenticated } = useAppSelector((state) => state.user);

  const selectedModel: AiProperty | null = useMemo(() => {
    if (models.length === 0) {
      return null;
    }

    if (selectedModelId === null) {
      return models[0];
    }

    return models.find((item) => item.id === selectedModelId) ?? models[0];
  }, [models, selectedModelId]);

  const handleSend = useCallback(async () => {
    if (!query.trim()) {
      return;
    }

    if (!isAuthenticated) {
      navigate(ROUTES.auth);
      return;
    }

    try {
      dispatch(resetChatRuntime());
      navigate(ROUTES.chat, {
        state: {
          model: selectedModel,
          initialQuery: query,
        },
      });
      setQuery("");
    } catch (error) {
      console.error("Failed to navigate:", error);
    }
  }, [dispatch, isAuthenticated, navigate, query, selectedModel]);

  const handleSelectModel = useCallback((model: AiProperty) => {
    setSelectedModelId(model.id);
  }, []);

  return {
    query,
    setQuery,
    models,
    selectedModel,
    handleSend,
    handleSelectModel,
  };
}
