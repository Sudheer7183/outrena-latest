/**
 * WeeklyDigestPage.tsx — Weekly digest history + AI preview.
 *
 * Left: list of past digests (weekOf, sentCount, replyCount, topCampaign,
 * generatedAt). Right: rich preview (executive summary, top campaigns table,
 * reply highlights, deals closed, recommendations). "Generate This Week's
 * Digest" button → POST → toast + refetch.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  DollarSign,
  Inbox,
  Loader2,
  Mail,
  Newspaper,
  Sparkles,
  TrendingUp,
  Trophy,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatCurrency, formatDate, formatDateTime, formatPercent } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────────────────────── */
interface TopCampaign {
  name: string;
  sent: number;
  openRate: number;
  replyRate: number;
  positiveReplies: number;
}
interface WeeklyDigest {
  id: string;
  weekOf: string;
  generatedAt: string;
  sentCount: number;
  replyCount: number;
  positiveReplyCount: number;
  dealsClosedCount: number;
  dealsClosedValue: number;
  topCampaign: string;
  executiveSummary: string;
  topCampaigns: TopCampaign[];
  replyHighlights: { prospect: string; snippet: string; sentiment: string }[];
  dealsClosed: { title: string; value: number; stage: string }[];
  recommendations: string[];
}

/* ── Mock data ───────────────────────────────────────────────────────────── */
function mkDigest(
  id: string,
  weeksAgo: number,
  sent: number,
  replies: number,
  positive: number,
  dealsCount: number,
  dealsValue: number,
  topCmp: string,
): WeeklyDigest {
  const weekOf = new Date(Date.now() - weeksAgo * 7 * 86400000).toISOString();
  return {
    id,
    weekOf,
    generatedAt: new Date(Date.now() - weeksAgo * 7 * 86400000 + 2 * 86400000).toISOString(),
    sentCount: sent,
    replyCount: replies,
    positiveReplyCount: positive,
    dealsClosedCount: dealsCount,
    dealsClosedValue: dealsValue,
    topCampaign: topCmp,
    executiveSummary: `Week of ${formatDate(weekOf)}: sent ${sent.toLocaleString()} emails with a ${formatPercent(replies / sent)} reply rate and ${positive} positive replies. ${dealsCount} deals closed worth ${formatCurrency(dealsValue)}. ${topCmp} led performance — keep doubling down on its angle next week.`,
    topCampaigns: [
      { name: topCmp, sent: Math.round(sent * 0.4), openRate: 0.54, replyRate: 0.12, positiveReplies: Math.round(positive * 0.5) },
      { name: "Fintech Renewals", sent: Math.round(sent * 0.3), openRate: 0.46, replyRate: 0.09, positiveReplies: Math.round(positive * 0.3) },
      { name: "DevTools Cold", sent: Math.round(sent * 0.3), openRate: 0.39, replyRate: 0.06, positiveReplies: Math.round(positive * 0.2) },
    ],
    replyHighlights: [
      { prospect: "Jordan Lee (Acme)", snippet: "Interested — can we set up a call next Tuesday?", sentiment: "positive" },
      { prospect: "Priya Nair (Globex)", snippet: "Not now, revisit in Q1.", sentiment: "objection" },
      { prospect: "Sara Chen (Umbrella)", snippet: "Who else is using this in our space?", sentiment: "positive" },
    ],
    dealsClosed: [
      { title: `${topCmp} — Annual`, value: Math.round(dealsValue * 0.6), stage: "closed_won" },
      { title: "Pawnee — Suite", value: Math.round(dealsValue * 0.4), stage: "closed_won" },
    ],
    recommendations: [
      `Scale ${topCmp}'s opener angle to the Fintech segment.`,
      "Pause Friday afternoon sends — underperforming by 22%.",
      "Refresh touch 3 with a case study link for the DevTools cohort.",
      "Re-engage the 18 objection replies with a new-evidence angle.",
    ],
  };
}

const MOCK_DIGESTS: WeeklyDigest[] = [
  mkDigest("wd1", 0, 4120, 388, 162, 3, 142000, "Q4 SaaS Outbound"),
  mkDigest("wd2", 1, 3980, 351, 148, 2, 96000, "Healthcare Expansion"),
  mkDigest("wd3", 2, 4450, 412, 175, 4, 188000, "Q4 SaaS Outbound"),
  mkDigest("wd4", 3, 3680, 309, 121, 1, 54000, "HR-Tech Net-New"),
];

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function sentimentVariant(s: string): "success" | "warning" | "destructive" | "secondary" {
  if (s === "positive") return "success";
  if (s === "objection") return "warning";
  if (s === "not_interested") return "destructive";
  return "secondary";
}

/* ── Digest preview ──────────────────────────────────────────────────────── */
function DigestPreview({ digest }: { digest: WeeklyDigest | null }) {
  if (!digest) {
    return (
      <Card className="flex h-full items-center justify-center">
        <CardContent className="p-10 text-center text-sm text-muted-foreground">
          Select a digest from the left to preview its contents.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Newspaper className="h-4 w-4" />
              Week of {formatDate(digest.weekOf)}
            </CardTitle>
            <CardDescription>Generated {formatDateTime(digest.generatedAt)}</CardDescription>
          </div>
          <Badge variant="secondary">{digest.topCampaign}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex-1">
        <ScrollArea maxHeightClass="max-h-[70vh]">
          <div className="space-y-5 pr-2">
            {/* Summary */}
            <section className="rounded-md border bg-muted/30 p-3">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" /> Executive Summary
              </p>
              <p className="text-sm">{digest.executiveSummary}</p>
            </section>

            {/* KPI row */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-md border p-3 text-center">
                <Mail className="mx-auto h-4 w-4 text-muted-foreground" />
                <p className="mt-1 text-lg font-bold">{(digest.sentCount ?? 0).toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">Sent</p>
              </div>
              <div className="rounded-md border p-3 text-center">
                <Inbox className="mx-auto h-4 w-4 text-muted-foreground" />
                <p className="mt-1 text-lg font-bold">{digest.replyCount}</p>
                <p className="text-xs text-muted-foreground">Replies</p>
              </div>
              <div className="rounded-md border p-3 text-center">
                <TrendingUp className="mx-auto h-4 w-4 text-emerald-600" />
                <p className="mt-1 text-lg font-bold text-emerald-600">{digest.positiveReplyCount}</p>
                <p className="text-xs text-muted-foreground">Positive</p>
              </div>
              <div className="rounded-md border p-3 text-center">
                <DollarSign className="mx-auto h-4 w-4 text-violet-600" />
                <p className="mt-1 text-lg font-bold text-violet-600">{formatCurrency(digest.dealsClosedValue)}</p>
                <p className="text-xs text-muted-foreground">Closed</p>
              </div>
            </div>

            {/* Top campaigns */}
            <section>
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
                <Trophy className="h-3.5 w-3.5" /> Top Performing Campaigns
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Campaign</TableHead>
                    <TableHead className="text-right">Sent</TableHead>
                    <TableHead className="text-right">Open %</TableHead>
                    <TableHead className="text-right">Reply %</TableHead>
                    <TableHead className="text-right">Positive</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(Array.isArray(digest.topCampaigns) ? digest.topCampaigns : []).map((c) => (
                    <TableRow key={c.name}>
                      <TableCell className="font-medium">{c.name}</TableCell>
                      <TableCell className="text-right">{c.sent}</TableCell>
                      <TableCell className="text-right">{formatPercent(c.openRate)}</TableCell>
                      <TableCell className="text-right">{formatPercent(c.replyRate)}</TableCell>
                      <TableCell className="text-right">{c.positiveReplies}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </section>

            {/* Reply highlights */}
            <section>
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
                <Inbox className="h-3.5 w-3.5" /> Reply Highlights
              </p>
              <div className="space-y-2">
                {(Array.isArray(digest.replyHighlights) ? digest.replyHighlights : []).map((r, i) => (
                  <div key={i} className="rounded-md border p-2">
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-sm font-medium">{r.prospect}</span>
                      <Badge variant={sentimentVariant(r.sentiment)} className="capitalize">
                        {r.sentiment.replace("_", " ")}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">“{r.snippet}”</p>
                  </div>
                ))}
              </div>
            </section>

            {/* Deals closed */}
            <section>
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5" /> Deals Closed
              </p>
              <div className="space-y-1">
                {(Array.isArray(digest.dealsClosed) ? digest.dealsClosed : []).map((d, i) => (
                  <div key={i} className="flex items-center justify-between rounded-md border p-2 text-sm">
                    <span className="font-medium">{d.title}</span>
                    <span className="font-bold text-emerald-600">{formatCurrency(d.value)}</span>
                  </div>
                ))}
              </div>
            </section>

            {/* Recommendations */}
            <section>
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" /> Recommendations for Next Week
              </p>
              <ul className="space-y-2">
                {(Array.isArray(digest.recommendations) ? digest.recommendations : []).map((r, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-500" />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */
export function WeeklyDigestPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["weekly-digest"],
    queryFn: () => http.get<WeeklyDigest[]>("/api/v1/weekly-digest"),
  });
  // BUG-39 FIX: robust null guard — API may return { digests: undefined } or a non-array
  const _dataAsMap = data as unknown as Record<string, unknown>;
  const digests = Array.isArray(data) ? data : (Array.isArray(_dataAsMap?.digests) ? _dataAsMap.digests as WeeklyDigest[] : MOCK_DIGESTS);
  const selected = digests.find((d) => d.id === selectedId) ?? digests[0] ?? null;

  const generateMutation = useMutation({
    mutationFn: () => http.post<WeeklyDigest>("/api/v1/weekly-digest/generate", {}),  // BUG-28 FIX: explicit empty body
    onSuccess: (d) => {
      queryClient.invalidateQueries({ queryKey: ["weekly-digest"] });
      toast.success("This week's digest generated");
      setSelectedId(d.id);
    },
    onError: (error: unknown) => {
      // BUG-28 FIX: Show actual error instead of generic cached-digest message
      const msg = (error as { message?: string })?.message ?? "Generate failed";
      toast.error(`Weekly digest generate failed: ${msg}`);
      setSelectedId(digests[0]?.id ?? null);
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Weekly Digest"
        description="Auto-generated recap of outreach performance, replies & deals — with next-week recommendations."
        actions={
          <Button onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
            {generateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Generate This Week's Digest
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* History list */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarDays className="h-4 w-4" />
              Past Digests
            </CardTitle>
            <CardDescription>{digests.length} weekly digests archived.</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full" />
                ))}
              </div>
            ) : (
              <ScrollArea maxHeightClass="max-h-[70vh]">
                <div className="space-y-2 pr-1">
                  {digests.map((d) => {
                    const active = d.id === (selected?.id ?? "");
                    return (
                      <button
                        key={d.id}
                        onClick={() => setSelectedId(d.id)}
                        className={cn(
                          "w-full rounded-md border p-3 text-left transition-colors hover:bg-accent",
                          active && "border-primary bg-primary/5",
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold">Week of {formatDate(d.weekOf)}</span>
                          {active && <Badge variant="default">Viewing</Badge>}
                        </div>
                        <div className="mt-1 grid grid-cols-3 gap-1 text-xs text-muted-foreground">
                          <span>{(d.sentCount ?? 0).toLocaleString()} sent</span>
                          <span>{d.replyCount} replies</span>
                          <span>{d.dealsClosedCount} deals</span>
                        </div>
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          Top: {d.topCampaign}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        {/* Preview */}
        <div className="lg:col-span-2">
          <DigestPreview digest={selected ?? null} />
        </div>
      </div>
    </div>
  );
}