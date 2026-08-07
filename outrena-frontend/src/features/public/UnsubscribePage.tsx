/**
 * UnsubscribePage.tsx — One-click unsubscribe confirmation page (/p/unsubscribe).
 *
 * Reads ?token=… and ?tenant_slug=… from the URL and calls
 * POST /api/v1/public/unsubscribe. Shows a clean confirmation.
 * No login required (FR-E14-018 / NFR-18).
 */
import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { publicUnsubscribeApi } from "@/services/apiClient";

export function UnsubscribePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const tenantSlug = params.get("tenant_slug") ?? "";
  const [state, setState] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token || !tenantSlug) {
      setState("error");
      setMessage("Invalid unsubscribe link — the link may be expired or malformed.");
      return;
    }
    publicUnsubscribeApi(token, tenantSlug)
      .then((res) => {
        setState("success");
        setMessage(res.message ?? "You have been unsubscribed successfully.");
      })
      .catch(() => {
        setState("error");
        setMessage("Something went wrong. Please try again or contact support.");
      });
  }, [token, tenantSlug]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
      <div className="w-full max-w-md rounded-2xl border bg-white dark:bg-slate-900 p-10 text-center shadow-lg">
        {state === "loading" && (
          <>
            <Loader2 className="mx-auto h-10 w-10 animate-spin text-muted-foreground" />
            <p className="mt-4 text-sm text-muted-foreground">Processing your request…</p>
          </>
        )}
        {state === "success" && (
          <>
            <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" />
            <h1 className="mt-4 text-xl font-semibold">You're unsubscribed</h1>
            <p className="mt-2 text-sm text-muted-foreground">{message}</p>
            <p className="mt-4 text-xs text-muted-foreground">
              You will not receive any further outreach emails from this sender.
            </p>
          </>
        )}
        {state === "error" && (
          <>
            <XCircle className="mx-auto h-12 w-12 text-destructive" />
            <h1 className="mt-4 text-xl font-semibold">Something went wrong</h1>
            <p className="mt-2 text-sm text-muted-foreground">{message}</p>
          </>
        )}
        <div className="mt-8 border-t pt-6">
          <Link to="/p" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            ← Back to OUTRENA
          </Link>
        </div>
      </div>
    </div>
  );
}
