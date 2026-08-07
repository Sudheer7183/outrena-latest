/**
 * CompetitorsPage.tsx — Competitor radar.
 *
 * Table of competitors (name, domain, category, threatLevel badge,
 * lastSeenAt, mentions). Add Competitor dialog. Run Radar Scan button
 * → toast + shows new mentions panel. Per-row threat level badge.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Radar,
  Plus,
  Pencil,
  Trash2,
  Globe,
  ShieldAlert,
  Loader2,
  Save,
  TrendingUp,
  MessageSquare,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, timeAgo, truncate } from "@/lib/utils";
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
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Info } from "lucide-react";
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
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ScrollArea } from "@/components/ui/scroll-area";

/* ── Types ─────────────────────────────────────────────────────────── */

type ThreatLevel = "low" | "medium" | "high" | "critical";

interface Competitor {
  id: string;
  name: string;
  domain: string;
  category: string;
  threatLevel: ThreatLevel;
  lastSeenAt: string;
  mentions: number;
  notes: string | null;
}

interface RadarMention {
  id: string;
  competitorName: string;
  source: string;
  snippet: string;
  url: string;
  detectedAt: string;
}

/* ── Mock data ─────────────────────────────────────────────────────── */

const MOCK_COMPETITORS: Competitor[] = [
  {
    id: "comp1",
    name: "Apollo.io",
    domain: "apollo.io",
    category: "Sales Intel",
    threatLevel: "high",
    lastSeenAt: "2025-01-09T14:00:00Z",
    mentions: 312,
    notes: "Dominant in SMB sales intel; expanding into workflows.",
  },
  {
    id: "comp2",
    name: "Clay",
    domain: "clay.com",
    category: "Outbound Enrichment",
    threatLevel: "critical",
    lastSeenAt: "2025-01-10T11:30:00Z",
    mentions: 198,
    notes: "Strong ICP+enrichment narrative; same buyer.",
  },
  {
    id: "comp3",
    name: "Outreach",
    domain: "outreach.io",
    category: "Sales Engagement",
    threatLevel: "medium",
    lastSeenAt: "2025-01-08T09:15:00Z",
    mentions: 540,
    notes: "Add-on AI features; not core to our niche.",
  },
  {
    id: "comp4",
    name: "Lavender",
    domain: "lavender.ai",
    category: "Email AI",
    threatLevel: "low",
    lastSeenAt: "2025-01-04T16:45:00Z",
    mentions: 64,
    notes: "Email-coaching only; no sourcing or ICP.",
  },
  {
    id: "comp5",
    name: "Common Room",
    domain: "commonroom.io",
    category: "Community Signals",
    threatLevel: "medium",
    lastSeenAt: "2025-01-07T13:20:00Z",
    mentions: 121,
    notes: "Strong community-signal detection; we overlap on intent.",
  },
];

const MOCK_NEW_MENTIONS: RadarMention[] = [
  mkM("m1", "Clay", "Reddit r/sales", "Anyone using Clay + OUTRENA together? Curious if the enrichment stacks.", "https://reddit.com/r/sales/xyz", "2025-01-10T08:30:00Z"),
  mkM("m2", "Apollo.io", "LinkedIn Post", "Apollo just shipped a 'Flow Builder' — looks like it competes with OUTRENA Autopilot.", "https://linkedin.com/post/abc", "2025-01-10T10:00:00Z"),
  mkM("m3", "Common Room", "G2 Review", "User says Common Room's signal detection is similar to OUTRENA's intent monitor.", "https://g2.com/review/123", "2025-01-09T18:00:00Z"),
  mkM("m4", "Outreach", "Twitter / X", "Outreach's new AI email writer — early access impressions thread.", "https://x.com/outreach/status/1", "2025-01-09T14:15:00Z"),
];

function mkM(
  id: string,
  competitorName: string,
  source: string,
  snippet: string,
  url: string,
  detectedAt: string,
): RadarMention {
  return { id, competitorName, source, snippet, url, detectedAt };
}

const THREAT_META: Record<ThreatLevel, { variant: "secondary" | "warning" | "destructive" | "outline"; label: string; dot: string }> = {
  low: { variant: "outline", label: "Low", dot: "bg-slate-400" },
  medium: { variant: "warning", label: "Medium", dot: "bg-amber-500" },
  high: { variant: "destructive", label: "High", dot: "bg-red-500" },
  critical: { variant: "destructive", label: "Critical", dot: "bg-red-700" },
};

/* ── Page ──────────────────────────────────────────────────────────── */

export function CompetitorsPage() {
  const qc = useQueryClient();
  const [edit, setEdit] = useState<Competitor | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [newMentions, setNewMentions] = useState<RadarMention[] | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Competitor | null>(null);

  const query = useQuery<Competitor[]>({
    queryKey: ["competitors"],
    queryFn: () => http.get<Competitor[]>("/api/v1/competitors"),
  });
  const competitors = query.data ?? MOCK_COMPETITORS;

  const stats = useMemo(() => {
    return {
      total: competitors.length,
      critical: competitors.filter((c) => c.threatLevel === "critical").length,
      high: competitors.filter((c) => c.threatLevel === "high").length,
      mentions: competitors.reduce((s, c) => s + c.mentions, 0),
    };
  }, [competitors]);

  const saveMutation = useMutation({
    mutationFn: (c: Competitor) => {
      if (competitors.some((x) => x.id === c.id)) {
        return http.put(`/api/v1/competitors/${c.id}`, c);
      }
      return http.post("/api/v1/competitors", c);
    },
    onSuccess: () => {
      toast.success("Competitor saved");
      setEdit(null);
      setAddOpen(false);
      qc.invalidateQueries({ queryKey: ["competitors"] });
    },
    onError: () => toast.error("Save failed — backend unavailable"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/competitors/${id}`),
    onSuccess: () => {
      toast.success("Competitor deleted");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["competitors"] });
    },
    onError: () => toast.error("Delete failed — backend unavailable"),
  });

  const scanMutation = useMutation({
    mutationFn: () => http.post<RadarMention[]>("/api/v1/competitor-radar"),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["competitors"] });
      const mentions = data ?? MOCK_NEW_MENTIONS;
      setNewMentions(mentions);
      toast.success(`Radar scan complete`, {
        description: `${mentions.length} new mention(s) detected.`,
      });
    },
    onError: () => {
      setNewMentions(MOCK_NEW_MENTIONS);
      toast.info("Backend unavailable — showing demo mentions");
    },
  });

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Competitor Radar"
        description="Track competitors, monitor mentions, and assess threat levels across the market."
        actions={
          <Button
            size="sm"
            onClick={() => scanMutation.mutate()}
            disabled={scanMutation.isPending}
          >
            {scanMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Radar className="h-4 w-4" />
            )}
            Run Radar Scan
          </Button>
        }
      />

      <Alert variant="default">
        <Info className="h-4 w-4" />
        <AlertTitle>Standalone tool — market intelligence only</AlertTitle>
        <AlertDescription>
          Competitor Radar monitors the market for threat signals and competitor
          mentions. It does not feed into Campaigns, Sequences, or ICP scoring —
          use it as an early-warning system to inform your GTM thesis and
          collateral positioning. Scan results are persisted for trend analysis.
        </AlertDescription>
      </Alert>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-4">
        <StatCard
          label="Tracked Competitors"
          value={stats.total}
          icon={<Radar className="h-4 w-4" />}
        />
        <StatCard
          label="Critical Threats"
          value={stats.critical}
          delta={stats.critical > 0 ? { value: "needs attention" } : undefined}
          icon={<ShieldAlert className="h-4 w-4" />}
        />
        <StatCard
          label="High Threats"
          value={stats.high}
          icon={<ShieldAlert className="h-4 w-4" />}
        />
        <StatCard
          label="Total Mentions"
          value={stats.mentions}
          delta={stats.mentions > 100 ? { value: "active coverage", positive: true } : undefined}
          icon={<MessageSquare className="h-4 w-4" />}
        />
      </div>

      {/* New mentions panel */}
      {newMentions && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4" />
              New Mentions from Latest Scan
            </CardTitle>
            <CardDescription>{newMentions.length} mention(s) detected in the last scan.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea maxHeightClass="max-h-72">
              <ul className="divide-y">
                {newMentions.map((m) => (
                  <li key={m.id} className="space-y-1 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">{m.competitorName}</Badge>
                        <span className="text-xs text-muted-foreground">{m.source}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">{timeAgo(m.detectedAt)}</span>
                    </div>
                    <p className="text-sm">{truncate(m.snippet, 220)}</p>
                    <a
                      href={m.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-primary underline"
                    >
                      View source
                    </a>
                  </li>
                ))}
              </ul>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {/* Table */}
      {query.isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Failed to load competitors. Please try again.
            </p>
            <Button onClick={() => query.refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Tracked Competitors</CardTitle>
              <CardDescription>{competitors.length} competitors</CardDescription>
            </div>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" />
              Add Competitor
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {query.isLoading ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-md bg-muted" />
              ))}
            </div>
          ) : competitors.length === 0 ? (
            <EmptyState
              icon={<Globe className="h-6 w-6" />}
              title="No competitors tracked"
              description="Add a competitor to start monitoring mentions."
              action={
                <Button size="sm" onClick={() => setAddOpen(true)}>
                  <Plus className="h-4 w-4" />
                  Add Competitor
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Domain</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Threat Level</TableHead>
                  <TableHead>Mentions</TableHead>
                  <TableHead>Last Seen</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {competitors.filter(Boolean).map((c) => {
                  // BUG-16 FIX: filter(Boolean) guards against undefined array items after save
                  const meta = THREAT_META[c.threatLevel] ?? THREAT_META.low;
                  return (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">{c.name}</TableCell>
                      <TableCell>
                        <a
                          href={`https://${c.domain}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-primary underline"
                        >
                          {c.domain}
                        </a>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">{c.category}</TableCell>
                      <TableCell>
                        <Badge variant={meta.variant} className="gap-1.5">
                          <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
                          {meta.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm font-medium">{c.mentions}</span>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {timeAgo(c.lastSeenAt)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="icon"
                                variant="ghost"
                                aria-label="Edit"
                                onClick={() => setEdit(c)}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Edit competitor</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="icon"
                                variant="ghost"
                                aria-label="Delete"
                                onClick={() => setDeleteTarget(c)}
                              >
                                <Trash2 className="h-4 w-4 text-red-600" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Delete competitor</TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      )}

      {/* Add/Edit dialog */}
      <CompetitorDialog
        open={!!edit || addOpen}
        competitor={edit}
        onClose={() => {
          setEdit(null);
          setAddOpen(false);
        }}
        onSubmit={(c) => saveMutation.mutate(c)}
        isPending={saveMutation.isPending}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete competitor?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.name
              ? `Competitor "${deleteTarget.name}" and its mention history will be permanently removed. This action cannot be undone.`
              : "This competitor will be permanently removed. This action cannot be undone."}
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
    </div>
  );
}

/* ── Subcomponents ─────────────────────────────────────────────────── */

function CompetitorDialog({
  open,
  competitor,
  onClose,
  onSubmit,
  isPending,
}: {
  open: boolean;
  competitor: Competitor | null;
  onClose: () => void;
  onSubmit: (c: Competitor) => void;
  isPending: boolean;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [category, setCategory] = useState("");
  const [threatLevel, setThreatLevel] = useState<ThreatLevel>("medium");
  const [notes, setNotes] = useState("");

  useMemo(() => {
    setName(competitor?.name ?? "");
    setDomain(competitor?.domain ?? "");
    setCategory(competitor?.category ?? "");
    setThreatLevel(competitor?.threatLevel ?? "medium");
    setNotes(competitor?.notes ?? "");
  }, [competitor, open]);

  function submit() {
    if (!name.trim() || !domain.trim()) return;
    onSubmit({
      id: competitor?.id ?? `comp-${Date.now()}`,
      name: name.trim(),
      domain: domain.trim().replace(/^https?:\/\//, ""),
      category: category.trim() || "Uncategorized",
      threatLevel: threatLevel,
      lastSeenAt: competitor?.lastSeenAt ?? new Date().toISOString(),
      mentions: competitor?.mentions ?? 0,
      notes: notes.trim() || null,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>{competitor ? "Edit Competitor" : "Add Competitor"}</DialogTitle>
        <DialogDescription>Track a competitor and their threat level.</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="comp-name">Name</Label>
            <Input id="comp-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="comp-domain">Domain</Label>
            <Input
              id="comp-domain"
              placeholder="acme.com"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="comp-category">Category</Label>
            <Input
              id="comp-category"
              placeholder="e.g. Sales Intel"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="comp-threat">Threat Level</Label>
            <select
              id="comp-threat"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={threatLevel}
              onChange={(e) => setThreatLevel(e.target.value as ThreatLevel)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="comp-notes">Notes</Label>
          <Textarea
            id="comp-notes"
            rows={3}
            placeholder="Why does this competitor matter?"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
      </div>
      <DialogFooter>
        <DialogClose onClose={onClose} />
        <Button onClick={submit} disabled={isPending || !name.trim() || !domain.trim()}>
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
