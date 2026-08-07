/**
 * ErrorBoundary.tsx — React error boundary that catches render errors in the
 * subtree below it and reports them to PostHog Error Tracking.
 *
 * Wrap the entire app with this (see src/App.tsx). On an uncaught render error
 * React calls `componentDidCatch` with the error + componentStack; we forward
 * both to PostHog via captureException() and render <ErrorFallback> so the
 * user sees a clean recovery UI instead of a blank page.
 *
 * PostHog capture is wrapped in try/catch so a PostHog outage can never break
 * the fallback UI itself.
 *
 * Note: React's error-boundary API requires a class component — function
 * components cannot implement `getDerivedStateFromError` /
 * `componentDidCatch`. This is one of the few class components in the codebase.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { captureException } from "@/lib/posthog";
import { ErrorFallback } from "@/components/ErrorFallback";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    try {
      captureException(error, {
        componentStack: info.componentStack ?? undefined,
        // React doesn't expose a stack on `error` directly for async errors;
        // include both so PostHog Error Tracking has full context.
        react_error_boundary: true,
      });
    } catch {
      /* never break the fallback */
    }
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <ErrorFallback error={this.state.error} onReset={this.handleReset} />
      );
    }
    return this.props.children;
  }
}
