/**
 * App.tsx — application root.
 *
 * Composes the four providers (ThemeProvider → QueryClientProvider →
 * AuthProvider → RouterProvider) + the Sonner toaster + the floating
 * SupportWidget (mounted only for authenticated users). `main.tsx` mounts
 * `<App />` into #root.
 *
 * The whole tree is wrapped in <ErrorBoundary> (PH-FE) which catches render
 * errors anywhere below and forwards them to PostHog Error Tracking. PostHog
 * is initialised once at module load (initPostHog is idempotent + no-ops if
 * VITE_POSTHOG_KEY is empty).
 *
 * The CookieConsentBanner is mounted inside <PublicLayout> (see SAAS2-FE spec
 * §16: "inside PublicLayout, not AppLayout") so it only appears on public
 * marketing pages and not on the authenticated app shell.
 */
import { RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { router } from "@/routes";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/components/ThemeProvider";
import { SupportWidget } from "@/components/SupportWidget";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { TooltipProvider } from "@/components/ui/tooltip";
import { initPostHog } from "@/lib/posthog";

// Initialise PostHog once at module load. Safe to call before React mounts —
// posthog-js queues events internally and flushes once its script is ready.
// No-ops entirely when VITE_POSTHOG_KEY is unset (dev/CI without PostHog).
initPostHog();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function AuthenticatedChrome() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <SupportWidget /> : null;
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="system">
        <QueryClientProvider client={queryClient}>
          <TooltipProvider delayDuration={200}>
            <AuthProvider>
              <RouterProvider router={router} />
              <AuthenticatedChrome />
              <Toaster richColors position="top-right" />
            </AuthProvider>
          </TooltipProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
