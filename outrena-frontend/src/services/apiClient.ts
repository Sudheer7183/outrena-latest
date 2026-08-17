// // /**
// //  * apiClient.ts — central axios instance with Bearer + tenant interceptors.
// //  *
// //  * The access token is read from a module-level holder kept in sync by
// //  * `AuthContext` (Section 7.6 of the migration doc). A `VITE_DEV_TENANT_SLUG`
// //  * override lets local dev target a specific tenant schema without Keycloak
// //  * claims.
// //  */
// // import axios, { AxiosError, type AxiosInstance } from "axios";
// // import type {
// //   LandingContent,
// //   ContactInfo,
// //   ContactMessage,
// //   Plan,
// //   TenantSignupRequest,
// //   TenantSignupStatus,
// //   TenantSignupRow,
// //   TenantRow,
// //   PlatformMetrics,
// //   AuditLog,
// //   TenantIntegration,
// //   IntegrationMode,
// //   IntegrationCatalogEntry,
// //   IntegrationTestResult,
// //   GlobalLlmConfig,
// //   GlobalLlmConfigInput,
// //   GlobalLlmTestResult,
// //   SenderIdentity,
// //   EmailQuota,
// //   UserDashboard,
// //   ManagerDashboard,
// //   UsageSummary,
// //   UsageManagerRollup,
// //   UsagePlatformRollup,
// //   CostTableEntry,
// //   CostTableInput,
// //   DsrSubmission,
// //   DsrSubmissionResponse,
// //   DsrStatusResponse,
// //   DsrRow,
// //   ConsentStatus,
// //   RetentionStatus,
// //   MailBridgeConfig,
// //   MailBridgeConfigInput,
// //   ProspectingFlow,
// //   ProspectingFlowInput,
// //   FlowRun,
// //   FlowAbTest,
// //   FlowAbTestInput,
// //   FlowWebhook,
// //   FlowWebhookInput,
// //   AutopilotQueueItem,
// //   RateLimit,
// //   RateLimitInput,
// //   RateLimitLog,
// //   SchedulerStatus,
// //   ManualTickResponse,
// //   SchedulerRun,
// //   Meeting,
// //   MeetingInput,
// //   MeetingPrep,
// //   DomainEnrichment,
// //   CallLog,
// //   CallLogInput,
// //   PlatformTenantConfig,
// //   FlowAnalyticsSummary,
// //   AutopilotQueueStats,
// //   AutopilotQueueEnqueueBody,
// //   PipelineStageResult,
// //   PipelineStatus,
// //   PipelineRunStageInput,
// //   FlowTemplate,
// //   FlowTemplateCloneInput,
// // } from "@/types/common";

// // let currentAccessToken: string | null = null;

// // export function setAccessToken(token: string | null): void {
// //   currentAccessToken = token;
// // }

// // export function getAccessToken(): string | null {
// //   return currentAccessToken;
// // }

// // const DEV_TENANT_SLUG = import.meta.env.VITE_DEV_TENANT_SLUG ?? "";

// // export const apiClient: AxiosInstance = axios.create({
// //   baseURL: "/",
// //   timeout: 15_000,
// //   headers: { "Content-Type": "application/json" },
// // });

// // apiClient.interceptors.request.use((config) => {
// //   const token = getAccessToken();
// //   if (token) {
// //     config.headers.Authorization = `Bearer ${token}`;
// //   }
// //   if (DEV_TENANT_SLUG) {
// //     config.headers["X-Tenant-Slug"] = DEV_TENANT_SLUG;
// //   }
// //   return config;
// // });

// // apiClient.interceptors.response.use(
// //   (resp) => resp,
// //   (error: AxiosError) => {
// //     // Normalise 401 → trigger re-login via AuthContext (handled by consumers).
// //     if (error.response?.status === 401) {
// //       window.dispatchEvent(new CustomEvent("outrena:unauthorized"));
// //     }
// //     return Promise.reject(error);
// //   },
// // );

// // /** Convenience typed request helpers used by feature service modules. */
// // export const http = {
// //   get: <T>(url: string, params?: Record<string, unknown>) =>
// //     apiClient.get<T>(url, { params }).then((r) => r.data),
// //   post: <T>(url: string, body?: unknown) =>
// //     apiClient.post<T>(url, body).then((r) => r.data),
// //   put: <T>(url: string, body?: unknown) =>
// //     apiClient.put<T>(url, body).then((r) => r.data),
// //   patch: <T>(url: string, body?: unknown) =>
// //     apiClient.patch<T>(url, body).then((r) => r.data),
// //   delete: <T>(url: string) => apiClient.delete<T>(url).then((r) => r.data),
// // };

// // /**
// //  * publicApi — calls to `/api/v1/public/*` and `/api/v1/tenant-signup*`.
// //  *
// //  * These endpoints are intentionally NOT authenticated: marketing pages, plan
// //  * list, contact form, tenant self-signup wizard. They still go through the
// //  * shared `apiClient` instance (so dev-tenant header is preserved), but the
// //  * backend does not require a Bearer token.
// //  */
// // export const publicApi = {
// //   landing: () => http.get<LandingContent>("/api/v1/public/landing"),
// //   plans: () => http.get<Plan[]>("/api/v1/public/plans"),
// //   contactInfo: () => http.get<ContactInfo>("/api/v1/public/contact-info"),
// //   contact: (body: ContactMessage) =>
// //     apiClient.post("/api/v1/public/contact", body).then((r) => r.status),
// //   checkSubdomain: (subdomain: string) =>
// //     apiClient
// //       .get<{ available: boolean }>("/api/v1/public/subdomain-check", {
// //         params: { subdomain },
// //       })
// //       .then((r) => r.data)
// //       .catch(() => ({ available: false })),
// //   submitSignup: (body: TenantSignupRequest) =>
// //     http.post<{ signup_id: string; status: string }>(
// //       "/api/v1/tenant-signup",
// //       body,
// //     ),
// //   signupStatus: (signupId: string) =>
// //     http.get<TenantSignupStatus>(
// //       `/api/v1/tenant-signup/${signupId}/status`,
// //     ),
// // };

// // /**
// //  * platformApi — SUPER_ADMIN calls to `/api/platform/admin/*`.
// //  *
// //  * Uses the authenticated `apiClient` (Bearer + tenant header) but targets the
// //  * cross-tenant platform admin router. All calls are role-gated server-side to
// //  * SUPER_ADMIN.
// //  */
// // export const platformApi = {
// //   signups: (status?: string) =>
// //     http.get<TenantSignupRow[]>("/api/platform/admin/signups", {
// //       status: status ?? "pending",
// //     }),
// //   approveSignup: (id: string) =>
// //     http.post<{ tenant_slug: string; provisioned: boolean }>(
// //       `/api/platform/admin/signups/${id}/approve`,
// //     ),
// //   rejectSignup: (id: string, reason: string) =>
// //     http.post(`/api/platform/admin/signups/${id}/reject`, { reason }),
// //   tenants: () => http.get<TenantRow[]>("/api/platform/admin/tenants"),
// //   suspendTenant: (id: string) =>
// //     http.post(`/api/platform/admin/tenants/${id}/suspend`),
// //   reactivateTenant: (id: string) =>
// //     http.post(`/api/platform/admin/tenants/${id}/reactivate`),
// //   metrics: () => http.get<PlatformMetrics>("/api/platform/admin/metrics"),
// //   auditLogs: (params?: { limit?: number; tenant_slug?: string; action?: string }) =>
// //     http.get<AuditLog[]>("/api/platform/admin/audit-logs", params),
// //   // ISSUE-3 FIX: Create tenant endpoint (provisioning — base platform router, not /admin)
// //   createTenant: (body: {
// //     slug: string;
// //     name: string;
// //     admin_email: string;
// //     admin_first_name: string;
// //     admin_last_name: string;
// //     temporary_password?: string;
// //     send_invitation: boolean;
// //   }) =>
// //     http.post<{ slug: string; status: string; url: string }>(
// //       "/api/platform/tenants",
// //       body,
// //     ),
// // };

// // /* ─────────────────────────────────────────────────────────────────────────── */
// // /* SAAS2-FE: Workstream helpers (integrations, LLM, users, usage, GDPR).      */
// // /* Each helper targets the exact endpoints specified in the SAAS2-FE task.    */
// // /* ─────────────────────────────────────────────────────────────────────────── */

// // /**
// //  * integrationConfigApi — dual-path integration config.
// //  *
// //  * Tenant side (`/api/v1/integrations`): list, create, update, test.
// //  * Platform side (`/api/platform/admin/...`): per-tenant mode + catalog.
// //  */
// // export const integrationConfigApi = {
// //   tenantList: () => http.get<TenantIntegration[]>("/api/v1/integrations"),
// //   tenantCreate: (body: {
// //     type: string;
// //     name: string;
// //     key_source: "tenant" | "platform";
// //     api_key?: string;
// //   }) => http.post<TenantIntegration>("/api/v1/integrations", {
// //     platform: body.type,
// //     name: body.name,
// //     key_source: body.key_source,
// //     apiKey: body.key_source === "tenant" ? body.api_key : undefined,
// //   }),
// //   tenantUpdate: (
// //     id: string,
// //     body: Partial<{
// //       name: string;
// //       key_source: "tenant" | "platform";
// //       api_key?: string;
// //       is_active: boolean;
// //     }>,
// //   ) => http.put<TenantIntegration>(`/api/v1/integrations/${id}`, {
// //     name: body.name,
// //     key_source: body.key_source,
// //     apiKey: body.api_key,
// //     isActive: body.is_active,
// //   }),
// //   tenantTest: (id: string) =>
// //     http.get<IntegrationTestResult>(
// //       `/api/v1/integrations/${id}/credentials-test`,
// //     ),
// //   // NOTE (Task 2-b finding 9): platformGetConfig removed — duplicate of
// //   // platformConfigApi.get() which is the one PlatformSettingsPage actually uses.
// //   platformSetMode: (tenantId: string, integration_mode: IntegrationMode) =>
// //     http.patch<{ tenant_id: string; integration_mode: IntegrationMode }>(
// //       `/api/platform/admin/tenants/${tenantId}/integration-mode`,
// //       { integration_mode },
// //     ),
// //   catalog: () =>
// //     http.get<IntegrationCatalogEntry[]>(
// //       "/api/platform/admin/integration-catalog",
// //     ),
// // };

// // /**
// //  * globalLlmApi — SUPER_ADMIN global LLM config (`/api/platform/admin/llm-configs`).
// //  */
// // export const globalLlmApi = {
// //   list: () =>
// //     http.get<GlobalLlmConfig[]>("/api/platform/admin/llm-configs"),
// //   create: (body: GlobalLlmConfigInput) =>
// //     http.post<GlobalLlmConfig>("/api/platform/admin/llm-configs", body),
// //   update: (id: string, body: GlobalLlmConfigInput) =>
// //     http.put<GlobalLlmConfig>(`/api/platform/admin/llm-configs/${id}`, body),
// //   remove: (id: string) =>
// //     http.delete<{ message: string }>(
// //       `/api/platform/admin/llm-configs/${id}`,
// //     ),
// //   setDefault: (id: string) =>
// //     http.post<{ message: string }>(
// //       `/api/platform/admin/llm-configs/${id}/set-default`,
// //     ),
// //   test: (id: string) =>
// //     http.post<GlobalLlmTestResult>(
// //       `/api/platform/admin/llm-configs/${id}/test`,
// //     ),
// // };

// // /**
// //  * senderIdentityApi — per-user sender identities (`/api/v1/users/me/...`).
// //  */
// // export const senderIdentityApi = {
// //   list: () =>
// //     http.get<SenderIdentity[]>("/api/v1/users/me/sender-identities"),
// //   create: (body: {
// //     email: string;
// //     email_type: "platform_assigned" | "corporate";
// //     display_name?: string;
// //   }) =>
// //     http.post<SenderIdentity>("/api/v1/users/me/sender-identities", body),
// //   remove: (id: string) =>
// //     http.delete<{ message: string }>(
// //       `/api/v1/users/me/sender-identities/${id}`,
// //     ),
// //   setDefault: (id: string) =>
// //     http.post<{ message: string }>(
// //       `/api/v1/users/me/sender-identities/${id}/set-default`,
// //     ),
// //   myQuota: () => http.get<EmailQuota>("/api/v1/users/me/email-quota"),
// //   // NOTE (Task 2-b finding 9): teamQuotas removed — was unused. Re-add from
// //   // git history (or AUDIT-FE-1 §C.7) when a Team Quotas card is built.
// // };

// // /**
// //  * managerDashboardApi — per-user + manager dashboards (`/api/v1/dashboard*`).
// //  */
// // export const managerDashboardApi = {
// //   mine: () =>
// //     http.get<UserDashboard>("/api/v1/dashboard", { user_id: "me" }),
// //   // NOTE (Task 2-b finding 9): user(userId) removed — was unused. Re-add when
// //   // a per-rep drill-down is built into ManagerDashboardPage.
// //   manager: () => http.get<ManagerDashboard>("/api/v1/dashboard/manager"),
// // };

// // /**
// //  * usageApi — usage + cost rollups (`/api/v1/usage/*` + platform equivalents).
// //  */
// // export const usageApi = {
// //   me: (period: string) =>
// //     http.get<UsageSummary>("/api/v1/usage/me", { period }),
// //   // NOTE (Task 2-b finding 9): user(userId, period) + tenant(period) removed —
// //   // were unused. Re-add when per-user / per-tenant usage drill-downs are built.
// //   manager: (period: string) =>
// //     http.get<UsageManagerRollup>("/api/v1/usage/manager", { period }),
// //   platform: (period: string) =>
// //     http.get<UsagePlatformRollup>(
// //       "/api/v1/usage/platform",
// //       { period },
// //     ),
// //   costTable: () =>
// //     http.get<CostTableEntry[]>("/api/v1/usage/cost-table"),
// //   updateCostTable: (entries: CostTableInput[]) =>
// //     http.put<CostTableEntry[]>("/api/v1/usage/cost-table", entries),
// // };

// // /**
// //  * gdprApi — GDPR DSR + consent + retention endpoints.
// //  *
// //  * Public DSR (no auth): `submitDsr` + `dsrStatus`.
// //  * Authenticated tenant-admin DSR workflow: `list`, `process`, `complete`,
// //  * `reject`, `export`.
// //  * Consent: `getConsent`, `grant`, `withdraw`.
// //  * Retention: `status`, `enforce`.
// //  */
// // export const gdprApi = {
// //   // Public DSR
// //   submitDsr: (body: DsrSubmission) =>
// //     http.post<DsrSubmissionResponse>("/api/v1/gdpr/dsr", body),
// //   dsrStatus: (dsrId: string) =>
// //     http.get<DsrStatusResponse>(`/api/v1/gdpr/dsr/${dsrId}/status`),
// //   // Tenant-admin DSR workflow
// //   list: (status?: string) =>
// //     http.get<DsrRow[]>("/api/v1/gdpr/dsrs", status ? { status } : undefined),
// //   process: (id: string) =>
// //     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/process`),
// //   complete: (id: string) =>
// //     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/complete`),
// //   reject: (id: string, reason?: string) =>
// //     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/reject`, { reason }),
// //   // NOTE (Task 2-b finding 9): exportUrl + grant removed — were unused.
// //   // GdprCenterPage builds export URLs inline; the consent grant endpoint
// //   // (/api/v1/gdpr/consent/grant) is still available on the backend. Re-add
// //   // these helpers when the corresponding UI is built.
// //   // Consent
// //   getConsent: (email: string) =>
// //     http.get<ConsentStatus>(`/api/v1/gdpr/consent/${encodeURIComponent(email)}`),
// //   withdraw: (email: string) =>
// //     http.post("/api/v1/gdpr/consent/withdraw", { email }),
// //   // Retention
// //   retentionStatus: () =>
// //     http.get<RetentionStatus>("/api/v1/gdpr/retention-status"),
// //   enforceRetention: () =>
// //     http.post<RetentionStatus>("/api/v1/gdpr/retention/enforce"),
// // };

// // /* ─────────────────────────────────────────────────────────────────────────── */
// // /* FIX-FE-1: New feature-page helpers (MailBridge, Flows, RateLimits,         */
// // /* Scheduler, Meetings, DomainEnrichment, CallLogs, PlatformTenantConfig).    */
// // /* Each helper targets the exact endpoints exposed by the backend router.     */
// // /* ─────────────────────────────────────────────────────────────────────────── */

// // /** mailbridgeApi — per-tenant MailBridge config CRUD (`/api/v1/mailbridge/config`). */
// // export const mailbridgeApi = {
// //   list: () => http.get<MailBridgeConfig[]>("/api/v1/mailbridge/config"),
// //   create: (body: MailBridgeConfigInput) =>
// //     http.post<MailBridgeConfig>("/api/v1/mailbridge/config", body),
// //   get: (id: string) =>
// //     http.get<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`),
// //   update: (id: string, body: Partial<MailBridgeConfigInput>) =>
// //     http.put<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`, body),
// //   remove: (id: string) =>
// //     http.delete<{ message: string }>(`/api/v1/mailbridge/config/${id}`),
// //   /** Send a test email through this config (best-effort). */
// //   sendTest: (body: { to: string; subject: string; body: string; configId?: string }) =>
// //     http.post<{ messageId: string; status: string; accepted: boolean }>(
// //       "/api/v1/mailbridge/send",
// //       body,
// //     ),
// // };

// // /** flowsApi — ProspectingFlow + FlowRun + FlowAbTest + FlowWebhook + AutopilotQueue. */
// // export const flowsApi = {
// //   // ProspectingFlow definitions
// //   listFlows: (params?: { isActive?: boolean; isTemplate?: boolean; limit?: number; offset?: number }) =>
// //     http.get<{ items: ProspectingFlow[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/flows",
// //       params,
// //     ),
// //   createFlow: (body: ProspectingFlowInput) =>
// //     http.post<ProspectingFlow>("/api/v1/flows", body),
// //   getFlow: (id: string) => http.get<ProspectingFlow>(`/api/v1/flows/${id}`),
// //   updateFlow: (id: string, body: Partial<ProspectingFlowInput>) =>
// //     http.put<ProspectingFlow>(`/api/v1/flows/${id}`, body),
// //   removeFlow: (id: string) =>
// //     http.delete<{ message: string }>(`/api/v1/flows/${id}`),
// //   // FlowRuns (list + detail; runs are created via /autopilot)
// //   listRuns: (params?: { flowId?: string; icpProfileId?: string; status?: string; limit?: number; offset?: number }) =>
// //     http.get<{ items: FlowRun[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/flows/runs",
// //       params,
// //     ),
// //   getRun: (runId: string) => http.get<FlowRun>(`/api/v1/flows/runs/${runId}`),
// //   // Flow A/B tests
// //   listAbTests: (params?: { icpProfileId?: string; status?: string }) =>
// //     http.get<{ items: FlowAbTest[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/flows/ab-tests",
// //       params,
// //     ),
// //   createAbTest: (body: FlowAbTestInput) =>
// //     http.post<FlowAbTest>("/api/v1/flows/ab-tests", body),
// //   getAbTest: (id: string) => http.get<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`),
// //   updateAbTest: (id: string, body: Partial<FlowAbTestInput> & { status?: string; significance?: string; summary?: string }) =>
// //     http.put<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`, body),
// //   removeAbTest: (id: string) =>
// //     http.delete<{ message: string }>(`/api/v1/flows/ab-tests/${id}`),
// //   // Flow webhooks
// //   listWebhooks: (params?: { flowId?: string; isActive?: boolean }) =>
// //     http.get<{ items: FlowWebhook[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/flows/webhooks",
// //       params,
// //     ),
// //   createWebhook: (body: FlowWebhookInput) =>
// //     http.post<FlowWebhook>("/api/v1/flows/webhooks", body),
// //   getWebhook: (id: string) => http.get<FlowWebhook>(`/api/v1/flows/webhooks/${id}`),
// //   updateWebhook: (id: string, body: Partial<FlowWebhookInput>) =>
// //     http.put<FlowWebhook>(`/api/v1/flows/webhooks/${id}`, body),
// //   removeWebhook: (id: string) =>
// //     http.delete<{ message: string }>(`/api/v1/flows/webhooks/${id}`),
// //   // AutopilotQueue (read-only)
// //   listQueue: (params?: { status?: string; limit?: number; offset?: number }) =>
// //     http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/flows/queue",
// //       params,
// //     ),
// // };

// // /** rateLimitsApi — RateLimit + RateLimitLog. */
// // export const rateLimitsApi = {
// //   list: (params?: { platform?: string; isActive?: boolean; limit?: number; offset?: number }) =>
// //     http.get<{ items: RateLimit[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/rate-limits",
// //       params,
// //     ),
// //   create: (body: RateLimitInput) =>
// //     http.post<RateLimit>("/api/v1/rate-limits", body),
// //   get: (id: string) => http.get<RateLimit>(`/api/v1/rate-limits/${id}`),
// //   update: (id: string, body: Partial<RateLimitInput> & { count?: number }) =>
// //     http.put<RateLimit>(`/api/v1/rate-limits/${id}`, body),
// //   remove: (id: string) =>
// //     http.delete<{ message: string }>(`/api/v1/rate-limits/${id}`),
// //   resetCounter: (id: string) =>
// //     http.post<RateLimit>(`/api/v1/rate-limits/${id}/reset`),
// //   listLogs: (params?: { key?: string; platform?: string; flowRunId?: string; limit?: number; offset?: number }) =>
// //     http.get<{ items: RateLimitLog[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/rate-limits/logs",
// //       params,
// //     ),
// // };

// // /** schedulerApi — scheduler status + manual tick + trigger + runs. */
// // export const schedulerApi = {
// //   status: () => http.get<SchedulerStatus>("/api/v1/scheduler/status"),
// //   tick: (body?: { tenantScoped?: boolean; maxSend?: number }) =>
// //     http.post<ManualTickResponse>("/api/v1/scheduler/tick", body ?? {}),
// //   trigger: () =>
// //     http.post<{ triggered: boolean; message: string; runId: string | null }>(
// //       "/api/v1/scheduler/trigger",
// //     ),
// //   runs: (params?: { limit?: number; offset?: number }) =>
// //     http.get<{ items: SchedulerRun[]; total: number }>(
// //       "/api/v1/scheduler/runs",
// //       params,
// //     ),
// // };

// // /** meetingsApi — Meeting CRUD. The backend Meeting model lives at
// //  * `/api/v1/meetings`; if the route is missing (pre-FIX-BE follow-up), the
// //  * page degrades to an error state. The MeetingPrep generate endpoint is
// //  * backed by the existing `/api/v1/meeting-prep` router. */
// // export const meetingsApi = {
// //   list: () => http.get<Meeting[]>("/api/v1/meetings"),
// //   create: (body: MeetingInput) => http.post<Meeting>("/api/v1/meetings", body),
// //   get: (id: string) => http.get<Meeting>(`/api/v1/meetings/${id}`),
// //   update: (id: string, body: Partial<MeetingInput>) =>
// //     http.patch<Meeting>(`/api/v1/meetings/${id}`, body),
// //   remove: (id: string) =>
// //     http.delete<{ message: string }>(`/api/v1/meetings/${id}`),
// //   // Meeting-prep integration
// //   generatePrep: (prospectId: string, callType: string = "discovery") =>
// //     http.post<{ id: string; brief: string }>("/api/v1/meeting-prep/generate", {
// //       prospectId,
// //       callType,
// //     }),
// //   getPrep: (briefId: string) =>
// //     http.get<MeetingPrep>(`/api/v1/meeting-prep/${briefId}`),
// //   listPrepForProspect: (prospectId: string) =>
// //     http.get<MeetingPrep[]>("/api/v1/meeting-prep", { prospect_id: prospectId }),
// // };

// // /** domainEnrichApi — fetch/cache enrichment for a domain. */
// // export const domainEnrichApi = {
// //   enrich: (domain: string, forceRefresh = false) =>
// //     http.post<DomainEnrichment>("/api/v1/domain-enrich", { domain, forceRefresh }),
// //   enrichBatch: (domains: string[]) =>
// //     http.post<{ enriched: DomainEnrichment[]; failed: string[] }>(
// //       "/api/v1/domain-enrich/batch",
// //       { domains },
// //     ),
// //   get: (domain: string) =>
// //     http.get<DomainEnrichment>(`/api/v1/domain-enrich/${encodeURIComponent(domain)}`),
// // };

// // /** callLogsApi — CallLog CRUD. */
// // export const callLogsApi = {
// //   list: (params?: { prospectId?: string; outcome?: string; limit?: number; offset?: number }) =>
// //     http.get<{ items: CallLog[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/call-logs",
// //       params,
// //     ),
// //   create: (body: CallLogInput) =>
// //     http.post<CallLog>("/api/v1/call-logs", body),
// //   get: (id: string) => http.get<CallLog>(`/api/v1/call-logs/${id}`),
// //   update: (id: string, body: Partial<CallLogInput>) =>
// //     http.patch<CallLog>(`/api/v1/call-logs/${id}`, body),
// //   remove: (id: string) =>
// //     http.delete<{ message: string }>(`/api/v1/call-logs/${id}`),
// // };

// // /** platformConfigApi — SUPER_ADMIN tenant_config (per-tenant). */
// // export const platformConfigApi = {
// //   get: (tenantId: number | string) =>
// //     http.get<PlatformTenantConfig>(
// //       `/api/platform/admin/tenants/${tenantId}/config`,
// //     ),
// //   setIntegrationMode: (tenantId: number | string, integration_mode: IntegrationMode) =>
// //     http.patch<{ tenant_id: number; integration_mode: IntegrationMode; updated_at: string }>(
// //       `/api/platform/admin/tenants/${tenantId}/integration-mode`,
// //       { integration_mode },
// //     ),
// // };

// // /** pipelineApi — 5-stage GTM workflow orchestrator. */
// // export const pipelineApi = {
// //   runStage: (body: PipelineRunStageInput) =>
// //     http.post<PipelineStageResult>("/api/v1/pipeline/run-stage", body),
// //   status: () => http.get<PipelineStatus>("/api/v1/pipeline/status"),
// // };

// // /** flowTemplatesApi — pre-built flow template definitions + clone. */
// // export const flowTemplatesApi = {
// //   list: () => http.get<FlowTemplate[]>("/api/v1/flow-templates"),
// //   clone: (body: FlowTemplateCloneInput) =>
// //     http.post<{ flow_id: string; name: string }>("/api/v1/flow-templates/clone", body),
// // };

// // /** publicUnsubscribeApi — one-click unsubscribe (no auth, FR-E14-018). */
// // export async function publicUnsubscribeApi(
// //   token: string,
// //   tenant_slug: string,
// // ): Promise<{ unsubscribed: boolean; message: string }> {
// //   return http.post<{ unsubscribed: boolean; message: string }>(
// //     "/api/v1/public/unsubscribe",
// //     { token, tenant_slug },
// //   );
// // }

// // /** flowAnalyticsApi — per-flow analytics dashboard. */
// // export const flowAnalyticsApi = {
// //   list: () =>
// //     http.get<FlowAnalyticsSummary[]>("/api/v1/flow-analytics"),
// //   get: (flowId: string) =>
// //     http.get<FlowAnalyticsSummary>(`/api/v1/flow-analytics/${flowId}`),
// // };

// // /** autopilotQueueApi — autopilot queue management with enqueue/trigger/cancel. */
// // export const autopilotQueueApi = {
// //   list: (params?: { status?: string; limit?: number; offset?: number }) =>
// //     http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
// //       "/api/v1/autopilot-queue",
// //       params,
// //     ),
// //   stats: () =>
// //     http.get<AutopilotQueueStats>("/api/v1/autopilot-queue/stats"),
// //   enqueue: (body: AutopilotQueueEnqueueBody) =>
// //     http.post<AutopilotQueueItem>("/api/v1/autopilot-queue/enqueue", body),
// //   triggerScheduler: () =>
// //     http.post<{ triggered: boolean; message: string }>("/api/v1/autopilot-queue/trigger-scheduler"),
// //   setAutonomousMode: (enabled: boolean) =>
// //     http.put<{ autonomousMode: boolean; message: string }>("/api/v1/autopilot-queue/autonomous-mode", { enabled }),
// //   cancel: (id: string) =>
// //     http.delete<{ message: string }>(`/api/v1/autopilot-queue/${id}`),
// // };


// /**
//  * apiClient.ts — central axios instance with Bearer + tenant interceptors.
//  *
//  * The access token is read from a module-level holder kept in sync by
//  * `AuthContext` (Section 7.6 of the migration doc). A `VITE_DEV_TENANT_SLUG`
//  * override lets local dev target a specific tenant schema without Keycloak
//  * claims.
//  */
// import axios, { AxiosError, type AxiosInstance } from "axios";
// import type {
//   LandingContent,
//   ContactInfo,
//   ContactMessage,
//   Plan,
//   TenantSignupRequest,
//   TenantSignupStatus,
//   TenantSignupRow,
//   TenantRow,
//   PlatformMetrics,
//   AuditLog,
//   TenantIntegration,
//   IntegrationMode,
//   IntegrationCatalogEntry,
//   IntegrationTestResult,
//   GlobalLlmConfig,
//   GlobalLlmConfigInput,
//   GlobalLlmTestResult,
//   SenderIdentity,
//   EmailQuota,
//   UserDashboard,
//   ManagerDashboard,
//   UsageSummary,
//   UsageManagerRollup,
//   UsagePlatformRollup,
//   CostTableEntry,
//   CostTableInput,
//   DsrSubmission,
//   DsrSubmissionResponse,
//   DsrStatusResponse,
//   DsrRow,
//   ConsentStatus,
//   RetentionStatus,
//   MailBridgeConfig,
//   MailBridgeConfigInput,
//   ProspectingFlow,
//   ProspectingFlowInput,
//   FlowRun,
//   FlowAbTest,
//   FlowAbTestInput,
//   FlowWebhook,
//   FlowWebhookInput,
//   AutopilotQueueItem,
//   RateLimit,
//   RateLimitInput,
//   RateLimitLog,
//   SchedulerStatus,
//   ManualTickResponse,
//   SchedulerRun,
//   Meeting,
//   MeetingInput,
//   MeetingPrep,
//   DomainEnrichment,
//   CallLog,
//   CallLogInput,
//   PlatformTenantConfig,
//   FlowAnalyticsSummary,
//   AutopilotQueueStats,
//   AutopilotQueueEnqueueBody,
//   PipelineStageResult,
//   PipelineStatus,
//   PipelineRunStageInput,
//   FlowTemplate,
//   FlowTemplateCloneInput,
// } from "@/types/common";

// let currentAccessToken: string | null = null;

// export function setAccessToken(token: string | null): void {
//   currentAccessToken = token;
// }

// export function getAccessToken(): string | null {
//   return currentAccessToken;
// }

// const DEV_TENANT_SLUG = import.meta.env.VITE_DEV_TENANT_SLUG ?? "";

// export const apiClient: AxiosInstance = axios.create({
//   baseURL: "/",
//   // 300s (5 min) — local LLMs (Ollama) can take 90–180s to respond.
//   // Cloud providers (Groq, OpenAI) respond in 2–10s so this has no
//   // practical impact on normal usage.
//   timeout: 300_000,
//   headers: { "Content-Type": "application/json" },
// });

// apiClient.interceptors.request.use((config) => {
//   const token = getAccessToken();
//   if (token) {
//     config.headers.Authorization = `Bearer ${token}`;
//   }
//   if (DEV_TENANT_SLUG) {
//     config.headers["X-Tenant-Slug"] = DEV_TENANT_SLUG;
//   }
//   return config;
// });

// apiClient.interceptors.response.use(
//   (resp) => resp,
//   (error: AxiosError) => {
//     // Normalise 401 → trigger re-login via AuthContext (handled by consumers).
//     if (error.response?.status === 401) {
//       window.dispatchEvent(new CustomEvent("outrena:unauthorized"));
//     }
//     return Promise.reject(error);
//   },
// );

// /** Convenience typed request helpers used by feature service modules. */
// export const http = {
//   get: <T>(url: string, params?: Record<string, unknown>) =>
//     apiClient.get<T>(url, { params }).then((r) => r.data),
//   post: <T>(url: string, body?: unknown) =>
//     apiClient.post<T>(url, body).then((r) => r.data),
//   put: <T>(url: string, body?: unknown) =>
//     apiClient.put<T>(url, body).then((r) => r.data),
//   patch: <T>(url: string, body?: unknown) =>
//     apiClient.patch<T>(url, body).then((r) => r.data),
//   delete: <T>(url: string) => apiClient.delete<T>(url).then((r) => r.data),
// };

// /**
//  * publicApi — calls to `/api/v1/public/*` and `/api/v1/tenant-signup*`.
//  *
//  * These endpoints are intentionally NOT authenticated: marketing pages, plan
//  * list, contact form, tenant self-signup wizard. They still go through the
//  * shared `apiClient` instance (so dev-tenant header is preserved), but the
//  * backend does not require a Bearer token.
//  */
// export const publicApi = {
//   landing: () => http.get<LandingContent>("/api/v1/public/landing"),
//   plans: () => http.get<Plan[]>("/api/v1/public/plans"),
//   contactInfo: () => http.get<ContactInfo>("/api/v1/public/contact-info"),
//   contact: (body: ContactMessage) =>
//     apiClient.post("/api/v1/public/contact", body).then((r) => r.status),
//   checkSubdomain: (subdomain: string) =>
//     apiClient
//       .get<{ available: boolean }>("/api/v1/public/subdomain-check", {
//         params: { subdomain },
//       })
//       .then((r) => r.data)
//       .catch(() => ({ available: false })),
//   submitSignup: (body: TenantSignupRequest) =>
//     http.post<{ signup_id: string; status: string }>(
//       "/api/v1/tenant-signup",
//       body,
//     ),
//   signupStatus: (signupId: string) =>
//     http.get<TenantSignupStatus>(
//       `/api/v1/tenant-signup/${signupId}/status`,
//     ),
// };

// /**
//  * platformApi — SUPER_ADMIN calls to `/api/platform/admin/*`.
//  *
//  * Uses the authenticated `apiClient` (Bearer + tenant header) but targets the
//  * cross-tenant platform admin router. All calls are role-gated server-side to
//  * SUPER_ADMIN.
//  */
// export const platformApi = {
//   signups: (status?: string) =>
//     http.get<TenantSignupRow[]>("/api/platform/admin/signups", {
//       status: status ?? "pending",
//     }),
//   approveSignup: (id: string) =>
//     http.post<{ tenant_slug: string; provisioned: boolean }>(
//       `/api/platform/admin/signups/${id}/approve`,
//     ),
//   rejectSignup: (id: string, reason: string) =>
//     http.post(`/api/platform/admin/signups/${id}/reject`, { reason }),
//   tenants: () => http.get<TenantRow[]>("/api/platform/admin/tenants"),
//   suspendTenant: (id: string) =>
//     http.post(`/api/platform/admin/tenants/${id}/suspend`),
//   reactivateTenant: (id: string) =>
//     http.post(`/api/platform/admin/tenants/${id}/reactivate`),
//   metrics: () => http.get<PlatformMetrics>("/api/platform/admin/metrics"),
//   auditLogs: (params?: { limit?: number; tenant_slug?: string; action?: string }) =>
//     http.get<AuditLog[]>("/api/platform/admin/audit-logs", params),
//   // ISSUE-3 FIX: Create tenant endpoint (provisioning — base platform router, not /admin)
//   createTenant: (body: {
//     slug: string;
//     name: string;
//     admin_email: string;
//     admin_first_name: string;
//     admin_last_name: string;
//     temporary_password?: string;
//     send_invitation: boolean;
//   }) =>
//     http.post<{ slug: string; status: string; url: string }>(
//       "/api/platform/tenants",
//       body,
//     ),
// };

// /* ─────────────────────────────────────────────────────────────────────────── */
// /* SAAS2-FE: Workstream helpers (integrations, LLM, users, usage, GDPR).      */
// /* Each helper targets the exact endpoints specified in the SAAS2-FE task.    */
// /* ─────────────────────────────────────────────────────────────────────────── */

// /**
//  * integrationConfigApi — dual-path integration config.
//  *
//  * Tenant side (`/api/v1/integrations`): list, create, update, test.
//  * Platform side (`/api/platform/admin/...`): per-tenant mode + catalog.
//  */
// export const integrationConfigApi = {
//   tenantList: () => http.get<TenantIntegration[]>("/api/v1/integrations"),
//   tenantCreate: (body: {
//     type: string;
//     name: string;
//     key_source: "tenant" | "platform";
//     api_key?: string;
//   }) => http.post<TenantIntegration>("/api/v1/integrations", {
//     platform: body.type,
//     name: body.name,
//     key_source: body.key_source,
//     apiKey: body.key_source === "tenant" ? body.api_key : undefined,
//   }),
//   tenantUpdate: (
//     id: string,
//     body: Partial<{
//       name: string;
//       key_source: "tenant" | "platform";
//       api_key?: string;
//       is_active: boolean;
//     }>,
//   ) => http.put<TenantIntegration>(`/api/v1/integrations/${id}`, {
//     name: body.name,
//     key_source: body.key_source,
//     apiKey: body.api_key,
//     isActive: body.is_active,
//   }),
//   tenantTest: (id: string) =>
//     http.get<IntegrationTestResult>(
//       `/api/v1/integrations/${id}/credentials-test`,
//     ),
//   // NOTE (Task 2-b finding 9): platformGetConfig removed — duplicate of
//   // platformConfigApi.get() which is the one PlatformSettingsPage actually uses.
//   platformSetMode: (tenantId: string, integration_mode: IntegrationMode) =>
//     http.patch<{ tenant_id: string; integration_mode: IntegrationMode }>(
//       `/api/platform/admin/tenants/${tenantId}/integration-mode`,
//       { integration_mode },
//     ),
//   catalog: () =>
//     http.get<IntegrationCatalogEntry[]>(
//       "/api/platform/admin/integration-catalog",
//     ),
// };

// /**
//  * globalLlmApi — SUPER_ADMIN global LLM config (`/api/platform/admin/llm-configs`).
//  */
// export const globalLlmApi = {
//   list: () =>
//     http.get<GlobalLlmConfig[]>("/api/platform/admin/llm-configs"),
//   create: (body: GlobalLlmConfigInput) =>
//     http.post<GlobalLlmConfig>("/api/platform/admin/llm-configs", body),
//   update: (id: string, body: GlobalLlmConfigInput) =>
//     http.put<GlobalLlmConfig>(`/api/platform/admin/llm-configs/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(
//       `/api/platform/admin/llm-configs/${id}`,
//     ),
//   setDefault: (id: string) =>
//     http.post<{ message: string }>(
//       `/api/platform/admin/llm-configs/${id}/set-default`,
//     ),
//   test: (id: string) =>
//     http.post<GlobalLlmTestResult>(
//       `/api/platform/admin/llm-configs/${id}/test`,
//     ),
// };

// /**
//  * senderIdentityApi — per-user sender identities (`/api/v1/users/me/...`).
//  */
// export const senderIdentityApi = {
//   list: () =>
//     http.get<SenderIdentity[]>("/api/v1/users/me/sender-identities"),
//   create: (body: {
//     email: string;
//     email_type: "platform_assigned" | "corporate";
//     display_name?: string;
//   }) =>
//     http.post<SenderIdentity>("/api/v1/users/me/sender-identities", body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(
//       `/api/v1/users/me/sender-identities/${id}`,
//     ),
//   setDefault: (id: string) =>
//     http.post<{ message: string }>(
//       `/api/v1/users/me/sender-identities/${id}/set-default`,
//     ),
//   myQuota: () => http.get<EmailQuota>("/api/v1/users/me/email-quota"),
//   // NOTE (Task 2-b finding 9): teamQuotas removed — was unused. Re-add from
//   // git history (or AUDIT-FE-1 §C.7) when a Team Quotas card is built.
// };

// /**
//  * managerDashboardApi — per-user + manager dashboards (`/api/v1/dashboard*`).
//  */
// export const managerDashboardApi = {
//   mine: () =>
//     http.get<UserDashboard>("/api/v1/dashboard", { user_id: "me" }),
//   // NOTE (Task 2-b finding 9): user(userId) removed — was unused. Re-add when
//   // a per-rep drill-down is built into ManagerDashboardPage.
//   manager: () => http.get<ManagerDashboard>("/api/v1/dashboard/manager"),
// };

// /**
//  * usageApi — usage + cost rollups (`/api/v1/usage/*` + platform equivalents).
//  */
// export const usageApi = {
//   me: (period: string) =>
//     http.get<UsageSummary>("/api/v1/usage/me", { period }),
//   // NOTE (Task 2-b finding 9): user(userId, period) + tenant(period) removed —
//   // were unused. Re-add when per-user / per-tenant usage drill-downs are built.
//   manager: (period: string) =>
//     http.get<UsageManagerRollup>("/api/v1/usage/manager", { period }),
//   platform: (period: string) =>
//     http.get<UsagePlatformRollup>(
//       "/api/v1/usage/platform",
//       { period },
//     ),
//   costTable: () =>
//     http.get<CostTableEntry[]>("/api/v1/usage/cost-table"),
//   updateCostTable: (entries: CostTableInput[]) =>
//     http.put<CostTableEntry[]>("/api/v1/usage/cost-table", entries),
// };

// /**
//  * gdprApi — GDPR DSR + consent + retention endpoints.
//  *
//  * Public DSR (no auth): `submitDsr` + `dsrStatus`.
//  * Authenticated tenant-admin DSR workflow: `list`, `process`, `complete`,
//  * `reject`, `export`.
//  * Consent: `getConsent`, `grant`, `withdraw`.
//  * Retention: `status`, `enforce`.
//  */
// export const gdprApi = {
//   // Public DSR
//   submitDsr: (body: DsrSubmission) =>
//     http.post<DsrSubmissionResponse>("/api/v1/gdpr/dsr", body),
//   dsrStatus: (dsrId: string) =>
//     http.get<DsrStatusResponse>(`/api/v1/gdpr/dsr/${dsrId}/status`),
//   // Tenant-admin DSR workflow
//   list: (status?: string) =>
//     http.get<DsrRow[]>("/api/v1/gdpr/dsrs", status ? { status } : undefined),
//   process: (id: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/process`),
//   complete: (id: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/complete`),
//   reject: (id: string, reason?: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/reject`, { reason }),
//   // NOTE (Task 2-b finding 9): exportUrl + grant removed — were unused.
//   // GdprCenterPage builds export URLs inline; the consent grant endpoint
//   // (/api/v1/gdpr/consent/grant) is still available on the backend. Re-add
//   // these helpers when the corresponding UI is built.
//   // Consent
//   getConsent: (email: string) =>
//     http.get<ConsentStatus>(`/api/v1/gdpr/consent/${encodeURIComponent(email)}`),
//   withdraw: (email: string) =>
//     http.post("/api/v1/gdpr/consent/withdraw", { email }),
//   // Retention
//   retentionStatus: () =>
//     http.get<RetentionStatus>("/api/v1/gdpr/retention-status"),
//   enforceRetention: () =>
//     http.post<RetentionStatus>("/api/v1/gdpr/retention/enforce"),
// };

// /* ─────────────────────────────────────────────────────────────────────────── */
// /* FIX-FE-1: New feature-page helpers (MailBridge, Flows, RateLimits,         */
// /* Scheduler, Meetings, DomainEnrichment, CallLogs, PlatformTenantConfig).    */
// /* Each helper targets the exact endpoints exposed by the backend router.     */
// /* ─────────────────────────────────────────────────────────────────────────── */

// /** mailbridgeApi — per-tenant MailBridge config CRUD (`/api/v1/mailbridge/config`). */
// export const mailbridgeApi = {
//   list: () => http.get<MailBridgeConfig[]>("/api/v1/mailbridge/config"),
//   create: (body: MailBridgeConfigInput) =>
//     http.post<MailBridgeConfig>("/api/v1/mailbridge/config", body),
//   get: (id: string) =>
//     http.get<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`),
//   update: (id: string, body: Partial<MailBridgeConfigInput>) =>
//     http.put<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/mailbridge/config/${id}`),
//   /** Send a test email through this config (best-effort). */
//   sendTest: (body: { to: string; subject: string; body: string; configId?: string }) =>
//     http.post<{ messageId: string; status: string; accepted: boolean }>(
//       "/api/v1/mailbridge/send",
//       body,
//     ),
// };

// /** flowsApi — ProspectingFlow + FlowRun + FlowAbTest + FlowWebhook + AutopilotQueue. */
// export const flowsApi = {
//   // ProspectingFlow definitions
//   listFlows: (params?: { isActive?: boolean; isTemplate?: boolean; limit?: number; offset?: number }) =>
//     http.get<{ items: ProspectingFlow[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows",
//       params,
//     ),
//   createFlow: (body: ProspectingFlowInput) =>
//     http.post<ProspectingFlow>("/api/v1/flows", body),
//   getFlow: (id: string) => http.get<ProspectingFlow>(`/api/v1/flows/${id}`),
//   updateFlow: (id: string, body: Partial<ProspectingFlowInput>) =>
//     http.put<ProspectingFlow>(`/api/v1/flows/${id}`, body),
//   removeFlow: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/${id}`),
//   // FlowRuns (list + detail; runs are created via /autopilot)
//   listRuns: (params?: { flowId?: string; icpProfileId?: string; status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: FlowRun[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/runs",
//       params,
//     ),
//   getRun: (runId: string) => http.get<FlowRun>(`/api/v1/flows/runs/${runId}`),
//   // Flow A/B tests
//   listAbTests: (params?: { icpProfileId?: string; status?: string }) =>
//     http.get<{ items: FlowAbTest[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/ab-tests",
//       params,
//     ),
//   createAbTest: (body: FlowAbTestInput) =>
//     http.post<FlowAbTest>("/api/v1/flows/ab-tests", body),
//   getAbTest: (id: string) => http.get<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`),
//   updateAbTest: (id: string, body: Partial<FlowAbTestInput> & { status?: string; significance?: string; summary?: string }) =>
//     http.put<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`, body),
//   removeAbTest: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/ab-tests/${id}`),
//   // Flow webhooks
//   listWebhooks: (params?: { flowId?: string; isActive?: boolean }) =>
//     http.get<{ items: FlowWebhook[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/webhooks",
//       params,
//     ),
//   createWebhook: (body: FlowWebhookInput) =>
//     http.post<FlowWebhook>("/api/v1/flows/webhooks", body),
//   getWebhook: (id: string) => http.get<FlowWebhook>(`/api/v1/flows/webhooks/${id}`),
//   updateWebhook: (id: string, body: Partial<FlowWebhookInput>) =>
//     http.put<FlowWebhook>(`/api/v1/flows/webhooks/${id}`, body),
//   removeWebhook: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/webhooks/${id}`),
//   // AutopilotQueue (read-only)
//   listQueue: (params?: { status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/queue",
//       params,
//     ),
// };

// /** rateLimitsApi — RateLimit + RateLimitLog. */
// export const rateLimitsApi = {
//   list: (params?: { platform?: string; isActive?: boolean; limit?: number; offset?: number }) =>
//     http.get<{ items: RateLimit[]; total: number; limit: number; offset: number }>(
//       "/api/v1/rate-limits",
//       params,
//     ),
//   create: (body: RateLimitInput) =>
//     http.post<RateLimit>("/api/v1/rate-limits", body),
//   get: (id: string) => http.get<RateLimit>(`/api/v1/rate-limits/${id}`),
//   update: (id: string, body: Partial<RateLimitInput> & { count?: number }) =>
//     http.put<RateLimit>(`/api/v1/rate-limits/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/rate-limits/${id}`),
//   resetCounter: (id: string) =>
//     http.post<RateLimit>(`/api/v1/rate-limits/${id}/reset`),
//   listLogs: (params?: { key?: string; platform?: string; flowRunId?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: RateLimitLog[]; total: number; limit: number; offset: number }>(
//       "/api/v1/rate-limits/logs",
//       params,
//     ),
// };

// /** schedulerApi — scheduler status + manual tick + trigger + runs. */
// export const schedulerApi = {
//   status: () => http.get<SchedulerStatus>("/api/v1/scheduler/status"),
//   tick: (body?: { tenantScoped?: boolean; maxSend?: number }) =>
//     http.post<ManualTickResponse>("/api/v1/scheduler/tick", body ?? {}),
//   trigger: () =>
//     http.post<{ triggered: boolean; message: string; runId: string | null }>(
//       "/api/v1/scheduler/trigger",
//     ),
//   runs: (params?: { limit?: number; offset?: number }) =>
//     http.get<{ items: SchedulerRun[]; total: number }>(
//       "/api/v1/scheduler/runs",
//       params,
//     ),
// };

// /** meetingsApi — Meeting CRUD. The backend Meeting model lives at
//  * `/api/v1/meetings`; if the route is missing (pre-FIX-BE follow-up), the
//  * page degrades to an error state. The MeetingPrep generate endpoint is
//  * backed by the existing `/api/v1/meeting-prep` router. */
// export const meetingsApi = {
//   list: () => http.get<Meeting[]>("/api/v1/meetings"),
//   create: (body: MeetingInput) => http.post<Meeting>("/api/v1/meetings", body),
//   get: (id: string) => http.get<Meeting>(`/api/v1/meetings/${id}`),
//   update: (id: string, body: Partial<MeetingInput>) =>
//     http.patch<Meeting>(`/api/v1/meetings/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/meetings/${id}`),
//   // Meeting-prep integration
//   generatePrep: (prospectId: string, callType: string = "discovery") =>
//     http.post<{ id: string; brief: string }>("/api/v1/meeting-prep/generate", {
//       prospectId,
//       callType,
//     }),
//   getPrep: (briefId: string) =>
//     http.get<MeetingPrep>(`/api/v1/meeting-prep/${briefId}`),
//   listPrepForProspect: (prospectId: string) =>
//     http.get<MeetingPrep[]>("/api/v1/meeting-prep", { prospect_id: prospectId }),
// };

// /** domainEnrichApi — fetch/cache enrichment for a domain. */
// export const domainEnrichApi = {
//   enrich: (domain: string, forceRefresh = false) =>
//     http.post<DomainEnrichment>("/api/v1/domain-enrich", { domain, forceRefresh }),
//   enrichBatch: (domains: string[]) =>
//     http.post<{ enriched: DomainEnrichment[]; failed: string[] }>(
//       "/api/v1/domain-enrich/batch",
//       { domains },
//     ),
//   get: (domain: string) =>
//     http.get<DomainEnrichment>(`/api/v1/domain-enrich/${encodeURIComponent(domain)}`),
// };

// /** callLogsApi — CallLog CRUD. */
// export const callLogsApi = {
//   list: (params?: { prospectId?: string; outcome?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: CallLog[]; total: number; limit: number; offset: number }>(
//       "/api/v1/call-logs",
//       params,
//     ),
//   create: (body: CallLogInput) =>
//     http.post<CallLog>("/api/v1/call-logs", body),
//   get: (id: string) => http.get<CallLog>(`/api/v1/call-logs/${id}`),
//   update: (id: string, body: Partial<CallLogInput>) =>
//     http.patch<CallLog>(`/api/v1/call-logs/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/call-logs/${id}`),
// };

// /** platformConfigApi — SUPER_ADMIN tenant_config (per-tenant). */
// export const platformConfigApi = {
//   get: (tenantId: number | string) =>
//     http.get<PlatformTenantConfig>(
//       `/api/platform/admin/tenants/${tenantId}/config`,
//     ),
//   setIntegrationMode: (tenantId: number | string, integration_mode: IntegrationMode) =>
//     http.patch<{ tenant_id: number; integration_mode: IntegrationMode; updated_at: string }>(
//       `/api/platform/admin/tenants/${tenantId}/integration-mode`,
//       { integration_mode },
//     ),
// };

// /** pipelineApi — 5-stage GTM workflow orchestrator. */
// export const pipelineApi = {
//   runStage: (body: PipelineRunStageInput) =>
//     http.post<PipelineStageResult>("/api/v1/pipeline/run-stage", body),
//   status: () => http.get<PipelineStatus>("/api/v1/pipeline/status"),
// };

// /** flowTemplatesApi — pre-built flow template definitions + clone. */
// export const flowTemplatesApi = {
//   list: () => http.get<FlowTemplate[]>("/api/v1/flow-templates"),
//   clone: (body: FlowTemplateCloneInput) =>
//     http.post<{ flow_id: string; name: string }>("/api/v1/flow-templates/clone", body),
// };

// /** publicUnsubscribeApi — one-click unsubscribe (no auth, FR-E14-018). */
// export async function publicUnsubscribeApi(
//   token: string,
//   tenant_slug: string,
// ): Promise<{ unsubscribed: boolean; message: string }> {
//   return http.post<{ unsubscribed: boolean; message: string }>(
//     "/api/v1/public/unsubscribe",
//     { token, tenant_slug },
//   );
// }

// /** flowAnalyticsApi — per-flow analytics dashboard. */
// export const flowAnalyticsApi = {
//   list: () =>
//     http.get<FlowAnalyticsSummary[]>("/api/v1/flow-analytics"),
//   get: (flowId: string) =>
//     http.get<FlowAnalyticsSummary>(`/api/v1/flow-analytics/${flowId}`),
// };

// /** autopilotQueueApi — autopilot queue management with enqueue/trigger/cancel. */
// export const autopilotQueueApi = {
//   list: (params?: { status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
//       "/api/v1/autopilot-queue",
//       params,
//     ),
//   stats: () =>
//     http.get<AutopilotQueueStats>("/api/v1/autopilot-queue/stats"),
//   enqueue: (body: AutopilotQueueEnqueueBody) =>
//     http.post<AutopilotQueueItem>("/api/v1/autopilot-queue/enqueue", body),
//   triggerScheduler: () =>
//     http.post<{ triggered: boolean; message: string }>("/api/v1/autopilot-queue/trigger-scheduler"),
//   setAutonomousMode: (enabled: boolean) =>
//     http.put<{ autonomousMode: boolean; message: string }>("/api/v1/autopilot-queue/autonomous-mode", { enabled }),
//   cancel: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/autopilot-queue/${id}`),
// };
// /**
//  * apiClient.ts — central axios instance with Bearer + tenant interceptors.
//  *
//  * The access token is read from a module-level holder kept in sync by
//  * `AuthContext` (Section 7.6 of the migration doc). A `VITE_DEV_TENANT_SLUG`
//  * override lets local dev target a specific tenant schema without Keycloak
//  * claims.
//  */
// import axios, { AxiosError, type AxiosInstance } from "axios";
// import type {
//   LandingContent,
//   ContactInfo,
//   ContactMessage,
//   Plan,
//   TenantSignupRequest,
//   TenantSignupStatus,
//   TenantSignupRow,
//   TenantRow,
//   PlatformMetrics,
//   AuditLog,
//   TenantIntegration,
//   IntegrationMode,
//   IntegrationCatalogEntry,
//   IntegrationTestResult,
//   GlobalLlmConfig,
//   GlobalLlmConfigInput,
//   GlobalLlmTestResult,
//   SenderIdentity,
//   EmailQuota,
//   UserDashboard,
//   ManagerDashboard,
//   UsageSummary,
//   UsageManagerRollup,
//   UsagePlatformRollup,
//   CostTableEntry,
//   CostTableInput,
//   DsrSubmission,
//   DsrSubmissionResponse,
//   DsrStatusResponse,
//   DsrRow,
//   ConsentStatus,
//   RetentionStatus,
//   MailBridgeConfig,
//   MailBridgeConfigInput,
//   ProspectingFlow,
//   ProspectingFlowInput,
//   FlowRun,
//   FlowAbTest,
//   FlowAbTestInput,
//   FlowWebhook,
//   FlowWebhookInput,
//   AutopilotQueueItem,
//   RateLimit,
//   RateLimitInput,
//   RateLimitLog,
//   SchedulerStatus,
//   ManualTickResponse,
//   SchedulerRun,
//   Meeting,
//   MeetingInput,
//   MeetingPrep,
//   DomainEnrichment,
//   CallLog,
//   CallLogInput,
//   PlatformTenantConfig,
//   FlowAnalyticsSummary,
//   AutopilotQueueStats,
//   AutopilotQueueEnqueueBody,
//   PipelineStageResult,
//   PipelineStatus,
//   PipelineRunStageInput,
//   FlowTemplate,
//   FlowTemplateCloneInput,
// } from "@/types/common";

// let currentAccessToken: string | null = null;

// export function setAccessToken(token: string | null): void {
//   currentAccessToken = token;
// }

// export function getAccessToken(): string | null {
//   return currentAccessToken;
// }

// const DEV_TENANT_SLUG = import.meta.env.VITE_DEV_TENANT_SLUG ?? "";

// export const apiClient: AxiosInstance = axios.create({
//   baseURL: "/",
//   timeout: 15_000,
//   headers: { "Content-Type": "application/json" },
// });

// apiClient.interceptors.request.use((config) => {
//   const token = getAccessToken();
//   if (token) {
//     config.headers.Authorization = `Bearer ${token}`;
//   }
//   if (DEV_TENANT_SLUG) {
//     config.headers["X-Tenant-Slug"] = DEV_TENANT_SLUG;
//   }
//   return config;
// });

// apiClient.interceptors.response.use(
//   (resp) => resp,
//   (error: AxiosError) => {
//     // Normalise 401 → trigger re-login via AuthContext (handled by consumers).
//     if (error.response?.status === 401) {
//       window.dispatchEvent(new CustomEvent("outrena:unauthorized"));
//     }
//     return Promise.reject(error);
//   },
// );

// /** Convenience typed request helpers used by feature service modules. */
// export const http = {
//   get: <T>(url: string, params?: Record<string, unknown>) =>
//     apiClient.get<T>(url, { params }).then((r) => r.data),
//   post: <T>(url: string, body?: unknown) =>
//     apiClient.post<T>(url, body).then((r) => r.data),
//   put: <T>(url: string, body?: unknown) =>
//     apiClient.put<T>(url, body).then((r) => r.data),
//   patch: <T>(url: string, body?: unknown) =>
//     apiClient.patch<T>(url, body).then((r) => r.data),
//   delete: <T>(url: string) => apiClient.delete<T>(url).then((r) => r.data),
// };

// /**
//  * publicApi — calls to `/api/v1/public/*` and `/api/v1/tenant-signup*`.
//  *
//  * These endpoints are intentionally NOT authenticated: marketing pages, plan
//  * list, contact form, tenant self-signup wizard. They still go through the
//  * shared `apiClient` instance (so dev-tenant header is preserved), but the
//  * backend does not require a Bearer token.
//  */
// export const publicApi = {
//   landing: () => http.get<LandingContent>("/api/v1/public/landing"),
//   plans: () => http.get<Plan[]>("/api/v1/public/plans"),
//   contactInfo: () => http.get<ContactInfo>("/api/v1/public/contact-info"),
//   contact: (body: ContactMessage) =>
//     apiClient.post("/api/v1/public/contact", body).then((r) => r.status),
//   checkSubdomain: (subdomain: string) =>
//     apiClient
//       .get<{ available: boolean }>("/api/v1/public/subdomain-check", {
//         params: { subdomain },
//       })
//       .then((r) => r.data)
//       .catch(() => ({ available: false })),
//   submitSignup: (body: TenantSignupRequest) =>
//     http.post<{ signup_id: string; status: string }>(
//       "/api/v1/tenant-signup",
//       body,
//     ),
//   signupStatus: (signupId: string) =>
//     http.get<TenantSignupStatus>(
//       `/api/v1/tenant-signup/${signupId}/status`,
//     ),
// };

// /**
//  * platformApi — SUPER_ADMIN calls to `/api/platform/admin/*`.
//  *
//  * Uses the authenticated `apiClient` (Bearer + tenant header) but targets the
//  * cross-tenant platform admin router. All calls are role-gated server-side to
//  * SUPER_ADMIN.
//  */
// export const platformApi = {
//   signups: (status?: string) =>
//     http.get<TenantSignupRow[]>("/api/platform/admin/signups", {
//       status: status ?? "pending",
//     }),
//   approveSignup: (id: string) =>
//     http.post<{ tenant_slug: string; provisioned: boolean }>(
//       `/api/platform/admin/signups/${id}/approve`,
//     ),
//   rejectSignup: (id: string, reason: string) =>
//     http.post(`/api/platform/admin/signups/${id}/reject`, { reason }),
//   tenants: () => http.get<TenantRow[]>("/api/platform/admin/tenants"),
//   suspendTenant: (id: string) =>
//     http.post(`/api/platform/admin/tenants/${id}/suspend`),
//   reactivateTenant: (id: string) =>
//     http.post(`/api/platform/admin/tenants/${id}/reactivate`),
//   metrics: () => http.get<PlatformMetrics>("/api/platform/admin/metrics"),
//   auditLogs: (params?: { limit?: number; tenant_slug?: string; action?: string }) =>
//     http.get<AuditLog[]>("/api/platform/admin/audit-logs", params),
//   // ISSUE-3 FIX: Create tenant endpoint (provisioning — base platform router, not /admin)
//   createTenant: (body: {
//     slug: string;
//     name: string;
//     admin_email: string;
//     admin_first_name: string;
//     admin_last_name: string;
//     temporary_password?: string;
//     send_invitation: boolean;
//   }) =>
//     http.post<{ slug: string; status: string; url: string }>(
//       "/api/platform/tenants",
//       body,
//     ),
// };

// /* ─────────────────────────────────────────────────────────────────────────── */
// /* SAAS2-FE: Workstream helpers (integrations, LLM, users, usage, GDPR).      */
// /* Each helper targets the exact endpoints specified in the SAAS2-FE task.    */
// /* ─────────────────────────────────────────────────────────────────────────── */

// /**
//  * integrationConfigApi — dual-path integration config.
//  *
//  * Tenant side (`/api/v1/integrations`): list, create, update, test.
//  * Platform side (`/api/platform/admin/...`): per-tenant mode + catalog.
//  */
// export const integrationConfigApi = {
//   tenantList: () => http.get<TenantIntegration[]>("/api/v1/integrations"),
//   tenantCreate: (body: {
//     type: string;
//     name: string;
//     key_source: "tenant" | "platform";
//     api_key?: string;
//   }) => http.post<TenantIntegration>("/api/v1/integrations", {
//     platform: body.type,
//     name: body.name,
//     key_source: body.key_source,
//     apiKey: body.key_source === "tenant" ? body.api_key : undefined,
//   }),
//   tenantUpdate: (
//     id: string,
//     body: Partial<{
//       name: string;
//       key_source: "tenant" | "platform";
//       api_key?: string;
//       is_active: boolean;
//     }>,
//   ) => http.put<TenantIntegration>(`/api/v1/integrations/${id}`, {
//     name: body.name,
//     key_source: body.key_source,
//     apiKey: body.api_key,
//     isActive: body.is_active,
//   }),
//   tenantTest: (id: string) =>
//     http.get<IntegrationTestResult>(
//       `/api/v1/integrations/${id}/credentials-test`,
//     ),
//   // NOTE (Task 2-b finding 9): platformGetConfig removed — duplicate of
//   // platformConfigApi.get() which is the one PlatformSettingsPage actually uses.
//   platformSetMode: (tenantId: string, integration_mode: IntegrationMode) =>
//     http.patch<{ tenant_id: string; integration_mode: IntegrationMode }>(
//       `/api/platform/admin/tenants/${tenantId}/integration-mode`,
//       { integration_mode },
//     ),
//   catalog: () =>
//     http.get<IntegrationCatalogEntry[]>(
//       "/api/platform/admin/integration-catalog",
//     ),
// };

// /**
//  * globalLlmApi — SUPER_ADMIN global LLM config (`/api/platform/admin/llm-configs`).
//  */
// export const globalLlmApi = {
//   list: () =>
//     http.get<GlobalLlmConfig[]>("/api/platform/admin/llm-configs"),
//   create: (body: GlobalLlmConfigInput) =>
//     http.post<GlobalLlmConfig>("/api/platform/admin/llm-configs", body),
//   update: (id: string, body: GlobalLlmConfigInput) =>
//     http.put<GlobalLlmConfig>(`/api/platform/admin/llm-configs/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(
//       `/api/platform/admin/llm-configs/${id}`,
//     ),
//   setDefault: (id: string) =>
//     http.post<{ message: string }>(
//       `/api/platform/admin/llm-configs/${id}/set-default`,
//     ),
//   test: (id: string) =>
//     http.post<GlobalLlmTestResult>(
//       `/api/platform/admin/llm-configs/${id}/test`,
//     ),
// };

// /**
//  * senderIdentityApi — per-user sender identities (`/api/v1/users/me/...`).
//  */
// export const senderIdentityApi = {
//   list: () =>
//     http.get<SenderIdentity[]>("/api/v1/users/me/sender-identities"),
//   create: (body: {
//     email: string;
//     email_type: "platform_assigned" | "corporate";
//     display_name?: string;
//   }) =>
//     http.post<SenderIdentity>("/api/v1/users/me/sender-identities", body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(
//       `/api/v1/users/me/sender-identities/${id}`,
//     ),
//   setDefault: (id: string) =>
//     http.post<{ message: string }>(
//       `/api/v1/users/me/sender-identities/${id}/set-default`,
//     ),
//   myQuota: () => http.get<EmailQuota>("/api/v1/users/me/email-quota"),
//   // NOTE (Task 2-b finding 9): teamQuotas removed — was unused. Re-add from
//   // git history (or AUDIT-FE-1 §C.7) when a Team Quotas card is built.
// };

// /**
//  * managerDashboardApi — per-user + manager dashboards (`/api/v1/dashboard*`).
//  */
// export const managerDashboardApi = {
//   mine: () =>
//     http.get<UserDashboard>("/api/v1/dashboard", { user_id: "me" }),
//   // NOTE (Task 2-b finding 9): user(userId) removed — was unused. Re-add when
//   // a per-rep drill-down is built into ManagerDashboardPage.
//   manager: () => http.get<ManagerDashboard>("/api/v1/dashboard/manager"),
// };

// /**
//  * usageApi — usage + cost rollups (`/api/v1/usage/*` + platform equivalents).
//  */
// export const usageApi = {
//   me: (period: string) =>
//     http.get<UsageSummary>("/api/v1/usage/me", { period }),
//   // NOTE (Task 2-b finding 9): user(userId, period) + tenant(period) removed —
//   // were unused. Re-add when per-user / per-tenant usage drill-downs are built.
//   manager: (period: string) =>
//     http.get<UsageManagerRollup>("/api/v1/usage/manager", { period }),
//   platform: (period: string) =>
//     http.get<UsagePlatformRollup>(
//       "/api/v1/usage/platform",
//       { period },
//     ),
//   costTable: () =>
//     http.get<CostTableEntry[]>("/api/v1/usage/cost-table"),
//   updateCostTable: (entries: CostTableInput[]) =>
//     http.put<CostTableEntry[]>("/api/v1/usage/cost-table", entries),
// };

// /**
//  * gdprApi — GDPR DSR + consent + retention endpoints.
//  *
//  * Public DSR (no auth): `submitDsr` + `dsrStatus`.
//  * Authenticated tenant-admin DSR workflow: `list`, `process`, `complete`,
//  * `reject`, `export`.
//  * Consent: `getConsent`, `grant`, `withdraw`.
//  * Retention: `status`, `enforce`.
//  */
// export const gdprApi = {
//   // Public DSR
//   submitDsr: (body: DsrSubmission) =>
//     http.post<DsrSubmissionResponse>("/api/v1/gdpr/dsr", body),
//   dsrStatus: (dsrId: string) =>
//     http.get<DsrStatusResponse>(`/api/v1/gdpr/dsr/${dsrId}/status`),
//   // Tenant-admin DSR workflow
//   list: (status?: string) =>
//     http.get<DsrRow[]>("/api/v1/gdpr/dsrs", status ? { status } : undefined),
//   process: (id: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/process`),
//   complete: (id: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/complete`),
//   reject: (id: string, reason?: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/reject`, { reason }),
//   // NOTE (Task 2-b finding 9): exportUrl + grant removed — were unused.
//   // GdprCenterPage builds export URLs inline; the consent grant endpoint
//   // (/api/v1/gdpr/consent/grant) is still available on the backend. Re-add
//   // these helpers when the corresponding UI is built.
//   // Consent
//   getConsent: (email: string) =>
//     http.get<ConsentStatus>(`/api/v1/gdpr/consent/${encodeURIComponent(email)}`),
//   withdraw: (email: string) =>
//     http.post("/api/v1/gdpr/consent/withdraw", { email }),
//   // Retention
//   retentionStatus: () =>
//     http.get<RetentionStatus>("/api/v1/gdpr/retention-status"),
//   enforceRetention: () =>
//     http.post<RetentionStatus>("/api/v1/gdpr/retention/enforce"),
// };

// /* ─────────────────────────────────────────────────────────────────────────── */
// /* FIX-FE-1: New feature-page helpers (MailBridge, Flows, RateLimits,         */
// /* Scheduler, Meetings, DomainEnrichment, CallLogs, PlatformTenantConfig).    */
// /* Each helper targets the exact endpoints exposed by the backend router.     */
// /* ─────────────────────────────────────────────────────────────────────────── */

// /** mailbridgeApi — per-tenant MailBridge config CRUD (`/api/v1/mailbridge/config`). */
// export const mailbridgeApi = {
//   list: () => http.get<MailBridgeConfig[]>("/api/v1/mailbridge/config"),
//   create: (body: MailBridgeConfigInput) =>
//     http.post<MailBridgeConfig>("/api/v1/mailbridge/config", body),
//   get: (id: string) =>
//     http.get<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`),
//   update: (id: string, body: Partial<MailBridgeConfigInput>) =>
//     http.put<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/mailbridge/config/${id}`),
//   /** Send a test email through this config (best-effort). */
//   sendTest: (body: { to: string; subject: string; body: string; configId?: string }) =>
//     http.post<{ messageId: string; status: string; accepted: boolean }>(
//       "/api/v1/mailbridge/send",
//       body,
//     ),
// };

// /** flowsApi — ProspectingFlow + FlowRun + FlowAbTest + FlowWebhook + AutopilotQueue. */
// export const flowsApi = {
//   // ProspectingFlow definitions
//   listFlows: (params?: { isActive?: boolean; isTemplate?: boolean; limit?: number; offset?: number }) =>
//     http.get<{ items: ProspectingFlow[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows",
//       params,
//     ),
//   createFlow: (body: ProspectingFlowInput) =>
//     http.post<ProspectingFlow>("/api/v1/flows", body),
//   getFlow: (id: string) => http.get<ProspectingFlow>(`/api/v1/flows/${id}`),
//   updateFlow: (id: string, body: Partial<ProspectingFlowInput>) =>
//     http.put<ProspectingFlow>(`/api/v1/flows/${id}`, body),
//   removeFlow: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/${id}`),
//   // FlowRuns (list + detail; runs are created via /autopilot)
//   listRuns: (params?: { flowId?: string; icpProfileId?: string; status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: FlowRun[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/runs",
//       params,
//     ),
//   getRun: (runId: string) => http.get<FlowRun>(`/api/v1/flows/runs/${runId}`),
//   // Flow A/B tests
//   listAbTests: (params?: { icpProfileId?: string; status?: string }) =>
//     http.get<{ items: FlowAbTest[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/ab-tests",
//       params,
//     ),
//   createAbTest: (body: FlowAbTestInput) =>
//     http.post<FlowAbTest>("/api/v1/flows/ab-tests", body),
//   getAbTest: (id: string) => http.get<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`),
//   updateAbTest: (id: string, body: Partial<FlowAbTestInput> & { status?: string; significance?: string; summary?: string }) =>
//     http.put<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`, body),
//   removeAbTest: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/ab-tests/${id}`),
//   // Flow webhooks
//   listWebhooks: (params?: { flowId?: string; isActive?: boolean }) =>
//     http.get<{ items: FlowWebhook[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/webhooks",
//       params,
//     ),
//   createWebhook: (body: FlowWebhookInput) =>
//     http.post<FlowWebhook>("/api/v1/flows/webhooks", body),
//   getWebhook: (id: string) => http.get<FlowWebhook>(`/api/v1/flows/webhooks/${id}`),
//   updateWebhook: (id: string, body: Partial<FlowWebhookInput>) =>
//     http.put<FlowWebhook>(`/api/v1/flows/webhooks/${id}`, body),
//   removeWebhook: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/webhooks/${id}`),
//   // AutopilotQueue (read-only)
//   listQueue: (params?: { status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/queue",
//       params,
//     ),
// };

// /** rateLimitsApi — RateLimit + RateLimitLog. */
// export const rateLimitsApi = {
//   list: (params?: { platform?: string; isActive?: boolean; limit?: number; offset?: number }) =>
//     http.get<{ items: RateLimit[]; total: number; limit: number; offset: number }>(
//       "/api/v1/rate-limits",
//       params,
//     ),
//   create: (body: RateLimitInput) =>
//     http.post<RateLimit>("/api/v1/rate-limits", body),
//   get: (id: string) => http.get<RateLimit>(`/api/v1/rate-limits/${id}`),
//   update: (id: string, body: Partial<RateLimitInput> & { count?: number }) =>
//     http.put<RateLimit>(`/api/v1/rate-limits/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/rate-limits/${id}`),
//   resetCounter: (id: string) =>
//     http.post<RateLimit>(`/api/v1/rate-limits/${id}/reset`),
//   listLogs: (params?: { key?: string; platform?: string; flowRunId?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: RateLimitLog[]; total: number; limit: number; offset: number }>(
//       "/api/v1/rate-limits/logs",
//       params,
//     ),
// };

// /** schedulerApi — scheduler status + manual tick + trigger + runs. */
// export const schedulerApi = {
//   status: () => http.get<SchedulerStatus>("/api/v1/scheduler/status"),
//   tick: (body?: { tenantScoped?: boolean; maxSend?: number }) =>
//     http.post<ManualTickResponse>("/api/v1/scheduler/tick", body ?? {}),
//   trigger: () =>
//     http.post<{ triggered: boolean; message: string; runId: string | null }>(
//       "/api/v1/scheduler/trigger",
//     ),
//   runs: (params?: { limit?: number; offset?: number }) =>
//     http.get<{ items: SchedulerRun[]; total: number }>(
//       "/api/v1/scheduler/runs",
//       params,
//     ),
// };

// /** meetingsApi — Meeting CRUD. The backend Meeting model lives at
//  * `/api/v1/meetings`; if the route is missing (pre-FIX-BE follow-up), the
//  * page degrades to an error state. The MeetingPrep generate endpoint is
//  * backed by the existing `/api/v1/meeting-prep` router. */
// export const meetingsApi = {
//   list: () => http.get<Meeting[]>("/api/v1/meetings"),
//   create: (body: MeetingInput) => http.post<Meeting>("/api/v1/meetings", body),
//   get: (id: string) => http.get<Meeting>(`/api/v1/meetings/${id}`),
//   update: (id: string, body: Partial<MeetingInput>) =>
//     http.patch<Meeting>(`/api/v1/meetings/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/meetings/${id}`),
//   // Meeting-prep integration
//   generatePrep: (prospectId: string, callType: string = "discovery") =>
//     http.post<{ id: string; brief: string }>("/api/v1/meeting-prep/generate", {
//       prospectId,
//       callType,
//     }),
//   getPrep: (briefId: string) =>
//     http.get<MeetingPrep>(`/api/v1/meeting-prep/${briefId}`),
//   listPrepForProspect: (prospectId: string) =>
//     http.get<MeetingPrep[]>("/api/v1/meeting-prep", { prospect_id: prospectId }),
// };

// /** domainEnrichApi — fetch/cache enrichment for a domain. */
// export const domainEnrichApi = {
//   enrich: (domain: string, forceRefresh = false) =>
//     http.post<DomainEnrichment>("/api/v1/domain-enrich", { domain, forceRefresh }),
//   enrichBatch: (domains: string[]) =>
//     http.post<{ enriched: DomainEnrichment[]; failed: string[] }>(
//       "/api/v1/domain-enrich/batch",
//       { domains },
//     ),
//   get: (domain: string) =>
//     http.get<DomainEnrichment>(`/api/v1/domain-enrich/${encodeURIComponent(domain)}`),
// };

// /** callLogsApi — CallLog CRUD. */
// export const callLogsApi = {
//   list: (params?: { prospectId?: string; outcome?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: CallLog[]; total: number; limit: number; offset: number }>(
//       "/api/v1/call-logs",
//       params,
//     ),
//   create: (body: CallLogInput) =>
//     http.post<CallLog>("/api/v1/call-logs", body),
//   get: (id: string) => http.get<CallLog>(`/api/v1/call-logs/${id}`),
//   update: (id: string, body: Partial<CallLogInput>) =>
//     http.patch<CallLog>(`/api/v1/call-logs/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/call-logs/${id}`),
// };

// /** platformConfigApi — SUPER_ADMIN tenant_config (per-tenant). */
// export const platformConfigApi = {
//   get: (tenantId: number | string) =>
//     http.get<PlatformTenantConfig>(
//       `/api/platform/admin/tenants/${tenantId}/config`,
//     ),
//   setIntegrationMode: (tenantId: number | string, integration_mode: IntegrationMode) =>
//     http.patch<{ tenant_id: number; integration_mode: IntegrationMode; updated_at: string }>(
//       `/api/platform/admin/tenants/${tenantId}/integration-mode`,
//       { integration_mode },
//     ),
// };

// /** pipelineApi — 5-stage GTM workflow orchestrator. */
// export const pipelineApi = {
//   runStage: (body: PipelineRunStageInput) =>
//     http.post<PipelineStageResult>("/api/v1/pipeline/run-stage", body),
//   status: () => http.get<PipelineStatus>("/api/v1/pipeline/status"),
// };

// /** flowTemplatesApi — pre-built flow template definitions + clone. */
// export const flowTemplatesApi = {
//   list: () => http.get<FlowTemplate[]>("/api/v1/flow-templates"),
//   clone: (body: FlowTemplateCloneInput) =>
//     http.post<{ flow_id: string; name: string }>("/api/v1/flow-templates/clone", body),
// };

// /** publicUnsubscribeApi — one-click unsubscribe (no auth, FR-E14-018). */
// export async function publicUnsubscribeApi(
//   token: string,
//   tenant_slug: string,
// ): Promise<{ unsubscribed: boolean; message: string }> {
//   return http.post<{ unsubscribed: boolean; message: string }>(
//     "/api/v1/public/unsubscribe",
//     { token, tenant_slug },
//   );
// }

// /** flowAnalyticsApi — per-flow analytics dashboard. */
// export const flowAnalyticsApi = {
//   list: () =>
//     http.get<FlowAnalyticsSummary[]>("/api/v1/flow-analytics"),
//   get: (flowId: string) =>
//     http.get<FlowAnalyticsSummary>(`/api/v1/flow-analytics/${flowId}`),
// };

// /** autopilotQueueApi — autopilot queue management with enqueue/trigger/cancel. */
// export const autopilotQueueApi = {
//   list: (params?: { status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
//       "/api/v1/autopilot-queue",
//       params,
//     ),
//   stats: () =>
//     http.get<AutopilotQueueStats>("/api/v1/autopilot-queue/stats"),
//   enqueue: (body: AutopilotQueueEnqueueBody) =>
//     http.post<AutopilotQueueItem>("/api/v1/autopilot-queue/enqueue", body),
//   triggerScheduler: () =>
//     http.post<{ triggered: boolean; message: string }>("/api/v1/autopilot-queue/trigger-scheduler"),
//   setAutonomousMode: (enabled: boolean) =>
//     http.put<{ autonomousMode: boolean; message: string }>("/api/v1/autopilot-queue/autonomous-mode", { enabled }),
//   cancel: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/autopilot-queue/${id}`),
// };


/**
 * apiClient.ts — central axios instance with Bearer + tenant interceptors.
 *
 * The access token is read from a module-level holder kept in sync by
 * `AuthContext` (Section 7.6 of the migration doc). A `VITE_DEV_TENANT_SLUG`
 * override lets local dev target a specific tenant schema without Keycloak
 * claims.
 */
// /**
//  * apiClient.ts — central axios instance with Bearer + tenant interceptors.
//  *
//  * The access token is read from a module-level holder kept in sync by
//  * `AuthContext` (Section 7.6 of the migration doc). A `VITE_DEV_TENANT_SLUG`
//  * override lets local dev target a specific tenant schema without Keycloak
//  * claims.
//  */
// import axios, { AxiosError, type AxiosInstance } from "axios";
// import type {
//   LandingContent,
//   ContactInfo,
//   ContactMessage,
//   Plan,
//   TenantSignupRequest,
//   TenantSignupStatus,
//   TenantSignupRow,
//   TenantRow,
//   PlatformMetrics,
//   AuditLog,
//   TenantIntegration,
//   IntegrationMode,
//   IntegrationCatalogEntry,
//   IntegrationTestResult,
//   GlobalLlmConfig,
//   GlobalLlmConfigInput,
//   GlobalLlmTestResult,
//   SenderIdentity,
//   EmailQuota,
//   UserDashboard,
//   ManagerDashboard,
//   UsageSummary,
//   UsageManagerRollup,
//   UsagePlatformRollup,
//   CostTableEntry,
//   CostTableInput,
//   DsrSubmission,
//   DsrSubmissionResponse,
//   DsrStatusResponse,
//   DsrRow,
//   ConsentStatus,
//   RetentionStatus,
//   MailBridgeConfig,
//   MailBridgeConfigInput,
//   ProspectingFlow,
//   ProspectingFlowInput,
//   FlowRun,
//   FlowAbTest,
//   FlowAbTestInput,
//   FlowWebhook,
//   FlowWebhookInput,
//   AutopilotQueueItem,
//   RateLimit,
//   RateLimitInput,
//   RateLimitLog,
//   SchedulerStatus,
//   ManualTickResponse,
//   SchedulerRun,
//   Meeting,
//   MeetingInput,
//   MeetingPrep,
//   DomainEnrichment,
//   CallLog,
//   CallLogInput,
//   PlatformTenantConfig,
//   FlowAnalyticsSummary,
//   AutopilotQueueStats,
//   AutopilotQueueEnqueueBody,
//   PipelineStageResult,
//   PipelineStatus,
//   PipelineRunStageInput,
//   FlowTemplate,
//   FlowTemplateCloneInput,
// } from "@/types/common";

// let currentAccessToken: string | null = null;

// export function setAccessToken(token: string | null): void {
//   currentAccessToken = token;
// }

// export function getAccessToken(): string | null {
//   return currentAccessToken;
// }

// const DEV_TENANT_SLUG = import.meta.env.VITE_DEV_TENANT_SLUG ?? "";

// export const apiClient: AxiosInstance = axios.create({
//   baseURL: "/",
//   timeout: 15_000,
//   headers: { "Content-Type": "application/json" },
// });

// apiClient.interceptors.request.use((config) => {
//   const token = getAccessToken();
//   if (token) {
//     config.headers.Authorization = `Bearer ${token}`;
//   }
//   if (DEV_TENANT_SLUG) {
//     config.headers["X-Tenant-Slug"] = DEV_TENANT_SLUG;
//   }
//   return config;
// });

// apiClient.interceptors.response.use(
//   (resp) => resp,
//   (error: AxiosError) => {
//     // Normalise 401 → trigger re-login via AuthContext (handled by consumers).
//     if (error.response?.status === 401) {
//       window.dispatchEvent(new CustomEvent("outrena:unauthorized"));
//     }
//     return Promise.reject(error);
//   },
// );

// /** Convenience typed request helpers used by feature service modules. */
// export const http = {
//   get: <T>(url: string, params?: Record<string, unknown>) =>
//     apiClient.get<T>(url, { params }).then((r) => r.data),
//   post: <T>(url: string, body?: unknown) =>
//     apiClient.post<T>(url, body).then((r) => r.data),
//   put: <T>(url: string, body?: unknown) =>
//     apiClient.put<T>(url, body).then((r) => r.data),
//   patch: <T>(url: string, body?: unknown) =>
//     apiClient.patch<T>(url, body).then((r) => r.data),
//   delete: <T>(url: string) => apiClient.delete<T>(url).then((r) => r.data),
// };

// /**
//  * publicApi — calls to `/api/v1/public/*` and `/api/v1/tenant-signup*`.
//  *
//  * These endpoints are intentionally NOT authenticated: marketing pages, plan
//  * list, contact form, tenant self-signup wizard. They still go through the
//  * shared `apiClient` instance (so dev-tenant header is preserved), but the
//  * backend does not require a Bearer token.
//  */
// export const publicApi = {
//   landing: () => http.get<LandingContent>("/api/v1/public/landing"),
//   plans: () => http.get<Plan[]>("/api/v1/public/plans"),
//   contactInfo: () => http.get<ContactInfo>("/api/v1/public/contact-info"),
//   contact: (body: ContactMessage) =>
//     apiClient.post("/api/v1/public/contact", body).then((r) => r.status),
//   checkSubdomain: (subdomain: string) =>
//     apiClient
//       .get<{ available: boolean }>("/api/v1/public/subdomain-check", {
//         params: { subdomain },
//       })
//       .then((r) => r.data)
//       .catch(() => ({ available: false })),
//   submitSignup: (body: TenantSignupRequest) =>
//     http.post<{ signup_id: string; status: string }>(
//       "/api/v1/tenant-signup",
//       body,
//     ),
//   signupStatus: (signupId: string) =>
//     http.get<TenantSignupStatus>(
//       `/api/v1/tenant-signup/${signupId}/status`,
//     ),
// };

// /**
//  * platformApi — SUPER_ADMIN calls to `/api/platform/admin/*`.
//  *
//  * Uses the authenticated `apiClient` (Bearer + tenant header) but targets the
//  * cross-tenant platform admin router. All calls are role-gated server-side to
//  * SUPER_ADMIN.
//  */
// export const platformApi = {
//   signups: (status?: string) =>
//     http.get<TenantSignupRow[]>("/api/platform/admin/signups", {
//       status: status ?? "pending",
//     }),
//   approveSignup: (id: string) =>
//     http.post<{ tenant_slug: string; provisioned: boolean }>(
//       `/api/platform/admin/signups/${id}/approve`,
//     ),
//   rejectSignup: (id: string, reason: string) =>
//     http.post(`/api/platform/admin/signups/${id}/reject`, { reason }),
//   tenants: () => http.get<TenantRow[]>("/api/platform/admin/tenants"),
//   suspendTenant: (id: string) =>
//     http.post(`/api/platform/admin/tenants/${id}/suspend`),
//   reactivateTenant: (id: string) =>
//     http.post(`/api/platform/admin/tenants/${id}/reactivate`),
//   metrics: () => http.get<PlatformMetrics>("/api/platform/admin/metrics"),
//   auditLogs: (params?: { limit?: number; tenant_slug?: string; action?: string }) =>
//     http.get<AuditLog[]>("/api/platform/admin/audit-logs", params),
//   // ISSUE-3 FIX: Create tenant endpoint (provisioning — base platform router, not /admin)
//   createTenant: (body: {
//     slug: string;
//     name: string;
//     admin_email: string;
//     admin_first_name: string;
//     admin_last_name: string;
//     temporary_password?: string;
//     send_invitation: boolean;
//   }) =>
//     http.post<{ slug: string; status: string; url: string }>(
//       "/api/platform/tenants",
//       body,
//     ),
// };

// /* ─────────────────────────────────────────────────────────────────────────── */
// /* SAAS2-FE: Workstream helpers (integrations, LLM, users, usage, GDPR).      */
// /* Each helper targets the exact endpoints specified in the SAAS2-FE task.    */
// /* ─────────────────────────────────────────────────────────────────────────── */

// /**
//  * integrationConfigApi — dual-path integration config.
//  *
//  * Tenant side (`/api/v1/integrations`): list, create, update, test.
//  * Platform side (`/api/platform/admin/...`): per-tenant mode + catalog.
//  */
// export const integrationConfigApi = {
//   tenantList: () => http.get<TenantIntegration[]>("/api/v1/integrations"),
//   tenantCreate: (body: {
//     type: string;
//     name: string;
//     key_source: "tenant" | "platform";
//     api_key?: string;
//   }) => http.post<TenantIntegration>("/api/v1/integrations", {
//     platform: body.type,
//     name: body.name,
//     key_source: body.key_source,
//     apiKey: body.key_source === "tenant" ? body.api_key : undefined,
//   }),
//   tenantUpdate: (
//     id: string,
//     body: Partial<{
//       name: string;
//       key_source: "tenant" | "platform";
//       api_key?: string;
//       is_active: boolean;
//     }>,
//   ) => http.put<TenantIntegration>(`/api/v1/integrations/${id}`, {
//     name: body.name,
//     key_source: body.key_source,
//     apiKey: body.api_key,
//     isActive: body.is_active,
//   }),
//   tenantTest: (id: string) =>
//     http.get<IntegrationTestResult>(
//       `/api/v1/integrations/${id}/credentials-test`,
//     ),
//   // NOTE (Task 2-b finding 9): platformGetConfig removed — duplicate of
//   // platformConfigApi.get() which is the one PlatformSettingsPage actually uses.
//   platformSetMode: (tenantId: string, integration_mode: IntegrationMode) =>
//     http.patch<{ tenant_id: string; integration_mode: IntegrationMode }>(
//       `/api/platform/admin/tenants/${tenantId}/integration-mode`,
//       { integration_mode },
//     ),
//   catalog: () =>
//     http.get<IntegrationCatalogEntry[]>(
//       "/api/platform/admin/integration-catalog",
//     ),
// };

// /**
//  * globalLlmApi — SUPER_ADMIN global LLM config (`/api/platform/admin/llm-configs`).
//  */
// export const globalLlmApi = {
//   list: () =>
//     http.get<GlobalLlmConfig[]>("/api/platform/admin/llm-configs"),
//   create: (body: GlobalLlmConfigInput) =>
//     http.post<GlobalLlmConfig>("/api/platform/admin/llm-configs", body),
//   update: (id: string, body: GlobalLlmConfigInput) =>
//     http.put<GlobalLlmConfig>(`/api/platform/admin/llm-configs/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(
//       `/api/platform/admin/llm-configs/${id}`,
//     ),
//   setDefault: (id: string) =>
//     http.post<{ message: string }>(
//       `/api/platform/admin/llm-configs/${id}/set-default`,
//     ),
//   test: (id: string) =>
//     http.post<GlobalLlmTestResult>(
//       `/api/platform/admin/llm-configs/${id}/test`,
//     ),
// };

// /**
//  * senderIdentityApi — per-user sender identities (`/api/v1/users/me/...`).
//  */
// export const senderIdentityApi = {
//   list: () =>
//     http.get<SenderIdentity[]>("/api/v1/users/me/sender-identities"),
//   create: (body: {
//     email: string;
//     email_type: "platform_assigned" | "corporate";
//     display_name?: string;
//   }) =>
//     http.post<SenderIdentity>("/api/v1/users/me/sender-identities", body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(
//       `/api/v1/users/me/sender-identities/${id}`,
//     ),
//   setDefault: (id: string) =>
//     http.post<{ message: string }>(
//       `/api/v1/users/me/sender-identities/${id}/set-default`,
//     ),
//   myQuota: () => http.get<EmailQuota>("/api/v1/users/me/email-quota"),
//   // NOTE (Task 2-b finding 9): teamQuotas removed — was unused. Re-add from
//   // git history (or AUDIT-FE-1 §C.7) when a Team Quotas card is built.
// };

// /**
//  * managerDashboardApi — per-user + manager dashboards (`/api/v1/dashboard*`).
//  */
// export const managerDashboardApi = {
//   mine: () =>
//     http.get<UserDashboard>("/api/v1/dashboard", { user_id: "me" }),
//   // NOTE (Task 2-b finding 9): user(userId) removed — was unused. Re-add when
//   // a per-rep drill-down is built into ManagerDashboardPage.
//   manager: () => http.get<ManagerDashboard>("/api/v1/dashboard/manager"),
// };

// /**
//  * usageApi — usage + cost rollups (`/api/v1/usage/*` + platform equivalents).
//  */
// export const usageApi = {
//   me: (period: string) =>
//     http.get<UsageSummary>("/api/v1/usage/me", { period }),
//   // NOTE (Task 2-b finding 9): user(userId, period) + tenant(period) removed —
//   // were unused. Re-add when per-user / per-tenant usage drill-downs are built.
//   manager: (period: string) =>
//     http.get<UsageManagerRollup>("/api/v1/usage/manager", { period }),
//   platform: (period: string) =>
//     http.get<UsagePlatformRollup>(
//       "/api/v1/usage/platform",
//       { period },
//     ),
//   costTable: () =>
//     http.get<CostTableEntry[]>("/api/v1/usage/cost-table"),
//   updateCostTable: (entries: CostTableInput[]) =>
//     http.put<CostTableEntry[]>("/api/v1/usage/cost-table", entries),
// };

// /**
//  * gdprApi — GDPR DSR + consent + retention endpoints.
//  *
//  * Public DSR (no auth): `submitDsr` + `dsrStatus`.
//  * Authenticated tenant-admin DSR workflow: `list`, `process`, `complete`,
//  * `reject`, `export`.
//  * Consent: `getConsent`, `grant`, `withdraw`.
//  * Retention: `status`, `enforce`.
//  */
// export const gdprApi = {
//   // Public DSR
//   submitDsr: (body: DsrSubmission) =>
//     http.post<DsrSubmissionResponse>("/api/v1/gdpr/dsr", body),
//   dsrStatus: (dsrId: string) =>
//     http.get<DsrStatusResponse>(`/api/v1/gdpr/dsr/${dsrId}/status`),
//   // Tenant-admin DSR workflow
//   list: (status?: string) =>
//     http.get<DsrRow[]>("/api/v1/gdpr/dsrs", status ? { status } : undefined),
//   process: (id: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/process`),
//   complete: (id: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/complete`),
//   reject: (id: string, reason?: string) =>
//     http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/reject`, { reason }),
//   // NOTE (Task 2-b finding 9): exportUrl + grant removed — were unused.
//   // GdprCenterPage builds export URLs inline; the consent grant endpoint
//   // (/api/v1/gdpr/consent/grant) is still available on the backend. Re-add
//   // these helpers when the corresponding UI is built.
//   // Consent
//   getConsent: (email: string) =>
//     http.get<ConsentStatus>(`/api/v1/gdpr/consent/${encodeURIComponent(email)}`),
//   withdraw: (email: string) =>
//     http.post("/api/v1/gdpr/consent/withdraw", { email }),
//   // Retention
//   retentionStatus: () =>
//     http.get<RetentionStatus>("/api/v1/gdpr/retention-status"),
//   enforceRetention: () =>
//     http.post<RetentionStatus>("/api/v1/gdpr/retention/enforce"),
// };

// /* ─────────────────────────────────────────────────────────────────────────── */
// /* FIX-FE-1: New feature-page helpers (MailBridge, Flows, RateLimits,         */
// /* Scheduler, Meetings, DomainEnrichment, CallLogs, PlatformTenantConfig).    */
// /* Each helper targets the exact endpoints exposed by the backend router.     */
// /* ─────────────────────────────────────────────────────────────────────────── */

// /** mailbridgeApi — per-tenant MailBridge config CRUD (`/api/v1/mailbridge/config`). */
// export const mailbridgeApi = {
//   list: () => http.get<MailBridgeConfig[]>("/api/v1/mailbridge/config"),
//   create: (body: MailBridgeConfigInput) =>
//     http.post<MailBridgeConfig>("/api/v1/mailbridge/config", body),
//   get: (id: string) =>
//     http.get<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`),
//   update: (id: string, body: Partial<MailBridgeConfigInput>) =>
//     http.put<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/mailbridge/config/${id}`),
//   /** Send a test email through this config (best-effort). */
//   sendTest: (body: { to: string; subject: string; body: string; configId?: string }) =>
//     http.post<{ messageId: string; status: string; accepted: boolean }>(
//       "/api/v1/mailbridge/send",
//       body,
//     ),
// };

// /** flowsApi — ProspectingFlow + FlowRun + FlowAbTest + FlowWebhook + AutopilotQueue. */
// export const flowsApi = {
//   // ProspectingFlow definitions
//   listFlows: (params?: { isActive?: boolean; isTemplate?: boolean; limit?: number; offset?: number }) =>
//     http.get<{ items: ProspectingFlow[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows",
//       params,
//     ),
//   createFlow: (body: ProspectingFlowInput) =>
//     http.post<ProspectingFlow>("/api/v1/flows", body),
//   getFlow: (id: string) => http.get<ProspectingFlow>(`/api/v1/flows/${id}`),
//   updateFlow: (id: string, body: Partial<ProspectingFlowInput>) =>
//     http.put<ProspectingFlow>(`/api/v1/flows/${id}`, body),
//   removeFlow: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/${id}`),
//   // FlowRuns (list + detail; runs are created via /autopilot)
//   listRuns: (params?: { flowId?: string; icpProfileId?: string; status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: FlowRun[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/runs",
//       params,
//     ),
//   getRun: (runId: string) => http.get<FlowRun>(`/api/v1/flows/runs/${runId}`),
//   // Flow A/B tests
//   listAbTests: (params?: { icpProfileId?: string; status?: string }) =>
//     http.get<{ items: FlowAbTest[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/ab-tests",
//       params,
//     ),
//   createAbTest: (body: FlowAbTestInput) =>
//     http.post<FlowAbTest>("/api/v1/flows/ab-tests", body),
//   getAbTest: (id: string) => http.get<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`),
//   updateAbTest: (id: string, body: Partial<FlowAbTestInput> & { status?: string; significance?: string; summary?: string }) =>
//     http.put<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`, body),
//   removeAbTest: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/ab-tests/${id}`),
//   // Flow webhooks
//   listWebhooks: (params?: { flowId?: string; isActive?: boolean }) =>
//     http.get<{ items: FlowWebhook[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/webhooks",
//       params,
//     ),
//   createWebhook: (body: FlowWebhookInput) =>
//     http.post<FlowWebhook>("/api/v1/flows/webhooks", body),
//   getWebhook: (id: string) => http.get<FlowWebhook>(`/api/v1/flows/webhooks/${id}`),
//   updateWebhook: (id: string, body: Partial<FlowWebhookInput>) =>
//     http.put<FlowWebhook>(`/api/v1/flows/webhooks/${id}`, body),
//   removeWebhook: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/flows/webhooks/${id}`),
//   // AutopilotQueue (read-only)
//   listQueue: (params?: { status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
//       "/api/v1/flows/queue",
//       params,
//     ),
// };

// /** rateLimitsApi — RateLimit + RateLimitLog. */
// export const rateLimitsApi = {
//   list: (params?: { platform?: string; isActive?: boolean; limit?: number; offset?: number }) =>
//     http.get<{ items: RateLimit[]; total: number; limit: number; offset: number }>(
//       "/api/v1/rate-limits",
//       params,
//     ),
//   create: (body: RateLimitInput) =>
//     http.post<RateLimit>("/api/v1/rate-limits", body),
//   get: (id: string) => http.get<RateLimit>(`/api/v1/rate-limits/${id}`),
//   update: (id: string, body: Partial<RateLimitInput> & { count?: number }) =>
//     http.put<RateLimit>(`/api/v1/rate-limits/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/rate-limits/${id}`),
//   resetCounter: (id: string) =>
//     http.post<RateLimit>(`/api/v1/rate-limits/${id}/reset`),
//   listLogs: (params?: { key?: string; platform?: string; flowRunId?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: RateLimitLog[]; total: number; limit: number; offset: number }>(
//       "/api/v1/rate-limits/logs",
//       params,
//     ),
// };

// /** schedulerApi — scheduler status + manual tick + trigger + runs. */
// export const schedulerApi = {
//   status: () => http.get<SchedulerStatus>("/api/v1/scheduler/status"),
//   tick: (body?: { tenantScoped?: boolean; maxSend?: number }) =>
//     http.post<ManualTickResponse>("/api/v1/scheduler/tick", body ?? {}),
//   trigger: () =>
//     http.post<{ triggered: boolean; message: string; runId: string | null }>(
//       "/api/v1/scheduler/trigger",
//     ),
//   runs: (params?: { limit?: number; offset?: number }) =>
//     http.get<{ items: SchedulerRun[]; total: number }>(
//       "/api/v1/scheduler/runs",
//       params,
//     ),
// };

// /** meetingsApi — Meeting CRUD. The backend Meeting model lives at
//  * `/api/v1/meetings`; if the route is missing (pre-FIX-BE follow-up), the
//  * page degrades to an error state. The MeetingPrep generate endpoint is
//  * backed by the existing `/api/v1/meeting-prep` router. */
// export const meetingsApi = {
//   list: () => http.get<Meeting[]>("/api/v1/meetings"),
//   create: (body: MeetingInput) => http.post<Meeting>("/api/v1/meetings", body),
//   get: (id: string) => http.get<Meeting>(`/api/v1/meetings/${id}`),
//   update: (id: string, body: Partial<MeetingInput>) =>
//     http.patch<Meeting>(`/api/v1/meetings/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/meetings/${id}`),
//   // Meeting-prep integration
//   generatePrep: (prospectId: string, callType: string = "discovery") =>
//     http.post<{ id: string; brief: string }>("/api/v1/meeting-prep/generate", {
//       prospectId,
//       callType,
//     }),
//   getPrep: (briefId: string) =>
//     http.get<MeetingPrep>(`/api/v1/meeting-prep/${briefId}`),
//   listPrepForProspect: (prospectId: string) =>
//     http.get<MeetingPrep[]>("/api/v1/meeting-prep", { prospect_id: prospectId }),
// };

// /** domainEnrichApi — fetch/cache enrichment for a domain. */
// export const domainEnrichApi = {
//   enrich: (domain: string, forceRefresh = false) =>
//     http.post<DomainEnrichment>("/api/v1/domain-enrich", { domain, forceRefresh }),
//   enrichBatch: (domains: string[]) =>
//     http.post<{ enriched: DomainEnrichment[]; failed: string[] }>(
//       "/api/v1/domain-enrich/batch",
//       { domains },
//     ),
//   get: (domain: string) =>
//     http.get<DomainEnrichment>(`/api/v1/domain-enrich/${encodeURIComponent(domain)}`),
// };

// /** callLogsApi — CallLog CRUD. */
// export const callLogsApi = {
//   list: (params?: { prospectId?: string; outcome?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: CallLog[]; total: number; limit: number; offset: number }>(
//       "/api/v1/call-logs",
//       params,
//     ),
//   create: (body: CallLogInput) =>
//     http.post<CallLog>("/api/v1/call-logs", body),
//   get: (id: string) => http.get<CallLog>(`/api/v1/call-logs/${id}`),
//   update: (id: string, body: Partial<CallLogInput>) =>
//     http.patch<CallLog>(`/api/v1/call-logs/${id}`, body),
//   remove: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/call-logs/${id}`),
// };

// /** platformConfigApi — SUPER_ADMIN tenant_config (per-tenant). */
// export const platformConfigApi = {
//   get: (tenantId: number | string) =>
//     http.get<PlatformTenantConfig>(
//       `/api/platform/admin/tenants/${tenantId}/config`,
//     ),
//   setIntegrationMode: (tenantId: number | string, integration_mode: IntegrationMode) =>
//     http.patch<{ tenant_id: number; integration_mode: IntegrationMode; updated_at: string }>(
//       `/api/platform/admin/tenants/${tenantId}/integration-mode`,
//       { integration_mode },
//     ),
// };

// /** pipelineApi — 5-stage GTM workflow orchestrator. */
// export const pipelineApi = {
//   runStage: (body: PipelineRunStageInput) =>
//     http.post<PipelineStageResult>("/api/v1/pipeline/run-stage", body),
//   status: () => http.get<PipelineStatus>("/api/v1/pipeline/status"),
// };

// /** flowTemplatesApi — pre-built flow template definitions + clone. */
// export const flowTemplatesApi = {
//   list: () => http.get<FlowTemplate[]>("/api/v1/flow-templates"),
//   clone: (body: FlowTemplateCloneInput) =>
//     http.post<{ flow_id: string; name: string }>("/api/v1/flow-templates/clone", body),
// };

// /** publicUnsubscribeApi — one-click unsubscribe (no auth, FR-E14-018). */
// export async function publicUnsubscribeApi(
//   token: string,
//   tenant_slug: string,
// ): Promise<{ unsubscribed: boolean; message: string }> {
//   return http.post<{ unsubscribed: boolean; message: string }>(
//     "/api/v1/public/unsubscribe",
//     { token, tenant_slug },
//   );
// }

// /** flowAnalyticsApi — per-flow analytics dashboard. */
// export const flowAnalyticsApi = {
//   list: () =>
//     http.get<FlowAnalyticsSummary[]>("/api/v1/flow-analytics"),
//   get: (flowId: string) =>
//     http.get<FlowAnalyticsSummary>(`/api/v1/flow-analytics/${flowId}`),
// };

// /** autopilotQueueApi — autopilot queue management with enqueue/trigger/cancel. */
// export const autopilotQueueApi = {
//   list: (params?: { status?: string; limit?: number; offset?: number }) =>
//     http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
//       "/api/v1/autopilot-queue",
//       params,
//     ),
//   stats: () =>
//     http.get<AutopilotQueueStats>("/api/v1/autopilot-queue/stats"),
//   enqueue: (body: AutopilotQueueEnqueueBody) =>
//     http.post<AutopilotQueueItem>("/api/v1/autopilot-queue/enqueue", body),
//   triggerScheduler: () =>
//     http.post<{ triggered: boolean; message: string }>("/api/v1/autopilot-queue/trigger-scheduler"),
//   setAutonomousMode: (enabled: boolean) =>
//     http.put<{ autonomousMode: boolean; message: string }>("/api/v1/autopilot-queue/autonomous-mode", { enabled }),
//   cancel: (id: string) =>
//     http.delete<{ message: string }>(`/api/v1/autopilot-queue/${id}`),
// };


/**
 * apiClient.ts — central axios instance with Bearer + tenant interceptors.
 *
 * The access token is read from a module-level holder kept in sync by
 * `AuthContext` (Section 7.6 of the migration doc). A `VITE_DEV_TENANT_SLUG`
 * override lets local dev target a specific tenant schema without Keycloak
 * claims.
 */
import axios, { AxiosError, type AxiosInstance } from "axios";
import type {
  LandingContent,
  ContactInfo,
  ContactMessage,
  Plan,
  TenantSignupRequest,
  TenantSignupStatus,
  TenantSignupRow,
  TenantRow,
  PlatformMetrics,
  AuditLog,
  TenantIntegration,
  IntegrationMode,
  IntegrationCatalogEntry,
  IntegrationTestResult,
  GlobalLlmConfig,
  GlobalLlmConfigInput,
  GlobalLlmTestResult,
  SenderIdentity,
  EmailQuota,
  UserDashboard,
  ManagerDashboard,
  UsageSummary,
  UsageManagerRollup,
  UsagePlatformRollup,
  CostTableEntry,
  CostTableInput,
  DsrSubmission,
  DsrSubmissionResponse,
  DsrStatusResponse,
  DsrRow,
  ConsentStatus,
  RetentionStatus,
  MailBridgeConfig,
  MailBridgeConfigInput,
  MailBridgePlatformRegistration,
  MailBridgeMailAccount,
  MailBridgeConnectStart,
  MailBridgeTemplate,
  MailBridgeTrackingStatus,
  ProspectingFlow,
  ProspectingFlowInput,
  FlowRun,
  FlowAbTest,
  FlowAbTestInput,
  FlowWebhook,
  FlowWebhookInput,
  AutopilotQueueItem,
  RateLimit,
  RateLimitInput,
  RateLimitLog,
  SchedulerStatus,
  ManualTickResponse,
  SchedulerRun,
  Meeting,
  MeetingInput,
  MeetingPrep,
  DomainEnrichment,
  CallLog,
  CallLogInput,
  PlatformTenantConfig,
  FlowAnalyticsSummary,
  AutopilotQueueStats,
  AutopilotQueueEnqueueBody,
  PipelineStageResult,
  PipelineStatus,
  PipelineRunStageInput,
  FlowTemplate,
  FlowTemplateCloneInput,
} from "@/types/common";

let currentAccessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  currentAccessToken = token;
}

export function getAccessToken(): string | null {
  return currentAccessToken;
}

const DEV_TENANT_SLUG = import.meta.env.VITE_DEV_TENANT_SLUG ?? "";

export const apiClient: AxiosInstance = axios.create({
  baseURL: "/",
  // 300s (5 min) — local LLMs (Ollama) can take 90–180s to respond.
  // Cloud providers (Groq, OpenAI) respond in 2–10s so this has no
  // practical impact on normal usage.
  timeout: 300_000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (DEV_TENANT_SLUG) {
    config.headers["X-Tenant-Slug"] = DEV_TENANT_SLUG;
  }
  return config;
});

apiClient.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    // Normalise 401 → trigger re-login via AuthContext (handled by consumers).
    if (error.response?.status === 401) {
      window.dispatchEvent(new CustomEvent("outrena:unauthorized"));
    }
    return Promise.reject(error);
  },
);

/** Convenience typed request helpers used by feature service modules. */
export const http = {
  get: <T>(url: string, params?: Record<string, unknown>) =>
    apiClient.get<T>(url, { params }).then((r) => r.data),
  post: <T>(url: string, body?: unknown) =>
    apiClient.post<T>(url, body).then((r) => r.data),
  put: <T>(url: string, body?: unknown) =>
    apiClient.put<T>(url, body).then((r) => r.data),
  patch: <T>(url: string, body?: unknown) =>
    apiClient.patch<T>(url, body).then((r) => r.data),
  delete: <T>(url: string) => apiClient.delete<T>(url).then((r) => r.data),
};

/**
 * publicApi — calls to `/api/v1/public/*` and `/api/v1/tenant-signup*`.
 *
 * These endpoints are intentionally NOT authenticated: marketing pages, plan
 * list, contact form, tenant self-signup wizard. They still go through the
 * shared `apiClient` instance (so dev-tenant header is preserved), but the
 * backend does not require a Bearer token.
 */
export const publicApi = {
  landing: () => http.get<LandingContent>("/api/v1/public/landing"),
  plans: () => http.get<Plan[]>("/api/v1/public/plans"),
  contactInfo: () => http.get<ContactInfo>("/api/v1/public/contact-info"),
  contact: (body: ContactMessage) =>
    apiClient.post("/api/v1/public/contact", body).then((r) => r.status),
  checkSubdomain: (subdomain: string) =>
    apiClient
      .get<{ available: boolean }>("/api/v1/public/subdomain-check", {
        params: { subdomain },
      })
      .then((r) => r.data)
      .catch(() => ({ available: false })),
  submitSignup: (body: TenantSignupRequest) =>
    http.post<{ signup_id: string; status: string }>(
      "/api/v1/tenant-signup",
      body,
    ),
  signupStatus: (signupId: string) =>
    http.get<TenantSignupStatus>(
      `/api/v1/tenant-signup/${signupId}/status`,
    ),
};

/**
 * platformApi — SUPER_ADMIN calls to `/api/platform/admin/*`.
 *
 * Uses the authenticated `apiClient` (Bearer + tenant header) but targets the
 * cross-tenant platform admin router. All calls are role-gated server-side to
 * SUPER_ADMIN.
 */
export const platformApi = {
  signups: (status?: string) =>
    http.get<TenantSignupRow[]>("/api/platform/admin/signups", {
      status: status ?? "pending",
    }),
  approveSignup: (id: string) =>
    http.post<{ tenant_slug: string; provisioned: boolean }>(
      `/api/platform/admin/signups/${id}/approve`,
    ),
  rejectSignup: (id: string, reason: string) =>
    http.post(`/api/platform/admin/signups/${id}/reject`, { reason }),
  tenants: () => http.get<TenantRow[]>("/api/platform/admin/tenants"),
  suspendTenant: (id: string) =>
    http.post(`/api/platform/admin/tenants/${id}/suspend`),
  reactivateTenant: (id: string) =>
    http.post(`/api/platform/admin/tenants/${id}/reactivate`),
  metrics: () => http.get<PlatformMetrics>("/api/platform/admin/metrics"),
  auditLogs: (params?: { limit?: number; tenant_slug?: string; action?: string }) =>
    http.get<AuditLog[]>("/api/platform/admin/audit-logs", params),
  // ISSUE-3 FIX: Create tenant endpoint (provisioning — base platform router, not /admin)
  createTenant: (body: {
    slug: string;
    name: string;
    admin_email: string;
    admin_first_name: string;
    admin_last_name: string;
    temporary_password?: string;
    send_invitation: boolean;
  }) =>
    http.post<{ slug: string; status: string; url: string }>(
      "/api/platform/tenants",
      body,
    ),
};

/* ─────────────────────────────────────────────────────────────────────────── */
/* SAAS2-FE: Workstream helpers (integrations, LLM, users, usage, GDPR).      */
/* Each helper targets the exact endpoints specified in the SAAS2-FE task.    */
/* ─────────────────────────────────────────────────────────────────────────── */

/**
 * integrationConfigApi — dual-path integration config.
 *
 * Tenant side (`/api/v1/integrations`): list, create, update, test.
 * Platform side (`/api/platform/admin/...`): per-tenant mode + catalog.
 */
export const integrationConfigApi = {
  tenantList: () => http.get<TenantIntegration[]>("/api/v1/integrations"),
  tenantCreate: (body: {
    type: string;
    name: string;
    key_source: "tenant" | "platform";
    api_key?: string;
  }) => http.post<TenantIntegration>("/api/v1/integrations", {
    platform: body.type,
    name: body.name,
    key_source: body.key_source,
    apiKey: body.key_source === "tenant" ? body.api_key : undefined,
  }),
  tenantUpdate: (
    id: string,
    body: Partial<{
      name: string;
      key_source: "tenant" | "platform";
      api_key?: string;
      is_active: boolean;
    }>,
  ) => http.put<TenantIntegration>(`/api/v1/integrations/${id}`, {
    name: body.name,
    key_source: body.key_source,
    apiKey: body.api_key,
    isActive: body.is_active,
  }),
  tenantTest: (id: string) =>
    http.get<IntegrationTestResult>(
      `/api/v1/integrations/${id}/credentials-test`,
    ),
  // NOTE (Task 2-b finding 9): platformGetConfig removed — duplicate of
  // platformConfigApi.get() which is the one PlatformSettingsPage actually uses.
  platformSetMode: (tenantId: string, integration_mode: IntegrationMode) =>
    http.patch<{ tenant_id: string; integration_mode: IntegrationMode }>(
      `/api/platform/admin/tenants/${tenantId}/integration-mode`,
      { integration_mode },
    ),
  catalog: () =>
    http.get<IntegrationCatalogEntry[]>(
      "/api/platform/admin/integration-catalog",
    ),
};

/**
 * globalLlmApi — SUPER_ADMIN global LLM config (`/api/platform/admin/llm-configs`).
 */
export const globalLlmApi = {
  list: () =>
    http.get<GlobalLlmConfig[]>("/api/platform/admin/llm-configs"),
  create: (body: GlobalLlmConfigInput) =>
    http.post<GlobalLlmConfig>("/api/platform/admin/llm-configs", body),
  update: (id: string, body: GlobalLlmConfigInput) =>
    http.put<GlobalLlmConfig>(`/api/platform/admin/llm-configs/${id}`, body),
  remove: (id: string) =>
    http.delete<{ message: string }>(
      `/api/platform/admin/llm-configs/${id}`,
    ),
  setDefault: (id: string) =>
    http.post<{ message: string }>(
      `/api/platform/admin/llm-configs/${id}/set-default`,
    ),
  test: (id: string) =>
    http.post<GlobalLlmTestResult>(
      `/api/platform/admin/llm-configs/${id}/test`,
    ),
};

/**
 * senderIdentityApi — per-user sender identities (`/api/v1/users/me/...`).
 */
export const senderIdentityApi = {
  list: () =>
    http.get<SenderIdentity[]>("/api/v1/users/me/sender-identities"),
  create: (body: {
    email: string;
    email_type: "platform_assigned" | "corporate";
    display_name?: string;
  }) =>
    http.post<SenderIdentity>("/api/v1/users/me/sender-identities", body),
  remove: (id: string) =>
    http.delete<{ message: string }>(
      `/api/v1/users/me/sender-identities/${id}`,
    ),
  setDefault: (id: string) =>
    http.post<{ message: string }>(
      `/api/v1/users/me/sender-identities/${id}/set-default`,
    ),
  myQuota: () => http.get<EmailQuota>("/api/v1/users/me/email-quota"),
  // NOTE (Task 2-b finding 9): teamQuotas removed — was unused. Re-add from
  // git history (or AUDIT-FE-1 §C.7) when a Team Quotas card is built.
};

/**
 * managerDashboardApi — per-user + manager dashboards (`/api/v1/dashboard*`).
 */
export const managerDashboardApi = {
  mine: () =>
    http.get<UserDashboard>("/api/v1/dashboard", { user_id: "me" }),
  // NOTE (Task 2-b finding 9): user(userId) removed — was unused. Re-add when
  // a per-rep drill-down is built into ManagerDashboardPage.
  manager: () => http.get<ManagerDashboard>("/api/v1/dashboard/manager"),
};

/**
 * usageApi — usage + cost rollups (`/api/v1/usage/*` + platform equivalents).
 */
export const usageApi = {
  me: (period: string) =>
    http.get<UsageSummary>("/api/v1/usage/me", { period }),
  // NOTE (Task 2-b finding 9): user(userId, period) + tenant(period) removed —
  // were unused. Re-add when per-user / per-tenant usage drill-downs are built.
  manager: (period: string) =>
    http.get<UsageManagerRollup>("/api/v1/usage/manager", { period }),
  platform: (period: string) =>
    http.get<UsagePlatformRollup>(
      "/api/v1/usage/platform",
      { period },
    ),
  costTable: () =>
    http.get<CostTableEntry[]>("/api/v1/usage/cost-table"),
  updateCostTable: (entries: CostTableInput[]) =>
    http.put<CostTableEntry[]>("/api/v1/usage/cost-table", entries),
};

/**
 * gdprApi — GDPR DSR + consent + retention endpoints.
 *
 * Public DSR (no auth): `submitDsr` + `dsrStatus`.
 * Authenticated tenant-admin DSR workflow: `list`, `process`, `complete`,
 * `reject`, `export`.
 * Consent: `getConsent`, `grant`, `withdraw`.
 * Retention: `status`, `enforce`.
 */
export const gdprApi = {
  // Public DSR
  submitDsr: (body: DsrSubmission) =>
    http.post<DsrSubmissionResponse>("/api/v1/gdpr/dsr", body),
  dsrStatus: (dsrId: string) =>
    http.get<DsrStatusResponse>(`/api/v1/gdpr/dsr/${dsrId}/status`),
  // Tenant-admin DSR workflow
  list: (status?: string) =>
    http.get<DsrRow[]>("/api/v1/gdpr/dsrs", status ? { status } : undefined),
  process: (id: string) =>
    http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/process`),
  complete: (id: string) =>
    http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/complete`),
  reject: (id: string, reason?: string) =>
    http.post<DsrRow>(`/api/v1/gdpr/dsrs/${id}/reject`, { reason }),
  // NOTE (Task 2-b finding 9): exportUrl + grant removed — were unused.
  // GdprCenterPage builds export URLs inline; the consent grant endpoint
  // (/api/v1/gdpr/consent/grant) is still available on the backend. Re-add
  // these helpers when the corresponding UI is built.
  // Consent
  getConsent: (email: string) =>
    http.get<ConsentStatus>(`/api/v1/gdpr/consent/${encodeURIComponent(email)}`),
  withdraw: (email: string) =>
    http.post("/api/v1/gdpr/consent/withdraw", { email }),
  // Retention
  retentionStatus: () =>
    http.get<RetentionStatus>("/api/v1/gdpr/retention-status"),
  enforceRetention: () =>
    http.post<RetentionStatus>("/api/v1/gdpr/retention/enforce"),
};

/* ─────────────────────────────────────────────────────────────────────────── */
/* FIX-FE-1: New feature-page helpers (MailBridge, Flows, RateLimits,         */
/* Scheduler, Meetings, DomainEnrichment, CallLogs, PlatformTenantConfig).    */
/* Each helper targets the exact endpoints exposed by the backend router.     */
/* ─────────────────────────────────────────────────────────────────────────── */

/** mailbridgeApi — per-tenant MailBridge config CRUD + tenancy endpoints. */
export const mailbridgeApi = {
  // ── Config CRUD ──────────────────────────────────────────────────────────
  list: () => http.get<MailBridgeConfig[]>("/api/v1/mailbridge/config"),
  create: (body: MailBridgeConfigInput) =>
    http.post<MailBridgeConfig>("/api/v1/mailbridge/config", body),
  get: (id: string) =>
    http.get<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`),
  update: (id: string, body: Partial<MailBridgeConfigInput>) =>
    http.put<MailBridgeConfig>(`/api/v1/mailbridge/config/${id}`, body),
  remove: (id: string) =>
    http.delete<{ message: string }>(`/api/v1/mailbridge/config/${id}`),
  /** Send a test email through this config (best-effort). */
  sendTest: (body: { to: string; subject: string; body: string; configId?: string }) =>
    http.post<{ messageId: string; status: string; accepted: boolean }>(
      "/api/v1/mailbridge/send",
      body,
    ),

  // ── Platform Registration ────────────────────────────────────────────────
  /** Register Outrena as a MailBridge tenant — returns {tenant_id, name, slug, api_key}. */
  registerPlatform: (body: { name: string; slug?: string }) =>
    http.post<MailBridgePlatformRegistration>("/api/v1/mailbridge/platform/register", body),

  // ── Account Connection (Identity Propagation) ────────────────────────────
  /** Start OAuth flow for connecting a user's mailbox (Gmail/Outlook). */
  connectStart: (provider: string) =>
    http.post<MailBridgeConnectStart>(`/api/v1/mailbridge/connect/${provider}/start`, {
      return_url: `${window.location.origin}/mailbridge`,
    }),
  /** List connected mail accounts for the current tenant. */
  listMailAccounts: () =>
    http.get<MailBridgeMailAccount[]>("/api/v1/mailbridge/mail-accounts"),

  // ── Templates (proxy to MailBridge /templates) ───────────────────────────
  listTemplates: (params?: { tag?: string; tone?: string }) =>
    http.get<MailBridgeTemplate[]>("/api/v1/mailbridge/templates", params),
  createTemplate: (body: Partial<MailBridgeTemplate>) =>
    http.post<MailBridgeTemplate>("/api/v1/mailbridge/templates", body),
  getTemplate: (name: string) =>
    http.get<MailBridgeTemplate>(`/api/v1/mailbridge/templates/${name}`),
  updateTemplate: (name: string, body: Partial<MailBridgeTemplate>) =>
    http.put<MailBridgeTemplate>(`/api/v1/mailbridge/templates/${name}`, body),
  deleteTemplate: (name: string) =>
    http.delete<{ message: string }>(`/api/v1/mailbridge/templates/${name}`),
  previewTemplate: (name: string, variables: Record<string, unknown>) =>
    http.post<{ subject: string; body_html: string; body_text: string }>(
      `/api/v1/mailbridge/templates/${name}/preview`,
      { variables },
    ),

  // ── Tracking (proxy to MailBridge /tracking) ─────────────────────────────
  getTracking: (messageId: string) =>
    http.get<MailBridgeTrackingStatus>(`/api/v1/mailbridge/tracking/${messageId}`),
  getSequenceTracking: (sequenceId: string) =>
    http.get<MailBridgeTrackingStatus[]>(`/api/v1/mailbridge/tracking/sequence/${sequenceId}`),

  // ── Suppression (proxy to MailBridge /tracking/suppression) ──────────────
  listSuppression: () =>
    http.get<{ email: string; reason: string; created_at: string }[]>("/api/v1/mailbridge/suppression"),
  addSuppression: (body: { email: string; reason?: string }) =>
    http.post<{ email: string; reason: string }>("/api/v1/mailbridge/suppression", body),
  removeSuppression: (email: string) =>
    http.delete<{ message: string }>(`/api/v1/mailbridge/suppression/${email}`),

  // ── Subject Performance ──────────────────────────────────────────────────
  getSubjectPerformance: (group?: string) =>
    http.get<Record<string, unknown>>("/api/v1/mailbridge/subject-performance", group ? { group } : undefined),
};

/** flowsApi — ProspectingFlow + FlowRun + FlowAbTest + FlowWebhook + AutopilotQueue. */
export const flowsApi = {
  // ProspectingFlow definitions
  listFlows: (params?: { isActive?: boolean; isTemplate?: boolean; limit?: number; offset?: number }) =>
    http.get<{ items: ProspectingFlow[]; total: number; limit: number; offset: number }>(
      "/api/v1/flows",
      params,
    ),
  createFlow: (body: ProspectingFlowInput) =>
    http.post<ProspectingFlow>("/api/v1/flows", body),
  getFlow: (id: string) => http.get<ProspectingFlow>(`/api/v1/flows/${id}`),
  updateFlow: (id: string, body: Partial<ProspectingFlowInput>) =>
    http.put<ProspectingFlow>(`/api/v1/flows/${id}`, body),
  removeFlow: (id: string) =>
    http.delete<{ message: string }>(`/api/v1/flows/${id}`),
  // FlowRuns (list + detail; runs are created via /autopilot)
  listRuns: (params?: { flowId?: string; icpProfileId?: string; status?: string; limit?: number; offset?: number }) =>
    http.get<{ items: FlowRun[]; total: number; limit: number; offset: number }>(
      "/api/v1/flows/runs",
      params,
    ),
  getRun: (runId: string) => http.get<FlowRun>(`/api/v1/flows/runs/${runId}`),
  // Flow A/B tests
  listAbTests: (params?: { icpProfileId?: string; status?: string }) =>
    http.get<{ items: FlowAbTest[]; total: number; limit: number; offset: number }>(
      "/api/v1/flows/ab-tests",
      params,
    ),
  createAbTest: (body: FlowAbTestInput) =>
    http.post<FlowAbTest>("/api/v1/flows/ab-tests", body),
  getAbTest: (id: string) => http.get<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`),
  updateAbTest: (id: string, body: Partial<FlowAbTestInput> & { status?: string; significance?: string; summary?: string }) =>
    http.put<FlowAbTest>(`/api/v1/flows/ab-tests/${id}`, body),
  removeAbTest: (id: string) =>
    http.delete<{ message: string }>(`/api/v1/flows/ab-tests/${id}`),
  // Flow webhooks
  listWebhooks: (params?: { flowId?: string; isActive?: boolean }) =>
    http.get<{ items: FlowWebhook[]; total: number; limit: number; offset: number }>(
      "/api/v1/flows/webhooks",
      params,
    ),
  createWebhook: (body: FlowWebhookInput) =>
    http.post<FlowWebhook>("/api/v1/flows/webhooks", body),
  getWebhook: (id: string) => http.get<FlowWebhook>(`/api/v1/flows/webhooks/${id}`),
  updateWebhook: (id: string, body: Partial<FlowWebhookInput>) =>
    http.put<FlowWebhook>(`/api/v1/flows/webhooks/${id}`, body),
  removeWebhook: (id: string) =>
    http.delete<{ message: string }>(`/api/v1/flows/webhooks/${id}`),
  // AutopilotQueue (read-only)
  listQueue: (params?: { status?: string; limit?: number; offset?: number }) =>
    http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
      "/api/v1/flows/queue",
      params,
    ),
};

/** rateLimitsApi — RateLimit + RateLimitLog. */
export const rateLimitsApi = {
  list: (params?: { platform?: string; isActive?: boolean; limit?: number; offset?: number }) =>
    http.get<{ items: RateLimit[]; total: number; limit: number; offset: number }>(
      "/api/v1/rate-limits",
      params,
    ),
  create: (body: RateLimitInput) =>
    http.post<RateLimit>("/api/v1/rate-limits", body),
  get: (id: string) => http.get<RateLimit>(`/api/v1/rate-limits/${id}`),
  update: (id: string, body: Partial<RateLimitInput> & { count?: number }) =>
    http.put<RateLimit>(`/api/v1/rate-limits/${id}`, body),
  remove: (id: string) =>
    http.delete<{ message: string }>(`/api/v1/rate-limits/${id}`),
  resetCounter: (id: string) =>
    http.post<RateLimit>(`/api/v1/rate-limits/${id}/reset`),
  listLogs: (params?: { key?: string; platform?: string; flowRunId?: string; limit?: number; offset?: number }) =>
    http.get<{ items: RateLimitLog[]; total: number; limit: number; offset: number }>(
      "/api/v1/rate-limits/logs",
      params,
    ),
};

/** schedulerApi — scheduler status + manual tick + trigger + runs. */
export const schedulerApi = {
  status: () => http.get<SchedulerStatus>("/api/v1/scheduler/status"),
  tick: (body?: { tenantScoped?: boolean; maxSend?: number }) =>
    http.post<ManualTickResponse>("/api/v1/scheduler/tick", body ?? {}),
  trigger: () =>
    http.post<{ triggered: boolean; message: string; runId: string | null }>(
      "/api/v1/scheduler/trigger",
    ),
  runs: (params?: { limit?: number; offset?: number }) =>
    http.get<{ items: SchedulerRun[]; total: number }>(
      "/api/v1/scheduler/runs",
      params,
    ),
};

/** meetingsApi — Meeting CRUD. The backend Meeting model lives at
 * `/api/v1/meetings`; if the route is missing (pre-FIX-BE follow-up), the
 * page degrades to an error state. The MeetingPrep generate endpoint is
 * backed by the existing `/api/v1/meeting-prep` router. */
export const meetingsApi = {
  list: () => http.get<Meeting[]>("/api/v1/meetings"),
  create: (body: MeetingInput) => http.post<Meeting>("/api/v1/meetings", body),
  get: (id: string) => http.get<Meeting>(`/api/v1/meetings/${id}`),
  update: (id: string, body: Partial<MeetingInput>) =>
    http.patch<Meeting>(`/api/v1/meetings/${id}`, body),
  remove: (id: string) =>
    http.delete<{ message: string }>(`/api/v1/meetings/${id}`),
  // Meeting-prep integration
  generatePrep: (prospectId: string, callType: string = "discovery") =>
    http.post<{ id: string; brief: string }>("/api/v1/meeting-prep/generate", {
      prospectId,
      callType,
    }),
  getPrep: (briefId: string) =>
    http.get<MeetingPrep>(`/api/v1/meeting-prep/${briefId}`),
  listPrepForProspect: (prospectId: string) =>
    http.get<MeetingPrep[]>("/api/v1/meeting-prep", { prospect_id: prospectId }),
};

/** domainEnrichApi — fetch/cache enrichment for a domain. */
export const domainEnrichApi = {
  enrich: (domain: string, forceRefresh = false) =>
    http.post<DomainEnrichment>("/api/v1/domain-enrich", { domain, forceRefresh }),
  enrichBatch: (domains: string[]) =>
    http.post<{ enriched: DomainEnrichment[]; failed: string[] }>(
      "/api/v1/domain-enrich/batch",
      { domains },
    ),
  get: (domain: string) =>
    http.get<DomainEnrichment>(`/api/v1/domain-enrich/${encodeURIComponent(domain)}`),
};

/** callLogsApi — CallLog CRUD. */
export const callLogsApi = {
  list: (params?: { prospectId?: string; outcome?: string; limit?: number; offset?: number }) =>
    http.get<{ items: CallLog[]; total: number; limit: number; offset: number }>(
      "/api/v1/call-logs",
      params,
    ),
  create: (body: CallLogInput) =>
    http.post<CallLog>("/api/v1/call-logs", body),
  get: (id: string) => http.get<CallLog>(`/api/v1/call-logs/${id}`),
  update: (id: string, body: Partial<CallLogInput>) =>
    http.patch<CallLog>(`/api/v1/call-logs/${id}`, body),
  remove: (id: string) =>
    http.delete<{ message: string }>(`/api/v1/call-logs/${id}`),
};

/** platformConfigApi — SUPER_ADMIN tenant_config (per-tenant). */
export const platformConfigApi = {
  get: (tenantId: number | string) =>
    http.get<PlatformTenantConfig>(
      `/api/platform/admin/tenants/${tenantId}/config`,
    ),
  setIntegrationMode: (tenantId: number | string, integration_mode: IntegrationMode) =>
    http.patch<{ tenant_id: number; integration_mode: IntegrationMode; updated_at: string }>(
      `/api/platform/admin/tenants/${tenantId}/integration-mode`,
      { integration_mode },
    ),
};

/** pipelineApi — 5-stage GTM workflow orchestrator. */
export const pipelineApi = {
  runStage: (body: PipelineRunStageInput) =>
    http.post<PipelineStageResult>("/api/v1/pipeline/run-stage", body),
  status: () => http.get<PipelineStatus>("/api/v1/pipeline/status"),
};

/** flowTemplatesApi — pre-built flow template definitions + clone. */
export const flowTemplatesApi = {
  list: () => http.get<FlowTemplate[]>("/api/v1/flow-templates"),
  clone: (body: FlowTemplateCloneInput) =>
    http.post<{ flow_id: string; name: string }>("/api/v1/flow-templates/clone", body),
};

/** publicUnsubscribeApi — one-click unsubscribe (no auth, FR-E14-018). */
export async function publicUnsubscribeApi(
  token: string,
  tenant_slug: string,
): Promise<{ unsubscribed: boolean; message: string }> {
  return http.post<{ unsubscribed: boolean; message: string }>(
    "/api/v1/public/unsubscribe",
    { token, tenant_slug },
  );
}

/** flowAnalyticsApi — per-flow analytics dashboard. */
export const flowAnalyticsApi = {
  list: () =>
    http.get<FlowAnalyticsSummary[]>("/api/v1/flow-analytics"),
  get: (flowId: string) =>
    http.get<FlowAnalyticsSummary>(`/api/v1/flow-analytics/${flowId}`),
};

/** autopilotQueueApi — autopilot queue management with enqueue/trigger/cancel. */
export const autopilotQueueApi = {
  list: (params?: { status?: string; limit?: number; offset?: number }) =>
    http.get<{ items: AutopilotQueueItem[]; total: number; limit: number; offset: number }>(
      "/api/v1/autopilot-queue",
      params,
    ),
  stats: () =>
    http.get<AutopilotQueueStats>("/api/v1/autopilot-queue/stats"),
  enqueue: (body: AutopilotQueueEnqueueBody) =>
    http.post<AutopilotQueueItem>("/api/v1/autopilot-queue/enqueue", body),
  triggerScheduler: () =>
    http.post<{ triggered: boolean; message: string }>("/api/v1/autopilot-queue/trigger-scheduler"),
  setAutonomousMode: (enabled: boolean) =>
    http.put<{ autonomousMode: boolean; message: string }>("/api/v1/autopilot-queue/autonomous-mode", { enabled }),
  cancel: (id: string) =>
    http.delete<{ message: string }>(`/api/v1/autopilot-queue/${id}`),
};