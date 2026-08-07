/**
 * AuditLogPage.tsx — tenant-scoped audit log viewer (TENANT_ADMIN).
 *
 * Fetches `GET /audit-logs?limit=`. Filter by action + date range. Export CSV
 * button (structural). Read-only table. Distinct from
 * `platform_admin/AuditLogsPage.tsx` (cross-tenant, SUPER_ADMIN).
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, RefreshCw, ScrollText } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import type { AuditLog } from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { NativeSelect as Select } from "@/components/ui/select";
import { formatDateTime } from "@/lib/utils";

export function AuditLogPage() {
  const [limit, setLimit] = useState("100");
  const [action, setAction] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["audit-logs", { limit, action, startDate, endDate }],
    queryFn: () =>
      http.get<AuditLog[]>("/api/v1/audit-logs", {
        limit: Number(limit),
        action: action || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      }),
  });

  const logs = data ?? [];

  function exportCsv() {
    if (logs.length === 0) {
      toast.error("Nothing to export");
      return;
    }
    const headers = [
      "time",
      "actor_user_id",
      "actor_role",
      "action",
      "target_type",
      "target_id",
      "tenant_slug",
      "ip_address",
      "request_id",
    ];
    const rows = logs.map((l) => [
      l.created_at,
      l.actor_user_id ?? "",
      l.actor_role ?? "",
      l.action,
      l.target_type ?? "",
      l.target_id ?? "",
      l.tenant_slug ?? "",
      l.ip_address ?? "",
      l.request_id ?? "",
    ]);
    const csv = [headers, ...rows]
      .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`Exported ${logs.length} rows to CSV`);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Logs"
        description="Tenant-scoped audit trail of all administrative and user actions."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={exportCsv} disabled={logs.length === 0}>
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              Refresh
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>
            Narrow by action, date range, or limit. Filters apply on next
            refresh.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Action
              </label>
              <Input
                placeholder="e.g. user.invite"
                value={action}
                onChange={(e) => setAction(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Start date
              </label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                End date
              </label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Limit
              </label>
              <Select value={limit} onChange={(e) => setLimit(e.target.value)}>
                <option value="50">50 rows</option>
                <option value="100">100 rows</option>
                <option value="250">250 rows</option>
                <option value="500">500 rows</option>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Events</CardTitle>
          <CardDescription>
            Showing {logs.length} event{logs.length === 1 ? "" : "s"}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : logs.length === 0 ? (
            <EmptyState
              icon={<ScrollText className="h-6 w-6" />}
              title="No audit events"
              description="Adjust filters or refresh to load events."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>IP</TableHead>
                  <TableHead>Request ID</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(log.created_at)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {log.actor_user_id ?? "system"}
                    </TableCell>
                    <TableCell>
                      {log.actor_role && (
                        <Badge variant="secondary">{log.actor_role}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{log.action}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {log.target_type ? `${log.target_type}:` : ""}
                      {log.target_id ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {log.ip_address ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {log.request_id ? log.request_id.slice(0, 8) : "—"}
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
