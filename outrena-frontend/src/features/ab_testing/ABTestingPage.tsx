/**
 * ABTestingPage.tsx - create, run, and evaluate A/B tests on campaign
 * subject lines / bodies, with statistical-significance results and a
 * winner-promotion flow.
 *
 * API (verified against app/features/ab_testing/router.py + schemas):
 *   GET    /api/v1/ab-testing?campaign_id=        -> AbTestResponse[]
 *   POST   /api/v1/ab-testing                       AbTestCreate -> AbTestResponse
 *   GET    /api/v1/ab-testing/:id                   -> AbTestResponse
 *   PUT    /api/v1/ab-testing/:id                    AbTestUpdate { status?, startedAt?, endedAt? }
 *   DELETE /api/v1/ab-testing/:id
 *   POST   /api/v1/ab-testing/:id/start              -> AbTestResponse (sets status=running + startedAt)
 *   GET    /api/v1/ab-testing/:id/significance       -> SignificanceResult (two-proportion z-test)
 *   GET    /api/v1/campaigns                          -> for the campaign selector
 *   GET    /api/v1/sequences?campaign_id=&limit=500   -> for the Promote Winner flow
 *   PUT    /api/v1/sequences/:id                      { subjectLine?, bodyCopy? } -> used by Promote Winner
 *
 * CORRECTIONS vs. the previous version:
 *   - `element` is `"subject" | "body" | "sendTime"` in the real schema -
 *     there is no `"angle"` variable type (the gap doc's description
 *     included it; the backend model does not support it). The create
 *     dialog only offers the three real options.
 *   - `SignificanceResult` is a FLAT object (variantACount, variantBCount,
 *     variantASuccesses, variantBSuccesses, variantARate, variantBRate,
 *     zScore, pValue, isSignificant, winner) - the previous code expected
 *     a `perVariant: [...]` array that doesn't exist on the backend at all
 *     and silently fell back to MOCK_SIG on every real response. Fixed to
 *     read the actual flat fields; all mock fallbacks removed.
 *   - "successes" in the significance result is `isPositiveReply` on the
 *     per-prospect assignment (confirmed in ab_testing/service.py) - i.e.
 *     positive reply rate, not opens. Labeled accurately as such.
 *   - There is no endpoint exposing individual AbTestAssignment rows, so
 *     the "per-prospect assignment breakdown table" the gap doc describes
 *     (AB-3) cannot be built from real data - the Results dialog shows the
 *     real aggregate stats and states this limitation instead of faking
 *     table rows.
 *   - There is no dedicated pause/stop/promote-winner endpoint. Pause/stop
 *     use the general `PUT {status}` update. "Promote Winner" (AB-4) is
 *     implemented by fetching the campaign's not-yet-sent sequences at the
 *     test's touchNumber and PUTing the winning variant's subject/body to
 *     each one - there is no bulk-apply endpoint, so this is orchestrated
 *     client-side against the real per-sequence update endpoint.
 *
 * AB-1  Create A/B Test dialog: name, campaign, element, variant content, split ratio.
 * AB-2  Test list with status badge + start/pause/resume/stop actions.
 * AB-3  Results dialog: variant A/B stats, winner badge, significance indicator.
 * AB-4  Promote winner - applies winning variant to not-yet-sent sequences.
 */
import {  useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FlaskConical,
  Loader2,
  Pause,
  Play,
  Plus,
  Rocket,
  Square,
  Trash2,
  Trophy,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect as Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";

/* Types (aligned with real backend schemas) */

interface AbTest {
  id: string;
  name: string;
  campaignId: string;
  description: string | null;
  element: "subject" | "body" | "sendTime";
  variantALabel: string;
  variantBLabel: string;
  variantASubject: string | null;
  variantBSubject: string | null;
  variantABody: string | null;
  variantBBody: string | null;
  splitRatio: number;
  status: string;
  touchNumber: number;
  startedAt: string | null;
  endedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

interface SignificanceResult {
  abTestId: string;
  variantACount: number;
  variantBCount: number;
  variantASuccesses: number;
  variantBSuccesses: number;
  variantARate: number;
  variantBRate: number;
  zScore: number;
  pValue: number;
  isSignificant: boolean;
  winner: "A" | "B" | null;
}

interface Campaign {
  id: string;
  name: string;
}

interface Sequence {
  id: string;
  campaignId: string;
  touchNumber: number;
  status: string;
}

const ELEMENT_OPTIONS: { value: AbTest["element"]; label: string }[] = [
  { value: "subject", label: "Subject Line" },
  { value: "body", label: "Email Body" },
  { value: "sendTime", label: "Send Time" },
];

const STATUS_META: Record<
  string,
  { label: string; variant: "secondary" | "success" | "warning" | "outline" }
> = {
  draft: { label: "Draft", variant: "secondary" },
  running: { label: "Running", variant: "success" },
  paused: { label: "Paused", variant: "warning" },
  completed: { label: "Completed", variant: "outline" },
};

function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, variant: "secondary" as const };
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

function normaliseList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: T[] }).items ?? [];
  return [];
}

const EMPTY_FORM = {
  name: "",
  campaignId: "",
  description: "",
  element: "subject" as AbTest["element"],
  variantALabel: "Variant A",
  variantBLabel: "Variant B",
  variantASubject: "",
  variantBSubject: "",
  variantABody: "",
  variantBBody: "",
  splitRatio: 0.5,
  touchNumber: 1,
};

export function ABTestingPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [resultsTest, setResultsTest] = useState<AbTest | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AbTest | null>(null);

  const testsQ = useQuery({
    queryKey: ["ab-testing"],
    queryFn: () =>
      http.get<unknown>("/api/v1/ab-testing").then((r) => normaliseList<AbTest>(r)),
  });
  const tests = testsQ.data ?? [];

  const campaignsQ = useQuery({
    queryKey: ["campaigns", "for-ab-testing"],
    queryFn: () =>
      http.get<unknown>("/api/v1/campaigns").then((r) => normaliseList<Campaign>(r)),
  });
  const campaigns = campaignsQ.data ?? [];

  function campaignName(id: string): string {
    return campaigns.find((c) => c.id === id)?.name ?? id;
  }

  const createMutation = useMutation({
    mutationFn: () =>
      http.post<AbTest>("/api/v1/ab-testing", {
        name: form.name,
        campaignId: form.campaignId,
        description: form.description || null,
        element: form.element,
        variantALabel: form.variantALabel,
        variantBLabel: form.variantBLabel,
        variantASubject: form.element === "subject" ? form.variantASubject || null : null,
        variantBSubject: form.element === "subject" ? form.variantBSubject || null : null,
        variantABody: form.element === "body" ? form.variantABody || null : null,
        variantBBody: form.element === "body" ? form.variantBBody || null : null,
        splitRatio: form.splitRatio,
        touchNumber: form.touchNumber,
      }),
    onSuccess: () => {
      toast.success("A/B test created");
      qc.invalidateQueries({ queryKey: ["ab-testing"] });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
    },
    onError: () => toast.error("Failed to create test"),
  });

  const startMutation = useMutation({
    mutationFn: (id: string) => http.post<AbTest>(`/api/v1/ab-testing/${id}/start`, {}),
    onSuccess: () => {
      toast.success("Test started");
      qc.invalidateQueries({ queryKey: ["ab-testing"] });
    },
    onError: () => toast.error("Failed to start test"),
  });

  const statusMutation = useMutation({
    mutationFn: ({
      id,
      status,
      endedAt,
    }: {
      id: string;
      status: string;
      endedAt?: string;
    }) => http.put<AbTest>(`/api/v1/ab-testing/${id}`, { status, endedAt }),
    onSuccess: (_res, { status }) => {
      toast.success(`Test ${status}`);
      qc.invalidateQueries({ queryKey: ["ab-testing"] });
    },
    onError: () => toast.error("Failed to update test"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/ab-testing/${id}`),
    onSuccess: () => {
      toast.success("Test deleted");
      qc.invalidateQueries({ queryKey: ["ab-testing"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete test"),
  });

  function handleCreate() {
    if (!form.name.trim() || !form.campaignId) {
      toast.error("Name and campaign are required");
      return;
    }
    createMutation.mutate();
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="A/B Testing"
        description="Test subject lines, email bodies, and send times against each other with statistical significance."
        actions={
          <Dialog
            open={createOpen}
            onOpenChange={(o) => {
              setCreateOpen(o);
              if (!o) setForm(EMPTY_FORM);
            }}
          >
            <DialogTrigger asChild>
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create Test
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create A/B Test</DialogTitle>
                <DialogDescription>
                  Split-test a single element between two variants on a
                  chosen touch of the sequence.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Test Name</Label>
                  <Input
                    placeholder="e.g. Subject line - urgency vs curiosity"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Campaign</Label>
                  <Select
                    value={form.campaignId}
                    onChange={(e) => setForm((f) => ({ ...f, campaignId: e.target.value }))}
                  >
                    <option value="">Select a campaign…</option>
                    {campaigns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label>Element</Label>
                    <Select
                      value={form.element}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          element: e.target.value as AbTest["element"],
                        }))
                      }
                    >
                      {ELEMENT_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Touch Number</Label>
                    <Select
                      value={String(form.touchNumber)}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, touchNumber: Number(e.target.value) }))
                      }
                    >
                      {[1, 2, 3, 4, 5, 6, 7].map((t) => (
                        <option key={t} value={t}>
                          Touch {t}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>

                {form.element === "sendTime" && (
                  <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">
                    Send-time tests don't have dedicated per-variant time
                    fields on the backend yet — this creates the test and
                    tracks significance the same way, but variant content
                    below is optional and won't drive a different send time.
                  </p>
                )}

                {form.element === "subject" && (
                  <div className="grid grid-cols-1 gap-3">
                    <div className="space-y-2">
                      <Label>{form.variantALabel} — Subject</Label>
                      <Input
                        value={form.variantASubject}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, variantASubject: e.target.value }))
                        }
                        placeholder="Subject line for Variant A"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{form.variantBLabel} — Subject</Label>
                      <Input
                        value={form.variantBSubject}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, variantBSubject: e.target.value }))
                        }
                        placeholder="Subject line for Variant B"
                      />
                    </div>
                  </div>
                )}

                {form.element === "body" && (
                  <div className="grid grid-cols-1 gap-3">
                    <div className="space-y-2">
                      <Label>{form.variantALabel} — Body</Label>
                      <Textarea
                        value={form.variantABody}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, variantABody: e.target.value }))
                        }
                        placeholder="Email body for Variant A"
                        rows={4}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{form.variantBLabel} — Body</Label>
                      <Textarea
                        value={form.variantBBody}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, variantBBody: e.target.value }))
                        }
                        placeholder="Email body for Variant B"
                        rows={4}
                      />
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <Label>
                    Split Ratio — {Math.round(form.splitRatio * 100)}% / {Math.round((1 - form.splitRatio) * 100)}%
                  </Label>
                  <Input
                    type="range"
                    min={0.1}
                    max={0.9}
                    step={0.05}
                    value={form.splitRatio}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, splitRatio: parseFloat(e.target.value) }))
                    }
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Fraction of prospects assigned to {form.variantALabel}.
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setCreateOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreate} disabled={createMutation.isPending}>
                  {createMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                  ) : null}
                  Create Test
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      {testsQ.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : testsQ.isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Failed to load A/B tests.</p>
            <Button onClick={() => testsQ.refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : tests.length === 0 ? (
        <EmptyState
          icon={<FlaskConical className="h-6 w-6" />}
          title="No A/B Tests Yet"
          description="Create your first test to compare subject lines, bodies, or send times."
          action={
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Test
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {tests.map((t) => {
            const meta = statusMeta(t.status);
            return (
              <Card key={t.id}>
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div
                      className="flex-1 min-w-0 cursor-pointer"
                      onClick={() => setResultsTest(t)}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-sm">{t.name}</span>
                        <Badge variant={meta.variant} className="text-[10px]">
                          {meta.label}
                        </Badge>
                        <Badge variant="outline" className="text-[10px]">
                          {ELEMENT_OPTIONS.find((o) => o.value === t.element)?.label ??
                            t.element}
                        </Badge>
                        <Badge variant="outline" className="text-[10px]">
                          Touch {t.touchNumber}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {campaignName(t.campaignId)}
                        {t.description ? ` · ${t.description}` : ""}
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        {t.variantALabel} ({Math.round(t.splitRatio * 100)}%) vs{" "}
                        {t.variantBLabel} ({Math.round((1 - t.splitRatio) * 100)}%)
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {t.status === "draft" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => startMutation.mutate(t.id)}
                          disabled={startMutation.isPending}
                        >
                          <Play className="h-3.5 w-3.5 mr-1" />
                          Start
                        </Button>
                      )}
                      {t.status === "running" && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              statusMutation.mutate({ id: t.id, status: "paused" })
                            }
                          >
                            <Pause className="h-3.5 w-3.5 mr-1" />
                            Pause
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              statusMutation.mutate({
                                id: t.id,
                                status: "completed",
                                endedAt: new Date().toISOString(),
                              })
                            }
                          >
                            <Square className="h-3.5 w-3.5 mr-1" />
                            Stop
                          </Button>
                        </>
                      )}
                      {t.status === "paused" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            statusMutation.mutate({ id: t.id, status: "running" })
                          }
                        >
                          <Play className="h-3.5 w-3.5 mr-1" />
                          Resume
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setResultsTest(t)}
                      >
                        Results
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-red-500 hover:text-red-600"
                        onClick={() => setDeleteTarget(t)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {resultsTest && (
        <ResultsDialog
          test={resultsTest}
          campaignName={campaignName(resultsTest.campaignId)}
          onClose={() => setResultsTest(null)}
        />
      )}

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete A/B test?</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `"${deleteTarget.name}" will be permanently removed. This action cannot be undone.`
                : "This A/B test will be permanently removed."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ── Results dialog (AB-3) + Promote Winner (AB-4) ── */

function ResultsDialog({
  test,
  campaignName,
  onClose,
}: {
  test: AbTest;
  campaignName: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [promoting, setPromoting] = useState(false);

  const sigQ = useQuery({
    queryKey: ["ab-testing", test.id, "significance"],
    queryFn: () =>
      http.get<SignificanceResult>(`/api/v1/ab-testing/${test.id}/significance`),
  });
  const sig = sigQ.data;

  const promoteMutation = useMutation({
    mutationFn: async (winner: "A" | "B") => {
      const winningSubject = winner === "A" ? test.variantASubject : test.variantBSubject;
      const winningBody = winner === "A" ? test.variantABody : test.variantBBody;

      const sequences = await http
        .get<unknown>(
          `/api/v1/sequences?campaign_id=${test.campaignId}&limit=500`,
        )
        .then((r) => normaliseList<Sequence>(r));

      const targets = sequences.filter(
        (s) =>
          s.touchNumber === test.touchNumber &&
          ["Draft", "QaFailed", "QaPassed", "Scheduled"].includes(s.status),
      );

      if (targets.length === 0) {
        throw new Error("No unsent sequences found at this touch to promote to");
      }

      await Promise.all(
        targets.map((s) =>
          http.put(`/api/v1/sequences/${s.id}`, {
            ...(winningSubject ? { subjectLine: winningSubject } : {}),
            ...(winningBody ? { bodyCopy: winningBody } : {}),
          }),
        ),
      );
      return targets.length;
    },
    onSuccess: (count) => {
      toast.success(`Winning variant applied to ${count} unsent touch(es)`);
      qc.invalidateQueries({ queryKey: ["sequences"] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Failed to promote winner"),
    onSettled: () => setPromoting(false),
  });

  function handlePromote() {
    if (!sig?.winner) return;
    setPromoting(true);
    promoteMutation.mutate(sig.winner);
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{test.name} — Results</DialogTitle>
          <DialogDescription>
            {campaignName} · Touch {test.touchNumber} ·{" "}
            {ELEMENT_OPTIONS.find((o) => o.value === test.element)?.label}
          </DialogDescription>
        </DialogHeader>

        {sigQ.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : sig ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <VariantCard
                label={test.variantALabel}
                count={sig.variantACount}
                successes={sig.variantASuccesses}
                rate={sig.variantARate}
                isWinner={sig.winner === "A"}
              />
              <VariantCard
                label={test.variantBLabel}
                count={sig.variantBCount}
                successes={sig.variantBSuccesses}
                rate={sig.variantBRate}
                isWinner={sig.winner === "B"}
              />
            </div>

            <div
              className={`rounded-md border p-3 text-sm ${
                sig.isSignificant
                  ? "border-emerald-300 bg-emerald-50"
                  : "border-amber-300 bg-amber-50"
              }`}
            >
              <p className="font-medium">
                {sig.isSignificant
                  ? `Statistically significant (p = ${sig.pValue.toFixed(4)})`
                  : `Not yet significant (p = ${sig.pValue.toFixed(4)})`}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                z-score: {sig.zScore.toFixed(3)} · "successes" here means a
                positive reply, per the backend's two-proportion z-test.
              </p>
              {!sig.isSignificant && (
                <p className="text-xs text-muted-foreground mt-1">
                  Keep the test running to gather more sends — significance
                  requires p &lt; 0.05.
                </p>
              )}
            </div>

            <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
              A per-prospect assignment breakdown isn't shown here — the
              backend's significance endpoint returns aggregate stats only;
              no endpoint exposes individual variant-assignment rows.
            </div>

            {sig.winner && (
              <Button
                onClick={handlePromote}
                disabled={promoting || promoteMutation.isPending}
                className="w-full"
              >
                {promoting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Rocket className="h-4 w-4 mr-2" />
                )}
                Promote Variant {sig.winner} to remaining unsent touches
              </Button>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground py-6 text-center">
            No significance data available yet.
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function VariantCard({
  label,
  count,
  successes,
  rate,
  isWinner,
}: {
  label: string;
  count: number;
  successes: number;
  rate: number;
  isWinner: boolean;
}) {
  return (
    <Card className={isWinner ? "border-amber-400 bg-amber-50/50" : ""}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-1.5">
          {label}
          {isWinner && <Trophy className="h-4 w-4 text-amber-500" />}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <p className="text-2xl font-bold">{pct(rate)}</p>
        <p className="text-xs text-muted-foreground">
          {successes} positive replies / {count} sent
        </p>
      </CardContent>
    </Card>
  );
}