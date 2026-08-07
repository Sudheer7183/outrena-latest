/**
 * FlowRunDetailPage.tsx — FIX-FE-1
 *
 * Detail view for a single FlowRun. Shows header (status, stats, error),
 * a vertical timeline of FlowRunStep rows, and the list of imported
 * prospect IDs. Targets `GET /api/v1/flows/runs/{run_id}`.
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  Database,
  Filter,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";

import { flowsApi } from "@/services/apiClient";
import type { FlowRunStep, FlowRunStepKind, FlowRunStepStatus } from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

const STEP_ICON: Record<FlowRunStepKind, typeof Database> = {
  SOURCE: Database,
  ENRICH: Sparkles,
  QUALITY: Filter,
  SEND: Send,
};

function stepStatusVariant(
  status: FlowRunStepStatus,
): "default" | "secondary" | "destructive" | "success" | "warning" | "outline" {
  switch (status) {
    case "COMPLETED":
      return "success";
    case "RUNNING":
      return "default";
    case "PENDING":
      return "warning";
    case "FAILED":
      return "destructive";
    case "SKIPPED":
      return "outline";
    default:
      return "secondary";
  }
}

interface RunStats {
  imported?: number;
  enriched?: number;
  qualified?: number;
  [key: string]: unknown;
}

function parseJson<T>(raw: string, fallback: T): T {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function FlowRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { data: run, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["flows", "runs", runId],
    queryFn: () => flowsApi.getRun(runId as string),
    enabled: !!runId,
    retry: false,
  });

  const stats = useMemo<RunStats>(
    () => (run ? parseJson<RunStats>(run.stats, {}) : {}),
    [run],
  );
  const importedIds = useMemo<string[]>(() => {
    if (!run) return [];
    const parsed = parseJson<string[]>(run.importedProspectIds, []);
    return parsed;
  }, [run]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Flow Run Detail"
        description={run ? `Run ${run.id.slice(0, 8)}…` : "Loading run…"}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/prospecting/flows/runs">
                <ArrowLeft className="h-4 w-4" />
                Back to runs
              </Link>
            </Button>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
          </>
        }
      />

      {isError ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <p className="text-sm font-medium">Failed to load flow run</p>
            <p className="text-xs text-muted-foreground">
              {(error as Error)?.message ?? "Unknown error"}
            </p>
            <Button variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : isLoading || !run ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          {/* Header card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-3">
                <span>Run {run.id.slice(0, 8)}…</span>
                <Badge
                  variant={
                    run.status === "COMPLETED"
                      ? "success"
                      : run.status === "FAILED"
                        ? "destructive"
                        : run.status === "RUNNING"
                          ? "default"
                          : run.status === "PENDING"
                            ? "warning"
                            : "outline"
                  }
                >
                  {run.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  triggered by <code className="font-mono">{run.triggeredBy}</code>
                  {run.triggeredById ? ` (${run.triggeredById.slice(0, 8)}…)` : ""}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div>
                <p className="text-xs uppercase text-muted-foreground">Flow ID</p>
                <p className="font-mono text-xs">{run.flowId}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">ICP Profile</p>
                <p className="font-mono text-xs">{run.icpProfileId}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Started</p>
                <p>{formatDateTime(run.startedAt)}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Completed</p>
                <p>{formatDateTime(run.completedAt)}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Imported</p>
                <p className="tabular-nums">{stats.imported ?? 0}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Enriched</p>
                <p className="tabular-nums">{stats.enriched ?? 0}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Qualified</p>
                <p className="tabular-nums">{stats.qualified ?? 0}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Updated</p>
                <p>{formatDateTime(run.updatedAt)}</p>
              </div>
              {run.errorMessage && (
                <div className="col-span-2 sm:col-span-4">
                  <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <p className="font-medium">Run failed</p>
                      <p className="text-xs">{run.errorMessage}</p>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Step timeline */}
          <Card>
            <CardHeader>
              <CardTitle>Step Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {run.steps.length === 0 ? (
                <EmptyState
                  icon={<RefreshCw className="h-6 w-6" />}
                  title="No steps recorded"
                  description="This run has no FlowRunStep rows yet. Steps appear as the run progresses."
                />
              ) : (
                <ol className="relative space-y-4 border-l border-border pl-6">
                  {run.steps
                    .slice()
                    .sort((a, b) => a.order - b.order)
                    .map((s: FlowRunStep) => {
                      const Icon = STEP_ICON[s.kind] ?? Database;
                      const metrics = parseJson<Record<string, unknown>>(s.metrics, {});
                      return (
                        <li key={s.id} className="relative">
                          <span
                            className={cn(
                              "absolute -left-[1.6rem] flex h-6 w-6 items-center justify-center rounded-full border bg-background",
                              s.status === "COMPLETED"
                                ? "border-emerald-500 text-emerald-600"
                                : s.status === "FAILED"
                                  ? "border-destructive text-destructive"
                                  : s.status === "RUNNING"
                                    ? "border-primary text-primary"
                                    : "border-border text-muted-foreground",
                            )}
                          >
                            <Icon className="h-3.5 w-3.5" />
                          </span>
                          <div className="rounded-md border p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-medium">{s.stepKey}</span>
                              <Badge variant="outline">{s.kind}</Badge>
                              <Badge variant={stepStatusVariant(s.status)}>
                                {s.status}
                              </Badge>
                              {s.durationMs !== null && (
                                <span className="text-xs text-muted-foreground">
                                  {s.durationMs} ms
                                </span>
                              )}
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              Started {formatDateTime(s.startedAt)} · Completed{" "}
                              {formatDateTime(s.completedAt)}
                            </p>
                            {s.errorMessage && (
                              <p className="mt-1 text-xs text-destructive">
                                {s.errorMessage}
                              </p>
                            )}
                            {Object.keys(metrics).length > 0 && (
                              <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 font-mono text-[10px]">
                                {JSON.stringify(metrics, null, 2)}
                              </pre>
                            )}
                          </div>
                        </li>
                      );
                    })}
                </ol>
              )}
            </CardContent>
          </Card>

          {/* Imported prospects */}
          <Card>
            <CardHeader>
              <CardTitle>Imported Prospects ({importedIds.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {importedIds.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No prospects imported by this run.
                </p>
              ) : (
                <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-3">
                  {importedIds.map((id) => (
                    <li key={id} className="font-mono text-xs text-muted-foreground">
                      {id}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
