/**
 * error-state.tsx — reusable error + retry block (Task 2-b finding 14).
 *
 * Used by pages that previously fell back to mock data on API error without
 * surfacing the failure to the user. Renders an inline centred card with the
 * error message + a Retry button wired to `onRetry`.
 */
import type { ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ErrorState({
  title = "Failed to load",
  description,
  error,
  onRetry,
  isRetrying,
  className,
  action,
}: {
  title?: string;
  description?: string;
  error?: unknown;
  onRetry?: () => void;
  isRetrying?: boolean;
  className?: string;
  /** Optional extra action node (e.g. "Continue with sample data" button). */
  action?: ReactNode;
}) {
  const message =
    description ??
    (error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "Unknown error");
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-10 text-center",
        className,
      )}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertCircle className="h-5 w-5" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{message}</p>
      </div>
      <div className="flex items-center gap-2">
        {onRetry && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            disabled={isRetrying}
          >
            <RefreshCw className={cn("h-4 w-4", isRetrying && "animate-spin")} />
            {isRetrying ? "Retrying…" : "Retry"}
          </Button>
        )}
        {action}
      </div>
    </div>
  );
}
