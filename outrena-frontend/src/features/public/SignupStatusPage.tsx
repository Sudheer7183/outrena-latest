/**
 * SignupStatusPage.tsx — polls tenant signup approval status.
 *
 * Fetches `GET /tenant-signup/{id}/status` every 5s. Renders:
 *   - pending_approval / provisioning → spinner + "we're provisioning" message
 *   - approved → "workspace ready" + login link at https://{tenant_slug}.outrena.app
 *   - rejected → reason + contact support link
 *
 * Auto-stops polling once a terminal status (approved / rejected) is reached.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { publicApi } from "@/services/apiClient";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const DOMAIN_HINT = "outrena.app";

export function SignupStatusPage() {
  const { id } = useParams<{ id: string }>();
  const [polling, setPolling] = useState(true);

  const { data, isError } = useQuery({
    queryKey: ["public", "signup-status", id],
    queryFn: () => publicApi.signupStatus(id as string),
    enabled: !!id,
    refetchInterval: polling ? 5_000 : false,
    refetchIntervalInBackground: false,
  });

  // Stop polling on terminal status.
  useEffect(() => {
    if (data?.status === "approved" || data?.status === "rejected") {
      setPolling(false);
    }
  }, [data?.status]);

  const status = data?.status ?? "pending_approval";
  const loginUrl = data?.tenant_slug
    ? `https://${data.tenant_slug}.${DOMAIN_HINT}/login`
    : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="w-full max-w-md"
      >
        <Card>
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full">
              {status === "approved" ? (
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300">
                  <CheckCircle2 className="h-8 w-8" />
                </div>
              ) : status === "rejected" ? (
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-950/40 dark:text-red-300">
                  <AlertCircle className="h-8 w-8" />
                </div>
              ) : (
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
                  <Clock className="h-8 w-8" />
                </div>
              )}
            </div>
            <CardTitle>
              {status === "approved" && "Your workspace is ready! 🎉"}
              {status === "rejected" && "Signup not approved"}
              {(status === "pending_approval" || status === "provisioning") &&
                "Provisioning your workspace…"}
            </CardTitle>
            <CardDescription>
              {status === "approved" &&
                "Your OUTRENA tenant has been provisioned. You can now sign in and start your outreach."}
              {status === "rejected" &&
                "We weren't able to approve this signup. See the reason below."}
              {(status === "pending_approval" || status === "provisioning") &&
                "This page will update automatically when your workspace is ready. It usually takes 1–5 minutes."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isError && (
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-700 dark:text-red-300">
                Couldn't load signup status. Check your link or contact
                support.
              </div>
            )}

            {status === "rejected" && data?.rejection_reason && (
              <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
                <p className="font-semibold">Reason:</p>
                <p className="mt-1">{data.rejection_reason}</p>
              </div>
            )}

            {(status === "pending_approval" || status === "provisioning") && (
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Polling every 5 seconds…
              </div>
            )}

            {status === "approved" && loginUrl && (
              <div className="space-y-3">
                <div className="rounded-md border bg-muted/50 p-3 text-sm">
                  <p className="font-medium">Your workspace URL:</p>
                  <a
                    href={loginUrl}
                    className="mt-1 flex items-center gap-1.5 break-all text-primary hover:underline"
                  >
                    {loginUrl}
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                </div>
                <Button asChild className="w-full">
                  <a href={loginUrl}>
                    Go to my workspace <ArrowRight className="h-4 w-4" />
                  </a>
                </Button>
              </div>
            )}

            {status === "rejected" && (
              <Button asChild variant="outline" className="w-full">
                <Link to="/p/contact">Contact support</Link>
              </Button>
            )}

            <Button asChild variant="ghost" className="w-full">
              <Link to="/p">Back to home</Link>
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
