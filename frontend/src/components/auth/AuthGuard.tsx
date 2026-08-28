import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAppSelector } from "@/store/hooks";
import { ROUTES } from "@/lib/constants";

export default function AuthGuard() {
  const { isAuthenticated } = useAppSelector((state) => state.user);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.auth} state={{ from: location }} replace />;
  }

  return <Outlet />;
}
