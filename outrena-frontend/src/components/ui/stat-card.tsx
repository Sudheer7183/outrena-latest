/**
 * stat-card.tsx — KPI tile used across dashboard + analytics pages.
 */
import type { ReactNode } from "react";
import { Card, CardContent } from "./card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  delta,
  icon,
  className,
}: {
  label: string;
  value: ReactNode;
  delta?: { value: string; positive?: boolean };
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn(className)}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          {icon && <div className="text-muted-foreground">{icon}</div>}
        </div>
        <p className="mt-2 text-2xl font-bold">{value}</p>
        {delta && (
          <p
            className={cn(
              "mt-1 text-xs font-medium",
              delta.positive ? "text-emerald-600" : "text-red-600",
            )}
          >
            {delta.positive ? "▲" : "▼"} {delta.value}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
