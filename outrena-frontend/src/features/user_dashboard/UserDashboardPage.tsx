/**
 * UserDashboardPage.tsx — personal dashboard for the logged-in user.
 *
 * Mounted at `/` inside <AppLayout>. Replaces the legacy DashboardPage as the
 * signed-in landing route. Fetches `GET /api/v1/dashboard?user_id=me` (the
 * backend forces REPs to their own data) and renders:
 *   - 4 StatCards: emails sent (7d), replies (7d), meetings booked (7d), pipeline value
 *   - Email quota card: emails sent today / daily quota, progress bar, throttled warning
 *   - My campaigns: active count + list (top 5)
 *   - My sender identities: count + default email
 *   - Recent activity chart: 7-day emails/replies/meetings
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CalendarCheck,
  CheckCircle2,
  ChevronRight,
  Mail,
  Reply,
  Send,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Users2,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { managerDashboardApi, senderIdentityApi } from "@/services/apiClient";
import { ErrorState } from "@/components/ui/error-state";
import type { UserDashboard } from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/ui/empty-state";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { http } from "@/services/apiClient";

/* ── Onboarding checklist types ─────────────────────────────────────────── */

interface ChecklistItem {
  key: string;
  label: string;
  description: string;
  link: string;
  order: number;
  done: boolean;
}

interface ChecklistData {
  items: ChecklistItem[];
  completed: number;
  total: number;
  all_done: boolean;
}

const MOCK_DASHBOARD: UserDashboard = {
  user_id: "me",
  user_name: "Dev Rep",
  campaigns: {
    active_count: 3,
    items: [
      { id: "c1", name: "Q1 SaaS Founder Outreach", status: "Active", prospect_count: 248 },
      { id: "c2", name: "Series B VP Eng — Competitor Switch", status: "Active", prospect_count: 134 },
      { id: "c3", name: "DTC Operator Roadshow", status: "Paused", prospect_count: 92 },
      { id: "c4", name: "Healthcare CISO Refresh", status: "Active", prospect_count: 76 },
      { id: "c5", name: "Fintech Compliance Leaders", status: "Draft", prospect_count: 0 },
    ],
  },
  email_quota: {
    date: new Date().toISOString().slice(0, 10),
    emails_sent: 412,
    daily_quota: 1000,
    remaining: 588,
    emails_bounced: 8,
    complaints: 0,
    is_throttled: false,
    throttled_until: null,
  },
  sender_identities: {
    total: 2,
    default_email: "dev.rep@outrena.io",
  },
  recent_activity: {
    emails_sent_7d: 2840,
    replies_received_7d: 218,
    meetings_booked_7d: 14,
    daily: [
      { date: "2025-02-06", emails_sent: 320, replies: 28, meetings: 1 },
      { date: "2025-02-07", emails_sent: 412, replies: 33, meetings: 2 },
      { date: "2025-02-08", emails_sent: 380, replies: 29, meetings: 1 },
      { date: "2025-02-09", emails_sent: 502, replies: 41, meetings: 3 },
      { date: "2025-02-10", emails_sent: 478, replies: 36, meetings: 2 },
      { date: "2025-02-11", emails_sent: 396, replies: 26, meetings: 2 },
      { date: "2025-02-12", emails_sent: 352, replies: 25, meetings: 3 },
    ],
  },
  prospects_contacted: 842,
  pipeline_value: 412_500,
};

export function UserDashboardPage() {
  // Gate every query on `initialized` (set by AuthProvider once the dev-bypass
  // or Keycloak session has resolved and setAccessToken() has run). Without
  // this, React's child-before-parent effect ordering means this page's
  // query effect can fire before AuthProvider's own effect sets the Bearer
  // token, sending the very first request with no Authorization header —
  // which the backend correctly rejects as "Tenant not identified" (400).
  const { initialized, isAuthenticated } = useAuth();

  // INFINITE-LOOP FIX: gate on BOTH `initialized` AND `isAuthenticated`.
  // Gating on `initialized` alone is insufficient: if Keycloak resolves the
  // session but the backend still returns 401 (missing tenant_slug claim,
  // TenantMiddleware failure, etc.), these queries fire → 401 → login
  // redirect → return → initialized=true → queries fire again → ∞.
  // Adding `isAuthenticated` ensures queries only fire when we have a valid
  // user object (i.e. `applyToken` succeeded and produced a non-null user),
  // and stop firing after the circuit breaker in AuthContext halts re-login.
  const queryEnabled = initialized && isAuthenticated;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dashboard", "me"],
    queryFn: () => managerDashboardApi.mine(),
    enabled: queryEnabled,
    // Do not retry on 401 — retrying will just re-trigger the 401 loop.
    retry: (failureCount, err) => {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401 || status === 403) return false;
      return failureCount < 1;
    },
  });

  // Also fetch the live email quota + sender identities so the cards stay
  // fresh when the user navigates here. These come from per-user endpoints
  // (Workstream 2). Falls back gracefully to the dashboard rollup on error.
  const { data: quota } = useQuery({
    queryKey: ["users", "me", "email-quota"],
    queryFn: () => senderIdentityApi.myQuota(),
    enabled: queryEnabled,
    retry: (failureCount, err) => {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401 || status === 403) return false;
      return failureCount < 1;
    },
  });

  // Onboarding checklist progress (Help Guide §Dashboard: "live progress bar (% onboarded)")
  const navigate = useNavigate();
  const { data: onboarding } = useQuery<ChecklistData>({
    queryKey: ["onboarding-checklist"],
    queryFn: () => http.get("/api/v1/onboarding/checklist"),
    enabled: queryEnabled,
    staleTime: 60_000,
  });

  const EMPTY_ACTIVITY = {
    emails_sent_7d: 0,
    replies_received_7d: 0,
    meetings_booked_7d: 0,
    daily: [] as { date: string; emails_sent: number; replies: number; meetings: number }[],
  };
  const EMPTY_DASHBOARD: UserDashboard = {
    user_id: "me",
    user_name: "",
    campaigns: { active_count: 0, items: [] },
    email_quota: {
      date: new Date().toISOString().slice(0, 10),
      emails_sent: 0,
      daily_quota: 1000,
      remaining: 1000,
      emails_bounced: 0,
      complaints: 0,
      is_throttled: false,
      throttled_until: null,
    },
    sender_identities: { total: 0, default_email: null },
    recent_activity: EMPTY_ACTIVITY,
    prospects_contacted: 0,
    pipeline_value: 0,
  };

  // Defensive merge: the live backend response may not (yet) include every
  // section the UI expects — e.g. a freshly-provisioned tenant with no send
  // history, or a dashboard contract that's still evolving server-side.
  // Merging over EMPTY_DASHBOARD (rather than using `data` directly, and
  // rather than falling back to MOCK_DASHBOARD's fabricated numbers once we
  // have a real — even if empty — response) means every field access below
  // is always safe, and a real empty tenant correctly shows zeros instead
  // of a crash or misleading mock data.
  const dashboard: UserDashboard = data
    ? { ...EMPTY_DASHBOARD, ...data }
    : MOCK_DASHBOARD;
  const quotaCard = quota ?? dashboard.email_quota;
  const activity = dashboard.recent_activity ?? EMPTY_ACTIVITY;
  const quotaPct = quotaCard
    ? Math.min(100, (quotaCard.emails_sent / Math.max(1, quotaCard.daily_quota)) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, ${dashboard.user_name || ""}`}
        description="Your outreach activity, quota, and pipeline momentum at a glance."
      />

{/* Task 2-b finding 14: explicit error + retry state */}
      {isError ? (
        <ErrorState
          title="Failed to load dashboard"
          error={error}
          onRetry={() => refetch()}
        />
      ) : null}

      {/* Onboarding progress card — Help Guide §Dashboard: "% onboarded" */}
      {onboarding && !onboarding.all_done && (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-primary" />
                Onboarding Progress
              </CardTitle>
              <Badge variant="secondary" className="text-xs">
                {Math.round((onboarding.completed / Math.max(1, onboarding.total)) * 100)}% onboarded
              </Badge>
            </div>
            <CardDescription>
              Complete these steps to get fully set up.
            </CardDescription>
            <Progress
              value={(onboarding.completed / Math.max(1, onboarding.total)) * 100}
              className="mt-2 h-2"
            />
          </CardHeader>
          <CardContent className="space-y-1">
            {onboarding.items.map((item) => (
              <button
                key={item.key}
                onClick={() => !item.done && navigate(item.link)}
                disabled={item.done}
                className={cn(
                  "w-full flex items-center gap-3 rounded-md px-3 py-2 text-left transition-colors",
                  item.done
                    ? "opacity-50 cursor-default"
                    : "hover:bg-accent cursor-pointer"
                )}
              >
                {item.done ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                ) : (
                  <div className="flex h-4 w-4 items-center justify-center rounded-full border-2 border-muted-foreground/30 shrink-0">
                    <span className="text-[9px] font-semibold text-muted-foreground">{item.order}</span>
                  </div>
                )}
                <span className={cn("text-sm", item.done && "line-through text-muted-foreground")}>
                  {item.label}
                </span>
                {!item.done && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground ml-auto shrink-0" />}
              </button>
            ))}
          </CardContent>
        </Card>
      )}

            {/* KPI tiles */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))
        ) : (
          <>
            <StatCard
              label="Emails sent (7d)"
              value={activity.emails_sent_7d.toLocaleString()}
              icon={<Send className="h-4 w-4" />}
              delta={{ value: "rolling 7-day window", positive: true }}
            />
            <StatCard
              label="Replies (7d)"
              value={activity.replies_received_7d.toLocaleString()}
              icon={<Reply className="h-4 w-4" />}
              delta={{
                value: `${((activity.replies_received_7d / Math.max(1, activity.emails_sent_7d)) * 100).toFixed(1)}% reply rate`,
                positive: true,
              }}
            />
            <StatCard
              label="Meetings booked (7d)"
              value={activity.meetings_booked_7d.toLocaleString()}
              icon={<CalendarCheck className="h-4 w-4" />}
              delta={{ value: "rolling 7-day window", positive: true }}
            />
            <StatCard
              label="Pipeline value"
              value={formatCurrency(dashboard.pipeline_value)}
              icon={<TrendingUp className="h-4 w-4" />}
              delta={{ value: "from active deals", positive: true }}
            />
          </>
        )}
      </div>

      {/* Email quota + recent activity chart */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Today's Email Quota
            </CardTitle>
            <CardDescription>{formatDate(quotaCard.date)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex items-end justify-between">
                <span className="text-3xl font-bold tabular-nums">
                  {quotaCard.emails_sent}
                </span>
                <span className="text-sm text-muted-foreground">
                  of {quotaCard.daily_quota} / day
                </span>
              </div>
              <Progress
                value={quotaPct}
                className="mt-2"
                indicatorClassName={cn(
                  quotaPct > 90
                    ? "bg-red-600"
                    : quotaPct > 75
                      ? "bg-amber-500"
                      : "bg-emerald-600",
                )}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                {quotaCard.remaining} remaining · {quotaPct.toFixed(0)}% used
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md border p-2.5">
                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                  Bounces
                </p>
                <p className="mt-0.5 font-semibold">{quotaCard.emails_bounced}</p>
              </div>
              <div className="rounded-md border p-2.5">
                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                  Complaints
                </p>
                <p className="mt-0.5 font-semibold">{quotaCard.complaints}</p>
              </div>
            </div>
            {quotaCard.is_throttled && (
              <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
                <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <p>
                  You are throttled until{" "}
                  <strong>{formatDate(quotaCard.throttled_until)}</strong>.
                  Reduce send volume or contact your admin.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent Activity (7 days)</CardTitle>
            <CardDescription>
              Daily breakdown of emails sent, replies, and meetings booked.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={activity.daily} margin={{ left: -12, right: 12, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v: string) => v.slice(5)}
                    stroke="#94a3b8"
                  />
                  <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#ffffff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="emails_sent" name="Emails sent" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="replies" name="Replies" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="meetings" name="Meetings" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* My campaigns + sender identities */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div className="space-y-1">
              <CardTitle>My Campaigns</CardTitle>
              <CardDescription>
                {dashboard.campaigns.active_count} active ·{" "}
                {dashboard.campaigns.items.length} total
              </CardDescription>
            </div>
            <Link
              to="/outreach/campaigns"
              className="inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              View all
            </Link>
          </CardHeader>
          <CardContent>
            {dashboard.campaigns.items.length === 0 ? (
              <EmptyState
                icon={<Mail className="h-6 w-6" />}
                title="No campaigns yet"
                description="Create your first campaign to start prospecting."
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Campaign</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Prospects</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(Array.isArray(dashboard.campaigns.items) ? dashboard.campaigns.items : []).slice(0, 5).map((c) => (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">{c.name}</TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            c.status === "Active"
                              ? "success"
                              : c.status === "Paused"
                                ? "warning"
                                : "secondary"
                          }
                        >
                          {c.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {c.prospect_count.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users2 className="h-4 w-4" />
              Sender Identities
            </CardTitle>
            <CardDescription>Your sending addresses.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-3xl font-bold">{dashboard.sender_identities.total}</p>
              <p className="text-xs text-muted-foreground">
                identities configured
              </p>
            </div>
            <div className="rounded-md border p-3 text-sm">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">
                Default sender
              </p>
              <p className="mt-0.5 truncate font-mono text-xs">
                {dashboard.sender_identities.default_email ?? "—"}
              </p>
            </div>
            <Link
              to="/setup/sender-identities"
              className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors hover:bg-accent"
            >
              Manage sender identities
            </Link>
            <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Prospects contacted</p>
              <p className="mt-0.5 text-lg font-bold">
                {dashboard.prospects_contacted.toLocaleString()}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}