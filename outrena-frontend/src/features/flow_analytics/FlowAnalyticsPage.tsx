/**
 * FlowAnalyticsPage.tsx — Per-flow performance dashboard.
 *
 * Shows KPI cards, funnel conversion, source-yield table, gate-pass-rate
 * table, and recent runs for a selected prospecting flow.
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Clock,
  Play,
  RefreshCw,
  TrendingUp,
  Users,
  Info,
} from "lucide-react";

import { flowAnalyticsApi, flowsApi } from "@/services/apiClient";
import type {
  FlowAnalyticsSummary,
  ProspectingFlow,
} from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/ui/stat-card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/utils";

/** Format milliseconds to human-readable duration. */
function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = (s % 60).toFixed(0);
  return `${m}m ${rem}s`;
}

/** Funnel step row for the conversion visualization. */
const FUNNEL_STEPS = [
  { key: "sourced" as const, label: "Sourced", color: "bg-blue-500" },
  { key: "deduped" as const, label: "Deduped", color: "bg-indigo-500" },
  { key: "enriched" as const, label: "Enriched", color: "bg-violet-500" },
  { key: "gated" as const, label: "Gated", color: "bg-purple-500" },
  { key: "imported" as const, label: "Imported", color: "bg-emerald-500" },
];

export function FlowAnalyticsPage() {
  const [selectedFlowId, setSelectedFlowId] = useState<string>("");

  // Fetch flows for selector
  const {
    data: flowsData,
    isLoading: flowsLoading,
  } = useQuery({
    queryKey: ["flows", "list"],
    queryFn: () => flowsApi.listFlows({ isTemplate: false }),
    retry: false,
  });
  const flows = useMemo(() => flowsData?.items ?? [], [flowsData]);

  // Auto-select first flow
  const effectiveFlowId = useMemo(() => {
    if (selectedFlowId) return selectedFlowId;
    return flows.length > 0 ? flows[0].id : "";
  }, [selectedFlowId, flows]);

  // Fetch analytics for selected flow
  const {
    data: analytics,
    isLoading: analyticsLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["flow-analytics", effectiveFlowId],
    queryFn: () => flowAnalyticsApi.get(effectiveFlowId),
    enabled: !!effectiveFlowId,
    retry: false,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Flow Analytics"
        description="Per-flow performance dashboard — KPIs, funnel conversion, source yield, and gate pass rates."
        actions={
          <>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
          </>
        }
      />

      {/* Flow selector */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium">Flow:</span>
            {flowsLoading ? (
              <Skeleton className="h-10 w-64" />
            ) : (
              <Select
                value={effectiveFlowId}
                onValueChange={setSelectedFlowId}
              >
                <SelectTrigger className="w-64">
                  <SelectValue placeholder="Select a flow…" />
                </SelectTrigger>
                <SelectContent>
                  {flows.map((f: ProspectingFlow) => (
                    <SelectItem key={f.id} value={f.id}>
                      {f.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        </CardContent>
      </Card>

      {!effectiveFlowId ? (
        <EmptyState
          icon={<BarChart3 className="h-6 w-6" />}
          title="No flow selected"
          description="Select a flow above to view its analytics."
        />
      ) : isError ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <p className="text-sm font-medium">Failed to load analytics</p>
            <p className="text-xs text-muted-foreground">
              {(error as Error)?.message ?? "Unknown error"}
            </p>
            <Button variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : analyticsLoading ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : analytics ? (
        <FlowAnalyticsContent analytics={analytics} />
      ) : null}
    </div>
  );
}

/** Inner content once analytics data is loaded. */
function FlowAnalyticsContent({
  analytics,
}: {
  analytics: FlowAnalyticsSummary;
}) {
  const { funnel } = analytics;
  const funnelMax = Math.max(funnel.sourced, 1);

  return (
    <>
      {/* KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Run Count"
          value={analytics.runCount.toLocaleString()}
          icon={<Play className="h-4 w-4" />}
        />
        <StatCard
          label="Success Rate"
          value={`${(analytics.successRate * 100).toFixed(1)}%`}
          icon={<TrendingUp className="h-4 w-4" />}
          delta={
            analytics.successRate >= 0.8
              ? { value: "Healthy", positive: true }
              : { value: "Below target", positive: false }
          }
        />
        <StatCard
          label="Avg Duration"
          value={formatDuration(analytics.avgDurationMs)}
          icon={<Clock className="h-4 w-4" />}
        />
        <StatCard
          label="Total Imported"
          value={analytics.totalImported.toLocaleString()}
          icon={<Users className="h-4 w-4" />}
        />
      </div>

      {/* Funnel conversion visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Funnel Conversion</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {FUNNEL_STEPS.map((step) => {
            const value = funnel[step.key];
            const pct = Math.round((value / funnelMax) * 100);
            const conversionFromPrev =
              step.key === "sourced"
                ? null
                : (() => {
                    const prevKey = FUNNEL_STEPS[
                      FUNNEL_STEPS.findIndex((s) => s.key === step.key) - 1
                    ]!.key;
                    const prevVal = funnel[prevKey];
                    return prevVal > 0
                      ? ((value / prevVal) * 100).toFixed(1)
                      : "—";
                  })();

            return (
              <div key={step.key} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{step.label}</span>
                  <span className="text-muted-foreground">
                    {value.toLocaleString()}
                    {conversionFromPrev !== null && (
                      <span className="ml-2 text-xs">
                        ({conversionFromPrev}% from prev)
                      </span>
                    )}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1">
                    <Progress
                      value={pct}
                      indicatorClassName={step.color}
                    />
                  </div>
                  <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
                    {pct}%
                  </span>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Source Yield table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Source Yield</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {analytics.sourceYield.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">
                No source yield data available.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Platform</TableHead>
                    <TableHead className="text-right">Runs</TableHead>
                    <TableHead className="text-right">Found</TableHead>
                    <TableHead className="text-right">After Dedup</TableHead>
                    <TableHead className="text-right">Yield %</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analytics.sourceYield.map((row, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">
                        {row.platform}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.runs}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.found}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.afterDedup}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.yieldPct.toFixed(1)}%
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Gate Pass Rate table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Gate Pass Rate</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {analytics.gatePassRates.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">
                No gate pass rate data available.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Gate</TableHead>
                    <TableHead className="text-right">Input</TableHead>
                    <TableHead className="text-right">Passed</TableHead>
                    <TableHead className="text-right">Rejected</TableHead>
                    <TableHead className="text-right">Pass Rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analytics.gatePassRates.map((row, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">
                        {row.gate}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.input}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.passed}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-red-600">
                        {row.rejected}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        <Badge
                          variant={row.passRate >= 0.5 ? "success" : "outline"}
                        >
                          {(row.passRate * 100).toFixed(1)}%
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Runs table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Runs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {analytics.recentRuns.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              No recent runs found.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Trigger</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead className="text-right">Imported</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {analytics.recentRuns.map((run) => (
                  <TableRow key={run.runId}>
                    <TableCell className="font-mono text-xs">
                      {run.runId.slice(0, 8)}
                    </TableCell>
                    <TableCell>
                      <RunStatusBadge status={run.status} />
                    </TableCell>
                    <TableCell className="text-sm">
                      {run.trigger}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(run.startedAt)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {formatDuration(run.durationMs)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {run.imported}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Inline help panel */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Info className="h-4 w-4" /> Help
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            <strong>Funnel Conversion</strong> shows the volume at each pipeline
            stage: Sourced (raw prospects from APIs) → Deduped (after
            deduplication) → Enriched (after data enrichment) → Gated (after
            quality gate filtering) → Imported (final prospects added to the
            database).
          </p>
          <p>
            <strong>Source Yield</strong> breaks down prospect yield by
            source/platform, showing how many prospects were found vs. survived
            deduplication.
          </p>
          <p>
            <strong>Gate Pass Rate</strong> shows how many prospects passed each
            quality gate. A low pass rate may indicate the gate thresholds need
            adjustment.
          </p>
        </CardContent>
      </Card>
    </>
  );
}

/** Status badge for a flow run. */
function RunStatusBadge({ status }: { status: string }) {
  const variant =
    status === "COMPLETED"
      ? "success"
      : status === "FAILED"
        ? "destructive"
        : status === "RUNNING"
          ? "default"
          : "outline";
  return <Badge variant={variant}>{status}</Badge>;
}
