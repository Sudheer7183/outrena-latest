/**
 * WeeklyDigestPage.tsx — Weekly performance recap.
 *
 * Gaps closed:
 *   WD-1  Digest list — past digests from GET /api/v1/weekly-digest,
 *         showing weekStart, sentCount, replyCount, meetingCount
 *   WD-2  Generate Digest button → POST /api/v1/weekly-digest/generate
 *         Returns WeeklyDigestGenerateResponse { digest: WeeklyDigestResponse }
 *   WD-3  Digest detail view — summary, highlights list, KPI chips,
 *         campaignPerformance and topProspects JSON blobs rendered as tables
 *
 * Real API schema (WeeklyDigestResponse):
 *   { id, weekStart, weekEnd, sentCount, replyCount, positiveReplyCount,
 *     meetingCount, bounceCount, summary, highlights: string[],
 *     topProspects, campaignPerformance, generatedAt, createdAt, updatedAt }
 *
 * Note: topProspects / campaignPerformance are raw JSON blobs (provider-
 * specific shape). Rendered as formatted JSON fallback when structure unknown.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  Inbox,
  Lightbulb,
  Loader2,
  Mail,
  MessageSquare,
  Newspaper,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatDate, formatDateTime } from "@/lib/utils";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";

/* ── Backend types ──────────────────────────────────────────────────────── */

interface WeeklyDigestResponse {
  id: string;
  weekStart: string;
  weekEnd: string;
  sentCount: number;
  replyCount: number;
  positiveReplyCount: number;
  meetingCount: number;
  bounceCount: number;
  summary: string;
  highlights: string[];
  topProspects: unknown;
  campaignPerformance: unknown;
  generatedAt: string;
  createdAt: string;
  updatedAt: string;
}

interface WeeklyDigestGenerateResponse {
  digest: WeeklyDigestResponse;
}

/* ── JSON blob renderer ─────────────────────────────────────────────────── */

function JsonBlobSection({
  title,
  icon,
  data,
}: {
  title: string;
  icon: React.ReactNode;
  data: unknown;
}) {
  if (!data) return null;

  // If it's an array of objects — render as a key-value list
  if (Array.isArray(data) && data.length > 0) {
    return (
      <section>
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
          {icon} {title}
        </p>
        <div className="space-y-1.5">
          {data.map((item, i) => (
            <div key={i} className="rounded-md border p-2 text-xs">
              {typeof item === "object" && item !== null ? (
                Object.entries(item as Record<string, unknown>).map(
                  ([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <span className="text-muted-foreground capitalize min-w-[80px]">
                        {k}:
                      </span>
                      <span className="font-medium">{String(v)}</span>
                    </div>
                  )
                )
              ) : (
                <span>{String(item)}</span>
              )}
            </div>
          ))}
        </div>
      </section>
    );
  }

  // If it's an object — render as key-value pairs
  if (typeof data === "object" && data !== null && !Array.isArray(data)) {
    return (
      <section>
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
          {icon} {title}
        </p>
        <div className="rounded-md border p-2 space-y-1">
          {Object.entries(data as Record<string, unknown>).map(([k, v]) => (
            <div key={k} className="flex gap-2 text-xs">
              <span className="text-muted-foreground capitalize min-w-[120px]">
                {k.replace(/([A-Z])/g, " $1").trim()}:
              </span>
              <span className="font-medium">
                {typeof v === "object" ? JSON.stringify(v) : String(v)}
              </span>
            </div>
          ))}
        </div>
      </section>
    );
  }

  return null;
}

/* ── Digest detail view ─────────────────────────────────────────────────── */

function DigestDetail({ digest }: { digest: WeeklyDigestResponse | null }) {
  if (!digest) {
    return (
      <Card className="flex h-full items-center justify-center min-h-[300px]">
        <CardContent className="p-10 text-center text-sm text-muted-foreground">
          Select a digest from the left to preview its contents.
        </CardContent>
      </Card>
    );
  }

  const highlights = Array.isArray(digest.highlights) ? digest.highlights : [];

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Newspaper className="h-4 w-4" />
              Week of {formatDate(digest.weekStart)}
            </CardTitle>
            <CardDescription>
              {formatDate(digest.weekStart)} – {formatDate(digest.weekEnd)} ·
              Generated {formatDateTime(digest.generatedAt)}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden">
        <ScrollArea maxHeightClass="max-h-[70vh]">
          <div className="space-y-5 pr-2">
            {/* WD-3 — Summary */}
            <section className="rounded-md border bg-muted/30 p-3">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" /> Executive Summary
              </p>
              <p className="text-sm leading-relaxed">{digest.summary}</p>
            </section>

            {/* KPI chips */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                {
                  icon: <Mail className="mx-auto h-4 w-4 text-muted-foreground" />,
                  value: digest.sentCount.toLocaleString(),
                  label: "Sent",
                },
                {
                  icon: <Inbox className="mx-auto h-4 w-4 text-muted-foreground" />,
                  value: digest.replyCount,
                  label: "Replies",
                },
                {
                  icon: <TrendingUp className="mx-auto h-4 w-4 text-emerald-600" />,
                  value: digest.positiveReplyCount,
                  label: "Positive",
                  color: "text-emerald-600",
                },
                {
                  icon: <MessageSquare className="mx-auto h-4 w-4 text-blue-600" />,
                  value: digest.meetingCount,
                  label: "Meetings",
                  color: "text-blue-600",
                },
              ].map((kpi) => (
                <div
                  key={kpi.label}
                  className="rounded-md border p-3 text-center"
                >
                  {kpi.icon}
                  <p
                    className={cn(
                      "mt-1 text-lg font-bold",
                      kpi.color ?? ""
                    )}
                  >
                    {kpi.value}
                  </p>
                  <p className="text-xs text-muted-foreground">{kpi.label}</p>
                </div>
              ))}
            </div>

            {/* Highlights */}
            {highlights.length > 0 && (
              <section>
                <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
                  <Lightbulb className="h-3.5 w-3.5" /> Highlights
                </p>
                <ul className="space-y-2">
                  {highlights.map((h, i) => (
                    <li key={i} className="flex gap-2 text-sm">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-500" />
                      <span>{h}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Campaign performance blob */}
            <JsonBlobSection
              title="Campaign Performance"
              icon={<TrendingUp className="h-3.5 w-3.5" />}
              data={digest.campaignPerformance}
            />

            {/* Top prospects blob */}
            <JsonBlobSection
              title="Top Prospects"
              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              data={digest.topProspects}
            />

            {/* Bounce count note */}
            {digest.bounceCount > 0 && (
              <p className="text-xs text-muted-foreground">
                ⚠ {digest.bounceCount} bounces this week — review domain
                health in Domains.
              </p>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */

export function WeeklyDigestPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  /* ── Queries ── */

  const { data: digests = [], isLoading } = useQuery<WeeklyDigestResponse[]>({
    queryKey: ["weekly-digest"],
    queryFn: () => http.get<WeeklyDigestResponse[]>("/api/v1/weekly-digest"),
    retry: false,
  });

  const selected =
    digests.find((d) => d.id === selectedId) ?? digests[0] ?? null;

  /* ── Mutations ── */

  // WD-2 — Generate digest
  const generateMut = useMutation({
    mutationFn: () =>
      http.post<WeeklyDigestGenerateResponse>(
        "/api/v1/weekly-digest/generate",
        {}
      ),
    onSuccess: (data) => {
      const digest = data.digest;
      toast.success("This week's digest generated");
      qc.invalidateQueries({ queryKey: ["weekly-digest"] });
      setSelectedId(digest.id);
    },
    onError: () => toast.error("Failed to generate digest"),
  });

  /* ── Render ── */

  return (
    <div className="space-y-6">
      <PageHeader
        title="Weekly Digest"
        description="AI-generated weekly recap of outreach performance — sent, replies, meetings, and highlights."
        actions={
          <Button
            onClick={() => generateMut.mutate()}
            disabled={generateMut.isPending}
          >
            {generateMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Generate This Week's Digest
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* WD-1 — Digest list */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarDays className="h-4 w-4" />
              Past Digests
            </CardTitle>
            <CardDescription>
              {digests.length} weekly digest
              {digests.length !== 1 ? "s" : ""} archived.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full" />
                ))}
              </div>
            ) : digests.length === 0 ? (
              <EmptyState
                icon={<Newspaper className="h-6 w-6" />}
                title="No digests yet"
                description="Click Generate This Week's Digest to create the first one."
                className="py-6"
              />
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
                          active && "border-primary bg-primary/5"
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold">
                            Week of {formatDate(d.weekStart)}
                          </span>
                          {active && (
                            <Badge variant="default" className="text-[10px]">
                              Viewing
                            </Badge>
                          )}
                        </div>
                        <div className="mt-1 grid grid-cols-3 gap-1 text-xs text-muted-foreground">
                          <span>{d.sentCount.toLocaleString()} sent</span>
                          <span>{d.replyCount} replies</span>
                          <span>{d.meetingCount} meetings</span>
                        </div>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          Generated {formatDate(d.generatedAt)}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        {/* WD-3 — Digest detail */}
        <div className="lg:col-span-2">
          <DigestDetail digest={selected} />
        </div>
      </div>
    </div>
  );
}