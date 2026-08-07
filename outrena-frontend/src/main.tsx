/**
 * main.tsx — Vite entry point.
 *
 * Mounts `<App />` (the provider tree + router) into #root, and initialises
 * PostHog product analytics (Tech Doc §12.2) BEFORE the first render so
 * autocapture sees every event from the very first paint.
 *
 * PostHog is only initialised when VITE_POSTHOG_KEY is set — dev/CI builds
 * without a key run with analytics disabled (no-op), mirroring the backend's
 * empty-POSTHOG_KEY behaviour (app/core/posthog_client.py).
 */
import React from "react";
import ReactDOM from "react-dom/client";
import posthog from "posthog-js";
import App from "@/App";
import "./index.css";

// ── PostHog init (Tech Doc §12.2) ────────────────────────────────────────────
const POSTHOG_KEY = import.meta.env.VITE_POSTHOG_KEY as string | undefined;
const POSTHOG_HOST =
  (import.meta.env.VITE_POSTHOG_HOST as string | undefined) ??
  "https://app.posthog.com";

if (POSTHOG_KEY) {
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    autocapture: true,               // clicks, form submits, page views
    capture_pageview: true,
    capture_pageleave: true,
    session_recording: {
      // PII safety per §12.2: input values are redacted, visible text kept.
      maskAllInputs: true,
      maskTextSelector: "[data-ph-mask]",
    },
    persistence: "localStorage+cookie",
    loaded: (ph) => {
      // Dev builds: log events to console instead of network noise.
      if (import.meta.env.DEV) ph.debug();
    },
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
