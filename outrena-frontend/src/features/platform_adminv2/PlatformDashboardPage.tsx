/**
 * PlatformDashboardPage.tsx — SUPER_ADMIN overview metrics.
 * Mounted at /platform-admin (index).
 */
import { useQuery } from "@tanstack/react-query";
import { Building2, DollarSign, TrendingDown, Users } from "lucide-react";
import { platformApi } from "@/services/apiClient";
import type { PlatformMetrics } from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function MetricCard({
  title,
  value,
  icon: Icon,
  loading,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  loading: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="text-2xl font-bold">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function PlatformDashboardPage() {
  const { data: metrics, isLoading } = useQuery<PlatformMetrics>({
    queryKey: ["platform", "metrics"],
    queryFn: () => platformApi.metrics(),
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Dashboard"
        description="High-level health metrics across all tenants on this instance."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Tenants"
          value={metrics?.total_tenants ?? "—"}
          icon={Building2}
          loading={isLoading}
        />
        <MetricCard
          title="Active Tenants"
          value={metrics?.active_tenants ?? "—"}
          icon={Building2}
          loading={isLoading}
        />
        <MetricCard
          title="Total Users"
          value={metrics?.total_users ?? "—"}
          icon={Users}
          loading={isLoading}
        />
        <MetricCard
          title="MRR"
          value={
            metrics
              ? `$${metrics.mrr.toLocaleString()}`
              : "—"
          }
          icon={DollarSign}
          loading={isLoading}
        />
      </div>

      {!isLoading && metrics && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Churn Rate</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-muted-foreground" />
            <span className="text-xl font-semibold">
              {(metrics.churn_rate * 100).toFixed(1)}%
            </span>
            <span className="text-sm text-muted-foreground">monthly</span>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
