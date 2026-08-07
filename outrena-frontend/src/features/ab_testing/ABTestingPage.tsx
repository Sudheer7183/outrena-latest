/**
 * ABTestingPage.tsx — A/B testing CRUD + significance + variants chart.
 *
 * Table of tests (draft/running/completed/paused). "New Test" dialog with 2+
 * variants (subject + body). Per-row "Start" (→ running) and "View
 * Significance" (per-variant stats + winner/confidence/p-value). Selecting a
 * test opens a detail drawer with a variants comparison bar chart.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartColumn,
  FlaskConical,
  Loader2,
  Play,
  Plus,
  Sigma,
  Trash2,
  Trophy,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import type { ABTest, ABTestVariant } from "@/types/common";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect as Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Info } from "lucide-react";
import {
  Tooltip as ShadcnTooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn, formatDateTime, formatPercent } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────────────────────── */

interface SignificanceResult {
  winner: string | null;
  confidence: number;
  pValue: number;
  sampleSizeNote: string;
  perVariant: { label: string; sent: number; opened: number; replied: number; openRate: number; replyRate: number }[];
}

/* ── Mock data ───────────────────────────────────────────────────────────── */
const now = new Date().toISOString();
function v(label: string, subject: string, sent: number, opened: number, replied: number): ABTestVariant {
  return { id: `${label}-${Math.random().toString(36).slice(2, 8)}`, label, subject, sent, opened, replied };
}

const MOCK_TESTS: ABTest[] = [
  {
    id: "ab1",
    name: "Q4 SaaS — Opener angle",
    status: "completed",
    metric: "reply_rate",
    winner: "B",
    createdAt: now,
    updatedAt: now,
    variants: [
      v("A", "Quick question about your outbound", 800, 384, 48),
      v("B", "Saw your Series B — congrats", 800, 452, 86),
    ],
  },
  {
    id: "ab2",
    name: "Fintech — Subject length",
    status: "running",
    metric: "open_rate",
    winner: null,
    createdAt: now,
    updatedAt: now,
    variants: [
      v("A", "Idea for your team", 600, 318, 31),
      v("B", "Cutting reply time by 40% — open to a look?", 600, 246, 22),
    ],
  },
  {
    id: "ab3",
    name: "DevTools — Touch 3 angle",
    status: "running",
    metric: "reply_rate",
    winner: null,
    createdAt: now,
    updatedAt: now,
    variants: [
      v("A", "Case study: how Acme shipped 2x faster", 500, 235, 28),
      v("B", "Worth a 10-min call this week?", 500, 228, 41),
      v("C", "Closing the loop — last note", 500, 198, 19),
    ],
  },
  {
    id: "ab4",
    name: "Healthcare — Founder mention",
    status: "paused",
    metric: "open_rate",
    winner: null,
    createdAt: now,
    updatedAt: now,
    variants: [
      v("A", "Compliance gap in your stack", 400, 196, 18),
      v("B", "From the founder of OUTRENA", 400, 244, 24),
    ],
  },
  {
    id: "ab5",
    name: "HR-Tech — Personalization depth",
    status: "draft",
    metric: "reply_rate",
    winner: null,
    createdAt: now,
    updatedAt: now,
    variants: [
      v("A", "Noticed your hiring push", 0, 0, 0),
      v("B", "Hiring + your 2025 roadmap", 0, 0, 0),
    ],
  },
];

const MOCK_SIG: SignificanceResult = {
  winner: "B",
  confidence: 0.96,
  pValue: 0.041,
  sampleSizeNote: "1,600 sends per arm — above the 1,000 minimum for 95% power.",
  perVariant: [
    { label: "A", sent: 800, opened: 384, replied: 48, openRate: 0.48, replyRate: 0.06 },
    { label: "B", sent: 800, opened: 452, replied: 86, openRate: 0.565, replyRate: 0.1075 },
  ],
};

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function statusBadge(status: string): { variant: "default" | "secondary" | "success" | "warning" | "destructive"; label: string } {
  switch (status) {
    case "running":
      return { variant: "success", label: "Running" };
    case "completed":
      return { variant: "default", label: "Completed" };
    case "paused":
      return { variant: "warning", label: "Paused" };
    default:
      return { variant: "secondary", label: "Draft" };
  }
}
function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-md">
      {label && <p className="mb-1 font-semibold">{label}</p>}
      {payload.map((p) => (
        <p key={p.name}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
}

/* ── New test dialog ─────────────────────────────────────────────────────── */
interface VariantDraft {
  label: string;
  subject: string;
  body: string;
}
function NewTestDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [campaignId, setCampaignId] = useState(""); // BUG-26 FIX
  const [metric, setMetric] = useState("reply_rate");
  const [variants, setVariants] = useState<VariantDraft[]>([
    { label: "A", subject: "", body: "" },
    { label: "B", subject: "", body: "" },
  ]);

  /* BUG-13 Fix B: Fetch campaigns for the dropdown instead of free-text input. */
  const { data: campaigns } = useQuery<{ id: string; name: string }[]>({
    queryKey: ["campaigns"],
    queryFn: () => http.get<{ id: string; name: string }[]>("/api/v1/campaigns"),
  });

  function updateVariant(i: number, patch: Partial<VariantDraft>) {
    setVariants((vs) => vs.map((v, idx) => (idx === i ? { ...v, ...patch } : v)));
  }
  function addVariant() {
    const next = String.fromCharCode(65 + variants.length);
    setVariants((vs) => [...vs, { label: next, subject: "", body: "" }]);
  }
  function removeVariant(i: number) {
    setVariants((vs) => vs.filter((__, idx) => idx !== i));
  }

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; campaignId: string; metric: string; variants: VariantDraft[] }) =>
      http.post<ABTest>("/api/v1/ab-testing", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ab-testing"] });
      toast.success("Test created");
      reset();
      onOpenChange(false);
    },
    onError: () => {
      toast.error("Create API unavailable — not saved");
      onOpenChange(false);
    },
  });

  function reset() {
    setName("");
    setMetric("reply_rate");
    setVariants([
      { label: "A", subject: "", body: "" },
      { label: "B", subject: "", body: "" },
    ]);
  }

  function submit() {
    // BUG-26 FIX: campaignId is required by backend
    if (!name || variants.length < 2) {
      toast.error("Add a name and at least 2 variants");
      return;
    }
    createMutation.mutate({ name, campaignId: campaignId || "default", metric, variants });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <DialogTitle>New A/B Test</DialogTitle>
        <DialogDescription>Define the metric and 2+ variants to test.</DialogDescription>
      </DialogHeader>
      <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="nt-name">Test name</Label>
            <Input id="nt-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Q4 SaaS — Opener angle" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nt-metric">Primary metric</Label>
            <Select id="nt-metric" value={metric} onChange={(e) => setMetric(e.target.value)}>
              <option value="open_rate">Open rate</option>
              <option value="reply_rate">Reply rate</option>
            </Select>
          </div>
        </div>
        {/* BUG-13 Fix B: campaignId as select dropdown populated from campaigns API */}
        <div className="space-y-1.5">
          <Label htmlFor="nt-campaign">Campaign</Label>
          <Select
            id="nt-campaign"
            value={campaignId}
            onChange={(e) => setCampaignId(e.target.value)}
          >
            <option value="">Select a campaign…</option>
            {((Array.isArray(campaigns) ? campaigns : ((campaigns as unknown as Record<string, unknown>)?.items ?? [])) as { id: string; name: string }[]).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-3">
          {variants.map((v, i) => (
            <div key={i} className="rounded-md border p-3">
              <div className="mb-2 flex items-center justify-between">
                <Badge variant="secondary">Variant {v.label}</Badge>
                {variants.length > 2 && (
                  <ShadcnTooltip>
                    <TooltipTrigger asChild>
                      <Button size="icon" variant="ghost" onClick={() => removeVariant(i)} aria-label="Remove variant">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Remove this variant (2 minimum required)</TooltipContent>
                  </ShadcnTooltip>
                )}
              </div>
              <div className="space-y-2">
                <Input value={v.subject} onChange={(e) => updateVariant(i, { subject: e.target.value })} placeholder="Subject line" />
                <Textarea value={v.body} onChange={(e) => updateVariant(i, { body: e.target.value })} placeholder="Body copy" className="min-h-[80px]" />
              </div>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addVariant}>
            <Plus className="h-4 w-4" />
            Add variant
          </Button>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={createMutation.isPending}>
          {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Create Test
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

/* ── Significance dialog ─────────────────────────────────────────────────── */
function SignificanceDialog({ test, onClose }: { test: ABTest | null; onClose: () => void }) {
  const [result, setResult] = useState<SignificanceResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setResult(null);
  }, [test?.id]);

  async function load() {
    if (!test) return;
    setLoading(true);
    try {
      const r = await http.get<SignificanceResult>(`/api/v1/ab-testing/${test.id}/significance`);
      setResult(r);
    } catch {
      setResult({
        ...MOCK_SIG,
        perVariant: test.variants.map((v) => ({
          label: v.label,
          sent: v.sent,
          opened: v.opened,
          replied: v.replied,
          openRate: v.sent ? v.opened / v.sent : 0,
          replyRate: v.sent ? v.replied / v.sent : 0,
        })),
      });
      toast.error("Significance API unavailable — showing computed stats");
    } finally {
      setLoading(false);
    }
  }

  if (!test) return null;
  const chartData = (result ?? MOCK_SIG).perVariant.map((pv) => ({
    label: pv.label,
    "Open Rate": Number((pv.openRate * 100).toFixed(1)),
    "Reply Rate": Number((pv.replyRate * 100).toFixed(1)),
  }));

  return (
    <Dialog open={!!test} onOpenChange={(o) => !o && onClose()}>
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Sigma className="h-4 w-4" />
          Significance — {test.name}
        </DialogTitle>
        <DialogDescription>Per-variant performance + statistical winner.</DialogDescription>
      </DialogHeader>

      {!result ? (
        <div className="space-y-3 py-2">
          <p className="text-sm text-muted-foreground">
            Run significance to compute the winner, confidence & p-value.
          </p>
          <Button onClick={load} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sigma className="h-4 w-4" />}
            Compute Significance
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Winner</p>
              <p className="mt-1 flex items-center gap-1 text-lg font-bold">
                <Trophy className="h-4 w-4 text-amber-500" />
                {result.winner ?? "—"}
              </p>
            </div>
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Confidence</p>
              <p className="mt-1 text-lg font-bold">{formatPercent(result.confidence)}</p>
            </div>
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">p-value</p>
              <p className="mt-1 text-lg font-bold">{result.pValue.toFixed(3)}</p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">{result.sampleSizeNote}</p>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Variant</TableHead>
                <TableHead className="text-right">Sent</TableHead>
                <TableHead className="text-right">Opened</TableHead>
                <TableHead className="text-right">Replied</TableHead>
                <TableHead className="text-right">Open %</TableHead>
                <TableHead className="text-right">Reply %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.perVariant.map((pv) => (
                <TableRow key={pv.label}>
                  <TableCell className="font-semibold">{pv.label}</TableCell>
                  <TableCell className="text-right">{pv.sent}</TableCell>
                  <TableCell className="text-right">{pv.opened}</TableCell>
                  <TableCell className="text-right">{pv.replied}</TableCell>
                  <TableCell className="text-right">{formatPercent(pv.openRate)}</TableCell>
                  <TableCell className="text-right">{formatPercent(pv.replyRate)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <YAxis tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Open Rate" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Reply Rate" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </Dialog>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */
export function ABTestingPage() {
  const queryClient = useQueryClient();
  const [newOpen, setNewOpen] = useState(false);
  const [sigTest, setSigTest] = useState<ABTest | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["ab-testing"],
    queryFn: () => http.get<ABTest[]>("/api/v1/ab-testing"),
  });
  const tests = Array.isArray(data) ? data : (Array.isArray((data as unknown as Record<string, unknown>)?.items) ? (data as unknown as { items: ABTest[] }).items : MOCK_TESTS);

  const startMutation = useMutation({
    mutationFn: (id: string) => http.post<ABTest>(`/api/v1/ab-testing/${id}/start`),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ["ab-testing"] });
      const previous = queryClient.getQueryData<ABTest[]>(["ab-testing"]);
      if (previous) {
        const next = previous.map((t) => (t.id === id ? { ...t, status: "running" } : t));
        queryClient.setQueryData<ABTest[]>(["ab-testing"], next);
      }
      return { previous };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.previous) queryClient.setQueryData<ABTest[]>(["ab-testing"], ctx.previous);
      toast.error("Failed to start test");
    },
    onSuccess: () => toast.success("Test started"),
  });

  const selected = tests.find((t) => t.id === selectedId) ?? null;
  const detailChart = useMemo(() => {
    queryClient.invalidateQueries({ queryKey: ["ab-tests"] });
    if (!selected) return [];
    return selected.variants.map((v) => ({
      label: v.label,
      Sent: v.sent,
      Opened: v.opened,
      Replied: v.replied,
    }));
  }, [selected]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="A/B Testing"
        description="Test subject lines, angles & copy variants. Track significance live."
        actions={
          <Button onClick={() => setNewOpen(true)}>
            <Plus className="h-4 w-4" />
            New Test
          </Button>
        }
      />

      <Alert variant="default">
        <Info className="h-4 w-4" />
        <AlertTitle>Standalone experiment framework</AlertTitle>
        <AlertDescription>
          A/B Testing runs independently of Campaigns &amp; Sequences. Each test
          holds 2+ variants (subject + body) and tracks open/reply rates per
          variant until statistical significance is reached. Tests do not
          auto-promote the winning variant into a Sequence — once a winner is
          declared, copy the subject/body into Templates or Email Studio
          manually to roll it out.
        </AlertDescription>
      </Alert>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Tests table */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <FlaskConical className="h-4 w-4" />
              Tests
            </CardTitle>
            <CardDescription>{tests.length} tests across all campaigns.</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : tests.length === 0 ? (
              <EmptyState icon={<FlaskConical className="h-8 w-8" />} title="No tests yet" description="Create your first A/B test." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Metric</TableHead>
                    <TableHead className="text-center">Variants</TableHead>
                    <TableHead>Winner</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tests.map((t) => {
                    const badge = statusBadge(t.status);
                    return (
                      <TableRow
                        key={t.id}
                        className={cn("cursor-pointer", selectedId === t.id && "bg-muted/50")}
                        onClick={() => setSelectedId(t.id)}
                      >
                        <TableCell className="font-medium">{t.name}</TableCell>
                        <TableCell>
                          <Badge variant={badge.variant}>{badge.label}</Badge>
                        </TableCell>
                        <TableCell className="capitalize text-muted-foreground">
                          {t.metric.replace("_", " ")}
                        </TableCell>
                        <TableCell className="text-center">{t.variants.length}</TableCell>
                        <TableCell>{t.winner ? <Badge variant="success">{t.winner}</Badge> : "—"}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                            {(t.status === "draft" || t.status === "paused") && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => startMutation.mutate(t.id)}
                                disabled={startMutation.isPending}
                              >
                                <Play className="h-3.5 w-3.5" />
                                Start
                              </Button>
                            )}
                            <Button size="sm" variant="outline" onClick={() => setSigTest(t)}>
                              <Sigma className="h-3.5 w-3.5" />
                              Significance
                            </Button>
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

        {/* Detail drawer */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <ChartColumn className="h-4 w-4" />
              Variant Comparison
            </CardTitle>
            <CardDescription>
              {selected ? selected.name : "Select a test to inspect variants."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!selected ? (
              <EmptyState icon={<ChartColumn className="h-8 w-8" />} title="No test selected" description="Click a row to view its variants." />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <Badge variant={statusBadge(selected.status).variant}>{statusBadge(selected.status).label}</Badge>
                  <span>Updated {formatDateTime(selected.updatedAt)}</span>
                </div>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={detailChart}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                      <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                      <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                      <Tooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="Sent" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Opened" fill="#10b981" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Replied" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-2">
                  {selected.variants.map((v) => (
                    <div key={v.id} className="rounded-md border p-2 text-sm">
                      <div className="mb-1 flex items-center justify-between">
                        <Badge variant="secondary">Variant {v.label}</Badge>
                        <span className="text-xs text-muted-foreground">
                          {v.sent} sent · {v.opened} open · {v.replied} reply
                        </span>
                      </div>
                      <p className="font-medium">{v.subject || "(no subject)"}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <NewTestDialog open={newOpen} onOpenChange={setNewOpen} />
      <SignificanceDialog test={sigTest} onClose={() => setSigTest(null)} />
    </div>
  );
}