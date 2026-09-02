import { useEffect, useState } from "react";
import { RouterProvider } from "react-router-dom";
import { appRouter } from "@/app/router";
import { useAppDispatch } from "@/store/hooks";
import { checkAuthStatus, expireSession } from "@/store/slices/userSlice";
import { Loader2 } from "lucide-react";
import {
  AUTH_SESSION_EXPIRED_EVENT,
  getAuthToken,
} from "@/lib/authToken";
import { ROUTES } from "@/lib/constants";

function App() {
  const dispatch = useAppDispatch();
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = getAuthToken();
      if (!token) {
        setIsInitializing(false);
        return;
      }

      try {
        await dispatch(checkAuthStatus()).unwrap();
      } catch (error) {
        // 即使检查失败（未登录），也视为初始化完成
        console.log("Auth check failed (expected if not logged in):", error);
      } finally {
        setIsInitializing(false);
      }
    };
    initAuth();
  }, [dispatch]);

  useEffect(() => {
    const handleSessionExpired = () => {
      dispatch(expireSession());
      void appRouter.navigate(ROUTES.auth, { replace: true });
    };
    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => {
      window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, [dispatch]);

  if (isInitializing) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-white">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return <RouterProvider router={appRouter} />;
}

export default App;
