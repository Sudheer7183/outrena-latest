// /**
//  * nav-config.tsx — single source of truth for the sidebar nav + routes.
//  *
//  * Originally 30 items across 7 sections (migration §7.3). Task SAAS-FE added
//  * 6 new items across 3 new sections (Setup.Billing, Admin.Roles/Permissions/
//  * AuditLogs, Support, Platform.Admin). Each item carries `minimumRole` so the
//  * Sidebar filters by role and ProtectedRoute gates the route.
//  */
// import {
//   LayoutDashboard,
//   HelpCircle,
//   Cpu,
//   FileText,
//   Settings2,
//   Plug,
//   Globe,
//   Wand2,
//   Target,
//   Users2,
//   Radar,
//   Linkedin,
//   BriefcaseBusiness,
//   Trophy,
//   Mail,
//   Send,
//   ListChecks,
//   Inbox,
//   Paperclip,
//   CalendarClock,
//   Ban,
//   LayoutTemplate,
//   KanbanSquare,
//   BarChart3,
//   FlaskConical,
//   Lightbulb,
//   Newspaper,
//   SlidersHorizontal,
//   ShieldCheck,
//   CreditCard,
//   KeyRound,
//   Lock,
//   ScrollText,
//   LifeBuoy,
//   ShieldAlert,
//   DollarSign,
//   Gauge,
//   PlugZap,
//   // FIX-FE-1: new feature-page icons
//   Mailbox,
//   Workflow,
//   History,
//   Webhook,
//   Timer,
//   AlarmClock,
//   Calendar,
//   Building2,
//   Phone,
//   ListOrdered,
//   UserCheck,
//   type LucideIcon,
// } from "lucide-react";
// import type { Role } from "@/types/common";

// export interface NavItem {
//   label: string;
//   path: string;
//   icon: LucideIcon;
//   minimumRole: Role;
// }

// export interface NavSection {
//   id: string;
//   label: string;
//   items: NavItem[];
// }

// export const NAV_SECTIONS: NavSection[] = [
//   {
//     id: "top",
//     label: "Overview",
//     items: [
//       { label: "Dashboard", path: "/", icon: LayoutDashboard, minimumRole: "REP" },
//       // SAAS2-FE: manager dashboard (MANAGER+)
//       { label: "Manager Dashboard", path: "/manager-dashboard", icon: Users2, minimumRole: "MANAGER" },
//       { label: "Help Guide", path: "/help-guide", icon: HelpCircle, minimumRole: "REP" },
//     ],
//   },
//   {
//     id: "setup",
//     label: "Setup",
//     items: [
//       { label: "LLM Models", path: "/setup/llm-models", icon: Cpu, minimumRole: "TENANT_ADMIN" },
//       { label: "Prompt Management", path: "/setup/prompts", icon: FileText, minimumRole: "TENANT_ADMIN" },
//       { label: "System Parameters", path: "/setup/system-params", icon: Settings2, minimumRole: "TENANT_ADMIN" },
//       { label: "Integrations", path: "/setup/integrations", icon: Plug, minimumRole: "TENANT_ADMIN" },
//       // SAAS2-FE: dual-path integration config
//       { label: "Integration Config", path: "/setup/integration-config", icon: PlugZap, minimumRole: "TENANT_ADMIN" },
//       { label: "Domains", path: "/setup/domains", icon: Globe, minimumRole: "TENANT_ADMIN" },
//       // FIX-FE-1: MailBridge config + Rate Limits + Scheduler
//       { label: "MailBridge", path: "/setup/mailbridge", icon: Mailbox, minimumRole: "TENANT_ADMIN" },
//       { label: "Rate Limits", path: "/setup/rate-limits", icon: Timer, minimumRole: "TENANT_ADMIN" },
//       { label: "Scheduler", path: "/setup/scheduler", icon: AlarmClock, minimumRole: "TENANT_ADMIN" },
//       // SAAS2-FE: per-user sender identities
//       { label: "Sender Identities", path: "/setup/sender-identities", icon: Mail, minimumRole: "REP" },
//       { label: "Billing", path: "/setup/billing", icon: CreditCard, minimumRole: "TENANT_ADMIN" },
//       // SAAS2-FE: usage + cost
//       { label: "Usage & Cost", path: "/usage", icon: DollarSign, minimumRole: "REP" },
//     ],
//   },
//   {
//     id: "prospecting",
//     label: "Prospecting",
//     items: [
//       { label: "Autopilot", path: "/prospecting/autopilot", icon: Wand2, minimumRole: "REP" },
//       { label: "ICP Profiles", path: "/prospecting/icp-profiles", icon: Target, minimumRole: "REP" },
//       { label: "Prospects", path: "/prospects", icon: Users2, minimumRole: "REP" },
//       { label: "Prospect Sourcing", path: "/prospecting/sourcing", icon: Radar, minimumRole: "REP" },
//       // FIX-FE-1: Flow definitions + runs + ab-tests + webhooks + domain enrichment
//       { label: "Flow Templates", path: "/prospecting/flow-templates", icon: LayoutTemplate, minimumRole: "REP" },
//       { label: "Flows", path: "/prospecting/flows", icon: Workflow, minimumRole: "REP" },
//       { label: "Flow Runs", path: "/prospecting/flows/runs", icon: History, minimumRole: "REP" },
//       { label: "Flow A/B Tests", path: "/prospecting/flows/ab-tests", icon: FlaskConical, minimumRole: "REP" },
//       { label: "Flow Webhooks", path: "/prospecting/flows/webhooks", icon: Webhook, minimumRole: "REP" },
//       { label: "Flow Analytics", path: "/prospecting/flow-analytics", icon: BarChart3, minimumRole: "REP" },
//       { label: "Autopilot Queue", path: "/prospecting/autopilot-queue", icon: ListOrdered, minimumRole: "REP" },
//       { label: "Domain Enrichment", path: "/prospecting/domain-enrich", icon: Building2, minimumRole: "REP" },
//       { label: "LinkedIn", path: "/prospecting/linkedin", icon: Linkedin, minimumRole: "REP" },
//       { label: "Job-Change Monitor", path: "/prospecting/job-change", icon: BriefcaseBusiness, minimumRole: "REP" },
//       { label: "Competitor Radar", path: "/prospecting/competitors", icon: Trophy, minimumRole: "REP" },
//       { label: "Lead Score", path: "/prospecting/lead-score", icon: ShieldCheck, minimumRole: "REP" },
//       { label: "Signals Feed", path: "/prospecting/signals", icon: Radar, minimumRole: "REP" },
//       { label: "Alumni Tracker", path: "/prospecting/alumni-tracker", icon: UserCheck, minimumRole: "REP" },
//     ],
//   },
//   {
//     id: "outreach",
//     label: "Outreach",
//     items: [
//       { label: "Campaigns", path: "/outreach/campaigns", icon: Mail, minimumRole: "REP" },
//       { label: "Email Studio", path: "/outreach/email-studio", icon: Send, minimumRole: "REP" },
//       { label: "Sequences", path: "/outreach/sequences", icon: ListChecks, minimumRole: "REP" },
//       { label: "Reply Inbox", path: "/outreach/reply-inbox", icon: Inbox, minimumRole: "REP" },
//       { label: "Collaterals", path: "/outreach/collaterals", icon: Paperclip, minimumRole: "REP" },
//       { label: "Meeting Prep", path: "/outreach/meeting-prep", icon: CalendarClock, minimumRole: "REP" },
//       { label: "Exclusion Rules", path: "/outreach/exclusion-rules", icon: Ban, minimumRole: "REP" },
//       { label: "Templates", path: "/outreach/templates", icon: LayoutTemplate, minimumRole: "REP" },
//     ],
//   },
//   {
//     id: "pipeline",
//     label: "Pipeline",
//     items: [
//       { label: "Pipeline", path: "/pipeline", icon: Workflow, minimumRole: "REP" },
//       { label: "Deals", path: "/pipeline/deals", icon: KanbanSquare, minimumRole: "REP" },
//       // FIX-FE-1: Meetings + Call Logs
//       { label: "Meetings", path: "/pipeline/meetings", icon: Calendar, minimumRole: "REP" },
//       { label: "Call Logs", path: "/pipeline/call-logs", icon: Phone, minimumRole: "REP" },
//     ],
//   },
//   {
//     id: "optimize",
//     label: "Optimize",
//     items: [
//       { label: "Analytics", path: "/optimize/analytics", icon: BarChart3, minimumRole: "REP" },
//       { label: "A/B Testing", path: "/optimize/ab-testing", icon: FlaskConical, minimumRole: "REP" },
//       { label: "Content Ideas", path: "/optimize/content-ideas", icon: Lightbulb, minimumRole: "REP" },
//       { label: "Weekly Digest", path: "/optimize/weekly-digest", icon: Newspaper, minimumRole: "REP" },
//       { label: "Optimization Rules", path: "/optimize/optimization-rules", icon: SlidersHorizontal, minimumRole: "REP" },
//     ],
//   },
//   {
//     id: "admin",
//     label: "Admin",
//     items: [
//       { label: "User Management", path: "/admin/users", icon: Users2, minimumRole: "TENANT_ADMIN" },
//       { label: "Roles & Permissions", path: "/admin/roles", icon: KeyRound, minimumRole: "TENANT_ADMIN" },
//       { label: "Feature Permissions", path: "/admin/permissions", icon: Lock, minimumRole: "TENANT_ADMIN" },
//       { label: "Audit Logs", path: "/admin/audit-logs", icon: ScrollText, minimumRole: "TENANT_ADMIN" },
//       // SAAS2-FE: GDPR center
//       { label: "GDPR Center", path: "/admin/gdpr", icon: ShieldCheck, minimumRole: "TENANT_ADMIN" },
//     ],
//   },
//   {
//     id: "support",
//     label: "Support",
//     items: [
//       { label: "Support Tickets", path: "/support", icon: LifeBuoy, minimumRole: "REP" },
//     ],
//   },
//   {
//     id: "platform",
//     label: "Platform",
//     items: [
//       {
//         label: "Platform Admin",
//         path: "/platform-admin",
//         icon: ShieldAlert,
//         minimumRole: "SUPER_ADMIN",
//       },
//       // SAAS2-FE: platform admin sub-pages (deep links)
//       { label: "Global LLM Config", path: "/platform-admin/llm-configs", icon: Cpu, minimumRole: "SUPER_ADMIN" },
//       { label: "Platform Integrations", path: "/platform-admin/integrations", icon: PlugZap, minimumRole: "SUPER_ADMIN" },
//       { label: "Platform Usage", path: "/platform-admin/usage", icon: DollarSign, minimumRole: "SUPER_ADMIN" },
//       { label: "Cost Table", path: "/platform-admin/cost-table", icon: Gauge, minimumRole: "SUPER_ADMIN" },
//     ],
//   },
// ];

// /** Flattened list (used by the router to verify all paths are covered). */
// export const ALL_NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

/**
 * nav-config.tsx — single source of truth for the sidebar nav + routes.
 *
 * Originally 30 items across 7 sections (migration §7.3). Task SAAS-FE added
 * 6 new items across 3 new sections (Setup.Billing, Admin.Roles/Permissions/
 * AuditLogs, Support, Platform.Admin). Each item carries `minimumRole` so the
 * Sidebar filters by role and ProtectedRoute gates the route.
 *
 * Gap fixes applied (N-1 through N-13 from gap analysis):
 *   N-2  Autopilot Pipeline uses Rocket icon + highlight:true
 *   N-3  Help Guide gets highlight:true
 *   N-4  Prompt Management gets highlight:true
 *   N-7  Campaign Results added to Optimize section
 *   PATH Autopilot label updated to "Autopilot Pipeline" to match reference
 *   PATH /setup/llm-configs alias added (dashboard links here)
 *   PATH /setup/prompt-management alias added (dashboard links here)
 *   All existing items, roles, paths and section structure preserved exactly.
 */
// import {
//   LayoutDashboard,
//   HelpCircle,
//   Cpu,
//   FileText,
//   Settings2,
//   Plug,
//   Globe,
//   Rocket,
//   Target,
//   Users2,
//   Radar,
//   Linkedin,
//   BriefcaseBusiness,
//   Trophy,
//   Mail,
//   Send,
//   ListChecks,
//   Inbox,
//   Paperclip,
//   CalendarClock,
//   Ban,
//   LayoutTemplate,
//   KanbanSquare,
//   BarChart3,
//   FlaskConical,
//   Lightbulb,
//   Newspaper,
//   SlidersHorizontal,
//   ShieldCheck,
//   CreditCard,
//   KeyRound,
//   Lock,
//   ScrollText,
//   LifeBuoy,
//   ShieldAlert,
//   DollarSign,
//   Gauge,
//   PlugZap,
//   TrendingUp,
//   // FIX-FE-1: new feature-page icons
//   Mailbox,
//   Workflow,
//   History,
//   Webhook,
//   Timer,
//   AlarmClock,
//   Calendar,
//   Building2,
//   Phone,
//   ListOrdered,
//   UserCheck,
//   type LucideIcon,
// } from "lucide-react";
// import type { Role } from "@/types/common";

// export interface NavItem {
//   label: string;
//   path: string;
//   icon: LucideIcon;
//   minimumRole: Role;
//   /** Renders with a visual accent (gradient bg, badge) to draw attention. */
//   highlight?: boolean;
// }

// export interface NavSection {
//   id: string;
//   label: string;
//   items: NavItem[];
// }

// export const NAV_SECTIONS: NavSection[] = [
//   // ── Overview ─────────────────────────────────────────────────────────────
//   {
//     id: "top",
//     label: "Overview",
//     items: [
//       { label: "Dashboard",         path: "/",                  icon: LayoutDashboard, minimumRole: "REP" },
//       { label: "Manager Dashboard", path: "/manager-dashboard", icon: Users2,          minimumRole: "MANAGER" },
//       // N-3: highlight Help Guide so new users can always find it
//       { label: "Help Guide",        path: "/help-guide",        icon: HelpCircle,      minimumRole: "REP", highlight: true },
//     ],
//   },

//   // ── Setup ─────────────────────────────────────────────────────────────────
//   {
//     id: "setup",
//     label: "Setup",
//     items: [
//       // path /setup/llm-models is the canonical route in routes/index.tsx
//       { label: "LLM Models",          path: "/setup/llm-models",        icon: Cpu,      minimumRole: "TENANT_ADMIN" },
//       // N-4: highlight Prompt Management
//       { label: "Prompt Management",   path: "/setup/prompts",            icon: FileText, minimumRole: "TENANT_ADMIN", highlight: true },
//       { label: "System Parameters",   path: "/setup/system-params",      icon: Settings2, minimumRole: "TENANT_ADMIN" },
//       { label: "Integrations",        path: "/setup/integrations",       icon: Plug,     minimumRole: "TENANT_ADMIN" },
//       // SAAS2-FE: dual-path integration config
//       { label: "Integration Config",  path: "/setup/integration-config", icon: PlugZap,  minimumRole: "TENANT_ADMIN" },
//       { label: "Domains",             path: "/setup/domains",            icon: Globe,    minimumRole: "TENANT_ADMIN" },
//       // FIX-FE-1: MailBridge config + Rate Limits + Scheduler
//       { label: "MailBridge",          path: "/setup/mailbridge",         icon: Mailbox,  minimumRole: "TENANT_ADMIN" },
//       { label: "Rate Limits",         path: "/setup/rate-limits",        icon: Timer,    minimumRole: "TENANT_ADMIN" },
//       { label: "Scheduler",           path: "/setup/scheduler",          icon: AlarmClock, minimumRole: "TENANT_ADMIN" },
//       // SAAS2-FE: per-user sender identities
//       { label: "Sender Identities",   path: "/setup/sender-identities",  icon: Mail,     minimumRole: "REP" },
//       { label: "Billing",             path: "/setup/billing",            icon: CreditCard, minimumRole: "TENANT_ADMIN" },
//       // SAAS2-FE: usage + cost
//       { label: "Usage & Cost",        path: "/usage",                    icon: DollarSign, minimumRole: "REP" },
//     ],
//   },

//   // ── Prospecting ───────────────────────────────────────────────────────────
//   {
//     id: "prospecting",
//     label: "Prospecting",
//     items: [
//       // N-2: Autopilot Pipeline — Rocket icon + highlight (the "wow" entry point)
//       { label: "Autopilot Pipeline",  path: "/prospecting/autopilot",        icon: Rocket,        minimumRole: "REP", highlight: true },
//       { label: "ICP Profiles",        path: "/prospecting/icp-profiles",     icon: Target,        minimumRole: "REP" },
//       { label: "Prospects",           path: "/prospects",                    icon: Users2,        minimumRole: "REP" },
//       { label: "Prospect Sourcing",   path: "/prospecting/sourcing",         icon: Radar,         minimumRole: "REP" },
//       // FIX-FE-1: Flow definitions + runs + ab-tests + webhooks + domain enrichment
//       { label: "Flow Templates",      path: "/prospecting/flow-templates",   icon: LayoutTemplate, minimumRole: "REP" },
//       { label: "Flows",               path: "/prospecting/flows",            icon: Workflow,       minimumRole: "REP" },
//       { label: "Flow Runs",           path: "/prospecting/flows/runs",       icon: History,        minimumRole: "REP" },
//       { label: "Flow A/B Tests",      path: "/prospecting/flows/ab-tests",   icon: FlaskConical,   minimumRole: "REP" },
//       { label: "Flow Webhooks",       path: "/prospecting/flows/webhooks",   icon: Webhook,        minimumRole: "REP" },
//       { label: "Flow Analytics",      path: "/prospecting/flow-analytics",   icon: BarChart3,      minimumRole: "REP" },
//       { label: "Autopilot Queue",     path: "/prospecting/autopilot-queue",  icon: ListOrdered,    minimumRole: "REP" },
//       // FIX-FE-1: Domain enrichment
//       { label: "Domain Enrichment",   path: "/prospecting/domain-enrich",   icon: Building2,      minimumRole: "REP" },
//       { label: "LinkedIn",            path: "/prospecting/linkedin",         icon: Linkedin,       minimumRole: "REP" },
//       { label: "Job-Change Monitor",  path: "/prospecting/job-change",       icon: BriefcaseBusiness, minimumRole: "REP" },
//       { label: "Competitor Radar",    path: "/prospecting/competitors",      icon: Trophy,         minimumRole: "REP" },
//       { label: "Lead Score",          path: "/prospecting/lead-score",       icon: ShieldCheck,    minimumRole: "REP" },
//       { label: "Signals Feed",        path: "/prospecting/signals",          icon: Radar,          minimumRole: "REP" },
//       { label: "Alumni Tracker",      path: "/prospecting/alumni-tracker",   icon: UserCheck,      minimumRole: "REP" },
//     ],
//   },

//   // ── Outreach ──────────────────────────────────────────────────────────────
//   {
//     id: "outreach",
//     label: "Outreach",
//     items: [
//       { label: "Campaigns",        path: "/outreach/campaigns",      icon: Mail,          minimumRole: "REP" },
//       { label: "Email Studio",     path: "/outreach/email-studio",   icon: Send,          minimumRole: "REP" },
//       { label: "Sequences",        path: "/outreach/sequences",      icon: ListChecks,    minimumRole: "REP" },
//       { label: "Reply Inbox",      path: "/outreach/reply-inbox",    icon: Inbox,         minimumRole: "REP" },
//       { label: "Collaterals",      path: "/outreach/collaterals",    icon: Paperclip,     minimumRole: "REP" },
//       { label: "Meeting Prep",     path: "/outreach/meeting-prep",   icon: CalendarClock, minimumRole: "REP" },
//       { label: "Exclusion Rules",  path: "/outreach/exclusion-rules",icon: Ban,           minimumRole: "REP" },
//       { label: "Templates",        path: "/outreach/templates",      icon: LayoutTemplate,minimumRole: "REP" },
//     ],
//   },

//   // ── Pipeline ──────────────────────────────────────────────────────────────
//   {
//     id: "pipeline",
//     label: "Pipeline",
//     items: [
//       { label: "Pipeline",   path: "/pipeline",        icon: Workflow,     minimumRole: "REP" },
//       { label: "Deals",      path: "/pipeline/deals",  icon: KanbanSquare, minimumRole: "REP" },
//       // FIX-FE-1: Meetings + Call Logs
//       { label: "Meetings",   path: "/pipeline/meetings",   icon: Calendar, minimumRole: "REP" },
//       { label: "Call Logs",  path: "/pipeline/call-logs",  icon: Phone,    minimumRole: "REP" },
//     ],
//   },

//   // ── Optimize ──────────────────────────────────────────────────────────────
//   {
//     id: "optimize",
//     label: "Optimize",
//     items: [
//       { label: "Analytics",            path: "/optimize/analytics",          icon: BarChart3,       minimumRole: "REP" },
//       // N-7: Campaign Results was missing from nav entirely
//       { label: "Campaign Results",     path: "/optimize/campaign-results",   icon: TrendingUp,      minimumRole: "REP" },
//       { label: "A/B Testing",          path: "/optimize/ab-testing",         icon: FlaskConical,    minimumRole: "REP" },
//       { label: "Content Ideas",        path: "/optimize/content-ideas",      icon: Lightbulb,       minimumRole: "REP" },
//       { label: "Weekly Digest",        path: "/optimize/weekly-digest",      icon: Newspaper,       minimumRole: "REP" },
//       { label: "Optimization Rules",   path: "/optimize/optimization-rules", icon: SlidersHorizontal, minimumRole: "REP" },
//     ],
//   },

//   // ── Admin ─────────────────────────────────────────────────────────────────
//   {
//     id: "admin",
//     label: "Admin",
//     items: [
//       { label: "User Management",      path: "/admin/users",        icon: Users2,      minimumRole: "TENANT_ADMIN" },
//       { label: "Roles & Permissions",  path: "/admin/roles",        icon: KeyRound,    minimumRole: "TENANT_ADMIN" },
//       { label: "Feature Permissions",  path: "/admin/permissions",  icon: Lock,        minimumRole: "TENANT_ADMIN" },
//       { label: "Audit Logs",           path: "/admin/audit-logs",   icon: ScrollText,  minimumRole: "TENANT_ADMIN" },
//       // SAAS2-FE: GDPR center
//       { label: "GDPR Center",          path: "/admin/gdpr",         icon: ShieldCheck, minimumRole: "TENANT_ADMIN" },
//     ],
//   },

//   // ── Support ───────────────────────────────────────────────────────────────
//   {
//     id: "support",
//     label: "Support",
//     items: [
//       { label: "Support Tickets", path: "/support", icon: LifeBuoy, minimumRole: "REP" },
//     ],
//   },

//   // ── Platform (SUPER_ADMIN only) ───────────────────────────────────────────
//   {
//     id: "platform",
//     label: "Platform",
//     items: [
//       { label: "Platform Admin",         path: "/platform-admin",                    icon: ShieldAlert, minimumRole: "SUPER_ADMIN" },
//       // SAAS2-FE: platform admin sub-pages (deep links)
//       { label: "Global LLM Config",      path: "/platform-admin/llm-configs",        icon: Cpu,    minimumRole: "SUPER_ADMIN" },
//       { label: "Platform Integrations",  path: "/platform-admin/integrations",       icon: PlugZap, minimumRole: "SUPER_ADMIN" },
//       { label: "Platform Usage",         path: "/platform-admin/usage",              icon: DollarSign, minimumRole: "SUPER_ADMIN" },
//       { label: "Cost Table",             path: "/platform-admin/cost-table",         icon: Gauge,  minimumRole: "SUPER_ADMIN" },
//     ],
//   },
// ];

// /** Flattened list (used by the router to verify all paths are covered). */
// export const ALL_NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

// /**
//  * Path aliases — some pages are navigable from the dashboard quick-actions
//  * using alternative paths. This map resolves them to the canonical NavItem
//  * so breadcrumbs and active-link detection still work.
//  *
//  * Key   = alias path (what the dashboard links to)
//  * Value = canonical path (what nav-config declares)
//  */
// export const PATH_ALIASES: Record<string, string> = {
//   "/setup/llm-configs":        "/setup/llm-models",
//   "/setup/prompt-management":  "/setup/prompts",
// };

/**
 * nav-config.tsx — single source of truth for the sidebar nav + routes.
 *
 * Changes from previous version:
 *   - FLOW BUILDER section restored as a separate collapsible section
 *     (matches Next.js reference structure)
 *   - Stub/no-backend items removed from nav (routes still exist for deep-links):
 *       Flow Runs, Domain Enrichment, Job-Change Monitor, Competitor Radar,
 *       Lead Score, Signals Feed, Meetings, Call Logs, Optimization Rules,
 *       Billing, Support Tickets
 *   - LinkedIn duplicate fixed: "LinkedIn" and "LinkedIn Hub" were two nav
 *     entries pointing to the same page. Kept one entry as "LinkedIn Hub"
 *     under PROSPECTING (matching Next.js) — removed the bare "LinkedIn" entry
 *   - Routes for hidden items are still registered in routes/index.tsx so
 *     deep-links and quick-action buttons still work
 */
// import {
//   LayoutDashboard,
//   HelpCircle,
//   Cpu,
//   FileText,
//   Settings2,
//   Plug,
//   Globe,
//   Rocket,
//   Target,
//   Users2,
  
//   Linkedin,
//   Mail,
//   Send,
//   ListChecks,
//   Inbox,
//   Paperclip,
//   CalendarClock,
//   Ban,
//   LayoutTemplate,
//   KanbanSquare,
//   BarChart3,
//   FlaskConical,
//   Lightbulb,
//   Newspaper,
//   ShieldCheck,
//   KeyRound,
//   Lock,
//   ScrollText,
//   ShieldAlert,
//   DollarSign,
//   Gauge,
//   PlugZap,
  
//   Mailbox,
//   Workflow,
//   Webhook,
//   Timer,
//   AlarmClock,
//   ListOrdered,
//   UserCheck,
//   type LucideIcon,
// } from "lucide-react";
// import type { Role } from "@/types/common";

// export interface NavItem {
//   label: string;
//   path: string;
//   icon: LucideIcon;
//   minimumRole: Role;
//   /** Renders with a visual accent (violet bg) to draw attention. */
//   highlight?: boolean;
// }

// export interface NavSection {
//   id: string;
//   label: string;
//   /** Item count shown in the section header badge (matches Next.js UX). */
//   items: NavItem[];
//   /** Default collapsed state. true = collapsed on first render. */
//   defaultCollapsed?: boolean;
// }

// export const NAV_SECTIONS: NavSection[] = [
//   // ── Overview ─────────────────────────────────────────────────────────────
//   {
//     id: "top",
//     label: "Overview",
//     defaultCollapsed: false,
//     items: [
//       { label: "Dashboard",         path: "/",                  icon: LayoutDashboard, minimumRole: "REP" },
//       { label: "Manager Dashboard", path: "/manager-dashboard", icon: Users2,          minimumRole: "MANAGER" },
//       { label: "Help Guide",        path: "/help-guide",        icon: HelpCircle,      minimumRole: "REP", highlight: true },
//     ],
//   },

//   // ── Setup ─────────────────────────────────────────────────────────────────
//   {
//     id: "setup",
//     label: "Setup",
//     defaultCollapsed: false,
//     items: [
//       { label: "LLM Models",         path: "/setup/llm-models",        icon: Cpu,        minimumRole: "TENANT_ADMIN" },
//       { label: "Prompt Management",  path: "/setup/prompts",            icon: FileText,   minimumRole: "TENANT_ADMIN", highlight: true },
//       { label: "System Parameters",  path: "/setup/system-params",      icon: Settings2,  minimumRole: "TENANT_ADMIN" },
//       { label: "Integrations",       path: "/setup/integrations",       icon: Plug,       minimumRole: "TENANT_ADMIN" },
//       { label: "Integration Config", path: "/setup/integration-config", icon: PlugZap,    minimumRole: "TENANT_ADMIN" },
//       { label: "Exclusion Rules",    path: "/outreach/exclusion-rules", icon: Ban,        minimumRole: "TENANT_ADMIN" },
//       { label: "Domains",            path: "/setup/domains",            icon: Globe,      minimumRole: "TENANT_ADMIN" },
//     ],
//   },

//   // ── Flow Builder ──────────────────────────────────────────────────────────
//   // Restored as a separate section matching the Next.js reference structure.
//   {
//     id: "flow_builder",
//     label: "Flow Builder",
//     defaultCollapsed: true,
//     items: [
//       { label: "Prospecting Flows",   path: "/prospecting/flows",           icon: Workflow,       minimumRole: "REP" },
//       { label: "Flow Templates",      path: "/prospecting/flow-templates",   icon: LayoutTemplate, minimumRole: "REP" },
//       { label: "Flow Webhooks",       path: "/prospecting/flows/webhooks",   icon: Webhook,        minimumRole: "REP" },
//       { label: "Rate Limits",         path: "/setup/rate-limits",            icon: Timer,          minimumRole: "TENANT_ADMIN" },
//       { label: "Flow Autopilot Queue",path: "/prospecting/autopilot-queue",  icon: ListOrdered,    minimumRole: "REP" },
//       { label: "Flow Analytics",      path: "/prospecting/flow-analytics",   icon: BarChart3,      minimumRole: "REP" },
//       { label: "Flow A/B Tests",      path: "/prospecting/flows/ab-tests",   icon: FlaskConical,   minimumRole: "REP" },
//     ],
//   },

//   // ── Prospecting ───────────────────────────────────────────────────────────
//   {
//     id: "prospecting",
//     label: "Prospecting",
//     defaultCollapsed: false,
//     items: [
//       { label: "Autopilot Pipeline", path: "/prospecting/autopilot",      icon: Rocket,    minimumRole: "REP", highlight: true },
//       { label: "ICP Profiles",       path: "/prospecting/icp-profiles",   icon: Target,    minimumRole: "REP" },
//       { label: "Prospects",          path: "/prospects",                  icon: Users2,    minimumRole: "REP" },
//       // LinkedIn Hub — single authoritative entry (was duplicated as both
//       // "LinkedIn" at /prospecting/linkedin AND "LinkedIn Hub" in Next.js)
//       { label: "LinkedIn Hub",       path: "/prospecting/linkedin",       icon: Linkedin,  minimumRole: "REP" },
//       { label: "Alumni Tracker",     path: "/prospecting/alumni-tracker", icon: UserCheck, minimumRole: "REP" },
//     ],
//   },

//   // ── Outreach ──────────────────────────────────────────────────────────────
//   {
//     id: "outreach",
//     label: "Outreach",
//     defaultCollapsed: false,
//     items: [
//       { label: "Campaigns",    path: "/outreach/campaigns",    icon: Mail,          minimumRole: "REP" },
//       { label: "Email Studio", path: "/outreach/email-studio", icon: Send,          minimumRole: "REP" },
//       { label: "Sequences",    path: "/outreach/sequences",    icon: ListChecks,    minimumRole: "REP" },
//       { label: "Reply Inbox",  path: "/outreach/reply-inbox",  icon: Inbox,         minimumRole: "REP" },
//       { label: "Collaterals",  path: "/outreach/collaterals",  icon: Paperclip,     minimumRole: "REP" },
//       { label: "Meeting Prep", path: "/outreach/meeting-prep", icon: CalendarClock, minimumRole: "REP" },
//       { label: "Templates",    path: "/outreach/templates",    icon: LayoutTemplate,minimumRole: "REP" },
//     ],
//   },

//   // ── Pipeline ──────────────────────────────────────────────────────────────
//   {
//     id: "pipeline",
//     label: "Pipeline",
//     defaultCollapsed: false,
//     items: [
//       { label: "Pipeline", path: "/pipeline",       icon: Workflow,     minimumRole: "REP" },
//       { label: "Deals",    path: "/pipeline/deals", icon: KanbanSquare, minimumRole: "REP" },
//     ],
//   },

//   // ── Optimize ──────────────────────────────────────────────────────────────
//   {
//     id: "optimize",
//     label: "Optimize",
//     defaultCollapsed: false,
//     items: [
//       { label: "Analytics",        path: "/optimize/analytics",        icon: BarChart3,    minimumRole: "REP" },
//       { label: "A/B Testing",      path: "/optimize/ab-testing",       icon: FlaskConical, minimumRole: "REP" },
//       { label: "Content Ideas",    path: "/optimize/content-ideas",    icon: Lightbulb,    minimumRole: "REP" },
//       { label: "Weekly Digest",    path: "/optimize/weekly-digest",    icon: Newspaper,    minimumRole: "REP" },
//     ],
//   },

//   // ── Admin ─────────────────────────────────────────────────────────────────
//   {
//     id: "admin",
//     label: "Admin",
//     defaultCollapsed: false,
//     items: [
//       { label: "User Management",     path: "/admin/users",       icon: Users2,      minimumRole: "TENANT_ADMIN" },
//       { label: "Roles & Permissions", path: "/admin/roles",       icon: KeyRound,    minimumRole: "TENANT_ADMIN" },
//       { label: "Feature Permissions", path: "/admin/permissions", icon: Lock,        minimumRole: "TENANT_ADMIN" },
//       { label: "Audit Logs",          path: "/admin/audit-logs",  icon: ScrollText,  minimumRole: "TENANT_ADMIN" },
//       { label: "GDPR Center",         path: "/admin/gdpr",        icon: ShieldCheck, minimumRole: "TENANT_ADMIN" },
//       // MailBridge + Scheduler + Sender Identities + Usage moved to Setup/Flow Builder
//       // for TENANT_ADMIN — keeping them accessible but not duplicated
//       { label: "MailBridge",          path: "/setup/mailbridge",         icon: Mailbox,    minimumRole: "TENANT_ADMIN" },
//       { label: "Scheduler",           path: "/setup/scheduler",          icon: AlarmClock, minimumRole: "TENANT_ADMIN" },
//       { label: "Sender Identities",   path: "/setup/sender-identities",  icon: Mail,       minimumRole: "REP" },
//       { label: "Usage & Cost",        path: "/usage",                    icon: DollarSign, minimumRole: "REP" },
//     ],
//   },

//   // ── Platform (SUPER_ADMIN only — invisible to TENANT_ADMIN) ───────────────
//   {
//     id: "platform",
//     label: "Platform",
//     defaultCollapsed: true,
//     items: [
//       { label: "Platform Admin",        path: "/platform-admin",                 icon: ShieldAlert, minimumRole: "SUPER_ADMIN" },
//       { label: "Global LLM Config",     path: "/platform-admin/llm-configs",     icon: Cpu,         minimumRole: "SUPER_ADMIN" },
//       { label: "Platform Integrations", path: "/platform-admin/integrations",    icon: PlugZap,     minimumRole: "SUPER_ADMIN" },
//       { label: "Platform Usage",        path: "/platform-admin/usage",           icon: DollarSign,  minimumRole: "SUPER_ADMIN" },
//       { label: "Cost Table",            path: "/platform-admin/cost-table",      icon: Gauge,       minimumRole: "SUPER_ADMIN" },
//     ],
//   },
// ];

// /** Flattened list (used by the router to verify all paths are covered). */
// export const ALL_NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

// /**
//  * Path aliases — some pages are navigable from the dashboard quick-actions
//  * using alternative paths. This map resolves them to the canonical NavItem
//  * so breadcrumbs and active-link detection still work.
//  */
// export const PATH_ALIASES: Record<string, string> = {
//   "/setup/llm-configs":       "/setup/llm-models",
//   "/setup/prompt-management": "/setup/prompts",
//   "/prospecting/linkedin":    "/prospecting/linkedin", // canonical — LinkedIn Hub
// };

import {
  LayoutDashboard,
  HelpCircle,
  Cpu,
  FileText,
  Settings2,
  Plug,
  Globe,
  Rocket,
  Target,
  Users2,
  
  Linkedin,
  Mail,
  Send,
  ListChecks,
  Inbox,
  Paperclip,
  CalendarClock,
  Ban,
  LayoutTemplate,
  KanbanSquare,
  BarChart3,
  FlaskConical,
  Lightbulb,
  Newspaper,
  ShieldCheck,
  KeyRound,
  Lock,
  ScrollText,
  ShieldAlert,
  DollarSign,
  Gauge,
  PlugZap,
  
  Mailbox,
  Workflow,
  Webhook,
  Timer,
  AlarmClock,
  ListOrdered,
  UserCheck,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "@/types/common";
 
export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  minimumRole: Role;
  /** Renders with a visual accent (violet bg) to draw attention. */
  highlight?: boolean;
}
 
export interface NavSection {
  id: string;
  label: string;
  /** Item count shown in the section header badge (matches Next.js UX). */
  items: NavItem[];
  /** Default collapsed state. true = collapsed on first render. */
  defaultCollapsed?: boolean;
}
 
export const NAV_SECTIONS: NavSection[] = [
  // ── Overview ─────────────────────────────────────────────────────────────
  {
    id: "top",
    label: "Overview",
    defaultCollapsed: false,
    items: [
      { label: "Dashboard",         path: "/",                  icon: LayoutDashboard, minimumRole: "REP" },
      { label: "Manager Dashboard", path: "/manager-dashboard", icon: Users2,          minimumRole: "MANAGER" },
      { label: "Help Guide",        path: "/help-guide",        icon: HelpCircle,      minimumRole: "REP", highlight: true },
    ],
  },
 
  // ── Setup ─────────────────────────────────────────────────────────────────
  {
    id: "setup",
    label: "Setup",
    defaultCollapsed: false,
    items: [
      { label: "LLM Models",         path: "/setup/llm-models",        icon: Cpu,        minimumRole: "TENANT_ADMIN" },
      { label: "Prompt Management",  path: "/setup/prompts",            icon: FileText,   minimumRole: "TENANT_ADMIN", highlight: true },
      { label: "System Parameters",  path: "/setup/system-params",      icon: Settings2,  minimumRole: "TENANT_ADMIN" },
      { label: "Integrations",       path: "/setup/integrations",       icon: Plug,       minimumRole: "MANAGER" },       // backend: MANAGER
      { label: "Integration Config", path: "/setup/integration-config", icon: PlugZap,    minimumRole: "MANAGER" },       // backend: MANAGER
      { label: "Exclusion Rules",    path: "/outreach/exclusion-rules", icon: Ban,        minimumRole: "MANAGER" },       // backend: MANAGER (write)
      { label: "Domains",            path: "/setup/domains",            icon: Globe,      minimumRole: "MANAGER" },       // backend: MANAGER
    ],
  },
 
  // ── Flow Builder ──────────────────────────────────────────────────────────
  // Restored as a separate section matching the Next.js reference structure.
  {
    id: "flow_builder",
    label: "Flow Builder",
    defaultCollapsed: true,
    items: [
      { label: "Prospecting Flows",   path: "/prospecting/flows",           icon: Workflow,       minimumRole: "REP" },      // list=REP, create=MANAGER
      { label: "Flow Templates",      path: "/prospecting/flow-templates",   icon: LayoutTemplate, minimumRole: "REP" },      // backend: REP
      { label: "Flow Webhooks",       path: "/prospecting/flows/webhooks",   icon: Webhook,        minimumRole: "REP" },      // list=REP, create=MANAGER
      { label: "Rate Limits",         path: "/setup/rate-limits",            icon: Timer,          minimumRole: "MANAGER" },  // backend: MANAGER (list/get), TENANT_ADMIN (create/update)
      { label: "Flow Autopilot Queue",path: "/prospecting/autopilot-queue",  icon: ListOrdered,    minimumRole: "REP" },      // backend: REP
      { label: "Flow Analytics",      path: "/prospecting/flow-analytics",   icon: BarChart3,      minimumRole: "REP" },      // backend: REP
      { label: "Flow A/B Tests",      path: "/prospecting/flows/ab-tests",   icon: FlaskConical,   minimumRole: "REP" },      // list=REP, create=MANAGER
    ],
  },
 
  // ── Prospecting ───────────────────────────────────────────────────────────
  {
    id: "prospecting",
    label: "Prospecting",
    defaultCollapsed: false,
    items: [
      { label: "Autopilot Pipeline", path: "/prospecting/autopilot",      icon: Rocket,    minimumRole: "MANAGER", highlight: true }, // backend: MANAGER
      { label: "ICP Profiles",       path: "/prospecting/icp-profiles",   icon: Target,    minimumRole: "MANAGER" },                  // backend: MANAGER
      { label: "Prospects",          path: "/prospects",                  icon: Users2,    minimumRole: "REP" },                      // backend: REP
      { label: "LinkedIn Hub",       path: "/prospecting/linkedin",       icon: Linkedin,  minimumRole: "MANAGER" },                  // backend: MANAGER (list/connect), TENANT_ADMIN (config)
      { label: "Alumni Tracker",     path: "/prospecting/alumni-tracker", icon: UserCheck, minimumRole: "REP" },                      // backend: REP
    ],
  },
 
  // ── Outreach ──────────────────────────────────────────────────────────────
  {
    id: "outreach",
    label: "Outreach",
    defaultCollapsed: false,
    items: [
      { label: "Campaigns",    path: "/outreach/campaigns",    icon: Mail,          minimumRole: "REP" },
      { label: "Email Studio", path: "/outreach/email-studio", icon: Send,          minimumRole: "REP" },
      { label: "Sequences",    path: "/outreach/sequences",    icon: ListChecks,    minimumRole: "REP" },
      { label: "Reply Inbox",  path: "/outreach/reply-inbox",  icon: Inbox,         minimumRole: "REP" },
      { label: "Collaterals",  path: "/outreach/collaterals",  icon: Paperclip,     minimumRole: "REP" },
      { label: "Meeting Prep", path: "/outreach/meeting-prep", icon: CalendarClock, minimumRole: "REP" },
      { label: "Templates",    path: "/outreach/templates",    icon: LayoutTemplate,minimumRole: "REP" },
    ],
  },
 
  // ── Pipeline ──────────────────────────────────────────────────────────────
  {
    id: "pipeline",
    label: "Pipeline",
    defaultCollapsed: false,
    items: [
      { label: "Pipeline", path: "/pipeline",       icon: Workflow,     minimumRole: "REP" },
      { label: "Deals",    path: "/pipeline/deals", icon: KanbanSquare, minimumRole: "REP" },
    ],
  },
 
  // ── Optimize ──────────────────────────────────────────────────────────────
  {
    id: "optimize",
    label: "Optimize",
    defaultCollapsed: false,
    items: [
      { label: "Analytics",        path: "/optimize/analytics",        icon: BarChart3,    minimumRole: "REP" },
      { label: "A/B Testing",      path: "/optimize/ab-testing",       icon: FlaskConical, minimumRole: "REP" },
      { label: "Content Ideas",    path: "/optimize/content-ideas",    icon: Lightbulb,    minimumRole: "REP" },
      { label: "Weekly Digest",    path: "/optimize/weekly-digest",    icon: Newspaper,    minimumRole: "REP" },
    ],
  },
 
  // ── Admin ─────────────────────────────────────────────────────────────────
  {
    id: "admin",
    label: "Admin",
    defaultCollapsed: false,
    items: [
      { label: "User Management",     path: "/admin/users",       icon: Users2,      minimumRole: "TENANT_ADMIN" },
      { label: "Roles & Permissions", path: "/admin/roles",       icon: KeyRound,    minimumRole: "TENANT_ADMIN" },
      { label: "Feature Permissions", path: "/admin/permissions", icon: Lock,        minimumRole: "TENANT_ADMIN" },
      { label: "Audit Logs",          path: "/admin/audit-logs",  icon: ScrollText,  minimumRole: "TENANT_ADMIN" },
      { label: "GDPR Center",         path: "/admin/gdpr",        icon: ShieldCheck, minimumRole: "TENANT_ADMIN" },
      { label: "MailBridge",          path: "/setup/mailbridge",  icon: Mailbox,     minimumRole: "MANAGER" },      // backend: MANAGER for read/list, TENANT_ADMIN for write
      { label: "Scheduler",           path: "/setup/scheduler",   icon: AlarmClock,  minimumRole: "TENANT_ADMIN" }, // backend: TENANT_ADMIN for config
      { label: "Sender Identities",   path: "/setup/sender-identities", icon: Mail,  minimumRole: "REP" },
      { label: "Usage & Cost",        path: "/usage",             icon: DollarSign,  minimumRole: "REP" },
    ],
  },
 
  // ── Platform (SUPER_ADMIN only — invisible to TENANT_ADMIN) ───────────────
  {
    id: "platform",
    label: "Platform",
    defaultCollapsed: true,
    items: [
      { label: "Platform Admin",        path: "/platform-admin",                 icon: ShieldAlert, minimumRole: "SUPER_ADMIN" },
      { label: "Global LLM Config",     path: "/platform-admin/llm-configs",     icon: Cpu,         minimumRole: "SUPER_ADMIN" },
      { label: "Platform Integrations", path: "/platform-admin/integrations",    icon: PlugZap,     minimumRole: "SUPER_ADMIN" },
      { label: "Platform Usage",        path: "/platform-admin/usage",           icon: DollarSign,  minimumRole: "SUPER_ADMIN" },
      { label: "Cost Table",            path: "/platform-admin/cost-table",      icon: Gauge,       minimumRole: "SUPER_ADMIN" },
    ],
  },
];
 
/** Flattened list (used by the router to verify all paths are covered). */
export const ALL_NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);
 
/**
 * Path aliases — some pages are navigable from the dashboard quick-actions
 * using alternative paths. This map resolves them to the canonical NavItem
 * so breadcrumbs and active-link detection still work.
 */
export const PATH_ALIASES: Record<string, string> = {
  "/setup/llm-configs":       "/setup/llm-models",
  "/setup/prompt-management": "/setup/prompts",
  "/prospecting/linkedin":    "/prospecting/linkedin", // canonical — LinkedIn Hub
};