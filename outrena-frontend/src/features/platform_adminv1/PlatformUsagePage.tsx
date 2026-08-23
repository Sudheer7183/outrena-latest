/**
 * PlatformUsagePage.tsx — SUPER_ADMIN cross-tenant usage + cost dashboard.
 *
 * Under <PlatformAdminLayout>. Mounted at `/platform-admin/usage`.
 *
 * Fetches GET /api/v1/usage/platform?period=YYYY-MM → cross-tenant rollup.
 * Renders:
 *   - Total platform cost StatCard
 *   - Cost per tenant (bar)
 *   - Top tenants by cost (table)
 *   - Cost trend (line)
 *   - Period selector
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Building2, DollarSign, TrendingUp } from "lucide-react";
import { usageApi } from "@/services/apiClient";
import type { UsagePlatformRollup } from "@/types/common";
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
import { NativeSelect as Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCurrency } from "@/lib/utils";

function currentPeriod(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function lastNPeriods(n: number): string[] {
  const out: string[] = [];
  const d = new Date();
  for (let i = 0; i < n; i++) {
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
    d.setMonth(d.getMonth() - 1);
  }
  return out;
}

const MOCK: UsagePlatformRollup = {
  total_cost_cents: 1_284_500,
  per_tenant: [
    { tenant_slug: "acme", tenant_name: "Acme Inc.", cost_cents: 412_000, events: 28_410 },
    { tenant_slug: "globex", tenant_name: "Globex Corp.", cost_cents: 318_500, events: 22_120 },
    { tenant_slug: "initech", tenant_name: "Initech", cost_cents: 184_200, events: 12_080 },
    { tenant_slug: "umbrella", tenant_name: "Umbrella LLC", cost_cents: 162_400, events: 10_280 },
    { tenant_slug: "hooli", tenant_name: "Hooli", cost_cents: 118_900, events: 8_120 },
    { tenant_slug: "stark", tenant_name: "Stark Industries", cost_cents: 88_500, events: 6_410 },
  ],
  daily: Array.from({ length: 28 }).map((_, i) => ({
    date: `2025-02-${String(i + 1).padStart(2, "0")}`,
    cost_cents: 20_000 + Math.round(Math.sin(i / 3) * 4_000 + (i % 7) * 1_500),
  })),
};

function centsToUsd(cents: number): number {
  return cents / 100;
}

export function PlatformUsagePage() {
  const [period, setPeriod] = useState<string>(currentPeriod());
  const periods = useMemo(() => lastNPeriods(12), []);

  const { data, isLoading } = useQuery({
    queryKey: ["usage", "platform", period],
    queryFn: () => usageApi.platform(period),
  });

  const rollup = data ?? MOCK;
  const totalUsd = centsToUsd(rollup.total_cost_cents);
  const perTenantUsd = rollup.per_tenant.map((t) => ({
    ...t,
    cost_usd: centsToUsd(t.cost_cents),
  }));
  const dailyUsd = rollup.daily.map((d) => ({
    date: d.date,
    cost_usd: centsToUsd(d.cost_cents),
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Usage"
        description="Cross-tenant cost + usage rollup across all OUTRENA customers."
        actions={
          <Select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="w-36"
          >
            {periods.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))
        ) : (
          <>
            <StatCard
              label="Total platform cost"
              value={formatCurrency(totalUsd, true)}
              icon={<DollarSign className="h-4 w-4" />}
              delta={{ value: "this period", positive: false }}
            />
            <StatCard
              label="Total events"
              value={rollup.per_tenant
                .reduce((s, t) => s + t.events, 0)
                .toLocaleString()}
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatCard
              label="Active tenants"
              value={rollup.per_tenant.length.toLocaleString()}
              icon={<Building2 className="h-4 w-4" />}
            />
            <StatCard
              label="Top tenant"
              value={perTenantUsd[0]?.tenant_name ?? "—"}
              icon={<Building2 className="h-4 w-4" />}
              delta={
                perTenantUsd[0]
                  ? {
                      value: formatCurrency(perTenantUsd[0].cost_usd, true),
                      positive: false,
                    }
                  : undefined
              }
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Cost per Tenant</CardTitle>
            <CardDescription>Spend by tenant this period.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={perTenantUsd} margin={{ left: -12, right: 12, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="tenant_slug"
                    tick={{ fontSize: 11 }}
                    stroke="#94a3b8"
                  />
                  <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#ffffff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(value: number) =>
                      formatCurrency(value, true)
                    }
                  />
                  <Bar
                    dataKey="cost_usd"
                    name="Cost (USD)"
                    fill="#10b981"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Platform Cost Trend</CardTitle>
            <CardDescription>Daily platform cost (USD).</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyUsd} margin={{ left: -12, right: 12, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: string) => v.slice(5)}
                    stroke="#94a3b8"
                  />
                  <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#ffffff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="cost_usd"
                    name="Cost (USD)"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top Tenants by Cost</CardTitle>
          <CardDescription>Tenant spend + event count.</CardDescription>
        </CardHeader>
        <CardContent>
          {perTenantUsd.length === 0 ? (
            <EmptyState
              icon={<Building2 className="h-6 w-6" />}
              title="No tenant data"
              description="Tenant-level cost will appear here once tenants start using the platform."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tenant</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead className="text-right">Events</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {perTenantUsd.map((t) => (
                  <TableRow key={t.tenant_slug}>
                    <TableCell className="font-medium">{t.tenant_name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {t.tenant_slug}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {t.events.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(t.cost_usd, true)}
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
