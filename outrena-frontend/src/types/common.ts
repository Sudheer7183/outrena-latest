/**
 * common.ts — shared frontend types & enums mirroring the FastAPI backend.
 *
 * Enums mirror `app/models/enums.py` (values match Prisma member names so the
 * public API contract is unchanged). Role mirrors `app/schemas/auth.py`.
 */

/* ── Auth / RBAC ─────────────────────────────────────────────────────────── */

export type Role = "SUPER_ADMIN" | "TENANT_ADMIN" | "MANAGER" | "REP";

export const ROLE_HIERARCHY: Record<Role, number> = {
  REP: 10,
  MANAGER: 20,
  TENANT_ADMIN: 30,
  SUPER_ADMIN: 40,
};

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  tenantSlug: string | null;
}

/* ── Backend enums (mirror app/models/enums.py) ──────────────────────────── */

export type TouchAngle =
  | "FirstTouch"
  | "NewEvidence"
  | "DifferentPain"
  | "IndustryInsight"
  | "DirectQuestion"
  | "Breakup";

export type EmailStatus =
  | "Draft"
  | "QaFailed"
  | "QaPassed"
  | "Scheduled"
  | "Sent"
  | "Replied"
  | "Bounced"
  | "Failed";

export type AutopilotQueueStatus =
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type SeniorityTier = "C_Suite" | "Director" | "IC";

/* ── Generic API shapes ──────────────────────────────────────────────────── */

export interface MessageResponse {
  message: string;
}

export interface ApiError {
  detail: string;
  status?: number;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page?: number;
  pageSize?: number;
}

/* ── Core domain models (selected, mirrored from backend schemas) ─────────── */

export interface Prospect {
  id: string;
  name: string;
  email: string | null;
  company: string | null;
  title: string | null;
  linkedinUrl: string | null;
  icpScore: number | null;
  seniority: SeniorityTier | null;
  enrichmentTier: string | null;
  intentSignals: string | null;
  createdAt: string;
  updatedAt: string;
  domain:string | null;
}

export interface Campaign {
  id: string;
  name: string;
  status: string;
  framework: string | null;
  gtmThesis: string | null;
  /** Owner rep — added Task 2-b finding 8. May be null on legacy rows. */
  ownerUserId?: string | null;
  prospectCount: number;
  sequenceCount: number;
  createdAt: string;
  updatedAt: string;
}

/** Minimal user row used by dropdowns (e.g. Campaign owner selector). */
export interface UserLite {
  id: string;
  email: string;
  name: string;
  role: string;
}

/** Minimal collateral row used by the Campaign create dialog multi-select. */
export interface CollateralLite {
  id: string;
  title: string;
  type: string;
}

/** Body for POST /api/v1/collaterals/link (Task 2-b finding 8). */
export interface CampaignCollateralLinkInput {
  collateralId: string;
  campaignId: string;
  sortOrder?: number;
}

export interface Sequence {
  id: string;
  campaignId: string;
  prospectId: string;
  touchNumber: number;
  sendDay: number;
  channel: string;
  angle: TouchAngle;
  framework: string | null;
  subjectLine: string | null;
  bodyCopy: string | null;
  qaScore: number | null;
  qaDetails: string;
  personalisationConfidence: number | null;
  flagForManualReview: boolean;
  status: EmailStatus;
  scheduledFor: string | null;
  sentAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Deal {
  id: string;
  title: string;
  value: number;
  stage: string;
  prospectId: string | null;
  campaignId: string | null;
  notes: string | null;
  expectedClose: string | null;
  closedAt: string | null;
  source: string;
  healthStatus: string | null;
  healthReason: string | null;
  healthCheckedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface KanbanBoard {
  stages: KanbanStage[];
}

export interface KanbanStage {
  id: string;
  name: string;
  deals: Deal[];
}

export interface ReplyDraft {
  id: string;
  prospectId: string | null;
  sequenceId: string | null;
  inboundMessage: string;
  category: string | null;
  suggestedReply: string | null;
  confidence: number | null;
  autoPilotEligible: boolean;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  category: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ABTest {
  id: string;
  name: string;
  status: string;
  metric: string;
  variants: ABTestVariant[];
  winner: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ABTestVariant {
  id: string;
  label: string;
  subject: string;
  sent: number;
  opened: number;
  replied: number;
}

/* ── SaaS commercialization types (Task SAAS-FE) ─────────────────────────── */

/** Public marketing landing content returned by GET /public/landing. */
export interface LandingContent {
  product: {
    name: string;
    tagline: string;
    description: string;
    features: LandingFeature[];
  };
  stats: {
    tenants: number;
    users: number;
    messages_sent: number;
  };
}

export interface LandingFeature {
  icon: string;
  title: string;
  description: string;
}

/** Public contact info returned by GET /public/contact-info. */
export interface ContactInfo {
  email: string;
  phone: string;
  address: string;
  support_hours: string;
}

/** Contact form submission body (POST /public/contact). */
export interface ContactMessage {
  name: string;
  email: string;
  company?: string;
  message: string;
}

/** Subscription plan returned by GET /public/plans and GET /billing/plans. */
export interface Plan {
  id: string;
  name: string;
  display_name: string;
  description: string;
  price_monthly_cents: number;
  price_yearly_cents: number;
  seat_limit: number;
  feature_flags: Record<string, boolean>;
  is_active: boolean;
  sort_order: number;
}

/** Tenant billing subscription returned by GET /billing/subscription. */
export interface Subscription {
  id: string;
  plan: Plan;
  status: string;
  seats_used: number;
  current_period_end: string;
}

/** Invoice row returned by GET /billing/invoices. */
export interface Invoice {
  id: string;
  amount_cents: number;
  currency: string;
  status: string;
  period_start: string;
  period_end: string;
  paid_at: string | null;
}

/** Data-driven Role returned by GET /roles. Distinct from the `Role` union. */
export interface RoleDefinition {
  id: string;
  name: string;
  description: string;
  is_system: boolean;
  permissions: Permission[];
}

export interface Permission {
  key: string;
  display_name: string;
  description: string;
  category: string;
}

export interface FeaturePermission {
  feature_key: string;
  required_permission: string;
  description: string;
}

/** Self-serve tenant signup (POST /tenant-signup). */
export interface TenantSignupRequest {
  company_name: string;
  subdomain: string;
  owner_email: string;
  owner_first_name: string;
  owner_last_name: string;
  plan_id: string;
  /** SAAS2-FE: dual-path integration mode selected during signup. */
  integration_mode?: IntegrationMode;
}

export interface TenantSignupStatus {
  status: "pending_approval" | "approved" | "rejected" | "provisioning";
  tenant_slug?: string;
  rejection_reason?: string;
}

export interface TenantSignupRow {
  id: string;
  company_name: string;
  subdomain: string;
  owner_email: string;
  owner_first_name: string;
  owner_last_name: string;
  plan_id: string;
  status: string;
  created_at: string;
}

export interface TenantRow {
  id: string;
  slug: string;
  name: string;
  status: string;
  plan_name: string;
  seats_used: number;
  seats_limit: number;
  created_at: string;
}

export interface PlatformMetrics {
  total_tenants: number;
  active_tenants: number;
  total_users: number;
  mrr: number;
  churn_rate: number;
}

export interface AuditLog {
  id: string;
  actor_user_id: string | null;
  actor_role: string | null;
  tenant_slug: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  metadata: Record<string, unknown> | null;
  request_id: string | null;
  ip_address: string | null;
  created_at: string;
}

/** Support tickets. */
export type SupportTicketStatus =
  | "open"
  | "pending"
  | "resolved"
  | "closed";

export type SupportTicketPriority = "low" | "normal" | "high" | "urgent";

export interface SupportTicket {
  id: string;
  subject: string;
  category: string;
  priority: SupportTicketPriority;
  status: SupportTicketStatus;
  created_at: string;
  updated_at: string;
}

export interface SupportMessage {
  id: string;
  author_user_id: string | null;
  author_role: string | null;
  body: string;
  is_internal_note: boolean;
  created_at: string;
}

export interface SupportTicketDetail extends SupportTicket {
  messages: SupportMessage[];
}

/** Help-guide content (server-filtered by role). */
export interface HelpSection {
  id: string;
  slug: string;
  title: string;
  description: string;
  sort_order: number;
}

export interface HelpArticle {
  id: string;
  slug: string;
  title: string;
  body: string;
  body_excerpt?: string;
  sort_order: number;
  section_slug?: string;
  section_title?: string;
}

export interface HelpSectionDetail extends HelpSection {
  articles: HelpArticle[];
}

export interface HelpSearchResult {
  id: string;
  slug: string;
  title: string;
  body_excerpt?: string;
  section_slug: string;
  section_title: string;
}

/* ── SAAS2-FE: Dual-path integrations + global LLM (Workstream 1) ─────────── */

export type IntegrationMode = "platform_managed" | "tenant_managed";
export type IntegrationKeySource = "platform" | "tenant";

/** Returned by GET /admin/tenants/{id}/config (SUPER_ADMIN). */
export interface TenantIntegrationConfig {
  tenant_id: string;
  tenant_slug: string;
  integration_mode: IntegrationMode;
  integrations_shared: boolean;
  plan_name?: string;
  updated_at?: string;
}

/** Row in GET /api/v1/integrations (per-tenant). */
export interface TenantIntegration {
  id: string;
  platform: string;
  name: string;
  key_source: IntegrationKeySource;
  isActive: boolean;
  apiKey: string | null;
  settings?: string;
  lastTestedAt?: string | null;
  lastTestResult?: string | null;
  createdAt?: string;
  updatedAt?: string;
}

/** Entry in GET /platform/admin/integration-catalog. */
export interface IntegrationCatalogEntry {
  type: string;
  name: string;
  has_platform_key: boolean;
  description?: string;
}

/** Result of GET /integrations/{id}/credentials-test. */
export interface IntegrationTestResult {
  integrationId: string;
  ok: boolean;
  detail?: string | null;
  latencyMs?: number | null;
}

/** Returned by GET /platform/admin/llm-configs (masked keys). */
export interface GlobalLlmConfig {
  id: string;
  provider: string;
  display_name: string;
  model_name: string;
  base_url: string | null;
  max_tokens: number | null;
  temperature: number | null;
  api_key_masked: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GlobalLlmConfigInput {
  provider: string;
  display_name: string;
  api_key?: string;
  base_url?: string;
  model_name: string;
  max_tokens?: number | null;
  temperature?: number | null;
  is_default?: boolean;
  is_active?: boolean;
}

export interface GlobalLlmTestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}

/** Pricing impact shown on plan cards. */
export interface IntegrationPathPricing {
  platform_managed_delta_cents: number;
  tenant_managed_delta_cents: number;
}

/* ── SAAS2-FE: User capabilities (Workstream 2) ──────────────────────────── */

export type SenderEmailType = "platform_assigned" | "corporate";

/** Row in GET /users/me/sender-identities. */
export interface SenderIdentity {
  id: string;
  email: string;
  email_type: SenderEmailType;
  display_name: string | null;
  is_verified: boolean;
  is_default: boolean;
  daily_send_quota: number;
  created_at?: string;
}

export interface EmailQuota {
  date: string;
  emails_sent: number;
  daily_quota: number;
  remaining: number;
  emails_bounced: number;
  complaints: number;
  is_throttled: boolean;
  throttled_until: string | null;
}

export interface UserEmailQuota extends EmailQuota {
  user_id: string;
  user_name: string;
}

/** Row in GET /dashboard/manager. */
export interface ManagerTeamMember {
  user_id: string;
  user_name: string;
  emails_sent: number;
  campaigns_active: number;
  prospects_contacted: number;
  replies_received: number;
  meetings_booked: number;
  quota_used_pct: number;
  is_at_risk: boolean;
}

export interface ManagerDashboard {
  team_totals: {
    total_users: number;
    total_emails_sent: number;
    total_campaigns_active: number;
    total_pipeline_value: number;
    total_meetings: number;
    total_replies: number;
  };
  members: ManagerTeamMember[];
  top_performers: ManagerTeamMember[];
  at_risk_users: ManagerTeamMember[];
}

/** Personal dashboard for the logged-in user (REP forced to own). */
export interface UserDashboard {
  user_id: string;
  user_name: string;
  campaigns: {
    active_count: number;
    items: { id: string; name: string; status: string; prospect_count: number }[];
  };
  email_quota: EmailQuota;
  sender_identities: {
    total: number;
    default_email: string | null;
  };
  recent_activity: {
    emails_sent_7d: number;
    replies_received_7d: number;
    meetings_booked_7d: number;
    daily: { date: string; emails_sent: number; replies: number; meetings: number }[];
  };
  prospects_contacted: number;
  pipeline_value: number;
}

/* ── SAAS2-FE: Usage + cost (Workstream 3) ───────────────────────────────── */

export interface UsageBreakdownRow {
  event_type: string;
  provider: string;
  quantity: number;
  cost_cents: number;
}

export interface UsageDailyPoint {
  date: string;
  cost_cents: number;
}

export interface UsageSummary {
  total_cost_cents: number;
  breakdown: UsageBreakdownRow[];
  daily: UsageDailyPoint[];
}

export interface UsageUserRow {
  user_id: string;
  user_name: string;
  cost_cents: number;
  events: number;
}

export interface UsageManagerRollup extends UsageSummary {
  per_user: UsageUserRow[];
}

export interface UsageTenantRollupRow {
  tenant_slug: string;
  tenant_name: string;
  cost_cents: number;
  events: number;
}

export interface UsagePlatformRollup {
  total_cost_cents: number;
  per_tenant: UsageTenantRollupRow[];
  daily: UsageDailyPoint[];
}

export interface CostTableEntry {
  id: string;
  provider: string;
  model: string;
  event_type: string;
  unit: string;
  price_per_unit_cents: number;
  updated_at?: string;
}

export interface CostTableInput {
  provider: string;
  model: string;
  event_type: string;
  unit: string;
  price_per_unit_cents: number;
}

/* ── SAAS2-FE: GDPR (Workstream 4) ───────────────────────────────────────── */

export type DsrRequestType =
  | "access"
  | "rectification"
  | "erasure"
  | "portability"
  | "objection"
  | "restriction";

export type DsrStatus =
  | "pending"
  | "processing"
  | "completed"
  | "rejected"
  | "cancelled";

export interface DsrSubmission {
  email: string;
  tenant_slug?: string;
  request_type: DsrRequestType;
  details?: string;
}

export interface DsrSubmissionResponse {
  dsr_id: string;
  status: DsrStatus;
}

export interface DsrStatusResponse {
  status: DsrStatus;
  created_at?: string;
  completed_at?: string | null;
  export_url?: string | null;
  rejection_reason?: string | null;
}

export interface DsrRow {
  id: string;
  email: string;
  request_type: DsrRequestType;
  status: DsrStatus;
  tenant_slug: string | null;
  details: string | null;
  created_at: string;
  updated_at: string;
  assigned_to: string | null;
  export_url: string | null;
  rejection_reason: string | null;
}

export type ConsentLawfulBasis =
  | "consent"
  | "contract"
  | "legal_obligation"
  | "vital_interests"
  | "public_task"
  | "legitimate_interests";

export interface ConsentRecord {
  id: string;
  email: string;
  prospect_id: string | null;
  lawful_basis: ConsentLawfulBasis;
  consent_text: string | null;
  granted_at: string | null;
  withdrawn_at: string | null;
  is_active: boolean;
}

export interface ConsentStatus {
  email: string;
  has_active_consent: boolean;
  lawful_basis: ConsentLawfulBasis | null;
  granted_at: string | null;
  withdrawn_at: string | null;
  history: ConsentRecord[];
}

export interface RetentionPolicy {
  id: string;
  data_category: string;
  retention_days: number;
  auto_purge: boolean;
  description: string | null;
}

export interface RetentionStatus {
  policies: RetentionPolicy[];
  last_enforced_at: string | null;
  pending_purge_count: number;
  next_run_at: string | null;
}

/* ── FIX-FE-1: Missing feature pages (MailBridge, Flows, RateLimits, etc.) ─ */

/** MailBridgeConfig — row in GET /api/v1/mailbridge/config. */
export type MailBridgeProvider = "gmail" | "smtp" | "outlook" | "sendgrid" | "ses";

export interface MailBridgeConfig {
  id: string;
  name: string;
  baseUrl: string;
  provider: string;
  fromEmail: string;
  fromName: string | null;
  isActive: boolean;
  webhookSecret: string | null;
  domainId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface MailBridgeConfigInput {
  name: string;
  baseUrl: string;
  provider?: string;
  fromEmail: string;
  fromName?: string | null;
  isActive?: boolean;
  webhookSecret?: string | null;
  domainId?: string | null;
}

/* ── Flows: ProspectingFlow + FlowRun + FlowAbTest + FlowWebhook ────────── */

export type FlowRunStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type FlowRunStepKind =
  | "SOURCE"
  | "ENRICH"
  | "QUALITY"
  | "SEND";

export type FlowRunStepStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED";

export type FlowAbTestStatus =
  | "DRAFT"
  | "RUNNING"
  | "COMPLETED"
  | "CANCELLED";

export type WebhookTriggerEvent =
  | "ICP_CREATED"
  | "FLOW_RUN_COMPLETED"
  | "FLOW_RUN_FAILED"
  | "PROSPECT_IMPORTED";

export type WebhookDeliveryStatus =
  | "PENDING"
  | "SUCCESS"
  | "FAILED"
  | "RETRYING";

export interface ProspectingFlow {
  id: string;
  name: string;
  description: string | null;
  isDefault: boolean;
  isActive: boolean;
  isTemplate: boolean;
  templateTag: string | null;
  templateIcon: string | null;
  templateColor: string | null;
  sourceSteps: string;
  enrichmentSteps: string;
  qualityGates: string;
  createdAt: string;
  updatedAt: string;
}

export interface ProspectingFlowInput {
  name: string;
  description?: string | null;
  isDefault?: boolean;
  isActive?: boolean;
  isTemplate?: boolean;
  templateTag?: string | null;
  templateIcon?: string | null;
  templateColor?: string | null;
  sourceSteps?: string;
  enrichmentSteps?: string;
  qualityGates?: string;
}

export interface FlowRunStep {
  id: string;
  runId: string;
  kind: FlowRunStepKind;
  stepKey: string;
  order: number;
  status: FlowRunStepStatus;
  metrics: string;
  durationMs: number | null;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

export interface FlowRun {
  id: string;
  flowId: string;
  icpProfileId: string;
  status: FlowRunStatus;
  triggeredBy: string;
  triggeredById: string | null;
  config: string;
  stats: string;
  importedProspectIds: string;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
  updatedAt: string;
  steps: FlowRunStep[];
}

export interface FlowAbTest {
  id: string;
  name: string;
  description: string | null;
  icpProfileId: string;
  flowAId: string;
  flowBId: string;
  status: FlowAbTestStatus;
  significance: string;
  summary: string;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface FlowAbTestInput {
  name: string;
  description?: string | null;
  icpProfileId: string;
  flowAId: string;
  flowBId: string;
}

export interface FlowWebhook {
  id: string;
  name: string;
  url: string;
  secret: string | null;
  events: string;
  flowId: string | null;
  isActive: boolean;
  config: string;
  createdAt: string;
  updatedAt: string;
}

export interface FlowWebhookInput {
  name: string;
  url: string;
  secret?: string | null;
  events?: string;
  flowId?: string | null;
  isActive?: boolean;
  config?: string;
}

export interface AutopilotQueueItem {
  id: string;
  flowId: string;
  icpProfileId: string;
  status: AutopilotQueueStatus;
  origin: string;
  config: string;
  flowRunId: string | null;
  errorMessage: string | null;
  queuedAt: string;
  pickedUpAt: string | null;
  completedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

/* ── RateLimits ─────────────────────────────────────────────────────────── */

export type RateLimitWindow = "MINUTELY" | "HOURLY" | "DAILY";
export type RateLimitThrottleMode = "skip" | "queue";

export interface RateLimit {
  id: string;
  key: string;
  label: string;
  platform: string | null;
  window: RateLimitWindow;
  limit: number;
  count: number;
  windowStart: string;
  throttleMode: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface RateLimitInput {
  key: string;
  label: string;
  platform?: string | null;
  window?: RateLimitWindow;
  limit?: number;
  throttleMode?: string;
  isActive?: boolean;
}

export interface RateLimitLog {
  id: string;
  key: string;
  platform: string | null;
  outcome: string;
  flowRunId: string | null;
  detail: string | null;
  createdAt: string;
}

/* ── Scheduler ──────────────────────────────────────────────────────────── */

export interface SchedulerStatus {
  isRunning: boolean;
  lastTickAt: string | null;
  nextTickAt: string | null;
  sentSinceLastTick: number;
  skippedSinceLastTick: number;
  updatedAt: string;
}

export interface ManualTickResponse {
  sent: number;
  skipped: number;
  durationMs: number;
  tickedAt: string;
}

export interface SchedulerRun {
  id: string;
  startedAt: string;
  completedAt: string | null;
  status: "running" | "completed" | "failed";
  sent: number;
  skipped: number;
  durationMs: number | null;
  error: string | null;
}

/* ── Meetings (lightweight calendar entries) ────────────────────────────── */

export type MeetingStatus =
  | "scheduled"
  | "completed"
  | "cancelled"
  | "no_show";

export interface Meeting {
  id: string;
  title: string;
  scheduledAt: string;
  durationMin: number;
  meetingUrl: string | null;
  status: string;
  prospectId: string | null;
  meetingPrepId: string | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface MeetingInput {
  title: string;
  prospectId?: string | null;
  scheduledAt: string;
  durationMin?: number;
  meetingUrl?: string | null;
  status?: string;
  meetingPrepId?: string | null;
  notes?: string | null;
}

export interface MeetingPrep {
  id: string;
  prospectId: string;
  callType: string;
  brief: string;
  createdAt: string;
}

/* ── DomainEnrichment ───────────────────────────────────────────────────── */

export interface DomainEnrichment {
  id: string;
  domain: string;
  companyName: string | null;
  industry: string | null;
  employeeCount: number | null;
  revenueRange: string | null;
  techStack: string[];
  location: string | null;
  description: string | null;
  lastEnrichedAt: string;
}

/* ── CallLogs ───────────────────────────────────────────────────────────── */

export type CallOutcome =
  | "connected"
  | "voicemail"
  | "gatekeeper"
  | "no-answer"
  | "pending";

export interface CallLog {
  id: string;
  prospectId: string;
  phone: string;
  outcome: string;
  durationSec: number | null;
  notes: string | null;
  calledAt: string;
  createdAt: string;
}

export interface CallLogInput {
  prospectId: string;
  phone: string;
  outcome?: string;
  durationSec?: number | null;
  notes?: string | null;
  calledAt?: string | null;
}

/* ── Flow Analytics ─────────────────────────────────────────────────────── */

export interface FlowAnalyticsSummary {
  flowId: string;
  flowName: string;
  runCount: number;
  successRate: number;
  avgDurationMs: number;
  totalImported: number;
  funnel: {
    sourced: number;
    deduped: number;
    enriched: number;
    gated: number;
    imported: number;
  };
  sourceYield: FlowAnalyticsSourceYield[];
  gatePassRates: FlowAnalyticsGatePassRate[];
  recentRuns: FlowAnalyticsRecentRun[];
}

export interface FlowAnalyticsSourceYield {
  platform: string;
  runs: number;
  found: number;
  afterDedup: number;
  yieldPct: number;
}

export interface FlowAnalyticsGatePassRate {
  gate: string;
  input: number;
  passed: number;
  rejected: number;
  passRate: number;
}

export interface FlowAnalyticsRecentRun {
  runId: string;
  status: string;
  trigger: string;
  startedAt: string | null;
  durationMs: number | null;
  imported: number;
}

/* ── Autopilot Queue (extended) ─────────────────────────────────────────── */

export interface AutopilotQueueStats {
  queued: number;
  running: number;
  completed24h: number;
  failed24h: number;
  autonomousMode: boolean;
}

export interface AutopilotQueueEnqueueBody {
  flowId: string;
  icpProfileId: string;
  maxProspects?: number;
  dryRun?: boolean;
}

/* ── Pipeline (5-stage GTM workflow) ─────────────────────────────────────── */

export type PipelineStageName = "thesis" | "signals" | "scoring" | "briefs" | "campaign";

export interface PipelineStageResult {
  stage: PipelineStageName;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  output: Record<string, unknown> | null;
  startedAt: string | null;
  completedAt: string | null;
  error: string | null;
}

export interface PipelineStatus {
  pipelineId: string | null;
  stages: PipelineStageResult[];
  currentStage: PipelineStageName | null;
  completedCount: number;
  totalCount: number;
}

export interface PipelineRunStageInput {
  stage: PipelineStageName;
  icp_id?: string;
  llm_config_id?: string;
  product_name?: string;
  target_industries?: string[];
  product_description?: string;
  key_value_props?: string[];
}

/* ── Flow Templates ─────────────────────────────────────────────────────── */

export interface FlowTemplate {
  id: string;
  name: string;
  description: string;
  sourcePlatforms: string[];
  enrichmentPlatforms: string[];
  gateStrictness: "strict" | "moderate" | "lenient";
  recommendedFor: string[];
  isTemplate: true;
  createdAt: string;
  updatedAt: string;
}

export interface FlowTemplateCloneInput {
  template_id: string;
  new_name?: string;
}

/* ── Platform TenantConfig (SUPER_ADMIN) ────────────────────────────────── */

export interface PlatformTenantConfig {
  tenant_id: number;
  plan: string;
  max_seats: number;
  features: Record<string, unknown>;
  integrations_shared: boolean;
  llm_provider_default: string;
  integration_mode: IntegrationMode;
  created_at: string;
  updated_at: string;
}
