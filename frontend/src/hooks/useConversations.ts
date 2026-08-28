import { useInfiniteQuery } from "@tanstack/react-query";
import { aiService } from "@/services/aiService";
import { useAppSelector } from "@/store/hooks";
import type { UserRespDTO } from "@/types/auth";

type ConversationUserIdentity =
  | Pick<UserRespDTO, "id" | "username">
  | null
  | undefined;

type UseConversationsOptions = {
  enabled?: boolean;
};

export const getConversationUserKey = (user: ConversationUserIdentity) => {
  if (!user) return "anonymous";
  if (typeof user.id === "number" && Number.isFinite(user.id) && user.id > 0) {
    return `id:${user.id}`;
  }
  if (user.username) return `username:${user.username}`;
  return "anonymous";
};

export const getConversationsQueryKey = (userKey: string, authEpoch: number) =>
  ["conversations", userKey, authEpoch] as const;

export function useConversations(options: UseConversationsOptions = {}) {
  const { isAuthenticated, currentUser, authEpoch } = useAppSelector(
    (state) => state.user,
  );
  const userKey = getConversationUserKey(currentUser);
  const enabled = (options.enabled ?? true) && isAuthenticated;

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
    refetch,
  } = useInfiniteQuery({
    queryKey: getConversationsQueryKey(userKey, authEpoch),
    queryFn: async ({ pageParam = 1 }) => {
      return aiService.getConversations({
        current: pageParam,
        size: 20,
      });
    },
    getNextPageParam: (lastPage) => {
      if (!lastPage || !lastPage.records) return undefined;
      if (lastPage.records.length < 20) return undefined;
      return lastPage.current + 1;
    },
    initialPageParam: 1,
    enabled,
  });

  return {
    conversations: data?.pages.flatMap((page) => page.records) || [],
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
    refetch,
  };
}
