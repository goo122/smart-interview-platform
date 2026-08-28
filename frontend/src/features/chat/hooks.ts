import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { chatApi } from "@/features/chat/api";

export const chatKeys = {
  all: ["chat"] as const,
  conversations: () => [...chatKeys.all, "conversations"] as const,
  messages: (sessionId: string) => [...chatKeys.all, "messages", sessionId] as const,
};

export function useConversations() {
  return useQuery({
    queryKey: chatKeys.conversations(),
    queryFn: () => chatApi.listConversations(),
    staleTime: 10_000,
  });
}

export function useConversationMessages(sessionId: string | null) {
  return useQuery({
    queryKey: chatKeys.messages(sessionId ?? "none"),
    queryFn: () => chatApi.listMessages(sessionId ?? ""),
    enabled: Boolean(sessionId),
    staleTime: 5_000,
  });
}

export function useChatMutations() {
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: chatApi.createConversation,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chatKeys.conversations() }),
  });
  const finish = useMutation({
    mutationFn: chatApi.finishConversation,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chatKeys.conversations() }),
  });
  const remove = useMutation({
    mutationFn: chatApi.deleteConversation,
    onSuccess: (_, sessionId) => {
      queryClient.invalidateQueries({ queryKey: chatKeys.conversations() });
      queryClient.removeQueries({ queryKey: chatKeys.messages(sessionId) });
    },
  });
  return { create, finish, remove };
}
