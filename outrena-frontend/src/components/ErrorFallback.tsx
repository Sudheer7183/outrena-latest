/**
 * ErrorFallback.tsx — UI shown when the React ErrorBoundary catches a render
 * error.
 *
 * Rendered by <ErrorBoundary> (see src/components/ErrorBoundary.tsx). The
 * boundary has already pushed the exception into PostHog Error Tracking, so
 * this UI just tells the user the team has been notified + offers recovery
 * actions (reload, navigate to dashboard, or reset the boundary and retry).
 *
 * Styled with shadcn Card + Button + Tailwind semantic tokens so it respects
 * the active theme (light/dark) and is mobile-responsive.
 */
import { AlertTriangle, Home, RefreshCw, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ErrorFallbackProps {
  /** The caught error (may be null if the boundary reset partially). */
  error: Error | null;
  /** Clears the boundary's error state and re-renders the children. */
  onReset: () => void;
}

function goDashboard() {
  window.location.assign("/");
}

function reload() {
  window.location.reload();
}

export function ErrorFallback({ error, onReset }: ErrorFallbackProps) {
  const isDev = import.meta.env.DEV;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
      <Card className="w-full max-w-md border-border">
        <CardHeader className="space-y-2 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <AlertTriangle className="h-6 w-6" aria-hidden="true" />
          </div>
          <CardTitle className="text-2xl">Something went wrong</CardTitle>
          <CardDescription>
            An unexpected error occurred while rendering this page. Our team has
            been notified and will look into it.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {isDev && error ? (
            <pre
              className="max-h-48 overflow-auto rounded-md border border-border bg-muted p-3 text-xs text-muted-foreground"
              role="alert"
              aria-live="polite"
            >
              <span className="font-semibold text-foreground">
                {error.name}:{" "}
              </span>
              {error.message}
              {error.stack ? `\n\n${error.stack}` : ""}
            </pre>
          ) : (
            <p className="text-center text-sm text-muted-foreground">
              If the problem persists, please contact support.
            </p>
          )}
        </CardContent>

        <CardFooter className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Button onClick={reload} className="w-full sm:w-auto">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Reload page
          </Button>
          <Button
            variant="outline"
            onClick={goDashboard}
            className="w-full sm:w-auto"
          >
            <Home className="h-4 w-4" aria-hidden="true" />
            Back to dashboard
          </Button>
          <Button
            variant="ghost"
            onClick={onReset}
            className="w-full sm:w-auto"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Try again
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
