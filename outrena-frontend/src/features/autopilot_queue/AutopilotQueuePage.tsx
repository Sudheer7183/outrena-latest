/**
 * AutopilotQueuePage.tsx — Autopilot queue management page.
 *
 * Shows KPI cards, queue controls (trigger, enqueue, autonomous mode),
 * queue items table with auto-refresh, and a pipeline flow diagram.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  FlaskConical,
  ListOrdered,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Rocket,
  Search,
  XCircle,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { autopilotQueueApi, flowsApi } from "@/services/apiClient";
import type {
  AutopilotQueueItem,
  // AutopilotQueueStats,
  AutopilotQueueEnqueueBody,
  AutopilotQueueStatus,
  ProspectingFlow,
} from "@/types/common";
import { useAuth } from "@/context/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/ui/stat-card";
import { Switch } from "@/components/ui/switch";
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

const AUTO_REFRESH_INTERVAL = 5_000;

interface EnqueueForm {
  flowId: string;
  icpProfileId: string;
  maxProspects: number;
  dryRun: boolean;
}

const EMPTY_ENQUEUE_FORM: EnqueueForm = {
  flowId: "",
  icpProfileId: "",
  maxProspects: 50,
  dryRun: false,
};

export function AutopilotQueuePage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const isManager = hasRole("MANAGER");

  const [enqueueOpen, setEnqueueOpen] = useState(false);
  const [enqueueForm, setEnqueueForm] = useState<EnqueueForm>(EMPTY_ENQUEUE_FORM);

  // Auto-refresh timer
  const [refreshKey, setRefreshKey] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshKey((k) => k + 1);
    }, AUTO_REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  // Stats
  const {
    data: stats,
    isLoading: statsLoading,
  } = useQuery({
    queryKey: ["autopilot-queue", "stats", refreshKey],
    queryFn: () => autopilotQueueApi.stats(),
    retry: false,
  });

  // Queue items
  const {
    data: queueData,
    isLoading: queueLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["autopilot-queue", "list", refreshKey],
    queryFn: () => autopilotQueueApi.list({ limit: 50 }),
    retry: false,
  });
  const queueItems = useMemo(() => queueData?.items ?? [], [queueData]);

  // Flows for enqueue dialog
  const { data: flowsData } = useQuery({
    queryKey: ["flows", "list"],
    queryFn: () => flowsApi.listFlows({ isTemplate: false }),
    retry: false,
  });
  const flows = useMemo(() => flowsData?.items ?? [], [flowsData]);

  // Mutations
  const triggerMut = useMutation({
    mutationFn: () => autopilotQueueApi.triggerScheduler(),
    onSuccess: (data) => {
      toast.success(data.message || "Scheduler triggered");
      qc.invalidateQueries({ queryKey: ["autopilot-queue"] });
    },
    onError: () => toast.error("Failed to trigger scheduler"),
  });

  const enqueueMut = useMutation({
    mutationFn: (body: AutopilotQueueEnqueueBody) =>
      autopilotQueueApi.enqueue(body),
    onSuccess: () => {
      toast.success("Flow enqueued");
      qc.invalidateQueries({ queryKey: ["autopilot-queue"] });
      setEnqueueOpen(false);
      setEnqueueForm(EMPTY_ENQUEUE_FORM);
    },
    onError: () => toast.error("Failed to enqueue flow"),
  });

  const autonomousMut = useMutation({
    mutationFn: (enabled: boolean) =>
      autopilotQueueApi.setAutonomousMode(enabled),
    onSuccess: (data) => {
      toast.success(
        data.autonomousMode
          ? "Autonomous mode ON"
          : "Autonomous mode OFF",
      );
      qc.invalidateQueries({ queryKey: ["autopilot-queue"] });
    },
    onError: () => toast.error("Failed to toggle autonomous mode"),
  });

  const cancelMut = useMutation({
    mutationFn: (id: string) => autopilotQueueApi.cancel(id),
    onSuccess: () => {
      toast.success("Queue item cancelled");
      qc.invalidateQueries({ queryKey: ["autopilot-queue"] });
    },
    onError: () => toast.error("Failed to cancel queue item"),
  });

  const handleEnqueue = useCallback(() => {
    if (!enqueueForm.flowId) {
      toast.error("Please select a flow");
      return;
    }
    if (!enqueueForm.icpProfileId) {
      toast.error("Please select an ICP profile");
      return;
    }
    enqueueMut.mutate({
      flowId: enqueueForm.flowId,
      icpProfileId: enqueueForm.icpProfileId,
      maxProspects: enqueueForm.maxProspects,
      dryRun: enqueueForm.dryRun,
    });
  }, [enqueueForm, enqueueMut]);

  // Resolve flow name from ID
  const flowNameMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const f of flows) m.set(f.id, f.name);
    return m;
  }, [flows]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Autopilot Queue"
        description="Manage the autopilot execution queue — trigger runs, enqueue flows, and monitor queue status."
        actions={
          <>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            {isManager && (
              <Button
                variant="outline"
                onClick={() => triggerMut.mutate()}
                disabled={triggerMut.isPending}
              >
                {triggerMut.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Zap className="h-4 w-4" />
                )}
                Trigger Scheduler Now
              </Button>
            )}
            <Button onClick={() => setEnqueueOpen(true)}>
              <Plus className="h-4 w-4" />
              Enqueue Flow
            </Button>
          </>
        }
      />

      {/* KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statsLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))
        ) : stats ? (
          <>
            <StatCard
              label="Queued"
              value={stats.queued.toLocaleString()}
              icon={<Clock className="h-4 w-4" />}
            />
            <StatCard
              label="Running"
              value={stats.running.toLocaleString()}
              icon={<Loader2 className="h-4 w-4" />}
            />
            <StatCard
              label="Completed (24h)"
              value={stats.completed24h.toLocaleString()}
              icon={<CheckCircle2 className="h-4 w-4" />}
            />
            <StatCard
              label="Failed (24h)"
              value={stats.failed24h.toLocaleString()}
              icon={<XCircle className="h-4 w-4" />}
              delta={
                stats.failed24h > 0
                  ? { value: "Review failures", positive: false }
                  : undefined
              }
            />
          </>
        ) : null}
      </div>

      {/* Autonomous Mode toggle */}
      {isManager && stats && (
        <Card>
          <CardContent className="flex items-center justify-between p-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">Autonomous Mode</p>
              <p className="text-xs text-muted-foreground">
                When ON, the scheduler automatically enqueues and runs flows
                based on ICP profiles and schedule configs.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant={stats.autonomousMode ? "success" : "outline"}>
                {stats.autonomousMode ? "ON" : "OFF"}
              </Badge>
              <Button
                variant={stats.autonomousMode ? "outline" : "default"}
                size="sm"
                onClick={() =>
                  autonomousMut.mutate(!stats.autonomousMode)
                }
                disabled={autonomousMut.isPending}
              >
                {autonomousMut.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : stats.autonomousMode ? (
                  <Pause className="h-4 w-4" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {stats.autonomousMode ? "Turn OFF" : "Turn ON"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Queue items table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Queue Items</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isError ? (
            <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
              <p className="text-sm font-medium">Failed to load queue</p>
              <p className="text-xs text-muted-foreground">
                {(error as Error)?.message ?? "Unknown error"}
              </p>
              <Button variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          ) : queueLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : queueItems.length === 0 ? (
            <EmptyState
              icon={<ListOrdered className="h-6 w-6" />}
              title="Queue is empty"
              description="Enqueue a flow to start processing prospects automatically."
              action={
                <Button onClick={() => setEnqueueOpen(true)}>
                  <Plus className="h-4 w-4" /> Enqueue Flow
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Flow</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queueItems.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-xs">
                      {item.id.slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {flowNameMap.get(item.flowId) ?? item.flowId.slice(0, 8)}
                    </TableCell>
                    <TableCell>
                      <QueueStatusBadge status={item.status} />
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(item.createdAt)}
                    </TableCell>
                    <TableCell className="text-right">
                      <QueueItemActions
                        item={item}
                        onCancel={(id) => cancelMut.mutate(id)}
                        onViewRun={(runId) =>
                          navigate(`/prospecting/flows/runs/${runId}`)
                        }
                        isCancelling={cancelMut.isPending}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Quick Autopilot Pipeline section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Autopilot Pipeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            The autopilot pipeline processes queued flows through these stages:
          </p>

          {/* Pipeline flow diagram */}
          <div className="flex flex-wrap items-center justify-center gap-2">
            <PipelineStep label="Queue" icon={<Clock className="h-4 w-4" />} active />
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
            <PipelineStep label="Source" icon={<Search className="h-4 w-4" />} />
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
            <PipelineStep label="Dedup" icon={<ListOrdered className="h-4 w-4" />} />
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
            <PipelineStep label="Enrich" icon={<FlaskConical className="h-4 w-4" />} />
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
            <PipelineStep label="Gate" icon={<AlertTriangle className="h-4 w-4" />} />
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
            <PipelineStep label="Import" icon={<CheckCircle2 className="h-4 w-4" />} active />
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/prospecting/autopilot")}
            >
              <Rocket className="h-4 w-4" />
              Open Quick Autopilot
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Enqueue dialog */}
      <Dialog open={enqueueOpen} onOpenChange={(o) => !o && setEnqueueOpen(false)}>
        <DialogClose onClose={() => setEnqueueOpen(false)} />
        <DialogHeader>
          <DialogTitle>Enqueue Flow</DialogTitle>
          <DialogDescription>
            Add a flow to the autopilot queue. The scheduler will pick it up
            and run the prospecting pipeline.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Flow</Label>
            <Select
              value={enqueueForm.flowId}
              onValueChange={(v) =>
                setEnqueueForm({ ...enqueueForm, flowId: v })
              }
            >
              <SelectTrigger>
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
          </div>
          <div className="space-y-2">
            <Label>ICP Profile</Label>
            <Input
              placeholder="ICP profile ID"
              value={enqueueForm.icpProfileId}
              onChange={(e) =>
                setEnqueueForm({
                  ...enqueueForm,
                  icpProfileId: e.target.value,
                })
              }
            />
          </div>
          <div className="space-y-2">
            <Label>Max Prospects</Label>
            <Input
              type="number"
              min={1}
              max={10000}
              value={enqueueForm.maxProspects}
              onChange={(e) =>
                setEnqueueForm({
                  ...enqueueForm,
                  maxProspects: parseInt(e.target.value, 10) || 50,
                })
              }
            />
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <div className="space-y-0.5">
              <span className="text-sm font-medium">Dry Run</span>
              <span className="text-xs text-muted-foreground">
                Run the pipeline without actually importing prospects.
              </span>
            </div>
            <Switch
              checked={enqueueForm.dryRun}
              onCheckedChange={(v) =>
                setEnqueueForm({ ...enqueueForm, dryRun: v })
              }
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setEnqueueOpen(false)}
          >
            Cancel
          </Button>
          <Button
            onClick={handleEnqueue}
            disabled={enqueueMut.isPending}
          >
            {enqueueMut.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Enqueuing…
              </>
            ) : (
              "Enqueue"
            )}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}

/** Queue status badge. */
function QueueStatusBadge({ status }: { status: AutopilotQueueStatus }) {
  const variant =
    status === "COMPLETED"
      ? "success"
      : status === "FAILED"
        ? "destructive"
        : status === "RUNNING"
          ? "default"
          : status === "CANCELLED"
            ? "outline"
            : "secondary";
  return <Badge variant={variant}>{status}</Badge>;
}

/** Queue item action buttons. */
function QueueItemActions({
  item,
  onCancel,
  onViewRun,
  isCancelling,
}: {
  item: AutopilotQueueItem;
  onCancel: (id: string) => void;
  onViewRun: (runId: string) => void;
  isCancelling: boolean;
}) {
  return (
    <div className="flex justify-end gap-1">
      {item.status === "COMPLETED" && item.flowRunId && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onViewRun(item.flowRunId!)}
        >
          View Run
        </Button>
      )}
      {item.status === "QUEUED" && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onCancel(item.id)}
          disabled={isCancelling}
        >
          Cancel
        </Button>
      )}
    </div>
  );
}

/** Pipeline step visual. */
function PipelineStep({
  label,
  icon,
  active = false,
}: {
  label: string;
  icon: React.ReactNode;
  active?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm ${
        active
          ? "border-primary bg-primary/10 text-primary font-medium"
          : "border-muted bg-muted/50 text-muted-foreground"
      }`}
    >
      {icon}
      {label}
    </div>
  );
}
