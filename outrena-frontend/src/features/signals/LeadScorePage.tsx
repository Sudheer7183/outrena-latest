/**
 * LeadScorePage.tsx — Signal monitor + lead scoring.
 *
 * Tabs:
 *  - Signals: table of recent signals (prospect, type, strength, detectedAt).
 *    "Scan Signals" button → toast + adds new mock signals.
 *  - Lead Score: select prospect → POST lead-score → show 0-100 score broken
 *    down by component (intent/fit/timing/engagement) with Progress bars.
 *  - Monitors: list of configured signal monitors + add/edit dialog.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Scan,
  Calculator,
  Bell,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  Save,
  Zap,
  Target,
  Clock,
  Hand,
  TrendingUp,
  Users2,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatPercent, timeAgo, truncate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { StatCard } from "@/components/ui/stat-card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/* ── Types ─────────────────────────────────────────────────────────── */

type SignalType = "funding" | "hiring" | "forum" | "linkedin";

interface SignalEvent {
  id: string;
  prospectName: string;
  prospectCompany: string;
  type: SignalType;
  strength: number; // 0–1
  summary: string;
  detectedAt: string;
}

interface LeadScoreResult {
  prospectName: string;
  overall: number; // 0–100
  components: {
    intent: number;
    fit: number;
    timing: number;
    engagement: number;
  };
  recommendation: string;
}

interface LeadScoreBatchResult {
  scored: number;
  tierDistribution: { tier: string; count: number }[];
  bySeniority: { seniority: string; count: number }[];
}

interface LeadScoreStats {
  totalScored: number;
  tierDistribution: { tier: string; count: number }[];
  bySeniority: { seniority: string; count: number }[];
}

interface SignalMonitor {
  id: string;
  name: string;
  type: SignalType;
  query: string;
  isActive: boolean;
  lastFiredAt: string | null;
}

/* ── Mock data ─────────────────────────────────────────────────────── */

// const _MOCK_SIGNALS: SignalEvent[] = [
//   mkS("s1", "Priya Shankar", "Ledgerline", "funding", 0.95, "Raised $35M Series B", "2025-01-09T08:00:00Z"),
//   mkS("s2", "Marcus Reuel", "Vaultnode", "hiring", 0.78, "Hiring 2 SDRs (posted 1d ago)", "2025-01-10T10:30:00Z"),
//   mkS("s3", "Daniel Okoro", "SwiftForge", "forum", 0.62, "Asked about SDR ramp on r/sales", "2025-01-08T18:15:00Z"),
//   mkS("s4", "Elena Voss", "Northbridge Pay", "linkedin", 0.71, "Posted about pipeline coverage", "2025-01-09T14:00:00Z"),
//   mkS("s5", "Sara Lindqvist", "Blue Harbor", "hiring", 0.66, "Hiring Head of People Ops", "2025-01-07T11:45:00Z"),
//   mkS("s6", "Renee Coleman", "Nexbridge", "linkedin", 0.55, "Commented on a competitor's post", "2025-01-06T09:20:00Z"),
//   mkS("s7", "Tom Bauermann", "Feldstein", "funding", 0.88, "Acquired by MA firm", "2025-01-05T16:00:00Z"),
// ];

// const _MOCK_MONITOR_PROSPECTS = [
//   { id: "p1", name: "Priya Shankar — Ledgerline" },
//   { id: "p2", name: "Marcus Reuel — Vaultnode" },
//   { id: "p3", name: "Elena Voss — Northbridge Pay" },
//   { id: "p4", name: "Daniel Okoro — SwiftForge" },
// ];

// const _MOCK_SCORE: LeadScoreResult = {
//   prospectName: "Priya Shankar — Ledgerline",
//   overall: 87,
//   components: {
//     intent: 0.92,
//     fit: 0.85,
//     timing: 0.88,
//     engagement: 0.78,
//   },
//   recommendation:
//     "High-priority target. Trigger outreach now — Series B raise + SDR hiring + active on LinkedIn. Lead with the ramp-time hook.",
// };

// const _MOCK_MONITORS: SignalMonitor[] = [
//   mkMon("mon1", "Series B fintech raises", "funding", "funding_round:Series B AND industry:fintech", true, "2025-01-09T08:00:00Z"),
//   mkMon("mon2", "SDR hiring posts", "hiring", "job_title:SDR AND posted:<7d", true, "2025-01-10T10:30:00Z"),
//   mkMon("mon3", "r/sales ramp discussions", "forum", "subreddit:sales AND keyword:ramp", false, null),
//   mkMon("mon4", "LinkedIn pipeline posts", "linkedin", "topic:pipeline AND role:VP Sales", true, "2025-01-09T14:00:00Z"),
// ];

// function mkS(
//   id: string,
//   prospectName: string,
//   prospectCompany: string,
//   type: SignalType,
//   strength: number,
//   summary: string,
//   detectedAt: string,
// ): SignalEvent {
//   return { id, prospectName, prospectCompany, type, strength, summary, detectedAt };
// }

// function mkMon(
//   id: string,
//   name: string,
//   type: SignalType,
//   query: string,
//   isActive: boolean,
//   lastFiredAt: string | null,
// ): SignalMonitor {
//   return { id, name, type, query, isActive, lastFiredAt };
// }

const SIGNAL_META: Record<SignalType, { label: string; icon: typeof Zap; variant: "default" | "secondary" | "outline" | "warning" }> = {
  funding: { label: "Funding", icon: TrendingUp, variant: "default" },
  hiring: { label: "Hiring", icon: Hand, variant: "secondary" },
  forum: { label: "Forum", icon: Activity, variant: "outline" },
  linkedin: { label: "LinkedIn", icon: Target, variant: "warning" },
};

/* ── Page ──────────────────────────────────────────────────────────── */

export function LeadScorePage() {
  const [tab, setTab] = useState("signals");

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Signals & Lead Scoring"
        description="Monitor buying signals, score leads across intent/fit/timing/engagement, and configure ongoing signal monitors."
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="signals">
            <Activity className="mr-1.5 h-4 w-4" />
            Signals
          </TabsTrigger>
          <TabsTrigger value="score">
            <Calculator className="mr-1.5 h-4 w-4" />
            Lead Score
          </TabsTrigger>
          <TabsTrigger value="monitors">
            <Bell className="mr-1.5 h-4 w-4" />
            Monitors
          </TabsTrigger>
        </TabsList>

        <TabsContent value="signals">
          <SignalsTab />
        </TabsContent>
        <TabsContent value="score">
          <LeadScoreTab />
        </TabsContent>
        <TabsContent value="monitors">
          <MonitorsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ── Signals tab ───────────────────────────────────────────────────── */

function SignalsTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | SignalType>("all");

  const query = useQuery<SignalEvent[]>({
    queryKey: ["signals"],
    queryFn: () => http.get<any>("/api/v1/signals")
      .then((r: any) => Array.isArray(r) ? r : (r?.items ?? [])),
  });
  const monitorsQuery = useQuery<SignalMonitor[]>({
    queryKey: ["signal-monitors"],
    queryFn: () => http.get<any>("/api/v1/signals/monitors")
      .then((r: any) => Array.isArray(r) ? r : (r?.items ?? [])),
  });
  const allSignals = query.data ?? [];
  const signals = useMemo(() => {
    if (filter === "all") return allSignals;
    return allSignals.filter((s) => s.type === filter);
  }, [allSignals, filter]);

  const scanMutation = useMutation({
    mutationFn: () => http.post<SignalEvent[]>("/api/v1/signals/scan"),
    onSuccess: (data) => {
      toast.success(`Scan complete`, {
        description: `${data?.length ?? 0} new signal(s) detected.`,
      });
      qc.invalidateQueries({ queryKey: ["signals"] });
    },
    onError: () => {
      toast.info("Backend unavailable — scan request noted");
    },
  });

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Recent Signals"
          value={allSignals.length}
          icon={<Activity className="h-4 w-4" />}
        />
        <StatCard
          label="High-Strength (≥0.8)"
          value={allSignals.filter((s) => s.strength >= 0.8).length}
          delta={allSignals.some((s) => s.strength >= 0.8) ? { value: "act now", positive: true } : undefined}
          icon={<Zap className="h-4 w-4" />}
        />
        <StatCard
          label="Active Monitors"
          value={(monitorsQuery.data ?? []).filter((m) => m.isActive).length}
          icon={<Bell className="h-4 w-4" />}
        />
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Recent Signals</CardTitle>
              <CardDescription>{signals.length} shown</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 rounded-md border p-0.5">
                {(["all", "funding", "hiring", "forum", "linkedin"] as const).map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setFilter(f)}
                    className={cn(
                      "rounded-sm px-2.5 py-1 text-xs font-medium capitalize transition-colors",
                      filter === f ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
                    )}
                  >
                    {f}
                  </button>
                ))}
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => scanMutation.mutate()}
                disabled={scanMutation.isPending}
              >
                {scanMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Scan className="h-4 w-4" />
                )}
                Scan Signals
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {query.isLoading ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-md bg-muted" />
              ))}
            </div>
          ) : signals.length === 0 ? (
            <EmptyState
              icon={<Activity className="h-6 w-6" />}
              title="No signals"
              description="Run a scan or adjust filters."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Prospect</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="w-40">Strength</TableHead>
                  <TableHead>Summary</TableHead>
                  <TableHead>Detected</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {signals.map((s) => {
                  const meta = SIGNAL_META[s.type];
                  const Icon = meta.icon;
                  return (
                    <TableRow key={s.id}>
                      <TableCell>
                        <div className="space-y-0.5">
                          <p className="font-medium">{s.prospectName}</p>
                          <p className="text-xs text-muted-foreground">{s.prospectCompany}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={meta.variant} className="gap-1">
                          <Icon className="h-3 w-3" />
                          {meta.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <Progress
                            value={s.strength * 100}
                            indicatorClassName={
                              s.strength >= 0.8
                                ? "bg-emerald-600"
                                : s.strength >= 0.6
                                  ? "bg-amber-500"
                                  : "bg-red-500"
                            }
                          />
                          <span className="text-xs text-muted-foreground">
                            {formatPercent(s.strength, 0)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {truncate(s.summary, 100)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {timeAgo(s.detectedAt)}
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

/* ── Lead Score tab ────────────────────────────────────────────────── */

function LeadScoreTab() {
  const qc = useQueryClient();
  const prospectsQuery = useQuery<{ id: string; name: string }[]>({
    queryKey: ["prospects-brief"],
    queryFn: () => http.get<any>("/api/v1/prospects?select=id,name,company")
      .then((r: any) => Array.isArray(r) ? r : (r?.items ?? [])),
  });
  const prospects = prospectsQuery.data ?? [];
  const [prospectId, setProspectId] = useState("");
  const [score, setScore] = useState<LeadScoreResult | null>(null);
  const [batchResult, setBatchResult] = useState<LeadScoreBatchResult | null>(null);

  const mutation = useMutation({
    mutationFn: (id: string) =>
      http.post<LeadScoreResult>("/api/v1/signals/lead-score", { prospectId: id }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["signals"] });
      setScore(data ?? null);
      toast.success("Lead score computed");
    },
    onError: () => {
      toast.error("Failed to compute lead score");
    },
  });

  const batchMut = useMutation({
    mutationFn: () =>
      http.post<LeadScoreBatchResult>("/api/v1/signals/lead-score-batch", { scoreAll: true }),
    onSuccess: (data) => {
      setBatchResult(data);
      qc.invalidateQueries({ queryKey: ["signals"] });
      toast.success(`Batch scoring complete: ${data.scored} prospects scored`);
    },
    onError: () => {
      toast.error("Batch scoring failed");
    },
  });

  const statsQuery = useQuery<LeadScoreStats>({
    queryKey: ["lead-score-stats"],
    queryFn: () => http.get<LeadScoreStats>("/api/v1/signals/lead-score/stats"),
    enabled: !!batchResult,
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Calculator className="h-4 w-4" />
                Lead Score Calculator
              </CardTitle>
              <CardDescription>Compute a 0–100 lead score from intent, fit, timing, and engagement.</CardDescription>
            </div>
            <Button
              variant="outline"
              onClick={() => batchMut.mutate()}
              disabled={batchMut.isPending}
            >
              {batchMut.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Users2 className="h-4 w-4" />
              )}
              {batchMut.isPending ? "Scoring All…" : "Score All"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <div className="space-y-2">
              <Label htmlFor="score-prospect">Prospect</Label>
              <Select value={prospectId} onValueChange={setProspectId}>
                <SelectTrigger id="score-prospect" className="w-full">
                  <SelectValue placeholder={prospectsQuery.isLoading ? "Loading prospects…" : "Select a prospect"} />
                </SelectTrigger>
                <SelectContent>
                  {prospects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                onClick={() => mutation.mutate(prospectId)}
                disabled={!prospectId || mutation.isPending}
              >
                {mutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Calculator className="h-4 w-4" />
                )}
                Compute Score
              </Button>
            </div>
          </div>

          {score && <LeadScoreCard score={score} />}
        </CardContent>
      </Card>

      {/* Batch Scoring Results */}
      {(batchResult || statsQuery.data) && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Batch Scoring Results</CardTitle>
                <CardDescription>
                  {batchResult ? `${batchResult.scored} prospects scored` : "Aggregate stats"}
                </CardDescription>
              </div>
              <Button size="sm" variant="ghost" onClick={() => { setBatchResult(null); }}>
                Dismiss
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Tier Distribution */}
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase text-muted-foreground">Tier Distribution</p>
                {((batchResult?.tierDistribution ?? statsQuery.data?.tierDistribution) ?? []).map((t) => (
                  <div key={t.tier} className="flex items-center justify-between rounded-md border px-3 py-2">
                    <span className="text-sm font-medium">{t.tier}</span>
                    <Badge variant="outline">{t.count}</Badge>
                  </div>
                ))}
                {(!batchResult?.tierDistribution?.length && !statsQuery.data?.tierDistribution?.length) && (
                  <p className="text-sm text-muted-foreground">No tier data available</p>
                )}
              </div>

              {/* By Seniority */}
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase text-muted-foreground">By Seniority</p>
                {((batchResult?.bySeniority ?? statsQuery.data?.bySeniority) ?? []).map((s) => (
                  <div key={s.seniority} className="flex items-center justify-between rounded-md border px-3 py-2">
                    <span className="text-sm font-medium">{s.seniority}</span>
                    <Badge variant="outline">{s.count}</Badge>
                  </div>
                ))}
                {(!batchResult?.bySeniority?.length && !statsQuery.data?.bySeniority?.length) && (
                  <p className="text-sm text-muted-foreground">No seniority data available</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function LeadScoreCard({ score }: { score: LeadScoreResult }) {
  const components = [
    // BUG-18 FIX: guard against undefined components before render
    { key: "intent", label: "Intent", value: score.components?.intent ?? 0, icon: Zap },
    { key: "fit", label: "Fit", value: score.components?.fit ?? 0, icon: Target },
    { key: "timing", label: "Timing", value: score.components?.timing ?? 0, icon: Clock },
    { key: "engagement", label: "Engagement", value: score.components?.engagement ?? 0, icon: Hand },
  ] as const;

  return (
    <div className="space-y-4 rounded-md border p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium">{score.prospectName}</p>
          <p className="text-xs text-muted-foreground">Lead score breakdown</p>
        </div>
        <div className="text-right">
          <p
            className={cn(
              "text-3xl font-bold",
              score.overall >= 80
                ? "text-emerald-600"
                : score.overall >= 60
                  ? "text-amber-500"
                  : "text-red-600",
            )}
          >
            {score.overall}
          </p>
          <p className="text-xs text-muted-foreground">/ 100</p>
        </div>
      </div>
      <Separator />
      <div className="space-y-3">
        {components.map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.key} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                  {c.label}
                </span>
                <span className="text-sm font-medium">{formatPercent(c.value, 0)}</span>
              </div>
              <Progress
                value={c.value * 100}
                indicatorClassName={
                  c.value >= 0.8
                    ? "bg-emerald-600"
                    : c.value >= 0.6
                      ? "bg-amber-500"
                      : "bg-red-500"
                }
              />
            </div>
          );
        })}
      </div>
      <Separator />
      <div className="space-y-1">
        <p className="text-xs font-medium uppercase text-muted-foreground">
          Recommendation
        </p>
        <p className="text-sm">{score.recommendation}</p>
      </div>
    </div>
  );
}

/* ── Monitors tab ──────────────────────────────────────────────────── */

function MonitorsTab() {
  const qc = useQueryClient();
  const [edit, setEdit] = useState<SignalMonitor | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SignalMonitor | null>(null);

  const query = useQuery<SignalMonitor[]>({
    queryKey: ["signal-monitors"],
    queryFn: () => http.get<SignalMonitor[]>("/api/v1/signals/monitors"),
  });
  const monitors = query.data ?? [];

  const saveMutation = useMutation({
    mutationFn: (m: SignalMonitor) => {
      if (monitors.some((x) => x.id === m.id)) {
        return http.put(`/api/v1/signals/monitors/${m.id}`, m);
      }
      return http.post("/api/v1/signals/monitors", m);
    },
    onSuccess: () => {
      toast.success("Monitor saved");
      setEdit(null);
      setAddOpen(false);
      qc.invalidateQueries({ queryKey: ["signal-monitors"] });
    },
    onError: () => toast.error("Save failed — backend unavailable"),
  });

  const toggleMutation = useMutation({
    mutationFn: (m: SignalMonitor) =>
      http.put(`/api/v1/signals/monitors/${m.id}`, { ...m, isActive: !m.isActive }),
    onSuccess: () => {
      toast.success("Monitor toggled");
      qc.invalidateQueries({ queryKey: ["signal-monitors"] });
    },
    onError: () => toast.error("Toggle failed — backend unavailable"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/signals/monitors/${id}`),
    onSuccess: () => {
      toast.success("Monitor deleted");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["signal-monitors"] });
    },
    onError: () => toast.error("Delete failed — backend unavailable"),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Signal Monitors</CardTitle>
            <CardDescription>
              Ongoing queries that fire signals when matched.
            </CardDescription>
          </div>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" />
            New Monitor
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {query.isError ? (
          <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
            <p className="text-sm font-medium">Failed to load signal monitors</p>
            <Button variant="outline" onClick={() => query.refetch()}>
              Retry
            </Button>
          </div>
        ) : query.isLoading ? (
          [0, 1, 2, 3].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-md bg-muted" />
          ))
        ) : monitors.length === 0 ? (
          <EmptyState
            icon={<Bell className="h-6 w-6" />}
            title="No monitors configured"
            description="Create a monitor to be notified when matching signals fire."
            action={
              <Button size="sm" onClick={() => setAddOpen(true)}>
                <Plus className="h-4 w-4" />
                New Monitor
              </Button>
            }
          />
        ) : (
          monitors.map((m) => {
            const meta = SIGNAL_META[m.type];
            const Icon = meta.icon;
            return (
              <div
                key={m.id}
                className="flex items-start justify-between gap-3 rounded-md border p-4"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <p className="truncate font-medium">{m.name}</p>
                    <Badge variant={meta.variant}>{meta.label}</Badge>
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    <code className="rounded bg-muted px-1 py-0.5">{m.query}</code>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {m.lastFiredAt
                      ? `Last fired ${timeAgo(m.lastFiredAt)}`
                      : "Never fired"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Switch
                    checked={m.isActive}
                    onCheckedChange={() => toggleMutation.mutate(m)}
                    aria-label="Toggle monitor"
                  />
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="Edit"
                        onClick={() => setEdit(m)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Edit monitor</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="Delete"
                        onClick={() => setDeleteTarget(m)}
                      >
                        <Trash2 className="h-4 w-4 text-red-600" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Delete monitor</TooltipContent>
                  </Tooltip>
                </div>
              </div>
            );
          })
        )}
      </CardContent>

      <MonitorDialog
        open={!!edit || addOpen}
        monitor={edit}
        onClose={() => {
          setEdit(null);
          setAddOpen(false);
        }}
        onSubmit={(m) => saveMutation.mutate(m)}
        isPending={saveMutation.isPending}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete signal monitor?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.name
              ? `Monitor "${deleteTarget.name}" will be permanently removed and will stop firing on matching signals. This action cannot be undone.`
              : "This signal monitor will be permanently removed. This action cannot be undone."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() =>
              deleteTarget && deleteMutation.mutate(deleteTarget.id)
            }
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </Dialog>
    </Card>
  );
}

function MonitorDialog({
  open,
  monitor,
  onClose,
  onSubmit,
  isPending,
}: {
  open: boolean;
  monitor: SignalMonitor | null;
  onClose: () => void;
  onSubmit: (m: SignalMonitor) => void;
  isPending: boolean;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState<SignalType>("funding");
  const [query, setQuery] = useState("");
  const [isActive, setIsActive] = useState(true);

  useMemo(() => {
    setName(monitor?.name ?? "");
    setType(monitor?.type ?? "funding");
    setQuery(monitor?.query ?? "");
    setIsActive(monitor?.isActive ?? true);
  }, [monitor, open]);

  function submit() {
    if (!name.trim() || !query.trim()) return;
    onSubmit({
      id: monitor?.id ?? `mon-${Date.now()}`,
      name: name.trim(),
      type,
      query: query.trim(),
      isActive,
      lastFiredAt: monitor?.lastFiredAt ?? null,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>{monitor ? "Edit Monitor" : "New Monitor"}</DialogTitle>
        <DialogDescription>
          Configure a query that fires signals when matched.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-2">
          <Label htmlFor="mon-name">Monitor Name</Label>
          <Input id="mon-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="mon-type">Signal Type</Label>
            <select
              id="mon-type"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={type}
              onChange={(e) => setType(e.target.value as SignalType)}
            >
              <option value="funding">Funding</option>
              <option value="hiring">Hiring</option>
              <option value="forum">Forum</option>
              <option value="linkedin">LinkedIn</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label>Active</Label>
            <div className="flex h-10 items-center gap-2">
              <Switch checked={isActive} onCheckedChange={setIsActive} />
              <span className="text-sm text-muted-foreground">
                {isActive ? "Active" : "Paused"}
              </span>
            </div>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="mon-query">Query</Label>
          <Input
            id="mon-query"
            placeholder="e.g. funding_round:Series B AND industry:fintech"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Use field:value pairs joined by AND/OR.
          </p>
        </div>
      </div>
      <DialogFooter>
        <DialogClose onClose={onClose} />
        <Button onClick={submit} disabled={isPending || !name.trim() || !query.trim()}>
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}