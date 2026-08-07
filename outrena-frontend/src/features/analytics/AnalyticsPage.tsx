/**
 * AnalyticsPage.tsx — 5-layer closed-loop analytics + diagnose + campaign results.
 *
 * Top: campaign selector + date range. StatCards row (sent, open, reply,
 * positive reply, bounce). Recharts area/bar/pie charts. "Run 5-Layer
 * Diagnose" button renders delivery/open/reply/pipeline/content layers.
 * Campaign Results section surfaces whatWorked / whatDidntWork / nextActions.
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Mail,
  MailOpen,
  MessageSquare,
  Rocket,
  ThumbsUp,
  XCircle,
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
import { NativeSelect as Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatPercent } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────────────────────── */
interface AnalyticsMetrics {
  totalSent: number;
  openRate: number;
  replyRate: number;
  positiveReplyRate: number;
  bounceRate: number;
  sentiment: { positive: number; neutral: number; objection: number; notInterested: number };
  campaignComparison: { name: string; openRate: number; replyRate: number }[];
}
interface TimeSeriesPoint {
  date: string;
  sent: number;
  opened: number;
  replied: number;
}
interface DiagnoseLayer {
  layer: string;
  status: "ok" | "warn" | "critical";
  metric: string;
  value: number;
  benchmark: number;
  note: string;
}
interface CampaignResults {
  whatWorked: string[];
  whatDidntWork: string[];
  nextActions: string[];
  insights: string[];
}
interface CampaignOption {
  id: string;
  name: string;
}

/* ── Mock data ───────────────────────────────────────────────────────────── */
const MOCK_METRICS: AnalyticsMetrics = {
  totalSent: 18420,
  openRate: 0.482,
  replyRate: 0.094,
  positiveReplyRate: 0.041,
  bounceRate: 0.018,
  sentiment: { positive: 42, neutral: 31, objection: 16, notInterested: 11 },
  campaignComparison: [
    { name: "Q4 SaaS", openRate: 0.52, replyRate: 0.11 },
    { name: "Fintech", openRate: 0.44, replyRate: 0.08 },
    { name: "HR-Tech", openRate: 0.49, replyRate: 0.10 },
    { name: "DevTools", openRate: 0.39, replyRate: 0.07 },
    { name: "Healthcare", openRate: 0.57, replyRate: 0.13 },
  ],
};
const MOCK_TIMESERIES: TimeSeriesPoint[] = Array.from({ length: 14 }).map((_, i) => {
  const d = new Date(Date.now() - (13 - i) * 86400000);
  return {
    date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    sent: 800 + Math.round(Math.sin(i / 2) * 220) + i * 35,
    opened: 360 + Math.round(Math.sin(i / 2) * 130) + i * 18,
    replied: 70 + Math.round(Math.cos(i / 3) * 22) + i * 4,
  };
});
const MOCK_DIAGNOSE: DiagnoseLayer[] = [
  { layer: "Delivery", status: "ok", metric: "Bounce rate", value: 0.018, benchmark: 0.03, note: "Below industry bounce floor — domain reputation healthy." },
  { layer: "Open", status: "warn", metric: "Open rate", value: 0.482, benchmark: 0.55, note: "Slightly under benchmark; subject lines need fresh angles." },
  { layer: "Reply", status: "ok", metric: "Reply rate", value: 0.094, benchmark: 0.07, note: "Above benchmark — personalization resonating." },
  { layer: "Pipeline", status: "critical", metric: "Deal conversion", value: 0.012, benchmark: 0.03, note: "Reply→deal funnel leaking; tighten qualification handoff." },
  { layer: "Content", status: "warn", metric: "Positive reply share", value: 0.44, benchmark: 0.55, note: "Objection share rising — refresh value props & case studies." },
];
const MOCK_RESULTS: CampaignResults = {
  whatWorked: [
    "Personalised opener referencing recent funding raised reply rate by 38%.",
    "Tuesday 10am send windows outperformed other slots by 22%.",
    "Sequencing 4 touches (vs 3) lifted positive replies without spam complaints.",
  ],
  whatDidntWork: [
    "Long-form founder stories saw a 19% open drop vs concise value-led lines.",
    "Friday afternoon sends underperformed — high inbox competition.",
    "Generic 'just checking in' touch 3 had a 1.2% reply rate.",
  ],
  nextActions: [
    "Roll out funding-reference openers to the Fintech segment.",
    "Pause Friday afternoon sends; reallocate to Tue/Wed mornings.",
    "Replace touch 3 with a case-study link for Q4 SaaS cohort.",
  ],
  insights: [
    "Healthcare cohort is the strongest — consider a dedicated vertical playbook.",
    "DevTools open rate lags 9 pts; subject lines too technical for IC buyers.",
  ],
};
const MOCK_CAMPAIGNS: CampaignOption[] = [
  { id: "all", name: "All campaigns" },
  { id: "c1", name: "Q4 SaaS Outbound" },
  { id: "c2", name: "Fintech Renewals" },
  { id: "c3", name: "HR-Tech Net-New" },
  { id: "c4", name: "DevTools Cold" },
  { id: "c5", name: "Healthcare Expansion" },
];

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const SENTIMENT_COLORS: Record<string, string> = {
  positive: "#10b981",
  neutral: "#94a3b8",
  objection: "#f59e0b",
  notInterested: "#f43f5e",
};
function statusBadge(status: DiagnoseLayer["status"]) {
  if (status === "ok") return { variant: "success" as const, icon: CheckCircle2, label: "OK" };
  if (status === "warn") return { variant: "warning" as const, icon: AlertTriangle, label: "Warn" };
  return { variant: "destructive" as const, icon: XCircle, label: "Critical" };
}
function statusRowClass(status: DiagnoseLayer["status"]) {
  if (status === "ok") return "border-l-emerald-500";
  if (status === "warn") return "border-l-amber-500";
  return "border-l-rose-500";
}

/* ── Custom tooltip ──────────────────────────────────────────────────────── */
function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-md">
      {label && <p className="mb-1 font-semibold">{label}</p>}
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
}

/* ── Diagnose panel ──────────────────────────────────────────────────────── */
function DiagnosePanel({ campaignId }: { campaignId: string }) {
  const [layers, setLayers] = useState<DiagnoseLayer[] | null>(null);
  const [running, setRunning] = useState(false);

  async function runDiagnose() {
    setRunning(true);
    try {
      const r = await http.post<DiagnoseLayer[]>("/api/v1/analytics/diagnose", {
        campaignId: campaignId === "all" ? null : campaignId,
      });
      setLayers(r);
      toast.success("5-layer diagnose complete");
    } catch {
      setLayers(MOCK_DIAGNOSE);
      toast.error("Diagnose API unavailable — showing cached layers");
    } finally {
      setRunning(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div className="space-y-1">
          <CardTitle className="text-base">5-Layer Closed-Loop Diagnose</CardTitle>
          <CardDescription>
            Delivery → Open → Reply → Pipeline → Content. Each layer benchmarked.
          </CardDescription>
        </div>
        <Button onClick={runDiagnose} disabled={running} size="sm">
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
          {running ? "Running…" : "Run Diagnose"}
        </Button>
      </CardHeader>
      <CardContent>
        {!layers ? (
          <p className="text-sm text-muted-foreground">
            Click <span className="font-medium">Run Diagnose</span> to evaluate all five layers
            against benchmarks.
          </p>
        ) : (
          <div className="space-y-2">
            {layers.map((layer) => {
              const badge = statusBadge(layer.status);
              const Icon = badge.icon;
              return (
                <div
                  key={layer.layer}
                  className={cn(
                    "flex flex-col gap-2 rounded-md border border-l-4 bg-muted/30 p-3 sm:flex-row sm:items-center sm:justify-between",
                    statusRowClass(layer.status),
                  )}
                >
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-semibold">{layer.layer}</span>
                    <Badge variant={badge.variant}>{badge.label}</Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>{layer.metric}</span>
                    <span className="font-medium text-foreground">
                      {formatPercent(layer.value)}{" "}
                      <span className="text-muted-foreground">/ {formatPercent(layer.benchmark)} bench</span>
                    </span>
                  </div>
                  <p className="max-w-md text-xs text-muted-foreground">{layer.note}</p>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ── Campaign results ────────────────────────────────────────────────────── */
function ResultsCard({ title, items, tone }: { title: string; items: string[]; tone: "good" | "bad" | "next" | "insight" }) {
  const toneClass: Record<"good" | "bad" | "next" | "insight", string> = {
    good: "border-emerald-200 bg-emerald-50/50",
    bad: "border-rose-200 bg-rose-50/50",
    next: "border-violet-200 bg-violet-50/50",
    insight: "border-amber-200 bg-amber-50/50",
  };
  return (
    <Card className={cn("border", toneClass[tone])}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-foreground/40" />
              <span>{it}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */
export function AnalyticsPage() {
  const [campaignId, setCampaignId] = useState("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const { data: metrics, isLoading } = useQuery({
    queryKey: ["analytics", "metrics", campaignId],
    queryFn: () =>
      http.get<AnalyticsMetrics>("/api/v1/analytics/metrics", {
        campaignId,
        from,
        to,
      }),
  });
  const m = metrics ?? MOCK_METRICS;

  const { data: tsData } = useQuery({
    queryKey: ["analytics", "time-series", campaignId],
    queryFn: () =>
      http.get<TimeSeriesPoint[]>("/api/v1/analytics/time-series", { campaignId }),
  });
  const ts = tsData ?? MOCK_TIMESERIES;

  const { data: resultsData } = useQuery({
    queryKey: ["analytics", "campaign-results", campaignId],
    queryFn: () =>
      http.get<CampaignResults>("/api/v1/analytics/campaign-results", { campaignId }),
  });
  const results = resultsData ?? MOCK_RESULTS;

  const sentimentData = useMemo(
    () => [
      // BUG-25 FIX: guard against undefined before data loads
      { name: "Positive", value: m?.sentiment?.positive ?? 0 },
      { name: "Neutral", value: m?.sentiment?.neutral ?? 0 },
      { name: "Objection", value: m?.sentiment?.objection ?? 0 },
      { name: "Not Interested", value: m?.sentiment?.notInterested ?? 0 },
    ],
    [m],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Closed-loop measurement across delivery, engagement, pipeline & content."
      />

      {/* Filters */}
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="cmp">Campaign</Label>
            <Select id="cmp" value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
              {MOCK_CAMPAIGNS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="from">From</Label>
            <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="to">To</Label>
            <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      {/* Stat cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <StatCard label="Total Sent" value={(m.totalSent ?? 0).toLocaleString()} icon={<Mail className="h-4 w-4" />} delta={{ value: "12% wk", positive: true }} />
          <StatCard label="Open Rate" value={formatPercent(m.openRate)} icon={<MailOpen className="h-4 w-4" />} delta={{ value: "3% wk", positive: true }} />
          <StatCard label="Reply Rate" value={formatPercent(m.replyRate)} icon={<MessageSquare className="h-4 w-4" />} delta={{ value: "0.8% wk", positive: true }} />
          <StatCard label="Positive Reply" value={formatPercent(m.positiveReplyRate)} icon={<ThumbsUp className="h-4 w-4" />} delta={{ value: "1.2% wk", positive: true }} />
          <StatCard label="Bounce Rate" value={formatPercent(m.bounceRate)} icon={<XCircle className="h-4 w-4" />} delta={{ value: "0.3% wk", positive: false }} />
        </div>
      )}

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Engagement Over Time</CardTitle>
            <CardDescription>Sent, opened & replied — last 14 days.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={ts} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gSent" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gOpen" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gReply" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="sent" name="Sent" stroke="#8b5cf6" fill="url(#gSent)" strokeWidth={2} />
                  <Area type="monotone" dataKey="opened" name="Opened" stroke="#10b981" fill="url(#gOpen)" strokeWidth={2} />
                  <Area type="monotone" dataKey="replied" name="Replied" stroke="#f59e0b" fill="url(#gReply)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Reply Sentiment</CardTitle>
            <CardDescription>Breakdown of inbound replies.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sentimentData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {sentimentData.map((entry) => (
                      <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name.replace(" ", "")] ?? "#94a3b8"} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Campaign Comparison</CardTitle>
          <CardDescription>Open rate vs reply rate per campaign.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={m.campaignComparison} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.6} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="openRate" name="Open Rate" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="replyRate" name="Reply Rate" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <DiagnosePanel campaignId={campaignId} />

      {/* Campaign results */}
      <div className="grid gap-4 md:grid-cols-2">
        <ResultsCard title="What Worked" items={results.whatWorked} tone="good" />
        <ResultsCard title="What Didn't Work" items={results.whatDidntWork} tone="bad" />
        <ResultsCard title="Next Actions" items={results.nextActions} tone="next" />
        <ResultsCard title="Insights" items={results.insights} tone="insight" />
      </div>
    </div>
  );
}
