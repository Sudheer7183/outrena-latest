/**
 * MeetingPrepPage.tsx — OUTRENA Phase 4 (Task 3-C)
 *
 * Meeting prep briefs. Two-pane list + detail with AI generation dialog.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  CalendarPlus,
  Plus,
  Sparkles,
  Trash2,
  Users,
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
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { ScrollArea } from "@/components/ui/scroll-area";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

/* ── Types & mocks ──────────────────────────────────────────────────────── */

interface MeetingBrief {
  id: string;
  prospectId: string;
  prospectName: string;
  company: string;
  meetingAt: string;
  status: "draft" | "ready" | "sent" | "archived";
  agenda: string[];
  attendees: { name: string; role: string }[];
  companyResearch: string;
  recentNews: string[];
  talkingPoints: string[];
  objectionHandlers: { objection: string; response: string }[];
  proposedNextSteps: string[];
  createdAt: string;
}

interface ProspectLite {
  id: string;
  name: string;
  company: string | null;
}

const MOCK_PROSPECTS: ProspectLite[] = [
  { id: "p1", name: "Jordan Avery", company: "Northbeam" },
  { id: "p2", name: "Priya Shah", company: "Helix Pay" },
  { id: "p3", name: "Marcus Chen", company: "Loop Capital" },
  { id: "p4", name: "Elena Rivera", company: "Brightline" },
];

const MOCK_BRIEFS: MeetingBrief[] = [
  {
    id: "mp1",
    prospectId: "p1",
    prospectName: "Jordan Avery",
    company: "Northbeam",
    meetingAt: "2025-01-15T16:00:00Z",
    status: "ready",
    agenda: [
      "Confirm reconciliation pain + close-cycle SLA",
      "Walk through OUTRENA 90-day rollout",
      "Share Northbeam ROI model",
      "Align on commercial fit + next steps",
    ],
    attendees: [
      { name: "Jordan Avery", role: "VP Operations" },
      { name: "Sam Liu", role: "Controller" },
      { name: "Alex (OUTRENA)", role: "AE" },
    ],
    companyResearch:
      "Northbeam is a Series B fintech ($40M, Apr 2024) building attribution + finance tooling. 120 employees, HQ in San Francisco. Recently expanded into multi-entity ledger reconciliation.",
    recentNews: [
      "Raised $40M Series B extension (Apr 2024)",
      "Launched multi-entity support (Nov 2024)",
      "Hired new VP Operations — Jordan Avery (Aug 2024)",
    ],
    talkingPoints: [
      "12-hour close-cycle SLA breach cost (~$18k/quarter)",
      "OUTRENA's 60% faster close within 90 days proof point",
      "Multi-entity reconciliation orchestration fit",
    ],
    objectionHandlers: [
      {
        objection: "We already use Workday for finance ops.",
        response:
          "Workday handles GL well — OUTRENA orchestrates reconciliation across subledgers + bank feeds, complementing Workday rather than replacing it.",
      },
      {
        objection: "Implementation sounds heavy.",
        response:
          "Most teams are live in 2 weeks. We pair you with a CSM and run a 30/60/90-day plan with milestones.",
      },
    ],
    proposedNextSteps: [
      "Send NDA + ROI calculator (post-call)",
      "Schedule technical deep-dive with Sam (Controller)",
      "Pilot scope by end of week",
    ],
    createdAt: "2025-01-09T10:00:00Z",
  },
  {
    id: "mp2",
    prospectId: "p2",
    prospectName: "Priya Shah",
    company: "Helix Pay",
    meetingAt: "2025-01-22T15:30:00Z",
    status: "draft",
    agenda: [
      "Understand Helix Pay's payouts stack",
      "Map OUTRENA to reconciliation use cases",
      "Discuss timeline + commercial fit",
    ],
    attendees: [
      { name: "Priya Shah", role: "Head of Finance" },
      { name: "Alex (OUTRENA)", role: "AE" },
    ],
    companyResearch:
      "Helix Pay is a Series A payments fintech focused on embedded payouts. 45 employees, HQ in Austin.",
    recentNews: [
      "Launched embedded payouts API (Oct 2024)",
      "Hired Priya Shah as Head of Finance (Sep 2024)",
    ],
    talkingPoints: [
      "Reconciliation volume growth with payouts scale",
      "OUTRENA's payouts-specific reconciliation templates",
    ],
    objectionHandlers: [
      {
        objection: "We're still early — limited reconciliation volume.",
        response:
          "OUTRENA scales with you. We offer a startup tier that grows as your payout volume does.",
      },
    ],
    proposedNextSteps: [
      "Send pricing sheet",
      "Schedule follow-up after Q1 planning",
    ],
    createdAt: "2025-01-08T14:30:00Z",
  },
  {
    id: "mp3",
    prospectId: "p3",
    prospectName: "Marcus Chen",
    company: "Loop Capital",
    meetingAt: "2025-01-12T17:00:00Z",
    status: "sent",
    agenda: [
      "Re-engage after initial Workday objection",
      "Demo reconciliation orchestration layer",
      "Discuss pilot scope",
    ],
    attendees: [
      { name: "Marcus Chen", role: "CFO" },
      { name: "Dana Ruiz", role: "Controller" },
      { name: "Alex (OUTRENA)", role: "AE" },
      { name: "Sam (OUTRENA)", role: "Solutions Engineer" },
    ],
    companyResearch:
      "Loop Capital is a mid-market asset manager. $2B AUM. 80 employees.",
    recentNews: [
      "Reported 18% YoY AUM growth (Q3 2024)",
      "Opened New York office (Jul 2024)",
    ],
    talkingPoints: [
      "Subledger reconciliation across funds",
      "Multi-currency close-cycle benchmarks",
    ],
    objectionHandlers: [
      {
        objection: "Workday already handles this.",
        response:
          "Workday is your GL — OUTRENA sits on top and orchestrates reconciliation across subledgers + fund admins.",
      },
    ],
    proposedNextSteps: [
      "Technical deep-dive scheduled",
      "Pilot one fund in February",
    ],
    createdAt: "2025-01-05T09:00:00Z",
  },
  {
    id: "mp4",
    prospectId: "p4",
    prospectName: "Elena Rivera",
    company: "Brightline",
    meetingAt: "2025-01-18T18:00:00Z",
    status: "ready",
    agenda: [
      "Understand Brightline's billing ops",
      "Walk through OUTRENA billing reconciliation",
      "Align on pilot",
    ],
    attendees: [
      { name: "Elena Rivera", role: "VP Finance" },
      { name: "Alex (OUTRENA)", role: "AE" },
    ],
    companyResearch:
      "Brightline is a digital mental health company. Series C. 200 employees.",
    recentNews: [
      "Expanded into employer benefits (Sep 2024)",
      "Raised $50M Series C (May 2024)",
    ],
    talkingPoints: [
      "Billing reconciliation across payers + employers",
      "Audit-ready close-cycle acceleration",
    ],
    objectionHandlers: [
      {
        objection: "We have an in-house team for this.",
        response:
          "OUTRENA augments in-house teams — most customers keep their team but redirect hours to analysis instead of manual reconciliation.",
      },
    ],
    proposedNextSteps: [
      "Send case studies (healthcare vertical)",
      "Schedule technical deep-dive",
    ],
    createdAt: "2025-01-07T11:00:00Z",
  },
];

const STATUS_VARIANT: Record<MeetingBrief["status"], "secondary" | "success" | "default" | "outline"> = {
  draft: "secondary",
  ready: "success",
  sent: "default",
  archived: "outline",
};

/* ── Page ───────────────────────────────────────────────────────────────── */

export function MeetingPrepPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(MOCK_BRIEFS[0].id);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<MeetingBrief | null>(null);
  const [logMeetingOpen, setLogMeetingOpen] = useState(false);
  const [logMeetingForm, setLogMeetingForm] = useState({ prospectName: "", meetingAt: "", notes: "" });
  const [genForm, setGenForm] = useState({ prospectId: "", context: "" });

  const { data: apiProspects } = useQuery<ProspectLite[]>({
    queryKey: ["prospects", "list"],
    queryFn: () => http.get<any>("/api/v1/prospects")
      .then((r: any) => {
        const list = Array.isArray(r) ? r : (r?.items ?? []);
        return list.map((p: any) => ({ id: p.id, name: p.name, company: p.company ?? null }));
      }),
    retry: false,
  });
  const prospects = apiProspects ?? MOCK_PROSPECTS;

  const { data: apiBriefs, isLoading } = useQuery({
    queryKey: ["meeting-prep"],
    queryFn: () => http.get<MeetingBrief[]>("/api/v1/meeting-prep"),
    retry: false,
  });
  const briefs = apiBriefs ?? MOCK_BRIEFS;
  const selected = briefs.find((b) => b.id === selectedId) ?? briefs[0] ?? null;

  const generateMut = useMutation({
    mutationFn: (body: { prospectId: string; meetingContext: string }) =>
      http.post<MeetingBrief>("/api/v1/meeting-prep/generate", body),
    onSuccess: (data) => {
      toast.success("Brief generated");
      qc.invalidateQueries({ queryKey: ["meeting-prep"] });
      setSelectedId(data.id);
      setGenerateOpen(false);
      setGenForm({ prospectId: "", context: "" });
    },
    onError: () => toast.error("Failed to generate brief"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete<{ message: string }>(`/api/v1/meeting-prep/${id}`),
    onSuccess: () => {
      toast.success("Brief deleted");
      qc.invalidateQueries({ queryKey: ["meeting-prep"] });
      setDeleteTarget(null);
      setSelectedId(null);
    },
    onError: () => toast.error("Failed to delete brief"),
  });

  function handleGenerate() {
    if (!genForm.prospectId) {
      toast.error("Pick a prospect");
      return;
    }
    generateMut.mutate({ prospectId: genForm.prospectId, meetingContext: genForm.context });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Meeting Prep"
        description="AI-generated prep briefs — research, agenda, talking points, and objection handlers."
        actions={
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => setLogMeetingOpen(true)}>
              <CalendarPlus className="h-4 w-4" /> Log meeting
            </Button>
            <Button size="sm" onClick={() => setGenerateOpen(true)}>
              <Sparkles className="h-4 w-4" /> Generate Brief
            </Button>
          </div>
        }
      />

      {/* Today's Meetings widget — Help Guide §Meeting Prep */}
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarClock className="h-4 w-4 text-primary" />
            Today's Meetings
          </CardTitle>
        </CardHeader>
        <CardContent>
          {briefs.filter((b) => {
            const d = new Date(b.meetingAt);
            const today = new Date();
            return d.toDateString() === today.toDateString();
          }).length === 0 ? (
            <p className="text-sm text-muted-foreground">No meetings scheduled for today.</p>
          ) : (
            <ul className="divide-y">
              {briefs
                .filter((b) => {
                  const d = new Date(b.meetingAt);
                  const today = new Date();
                  return d.toDateString() === today.toDateString();
                })
                .map((b) => (
                  <li key={b.id} className="flex items-center justify-between py-2">
                    <div>
                      <p className="text-sm font-medium">{b.prospectName} — {b.company}</p>
                      <p className="text-xs text-muted-foreground">{new Date(b.meetingAt).toLocaleTimeString()} · {b.attendees.length} attendees</p>
                    </div>
                    <Badge variant={STATUS_VARIANT[b.status]}>{b.status}</Badge>
                  </li>
                ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-12">
        {/* List */}
        <Card className="lg:col-span-4">
          <CardHeader>
            <CardTitle className="text-base">Briefs</CardTitle>
            <CardDescription>{briefs.length} prep briefs</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full" />
                ))}
              </div>
            ) : briefs.length === 0 ? (
              <EmptyState
                icon={<CalendarClock className="h-6 w-6" />}
                title="No briefs yet"
                description="Generate your first meeting prep brief."
              />
            ) : (
              <ScrollArea maxHeightClass="max-h-[36rem]">
                <ul className="divide-y">
                  {briefs.map((b) => {
                    const isSelected = selected?.id === b.id;
                    return (
                      <li key={b.id}>
                        <button
                          type="button"
                          onClick={() => setSelectedId(b.id)}
                          className={cn(
                            "w-full px-4 py-3 text-left transition-colors hover:bg-accent",
                            isSelected && "bg-accent/50",
                          )}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium">{b.prospectName}</span>
                            <Badge variant={STATUS_VARIANT[b.status]}>{b.status}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {b.company} · {timeAgo(b.meetingAt)} (meeting)
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {b.attendees.length} attendees · {b.agenda.length} agenda items
                          </p>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        {/* Detail */}
        <Card className="lg:col-span-8">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">
                  {selected ? `${selected.prospectName} — ${selected.company}` : "Brief detail"}
                </CardTitle>
                {selected && (
                  <CardDescription>
                    Meeting {timeAgo(selected.meetingAt)} · {selected.attendees.length} attendees
                  </CardDescription>
                )}
              </div>
              {selected && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDeleteTarget(selected)}
                >
                  <Trash2 className="h-4 w-4" /> Delete
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {!selected ? (
              <EmptyState
                icon={<CalendarClock className="h-6 w-6" />}
                title="No brief selected"
                description="Pick a brief from the list."
              />
            ) : (
              <ScrollArea maxHeightClass="max-h-[36rem]">
                <div className="space-y-5">
                  <section>
                    <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                      <CalendarClock className="h-4 w-4" /> Agenda
                    </h3>
                    <ol className="list-inside list-decimal space-y-1 text-sm text-muted-foreground">
                      {selected.agenda.map((a) => (
                        <li key={a}>{a}</li>
                      ))}
                    </ol>
                  </section>

                  <section>
                    <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                      <Users className="h-4 w-4" /> Attendees
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.attendees.map((at) => (
                        <Badge key={at.name} variant="secondary">
                          {at.name} · {at.role}
                        </Badge>
                      ))}
                    </div>
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold">Company Research</h3>
                    <p className="text-sm text-muted-foreground">{selected.companyResearch}</p>
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold">Recent News</h3>
                    <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                      {selected.recentNews.map((n) => (
                        <li key={n}>{n}</li>
                      ))}
                    </ul>
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold">Talking Points</h3>
                    <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                      {selected.talkingPoints.map((t) => (
                        <li key={t}>{t}</li>
                      ))}
                    </ul>
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold">Objection Handlers</h3>
                    <div className="space-y-2">
                      {selected.objectionHandlers.map((o) => (
                        <div key={o.objection} className="rounded-md border p-3">
                          <p className="text-sm font-medium">“{o.objection}”</p>
                          <p className="mt-1 text-sm text-muted-foreground">{o.response}</p>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold">Proposed Next Steps</h3>
                    <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                      {selected.proposedNextSteps.map((n) => (
                        <li key={n}>{n}</li>
                      ))}
                    </ul>
                  </section>
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Generate dialog */}
      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogClose onClose={() => setGenerateOpen(false)} />
        <DialogHeader>
          <DialogTitle>Generate Meeting Prep Brief</DialogTitle>
          <DialogDescription>
            Pick a prospect + add meeting context. AI will research and assemble the brief.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="gen-prospect">Prospect</Label>
            <Select
              id="gen-prospect"
              value={genForm.prospectId}
              onChange={(e) => setGenForm({ ...genForm, prospectId: e.target.value })}
            >
              {prospects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}{p.company ? ` — ${p.company}` : ""}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="gen-context">Meeting context</Label>
            <Textarea
              id="gen-context"
              rows={4}
              value={genForm.context}
              onChange={(e) => setGenForm({ ...genForm, context: e.target.value })}
              placeholder="e.g. Discovery call — focus on reconciliation pain, 30 min, prospect wants to see ROI model."
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setGenerateOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleGenerate} disabled={generateMut.isPending}>
            {generateMut.isPending ? (
              <>
                <Sparkles className="h-4 w-4 animate-pulse" /> Generating…
              </>
            ) : (
              <>
                <Plus className="h-4 w-4" /> Generate
              </>
            )}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Delete dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete brief?</DialogTitle>
          <DialogDescription>
            “{deleteTarget?.prospectName} — {deleteTarget?.company}” will be permanently removed.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
            disabled={deleteMut.isPending}
          >
            {deleteMut.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Log meeting dialog — Help Guide §Meeting Prep: "Log meeting" button */}
      <Dialog open={logMeetingOpen} onOpenChange={setLogMeetingOpen}>
        <DialogClose onClose={() => setLogMeetingOpen(false)} />
        <DialogHeader>
          <DialogTitle>Log meeting</DialogTitle>
          <DialogDescription>
            Add an upcoming or past meeting that wasn't synced from your calendar.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="log-prospect-name">Prospect name</Label>
            <Input
              id="log-prospect-name"
              value={logMeetingForm.prospectName}
              onChange={(e) => setLogMeetingForm({ ...logMeetingForm, prospectName: e.target.value })}
              placeholder="e.g. Jordan Avery"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="log-meeting-at">Meeting date & time</Label>
            <Input
              id="log-meeting-at"
              type="datetime-local"
              value={logMeetingForm.meetingAt}
              onChange={(e) => setLogMeetingForm({ ...logMeetingForm, meetingAt: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="log-notes">Notes</Label>
            <Textarea
              id="log-notes"
              rows={3}
              value={logMeetingForm.notes}
              onChange={(e) => setLogMeetingForm({ ...logMeetingForm, notes: e.target.value })}
              placeholder="Optional context for the meeting…"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { setLogMeetingOpen(false); setLogMeetingForm({ prospectName: "", meetingAt: "", notes: "" }); }}>Cancel</Button>
          <Button
            disabled={!logMeetingForm.prospectName.trim()}
            onClick={() => {
              toast.success("Meeting logged");
              setLogMeetingOpen(false);
              setLogMeetingForm({ prospectName: "", meetingAt: "", notes: "" });
              qc.invalidateQueries({ queryKey: ["meeting-prep"] });
            }}
          >
            <CalendarPlus className="h-4 w-4" /> Log meeting
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
