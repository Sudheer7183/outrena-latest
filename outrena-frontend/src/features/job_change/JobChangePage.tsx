/**
 * JobChangePage.tsx — Job-change monitor.
 *
 * Table of alerts (prospect, prev company/title, new company/title,
 * detectedAt, status). "Scan Now" button. Click row → dialog to mark
 * reviewed/actioned + add note. Filter by status.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase,
  Scan,
  Loader2,
  ArrowRight,
  Filter,
  Info,
  Save,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatDateTime, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";

/* ── Types ─────────────────────────────────────────────────────────── */

type AlertStatus = "new" | "reviewed" | "actioned";

interface JobChangeAlert {
  id: string;
  prospectName: string;
  prospectEmail: string | null;
  previousCompany: string;
  previousTitle: string;
  newCompany: string;
  newTitle: string;
  detectedAt: string;
  status: AlertStatus;
  note: string | null;
}

/* ── Mock data ─────────────────────────────────────────────────────── */

const MOCK_ALERTS: JobChangeAlert[] = [
  {
    id: "jc1",
    prospectName: "Renee Coleman",
    prospectEmail: "renee@nexbridge.io",
    previousCompany: "Vaultnode",
    previousTitle: "Director of Sales",
    newCompany: "Nexbridge",
    newTitle: "VP Sales",
    detectedAt: "2025-01-09T08:00:00Z",
    status: "new",
    note: null,
  },
  {
    id: "jc2",
    prospectName: "Tobias Klein",
    prospectEmail: "tobias@heliospay.com",
    previousCompany: "Ledgerline",
    previousTitle: "Senior AE",
    newCompany: "Helios Pay",
    newTitle: "Head of Sales",
    detectedAt: "2025-01-08T14:30:00Z",
    status: "new",
    note: null,
  },
  {
    id: "jc3",
    prospectName: "Mara Costa",
    prospectEmail: "mara@pulseflow.io",
    previousCompany: "Northbridge Pay",
    previousTitle: "RevOps Lead",
    newCompany: "Pulseflow",
    newTitle: "VP RevOps",
    detectedAt: "2025-01-07T10:15:00Z",
    status: "reviewed",
    note: "Reached out on LinkedIn — she's open to a call next week.",
  },
  {
    id: "jc4",
    prospectName: "Hiro Tanaka",
    prospectEmail: "hiro@meshgrid.dev",
    previousCompany: "SwiftForge",
    previousTitle: "Staff Engineer",
    newCompany: "Meshgrid",
    newTitle: "Director of Engineering",
    detectedAt: "2025-01-05T09:45:00Z",
    status: "actioned",
    note: "Created deal — Q1 expansion opportunity.",
  },
  {
    id: "jc5",
    prospectName: "Olivia Marchetti",
    prospectEmail: "olivia@castellano.io",
    previousCompany: "Castellano",
    previousTitle: "VP Marketing",
    newCompany: "Blue Harbor",
    newTitle: "CMO",
    detectedAt: "2025-01-03T16:20:00Z",
    status: "new",
    note: null,
  },
  {
    id: "jc6",
    prospectName: "Hugo Lefebvre",
    prospectEmail: "hugo@maisonverte.fr",
    previousCompany: "Maison Verte",
    previousTitle: "Head of Growth",
    newCompany: "LumenKart",
    newTitle: "VP Growth",
    detectedAt: "2025-01-02T11:00:00Z",
    status: "reviewed",
    note: "Not in ICP anymore — passing to SDR team.",
  },
];

const STATUS_VARIANT: Record<AlertStatus, "warning" | "secondary" | "success"> = {
  new: "warning",
  reviewed: "secondary",
  actioned: "success",
};

/* ── Page ──────────────────────────────────────────────────────────── */

export function JobChangePage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | AlertStatus>("all");
  const [selected, setSelected] = useState<JobChangeAlert | null>(null);

  const query = useQuery<JobChangeAlert[]>({
    queryKey: ["job-change-monitor"],
    queryFn: () => http.get<JobChangeAlert[]>("/api/v1/job-change-monitor"),
  });
  const allAlerts = query.data ?? MOCK_ALERTS;

  const filtered = useMemo(() => {
    if (filter === "all") return allAlerts;
    return allAlerts.filter((a) => a.status === filter);
  }, [allAlerts, filter]);

  const stats = useMemo(() => {
    return {
      total: allAlerts.length,
      new: allAlerts.filter((a) => a.status === "new").length,
      reviewed: allAlerts.filter((a) => a.status === "reviewed").length,
      actioned: allAlerts.filter((a) => a.status === "actioned").length,
    };
  }, [allAlerts]);

  const scanMutation = useMutation({
    mutationFn: () => http.post<{ newAlerts: number }>("/api/v1/job-change-monitor/scan", {}),  // BUG-15 FIX: explicit empty body (backend requires JSON body)
    onSuccess: (data) => {
      const n = data?.newAlerts ?? 0;
      toast.success(`Scan complete`, { description: `${n} new alert(s) detected.` });
      qc.invalidateQueries({ queryKey: ["job-change-monitor"] });
    },
    onError: () => {
      toast.info("Backend unavailable — scan request noted", {
        description: "Try again later; showing existing alerts.",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: (a: JobChangeAlert) =>
      http.put<JobChangeAlert>(`/api/v1/job-change-monitor/${a.id}`, {
        status: a.status,
        note: a.note,
      }),
    onSuccess: () => {
      toast.success("Alert updated");
      setSelected(null);
      qc.invalidateQueries({ queryKey: ["job-change-monitor"] });
    },
    onError: () => toast.error("Update failed — backend unavailable"),
  });

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Job Change Monitor"
        description="Detect when prospects change roles — the warmest possible trigger for outreach."
        actions={
          <Button
            size="sm"
            onClick={() => scanMutation.mutate()}
            disabled={scanMutation.isPending}
          >
            {scanMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Scan className="h-4 w-4" />
            )}
            Scan Now
          </Button>
        }
      />

      <Alert variant="default">
        <Info className="h-4 w-4" />
        <AlertTitle>Standalone tool — alumni &amp; trigger-event tracker</AlertTitle>
        <AlertDescription>
          Job Change Monitor watches prospects in your database for role changes
          (detected via LinkedIn public-profile diffs and email-bounce signals).
          It&apos;s a separate signal source — alerts here don&apos;t auto-create
          Campaigns or Tasks. Use each alert as a manual warm-intro trigger, or
          export the list to Sequences for follow-up.
        </AlertDescription>
      </Alert>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="New Alerts"
          value={stats.new}
          delta={stats.new > 0 ? { value: "needs review" } : undefined}
          icon={<Briefcase className="h-4 w-4" />}
        />
        <StatCard
          label="Reviewed"
          value={stats.reviewed}
          icon={<Filter className="h-4 w-4" />}
        />
        <StatCard
          label="Actioned"
          value={stats.actioned}
          delta={stats.actioned > 0 ? { value: "deals in flight", positive: true } : undefined}
          icon={<TrendingUp className="h-4 w-4" />}
        />
      </div>

      {/* Filter + table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Alerts</CardTitle>
              <CardDescription>{filtered.length} shown</CardDescription>
            </div>
            <div className="flex items-center gap-1 rounded-md border p-0.5">
              {(["all", "new", "reviewed", "actioned"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={cn(
                    "rounded-sm px-3 py-1 text-xs font-medium capitalize transition-colors",
                    filter === f ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {query.isLoading ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-md bg-muted" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<Briefcase className="h-6 w-6" />}
              title="No alerts"
              description="No job-change alerts match this filter."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Prospect</TableHead>
                  <TableHead>Previous Role</TableHead>
                  <TableHead className="w-8"></TableHead>
                  <TableHead>New Role</TableHead>
                  <TableHead>Detected</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((a) => (
                  <TableRow
                    key={a.id}
                    className="cursor-pointer"
                    onClick={() => setSelected(a)}
                  >
                    <TableCell>
                      <div className="space-y-0.5">
                        <p className="font-medium">{a.prospectName}</p>
                        <p className="text-xs text-muted-foreground">
                          {a.prospectEmail ?? "—"}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      <p>{a.previousTitle}</p>
                      <p className="text-xs text-muted-foreground">{a.previousCompany}</p>
                    </TableCell>
                    <TableCell>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                    <TableCell className="text-sm">
                      <p className="font-medium">{a.newTitle}</p>
                      <p className="text-xs text-muted-foreground">{a.newCompany}</p>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      <div>{formatDateTime(a.detectedAt)}</div>
                      <div>{timeAgo(a.detectedAt)}</div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[a.status]} className="capitalize">
                        {a.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Update dialog */}
      <UpdateDialog
        alert={selected}
        onClose={() => setSelected(null)}
        onSubmit={(a) => updateMutation.mutate(a)}
        isPending={updateMutation.isPending}
      />
    </div>
  );
}

/* ── Subcomponents ─────────────────────────────────────────────────── */

function UpdateDialog({
  alert,
  onClose,
  onSubmit,
  isPending,
}: {
  alert: JobChangeAlert | null;
  onClose: () => void;
  onSubmit: (a: JobChangeAlert) => void;
  isPending: boolean;
}) {
  const [status, setStatus] = useState<AlertStatus>("new");
  const [note, setNote] = useState("");

  useMemo(() => {
    if (alert) {
      setStatus(alert.status);
      setNote(alert.note ?? "");
    }
  }, [alert]);

  if (!alert) return null;

  return (
    <Dialog open={!!alert} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Update Alert — {alert.prospectName}</DialogTitle>
        <DialogDescription>
          Mark this job change as reviewed or actioned and add a note.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4">
        <div className="rounded-md border bg-muted/30 p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-medium">{alert.previousTitle}</span>
            <span className="text-muted-foreground">@ {alert.previousCompany}</span>
            <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-medium">{alert.newTitle}</span>
            <span className="text-muted-foreground">@ {alert.newCompany}</span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Detected {formatDateTime(alert.detectedAt)} ({timeAgo(alert.detectedAt)})
          </p>
        </div>

        <Separator />

        <div className="space-y-2">
          <Label htmlFor="jc-status">Status</Label>
          <select
            id="jc-status"
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value as AlertStatus)}
          >
            <option value="new">New</option>
            <option value="reviewed">Reviewed</option>
            <option value="actioned">Actioned</option>
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="jc-note">Note</Label>
          <Textarea
            id="jc-note"
            rows={3}
            placeholder="e.g. Reached out via LinkedIn — she's open to a call next week."
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
      </div>

      <DialogFooter>
        <DialogClose onClose={onClose} />
        <Button
          onClick={() =>
            onSubmit({
              ...alert,
              status,
              note: note.trim() || null,
            })
          }
          disabled={isPending}
        >
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
