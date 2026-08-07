/**
 * RetentionPolicyViewer.tsx — retention policy viewer + enforce action.
 *
 * Used by:
 *   - GdprCenterPage (TENANT_ADMIN) as the "Retention" tab
 *   - Anywhere else that wants to surface retention policies
 *
 * Fetches GET /api/v1/gdpr/retention-status → RetentionStatus.
 * Mutation: POST /api/v1/gdpr/retention/enforce → trigger immediate purge.
 *
 * Accepts a `fallbackData` prop so callers can supply mock data for offline
 * rendering; if the API call succeeds it overrides the fallback.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, PlayCircle, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { gdprApi } from "@/services/apiClient";
import type { RetentionStatus } from "@/types/common";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime } from "@/lib/utils";

export function RetentionPolicyViewer({
  fallbackData,
}: {
  fallbackData: RetentionStatus;
}) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["gdpr", "retention-status"],
    queryFn: () => gdprApi.retentionStatus(),
  });

  const enforceMutation = useMutation({
    mutationFn: () => gdprApi.enforceRetention(),
    onSuccess: (res) => {
      toast.success(
        `Retention enforcement complete · ${res?.pending_purge_count ?? 0} records affected`,
      );
      queryClient.invalidateQueries({
        queryKey: ["gdpr", "retention-status"],
      });
    },
    onError: () => toast.error("Failed to enforce retention"),
  });

  const status: RetentionStatus = data ?? fallbackData;
  const policies = status.policies ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Enforcement Status
          </CardTitle>
          <CardDescription>
            Last enforcement run + pending purge queue. Auto-purge runs daily
            at 03:00 UTC.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-md border p-3">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Last enforced
            </p>
            <p className="mt-0.5 text-sm">
              {status.last_enforced_at ? formatDateTime(status.last_enforced_at) : "—"}
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Pending purge count
            </p>
            <p className="mt-0.5 text-lg font-bold">
              {/* BUG-32 FIX: guard undefined before toLocaleString */}
              {status?.pending_purge_count != null ? status.pending_purge_count.toLocaleString() : "—"}
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Next scheduled run
            </p>
            <p className="mt-0.5 text-sm">
              {status.next_run_at ? formatDateTime(status.next_run_at) : "—"}
            </p>
          </div>
          <div className="sm:col-span-3 flex justify-end">
            <Button
              variant="outline"
              onClick={() => enforceMutation.mutate()}
              disabled={enforceMutation.isPending}
            >
              <PlayCircle className="h-4 w-4" />
              {enforceMutation.isPending ? "Enforcing…" : "Enforce now"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            Retention Policies
          </CardTitle>
          <CardDescription>
            Per-data-category retention periods + auto-purge behavior.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : policies.length === 0 ? (
            <EmptyState
              icon={<Trash2 className="h-6 w-6" />}
              title="No retention policies"
              description="Retention policies will appear here once configured."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Category</TableHead>
                  <TableHead>Retention</TableHead>
                  <TableHead>Auto-purge</TableHead>
                  <TableHead>Description</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {policies.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">
                      {p.data_category}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{p.retention_days} days</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.auto_purge ? "success" : "secondary"}>
                        {p.auto_purge ? "Auto" : "Manual"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {p.description ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
