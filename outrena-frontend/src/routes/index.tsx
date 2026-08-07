/**
 * routes/index.tsx — createBrowserRouter with all nav routes + login/forbidden
 * + public marketing site + platform admin console + SaaS billing/RBAC/support.
 *
 * Structure (migration §7.2 + SAAS-FE):
 *   /login, /forbidden                                 (public)
 *   <PublicLayout>                                     (no auth, marketing site)
 *     /p                          LandingPage
 *     /p/pricing                  PricingPage
 *     /p/about                    AboutPage
 *     /p/contact                  ContactPage
 *     /p/privacy                  PrivacyPage
 *     /p/terms                    TermsPage
 *     /signup                     SignupPage
 *     /signup/status/:id          SignupStatusPage
 *   <AppLayout>                                        (sidebar + topbar shell)
 *     /                          UserDashboardPage     (REP)
 *     /help-guide                HelpGuidePage         (REP)
 *     <ProtectedRoute REP>                             (role-gated group)
 *       /prospecting/autopilot … /optimize/*           (22 REP pages)
 *       /support                                       (REP)
 *     <ProtectedRoute TENANT_ADMIN>
 *       /setup/*                                       (5 setup pages)
 *       /setup/billing                                 BillingPage
 *       /admin/users                                   UserManagementPage
 *       /admin/roles                                   RolesPage
 *       /admin/permissions                             PermissionsPage
 *       /admin/audit-logs                              AuditLogPage
 *   <ProtectedRoute SUPER_ADMIN>                       (separate console)
 *     /platform-admin/*                                (5 platform pages)
 */
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import { useAuth } from "@/context/AuthContext";

import { LoginPage } from "@/features/auth/LoginPage";
import { ForbiddenPage } from "@/features/auth/ForbiddenPage";
import { HelpGuidePage } from "@/features/help_guide/HelpGuidePage";
import { LlmConfigPage } from "@/features/llm_config/LlmConfigPage";
import { PromptManagementPage } from "@/features/prompt_management/PromptManagementPage";
import { SystemParamsPage } from "@/features/system_params/SystemParamsPage";
import { IntegrationsPage } from "@/features/integrations/IntegrationsPage";
import { DomainsPage } from "@/features/domains/DomainsPage";
import { AutopilotPage } from "@/features/autopilot/AutopilotPage";
import { IcpProfilesPage } from "@/features/icp/IcpProfilesPage";
import { ProspectsPage } from "@/features/prospects/ProspectsPage";
import { ProspectSourcingPage } from "@/features/prospect_source/ProspectSourcingPage";
import { LinkedInPage } from "@/features/linkedin/LinkedInPage";
import { JobChangePage } from "@/features/job_change/JobChangePage";
import { CompetitorsPage } from "@/features/competitors/CompetitorsPage";
import { LeadScorePage } from "@/features/signals/LeadScorePage";
import { SignalsFeedPage } from "@/features/signals/SignalsFeedPage";
import { CampaignsPage } from "@/features/campaigns/CampaignsPage";
import { CampaignDetailPage } from "@/features/campaigns/CampaignDetailPage";
import { EmailStudioPage } from "@/features/email_studio/EmailStudioPage";
import { SequencesPage } from "@/features/sequences/SequencesPage";
import { ReplyInboxPage } from "@/features/reply_drafts/ReplyInboxPage";
import { CollateralsPage } from "@/features/collaterals/CollateralsPage";
import { MeetingPrepPage } from "@/features/meeting_prep/MeetingPrepPage";
import { ExclusionRulesPage } from "@/features/exclusion_rules/ExclusionRulesPage";
import { TemplatesPage } from "@/features/templates/TemplatesPage";
import { DealsKanbanPage } from "@/features/deals/DealsKanbanPage";
import { AnalyticsPage } from "@/features/analytics/AnalyticsPage";
import { ABTestingPage } from "@/features/ab_testing/ABTestingPage";
import { ContentIdeasPage } from "@/features/content_ideas/ContentIdeasPage";
import { WeeklyDigestPage } from "@/features/weekly_digest/WeeklyDigestPage";
import { OptimizationRulesPage } from "@/features/optimization_rules/OptimizationRulesPage";
import { UserManagementPage } from "@/features/user_management/UserManagementPage";

// SAAS-FE: public marketing site
import { PublicLayout } from "@/features/public/PublicLayout";
import { LandingPage } from "@/features/public/LandingPage";
import { PricingPage } from "@/features/public/PricingPage";
import { AboutPage } from "@/features/public/AboutPage";
import { ContactPage } from "@/features/public/ContactPage";
import { PrivacyPage } from "@/features/public/PrivacyPage";
import { TermsPage } from "@/features/public/TermsPage";
import { SignupPage } from "@/features/public/SignupPage";
import { SignupStatusPage } from "@/features/public/SignupStatusPage";
// SAAS2-FE: public DSR + DPA
import { DpaPage } from "@/features/public/DpaPage";
import { GdprRightsPage } from "@/features/public/GdprRightsPage";
import { DsrStatusPage } from "@/features/public/DsrStatusPage";
import { UnsubscribePage } from "@/features/public/UnsubscribePage";

// SAAS-FE: platform admin console
import { PlatformAdminLayout } from "@/features/platform_admin/PlatformAdminLayout";
import { PlatformDashboardPage } from "@/features/platform_admin/PlatformDashboardPage";
import { TenantsPage } from "@/features/platform_admin/TenantsPage";
import { SignupApprovalsPage } from "@/features/platform_admin/SignupApprovalsPage";
import { AuditLogsPage as PlatformAuditLogsPage } from "@/features/platform_admin/AuditLogsPage";
import { PlatformSettingsPage } from "@/features/platform_admin/PlatformSettingsPage";
// SAAS2-FE: platform admin integrations + usage + cost table
import { PlatformIntegrationsPage } from "@/features/platform_admin/PlatformIntegrationsPage";
import { PlatformUsagePage } from "@/features/platform_admin/PlatformUsagePage";
import { CostTablePage } from "@/features/platform_admin/CostTablePage";

// SAAS-FE: tenant-scoped billing / RBAC / support / audit
import { BillingPage } from "@/features/billing/BillingPage";
import { RolesPage } from "@/features/rbac/RolesPage";
import { PermissionsPage } from "@/features/rbac/PermissionsPage";
import { AuditLogPage } from "@/features/audit/AuditLogPage";
import { SupportPage } from "@/features/support/SupportPage";

// SAAS2-FE: new feature modules
import { IntegrationConfigPage } from "@/features/integration_config/IntegrationConfigPage";
import { GlobalLlmConfigPage } from "@/features/global_llm/GlobalLlmConfigPage";
import { UserDashboardPage } from "@/features/user_dashboard/UserDashboardPage";
import { ManagerDashboardPage } from "@/features/manager_dashboard/ManagerDashboardPage";
import { SenderIdentitiesPage } from "@/features/sender_identities/SenderIdentitiesPage";
import { UsagePage } from "@/features/usage/UsagePage";
import { GdprCenterPage } from "@/features/gdpr/GdprCenterPage";

// FIX-FE-1: missing feature pages (MailBridge, Flows, RateLimits, Scheduler,
// Meetings, DomainEnrichment, CallLogs)
import { MailBridgePage } from "@/features/mailbridge/MailBridgePage";
import { FlowsPage } from "@/features/flows/FlowsPage";
import { PipelinePage } from "@/features/pipeline/PipelinePage";
import { FlowTemplatesPage } from "@/features/flow_templates/FlowTemplatesPage";
import { FlowRunsPage } from "@/features/flows/FlowRunsPage";
import { FlowRunDetailPage } from "@/features/flows/FlowRunDetailPage";
import { FlowAbTestsPage } from "@/features/flows/FlowAbTestsPage";
import { FlowWebhooksPage } from "@/features/flows/FlowWebhooksPage";
import { RateLimitsPage } from "@/features/rate_limits/RateLimitsPage";
import { SchedulerStatusPage } from "@/features/scheduler/SchedulerStatusPage";
import { MeetingsPage } from "@/features/meetings/MeetingsPage";
import { DomainEnrichmentPage } from "@/features/domain_enrich/DomainEnrichmentPage";
import { CallLogsPage } from "@/features/call_logs/CallLogsPage";

// AI feature: Alumni Tracker
import { AlumniTrackerPage } from "@/features/alumni_tracker/AlumniTrackerPage";
import { FlowAnalyticsPage } from "@/features/flow_analytics/FlowAnalyticsPage";
import { AutopilotQueuePage } from "@/features/autopilot_queue/AutopilotQueuePage";

export const router = createBrowserRouter([
  // ── Public marketing site (no auth, outside AppLayout) ─────────────────
  {
    element: <PublicLayout />,
    children: [
      { path: "/p", element: <LandingPage /> },
      { path: "/p/pricing", element: <PricingPage /> },
      { path: "/p/about", element: <AboutPage /> },
      { path: "/p/contact", element: <ContactPage /> },
      { path: "/p/privacy", element: <PrivacyPage /> },
      { path: "/p/terms", element: <TermsPage /> },
      // SAAS2-FE: public DSR + DPA
      { path: "/p/dpa", element: <DpaPage /> },
      { path: "/p/gdpr-rights", element: <GdprRightsPage /> },
      { path: "/p/gdpr-status", element: <DsrStatusPage /> },
      { path: "/p/unsubscribe", element: <UnsubscribePage /> },
    ],
  },
  // ── Tenant self-signup (no auth, no chrome) ────────────────────────────
  { path: "/signup", element: <SignupPage /> },
  { path: "/signup/status/:id", element: <SignupStatusPage /> },

  // ── Auth pages ─────────────────────────────────────────────────────────
  { path: "/login", element: <LoginPage /> },
  { path: "/forbidden", element: <ForbiddenPage /> },

  // ── Platform admin console (SUPER_ADMIN, own layout) ───────────────────
  {
    path: "/platform-admin",
    element: <ProtectedRoute minimumRole="SUPER_ADMIN" />,
    children: [
      {
        element: <PlatformAdminLayout />,
        children: [
          { index: true, element: <PlatformDashboardPage /> },
          { path: "tenants", element: <TenantsPage /> },
          { path: "approvals", element: <SignupApprovalsPage /> },
          { path: "audit-logs", element: <PlatformAuditLogsPage /> },
          { path: "settings", element: <PlatformSettingsPage /> },
          // SAAS2-FE: platform admin integrations + usage + cost table
          { path: "integrations", element: <PlatformIntegrationsPage /> },
          { path: "llm-configs", element: <GlobalLlmConfigPage /> },
          { path: "usage", element: <PlatformUsagePage /> },
          { path: "cost-table", element: <CostTablePage /> },
        ],
      },
    ],
  },

  // ── Main app shell ─────────────────────────────────────────────────────
  {
    path: "/",
    element: <AppLayout />,
    children: [
      // SAAS2-FE: per-user dashboard replaces legacy DashboardPage as `/`.
      // INFINITE-LOOP FIX: wrapping in ProtectedRoute ensures unauthenticated
      // users are redirected to /login before UserDashboardPage mounts and
      // fires API calls — preventing the 401 → kc.login() → redirect → 401
      // cycle for users whose session isn't fully established yet.
      {
        element: <ProtectedRoute minimumRole="REP" />,
        children: [{ index: true, element: <UserDashboardPage /> }],
      },
      {
        path: "help-guide",
        element: <ProtectedRoute minimumRole="REP" />,
        children: [
          {
            path: ":sectionSlug?/:articleSlug?",
            element: <HelpGuidePage />,
          },
        ],
      },
      // SAAS2-FE: manager dashboard (MANAGER+)
      {
        path: "manager-dashboard",
        element: <ProtectedRoute minimumRole="MANAGER" />,
        children: [{ index: true, element: <ManagerDashboardPage /> }],
      },
      // REP-gated feature pages
      {
        element: <ProtectedRoute minimumRole="REP" />,
        children: [
          { path: "prospecting/autopilot", element: <AutopilotPage /> },
          { path: "prospecting/icp-profiles", element: <IcpProfilesPage /> },
          { path: "prospects", element: <ProspectsPage /> },
          { path: "prospecting/sourcing", element: <ProspectSourcingPage /> },
          // FIX-FE-1: Flow pages (definitions, runs, ab-tests, webhooks)
          { path: "prospecting/flow-templates", element: <FlowTemplatesPage /> },
          { path: "prospecting/flows", element: <FlowsPage /> },
          { path: "prospecting/flows/runs", element: <FlowRunsPage /> },
          { path: "prospecting/flows/runs/:runId", element: <FlowRunDetailPage /> },
          { path: "prospecting/flows/ab-tests", element: <FlowAbTestsPage /> },
          { path: "prospecting/flows/webhooks", element: <FlowWebhooksPage /> },
          { path: "prospecting/flow-analytics", element: <FlowAnalyticsPage /> },
          { path: "prospecting/autopilot-queue", element: <AutopilotQueuePage /> },
          // FIX-FE-1: Domain enrichment
          { path: "prospecting/domain-enrich", element: <DomainEnrichmentPage /> },
          { path: "prospecting/linkedin", element: <LinkedInPage /> },
          { path: "prospecting/job-change", element: <JobChangePage /> },
          { path: "prospecting/competitors", element: <CompetitorsPage /> },
          { path: "prospecting/lead-score", element: <LeadScorePage /> },
          { path: "prospecting/signals", element: <SignalsFeedPage /> },
          { path: "prospecting/alumni-tracker", element: <AlumniTrackerPage /> },
          { path: "outreach/campaigns", element: <CampaignsPage /> },
          { path: "outreach/campaigns/:id", element: <CampaignDetailPage /> },
          { path: "outreach/email-studio", element: <EmailStudioPage /> },
          { path: "outreach/sequences", element: <SequencesPage /> },
          { path: "outreach/reply-inbox", element: <ReplyInboxPage /> },
          { path: "outreach/collaterals", element: <CollateralsPage /> },
          { path: "outreach/meeting-prep", element: <MeetingPrepPage /> },
          { path: "outreach/exclusion-rules", element: <ExclusionRulesPage /> },
          { path: "outreach/templates", element: <TemplatesPage /> },
          { path: "pipeline", element: <PipelinePage /> },
          { path: "pipeline/deals", element: <DealsKanbanPage /> },
          // FIX-FE-1: Meetings + Call Logs
          { path: "pipeline/meetings", element: <MeetingsPage /> },
          { path: "pipeline/call-logs", element: <CallLogsPage /> },
          { path: "optimize/analytics", element: <AnalyticsPage /> },
          { path: "optimize/ab-testing", element: <ABTestingPage /> },
          { path: "optimize/content-ideas", element: <ContentIdeasPage /> },
          { path: "optimize/weekly-digest", element: <WeeklyDigestPage /> },
          {
            path: "optimize/optimization-rules",
            element: <OptimizationRulesPage />,
          },
          // SAAS2-FE: sender identities (any authenticated user — own data)
          { path: "setup/sender-identities", element: <SenderIdentitiesPage /> },
          // SAAS2-FE: usage + cost (REP sees own, MANAGER+ sees tenant)
          { path: "usage", element: <UsagePage /> },
          // SAAS-FE: support (any authenticated user)
          { path: "support", element: <SupportPage /> },
        ],
      },
      // TENANT_ADMIN-gated setup + admin pages
      {
        element: <ProtectedRoute minimumRole="TENANT_ADMIN" />,
        children: [
          { path: "setup/llm-models", element: <LlmConfigPage /> },
          { path: "setup/prompts", element: <PromptManagementPage /> },
          { path: "setup/system-params", element: <SystemParamsPage /> },
          { path: "setup/integrations", element: <IntegrationsPage /> },
          { path: "setup/domains", element: <DomainsPage /> },
          // SAAS2-FE: dual-path integration config
          { path: "setup/integration-config", element: <IntegrationConfigPage /> },
          // FIX-FE-1: MailBridge config + Rate Limits + Scheduler status
          { path: "setup/mailbridge", element: <MailBridgePage /> },
          { path: "setup/rate-limits", element: <RateLimitsPage /> },
          { path: "setup/scheduler", element: <SchedulerStatusPage /> },
          // SAAS-FE: billing
          { path: "setup/billing", element: <BillingPage /> },
          { path: "admin/users", element: <UserManagementPage /> },
          // SAAS-FE: RBAC + audit
          { path: "admin/roles", element: <RolesPage /> },
          { path: "admin/permissions", element: <PermissionsPage /> },
          { path: "admin/audit-logs", element: <AuditLogPage /> },
          // SAAS2-FE: GDPR center
          { path: "admin/gdpr", element: <GdprCenterPage /> },
        ],
      },
      // Catch-all: redirect to landing for unauthenticated, dashboard for authenticated.
      { path: "*", element: <CatchAllRedirect /> },
    ],
  },
]);

/**
 * Catch-all redirect: → `/` (dashboard) if authenticated, → `/p` (landing)
 * otherwise. Reads `useAuth()` (the router is mounted inside <AuthProvider>).
 */
function CatchAllRedirect() {
  const { isAuthenticated } = useAuth();
  return <Navigate to={isAuthenticated ? "/" : "/p"} replace />;
}

