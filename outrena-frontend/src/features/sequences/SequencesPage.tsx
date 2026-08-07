/**
 * SequencesPage.tsx — OUTRENA Phase 4 (Task 3-C)
 *
 * 7-touch sequence cadence editor. Horizontal touch timeline + expandable
 * editor with subject-line variants, schedule, send-now, save, and CSV export.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  Download,
  ListChecks,
  Mail,
  Plus,
  Save,
  Send,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatDate, formatDateTime } from "@/lib/utils";
import type { EmailStatus, Sequence, TouchAngle } from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

/* ── Types & mocks ──────────────────────────────────────────────────────── */

interface CadenceSpec {
  touch: number;
  day: number;
  angle: TouchAngle;
  label: string;
}
interface SubjectLine {
  id: string;
  text: string;
  qaScore: number | null;
}

interface CampaignLite {
  id: string;
  name: string;
}
interface ProspectLite {
  id: string;
  name: string;
  company: string | null;
}

const CADENCE: CadenceSpec[] = [
  { touch: 1, day: 1, angle: "FirstTouch", label: "First touch" },
  { touch: 2, day: 4, angle: "NewEvidence", label: "New evidence" },
  { touch: 3, day: 9, angle: "DifferentPain", label: "Different pain" },
  { touch: 4, day: 16, angle: "IndustryInsight", label: "Industry insight" },
  { touch: 5, day: 25, angle: "DirectQuestion", label: "Direct question" },
  { touch: 6, day: 35, angle: "Breakup", label: "Breakup" },
  { touch: 7, day: 49, angle: "IndustryInsight", label: "Final value touch" },
];

const STATUS_VARIANT: Record<EmailStatus, "secondary" | "success" | "warning" | "destructive" | "outline" | "default"> = {
  Draft: "secondary",
  QaFailed: "destructive",
  QaPassed: "success",
  Scheduled: "warning",
  Sent: "success",
  Replied: "default",
  Bounced: "destructive",
  Failed: "destructive",
};

const MOCK_CAMPAIGNS: CampaignLite[] = [
  { id: "c1", name: "Q1 Outbound — Fintech Ops" },
  { id: "c2", name: "Cybersec SOC Automation" },
];

const MOCK_PROSPECTS: ProspectLite[] = [
  { id: "p1", name: "Jordan Avery", company: "Northbeam" },
  { id: "p2", name: "Priya Shah", company: "Helix Pay" },
  { id: "p3", name: "Marcus Chen", company: "Loop Capital" },
];

const MOCK_SUBJECTS: SubjectLine[] = [
  { id: "s1", text: "Northbeam's close-cycle SLA — 12 hours late?", qaScore: 0.84 },
  { id: "s2", text: "Reconciliation eating your close cycle?", qaScore: 0.71 },
];

function mockSequence(campaignId: string, prospectId: string): Sequence[] {
  const statuses: EmailStatus[] = [
    "Sent",
    "Sent",
    "Sent",
    "Scheduled",
    "QaPassed",
    "QaPassed",
    "Draft",
  ];
  return CADENCE.map((c, i) => ({
    id: `seq_${campaignId}_${prospectId}_${c.touch}`,
    campaignId,
    prospectId,
    touchNumber: c.touch,
    sendDay: c.day,
    channel: "email",
    angle: c.angle,
    framework: i % 2 === 0 ? "trigger" : "value",
    subjectLine:
      c.touch === 1
        ? "Northbeam's close-cycle SLA — 12 hours late?"
        : c.touch === 2
          ? "Reconciliation eating your close cycle?"
          : c.touch === 3
            ? "A different angle on Northbeam's ops load"
            : c.touch === 4
              ? "Industry insight: fintech close-cycle benchmarks"
              : c.touch === 5
                ? "Quick question on your reconciliation stack"
                : c.touch === 6
                  ? "Closing the loop — should I break up with you?"
                  : "Last note: 60% faster close, ROI breakdown",
    bodyCopy: `Hi {{firstName}},\n\nTouch ${c.touch} (${c.angle}). Body copy placeholder for ${c.label}.`,
    qaScore: c.touch <= 3 ? 0.84 : c.touch === 4 ? 0.78 : 0.72,
    qaDetails: "[]",
    personalisationConfidence: 0.74,
    flagForManualReview: c.touch === 6,
    status: statuses[i],
    scheduledFor: c.touch === 4 ? "2025-01-22T15:00:00Z" : null,
    sentAt: c.touch <= 3 ? `2025-01-${String(c.day).padStart(2, "0")}T15:00:00Z` : null,
    createdAt: "2024-12-02T10:00:00Z",
    updatedAt: "2025-01-08T14:23:00Z",
  }));
}

/* ── Page ───────────────────────────────────────────────────────────────── */

export function SequencesPage() {
  const qc = useQueryClient();

  const campaignsQ = useQuery({
    queryKey: ["campaigns-lite"],
    queryFn: () => http.get<CampaignLite[]>("/api/v1/campaigns"),
    retry: false,
  });
  const campaignsList = Array.isArray(campaignsQ.data) && campaignsQ.data.length > 0 ? campaignsQ.data : MOCK_CAMPAIGNS;

  const prospectsQ = useQuery({
    queryKey: ["prospects-lite"],
    queryFn: () => http.get<ProspectLite[]>("/api/v1/prospects"),
    retry: false,
  });
  const prospectsList = Array.isArray(prospectsQ.data) && prospectsQ.data.length > 0 ? prospectsQ.data : MOCK_PROSPECTS;

  const [campaignId, setCampaignId] = useState(MOCK_CAMPAIGNS[0].id);
  const [prospectId, setProspectId] = useState(MOCK_PROSPECTS[0].id);
  const [selectedTouch, setSelectedTouch] = useState<number | null>(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleAt, setScheduleAt] = useState("");
  const [drafts, setDrafts] = useState<Record<string, { subjectLine: string; bodyCopy: string }>>({});
  const [subjectVariants, setSubjectVariants] = useState<Record<string, SubjectLine[]>>({});

  const { data: apiSequences, isLoading } = useQuery({
    queryKey: ["sequences", campaignId, prospectId],
    queryFn: () => http.get<Sequence[]>("/api/v1/sequences", { campaignId, prospectId }),
    retry: false,
  });
  const sequences = apiSequences ?? mockSequence(campaignId, prospectId);

  const cadence = useQuery({
    queryKey: ["cadence"],
    queryFn: () => http.get<CadenceSpec[]>("/api/v1/sequences/cadence"),
    retry: false,
  });
  const cadenceSpec = cadence.data ?? CADENCE;

  const selected = sequences.find((s) => s.touchNumber === selectedTouch) ?? null;
  const selectedDraft = selected
    ? drafts[selected.id] ?? {
        subjectLine: selected.subjectLine ?? "",
        bodyCopy: selected.bodyCopy ?? "",
      }
    : null;
  const selectedVariants = selected ? subjectVariants[selected.id] ?? MOCK_SUBJECTS : [];

  const saveMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { subjectLine: string; bodyCopy: string } }) =>
      http.put<Sequence>(`/api/v1/sequences/${id}`, body),
    onSuccess: () => {
      toast.success("Sequence saved");
      qc.invalidateQueries({ queryKey: ["sequences"] });
    },
    onError: () => toast.error("Failed to save sequence"),
  });

  const scheduleMut = useMutation({
    mutationFn: ({ id, sendAt }: { id: string; sendAt: string }) =>
      http.post<Sequence>(`/api/v1/sequences/${id}/scheduled-send`, { sendAt }),
    onSuccess: () => {
      toast.success("Sequence scheduled");
      setScheduleOpen(false);
      qc.invalidateQueries({ queryKey: ["sequences"] });
    },
    onError: () => toast.error("Failed to schedule sequence"),
  });

  const sendNowMut = useMutation({
    mutationFn: (id: string) => http.post<{ message: string }>(`/api/v1/sequences/${id}/send-email`),
    onSuccess: () => {
      toast.success("Email sent");
      qc.invalidateQueries({ queryKey: ["sequences"] });
    },
    onError: () => toast.error("Failed to send email"),
  });

  const subjectMut = useMutation({
    mutationFn: (id: string) =>
      http.post<SubjectLine[]>(`/api/v1/sequences/${id}/subject-lines`, {}),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["sequences"] });
      if (selected) {
        setSubjectVariants((prev) => ({ ...prev, [selected.id]: data }));
      }
      toast.success(`Generated ${data.length} subject-line variants`);
    },
    onError: () => {
      if (selected) {
        setSubjectVariants((prev) => ({ ...prev, [selected.id]: MOCK_SUBJECTS }));
      }
      toast.warning("Subject-line API unavailable — showing mock variants");
    },
  });

  function exportCsv() {
    const rows = [
      ["touchNumber", "sendDay", "prospect", "subjectLine", "status", "sentAt"],
      ...sequences.map((s) => [
        String(s.touchNumber),
        String(s.sendDay),
        MOCK_PROSPECTS.find((p) => p.id === s.prospectId)?.name ?? s.prospectId,
        s.subjectLine ?? "",
        s.status,
        s.sentAt ?? "",
      ]),
    ];
    const csv = rows
      .map((r) => r.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sequence-${campaignId}-${prospectId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Cadence exported");
  }

  const summary = useMemo(() => {
    const byStatus = sequences.reduce<Record<string, number>>((acc, s) => {
      acc[s.status] = (acc[s.status] ?? 0) + 1;
      return acc;
    }, {});
    return byStatus;
  }, [sequences]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sequences"
        description="7-touch cadence editor with subject-line variants, scheduling, and MailBridge sending."
        actions={
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download className="h-4 w-4" /> Export Cadence
          </Button>
        }
      />

      <Card>
        <CardContent className="p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="seq-campaign">Campaign</Label>
              <Select
                id="seq-campaign"
                value={campaignId}
                onChange={(e) => {
                  setCampaignId(e.target.value);
                  setSelectedTouch(null);
                }}
              >
                {campaignsList.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="seq-prospect">Prospect</Label>
              <Select
                id="seq-prospect"
                value={prospectId}
                onChange={(e) => {
                  setProspectId(e.target.value);
                  setSelectedTouch(null);
                }}
              >
                {prospectsList.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {p.company}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          {Object.keys(summary).length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {Object.entries(summary).map(([status, count]) => (
                <Badge key={status} variant={STATUS_VARIANT[status as EmailStatus] ?? "secondary"}>
                  {status}: {count}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : sequences.length === 0 ? (
        <EmptyState
          icon={<ListChecks className="h-6 w-6" />}
          title="No sequences for this campaign + prospect"
          description="Pick another prospect or generate a cadence."
        />
      ) : (
        <>
          {/* Horizontal timeline */}
          <ScrollArea maxHeightClass="max-h-none">
            <div className="flex gap-3 overflow-x-auto pb-2">
              {cadenceSpec.map((c) => {
                const seq = sequences.find((s) => s.touchNumber === c.touch);
                const isSelected = selectedTouch === c.touch;
                return (
                  <button
                    key={c.touch}
                    type="button"
                    onClick={() => setSelectedTouch(c.touch)}
                    className={cn(
                      "w-56 shrink-0 rounded-lg border p-3 text-left transition-colors hover:bg-accent",
                      isSelected ? "border-primary bg-accent/50 ring-1 ring-primary" : "bg-card",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase text-muted-foreground">
                        Touch {c.touch}
                      </span>
                      {seq && (
                        <Badge variant={STATUS_VARIANT[seq.status] ?? "secondary"} className="text-[10px]">
                          {seq.status}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-1 text-sm font-medium">{c.label}</p>
                    <p className="text-xs text-muted-foreground">Day {c.day} · {c.angle}</p>
                    {seq && (
                      <p className="mt-2 truncate text-xs text-muted-foreground">
                        {seq.subjectLine ?? "— no subject —"}
                      </p>
                    )}
                    {seq?.qaScore !== null && seq?.qaScore !== undefined && (
                      <p className="mt-1 text-xs">
                        QA: <span className="font-medium">{Math.round(seq.qaScore * 100)}%</span>
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </ScrollArea>

          {/* Expanded editor */}
          {selected && selectedDraft && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">
                      Touch {selected.touchNumber} — {CADENCE[selected.touchNumber - 1]?.label}
                    </CardTitle>
                    <CardDescription>
                      Day {selected.sendDay} · {selected.angle} · {selected.framework ?? "—"}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setScheduleOpen(true)}
                      disabled={selected.status === "Sent" || selected.status === "Replied"}
                    >
                      <CalendarClock className="h-4 w-4" /> Schedule
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => sendNowMut.mutate(selected.id)}
                      disabled={selected.status === "Sent" || selected.status === "Replied" || sendNowMut.isPending}
                    >
                      <Send className="h-4 w-4" />
                      {sendNowMut.isPending ? "Sending…" : "Send Now"}
                    </Button>
                    <Button
                      size="sm"
                      onClick={() =>
                        saveMut.mutate({ id: selected.id, body: selectedDraft })
                      }
                      disabled={saveMut.isPending}
                    >
                      <Save className="h-4 w-4" />
                      {saveMut.isPending ? "Saving…" : "Save"}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="subj">Subject line</Label>
                  <Input
                    id="subj"
                    value={selectedDraft.subjectLine}
                    onChange={(e) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [selected.id]: { ...selectedDraft, subjectLine: e.target.value },
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="body">Body copy</Label>
                  <Textarea
                    id="body"
                    rows={8}
                    value={selectedDraft.bodyCopy}
                    onChange={(e) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [selected.id]: { ...selectedDraft, bodyCopy: e.target.value },
                      }))
                    }
                  />
                </div>

                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Mail className="h-4 w-4" /> Subject-line variants
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => subjectMut.mutate(selected.id)}
                      disabled={subjectMut.isPending}
                    >
                      <Plus className="h-4 w-4" />
                      {subjectMut.isPending ? "Generating…" : "Generate more"}
                    </Button>
                  </div>
                  {selectedVariants.length === 0 ? (
                    <p className="text-xs text-muted-foreground">No variants yet.</p>
                  ) : (
                    <ul className="space-y-1.5">
                      {selectedVariants.map((v) => (
                        <li
                          key={v.id}
                          className="flex items-center justify-between gap-2 rounded bg-background p-2 text-sm"
                        >
                          <span className="min-w-0 flex-1 truncate">{v.text}</span>
                          {v.qaScore !== null && (
                            <Badge variant="secondary" className="shrink-0">
                              {Math.round(v.qaScore * 100)}%
                            </Badge>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="shrink-0"
                            onClick={() =>
                              setDrafts((prev) => ({
                                ...prev,
                                [selected.id]: { ...selectedDraft, subjectLine: v.text },
                              }))
                            }
                          >
                            Use
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                  <div>
                    <p className="text-muted-foreground">QA score</p>
                    <p className="font-medium">
                      {selected.qaScore !== null ? `${Math.round(selected.qaScore * 100)}%` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Personalisation</p>
                    <p className="font-medium">
                      {selected.personalisationConfidence !== null
                        ? `${Math.round(selected.personalisationConfidence * 100)}%`
                        : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Scheduled for</p>
                    <p className="font-medium">{formatDateTime(selected.scheduledFor)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Sent at</p>
                    <p className="font-medium">{formatDateTime(selected.sentAt)}</p>
                  </div>
                </div>
                {selected.flagForManualReview && (
                  <p className="text-xs text-amber-700">
                    This touch is flagged for manual review.
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Schedule dialog */}
      <Dialog open={scheduleOpen} onOpenChange={setScheduleOpen}>
        <DialogClose onClose={() => setScheduleOpen(false)} />
        <DialogHeader>
          <DialogTitle>Schedule touch</DialogTitle>
          <DialogDescription>
            Pick a send date/time. {selected && `Currently scheduled: ${formatDate(selected.scheduledFor)}`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="sched">Send at</Label>
          <Input
            id="sched"
            type="datetime-local"
            value={scheduleAt}
            onChange={(e) => setScheduleAt(e.target.value)}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setScheduleOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={!scheduleAt || !selected || scheduleMut.isPending}
            onClick={() =>
              selected &&
              scheduleAt &&
              scheduleMut.mutate({ id: selected.id, sendAt: new Date(scheduleAt).toISOString() })
            }
          >
            {scheduleMut.isPending ? "Scheduling…" : "Schedule"}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
