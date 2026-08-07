/**
 * AuditLogsPage.tsx — platform-wide audit log viewer (SUPER_ADMIN).
 *
 * Fetches `GET /admin/audit-logs?limit=&tenant_slug=&action=`. Filter by
 * tenant_slug + action + limit selector. Read-only table.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, ScrollText } from "lucide-react";
import { platformApi } from "@/services/apiClient";
import type { AuditLog as AuditLogType } from "@/types/common";
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

export function AuditLogsPage() {
  const [limit, setLimit] = useState("100");
  const [tenantSlug, setTenantSlug] = useState("");
  const [action, setAction] = useState("");

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["platform", "audit-logs", { limit, tenantSlug, action }],
    queryFn: () =>
      platformApi.auditLogs({
        limit: Number(limit),
        tenant_slug: tenantSlug || undefined,
        action: action || undefined,
      }),
  });

  const logs = data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Audit Logs"
        description="Cross-tenant audit trail. Read-only — filters narrow the view."
        actions={
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>
            Combine tenant + action + limit to narrow the view.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Tenant slug
              </label>
              <Input
                placeholder="e.g. acme"
                value={tenantSlug}
                onChange={(e) => setTenantSlug(e.target.value)}
              />
            </div>
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
                Limit
              </label>
              <Select
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
              >
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
                  <TableHead>Tenant</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log: AuditLogType) => (
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
                    <TableCell className="text-muted-foreground">
                      {log.tenant_slug ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{log.action}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {log.target_type ? `${log.target_type}:` : ""}
                      {log.target_id ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {log.ip_address ?? "—"}
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
