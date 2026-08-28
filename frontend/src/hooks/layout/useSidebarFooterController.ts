import { useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "@/lib/constants";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { resetChatRuntime } from "@/store/slices/chatSlice";
import { logoutUser } from "@/store/slices/userSlice";

export function useSidebarFooterController() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { isAuthenticated, currentUser } = useAppSelector(
    (state) => state.user,
  );

  const userInitials = useMemo(() => {
    return currentUser?.username?.slice(0, 2).toUpperCase() || "ME";
  }, [currentUser?.username]);

  const handleLogout = useCallback(async () => {
    await dispatch(logoutUser());
    dispatch(resetChatRuntime());
    navigate(ROUTES.auth);
  }, [dispatch, navigate]);

  return {
    isAuthenticated,
    currentUser,
    userInitials,
    handleLogout,
  };
}
