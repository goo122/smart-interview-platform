import { useCallback, useMemo } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ROUTES } from "@/lib/constants";
import { buildChatSessionPath, normalizeInitialQuery, type ChatPageLocationState } from "@/hooks/chat/chatRuntime.shared";
import { useAppSelector } from "@/store/hooks";

export function useChatRouteState() {
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams<{ sessionId?: string }>();
  const { currentSessionId } = useAppSelector((state) => state.chat);

  const locationState = useMemo(
    () => (location.state as ChatPageLocationState | null) ?? null,
    [location.state],
  );
  const routeSessionId = params.sessionId?.trim() || null;
  const initialQuery = normalizeInitialQuery(locationState?.initialQuery);
  const initialModel = locationState?.model ?? null;
  const hasPendingInitialQuery = Boolean(initialQuery);

  const navigateToSession = useCallback(
    (sessionId: string, options?: { replace?: boolean }) => {
      navigate(buildChatSessionPath(sessionId), {
        replace: options?.replace,
      });
    },
    [navigate],
  );

  const navigateToChatRoot = useCallback(
    (options?: { replace?: boolean }) => {
      navigate(ROUTES.chat, {
        replace: options?.replace,
      });
    },
    [navigate],
  );

  const shouldRedirectToRuntimeSession =
    !routeSessionId && !hasPendingInitialQuery && Boolean(currentSessionId);

  return {
    routeSessionId,
    currentRuntimeSessionId: currentSessionId,
    initialQuery,
    initialModel,
    hasPendingInitialQuery,
    shouldRedirectToRuntimeSession,
    locationKey: location.key,
    navigateToSession,
    navigateToChatRoot,
  };
}
