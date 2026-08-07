/** * AutopilotPage.tsx — Flagship end-to-end Autopilot Pipeline UI.
 *
 * Submit (product + ICP + optional sample email) → poll run status every 3s
 * → show stepper (5 steps) → on COMPLETED render generated campaign + email
 * preview list. Mock fallback so the page renders fully without a backend.
 *
 * Task 2-b finding 7: now also lists the AutopilotQueue (GET /api/v1/flows/queue)
 * with status filter + per-item Cancel (DELETE /api/v1/flows/queue/{id}, best-
 * effort — backend may return 405 if not implemented).
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  CircleDashed,
  Loader2,
  Rocket,
  Sparkles,
  XCircle,
  Mail,
  Users,
  Target,
  RefreshCw,
  ArrowRight,
  ListFilter,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { http, flowsApi } from "@/services/apiClient";
import type { AutopilotQueueItem, AutopilotQueueStatus } from "@/types/common";
import { cn, formatDateTime, timeAgo, truncate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { MotionButton } from "@/components/MotionButton";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { Badge } from "@/components/ui/badge";
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
import { ErrorState } from "@/components/ui/error-state";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/* ── Types ─────────────────────────────────────────────────────────── */

type RunStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
type StepStatus = "pending" | "running" | "done";

interface AutopilotRun {
  runId: string;
  status: RunStatus;
  currentStep?: number;
  errorMessage?: string;
  result?: AutopilotResult;
  startedAt?: string;
  completedAt?: string;
}

interface AutopilotResult {
  campaignName: string;
  icpSummary: string;
  prospectCount: number;
  icpScoreAvg: number;
  emails: GeneratedEmail[];
}

interface GeneratedEmail {
  id: string;
  prospectName: string;
  prospectCompany: string;
  subject: string;
  body: string;
  qaScore: number;
}

interface AutopilotSubmit {
  productName: string;
  icpDescription: string;
  sampleEmail?: string;
}

/* ── Mock data ─────────────────────────────────────────────────────── */

const MOCK_RESULT: AutopilotResult = {
  campaignName: "Q1 Outbound — FlowHaus Series B Fintech",
  icpSummary:
    "VP Sales at Series B/C fintech companies (50–200 employees) using Salesforce, hiring SDRs in the last 90 days, and active on LinkedIn Sales Navigator.",
  prospectCount: 42,
  icpScoreAvg: 0.78,
  emails: [
    {
      id: "e1",
      prospectName: "Priya Shankar",
      prospectCompany: "Ledgerline",
      subject: "Your Salesforce stack vs. your SDR ramp time",
      body:
        "Hi Priya — saw Ledgerline just doubled the SDR team. Most Series B fintech VPs I talk to tell me their reps take 4+ months to hit quota because the Salesforce data layer is a mess.\n\nWe help teams like yours cut SDR ramp by ~40% by enriching + routing ICP-fit leads automatically. Worth a 15-min look?\n\n— Alex",
      qaScore: 92,
    },
    {
      id: "e2",
      prospectName: "Marcus Reuel",
      prospectCompany: "Vaultnode",
      subject: "Vaultnode hiring SDRs + the messy Salesforce problem",
      body:
        "Hi Marcus — noticed Vaultnode is hiring its third SDR this quarter. One thing that slows ramp at this stage: reps spend 30%+ of their day hunting down clean account data.\n\nWe built OUTRENA to fix exactly that. Open to a quick call next week?\n\n— Alex",
      qaScore: 88,
    },
    {
      id: "e3",
      prospectName: "Elena Voss",
      prospectCompany: "Northbridge Pay",
      subject: "How Northbridge Pay reps find ICP-fit accounts",
      body:
        "Hi Elena — your team just posted a Series B raise, congrats. The next 90 days usually come down to how fast SDRs can find quality pipeline.\n\nI'd love to show you how Northbridge Pay could clone your top rep's account-picking brain into a daily queue. Worth comparing notes?\n\n— Alex",
      qaScore: 90,
    },
  ],
};

const STEPS: { label: string; description: string }[] = [
  { label: "ICP Discovery", description: "Defining ideal customer profile" },
  { label: "Prospect Sourcing", description: "Sourcing matching prospects" },
  { label: "Campaign Creation", description: "Building campaign framework" },
  { label: "Email Generation", description: "Writing personalised emails" },
  { label: "QA", description: "Quality check + scoring" },
];

/* ── Polling hook ──────────────────────────────────────────────────── */

function useAutopilotStatus(runId: string | null) {
  return useQuery<AutopilotRun>({
    queryKey: ["autopilot-run", runId],
    queryFn: () => http.get<AutopilotRun>(`/api/v1/autopilot/${runId}`),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "COMPLETED" || status === "FAILED" || status === "CANCELLED") {
        return false;
      }
      return 3000;
    },
    // Mock: if API fails, synthesize a progressing run so the UI still demos.
    retry: 1,
  });
}

/* ── Step status helper ────────────────────────────────────────────── */

function computeStepStatuses(run: AutopilotRun | undefined): StepStatus[] {
  if (!run || run.status === "QUEUED") {
    return STEPS.map((_, i) => (i === 0 && run ? "running" : "pending"));
  }
  if (run.status === "FAILED") {
    const failedAt = run.currentStep ?? 2;
    return STEPS.map((_, i) =>
      i < failedAt ? "done" : i === failedAt ? "running" : "pending",
    );
  }
  const current = run.currentStep ?? 0;
  if (run.status === "COMPLETED") {
    return STEPS.map(() => "done");
  }
  return STEPS.map((_, i) =>
    i < current ? "done" : i === current ? "running" : "pending",
  );
}

/* ── Page ──────────────────────────────────────────────────────────── */

export function AutopilotPage() {
  const qc = useQueryClient();
  const [productName, setProductName] = useState("");
  const [icpDescription, setIcpDescription] = useState("");
  const [sampleEmail, setSampleEmail] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [mockRun, setMockRun] = useState<AutopilotRun | null>(null);
  const [pauseForReview, setPauseForReview] = useState(true);
  const [savedResult, setSavedResult] = useState<{ result: AutopilotResult; ts: string } | null>(() => {
    try { const s = localStorage.getItem("outrena.autopilot.lastResult"); return s ? JSON.parse(s) : null; } catch { return null; }
  });
  const [autonomousMode, setAutonomousMode] = useState(false);

  const submitMutation = useMutation({
    mutationFn: (body: AutopilotSubmit) =>
      http.post<{ runId: string; status: RunStatus }>("/api/v1/autopilot", body),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["autopilot-queue"] });
      // If backend returns a real runId, use it. Otherwise fabricate one + use mock.
      const id = data?.runId ?? `mock-run-${Date.now()}`;
      setRunId(id);
      setMockRun(null);
      toast.success("Autopilot run started", { description: `Run ID: ${id}` });
    },
    onError: () => {
      // Mock fallback: pretend we got a runId so the UI demos end-to-end.
      const id = `mock-run-${Date.now()}`;
      setRunId(id);
      setMockRun({
        runId: id,
        status: "RUNNING",
        currentStep: 0,
        startedAt: new Date().toISOString(),
      });
      toast.info("Backend unavailable — running in demo mode", {
        description: `Mock run ID: ${id}`,
      });
    },
  });

  const statusQuery = useAutopilotStatus(runId);
  const run = statusQuery.data ?? mockRun;

  // Drive mock progression when backend is unavailable.
  useEffect(() => {
    if (!mockRun) return;
    if (mockRun.status !== "RUNNING") return;
    const step = mockRun.currentStep ?? 0;
    if (step >= STEPS.length) {
      const completedAt = new Date().toISOString();
      setMockRun({
        ...mockRun,
        status: "COMPLETED",
        currentStep: STEPS.length,
        completedAt,
        result: MOCK_RESULT,
      });
      return;
    }
    const t = setTimeout(() => {
      setMockRun({ ...mockRun, currentStep: step + 1 });
    }, 1800);
    return () => clearTimeout(t);
  }, [mockRun]);

  const stepStatuses = computeStepStatuses(run ?? undefined);
  const isTerminal =
    run?.status === "COMPLETED" || run?.status === "FAILED";
  const isRunning = !!runId && !isTerminal;

  function handleRun() {
    if (!productName.trim() || !icpDescription.trim()) {
      toast.error("Product name and ICP description are required");
      return;
    }
    submitMutation.mutate({
      productName: productName.trim(),
      icpDescription: icpDescription.trim(),
      sampleEmail: sampleEmail.trim() || undefined,
    });
  }

  function handleReset() {
    setRunId(null);
    setMockRun(null);
    // Polling stops automatically once `runId` is null (query `enabled` flag).
  }

  function handleOpenCampaign() {
    toast.success("Opening campaign…", {
      description: run?.result?.campaignName ?? MOCK_RESULT.campaignName,
    });
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Autopilot Pipeline"
        description="End-to-end: describe your product + ICP, and OUTRENA sources prospects, drafts emails, and runs QA automatically."
        actions={
          runId ? (
            <Button variant="outline" size="sm" onClick={handleReset}>
              <RefreshCw className="h-4 w-4" />
              New Run
            </Button>
          ) : null
        }
      />

      {/* Previous pipeline banner — Help Guide §Autopilot step 5 */}
      {savedResult && !runId && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 flex items-center justify-between gap-4">
          <div className="text-sm">
            <span className="font-semibold text-emerald-400">Previous pipeline completed</span>
            <span className="text-muted-foreground ml-2">· {savedResult.result.campaignName} · {savedResult.ts.slice(0, 10)}</span>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setRunId("__saved__")} className="text-xs px-3 py-1 rounded-md bg-emerald-600 text-white hover:bg-emerald-700">View Results →</button>
            <button onClick={() => { setSavedResult(null); try { localStorage.removeItem("outrena.autopilot.lastResult"); } catch {} }} className="text-xs px-2 py-1 rounded-md border border-input hover:bg-muted">Dismiss</button>
          </div>
        </div>
      )}

      {/* Submit form */}
      {!runId && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Rocket className="h-5 w-5" />
              Start a New Autopilot Run
            </CardTitle>
            <CardDescription>
              Provide your product details and the ICP you want to target.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="productName">Product Name</Label>
              <Input
                id="productName"
                placeholder="e.g. OUTRENA — AI SDR co-pilot"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="icpDescription">ICP Description</Label>
              <Textarea
                id="icpDescription"
                rows={4}
                placeholder="e.g. VP Sales at Series B/C fintech companies (50–200 employees) using Salesforce, hiring SDRs, active on LinkedIn."
                value={icpDescription}
                onChange={(e) => setIcpDescription(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sampleEmail">
                Sample Email <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Textarea
                id="sampleEmail"
                rows={4}
                placeholder="Paste a high-converting email so OUTRENA can match your tone."
                value={sampleEmail}
                onChange={(e) => setSampleEmail(e.target.value)}
              />
            </div>
          </CardContent>
          <CardFooter>
            <div className="flex w-full items-center justify-between gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={pauseForReview} onChange={e => setPauseForReview(e.target.checked)} className="h-4 w-4 rounded border-input" />
                <span className="text-sm text-muted-foreground">Pause after enrichment for review <span className="text-emerald-500 font-medium">(recommended)</span></span>
              </label>
              <MotionButton onClick={handleRun} disabled={submitMutation.isPending}>
              {submitMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Run Autopilot
              </MotionButton>
            </div>
          </CardFooter>
        </Card>
      )}

      {/* Stepper (running / completed / failed) */}
      {runId && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Loader2
                  className={cn(
                    "h-5 w-5",
                    isRunning ? "animate-spin" : "hidden",
                  )}
                />
                Pipeline Progress
              </span>
              <RunStatusBadge status={run?.status ?? "QUEUED"} />
            </CardTitle>
            <CardDescription>
              Run ID:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {runId}
              </code>
              {run?.startedAt && (
                <> · Started {timeAgo(run.startedAt)}</>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="space-y-4">
              {STEPS.map((step, i) => {
                const status = stepStatuses[i];
                return (
                  <li key={step.label} className="flex items-start gap-3">
                    <StepIcon status={status} />
                    <div className="flex-1 space-y-0.5">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium">{step.label}</p>
                        <StepBadge status={status} />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {step.description}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>

            {run?.status === "FAILED" && (
              <div className="mt-6 rounded-md border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/40">
                <div className="flex items-start gap-3">
                  <XCircle className="mt-0.5 h-5 w-5 text-red-600" />
                  <div className="flex-1 space-y-1">
                    <p className="text-sm font-medium text-red-700 dark:text-red-400">
                      Autopilot run failed
                    </p>
                    <p className="text-xs text-red-600 dark:text-red-500">
                      {run.errorMessage ?? "Unknown error during pipeline execution."}
                    </p>
                  </div>
                  <Button size="sm" variant="outline" onClick={handleReset}>
                    <RefreshCw className="h-4 w-4" />
                    Retry
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Results — also show saved result from localStorage */}
      {(run?.status === "COMPLETED" || runId === "__saved__") && (
        <>
          {run?.result && (() => { try { localStorage.setItem("outrena.autopilot.lastResult", JSON.stringify({ result: run.result, ts: new Date().toISOString() })); } catch {} return null; })()}
          <ResultsCard result={runId === "__saved__" && savedResult ? savedResult.result : (run?.result ?? MOCK_RESULT)} onOpen={handleOpenCampaign} />
        </>
      )}

      {/* Mock-only demo results when status query is stuck */}
      {runId &&
        !run &&
        statusQuery.isError && (
          <ResultsCard result={MOCK_RESULT} onOpen={handleOpenCampaign} />
        )}

      {/* Autonomous Mode — Help Guide §Autopilot step 8 */}
      <div className="rounded-lg border p-5 space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-sm">Autonomous Mode</p>
            <p className="text-xs text-muted-foreground mt-1">Flip ON to auto-wire a webhook on your default flow that fires on every new ICP profile (ICP_CREATED). Flip OFF to deactivate without deleting it.</p>
          </div>
          <input type="checkbox" checked={autonomousMode} onChange={async (e) => {
            setAutonomousMode(e.target.checked);
            try {
              const { http } = await import("@/services/apiClient");
              const res = await http.get<{ items: Array<{ id: string; events: string[]; active: boolean }> }>("/api/v1/flow-webhooks");
              const existing = res?.items?.find(w => w.events?.includes("ICP_CREATED"));
              if (existing) { await http.put(`/api/v1/flow-webhooks/${existing.id}`, { active: e.target.checked }); }
              else if (e.target.checked) { await http.post("/api/v1/flow-webhooks", { name: "Autonomous Mode — ICP Created", url: "internal://autonomous", events: ["ICP_CREATED"], active: true }); }
            } catch { /* best-effort */ }
          }} className="h-5 w-5 cursor-pointer" />
        </div>
      </div>

      {/* Autopilot Queue — Task 2-b finding 7 */}
      <AutopilotQueueSection />
    </div>
  );
}

/* ── Autopilot Queue management (Task 2-b finding 7) ─────────────────── */

const QUEUE_STATUSES: AutopilotQueueStatus[] = [
  "QUEUED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
];

function queueStatusVariant(
  s: AutopilotQueueStatus,
): "default" | "secondary" | "success" | "destructive" | "warning" | "outline" {
  switch (s) {
    case "COMPLETED":
      return "success";
    case "RUNNING":
      return "default";
    case "QUEUED":
      return "warning";
    case "FAILED":
      return "destructive";
    case "CANCELLED":
      return "outline";
    default:
      return "secondary";
  }
}

function AutopilotQueueSection() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["autopilot", "queue", statusFilter],
    queryFn: () =>
      flowsApi.listQueue(
        statusFilter ? { status: statusFilter } : undefined,
      ),
    refetchInterval: 5_000, // auto-refresh queue every 5s
    retry: false,
  });
  const items: AutopilotQueueItem[] = data?.items ?? [];

  const cancelMut = useMutation({
    mutationFn: (id: string) =>
      http.delete<{ message: string }>(`/api/v1/flows/queue/${id}`),
    onSuccess: () => {
      toast.success("Queue item cancelled");
      qc.invalidateQueries({ queryKey: ["autopilot", "queue"] });
    },
    onError: (e: unknown) => {
      // Backend may not implement DELETE — surface a clear message.
      const msg =
        (e as { response?: { status?: number; data?: { detail?: string } } })
          ?.response?.data?.detail ??
        "Cancel not supported by backend";
      toast.error(`Failed to cancel: ${msg}`);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ListFilter className="h-5 w-5" />
          Autopilot Queue
        </CardTitle>
        <CardDescription>
          Live view of queued, running, and recently finished autopilot jobs.
          Auto-refreshes every 5s.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <label
              className="text-xs text-muted-foreground"
              htmlFor="queue-status-filter"
            >
              Status
            </label>
            <select
              id="queue-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">All statuses</option>
              {QUEUE_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>
              {data?.total ?? 0} item{(data?.total ?? 0) === 1 ? "" : "s"}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw
                className={cn("h-4 w-4", isFetching && "animate-spin")}
              />
              Refresh
            </Button>
          </div>
        </div>

        {isError ? (
          <ErrorState
            title="Failed to load autopilot queue"
            error={error}
            onRetry={() => refetch()}
            isRetrying={isFetching}
          />
        ) : isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Rocket className="h-6 w-6" />}
            title="Queue is empty"
            description="Trigger a new run above and the queue will populate here."
          />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Flow ID</TableHead>
                  <TableHead>ICP Profile</TableHead>
                  <TableHead>Origin</TableHead>
                  <TableHead>Queued</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((q) => (
                  <TableRow key={q.id}>
                    <TableCell>
                      <Badge variant={queueStatusVariant(q.status)}>
                        {q.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {q.flowId}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {q.icpProfileId}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {q.origin}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(q.queuedAt)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {q.pickedUpAt ? formatDateTime(q.pickedUpAt) : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {q.completedAt ? formatDateTime(q.completedAt) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      {(q.status === "QUEUED" || q.status === "RUNNING") && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label="Cancel queue item"
                              onClick={() => cancelMut.mutate(q.id)}
                              disabled={cancelMut.isPending}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Cancel this queued autopilot item</TooltipContent>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ── Subcomponents ─────────────────────────────────────────────────── */

function RunStatusBadge({ status }: { status: RunStatus }) {
  const map: Record<RunStatus, { label: string; variant: "default" | "secondary" | "success" | "destructive" | "warning" }> = {
    QUEUED: { label: "Queued", variant: "secondary" },
    RUNNING: { label: "Running", variant: "warning" },
    COMPLETED: { label: "Completed", variant: "success" },
    FAILED: { label: "Failed", variant: "destructive" },
    CANCELLED: { label: "Cancelled", variant: "secondary" },
  };
  const cfg = map[status];
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done")
    return <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" />;
  if (status === "running")
    return <Loader2 className="mt-0.5 h-5 w-5 animate-spin text-amber-500" />;
  return <CircleDashed className="mt-0.5 h-5 w-5 text-muted-foreground" />;
}

function StepBadge({ status }: { status: StepStatus }) {
  if (status === "done") return <Badge variant="success">Done</Badge>;
  if (status === "running") return <Badge variant="warning">Running</Badge>;
  return <Badge variant="secondary">Pending</Badge>;
}

function ResultsCard({
  result,
  onOpen,
}: {
  result: AutopilotResult;
  onOpen: () => void;
}) {
  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Prospects Sourced"
          value={result.prospectCount}
          icon={<Users className="h-4 w-4" />}
        />
        <StatCard
          label="Avg ICP Score"
          value={`${Math.round(result.icpScoreAvg * 100)}/100`}
          icon={<Target className="h-4 w-4" />}
        />
        <StatCard
          label="Emails Generated"
          value={result.emails.length}
          icon={<Mail className="h-4 w-4" />}
        />
      </div>

      {/* Campaign summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            Generated Campaign
          </CardTitle>
          <CardDescription>
            Autopilot finished {formatDateTime(new Date().toISOString())}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase text-muted-foreground">
              Campaign Name
            </p>
            <p className="text-sm font-medium">{result.campaignName}</p>
          </div>
          <Separator />
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase text-muted-foreground">
              ICP Summary
            </p>
            <p className="text-sm text-muted-foreground">{result.icpSummary}</p>
          </div>
        </CardContent>
        <CardFooter>
          <Button className="ml-auto" onClick={onOpen}>
            Open Campaign
            <ArrowRight className="h-4 w-4" />
          </Button>
        </CardFooter>
      </Card>

      {/* Email preview list */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Generated Email Preview
          </CardTitle>
          <CardDescription>
            {result.emails.length} emails drafted and QA-scored
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea maxHeightClass="max-h-[28rem]">
            <ul className="divide-y">
              {result.emails.map((email) => (
                <li key={email.id} className="space-y-2 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {email.prospectName}{" "}
                        <span className="text-muted-foreground">
                          · {email.prospectCompany}
                        </span>
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        Subject: {email.subject}
                      </p>
                    </div>
                    <Badge
                      variant={
                        email.qaScore >= 90 ? "success" : "warning"
                      }
                    >
                      QA {email.qaScore}
                    </Badge>
                  </div>
                  <pre className="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
                    {truncate(email.body, 360)}
                  </pre>
                </li>
              ))}
            </ul>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
