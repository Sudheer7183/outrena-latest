/**
 * nav-config.tsx — single source of truth for the sidebar nav + routes.
 *
 * Originally 30 items across 7 sections (migration §7.3). Task SAAS-FE added
 * 6 new items across 3 new sections (Setup.Billing, Admin.Roles/Permissions/
 * AuditLogs, Support, Platform.Admin). Each item carries `minimumRole` so the
 * Sidebar filters by role and ProtectedRoute gates the route.
 */
import {
  LayoutDashboard,
  HelpCircle,
  Cpu,
  FileText,
  Settings2,
  Plug,
  Globe,
  Wand2,
  Target,
  Users2,
  Radar,
  Linkedin,
  BriefcaseBusiness,
  Trophy,
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
  SlidersHorizontal,
  ShieldCheck,
  CreditCard,
  KeyRound,
  Lock,
  ScrollText,
  LifeBuoy,
  ShieldAlert,
  DollarSign,
  Gauge,
  PlugZap,
  // FIX-FE-1: new feature-page icons
  Mailbox,
  Workflow,
  History,
  Webhook,
  Timer,
  AlarmClock,
  Calendar,
  Building2,
  Phone,
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
}

export interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    id: "top",
    label: "Overview",
    items: [
      { label: "Dashboard", path: "/", icon: LayoutDashboard, minimumRole: "REP" },
      // SAAS2-FE: manager dashboard (MANAGER+)
      { label: "Manager Dashboard", path: "/manager-dashboard", icon: Users2, minimumRole: "MANAGER" },
      { label: "Help Guide", path: "/help-guide", icon: HelpCircle, minimumRole: "REP" },
    ],
  },
  {
    id: "setup",
    label: "Setup",
    items: [
      { label: "LLM Models", path: "/setup/llm-models", icon: Cpu, minimumRole: "TENANT_ADMIN" },
      { label: "Prompt Management", path: "/setup/prompts", icon: FileText, minimumRole: "TENANT_ADMIN" },
      { label: "System Parameters", path: "/setup/system-params", icon: Settings2, minimumRole: "TENANT_ADMIN" },
      { label: "Integrations", path: "/setup/integrations", icon: Plug, minimumRole: "TENANT_ADMIN" },
      // SAAS2-FE: dual-path integration config
      { label: "Integration Config", path: "/setup/integration-config", icon: PlugZap, minimumRole: "TENANT_ADMIN" },
      { label: "Domains", path: "/setup/domains", icon: Globe, minimumRole: "TENANT_ADMIN" },
      // FIX-FE-1: MailBridge config + Rate Limits + Scheduler
      { label: "MailBridge", path: "/setup/mailbridge", icon: Mailbox, minimumRole: "TENANT_ADMIN" },
      { label: "Rate Limits", path: "/setup/rate-limits", icon: Timer, minimumRole: "TENANT_ADMIN" },
      { label: "Scheduler", path: "/setup/scheduler", icon: AlarmClock, minimumRole: "TENANT_ADMIN" },
      // SAAS2-FE: per-user sender identities
      { label: "Sender Identities", path: "/setup/sender-identities", icon: Mail, minimumRole: "REP" },
      { label: "Billing", path: "/setup/billing", icon: CreditCard, minimumRole: "TENANT_ADMIN" },
      // SAAS2-FE: usage + cost
      { label: "Usage & Cost", path: "/usage", icon: DollarSign, minimumRole: "REP" },
    ],
  },
  {
    id: "prospecting",
    label: "Prospecting",
    items: [
      { label: "Autopilot", path: "/prospecting/autopilot", icon: Wand2, minimumRole: "REP" },
      { label: "ICP Profiles", path: "/prospecting/icp-profiles", icon: Target, minimumRole: "REP" },
      { label: "Prospects", path: "/prospects", icon: Users2, minimumRole: "REP" },
      { label: "Prospect Sourcing", path: "/prospecting/sourcing", icon: Radar, minimumRole: "REP" },
      // FIX-FE-1: Flow definitions + runs + ab-tests + webhooks + domain enrichment
      { label: "Flow Templates", path: "/prospecting/flow-templates", icon: LayoutTemplate, minimumRole: "REP" },
      { label: "Flows", path: "/prospecting/flows", icon: Workflow, minimumRole: "REP" },
      { label: "Flow Runs", path: "/prospecting/flows/runs", icon: History, minimumRole: "REP" },
      { label: "Flow A/B Tests", path: "/prospecting/flows/ab-tests", icon: FlaskConical, minimumRole: "REP" },
      { label: "Flow Webhooks", path: "/prospecting/flows/webhooks", icon: Webhook, minimumRole: "REP" },
      { label: "Flow Analytics", path: "/prospecting/flow-analytics", icon: BarChart3, minimumRole: "REP" },
      { label: "Autopilot Queue", path: "/prospecting/autopilot-queue", icon: ListOrdered, minimumRole: "REP" },
      { label: "Domain Enrichment", path: "/prospecting/domain-enrich", icon: Building2, minimumRole: "REP" },
      { label: "LinkedIn", path: "/prospecting/linkedin", icon: Linkedin, minimumRole: "REP" },
      { label: "Job-Change Monitor", path: "/prospecting/job-change", icon: BriefcaseBusiness, minimumRole: "REP" },
      { label: "Competitor Radar", path: "/prospecting/competitors", icon: Trophy, minimumRole: "REP" },
      { label: "Lead Score", path: "/prospecting/lead-score", icon: ShieldCheck, minimumRole: "REP" },
      { label: "Signals Feed", path: "/prospecting/signals", icon: Radar, minimumRole: "REP" },
      { label: "Alumni Tracker", path: "/prospecting/alumni-tracker", icon: UserCheck, minimumRole: "REP" },
    ],
  },
  {
    id: "outreach",
    label: "Outreach",
    items: [
      { label: "Campaigns", path: "/outreach/campaigns", icon: Mail, minimumRole: "REP" },
      { label: "Email Studio", path: "/outreach/email-studio", icon: Send, minimumRole: "REP" },
      { label: "Sequences", path: "/outreach/sequences", icon: ListChecks, minimumRole: "REP" },
      { label: "Reply Inbox", path: "/outreach/reply-inbox", icon: Inbox, minimumRole: "REP" },
      { label: "Collaterals", path: "/outreach/collaterals", icon: Paperclip, minimumRole: "REP" },
      { label: "Meeting Prep", path: "/outreach/meeting-prep", icon: CalendarClock, minimumRole: "REP" },
      { label: "Exclusion Rules", path: "/outreach/exclusion-rules", icon: Ban, minimumRole: "REP" },
      { label: "Templates", path: "/outreach/templates", icon: LayoutTemplate, minimumRole: "REP" },
    ],
  },
  {
    id: "pipeline",
    label: "Pipeline",
    items: [
      { label: "Pipeline", path: "/pipeline", icon: Workflow, minimumRole: "REP" },
      { label: "Deals", path: "/pipeline/deals", icon: KanbanSquare, minimumRole: "REP" },
      // FIX-FE-1: Meetings + Call Logs
      { label: "Meetings", path: "/pipeline/meetings", icon: Calendar, minimumRole: "REP" },
      { label: "Call Logs", path: "/pipeline/call-logs", icon: Phone, minimumRole: "REP" },
    ],
  },
  {
    id: "optimize",
    label: "Optimize",
    items: [
      { label: "Analytics", path: "/optimize/analytics", icon: BarChart3, minimumRole: "REP" },
      { label: "A/B Testing", path: "/optimize/ab-testing", icon: FlaskConical, minimumRole: "REP" },
      { label: "Content Ideas", path: "/optimize/content-ideas", icon: Lightbulb, minimumRole: "REP" },
      { label: "Weekly Digest", path: "/optimize/weekly-digest", icon: Newspaper, minimumRole: "REP" },
      { label: "Optimization Rules", path: "/optimize/optimization-rules", icon: SlidersHorizontal, minimumRole: "REP" },
    ],
  },
  {
    id: "admin",
    label: "Admin",
    items: [
      { label: "User Management", path: "/admin/users", icon: Users2, minimumRole: "TENANT_ADMIN" },
      { label: "Roles & Permissions", path: "/admin/roles", icon: KeyRound, minimumRole: "TENANT_ADMIN" },
      { label: "Feature Permissions", path: "/admin/permissions", icon: Lock, minimumRole: "TENANT_ADMIN" },
      { label: "Audit Logs", path: "/admin/audit-logs", icon: ScrollText, minimumRole: "TENANT_ADMIN" },
      // SAAS2-FE: GDPR center
      { label: "GDPR Center", path: "/admin/gdpr", icon: ShieldCheck, minimumRole: "TENANT_ADMIN" },
    ],
  },
  {
    id: "support",
    label: "Support",
    items: [
      { label: "Support Tickets", path: "/support", icon: LifeBuoy, minimumRole: "REP" },
    ],
  },
  {
    id: "platform",
    label: "Platform",
    items: [
      {
        label: "Platform Admin",
        path: "/platform-admin",
        icon: ShieldAlert,
        minimumRole: "SUPER_ADMIN",
      },
      // SAAS2-FE: platform admin sub-pages (deep links)
      { label: "Global LLM Config", path: "/platform-admin/llm-configs", icon: Cpu, minimumRole: "SUPER_ADMIN" },
      { label: "Platform Integrations", path: "/platform-admin/integrations", icon: PlugZap, minimumRole: "SUPER_ADMIN" },
      { label: "Platform Usage", path: "/platform-admin/usage", icon: DollarSign, minimumRole: "SUPER_ADMIN" },
      { label: "Cost Table", path: "/platform-admin/cost-table", icon: Gauge, minimumRole: "SUPER_ADMIN" },
    ],
  },
];

/** Flattened list (used by the router to verify all paths are covered). */
export const ALL_NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);
