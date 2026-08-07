/**
 * UsagePage.tsx — tenant usage + cost dashboard (REP+).
 *
 * Mounted at `/usage` (REP sees own, MANAGER+ sees tenant + per-user). Fetches:
 *   - GET /api/v1/usage/me?period=YYYY-MM (REP)
 *   - GET /api/v1/usage/manager?period=YYYY-MM (MANAGER+) — tenant rollup + per-user
 *
 * Renders:
 *   - Cost summary card (total this period)
 *   - Cost breakdown by event_type (bar chart)
 *   - Cost trend over time (line chart)
 *   - Cost by provider (donut / bar)
 *   - Per-user cost table (MANAGER+ only)
 *   - Period selector (month) + CSV export
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Download, DollarSign, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { usageApi } from "@/services/apiClient";
import type {
  UsageBreakdownRow,
  UsageManagerRollup,
  UsageSummary,
} from "@/types/common";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { StatCard } from "@/components/ui/stat-card";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
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

const PIE_COLORS = ["#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899"];

function currentPeriod(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function lastNPeriods(n: number): string[] {
  const out: string[] = [];
  const d = new Date();
  for (let i = 0; i < n; i++) {
    out.push(
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
    );
    d.setMonth(d.getMonth() - 1);
  }
  return out;
}

const MOCK_USAGE: UsageSummary = {
  total_cost_cents: 184_50,
  breakdown: [
    { event_type: "llm_completion", provider: "openai", quantity: 1_840_000, cost_cents: 9_200 },
    { event_type: "llm_completion", provider: "anthropic", quantity: 320_000, cost_cents: 4_800 },
    { event_type: "email_send", provider: "sendgrid", quantity: 28_410, cost_cents: 1_420 },
    { event_type: "enrichment", provider: "apollo", quantity: 5_120, cost_cents: 2_560 },
    { event_type: "linkedin_action", provider: "linkedin", quantity: 1_280, cost_cents: 470 },
  ],
  daily: Array.from({ length: 28 }).map((_, i) => ({
    date: `2025-02-${String(i + 1).padStart(2, "0")}`,
    cost_cents: 200 + Math.round(Math.sin(i / 3) * 120 + (i % 7) * 60),
  })),
};

const MOCK_MANAGER_ROLLUP: UsageManagerRollup = {
  ...MOCK_USAGE,
  per_user: [
    { user_id: "u-1", user_name: "Amelia Chen", cost_cents: 4_120, events: 1_840 },
    { user_id: "u-2", user_name: "Marcus Lee", cost_cents: 3_890, events: 1_720 },
    { user_id: "u-3", user_name: "Priya Nair", cost_cents: 2_120, events: 920 },
    { user_id: "u-4", user_name: "Diego Santos", cost_cents: 1_840, events: 810 },
    { user_id: "u-5", user_name: "Yuki Tanaka", cost_cents: 980, events: 440 },
    { user_id: "u-6", user_name: "Sam Rivera", cost_cents: 4_410, events: 2_120 },
    { user_id: "u-7", user_name: "Other Users", cost_cents: 1_090, events: 480 },
  ],
};

function centsToUsd(cents: number): number {
  return cents / 100;
}

function exportCsv(
  summary: UsageSummary,
  perUser: UsageManagerRollup["per_user"] | undefined,
) {
  const rows: string[][] = [];
  rows.push(["Section", "Event type", "Provider", "Quantity", "Cost USD"]);
  for (const b of (summary.breakdown ?? [])) {
    rows.push([
      "Breakdown",
      b.event_type,
      b.provider,
      String(b.quantity),
      centsToUsd(b.cost_cents).toFixed(2),
    ]);
  }
  rows.push([]);
  rows.push(["Daily", "", "", "Date", "Cost USD"]);
  for (const d of (summary.daily ?? [])) {
    rows.push(["Daily", "", "", d.date, centsToUsd(d.cost_cents).toFixed(2)]);
  }
  if (perUser && perUser.length > 0) {
    rows.push([]);
    rows.push(["Per user", "", "", "User", "Cost USD"]);
    for (const u of perUser) {
      rows.push([
        "Per user",
        "",
        "",
        u.user_name,
        centsToUsd(u.cost_cents).toFixed(2),
      ]);
    }
  }
  const csv = rows
    .map((r) => r.map((c) => `"${(c ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `usage-${currentPeriod()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  toast.success("CSV exported");
}

export function UsagePage() {
  const { user } = useAuth();
  const isManager = !!user && ["MANAGER", "TENANT_ADMIN", "SUPER_ADMIN"].includes(user.role);

  const [period, setPeriod] = useState<string>(currentPeriod());
  const periods = useMemo(() => lastNPeriods(12), []);

  const meQuery = useQuery({
    queryKey: ["usage", "me", period],
    queryFn: () => usageApi.me(period),
    enabled: !isManager,
  });

  const managerQuery = useQuery({
    queryKey: ["usage", "manager", period],
    queryFn: () => usageApi.manager(period),
    enabled: isManager,
  });

  const isLoading = isManager ? managerQuery.isLoading : meQuery.isLoading;
  const summary: UsageSummary = isManager
    ? (managerQuery.data ?? MOCK_MANAGER_ROLLUP)
    : (meQuery.data ?? MOCK_USAGE);
  const perUser = isManager
    ? (managerQuery.data?.per_user ?? MOCK_MANAGER_ROLLUP.per_user)
    : undefined;

  // Safe accessors — API may return null/undefined when no usage recorded yet
  const breakdown = Array.isArray(summary?.breakdown) ? summary.breakdown : [];
  const daily = Array.isArray(summary?.daily) ? summary.daily : [];

  // Aggregate breakdown by event_type for chart
  const byEventType = useMemo(() => {
    const map = new Map<string, number>();
    for (const b of breakdown) {
      map.set(b.event_type, (map.get(b.event_type) ?? 0) + b.cost_cents);
    }
    return Array.from(map.entries()).map(([event_type, cost_cents]) => ({
      event_type,
      cost_cents,
      cost_usd: centsToUsd(cost_cents),
    }));
  }, [breakdown]);

  const byProvider = useMemo(() => {
    const map = new Map<string, number>();
    for (const b of breakdown) {
      map.set(b.provider, (map.get(b.provider) ?? 0) + b.cost_cents);
    }
    return Array.from(map.entries()).map(([provider, cost_cents]) => ({
      provider,
      cost_cents,
      cost_usd: centsToUsd(cost_cents),
    }));
  }, [breakdown]);

  const dailyUsd = useMemo(
    () =>
      daily.map((d) => ({
        date: d.date,
        cost_usd: centsToUsd(d.cost_cents),
      })),
    [daily],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Usage & Cost"
        description={
          isManager
            ? "Tenant-wide usage and cost breakdown across users, providers, and event types."
            : "Your personal usage and cost breakdown for the selected period."
        }
        actions={
          <div className="flex items-center gap-2">
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportCsv(summary, perUser)}
            >
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </div>
        }
      />

      {/* Cost summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))
        ) : (
          <>
            <StatCard
              label="Total cost (this period)"
              value={formatCurrency(centsToUsd(summary.total_cost_cents), true)}
              icon={<DollarSign className="h-4 w-4" />}
              delta={{ value: "vs prior period", positive: false }}
            />
            <StatCard
              label="Total events"
              value={(summary.breakdown ?? [])
                .reduce((s: number, b: { quantity: number }) => s + (b.quantity ?? 0), 0)
                .toLocaleString()}  /* BUG-08 FIX: guard against undefined breakdown */
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatCard
              label="Top event type"
              value={byEventType[0]?.event_type ?? "—"}
              icon={<TrendingUp className="h-4 w-4" />}
              delta={
                byEventType[0]
                  ? {
                      value: formatCurrency(centsToUsd(byEventType[0].cost_cents), true),
                      positive: false,
                    }
                  : undefined
              }
            />
            <StatCard
              label="Top provider"
              value={byProvider[0]?.provider ?? "—"}
              icon={<TrendingUp className="h-4 w-4" />}
              delta={
                byProvider[0]
                  ? {
                      value: formatCurrency(centsToUsd(byProvider[0].cost_cents), true),
                      positive: false,
                    }
                  : undefined
              }
            />
          </>
        )}
      </div>

      {/* Cost trend + breakdown by event type */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Cost Trend</CardTitle>
            <CardDescription>Daily cost (USD) over the period.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyUsd} margin={{ left: -12, right: 12, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
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
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Cost by Event Type</CardTitle>
            <CardDescription>
              Breakdown of cost across event categories.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byEventType} layout="vertical" margin={{ left: 60, right: 12, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                  <XAxis type="number" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                  <YAxis
                    type="category"
                    dataKey="event_type"
                    tick={{ fontSize: 11 }}
                    stroke="#94a3b8"
                    width={120}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#ffffff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="cost_usd" name="Cost (USD)" fill="#10b981" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Cost by provider pie + per-user table */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Cost by Provider</CardTitle>
            <CardDescription>Share of spend per provider.</CardDescription>
          </CardHeader>
          <CardContent>
            {byProvider.length === 0 ? (
              <EmptyState
                title="No provider data"
                description="Provider spend will appear here once usage events are recorded."
              />
            ) : (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={byProvider}
                      dataKey="cost_cents"
                      nameKey="provider"
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {byProvider.map((entry, idx) => (
                        <Cell
                          key={entry.provider}
                          fill={PIE_COLORS[idx % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) =>
                        formatCurrency(centsToUsd(value), true)
                      }
                      contentStyle={{
                        backgroundColor: "#ffffff",
                        border: "1px solid #e2e8f0",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {isManager ? (
          <Card>
            <CardHeader>
              <CardTitle>Per-User Cost</CardTitle>
              <CardDescription>
                Top users by cost this period (MANAGER+ view).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!perUser || perUser.length === 0 ? (
                <EmptyState
                  title="No per-user data"
                  description="Per-user cost will appear here once usage events are recorded."
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead className="text-right">Events</TableHead>
                      <TableHead className="text-right">Cost</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {perUser.slice(0, 8).map((u) => (
                      <TableRow key={u.user_id}>
                        <TableCell className="font-medium">{u.user_name}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {u.events.toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatCurrency(centsToUsd(u.cost_cents), true)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Breakdown Detail</CardTitle>
              <CardDescription>
                Cost per event type + provider pair.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Event type</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead className="text-right">Quantity</TableHead>
                    <TableHead className="text-right">Cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.breakdown.map((b: UsageBreakdownRow, i) => (
                    <TableRow key={`${b.event_type}-${b.provider}-${i}`}>
                      <TableCell className="font-medium">{b.event_type}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{b.provider}</Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {b.quantity.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatCurrency(centsToUsd(b.cost_cents), true)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
