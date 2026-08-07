/**
 * ForbiddenPage.tsx — 403 page (insufficient role).
 *
 * Shown by `ProtectedRoute` when the user's role is below the required
 * minimum. Centred shield + lock icon, explanation, and a link back to the
 * Dashboard.
 */
import { Link } from "react-router-dom";
import { Home, ShieldX } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ForbiddenPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-950/40">
          <ShieldX className="h-8 w-8 text-red-600 dark:text-red-400" />
        </div>
        <p className="mb-2 text-5xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          403
        </p>
        <h1 className="mb-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
          Access Forbidden
        </h1>
        <p className="mx-auto mb-8 max-w-sm text-sm text-slate-600 dark:text-slate-400">
          Your current role does not have permission to view this page. If you
          believe this is a mistake, ask a tenant admin to upgrade your role.
        </p>
        <Link to="/" className="inline-block">
          <Button>
            <Home className="h-4 w-4" />
            Back to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
