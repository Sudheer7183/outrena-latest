/**
 * PlatformDashboardPage.tsx — SUPER_ADMIN platform metrics overview.
 *
 * Fetches `GET /admin/metrics` for the 5 KPIs (total_tenants, active_tenants,
 * total_users, mrr, churn_rate). Renders metric cards + a simple MRR bar
 * chart (divs, no chart lib) + a recent-pending-signups table.
 */
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  DollarSign,
  TrendingDown,
  Users2,
} from "lucide-react";
import { Link } from "react-router-dom";
import { platformApi } from "@/services/apiClient";
import type { PlatformMetrics } from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCurrency, formatPercent, timeAgo } from "@/lib/utils";

const MOCK_METRICS: PlatformMetrics = {
  total_tenants: 412,
  active_tenants: 386,
  total_users: 3_180,
  mrr: 184_500,
  churn_rate: 0.018,
};

// Mock MRR trend (last 6 months) for the bar chart.
const MRR_TREND = [
  { month: "Aug", mrr: 142_000 },
  { month: "Sep", mrr: 152_000 },
  { month: "Oct", mrr: 161_000 },
  { month: "Nov", mrr: 169_000 },
  { month: "Dec", mrr: 176_000 },
  { month: "Jan", mrr: 184_500 },
];

export function PlatformDashboardPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ["platform", "metrics"],
    queryFn: () => platformApi.metrics(),
  });
  const { data: signups } = useQuery({
    queryKey: ["platform", "signups", "pending"],
    queryFn: () => platformApi.signups("pending"),
  });

  const m = metrics ?? MOCK_METRICS;
  const pending = signups ?? [];
  const maxMrr = Math.max(...MRR_TREND.map((p) => p.mrr));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Dashboard"
        description="Cross-tenant metrics, MRR trend, and pending tenant signups."
      />

      {/* KPI tiles */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {isLoading
          ? Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))
          : (
            <>
              <StatCard
                label="Total Tenants"
                value={m.total_tenants.toLocaleString()}
                icon={<Building2 className="h-4 w-4" />}
                delta={{ value: "12 this month", positive: true }}
              />
              <StatCard
                label="Active Tenants"
                value={m.active_tenants.toLocaleString()}
                icon={<Activity className="h-4 w-4" />}
                delta={{
                  value: `${formatPercent(m.active_tenants / m.total_tenants)} of total`,
                  positive: true,
                }}
              />
              <StatCard
                label="Total Users"
                value={m.total_users.toLocaleString()}
                icon={<Users2 className="h-4 w-4" />}
                delta={{ value: "4.2% MoM", positive: true }}
              />
              <StatCard
                label="MRR"
                value={formatCurrency(m.mrr)}
                icon={<DollarSign className="h-4 w-4" />}
                delta={{ value: "4.8% MoM", positive: true }}
              />
              <StatCard
                label="Churn Rate"
                value={formatPercent(m.churn_rate, 2)}
                icon={<TrendingDown className="h-4 w-4" />}
                delta={{ value: "0.4pp MoM", positive: false }}
              />
            </>
          )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* MRR trend bar chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>MRR Trend</CardTitle>
            <CardDescription>Last 6 months.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-56 items-end gap-3">
              {MRR_TREND.map((p) => {
                const h = (p.mrr / maxMrr) * 100;
                return (
                  <div
                    key={p.month}
                    className="flex flex-1 flex-col items-center gap-2"
                  >
                    <div className="flex w-full flex-1 items-end">
                      <div
                        className="w-full rounded-t bg-primary transition-all"
                        style={{ height: `${h}%` }}
                        title={formatCurrency(p.mrr)}
                      />
                    </div>
                    <span className="text-xs font-medium text-muted-foreground">
                      {p.month}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Active vs total breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Tenant Health</CardTitle>
            <CardDescription>Active vs total tenants.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Active</span>
                <span className="font-semibold">{m.active_tenants}</span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-emerald-600"
                  style={{
                    width: `${(m.active_tenants / m.total_tenants) * 100}%`,
                  }}
                />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  Suspended / churned
                </span>
                <span className="font-semibold">
                  {m.total_tenants - m.active_tenants}
                </span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-red-600"
                  style={{
                    width: `${((m.total_tenants - m.active_tenants) / m.total_tenants) * 100}%`,
                  }}
                />
              </div>
            </div>
            <div className="rounded-md border bg-muted/50 p-3 text-sm">
              <p className="text-muted-foreground">Churn rate</p>
              <p className="text-lg font-bold">{formatPercent(m.churn_rate, 2)}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pending signups */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div className="space-y-1">
            <CardTitle>Pending Signups</CardTitle>
            <CardDescription>
              New tenant requests awaiting approval.
            </CardDescription>
          </div>
          <Link
            to="/platform-admin/approvals"
            className="text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            View all →
          </Link>
        </CardHeader>
        <CardContent>
          {pending.length === 0 ? (
            <EmptyState
              icon={<Building2 className="h-6 w-6" />}
              title="No pending signups"
              description="All caught up. New tenant requests will appear here."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead>
                  <TableHead>Subdomain</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pending.slice(0, 8).map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.company_name}</TableCell>
                    <TableCell className="text-muted-foreground">{s.subdomain}</TableCell>
                    <TableCell className="text-muted-foreground">{s.owner_email}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {timeAgo(s.created_at)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="warning">{s.status}</Badge>
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
