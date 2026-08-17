// /**
//  * UserDashboardPage.tsx — personal dashboard for the logged-in user.
//  *
//  * Mounted at `/` inside <AppLayout>. Fetches:
//  *   - GET /api/v1/dashboard?user_id=me  → DashboardResponse (aggregation + topCampaigns)
//  *   - GET /api/v1/users/me/email-quota  → EmailQuota (today's send quota)
//  *   - GET /api/v1/llm-configs           → LlmConfig[] (LLM warning banner)
//  *   - GET /api/v1/domains               → Domain[] (Domains Ready stat)
//  *   - GET /api/v1/onboarding/checklist  → ChecklistData (onboarding progress)
//  *
//  * Gap fixes applied (D-1 through D-6 from gap analysis):
//  *   D-1  "No LLM configured" amber warning banner with Configure LLM CTA
//  *   D-2  6 stat cards: Total Prospects, Active Campaigns, Emails Generated,
//  *        Avg Open Rate, Avg Reply Rate, Domains Ready — sourced from real API
//  *   D-3  17-item Quick Actions grid navigating to all major pages
//  *   D-4  Recent Campaigns card (top 5 by reply rate, from topCampaigns)
//  *   D-5  10-step AI Outreach Workflow guide (numbered, clickable)
//  *   D-6  useNavigate() wires all navigation actions
//  *
//  * All existing functionality preserved:
//  *   - 4 personal stat cards (emails sent 7d, replies, meetings, pipeline value)
//  *   - Email quota card with progress bar + throttle warning
//  *   - My campaigns list (active count + top 5)
//  *   - Sender identities card
//  *   - 7-day activity bar chart (Recharts)
//  *   - Onboarding checklist
//  */
// import { useQuery } from "@tanstack/react-query";
// import {
//   Bar,
//   BarChart,
//   CartesianGrid,
//   ResponsiveContainer,
//   Tooltip,
//   XAxis,
//   YAxis,
// } from "recharts";
// import {
//   AlertCircle,
//   BarChart3,
//   Bot,
//   BookOpen,
//   CalendarCheck,
//   CalendarDays,
//   ChevronRight,
//   FileText,
//   Globe,
//   Inbox,
//   Kanban,
//   Layers,
//   Lightbulb,
//   Link2,
//   Linkedin,
//   Mail,
//   Megaphone,
//   MessageSquare,
//   Eye,
//   PlayCircle,
//   Plus,
//   Reply,
//   Rocket,
//   Send,
//   ShieldAlert,
//   Sparkles,
//   Target,
//   TrendingUp,
//   Users,
//   Users2,
// } from "lucide-react";
// import { useNavigate } from "react-router-dom";
// import { useAuth } from "@/context/AuthContext";
// import {
//   http,
//   managerDashboardApi,
//   senderIdentityApi,
// } from "@/services/apiClient";
// import { ErrorState } from "@/components/ui/error-state";
// import type { UserDashboard } from "@/types/common";
// import { PageHeader } from "@/components/ui/page-header";
// import { StatCard } from "@/components/ui/stat-card";
// import {
//   Card,
//   CardContent,
//   CardDescription,
//   CardHeader,
//   CardTitle,
// } from "@/components/ui/card";
// import { Skeleton } from "@/components/ui/skeleton";
// import { Badge } from "@/components/ui/badge";
// import { Progress } from "@/components/ui/progress";
// import {
//   Table,
//   TableBody,
//   TableCell,
//   TableHead,
//   TableHeader,
//   TableRow,
// } from "@/components/ui/table";
// import { Button } from "@/components/ui/button";
// import { EmptyState } from "@/components/ui/empty-state";
// import { cn, formatCurrency, formatDate } from "@/lib/utils";

// /* ── Local types ─────────────────────────────────────────────────────────── */

// interface ChecklistItem {
//   key: string;
//   label: string;
//   description: string;
//   link: string;
//   order: number;
//   done: boolean;
// }

// interface ChecklistData {
//   items: ChecklistItem[];
//   completed: number;
//   total: number;
//   all_done: boolean;
// }

// interface LlmConfig {
//   id: string;
//   name: string;
//   isActive: boolean;
//   isDefault: boolean;
// }

// interface DomainSummary {
//   id: string;
//   domain: string;
//   status: string;
// }

// /* ── Mock fallback data (used only if API returns nothing usable) ─────────── */

// const MOCK_DASHBOARD: UserDashboard = {
//   user_id: "me",
//   user_name: "Dev Rep",
//   campaigns: {
//     active_count: 3,
//     items: [
//       { id: "c1", name: "Q1 SaaS Founder Outreach", status: "Active", prospect_count: 248 },
//       { id: "c2", name: "Series B VP Eng — Competitor Switch", status: "Active", prospect_count: 134 },
//       { id: "c3", name: "DTC Operator Roadshow", status: "Paused", prospect_count: 92 },
//       { id: "c4", name: "Healthcare CISO Refresh", status: "Active", prospect_count: 76 },
//       { id: "c5", name: "Fintech Compliance Leaders", status: "Draft", prospect_count: 0 },
//     ],
//   },
//   email_quota: {
//     date: new Date().toISOString().slice(0, 10),
//     emails_sent: 412,
//     daily_quota: 1000,
//     remaining: 588,
//     emails_bounced: 8,
//     complaints: 0,
//     is_throttled: false,
//     throttled_until: null,
//   },
//   sender_identities: {
//     total: 2,
//     default_email: "dev.rep@outrena.io",
//   },
//   recent_activity: {
//     emails_sent_7d: 2840,
//     replies_received_7d: 218,
//     meetings_booked_7d: 14,
//     daily: [
//       { date: "Mon", emails_sent: 320, replies: 28, meetings: 1 },
//       { date: "Tue", emails_sent: 412, replies: 33, meetings: 2 },
//       { date: "Wed", emails_sent: 380, replies: 29, meetings: 1 },
//       { date: "Thu", emails_sent: 502, replies: 41, meetings: 3 },
//       { date: "Fri", emails_sent: 478, replies: 36, meetings: 2 },
//       { date: "Sat", emails_sent: 396, replies: 26, meetings: 2 },
//       { date: "Sun", emails_sent: 352, replies: 25, meetings: 3 },
//     ],
//   },
//   prospects_contacted: 842,
//   pipeline_value: 412_500,
// };

// /* ── Quick Actions definition ────────────────────────────────────────────── */

// const QUICK_ACTIONS = [
//   { label: "Add LLM Model",     path: "/setup/llm-models",            icon: Bot },
//   { label: "Manage Prompts",    path: "/setup/prompts",               icon: FileText },
//   { label: "Create ICP",        path: "/prospecting/icp-profiles",    icon: Target },
//   { label: "Add Prospect",      path: "/prospects",                   icon: Users },
//   { label: "Integrations",      path: "/setup/integrations",          icon: Link2 },
//   { label: "Run Autopilot",     path: "/prospecting/autopilot",       icon: Rocket },
//   { label: "Campaigns",         path: "/outreach/campaigns",          icon: Megaphone },
//   { label: "Generate Email",    path: "/outreach/email-studio",       icon: Sparkles },
//   { label: "Build Sequence",    path: "/outreach/sequences",          icon: Layers },
//   { label: "Setup Domain",      path: "/setup/domains",               icon: Globe },
//   { label: "Analytics",         path: "/optimize/analytics",          icon: BarChart3 },
//   { label: "Templates",         path: "/outreach/templates",          icon: BookOpen },
//   { label: "Track Deals",       path: "/pipeline/deals",              icon: Kanban },
//   { label: "Reply Inbox",       path: "/outreach/reply-inbox",        icon: Inbox },
//   { label: "LinkedIn Hub",      path: "/prospecting/linkedin",        icon: Linkedin },
//   { label: "Content Ideas",     path: "/optimize/content-ideas",      icon: Lightbulb },
//   { label: "Weekly Digest",     path: "/optimize/weekly-digest",      icon: CalendarDays },
// ] as const;

// /* ── Workflow steps definition ───────────────────────────────────────────── */

// const WORKFLOW_STEPS = [
//   { step: 1,  title: "Connect AI Model",       desc: "Set up your LLM provider",         path: "/setup/llm-models" },
//   { step: 2,  title: "Setup Domain",           desc: "Configure sending domain & DNS",   path: "/setup/domains" },
//   { step: 3,  title: "Configure Integrations", desc: "Connect MailBridge & data tools",  path: "/setup/integrations" },
//   { step: 4,  title: "Define ICP",             desc: "Create ideal customer profile",    path: "/prospecting/icp-profiles" },
//   { step: 5,  title: "Import Prospects",       desc: "Add & enrich your leads",          path: "/prospects" },
//   { step: 6,  title: "Run Autopilot",          desc: "AI GTM pipeline — 60 seconds",    path: "/prospecting/autopilot" },
//   { step: 7,  title: "Generate Emails",        desc: "AI copywriting & QA scoring",      path: "/outreach/email-studio" },
//   { step: 8,  title: "Build Sequence",         desc: "Multi-touch cadence",              path: "/outreach/sequences" },
//   { step: 9,  title: "Track Replies",          desc: "Manage inbox & AI drafts",         path: "/outreach/reply-inbox" },
//   { step: 10, title: "Close Deals",            desc: "Pipeline & revenue tracking",      path: "/pipeline/deals" },
// ] as const;

// /* ── Helpers ─────────────────────────────────────────────────────────────── */

// function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
//   const s = status.toLowerCase();
//   if (s === "active") return "default";
//   if (s === "paused") return "secondary";
//   if (s === "draft") return "outline";
//   return "secondary";
// }

// function fmtPct(rate: number): string {
//   return `${(rate * 100).toFixed(1)}%`;
// }

// /* ══════════════════════════════════════════════════════════════════════════ */
// /*  Component                                                                */
// /* ══════════════════════════════════════════════════════════════════════════ */

// export function UserDashboardPage() {
//   const { initialized, isAuthenticated } = useAuth();
//   const navigate = useNavigate();

//   // Gate every query: wait until AuthProvider has resolved + user is authenticated.
//   // Without this gate, API calls fire before the Bearer token is set → 400/401 loop.
//   const queryEnabled = initialized && isAuthenticated;

//   // ── Personal dashboard (aggregation + topCampaigns + timeSeries) ─────────
//   const {
//     data: dashRaw,
//     isLoading: dashLoading,
//     isError: dashError,
//     error: dashErr,
//     refetch: refetchDash,
//   } = useQuery({
//     queryKey: ["dashboard", "me"],
//     queryFn: () => managerDashboardApi.mine(),
//     enabled: queryEnabled,
//     retry: (failureCount, err) => {
//       const status = (err as { response?: { status?: number } })?.response?.status;
//       if (status === 401 || status === 403) return false;
//       return failureCount < 1;
//     },
//   });

//   // ── Email quota (today's send stats) ─────────────────────────────────────
//   const { data: quotaData } = useQuery({
//     queryKey: ["email-quota", "me"],
//     queryFn: () => senderIdentityApi.myQuota(),
//     enabled: queryEnabled,
//   });

//   // ── LLM configs (for the warning banner) ─────────────────────────────────
//   const { data: llmConfigs = [] } = useQuery<LlmConfig[]>({
//     queryKey: ["llm-configs"],
//     queryFn: () => http.get<LlmConfig[]>("/api/v1/llm-configs"),
//     enabled: queryEnabled,
//   });

//   // ── Domains (for "Domains Ready" stat card) ───────────────────────────────
//   const { data: domains = [] } = useQuery<DomainSummary[]>({
//     queryKey: ["domains"],
//     queryFn: () => http.get<DomainSummary[]>("/api/v1/domains"),
//     enabled: queryEnabled,
//   });

//   // ── Onboarding checklist ──────────────────────────────────────────────────
//   const { data: checklist } = useQuery<ChecklistData>({
//     queryKey: ["onboarding-checklist"],
//     queryFn: () => http.get<ChecklistData>("/api/v1/onboarding/checklist"),
//     enabled: queryEnabled,
//   });

//   // ── Resolve data (real or mock fallback) ──────────────────────────────────
//   const dash: UserDashboard = (dashRaw as UserDashboard) ?? MOCK_DASHBOARD;
//   const quota = quotaData ?? dash.email_quota;
//   const activity = dash.recent_activity;

//   // ── Derived values ────────────────────────────────────────────────────────

//   // LLM warning: no active config
//   const hasActiveLlm = llmConfigs.some((c) => c.isActive);

//   // 6 stat cards — sourced from DashboardResponse.aggregation when available,
//   // fall back to UserDashboard personal totals.
//   const agg = (dashRaw as any)?.aggregation ?? null;

//   const totalProspects: number =
//     agg?.totalProspects ?? dash.prospects_contacted ?? 0;
//   const activeCampaigns: number =
//     agg?.activeCampaigns ?? dash.campaigns?.active_count ?? 0;
//   const emailsGenerated: number =
//     agg?.totalSequences ?? activity?.emails_sent_7d ?? 0;
//   const avgOpenRate: number = agg?.avgOpenRate ?? 0;
//   const avgReplyRate: number = agg?.avgReplyRate ?? 0;

//   const domainsReady = domains.filter(
//     (d) => d.status === "ready" || d.status === "verified"
//   ).length;
//   const domainsTotal = domains.length;

//   // Recent campaigns from topCampaigns (already sorted by reply rate in BE)
//   const topCampaigns: Array<{
//     id: string;
//     name: string;
//     status: string;
//     replyRate?: number | null;
//   }> = (dashRaw as any)?.topCampaigns ?? dash.campaigns?.items ?? [];

//   // Chart data — map daily activity to Recharts shape
//   const chartData = (activity?.daily ?? []).map(
//     (d: { date: string; emails_sent: number; replies: number; meetings: number }) => ({
//       date:
//         d.date.length === 10
//           ? new Date(d.date).toLocaleDateString("en-US", { weekday: "short" })
//           : d.date,
//       Sent: d.emails_sent,
//       Replies: d.replies,
//     })
//   );

//   // Quota progress
//   const quotaPct = quota
//     ? Math.round((quota.emails_sent / Math.max(quota.daily_quota, 1)) * 100)
//     : 0;

//   // ── Loading skeleton ──────────────────────────────────────────────────────
//   if (dashLoading) {
//     return (
//       <div className="space-y-6 p-6">
//         <Skeleton className="h-8 w-48" />
//         <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
//           {Array.from({ length: 6 }).map((_, i) => (
//             <Skeleton key={i} className="h-24 rounded-xl" />
//           ))}
//         </div>
//         <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
//           <Skeleton className="h-56 rounded-xl" />
//           <Skeleton className="h-56 rounded-xl" />
//         </div>
//         <Skeleton className="h-40 rounded-xl" />
//       </div>
//     );
//   }

//   // ── Error state ───────────────────────────────────────────────────────────
//   if (dashError) {
//     return (
//       <ErrorState
//         title="Dashboard failed to load"
//         description={
//           (dashErr as { message?: string })?.message ??
//           "Could not reach the backend. Check your connection."
//         }
//         onRetry={refetchDash}
//       />
//     );
//   }

//   /* ════════════════════════════════════════════════════════════════════════ */
//   /*  Render                                                                  */
//   /* ════════════════════════════════════════════════════════════════════════ */

//   return (
//     <div className="space-y-6">
//       <PageHeader
//         title={`Welcome back${dash.user_name ? `, ${dash.user_name.split(" ")[0]}` : ""}`}
//         description="Your outreach command center"
//       />

//       {/* ── D-1: LLM Warning Banner ───────────────────────────────────────── */}
//       {!hasActiveLlm && (
//         <Card className="border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800">
//           <CardContent className="p-4 flex items-center gap-4">
//             <AlertCircle className="h-5 w-5 text-amber-600 shrink-0" />
//             <div className="flex-1">
//               <p className="font-medium text-sm text-amber-900 dark:text-amber-200">
//                 No LLM configured yet
//               </p>
//               <p className="text-xs text-amber-700 dark:text-amber-400">
//                 Connect an AI model to start generating personalized outreach emails.
//               </p>
//             </div>
//             <Button
//               size="sm"
//               onClick={() => navigate("/setup/llm-models")}
//               className="shrink-0"
//             >
//               <Plus className="h-4 w-4 mr-1" />
//               Configure LLM
//             </Button>
//           </CardContent>
//         </Card>
//       )}

//       {/* ── D-2: 6 Stat Cards ─────────────────────────────────────────────── */}
//       <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
//         {[
//           {
//             label: "Total Prospects",
//             value: totalProspects.toLocaleString(),
//             icon: <Users className="h-4 w-4" />,
//             colorCls: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40",
//           },
//           {
//             label: "Active Campaigns",
//             value: activeCampaigns.toLocaleString(),
//             icon: <PlayCircle className="h-4 w-4" />,
//             colorCls: "text-blue-600 bg-blue-50 dark:bg-blue-950/40",
//           },
//           {
//             label: "Emails Generated",
//             value: emailsGenerated.toLocaleString(),
//             icon: <Mail className="h-4 w-4" />,
//             colorCls: "text-violet-600 bg-violet-50 dark:bg-violet-950/40",
//           },
//           {
//             label: "Avg Open Rate",
//             value: fmtPct(avgOpenRate),
//             icon: <Eye className="h-4 w-4" />,
//             colorCls: "text-amber-600 bg-amber-50 dark:bg-amber-950/40",
//           },
//           {
//             label: "Avg Reply Rate",
//             value: fmtPct(avgReplyRate),
//             icon: <MessageSquare className="h-4 w-4" />,
//             colorCls: "text-rose-600 bg-rose-50 dark:bg-rose-950/40",
//           },
//           {
//             label: "Domains Ready",
//             value: `${domainsReady}/${domainsTotal}`,
//             icon: <Globe className="h-4 w-4" />,
//             colorCls: "text-teal-600 bg-teal-50 dark:bg-teal-950/40",
//           },
//         ].map((s) => (
//           <Card key={s.label}>
//             <CardContent className="p-4">
//               <div className="flex items-center gap-3">
//                 <div className={cn("p-2 rounded-lg", s.colorCls)}>{s.icon}</div>
//                 <div>
//                   <p className="text-2xl font-bold leading-tight">{s.value}</p>
//                   <p className="text-xs text-muted-foreground">{s.label}</p>
//                 </div>
//               </div>
//             </CardContent>
//           </Card>
//         ))}
//       </div>

//       {/* ── Personal activity stats (existing 4 cards) ───────────────────── */}
//       <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
//         <StatCard
//           label="Emails sent (7d)"
//           value={(activity?.emails_sent_7d ?? 0).toLocaleString()}
//           icon={<Send className="h-4 w-4" />}
//         />
//         <StatCard
//           label="Replies (7d)"
//           value={(activity?.replies_received_7d ?? 0).toLocaleString()}
//           icon={<Reply className="h-4 w-4" />}
//         />
//         <StatCard
//           label="Meetings booked (7d)"
//           value={(activity?.meetings_booked_7d ?? 0).toLocaleString()}
//           icon={<CalendarCheck className="h-4 w-4" />}
//         />
//         <StatCard
//           label="Pipeline value"
//           value={formatCurrency(dash.pipeline_value ?? 0)}
//           icon={<TrendingUp className="h-4 w-4" />}
//         />
//       </div>

//       {/* ── Middle row: Quick Actions + Recent Campaigns ──────────────────── */}
//       <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

//         {/* D-3: Quick Actions */}
//         <Card>
//           <CardHeader className="pb-3">
//             <CardTitle className="text-base">Quick Actions</CardTitle>
//             <CardDescription>Jump to any part of the platform</CardDescription>
//           </CardHeader>
//           <CardContent>
//             <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
//               {QUICK_ACTIONS.map((action) => {
//                 const Icon = action.icon;
//                 return (
//                   <button
//                     key={action.label}
//                     onClick={() => navigate(action.path)}
//                     className="flex flex-col items-center gap-1.5 p-2.5 rounded-lg border border-border hover:bg-accent transition-colors text-center"
//                   >
//                     <Icon className="h-4 w-4 text-muted-foreground" />
//                     <span className="text-xs leading-tight">{action.label}</span>
//                   </button>
//                 );
//               })}
//             </div>
//           </CardContent>
//         </Card>

//         {/* D-4: Recent Campaigns */}
//         <Card>
//           <CardHeader className="pb-3">
//             <CardTitle className="text-base">Recent Campaigns</CardTitle>
//             <CardDescription>Top 5 by reply rate</CardDescription>
//           </CardHeader>
//           <CardContent>
//             {topCampaigns.length === 0 ? (
//               <div className="py-8 text-center">
//                 <p className="text-sm text-muted-foreground">
//                   No campaigns yet.{" "}
//                   <button
//                     onClick={() => navigate("/outreach/campaigns")}
//                     className="text-primary underline underline-offset-2"
//                   >
//                     Create your first campaign
//                   </button>
//                 </p>
//               </div>
//             ) : (
//               <div className="space-y-0">
//                 {topCampaigns.slice(0, 5).map((c) => (
//                   <div
//                     key={c.id}
//                     className="flex items-center justify-between py-2.5 border-b border-border last:border-0"
//                   >
//                     <div className="min-w-0 flex-1">
//                       <p className="text-sm font-medium truncate">{c.name}</p>
//                       <Badge
//                         variant={statusVariant(c.status)}
//                         className="text-[10px] h-4 mt-0.5"
//                       >
//                         {c.status}
//                       </Badge>
//                     </div>
//                     <div className="text-right ml-3 shrink-0">
//                       <p className="text-sm font-medium">
//                         {c.replyRate != null ? fmtPct(c.replyRate) : "—"}
//                       </p>
//                       <p className="text-xs text-muted-foreground">reply rate</p>
//                     </div>
//                   </div>
//                 ))}
//               </div>
//             )}
//             <div className="mt-3 pt-3 border-t border-border">
//               <Button
//                 variant="outline"
//                 size="sm"
//                 className="w-full"
//                 onClick={() => navigate("/outreach/campaigns")}
//               >
//                 View all campaigns
//                 <ChevronRight className="h-3 w-3 ml-1" />
//               </Button>
//             </div>
//           </CardContent>
//         </Card>
//       </div>

//       {/* ── Activity chart + Email quota row ─────────────────────────────── */}
//       <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
//         {/* Recharts activity chart (existing) */}
//         <Card className="lg:col-span-2">
//           <CardHeader className="pb-3">
//             <CardTitle className="text-base">7-day activity</CardTitle>
//             <CardDescription>Emails sent vs replies</CardDescription>
//           </CardHeader>
//           <CardContent>
//             {chartData.length === 0 ? (
//               <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
//                 No activity data yet
//               </div>
//             ) : (
//               <ResponsiveContainer width="100%" height={200}>
//                 <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
//                   <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
//                   <XAxis
//                     dataKey="date"
//                     tick={{ fontSize: 11 }}
//                     tickLine={false}
//                     axisLine={false}
//                   />
//                   <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
//                   <Tooltip />
//                   <Bar dataKey="Sent" fill="#6366f1" radius={[3, 3, 0, 0]} />
//                   <Bar dataKey="Replies" fill="#10b981" radius={[3, 3, 0, 0]} />
//                 </BarChart>
//               </ResponsiveContainer>
//             )}
//           </CardContent>
//         </Card>

//         {/* Email quota card (existing) */}
//         <Card>
//           <CardHeader className="pb-3">
//             <CardTitle className="text-base flex items-center gap-2">
//               <Mail className="h-4 w-4" />
//               Email quota today
//             </CardTitle>
//           </CardHeader>
//           <CardContent className="space-y-3">
//             {quota ? (
//               <>
//                 {quota.is_throttled && (
//                   <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 dark:bg-amber-950/30 p-2 rounded-md">
//                     <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
//                     Sending throttled
//                     {quota.throttled_until &&
//                       ` until ${formatDate(quota.throttled_until)}`}
//                   </div>
//                 )}
//                 <div className="flex justify-between text-sm">
//                   <span className="text-muted-foreground">Sent today</span>
//                   <span className="font-medium">
//                     {quota.emails_sent.toLocaleString()} /{" "}
//                     {quota.daily_quota.toLocaleString()}
//                   </span>
//                 </div>
//                 <Progress
//                   value={quotaPct}
//                   className={cn(
//                     "h-2",
//                     quotaPct >= 90
//                       ? "[&>div]:bg-rose-500"
//                       : quotaPct >= 70
//                       ? "[&>div]:bg-amber-500"
//                       : "[&>div]:bg-primary"
//                   )}
//                 />
//                 <p className="text-xs text-muted-foreground">
//                   {quota.remaining.toLocaleString()} remaining •{" "}
//                   {quota.emails_bounced} bounced • {quota.complaints} complaints
//                 </p>
//               </>
//             ) : (
//               <p className="text-sm text-muted-foreground">No quota data</p>
//             )}
//           </CardContent>
//         </Card>
//       </div>

//       {/* ── Onboarding checklist (existing) ──────────────────────────────── */}
//       {checklist && !checklist.all_done && (
//         <Card>
//           <CardHeader className="pb-3">
//             <CardTitle className="text-base flex items-center justify-between">
//               <span>Getting started</span>
//               <span className="text-sm font-normal text-muted-foreground">
//                 {checklist.completed}/{checklist.total} complete
//               </span>
//             </CardTitle>
//             <Progress
//               value={Math.round((checklist.completed / checklist.total) * 100)}
//               className="h-1.5 mt-1"
//             />
//           </CardHeader>
//           <CardContent>
//             <div className="space-y-2">
//               {checklist.items
//                 .sort((a, b) => a.order - b.order)
//                 .map((item) => (
//                   <div
//                     key={item.key}
//                     className={cn(
//                       "flex items-start gap-3 p-2.5 rounded-lg transition-colors",
//                       item.done ? "opacity-50" : "hover:bg-accent cursor-pointer"
//                     )}
//                     onClick={() => !item.done && navigate(item.link)}
//                   >
//                     <div
//                       className={cn(
//                         "mt-0.5 h-4 w-4 rounded-full border-2 shrink-0 flex items-center justify-center",
//                         item.done
//                           ? "border-primary bg-primary"
//                           : "border-muted-foreground"
//                       )}
//                     >
//                       {item.done && (
//                         <svg className="h-2.5 w-2.5 text-primary-foreground" viewBox="0 0 10 10" fill="none">
//                           <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
//                         </svg>
//                       )}
//                     </div>
//                     <div>
//                       <p className="text-sm font-medium">{item.label}</p>
//                       <p className="text-xs text-muted-foreground">{item.description}</p>
//                     </div>
//                   </div>
//                 ))}
//             </div>
//           </CardContent>
//         </Card>
//       )}

//       {/* ── My Campaigns table (existing) ────────────────────────────────── */}
//       <Card>
//         <CardHeader className="pb-3">
//           <CardTitle className="text-base flex items-center justify-between">
//             <span>My campaigns</span>
//             <Badge variant="secondary">{dash.campaigns?.active_count ?? 0} active</Badge>
//           </CardTitle>
//         </CardHeader>
//         <CardContent className="p-0">
//           {!dash.campaigns?.items?.length ? (
//             <EmptyState
//               title="No campaigns yet"
//               description="Create your first campaign to start sending outreach."
//               action={
//                 <Button size="sm" onClick={() => navigate("/outreach/campaigns")}>
//                   Create campaign
//                 </Button>
//               }
//             />
//           ) : (
//             <Table>
//               <TableHeader>
//                 <TableRow>
//                   <TableHead>Name</TableHead>
//                   <TableHead>Status</TableHead>
//                   <TableHead className="text-right">Prospects</TableHead>
//                   <TableHead />
//                 </TableRow>
//               </TableHeader>
//               <TableBody>
//                 {dash.campaigns.items.map((c) => (
//                   <TableRow key={c.id}>
//                     <TableCell className="font-medium">{c.name}</TableCell>
//                     <TableCell>
//                       <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
//                     </TableCell>
//                     <TableCell className="text-right">
//                       {c.prospect_count?.toLocaleString() ?? "—"}
//                     </TableCell>
//                     <TableCell className="w-8">
//                       <Button
//                         variant="ghost"
//                         size="icon"
//                         className="h-7 w-7"
//                         onClick={() => navigate(`/outreach/campaigns/${c.id}`)}
//                       >
//                         <ChevronRight className="h-4 w-4" />
//                       </Button>
//                     </TableCell>
//                   </TableRow>
//                 ))}
//               </TableBody>
//             </Table>
//           )}
//         </CardContent>
//       </Card>

//       {/* ── Sender identities (existing) ─────────────────────────────────── */}
//       {dash.sender_identities && (
//         <Card>
//           <CardHeader className="pb-3">
//             <CardTitle className="text-base flex items-center gap-2">
//               <Users2 className="h-4 w-4" />
//               Sender identity
//             </CardTitle>
//           </CardHeader>
//           <CardContent>
//             <p className="text-sm">
//               <span className="text-muted-foreground">Default: </span>
//               <span className="font-medium font-mono text-sm">
//                 {dash.sender_identities.default_email ?? "—"}
//               </span>
//             </p>
//             <p className="text-xs text-muted-foreground mt-1">
//               {dash.sender_identities.total} identit
//               {dash.sender_identities.total === 1 ? "y" : "ies"} configured
//             </p>
//             <Button
//               variant="outline"
//               size="sm"
//               className="mt-3"
//               onClick={() => navigate("/setup/sender-identities")}
//             >
//               Manage identities
//             </Button>
//           </CardContent>
//         </Card>
//       )}

//       {/* ── D-5: 10-Step AI Outreach Workflow Guide ───────────────────────── */}
//       <Card>
//         <CardHeader className="pb-3">
//           <CardTitle className="text-base">AI Outreach Workflow</CardTitle>
//           <CardDescription>
//             Follow these 10 steps from setup to closed-won deals
//           </CardDescription>
//         </CardHeader>
//         <CardContent>
//           <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
//             {WORKFLOW_STEPS.map((s) => (
//               <button
//                 key={s.step}
//                 onClick={() => navigate(s.path)}
//                 className="flex items-start gap-3 p-3 rounded-lg border border-border hover:bg-accent transition-colors text-left"
//               >
//                 <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
//                   {s.step}
//                 </div>
//                 <div>
//                   <p className="text-sm font-medium">{s.title}</p>
//                   <p className="text-xs text-muted-foreground">{s.desc}</p>
//                 </div>
//               </button>
//             ))}
//           </div>
//         </CardContent>
//       </Card>
//     </div>
//   );
// }

/**
 * UserDashboardPage.tsx — personal dashboard for the logged-in user.
 *
 * Mounted at `/` inside <AppLayout>. Fetches:
 *   - GET /api/v1/dashboard?user_id=me  → DashboardResponse (aggregation + topCampaigns)
 *   - GET /api/v1/users/me/email-quota  → EmailQuota (today's send quota)
 *   - GET /api/v1/llm-configs           → LlmConfig[] (LLM warning banner)
 *   - GET /api/v1/domains               → Domain[] (Domains Ready stat)
 *   - GET /api/v1/onboarding/checklist  → ChecklistData (onboarding progress)
 *
 * Gap fixes applied (D-1 through D-6 from gap analysis):
 *   D-1  "No LLM configured" amber warning banner with Configure LLM CTA
 *   D-2  6 stat cards: Total Prospects, Active Campaigns, Emails Generated,
 *        Avg Open Rate, Avg Reply Rate, Domains Ready — sourced from real API
 *   D-3  17-item Quick Actions grid navigating to all major pages
 *   D-4  Recent Campaigns card (top 5 by reply rate, from topCampaigns)
 *   D-5  10-step AI Outreach Workflow guide (numbered, clickable)
 *   D-6  useNavigate() wires all navigation actions
 *
 * All existing functionality preserved:
 *   - 4 personal stat cards (emails sent 7d, replies, meetings, pipeline value)
 *   - Email quota card with progress bar + throttle warning
 *   - My campaigns list (active count + top 5)
 *   - Sender identities card
 *   - 7-day activity bar chart (Recharts)
 *   - Onboarding checklist
 */
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertCircle,
  BarChart3,
  Bot,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  ChevronRight,
  FileText,
  Globe,
  Inbox,
  Kanban,
  Layers,
  Lightbulb,
  Link2,
  Linkedin,
  Mail,
  Megaphone,
  MessageSquare,
  Eye,
  PlayCircle,
  Plus,
  Reply,
  Rocket,
  Send,
  ShieldAlert,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  Users2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  http,
  managerDashboardApi,
  senderIdentityApi,
} from "@/services/apiClient";
import { ErrorState } from "@/components/ui/error-state";
import type { UserDashboard } from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { cn, formatCurrency, formatDate } from "@/lib/utils";

/* ── Local types ─────────────────────────────────────────────────────────── */

interface ChecklistItem {
  key: string;
  label: string;
  description: string;
  link: string;
  order: number;
  done: boolean;
}

interface ChecklistData {
  items: ChecklistItem[];
  completed: number;
  total: number;
  all_done: boolean;
}

interface LlmConfig {
  id: string;
  name: string;
  isActive: boolean;
  isDefault: boolean;
}

interface DomainSummary {
  id: string;
  domain: string;
  status: string;
}

/* ── Mock fallback data (used only if API returns nothing usable) ─────────── */

const MOCK_DASHBOARD: UserDashboard = {
  user_id: "me",
  user_name: "Dev Rep",
  campaigns: {
    active_count: 3,
    items: [
      { id: "c1", name: "Q1 SaaS Founder Outreach", status: "Active", prospect_count: 248 },
      { id: "c2", name: "Series B VP Eng — Competitor Switch", status: "Active", prospect_count: 134 },
      { id: "c3", name: "DTC Operator Roadshow", status: "Paused", prospect_count: 92 },
      { id: "c4", name: "Healthcare CISO Refresh", status: "Active", prospect_count: 76 },
      { id: "c5", name: "Fintech Compliance Leaders", status: "Draft", prospect_count: 0 },
    ],
  },
  email_quota: {
    date: new Date().toISOString().slice(0, 10),
    emails_sent: 412,
    daily_quota: 1000,
    remaining: 588,
    emails_bounced: 8,
    complaints: 0,
    is_throttled: false,
    throttled_until: null,
  },
  sender_identities: {
    total: 2,
    default_email: "dev.rep@outrena.io",
  },
  recent_activity: {
    emails_sent_7d: 2840,
    replies_received_7d: 218,
    meetings_booked_7d: 14,
    daily: [
      { date: "Mon", emails_sent: 320, replies: 28, meetings: 1 },
      { date: "Tue", emails_sent: 412, replies: 33, meetings: 2 },
      { date: "Wed", emails_sent: 380, replies: 29, meetings: 1 },
      { date: "Thu", emails_sent: 502, replies: 41, meetings: 3 },
      { date: "Fri", emails_sent: 478, replies: 36, meetings: 2 },
      { date: "Sat", emails_sent: 396, replies: 26, meetings: 2 },
      { date: "Sun", emails_sent: 352, replies: 25, meetings: 3 },
    ],
  },
  prospects_contacted: 842,
  pipeline_value: 412_500,
};

/* ── Quick Actions definition ────────────────────────────────────────────── */

const QUICK_ACTIONS = [
  { label: "Add LLM Model",     path: "/setup/llm-models",            icon: Bot },
  { label: "Manage Prompts",    path: "/setup/prompts",               icon: FileText },
  { label: "Create ICP",        path: "/prospecting/icp-profiles",    icon: Target },
  { label: "Add Prospect",      path: "/prospects",                   icon: Users },
  { label: "Integrations",      path: "/setup/integrations",          icon: Link2 },
  { label: "Run Autopilot",     path: "/prospecting/autopilot",       icon: Rocket },
  { label: "Campaigns",         path: "/outreach/campaigns",          icon: Megaphone },
  { label: "Generate Email",    path: "/outreach/email-studio",       icon: Sparkles },
  { label: "Build Sequence",    path: "/outreach/sequences",          icon: Layers },
  { label: "Setup Domain",      path: "/setup/domains",               icon: Globe },
  { label: "Analytics",         path: "/optimize/analytics",          icon: BarChart3 },
  { label: "Templates",         path: "/outreach/templates",          icon: BookOpen },
  { label: "Track Deals",       path: "/pipeline/deals",              icon: Kanban },
  { label: "Reply Inbox",       path: "/outreach/reply-inbox",        icon: Inbox },
  { label: "LinkedIn Hub",      path: "/prospecting/linkedin",        icon: Linkedin },
  { label: "Content Ideas",     path: "/optimize/content-ideas",      icon: Lightbulb },
  { label: "Weekly Digest",     path: "/optimize/weekly-digest",      icon: CalendarDays },
] as const;

/* ── Workflow steps definition ───────────────────────────────────────────── */

const WORKFLOW_STEPS = [
  { step: 1,  title: "Connect AI Model",       desc: "Set up your LLM provider",         path: "/setup/llm-models" },
  { step: 2,  title: "Setup Domain",           desc: "Configure sending domain & DNS",   path: "/setup/domains" },
  { step: 3,  title: "Configure Integrations", desc: "Connect MailBridge & data tools",  path: "/setup/integrations" },
  { step: 4,  title: "Define ICP",             desc: "Create ideal customer profile",    path: "/prospecting/icp-profiles" },
  { step: 5,  title: "Import Prospects",       desc: "Add & enrich your leads",          path: "/prospects" },
  { step: 6,  title: "Run Autopilot",          desc: "AI GTM pipeline — 60 seconds",    path: "/prospecting/autopilot" },
  { step: 7,  title: "Generate Emails",        desc: "AI copywriting & QA scoring",      path: "/outreach/email-studio" },
  { step: 8,  title: "Build Sequence",         desc: "Multi-touch cadence",              path: "/outreach/sequences" },
  { step: 9,  title: "Track Replies",          desc: "Manage inbox & AI drafts",         path: "/outreach/reply-inbox" },
  { step: 10, title: "Close Deals",            desc: "Pipeline & revenue tracking",      path: "/pipeline/deals" },
] as const;

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  const s = status.toLowerCase();
  if (s === "active") return "default";
  if (s === "paused") return "secondary";
  if (s === "draft") return "outline";
  return "secondary";
}

function fmtPct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

/* ══════════════════════════════════════════════════════════════════════════ */
/*  Component                                                                */
/* ══════════════════════════════════════════════════════════════════════════ */

export function UserDashboardPage() {
  const { initialized, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Gate every query: wait until AuthProvider has resolved + user is authenticated.
  // Without this gate, API calls fire before the Bearer token is set → 400/401 loop.
  const queryEnabled = initialized && isAuthenticated;

  // ── Personal dashboard (aggregation + topCampaigns + timeSeries) ─────────
  const {
    data: dashRaw,
    isLoading: dashLoading,
    isError: dashError,
    error: dashErr,
    refetch: refetchDash,
  } = useQuery({
    queryKey: ["dashboard", "me"],
    queryFn: () => managerDashboardApi.mine(),
    enabled: queryEnabled,
    retry: (failureCount, err) => {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401 || status === 403) return false;
      return failureCount < 1;
    },
  });

  // ── Email quota (today's send stats) ─────────────────────────────────────
  const { data: quotaData } = useQuery({
    queryKey: ["email-quota", "me"],
    queryFn: () => senderIdentityApi.myQuota(),
    enabled: queryEnabled,
  });

  // ── LLM configs (for the warning banner) ─────────────────────────────────
  const { data: llmConfigs = [] } = useQuery<LlmConfig[]>({
    queryKey: ["llm-configs"],
    queryFn: () => http.get<LlmConfig[]>("/api/v1/llm-configs"),
    enabled: queryEnabled,
  });

  // ── Domains (for "Domains Ready" stat card) ───────────────────────────────
  const { data: domains = [] } = useQuery<DomainSummary[]>({
    queryKey: ["domains"],
    queryFn: () => http.get<DomainSummary[]>("/api/v1/domains"),
    enabled: queryEnabled,
  });

  // ── Recent Campaigns (real data — top 5 by reply_rate desc) ─────────────
  const { data: campaignsRaw } = useQuery<unknown>({
    queryKey: ["campaigns", "dashboard-top5"],
    queryFn: () => http.get<unknown>("/api/v1/campaigns?limit=5&sort=reply_rate&order=desc"),
    enabled: queryEnabled,
    staleTime: 60_000,
  });

  // ── Onboarding checklist ──────────────────────────────────────────────────
  const { data: checklist } = useQuery<ChecklistData>({
    queryKey: ["onboarding-checklist"],
    queryFn: () => http.get<ChecklistData>("/api/v1/onboarding/checklist"),
    enabled: queryEnabled,
  });

  // ── Resolve data (real or mock fallback) ──────────────────────────────────
  const dash: UserDashboard = (dashRaw as UserDashboard) ?? MOCK_DASHBOARD;
  const quota = quotaData ?? dash.email_quota;
  const activity = dash.recent_activity;

  // ── Derived values ────────────────────────────────────────────────────────

  // LLM warning: no active config
  const hasActiveLlm = llmConfigs.some((c) => c.isActive);

  // 6 stat cards — sourced from DashboardResponse.aggregation when available,
  // fall back to UserDashboard personal totals.
  const agg = (dashRaw as any)?.aggregation ?? null;

  const totalProspects: number =
    agg?.totalProspects ?? dash.prospects_contacted ?? 0;
  const activeCampaigns: number =
    agg?.activeCampaigns ?? dash.campaigns?.active_count ?? 0;
  const emailsGenerated: number =
    agg?.totalSequences ?? activity?.emails_sent_7d ?? 0;
  const avgOpenRate: number = agg?.avgOpenRate ?? 0;
  const avgReplyRate: number = agg?.avgReplyRate ?? 0;

  const domainsReady = domains.filter(
    (d) => d.status === "ready" || d.status === "verified"
  ).length;
  const domainsTotal = domains.length;

  // Recent campaigns — prefer real API data, fall back to dashboard aggregate
  const realCampaigns: Array<{ id: string; name: string; status: string; replyRate?: number | null }> = (() => {
    if (!campaignsRaw) return [];
    const items = Array.isArray(campaignsRaw)
      ? campaignsRaw
      : ((campaignsRaw as { items?: unknown[] }).items ?? []);
    return (items as Array<{ id: string; name: string; status: string; reply_rate?: number | null; replyRate?: number | null }>)
      .slice(0, 5)
      .map((c) => ({ id: c.id, name: c.name, status: c.status, replyRate: c.replyRate ?? c.reply_rate ?? null }));
  })();
  const topCampaigns: Array<{
    id: string;
    name: string;
    status: string;
    replyRate?: number | null;
  }> = (dashRaw as any)?.topCampaigns ?? (realCampaigns.length > 0 ? realCampaigns : []);

  // Chart data — map daily activity to Recharts shape
  const chartData = (activity?.daily ?? []).map(
    (d: { date: string; emails_sent: number; replies: number; meetings: number }) => ({
      date:
        d.date.length === 10
          ? new Date(d.date).toLocaleDateString("en-US", { weekday: "short" })
          : d.date,
      Sent: d.emails_sent,
      Replies: d.replies,
    })
  );

  // Quota progress
  const quotaPct = quota
    ? Math.round((quota.emails_sent / Math.max(quota.daily_quota, 1)) * 100)
    : 0;

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (dashLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-56 rounded-xl" />
          <Skeleton className="h-56 rounded-xl" />
        </div>
        <Skeleton className="h-40 rounded-xl" />
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────────────
  if (dashError) {
    return (
      <ErrorState
        title="Dashboard failed to load"
        description={
          (dashErr as { message?: string })?.message ??
          "Could not reach the backend. Check your connection."
        }
        onRetry={refetchDash}
      />
    );
  }

  /* ════════════════════════════════════════════════════════════════════════ */
  /*  Render                                                                  */
  /* ════════════════════════════════════════════════════════════════════════ */

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back${dash.user_name ? `, ${dash.user_name.split(" ")[0]}` : ""}`}
        description="Your outreach command center"
      />

      {/* ── D-1: LLM Warning Banner ───────────────────────────────────────── */}
      {!hasActiveLlm && (
        <Card className="border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-amber-600 shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-sm text-amber-900 dark:text-amber-200">
                No LLM configured yet
              </p>
              <p className="text-xs text-amber-700 dark:text-amber-400">
                Connect an AI model to start generating personalized outreach emails.
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => navigate("/setup/llm-models")}
              className="shrink-0"
            >
              <Plus className="h-4 w-4 mr-1" />
              Configure LLM
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── D-2: 6 Stat Cards ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {[
          {
            label: "Total Prospects",
            value: totalProspects.toLocaleString(),
            icon: <Users className="h-4 w-4" />,
            colorCls: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40",
          },
          {
            label: "Active Campaigns",
            value: activeCampaigns.toLocaleString(),
            icon: <PlayCircle className="h-4 w-4" />,
            colorCls: "text-blue-600 bg-blue-50 dark:bg-blue-950/40",
          },
          {
            label: "Emails Generated",
            value: emailsGenerated.toLocaleString(),
            icon: <Mail className="h-4 w-4" />,
            colorCls: "text-violet-600 bg-violet-50 dark:bg-violet-950/40",
          },
          {
            label: "Avg Open Rate",
            value: fmtPct(avgOpenRate),
            icon: <Eye className="h-4 w-4" />,
            colorCls: "text-amber-600 bg-amber-50 dark:bg-amber-950/40",
          },
          {
            label: "Avg Reply Rate",
            value: fmtPct(avgReplyRate),
            icon: <MessageSquare className="h-4 w-4" />,
            colorCls: "text-rose-600 bg-rose-50 dark:bg-rose-950/40",
          },
          {
            label: "Domains Ready",
            value: `${domainsReady}/${domainsTotal}`,
            icon: <Globe className="h-4 w-4" />,
            colorCls: "text-teal-600 bg-teal-50 dark:bg-teal-950/40",
          },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className={cn("p-2 rounded-lg", s.colorCls)}>{s.icon}</div>
                <div>
                  <p className="text-2xl font-bold leading-tight">{s.value}</p>
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Personal activity stats (existing 4 cards) ───────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard
          label="Emails sent (7d)"
          value={(activity?.emails_sent_7d ?? 0).toLocaleString()}
          icon={<Send className="h-4 w-4" />}
        />
        <StatCard
          label="Replies (7d)"
          value={(activity?.replies_received_7d ?? 0).toLocaleString()}
          icon={<Reply className="h-4 w-4" />}
        />
        <StatCard
          label="Meetings booked (7d)"
          value={(activity?.meetings_booked_7d ?? 0).toLocaleString()}
          icon={<CalendarCheck className="h-4 w-4" />}
        />
        <StatCard
          label="Pipeline value"
          value={formatCurrency(dash.pipeline_value ?? 0)}
          icon={<TrendingUp className="h-4 w-4" />}
        />
      </div>

      {/* ── Middle row: Quick Actions + Recent Campaigns ──────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* D-3: Quick Actions */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Quick Actions</CardTitle>
            <CardDescription>Jump to any part of the platform</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {QUICK_ACTIONS.map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.label}
                    onClick={() => navigate(action.path)}
                    className="flex flex-col items-center gap-1.5 p-2.5 rounded-lg border border-border hover:bg-accent transition-colors text-center"
                  >
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className="text-xs leading-tight">{action.label}</span>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* D-4: Recent Campaigns */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Recent Campaigns</CardTitle>
            <CardDescription>Top 5 by reply rate</CardDescription>
          </CardHeader>
          <CardContent>
            {topCampaigns.length === 0 ? (
              <div className="py-8 text-center">
                <p className="text-sm text-muted-foreground">
                  No campaigns yet.{" "}
                  <button
                    onClick={() => navigate("/outreach/campaigns")}
                    className="text-primary underline underline-offset-2"
                  >
                    Create your first campaign
                  </button>
                </p>
              </div>
            ) : (
              <div className="space-y-0">
                {topCampaigns.slice(0, 5).map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center justify-between py-2.5 border-b border-border last:border-0"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{c.name}</p>
                      <Badge
                        variant={statusVariant(c.status)}
                        className="text-[10px] h-4 mt-0.5"
                      >
                        {c.status}
                      </Badge>
                    </div>
                    <div className="text-right ml-3 shrink-0">
                      <p className="text-sm font-medium">
                        {c.replyRate != null ? fmtPct(c.replyRate) : "—"}
                      </p>
                      <p className="text-xs text-muted-foreground">reply rate</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-3 pt-3 border-t border-border">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => navigate("/outreach/campaigns")}
              >
                View all campaigns
                <ChevronRight className="h-3 w-3 ml-1" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Activity chart + Email quota row ─────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recharts activity chart (existing) */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">7-day activity</CardTitle>
            <CardDescription>Emails sent vs replies</CardDescription>
          </CardHeader>
          <CardContent>
            {chartData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
                No activity data yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Bar dataKey="Sent" fill="#6366f1" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Replies" fill="#10b981" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Email quota card (existing) */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Email quota today
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {quota ? (
              <>
                {quota.is_throttled && (
                  <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 dark:bg-amber-950/30 p-2 rounded-md">
                    <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
                    Sending throttled
                    {quota.throttled_until &&
                      ` until ${formatDate(quota.throttled_until)}`}
                  </div>
                )}
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Sent today</span>
                  <span className="font-medium">
                    {quota.emails_sent.toLocaleString()} /{" "}
                    {quota.daily_quota.toLocaleString()}
                  </span>
                </div>
                <Progress
                  value={quotaPct}
                  className={cn(
                    "h-2",
                    quotaPct >= 90
                      ? "[&>div]:bg-rose-500"
                      : quotaPct >= 70
                      ? "[&>div]:bg-amber-500"
                      : "[&>div]:bg-primary"
                  )}
                />
                <p className="text-xs text-muted-foreground">
                  {quota.remaining.toLocaleString()} remaining •{" "}
                  {quota.emails_bounced} bounced • {quota.complaints} complaints
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No quota data</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Onboarding checklist (existing) ──────────────────────────────── */}
      {checklist && !checklist.all_done && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center justify-between">
              <span>Getting started</span>
              <span className="text-sm font-normal text-muted-foreground">
                {checklist.completed}/{checklist.total} complete
              </span>
            </CardTitle>
            <Progress
              value={Math.round((checklist.completed / checklist.total) * 100)}
              className="h-1.5 mt-1"
            />
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {checklist.items
                .sort((a, b) => a.order - b.order)
                .map((item) => (
                  <div
                    key={item.key}
                    className={cn(
                      "flex items-start gap-3 p-2.5 rounded-lg transition-colors",
                      item.done ? "opacity-50" : "hover:bg-accent cursor-pointer"
                    )}
                    onClick={() => !item.done && navigate(item.link)}
                  >
                    <div
                      className={cn(
                        "mt-0.5 h-4 w-4 rounded-full border-2 shrink-0 flex items-center justify-center",
                        item.done
                          ? "border-primary bg-primary"
                          : "border-muted-foreground"
                      )}
                    >
                      {item.done && (
                        <svg className="h-2.5 w-2.5 text-primary-foreground" viewBox="0 0 10 10" fill="none">
                          <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="text-xs text-muted-foreground">{item.description}</p>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── My Campaigns table (existing) ────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center justify-between">
            <span>My campaigns</span>
            <Badge variant="secondary">{dash.campaigns?.active_count ?? 0} active</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!dash.campaigns?.items?.length ? (
            <EmptyState
              title="No campaigns yet"
              description="Create your first campaign to start sending outreach."
              action={
                <Button size="sm" onClick={() => navigate("/outreach/campaigns")}>
                  Create campaign
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Prospects</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {dash.campaigns.items.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {c.prospect_count?.toLocaleString() ?? "—"}
                    </TableCell>
                    <TableCell className="w-8">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => navigate(`/outreach/campaigns/${c.id}`)}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ── Sender identities (existing) ─────────────────────────────────── */}
      {dash.sender_identities && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Users2 className="h-4 w-4" />
              Sender identity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">
              <span className="text-muted-foreground">Default: </span>
              <span className="font-medium font-mono text-sm">
                {dash.sender_identities.default_email ?? "—"}
              </span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {dash.sender_identities.total} identit
              {dash.sender_identities.total === 1 ? "y" : "ies"} configured
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => navigate("/setup/sender-identities")}
            >
              Manage identities
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── D-5: 10-Step AI Outreach Workflow Guide ───────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">AI Outreach Workflow</CardTitle>
          <CardDescription>
            Follow these 10 steps from setup to closed-won deals
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {WORKFLOW_STEPS.map((s) => (
              <button
                key={s.step}
                onClick={() => navigate(s.path)}
                className="flex items-start gap-3 p-3 rounded-lg border border-border hover:bg-accent transition-colors text-left"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
                  {s.step}
                </div>
                <div>
                  <p className="text-sm font-medium">{s.title}</p>
                  <p className="text-xs text-muted-foreground">{s.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}