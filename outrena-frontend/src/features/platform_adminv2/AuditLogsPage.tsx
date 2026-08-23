/**
 * AuditLogsPage.tsx — SUPER_ADMIN cross-tenant audit log.
 * Mounted at /platform-admin/audit-logs.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Search } from "lucide-react";
import { platformApi } from "@/services/apiClient";
import type { AuditLog } from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime } from "@/lib/utils";

export function AuditLogsPage() {
  const [tenantFilter, setTenantFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");

  const { data: logs = [], isLoading, refetch } = useQuery<AuditLog[]>({
    queryKey: ["platform", "audit-logs", tenantFilter, actionFilter],
    queryFn: () =>
      platformApi.auditLogs({
        limit: 100,
        tenant_slug: tenantFilter || undefined,
        action: actionFilter || undefined,
      }),
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Logs"
        description="Cross-tenant platform-level activity log."
        actions={
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Refresh
          </Button>
        }
      />

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Filter by tenant slug…"
            value={tenantFilter}
            onChange={(e) => setTenantFilter(e.target.value)}
          />
        </div>
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Filter by action…"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
          />
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Events ({logs.length})</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : logs.length === 0 ? (
            <EmptyState
              icon={<Search className="h-8 w-8" />}
              title="No audit events"
              description="No events match your current filters."
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Tenant</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Target</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatDateTime(log.created_at)}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {log.tenant_slug ?? "—"}
                      </TableCell>
                      <TableCell className="text-xs">
                        {log.actor_user_id?.slice(0, 8) ?? "system"}
                      </TableCell>
                      <TableCell className="text-xs">
                        {log.actor_role ?? "—"}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {log.action}
                      </TableCell>
                      <TableCell className="text-xs">
                        {log.target_type && log.target_id
                          ? `${log.target_type}:${log.target_id}`
                          : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}