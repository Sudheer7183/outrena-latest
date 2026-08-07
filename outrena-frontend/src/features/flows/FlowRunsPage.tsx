/**
 * FlowRunsPage.tsx — FIX-FE-1
 *
 * Lists FlowRun executions with status filter. Row click navigates to the
 * run detail page. Targets `GET /api/v1/flows/runs`.
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ChevronRight,
  PlayCircle,
  RefreshCw,
} from "lucide-react";

import { flowsApi } from "@/services/apiClient";
import type { FlowRun, FlowRunStatus } from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { NativeSelect as Select } from "@/components/ui/select";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDateTime } from "@/lib/utils";

const STATUSES: FlowRunStatus[] = [
  "PENDING",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
];

function statusVariant(
  status: FlowRunStatus,
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
    case "CANCELLED":
      return "outline";
    default:
      return "secondary";
  }
}

interface RunStats {
  imported?: number;
  enriched?: number;
  qualified?: number;
}

function parseStats(json: string): RunStats {
  try {
    return JSON.parse(json) as RunStats;
  } catch {
    return {};
  }
}

export function FlowRunsPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["flows", "runs", statusFilter],
    queryFn: () =>
      flowsApi.listRuns(statusFilter ? { status: statusFilter } : undefined),
    retry: false,
  });
  const runs = useMemo(() => data?.items ?? [], [data]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Flow Runs"
        description="Execution log of every ProspectingFlow run. Click a row to inspect the step timeline and imported prospects."
        actions={
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        }
      />

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="sm:w-48"
              aria-label="Filter by status"
            >
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
            <p className="text-xs text-muted-foreground">
              {data?.total ?? 0} run{(data?.total ?? 0) === 1 ? "" : "s"} total
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {isError ? (
            <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
              <p className="text-sm font-medium">Failed to load flow runs</p>
              <p className="text-xs text-muted-foreground">
                {(error as Error)?.message ?? "Unknown error"}
              </p>
              <Button variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          ) : isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : runs.length === 0 ? (
            <EmptyState
              icon={<PlayCircle className="h-6 w-6" />}
              title="No flow runs yet"
              description="Trigger an autopilot run from the Autopilot page to populate the execution log."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Flow ID</TableHead>
                  <TableHead>ICP Profile</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Triggered By</TableHead>
                  <TableHead>Started At</TableHead>
                  <TableHead>Completed At</TableHead>
                  <TableHead>Stats</TableHead>
                  <TableHead className="text-right">View</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((r: FlowRun) => {
                  const stats = parseStats(r.stats);
                  return (
                    <TableRow
                      key={r.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/prospecting/flows/runs/${r.id}`)}
                    >
                      <TableCell className="font-mono text-xs">{r.flowId}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {r.icpProfileId}
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{r.triggeredBy}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(r.startedAt)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(r.completedAt)}
                      </TableCell>
                      <TableCell className="text-xs tabular-nums">
                        <span className="text-muted-foreground">i:</span>
                        {stats.imported ?? 0}{" "}
                        <span className="text-muted-foreground">e:</span>
                        {stats.enriched ?? 0}{" "}
                        <span className="text-muted-foreground">q:</span>
                        {stats.qualified ?? 0}
                      </TableCell>
                      <TableCell className="text-right">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label="View run detail"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/prospecting/flows/runs/${r.id}`);
                              }}
                            >
                              <ChevronRight className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Open run detail page</TooltipContent>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
