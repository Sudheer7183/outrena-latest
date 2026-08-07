/**
 * posthog.ts — PostHog JS client for exception tracking + session replay
 * + product analytics.
 *
 * Self-hosted instance (see docker-compose.posthog.yml). No-op if
 * `VITE_POSTHOG_KEY` is empty so local dev / CI builds keep working without a
 * PostHog server running.
 *
 * Design rules (per PH-FE spec):
 *   1. Never break the app. Every helper is wrapped in try/catch and silently
 *      no-ops if PostHog is not initialised or the call throws.
 *   2. GDPR: `maskAllInputs: true` on session recording so PII form inputs
 *      are NEVER recorded. (The spec also mentioned `blockAllMedia`, but that
 *      option does not exist in posthog-js SessionRecordingOptions — see
 *      `@posthog/types` SessionRecordingOptions; only `maskAllInputs`,
 *      `maskTextSelector`, `blockSelector`, `blockClass` etc. are supported.)
 *   3. Identity is set by AuthContext on login (identifyUser) and cleared on
 *      logout (resetUser) — see src/context/AuthContext.tsx.
 *
 * Env vars (declared in src/vite-env.d.ts):
 *   - VITE_POSTHOG_KEY  : project API key. Empty/undefined ⇒ PostHog disabled.
 *   - VITE_POSTHOG_HOST : ingestion host, e.g. https://posthog.outrena.app
 *                         (defaults to http://localhost:8000 for local dev).
 */
import posthog from "posthog-js";

let initialized = false;

/**
 * Initialise the PostHog JS client. Safe to call once at module load (App.tsx
 * invokes it on mount). If `VITE_POSTHOG_KEY` is empty the function returns
 * early and all helper functions below become no-ops.
 */
export function initPostHog(): void {
  const key = import.meta.env.VITE_POSTHOG_KEY;
  const host = import.meta.env.VITE_POSTHOG_HOST ?? "http://localhost:8000";

  if (!key) {
    // dev-safe: PostHog disabled. Helpers all no-op via `initialized` guard.
    return;
  }

  try {
    posthog.init(key, {
      api_host: host,
      autocapture: true, // captures clicks, page views, etc.
      capture_pageview: true,
      capture_exceptions: true, // uncaught JS errors → PostHog Error Tracking
      session_recording: {
        // GDPR: never record form input values ( Prospect emails, names,
        // phone numbers, sender identities, etc.). Only the FACT that an input
        // was focused / changed is recorded.
        maskAllInputs: true,
      },
      persistence: "localStorage+cookie",
      loaded: () => {
        // posthog-js's init is synchronous (events queue while the script
        // finishes loading from api_host); `loaded` fires once fully ready.
        initialized = true;
      },
    });

    // Mark initialised synchronously too so events captured between init() and
    // the async `loaded` callback are NOT dropped (posthog-js queues them
    // internally and flushes once the script is ready).
    initialized = true;
  } catch {
    // Never break the app — PostHog is observability, not core functionality.
    initialized = false;
  }
}

/**
 * Identify the signed-in user to PostHog. Called by AuthContext after a
 * successful login. Properties are persisted on the person record.
 */
export function identifyUser(
  distinctId: string,
  properties?: Record<string, unknown>,
): void {
  if (!initialized) return;
  try {
    posthog.identify(distinctId, properties);
  } catch {
    /* never break */
  }
}

/**
 * Capture a custom product-analytics event.
 */
export function captureEvent(
  event: string,
  properties?: Record<string, unknown>,
): void {
  if (!initialized) return;
  try {
    posthog.capture(event, properties);
  } catch {
    /* never break */
  }
}

/**
 * Capture an exception (Error object) to PostHog Error Tracking. Used by the
 * React ErrorBoundary in addition to the automatic `capture_exceptions` flag
 * (the boundary adds React componentStack context).
 */
export function captureException(
  error: Error,
  properties?: Record<string, unknown>,
): void {
  if (!initialized) return;
  try {
    posthog.captureException(error, properties);
  } catch {
    /* never break */
  }
}

/**
 * Reset the identified user (clears person + session). Called by AuthContext
 * on logout so events captured after logout are anonymous.
 */
export function resetUser(): void {
  if (!initialized) return;
  try {
    posthog.reset();
  } catch {
    /* never break */
  }
}

/** Whether initPostHog() has run successfully (PostHog is active). */
export function isPostHogInitialized(): boolean {
  return initialized;
}

export { posthog };
