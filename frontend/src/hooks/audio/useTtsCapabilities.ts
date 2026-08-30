import { useQuery } from "@tanstack/react-query";
import { ttsService, type TtsCapabilities } from "@/services/ttsService";
import type { UserRespDTO } from "@/types/auth";

const getUserKey = (currentUser: UserRespDTO | null) =>
  currentUser ? `${currentUser.id ?? "none"}:${currentUser.username}` : "anonymous";

export function useTtsCapabilities(currentUser: UserRespDTO | null) {
  const query = useQuery<TtsCapabilities>({
    queryKey: ["tts-capabilities", getUserKey(currentUser)],
    queryFn: ttsService.getCapabilities,
    enabled: Boolean(currentUser),
    staleTime: 60_000,
    retry: false,
  });

  const availabilityMessage = query.isLoading
    ? "正在检查语音合成服务..."
    : query.error
      ? "暂时无法连接语音合成服务，请稍后重试。"
      : query.data?.available
        ? null
        : "当前环境未配置语音合成服务。";

  return {
    capabilities: query.data ?? null,
    isLoading: query.isLoading,
    availabilityMessage,
  };
}
