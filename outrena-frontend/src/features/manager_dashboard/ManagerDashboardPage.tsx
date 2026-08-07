/**
 * ManagerDashboardPage.tsx — team dashboard for MANAGER+ users.
 *
 * Mounted at `/manager-dashboard` (MANAGER+). Fetches
 * `GET /api/v1/dashboard/manager` → team totals + per-user rows + at-risk +
 * top performers. Renders:
 *   - Team summary StatCards (users, emails sent, campaigns active, pipeline)
 *   - Per-user table: name, emails sent, campaigns active, prospects, replies,
 *     meetings, quota %, at-risk badge
 *   - Top performers section + at-risk users section
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarCheck,
  Mail,
  Reply,
  Send,
  Trophy,
  Users2,
} from "lucide-react";
import { managerDashboardApi } from "@/services/apiClient";
import { ErrorState } from "@/components/ui/error-state";
import type { ManagerDashboard, ManagerTeamMember } from "@/types/common";
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
import { cn, formatCurrency, initials } from "@/lib/utils";

const MOCK: ManagerDashboard = {
  team_totals: {
    total_users: 12,
    total_emails_sent: 28_410,
    total_campaigns_active: 18,
    total_pipeline_value: 2_140_000,
    total_meetings: 86,
    total_replies: 1_082,
  },
  members: [
    {
      user_id: "u-1",
      user_name: "Amelia Chen",
      emails_sent: 4_120,
      campaigns_active: 3,
      prospects_contacted: 312,
      replies_received: 184,
      meetings_booked: 22,
      quota_used_pct: 68,
      is_at_risk: false,
    },
    {
      user_id: "u-2",
      user_name: "Marcus Lee",
      emails_sent: 3_890,
      campaigns_active: 2,
      prospects_contacted: 268,
      replies_received: 142,
      meetings_booked: 18,
      quota_used_pct: 84,
      is_at_risk: false,
    },
    {
      user_id: "u-3",
      user_name: "Priya Nair",
      emails_sent: 2_120,
      campaigns_active: 2,
      prospects_contacted: 198,
      replies_received: 96,
      meetings_booked: 11,
      quota_used_pct: 95,
      is_at_risk: true,
    },
    {
      user_id: "u-4",
      user_name: "Diego Santos",
      emails_sent: 1_840,
      campaigns_active: 1,
      prospects_contacted: 162,
      replies_received: 74,
      meetings_booked: 8,
      quota_used_pct: 42,
      is_at_risk: false,
    },
    {
      user_id: "u-5",
      user_name: "Yuki Tanaka",
      emails_sent: 980,
      campaigns_active: 1,
      prospects_contacted: 84,
      replies_received: 28,
      meetings_booked: 3,
      quota_used_pct: 22,
      is_at_risk: false,
    },
    {
      user_id: "u-6",
      user_name: "Sam Rivera",
      emails_sent: 4_410,
      campaigns_active: 4,
      prospects_contacted: 348,
      replies_received: 198,
      meetings_booked: 24,
      quota_used_pct: 71,
      is_at_risk: false,
    },
  ],
  top_performers: [],
  at_risk_users: [],
};

function quotaVariant(pct: number) {
  if (pct >= 90) return "destructive" as const;
  if (pct >= 75) return "warning" as const;
  return "success" as const;
}

function quotaBarClass(pct: number) {
  if (pct >= 90) return "bg-red-600";
  if (pct >= 75) return "bg-amber-500";
  return "bg-emerald-600";
}

export function ManagerDashboardPage() {
  const { data, isLoading , isError, error, refetch } = useQuery({
    queryKey: ["dashboard", "manager"],
    queryFn: () => managerDashboardApi.manager(),
  });

  const dashboard = data ?? MOCK;
  const totals = dashboard.team_totals;
  const members = dashboard.members ?? [];
  const topPerformers =
    dashboard.top_performers?.length > 0
      ? dashboard.top_performers
      : [...members]
          .sort((a, b) => b.meetings_booked - a.meetings_booked)
          .slice(0, 3);
  const atRisk =
    dashboard.at_risk_users?.length > 0
      ? dashboard.at_risk_users
      : members.filter((m) => m.is_at_risk);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Team Dashboard"
        description="Per-user activity, quota, and pipeline momentum for your team."
      />

{/* Task 2-b finding 14: explicit error + retry state */}
        {isError ? (
          <ErrorState
            title="Failed to load team dashboard"
            error={error}
            onRetry={() => refetch()}
          />
        ) : null}

              {/* Team summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))
        ) : (
          <>
            <StatCard
              label="Team members"
              value={totals.total_users.toLocaleString()}
              icon={<Users2 className="h-4 w-4" />}
            />
            <StatCard
              label="Emails sent (all-time)"
              value={totals.total_emails_sent.toLocaleString()}
              icon={<Send className="h-4 w-4" />}
            />
            <StatCard
              label="Active campaigns"
              value={totals.total_campaigns_active.toLocaleString()}
              icon={<Mail className="h-4 w-4" />}
            />
            <StatCard
              label="Pipeline value"
              value={formatCurrency(totals.total_pipeline_value)}
              icon={<Trophy className="h-4 w-4" />}
            />
          </>
        )}
      </div>

      {/* Top performers + at-risk */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trophy className="h-4 w-4" />
              Top Performers
            </CardTitle>
            <CardDescription>By meetings booked this period.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {topPerformers.length === 0 ? (
              <EmptyState
                title="No data yet"
                description="Team performance will appear here once members start booking meetings."
              />
            ) : (
              topPerformers.map((m, idx) => (
                <PerformerRow key={m.user_id} member={m} rank={idx + 1} />
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              At-Risk Users
            </CardTitle>
            <CardDescription>
              Near quota limit or high bounce / complaint rate.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {atRisk.length === 0 ? (
              <EmptyState
                title="No at-risk users"
                description="Everyone is within healthy send limits."
              />
            ) : (
              atRisk.map((m) => (
                <div
                  key={m.user_id}
                  className="flex items-center justify-between rounded-md border border-amber-500/40 bg-amber-500/5 p-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 text-xs font-semibold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                      {initials(m.user_name)}
                    </div>
                    <div>
                      <p className="text-sm font-medium">{m.user_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {m.quota_used_pct.toFixed(0)}% quota used ·{" "}
                        {m.emails_sent.toLocaleString()} sent
                      </p>
                    </div>
                  </div>
                  <Badge variant="warning">At risk</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Per-user table */}
      <Card>
        <CardHeader>
          <CardTitle>Team Members</CardTitle>
          <CardDescription>
            Per-user activity, reply + meeting volume, and quota health.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : members.length === 0 ? (
            <EmptyState
              icon={<Users2 className="h-6 w-6" />}
              title="No team members"
              description="Invite reps via User Management to populate this view."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Member</TableHead>
                  <TableHead className="text-right">Emails</TableHead>
                  <TableHead className="text-right">Campaigns</TableHead>
                  <TableHead className="text-right">Prospects</TableHead>
                  <TableHead className="text-right">Replies</TableHead>
                  <TableHead className="text-right">Meetings</TableHead>
                  <TableHead className="w-40">Quota used</TableHead>
                  <TableHead className="text-right">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.user_id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                          {initials(m.user_name)}
                        </div>
                        <span className="font-medium">{m.user_name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {m.emails_sent.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {m.campaigns_active}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {m.prospects_contacted.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <span className="inline-flex items-center gap-1">
                        <Reply className="h-3 w-3 text-muted-foreground" />
                        {m.replies_received}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <span className="inline-flex items-center gap-1">
                        <CalendarCheck className="h-3 w-3 text-muted-foreground" />
                        {m.meetings_booked}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <Progress
                          value={m.quota_used_pct}
                          indicatorClassName={cn(quotaBarClass(m.quota_used_pct))}
                        />
                        <p className="text-xs text-muted-foreground">
                          {m.quota_used_pct.toFixed(0)}%
                        </p>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant={quotaVariant(m.quota_used_pct)}>
                        {m.is_at_risk ? "At risk" : "Healthy"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function PerformerRow({
  member,
  rank,
}: {
  member: ManagerTeamMember;
  rank: number;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div className="flex items-center gap-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
          #{rank}
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
          {initials(member.user_name)}
        </div>
        <div>
          <p className="text-sm font-medium">{member.user_name}</p>
          <p className="text-xs text-muted-foreground">
            {member.meetings_booked} meetings · {member.replies_received} replies
          </p>
        </div>
      </div>
      <Badge variant="success">{member.emails_sent.toLocaleString()} sent</Badge>
    </div>
  );
}
