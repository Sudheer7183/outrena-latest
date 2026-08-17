/**
 * CampaignResultsPage.tsx — Closed-loop campaign attribution.
 *
 * Gaps closed:
 *   CR-1  Campaign Results list — cards per result with totalSent, reply
 *         rates, positive reply rate, bounce rate, generatedAt
 *   CR-2  Detail view (drill-in): Conversion Rates card, AI Insights card
 *         (whatWorked / whatDidntWork / nextActions), funnel stat chips
 *   CR-3  "Compute Results" button — POST /api/v1/analytics/campaign-results
 *         ?campaign_id= to generate a result for campaigns that don't have one
 *
 * API contract (analytics router):
 *   GET  /api/v1/analytics/campaign-results?campaign_id=  → CampaignResultResponse | null
 *   POST /api/v1/analytics/campaign-results?campaign_id=  → CampaignResultResponse
 *   GET  /api/v1/campaigns/my                             → CampaignListResponse { items }
 *
 * CampaignResultResponse shape:
 *   { id, campaignId, totalSent, totalReplied, totalPositive, totalBounced,
 *     replyRate, positiveReplyRate, bounceRate,
 *     whatWorked, whatDidntWork, nextActions, insights, generatedAt }
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Award,
  Ban,
  BarChart3,
  CheckCircle2,
  Lightbulb,
  Loader2,
  Mail,
  MessageSquare,
  RefreshCw,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { timeAgo } from "@/lib/utils";

/* ── Backend types ──────────────────────────────────────────────────────── */

interface CampaignResultResponse {
  id: string;
  campaignId: string;
  totalSent: number;
  totalReplied: number;
  totalPositive: number;
  totalBounced: number;
  replyRate: number;
  positiveReplyRate: number;
  bounceRate: number;
  whatWorked: string | null;
  whatDidntWork: string | null;
  nextActions: string | null;
  insights: string | null;
  generatedAt: string;
}

interface CampaignItem {
  id: string;
  name: string;
  status: string;
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function pct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

/* ── Rate bar ───────────────────────────────────────────────────────────── */

function RateBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const p = Math.min(value * 100, 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className="text-sm font-medium">{pct(value)}</span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all`}
          style={{ width: `${p}%` }}
        />
      </div>
    </div>
  );
}

/* ── Stat chip ──────────────────────────────────────────────────────────── */

function StatChip({
  icon,
  label,
  value,
  colorClass,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  colorClass: string;
}) {
  return (
    <Card className="p-3">
      <div className="flex items-center gap-2 mb-1">
        <span className={colorClass}>{icon}</span>
        <span className="text-xs font-medium text-muted-foreground">
          {label}
        </span>
      </div>
      <p className="text-2xl font-bold">{value.toLocaleString()}</p>
    </Card>
  );
}

/* ── Detail view ────────────────────────────────────────────────────────── */

function ResultDetail({
  result,
  campaignName,
  onBack,
  onRecompute,
  recomputing,
}: {
  result: CampaignResultResponse;
  campaignName: string;
  onBack: () => void;
  onRecompute: () => void;
  recomputing: boolean;
}) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <Button variant="ghost" size="icon" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{campaignName}</h1>
            <p className="text-sm text-muted-foreground">
              {result.totalSent.toLocaleString()} emails sent ·{" "}
              {result.totalReplied} replied · {result.totalPositive} positive ·
              computed {timeAgo(result.generatedAt)}
            </p>
          </div>
        </div>
        {/* CR-3 — Recompute button */}
        <Button
          variant="outline"
          size="sm"
          onClick={onRecompute}
          disabled={recomputing}
        >
          {recomputing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Recompute
        </Button>
      </div>

      {/* CR-2 — Funnel stat chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatChip
          icon={<Mail className="h-4 w-4" />}
          label="Sent"
          value={result.totalSent}
          colorClass="text-slate-600"
        />
        <StatChip
          icon={<MessageSquare className="h-4 w-4" />}
          label="Replied"
          value={result.totalReplied}
          colorClass="text-green-600"
        />
        <StatChip
          icon={<CheckCircle2 className="h-4 w-4" />}
          label="Positive"
          value={result.totalPositive}
          colorClass="text-emerald-600"
        />
        <StatChip
          icon={<Ban className="h-4 w-4" />}
          label="Bounced"
          value={result.totalBounced}
          colorClass="text-red-600"
        />
      </div>

      {/* CR-2 — Conversion Rates card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Conversion Rates</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <RateBar
            label="Reply Rate"
            value={result.replyRate}
            color="bg-green-500"
          />
          <RateBar
            label="Positive Reply Rate"
            value={result.positiveReplyRate}
            color="bg-emerald-500"
          />
          <RateBar
            label="Bounce Rate"
            value={result.bounceRate}
            color="bg-red-500"
          />
        </CardContent>
      </Card>

      {/* CR-2 — AI Insights card */}
      {(result.whatWorked ||
        result.whatDidntWork ||
        result.nextActions ||
        result.insights) && (
        <div className="grid gap-4 md:grid-cols-2">
          {result.whatWorked && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Award className="h-4 w-4 text-emerald-500" />
                  What Worked
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {result.whatWorked}
                </p>
              </CardContent>
            </Card>
          )}
          {result.whatDidntWork && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <XCircle className="h-4 w-4 text-rose-500" />
                  What Didn't Work
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {result.whatDidntWork}
                </p>
              </CardContent>
            </Card>
          )}
          {result.nextActions && (
            <Card className="md:col-span-2">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-blue-500" />
                  Recommended Next Actions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {result.nextActions}
                </p>
              </CardContent>
            </Card>
          )}
          {result.insights && (
            <Card className="md:col-span-2">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-amber-500" />
                  AI Insights
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {result.insights}
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */

export function CampaignResultsPage() {
  const qc = useQueryClient();
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(
    null
  );
  const [computeTargetId, setComputeTargetId] = useState("");

  /* ── Queries ── */

  // All campaigns for the compute selector
  const { data: campaignList } = useQuery<CampaignItem[]>({
    queryKey: ["campaigns", "my"],
    queryFn: () =>
      http
        .get<{ items: CampaignItem[] }>("/api/v1/campaigns/my")
        .then((r) => r.items ?? []),
    retry: false,
  });

  // All results (one per campaign that has been computed)
  // We load results for each campaign separately — backend requires campaign_id
  // So we first get all campaigns, then load results for each one
  const { data: allResults = [], isLoading: resultsLoading } = useQuery<
    CampaignResultResponse[]
  >({
    queryKey: ["campaign-results", "all"],
    queryFn: async () => {
      if (!campaignList || campaignList.length === 0) return [];
      const settled = await Promise.allSettled(
        campaignList.map((c) =>
          http
            .get<CampaignResultResponse | null>(
              `/api/v1/analytics/campaign-results?campaign_id=${c.id}`
            )
            .catch(() => null)
        )
      );
      return settled
        .filter(
          (s): s is PromiseFulfilledResult<CampaignResultResponse | null> =>
            s.status === "fulfilled" && s.value !== null
        )
        .map((s) => s.value as CampaignResultResponse);
    },
    enabled: (campaignList?.length ?? 0) > 0,
    retry: false,
  });

  /* ── Compute mutation (CR-3) ── */

  const computeMut = useMutation({
    mutationFn: (campaignId: string) =>
      http.post<CampaignResultResponse>(
        `/api/v1/analytics/campaign-results?campaign_id=${campaignId}`,
        {}
      ),
    onSuccess: (data) => {
      toast.success("Campaign results computed");
      qc.invalidateQueries({ queryKey: ["campaign-results"] });
      setComputeTargetId("");
      setSelectedCampaignId(data.campaignId);
    },
    onError: () => toast.error("Failed to compute results"),
  });

  /* ── Detail drill-in ── */

  const selectedResult = selectedCampaignId
    ? allResults.find((r) => r.campaignId === selectedCampaignId) ?? null
    : null;

  const campaignMap = Object.fromEntries(
    (campaignList ?? []).map((c) => [c.id, c.name])
  );

  if (selectedResult) {
    return (
      <ResultDetail
        result={selectedResult}
        campaignName={campaignMap[selectedResult.campaignId] ?? "Campaign"}
        onBack={() => setSelectedCampaignId(null)}
        onRecompute={() => computeMut.mutate(selectedResult.campaignId)}
        recomputing={computeMut.isPending}
      />
    );
  }

  /* ── List view ── */

  // Campaigns that don't have a result yet
  const campaignsWithoutResult = (campaignList ?? []).filter(
    (c) => !allResults.some((r) => r.campaignId === c.id)
  );

  const isLoading = resultsLoading;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Campaign Results"
        description="Closed-loop attribution — track reply rates, what worked, what didn't, and AI-generated lessons for each campaign."
      />

      {/* CR-3 — Compute results for campaigns without one */}
      <Card className="border-primary/30 bg-primary/5">
        <CardContent className="py-4">
          <div className="flex items-center gap-3 flex-wrap">
            <BarChart3 className="h-5 w-5 text-primary shrink-0" />
            <p className="text-sm flex-1 min-w-[180px]">
              Compute results for a campaign:
            </p>
            <Select
              value={computeTargetId}
              onValueChange={setComputeTargetId}
            >
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="Select campaign…" />
              </SelectTrigger>
              <SelectContent className="max-h-60">
                {campaignsWithoutResult.length === 0 ? (
                  <SelectItem value="_none" disabled>
                    All campaigns have results
                  </SelectItem>
                ) : (
                  campaignsWithoutResult.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              disabled={!computeTargetId || computeMut.isPending}
              onClick={() => computeMut.mutate(computeTargetId)}
            >
              {computeMut.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Compute
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* CR-1 — Results list */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full rounded-lg" />
          ))}
        </div>
      ) : allResults.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={<TrendingUp className="h-10 w-10" />}
              title="No campaign results yet"
              description="Select a campaign above and click Compute to generate the first result."
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {allResults.map((result) => (
            <Card
              key={result.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => setSelectedCampaignId(result.campaignId)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <CardTitle className="text-base truncate">
                      {campaignMap[result.campaignId] ?? "Unknown Campaign"}
                    </CardTitle>
                    <CardDescription className="text-xs">
                      {result.totalSent.toLocaleString()} sent ·{" "}
                      {result.totalReplied} replied
                    </CardDescription>
                  </div>
                  <Badge variant="secondary" className="shrink-0 text-xs">
                    {timeAgo(result.generatedAt)}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Reply Rate</p>
                    <p className="font-semibold">{pct(result.replyRate)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">
                      Positive Reply
                    </p>
                    <p className="font-semibold text-emerald-600">
                      {pct(result.positiveReplyRate)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Bounce Rate</p>
                    <p className="font-semibold text-rose-600">
                      {pct(result.bounceRate)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Positive</p>
                    <p className="font-semibold">{result.totalPositive}</p>
                  </div>
                </div>
                {result.whatWorked && (
                  <p className="mt-3 text-xs text-muted-foreground line-clamp-2">
                    {result.whatWorked}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}