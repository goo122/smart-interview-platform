import { useEffect, useState } from "react";
import { RouterProvider } from "react-router-dom";
import { appRouter } from "@/app/router";
import { useAppDispatch } from "@/store/hooks";
import { checkAuthStatus } from "@/store/slices/userSlice";
import { Loader2 } from "lucide-react";
import { getAuthToken } from "@/lib/authToken";

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
