/**
 * ReplyInboxPage.tsx — OUTRENA Phase 4 (Task 3-C)
 *
 * Reply triage with auto-pilot eligibility. Two-pane inbox + detail with
 * category filter, auto-pilot-only switch, categorize + auto-reply actions.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Inbox,
  LogIn,
  Send,
  Sparkles,
  Tag,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatPercent, timeAgo, truncate } from "@/lib/utils";
import type { ReplyDraft } from "@/types/common";
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
import { PageHeader } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/ui/stat-card";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";

/* ── Types & mocks ──────────────────────────────────────────────────────── */

const CATEGORIES = [
  "positive",
  "neutral",
  "objection",
  "not_interested",
  "oof",
] as const;

const CATEGORY_VARIANT: Record<string, "success" | "secondary" | "warning" | "destructive" | "outline"> = {
  positive: "success",
  neutral: "secondary",
  objection: "warning",
  not_interested: "destructive",
  oof: "outline",
};

const MOCK_REPLIES: (ReplyDraft & { prospectName: string })[] = [
  {
    id: "rd1",
    prospectId: "p1",
    sequenceId: "s1",
    inboundMessage:
      "Hey — this is interesting. We've been looking at reconciliation tools. Do you have a deck or a 15-min slot next week?",
    category: "positive",
    suggestedReply:
      "Thanks Jordan! I've got Tuesday at 10am or Wednesday at 2pm PT open. I'll bring a 1-page deck with the 90-day ROI breakdown. Which works?",
    confidence: 0.91,
    autoPilotEligible: true,
    status: "pending",
    createdAt: "2025-01-10T14:23:00Z",
    updatedAt: "2025-01-10T14:23:00Z",
    prospectName: "Jordan Avery",
  },
  {
    id: "rd2",
    prospectId: "p2",
    sequenceId: "s2",
    inboundMessage: "Got it, thanks. Not now — ping me in Q2.",
    category: "neutral",
    suggestedReply: "Sounds good, Priya. I'll reach back out in April. Have a great quarter.",
    confidence: 0.86,
    autoPilotEligible: true,
    status: "pending",
    createdAt: "2025-01-10T11:02:00Z",
    updatedAt: "2025-01-10T11:02:00Z",
    prospectName: "Priya Shah",
  },
  {
    id: "rd3",
    prospectId: "p3",
    sequenceId: "s3",
    inboundMessage: "We already use Workday for this. Why switch?",
    category: "objection",
    suggestedReply:
      "Totally fair — Workday is solid for GL. OUTRENA complements it by orchestrating reconciliation across subledgers + bank feeds. 15-min demo?",
    confidence: 0.62,
    autoPilotEligible: false,
    status: "pending",
    createdAt: "2025-01-09T18:45:00Z",
    updatedAt: "2025-01-09T18:45:00Z",
    prospectName: "Marcus Chen",
  },
  {
    id: "rd4",
    prospectId: "p4",
    sequenceId: "s4",
    inboundMessage: "Please remove me from your list.",
    category: "not_interested",
    suggestedReply: "Done — removing you now. Apologies for the interruption.",
    confidence: 0.94,
    autoPilotEligible: true,
    status: "pending",
    createdAt: "2025-01-09T09:15:00Z",
    updatedAt: "2025-01-09T09:15:00Z",
    prospectName: "Elena Rivera",
  },
  {
    id: "rd5",
    prospectId: "p5",
    sequenceId: "s5",
    inboundMessage: "Out of office until Jan 20. Will respond on return.",
    category: "oof",
    suggestedReply: "Thanks — I'll follow up after you're back.",
    confidence: 0.97,
    autoPilotEligible: true,
    status: "pending",
    createdAt: "2025-01-08T22:00:00Z",
    updatedAt: "2025-01-08T22:00:00Z",
    prospectName: "Tom Walsh",
  },
  {
    id: "rd6",
    prospectId: "p6",
    sequenceId: "s6",
    inboundMessage: "Yes — let's talk. I'm free Thursday afternoon.",
    category: "positive",
    suggestedReply: "Great — Thursday at 2pm PT works. I'll send a calendar invite shortly.",
    confidence: 0.89,
    autoPilotEligible: true,
    status: "pending",
    createdAt: "2025-01-08T15:30:00Z",
    updatedAt: "2025-01-08T15:30:00Z",
    prospectName: "Aisha Khan",
  },
  {
    id: "rd7",
    prospectId: "p7",
    sequenceId: "s7",
    inboundMessage: "What's pricing look like for a 200-person org?",
    category: "positive",
    suggestedReply:
      "For 200 seats we typically land at $18k/yr, billed annually. Happy to walk through ROI in a quick call.",
    confidence: 0.78,
    autoPilotEligible: false,
    status: "pending",
    createdAt: "2025-01-07T10:11:00Z",
    updatedAt: "2025-01-07T10:11:00Z",
    prospectName: "Daniel Park",
  },
  {
    id: "rd8",
    prospectId: "p8",
    sequenceId: "s8",
    inboundMessage: "Not relevant right now, but thanks.",
    category: "not_interested",
    suggestedReply: "Understood — I'll close your sequence. Good luck with Q1.",
    confidence: 0.88,
    autoPilotEligible: true,
    status: "pending",
    createdAt: "2025-01-06T16:00:00Z",
    updatedAt: "2025-01-06T16:00:00Z",
    prospectName: "Sofia Mendoza",
  },
];

type ReplyRow = (typeof MOCK_REPLIES)[number];

/* ── Page ───────────────────────────────────────────────────────────────── */

export function ReplyInboxPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(MOCK_REPLIES[0].id);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [autoPilotOnly, setAutoPilotOnly] = useState(false);
  const [editedReply, setEditedReply] = useState<Record<string, string>>({});
  const [logReplyOpen, setLogReplyOpen] = useState(false);
  const [manualReply, setManualReply] = useState("");

  // Check MailBridge connection status
  const { data: mailbridgeStatus } = useQuery({
    queryKey: ["mailbridge-status"],
    queryFn: () => http.get<{ connected: boolean }>("/api/v1/mailbridge/status").catch(() => ({ connected: false })),
    retry: false,
    staleTime: 60_000,
  });
  const mailbridgeConnected = mailbridgeStatus?.connected ?? false;

  const { data: apiReplies, isLoading } = useQuery({
    queryKey: ["reply-drafts"],
    queryFn: () => http.get<ReplyDraft[]>("/api/v1/reply-drafts"),
    retry: false,
  });
  const replies = (apiReplies ?? MOCK_REPLIES) as ReplyRow[];

  const filtered = useMemo(
    () =>
      replies.filter((r) => {
        const matchesCat = categoryFilter === "all" || r.category === categoryFilter;
        const matchesAuto = !autoPilotOnly || r.autoPilotEligible;
        return matchesCat && matchesAuto;
      }),
    [replies, categoryFilter, autoPilotOnly],
  );

  const selected =
    replies.find((r) => r.id === selectedId) ?? filtered[0] ?? null;

  const stats = useMemo(() => {
    const total = replies.length;
    const positive = replies.filter((r) => r.category === "positive").length;
    const positiveRate = total ? positive / total : 0;
    const autoSent = replies.filter((r) => r.status === "sent" && r.autoPilotEligible).length;
    const avgConfidence =
      total > 0
        ? replies.reduce((sum, r) => sum + (r.confidence ?? 0), 0) / total
        : 0;
    return { total, positiveRate, autoSent, avgConfidence };
  }, [replies]);

  const categorizeMut = useMutation({
    mutationFn: (id: string) =>
      http.post<ReplyDraft>(`/api/v1/reply-drafts/${id}/reply-categorize`, {}),
    onSuccess: () => {
      toast.success("Reply re-categorized");
      qc.invalidateQueries({ queryKey: ["reply-drafts"] });
    },
    onError: () => toast.error("Failed to categorize"),
  });

  const autoReplyMut = useMutation({
    mutationFn: (id: string) =>
      http.post<{ message: string }>(`/api/v1/reply-drafts/${id}/auto-reply`, {}),
    onSuccess: () => {
      toast.success("Auto-reply sent");
      qc.invalidateQueries({ queryKey: ["reply-drafts"] });
    },
    onError: () => toast.error("Failed to send auto-reply"),
  });

  function canAutoReply(r: ReplyRow | null): boolean {
    return !!r && r.autoPilotEligible && (r.confidence ?? 0) >= 0.8;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reply Inbox"
        description="Triage inbound replies and trigger auto-pilot responses for high-confidence positives."
        actions={
          <Button variant="outline" size="sm" onClick={() => setLogReplyOpen(true)}>
            <LogIn className="h-4 w-4" /> Log a reply
          </Button>
        }
      />

      {/* MailBridge not connected warning — Help Guide §Reply Inbox */}
      {!mailbridgeConnected && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-700 dark:text-amber-300">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <div>
            <p className="font-medium">MailBridge not connected</p>
            <p className="text-xs mt-0.5">Inbound replies won't appear here until MailBridge is set up. You can still log replies manually.</p>
          </div>
          <Button variant="outline" size="sm" className="ml-auto shrink-0" onClick={() => toast.info("Redirecting to MailBridge setup…")}>
            Set up MailBridge
          </Button>
        </div>
      )}

      {/* Log a reply dialog — Help Guide §Reply Inbox: "Manual 'Log a reply' button" */}
      <Dialog open={logReplyOpen} onOpenChange={setLogReplyOpen}>
        <DialogClose onClose={() => setLogReplyOpen(false)} />
        <DialogHeader>
          <DialogTitle>Log a reply</DialogTitle>
          <DialogDescription>
            Paste an external reply that wasn't captured by MailBridge. It will be added to the inbox for triage.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="manual-reply">Reply text</Label>
            <Textarea
              id="manual-reply"
              rows={6}
              value={manualReply}
              onChange={(e) => setManualReply(e.target.value)}
              placeholder="Paste the prospect's reply here…"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { setLogReplyOpen(false); setManualReply(""); }}>Cancel</Button>
          <Button
            disabled={!manualReply.trim()}
            onClick={() => {
              toast.success("Reply logged to inbox");
              setLogReplyOpen(false);
              setManualReply("");
              qc.invalidateQueries({ queryKey: ["reply-drafts"] });
            }}
          >
            <LogIn className="h-4 w-4" /> Log reply
          </Button>
        </DialogFooter>
      </Dialog>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total replies" value={stats.total} icon={<Inbox className="h-5 w-5" />} />
        <StatCard
          label="Positive rate"
          value={formatPercent(stats.positiveRate)}
          delta={{ value: "+4% vs last week", positive: true }}
        />
        <StatCard
          label="Auto-pilot sent"
          value={stats.autoSent}
          icon={<Bot className="h-5 w-5" />}
        />
        <StatCard
          label="Avg confidence"
          value={formatPercent(stats.avgConfidence)}
          icon={<Sparkles className="h-5 w-5" />}
        />
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <Select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="sm:w-48"
          >
            <option value="all">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={autoPilotOnly} onCheckedChange={setAutoPilotOnly} />
            Auto-Pilot eligible only
          </label>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-12">
        {/* Inbox list */}
        <Card className="lg:col-span-5">
          <CardHeader>
            <CardTitle className="text-base">Inbox</CardTitle>
            <CardDescription>{filtered.length} replies</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                icon={<Inbox className="h-6 w-6" />}
                title="No replies match your filters"
                description="Try widening the category or disabling the auto-pilot-only switch."
              />
            ) : (
              <ScrollArea maxHeightClass="max-h-[32rem]">
                <ul className="divide-y">
                  {filtered.map((r) => {
                    const isSelected = selected?.id === r.id;
                    return (
                      <li key={r.id}>
                        <button
                          type="button"
                          onClick={() => setSelectedId(r.id)}
                          className={cn(
                            "w-full px-4 py-3 text-left transition-colors hover:bg-accent",
                            isSelected && "bg-accent/50",
                          )}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium">{r.prospectName}</span>
                            <span className="text-xs text-muted-foreground">
                              {timeAgo(r.createdAt)}
                            </span>
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {truncate(r.inboundMessage, 80)}
                          </p>
                          <div className="mt-2 flex flex-wrap items-center gap-1.5">
                            {r.category && (
                              <Badge variant={CATEGORY_VARIANT[r.category] ?? "secondary"}>
                                {r.category}
                              </Badge>
                            )}
                            {r.autoPilotEligible && (
                              <Badge variant="outline" className="gap-1">
                                <Bot className="h-3 w-3" /> Auto-Pilot
                              </Badge>
                            )}
                            {r.confidence !== null && (
                              <span className="text-xs text-muted-foreground">
                                {formatPercent(r.confidence)} conf.
                              </span>
                            )}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        {/* Detail panel */}
        <Card className="lg:col-span-7">
          <CardHeader>
            <CardTitle className="text-base">Reply detail</CardTitle>
            {selected && (
              <CardDescription>
                {selected.prospectName} · {timeAgo(selected.createdAt)}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            {!selected ? (
              <EmptyState
                icon={<Inbox className="h-6 w-6" />}
                title="No reply selected"
                description="Pick a reply from the inbox to triage."
              />
            ) : (
              <div className="space-y-4">
                <div className="rounded-md border bg-muted/30 p-3">
                  <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                    Inbound message
                  </p>
                  <p className="whitespace-pre-wrap text-sm">{selected.inboundMessage}</p>
                </div>

                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <Badge variant={CATEGORY_VARIANT[selected.category ?? "neutral"] ?? "secondary"}>
                    {selected.category ?? "uncategorized"}
                  </Badge>
                  {selected.autoPilotEligible && (
                    <Badge variant="outline" className="gap-1">
                      <Bot className="h-3 w-3" /> Auto-Pilot eligible
                    </Badge>
                  )}
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Confidence</span>
                    <Progress
                      value={(selected.confidence ?? 0) * 100}
                      className="w-32"
                      indicatorClassName={
                        (selected.confidence ?? 0) >= 0.8 ? "bg-emerald-600" : "bg-amber-500"
                      }
                    />
                    <span className="font-medium">{formatPercent(selected.confidence ?? 0)}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor="suggested-reply">
                    Suggested reply
                  </label>
                  <Textarea
                    id="suggested-reply"
                    rows={6}
                    value={editedReply[selected.id] ?? selected.suggestedReply ?? ""}
                    onChange={(e) =>
                      setEditedReply((prev) => ({ ...prev, [selected.id]: e.target.value }))
                    }
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    onClick={() => categorizeMut.mutate(selected.id)}
                    disabled={categorizeMut.isPending}
                  >
                    <Tag className="h-4 w-4" />
                    {categorizeMut.isPending ? "Categorizing…" : "Categorize"}
                  </Button>
                  <Button
                    onClick={() => autoReplyMut.mutate(selected.id)}
                    disabled={!canAutoReply(selected) || autoReplyMut.isPending}
                    title={
                      !canAutoReply(selected)
                        ? "Auto-reply requires auto-pilot eligibility and ≥ 80% confidence"
                        : ""
                    }
                  >
                    {autoReplyMut.isPending ? (
                      <>
                        <Send className="h-4 w-4 animate-spin" /> Sending…
                      </>
                    ) : (
                      <>
                        <Bot className="h-4 w-4" /> Send Auto-Reply
                      </>
                    )}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => toast.success("Reply opened in MailBridge composer")}
                  >
                    <CheckCircle2 className="h-4 w-4" /> Edit &amp; Send Manual
                  </Button>
                </div>
                {!canAutoReply(selected) && (
                  <p className="text-xs text-muted-foreground">
                    Auto-reply is gated: requires auto-pilot eligibility AND confidence ≥ 80%.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
