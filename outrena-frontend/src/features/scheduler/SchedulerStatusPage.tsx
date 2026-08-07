/**
 * SchedulerStatusPage.tsx — FIX-FE-1 + AI feature enhancement.
 *
 * Single-card page showing the in-process scheduler status (id=1).
 * Auto-refreshes every 10s. Manual tick button with confirmation.
 * Trigger Now button that POSTs to /api/v1/scheduler/trigger.
 * Recent scheduler runs/logs table.
 * Targets `GET /api/v1/scheduler/status` + `POST /api/v1/scheduler/tick`
 * + `POST /api/v1/scheduler/trigger` + `GET /api/v1/scheduler/runs`.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Clock,
  FastForward,
  RefreshCw,
  Zap,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

import { schedulerApi } from "@/services/apiClient";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { TooltipProvider } from "@/components/ui/tooltip";
import { formatDateTime, timeAgo } from "@/lib/utils";

const AUTO_REFRESH_MS = 10_000;

/* ── Scheduler run log type ────────────────────────────────────────── */

interface SchedulerRun {
  id: string;
  startedAt: string;
  completedAt: string | null;
  status: "running" | "completed" | "failed";
  sent: number;
  skipped: number;
  durationMs: number | null;
  error: string | null;
}

// interface TriggerResponse {
//   triggered: boolean;
//   message: string;
//   runId: string | null;
// }

/* ── Page ──────────────────────────────────────────────────────────── */

export function SchedulerStatusPage() {
  const qc = useQueryClient();
  const [tickOpen, setTickOpen] = useState(false);
  const [triggerOpen, setTriggerOpen] = useState(false);
  const [maxSend, setMaxSend] = useState(50);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["scheduler", "status"],
    queryFn: () => schedulerApi.status(),
    retry: false,
  });

  const { data: runs, isLoading: runsLoading } = useQuery<SchedulerRun[]>({
    queryKey: ["scheduler", "runs"],
    queryFn: () =>
      schedulerApi.runs({ limit: 20 })
        .then((r) => r?.items ?? [])
        .catch(() => []),
    retry: false,
  });

  // Auto-refresh every 10s
  useEffect(() => {
    const id = window.setInterval(() => {
      qc.invalidateQueries({ queryKey: ["scheduler", "status"] });
      qc.invalidateQueries({ queryKey: ["scheduler", "runs"] });
    }, AUTO_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [qc]);

  const tickMut = useMutation({
    mutationFn: (body: { tenantScoped: boolean; maxSend: number }) =>
      schedulerApi.tick(body),
    onSuccess: (res) => {
      toast.success(`Tick complete — sent ${res.sent}, skipped ${res.skipped} (${res.durationMs}ms)`);
      qc.invalidateQueries({ queryKey: ["scheduler", "status"] });
      qc.invalidateQueries({ queryKey: ["scheduler", "runs"] });
      setTickOpen(false);
    },
    onError: () => toast.error("Failed to run scheduler tick"),
  });

  const triggerMut = useMutation({
    mutationFn: () => schedulerApi.trigger(),
    onSuccess: (res) => {
      toast.success(res?.message ?? "Scheduler triggered", {
        description: res?.runId ? `Run ID: ${res.runId}` : undefined,
      });
      qc.invalidateQueries({ queryKey: ["scheduler", "status"] });
      qc.invalidateQueries({ queryKey: ["scheduler", "runs"] });
      setTriggerOpen(false);
    },
    onError: () => toast.error("Failed to trigger scheduler"),
  });

  function handleTick() {
    if (maxSend < 1 || maxSend > 1000) {
      toast.error("maxSend must be between 1 and 1000");
      return;
    }
    tickMut.mutate({ tenantScoped: true, maxSend });
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="Scheduler Status"
          description="In-process scheduler that runs the sequence sender + autopilot pipeline. Auto-refreshes every 10 seconds."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button
                variant="secondary"
                onClick={() => setTriggerOpen(true)}
              >
                <Zap className="h-4 w-4" />
                Trigger Now
              </Button>
              <Button onClick={() => setTickOpen(true)}>
                <FastForward className="h-4 w-4" />
                Run tick now
              </Button>
            </>
          }
        />

        {isError ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
              <p className="text-sm font-medium">Failed to load scheduler status</p>
              <p className="text-xs text-muted-foreground">
                {(error as Error)?.message ?? "Unknown error"}
              </p>
              <Button variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </CardContent>
          </Card>
        ) : isLoading || !data ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Scheduler
                  <Badge variant={data.isRunning ? "success" : "outline"}>
                    {data.isRunning ? "Running" : "Stopped"}
                  </Badge>
                </CardTitle>
                <CardDescription>
                  Last updated {timeAgo(data.updatedAt)} ({formatDateTime(data.updatedAt)})
                </CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Last tick</p>
                  <p className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    {formatDateTime(data.lastTickAt)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Next tick</p>
                  <p className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    {formatDateTime(data.nextTickAt)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Updated</p>
                  <p>{formatDateTime(data.updatedAt)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Sent since last tick</p>
                  <p className="tabular-nums text-2xl font-semibold text-emerald-600">
                    {data.sentSinceLastTick}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Skipped since last tick</p>
                  <p className="tabular-nums text-2xl font-semibold text-amber-600">
                    {data.skippedSinceLastTick}
                  </p>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Manual Tick</CardTitle>
                  <CardDescription>
                    Force a single synchronous scheduler tick (testing / ops).
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p className="text-muted-foreground">
                    A manual tick processes due sequences for this tenant only.
                  </p>
                  <Button className="w-full" onClick={() => setTickOpen(true)}>
                    <FastForward className="h-4 w-4" />
                    Run tick now
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="h-4 w-4" />
                    Trigger Now
                  </CardTitle>
                  <CardDescription>
                    Immediately trigger the scheduler pipeline.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p className="text-muted-foreground">
                    Triggers the scheduler to process all due sequences
                    immediately, without waiting for the next tick interval.
                  </p>
                  <Button
                    className="w-full"
                    variant="secondary"
                    onClick={() => setTriggerOpen(true)}
                    disabled={triggerMut.isPending}
                  >
                    {triggerMut.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Zap className="h-4 w-4" />
                    )}
                    Trigger Now
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Recent Scheduler Runs */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Scheduler Runs</CardTitle>
            <CardDescription>
              Latest scheduler execution history.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {runsLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : !runs || runs.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No scheduler runs recorded yet.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-36">Started</TableHead>
                    <TableHead className="w-36">Completed</TableHead>
                    <TableHead className="w-28">Status</TableHead>
                    <TableHead className="w-20">Sent</TableHead>
                    <TableHead className="w-20">Skipped</TableHead>
                    <TableHead className="w-24">Duration</TableHead>
                    <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell className="text-xs">
                        {formatDateTime(run.startedAt)}
                      </TableCell>
                      <TableCell className="text-xs">
                        {run.completedAt ? formatDateTime(run.completedAt) : "—"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            run.status === "completed"
                              ? "success"
                              : run.status === "failed"
                                ? "destructive"
                                : "secondary"
                          }
                          className="text-[10px]"
                        >
                          {run.status === "running" && (
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          )}
                          {run.status === "completed" && (
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                          )}
                          {run.status === "failed" && (
                            <XCircle className="mr-1 h-3 w-3" />
                          )}
                          {run.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="tabular-nums text-sm">
                        {run.sent}
                      </TableCell>
                      <TableCell className="tabular-nums text-sm">
                        {run.skipped}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {run.durationMs != null ? `${run.durationMs}ms` : "—"}
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate text-xs text-destructive">
                        {run.error ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Trigger Now confirmation dialog */}
        <Dialog open={triggerOpen} onOpenChange={setTriggerOpen}>
          <DialogClose onClose={() => setTriggerOpen(false)} />
          <DialogHeader>
            <DialogTitle>Trigger Scheduler Now?</DialogTitle>
            <DialogDescription>
              This will immediately trigger the scheduler pipeline to process all
              due sequences, regardless of the next scheduled tick.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTriggerOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => triggerMut.mutate()}
              disabled={triggerMut.isPending}
            >
              {triggerMut.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Triggering…
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  Trigger Now
                </>
              )}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Manual tick dialog */}
        <Dialog open={tickOpen} onOpenChange={setTickOpen}>
          <DialogClose onClose={() => setTickOpen(false)} />
          <DialogHeader>
            <DialogTitle>Run scheduler tick?</DialogTitle>
            <DialogDescription>
              This will synchronously process due sequences for the current tenant. Avoid running during peak load.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="tick-max">Max sends per tick</Label>
              <Input
                id="tick-max"
                type="number"
                min={1}
                max={1000}
                value={maxSend}
                onChange={(e) => setMaxSend(Number(e.target.value))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTickOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleTick} disabled={tickMut.isPending}>
              {tickMut.isPending ? "Running…" : "Run tick"}
            </Button>
          </DialogFooter>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
