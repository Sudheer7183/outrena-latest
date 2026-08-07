/**
 * DsrStatusPage.tsx — public DSR status lookup.
 *
 * Mounted at `/p/gdpr-status` (no auth, inside <PublicLayout>). Reads
 * `?dsr_id=` query param to pre-populate, then calls
 * `GET /api/v1/gdpr/dsr/{dsr_id}/status` → renders the status card.
 *
 * Also offers a manual lookup form.
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  Clock,
  Download,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { gdprApi } from "@/services/apiClient";
import type { DsrStatus } from "@/types/common";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

function statusVariant(
  status: DsrStatus,
): "default" | "secondary" | "success" | "warning" | "destructive" {
  switch (status) {
    case "pending":
      return "warning";
    case "processing":
      return "default";
    case "completed":
      return "success";
    case "rejected":
      return "destructive";
    case "cancelled":
      return "secondary";
    default:
      return "secondary";
  }
}

function StatusIcon({ status }: { status: DsrStatus }) {
  if (status === "completed") return <CheckCircle2 className="h-6 w-6 text-emerald-600" />;
  if (status === "rejected" || status === "cancelled")
    return <XCircle className="h-6 w-6 text-red-600" />;
  return <Clock className="h-6 w-6 text-amber-500" />;
}

export function DsrStatusPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [dsrId, setDsrId] = useState(searchParams.get("dsr_id") ?? "");

  const enabled = dsrId.trim().length > 0;

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["public", "dsr-status", dsrId.trim()],
    queryFn: () => gdprApi.dsrStatus(dsrId.trim()),
    enabled,
  });

  // Keep URL in sync so users can share the link.
  useEffect(() => {
    if (dsrId) {
      const next = new URLSearchParams(searchParams);
      next.set("dsr_id", dsrId.trim());
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dsrId]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!dsrId.trim()) return;
    refetch();
  }

  return (
    <div>
      <section className="border-b bg-card">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          >
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5" />
              GDPR · Request Status
            </div>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Check Your DSR Status
            </h1>
            <p className="mt-3 max-w-2xl text-base text-muted-foreground">
              Enter the reference number you received when you submitted your
              Data Subject Request to see its current status.
            </p>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        <Card>
          <CardHeader>
            <CardTitle>Look up request</CardTitle>
            <CardDescription>
              Your reference number was emailed to you when you submitted the
              request.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="dsr-id-lookup">Reference number</Label>
                <Input
                  id="dsr-id-lookup"
                  placeholder="dsr-xxxxxxxxxxxx"
                  value={dsrId}
                  onChange={(e) => setDsrId(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" disabled={!dsrId.trim() || isFetching}>
                <Search className="h-4 w-4" />
                Check status
              </Button>
            </form>
          </CardContent>
        </Card>

        {enabled && data && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="mt-6"
          >
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <StatusIcon status={data.status} />
                  <div>
                    <p className="text-lg font-semibold capitalize">
                      {data.status}
                    </p>
                    <p className="text-xs font-normal text-muted-foreground">
                      Reference: <span className="font-mono">{dsrId}</span>
                    </p>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-md border p-3">
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">
                      Status
                    </p>
                    <Badge variant={statusVariant(data.status)} className="mt-1 capitalize">
                      {data.status}
                    </Badge>
                  </div>
                  <div className="rounded-md border p-3">
                    <p className="text-xs uppercase tracking-wider text-muted-foreground">
                      Completed
                    </p>
                    <p className="mt-1 text-xs">
                      {data.completed_at
                        ? new Date(data.completed_at).toLocaleString()
                        : "—"}
                    </p>
                  </div>
                </div>

                {data.rejection_reason && (
                  <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-700 dark:text-red-300">
                    <p className="font-medium">Rejection reason:</p>
                    <p>{data.rejection_reason}</p>
                  </div>
                )}

                {data.export_url && (
                  <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3">
                    <p className="font-medium text-emerald-700 dark:text-emerald-300">
                      Your data export is ready
                    </p>
                    <a
                      href={data.export_url}
                      className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Download export
                    </a>
                  </div>
                )}

                <p className="text-xs text-muted-foreground">
                  {data.status === "pending" &&
                    "Your request is in our queue and will be picked up shortly."}
                  {data.status === "processing" &&
                    "Our team is actively working on your request."}
                  {data.status === "completed" &&
                    "Your request has been fulfilled. The export link above (if any) is valid for 14 days."}
                  {data.status === "rejected" &&
                    "Your request was rejected. See the reason above or contact dpo@outrena.io."}
                  {data.status === "cancelled" &&
                    "Your request was cancelled at your request."}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {enabled && !isLoading && !data && (
          <Card className="mt-6 border-l-4 border-l-amber-500">
            <CardContent className="p-4 text-sm text-muted-foreground">
              No request found for that reference number. Double-check the ID
              and try again, or contact{" "}
              <a
                href="mailto:dpo@outrena.io"
                className="font-medium text-foreground hover:underline"
              >
                dpo@outrena.io
              </a>
              .
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
