/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_KEYCLOAK_URL: string;
  readonly VITE_KEYCLOAK_REALM: string;
  readonly VITE_KEYCLOAK_CLIENT_ID: string;
  /** PH-FE: PostHog project API key. Empty/undefined ⇒ PostHog disabled. */
  readonly VITE_POSTHOG_KEY?: string;
  /** PH-FE: PostHog ingestion host (self-hosted). Defaults to http://localhost:8000. */
  readonly VITE_POSTHOG_HOST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
