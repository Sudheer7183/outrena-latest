/**
 * AlumniTrackerPage.tsx — Alumni / Job-Change Tracker.
 *
 * Gaps closed:
 *   AT-1  Manual scan trigger → POST /api/v1/job-change-monitor/scan
 *         Body: { prospectIds: null } scans all prospects
 *   AT-2  Last Scan Results card — shows scanned count, detected count,
 *         and list of newly-detected job changes from JobChangeScanResponse
 *   AT-3  Job-Change Alerts table — old title/company → new title/company
 *         with ArrowRight transition, ICP match badge + fit score,
 *         status workflow (new → viewed → contacted → converted),
 *         search + status filter, dismiss action
 *
 * API contract (job_change_monitor.py):
 *   GET  /api/v1/job-change-monitor          → JobChangeAlertResponse[]
 *   POST /api/v1/job-change-monitor/scan     → JobChangeScanResponse
 *   PUT  /api/v1/job-change-monitor/{id}     → JobChangeAlertResponse
 *
 * JobChangeAlertResponse: { id, prospectId, previousCompany, previousTitle,
 *   newCompany, newTitle, newDomain, newLinkedinUrl, detectedAt, icpProfileId,
 *   icpFitScore, icpPersona, matchReason, status, notes, scanSource,
 *   lastScannedAt, createdAt, updatedAt }
 *
 * JobChangeScanResponse: { scanned, detected, newAlerts: JobChangeAlertResponse[] }
 *
 * Note: API returns prospectId (not prospectName) — prospect names are
 * looked up from /api/v1/prospects and joined client-side.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  Mail,
  Radar,
  RotateCcw,
  Search,
  Target,
  TrendingUp,
  UserCheck,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, timeAgo } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/ui/stat-card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/* ── Backend types ──────────────────────────────────────────────────────── */

interface JobChangeAlertResponse {
  id: string;
  prospectId: string;
  previousCompany: string | null;
  previousTitle: string | null;
  newCompany: string;
  newTitle: string | null;
  newDomain: string | null;
  newLinkedinUrl: string | null;
  detectedAt: string;
  icpProfileId: string | null;
  icpFitScore: number | null;
  icpPersona: string | null;
  matchReason: string | null;
  status: string; // new | viewed | contacted | converted | dismissed
  notes: string | null;
  scanSource: string;
  lastScannedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

interface JobChangeScanResponse {
  scanned: number;
  detected: number;
  newAlerts: JobChangeAlertResponse[];
}

interface ProspectLite {
  id: string;
  firstName: string;
  lastName: string;
  email: string | null;
  linkedinUrl: string | null;
}

/* ── Status config ──────────────────────────────────────────────────────── */

const STATUS_CHIP: Record<string, string> = {
  new: "bg-emerald-100 text-emerald-700 border-emerald-200",
  viewed: "bg-blue-100 text-blue-700 border-blue-200",
  contacted: "bg-amber-100 text-amber-700 border-amber-200",
  converted: "bg-violet-100 text-violet-700 border-violet-200",
  dismissed: "bg-slate-100 text-slate-500 border-slate-200",
};

const STATUS_NEXT: Record<string, { label: string; next: string; icon: React.ReactNode } | null> = {
  new: { label: "Mark viewed", next: "viewed", icon: <Clock className="h-3 w-3" /> },
  viewed: { label: "Mark contacted", next: "contacted", icon: <Mail className="h-3 w-3" /> },
  contacted: { label: "Mark converted", next: "converted", icon: <TrendingUp className="h-3 w-3" /> },
  converted: null,
  dismissed: null,
};

/* ── Page ───────────────────────────────────────────────────────────────── */

export function AlumniTrackerPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [scanResult, setScanResult] = useState<JobChangeScanResponse | null>(null);

  /* ── Queries ── */

  const alertsQuery = useQuery<JobChangeAlertResponse[]>({
    queryKey: ["alumni-alerts"],
    queryFn: () => http.get<JobChangeAlertResponse[]>("/api/v1/job-change-monitor"),
    retry: false,
  });

  const prospectsQuery = useQuery<ProspectLite[]>({
    queryKey: ["prospects", "lite"],
    queryFn: () =>
      http.get<unknown>("/api/v1/prospects").then((r) =>
        Array.isArray(r) ? r : ((r as { items?: ProspectLite[] })?.items ?? [])
      ),
    retry: false,
  });

  const alerts = alertsQuery.data ?? [];
  const prospectMap = Object.fromEntries(
    (prospectsQuery.data ?? []).map((p) => [p.id, p])
  ) as Record<string, ProspectLite>;

  /* ── Mutations ── */

  // AT-1 — Run scan
  const scanMut = useMutation({
    mutationFn: () =>
      http.post<JobChangeScanResponse>("/api/v1/job-change-monitor/scan", {}),
    onSuccess: (data) => {
      setScanResult(data);
      toast.success(
        `Scan complete — ${data.scanned} prospects checked, ${data.detected} job changes detected`
      );
      qc.invalidateQueries({ queryKey: ["alumni-alerts"] });
    },
    onError: () => toast.error("Scan failed — check backend logs"),
  });

  // Status update
  const updateMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      http.put<JobChangeAlertResponse>(`/api/v1/job-change-monitor/${id}`, {
        status,
      }),
    onSuccess: (_, vars) => {
      toast.success(`Marked as ${vars.status}`);
      qc.invalidateQueries({ queryKey: ["alumni-alerts"] });
    },
    onError: () => toast.error("Failed to update status"),
  });

  /* ── Derived metrics ── */

  const totalTracked = alerts.length;
  const newCount = alerts.filter((a) => a.status === "new").length;
  const icpMatchCount = alerts.filter((a) => Boolean(a.icpProfileId)).length;
  const contactedCount = alerts.filter((a) => a.status === "contacted").length;
  const convertedCount = alerts.filter((a) => a.status === "converted").length;

  /* ── Filtered list ── */

  const filtered = alerts.filter((a) => {
    const p = prospectMap[a.prospectId];
    const name = p ? `${p.firstName} ${p.lastName}` : "";
    const matchSearch =
      !search ||
      name.toLowerCase().includes(search.toLowerCase()) ||
      (a.newCompany ?? "").toLowerCase().includes(search.toLowerCase()) ||
      (a.previousCompany ?? "").toLowerCase().includes(search.toLowerCase()) ||
      (a.icpPersona ?? "").toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || a.status === statusFilter;
    return matchSearch && matchStatus && a.status !== "dismissed";
  });

  /* ── Render ── */

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alumni Tracker"
        description="Watches past prospects for job changes — flags re-engagement opportunities when they land at an ICP-matched account."
        actions={
          <Button
            size="sm"
            onClick={() => scanMut.mutate()}
            disabled={scanMut.isPending}
          >
            {scanMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Radar className="h-4 w-4" />
            )}
            {scanMut.isPending ? "Scanning…" : "Run Scan"}
          </Button>
        }
      />

      {/* KPI cards */}
      <div className="grid gap-4 grid-cols-2 sm:grid-cols-5">
        <StatCard
          label="Total Tracked"
          value={totalTracked}
          icon={<UserCheck className="h-4 w-4" />}
        />
        <StatCard
          label="New Alerts"
          value={newCount}
          icon={<AlertCircle className="h-4 w-4" />}
          delta={newCount > 0 ? { value: "action needed", positive: true } : undefined}
        />
        <StatCard
          label="ICP Matches"
          value={icpMatchCount}
          icon={<Target className="h-4 w-4" />}
        />
        <StatCard
          label="Contacted"
          value={contactedCount}
          icon={<Mail className="h-4 w-4" />}
        />
        <StatCard
          label="Re-converted"
          value={convertedCount}
          icon={<RotateCcw className="h-4 w-4" />}
          delta={
            convertedCount > 0
              ? { value: String(convertedCount), positive: true }
              : undefined
          }
        />
      </div>

      {/* AT-2 — Last Scan Results card */}
      {scanResult && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-primary" />
              Last Scan Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Prospects scanned: </span>
                <span className="font-bold">{scanResult.scanned}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Job changes detected: </span>
                <span className="font-bold text-emerald-600">
                  {scanResult.detected}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">No change: </span>
                <span className="font-bold">
                  {scanResult.scanned - scanResult.detected}
                </span>
              </div>
            </div>
            {scanResult.detected > 0 && (
              <p className="text-xs text-muted-foreground">
                {scanResult.detected} new alert{scanResult.detected !== 1 ? "s" : ""} added — see the table below.
              </p>
            )}
            {scanResult.detected === 0 && scanResult.scanned > 0 && (
              <p className="text-xs text-muted-foreground">
                No job changes detected for these prospects. This is expected for test data — the LLM uses real-world knowledge to detect actual job moves.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* AT-3 — Alerts table */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <CardTitle className="text-base">Job-Change Alerts</CardTitle>
              <CardDescription>
                Past prospects who moved to a new company. ICP matches are your
                highest-priority re-engagement targets.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search + filter */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name, company, ICP persona…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="new">New</SelectItem>
                <SelectItem value="viewed">Viewed</SelectItem>
                <SelectItem value="contacted">Contacted</SelectItem>
                <SelectItem value="converted">Converted</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Table */}
          {alertsQuery.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<UserCheck className="h-8 w-8" />}
              title={
                alerts.length === 0
                  ? "No alumni alerts yet"
                  : "No alerts match your filters"
              }
              description={
                alerts.length === 0
                  ? 'Click "Run Scan" to check your prospects for job changes. The AI searches the web and LinkedIn for role changes, then matches the new company against your ICP profiles.'
                  : "Try adjusting your search or status filter."
              }
              action={
                alerts.length === 0 ? (
                  <Button
                    size="sm"
                    onClick={() => scanMut.mutate()}
                    disabled={scanMut.isPending}
                  >
                    {scanMut.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Radar className="h-4 w-4" />
                    )}
                    Run First Scan
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Alumnus</TableHead>
                    <TableHead>Previous Role</TableHead>
                    <TableHead className="w-6"></TableHead>
                    <TableHead>New Role</TableHead>
                    <TableHead>ICP Match</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Detected</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((alert) => {
                    const prospect = prospectMap[alert.prospectId];
                    const prospectName = prospect
                      ? `${prospect.firstName} ${prospect.lastName}`
                      : alert.prospectId;
                    const linkedinUrl =
                      alert.newLinkedinUrl ?? prospect?.linkedinUrl ?? null;
                    const nextAction = STATUS_NEXT[alert.status];

                    return (
                      <TableRow key={alert.id}>
                        {/* Alumnus */}
                        <TableCell>
                          <div className="space-y-0.5">
                            <p className="font-medium text-sm">{prospectName}</p>
                            {prospect?.email && (
                              <p className="text-xs text-muted-foreground">
                                {prospect.email}
                              </p>
                            )}
                            {linkedinUrl && (
                              <a
                                href={linkedinUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                              >
                                LinkedIn{" "}
                                <ExternalLink className="h-2.5 w-2.5" />
                              </a>
                            )}
                          </div>
                        </TableCell>
                        {/* Previous role */}
                        <TableCell className="text-xs">
                          <p className="font-medium">
                            {alert.previousTitle ?? "—"}
                          </p>
                          <p className="text-muted-foreground">
                            {alert.previousCompany ?? "—"}
                          </p>
                        </TableCell>
                        {/* Arrow */}
                        <TableCell>
                          <ArrowRight className="h-4 w-4 text-muted-foreground" />
                        </TableCell>
                        {/* New role */}
                        <TableCell className="text-xs">
                          <p className="font-medium text-emerald-700">
                            {alert.newTitle ?? "—"}
                          </p>
                          <p className="text-muted-foreground">
                            {alert.newCompany}
                          </p>
                          {alert.newDomain && (
                            <p className="text-[10px] text-muted-foreground">
                              {alert.newDomain}
                            </p>
                          )}
                        </TableCell>
                        {/* ICP Match */}
                        <TableCell>
                          {alert.icpProfileId ? (
                            <div className="space-y-1">
                              <Badge
                                variant="outline"
                                className="text-[10px] bg-violet-50 text-violet-700 border-violet-200"
                              >
                                {alert.icpPersona ?? "ICP Match"}
                              </Badge>
                              {alert.icpFitScore != null && (
                                <p className="text-[10px] text-muted-foreground">
                                  {Math.round(alert.icpFitScore)}% fit
                                </p>
                              )}
                              {alert.matchReason && (
                                <p
                                  className="text-[10px] text-muted-foreground max-w-[160px] truncate"
                                  title={alert.matchReason}
                                >
                                  {alert.matchReason}
                                </p>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              —
                            </span>
                          )}
                        </TableCell>
                        {/* Status */}
                        <TableCell>
                          <span
                            className={cn(
                              "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize",
                              STATUS_CHIP[alert.status] ?? STATUS_CHIP.new
                            )}
                          >
                            {alert.status}
                          </span>
                        </TableCell>
                        {/* Detected */}
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {timeAgo(alert.detectedAt)}
                        </TableCell>
                        {/* Actions */}
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            {nextAction && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 text-xs"
                                title={nextAction.label}
                                onClick={() =>
                                  updateMut.mutate({
                                    id: alert.id,
                                    status: nextAction.next,
                                  })
                                }
                                disabled={updateMut.isPending}
                              >
                                {nextAction.icon}
                                <span className="sr-only">
                                  {nextAction.label}
                                </span>
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs text-muted-foreground hover:text-destructive"
                              title="Dismiss alert"
                              onClick={() =>
                                updateMut.mutate({
                                  id: alert.id,
                                  status: "dismissed",
                                })
                              }
                              disabled={updateMut.isPending}
                            >
                              ✕
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* How it works (shown when no alerts yet) */}
      {alerts.length === 0 && !alertsQuery.isLoading && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">How It Works</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                {
                  icon: <Building2 className="h-4 w-4" />,
                  step: "1",
                  title: "Closed-won prospects tracked",
                  desc: "Every prospect linked to a closed-won deal becomes an alumnus automatically.",
                },
                {
                  icon: <Radar className="h-4 w-4" />,
                  step: "2",
                  title: "Web + LinkedIn scan",
                  desc: "The AI searches the web for each person to detect if they've changed companies.",
                },
                {
                  icon: <TrendingUp className="h-4 w-4" />,
                  step: "3",
                  title: "ICP match + re-engage",
                  desc: "If the new company fits an ICP, you get an alert with fit score and match reason.",
                },
              ].map((item) => (
                <div key={item.step} className="space-y-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <span className="text-base font-bold">{item.step}</span>
                  </div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">{item.desc}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}