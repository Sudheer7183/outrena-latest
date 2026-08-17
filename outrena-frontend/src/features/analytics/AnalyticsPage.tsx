// // // /**
// // //  * AnalyticsPage.tsx - campaign performance, health diagnostics, and
// // //  * statistical breakdowns across sequences, prospects, and LLM usage.
// // //  *
// // //  * API (verified against real routers/schemas - see comments per section):
// // //  *   GET  /api/v1/analytics/metrics?campaign_id=        -> CampaignMetricResponse[] (per campaign+date)
// // //  *   GET  /api/v1/analytics/time-series?days=N          -> TimeSeriesResponse
// // //  *   POST /api/v1/analytics/diagnose                     { campaignId } -> DiagnoseResponse
// // //  *   GET  /api/v1/analytics/campaign-results?campaign_id= -> CampaignResultResponse | null
// // //  *   POST /api/v1/analytics/campaign-results?campaign_id= -> CampaignResultResponse (generates)
// // //  *   GET  /api/v1/campaigns                               -> CampaignResponse[] (for names + selector)
// // //  *   GET  /api/v1/sequences?limit=500                      -> SequenceResponse[] (touchNumber, angle, status, timestamps)
// // //  *   GET  /api/v1/prospects?limit=500                      -> Prospect[] (intentSource)
// // //  *   GET  /api/v1/system-params?category=Analytics%20Benchmarks -> SystemParamResponse[]
// // //  *   GET  /api/v1/usage/tenant?period=YYYY-MM               -> UsageResponse (LLM cost/event breakdown)
// // //  *
// // //  * CORRECTIONS vs. the previous version: the old page had a completely wrong
// // //  * response shape for /analytics/metrics (treated it as one aggregated
// // //  * object; it's actually an array of per-campaign-per-date rows), called
// // //  * /analytics/time-series with a campaignId param it doesn't accept (it's
// // //  * tenant-wide, only takes `days`), and fell back to MOCK_METRICS /
// // //  * MOCK_TIMESERIES / MOCK_DIAGNOSE / MOCK_RESULTS / MOCK_CAMPAIGNS whenever
// // //  * a real call returned anything falsy. All mock fallbacks removed.
// // //  *
// // //  * Backend gaps documented rather than faked:
// // //  *   - AN-4 "Intent Source Attribution" is built from Prospect.intentSource
// // //  *     (FUNDING_URGENCY/HIRING_BUDGET/FORUM_PAIN/LINKEDIN_DEMAND/REFERRAL/
// // //  *     INBOUND/OTHER) - the real backend field. There is no field tracking
// // //  *     which *sourcing platform* (Apollo/LinkedIn/manual/CSV) found a
// // //  *     prospect, so that specific breakdown the gap doc describes isn't
// // //  *     buildable from real data; intentSource is the closest real analogue
// // //  *     and is labeled accurately as such.
// // //  *   - AN-7 "avg generation time" has no backend field anywhere (LLM calls
// // //  *     aren't timed) - omitted rather than fabricated. LLM usage/cost and
// // //  *     QA score distribution (both real) are shown instead.
// // //  *   - AN-9/AN-11 (Auto-Optimization Rules) already live on a separate,
// // //  *     fully-built OptimizationRulesPage per the gap audit - this page
// // //  *     links out to it instead of duplicating its CRUD.
// // //  *
// // //  * AN-1  Sequence Status Distribution (donut, from /sequences grouped by status)
// // //  * AN-2  Campaign Performance table (from /analytics/metrics, summed per campaign)
// // //  * AN-3  Sequence Step Performance (bar, from /sequences grouped by touchNumber)
// // //  * AN-4  Intent Source Attribution (bar, from /prospects.intentSource + reply join)
// // //  * AN-5  Copy Angle Performance (bar, from /sequences grouped by angle)
// // //  * AN-6  Campaign Health Diagnostics (from /analytics/diagnose)
// // //  * AN-7  AI Performance Diagnostics (usage/tenant + QA score histogram)
// // //  * AN-8  Industry Benchmarks (from /system-params?category=Analytics Benchmarks)
// // //  * AN-9  Auto-Optimization summary + link to OptimizationRulesPage
// // //  * AN-10 Generate Insights dialog (POST /analytics/campaign-results)
// // //  * AN-11 link to OptimizationRulesPage (already implemented there)
// // //  * AN-12 Date range filter (7/14/30/60/90 days) driving time-series + metrics
// // //  */
// // // import { useMemo, useState } from "react";
// // // import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// // // import {
// // //   Activity,
// // //   AlertTriangle,
// // //   BarChart3,
// // //   Bot,
// // //   CheckCircle2,
// // //   ExternalLink,
// // //   Info,
// // //   Loader2,
// // //   Sparkles,
// // //   Target,
// // //   TrendingUp,
// // // } from "lucide-react";
// // // import { toast } from "sonner";
// // // import {
// // //   Bar,
// // //   BarChart,
// // //   CartesianGrid,
// // //   Cell,
// // //   Legend,
// // //   Line,
// // //   LineChart,
// // //   Pie,
// // //   PieChart,
// // //   ResponsiveContainer,
// // //   Tooltip as RTooltip,
// // //   XAxis,
// // //   YAxis,
// // // } from "recharts";
// // // import { useNavigate } from "react-router-dom";

// // // import { http } from "@/services/apiClient";
// // // import { PageHeader } from "@/components/ui/page-header";
// // // import { Button } from "@/components/ui/button";
// // // import {
// // //   Card,
// // //   CardContent,
// // //   CardDescription,
// // //   CardHeader,
// // //   CardTitle,
// // // } from "@/components/ui/card";
// // // import { Badge } from "@/components/ui/badge";
// // // import { NativeSelect as Select } from "@/components/ui/select";
// // // import { Skeleton } from "@/components/ui/skeleton";
// // // import {
// // //   Table,
// // //   TableBody,
// // //   TableCell,
// // //   TableHead,
// // //   TableHeader,
// // //   TableRow,
// // // } from "@/components/ui/table";
// // // import {
// // //   Dialog,
// // //   DialogContent,
// // //   DialogDescription,
// // //   DialogFooter,
// // //   DialogHeader,
// // //   DialogTitle,
// // //   DialogTrigger,
// // // } from "@/components/ui/dialog";

// // // /* Types (aligned with real backend schemas) */

// // // interface CampaignMetricRow {
// // //   id: string;
// // //   campaignId: string;
// // //   date: string;
// // //   totalSent: number;
// // //   totalOpened: number;
// // //   totalReplied: number;
// // //   totalBounced: number;
// // //   openRate: number;
// // //   replyRate: number;
// // //   bounceRate: number;
// // //   diagnosticNote: string | null;
// // // }

// // // interface Campaign {
// // //   id: string;
// // //   name: string;
// // //   status: string;
// // // }

// // // interface Sequence {
// // //   id: string;
// // //   campaignId: string;
// // //   prospectId: string;
// // //   touchNumber: number;
// // //   angle: string;
// // //   status: string;
// // //   qaScore: number | null;
// // //   sentAt: string | null;
// // //   openedAt: string | null;
// // //   repliedAt: string | null;
// // //   bouncedAt: string | null;
// // // }

// // // interface ProspectLite {
// // //   id: string;
// // //   intentSource: string;
// // // }

// // // interface TimeSeriesPoint {
// // //   date: string;
// // //   sent: number;
// // //   opened: number;
// // //   replied: number;
// // //   bounced: number;
// // // }

// // // interface DiagnoseLayerResult {
// // //   layer: string;
// // //   status: "ok" | "warn" | "critical";
// // //   metric: string;
// // //   value: number;
// // //   benchmark: number | null;
// // //   note: string;
// // // }

// // // interface DiagnoseResponse {
// // //   campaignId: string | null;
// // //   layers: DiagnoseLayerResult[];
// // //   summary: string;
// // //   generatedAt: string;
// // // }

// // // interface CampaignResult {
// // //   id: string;
// // //   campaignId: string;
// // //   totalSent: number;
// // //   totalReplied: number;
// // //   totalPositive: number;
// // //   totalBounced: number;
// // //   replyRate: number;
// // //   positiveReplyRate: number;
// // //   bounceRate: number;
// // //   whatWorked: string | null;
// // //   whatDidntWork: string | null;
// // //   nextActions: string | null;
// // //   insights: string | null;
// // //   generatedAt: string;
// // // }

// // // interface SystemParamLite {
// // //   key: string;
// // //   label: string;
// // //   value: string;
// // //   unit: string | null;
// // // }

// // // interface UsageBreakdownRow {
// // //   event_type: string;
// // //   provider: string | null;
// // //   total_quantity: number;
// // //   total_cost_cents: number;
// // //   event_count: number;
// // // }

// // // interface UsageResponse {
// // //   period_start: string;
// // //   period_end: string;
// // //   breakdown: UsageBreakdownRow[];
// // //   total_cost_cents: number;
// // // }

// // // const DATE_RANGES = [
// // //   { label: "Last 7 days", days: 7 },
// // //   { label: "Last 14 days", days: 14 },
// // //   { label: "Last 30 days", days: 30 },
// // //   { label: "Last 60 days", days: 60 },
// // //   { label: "Last 90 days", days: 90 },
// // // ];

// // // const ANGLE_LABELS: Record<string, string> = {
// // //   FirstTouch: "First Touch",
// // //   NewEvidence: "New Evidence",
// // //   DifferentPain: "Different Pain",
// // //   IndustryInsight: "Industry Insight",
// // //   DirectQuestion: "Direct Question",
// // //   Breakup: "Breakup",
// // // };

// // // const INTENT_LABELS: Record<string, string> = {
// // //   FUNDING_URGENCY: "Funding Urgency",
// // //   HIRING_BUDGET: "Hiring Budget",
// // //   FORUM_PAIN: "Forum Pain Signal",
// // //   LINKEDIN_DEMAND: "LinkedIn Demand",
// // //   REFERRAL: "Referral",
// // //   INBOUND: "Inbound",
// // //   OTHER: "Other",
// // // };

// // // const STATUS_COLORS: Record<string, string> = {
// // //   Draft: "#94a3b8",
// // //   QaFailed: "#ef4444",
// // //   QaPassed: "#22c55e",
// // //   Scheduled: "#3b82f6",
// // //   Sent: "#8b5cf6",
// // //   Replied: "#10b981",
// // //   Bounced: "#f97316",
// // //   Failed: "#dc2626",
// // // };

// // // function normaliseList<T>(raw: unknown): T[] {
// // //   if (Array.isArray(raw)) return raw as T[];
// // //   if (raw && typeof raw === "object" && "items" in raw)
// // //     return (raw as { items: T[] }).items ?? [];
// // //   return [];
// // // }

// // // function pct(n: number): string {
// // //   return `${(n * 100).toFixed(1)}%`;
// // // }

// // // /* Page */

// // // export function AnalyticsPage() {
// // //   const qc = useQueryClient();
// // //   const navigate = useNavigate();
// // //   const [rangeDays, setRangeDays] = useState(30);
// // //   const [insightsOpen, setInsightsOpen] = useState(false);
// // //   const [insightsCampaignId, setInsightsCampaignId] = useState<string>("");

// // //   const campaignsQ = useQuery({
// // //     queryKey: ["campaigns", "for-analytics"],
// // //     queryFn: () =>
// // //       http.get<unknown>("/api/v1/campaigns").then((r) => normaliseList<Campaign>(r)),
// // //   });
// // //   const campaigns = campaignsQ.data ?? [];

// // //   const metricsQ = useQuery({
// // //     queryKey: ["analytics", "metrics"],
// // //     queryFn: () =>
// // //       http
// // //         .get<unknown>("/api/v1/analytics/metrics")
// // //         .then((r) => normaliseList<CampaignMetricRow>(r)),
// // //   });
// // //   const metrics = metricsQ.data ?? [];

// // //   const timeSeriesQ = useQuery({
// // //     queryKey: ["analytics", "time-series", rangeDays],
// // //     queryFn: () =>
// // //       http.get<{ points: TimeSeriesPoint[] }>(
// // //         `/api/v1/analytics/time-series?days=${rangeDays}`,
// // //       ),
// // //   });
// // //   const timeSeries = timeSeriesQ.data?.points ?? [];

// // //   const sequencesQ = useQuery({
// // //     queryKey: ["sequences", "for-analytics"],
// // //     queryFn: () =>
// // //       http
// // //         .get<unknown>("/api/v1/sequences?limit=500")
// // //         .then((r) => normaliseList<Sequence>(r)),
// // //   });
// // //   const sequences = sequencesQ.data ?? [];

// // //   const prospectsQ = useQuery({
// // //     queryKey: ["prospects", "for-analytics"],
// // //     queryFn: () =>
// // //       http
// // //         .get<unknown>("/api/v1/prospects?limit=500")
// // //         .then((r) => normaliseList<ProspectLite>(r)),
// // //   });
// // //   const prospects = prospectsQ.data ?? [];

// // //   const diagnoseQ = useQuery({
// // //     queryKey: ["analytics", "diagnose", "tenant"],
// // //     queryFn: () =>
// // //       http.post<DiagnoseResponse>("/api/v1/analytics/diagnose", {
// // //         campaignId: null,
// // //       }),
// // //   });
// // //   const diagnose = diagnoseQ.data;

// // //   const benchmarksQ = useQuery({
// // //     queryKey: ["system-params", "Analytics Benchmarks"],
// // //     queryFn: () =>
// // //       http
// // //         .get<unknown>(
// // //           `/api/v1/system-params?category=${encodeURIComponent("Analytics Benchmarks")}`,
// // //         )
// // //         .then((r) => normaliseList<SystemParamLite>(r)),
// // //   });
// // //   const benchmarks = benchmarksQ.data ?? [];

// // //   const usageQ = useQuery({
// // //     queryKey: ["usage", "tenant"],
// // //     queryFn: () => http.get<UsageResponse>("/api/v1/usage/tenant"),
// // //   });
// // //   const usage = usageQ.data;

// // //   const resultQ = useQuery({
// // //     queryKey: ["analytics", "campaign-results", insightsCampaignId],
// // //     queryFn: () =>
// // //       http.get<CampaignResult | null>(
// // //         `/api/v1/analytics/campaign-results?campaign_id=${insightsCampaignId}`,
// // //       ),
// // //     enabled: !!insightsCampaignId && insightsOpen,
// // //   });

// // //   const generateInsightsMutation = useMutation({
// // //     mutationFn: (campaignId: string) =>
// // //       http.post<CampaignResult>(
// // //         `/api/v1/analytics/campaign-results?campaign_id=${campaignId}`,
// // //         {},
// // //       ),
// // //     onSuccess: () => {
// // //       toast.success("Insights generated");
// // //       qc.invalidateQueries({ queryKey: ["analytics", "campaign-results"] });
// // //     },
// // //     onError: () =>
// // //       toast.error("Failed to generate insights — this campaign may have no metrics yet"),
// // //   });

// // //   /* ── AN-2: Campaign Performance table (sum metrics per campaignId) ── */
// // //   const campaignPerformance = useMemo(() => {
// // //     const byCampaign = new Map<
// // //       string,
// // //       { sent: number; opened: number; replied: number; bounced: number }
// // //     >();
// // //     for (const m of metrics) {
// // //       const cur = byCampaign.get(m.campaignId) ?? {
// // //         sent: 0,
// // //         opened: 0,
// // //         replied: 0,
// // //         bounced: 0,
// // //       };
// // //       cur.sent += m.totalSent;
// // //       cur.opened += m.totalOpened;
// // //       cur.replied += m.totalReplied;
// // //       cur.bounced += m.totalBounced;
// // //       byCampaign.set(m.campaignId, cur);
// // //     }
// // //     return Array.from(byCampaign.entries())
// // //       .map(([campaignId, agg]) => {
// // //         const campaign = campaigns.find((c) => c.id === campaignId);
// // //         return {
// // //           campaignId,
// // //           name: campaign?.name ?? campaignId,
// // //           status: campaign?.status ?? "unknown",
// // //           ...agg,
// // //           openRate: agg.sent ? agg.opened / agg.sent : 0,
// // //           replyRate: agg.sent ? agg.replied / agg.sent : 0,
// // //           bounceRate: agg.sent ? agg.bounced / agg.sent : 0,
// // //         };
// // //       })
// // //       .sort((a, b) => b.sent - a.sent);
// // //   }, [metrics, campaigns]);

// // //   /* ── AN-1: Sequence Status Distribution ── */
// // //   const statusDistribution = useMemo(() => {
// // //     const counts = new Map<string, number>();
// // //     for (const s of sequences) counts.set(s.status, (counts.get(s.status) ?? 0) + 1);
// // //     return Array.from(counts.entries()).map(([status, count]) => ({
// // //       status,
// // //       count,
// // //       fill: STATUS_COLORS[status] ?? "#94a3b8",
// // //     }));
// // //   }, [sequences]);

// // //   /* ── AN-3: Sequence Step Performance (touch 1-7) ── */
// // //   const stepPerformance = useMemo(() => {
// // //     const byTouch = new Map<
// // //       number,
// // //       { sent: number; opened: number; replied: number }
// // //     >();
// // //     for (const s of sequences) {
// // //       const cur = byTouch.get(s.touchNumber) ?? { sent: 0, opened: 0, replied: 0 };
// // //       if (s.sentAt) cur.sent += 1;
// // //       if (s.openedAt) cur.opened += 1;
// // //       if (s.repliedAt) cur.replied += 1;
// // //       byTouch.set(s.touchNumber, cur);
// // //     }
// // //     return Array.from(byTouch.entries())
// // //       .sort(([a], [b]) => a - b)
// // //       .map(([touch, agg]) => ({
// // //         touch: `T${touch}`,
// // //         openRate: agg.sent ? Math.round((agg.opened / agg.sent) * 1000) / 10 : 0,
// // //         replyRate: agg.sent ? Math.round((agg.replied / agg.sent) * 1000) / 10 : 0,
// // //         sent: agg.sent,
// // //       }));
// // //   }, [sequences]);

// // //   /* ── AN-5: Copy Angle Performance ── */
// // //   const anglePerformance = useMemo(() => {
// // //     const byAngle = new Map<
// // //       string,
// // //       { sent: number; opened: number; replied: number }
// // //     >();
// // //     for (const s of sequences) {
// // //       const cur = byAngle.get(s.angle) ?? { sent: 0, opened: 0, replied: 0 };
// // //       if (s.sentAt) cur.sent += 1;
// // //       if (s.openedAt) cur.opened += 1;
// // //       if (s.repliedAt) cur.replied += 1;
// // //       byAngle.set(s.angle, cur);
// // //     }
// // //     return Array.from(byAngle.entries())
// // //       .map(([angle, agg]) => ({
// // //         angle: ANGLE_LABELS[angle] ?? angle,
// // //         replyRate: agg.sent ? Math.round((agg.replied / agg.sent) * 1000) / 10 : 0,
// // //         sent: agg.sent,
// // //       }))
// // //       .sort((a, b) => b.replyRate - a.replyRate);
// // //   }, [sequences]);

// // //   /* ── AN-4: Intent Source Attribution (real Prospect.intentSource) ── */
// // //   const intentAttribution = useMemo(() => {
// // //     const repliedProspectIds = new Set(
// // //       sequences.filter((s) => s.repliedAt).map((s) => s.prospectId),
// // //     );
// // //     const bySource = new Map<string, { total: number; replied: number }>();
// // //     for (const p of prospects) {
// // //       const cur = bySource.get(p.intentSource) ?? { total: 0, replied: 0 };
// // //       cur.total += 1;
// // //       if (repliedProspectIds.has(p.id)) cur.replied += 1;
// // //       bySource.set(p.intentSource, cur);
// // //     }
// // //     return Array.from(bySource.entries())
// // //       .map(([source, agg]) => ({
// // //         source: INTENT_LABELS[source] ?? source,
// // //         total: agg.total,
// // //         replied: agg.replied,
// // //         contributionRate: agg.total ? Math.round((agg.replied / agg.total) * 1000) / 10 : 0,
// // //       }))
// // //       .sort((a, b) => b.replied - a.replied);
// // //   }, [sequences, prospects]);

// // //   /* ── AN-7: QA Score Distribution ── */
// // //   const qaDistribution = useMemo(() => {
// // //     const buckets = [
// // //       { label: "0-59", min: 0, max: 59, count: 0 },
// // //       { label: "60-69", min: 60, max: 69, count: 0 },
// // //       { label: "70-79", min: 70, max: 79, count: 0 },
// // //       { label: "80-89", min: 80, max: 89, count: 0 },
// // //       { label: "90-100", min: 90, max: 100, count: 0 },
// // //     ];
// // //     for (const s of sequences) {
// // //       if (s.qaScore == null) continue;
// // //       const bucket = buckets.find((b) => s.qaScore! >= b.min && s.qaScore! <= b.max);
// // //       if (bucket) bucket.count += 1;
// // //     }
// // //     return buckets;
// // //   }, [sequences]);

// // //   const scoredCount = sequences.filter((s) => s.qaScore != null).length;
// // //   const avgQaScore = scoredCount
// // //     ? Math.round(
// // //         sequences.reduce((sum, s) => sum + (s.qaScore ?? 0), 0) / scoredCount,
// // //       )
// // //     : null;

// // //   const isLoading =
// // //     campaignsQ.isLoading || metricsQ.isLoading || sequencesQ.isLoading;

// // //   return (
// // //     <div className="space-y-6 p-6">
// // //       <PageHeader
// // //         title="Analytics"
// // //         description="Campaign performance, health diagnostics, and statistical breakdowns across your outreach."
// // //         actions={
// // //           <div className="flex items-center gap-2">
// // //             <Select
// // //               value={String(rangeDays)}
// // //               onChange={(e) => setRangeDays(Number(e.target.value))}
// // //               className="w-40"
// // //             >
// // //               {DATE_RANGES.map((r) => (
// // //                 <option key={r.days} value={r.days}>
// // //                   {r.label}
// // //                 </option>
// // //               ))}
// // //             </Select>
// // //             <Dialog open={insightsOpen} onOpenChange={setInsightsOpen}>
// // //               <DialogTrigger asChild>
// // //                 <Button variant="outline" onClick={() => setInsightsOpen(true)}>
// // //                   <Sparkles className="h-4 w-4 mr-2" />
// // //                   AI Insights
// // //                 </Button>
// // //               </DialogTrigger>
// // //               <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
// // //                 <DialogHeader>
// // //                   <DialogTitle>Generate Campaign Insights</DialogTitle>
// // //                   <DialogDescription>
// // //                     Select a campaign to generate an AI-written post-mortem:
// // //                     what worked, what didn't, and next actions.
// // //                   </DialogDescription>
// // //                 </DialogHeader>
// // //                 <div className="space-y-4">
// // //                   <Select
// // //                     value={insightsCampaignId}
// // //                     onChange={(e) => setInsightsCampaignId(e.target.value)}
// // //                   >
// // //                     <option value="">Select a campaign…</option>
// // //                     {campaigns.map((c) => (
// // //                       <option key={c.id} value={c.id}>
// // //                         {c.name}
// // //                       </option>
// // //                     ))}
// // //                   </Select>

// // //                   {insightsCampaignId && resultQ.isLoading && (
// // //                     <Skeleton className="h-32 w-full" />
// // //                   )}

// // //                   {insightsCampaignId && !resultQ.isLoading && !resultQ.data && (
// // //                     <div className="text-center py-6 text-sm text-muted-foreground">
// // //                       No insights generated yet for this campaign.
// // //                     </div>
// // //                   )}

// // //                   {resultQ.data && (
// // //                     <div className="space-y-3 text-sm">
// // //                       <div className="grid grid-cols-3 gap-3">
// // //                         <div className="rounded-md border p-2 text-center">
// // //                           <p className="text-lg font-bold">{resultQ.data.totalSent}</p>
// // //                           <p className="text-xs text-muted-foreground">Sent</p>
// // //                         </div>
// // //                         <div className="rounded-md border p-2 text-center">
// // //                           <p className="text-lg font-bold">{pct(resultQ.data.replyRate)}</p>
// // //                           <p className="text-xs text-muted-foreground">Reply rate</p>
// // //                         </div>
// // //                         <div className="rounded-md border p-2 text-center">
// // //                           <p className="text-lg font-bold">
// // //                             {pct(resultQ.data.positiveReplyRate)}
// // //                           </p>
// // //                           <p className="text-xs text-muted-foreground">Positive rate</p>
// // //                         </div>
// // //                       </div>
// // //                       {resultQ.data.whatWorked && (
// // //                         <div>
// // //                           <p className="font-medium text-xs mb-1">What worked</p>
// // //                           <p className="text-muted-foreground">{resultQ.data.whatWorked}</p>
// // //                         </div>
// // //                       )}
// // //                       {resultQ.data.whatDidntWork && (
// // //                         <div>
// // //                           <p className="font-medium text-xs mb-1">What didn't work</p>
// // //                           <p className="text-muted-foreground">
// // //                             {resultQ.data.whatDidntWork}
// // //                           </p>
// // //                         </div>
// // //                       )}
// // //                       {resultQ.data.nextActions && (
// // //                         <div>
// // //                           <p className="font-medium text-xs mb-1">Next actions</p>
// // //                           <p className="text-muted-foreground">{resultQ.data.nextActions}</p>
// // //                         </div>
// // //                       )}
// // //                       {resultQ.data.insights && (
// // //                         <div>
// // //                           <p className="font-medium text-xs mb-1">Insights</p>
// // //                           <p className="text-muted-foreground">{resultQ.data.insights}</p>
// // //                         </div>
// // //                       )}
// // //                       <p className="text-[10px] text-muted-foreground">
// // //                         Generated {new Date(resultQ.data.generatedAt).toLocaleString()}
// // //                       </p>
// // //                     </div>
// // //                   )}
// // //                 </div>
// // //                 <DialogFooter>
// // //                   <Button
// // //                     variant="outline"
// // //                     onClick={() => {
// // //                       setInsightsOpen(false);
// // //                       setInsightsCampaignId("");
// // //                     }}
// // //                   >
// // //                     Close
// // //                   </Button>
// // //                   <Button
// // //                     onClick={() =>
// // //                       insightsCampaignId &&
// // //                       generateInsightsMutation.mutate(insightsCampaignId)
// // //                     }
// // //                     disabled={!insightsCampaignId || generateInsightsMutation.isPending}
// // //                   >
// // //                     {generateInsightsMutation.isPending ? (
// // //                       <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
// // //                     ) : (
// // //                       <Sparkles className="h-3.5 w-3.5 mr-1.5" />
// // //                     )}
// // //                     Generate Insights
// // //                   </Button>
// // //                 </DialogFooter>
// // //               </DialogContent>
// // //             </Dialog>
// // //           </div>
// // //         }
// // //       />

// // //       {isLoading ? (
// // //         <div className="space-y-3">
// // //           {[0, 1, 2].map((i) => (
// // //             <Skeleton key={i} className="h-32 w-full" />
// // //           ))}
// // //         </div>
// // //       ) : (
// // //         <>
// // //           {/* Time series (AN-12 date range) */}
// // //           <Card>
// // //             <CardHeader>
// // //               <CardTitle className="text-base">Activity Over Time</CardTitle>
// // //               <CardDescription>
// // //                 Sent, opened, replied, and bounced counts for the selected range.
// // //               </CardDescription>
// // //             </CardHeader>
// // //             <CardContent>
// // //               {timeSeriesQ.isLoading ? (
// // //                 <Skeleton className="h-64 w-full" />
// // //               ) : (
// // //                 <ResponsiveContainer width="100%" height={260}>
// // //                   <LineChart data={timeSeries}>
// // //                     <CartesianGrid strokeDasharray="3 3" />
// // //                     <XAxis dataKey="date" tick={{ fontSize: 11 }} />
// // //                     <YAxis tick={{ fontSize: 11 }} />
// // //                     <RTooltip />
// // //                     <Legend />
// // //                     <Line type="monotone" dataKey="sent" stroke="#8b5cf6" strokeWidth={2} />
// // //                     <Line type="monotone" dataKey="opened" stroke="#3b82f6" strokeWidth={2} />
// // //                     <Line type="monotone" dataKey="replied" stroke="#10b981" strokeWidth={2} />
// // //                     <Line type="monotone" dataKey="bounced" stroke="#f97316" strokeWidth={2} />
// // //                   </LineChart>
// // //                 </ResponsiveContainer>
// // //               )}
// // //             </CardContent>
// // //           </Card>

// // //           {/* AN-2: Campaign Performance table */}
// // //           <Card>
// // //             <CardHeader>
// // //               <CardTitle className="text-base flex items-center gap-2">
// // //                 <BarChart3 className="h-4 w-4" /> Campaign Performance
// // //               </CardTitle>
// // //               <CardDescription>
// // //                 Aggregated send/open/reply/bounce metrics per campaign.
// // //               </CardDescription>
// // //             </CardHeader>
// // //             <CardContent>
// // //               {campaignPerformance.length === 0 ? (
// // //                 <p className="text-sm text-muted-foreground py-6 text-center">
// // //                   No campaign metrics yet — metrics populate once sequences start sending.
// // //                 </p>
// // //               ) : (
// // //                 <Table>
// // //                   <TableHeader>
// // //                     <TableRow>
// // //                       <TableHead>Campaign</TableHead>
// // //                       <TableHead>Status</TableHead>
// // //                       <TableHead className="text-right">Sent</TableHead>
// // //                       <TableHead className="text-right">Opened</TableHead>
// // //                       <TableHead className="text-right">Replied</TableHead>
// // //                       <TableHead className="text-right">Bounced</TableHead>
// // //                       <TableHead className="text-right">Open Rate</TableHead>
// // //                       <TableHead className="text-right">Reply Rate</TableHead>
// // //                     </TableRow>
// // //                   </TableHeader>
// // //                   <TableBody>
// // //                     {campaignPerformance.map((c) => (
// // //                       <TableRow key={c.campaignId}>
// // //                         <TableCell className="font-medium">{c.name}</TableCell>
// // //                         <TableCell>
// // //                           <Badge variant="outline" className="text-[10px]">
// // //                             {c.status}
// // //                           </Badge>
// // //                         </TableCell>
// // //                         <TableCell className="text-right tabular-nums">{c.sent}</TableCell>
// // //                         <TableCell className="text-right tabular-nums">{c.opened}</TableCell>
// // //                         <TableCell className="text-right tabular-nums">{c.replied}</TableCell>
// // //                         <TableCell className="text-right tabular-nums">{c.bounced}</TableCell>
// // //                         <TableCell className="text-right tabular-nums">
// // //                           {pct(c.openRate)}
// // //                         </TableCell>
// // //                         <TableCell className="text-right tabular-nums">
// // //                           {pct(c.replyRate)}
// // //                         </TableCell>
// // //                       </TableRow>
// // //                     ))}
// // //                   </TableBody>
// // //                 </Table>
// // //               )}
// // //             </CardContent>
// // //           </Card>

// // //           <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
// // //             {/* AN-1: Sequence Status Distribution */}
// // //             <Card>
// // //               <CardHeader>
// // //                 <CardTitle className="text-base">Sequence Status Distribution</CardTitle>
// // //                 <CardDescription className="text-xs">
// // //                   Current status of all sequenced touches.
// // //                 </CardDescription>
// // //               </CardHeader>
// // //               <CardContent>
// // //                 {statusDistribution.length === 0 ? (
// // //                   <p className="text-sm text-muted-foreground py-6 text-center">
// // //                     No sequences yet.
// // //                   </p>
// // //                 ) : (
// // //                   <ResponsiveContainer width="100%" height={240}>
// // //                     <PieChart>
// // //                       <Pie
// // //                         data={statusDistribution}
// // //                         dataKey="count"
// // //                         nameKey="status"
// // //                         cx="50%"
// // //                         cy="50%"
// // //                         outerRadius={80}
// // //                         label={(entry: { status: string }) => entry.status}
// // //                       >
// // //                         {statusDistribution.map((entry) => (
// // //                           <Cell key={entry.status} fill={entry.fill} />
// // //                         ))}
// // //                       </Pie>
// // //                       <RTooltip />
// // //                     </PieChart>
// // //                   </ResponsiveContainer>
// // //                 )}
// // //               </CardContent>
// // //             </Card>

// // //             {/* AN-3: Sequence Step Performance */}
// // //             <Card>
// // //               <CardHeader>
// // //                 <CardTitle className="text-base">Sequence Step Performance</CardTitle>
// // //                 <CardDescription className="text-xs">
// // //                   Open and reply rate by touch number (T1-T7).
// // //                 </CardDescription>
// // //               </CardHeader>
// // //               <CardContent>
// // //                 {stepPerformance.length === 0 ? (
// // //                   <p className="text-sm text-muted-foreground py-6 text-center">
// // //                     No sent touches yet.
// // //                   </p>
// // //                 ) : (
// // //                   <ResponsiveContainer width="100%" height={240}>
// // //                     <BarChart data={stepPerformance}>
// // //                       <CartesianGrid strokeDasharray="3 3" />
// // //                       <XAxis dataKey="touch" tick={{ fontSize: 11 }} />
// // //                       <YAxis tick={{ fontSize: 11 }} unit="%" />
// // //                       <RTooltip />
// // //                       <Legend />
// // //                       <Bar dataKey="openRate" name="Open %" fill="#3b82f6" />
// // //                       <Bar dataKey="replyRate" name="Reply %" fill="#10b981" />
// // //                     </BarChart>
// // //                   </ResponsiveContainer>
// // //                 )}
// // //               </CardContent>
// // //             </Card>

// // //             {/* AN-5: Copy Angle Performance */}
// // //             <Card>
// // //               <CardHeader>
// // //                 <CardTitle className="text-base">Copy Angle Performance</CardTitle>
// // //                 <CardDescription className="text-xs">
// // //                   Reply rate by messaging angle, best first.
// // //                 </CardDescription>
// // //               </CardHeader>
// // //               <CardContent>
// // //                 {anglePerformance.length === 0 ? (
// // //                   <p className="text-sm text-muted-foreground py-6 text-center">
// // //                     No sent touches yet.
// // //                   </p>
// // //                 ) : (
// // //                   <ResponsiveContainer width="100%" height={240}>
// // //                     <BarChart data={anglePerformance} layout="vertical">
// // //                       <CartesianGrid strokeDasharray="3 3" />
// // //                       <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
// // //                       <YAxis
// // //                         type="category"
// // //                         dataKey="angle"
// // //                         tick={{ fontSize: 11 }}
// // //                         width={110}
// // //                       />
// // //                       <RTooltip />
// // //                       <Bar dataKey="replyRate" name="Reply %" fill="#8b5cf6" />
// // //                     </BarChart>
// // //                   </ResponsiveContainer>
// // //                 )}
// // //               </CardContent>
// // //             </Card>

// // //             {/* AN-4: Intent Source Attribution */}
// // //             <Card>
// // //               <CardHeader>
// // //                 <CardTitle className="text-base">Intent Source Attribution</CardTitle>
// // //                 <CardDescription className="text-xs">
// // //                   Prospect count and reply contribution by buying-intent
// // //                   source (Prospect.intentSource).
// // //                 </CardDescription>
// // //               </CardHeader>
// // //               <CardContent>
// // //                 {intentAttribution.length === 0 ? (
// // //                   <p className="text-sm text-muted-foreground py-6 text-center">
// // //                     No prospects yet.
// // //                   </p>
// // //                 ) : (
// // //                   <ResponsiveContainer width="100%" height={240}>
// // //                     <BarChart data={intentAttribution} layout="vertical">
// // //                       <CartesianGrid strokeDasharray="3 3" />
// // //                       <XAxis type="number" tick={{ fontSize: 11 }} />
// // //                       <YAxis
// // //                         type="category"
// // //                         dataKey="source"
// // //                         tick={{ fontSize: 11 }}
// // //                         width={110}
// // //                       />
// // //                       <RTooltip />
// // //                       <Legend />
// // //                       <Bar dataKey="total" name="Prospects" fill="#94a3b8" />
// // //                       <Bar dataKey="replied" name="Replied" fill="#10b981" />
// // //                     </BarChart>
// // //                   </ResponsiveContainer>
// // //                 )}
// // //               </CardContent>
// // //             </Card>
// // //           </div>

// // //           {/* AN-6: Campaign Health Diagnostics */}
// // //           <Card>
// // //             <CardHeader>
// // //               <CardTitle className="text-base flex items-center gap-2">
// // //                 <Activity className="h-4 w-4" /> Campaign Health Diagnostics
// // //               </CardTitle>
// // //               <CardDescription>
// // //                 5-layer closed-loop diagnostic across all active campaigns.
// // //               </CardDescription>
// // //             </CardHeader>
// // //             <CardContent>
// // //               {diagnoseQ.isLoading ? (
// // //                 <Skeleton className="h-32 w-full" />
// // //               ) : diagnose ? (
// // //                 <div className="space-y-3">
// // //                   <p className="text-sm text-muted-foreground">{diagnose.summary}</p>
// // //                   <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2">
// // //                     {diagnose.layers.map((l) => (
// // //                       <div
// // //                         key={l.layer}
// // //                         className={`rounded-md border p-2.5 text-xs ${
// // //                           l.status === "critical"
// // //                             ? "border-red-300 bg-red-50"
// // //                             : l.status === "warn"
// // //                               ? "border-amber-300 bg-amber-50"
// // //                               : "border-emerald-200 bg-emerald-50"
// // //                         }`}
// // //                       >
// // //                         <div className="flex items-center justify-between mb-1">
// // //                           <span className="font-medium capitalize">{l.layer}</span>
// // //                           {l.status === "critical" ? (
// // //                             <AlertTriangle className="h-3.5 w-3.5 text-red-600" />
// // //                           ) : l.status === "warn" ? (
// // //                             <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
// // //                           ) : (
// // //                             <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
// // //                           )}
// // //                         </div>
// // //                         <p className="tabular-nums font-mono">
// // //                           {l.metric}: {l.value}
// // //                           {l.benchmark != null && (
// // //                             <span className="text-muted-foreground"> / {l.benchmark}</span>
// // //                           )}
// // //                         </p>
// // //                         <p className="text-muted-foreground mt-1">{l.note}</p>
// // //                       </div>
// // //                     ))}
// // //                   </div>
// // //                 </div>
// // //               ) : (
// // //                 <p className="text-sm text-muted-foreground py-6 text-center">
// // //                   No diagnostic data available yet.
// // //                 </p>
// // //               )}
// // //             </CardContent>
// // //           </Card>

// // //           <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
// // //             {/* AN-7: AI Performance Diagnostics */}
// // //             <Card>
// // //               <CardHeader>
// // //                 <CardTitle className="text-base flex items-center gap-2">
// // //                   <Bot className="h-4 w-4" /> AI Performance
// // //                 </CardTitle>
// // //                 <CardDescription className="text-xs">
// // //                   LLM usage/cost this period and QA score distribution.
// // //                   (Generation-time tracking isn't recorded by the backend.)
// // //                 </CardDescription>
// // //               </CardHeader>
// // //               <CardContent className="space-y-4">
// // //                 {usageQ.isLoading ? (
// // //                   <Skeleton className="h-24 w-full" />
// // //                 ) : usage && usage.breakdown.length > 0 ? (
// // //                   <div className="space-y-1.5">
// // //                     {usage.breakdown.map((row) => (
// // //                       <div
// // //                         key={`${row.event_type}-${row.provider}`}
// // //                         className="flex items-center justify-between text-xs bg-muted/50 rounded px-2 py-1.5"
// // //                       >
// // //                         <span>
// // //                           {row.event_type}
// // //                           {row.provider ? ` · ${row.provider}` : ""}
// // //                         </span>
// // //                         <span className="tabular-nums text-muted-foreground">
// // //                           {row.event_count} calls · ${(row.total_cost_cents / 100).toFixed(2)}
// // //                         </span>
// // //                       </div>
// // //                     ))}
// // //                     <p className="text-xs font-medium pt-1">
// // //                       Total: ${(usage.total_cost_cents / 100).toFixed(2)}
// // //                     </p>
// // //                   </div>
// // //                 ) : (
// // //                   <p className="text-xs text-muted-foreground">No usage recorded this period.</p>
// // //                 )}

// // //                 <div>
// // //                   <p className="text-xs font-medium mb-2">
// // //                     QA Score Distribution
// // //                     {avgQaScore != null && (
// // //                       <span className="text-muted-foreground"> · avg {avgQaScore}</span>
// // //                     )}
// // //                   </p>
// // //                   {scoredCount === 0 ? (
// // //                     <p className="text-xs text-muted-foreground">No QA-scored emails yet.</p>
// // //                   ) : (
// // //                     <ResponsiveContainer width="100%" height={140}>
// // //                       <BarChart data={qaDistribution}>
// // //                         <XAxis dataKey="label" tick={{ fontSize: 10 }} />
// // //                         <YAxis tick={{ fontSize: 10 }} />
// // //                         <RTooltip />
// // //                         <Bar dataKey="count" fill="#3b82f6" />
// // //                       </BarChart>
// // //                     </ResponsiveContainer>
// // //                   )}
// // //                 </div>
// // //               </CardContent>
// // //             </Card>

// // //             {/* AN-8: Industry Benchmarks */}
// // //             <Card>
// // //               <CardHeader>
// // //                 <CardTitle className="text-base flex items-center gap-2">
// // //                   <Target className="h-4 w-4" /> Benchmarks
// // //                 </CardTitle>
// // //                 <CardDescription className="text-xs">
// // //                   Your configured health-diagnostic thresholds (System
// // //                   Parameters → Analytics Benchmarks).
// // //                 </CardDescription>
// // //               </CardHeader>
// // //               <CardContent>
// // //                 {benchmarksQ.isLoading ? (
// // //                   <Skeleton className="h-24 w-full" />
// // //                 ) : benchmarks.length === 0 ? (
// // //                   <p className="text-xs text-muted-foreground py-4 text-center">
// // //                     No benchmark parameters configured.
// // //                   </p>
// // //                 ) : (
// // //                   <div className="grid grid-cols-2 gap-2">
// // //                     {benchmarks.map((b) => (
// // //                       <div key={b.key} className="rounded-md border p-2 text-center">
// // //                         <p className="text-lg font-bold">
// // //                           {b.value}
// // //                           {b.unit?.includes("%") ? "" : ""}
// // //                         </p>
// // //                         <p className="text-[10px] text-muted-foreground">{b.label}</p>
// // //                       </div>
// // //                     ))}
// // //                   </div>
// // //                 )}
// // //                 <Button
// // //                   variant="ghost"
// // //                   size="sm"
// // //                   className="mt-3 w-full"
// // //                   onClick={() => navigate("/setup/system-params")}
// // //                 >
// // //                   Adjust benchmarks in System Parameters
// // //                   <ExternalLink className="h-3 w-3 ml-1.5" />
// // //                 </Button>
// // //               </CardContent>
// // //             </Card>
// // //           </div>

// // //           {/* AN-9 / AN-11: Auto-Optimization link-out */}
// // //           <Card className="border-violet-200 bg-violet-50/50">
// // //             <CardContent className="py-4 flex items-center justify-between gap-4">
// // //               <div className="flex items-center gap-3">
// // //                 <TrendingUp className="h-5 w-5 text-violet-600 shrink-0" />
// // //                 <div>
// // //                   <p className="text-sm font-medium">Auto-Optimization Rules Engine</p>
// // //                   <p className="text-xs text-muted-foreground">
// // //                     Create rules like "if reply rate &lt; 5% for 3+ days, pause
// // //                     campaign" — managed on its own page with full create/edit/delete.
// // //                   </p>
// // //                 </div>
// // //               </div>
// // //               <Button
// // //                 variant="outline"
// // //                 size="sm"
// // //                 className="shrink-0"
// // //                 onClick={() => navigate("/optimize/optimization-rules")}
// // //               >
// // //                 Open Optimization Rules
// // //                 <ExternalLink className="h-3 w-3 ml-1.5" />
// // //               </Button>
// // //             </CardContent>
// // //           </Card>

// // //           <Card className="p-4 bg-muted/30 border-dashed">
// // //             <div className="flex gap-3">
// // //               <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
// // //               <p className="text-xs text-muted-foreground">
// // //                 Campaign Performance and the time-series chart reflect data
// // //                 across all campaigns for the selected range. Sequence-derived
// // //                 charts (status, step, angle, intent) are computed from the
// // //                 most recent 500 sequences and 500 prospects.
// // //               </p>
// // //             </div>
// // //           </Card>
// // //         </>
// // //       )}
// // //     </div>
// // //   );
// // // }

// // /**
// //  * AnalyticsPage.tsx - campaign performance, health diagnostics, and
// //  * statistical breakdowns across sequences, prospects, and LLM usage.
// //  *
// //  * API (verified against real routers/schemas - see comments per section):
// //  *   GET  /api/v1/analytics/metrics?campaign_id=        -> CampaignMetricResponse[] (per campaign+date)
// //  *   GET  /api/v1/analytics/time-series?days=N          -> TimeSeriesResponse
// //  *   POST /api/v1/analytics/diagnose                     { campaignId } -> DiagnoseResponse
// //  *   GET  /api/v1/analytics/campaign-results?campaign_id= -> CampaignResultResponse | null
// //  *   POST /api/v1/analytics/campaign-results?campaign_id= -> CampaignResultResponse (generates)
// //  *   GET  /api/v1/campaigns                               -> CampaignResponse[] (for names + selector)
// //  *   GET  /api/v1/sequences?limit=500                      -> SequenceResponse[] (touchNumber, angle, status, timestamps)
// //  *   GET  /api/v1/prospects?limit=500                      -> Prospect[] (intentSource)
// //  *   GET  /api/v1/system-params?category=Analytics%20Benchmarks -> SystemParamResponse[]
// //  *   GET  /api/v1/usage/tenant?period=YYYY-MM               -> UsageResponse (LLM cost/event breakdown)
// //  *
// //  * CORRECTIONS vs. the previous version: the old page had a completely wrong
// //  * response shape for /analytics/metrics (treated it as one aggregated
// //  * object; it's actually an array of per-campaign-per-date rows), called
// //  * /analytics/time-series with a campaignId param it doesn't accept (it's
// //  * tenant-wide, only takes `days`), and fell back to MOCK_METRICS /
// //  * MOCK_TIMESERIES / MOCK_DIAGNOSE / MOCK_RESULTS / MOCK_CAMPAIGNS whenever
// //  * a real call returned anything falsy. All mock fallbacks removed.
// //  *
// //  * Backend gaps documented rather than faked:
// //  *   - AN-4 "Intent Source Attribution" is built from Prospect.intentSource
// //  *     (FUNDING_URGENCY/HIRING_BUDGET/FORUM_PAIN/LINKEDIN_DEMAND/REFERRAL/
// //  *     INBOUND/OTHER) - the real backend field. There is no field tracking
// //  *     which *sourcing platform* (Apollo/LinkedIn/manual/CSV) found a
// //  *     prospect, so that specific breakdown the gap doc describes isn't
// //  *     buildable from real data; intentSource is the closest real analogue
// //  *     and is labeled accurately as such.
// //  *   - AN-7 "avg generation time" has no backend field anywhere (LLM calls
// //  *     aren't timed) - omitted rather than fabricated. LLM usage/cost and
// //  *     QA score distribution (both real) are shown instead.
// //  *   - AN-9/AN-11 (Auto-Optimization Rules) already live on a separate,
// //  *     fully-built OptimizationRulesPage per the gap audit - this page
// //  *     links out to it instead of duplicating its CRUD.
// //  *
// //  * AN-1  Sequence Status Distribution (donut, from /sequences grouped by status)
// //  * AN-2  Campaign Performance table (from /analytics/metrics, summed per campaign)
// //  * AN-3  Sequence Step Performance (bar, from /sequences grouped by touchNumber)
// //  * AN-4  Intent Source Attribution (bar, from /prospects.intentSource + reply join)
// //  * AN-5  Copy Angle Performance (bar, from /sequences grouped by angle)
// //  * AN-6  Campaign Health Diagnostics (from /analytics/diagnose)
// //  * AN-7  AI Performance Diagnostics (usage/tenant + QA score histogram)
// //  * AN-8  Industry Benchmarks (from /system-params?category=Analytics Benchmarks)
// //  * AN-9  Auto-Optimization summary + link to OptimizationRulesPage
// //  * AN-10 Generate Insights dialog (POST /analytics/campaign-results)
// //  * AN-11 link to OptimizationRulesPage (already implemented there)
// //  * AN-12 Date range filter (7/14/30/60/90 days) driving time-series + metrics
// //  */
// // import { useMemo, useState } from "react";
// // import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// // import {
// //   Activity,
// //   AlertTriangle,
// //   BarChart3,
// //   Bot,
// //   CheckCircle2,
// //   ExternalLink,
// //   Info,
// //   Loader2,
// //   Sparkles,
// //   Target,
// //   TrendingUp,
// // } from "lucide-react";
// // import { toast } from "sonner";
// // import {
// //   Bar,
// //   BarChart,
// //   CartesianGrid,
// //   Cell,
// //   Legend,
// //   Line,
// //   LineChart,
// //   Pie,
// //   PieChart,
// //   ResponsiveContainer,
// //   Tooltip as RTooltip,
// //   XAxis,
// //   YAxis,
// // } from "recharts";
// // import { useNavigate } from "react-router-dom";

// // import { http } from "@/services/apiClient";
// // import { PageHeader } from "@/components/ui/page-header";
// // import { Button } from "@/components/ui/button";
// // import {
// //   Card,
// //   CardContent,
// //   CardDescription,
// //   CardHeader,
// //   CardTitle,
// // } from "@/components/ui/card";
// // import { Badge } from "@/components/ui/badge";
// // import { NativeSelect as Select } from "@/components/ui/select";
// // import { Skeleton } from "@/components/ui/skeleton";
// // import {
// //   Table,
// //   TableBody,
// //   TableCell,
// //   TableHead,
// //   TableHeader,
// //   TableRow,
// // } from "@/components/ui/table";
// // import {
// //   Dialog,
// //   DialogContent,
// //   DialogDescription,
// //   DialogFooter,
// //   DialogHeader,
// //   DialogTitle,
// //   DialogTrigger,
// // } from "@/components/ui/dialog";

// // /* Types (aligned with real backend schemas) */

// // interface CampaignMetricRow {
// //   id: string;
// //   campaignId: string;
// //   date: string;
// //   totalSent: number;
// //   totalOpened: number;
// //   totalReplied: number;
// //   totalBounced: number;
// //   openRate: number;
// //   replyRate: number;
// //   bounceRate: number;
// //   diagnosticNote: string | null;
// // }

// // interface Campaign {
// //   id: string;
// //   name: string;
// //   status: string;
// // }

// // interface Sequence {
// //   id: string;
// //   campaignId: string;
// //   prospectId: string;
// //   touchNumber: number;
// //   angle: string;
// //   status: string;
// //   qaScore: number | null;
// //   sentAt: string | null;
// //   openedAt: string | null;
// //   repliedAt: string | null;
// //   bouncedAt: string | null;
// // }

// // interface ProspectLite {
// //   id: string;
// //   intentSource: string;
// // }

// // interface TimeSeriesPoint {
// //   date: string;
// //   sent: number;
// //   opened: number;
// //   replied: number;
// //   bounced: number;
// // }

// // interface DiagnoseLayerResult {
// //   layer: string;
// //   status: "ok" | "warn" | "critical";
// //   metric: string;
// //   value: number;
// //   benchmark: number | null;
// //   note: string;
// // }

// // interface DiagnoseResponse {
// //   campaignId: string | null;
// //   layers: DiagnoseLayerResult[];
// //   summary: string;
// //   generatedAt: string;
// // }

// // interface CampaignResult {
// //   id: string;
// //   campaignId: string;
// //   totalSent: number;
// //   totalReplied: number;
// //   totalPositive: number;
// //   totalBounced: number;
// //   replyRate: number;
// //   positiveReplyRate: number;
// //   bounceRate: number;
// //   whatWorked: string | null;
// //   whatDidntWork: string | null;
// //   nextActions: string | null;
// //   insights: string | null;
// //   generatedAt: string;
// // }

// // interface SystemParamLite {
// //   key: string;
// //   label: string;
// //   value: string;
// //   unit: string | null;
// // }

// // interface UsageBreakdownRow {
// //   event_type: string;
// //   provider: string | null;
// //   total_quantity: number;
// //   total_cost_cents: number;
// //   event_count: number;
// // }

// // interface UsageResponse {
// //   period_start: string;
// //   period_end: string;
// //   breakdown: UsageBreakdownRow[];
// //   total_cost_cents: number;
// // }

// // const DATE_RANGES = [
// //   { label: "Last 7 days", days: 7 },
// //   { label: "Last 14 days", days: 14 },
// //   { label: "Last 30 days", days: 30 },
// //   { label: "Last 60 days", days: 60 },
// //   { label: "Last 90 days", days: 90 },
// // ];

// // const ANGLE_LABELS: Record<string, string> = {
// //   FirstTouch: "First Touch",
// //   NewEvidence: "New Evidence",
// //   DifferentPain: "Different Pain",
// //   IndustryInsight: "Industry Insight",
// //   DirectQuestion: "Direct Question",
// //   Breakup: "Breakup",
// // };

// // const INTENT_LABELS: Record<string, string> = {
// //   FUNDING_URGENCY: "Funding Urgency",
// //   HIRING_BUDGET: "Hiring Budget",
// //   FORUM_PAIN: "Forum Pain Signal",
// //   LINKEDIN_DEMAND: "LinkedIn Demand",
// //   REFERRAL: "Referral",
// //   INBOUND: "Inbound",
// //   OTHER: "Other",
// // };

// // const STATUS_COLORS: Record<string, string> = {
// //   Draft: "#94a3b8",
// //   QaFailed: "#ef4444",
// //   QaPassed: "#22c55e",
// //   Scheduled: "#3b82f6",
// //   Sent: "#8b5cf6",
// //   Replied: "#10b981",
// //   Bounced: "#f97316",
// //   Failed: "#dc2626",
// // };

// // function normaliseList<T>(raw: unknown): T[] {
// //   if (Array.isArray(raw)) return raw as T[];
// //   if (raw && typeof raw === "object" && "items" in raw)
// //     return (raw as { items: T[] }).items ?? [];
// //   return [];
// // }

// // function pct(n: number): string {
// //   return `${(n * 100).toFixed(1)}%`;
// // }

// // /* Page */

// // export function AnalyticsPage() {
// //   const qc = useQueryClient();
// //   const navigate = useNavigate();
// //   const [rangeDays, setRangeDays] = useState(30);
// //   const [insightsOpen, setInsightsOpen] = useState(false);
// //   const [insightsCampaignId, setInsightsCampaignId] = useState<string>("");

// //   const campaignsQ = useQuery({
// //     queryKey: ["campaigns", "for-analytics"],
// //     queryFn: () =>
// //       http.get<unknown>("/api/v1/campaigns").then((r) => normaliseList<Campaign>(r)),
// //   });
// //   const campaigns = campaignsQ.data ?? [];

// //   const metricsQ = useQuery({
// //     queryKey: ["analytics", "metrics", rangeDays],
// //     queryFn: () =>
// //       http
// //         .get<unknown>(`/api/v1/analytics/metrics?days=${rangeDays}`)
// //         .then((r) => normaliseList<CampaignMetricRow>(r)),
// //   });
// //   const metrics = metricsQ.data ?? [];

// //   const timeSeriesQ = useQuery({
// //     queryKey: ["analytics", "time-series", rangeDays],
// //     queryFn: () =>
// //       http.get<{ points: TimeSeriesPoint[] }>(
// //         `/api/v1/analytics/time-series?days=${rangeDays}`,
// //       ),
// //   });
// //   const timeSeries = timeSeriesQ.data?.points ?? [];

// //   const sequencesQ = useQuery({
// //     queryKey: ["sequences", "for-analytics", rangeDays],
// //     queryFn: () =>
// //       http
// //         .get<unknown>(`/api/v1/sequences?limit=500&days=${rangeDays}`)
// //         .then((r) => normaliseList<Sequence>(r)),
// //   });
// //   const sequences = sequencesQ.data ?? [];

// //   const prospectsQ = useQuery({
// //     queryKey: ["prospects", "for-analytics"],
// //     queryFn: () =>
// //       http
// //         .get<unknown>("/api/v1/prospects?limit=500")
// //         .then((r) => normaliseList<ProspectLite>(r)),
// //   });
// //   const prospects = prospectsQ.data ?? [];

// //   const diagnoseQ = useQuery({
// //     queryKey: ["analytics", "diagnose", "tenant"],
// //     queryFn: () =>
// //       http.post<DiagnoseResponse>("/api/v1/analytics/diagnose", {
// //         campaignId: null,
// //       }),
// //   });
// //   const diagnose = diagnoseQ.data;

// //   const benchmarksQ = useQuery({
// //     queryKey: ["system-params", "Analytics Benchmarks"],
// //     queryFn: () =>
// //       http
// //         .get<unknown>(
// //           `/api/v1/system-params?category=${encodeURIComponent("Analytics Benchmarks")}`,
// //         )
// //         .then((r) => normaliseList<SystemParamLite>(r)),
// //   });
// //   const benchmarks = benchmarksQ.data ?? [];

// //   const usageQ = useQuery({
// //     queryKey: ["usage", "tenant"],
// //     queryFn: () => http.get<UsageResponse>("/api/v1/usage/tenant"),
// //   });
// //   const usage = usageQ.data;

// //   const resultQ = useQuery({
// //     queryKey: ["analytics", "campaign-results", insightsCampaignId],
// //     queryFn: () =>
// //       http.get<CampaignResult | null>(
// //         `/api/v1/analytics/campaign-results?campaign_id=${insightsCampaignId}`,
// //       ),
// //     enabled: !!insightsCampaignId && insightsOpen,
// //   });

// //   const generateInsightsMutation = useMutation({
// //     mutationFn: (campaignId: string) =>
// //       http.post<CampaignResult>(
// //         `/api/v1/analytics/campaign-results?campaign_id=${campaignId}`,
// //         {},
// //       ),
// //     onSuccess: () => {
// //       toast.success("Insights generated");
// //       qc.invalidateQueries({ queryKey: ["analytics", "campaign-results"] });
// //     },
// //     onError: () =>
// //       toast.error("Failed to generate insights — this campaign may have no metrics yet"),
// //   });

// //   /* ── AN-2: Campaign Performance table (sum metrics per campaignId) ── */
// //   const campaignPerformance = useMemo(() => {
// //     const byCampaign = new Map<
// //       string,
// //       { sent: number; opened: number; replied: number; bounced: number }
// //     >();
// //     for (const m of metrics) {
// //       const cur = byCampaign.get(m.campaignId) ?? {
// //         sent: 0,
// //         opened: 0,
// //         replied: 0,
// //         bounced: 0,
// //       };
// //       cur.sent += m.totalSent;
// //       cur.opened += m.totalOpened;
// //       cur.replied += m.totalReplied;
// //       cur.bounced += m.totalBounced;
// //       byCampaign.set(m.campaignId, cur);
// //     }
// //     return Array.from(byCampaign.entries())
// //       .map(([campaignId, agg]) => {
// //         const campaign = campaigns.find((c) => c.id === campaignId);
// //         return {
// //           campaignId,
// //           name: campaign?.name ?? campaignId,
// //           status: campaign?.status ?? "unknown",
// //           ...agg,
// //           openRate: agg.sent ? agg.opened / agg.sent : 0,
// //           replyRate: agg.sent ? agg.replied / agg.sent : 0,
// //           bounceRate: agg.sent ? agg.bounced / agg.sent : 0,
// //         };
// //       })
// //       .sort((a, b) => b.sent - a.sent);
// //   }, [metrics, campaigns]);

// //   /* ── AN-1: Sequence Status Distribution ── */
// //   const statusDistribution = useMemo(() => {
// //     const counts = new Map<string, number>();
// //     for (const s of sequences) counts.set(s.status, (counts.get(s.status) ?? 0) + 1);
// //     return Array.from(counts.entries()).map(([status, count]) => ({
// //       status,
// //       count,
// //       fill: STATUS_COLORS[status] ?? "#94a3b8",
// //     }));
// //   }, [sequences]);

// //   /* ── AN-3: Sequence Step Performance (touch 1-7) ── */
// //   const stepPerformance = useMemo(() => {
// //     const byTouch = new Map<
// //       number,
// //       { sent: number; opened: number; replied: number }
// //     >();
// //     for (const s of sequences) {
// //       const cur = byTouch.get(s.touchNumber) ?? { sent: 0, opened: 0, replied: 0 };
// //       if (s.sentAt) cur.sent += 1;
// //       if (s.openedAt) cur.opened += 1;
// //       if (s.repliedAt) cur.replied += 1;
// //       byTouch.set(s.touchNumber, cur);
// //     }
// //     return Array.from(byTouch.entries())
// //       .sort(([a], [b]) => a - b)
// //       .map(([touch, agg]) => ({
// //         touch: `T${touch}`,
// //         openRate: agg.sent ? Math.round((agg.opened / agg.sent) * 1000) / 10 : 0,
// //         replyRate: agg.sent ? Math.round((agg.replied / agg.sent) * 1000) / 10 : 0,
// //         sent: agg.sent,
// //       }));
// //   }, [sequences]);

// //   /* ── AN-5: Copy Angle Performance ── */
// //   const anglePerformance = useMemo(() => {
// //     const byAngle = new Map<
// //       string,
// //       { sent: number; opened: number; replied: number }
// //     >();
// //     for (const s of sequences) {
// //       const cur = byAngle.get(s.angle) ?? { sent: 0, opened: 0, replied: 0 };
// //       if (s.sentAt) cur.sent += 1;
// //       if (s.openedAt) cur.opened += 1;
// //       if (s.repliedAt) cur.replied += 1;
// //       byAngle.set(s.angle, cur);
// //     }
// //     return Array.from(byAngle.entries())
// //       .map(([angle, agg]) => ({
// //         angle: ANGLE_LABELS[angle] ?? angle,
// //         replyRate: agg.sent ? Math.round((agg.replied / agg.sent) * 1000) / 10 : 0,
// //         sent: agg.sent,
// //       }))
// //       .sort((a, b) => b.replyRate - a.replyRate);
// //   }, [sequences]);

// //   /* ── AN-4: Intent Source Attribution (real Prospect.intentSource) ── */
// //   const intentAttribution = useMemo(() => {
// //     const repliedProspectIds = new Set(
// //       sequences.filter((s) => s.repliedAt).map((s) => s.prospectId),
// //     );
// //     const bySource = new Map<string, { total: number; replied: number }>();
// //     for (const p of prospects) {
// //       const cur = bySource.get(p.intentSource) ?? { total: 0, replied: 0 };
// //       cur.total += 1;
// //       if (repliedProspectIds.has(p.id)) cur.replied += 1;
// //       bySource.set(p.intentSource, cur);
// //     }
// //     return Array.from(bySource.entries())
// //       .map(([source, agg]) => ({
// //         source: INTENT_LABELS[source] ?? source,
// //         total: agg.total,
// //         replied: agg.replied,
// //         contributionRate: agg.total ? Math.round((agg.replied / agg.total) * 1000) / 10 : 0,
// //       }))
// //       .sort((a, b) => b.replied - a.replied);
// //   }, [sequences, prospects]);

// //   /* ── AN-7: QA Score Distribution ── */
// //   const qaDistribution = useMemo(() => {
// //     const buckets = [
// //       { label: "0-59", min: 0, max: 59, count: 0 },
// //       { label: "60-69", min: 60, max: 69, count: 0 },
// //       { label: "70-79", min: 70, max: 79, count: 0 },
// //       { label: "80-89", min: 80, max: 89, count: 0 },
// //       { label: "90-100", min: 90, max: 100, count: 0 },
// //     ];
// //     for (const s of sequences) {
// //       if (s.qaScore == null) continue;
// //       const bucket = buckets.find((b) => s.qaScore! >= b.min && s.qaScore! <= b.max);
// //       if (bucket) bucket.count += 1;
// //     }
// //     return buckets;
// //   }, [sequences]);

// //   const scoredCount = sequences.filter((s) => s.qaScore != null).length;
// //   const avgQaScore = scoredCount
// //     ? Math.round(
// //         sequences.reduce((sum, s) => sum + (s.qaScore ?? 0), 0) / scoredCount,
// //       )
// //     : null;

// //   const isLoading =
// //     campaignsQ.isLoading || metricsQ.isLoading || sequencesQ.isLoading;

// //   return (
// //     <div className="space-y-6 p-6">
// //       <PageHeader
// //         title="Analytics"
// //         description="Campaign performance, health diagnostics, and statistical breakdowns across your outreach."
// //         actions={
// //           <div className="flex items-center gap-2">
// //             <Select
// //               value={String(rangeDays)}
// //               onChange={(e) => setRangeDays(Number(e.target.value))}
// //               className="w-40"
// //             >
// //               {DATE_RANGES.map((r) => (
// //                 <option key={r.days} value={r.days}>
// //                   {r.label}
// //                 </option>
// //               ))}
// //             </Select>
// //             <Dialog open={insightsOpen} onOpenChange={setInsightsOpen}>
// //               <DialogTrigger asChild>
// //                 <Button variant="outline" onClick={() => setInsightsOpen(true)}>
// //                   <Sparkles className="h-4 w-4 mr-2" />
// //                   AI Insights
// //                 </Button>
// //               </DialogTrigger>
// //               <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
// //                 <DialogHeader>
// //                   <DialogTitle>Generate Campaign Insights</DialogTitle>
// //                   <DialogDescription>
// //                     Select a campaign to generate an AI-written post-mortem:
// //                     what worked, what didn't, and next actions.
// //                   </DialogDescription>
// //                 </DialogHeader>
// //                 <div className="space-y-4">
// //                   <Select
// //                     value={insightsCampaignId}
// //                     onChange={(e) => setInsightsCampaignId(e.target.value)}
// //                   >
// //                     <option value="">Select a campaign…</option>
// //                     {campaigns.map((c) => (
// //                       <option key={c.id} value={c.id}>
// //                         {c.name}
// //                       </option>
// //                     ))}
// //                   </Select>

// //                   {insightsCampaignId && resultQ.isLoading && (
// //                     <Skeleton className="h-32 w-full" />
// //                   )}

// //                   {insightsCampaignId && !resultQ.isLoading && !resultQ.data && (
// //                     <div className="text-center py-6 text-sm text-muted-foreground">
// //                       No insights generated yet for this campaign.
// //                     </div>
// //                   )}

// //                   {resultQ.data && (
// //                     <div className="space-y-3 text-sm">
// //                       <div className="grid grid-cols-3 gap-3">
// //                         <div className="rounded-md border p-2 text-center">
// //                           <p className="text-lg font-bold">{resultQ.data.totalSent}</p>
// //                           <p className="text-xs text-muted-foreground">Sent</p>
// //                         </div>
// //                         <div className="rounded-md border p-2 text-center">
// //                           <p className="text-lg font-bold">{pct(resultQ.data.replyRate)}</p>
// //                           <p className="text-xs text-muted-foreground">Reply rate</p>
// //                         </div>
// //                         <div className="rounded-md border p-2 text-center">
// //                           <p className="text-lg font-bold">
// //                             {pct(resultQ.data.positiveReplyRate)}
// //                           </p>
// //                           <p className="text-xs text-muted-foreground">Positive rate</p>
// //                         </div>
// //                       </div>
// //                       {resultQ.data.whatWorked && (
// //                         <div>
// //                           <p className="font-medium text-xs mb-1">What worked</p>
// //                           <p className="text-muted-foreground">{resultQ.data.whatWorked}</p>
// //                         </div>
// //                       )}
// //                       {resultQ.data.whatDidntWork && (
// //                         <div>
// //                           <p className="font-medium text-xs mb-1">What didn't work</p>
// //                           <p className="text-muted-foreground">
// //                             {resultQ.data.whatDidntWork}
// //                           </p>
// //                         </div>
// //                       )}
// //                       {resultQ.data.nextActions && (
// //                         <div>
// //                           <p className="font-medium text-xs mb-1">Next actions</p>
// //                           <p className="text-muted-foreground">{resultQ.data.nextActions}</p>
// //                         </div>
// //                       )}
// //                       {resultQ.data.insights && (
// //                         <div>
// //                           <p className="font-medium text-xs mb-1">Insights</p>
// //                           <p className="text-muted-foreground">{resultQ.data.insights}</p>
// //                         </div>
// //                       )}
// //                       <p className="text-[10px] text-muted-foreground">
// //                         Generated {new Date(resultQ.data.generatedAt).toLocaleString()}
// //                       </p>
// //                     </div>
// //                   )}
// //                 </div>
// //                 <DialogFooter>
// //                   <Button
// //                     variant="outline"
// //                     onClick={() => {
// //                       setInsightsOpen(false);
// //                       setInsightsCampaignId("");
// //                     }}
// //                   >
// //                     Close
// //                   </Button>
// //                   <Button
// //                     onClick={() =>
// //                       insightsCampaignId &&
// //                       generateInsightsMutation.mutate(insightsCampaignId)
// //                     }
// //                     disabled={!insightsCampaignId || generateInsightsMutation.isPending}
// //                   >
// //                     {generateInsightsMutation.isPending ? (
// //                       <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
// //                     ) : (
// //                       <Sparkles className="h-3.5 w-3.5 mr-1.5" />
// //                     )}
// //                     Generate Insights
// //                   </Button>
// //                 </DialogFooter>
// //               </DialogContent>
// //             </Dialog>
// //           </div>
// //         }
// //       />

// //       {isLoading ? (
// //         <div className="space-y-3">
// //           {[0, 1, 2].map((i) => (
// //             <Skeleton key={i} className="h-32 w-full" />
// //           ))}
// //         </div>
// //       ) : (
// //         <>
// //           {/* Time series (AN-12 date range) */}
// //           <Card>
// //             <CardHeader>
// //               <CardTitle className="text-base">Activity Over Time</CardTitle>
// //               <CardDescription>
// //                 Sent, opened, replied, and bounced counts for the selected range.
// //               </CardDescription>
// //             </CardHeader>
// //             <CardContent>
// //               {timeSeriesQ.isLoading ? (
// //                 <Skeleton className="h-64 w-full" />
// //               ) : (
// //                 <ResponsiveContainer width="100%" height={260}>
// //                   <LineChart data={timeSeries}>
// //                     <CartesianGrid strokeDasharray="3 3" />
// //                     <XAxis dataKey="date" tick={{ fontSize: 11 }} />
// //                     <YAxis tick={{ fontSize: 11 }} />
// //                     <RTooltip />
// //                     <Legend />
// //                     <Line type="monotone" dataKey="sent" stroke="#8b5cf6" strokeWidth={2} />
// //                     <Line type="monotone" dataKey="opened" stroke="#3b82f6" strokeWidth={2} />
// //                     <Line type="monotone" dataKey="replied" stroke="#10b981" strokeWidth={2} />
// //                     <Line type="monotone" dataKey="bounced" stroke="#f97316" strokeWidth={2} />
// //                   </LineChart>
// //                 </ResponsiveContainer>
// //               )}
// //             </CardContent>
// //           </Card>

// //           {/* AN-2: Campaign Performance table */}
// //           <Card>
// //             <CardHeader>
// //               <CardTitle className="text-base flex items-center gap-2">
// //                 <BarChart3 className="h-4 w-4" /> Campaign Performance
// //               </CardTitle>
// //               <CardDescription>
// //                 Aggregated send/open/reply/bounce metrics per campaign.
// //               </CardDescription>
// //             </CardHeader>
// //             <CardContent>
// //               {campaignPerformance.length === 0 ? (
// //                 <p className="text-sm text-muted-foreground py-6 text-center">
// //                   No campaign metrics yet — metrics populate once sequences start sending.
// //                 </p>
// //               ) : (
// //                 <Table>
// //                   <TableHeader>
// //                     <TableRow>
// //                       <TableHead>Campaign</TableHead>
// //                       <TableHead>Status</TableHead>
// //                       <TableHead className="text-right">Sent</TableHead>
// //                       <TableHead className="text-right">Opened</TableHead>
// //                       <TableHead className="text-right">Replied</TableHead>
// //                       <TableHead className="text-right">Bounced</TableHead>
// //                       <TableHead className="text-right">Open Rate</TableHead>
// //                       <TableHead className="text-right">Reply Rate</TableHead>
// //                     </TableRow>
// //                   </TableHeader>
// //                   <TableBody>
// //                     {campaignPerformance.map((c) => (
// //                       <TableRow key={c.campaignId}>
// //                         <TableCell className="font-medium">{c.name}</TableCell>
// //                         <TableCell>
// //                           <Badge variant="outline" className="text-[10px]">
// //                             {c.status}
// //                           </Badge>
// //                         </TableCell>
// //                         <TableCell className="text-right tabular-nums">{c.sent}</TableCell>
// //                         <TableCell className="text-right tabular-nums">{c.opened}</TableCell>
// //                         <TableCell className="text-right tabular-nums">{c.replied}</TableCell>
// //                         <TableCell className="text-right tabular-nums">{c.bounced}</TableCell>
// //                         <TableCell className="text-right tabular-nums">
// //                           {pct(c.openRate)}
// //                         </TableCell>
// //                         <TableCell className="text-right tabular-nums">
// //                           {pct(c.replyRate)}
// //                         </TableCell>
// //                       </TableRow>
// //                     ))}
// //                   </TableBody>
// //                 </Table>
// //               )}
// //             </CardContent>
// //           </Card>

// //           <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
// //             {/* AN-1: Sequence Status Distribution */}
// //             <Card>
// //               <CardHeader>
// //                 <CardTitle className="text-base">Sequence Status Distribution</CardTitle>
// //                 <CardDescription className="text-xs">
// //                   Current status of all sequenced touches.
// //                 </CardDescription>
// //               </CardHeader>
// //               <CardContent>
// //                 {statusDistribution.length === 0 ? (
// //                   <p className="text-sm text-muted-foreground py-6 text-center">
// //                     No sequences yet.
// //                   </p>
// //                 ) : (
// //                   <ResponsiveContainer width="100%" height={240}>
// //                     <PieChart>
// //                       <Pie
// //                         data={statusDistribution}
// //                         dataKey="count"
// //                         nameKey="status"
// //                         cx="50%"
// //                         cy="50%"
// //                         outerRadius={80}
// //                         label={(entry: { status: string }) => entry.status}
// //                       >
// //                         {statusDistribution.map((entry) => (
// //                           <Cell key={entry.status} fill={entry.fill} />
// //                         ))}
// //                       </Pie>
// //                       <RTooltip />
// //                     </PieChart>
// //                   </ResponsiveContainer>
// //                 )}
// //               </CardContent>
// //             </Card>

// //             {/* AN-3: Sequence Step Performance */}
// //             <Card>
// //               <CardHeader>
// //                 <CardTitle className="text-base">Sequence Step Performance</CardTitle>
// //                 <CardDescription className="text-xs">
// //                   Open and reply rate by touch number (T1-T7).
// //                 </CardDescription>
// //               </CardHeader>
// //               <CardContent>
// //                 {stepPerformance.length === 0 ? (
// //                   <p className="text-sm text-muted-foreground py-6 text-center">
// //                     No sent touches yet.
// //                   </p>
// //                 ) : (
// //                   <ResponsiveContainer width="100%" height={240}>
// //                     <BarChart data={stepPerformance}>
// //                       <CartesianGrid strokeDasharray="3 3" />
// //                       <XAxis dataKey="touch" tick={{ fontSize: 11 }} />
// //                       <YAxis tick={{ fontSize: 11 }} unit="%" />
// //                       <RTooltip />
// //                       <Legend />
// //                       <Bar dataKey="openRate" name="Open %" fill="#3b82f6" />
// //                       <Bar dataKey="replyRate" name="Reply %" fill="#10b981" />
// //                     </BarChart>
// //                   </ResponsiveContainer>
// //                 )}
// //               </CardContent>
// //             </Card>

// //             {/* AN-5: Copy Angle Performance */}
// //             <Card>
// //               <CardHeader>
// //                 <CardTitle className="text-base">Copy Angle Performance</CardTitle>
// //                 <CardDescription className="text-xs">
// //                   Reply rate by messaging angle, best first.
// //                 </CardDescription>
// //               </CardHeader>
// //               <CardContent>
// //                 {anglePerformance.length === 0 ? (
// //                   <p className="text-sm text-muted-foreground py-6 text-center">
// //                     No sent touches yet.
// //                   </p>
// //                 ) : (
// //                   <ResponsiveContainer width="100%" height={240}>
// //                     <BarChart data={anglePerformance} layout="vertical">
// //                       <CartesianGrid strokeDasharray="3 3" />
// //                       <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
// //                       <YAxis
// //                         type="category"
// //                         dataKey="angle"
// //                         tick={{ fontSize: 11 }}
// //                         width={110}
// //                       />
// //                       <RTooltip />
// //                       <Bar dataKey="replyRate" name="Reply %" fill="#8b5cf6" />
// //                     </BarChart>
// //                   </ResponsiveContainer>
// //                 )}
// //               </CardContent>
// //             </Card>

// //             {/* AN-4: Intent Source Attribution */}
// //             <Card>
// //               <CardHeader>
// //                 <CardTitle className="text-base">Intent Source Attribution</CardTitle>
// //                 <CardDescription className="text-xs">
// //                   Prospect count and reply contribution by buying-intent
// //                   source (Prospect.intentSource).
// //                 </CardDescription>
// //               </CardHeader>
// //               <CardContent>
// //                 {intentAttribution.length === 0 ? (
// //                   <p className="text-sm text-muted-foreground py-6 text-center">
// //                     No prospects yet.
// //                   </p>
// //                 ) : (
// //                   <ResponsiveContainer width="100%" height={240}>
// //                     <BarChart data={intentAttribution} layout="vertical">
// //                       <CartesianGrid strokeDasharray="3 3" />
// //                       <XAxis type="number" tick={{ fontSize: 11 }} />
// //                       <YAxis
// //                         type="category"
// //                         dataKey="source"
// //                         tick={{ fontSize: 11 }}
// //                         width={110}
// //                       />
// //                       <RTooltip />
// //                       <Legend />
// //                       <Bar dataKey="total" name="Prospects" fill="#94a3b8" />
// //                       <Bar dataKey="replied" name="Replied" fill="#10b981" />
// //                     </BarChart>
// //                   </ResponsiveContainer>
// //                 )}
// //               </CardContent>
// //             </Card>
// //           </div>

// //           {/* AN-6: Campaign Health Diagnostics */}
// //           <Card>
// //             <CardHeader>
// //               <CardTitle className="text-base flex items-center gap-2">
// //                 <Activity className="h-4 w-4" /> Campaign Health Diagnostics
// //               </CardTitle>
// //               <CardDescription>
// //                 5-layer closed-loop diagnostic across all active campaigns.
// //               </CardDescription>
// //             </CardHeader>
// //             <CardContent>
// //               {diagnoseQ.isLoading ? (
// //                 <Skeleton className="h-32 w-full" />
// //               ) : diagnose ? (
// //                 <div className="space-y-3">
// //                   <p className="text-sm text-muted-foreground">{diagnose.summary}</p>
// //                   <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2">
// //                     {diagnose.layers.map((l) => (
// //                       <div
// //                         key={l.layer}
// //                         className={`rounded-md border p-2.5 text-xs ${
// //                           l.status === "critical"
// //                             ? "border-red-300 bg-red-50"
// //                             : l.status === "warn"
// //                               ? "border-amber-300 bg-amber-50"
// //                               : "border-emerald-200 bg-emerald-50"
// //                         }`}
// //                       >
// //                         <div className="flex items-center justify-between mb-1">
// //                           <span className="font-medium capitalize">{l.layer}</span>
// //                           {l.status === "critical" ? (
// //                             <AlertTriangle className="h-3.5 w-3.5 text-red-600" />
// //                           ) : l.status === "warn" ? (
// //                             <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
// //                           ) : (
// //                             <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
// //                           )}
// //                         </div>
// //                         <p className="tabular-nums font-mono">
// //                           {l.metric}: {l.value}
// //                           {l.benchmark != null && (
// //                             <span className="text-muted-foreground"> / {l.benchmark}</span>
// //                           )}
// //                         </p>
// //                         <p className="text-muted-foreground mt-1">{l.note}</p>
// //                       </div>
// //                     ))}
// //                   </div>
// //                 </div>
// //               ) : (
// //                 <p className="text-sm text-muted-foreground py-6 text-center">
// //                   No diagnostic data available yet.
// //                 </p>
// //               )}
// //             </CardContent>
// //           </Card>

// //           <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
// //             {/* AN-7: AI Performance Diagnostics */}
// //             <Card>
// //               <CardHeader>
// //                 <CardTitle className="text-base flex items-center gap-2">
// //                   <Bot className="h-4 w-4" /> AI Performance
// //                 </CardTitle>
// //                 <CardDescription className="text-xs">
// //                   LLM usage/cost this period and QA score distribution.
// //                   (Generation-time tracking isn't recorded by the backend.)
// //                 </CardDescription>
// //               </CardHeader>
// //               <CardContent className="space-y-4">
// //                 {usageQ.isLoading ? (
// //                   <Skeleton className="h-24 w-full" />
// //                 ) : usage && usage.breakdown.length > 0 ? (
// //                   <div className="space-y-1.5">
// //                     {usage.breakdown.map((row) => (
// //                       <div
// //                         key={`${row.event_type}-${row.provider}`}
// //                         className="flex items-center justify-between text-xs bg-muted/50 rounded px-2 py-1.5"
// //                       >
// //                         <span>
// //                           {row.event_type}
// //                           {row.provider ? ` · ${row.provider}` : ""}
// //                         </span>
// //                         <span className="tabular-nums text-muted-foreground">
// //                           {row.event_count} calls · ${(row.total_cost_cents / 100).toFixed(2)}
// //                         </span>
// //                       </div>
// //                     ))}
// //                     <p className="text-xs font-medium pt-1">
// //                       Total: ${(usage.total_cost_cents / 100).toFixed(2)}
// //                     </p>
// //                   </div>
// //                 ) : (
// //                   <p className="text-xs text-muted-foreground">No usage recorded this period.</p>
// //                 )}

// //                 <div>
// //                   <p className="text-xs font-medium mb-2">
// //                     QA Score Distribution
// //                     {avgQaScore != null && (
// //                       <span className="text-muted-foreground"> · avg {avgQaScore}</span>
// //                     )}
// //                   </p>
// //                   {scoredCount === 0 ? (
// //                     <p className="text-xs text-muted-foreground">No QA-scored emails yet.</p>
// //                   ) : (
// //                     <ResponsiveContainer width="100%" height={140}>
// //                       <BarChart data={qaDistribution}>
// //                         <XAxis dataKey="label" tick={{ fontSize: 10 }} />
// //                         <YAxis tick={{ fontSize: 10 }} />
// //                         <RTooltip />
// //                         <Bar dataKey="count" fill="#3b82f6" />
// //                       </BarChart>
// //                     </ResponsiveContainer>
// //                   )}
// //                 </div>
// //               </CardContent>
// //             </Card>

// //             {/* AN-8: Industry Benchmarks */}
// //             <Card>
// //               <CardHeader>
// //                 <CardTitle className="text-base flex items-center gap-2">
// //                   <Target className="h-4 w-4" /> Benchmarks
// //                 </CardTitle>
// //                 <CardDescription className="text-xs">
// //                   Your configured health-diagnostic thresholds (System
// //                   Parameters → Analytics Benchmarks).
// //                 </CardDescription>
// //               </CardHeader>
// //               <CardContent>
// //                 {benchmarksQ.isLoading ? (
// //                   <Skeleton className="h-24 w-full" />
// //                 ) : benchmarks.length === 0 ? (
// //                   <p className="text-xs text-muted-foreground py-4 text-center">
// //                     No benchmark parameters configured.
// //                   </p>
// //                 ) : (
// //                   <div className="grid grid-cols-2 gap-2">
// //                     {benchmarks.map((b) => (
// //                       <div key={b.key} className="rounded-md border p-2 text-center">
// //                         <p className="text-lg font-bold">
// //                           {b.value}
// //                           {b.unit?.includes("%") ? "" : ""}
// //                         </p>
// //                         <p className="text-[10px] text-muted-foreground">{b.label}</p>
// //                       </div>
// //                     ))}
// //                   </div>
// //                 )}
// //                 <Button
// //                   variant="ghost"
// //                   size="sm"
// //                   className="mt-3 w-full"
// //                   onClick={() => navigate("/setup/system-params")}
// //                 >
// //                   Adjust benchmarks in System Parameters
// //                   <ExternalLink className="h-3 w-3 ml-1.5" />
// //                 </Button>
// //               </CardContent>
// //             </Card>
// //           </div>

// //           {/* AN-9 / AN-11: Auto-Optimization link-out */}
// //           <Card className="border-violet-200 bg-violet-50/50">
// //             <CardContent className="py-4 flex items-center justify-between gap-4">
// //               <div className="flex items-center gap-3">
// //                 <TrendingUp className="h-5 w-5 text-violet-600 shrink-0" />
// //                 <div>
// //                   <p className="text-sm font-medium">Auto-Optimization Rules Engine</p>
// //                   <p className="text-xs text-muted-foreground">
// //                     Create rules like "if reply rate &lt; 5% for 3+ days, pause
// //                     campaign" — managed on its own page with full create/edit/delete.
// //                   </p>
// //                 </div>
// //               </div>
// //               <Button
// //                 variant="outline"
// //                 size="sm"
// //                 className="shrink-0"
// //                 onClick={() => navigate("/optimize/optimization-rules")}
// //               >
// //                 Open Optimization Rules
// //                 <ExternalLink className="h-3 w-3 ml-1.5" />
// //               </Button>
// //             </CardContent>
// //           </Card>

// //           <Card className="p-4 bg-muted/30 border-dashed">
// //             <div className="flex gap-3">
// //               <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
// //               <p className="text-xs text-muted-foreground">
// //                 Campaign Performance and the time-series chart reflect data
// //                 across all campaigns for the selected range. Sequence-derived
// //                 charts (status, step, angle, intent) are computed from the
// //                 most recent 500 sequences and 500 prospects.
// //               </p>
// //             </div>
// //           </Card>
// //         </>
// //       )}
// //     </div>
// //   );
// // }

// /**
//  * AnalyticsPage.tsx - campaign performance, health diagnostics, and
//  * statistical breakdowns across sequences, prospects, and LLM usage.
//  *
//  * API (verified against real routers/schemas - see comments per section):
//  *   GET  /api/v1/analytics/metrics?campaign_id=        -> CampaignMetricResponse[] (per campaign+date)
//  *   GET  /api/v1/analytics/time-series?days=N          -> TimeSeriesResponse
//  *   POST /api/v1/analytics/diagnose                     { campaignId } -> DiagnoseResponse
//  *   GET  /api/v1/analytics/campaign-results?campaign_id= -> CampaignResultResponse | null
//  *   POST /api/v1/analytics/campaign-results?campaign_id= -> CampaignResultResponse (generates)
//  *   GET  /api/v1/campaigns                               -> CampaignResponse[] (for names + selector)
//  *   GET  /api/v1/sequences?limit=500                      -> SequenceResponse[] (touchNumber, angle, status, timestamps)
//  *   GET  /api/v1/prospects?limit=500                      -> Prospect[] (intentSource)
//  *   GET  /api/v1/system-params?category=Analytics%20Benchmarks -> SystemParamResponse[]
//  *   GET  /api/v1/usage/tenant?period=YYYY-MM               -> UsageResponse (LLM cost/event breakdown)
//  *
//  * CORRECTIONS vs. the previous version: the old page had a completely wrong
//  * response shape for /analytics/metrics (treated it as one aggregated
//  * object; it's actually an array of per-campaign-per-date rows), called
//  * /analytics/time-series with a campaignId param it doesn't accept (it's
//  * tenant-wide, only takes `days`), and fell back to MOCK_METRICS /
//  * MOCK_TIMESERIES / MOCK_DIAGNOSE / MOCK_RESULTS / MOCK_CAMPAIGNS whenever
//  * a real call returned anything falsy. All mock fallbacks removed.
//  *
//  * Backend gaps documented rather than faked:
//  *   - AN-4 "Intent Source Attribution" is built from Prospect.intentSource
//  *     (FUNDING_URGENCY/HIRING_BUDGET/FORUM_PAIN/LINKEDIN_DEMAND/REFERRAL/
//  *     INBOUND/OTHER) - the real backend field. There is no field tracking
//  *     which *sourcing platform* (Apollo/LinkedIn/manual/CSV) found a
//  *     prospect, so that specific breakdown the gap doc describes isn't
//  *     buildable from real data; intentSource is the closest real analogue
//  *     and is labeled accurately as such.
//  *   - AN-7 "avg generation time" has no backend field anywhere (LLM calls
//  *     aren't timed) - omitted rather than fabricated. LLM usage/cost and
//  *     QA score distribution (both real) are shown instead.
//  *   - AN-9/AN-11 (Auto-Optimization Rules) already live on a separate,
//  *     fully-built OptimizationRulesPage per the gap audit - this page
//  *     links out to it instead of duplicating its CRUD.
//  *
//  * AN-1  Sequence Status Distribution (donut, from /sequences grouped by status)
//  * AN-2  Campaign Performance table (from /analytics/metrics, summed per campaign)
//  * AN-3  Sequence Step Performance (bar, from /sequences grouped by touchNumber)
//  * AN-4  Intent Source Attribution (bar, from /prospects.intentSource + reply join)
//  * AN-5  Copy Angle Performance (bar, from /sequences grouped by angle)
//  * AN-6  Campaign Health Diagnostics (from /analytics/diagnose)
//  * AN-7  AI Performance Diagnostics (usage/tenant + QA score histogram)
//  * AN-8  Industry Benchmarks (from /system-params?category=Analytics Benchmarks)
//  * AN-9  Auto-Optimization summary + link to OptimizationRulesPage
//  * AN-10 Generate Insights dialog (POST /analytics/campaign-results)
//  * AN-11 link to OptimizationRulesPage (already implemented there)
//  * AN-12 Date range filter (7/14/30/60/90 days) driving time-series + metrics
//  */
// import { useMemo, useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   Activity,
//   AlertTriangle,
//   BarChart3,
//   Bot,
//   CheckCircle2,
//   ExternalLink,
//   Info,
//   Loader2,
//   Sparkles,
//   Target,
//   TrendingUp,
// } from "lucide-react";
// import { toast } from "sonner";
// import {
//   Bar,
//   BarChart,
//   CartesianGrid,
//   Cell,
//   Legend,
//   Line,
//   LineChart,
//   Pie,
//   PieChart,
//   ResponsiveContainer,
//   Tooltip as RTooltip,
//   XAxis,
//   YAxis,
// } from "recharts";
// import { useNavigate } from "react-router-dom";

// import { http } from "@/services/apiClient";
// import { PageHeader } from "@/components/ui/page-header";
// import { Button } from "@/components/ui/button";
// import {
//   Card,
//   CardContent,
//   CardDescription,
//   CardHeader,
//   CardTitle,
// } from "@/components/ui/card";
// import { Badge } from "@/components/ui/badge";
// import { NativeSelect as Select } from "@/components/ui/select";
// import { Skeleton } from "@/components/ui/skeleton";
// import {
//   Table,
//   TableBody,
//   TableCell,
//   TableHead,
//   TableHeader,
//   TableRow,
// } from "@/components/ui/table";
// import {
//   Dialog,
//   DialogContent,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
//   DialogTrigger,
// } from "@/components/ui/dialog";

// /* Types (aligned with real backend schemas) */

// interface CampaignMetricRow {
//   id: string;
//   campaignId: string;
//   date: string;
//   totalSent: number;
//   totalOpened: number;
//   totalReplied: number;
//   totalBounced: number;
//   openRate: number;
//   replyRate: number;
//   bounceRate: number;
//   diagnosticNote: string | null;
// }

// interface Campaign {
//   id: string;
//   name: string;
//   status: string;
// }

// interface Sequence {
//   id: string;
//   campaignId: string;
//   prospectId: string;
//   touchNumber: number;
//   angle: string;
//   status: string;
//   qaScore: number | null;
//   sentAt: string | null;
//   openedAt: string | null;
//   repliedAt: string | null;
//   bouncedAt: string | null;
// }

// interface ProspectLite {
//   id: string;
//   intentSource: string;
// }

// interface TimeSeriesPoint {
//   date: string;
//   sent: number;
//   opened: number;
//   replied: number;
//   bounced: number;
// }

// interface DiagnoseLayerResult {
//   layer: string;
//   status: "ok" | "warn" | "critical";
//   metric: string;
//   value: number;
//   benchmark: number | null;
//   note: string;
// }

// interface DiagnoseResponse {
//   campaignId: string | null;
//   layers: DiagnoseLayerResult[];
//   summary: string;
//   generatedAt: string;
// }

// interface CampaignResult {
//   id: string;
//   campaignId: string;
//   totalSent: number;
//   totalReplied: number;
//   totalPositive: number;
//   totalBounced: number;
//   replyRate: number;
//   positiveReplyRate: number;
//   bounceRate: number;
//   whatWorked: string | null;
//   whatDidntWork: string | null;
//   nextActions: string | null;
//   insights: string | null;
//   generatedAt: string;
// }

// interface SystemParamLite {
//   key: string;
//   label: string;
//   value: string;
//   unit: string | null;
// }

// interface UsageBreakdownRow {
//   event_type: string;
//   provider: string | null;
//   total_quantity: number;
//   total_cost_cents: number;
//   event_count: number;
// }

// interface UsageResponse {
//   period_start: string;
//   period_end: string;
//   breakdown: UsageBreakdownRow[];
//   total_cost_cents: number;
// }

// const DATE_RANGES = [
//   { label: "Last 7 days", days: 7 },
//   { label: "Last 14 days", days: 14 },
//   { label: "Last 30 days", days: 30 },
//   { label: "Last 60 days", days: 60 },
//   { label: "Last 90 days", days: 90 },
// ];

// const ANGLE_LABELS: Record<string, string> = {
//   FirstTouch: "First Touch",
//   NewEvidence: "New Evidence",
//   DifferentPain: "Different Pain",
//   IndustryInsight: "Industry Insight",
//   DirectQuestion: "Direct Question",
//   Breakup: "Breakup",
// };

// const INTENT_LABELS: Record<string, string> = {
//   FUNDING_URGENCY: "Funding Urgency",
//   HIRING_BUDGET: "Hiring Budget",
//   FORUM_PAIN: "Forum Pain Signal",
//   LINKEDIN_DEMAND: "LinkedIn Demand",
//   REFERRAL: "Referral",
//   INBOUND: "Inbound",
//   OTHER: "Other",
// };

// const STATUS_COLORS: Record<string, string> = {
//   Draft: "#94a3b8",
//   QaFailed: "#ef4444",
//   QaPassed: "#22c55e",
//   Scheduled: "#3b82f6",
//   Sent: "#8b5cf6",
//   Replied: "#10b981",
//   Bounced: "#f97316",
//   Failed: "#dc2626",
// };

// function normaliseList<T>(raw: unknown): T[] {
//   if (Array.isArray(raw)) return raw as T[];
//   if (raw && typeof raw === "object" && "items" in raw)
//     return (raw as { items: T[] }).items ?? [];
//   return [];
// }

// function pct(n: number): string {
//   return `${(n * 100).toFixed(1)}%`;
// }

// /* Page */

// export function AnalyticsPage() {
//   const qc = useQueryClient();
//   const navigate = useNavigate();
//   const [rangeDays, setRangeDays] = useState(30);
//   const [insightsOpen, setInsightsOpen] = useState(false);
//   const [insightsCampaignId, setInsightsCampaignId] = useState<string>("");

//   const campaignsQ = useQuery({
//     queryKey: ["campaigns", "for-analytics"],
//     queryFn: () =>
//       http.get<unknown>("/api/v1/campaigns").then((r) => normaliseList<Campaign>(r)),
//   });
//   const campaigns = campaignsQ.data ?? [];

//   const metricsQ = useQuery({
//     queryKey: ["analytics", "metrics", rangeDays],
//     queryFn: () =>
//       http
//         .get<unknown>(`/api/v1/analytics/metrics?days=${rangeDays}`)
//         .then((r) => normaliseList<CampaignMetricRow>(r)),
//   });
//   const metrics = metricsQ.data ?? [];

//   const timeSeriesQ = useQuery({
//     queryKey: ["analytics", "time-series", rangeDays],
//     queryFn: () =>
//       http.get<{ points: TimeSeriesPoint[] }>(
//         `/api/v1/analytics/time-series?days=${rangeDays}`,
//       ),
//   });
//   const timeSeries = timeSeriesQ.data?.points ?? [];

//   const sequencesQ = useQuery({
//     queryKey: ["sequences", "for-analytics", rangeDays],
//     queryFn: () =>
//       http
//         .get<unknown>(`/api/v1/sequences?limit=500&days=${rangeDays}`)
//         .then((r) => normaliseList<Sequence>(r)),
//   });
//   const sequences = sequencesQ.data ?? [];

//   const prospectsQ = useQuery({
//     queryKey: ["prospects", "for-analytics"],
//     queryFn: () =>
//       http
//         .get<unknown>("/api/v1/prospects?limit=500")
//         .then((r) => normaliseList<ProspectLite>(r)),
//   });
//   const prospects = prospectsQ.data ?? [];

//   const diagnoseQ = useQuery({
//     queryKey: ["analytics", "diagnose", "tenant"],
//     queryFn: () =>
//       http.post<DiagnoseResponse>("/api/v1/analytics/diagnose", {
//         campaignId: null,
//       }),
//   });
//   const diagnose = diagnoseQ.data;

//   const benchmarksQ = useQuery({
//     queryKey: ["system-params", "Analytics Benchmarks"],
//     queryFn: () =>
//       http
//         .get<unknown>(
//           `/api/v1/system-params?category=${encodeURIComponent("Analytics Benchmarks")}`,
//         )
//         .then((r) => normaliseList<SystemParamLite>(r)),
//   });
//   const benchmarks = benchmarksQ.data ?? [];

//   const usageQ = useQuery({
//     queryKey: ["usage", "tenant"],
//     queryFn: () => http.get<UsageResponse>("/api/v1/usage/tenant"),
//   });
//   const usage = usageQ.data;

//   const resultQ = useQuery({
//     queryKey: ["analytics", "campaign-results", insightsCampaignId],
//     queryFn: () =>
//       http.get<CampaignResult | null>(
//         `/api/v1/analytics/campaign-results?campaign_id=${insightsCampaignId}`,
//       ),
//     enabled: !!insightsCampaignId && insightsOpen,
//   });

//   const generateInsightsMutation = useMutation({
//     mutationFn: (campaignId: string) =>
//       http.post<CampaignResult>(
//         `/api/v1/analytics/campaign-results?campaign_id=${campaignId}`,
//         {},
//       ),
//     onSuccess: () => {
//       toast.success("Insights generated");
//       qc.invalidateQueries({ queryKey: ["analytics", "campaign-results"] });
//     },
//     onError: () =>
//       toast.error("Failed to generate insights — this campaign may have no metrics yet"),
//   });

//   /* ── AN-2: Campaign Performance table (sum metrics per campaignId) ── */
//   const campaignPerformance = useMemo(() => {
//     const byCampaign = new Map<
//       string,
//       { sent: number; opened: number; replied: number; bounced: number }
//     >();
//     for (const m of metrics) {
//       const cur = byCampaign.get(m.campaignId) ?? {
//         sent: 0,
//         opened: 0,
//         replied: 0,
//         bounced: 0,
//       };
//       cur.sent += m.totalSent;
//       cur.opened += m.totalOpened;
//       cur.replied += m.totalReplied;
//       cur.bounced += m.totalBounced;
//       byCampaign.set(m.campaignId, cur);
//     }
//     return Array.from(byCampaign.entries())
//       .map(([campaignId, agg]) => {
//         const campaign = campaigns.find((c) => c.id === campaignId);
//         return {
//           campaignId,
//           name: campaign?.name ?? campaignId,
//           status: campaign?.status ?? "unknown",
//           ...agg,
//           openRate: agg.sent ? agg.opened / agg.sent : 0,
//           replyRate: agg.sent ? agg.replied / agg.sent : 0,
//           bounceRate: agg.sent ? agg.bounced / agg.sent : 0,
//         };
//       })
//       .sort((a, b) => b.sent - a.sent);
//   }, [metrics, campaigns]);

//   /* ── AN-1: Sequence Status Distribution ── */
//   const statusDistribution = useMemo(() => {
//     const counts = new Map<string, number>();
//     for (const s of sequences) counts.set(s.status, (counts.get(s.status) ?? 0) + 1);
//     return Array.from(counts.entries()).map(([status, count]) => ({
//       status,
//       count,
//       fill: STATUS_COLORS[status] ?? "#94a3b8",
//     }));
//   }, [sequences]);

//   /* ── AN-3: Sequence Step Performance (touch 1-7) ── */
//   const stepPerformance = useMemo(() => {
//     const byTouch = new Map<
//       number,
//       { sent: number; opened: number; replied: number }
//     >();
//     for (const s of sequences) {
//       const cur = byTouch.get(s.touchNumber) ?? { sent: 0, opened: 0, replied: 0 };
//       if (s.sentAt) cur.sent += 1;
//       if (s.openedAt) cur.opened += 1;
//       if (s.repliedAt) cur.replied += 1;
//       byTouch.set(s.touchNumber, cur);
//     }
//     return Array.from(byTouch.entries())
//       .sort(([a], [b]) => a - b)
//       .map(([touch, agg]) => ({
//         touch: `T${touch}`,
//         openRate: agg.sent ? Math.round((agg.opened / agg.sent) * 1000) / 10 : 0,
//         replyRate: agg.sent ? Math.round((agg.replied / agg.sent) * 1000) / 10 : 0,
//         sent: agg.sent,
//       }));
//   }, [sequences]);

//   /* ── AN-5: Copy Angle Performance ── */
//   const anglePerformance = useMemo(() => {
//     const byAngle = new Map<
//       string,
//       { sent: number; opened: number; replied: number }
//     >();
//     for (const s of sequences) {
//       const cur = byAngle.get(s.angle) ?? { sent: 0, opened: 0, replied: 0 };
//       if (s.sentAt) cur.sent += 1;
//       if (s.openedAt) cur.opened += 1;
//       if (s.repliedAt) cur.replied += 1;
//       byAngle.set(s.angle, cur);
//     }
//     return Array.from(byAngle.entries())
//       .map(([angle, agg]) => ({
//         angle: ANGLE_LABELS[angle] ?? angle,
//         replyRate: agg.sent ? Math.round((agg.replied / agg.sent) * 1000) / 10 : 0,
//         sent: agg.sent,
//       }))
//       .sort((a, b) => b.replyRate - a.replyRate);
//   }, [sequences]);

//   /* ── AN-4: Intent Source Attribution (real Prospect.intentSource) ── */
//   const intentAttribution = useMemo(() => {
//     const repliedProspectIds = new Set(
//       sequences.filter((s) => s.repliedAt).map((s) => s.prospectId),
//     );
//     const bySource = new Map<string, { total: number; replied: number }>();
//     for (const p of prospects) {
//       const cur = bySource.get(p.intentSource) ?? { total: 0, replied: 0 };
//       cur.total += 1;
//       if (repliedProspectIds.has(p.id)) cur.replied += 1;
//       bySource.set(p.intentSource, cur);
//     }
//     return Array.from(bySource.entries())
//       .map(([source, agg]) => ({
//         source: INTENT_LABELS[source] ?? source,
//         total: agg.total,
//         replied: agg.replied,
//         contributionRate: agg.total ? Math.round((agg.replied / agg.total) * 1000) / 10 : 0,
//       }))
//       .sort((a, b) => b.replied - a.replied);
//   }, [sequences, prospects]);

//   /* ── AN-7: QA Score Distribution ── */
//   const qaDistribution = useMemo(() => {
//     const buckets = [
//       { label: "0-59", min: 0, max: 59, count: 0 },
//       { label: "60-69", min: 60, max: 69, count: 0 },
//       { label: "70-79", min: 70, max: 79, count: 0 },
//       { label: "80-89", min: 80, max: 89, count: 0 },
//       { label: "90-100", min: 90, max: 100, count: 0 },
//     ];
//     for (const s of sequences) {
//       if (s.qaScore == null) continue;
//       const bucket = buckets.find((b) => s.qaScore! >= b.min && s.qaScore! <= b.max);
//       if (bucket) bucket.count += 1;
//     }
//     return buckets;
//   }, [sequences]);

//   const scoredCount = sequences.filter((s) => s.qaScore != null).length;
//   const avgQaScore = scoredCount
//     ? Math.round(
//         sequences.reduce((sum, s) => sum + (s.qaScore ?? 0), 0) / scoredCount,
//       )
//     : null;

//   const isLoading =
//     campaignsQ.isLoading || metricsQ.isLoading || sequencesQ.isLoading;

//   return (
//     <div className="space-y-6 p-6">
//       <PageHeader
//         title="Analytics"
//         description="Campaign performance, health diagnostics, and statistical breakdowns across your outreach."
//         actions={
//           <div className="flex items-center gap-2">
//             <Select
//               value={String(rangeDays)}
//               onChange={(e) => setRangeDays(Number(e.target.value))}
//               className="w-40"
//             >
//               {DATE_RANGES.map((r) => (
//                 <option key={r.days} value={r.days}>
//                   {r.label}
//                 </option>
//               ))}
//             </Select>
//             <Dialog open={insightsOpen} onOpenChange={setInsightsOpen}>
//               <DialogTrigger asChild>
//                 <Button variant="outline" onClick={() => setInsightsOpen(true)}>
//                   <Sparkles className="h-4 w-4 mr-2" />
//                   AI Insights
//                 </Button>
//               </DialogTrigger>
//               <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
//                 <DialogHeader>
//                   <DialogTitle>Generate Campaign Insights</DialogTitle>
//                   <DialogDescription>
//                     Select a campaign to generate an AI-written post-mortem:
//                     what worked, what didn't, and next actions.
//                   </DialogDescription>
//                 </DialogHeader>
//                 <div className="space-y-4">
//                   <Select
//                     value={insightsCampaignId}
//                     onChange={(e) => setInsightsCampaignId(e.target.value)}
//                   >
//                     <option value="">Select a campaign…</option>
//                     {campaigns.map((c) => (
//                       <option key={c.id} value={c.id}>
//                         {c.name}
//                       </option>
//                     ))}
//                   </Select>

//                   {insightsCampaignId && resultQ.isLoading && (
//                     <Skeleton className="h-32 w-full" />
//                   )}

//                   {insightsCampaignId && !resultQ.isLoading && !resultQ.data && (
//                     <div className="text-center py-6 text-sm text-muted-foreground">
//                       No insights generated yet for this campaign.
//                     </div>
//                   )}

//                   {resultQ.data && (
//                     <div className="space-y-3 text-sm">
//                       <div className="grid grid-cols-3 gap-3">
//                         <div className="rounded-md border p-2 text-center">
//                           <p className="text-lg font-bold">{resultQ.data.totalSent}</p>
//                           <p className="text-xs text-muted-foreground">Sent</p>
//                         </div>
//                         <div className="rounded-md border p-2 text-center">
//                           <p className="text-lg font-bold">{pct(resultQ.data.replyRate)}</p>
//                           <p className="text-xs text-muted-foreground">Reply rate</p>
//                         </div>
//                         <div className="rounded-md border p-2 text-center">
//                           <p className="text-lg font-bold">
//                             {pct(resultQ.data.positiveReplyRate)}
//                           </p>
//                           <p className="text-xs text-muted-foreground">Positive rate</p>
//                         </div>
//                       </div>
//                       {resultQ.data.whatWorked && (
//                         <div>
//                           <p className="font-medium text-xs mb-1">What worked</p>
//                           <p className="text-muted-foreground">{resultQ.data.whatWorked}</p>
//                         </div>
//                       )}
//                       {resultQ.data.whatDidntWork && (
//                         <div>
//                           <p className="font-medium text-xs mb-1">What didn't work</p>
//                           <p className="text-muted-foreground">
//                             {resultQ.data.whatDidntWork}
//                           </p>
//                         </div>
//                       )}
//                       {resultQ.data.nextActions && (
//                         <div>
//                           <p className="font-medium text-xs mb-1">Next actions</p>
//                           <p className="text-muted-foreground">{resultQ.data.nextActions}</p>
//                         </div>
//                       )}
//                       {resultQ.data.insights && (
//                         <div>
//                           <p className="font-medium text-xs mb-1">Insights</p>
//                           <p className="text-muted-foreground">{resultQ.data.insights}</p>
//                         </div>
//                       )}
//                       <p className="text-[10px] text-muted-foreground">
//                         Generated {new Date(resultQ.data.generatedAt).toLocaleString()}
//                       </p>
//                     </div>
//                   )}
//                 </div>
//                 <DialogFooter>
//                   <Button
//                     variant="outline"
//                     onClick={() => {
//                       setInsightsOpen(false);
//                       setInsightsCampaignId("");
//                     }}
//                   >
//                     Close
//                   </Button>
//                   <Button
//                     onClick={() =>
//                       insightsCampaignId &&
//                       generateInsightsMutation.mutate(insightsCampaignId)
//                     }
//                     disabled={!insightsCampaignId || generateInsightsMutation.isPending}
//                   >
//                     {generateInsightsMutation.isPending ? (
//                       <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
//                     ) : (
//                       <Sparkles className="h-3.5 w-3.5 mr-1.5" />
//                     )}
//                     Generate Insights
//                   </Button>
//                 </DialogFooter>
//               </DialogContent>
//             </Dialog>
//           </div>
//         }
//       />

//       {isLoading ? (
//         <div className="space-y-3">
//           {[0, 1, 2].map((i) => (
//             <Skeleton key={i} className="h-32 w-full" />
//           ))}
//         </div>
//       ) : (
//         <>
//           {/* Time series (AN-12 date range) */}
//           <Card>
//             <CardHeader>
//               <CardTitle className="text-base">Activity Over Time</CardTitle>
//               <CardDescription>
//                 Sent, opened, replied, and bounced counts for the selected range.
//               </CardDescription>
//             </CardHeader>
//             <CardContent>
//               {timeSeriesQ.isLoading ? (
//                 <Skeleton className="h-64 w-full" />
//               ) : (
//                 <ResponsiveContainer width="100%" height={260}>
//                   <LineChart data={timeSeries}>
//                     <CartesianGrid strokeDasharray="3 3" />
//                     <XAxis dataKey="date" tick={{ fontSize: 11 }} />
//                     <YAxis tick={{ fontSize: 11 }} />
//                     <RTooltip />
//                     <Legend />
//                     <Line type="monotone" dataKey="sent" stroke="#8b5cf6" strokeWidth={2} />
//                     <Line type="monotone" dataKey="opened" stroke="#3b82f6" strokeWidth={2} />
//                     <Line type="monotone" dataKey="replied" stroke="#10b981" strokeWidth={2} />
//                     <Line type="monotone" dataKey="bounced" stroke="#f97316" strokeWidth={2} />
//                   </LineChart>
//                 </ResponsiveContainer>
//               )}
//             </CardContent>
//           </Card>

//           {/* AN-2: Campaign Performance table */}
//           <Card>
//             <CardHeader>
//               <CardTitle className="text-base flex items-center gap-2">
//                 <BarChart3 className="h-4 w-4" /> Campaign Performance
//               </CardTitle>
//               <CardDescription>
//                 Aggregated send/open/reply/bounce metrics per campaign.
//               </CardDescription>
//             </CardHeader>
//             <CardContent>
//               {campaignPerformance.length === 0 ? (
//                 <p className="text-sm text-muted-foreground py-6 text-center">
//                   No campaign metrics yet — metrics populate once sequences start sending.
//                 </p>
//               ) : (
//                 <Table>
//                   <TableHeader>
//                     <TableRow>
//                       <TableHead>Campaign</TableHead>
//                       <TableHead>Status</TableHead>
//                       <TableHead className="text-right">Sent</TableHead>
//                       <TableHead className="text-right">Opened</TableHead>
//                       <TableHead className="text-right">Replied</TableHead>
//                       <TableHead className="text-right">Bounced</TableHead>
//                       <TableHead className="text-right">Open Rate</TableHead>
//                       <TableHead className="text-right">Reply Rate</TableHead>
//                     </TableRow>
//                   </TableHeader>
//                   <TableBody>
//                     {campaignPerformance.map((c) => (
//                       <TableRow key={c.campaignId}>
//                         <TableCell className="font-medium">{c.name}</TableCell>
//                         <TableCell>
//                           <Badge variant="outline" className="text-[10px]">
//                             {c.status}
//                           </Badge>
//                         </TableCell>
//                         <TableCell className="text-right tabular-nums">{c.sent}</TableCell>
//                         <TableCell className="text-right tabular-nums">{c.opened}</TableCell>
//                         <TableCell className="text-right tabular-nums">{c.replied}</TableCell>
//                         <TableCell className="text-right tabular-nums">{c.bounced}</TableCell>
//                         <TableCell className="text-right tabular-nums">
//                           {pct(c.openRate)}
//                         </TableCell>
//                         <TableCell className="text-right tabular-nums">
//                           {pct(c.replyRate)}
//                         </TableCell>
//                       </TableRow>
//                     ))}
//                   </TableBody>
//                 </Table>
//               )}
//             </CardContent>
//           </Card>

//           <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
//             {/* AN-1: Sequence Status Distribution */}
//             <Card>
//               <CardHeader>
//                 <CardTitle className="text-base">Sequence Status Distribution</CardTitle>
//                 <CardDescription className="text-xs">
//                   Current status of all sequenced touches.
//                 </CardDescription>
//               </CardHeader>
//               <CardContent>
//                 {statusDistribution.length === 0 ? (
//                   <p className="text-sm text-muted-foreground py-6 text-center">
//                     No sequences yet.
//                   </p>
//                 ) : (
//                   <ResponsiveContainer width="100%" height={240}>
//                     <PieChart>
//                       <Pie
//                         data={statusDistribution}
//                         dataKey="count"
//                         nameKey="status"
//                         cx="50%"
//                         cy="50%"
//                         outerRadius={80}
//                         label={(entry: { status: string }) => entry.status}
//                       >
//                         {statusDistribution.map((entry) => (
//                           <Cell key={entry.status} fill={entry.fill} />
//                         ))}
//                       </Pie>
//                       <RTooltip />
//                     </PieChart>
//                   </ResponsiveContainer>
//                 )}
//               </CardContent>
//             </Card>

//             {/* AN-3: Sequence Step Performance */}
//             <Card>
//               <CardHeader>
//                 <CardTitle className="text-base">Sequence Step Performance</CardTitle>
//                 <CardDescription className="text-xs">
//                   Open and reply rate by touch number (T1-T7).
//                 </CardDescription>
//               </CardHeader>
//               <CardContent>
//                 {stepPerformance.length === 0 ? (
//                   <p className="text-sm text-muted-foreground py-6 text-center">
//                     No sent touches yet.
//                   </p>
//                 ) : (
//                   <ResponsiveContainer width="100%" height={240}>
//                     <BarChart data={stepPerformance}>
//                       <CartesianGrid strokeDasharray="3 3" />
//                       <XAxis dataKey="touch" tick={{ fontSize: 11 }} />
//                       <YAxis tick={{ fontSize: 11 }} unit="%" />
//                       <RTooltip />
//                       <Legend />
//                       <Bar dataKey="openRate" name="Open %" fill="#3b82f6" />
//                       <Bar dataKey="replyRate" name="Reply %" fill="#10b981" />
//                     </BarChart>
//                   </ResponsiveContainer>
//                 )}
//               </CardContent>
//             </Card>

//             {/* AN-5: Copy Angle Performance */}
//             <Card>
//               <CardHeader>
//                 <CardTitle className="text-base">Copy Angle Performance</CardTitle>
//                 <CardDescription className="text-xs">
//                   Reply rate by messaging angle, best first.
//                 </CardDescription>
//               </CardHeader>
//               <CardContent>
//                 {anglePerformance.length === 0 ? (
//                   <p className="text-sm text-muted-foreground py-6 text-center">
//                     No sent touches yet.
//                   </p>
//                 ) : (
//                   <ResponsiveContainer width="100%" height={240}>
//                     <BarChart data={anglePerformance} layout="vertical">
//                       <CartesianGrid strokeDasharray="3 3" />
//                       <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
//                       <YAxis
//                         type="category"
//                         dataKey="angle"
//                         tick={{ fontSize: 11 }}
//                         width={110}
//                       />
//                       <RTooltip />
//                       <Bar dataKey="replyRate" name="Reply %" fill="#8b5cf6" />
//                     </BarChart>
//                   </ResponsiveContainer>
//                 )}
//               </CardContent>
//             </Card>

//             {/* AN-4: Intent Source Attribution */}
//             <Card>
//               <CardHeader>
//                 <CardTitle className="text-base">Intent Source Attribution</CardTitle>
//                 <CardDescription className="text-xs">
//                   Prospect count and reply contribution by buying-intent
//                   source (Prospect.intentSource).
//                 </CardDescription>
//               </CardHeader>
//               <CardContent>
//                 {intentAttribution.length === 0 ? (
//                   <p className="text-sm text-muted-foreground py-6 text-center">
//                     No prospects yet.
//                   </p>
//                 ) : (
//                   <ResponsiveContainer width="100%" height={240}>
//                     <BarChart data={intentAttribution} layout="vertical">
//                       <CartesianGrid strokeDasharray="3 3" />
//                       <XAxis type="number" tick={{ fontSize: 11 }} />
//                       <YAxis
//                         type="category"
//                         dataKey="source"
//                         tick={{ fontSize: 11 }}
//                         width={110}
//                       />
//                       <RTooltip />
//                       <Legend />
//                       <Bar dataKey="total" name="Prospects" fill="#94a3b8" />
//                       <Bar dataKey="replied" name="Replied" fill="#10b981" />
//                     </BarChart>
//                   </ResponsiveContainer>
//                 )}
//               </CardContent>
//             </Card>
//           </div>

//           {/* AN-6: Campaign Health Diagnostics */}
//           <Card>
//             <CardHeader>
//               <CardTitle className="text-base flex items-center gap-2">
//                 <Activity className="h-4 w-4" /> Campaign Health Diagnostics
//               </CardTitle>
//               <CardDescription>
//                 5-layer closed-loop diagnostic across all active campaigns.
//               </CardDescription>
//             </CardHeader>
//             <CardContent>
//               {diagnoseQ.isLoading ? (
//                 <Skeleton className="h-32 w-full" />
//               ) : diagnose ? (
//                 <div className="space-y-3">
//                   <p className="text-sm text-muted-foreground">{diagnose.summary}</p>
//                   <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2">
//                     {diagnose.layers.map((l) => (
//                       <div
//                         key={l.layer}
//                         className={`rounded-md border p-2.5 text-xs ${
//                           l.status === "critical"
//                             ? "border-red-300 bg-red-50"
//                             : l.status === "warn"
//                               ? "border-amber-300 bg-amber-50"
//                               : "border-emerald-200 bg-emerald-50"
//                         }`}
//                       >
//                         <div className="flex items-center justify-between mb-1">
//                           <span className="font-medium capitalize">{l.layer}</span>
//                           {l.status === "critical" ? (
//                             <AlertTriangle className="h-3.5 w-3.5 text-red-600" />
//                           ) : l.status === "warn" ? (
//                             <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
//                           ) : (
//                             <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
//                           )}
//                         </div>
//                         <p className="tabular-nums font-mono">
//                           {l.metric}: {l.value}
//                           {l.benchmark != null && (
//                             <span className="text-muted-foreground"> / {l.benchmark}</span>
//                           )}
//                         </p>
//                         <p className="text-muted-foreground mt-1">{l.note}</p>
//                       </div>
//                     ))}
//                   </div>
//                 </div>
//               ) : (
//                 <p className="text-sm text-muted-foreground py-6 text-center">
//                   No diagnostic data available yet.
//                 </p>
//               )}
//             </CardContent>
//           </Card>

//           <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
//             {/* AN-7: AI Performance Diagnostics */}
//             <Card>
//               <CardHeader>
//                 <CardTitle className="text-base flex items-center gap-2">
//                   <Bot className="h-4 w-4" /> AI Performance
//                 </CardTitle>
//                 <CardDescription className="text-xs">
//                   LLM usage/cost this period and QA score distribution.
//                   (Generation-time tracking isn't recorded by the backend.)
//                 </CardDescription>
//               </CardHeader>
//               <CardContent className="space-y-4">
//                 {usageQ.isLoading ? (
//                   <Skeleton className="h-24 w-full" />
//                 ) : usage && usage.breakdown.length > 0 ? (
//                   <div className="space-y-1.5">
//                     {usage.breakdown.map((row) => (
//                       <div
//                         key={`${row.event_type}-${row.provider}`}
//                         className="flex items-center justify-between text-xs bg-muted/50 rounded px-2 py-1.5"
//                       >
//                         <span>
//                           {row.event_type}
//                           {row.provider ? ` · ${row.provider}` : ""}
//                         </span>
//                         <span className="tabular-nums text-muted-foreground">
//                           {row.event_count} calls · ${(row.total_cost_cents / 100).toFixed(2)}
//                         </span>
//                       </div>
//                     ))}
//                     <p className="text-xs font-medium pt-1">
//                       Total: ${(usage.total_cost_cents / 100).toFixed(2)}
//                     </p>
//                   </div>
//                 ) : (
//                   <p className="text-xs text-muted-foreground">No usage recorded this period.</p>
//                 )}

//                 <div>
//                   <p className="text-xs font-medium mb-2">
//                     QA Score Distribution
//                     {avgQaScore != null && (
//                       <span className="text-muted-foreground"> · avg {avgQaScore}</span>
//                     )}
//                   </p>
//                   {scoredCount === 0 ? (
//                     <p className="text-xs text-muted-foreground">No QA-scored emails yet.</p>
//                   ) : (
//                     <ResponsiveContainer width="100%" height={140}>
//                       <BarChart data={qaDistribution}>
//                         <XAxis dataKey="label" tick={{ fontSize: 10 }} />
//                         <YAxis tick={{ fontSize: 10 }} />
//                         <RTooltip />
//                         <Bar dataKey="count" fill="#3b82f6" />
//                       </BarChart>
//                     </ResponsiveContainer>
//                   )}
//                 </div>
//               </CardContent>
//             </Card>

//             {/* AN-8: Industry Benchmarks */}
//             <Card>
//               <CardHeader>
//                 <CardTitle className="text-base flex items-center gap-2">
//                   <Target className="h-4 w-4" /> Benchmarks
//                 </CardTitle>
//                 <CardDescription className="text-xs">
//                   Your configured health-diagnostic thresholds (System
//                   Parameters → Analytics Benchmarks).
//                 </CardDescription>
//               </CardHeader>
//               <CardContent>
//                 {benchmarksQ.isLoading ? (
//                   <Skeleton className="h-24 w-full" />
//                 ) : benchmarks.length === 0 ? (
//                   <p className="text-xs text-muted-foreground py-4 text-center">
//                     No benchmark parameters configured.
//                   </p>
//                 ) : (
//                   <div className="grid grid-cols-2 gap-2">
//                     {benchmarks.map((b) => (
//                       <div key={b.key} className="rounded-md border p-2 text-center">
//                         <p className="text-lg font-bold">
//                           {b.value}
//                           {b.unit?.includes("%") ? "" : ""}
//                         </p>
//                         <p className="text-[10px] text-muted-foreground">{b.label}</p>
//                       </div>
//                     ))}
//                   </div>
//                 )}
//                 <Button
//                   variant="ghost"
//                   size="sm"
//                   className="mt-3 w-full"
//                   onClick={() => navigate("/setup/system-params")}
//                 >
//                   Adjust benchmarks in System Parameters
//                   <ExternalLink className="h-3 w-3 ml-1.5" />
//                 </Button>
//               </CardContent>
//             </Card>
//           </div>

//           {/* AN-9 / AN-11: Auto-Optimization link-out */}
//           <Card className="border-violet-200 bg-violet-50/50">
//             <CardContent className="py-4 flex items-center justify-between gap-4">
//               <div className="flex items-center gap-3">
//                 <TrendingUp className="h-5 w-5 text-violet-600 shrink-0" />
//                 <div>
//                   <p className="text-sm font-medium">Auto-Optimization Rules Engine</p>
//                   <p className="text-xs text-muted-foreground">
//                     Create rules like "if reply rate &lt; 5% for 3+ days, pause
//                     campaign" — managed on its own page with full create/edit/delete.
//                   </p>
//                 </div>
//               </div>
//               <Button
//                 variant="outline"
//                 size="sm"
//                 className="shrink-0"
//                 onClick={() => navigate("/optimize/optimization-rules")}
//               >
//                 Open Optimization Rules
//                 <ExternalLink className="h-3 w-3 ml-1.5" />
//               </Button>
//             </CardContent>
//           </Card>

//           <Card className="p-4 bg-muted/30 border-dashed">
//             <div className="flex gap-3">
//               <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
//               <p className="text-xs text-muted-foreground">
//                 Campaign Performance and the time-series chart reflect data
//                 across all campaigns for the selected range. Sequence-derived
//                 charts (status, step, angle, intent) are computed from the
//                 most recent 500 sequences and 500 prospects.
//               </p>
//             </div>
//           </Card>
//         </>
//       )}
//     </div>
//   );
// }

/**
 * AnalyticsPage.tsx - campaign performance, health diagnostics, and
 * statistical breakdowns across sequences, prospects, and LLM usage.
 *
 * API (verified against real routers/schemas - see comments per section):
 *   GET  /api/v1/analytics/metrics?campaign_id=        -> CampaignMetricResponse[] (per campaign+date)
 *   GET  /api/v1/analytics/time-series?days=N          -> TimeSeriesResponse
 *   POST /api/v1/analytics/diagnose                     { campaignId } -> DiagnoseResponse
 *   GET  /api/v1/analytics/campaign-results?campaign_id= -> CampaignResultResponse | null
 *   POST /api/v1/analytics/campaign-results?campaign_id= -> CampaignResultResponse (generates)
 *   GET  /api/v1/campaigns                               -> CampaignResponse[] (for names + selector)
 *   GET  /api/v1/sequences?limit=500                      -> SequenceResponse[] (touchNumber, angle, status, timestamps)
 *   GET  /api/v1/prospects?limit=500                      -> Prospect[] (intentSource)
 *   GET  /api/v1/system-params?category=Analytics%20Benchmarks -> SystemParamResponse[]
 *   GET  /api/v1/usage/tenant?period=YYYY-MM               -> UsageResponse (LLM cost/event breakdown)
 *
 * CORRECTIONS vs. the previous version: the old page had a completely wrong
 * response shape for /analytics/metrics (treated it as one aggregated
 * object; it's actually an array of per-campaign-per-date rows), called
 * /analytics/time-series with a campaignId param it doesn't accept (it's
 * tenant-wide, only takes `days`), and fell back to MOCK_METRICS /
 * MOCK_TIMESERIES / MOCK_DIAGNOSE / MOCK_RESULTS / MOCK_CAMPAIGNS whenever
 * a real call returned anything falsy. All mock fallbacks removed.
 *
 * Backend gaps documented rather than faked:
 *   - AN-4 "Intent Source Attribution" is built from Prospect.intentSource
 *     (FUNDING_URGENCY/HIRING_BUDGET/FORUM_PAIN/LINKEDIN_DEMAND/REFERRAL/
 *     INBOUND/OTHER) - the real backend field. There is no field tracking
 *     which *sourcing platform* (Apollo/LinkedIn/manual/CSV) found a
 *     prospect, so that specific breakdown the gap doc describes isn't
 *     buildable from real data; intentSource is the closest real analogue
 *     and is labeled accurately as such.
 *   - AN-7 "avg generation time" has no backend field anywhere (LLM calls
 *     aren't timed) - omitted rather than fabricated. LLM usage/cost and
 *     QA score distribution (both real) are shown instead.
 *   - AN-9/AN-11 (Auto-Optimization Rules) already live on a separate,
 *     fully-built OptimizationRulesPage per the gap audit - this page
 *     links out to it instead of duplicating its CRUD.
 *
 * AN-1  Sequence Status Distribution (donut, from /sequences grouped by status)
 * AN-2  Campaign Performance table (from /analytics/metrics, summed per campaign)
 * AN-3  Sequence Step Performance (bar, from /sequences grouped by touchNumber)
 * AN-4  Intent Source Attribution (bar, from /prospects.intentSource + reply join)
 * AN-5  Copy Angle Performance (bar, from /sequences grouped by angle)
 * AN-6  Campaign Health Diagnostics (from /analytics/diagnose)
 * AN-7  AI Performance Diagnostics (usage/tenant + QA score histogram)
 * AN-8  Industry Benchmarks (from /system-params?category=Analytics Benchmarks)
 * AN-9  Auto-Optimization summary + link to OptimizationRulesPage
 * AN-10 Generate Insights dialog (POST /analytics/campaign-results)
 * AN-11 link to OptimizationRulesPage (already implemented there)
 * AN-12 Date range filter (7/14/30/60/90 days) driving time-series + metrics
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  ExternalLink,
  Info,
  Loader2,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useNavigate } from "react-router-dom";

import { http } from "@/services/apiClient";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
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
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

/* Types (aligned with real backend schemas) */

interface CampaignMetricRow {
  id: string;
  campaignId: string;
  date: string;
  totalSent: number;
  totalOpened: number;
  totalReplied: number;
  totalBounced: number;
  openRate: number;
  replyRate: number;
  bounceRate: number;
  diagnosticNote: string | null;
}

interface Campaign {
  id: string;
  name: string;
  status: string;
}

interface Sequence {
  id: string;
  campaignId: string;
  prospectId: string;
  touchNumber: number;
  angle: string;
  status: string;
  qaScore: number | null;
  sentAt: string | null;
  openedAt: string | null;
  repliedAt: string | null;
  bouncedAt: string | null;
}

interface ProspectLite {
  id: string;
  intentSource: string;
}

interface TimeSeriesPoint {
  date: string;
  sent: number;
  opened: number;
  replied: number;
  bounced: number;
}

interface DiagnoseLayerResult {
  layer: string;
  status: "ok" | "warn" | "critical";
  metric: string;
  value: number;
  benchmark: number | null;
  note: string;
}

interface DiagnoseResponse {
  campaignId: string | null;
  layers: DiagnoseLayerResult[];
  summary: string;
  generatedAt: string;
}

interface CampaignResult {
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

interface SystemParamLite {
  key: string;
  label: string;
  value: string;
  unit: string | null;
}

interface UsageBreakdownRow {
  event_type: string;
  provider: string | null;
  total_quantity: number;
  total_cost_cents: number;
  event_count: number;
}

interface UsageResponse {
  period_start: string;
  period_end: string;
  breakdown: UsageBreakdownRow[];
  total_cost_cents: number;
}

const DATE_RANGES = [
  { label: "Last 7 days", days: 7 },
  { label: "Last 14 days", days: 14 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 60 days", days: 60 },
  { label: "Last 90 days", days: 90 },
];

const ANGLE_LABELS: Record<string, string> = {
  FirstTouch: "First Touch",
  NewEvidence: "New Evidence",
  DifferentPain: "Different Pain",
  IndustryInsight: "Industry Insight",
  DirectQuestion: "Direct Question",
  Breakup: "Breakup",
};

const INTENT_LABELS: Record<string, string> = {
  FUNDING_URGENCY: "Funding Urgency",
  HIRING_BUDGET: "Hiring Budget",
  FORUM_PAIN: "Forum Pain Signal",
  LINKEDIN_DEMAND: "LinkedIn Demand",
  REFERRAL: "Referral",
  INBOUND: "Inbound",
  OTHER: "Other",
};

const STATUS_COLORS: Record<string, string> = {
  Draft: "#94a3b8",
  QaFailed: "#ef4444",
  QaPassed: "#22c55e",
  Scheduled: "#3b82f6",
  Sent: "#8b5cf6",
  Replied: "#10b981",
  Bounced: "#f97316",
  Failed: "#dc2626",
};

function normaliseList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: T[] }).items ?? [];
  return [];
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

/* Page */

export function AnalyticsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [rangeDays, setRangeDays] = useState(30);
  const [insightsOpen, setInsightsOpen] = useState(false);
  const [insightsCampaignId, setInsightsCampaignId] = useState<string>("");

  const campaignsQ = useQuery({
    queryKey: ["campaigns", "for-analytics"],
    queryFn: () =>
      http.get<unknown>("/api/v1/campaigns").then((r) => normaliseList<Campaign>(r)),
  });
  const campaigns = campaignsQ.data ?? [];

  const metricsQ = useQuery({
    queryKey: ["analytics", "metrics", rangeDays],
    queryFn: () =>
      http
        .get<unknown>(`/api/v1/analytics/metrics?days=${rangeDays}`)
        .then((r) => normaliseList<CampaignMetricRow>(r)),
  });
  const metrics = metricsQ.data ?? [];

  const timeSeriesQ = useQuery({
    queryKey: ["analytics", "time-series", rangeDays],
    queryFn: () =>
      http.get<{ points: TimeSeriesPoint[] }>(
        `/api/v1/analytics/time-series?days=${rangeDays}`,
      ),
  });
  const timeSeries = timeSeriesQ.data?.points ?? [];

  const sequencesQ = useQuery({
    queryKey: ["sequences", "for-analytics", rangeDays],
    queryFn: () =>
      http
        .get<unknown>(`/api/v1/sequences?limit=500&days=${rangeDays}`)
        .then((r) => normaliseList<Sequence>(r)),
  });
  const sequences = sequencesQ.data ?? [];

  const prospectsQ = useQuery({
    queryKey: ["prospects", "for-analytics"],
    queryFn: () =>
      http
        .get<unknown>("/api/v1/prospects?limit=500")
        .then((r) => normaliseList<ProspectLite>(r)),
  });
  const prospects = prospectsQ.data ?? [];

  const diagnoseQ = useQuery({
    queryKey: ["analytics", "diagnose", "tenant"],
    queryFn: () =>
      http.post<DiagnoseResponse>("/api/v1/analytics/diagnose", {
        campaignId: null,
      }),
  });
  const diagnose = diagnoseQ.data;

  const benchmarksQ = useQuery({
    queryKey: ["system-params", "Analytics Benchmarks"],
    queryFn: () =>
      http
        .get<unknown>(
          `/api/v1/system-params?category=${encodeURIComponent("Analytics Benchmarks")}`,
        )
        .then((r) => normaliseList<SystemParamLite>(r)),
  });
  const benchmarks = benchmarksQ.data ?? [];

  const usageQ = useQuery({
    queryKey: ["usage", "tenant", rangeDays],
    queryFn: () => http.get<UsageResponse>(`/api/v1/usage/tenant?days=${rangeDays}`),
  });
  const usage = usageQ.data;

  const resultQ = useQuery({
    queryKey: ["analytics", "campaign-results", insightsCampaignId],
    queryFn: () =>
      http.get<CampaignResult | null>(
        `/api/v1/analytics/campaign-results?campaign_id=${insightsCampaignId}`,
      ),
    enabled: !!insightsCampaignId && insightsOpen,
  });

  const generateInsightsMutation = useMutation({
    mutationFn: (campaignId: string) =>
      http.post<CampaignResult>(
        `/api/v1/analytics/campaign-results?campaign_id=${campaignId}`,
        {},
      ),
    onSuccess: () => {
      toast.success("Insights generated");
      qc.invalidateQueries({ queryKey: ["analytics", "campaign-results"] });
    },
    onError: () =>
      toast.error("Failed to generate insights — this campaign may have no metrics yet"),
  });

  /* ── AN-2: Campaign Performance table (sum metrics per campaignId) ── */
  const campaignPerformance = useMemo(() => {
    const byCampaign = new Map<
      string,
      { sent: number; opened: number; replied: number; bounced: number }
    >();
    for (const m of metrics) {
      const cur = byCampaign.get(m.campaignId) ?? {
        sent: 0,
        opened: 0,
        replied: 0,
        bounced: 0,
      };
      cur.sent += m.totalSent;
      cur.opened += m.totalOpened;
      cur.replied += m.totalReplied;
      cur.bounced += m.totalBounced;
      byCampaign.set(m.campaignId, cur);
    }
    return Array.from(byCampaign.entries())
      .map(([campaignId, agg]) => {
        const campaign = campaigns.find((c) => c.id === campaignId);
        return {
          campaignId,
          name: campaign?.name ?? campaignId,
          status: campaign?.status ?? "unknown",
          ...agg,
          openRate: agg.sent ? agg.opened / agg.sent : 0,
          replyRate: agg.sent ? agg.replied / agg.sent : 0,
          bounceRate: agg.sent ? agg.bounced / agg.sent : 0,
        };
      })
      .sort((a, b) => b.sent - a.sent);
  }, [metrics, campaigns]);

  /* ── AN-1: Sequence Status Distribution ── */
  const statusDistribution = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of sequences) counts.set(s.status, (counts.get(s.status) ?? 0) + 1);
    return Array.from(counts.entries()).map(([status, count]) => ({
      status,
      count,
      fill: STATUS_COLORS[status] ?? "#94a3b8",
    }));
  }, [sequences]);

  /* ── AN-3: Sequence Step Performance (touch 1-7) ── */
  const stepPerformance = useMemo(() => {
    const byTouch = new Map<
      number,
      { sent: number; opened: number; replied: number }
    >();
    for (const s of sequences) {
      const cur = byTouch.get(s.touchNumber) ?? { sent: 0, opened: 0, replied: 0 };
      if (s.sentAt) cur.sent += 1;
      if (s.openedAt) cur.opened += 1;
      if (s.repliedAt) cur.replied += 1;
      byTouch.set(s.touchNumber, cur);
    }
    return Array.from(byTouch.entries())
      .sort(([a], [b]) => a - b)
      .map(([touch, agg]) => ({
        touch: `T${touch}`,
        openRate: agg.sent ? Math.round((agg.opened / agg.sent) * 1000) / 10 : 0,
        replyRate: agg.sent ? Math.round((agg.replied / agg.sent) * 1000) / 10 : 0,
        sent: agg.sent,
      }));
  }, [sequences]);

  /* ── AN-5: Copy Angle Performance ── */
  const anglePerformance = useMemo(() => {
    const byAngle = new Map<
      string,
      { sent: number; opened: number; replied: number }
    >();
    for (const s of sequences) {
      const cur = byAngle.get(s.angle) ?? { sent: 0, opened: 0, replied: 0 };
      if (s.sentAt) cur.sent += 1;
      if (s.openedAt) cur.opened += 1;
      if (s.repliedAt) cur.replied += 1;
      byAngle.set(s.angle, cur);
    }
    return Array.from(byAngle.entries())
      .map(([angle, agg]) => ({
        angle: ANGLE_LABELS[angle] ?? angle,
        replyRate: agg.sent ? Math.round((agg.replied / agg.sent) * 1000) / 10 : 0,
        sent: agg.sent,
      }))
      .sort((a, b) => b.replyRate - a.replyRate);
  }, [sequences]);

  /* ── AN-4: Intent Source Attribution (real Prospect.intentSource) ── */
  const intentAttribution = useMemo(() => {
    const repliedProspectIds = new Set(
      sequences.filter((s) => s.repliedAt).map((s) => s.prospectId),
    );
    const bySource = new Map<string, { total: number; replied: number }>();
    for (const p of prospects) {
      const cur = bySource.get(p.intentSource) ?? { total: 0, replied: 0 };
      cur.total += 1;
      if (repliedProspectIds.has(p.id)) cur.replied += 1;
      bySource.set(p.intentSource, cur);
    }
    return Array.from(bySource.entries())
      .map(([source, agg]) => ({
        source: INTENT_LABELS[source] ?? source,
        total: agg.total,
        replied: agg.replied,
        contributionRate: agg.total ? Math.round((agg.replied / agg.total) * 1000) / 10 : 0,
      }))
      .sort((a, b) => b.replied - a.replied);
  }, [sequences, prospects]);

  /* ── AN-7: QA Score Distribution ── */
  const qaDistribution = useMemo(() => {
    const buckets = [
      { label: "0-59", min: 0, max: 59, count: 0 },
      { label: "60-69", min: 60, max: 69, count: 0 },
      { label: "70-79", min: 70, max: 79, count: 0 },
      { label: "80-89", min: 80, max: 89, count: 0 },
      { label: "90-100", min: 90, max: 100, count: 0 },
    ];
    for (const s of sequences) {
      if (s.qaScore == null) continue;
      const bucket = buckets.find((b) => s.qaScore! >= b.min && s.qaScore! <= b.max);
      if (bucket) bucket.count += 1;
    }
    return buckets;
  }, [sequences]);

  const scoredCount = sequences.filter((s) => s.qaScore != null).length;
  const avgQaScore = scoredCount
    ? Math.round(
        sequences.reduce((sum, s) => sum + (s.qaScore ?? 0), 0) / scoredCount,
      )
    : null;

  const isLoading =
    campaignsQ.isLoading || metricsQ.isLoading || sequencesQ.isLoading;

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Analytics"
        description="Campaign performance, health diagnostics, and statistical breakdowns across your outreach."
        actions={
          <div className="flex items-center gap-2">
            <Select
              value={String(rangeDays)}
              onChange={(e) => setRangeDays(Number(e.target.value))}
              className="w-40"
            >
              {DATE_RANGES.map((r) => (
                <option key={r.days} value={r.days}>
                  {r.label}
                </option>
              ))}
            </Select>
            <Dialog open={insightsOpen} onOpenChange={setInsightsOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" onClick={() => setInsightsOpen(true)}>
                  <Sparkles className="h-4 w-4 mr-2" />
                  AI Insights
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Generate Campaign Insights</DialogTitle>
                  <DialogDescription>
                    Select a campaign to generate an AI-written post-mortem:
                    what worked, what didn't, and next actions.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <Select
                    value={insightsCampaignId}
                    onChange={(e) => setInsightsCampaignId(e.target.value)}
                  >
                    <option value="">Select a campaign…</option>
                    {campaigns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </Select>

                  {insightsCampaignId && resultQ.isLoading && (
                    <Skeleton className="h-32 w-full" />
                  )}

                  {insightsCampaignId && !resultQ.isLoading && !resultQ.data && (
                    <div className="text-center py-6 text-sm text-muted-foreground">
                      No insights generated yet for this campaign.
                    </div>
                  )}

                  {resultQ.data && (
                    <div className="space-y-3 text-sm">
                      <div className="grid grid-cols-3 gap-3">
                        <div className="rounded-md border p-2 text-center">
                          <p className="text-lg font-bold">{resultQ.data.totalSent}</p>
                          <p className="text-xs text-muted-foreground">Sent</p>
                        </div>
                        <div className="rounded-md border p-2 text-center">
                          <p className="text-lg font-bold">{pct(resultQ.data.replyRate)}</p>
                          <p className="text-xs text-muted-foreground">Reply rate</p>
                        </div>
                        <div className="rounded-md border p-2 text-center">
                          <p className="text-lg font-bold">
                            {pct(resultQ.data.positiveReplyRate)}
                          </p>
                          <p className="text-xs text-muted-foreground">Positive rate</p>
                        </div>
                      </div>
                      {resultQ.data.whatWorked && (
                        <div>
                          <p className="font-medium text-xs mb-1">What worked</p>
                          <p className="text-muted-foreground">{resultQ.data.whatWorked}</p>
                        </div>
                      )}
                      {resultQ.data.whatDidntWork && (
                        <div>
                          <p className="font-medium text-xs mb-1">What didn't work</p>
                          <p className="text-muted-foreground">
                            {resultQ.data.whatDidntWork}
                          </p>
                        </div>
                      )}
                      {resultQ.data.nextActions && (
                        <div>
                          <p className="font-medium text-xs mb-1">Next actions</p>
                          <p className="text-muted-foreground">{resultQ.data.nextActions}</p>
                        </div>
                      )}
                      {resultQ.data.insights && (
                        <div>
                          <p className="font-medium text-xs mb-1">Insights</p>
                          <p className="text-muted-foreground">{resultQ.data.insights}</p>
                        </div>
                      )}
                      <p className="text-[10px] text-muted-foreground">
                        Generated {new Date(resultQ.data.generatedAt).toLocaleString()}
                      </p>
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setInsightsOpen(false);
                      setInsightsCampaignId("");
                    }}
                  >
                    Close
                  </Button>
                  <Button
                    onClick={() =>
                      insightsCampaignId &&
                      generateInsightsMutation.mutate(insightsCampaignId)
                    }
                    disabled={!insightsCampaignId || generateInsightsMutation.isPending}
                  >
                    {generateInsightsMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                    ) : (
                      <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                    )}
                    Generate Insights
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : (
        <>
          {/* Time series (AN-12 date range) */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Activity Over Time</CardTitle>
              <CardDescription>
                Sent, opened, replied, and bounced counts for the selected range.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {timeSeriesQ.isLoading ? (
                <Skeleton className="h-64 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={timeSeries}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <RTooltip />
                    <Legend />
                    <Line type="monotone" dataKey="sent" stroke="#8b5cf6" strokeWidth={2} />
                    <Line type="monotone" dataKey="opened" stroke="#3b82f6" strokeWidth={2} />
                    <Line type="monotone" dataKey="replied" stroke="#10b981" strokeWidth={2} />
                    <Line type="monotone" dataKey="bounced" stroke="#f97316" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* AN-2: Campaign Performance table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="h-4 w-4" /> Campaign Performance
              </CardTitle>
              <CardDescription>
                Aggregated send/open/reply/bounce metrics per campaign.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {campaignPerformance.length === 0 ? (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  No campaign metrics yet — metrics populate once sequences start sending.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Campaign</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Sent</TableHead>
                      <TableHead className="text-right">Opened</TableHead>
                      <TableHead className="text-right">Replied</TableHead>
                      <TableHead className="text-right">Bounced</TableHead>
                      <TableHead className="text-right">Open Rate</TableHead>
                      <TableHead className="text-right">Reply Rate</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {campaignPerformance.map((c) => (
                      <TableRow key={c.campaignId}>
                        <TableCell className="font-medium">{c.name}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[10px]">
                            {c.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{c.sent}</TableCell>
                        <TableCell className="text-right tabular-nums">{c.opened}</TableCell>
                        <TableCell className="text-right tabular-nums">{c.replied}</TableCell>
                        <TableCell className="text-right tabular-nums">{c.bounced}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {pct(c.openRate)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {pct(c.replyRate)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* AN-1: Sequence Status Distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Sequence Status Distribution</CardTitle>
                <CardDescription className="text-xs">
                  Current status of all sequenced touches.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {statusDistribution.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-6 text-center">
                    No sequences yet.
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie
                        data={statusDistribution}
                        dataKey="count"
                        nameKey="status"
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label={(entry: { status: string }) => entry.status}
                      >
                        {statusDistribution.map((entry) => (
                          <Cell key={entry.status} fill={entry.fill} />
                        ))}
                      </Pie>
                      <RTooltip />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            {/* AN-3: Sequence Step Performance */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Sequence Step Performance</CardTitle>
                <CardDescription className="text-xs">
                  Open and reply rate by touch number (T1-T7).
                </CardDescription>
              </CardHeader>
              <CardContent>
                {stepPerformance.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-6 text-center">
                    No sent touches yet.
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={stepPerformance}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="touch" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} unit="%" />
                      <RTooltip />
                      <Legend />
                      <Bar dataKey="openRate" name="Open %" fill="#3b82f6" />
                      <Bar dataKey="replyRate" name="Reply %" fill="#10b981" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            {/* AN-5: Copy Angle Performance */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Copy Angle Performance</CardTitle>
                <CardDescription className="text-xs">
                  Reply rate by messaging angle, best first.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {anglePerformance.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-6 text-center">
                    No sent touches yet.
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={anglePerformance} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
                      <YAxis
                        type="category"
                        dataKey="angle"
                        tick={{ fontSize: 11 }}
                        width={110}
                      />
                      <RTooltip />
                      <Bar dataKey="replyRate" name="Reply %" fill="#8b5cf6" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            {/* AN-4: Intent Source Attribution */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Intent Source Attribution</CardTitle>
                <CardDescription className="text-xs">
                  Prospect count and reply contribution by buying-intent
                  source (Prospect.intentSource).
                </CardDescription>
              </CardHeader>
              <CardContent>
                {intentAttribution.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-6 text-center">
                    No prospects yet.
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={intentAttribution} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" tick={{ fontSize: 11 }} />
                      <YAxis
                        type="category"
                        dataKey="source"
                        tick={{ fontSize: 11 }}
                        width={110}
                      />
                      <RTooltip />
                      <Legend />
                      <Bar dataKey="total" name="Prospects" fill="#94a3b8" />
                      <Bar dataKey="replied" name="Replied" fill="#10b981" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          {/* AN-6: Campaign Health Diagnostics */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Activity className="h-4 w-4" /> Campaign Health Diagnostics
              </CardTitle>
              <CardDescription>
                5-layer closed-loop diagnostic across all active campaigns.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {diagnoseQ.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : diagnose ? (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">{diagnose.summary}</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2">
                    {diagnose.layers.map((l) => (
                      <div
                        key={l.layer}
                        className={`rounded-md border p-2.5 text-xs ${
                          l.status === "critical"
                            ? "border-red-300 bg-red-50"
                            : l.status === "warn"
                              ? "border-amber-300 bg-amber-50"
                              : "border-emerald-200 bg-emerald-50"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium capitalize">{l.layer}</span>
                          {l.status === "critical" ? (
                            <AlertTriangle className="h-3.5 w-3.5 text-red-600" />
                          ) : l.status === "warn" ? (
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                          ) : (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                          )}
                        </div>
                        <p className="tabular-nums font-mono">
                          {l.metric}: {l.value}
                          {l.benchmark != null && (
                            <span className="text-muted-foreground"> / {l.benchmark}</span>
                          )}
                        </p>
                        <p className="text-muted-foreground mt-1">{l.note}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  No diagnostic data available yet.
                </p>
              )}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* AN-7: AI Performance Diagnostics */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Bot className="h-4 w-4" /> AI Performance
                </CardTitle>
                <CardDescription className="text-xs">
                  LLM usage/cost this period and QA score distribution.
                  (Generation-time tracking isn't recorded by the backend.)
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {usageQ.isLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : usage && usage.breakdown.length > 0 ? (
                  <div className="space-y-1.5">
                    {usage.breakdown.map((row) => (
                      <div
                        key={`${row.event_type}-${row.provider}`}
                        className="flex items-center justify-between text-xs bg-muted/50 rounded px-2 py-1.5"
                      >
                        <span>
                          {row.event_type}
                          {row.provider ? ` · ${row.provider}` : ""}
                        </span>
                        <span className="tabular-nums text-muted-foreground">
                          {row.event_count} calls · ${(row.total_cost_cents / 100).toFixed(2)}
                        </span>
                      </div>
                    ))}
                    <p className="text-xs font-medium pt-1">
                      Total: ${(usage.total_cost_cents / 100).toFixed(2)}
                    </p>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No usage recorded this period.</p>
                )}

                <div>
                  <p className="text-xs font-medium mb-2">
                    QA Score Distribution
                    {avgQaScore != null && (
                      <span className="text-muted-foreground"> · avg {avgQaScore}</span>
                    )}
                  </p>
                  {scoredCount === 0 ? (
                    <p className="text-xs text-muted-foreground">No QA-scored emails yet.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={140}>
                      <BarChart data={qaDistribution}>
                        <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <RTooltip />
                        <Bar dataKey="count" fill="#3b82f6" />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* AN-8: Industry Benchmarks */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Target className="h-4 w-4" /> Benchmarks
                </CardTitle>
                <CardDescription className="text-xs">
                  Your configured health-diagnostic thresholds (System
                  Parameters → Analytics Benchmarks).
                </CardDescription>
              </CardHeader>
              <CardContent>
                {benchmarksQ.isLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : benchmarks.length === 0 ? (
                  <div className="space-y-2">
                    <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-wide">Industry Averages</p>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { label: "Open Rate",   value: "25–35%", note: "Cold outreach avg" },
                        { label: "Reply Rate",  value: "5–15%",  note: "Cold outreach avg" },
                        { label: "Bounce Rate", value: "< 5%",   note: "Hard bounce target" },
                        { label: "QA Score",    value: "> 70",   note: "Minimum acceptable" },
                      ].map((b) => (
                        <div key={b.label} className="rounded-md border bg-muted/30 p-2 text-center">
                          <p className="text-sm font-bold">{b.value}</p>
                          <p className="text-[10px] font-medium text-muted-foreground">{b.label}</p>
                          <p className="text-[9px] text-muted-foreground/70">{b.note}</p>
                        </div>
                      ))}
                    </div>
                    <p className="text-[10px] text-muted-foreground text-center pt-1">
                      Configure custom thresholds in System Parameters
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {benchmarks.map((b) => (
                      <div key={b.key} className="rounded-md border p-2 text-center">
                        <p className="text-lg font-bold">
                          {b.value}
                          {b.unit?.includes("%") ? "" : ""}
                        </p>
                        <p className="text-[10px] text-muted-foreground">{b.label}</p>
                      </div>
                    ))}
                  </div>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-3 w-full"
                  onClick={() => navigate("/setup/system-params")}
                >
                  Adjust benchmarks in System Parameters
                  <ExternalLink className="h-3 w-3 ml-1.5" />
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* AN-9 / AN-11: Auto-Optimization link-out */}
          <Card className="border-violet-200 bg-violet-50/50">
            <CardContent className="py-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <TrendingUp className="h-5 w-5 text-violet-600 shrink-0" />
                <div>
                  <p className="text-sm font-medium">Auto-Optimization Rules Engine</p>
                  <p className="text-xs text-muted-foreground">
                    Create rules like "if reply rate &lt; 5% for 3+ days, pause
                    campaign" — managed on its own page with full create/edit/delete.
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="shrink-0"
                onClick={() => navigate("/optimize/optimization-rules")}
              >
                Open Optimization Rules
                <ExternalLink className="h-3 w-3 ml-1.5" />
              </Button>
            </CardContent>
          </Card>

          <Card className="p-4 bg-muted/30 border-dashed">
            <div className="flex gap-3">
              <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <p className="text-xs text-muted-foreground">
                Campaign Performance and the time-series chart reflect data
                across all campaigns for the selected range. Sequence-derived
                charts (status, step, angle, intent) are computed from the
                most recent 500 sequences and 500 prospects.
              </p>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}