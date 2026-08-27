

// import {
//   LayoutDashboard,
//   // HelpCircle,
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
//       // { label: "Manager Dashboard", path: "/manager-dashboard", icon: Users2,          minimumRole: "MANAGER" },
//       // { label: "Help Guide",        path: "/help-guide",        icon: HelpCircle,      minimumRole: "REP", highlight: true },
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
//       { label: "Integrations",       path: "/setup/integrations",       icon: Plug,       minimumRole: "MANAGER" },       // backend: MANAGER
//       { label: "Integration Config", path: "/setup/integration-config", icon: PlugZap,    minimumRole: "MANAGER" },       // backend: MANAGER
//       { label: "Exclusion Rules",    path: "/outreach/exclusion-rules", icon: Ban,        minimumRole: "MANAGER" },       // backend: MANAGER (write)
//       { label: "Domains",            path: "/setup/domains",            icon: Globe,      minimumRole: "MANAGER" },       // backend: MANAGER
//     ],
//   },
 
//   // ── Flow Builder ──────────────────────────────────────────────────────────
//   // Restored as a separate section matching the Next.js reference structure.
//   {
//     id: "flow_builder",
//     label: "Flow Builder",
//     defaultCollapsed: true,
//     items: [
//       { label: "Prospecting Flows",   path: "/prospecting/flows",           icon: Workflow,       minimumRole: "REP" },      // list=REP, create=MANAGER
//       { label: "Flow Templates",      path: "/prospecting/flow-templates",   icon: LayoutTemplate, minimumRole: "REP" },      // backend: REP
//       { label: "Flow Webhooks",       path: "/prospecting/flows/webhooks",   icon: Webhook,        minimumRole: "REP" },      // list=REP, create=MANAGER
//       { label: "Rate Limits",         path: "/setup/rate-limits",            icon: Timer,          minimumRole: "MANAGER" },  // backend: MANAGER (list/get), TENANT_ADMIN (create/update)
//       { label: "Flow Autopilot Queue",path: "/prospecting/autopilot-queue",  icon: ListOrdered,    minimumRole: "REP" },      // backend: REP
//       { label: "Flow Analytics",      path: "/prospecting/flow-analytics",   icon: BarChart3,      minimumRole: "REP" },      // backend: REP
//       { label: "Flow A/B Tests",      path: "/prospecting/flows/ab-tests",   icon: FlaskConical,   minimumRole: "REP" },      // list=REP, create=MANAGER
//     ],
//   },
 
//   // ── Prospecting ───────────────────────────────────────────────────────────
//   {
//     id: "prospecting",
//     label: "Prospecting",
//     defaultCollapsed: false,
//     items: [
//       { label: "Autopilot Pipeline", path: "/prospecting/autopilot",      icon: Rocket,    minimumRole: "MANAGER", highlight: true }, // backend: MANAGER
//       { label: "ICP Profiles",       path: "/prospecting/icp-profiles",   icon: Target,    minimumRole: "MANAGER" },                  // backend: MANAGER
//       { label: "Prospects",          path: "/prospects",                  icon: Users2,    minimumRole: "REP" },                      // backend: REP
//       { label: "LinkedIn Hub",       path: "/prospecting/linkedin",       icon: Linkedin,  minimumRole: "MANAGER" },                  // backend: MANAGER (list/connect), TENANT_ADMIN (config)
//       { label: "Alumni Tracker",     path: "/prospecting/alumni-tracker", icon: UserCheck, minimumRole: "REP" },                      // backend: REP
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
//       { label: "MailBridge",          path: "/setup/mailbridge",  icon: Mailbox,     minimumRole: "MANAGER" },      // backend: MANAGER for read/list, TENANT_ADMIN for write
//       { label: "Scheduler",           path: "/setup/scheduler",   icon: AlarmClock,  minimumRole: "TENANT_ADMIN" }, // backend: TENANT_ADMIN for config
//       { label: "Sender Identities",   path: "/setup/sender-identities", icon: Mail,  minimumRole: "REP" },
//       { label: "Usage & Cost",        path: "/usage",             icon: DollarSign,  minimumRole: "REP" },
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
  // HelpCircle,
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
      // { label: "Manager Dashboard", path: "/manager-dashboard", icon: Users2,          minimumRole: "MANAGER" },
      // { label: "Help Guide",        path: "/help-guide",        icon: HelpCircle,      minimumRole: "REP", highlight: true },
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
      { label: "Scheduler",           path: "/setup/scheduler",   icon: AlarmClock,  minimumRole: "MANAGER" },      // MANAGER+ can view status, run tick, trigger
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