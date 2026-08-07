/**
 * AlumniTrackerPage.tsx — Alumni / Job-Change Tracker.
 *
 * Tracks former prospects who changed jobs and re-surfaces them as warm leads.
 * Uses the job-change-monitor API for scanning + listing alumni alerts.
 *
 * Layout:
 *  - 5 KPI cards (Total Tracked, New Alerts, ICP Matches, Contacted, Re-converted)
 *  - "Run Scan" button → POST /api/v1/job-change-monitor/scan
 *  - Alumni list table
 *  - "How It Works" section
 */
// import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase,
  // RefreshCw,
  Target,
  Mail,
  RotateCcw,
  AlertCircle,
  Loader2,
  Search,
  Eye,
  // ArrowRight,
  CheckCircle2,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/ui/stat-card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

/* ── Types ─────────────────────────────────────────────────────────── */

interface AlumniAlert {
  id: string;
  prospectName: string;
  previousCompany: string;
  newCompany: string;
  alertDate: string;
  icpMatch: boolean;
  icpProfileName?: string;
  contacted: boolean;
  reconverted: boolean;
}

interface ScanResult {
  scanned: number;
  newAlerts: number;
}

/* ── Page ──────────────────────────────────────────────────────────── */

export function AlumniTrackerPage() {
  const qc = useQueryClient();

  const alertsQuery = useQuery<AlumniAlert[]>({
    queryKey: ["alumni-alerts"],
    queryFn: () =>
      http
        .get<any>("/api/v1/job-change-monitor")
        .then((r: any) => (Array.isArray(r) ? r : r?.items ?? [])),
  });

  const alerts = alertsQuery.data ?? [];

  const scanMut = useMutation({
    mutationFn: () => http.post<ScanResult>("/api/v1/job-change-monitor/scan"),
    onSuccess: (data) => {
      toast.success(`Scan complete: ${data.newAlerts} new alert(s) found`);
      qc.invalidateQueries({ queryKey: ["alumni-alerts"] });
    },
    onError: () => {
      toast.error("Scan failed — backend unavailable");
    },
  });

  // KPIs derived from alerts
  const totalTracked = alerts.length;
  const newAlerts = alerts.filter((a) => !a.contacted).length;
  const icpMatches = alerts.filter((a) => a.icpMatch).length;
  const contacted = alerts.filter((a) => a.contacted).length;
  const reconverted = alerts.filter((a) => a.reconverted).length;

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Alumni Tracker"
        description="Track former prospects who changed jobs and re-surface them as warm leads."
      />

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-5">
        <StatCard
          label="Total Tracked"
          value={totalTracked}
          icon={<Briefcase className="h-4 w-4" />}
        />
        <StatCard
          label="New Alerts"
          value={newAlerts}
          icon={<AlertCircle className="h-4 w-4" />}
          delta={newAlerts > 0 ? { value: "action", positive: true } : undefined}
        />
        <StatCard
          label="ICP Matches"
          value={icpMatches}
          icon={<Target className="h-4 w-4" />}
        />
        <StatCard
          label="Contacted"
          value={contacted}
          icon={<Mail className="h-4 w-4" />}
        />
        <StatCard
          label="Re-converted"
          value={reconverted}
          icon={<RotateCcw className="h-4 w-4" />}
          delta={reconverted > 0 ? { value: `${reconverted}`, positive: true } : undefined}
        />
      </div>

      {/* Scan button + Alumni Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Alumni Alerts</CardTitle>
              <CardDescription>
                Job-change events for your past prospects.
              </CardDescription>
            </div>
            <Button
              size="sm"
              onClick={() => scanMut.mutate()}
              disabled={scanMut.isPending}
            >
              {scanMut.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              {scanMut.isPending ? "Scanning…" : "Run Scan"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {alertsQuery.isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <EmptyState
              icon={<Briefcase className="h-6 w-6" />}
              title="No alumni alerts yet"
              description="Run a scan to detect job changes among your past prospects."
              action={
                <Button size="sm" onClick={() => scanMut.mutate()} disabled={scanMut.isPending}>
                  {scanMut.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  Run Scan
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Previous Company</TableHead>
                  <TableHead>New Company</TableHead>
                  <TableHead>Alert Date</TableHead>
                  <TableHead>ICP Match</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-medium">{a.prospectName}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {a.previousCompany}
                    </TableCell>
                    <TableCell className="text-sm font-medium">
                      {a.newCompany}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {timeAgo(a.alertDate)}
                    </TableCell>
                    <TableCell>
                      {a.icpMatch ? (
                        <Badge variant="success">
                          {a.icpProfileName ?? "ICP Match"}
                        </Badge>
                      ) : (
                        <Badge variant="secondary">No</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={a.contacted}
                          onClick={() =>
                            toast.info(`Contacting ${a.prospectName} — feature coming soon`)
                          }
                        >
                          {a.contacted ? (
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          ) : (
                            <Mail className="h-3.5 w-3.5" />
                          )}
                          {a.contacted ? "Contacted" : "Contact"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            toast.info(`Viewing ${a.prospectName} details — feature coming soon`)
                          }
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* How It Works */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">How It Works</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 sm:grid-cols-3">
            <div className="space-y-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                <span className="text-lg font-bold">1</span>
              </div>
              <p className="text-sm font-medium">Detect Job Changes</p>
              <p className="text-xs text-muted-foreground">
                The scanner monitors LinkedIn and other sources for job changes
                among your past prospects. When a change is detected, an alert
                is created automatically.
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                <span className="text-lg font-bold">2</span>
              </div>
              <p className="text-sm font-medium">Match Against ICP Profiles</p>
              <p className="text-xs text-muted-foreground">
                Each job-change alert is compared against your ICP profiles. If
                the prospect&apos;s new role matches an ICP, they&apos;re flagged as a warm
                lead with a suggested connection note.
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                <span className="text-lg font-bold">3</span>
              </div>
              <p className="text-sm font-medium">Re-engage &amp; Convert</p>
              <p className="text-xs text-muted-foreground">
                Reach out to matched alumni with a personalised congratulations
                message. Since they already know your brand, re-conversion rates
                are 3–5× higher than cold outreach.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
