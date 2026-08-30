import { useQuery } from "@tanstack/react-query";
import type { UserRespDTO } from "@/types/auth";
import { speechService, type SpeechCapabilities } from "@/services/speechService";

const getUserKey = (user: UserRespDTO | null) =>
  user ? `${user.id ?? "none"}:${user.username}` : "anonymous";

export function useSpeechCapabilities(currentUser: UserRespDTO | null) {
  const query = useQuery<SpeechCapabilities>({
    queryKey: ["speech-capabilities", getUserKey(currentUser)],
    queryFn: speechService.getCapabilities,
    enabled: Boolean(currentUser),
    staleTime: 60_000,
    retry: false,
  });

  const errorMessage = query.error instanceof Error ? query.error.message : null;
  const availabilityMessage = query.isLoading
    ? "正在检查语音转写服务..."
    : errorMessage
      ? "暂时无法连接语音转写服务，请检查网络后重试。"
      : query.data?.available
        ? null
        : "当前环境未配置语音转写服务。";

  return {
    capabilities: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
    availabilityMessage,
  };
}
