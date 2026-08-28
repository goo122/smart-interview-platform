import { useMutation, useQueries, useQuery, useQueryClient, type Query } from "@tanstack/react-query";
import type { KnowledgeDocumentPage } from "@/api/generated";
import { knowledgeApi } from "@/features/knowledge/api";
import { isDocumentProcessing } from "@/features/knowledge/types";

export const knowledgeKeys = {
  all: ["knowledge"] as const,
  bases: () => [...knowledgeKeys.all, "bases"] as const,
  documents: (baseId: string) => [...knowledgeKeys.all, "documents", baseId] as const,
};

export function useKnowledgeBases() {
  return useQuery({
    queryKey: knowledgeKeys.bases(),
    queryFn: () => knowledgeApi.listBases(),
    staleTime: 30_000,
  });
}

export function useKnowledgeDocuments(baseId: string | null) {
  return useQuery({
    queryKey: knowledgeKeys.documents(baseId ?? "none"),
    queryFn: () => knowledgeApi.listDocuments(baseId ?? ""),
    enabled: Boolean(baseId),
    staleTime: 1_000,
    refetchInterval: (query) => {
      const records = query.state.data?.records ?? [];
      return records.some(isDocumentProcessing) ? 2_000 : false;
    },
    refetchIntervalInBackground: false,
  });
}

export function useKnowledgeBaseReadiness() {
  const basesQuery = useKnowledgeBases();
  const documentQueries = useQueries({
    queries: (basesQuery.data?.records ?? []).map((base) => ({
      queryKey: knowledgeKeys.documents(base.id),
      queryFn: () => knowledgeApi.listDocuments(base.id),
      staleTime: 1_000,
      refetchInterval: (query: Query<KnowledgeDocumentPage, Error>) =>
        (query.state.data?.records ?? []).some(isDocumentProcessing) ? 2_000 : false,
      refetchIntervalInBackground: false,
    })),
  });
  const readyBaseIds = new Set(
    documentQueries.flatMap((query, index) =>
      (query.data?.records ?? []).some((document) => document.status === "READY")
        ? [basesQuery.data?.records[index]?.id ?? ""]
        : [],
    ),
  );
  return { ...basesQuery, documentQueries, readyBaseIds };
}

export function useKnowledgeMutations() {
  const queryClient = useQueryClient();
  const invalidateBases = () => queryClient.invalidateQueries({ queryKey: knowledgeKeys.bases() });
  const create = useMutation({
    mutationFn: knowledgeApi.createBase,
    onSuccess: invalidateBases,
  });
  const remove = useMutation({
    mutationFn: knowledgeApi.deleteBase,
    onSuccess: async () => {
      await invalidateBases();
      queryClient.removeQueries({ queryKey: [...knowledgeKeys.all, "documents"] });
    },
  });
  const upload = useMutation({
    mutationFn: ({ baseId, file, onProgress }: { baseId: string; file: File; onProgress?: (percent: number) => void }) =>
      knowledgeApi.uploadDocument(baseId, file, onProgress),
    onSuccess: (_, variables) => queryClient.invalidateQueries({ queryKey: knowledgeKeys.documents(variables.baseId) }),
  });
  const removeDocument = useMutation({
    mutationFn: knowledgeApi.deleteDocument,
    onSuccess: (_, documentId) => {
      queryClient.invalidateQueries({ queryKey: [...knowledgeKeys.all, "documents"] });
      queryClient.removeQueries({ queryKey: knowledgeKeys.documents(documentId) });
    },
  });
  return { create, remove, upload, removeDocument };
}
