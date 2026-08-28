import { Navigate, Outlet, useLocation } from "react-router-dom";
import { AuthLoading, useAuth } from "@/features/auth/context";

export function AuthGuard() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "UNKNOWN" || status === "REFRESHING") return <AuthLoading />;
  if (status !== "AUTHENTICATED") {
    return <Navigate to="/auth" replace state={{ from: location }} />;
  }
  return <Outlet />;
}
