/**
 * SignalsFeedPage.tsx — Dedicated signals feed at /prospecting/signals.
 *
 * PRD §9.2 lists /prospecting/signals as a separate route from /prospecting/lead-score.
 * This page shows the real-time signals feed (job changes, competitor mentions,
 * funding events, content engagement). The full scoring/monitors UI remains at
 * /prospecting/lead-score as before — this page deep-links to the Signals tab.
 */
import { useQuery } from "@tanstack/react-query";
import { Activity, TrendingUp, Briefcase, Trophy, Linkedin, Zap } from "lucide-react";
import { http } from "@/services/apiClient";
import { PageHeader } from "@/components/ui/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "react-router-dom";
import { timeAgo } from "@/lib/utils";

const SIGNAL_ICONS: Record<string, React.ReactNode> = {
  job_change: <Briefcase className="h-4 w-4 text-blue-500" />,
  competitor_mention: <Trophy className="h-4 w-4 text-amber-500" />,
  funding: <TrendingUp className="h-4 w-4 text-emerald-500" />,
  hiring: <Activity className="h-4 w-4 text-violet-500" />,
  content_engagement: <Zap className="h-4 w-4 text-rose-500" />,
  linkedin_activity: <Linkedin className="h-4 w-4 text-sky-500" />,
};

const STRENGTH_COLOR = (s: number) =>
  s >= 80 ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400"
  : s >= 50 ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
  : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400";

export function SignalsFeedPage() {
  const { data, isLoading } = useQuery<{ items: any[]; total: number }>({
    queryKey: ["signals-feed"],
    queryFn: () => http.get("/api/v1/signals", { limit: 50, offset: 0 }),
    refetchInterval: 60_000, // refresh every minute
  });

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader
        title="Signals Feed"
        description="Real-time buying signals detected across your prospects — job changes, competitor mentions, funding events, and more."
      />

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data?.total ?? 0} signals detected · Auto-refreshes every minute
        </p>
        <Link
          to="/prospecting/lead-score"
          className="text-sm text-primary underline underline-offset-2"
        >
          Configure monitors & lead scoring →
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      ) : !data?.items?.length ? (
        <EmptyState
          title="No signals yet"
          description="Set up signal monitors on the Lead Score page to start detecting buying intent."
          action={
            <Link to="/prospecting/lead-score">
              <span className="text-sm text-primary underline underline-offset-2">
                Go to Lead Score & Monitors →
              </span>
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {(Array.isArray(data.items) ? data.items : []).map((signal: any) => (
            <Card key={signal.id} className="hover:shadow-sm transition-shadow">
              <CardContent className="flex items-start gap-4 p-4">
                <div className="mt-0.5 shrink-0">
                  {SIGNAL_ICONS[signal.type] ?? <Activity className="h-4 w-4 text-muted-foreground" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium capitalize">
                      {signal.type?.replace(/_/g, " ")}
                    </span>
                    <Badge className={`text-xs ${STRENGTH_COLOR(signal.strength ?? 0)}`}>
                      {signal.strength ?? 0}/100
                    </Badge>
                    {signal.source && (
                      <Badge variant="outline" className="text-xs">{signal.source}</Badge>
                    )}
                  </div>
                  {signal.metadata && typeof signal.metadata === "object" && (
                    <p className="text-xs text-muted-foreground mt-1 truncate">
                      {JSON.stringify(signal.metadata).slice(0, 120)}
                    </p>
                  )}
                </div>
                <div className="text-xs text-muted-foreground shrink-0">
                  {timeAgo(signal.detectedAt)}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}