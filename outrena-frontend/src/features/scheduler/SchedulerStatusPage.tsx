// /**
//  * SchedulerStatusPage.tsx — Full rebuild with 3 new features:
//  *   Tab 1: Status        — existing scheduler health cards + recent runs
//  *   Tab 2: Campaigns     — sequences grouped by campaign, filterable
//  *   Tab 3: Skip Details  — per-sequence skip drill-down with reason breakdown
//  *   Tab 4: Daily Sent    — daily sent log per campaign
//  *
//  * New backend endpoints consumed:
//  *   GET /api/v1/scheduler/campaign-schedules
//  *   GET /api/v1/scheduler/skipped-details
//  *   GET /api/v1/scheduler/daily-sent
//  */
// import { useEffect, useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   Activity,
//   BarChart3,
//   Calendar,
//   CheckCircle2,
//   ChevronDown,
//   Clock,
//   FastForward,
//   Filter,
//   Loader2,
//   RefreshCw,
//   SkipForward,
//   X,
//   XCircle,
//   Zap,
// } from "lucide-react";
// import { toast } from "sonner";

// import { schedulerApi, http } from "@/services/apiClient";
// import { Badge } from "@/components/ui/badge";
// import { Button } from "@/components/ui/button";
// import {
//   Card,
//   CardContent,
//   CardDescription,
//   CardHeader,
//   CardTitle,
// } from "@/components/ui/card";
// import {
//   Dialog,
//   DialogClose,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
// } from "@/components/ui/dialog";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { PageHeader } from "@/components/ui/page-header";
// import { Skeleton } from "@/components/ui/skeleton";
// import {
//   Table,
//   TableBody,
//   TableCell,
//   TableHead,
//   TableHeader,
//   TableRow,
// } from "@/components/ui/table";
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// import { TooltipProvider } from "@/components/ui/tooltip";
// import { formatDateTime, timeAgo } from "@/lib/utils";

// const AUTO_REFRESH_MS = 10_000;

// // ── Types ────────────────────────────────────────────────────────────────────

// interface SchedulerRun {
//   id: string;
//   startedAt: string;
//   completedAt: string | null;
//   status: "running" | "completed" | "failed";
//   sent: number;
//   skipped: number;
//   durationMs: number | null;
//   error: string | null;
// }

// interface CampaignScheduleItem {
//   campaignId: string;
//   campaignName: string;
//   campaignStatus: string;
//   totalSequences: number;
//   scheduled: number;
//   sent: number;
//   skipped: number;
//   replied: number;
//   bounced: number;
//   failed: number;
//   nextSendAt: string | null;
// }

// interface SkipLogItem {
//   id: string;
//   runId: string | null;
//   sequenceId: string;
//   campaignId: string | null;
//   campaignName: string | null;
//   prospectId: string | null;
//   prospectEmail: string | null;
//   skipReason: string;
//   detail: string | null;
//   skippedAt: string;
// }

// interface SkipLogResponse {
//   items: SkipLogItem[];
//   total: number;
//   reasonBreakdown: Record<string, number>;
// }

// interface DailySentItem {
//   campaignId: string;
//   campaignName: string;
//   sentDate: string;
//   sentCount: number;
// }

// // ── Skip reason helpers ───────────────────────────────────────────────────────

// const SKIP_REASON_LABELS: Record<string, string> = {
//   no_email: "No Email",
//   suppressed: "Suppressed",
//   business_hours: "Outside Business Hours",
//   quota_exceeded: "Quota Exceeded",
//   no_mailbridge_config: "No MailBridge Config",
//   send_error: "Send Error",
//   warmup_cap: "Warmup Cap Reached",
// };

// const SKIP_REASON_COLORS: Record<string, string> = {
//   no_email: "bg-gray-100 text-gray-700",
//   suppressed: "bg-red-100 text-red-700",
//   business_hours: "bg-blue-100 text-blue-700",
//   quota_exceeded: "bg-orange-100 text-orange-700",
//   no_mailbridge_config: "bg-purple-100 text-purple-700",
//   send_error: "bg-rose-100 text-rose-700",
//   warmup_cap: "bg-amber-100 text-amber-700",
// };

// function SkipReasonBadge({ reason }: { reason: string }) {
//   const label = SKIP_REASON_LABELS[reason] ?? reason;
//   const color = SKIP_REASON_COLORS[reason] ?? "bg-gray-100 text-gray-700";
//   return (
//     <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${color}`}>
//       {label}
//     </span>
//   );
// }

// function CampaignStatusBadge({ status }: { status: string }) {
//   const map: Record<string, string> = {
//     active: "bg-emerald-100 text-emerald-700",
//     draft: "bg-gray-100 text-gray-600",
//     paused: "bg-amber-100 text-amber-700",
//     completed: "bg-blue-100 text-blue-700",
//   };
//   return (
//     <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${map[status] ?? "bg-gray-100 text-gray-600"}`}>
//       {status}
//     </span>
//   );
// }

// // ── Main page ─────────────────────────────────────────────────────────────────

// export function SchedulerStatusPage() {
//   const qc = useQueryClient();
//   const [tickOpen, setTickOpen] = useState(false);
//   const [triggerOpen, setTriggerOpen] = useState(false);
//   const [maxSend, setMaxSend] = useState(50);

//   // Campaign schedules filter state
//   const [campFilter, setCampFilter] = useState("");
//   const [campStatusFilter, setCampStatusFilter] = useState("");

//   // Skip details filter state
//   const [skipRunId, setSkipRunId] = useState("");
//   const [skipCampId, setSkipCampId] = useState("");
//   const [skipReasonFilter, setSkipReasonFilter] = useState("");
//   const [expandedSkipId, setExpandedSkipId] = useState<string | null>(null);

//   // Daily sent filter state
//   const [dailyCampId, setDailyCampId] = useState("");
//   const [dailySince, setDailySince] = useState("");
//   const [dailyUntil, setDailyUntil] = useState("");

//   // ── Queries ─────────────────────────────────────────────────────────────────

//   const { data: status, isLoading, isError, error, refetch } = useQuery({
//     queryKey: ["scheduler", "status"],
//     queryFn: () => schedulerApi.status(),
//     retry: false,
//   });

//   const { data: runs, isLoading: runsLoading } = useQuery<SchedulerRun[]>({
//     queryKey: ["scheduler", "runs"],
//     queryFn: () =>
//       schedulerApi.runs({ limit: 20 }).then((r) => r?.items ?? []).catch(() => []),
//     retry: false,
//   });

//   const { data: campSchedules, isLoading: campLoading, refetch: refetchCamps } = useQuery<{
//     items: CampaignScheduleItem[];
//     total: number;
//   }>({
//     queryKey: ["scheduler", "campaign-schedules", campFilter, campStatusFilter],
//     queryFn: () =>
//       schedulerApi.campaignSchedules({
//         campaign_id: campFilter || undefined,
//         status: campStatusFilter || undefined,
//         limit: 100,
//         offset: 0,
//       }),
//     retry: false,
//   });

//   const { data: skipData, isLoading: skipLoading, refetch: refetchSkips } = useQuery<SkipLogResponse>({
//     queryKey: ["scheduler", "skipped-details", skipRunId, skipCampId, skipReasonFilter],
//     queryFn: () =>
//       schedulerApi.skippedDetails({
//         run_id: skipRunId || undefined,
//         campaign_id: skipCampId || undefined,
//         skip_reason: skipReasonFilter || undefined,
//         limit: 100,
//         offset: 0,
//       }),
//     retry: false,
//   });

//   const { data: dailySentData, isLoading: dailyLoading, refetch: refetchDaily } = useQuery<{
//     items: DailySentItem[];
//     total: number;
//   }>({
//     queryKey: ["scheduler", "daily-sent", dailyCampId, dailySince, dailyUntil],
//     queryFn: () =>
//       schedulerApi.dailySent({
//         campaign_id: dailyCampId || undefined,
//         since: dailySince || undefined,
//         until: dailyUntil || undefined,
//         limit: 100,
//         offset: 0,
//       }),
//     retry: false,
//   });

//   // Shared campaign list for all dropdowns
//   const { data: campaignList } = useQuery<{ id: string; name: string; status: string }[]>({
//     queryKey: ["scheduler", "campaigns-list"],
//     queryFn: () =>
//       http.get<any>("/api/v1/campaigns").then((r) => {
//         const items: any[] = Array.isArray(r) ? r : r?.items ?? [];
//         return items.map((c: any) => ({ id: c.id, name: c.name, status: c.status ?? "draft" }));
//       }).catch(() => []),
//     retry: false,
//     staleTime: 60_000,
//   });

//   // Auto-refresh every 10s
//   useEffect(() => {
//     const id = window.setInterval(() => {
//       qc.invalidateQueries({ queryKey: ["scheduler", "status"] });
//       qc.invalidateQueries({ queryKey: ["scheduler", "runs"] });
//     }, AUTO_REFRESH_MS);
//     return () => window.clearInterval(id);
//   }, [qc]);

//   // ── Mutations ────────────────────────────────────────────────────────────────

//   const tickMut = useMutation({
//     mutationFn: (body: { tenantScoped: boolean; maxSend: number }) =>
//       schedulerApi.tick(body),
//     onSuccess: (res) => {
//       toast.success(
//         `Tick complete — sent ${res.sent}, skipped ${res.skipped} (${res.durationMs}ms)`,
//       );
//       qc.invalidateQueries({ queryKey: ["scheduler"] });
//       setTickOpen(false);
//     },
//     onError: () => toast.error("Failed to run scheduler tick"),
//   });

//   const triggerMut = useMutation({
//     mutationFn: () => schedulerApi.trigger(),
//     onSuccess: (res) => {
//       toast.success(res?.message ?? "Scheduler triggered", {
//         description: res?.runId ? `Run ID: ${res.runId}` : undefined,
//       });
//       qc.invalidateQueries({ queryKey: ["scheduler"] });
//       setTriggerOpen(false);
//     },
//     onError: () => toast.error("Failed to trigger scheduler"),
//   });

//   function handleTick() {
//     if (maxSend < 1 || maxSend > 1000) {
//       toast.error("maxSend must be between 1 and 1000");
//       return;
//     }
//     tickMut.mutate({ tenantScoped: true, maxSend });
//   }

//   // ── Render ────────────────────────────────────────────────────────────────────

//   return (
//     <TooltipProvider delayDuration={200}>
//       <div className="space-y-6">
//         <PageHeader
//           title="Scheduler"
//           description="Monitor and control the email sending scheduler. Auto-refreshes every 10 seconds."
//           actions={
//             <>
//               <Button variant="outline" size="sm" onClick={() => refetch()}>
//                 <RefreshCw className="h-4 w-4" />
//                 Refresh
//               </Button>
//               <Button
//                 variant="secondary"
//                 size="sm"
//                 onClick={() => setTriggerOpen(true)}
//               >
//                 <Zap className="h-4 w-4" />
//                 Trigger Now
//               </Button>
//               <Button size="sm" onClick={() => setTickOpen(true)}>
//                 <FastForward className="h-4 w-4" />
//                 Run Tick
//               </Button>
//             </>
//           }
//         />

//         <Tabs defaultValue="status" className="space-y-4">
//           <TabsList>
//             <TabsTrigger value="status" className="gap-2">
//               <Activity className="h-4 w-4" />
//               Status
//             </TabsTrigger>
//             <TabsTrigger value="campaigns" className="gap-2">
//               <BarChart3 className="h-4 w-4" />
//               Campaign Schedules
//             </TabsTrigger>
//             <TabsTrigger value="skipped" className="gap-2">
//               <SkipForward className="h-4 w-4" />
//               Skip Details
//             </TabsTrigger>
//             <TabsTrigger value="daily" className="gap-2">
//               <Calendar className="h-4 w-4" />
//               Daily Sent
//             </TabsTrigger>
//           </TabsList>

//           {/* ── Tab 1: Status ──────────────────────────────────────────────── */}
//           <TabsContent value="status" className="space-y-6">
//             {isError ? (
//               <Card>
//                 <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
//                   <XCircle className="h-8 w-8 text-destructive" />
//                   <p className="text-sm font-medium">Failed to load scheduler status</p>
//                   <p className="text-xs text-muted-foreground">
//                     {(error as Error)?.message ?? "Unknown error"}
//                   </p>
//                   <Button variant="outline" size="sm" onClick={() => refetch()}>
//                     Retry
//                   </Button>
//                 </CardContent>
//               </Card>
//             ) : isLoading || !status ? (
//               <Skeleton className="h-48 w-full" />
//             ) : (
//               <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
//                 {/* Status card */}
//                 <Card className="lg:col-span-2">
//                   <CardHeader>
//                     <CardTitle className="flex items-center gap-2">
//                       <Activity className="h-5 w-5" />
//                       Scheduler Engine
//                       <Badge variant={status.isRunning ? "success" : "outline"}>
//                         {status.isRunning ? "Running" : "Idle"}
//                       </Badge>
//                     </CardTitle>
//                     <CardDescription>
//                       Last updated {timeAgo(status.updatedAt)} ({formatDateTime(status.updatedAt)})
//                     </CardDescription>
//                   </CardHeader>
//                   <CardContent className="grid grid-cols-2 gap-6 text-sm sm:grid-cols-3">
//                     <div>
//                       <p className="text-xs uppercase tracking-wide text-muted-foreground">Last Tick</p>
//                       <p className="mt-1 flex items-center gap-1.5">
//                         <Clock className="h-3.5 w-3.5 text-muted-foreground" />
//                         {status.lastTickAt ? formatDateTime(status.lastTickAt) : "Never"}
//                       </p>
//                     </div>
//                     <div>
//                       <p className="text-xs uppercase tracking-wide text-muted-foreground">Next Tick</p>
//                       <p className="mt-1 flex items-center gap-1.5">
//                         <Clock className="h-3.5 w-3.5 text-muted-foreground" />
//                         {status.nextTickAt ? formatDateTime(status.nextTickAt) : "—"}
//                       </p>
//                     </div>
//                     <div>
//                       <p className="text-xs uppercase tracking-wide text-muted-foreground">Updated</p>
//                       <p className="mt-1">{formatDateTime(status.updatedAt)}</p>
//                     </div>
//                     <div>
//                       <p className="text-xs uppercase tracking-wide text-muted-foreground">Sent (last tick)</p>
//                       <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-600">
//                         {status.sentSinceLastTick}
//                       </p>
//                     </div>
//                     <div>
//                       <p className="text-xs uppercase tracking-wide text-muted-foreground">Skipped (last tick)</p>
//                       <p className="mt-1 text-2xl font-semibold tabular-nums text-amber-600">
//                         {status.skippedSinceLastTick}
//                       </p>
//                     </div>
//                   </CardContent>
//                 </Card>

//                 {/* Action cards */}
//                 <div className="space-y-4">
//                   <Card>
//                     <CardHeader className="pb-3">
//                       <CardTitle className="text-sm">Manual Tick</CardTitle>
//                       <CardDescription className="text-xs">
//                         Synchronously process due sequences for this tenant.
//                       </CardDescription>
//                     </CardHeader>
//                     <CardContent>
//                       <Button className="w-full" size="sm" onClick={() => setTickOpen(true)}>
//                         <FastForward className="h-4 w-4" />
//                         Run Tick Now
//                       </Button>
//                     </CardContent>
//                   </Card>

//                   <Card>
//                     <CardHeader className="pb-3">
//                       <CardTitle className="flex items-center gap-2 text-sm">
//                         <Zap className="h-4 w-4" />
//                         Trigger Pipeline
//                       </CardTitle>
//                       <CardDescription className="text-xs">
//                         Trigger all due sequences without waiting for next tick.
//                       </CardDescription>
//                     </CardHeader>
//                     <CardContent>
//                       <Button
//                         className="w-full"
//                         size="sm"
//                         variant="secondary"
//                         onClick={() => setTriggerOpen(true)}
//                         disabled={triggerMut.isPending}
//                       >
//                         {triggerMut.isPending ? (
//                           <Loader2 className="h-4 w-4 animate-spin" />
//                         ) : (
//                           <Zap className="h-4 w-4" />
//                         )}
//                         Trigger Now
//                       </Button>
//                     </CardContent>
//                   </Card>
//                 </div>
//               </div>
//             )}

//             {/* Recent runs table */}
//             <Card>
//               <CardHeader>
//                 <CardTitle className="text-base">Recent Scheduler Runs</CardTitle>
//                 <CardDescription>Latest execution history.</CardDescription>
//               </CardHeader>
//               <CardContent className="p-0">
//                 {runsLoading ? (
//                   <div className="space-y-2 p-4">
//                     {[1, 2, 3].map((i) => (
//                       <Skeleton key={i} className="h-10 w-full" />
//                     ))}
//                   </div>
//                 ) : !runs || runs.length === 0 ? (
//                   <div className="p-8 text-center text-sm text-muted-foreground">
//                     No scheduler runs recorded yet.
//                   </div>
//                 ) : (
//                   <Table>
//                     <TableHeader>
//                       <TableRow>
//                         <TableHead className="w-36">Started</TableHead>
//                         <TableHead className="w-36">Completed</TableHead>
//                         <TableHead className="w-28">Status</TableHead>
//                         <TableHead className="w-20 text-right">Sent</TableHead>
//                         <TableHead className="w-20 text-right">Skipped</TableHead>
//                         <TableHead className="w-24">Duration</TableHead>
//                         <TableHead>Error</TableHead>
//                       </TableRow>
//                     </TableHeader>
//                     <TableBody>
//                       {runs.map((run) => (
//                         <TableRow key={run.id}>
//                           <TableCell className="text-xs">
//                             {formatDateTime(run.startedAt)}
//                           </TableCell>
//                           <TableCell className="text-xs">
//                             {run.completedAt ? formatDateTime(run.completedAt) : "—"}
//                           </TableCell>
//                           <TableCell>
//                             <Badge
//                               variant={
//                                 run.status === "completed"
//                                   ? "success"
//                                   : run.status === "failed"
//                                   ? "destructive"
//                                   : "secondary"
//                               }
//                               className="text-[10px]"
//                             >
//                               {run.status === "running" && (
//                                 <Loader2 className="mr-1 h-3 w-3 animate-spin" />
//                               )}
//                               {run.status === "completed" && (
//                                 <CheckCircle2 className="mr-1 h-3 w-3" />
//                               )}
//                               {run.status === "failed" && (
//                                 <XCircle className="mr-1 h-3 w-3" />
//                               )}
//                               {run.status}
//                             </Badge>
//                           </TableCell>
//                           <TableCell className="text-right tabular-nums text-sm text-emerald-600">
//                             {run.sent}
//                           </TableCell>
//                           <TableCell className="text-right tabular-nums text-sm text-amber-600">
//                             {run.skipped}
//                           </TableCell>
//                           <TableCell className="text-xs text-muted-foreground">
//                             {run.durationMs != null ? `${run.durationMs}ms` : "—"}
//                           </TableCell>
//                           <TableCell className="max-w-[200px] truncate text-xs text-destructive">
//                             {run.error ?? "—"}
//                           </TableCell>
//                         </TableRow>
//                       ))}
//                     </TableBody>
//                   </Table>
//                 )}
//               </CardContent>
//             </Card>
//           </TabsContent>

//           {/* ── Tab 2: Campaign Schedules ──────────────────────────────────── */}
//           <TabsContent value="campaigns" className="space-y-4">
//             {/* Filters */}
//             <Card>
//               <CardContent className="flex flex-wrap items-end gap-3 p-4">
//                 <div className="flex-1 space-y-1 min-w-[200px]">
//                   <Label className="text-xs">Campaign</Label>
//                   <select
//                     className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
//                     value={campFilter}
//                     onChange={(e) => setCampFilter(e.target.value)}
//                   >
//                     <option value="">All campaigns</option>
//                     {(campaignList ?? []).map((c) => (
//                       <option key={c.id} value={c.id}>
//                         {c.name}
//                       </option>
//                     ))}
//                   </select>
//                 </div>
//                 <div className="w-44 space-y-1">
//                   <Label className="text-xs">Status</Label>
//                   <select
//                     className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
//                     value={campStatusFilter}
//                     onChange={(e) => setCampStatusFilter(e.target.value)}
//                   >
//                     <option value="">All statuses</option>
//                     <option value="draft">Draft</option>
//                     <option value="active">Active</option>
//                     <option value="paused">Paused</option>
//                     <option value="completed">Completed</option>
//                   </select>
//                 </div>
//                 <div className="flex gap-2">
//                   <Button size="sm" variant="outline" onClick={() => refetchCamps()}>
//                     <Filter className="h-3.5 w-3.5" />
//                     Apply
//                   </Button>
//                   {(campFilter || campStatusFilter) && (
//                     <Button
//                       size="sm"
//                       variant="ghost"
//                       onClick={() => {
//                         setCampFilter("");
//                         setCampStatusFilter("");
//                       }}
//                     >
//                       <X className="h-3.5 w-3.5" />
//                       Clear
//                     </Button>
//                   )}
//                 </div>
//               </CardContent>
//             </Card>

//             <Card>
//               <CardHeader>
//                 <div className="flex items-center justify-between">
//                   <CardTitle className="text-base">Campaign Sequences</CardTitle>
//                   {campSchedules && (
//                     <span className="text-sm text-muted-foreground">
//                       {campSchedules.total} campaign{campSchedules.total !== 1 ? "s" : ""}
//                     </span>
//                   )}
//                 </div>
//                 <CardDescription>
//                   Sequence counts per campaign. Scheduled = queued to send; Sent = delivered.
//                 </CardDescription>
//               </CardHeader>
//               <CardContent className="p-0">
//                 {campLoading ? (
//                   <div className="space-y-2 p-4">
//                     {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
//                   </div>
//                 ) : !campSchedules || campSchedules.items.length === 0 ? (
//                   <div className="p-8 text-center text-sm text-muted-foreground">
//                     No campaigns found. Adjust filters or create a campaign first.
//                   </div>
//                 ) : (
//                   <Table>
//                     <TableHeader>
//                       <TableRow>
//                         <TableHead>Campaign</TableHead>
//                         <TableHead className="w-24">Status</TableHead>
//                         <TableHead className="w-20 text-right">Total</TableHead>
//                         <TableHead className="w-24 text-right">Scheduled</TableHead>
//                         <TableHead className="w-20 text-right">Sent</TableHead>
//                         <TableHead className="w-20 text-right">Replied</TableHead>
//                         <TableHead className="w-20 text-right">Bounced</TableHead>
//                         <TableHead className="w-20 text-right">Failed</TableHead>
//                         <TableHead className="w-40">Next Send</TableHead>
//                       </TableRow>
//                     </TableHeader>
//                     <TableBody>
//                       {campSchedules.items.map((item) => (
//                         <TableRow key={item.campaignId}>
//                           <TableCell>
//                             <div className="font-medium text-sm">{item.campaignName}</div>
//                             <div className="text-xs text-muted-foreground font-mono">
//                               {item.campaignId.slice(-8)}
//                             </div>
//                           </TableCell>
//                           <TableCell>
//                             <CampaignStatusBadge status={item.campaignStatus} />
//                           </TableCell>
//                           <TableCell className="text-right tabular-nums text-sm">
//                             {item.totalSequences}
//                           </TableCell>
//                           <TableCell className="text-right">
//                             {item.scheduled > 0 ? (
//                               <span className="tabular-nums text-sm font-semibold text-blue-600">
//                                 {item.scheduled}
//                               </span>
//                             ) : (
//                               <span className="tabular-nums text-sm text-muted-foreground">0</span>
//                             )}
//                           </TableCell>
//                           <TableCell className="text-right tabular-nums text-sm text-emerald-600">
//                             {item.sent}
//                           </TableCell>
//                           <TableCell className="text-right tabular-nums text-sm text-purple-600">
//                             {item.replied}
//                           </TableCell>
//                           <TableCell className="text-right tabular-nums text-sm text-rose-600">
//                             {item.bounced}
//                           </TableCell>
//                           <TableCell className="text-right tabular-nums text-sm text-muted-foreground">
//                             {item.failed}
//                           </TableCell>
//                           <TableCell className="text-xs text-muted-foreground">
//                             {item.nextSendAt ? formatDateTime(item.nextSendAt) : "—"}
//                           </TableCell>
//                         </TableRow>
//                       ))}
//                     </TableBody>
//                   </Table>
//                 )}
//               </CardContent>
//             </Card>
//           </TabsContent>

//           {/* ── Tab 3: Skip Details ────────────────────────────────────────── */}
//           <TabsContent value="skipped" className="space-y-4">
//             {/* Reason breakdown summary */}
//             {skipData && Object.keys(skipData.reasonBreakdown).length > 0 && (
//               <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
//                 {Object.entries(skipData.reasonBreakdown)
//                   .sort((a, b) => b[1] - a[1])
//                   .map(([reason, count]) => (
//                     <Card
//                       key={reason}
//                       className={`cursor-pointer transition-shadow hover:shadow-md ${
//                         skipReasonFilter === reason ? "ring-2 ring-primary" : ""
//                       }`}
//                       onClick={() =>
//                         setSkipReasonFilter(skipReasonFilter === reason ? "" : reason)
//                       }
//                     >
//                       <CardContent className="p-4">
//                         <p className="text-2xl font-bold tabular-nums">{count}</p>
//                         <SkipReasonBadge reason={reason} />
//                         {skipReasonFilter === reason && (
//                           <p className="mt-1 text-[10px] text-muted-foreground">
//                             Click to clear filter
//                           </p>
//                         )}
//                       </CardContent>
//                     </Card>
//                   ))}
//               </div>
//             )}

//             {/* Filters */}
//             <Card>
//               <CardContent className="flex flex-wrap items-end gap-3 p-4">
//                 <div className="flex-1 min-w-[160px] space-y-1">
//                   <Label className="text-xs">Run ID</Label>
//                   <Input
//                     placeholder="Filter by run ID…"
//                     value={skipRunId}
//                     onChange={(e) => setSkipRunId(e.target.value)}
//                     className="h-8 text-sm"
//                   />
//                 </div>
//                 <div className="flex-1 min-w-[160px] space-y-1">
//                   <Label className="text-xs">Campaign</Label>
//                   <select
//                     className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
//                     value={skipCampId}
//                     onChange={(e) => setSkipCampId(e.target.value)}
//                   >
//                     <option value="">All campaigns</option>
//                     {(campaignList ?? []).map((c) => (
//                       <option key={c.id} value={c.id}>
//                         {c.name}
//                       </option>
//                     ))}
//                   </select>
//                 </div>
//                 <div className="w-52 space-y-1">
//                   <Label className="text-xs">Skip Reason</Label>
//                   <select
//                     className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
//                     value={skipReasonFilter}
//                     onChange={(e) => setSkipReasonFilter(e.target.value)}
//                   >
//                     <option value="">All reasons</option>
//                     {Object.entries(SKIP_REASON_LABELS).map(([value, label]) => (
//                       <option key={value} value={value}>
//                         {label}
//                       </option>
//                     ))}
//                   </select>
//                 </div>
//                 <div className="flex gap-2">
//                   <Button size="sm" variant="outline" onClick={() => refetchSkips()}>
//                     <Filter className="h-3.5 w-3.5" />
//                     Apply
//                   </Button>
//                   {(skipRunId || skipCampId || skipReasonFilter) && (
//                     <Button
//                       size="sm"
//                       variant="ghost"
//                       onClick={() => {
//                         setSkipRunId("");
//                         setSkipCampId("");
//                         setSkipReasonFilter("");
//                       }}
//                     >
//                       <X className="h-3.5 w-3.5" />
//                       Clear
//                     </Button>
//                   )}
//                 </div>
//               </CardContent>
//             </Card>

//             <Card>
//               <CardHeader>
//                 <div className="flex items-center justify-between">
//                   <CardTitle className="text-base">Skipped Sequences</CardTitle>
//                   {skipData && (
//                     <span className="text-sm text-muted-foreground">
//                       {skipData.total} skip event{skipData.total !== 1 ? "s" : ""}
//                     </span>
//                   )}
//                 </div>
//                 <CardDescription>
//                   Click a reason card above to filter by that reason. Click a row to see detail.
//                   {!skipData || skipData.total === 0 && skipData.reasonBreakdown && Object.keys(skipData.reasonBreakdown).length === 0
//                     ? " Skip logging requires migration 0022 to be applied."
//                     : ""}
//                 </CardDescription>
//               </CardHeader>
//               <CardContent className="p-0">
//                 {skipLoading ? (
//                   <div className="space-y-2 p-4">
//                     {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
//                   </div>
//                 ) : !skipData || skipData.items.length === 0 ? (
//                   <div className="p-8 text-center space-y-2">
//                     <SkipForward className="h-8 w-8 mx-auto text-muted-foreground/40" />
//                     <p className="text-sm text-muted-foreground">
//                       No skip events found.
//                     </p>
//                     <p className="text-xs text-muted-foreground">
//                       Skip details are recorded from migration 0022 onwards. Run{" "}
//                       <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
//                         alembic upgrade head
//                       </code>{" "}
//                       to enable skip logging.
//                     </p>
//                   </div>
//                 ) : (
//                   <Table>
//                     <TableHeader>
//                       <TableRow>
//                         <TableHead className="w-8"></TableHead>
//                         <TableHead>Campaign</TableHead>
//                         <TableHead>Prospect Email</TableHead>
//                         <TableHead>Skip Reason</TableHead>
//                         <TableHead className="w-36">Skipped At</TableHead>
//                         <TableHead>Run ID</TableHead>
//                       </TableRow>
//                     </TableHeader>
//                     <TableBody>
//                       {skipData.items.map((item) => (
//                         <>
//                           <TableRow
//                             key={item.id}
//                             className="cursor-pointer"
//                             onClick={() =>
//                               setExpandedSkipId(expandedSkipId === item.id ? null : item.id)
//                             }
//                           >
//                             <TableCell className="text-muted-foreground">
//                               <ChevronDown
//                                 className={`h-4 w-4 transition-transform ${
//                                   expandedSkipId === item.id ? "rotate-180" : ""
//                                 }`}
//                               />
//                             </TableCell>
//                             <TableCell>
//                               <span className="text-sm">
//                                 {item.campaignName ?? "—"}
//                               </span>
//                             </TableCell>
//                             <TableCell className="text-sm font-mono">
//                               {item.prospectEmail ?? "—"}
//                             </TableCell>
//                             <TableCell>
//                               <SkipReasonBadge reason={item.skipReason} />
//                             </TableCell>
//                             <TableCell className="text-xs text-muted-foreground">
//                               {formatDateTime(item.skippedAt)}
//                             </TableCell>
//                             <TableCell className="font-mono text-xs text-muted-foreground">
//                               {item.runId ? item.runId.slice(-8) : "manual"}
//                             </TableCell>
//                           </TableRow>
//                           {expandedSkipId === item.id && (
//                             <TableRow key={`${item.id}-detail`} className="bg-muted/30">
//                               <TableCell />
//                               <TableCell colSpan={5} className="py-3">
//                                 <div className="space-y-1 text-xs">
//                                   <div className="flex gap-6">
//                                     <div>
//                                       <span className="font-medium text-muted-foreground">Sequence ID: </span>
//                                       <span className="font-mono">{item.sequenceId}</span>
//                                     </div>
//                                     {item.prospectId && (
//                                       <div>
//                                         <span className="font-medium text-muted-foreground">Prospect ID: </span>
//                                         <span className="font-mono">{item.prospectId}</span>
//                                       </div>
//                                     )}
//                                     {item.runId && (
//                                       <div>
//                                         <span className="font-medium text-muted-foreground">Run ID: </span>
//                                         <span className="font-mono">{item.runId}</span>
//                                       </div>
//                                     )}
//                                   </div>
//                                   {item.detail && (
//                                     <div>
//                                       <span className="font-medium text-muted-foreground">Detail: </span>
//                                       <span className="text-destructive">{item.detail}</span>
//                                     </div>
//                                   )}
//                                 </div>
//                               </TableCell>
//                             </TableRow>
//                           )}
//                         </>
//                       ))}
//                     </TableBody>
//                   </Table>
//                 )}
//               </CardContent>
//             </Card>
//           </TabsContent>

//           {/* ── Tab 4: Daily Sent ──────────────────────────────────────────── */}
//           <TabsContent value="daily" className="space-y-4">
//             {/* Filters */}
//             <Card>
//               <CardContent className="flex flex-wrap items-end gap-3 p-4">
//                 <div className="flex-1 min-w-[180px] space-y-1">
//                   <Label className="text-xs">Campaign</Label>
//                   <select
//                     className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
//                     value={dailyCampId}
//                     onChange={(e) => setDailyCampId(e.target.value)}
//                   >
//                     <option value="">All campaigns</option>
//                     {(campaignList ?? []).map((c) => (
//                       <option key={c.id} value={c.id}>
//                         {c.name}
//                       </option>
//                     ))}
//                   </select>
//                 </div>
//                 <div className="w-36 space-y-1">
//                   <Label className="text-xs">From Date</Label>
//                   <Input
//                     type="date"
//                     value={dailySince}
//                     onChange={(e) => setDailySince(e.target.value)}
//                     className="h-8 text-sm"
//                   />
//                 </div>
//                 <div className="w-36 space-y-1">
//                   <Label className="text-xs">To Date</Label>
//                   <Input
//                     type="date"
//                     value={dailyUntil}
//                     onChange={(e) => setDailyUntil(e.target.value)}
//                     className="h-8 text-sm"
//                   />
//                 </div>
//                 <div className="flex gap-2">
//                   <Button size="sm" variant="outline" onClick={() => refetchDaily()}>
//                     <Filter className="h-3.5 w-3.5" />
//                     Apply
//                   </Button>
//                   {(dailyCampId || dailySince || dailyUntil) && (
//                     <Button
//                       size="sm"
//                       variant="ghost"
//                       onClick={() => {
//                         setDailyCampId("");
//                         setDailySince("");
//                         setDailyUntil("");
//                       }}
//                     >
//                       <X className="h-3.5 w-3.5" />
//                       Clear
//                     </Button>
//                   )}
//                 </div>
//               </CardContent>
//             </Card>

//             <Card>
//               <CardHeader>
//                 <div className="flex items-center justify-between">
//                   <CardTitle className="text-base">Daily Sent Log</CardTitle>
//                   {dailySentData && (
//                     <span className="text-sm text-muted-foreground">
//                       {dailySentData.total} entries
//                     </span>
//                   )}
//                 </div>
//                 <CardDescription>
//                   Emails sent per campaign per day. Updated in real-time as ticks run.
//                 </CardDescription>
//               </CardHeader>
//               <CardContent className="p-0">
//                 {dailyLoading ? (
//                   <div className="space-y-2 p-4">
//                     {[1, 2, 3, 4, 5].map((i) => (
//                       <Skeleton key={i} className="h-10 w-full" />
//                     ))}
//                   </div>
//                 ) : !dailySentData || dailySentData.items.length === 0 ? (
//                   <div className="p-8 text-center space-y-2">
//                     <Calendar className="h-8 w-8 mx-auto text-muted-foreground/40" />
//                     <p className="text-sm text-muted-foreground">
//                       No daily sent data found.
//                     </p>
//                     <p className="text-xs text-muted-foreground">
//                       Daily logs populate as emails are sent. If you've sent emails recently,
//                       run{" "}
//                       <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
//                         alembic upgrade head
//                       </code>{" "}
//                       to enable the aggregation table.
//                     </p>
//                   </div>
//                 ) : (
//                   <Table>
//                     <TableHeader>
//                       <TableRow>
//                         <TableHead>Date</TableHead>
//                         <TableHead>Campaign</TableHead>
//                         <TableHead className="w-28 text-right">Emails Sent</TableHead>
//                       </TableRow>
//                     </TableHeader>
//                     <TableBody>
//                       {dailySentData.items.map((item, i) => (
//                         <TableRow key={`${item.campaignId}-${item.sentDate}-${i}`}>
//                           <TableCell className="font-mono text-sm">
//                             {item.sentDate}
//                           </TableCell>
//                           <TableCell>
//                             <div className="text-sm font-medium">{item.campaignName}</div>
//                             <div className="font-mono text-xs text-muted-foreground">
//                               {item.campaignId.slice(-8)}
//                             </div>
//                           </TableCell>
//                           <TableCell className="text-right">
//                             <span className="text-lg font-semibold tabular-nums text-emerald-600">
//                               {item.sentCount}
//                             </span>
//                           </TableCell>
//                         </TableRow>
//                       ))}
//                     </TableBody>
//                   </Table>
//                 )}
//               </CardContent>
//             </Card>
//           </TabsContent>
//         </Tabs>

//         {/* ── Trigger Now dialog ──────────────────────────────────────────── */}
//         <Dialog open={triggerOpen} onOpenChange={setTriggerOpen}>
//           <DialogClose onClose={() => setTriggerOpen(false)} />
//           <DialogHeader>
//             <DialogTitle>Trigger Scheduler Now?</DialogTitle>
//             <DialogDescription>
//               Immediately triggers the scheduler pipeline to process all due sequences,
//               regardless of the next scheduled tick.
//             </DialogDescription>
//           </DialogHeader>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setTriggerOpen(false)}>
//               Cancel
//             </Button>
//             <Button onClick={() => triggerMut.mutate()} disabled={triggerMut.isPending}>
//               {triggerMut.isPending ? (
//                 <>
//                   <Loader2 className="h-4 w-4 animate-spin" />
//                   Triggering…
//                 </>
//               ) : (
//                 <>
//                   <Zap className="h-4 w-4" />
//                   Trigger Now
//                 </>
//               )}
//             </Button>
//           </DialogFooter>
//         </Dialog>

//         {/* ── Manual tick dialog ─────────────────────────────────────────── */}
//         <Dialog open={tickOpen} onOpenChange={setTickOpen}>
//           <DialogClose onClose={() => setTickOpen(false)} />
//           <DialogHeader>
//             <DialogTitle>Run Scheduler Tick?</DialogTitle>
//             <DialogDescription>
//               Synchronously processes due sequences for the current tenant. Avoid during peak load.
//             </DialogDescription>
//           </DialogHeader>
//           <div className="space-y-3 py-2">
//             <div className="space-y-2">
//               <Label htmlFor="tick-max">Max sends per tick</Label>
//               <Input
//                 id="tick-max"
//                 type="number"
//                 min={1}
//                 max={1000}
//                 value={maxSend}
//                 onChange={(e) => setMaxSend(Number(e.target.value))}
//               />
//             </div>
//           </div>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setTickOpen(false)}>
//               Cancel
//             </Button>
//             <Button onClick={handleTick} disabled={tickMut.isPending}>
//               {tickMut.isPending ? "Running…" : "Run Tick"}
//             </Button>
//           </DialogFooter>
//         </Dialog>
//       </div>
//     </TooltipProvider>
//   );
// }

/**
 * SchedulerStatusPage.tsx — Full rebuild with 3 new features:
 *   Tab 1: Status        — existing scheduler health cards + recent runs
 *   Tab 2: Campaigns     — sequences grouped by campaign, filterable
 *   Tab 3: Skip Details  — per-sequence skip drill-down with reason breakdown
 *   Tab 4: Daily Sent    — daily sent log per campaign
 *
 * New backend endpoints consumed:
 *   GET /api/v1/scheduler/campaign-schedules
 *   GET /api/v1/scheduler/skipped-details
 *   GET /api/v1/scheduler/daily-sent
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Calendar,
  CheckCircle2,
  ChevronDown,
  Clock,
  FastForward,
  Filter,
  Loader2,
  RefreshCw,
  Save,
  Settings,
  SkipForward,
  ToggleLeft,
  ToggleRight,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { schedulerApi, http } from "@/services/apiClient";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Switch } from "@/components/ui/switch";
import { formatDateTime, timeAgo } from "@/lib/utils";

const AUTO_REFRESH_MS = 10_000;

// ── Types ────────────────────────────────────────────────────────────────────

interface SchedulerRun {
  id: string;
  startedAt: string;
  completedAt: string | null;
  status: "running" | "completed" | "failed";
  sent: number;
  skipped: number;
  durationMs: number | null;
  error: string | null;
}

interface CampaignScheduleItem {
  campaignId: string;
  campaignName: string;
  campaignStatus: string;
  totalSequences: number;
  scheduled: number;
  sent: number;
  skipped: number;
  replied: number;
  bounced: number;
  failed: number;
  nextSendAt: string | null;
}

interface SkipLogItem {
  id: string;
  runId: string | null;
  sequenceId: string;
  campaignId: string | null;
  campaignName: string | null;
  prospectId: string | null;
  prospectEmail: string | null;
  skipReason: string;
  detail: string | null;
  skippedAt: string;
}

interface SkipLogResponse {
  items: SkipLogItem[];
  total: number;
  reasonBreakdown: Record<string, number>;
}

interface DailySentItem {
  campaignId: string;
  campaignName: string;
  sentDate: string;
  sentCount: number;
}

// ── Skip reason helpers ───────────────────────────────────────────────────────

const SKIP_REASON_LABELS: Record<string, string> = {
  no_email: "No Email",
  suppressed: "Suppressed",
  business_hours: "Outside Business Hours",
  quota_exceeded: "Quota Exceeded",
  no_mailbridge_config: "No MailBridge Config",
  send_error: "Send Error",
  warmup_cap: "Warmup Cap Reached",
};

const SKIP_REASON_COLORS: Record<string, string> = {
  no_email: "bg-gray-100 text-gray-700",
  suppressed: "bg-red-100 text-red-700",
  business_hours: "bg-blue-100 text-blue-700",
  quota_exceeded: "bg-orange-100 text-orange-700",
  no_mailbridge_config: "bg-purple-100 text-purple-700",
  send_error: "bg-rose-100 text-rose-700",
  warmup_cap: "bg-amber-100 text-amber-700",
};

function SkipReasonBadge({ reason }: { reason: string }) {
  const label = SKIP_REASON_LABELS[reason] ?? reason;
  const color = SKIP_REASON_COLORS[reason] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${color}`}>
      {label}
    </span>
  );
}

function CampaignStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: "bg-emerald-100 text-emerald-700",
    draft: "bg-gray-100 text-gray-600",
    paused: "bg-amber-100 text-amber-700",
    completed: "bg-blue-100 text-blue-700",
  };
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${map[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function SchedulerStatusPage() {
  const qc = useQueryClient();
  const [tickOpen, setTickOpen] = useState(false);
  const [triggerOpen, setTriggerOpen] = useState(false);
  const [maxSend, setMaxSend] = useState(50);

  // Campaign schedules filter state
  const [campFilter, setCampFilter] = useState("");
  const [campStatusFilter, setCampStatusFilter] = useState("");

  // Skip details filter state
  const [skipRunId, setSkipRunId] = useState("");
  const [skipCampId, setSkipCampId] = useState("");
  const [skipReasonFilter, setSkipReasonFilter] = useState("");
  const [expandedSkipId, setExpandedSkipId] = useState<string | null>(null);

  // Daily sent filter state
  const [dailyCampId, setDailyCampId] = useState("");
  const [dailySince, setDailySince] = useState("");
  const [dailyUntil, setDailyUntil] = useState("");

  // Scheduler settings state
  const [settingsEnabled, setSettingsEnabled] = useState<boolean | null>(null);
  const [settingsInterval, setSettingsInterval] = useState<string>("");
  const [settingsSaving, setSettingsSaving] = useState(false);

  // ── Queries ─────────────────────────────────────────────────────────────────

  const { data: status, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["scheduler", "status"],
    queryFn: () => schedulerApi.status(),
    retry: false,
  });

  const { data: runs, isLoading: runsLoading } = useQuery<SchedulerRun[]>({
    queryKey: ["scheduler", "runs"],
    queryFn: () =>
      schedulerApi.runs({ limit: 20 }).then((r) => r?.items ?? []).catch(() => []),
    retry: false,
  });

  const { data: campSchedules, isLoading: campLoading, refetch: refetchCamps } = useQuery<{
    items: CampaignScheduleItem[];
    total: number;
  }>({
    queryKey: ["scheduler", "campaign-schedules", campFilter, campStatusFilter],
    queryFn: () =>
      schedulerApi.campaignSchedules({
        campaign_id: campFilter || undefined,
        status: campStatusFilter || undefined,
        limit: 100,
        offset: 0,
      }),
    retry: false,
  });

  const { data: skipData, isLoading: skipLoading, refetch: refetchSkips } = useQuery<SkipLogResponse>({
    queryKey: ["scheduler", "skipped-details", skipRunId, skipCampId, skipReasonFilter],
    queryFn: () =>
      schedulerApi.skippedDetails({
        run_id: skipRunId || undefined,
        campaign_id: skipCampId || undefined,
        skip_reason: skipReasonFilter || undefined,
        limit: 100,
        offset: 0,
      }),
    retry: false,
  });

  const { data: dailySentData, isLoading: dailyLoading, refetch: refetchDaily } = useQuery<{
    items: DailySentItem[];
    total: number;
  }>({
    queryKey: ["scheduler", "daily-sent", dailyCampId, dailySince, dailyUntil],
    queryFn: () =>
      schedulerApi.dailySent({
        campaign_id: dailyCampId || undefined,
        since: dailySince || undefined,
        until: dailyUntil || undefined,
        limit: 100,
        offset: 0,
      }),
    retry: false,
  });

  // Shared campaign list for all dropdowns
  const { data: campaignList } = useQuery<{ id: string; name: string; status: string }[]>({
    queryKey: ["scheduler", "campaigns-list"],
    queryFn: () =>
      http.get<any>("/api/v1/campaigns").then((r) => {
        const items: any[] = Array.isArray(r) ? r : r?.items ?? [];
        return items.map((c: any) => ({ id: c.id, name: c.name, status: c.status ?? "draft" }));
      }).catch(() => []),
    retry: false,
    staleTime: 60_000,
  });

  // Scheduler settings from SystemParameter table
  const { data: schedulerParams, refetch: refetchSettings } = useQuery<
    { key: string; value: string; label: string; description: string; valueType: string; unit?: string }[]
  >({
    queryKey: ["scheduler", "settings-params"],
    queryFn: () =>
      http
        .get<{ key: string; value: string; label: string; description: string; valueType: string; unit?: string }[]>(
          "/api/v1/system-params?category=scheduler"
        )
        .catch(() => []),
    retry: false,
    staleTime: 30_000,
  });

  // Sync settings state when params load
  useEffect(() => {
    if (!schedulerParams) return;
    const enabledParam = schedulerParams.find((p) => p.key === "scheduler.enabled");
    const intervalParam = schedulerParams.find((p) => p.key === "scheduler.tick_interval_minutes");
    if (enabledParam && settingsEnabled === null) {
      setSettingsEnabled(enabledParam.value.toLowerCase() !== "false");
    }
    if (intervalParam && settingsInterval === "") {
      setSettingsInterval(intervalParam.value);
    }
  }, [schedulerParams]);

  async function saveSchedulerSettings() {
    setSettingsSaving(true);
    try {
      await Promise.all([
        http.put("/api/v1/system-params/scheduler.enabled", {
          value: settingsEnabled ? "true" : "false",
        }),
        http.put("/api/v1/system-params/scheduler.tick_interval_minutes", {
          value: settingsInterval,
        }),
      ]);
      await refetchSettings();
      toast.success("Scheduler settings saved successfully");
    } catch {
      toast.error("Failed to save scheduler settings");
    } finally {
      setSettingsSaving(false);
    }
  }

  // Auto-refresh every 10s
  useEffect(() => {
    const id = window.setInterval(() => {
      qc.invalidateQueries({ queryKey: ["scheduler", "status"] });
      qc.invalidateQueries({ queryKey: ["scheduler", "runs"] });
    }, AUTO_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [qc]);

  // ── Mutations ────────────────────────────────────────────────────────────────

  const tickMut = useMutation({
    mutationFn: (body: { tenantScoped: boolean; maxSend: number }) =>
      schedulerApi.tick(body),
    onSuccess: (res) => {
      toast.success(
        `Tick complete — sent ${res.sent}, skipped ${res.skipped} (${res.durationMs}ms)`,
      );
      qc.invalidateQueries({ queryKey: ["scheduler"] });
      setTickOpen(false);
    },
    onError: () => toast.error("Failed to run scheduler tick"),
  });

  const triggerMut = useMutation({
    mutationFn: () => schedulerApi.trigger(),
    onSuccess: (res) => {
      toast.success(res?.message ?? "Scheduler triggered", {
        description: res?.runId ? `Run ID: ${res.runId}` : undefined,
      });
      qc.invalidateQueries({ queryKey: ["scheduler"] });
      setTriggerOpen(false);
    },
    onError: () => toast.error("Failed to trigger scheduler"),
  });

  function handleTick() {
    if (maxSend < 1 || maxSend > 1000) {
      toast.error("maxSend must be between 1 and 1000");
      return;
    }
    tickMut.mutate({ tenantScoped: true, maxSend });
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="Scheduler"
          description="Monitor and control the email sending scheduler. Auto-refreshes every 10 seconds."
          actions={
            <>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setTriggerOpen(true)}
              >
                <Zap className="h-4 w-4" />
                Trigger Now
              </Button>
              <Button size="sm" onClick={() => setTickOpen(true)}>
                <FastForward className="h-4 w-4" />
                Run Tick
              </Button>
            </>
          }
        />

        <Tabs defaultValue="status" className="space-y-4">
          <TabsList>
            <TabsTrigger value="status" className="gap-2">
              <Activity className="h-4 w-4" />
              Status
            </TabsTrigger>
            <TabsTrigger value="campaigns" className="gap-2">
              <BarChart3 className="h-4 w-4" />
              Campaign Schedules
            </TabsTrigger>
            <TabsTrigger value="skipped" className="gap-2">
              <SkipForward className="h-4 w-4" />
              Skip Details
            </TabsTrigger>
            <TabsTrigger value="daily" className="gap-2">
              <Calendar className="h-4 w-4" />
              Daily Sent
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-2">
              <Settings className="h-4 w-4" />
              Settings
            </TabsTrigger>
          </TabsList>

          {/* ── Tab 1: Status ──────────────────────────────────────────────── */}
          <TabsContent value="status" className="space-y-6">
            {isError ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                  <XCircle className="h-8 w-8 text-destructive" />
                  <p className="text-sm font-medium">Failed to load scheduler status</p>
                  <p className="text-xs text-muted-foreground">
                    {(error as Error)?.message ?? "Unknown error"}
                  </p>
                  <Button variant="outline" size="sm" onClick={() => refetch()}>
                    Retry
                  </Button>
                </CardContent>
              </Card>
            ) : isLoading || !status ? (
              <Skeleton className="h-48 w-full" />
            ) : (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                {/* Status card */}
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="h-5 w-5" />
                      Scheduler Engine
                      <Badge variant={status.isRunning ? "success" : "outline"}>
                        {status.isRunning ? "Running" : "Idle"}
                      </Badge>
                    </CardTitle>
                    <CardDescription>
                      Last updated {timeAgo(status.updatedAt)} ({formatDateTime(status.updatedAt)})
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid grid-cols-2 gap-6 text-sm sm:grid-cols-3">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Last Tick</p>
                      <p className="mt-1 flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                        {status.lastTickAt ? formatDateTime(status.lastTickAt) : "Never"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Next Tick</p>
                      <p className="mt-1 flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                        {status.nextTickAt ? formatDateTime(status.nextTickAt) : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Updated</p>
                      <p className="mt-1">{formatDateTime(status.updatedAt)}</p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Sent (last tick)</p>
                      <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-600">
                        {status.sentSinceLastTick}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Skipped (last tick)</p>
                      <p className="mt-1 text-2xl font-semibold tabular-nums text-amber-600">
                        {status.skippedSinceLastTick}
                      </p>
                    </div>
                  </CardContent>
                </Card>

                {/* Action cards */}
                <div className="space-y-4">
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm">Manual Tick</CardTitle>
                      <CardDescription className="text-xs">
                        Synchronously process due sequences for this tenant.
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button className="w-full" size="sm" onClick={() => setTickOpen(true)}>
                        <FastForward className="h-4 w-4" />
                        Run Tick Now
                      </Button>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="flex items-center gap-2 text-sm">
                        <Zap className="h-4 w-4" />
                        Trigger Pipeline
                      </CardTitle>
                      <CardDescription className="text-xs">
                        Trigger all due sequences without waiting for next tick.
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button
                        className="w-full"
                        size="sm"
                        variant="secondary"
                        onClick={() => setTriggerOpen(true)}
                        disabled={triggerMut.isPending}
                      >
                        {triggerMut.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Zap className="h-4 w-4" />
                        )}
                        Trigger Now
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </div>
            )}

            {/* Recent runs table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent Scheduler Runs</CardTitle>
                <CardDescription>Latest execution history.</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {runsLoading ? (
                  <div className="space-y-2 p-4">
                    {[1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : !runs || runs.length === 0 ? (
                  <div className="p-8 text-center text-sm text-muted-foreground">
                    No scheduler runs recorded yet.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-36">Started</TableHead>
                        <TableHead className="w-36">Completed</TableHead>
                        <TableHead className="w-28">Status</TableHead>
                        <TableHead className="w-20 text-right">Sent</TableHead>
                        <TableHead className="w-20 text-right">Skipped</TableHead>
                        <TableHead className="w-24">Duration</TableHead>
                        <TableHead>Error</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {runs.map((run) => (
                        <TableRow key={run.id}>
                          <TableCell className="text-xs">
                            {formatDateTime(run.startedAt)}
                          </TableCell>
                          <TableCell className="text-xs">
                            {run.completedAt ? formatDateTime(run.completedAt) : "—"}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                run.status === "completed"
                                  ? "success"
                                  : run.status === "failed"
                                  ? "destructive"
                                  : "secondary"
                              }
                              className="text-[10px]"
                            >
                              {run.status === "running" && (
                                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                              )}
                              {run.status === "completed" && (
                                <CheckCircle2 className="mr-1 h-3 w-3" />
                              )}
                              {run.status === "failed" && (
                                <XCircle className="mr-1 h-3 w-3" />
                              )}
                              {run.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sm text-emerald-600">
                            {run.sent}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sm text-amber-600">
                            {run.skipped}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {run.durationMs != null ? `${run.durationMs}ms` : "—"}
                          </TableCell>
                          <TableCell className="max-w-[200px] truncate text-xs text-destructive">
                            {run.error ?? "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Tab 2: Campaign Schedules ──────────────────────────────────── */}
          <TabsContent value="campaigns" className="space-y-4">
            {/* Filters */}
            <Card>
              <CardContent className="flex flex-wrap items-end gap-3 p-4">
                <div className="flex-1 space-y-1 min-w-[200px]">
                  <Label className="text-xs">Campaign</Label>
                  <select
                    className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={campFilter}
                    onChange={(e) => setCampFilter(e.target.value)}
                  >
                    <option value="">All campaigns</option>
                    {(campaignList ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="w-44 space-y-1">
                  <Label className="text-xs">Status</Label>
                  <select
                    className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={campStatusFilter}
                    onChange={(e) => setCampStatusFilter(e.target.value)}
                  >
                    <option value="">All statuses</option>
                    <option value="draft">Draft</option>
                    <option value="active">Active</option>
                    <option value="paused">Paused</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => refetchCamps()}>
                    <Filter className="h-3.5 w-3.5" />
                    Apply
                  </Button>
                  {(campFilter || campStatusFilter) && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setCampFilter("");
                        setCampStatusFilter("");
                      }}
                    >
                      <X className="h-3.5 w-3.5" />
                      Clear
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Campaign Sequences</CardTitle>
                  {campSchedules && (
                    <span className="text-sm text-muted-foreground">
                      {campSchedules.total} campaign{campSchedules.total !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                <CardDescription>
                  Sequence counts per campaign. Scheduled = queued to send; Sent = delivered.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {campLoading ? (
                  <div className="space-y-2 p-4">
                    {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
                  </div>
                ) : !campSchedules || campSchedules.items.length === 0 ? (
                  <div className="p-8 text-center text-sm text-muted-foreground">
                    No campaigns found. Adjust filters or create a campaign first.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Campaign</TableHead>
                        <TableHead className="w-24">Status</TableHead>
                        <TableHead className="w-20 text-right">Total</TableHead>
                        <TableHead className="w-24 text-right">Scheduled</TableHead>
                        <TableHead className="w-20 text-right">Sent</TableHead>
                        <TableHead className="w-20 text-right">Replied</TableHead>
                        <TableHead className="w-20 text-right">Bounced</TableHead>
                        <TableHead className="w-20 text-right">Failed</TableHead>
                        <TableHead className="w-40">Next Send</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {campSchedules.items.map((item) => (
                        <TableRow key={item.campaignId}>
                          <TableCell>
                            <div className="font-medium text-sm">{item.campaignName}</div>
                            <div className="text-xs text-muted-foreground font-mono">
                              {item.campaignId.slice(-8)}
                            </div>
                          </TableCell>
                          <TableCell>
                            <CampaignStatusBadge status={item.campaignStatus} />
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sm">
                            {item.totalSequences}
                          </TableCell>
                          <TableCell className="text-right">
                            {item.scheduled > 0 ? (
                              <span className="tabular-nums text-sm font-semibold text-blue-600">
                                {item.scheduled}
                              </span>
                            ) : (
                              <span className="tabular-nums text-sm text-muted-foreground">0</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sm text-emerald-600">
                            {item.sent}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sm text-purple-600">
                            {item.replied}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sm text-rose-600">
                            {item.bounced}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sm text-muted-foreground">
                            {item.failed}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {item.nextSendAt ? formatDateTime(item.nextSendAt) : "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Tab 3: Skip Details ────────────────────────────────────────── */}
          <TabsContent value="skipped" className="space-y-4">
            {/* Reason breakdown summary */}
            {skipData && Object.keys(skipData.reasonBreakdown).length > 0 && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {Object.entries(skipData.reasonBreakdown)
                  .sort((a, b) => b[1] - a[1])
                  .map(([reason, count]) => (
                    <Card
                      key={reason}
                      className={`cursor-pointer transition-shadow hover:shadow-md ${
                        skipReasonFilter === reason ? "ring-2 ring-primary" : ""
                      }`}
                      onClick={() =>
                        setSkipReasonFilter(skipReasonFilter === reason ? "" : reason)
                      }
                    >
                      <CardContent className="p-4">
                        <p className="text-2xl font-bold tabular-nums">{count}</p>
                        <SkipReasonBadge reason={reason} />
                        {skipReasonFilter === reason && (
                          <p className="mt-1 text-[10px] text-muted-foreground">
                            Click to clear filter
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  ))}
              </div>
            )}

            {/* Filters */}
            <Card>
              <CardContent className="flex flex-wrap items-end gap-3 p-4">
                <div className="flex-1 min-w-[160px] space-y-1">
                  <Label className="text-xs">Run ID</Label>
                  <Input
                    placeholder="Filter by run ID…"
                    value={skipRunId}
                    onChange={(e) => setSkipRunId(e.target.value)}
                    className="h-8 text-sm"
                  />
                </div>
                <div className="flex-1 min-w-[160px] space-y-1">
                  <Label className="text-xs">Campaign</Label>
                  <select
                    className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={skipCampId}
                    onChange={(e) => setSkipCampId(e.target.value)}
                  >
                    <option value="">All campaigns</option>
                    {(campaignList ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="w-52 space-y-1">
                  <Label className="text-xs">Skip Reason</Label>
                  <select
                    className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={skipReasonFilter}
                    onChange={(e) => setSkipReasonFilter(e.target.value)}
                  >
                    <option value="">All reasons</option>
                    {Object.entries(SKIP_REASON_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => refetchSkips()}>
                    <Filter className="h-3.5 w-3.5" />
                    Apply
                  </Button>
                  {(skipRunId || skipCampId || skipReasonFilter) && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setSkipRunId("");
                        setSkipCampId("");
                        setSkipReasonFilter("");
                      }}
                    >
                      <X className="h-3.5 w-3.5" />
                      Clear
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Skipped Sequences</CardTitle>
                  {skipData && (
                    <span className="text-sm text-muted-foreground">
                      {skipData.total} skip event{skipData.total !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                <CardDescription>
                  Click a reason card above to filter by that reason. Click a row to see detail.
                  {!skipData || skipData.total === 0 && skipData.reasonBreakdown && Object.keys(skipData.reasonBreakdown).length === 0
                    ? " Skip logging requires migration 0022 to be applied."
                    : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {skipLoading ? (
                  <div className="space-y-2 p-4">
                    {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
                  </div>
                ) : !skipData || skipData.items.length === 0 ? (
                  <div className="p-8 text-center space-y-2">
                    <SkipForward className="h-8 w-8 mx-auto text-muted-foreground/40" />
                    <p className="text-sm text-muted-foreground">
                      No skip events found.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Skip details are recorded from migration 0022 onwards. Run{" "}
                      <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
                        alembic upgrade head
                      </code>{" "}
                      to enable skip logging.
                    </p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-8"></TableHead>
                        <TableHead>Campaign</TableHead>
                        <TableHead>Prospect Email</TableHead>
                        <TableHead>Skip Reason</TableHead>
                        <TableHead className="w-36">Skipped At</TableHead>
                        <TableHead>Run ID</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {skipData.items.map((item) => (
                        <>
                          <TableRow
                            key={item.id}
                            className="cursor-pointer"
                            onClick={() =>
                              setExpandedSkipId(expandedSkipId === item.id ? null : item.id)
                            }
                          >
                            <TableCell className="text-muted-foreground">
                              <ChevronDown
                                className={`h-4 w-4 transition-transform ${
                                  expandedSkipId === item.id ? "rotate-180" : ""
                                }`}
                              />
                            </TableCell>
                            <TableCell>
                              <span className="text-sm">
                                {item.campaignName ?? "—"}
                              </span>
                            </TableCell>
                            <TableCell className="text-sm font-mono">
                              {item.prospectEmail ?? "—"}
                            </TableCell>
                            <TableCell>
                              <SkipReasonBadge reason={item.skipReason} />
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {formatDateTime(item.skippedAt)}
                            </TableCell>
                            <TableCell className="font-mono text-xs text-muted-foreground">
                              {item.runId ? item.runId.slice(-8) : "manual"}
                            </TableCell>
                          </TableRow>
                          {expandedSkipId === item.id && (
                            <TableRow key={`${item.id}-detail`} className="bg-muted/30">
                              <TableCell />
                              <TableCell colSpan={5} className="py-3">
                                <div className="space-y-1 text-xs">
                                  <div className="flex gap-6">
                                    <div>
                                      <span className="font-medium text-muted-foreground">Sequence ID: </span>
                                      <span className="font-mono">{item.sequenceId}</span>
                                    </div>
                                    {item.prospectId && (
                                      <div>
                                        <span className="font-medium text-muted-foreground">Prospect ID: </span>
                                        <span className="font-mono">{item.prospectId}</span>
                                      </div>
                                    )}
                                    {item.runId && (
                                      <div>
                                        <span className="font-medium text-muted-foreground">Run ID: </span>
                                        <span className="font-mono">{item.runId}</span>
                                      </div>
                                    )}
                                  </div>
                                  {item.detail && (
                                    <div>
                                      <span className="font-medium text-muted-foreground">Detail: </span>
                                      <span className="text-destructive">{item.detail}</span>
                                    </div>
                                  )}
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Tab 4: Daily Sent ──────────────────────────────────────────── */}
          <TabsContent value="daily" className="space-y-4">
            {/* Filters */}
            <Card>
              <CardContent className="flex flex-wrap items-end gap-3 p-4">
                <div className="flex-1 min-w-[180px] space-y-1">
                  <Label className="text-xs">Campaign</Label>
                  <select
                    className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={dailyCampId}
                    onChange={(e) => setDailyCampId(e.target.value)}
                  >
                    <option value="">All campaigns</option>
                    {(campaignList ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="w-36 space-y-1">
                  <Label className="text-xs">From Date</Label>
                  <Input
                    type="date"
                    value={dailySince}
                    onChange={(e) => setDailySince(e.target.value)}
                    className="h-8 text-sm"
                  />
                </div>
                <div className="w-36 space-y-1">
                  <Label className="text-xs">To Date</Label>
                  <Input
                    type="date"
                    value={dailyUntil}
                    onChange={(e) => setDailyUntil(e.target.value)}
                    className="h-8 text-sm"
                  />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => refetchDaily()}>
                    <Filter className="h-3.5 w-3.5" />
                    Apply
                  </Button>
                  {(dailyCampId || dailySince || dailyUntil) && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setDailyCampId("");
                        setDailySince("");
                        setDailyUntil("");
                      }}
                    >
                      <X className="h-3.5 w-3.5" />
                      Clear
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Daily Sent Log</CardTitle>
                  {dailySentData && (
                    <span className="text-sm text-muted-foreground">
                      {dailySentData.total} entries
                    </span>
                  )}
                </div>
                <CardDescription>
                  Emails sent per campaign per day. Updated in real-time as ticks run.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {dailyLoading ? (
                  <div className="space-y-2 p-4">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : !dailySentData || dailySentData.items.length === 0 ? (
                  <div className="p-8 text-center space-y-2">
                    <Calendar className="h-8 w-8 mx-auto text-muted-foreground/40" />
                    <p className="text-sm text-muted-foreground">
                      No daily sent data found.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Daily logs populate as emails are sent. If you've sent emails recently,
                      run{" "}
                      <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
                        alembic upgrade head
                      </code>{" "}
                      to enable the aggregation table.
                    </p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Campaign</TableHead>
                        <TableHead className="w-28 text-right">Emails Sent</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dailySentData.items.map((item, i) => (
                        <TableRow key={`${item.campaignId}-${item.sentDate}-${i}`}>
                          <TableCell className="font-mono text-sm">
                            {item.sentDate}
                          </TableCell>
                          <TableCell>
                            <div className="text-sm font-medium">{item.campaignName}</div>
                            <div className="font-mono text-xs text-muted-foreground">
                              {item.campaignId.slice(-8)}
                            </div>
                          </TableCell>
                          <TableCell className="text-right">
                            <span className="text-lg font-semibold tabular-nums text-emerald-600">
                              {item.sentCount}
                            </span>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          {/* ── Tab 5: Settings ────────────────────────────────────────── */}
          <TabsContent value="settings" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Settings className="h-5 w-5" />
                  Scheduler Settings
                </CardTitle>
                <CardDescription>
                  Control automatic email sending for this tenant. Changes take
                  effect on the next global scheduler tick.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                {/* Enable / Disable */}
                <div className="flex items-start justify-between gap-6 rounded-lg border p-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      {settingsEnabled ? (
                        <ToggleRight className="h-5 w-5 text-emerald-500" />
                      ) : (
                        <ToggleLeft className="h-5 w-5 text-muted-foreground" />
                      )}
                      <p className="font-medium text-sm">Automatic Email Sending</p>
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          settingsEnabled
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {settingsEnabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      When disabled, no automatic emails will be sent for this tenant.
                      Reply and bounce tracking continue to work regardless of this setting.
                      Manual tick from the Status tab still works while disabled.
                    </p>
                  </div>
                  <Switch
                    checked={settingsEnabled ?? false}
                    onCheckedChange={(val) => setSettingsEnabled(val)}
                    className="mt-1 shrink-0"
                  />
                </div>

                {/* Tick interval */}
                <div className="space-y-3 rounded-lg border p-4">
                  <div className="space-y-1">
                    <p className="font-medium text-sm">Send Interval</p>
                    <p className="text-sm text-muted-foreground">
                      How often the scheduler checks for and sends due sequences
                      for this tenant. Lower = more frequent but more DB load.
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {[
                      { label: "Every 5 min", value: "5" },
                      { label: "Every 15 min", value: "15" },
                      { label: "Every 30 min", value: "30" },
                      { label: "Every 60 min", value: "60" },
                    ].map(({ label, value }) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setSettingsInterval(value)}
                        className={`rounded-lg border px-4 py-3 text-sm font-medium transition-colors ${
                          settingsInterval === value
                            ? "border-primary bg-primary/5 text-primary"
                            : "border-input bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="flex items-center gap-3">
                    <p className="text-xs text-muted-foreground shrink-0">Custom (minutes):</p>
                    <Input
                      type="number"
                      min={1}
                      max={1440}
                      value={settingsInterval}
                      onChange={(e) => setSettingsInterval(e.target.value)}
                      className="h-8 w-28 text-sm"
                    />
                    <p className="text-xs text-muted-foreground">
                      Min: 1 · Max: 1440 (24h)
                    </p>
                  </div>
                </div>

                {/* Current values summary */}
                {schedulerParams && (
                  <div className="rounded-lg bg-muted/40 p-4 space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Current saved values
                    </p>
                    {schedulerParams
                      .filter((p) =>
                        ["scheduler.enabled", "scheduler.tick_interval_minutes"].includes(p.key)
                      )
                      .map((p) => (
                        <div key={p.key} className="flex justify-between text-sm">
                          <span className="text-muted-foreground">{p.label || p.key}</span>
                          <span className="font-mono font-medium">
                            {p.value}
                            {p.unit ? ` ${p.unit}` : ""}
                          </span>
                        </div>
                      ))}
                  </div>
                )}

                {/* Save button */}
                <div className="flex justify-end">
                  <Button
                    onClick={saveSchedulerSettings}
                    disabled={settingsSaving || settingsEnabled === null}
                    className="gap-2"
                  >
                    {settingsSaving ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    {settingsSaving ? "Saving…" : "Save Settings"}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Advanced params info card */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">All Scheduler Parameters</CardTitle>
                <CardDescription>
                  Full list of scheduler parameters. Edit advanced settings in{" "}
                  <a
                    href="/setup/system-params"
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    System Parameters → Scheduler
                  </a>
                  .
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {!schedulerParams || schedulerParams.length === 0 ? (
                  <div className="p-6 text-sm text-muted-foreground text-center">
                    No scheduler parameters found.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Parameter</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead className="w-32 text-right">Current Value</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {schedulerParams.map((p) => (
                        <TableRow key={p.key}>
                          <TableCell className="font-mono text-xs">{p.key}</TableCell>
                          <TableCell className="text-sm text-muted-foreground max-w-sm">
                            {p.description}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm font-medium">
                            {p.value}
                            {p.unit ? (
                              <span className="ml-1 text-xs text-muted-foreground">{p.unit}</span>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* ── Trigger Now dialog ──────────────────────────────────────────── */}
        <Dialog open={triggerOpen} onOpenChange={setTriggerOpen}>
          <DialogClose onClose={() => setTriggerOpen(false)} />
          <DialogHeader>
            <DialogTitle>Trigger Scheduler Now?</DialogTitle>
            <DialogDescription>
              Immediately triggers the scheduler pipeline to process all due sequences,
              regardless of the next scheduled tick.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTriggerOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => triggerMut.mutate()} disabled={triggerMut.isPending}>
              {triggerMut.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Triggering…
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  Trigger Now
                </>
              )}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* ── Manual tick dialog ─────────────────────────────────────────── */}
        <Dialog open={tickOpen} onOpenChange={setTickOpen}>
          <DialogClose onClose={() => setTickOpen(false)} />
          <DialogHeader>
            <DialogTitle>Run Scheduler Tick?</DialogTitle>
            <DialogDescription>
              Synchronously processes due sequences for the current tenant. Avoid during peak load.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label htmlFor="tick-max">Max sends per tick</Label>
              <Input
                id="tick-max"
                type="number"
                min={1}
                max={1000}
                value={maxSend}
                onChange={(e) => setMaxSend(Number(e.target.value))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTickOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleTick} disabled={tickMut.isPending}>
              {tickMut.isPending ? "Running…" : "Run Tick"}
            </Button>
          </DialogFooter>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
