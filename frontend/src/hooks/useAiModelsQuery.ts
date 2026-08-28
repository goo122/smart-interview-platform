import { useQuery } from "@tanstack/react-query";
import { aiService } from "@/services/aiService";
import { useAppSelector } from "@/store/hooks";
import type { AiProperty } from "@/types/ai";
import type { UserRespDTO } from "@/types/auth";

type ModelUserIdentity =
  | Pick<UserRespDTO, "id" | "username">
  | null
  | undefined;

type UseAiModelsQueryOptions = {
  enabled?: boolean;
};

const getAiModelsUserKey = (user: ModelUserIdentity) => {
  if (!user) return "anonymous";
  if (typeof user.id === "number" && Number.isFinite(user.id) && user.id > 0) {
    return `id:${user.id}`;
  }
  if (user.username) return `username:${user.username}`;
  return "anonymous";
};

export const getAiModelsQueryKey = (userKey: string, authEpoch: number) =>
  ["ai-models", userKey, authEpoch] as const;

export function useAiModelsQuery(options: UseAiModelsQueryOptions = {}) {
  const { isAuthenticated, currentUser, authEpoch } = useAppSelector(
    (state) => state.user,
  );

  const userKey = getAiModelsUserKey(currentUser);
  const enabled = (options.enabled ?? true) && isAuthenticated;

  const query = useQuery({
    queryKey: getAiModelsQueryKey(userKey, authEpoch),
    queryFn: async () => {
      const response = await aiService.getAiProperties({ isEnabled: 1 });
      return response?.records ?? [];
    },
    enabled,
  });

  return {
    ...query,
    models: (query.data ?? []) as AiProperty[],
  };
}
