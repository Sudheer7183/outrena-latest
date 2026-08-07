/**
 * ProtectedRoute.tsx — role-gated route element.
 *
 * Wraps a set of child routes. If the user is unauthenticated, redirects to
 * `/login`. If the user's role is below `minimumRole`, redirects to
 * `/forbidden`. Uses `<Outlet />` so it composes inside `createBrowserRouter`.
 */
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import type { Role } from "@/types/common";
import { ROLE_HIERARCHY } from "@/types/common";

interface ProtectedRouteProps {
  minimumRole?: Role;
}

export function ProtectedRoute({ minimumRole = "REP" }: ProtectedRouteProps) {
  const { isAuthenticated, user, initialized } = useAuth();
  const location = useLocation();

  if (!initialized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm">Authenticating…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (ROLE_HIERARCHY[user.role] < ROLE_HIERARCHY[minimumRole]) {
    return <Navigate to="/forbidden" replace />;
  }

  return <Outlet />;
}
