/**
 * MeetingPrepPage.tsx — OUTRENA Meeting Prep
 *
 * Gaps closed:
 *   MP-1  Meeting list view — cards with prospect name, meeting type, date, status
 *   MP-2  Generate Brief dialog — prospect selector, meeting type selector, date picker
 *         POST /api/v1/meeting-prep/generate { prospectId, callType }
 *   MP-3  4-tab detail view: Talking Points / Objections / Questions / Next Steps
 *   MP-4  Research Summary card in brief detail
 *   MP-5  Approach card in brief detail
 *   MP-6  Agenda card (time-blocked) in brief detail
 *   MP-7  Delete meeting prep record
 *
 * Additional fixes:
 *   - Real API shape: { id, prospectId, callType, brief, createdAt }
 *     `brief` is a JSON string — parsed with safeParse()
 *   - Prospect name looked up from /api/v1/prospects join by prospectId
 *   - No mock data fallback — defaults to [] so empty state renders correctly
 *   - Generate mutation sends { prospectId, callType } (not meetingContext)
 *   - Log Meeting dialog calls POST /api/v1/meetings (Meeting calendar entity)
 *   - Status field absent from API — removed from type, badge omitted on list
 *   - Radix Select used in generate dialog (SelectTrigger/SelectContent/SelectItem)
 *   - Selected ID initialised to null (not a hardcoded mock ID)
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Calendar,
  CalendarClock,
  CalendarPlus,
  CheckCircle2,
  Clock,
  FileText,
  Handshake,
  Lightbulb,
  ListChecks,
  MessageCircle,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, timeAgo } from "@/lib/utils";
import type { MeetingPrep, MeetingInput } from "@/types/common";
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
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

/* ── Constants ──────────────────────────────────────────────────────────── */

const MEETING_TYPES = [
  { id: "discovery", label: "Discovery Call" },
  { id: "demo", label: "Product Demo" },
  { id: "negotiation", label: "Negotiation" },
  { id: "follow_up", label: "Follow-up" },
] as const;

/* ── Types ──────────────────────────────────────────────────────────────── */

interface ProspectLite {
  id: string;
  firstName: string;
  lastName: string;
  title: string | null;
  company: string | null;
}

/** Shape extracted from the `brief` JSON string stored in MeetingPrep.brief */
interface ParsedBrief {
  researchSummary?: string;
  approach?: string;
  meetingObjective?: string;
  prospectBackground?: string;
  icpFit?: string;
  recentActivity?: string;
  agenda?: Array<{ time: string; item: string; detail: string }>;
  talkingPoints?: string[];
  objections?: Array<{ objection: string; response: string }>;
  /** discovery questions — stored as "questions" or "discoveryQuestions" */
  questions?: string[];
  discoveryQuestions?: string[];
  nextSteps?: string[];
  nextStepsIfYes?: string[];
  nextStepsIfNo?: string[];
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function safeParse(str: string | null | undefined): ParsedBrief | null {
  if (!str) return null;
  try {
    return JSON.parse(str) as ParsedBrief;
  } catch {
    return null;
  }
}

function safeArray<T>(val: T[] | undefined | null): T[] {
  return Array.isArray(val) ? val : [];
}

function prospectDisplayName(p: ProspectLite | undefined): string {
  if (!p) return "Unknown Prospect";
  return `${p.firstName} ${p.lastName}`;
}

function meetingTypeLabel(callType: string): string {
  return MEETING_TYPES.find((t) => t.id === callType)?.label ?? callType;
}

/* ── Page ───────────────────────────────────────────────────────────────── */

export function MeetingPrepPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<MeetingPrep | null>(null);
  const [logMeetingOpen, setLogMeetingOpen] = useState(false);

  // Generate dialog form state
  const [genProspectId, setGenProspectId] = useState("");
  const [genCallType, setGenCallType] = useState("discovery");

  // Log meeting form state
  const [logForm, setLogForm] = useState<{
    title: string;
    scheduledAt: string;
    durationMin: number;
    prospectId: string;
    notes: string;
  }>({
    title: "",
    scheduledAt: "",
    durationMin: 30,
    prospectId: "",
    notes: "",
  });

  /* ── Queries ── */

  const { data: prospects = [] } = useQuery<ProspectLite[]>({
    queryKey: ["prospects", "lite"],
    queryFn: () =>
      http
        .get<{ items?: ProspectLite[]; data?: ProspectLite[] } | ProspectLite[]>(
          "/api/v1/prospects"
        )
        .then((r) => {
          if (Array.isArray(r)) return r;
          return r.items ?? r.data ?? [];
        }),
    retry: false,
  });

  const { data: briefs = [], isLoading } = useQuery<MeetingPrep[]>({
    queryKey: ["meeting-prep"],
    queryFn: () => http.get<MeetingPrep[]>("/api/v1/meeting-prep"),
    retry: false,
  });

  // Build a prospect lookup map from id → ProspectLite
  const prospectMap = Object.fromEntries(
    prospects.map((p) => [p.id, p])
  ) as Record<string, ProspectLite>;

  const selected = briefs.find((b) => b.id === selectedId) ?? null;

  /* ── Mutations ── */

  const generateMut = useMutation({
    mutationFn: (body: { prospectId: string; callType: string }) =>
      http.post<MeetingPrep>("/api/v1/meeting-prep/generate", body),
    onSuccess: (data) => {
      toast.success("Brief generated");
      qc.invalidateQueries({ queryKey: ["meeting-prep"] });
      setSelectedId(data.id);
      setGenerateOpen(false);
      setGenProspectId("");
      setGenCallType("discovery");
    },
    onError: () => toast.error("Failed to generate brief"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) =>
      http.delete<void>(`/api/v1/meeting-prep/${id}`),
    onSuccess: () => {
      toast.success("Brief deleted");
      qc.invalidateQueries({ queryKey: ["meeting-prep"] });
      setDeleteTarget(null);
      setSelectedId(null);
    },
    onError: () => toast.error("Failed to delete brief"),
  });

  const logMeetingMut = useMutation({
    mutationFn: (body: MeetingInput) =>
      http.post<{ id: string }>("/api/v1/meetings", body),
    onSuccess: () => {
      toast.success("Meeting logged");
      setLogMeetingOpen(false);
      setLogForm({
        title: "",
        scheduledAt: "",
        durationMin: 30,
        prospectId: "",
        notes: "",
      });
    },
    onError: () => toast.error("Failed to log meeting"),
  });

  /* ── Handlers ── */

  function handleGenerate() {
    if (!genProspectId) {
      toast.error("Select a prospect");
      return;
    }
    generateMut.mutate({ prospectId: genProspectId, callType: genCallType });
  }

  function handleLogMeeting() {
    if (!logForm.title.trim() || !logForm.scheduledAt) {
      toast.error("Title and scheduled date are required");
      return;
    }
    logMeetingMut.mutate({
      title: logForm.title.trim(),
      scheduledAt: new Date(logForm.scheduledAt).toISOString(),
      durationMin: logForm.durationMin,
      prospectId: logForm.prospectId || null,
      notes: logForm.notes.trim() || null,
    });
  }

  /* ── Render: Detail view (drill-in) ── */

  if (Boolean(selected)) {
    const prep = selected!;
    const prospectInfo = prospectMap[prep.prospectId];
    const parsed = safeParse(prep.brief);
    const talkingPoints = safeArray(parsed?.talkingPoints);
    const objections = safeArray(parsed?.objections);
    const questions = safeArray(
      parsed?.questions ?? parsed?.discoveryQuestions
    );
    const nextSteps = safeArray(
      parsed?.nextSteps ??
        (parsed?.nextStepsIfYes && parsed?.nextStepsIfNo
          ? [...(parsed.nextStepsIfYes ?? []), ...(parsed.nextStepsIfNo ?? [])]
          : undefined)
    );
    const agenda = safeArray(parsed?.agenda);
    const approach = parsed?.approach ?? null;
    const researchSummary = parsed?.researchSummary ?? null;

    return (
      <div className="space-y-6">
        {/* Back header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSelectedId(null)}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold">
                {prospectDisplayName(prospectInfo)}
              </h1>
              <p className="text-sm text-muted-foreground">
                {prospectInfo?.title && `${prospectInfo.title} · `}
                {prospectInfo?.company && `${prospectInfo.company} · `}
                {meetingTypeLabel(prep.callType)}
                {" · "}
                Generated {timeAgo(prep.createdAt)}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:bg-destructive/10"
            onClick={() => setDeleteTarget(prep)}
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>

        {/* MP-4 — Research Summary card */}
        {Boolean(researchSummary) && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-4 w-4" /> Research Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {researchSummary}
              </p>
            </CardContent>
          </Card>
        )}

        {/* Brief objective / background (from parsed.meetingObjective etc) */}
        {Boolean(parsed?.meetingObjective) && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Handshake className="h-4 w-4" /> Meeting Objective
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {parsed?.meetingObjective && (
                <p>{parsed.meetingObjective}</p>
              )}
              {parsed?.prospectBackground && (
                <div>
                  <span className="font-medium">Background: </span>
                  <span className="text-muted-foreground">
                    {parsed.prospectBackground}
                  </span>
                </div>
              )}
              {parsed?.icpFit && (
                <div>
                  <span className="font-medium">ICP Fit: </span>
                  <span className="text-muted-foreground">{parsed.icpFit}</span>
                </div>
              )}
              {parsed?.recentActivity && (
                <div>
                  <span className="font-medium">Recent Activity: </span>
                  <span className="text-muted-foreground">
                    {parsed.recentActivity}
                  </span>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* MP-5 — Approach card */}
        {Boolean(approach) && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-amber-500" /> Recommended
                Approach
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {approach}
              </p>
            </CardContent>
          </Card>
        )}

        {/* MP-6 — Agenda card (time-blocked) */}
        {agenda.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Clock className="h-4 w-4 text-blue-500" /> Time-Blocked Agenda
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {agenda.map((item, i) => (
                  <div key={i} className="flex gap-3 items-start">
                    <Badge
                      variant="outline"
                      className="text-xs font-mono shrink-0 bg-blue-50 text-blue-700 border-blue-200"
                    >
                      {item.time}
                    </Badge>
                    <div className="min-w-0">
                      <p className="text-sm font-medium">{item.item}</p>
                      {item.detail && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {item.detail}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* MP-3 — 4-tab detail layout */}
        <Tabs defaultValue="talking-points">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="talking-points">Talking Points</TabsTrigger>
            <TabsTrigger value="objections">Objections</TabsTrigger>
            <TabsTrigger value="questions">Questions</TabsTrigger>
            <TabsTrigger value="next-steps">Next Steps</TabsTrigger>
          </TabsList>

          {/* Tab 1 — Talking Points */}
          <TabsContent value="talking-points" className="mt-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-amber-500" /> Talking
                  Points
                </CardTitle>
              </CardHeader>
              <CardContent>
                {talkingPoints.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No talking points in brief.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {talkingPoints.map((tp, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <span className="text-primary font-bold shrink-0">
                          {i + 1}.
                        </span>
                        <span>{tp}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 2 — Objections */}
          <TabsContent value="objections" className="mt-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <MessageCircle className="h-4 w-4 text-blue-500" /> Objection
                  Handlers
                </CardTitle>
              </CardHeader>
              <CardContent>
                {objections.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No objection handlers in brief.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {objections.map((obj, i) => (
                      <div
                        key={i}
                        className="border-l-2 border-amber-300 pl-3"
                      >
                        <p className="text-sm font-medium">
                          "{obj.objection}"
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {obj.response}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 3 — Discovery Questions */}
          <TabsContent value="questions" className="mt-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <ListChecks className="h-4 w-4 text-green-500" /> Discovery
                  Questions
                </CardTitle>
              </CardHeader>
              <CardContent>
                {questions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No discovery questions in brief.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {questions.map((q, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <span className="text-green-500 shrink-0 font-medium">
                          Q{i + 1}:
                        </span>
                        <span>{q}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 4 — Next Steps */}
          <TabsContent value="next-steps" className="mt-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <ArrowRight className="h-4 w-4 text-purple-500" /> Recommended
                  Next Steps
                </CardTitle>
              </CardHeader>
              <CardContent>
                {nextSteps.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No next steps in brief.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {nextSteps.map((ns, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <ArrowRight className="h-3 w-3 text-purple-500 shrink-0 mt-1" />
                        <span>{ns}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* If brief is plain text (LLM returned prose, not JSON) */}
        {!parsed && prep.brief && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Brief</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap text-sm text-muted-foreground font-sans leading-relaxed">
                {prep.brief}
              </pre>
            </CardContent>
          </Card>
        )}

        {/* Delete confirmation dialog (accessible from detail view too) */}
        <Dialog
          open={Boolean(deleteTarget)}
          onOpenChange={(o) => !o && setDeleteTarget(null)}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete brief?</DialogTitle>
              <DialogDescription>
                Brief for{" "}
                {deleteTarget
                  ? prospectDisplayName(prospectMap[deleteTarget.prospectId])
                  : ""}{" "}
                will be permanently removed.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() =>
                  deleteTarget && deleteMut.mutate(deleteTarget.id)
                }
                disabled={deleteMut.isPending}
              >
                {deleteMut.isPending ? "Deleting…" : "Delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  /* ── Render: List view ── */

  return (
    <div className="space-y-6">
      <PageHeader
        title="Meeting Prep"
        description="AI-generated prep briefs — research, agenda, talking points, and objection handlers."
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setLogMeetingOpen(true)}
            >
              <CalendarPlus className="h-4 w-4" /> Log meeting
            </Button>
            <Button size="sm" onClick={() => setGenerateOpen(true)}>
              <Sparkles className="h-4 w-4" /> Generate Brief
            </Button>
          </div>
        }
      />

      {/* MP-1 — Meeting list */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-lg" />
          ))}
        </div>
      ) : briefs.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={<CalendarClock className="h-10 w-10" />}
              title="No meeting briefs yet"
              description='Click "Generate Brief" to create your first AI-powered meeting prep brief.'
              action={
                <Button size="sm" onClick={() => setGenerateOpen(true)}>
                  <Plus className="h-4 w-4" /> Generate Brief
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {briefs.map((prep) => {
            const prospectInfo = prospectMap[prep.prospectId];
            const parsed = safeParse(prep.brief);
            return (
              <Card
                key={prep.id}
                className={cn(
                  "cursor-pointer transition-shadow hover:shadow-md",
                  selectedId === prep.id && "ring-2 ring-primary"
                )}
                onClick={() => setSelectedId(prep.id)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <CardTitle className="text-base truncate">
                        {prospectDisplayName(prospectInfo)}
                      </CardTitle>
                      <CardDescription className="text-xs truncate">
                        {prospectInfo?.title
                          ? `${prospectInfo.title} · `
                          : ""}
                        {prospectInfo?.company ?? "No company"}
                      </CardDescription>
                    </div>
                    <Badge variant="secondary" className="shrink-0 capitalize">
                      {meetingTypeLabel(prep.callType)}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Calendar className="h-3 w-3" />
                    <span>Generated {timeAgo(prep.createdAt)}</span>
                  </div>
                  {parsed?.researchSummary && (
                    <p className="text-xs text-muted-foreground line-clamp-2 pt-1">
                      {parsed.researchSummary}
                    </p>
                  )}
                  {!parsed && prep.brief && (
                    <p className="text-xs text-muted-foreground line-clamp-2 pt-1">
                      {prep.brief.slice(0, 120)}…
                    </p>
                  )}
                  <div className="flex items-center gap-2 pt-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedId(prep.id);
                      }}
                    >
                      View Brief
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget(prep);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* MP-2 — Generate Brief dialog */}
      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Generate Meeting Brief</DialogTitle>
            <DialogDescription>
              Select a prospect and meeting type. AI will generate a
              comprehensive prep brief with talking points, objections, and
              discovery questions.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Prospect selector */}
            <div className="space-y-2">
              <Label>Prospect</Label>
              <Select value={genProspectId} onValueChange={setGenProspectId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a prospect…" />
                </SelectTrigger>
                <SelectContent className="max-h-60">
                  {prospects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.firstName} {p.lastName}
                      {p.title ? ` — ${p.title}` : ""}
                      {p.company ? ` @ ${p.company}` : ""}
                    </SelectItem>
                  ))}
                  {prospects.length === 0 && (
                    <SelectItem value="__none__" disabled>
                      No prospects available
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
            {/* Meeting type selector */}
            <div className="space-y-2">
              <Label>Meeting Type</Label>
              <Select value={genCallType} onValueChange={setGenCallType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MEETING_TYPES.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setGenerateOpen(false);
                setGenProspectId("");
                setGenCallType("discovery");
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleGenerate} disabled={generateMut.isPending}>
              {generateMut.isPending ? (
                <>
                  <Sparkles className="h-4 w-4 animate-pulse" /> Generating…
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" /> Generate Brief
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MP-7 — Delete confirmation dialog (from list view) */}
      <Dialog
        open={Boolean(deleteTarget)}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete brief?</DialogTitle>
            <DialogDescription>
              Brief for{" "}
              {deleteTarget
                ? prospectDisplayName(prospectMap[deleteTarget.prospectId])
                : ""}{" "}
              will be permanently removed. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() =>
                deleteTarget && deleteMut.mutate(deleteTarget.id)
              }
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Log Meeting dialog — calls POST /api/v1/meetings */}
      <Dialog open={logMeetingOpen} onOpenChange={setLogMeetingOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Log Meeting</DialogTitle>
            <DialogDescription>
              Add an upcoming or past meeting not synced from your calendar.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="log-title">Meeting title *</Label>
              <Input
                id="log-title"
                value={logForm.title}
                onChange={(e) =>
                  setLogForm((f) => ({ ...f, title: e.target.value }))
                }
                placeholder="e.g. Discovery call with Jordan Avery"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="log-date">Date & time *</Label>
              <Input
                id="log-date"
                type="datetime-local"
                value={logForm.scheduledAt}
                onChange={(e) =>
                  setLogForm((f) => ({ ...f, scheduledAt: e.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="log-duration">Duration (minutes)</Label>
              <Input
                id="log-duration"
                type="number"
                min={5}
                max={480}
                value={logForm.durationMin}
                onChange={(e) =>
                  setLogForm((f) => ({
                    ...f,
                    durationMin: parseInt(e.target.value, 10) || 30,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Prospect (optional)</Label>
              <Select
                value={logForm.prospectId}
                onValueChange={(v) =>
                  setLogForm((f) => ({ ...f, prospectId: v }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Link a prospect…" />
                </SelectTrigger>
                <SelectContent className="max-h-60">
                  <SelectItem value="">No prospect</SelectItem>
                  {prospects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.firstName} {p.lastName}
                      {p.company ? ` @ ${p.company}` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="log-notes">Notes</Label>
              <Textarea
                id="log-notes"
                rows={3}
                value={logForm.notes}
                onChange={(e) =>
                  setLogForm((f) => ({ ...f, notes: e.target.value }))
                }
                placeholder="Optional context for the meeting…"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setLogMeetingOpen(false);
                setLogForm({
                  title: "",
                  scheduledAt: "",
                  durationMin: 30,
                  prospectId: "",
                  notes: "",
                });
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleLogMeeting}
              disabled={logMeetingMut.isPending || !logForm.title.trim()}
            >
              <CalendarPlus className="h-4 w-4" />
              {logMeetingMut.isPending ? "Logging…" : "Log Meeting"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
