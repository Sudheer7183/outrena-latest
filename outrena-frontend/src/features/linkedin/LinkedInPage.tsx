// /**
//  * LinkedInPage.tsx — LinkedIn config + engagement + inbox.
//  *
//  * Gaps closed:
//  *   LI-1  Connection status card — shows active accounts, connect/disconnect.
//  *         Uses cookieJar (li_at session cookie), not accessToken.
//  *   LI-2  Inbox tab — LinkedIn message inbox with triage button
//  *         POST /api/v1/linkedin/inbox/triage { messageIds, status }
//  *   LI-3  Engagement tab — ICP-matched engagement tasks,
//  *         POST /api/v1/linkedin/engagements/check-icp
//  *   LI-4  Dormant state — "LinkedIn Integration is Dormant" empty state
//  *         with feature preview cards + setup instructions
//  *
//  * API contracts (linkedin.py schemas):
//  *   LinkedInConfigResponse: { id, accountName, accountHandle, isActive,
//  *     syncStatus, lastSyncedAt, createdAt, updatedAt }
//  *   LinkedInEngagementResponse: { id, prospectId, icpProfileId, action,
//  *     note, status, scheduledAt, executedAt, owner_user_id, createdAt }
//  *   LinkedInInboxMessageResponse: { id, prospectId, senderName,
//  *     senderHandle, body, status, receivedAt, triagedAt, createdAt }
//  *   IcpMatchResponse: { success, checked, matches: IcpMatchResult[] }
//  *   IcpMatchResult: { engagement_id, is_icp_match, icp_profile_id,
//  *     icp_profile_name, match_reason, suggested_note }
//  */
// import { useMemo, useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   BarChart3,
//   CheckCircle2,
//   Clock,
//   Heart,
//   Inbox as InboxIcon,
//   Linkedin,
//   Loader2,
//   MessageSquare,
//   Pencil,
//   Plus,
//   RefreshCw,
//   Save,
//   Sparkles,
//   Target,
//   Trash2,
//   UserPlus,
// } from "lucide-react";
// import { toast } from "sonner";

// import { http } from "@/services/apiClient";
// import { cn, formatDateTime, timeAgo, truncate } from "@/lib/utils";
// import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
//   DialogContent,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
// } from "@/components/ui/dialog";
// import { EmptyState } from "@/components/ui/empty-state";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { PageHeader } from "@/components/ui/page-header";
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from "@/components/ui/select";
// import { Skeleton } from "@/components/ui/skeleton";
// import { Switch } from "@/components/ui/switch";
// import {
//   Table,
//   TableBody,
//   TableCell,
//   TableHead,
//   TableHeader,
//   TableRow,
// } from "@/components/ui/table";
// import {
//   Tabs,
//   TabsContent,
//   TabsList,
//   TabsTrigger,
// } from "@/components/ui/tabs";
// import { Textarea } from "@/components/ui/textarea";

// /* ── Backend types (linkedin.py) ────────────────────────────────────────── */

// interface LinkedInConfigResponse {
//   id: string;
//   accountName: string;
//   accountHandle: string | null;
//   isActive: boolean;
//   syncStatus: string;
//   lastSyncedAt: string | null;
//   createdAt: string;
//   updatedAt: string;
// }

// type EngagementAction = "connect" | "message" | "view" | "endorse";

// interface LinkedInEngagementResponse {
//   id: string;
//   prospectId: string | null;
//   icpProfileId: string | null;
//   action: string;
//   note: string | null;
//   status: string;
//   scheduledAt: string | null;
//   executedAt: string | null;
//   owner_user_id: string | null;
//   createdAt: string;
//   updatedAt: string;
// }

// interface LinkedInInboxMessageResponse {
//   id: string;
//   prospectId: string | null;
//   senderName: string;
//   senderHandle: string | null;
//   body: string;
//   status: string; // unread | read | archived | converted_to_reply_draft
//   receivedAt: string;
//   triagedAt: string | null;
//   createdAt: string;
//   updatedAt: string;
// }

// interface IcpMatchResult {
//   engagement_id: string;
//   is_icp_match: boolean;
//   icp_profile_id: string | null;
//   icp_profile_name: string | null;
//   match_reason: string | null;
//   suggested_note: string | null;
// }

// interface IcpMatchResponse {
//   success: boolean;
//   checked: number;
//   matches: IcpMatchResult[];
//   error: string | null;
// }

// /* ── Action / status metadata ────────────────────────────────────────────── */

// const ACTION_META: Record<
//   string,
//   { label: string; icon: React.ElementType; color: string }
// > = {
//   connect: { label: "Connect", icon: UserPlus, color: "text-blue-600" },
//   message: { label: "Message", icon: MessageSquare, color: "text-violet-600" },
//   view: { label: "View", icon: Heart, color: "text-rose-500" },
//   endorse: { label: "Endorse", icon: CheckCircle2, color: "text-emerald-600" },
// };

// const STATUS_CHIP: Record<string, string> = {
//   pending: "bg-slate-100 text-slate-700",
//   scheduled: "bg-amber-100 text-amber-700",
//   done: "bg-emerald-100 text-emerald-700",
//   failed: "bg-rose-100 text-rose-700",
// };

// /* ── Page ───────────────────────────────────────────────────────────────── */

// export function LinkedInPage() {
//   const [tab, setTab] = useState("config");

//   return (
//     <div className="space-y-6">
//       <PageHeader
//         title="LinkedIn Hub"
//         description="Manage LinkedIn accounts, schedule engagement tasks, and triage inbox messages."
//       />

//       <Alert>
//         <Linkedin className="h-4 w-4" />
//         <AlertTitle>Companion channel — runs in parallel to email</AlertTitle>
//         <AlertDescription>
//           LinkedIn engagement layers connection requests, messages, and likes on
//           top of email sequences for the same prospects. Triage LinkedIn replies
//           manually in the Inbox tab — they are not auto-synced to Reply Inbox.
//         </AlertDescription>
//       </Alert>

//       <Tabs value={tab} onValueChange={setTab}>
//         <TabsList>
//           <TabsTrigger value="config">
//             <Linkedin className="mr-1.5 h-4 w-4" />
//             Accounts
//           </TabsTrigger>
//           <TabsTrigger value="engagement">
//             <Target className="mr-1.5 h-4 w-4" />
//             Engagement
//           </TabsTrigger>
//           <TabsTrigger value="inbox">
//             <InboxIcon className="mr-1.5 h-4 w-4" />
//             Inbox
//           </TabsTrigger>
//         </TabsList>
//         <TabsContent value="config" className="mt-4">
//           <ConfigTab />
//         </TabsContent>
//         <TabsContent value="engagement" className="mt-4">
//           <EngagementTab />
//         </TabsContent>
//         <TabsContent value="inbox" className="mt-4">
//           <InboxTab />
//         </TabsContent>
//       </Tabs>
//     </div>
//   );
// }

// /* ── LI-1 — Config tab ───────────────────────────────────────────────────── */

// function ConfigTab() {
//   const qc = useQueryClient();
//   const [addOpen, setAddOpen] = useState(false);
//   const [editTarget, setEditTarget] =
//     useState<LinkedInConfigResponse | null>(null);
//   const [deleteTarget, setDeleteTarget] =
//     useState<LinkedInConfigResponse | null>(null);

//   const query = useQuery<LinkedInConfigResponse[]>({
//     queryKey: ["linkedin-config"],
//     queryFn: () =>
//       http.get<LinkedInConfigResponse[]>("/api/v1/linkedin/config"),
//     retry: false,
//   });

//   const accounts = query.data ?? [];
//   const hasAccounts = accounts.length > 0;

//   const deleteMut = useMutation({
//     mutationFn: (id: string) => http.delete(`/api/v1/linkedin/config/${id}`),
//     onSuccess: () => {
//       toast.success("Account removed");
//       setDeleteTarget(null);
//       qc.invalidateQueries({ queryKey: ["linkedin-config"] });
//     },
//     onError: () => toast.error("Failed to remove account"),
//   });

//   function invalidate() {
//     qc.invalidateQueries({ queryKey: ["linkedin-config"] });
//   }

//   return (
//     <>
//       {/* LI-4 — Dormant state when no accounts */}
//       {!query.isLoading && !hasAccounts && (
//         <Card className="border-dashed border-2 border-muted-foreground/20 mb-4">
//           <CardContent className="py-10 flex flex-col items-center text-center space-y-4">
//             <div className="h-14 w-14 rounded-full bg-blue-100 flex items-center justify-center">
//               <Linkedin className="h-7 w-7 text-blue-600" />
//             </div>
//             <div>
//               <h3 className="font-semibold">LinkedIn Integration is Dormant</h3>
//               <p className="text-sm text-muted-foreground mt-1 max-w-md">
//                 Connect your LinkedIn account using a session cookie (li_at) to
//                 enable inbox triage, ICP engagement checking, and connection
//                 outreach. All LinkedIn features remain inactive until you add an
//                 account.
//               </p>
//             </div>
//             <Button onClick={() => setAddOpen(true)}>
//               <Plus className="h-4 w-4" /> Add LinkedIn Account
//             </Button>
//             <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-lg mt-2 opacity-60">
//               {[
//                 {
//                   icon: <InboxIcon className="h-5 w-5" />,
//                   title: "Inbox Triage",
//                   desc: "Sort messages into positive, neutral, negative, or needs-follow-up.",
//                 },
//                 {
//                   icon: <Target className="h-5 w-5" />,
//                   title: "ICP Engagement",
//                   desc: "Review engagements, flag ICP matches, generate connection notes.",
//                 },
//                 {
//                   icon: <BarChart3 className="h-5 w-5" />,
//                   title: "Weekly Recap",
//                   desc: "Track connections accepted and conversations started.",
//                 },
//               ].map((f, i) => (
//                 <Card key={i}>
//                   <CardContent className="p-3">
//                     <div className="text-muted-foreground mb-2">{f.icon}</div>
//                     <p className="text-xs font-medium">{f.title}</p>
//                     <p className="text-xs text-muted-foreground mt-0.5">
//                       {f.desc}
//                     </p>
//                   </CardContent>
//                 </Card>
//               ))}
//             </div>
//           </CardContent>
//         </Card>
//       )}

//       <Card>
//         <CardHeader>
//           <div className="flex items-center justify-between">
//             <div>
//               <CardTitle className="text-base">LinkedIn Accounts</CardTitle>
//               <CardDescription>
//                 Authenticated sessions used for engagement and inbox access.
//               </CardDescription>
//             </div>
//             <Button size="sm" onClick={() => setAddOpen(true)}>
//               <Plus className="h-4 w-4" /> Add Account
//             </Button>
//           </div>
//         </CardHeader>
//         <CardContent className="p-0">
//           {query.isLoading ? (
//             <div className="space-y-2 p-4">
//               {Array.from({ length: 3 }).map((_, i) => (
//                 <Skeleton key={i} className="h-12 w-full" />
//               ))}
//             </div>
//           ) : !hasAccounts ? (
//             <EmptyState
//               icon={<Linkedin className="h-6 w-6" />}
//               title="No accounts yet"
//               description='Click "Add Account" above to connect your first LinkedIn account.'
//               className="py-8"
//             />
//           ) : (
//             <Table>
//               <TableHeader>
//                 <TableRow>
//                   <TableHead>Account</TableHead>
//                   <TableHead>Handle</TableHead>
//                   <TableHead>Status</TableHead>
//                   <TableHead>Sync</TableHead>
//                   <TableHead>Last synced</TableHead>
//                   <TableHead className="text-right">Actions</TableHead>
//                 </TableRow>
//               </TableHeader>
//               <TableBody>
//                 {accounts.map((acc) => (
//                   <TableRow key={acc.id}>
//                     <TableCell className="font-medium">
//                       {acc.accountName}
//                     </TableCell>
//                     <TableCell className="text-sm text-muted-foreground">
//                       {acc.accountHandle ?? "—"}
//                     </TableCell>
//                     <TableCell>
//                       <Badge
//                         variant={acc.isActive ? "default" : "secondary"}
//                         className={
//                           acc.isActive
//                             ? "bg-emerald-100 text-emerald-700 border-emerald-200"
//                             : ""
//                         }
//                       >
//                         {acc.isActive ? "Active" : "Paused"}
//                       </Badge>
//                     </TableCell>
//                     <TableCell>
//                       <Badge variant="outline" className="text-xs capitalize">
//                         {acc.syncStatus}
//                       </Badge>
//                     </TableCell>
//                     <TableCell className="text-xs text-muted-foreground">
//                       {acc.lastSyncedAt ? timeAgo(acc.lastSyncedAt) : "Never"}
//                     </TableCell>
//                     <TableCell className="text-right">
//                       <div className="flex justify-end gap-1">
//                         <Button
//                           size="icon"
//                           variant="ghost"
//                           className="h-7 w-7"
//                           onClick={() => setEditTarget(acc)}
//                         >
//                           <Pencil className="h-4 w-4" />
//                         </Button>
//                         <Button
//                           size="icon"
//                           variant="ghost"
//                           className="h-7 w-7 text-destructive"
//                           onClick={() => setDeleteTarget(acc)}
//                         >
//                           <Trash2 className="h-4 w-4" />
//                         </Button>
//                       </div>
//                     </TableCell>
//                   </TableRow>
//                 ))}
//               </TableBody>
//             </Table>
//           )}
//         </CardContent>
//       </Card>

//       {/* Add / Edit dialog */}
//       <AccountFormDialog
//         open={addOpen || Boolean(editTarget)}
//         editing={editTarget}
//         onClose={() => {
//           setAddOpen(false);
//           setEditTarget(null);
//         }}
//         onSaved={invalidate}
//       />

//       {/* Delete dialog */}
//       <Dialog
//         open={Boolean(deleteTarget)}
//         onOpenChange={(o) => !o && setDeleteTarget(null)}
//       >
//         <DialogContent>
//           <DialogHeader>
//             <DialogTitle>Remove LinkedIn account?</DialogTitle>
//             <DialogDescription>
//               "{deleteTarget?.accountName}" and its stored session will be
//               permanently removed. Scheduled engagement tasks will be cancelled.
//             </DialogDescription>
//           </DialogHeader>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setDeleteTarget(null)}>
//               Cancel
//             </Button>
//             <Button
//               variant="destructive"
//               onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
//               disabled={deleteMut.isPending}
//             >
//               {deleteMut.isPending ? "Removing…" : "Remove"}
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>
//     </>
//   );
// }

// function AccountFormDialog({
//   open,
//   editing,
//   onClose,
//   onSaved,
// }: {
//   open: boolean;
//   editing: LinkedInConfigResponse | null;
//   onClose: () => void;
//   onSaved: () => void;
// }) {
//   const [accountName, setAccountName] = useState("");
//   const [accountHandle, setAccountHandle] = useState("");
//   const [cookieJar, setCookieJar] = useState("");
//   const [isActive, setIsActive] = useState(true);
//   const [saving, setSaving] = useState(false);

//   useMemo(() => {
//     setAccountName(editing?.accountName ?? "");
//     setAccountHandle(editing?.accountHandle ?? "");
//     setCookieJar("");
//     setIsActive(editing?.isActive ?? true);
//   }, [editing, open]);

//   async function submit() {
//     if (!accountName.trim()) return;
//     setSaving(true);
//     try {
//       const payload = {
//         accountName: accountName.trim(),
//         accountHandle: accountHandle.trim() || null,
//         isActive,
//         cookieJar: cookieJar.trim() || null,
//       };
//       if (editing) {
//         await http.put(`/api/v1/linkedin/config/${editing.id}`, payload);
//         toast.success("Account updated");
//       } else {
//         await http.post("/api/v1/linkedin/config", payload);
//         toast.success("Account added");
//       }
//       onSaved();
//       onClose();
//     } catch {
//       toast.error("Failed to save account");
//     } finally {
//       setSaving(false);
//     }
//   }

//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
//       <DialogContent>
//         <DialogHeader>
//           <DialogTitle>
//             {editing ? "Edit Account" : "Add LinkedIn Account"}
//           </DialogTitle>
//           <DialogDescription>
//             Provide the account email and LinkedIn session cookie (li_at) to
//             authenticate.
//           </DialogDescription>
//         </DialogHeader>
//         <div className="space-y-3">
//           <div className="space-y-1.5">
//             <Label htmlFor="acc-name">Account Email *</Label>
//             <Input
//               id="acc-name"
//               value={accountName}
//               onChange={(e) => setAccountName(e.target.value)}
//               placeholder="you@company.com"
//             />
//           </div>
//           <div className="space-y-1.5">
//             <Label htmlFor="acc-handle">LinkedIn Handle (optional)</Label>
//             <Input
//               id="acc-handle"
//               value={accountHandle}
//               onChange={(e) => setAccountHandle(e.target.value)}
//               placeholder="e.g. in/yourname"
//             />
//           </div>
//           <div className="space-y-1.5">
//             <Label htmlFor="acc-cookie">
//               Session Cookie (li_at){" "}
//               <span className="text-muted-foreground text-xs">
//                 — leave blank to keep existing
//               </span>
//             </Label>
//             <Input
//               id="acc-cookie"
//               type="password"
//               value={cookieJar}
//               onChange={(e) => setCookieJar(e.target.value)}
//               placeholder="paste li_at cookie value…"
//             />
//           </div>
//           <div className="flex items-center gap-3">
//             <Switch checked={isActive} onCheckedChange={setIsActive} />
//             <Label>{isActive ? "Active" : "Paused"}</Label>
//           </div>
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={onClose}>
//             Cancel
//           </Button>
//           <Button
//             onClick={submit}
//             disabled={saving || !accountName.trim()}
//           >
//             {saving ? (
//               <Loader2 className="h-4 w-4 animate-spin" />
//             ) : (
//               <Save className="h-4 w-4" />
//             )}
//             {editing ? "Save" : "Add Account"}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// /* ── LI-3 — Engagement tab ───────────────────────────────────────────────── */

// function EngagementTab() {
//   const qc = useQueryClient();
//   const [createOpen, setCreateOpen] = useState(false);
//   const [icpResult, setIcpResult] = useState<IcpMatchResponse | null>(null);

//   const query = useQuery<LinkedInEngagementResponse[]>({
//     queryKey: ["linkedin-engagements"],
//     queryFn: () =>
//       http.get<LinkedInEngagementResponse[]>("/api/v1/linkedin/engagements"),
//     retry: false,
//   });

//   const tasks = query.data ?? [];

//   const createMut = useMutation({
//     mutationFn: (body: {
//       prospectId: string | null;
//       action: string;
//       note: string | null;
//       scheduledAt: string | null;
//     }) => http.post<LinkedInEngagementResponse>("/api/v1/linkedin/engagements", body),
//     onSuccess: () => {
//       toast.success("Engagement task created");
//       setCreateOpen(false);
//       qc.invalidateQueries({ queryKey: ["linkedin-engagements"] });
//     },
//     onError: () => toast.error("Failed to create task"),
//   });

//   const icpCheckMut = useMutation({
//     mutationFn: () =>
//       http.post<IcpMatchResponse>("/api/v1/linkedin/engagements/check-icp", {}),
//     onSuccess: (data) => {
//       setIcpResult(data);
//       if (data.success) {
//         const n = data.matches.filter((m) => m.is_icp_match).length;
//         toast.success(`ICP check complete: ${n} match(es) found`);
//       } else {
//         toast.error(data.error ?? "ICP check failed");
//       }
//     },
//     onError: () => toast.error("ICP check failed"),
//   });

//   return (
//     <div className="space-y-4">
//       <Card>
//         <CardHeader>
//           <div className="flex items-center justify-between">
//             <div>
//               <CardTitle className="text-base">Engagement Tasks</CardTitle>
//               <CardDescription>
//                 Scheduled connects, messages, and profile views.
//               </CardDescription>
//             </div>
//             <div className="flex gap-2">
//               <Button
//                 size="sm"
//                 variant="outline"
//                 onClick={() => icpCheckMut.mutate()}
//                 disabled={icpCheckMut.isPending}
//               >
//                 {icpCheckMut.isPending ? (
//                   <Loader2 className="h-4 w-4 animate-spin" />
//                 ) : (
//                   <Target className="h-4 w-4" />
//                 )}
//                 Check ICP Matches
//               </Button>
//               <Button size="sm" onClick={() => setCreateOpen(true)}>
//                 <Plus className="h-4 w-4" /> New Task
//               </Button>
//             </div>
//           </div>
//         </CardHeader>
//         <CardContent className="p-0">
//           {query.isLoading ? (
//             <div className="space-y-2 p-4">
//               {Array.from({ length: 3 }).map((_, i) => (
//                 <Skeleton key={i} className="h-12 w-full" />
//               ))}
//             </div>
//           ) : tasks.length === 0 ? (
//             <EmptyState
//               icon={<Target className="h-6 w-6" />}
//               title="No engagement tasks"
//               description='Create a task to schedule a connect, message, or profile view.'
//               className="py-8"
//             />
//           ) : (
//             <Table>
//               <TableHeader>
//                 <TableRow>
//                   <TableHead>Action</TableHead>
//                   <TableHead>Status</TableHead>
//                   <TableHead>Scheduled</TableHead>
//                   <TableHead>Note</TableHead>
//                 </TableRow>
//               </TableHeader>
//               <TableBody>
//                 {tasks.map((t) => {
//                   const meta = ACTION_META[t.action] ?? ACTION_META.connect;
//                   const Icon = meta.icon;
//                   return (
//                     <TableRow key={t.id}>
//                       <TableCell>
//                         <div className="flex items-center gap-2">
//                           <Icon className={cn("h-4 w-4", meta.color)} />
//                           <span className="text-sm font-medium capitalize">
//                             {meta.label}
//                           </span>
//                         </div>
//                       </TableCell>
//                       <TableCell>
//                         <span
//                           className={cn(
//                             "inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize",
//                             STATUS_CHIP[t.status] ?? STATUS_CHIP.pending
//                           )}
//                         >
//                           {t.status}
//                         </span>
//                       </TableCell>
//                       <TableCell className="text-xs text-muted-foreground">
//                         {t.scheduledAt ? (
//                           <span className="flex items-center gap-1">
//                             <Clock className="h-3 w-3" />
//                             {formatDateTime(t.scheduledAt)}
//                           </span>
//                         ) : (
//                           "—"
//                         )}
//                       </TableCell>
//                       <TableCell className="text-xs text-muted-foreground max-w-xs">
//                         {t.note ? truncate(t.note, 80) : "—"}
//                       </TableCell>
//                     </TableRow>
//                   );
//                 })}
//               </TableBody>
//             </Table>
//           )}
//         </CardContent>
//       </Card>

//       {/* ICP match results */}
//       {icpResult && (
//         <Card>
//           <CardHeader>
//             <div className="flex items-center justify-between">
//               <div>
//                 <CardTitle className="text-base">ICP Match Results</CardTitle>
//                 <CardDescription>
//                   {icpResult.checked} checked ·{" "}
//                   {icpResult.matches.filter((m) => m.is_icp_match).length}{" "}
//                   matches found
//                 </CardDescription>
//               </div>
//               <Button
//                 size="sm"
//                 variant="ghost"
//                 onClick={() => setIcpResult(null)}
//               >
//                 Dismiss
//               </Button>
//             </div>
//           </CardHeader>
//           <CardContent className="p-0">
//             {icpResult.matches.filter((m) => m.is_icp_match).length === 0 ? (
//               <p className="p-4 text-sm text-muted-foreground">
//                 No ICP matches found.
//               </p>
//             ) : (
//               <Table>
//                 <TableHeader>
//                   <TableRow>
//                     <TableHead>ICP Profile</TableHead>
//                     <TableHead>Match Reason</TableHead>
//                     <TableHead>Suggested Note</TableHead>
//                   </TableRow>
//                 </TableHeader>
//                 <TableBody>
//                   {icpResult.matches
//                     .filter((m) => m.is_icp_match)
//                     .map((m, i) => (
//                       <TableRow key={i}>
//                         <TableCell>
//                           <Badge variant="outline">
//                             {m.icp_profile_name ?? m.icp_profile_id ?? "—"}
//                           </Badge>
//                         </TableCell>
//                         <TableCell className="text-sm text-muted-foreground">
//                           {m.match_reason ? truncate(m.match_reason, 80) : "—"}
//                         </TableCell>
//                         <TableCell className="text-xs text-muted-foreground max-w-xs">
//                           {m.suggested_note
//                             ? truncate(m.suggested_note, 100)
//                             : "—"}
//                         </TableCell>
//                       </TableRow>
//                     ))}
//                 </TableBody>
//               </Table>
//             )}
//           </CardContent>
//         </Card>
//       )}

//       {/* New task dialog */}
//       <EngagementFormDialog
//         open={createOpen}
//         onClose={() => setCreateOpen(false)}
//         onSubmit={(body) => createMut.mutate(body)}
//         isPending={createMut.isPending}
//       />
//     </div>
//   );
// }

// function EngagementFormDialog({
//   open,
//   onClose,
//   onSubmit,
//   isPending,
// }: {
//   open: boolean;
//   onClose: () => void;
//   onSubmit: (body: {
//     prospectId: string | null;
//     action: string;
//     note: string | null;
//     scheduledAt: string | null;
//   }) => void;
//   isPending: boolean;
// }) {
//   const [action, setAction] = useState<EngagementAction>("connect");
//   const [scheduledAt, setScheduledAt] = useState("");
//   const [note, setNote] = useState("");

//   function submit() {
//     onSubmit({
//       prospectId: null,
//       action,
//       scheduledAt: scheduledAt ? new Date(scheduledAt).toISOString() : null,
//       note: note.trim() || null,
//     });
//     setAction("connect");
//     setScheduledAt("");
//     setNote("");
//   }

//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
//       <DialogContent>
//         <DialogHeader>
//           <DialogTitle>New Engagement Task</DialogTitle>
//           <DialogDescription>
//             Schedule a connect, message, view, or endorsement.
//           </DialogDescription>
//         </DialogHeader>
//         <div className="space-y-3">
//           <div className="grid grid-cols-2 gap-3">
//             <div className="space-y-1.5">
//               <Label>Action</Label>
//               <Select
//                 value={action}
//                 onValueChange={(v) => setAction(v as EngagementAction)}
//               >
//                 <SelectTrigger>
//                   <SelectValue />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="connect">Connect</SelectItem>
//                   <SelectItem value="message">Message</SelectItem>
//                   <SelectItem value="view">Profile View</SelectItem>
//                   <SelectItem value="endorse">Endorse</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>
//             <div className="space-y-1.5">
//               <Label htmlFor="eng-sched">Scheduled at</Label>
//               <Input
//                 id="eng-sched"
//                 type="datetime-local"
//                 value={scheduledAt}
//                 onChange={(e) => setScheduledAt(e.target.value)}
//               />
//             </div>
//           </div>
//           <div className="space-y-1.5">
//             <Label htmlFor="eng-note">Note / Message</Label>
//             <Textarea
//               id="eng-note"
//               rows={3}
//               placeholder="Hi {firstName} — saw your post…"
//               value={note}
//               onChange={(e) => setNote(e.target.value)}
//             />
//           </div>
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={onClose}>
//             Cancel
//           </Button>
//           <Button onClick={submit} disabled={isPending}>
//             {isPending ? (
//               <Loader2 className="h-4 w-4 animate-spin" />
//             ) : (
//               <Save className="h-4 w-4" />
//             )}
//             Create Task
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// /* ── LI-2 — Inbox tab ────────────────────────────────────────────────────── */

// function InboxTab() {
//   const qc = useQueryClient();
//   const [filter, setFilter] = useState<"all" | "unread" | "triaged">("all");
//   const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

//   const query = useQuery<LinkedInInboxMessageResponse[]>({
//     queryKey: ["linkedin-inbox"],
//     queryFn: () =>
//       http.get<LinkedInInboxMessageResponse[]>("/api/v1/linkedin/inbox"),
//     retry: false,
//   });

//   const allMessages = query.data ?? [];

//   const messages = useMemo(() => {
//     if (filter === "unread")
//       return allMessages.filter((m) => m.status === "unread");
//     if (filter === "triaged")
//       return allMessages.filter((m) => Boolean(m.triagedAt));
//     return allMessages;
//   }, [allMessages, filter]);

//   const triageMut = useMutation({
//     mutationFn: (ids: string[]) =>
//       http.post("/api/v1/linkedin/inbox/triage", {
//         messageIds: ids,
//         status: "converted_to_reply_draft",
//       }),
//     onSuccess: () => {
//       toast.success("Triage complete — replies drafted in Reply Inbox");
//       setSelectedIds(new Set());
//       qc.invalidateQueries({ queryKey: ["linkedin-inbox"] });
//     },
//     onError: () => toast.error("Triage failed"),
//   });

//   function toggleSelect(id: string) {
//     setSelectedIds((prev) => {
//       const next = new Set(prev);
//       if (next.has(id)) next.delete(id);
//       else next.add(id);
//       return next;
//     });
//   }

//   return (
//     <Card>
//       <CardHeader>
//         <div className="flex items-center justify-between gap-3 flex-wrap">
//           <div>
//             <CardTitle className="text-base">LinkedIn Inbox</CardTitle>
//             <CardDescription>
//               Triage messages to create reply drafts in Reply Inbox.
//             </CardDescription>
//           </div>
//           <div className="flex items-center gap-2">
//             {selectedIds.size > 0 && (
//               <Button
//                 size="sm"
//                 onClick={() => triageMut.mutate([...selectedIds])}
//                 disabled={triageMut.isPending}
//               >
//                 {triageMut.isPending ? (
//                   <Loader2 className="h-4 w-4 animate-spin" />
//                 ) : (
//                   <Sparkles className="h-4 w-4" />
//                 )}
//                 Triage {selectedIds.size} selected
//               </Button>
//             )}
//             <Button
//               size="sm"
//               variant="outline"
//               onClick={() =>
//                 qc.invalidateQueries({ queryKey: ["linkedin-inbox"] })
//               }
//             >
//               <RefreshCw className="h-4 w-4" />
//             </Button>
//             {/* Filter toggle */}
//             <div className="flex items-center gap-0.5 rounded-md border p-0.5">
//               {(["all", "unread", "triaged"] as const).map((f) => (
//                 <button
//                   key={f}
//                   type="button"
//                   onClick={() => setFilter(f)}
//                   className={cn(
//                     "rounded-sm px-3 py-1 text-xs font-medium capitalize transition-colors",
//                     filter === f
//                       ? "bg-background text-foreground shadow-sm"
//                       : "text-muted-foreground"
//                   )}
//                 >
//                   {f}
//                 </button>
//               ))}
//             </div>
//           </div>
//         </div>
//       </CardHeader>
//       <CardContent className="p-0">
//         {query.isLoading ? (
//           <div className="space-y-2 p-4">
//             {Array.from({ length: 4 }).map((_, i) => (
//               <Skeleton key={i} className="h-20 w-full" />
//             ))}
//           </div>
//         ) : messages.length === 0 ? (
//           <EmptyState
//             icon={<InboxIcon className="h-6 w-6" />}
//             title="No messages"
//             description="LinkedIn inbox is empty for this filter."
//             className="py-8"
//           />
//         ) : (
//           <ul className="divide-y">
//             {messages.map((m) => {
//               const isTriaged = Boolean(m.triagedAt);
//               const isSelected = selectedIds.has(m.id);
//               return (
//                 <li
//                   key={m.id}
//                   className={cn(
//                     "flex items-start gap-3 p-4 cursor-pointer hover:bg-muted/30 transition-colors",
//                     isSelected && "bg-primary/5"
//                   )}
//                   onClick={() => !isTriaged && toggleSelect(m.id)}
//                 >
//                   <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 text-xs font-semibold">
//                     {m.senderName.slice(0, 2).toUpperCase()}
//                   </div>
//                   <div className="min-w-0 flex-1 space-y-0.5">
//                     <div className="flex items-center justify-between gap-2">
//                       <p className="text-sm font-medium truncate">
//                         {m.senderName}
//                       </p>
//                       <span className="shrink-0 text-xs text-muted-foreground">
//                         {timeAgo(m.receivedAt)}
//                       </span>
//                     </div>
//                     {m.senderHandle && (
//                       <p className="text-xs text-muted-foreground">
//                         {m.senderHandle}
//                       </p>
//                     )}
//                     <p className="text-sm text-muted-foreground">
//                       {truncate(m.body, 180)}
//                     </p>
//                     <div className="flex items-center gap-2 pt-1">
//                       {isTriaged ? (
//                         <Badge
//                           variant="outline"
//                           className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200"
//                         >
//                           Triaged {m.triagedAt ? timeAgo(m.triagedAt) : ""}
//                         </Badge>
//                       ) : (
//                         <Badge variant="outline" className="text-xs">
//                           {m.status}
//                         </Badge>
//                       )}
//                     </div>
//                   </div>
//                   {!isTriaged && (
//                     <Button
//                       size="sm"
//                       variant={isSelected ? "default" : "outline"}
//                       className="shrink-0"
//                       onClick={(e) => {
//                         e.stopPropagation();
//                         triageMut.mutate([m.id]);
//                       }}
//                       disabled={triageMut.isPending}
//                     >
//                       <Sparkles className="h-4 w-4" />
//                       Triage
//                     </Button>
//                   )}
//                 </li>
//               );
//             })}
//           </ul>
//         )}
//       </CardContent>
//     </Card>
//   );
// }

/**
 * LinkedInPage.tsx — LinkedIn config + engagement + inbox.
 *
 * Gaps closed:
 *   LI-1  Connection status card — shows active accounts, connect/disconnect.
 *         Uses cookieJar (li_at session cookie), not accessToken.
 *   LI-2  Inbox tab — LinkedIn message inbox with triage button
 *         POST /api/v1/linkedin/inbox/triage { messageIds, status }
 *   LI-3  Engagement tab — ICP-matched engagement tasks,
 *         POST /api/v1/linkedin/engagements/check-icp
 *   LI-4  Dormant state — "LinkedIn Integration is Dormant" empty state
 *         with feature preview cards + setup instructions
 *
 * API contracts (linkedin.py schemas):
 *   LinkedInConfigResponse: { id, accountName, accountHandle, isActive,
 *     syncStatus, lastSyncedAt, createdAt, updatedAt }
 *   LinkedInEngagementResponse: { id, prospectId, icpProfileId, action,
 *     note, status, scheduledAt, executedAt, owner_user_id, createdAt }
 *   LinkedInInboxMessageResponse: { id, prospectId, senderName,
 *     senderHandle, body, status, receivedAt, triagedAt, createdAt }
 *   IcpMatchResponse: { success, checked, matches: IcpMatchResult[] }
 *   IcpMatchResult: { engagement_id, is_icp_match, icp_profile_id,
 *     icp_profile_name, match_reason, suggested_note }
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  CheckCircle2,
  Clock,
  Heart,
  Inbox as InboxIcon,
  Linkedin,
  Loader2,
  MessageSquare,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Target,
  Trash2,
  UserPlus,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatDateTime, timeAgo, truncate } from "@/lib/utils";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

/* ── Backend types (linkedin.py) ────────────────────────────────────────── */

interface LinkedInConfigResponse {
  id: string;
  accountName: string;
  accountHandle: string | null;
  isActive: boolean;
  syncStatus: string;
  lastSyncedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

type EngagementAction = "connect" | "message" | "view" | "endorse";

interface LinkedInEngagementResponse {
  id: string;
  prospectId: string | null;
  icpProfileId: string | null;
  action: string;
  note: string | null;
  status: string;
  scheduledAt: string | null;
  executedAt: string | null;
  owner_user_id: string | null;
  createdAt: string;
  updatedAt: string;
}

interface LinkedInInboxMessageResponse {
  id: string;
  prospectId: string | null;
  senderName: string;
  senderHandle: string | null;
  body: string;
  status: string; // unread | read | archived | converted_to_reply_draft
  receivedAt: string;
  triagedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

interface IcpMatchResult {
  engagement_id: string;
  is_icp_match: boolean;
  icp_profile_id: string | null;
  icp_profile_name: string | null;
  match_reason: string | null;
  suggested_note: string | null;
}

interface IcpMatchResponse {
  success: boolean;
  checked: number;
  matches: IcpMatchResult[];
  error: string | null;
}

/* ── Action / status metadata ────────────────────────────────────────────── */

const ACTION_META: Record<
  string,
  { label: string; icon: React.ElementType; color: string }
> = {
  connect: { label: "Connect", icon: UserPlus, color: "text-blue-600" },
  message: { label: "Message", icon: MessageSquare, color: "text-violet-600" },
  view: { label: "View", icon: Heart, color: "text-rose-500" },
  endorse: { label: "Endorse", icon: CheckCircle2, color: "text-emerald-600" },
};

const STATUS_CHIP: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700",
  scheduled: "bg-amber-100 text-amber-700",
  done: "bg-emerald-100 text-emerald-700",
  failed: "bg-rose-100 text-rose-700",
};

/* ── Page ───────────────────────────────────────────────────────────────── */

export function LinkedInPage() {
  const [tab, setTab] = useState("config");

  return (
    <div className="space-y-6">
      <PageHeader
        title="LinkedIn Hub"
        description="Manage LinkedIn accounts, schedule engagement tasks, and triage inbox messages."
      />

      <Alert>
        <Linkedin className="h-4 w-4" />
        <AlertTitle>Companion channel — runs in parallel to email</AlertTitle>
        <AlertDescription>
          LinkedIn engagement layers connection requests, messages, and likes on
          top of email sequences for the same prospects. Triage LinkedIn replies
          manually in the Inbox tab — they are not auto-synced to Reply Inbox.
        </AlertDescription>
      </Alert>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="config">
            <Linkedin className="mr-1.5 h-4 w-4" />
            Accounts
          </TabsTrigger>
          <TabsTrigger value="engagement">
            <Target className="mr-1.5 h-4 w-4" />
            Engagement
          </TabsTrigger>
          <TabsTrigger value="inbox">
            <InboxIcon className="mr-1.5 h-4 w-4" />
            Inbox
          </TabsTrigger>
        </TabsList>
        <TabsContent value="config" className="mt-4">
          <ConfigTab />
        </TabsContent>
        <TabsContent value="engagement" className="mt-4">
          <EngagementTab />
        </TabsContent>
        <TabsContent value="inbox" className="mt-4">
          <InboxTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ── LI-1 — Config tab ───────────────────────────────────────────────────── */

function ConfigTab() {
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] =
    useState<LinkedInConfigResponse | null>(null);
  const [deleteTarget, setDeleteTarget] =
    useState<LinkedInConfigResponse | null>(null);

  const query = useQuery<LinkedInConfigResponse[]>({
    queryKey: ["linkedin-config"],
    queryFn: () =>
      http.get<LinkedInConfigResponse[]>("/api/v1/linkedin/config"),
    retry: false,
  });

  const accounts = query.data ?? [];
  const hasAccounts = accounts.length > 0;

  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/linkedin/config/${id}`),
    onSuccess: () => {
      toast.success("Account removed");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["linkedin-config"] });
    },
    onError: () => toast.error("Failed to remove account"),
  });

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["linkedin-config"] });
  }

  return (
    <>
      {/* LI-4 — Dormant state when no accounts */}
      {!query.isLoading && !hasAccounts && (
        <Card className="border-dashed border-2 border-muted-foreground/20 mb-4">
          <CardContent className="py-10 flex flex-col items-center text-center space-y-4">
            <div className="h-14 w-14 rounded-full bg-blue-100 flex items-center justify-center">
              <Linkedin className="h-7 w-7 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold">LinkedIn Integration is Dormant</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-md">
                Connect your LinkedIn account using a session cookie (li_at) to
                enable inbox triage, ICP engagement checking, and connection
                outreach. All LinkedIn features remain inactive until you add an
                account.
              </p>
            </div>
            <Button onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" /> Add LinkedIn Account
            </Button>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-lg mt-2 opacity-60">
              {[
                {
                  icon: <InboxIcon className="h-5 w-5" />,
                  title: "Inbox Triage",
                  desc: "Sort messages into positive, neutral, negative, or needs-follow-up.",
                },
                {
                  icon: <Target className="h-5 w-5" />,
                  title: "ICP Engagement",
                  desc: "Review engagements, flag ICP matches, generate connection notes.",
                },
                {
                  icon: <BarChart3 className="h-5 w-5" />,
                  title: "Weekly Recap",
                  desc: "Track connections accepted and conversations started.",
                },
              ].map((f, i) => (
                <Card key={i}>
                  <CardContent className="p-3">
                    <div className="text-muted-foreground mb-2">{f.icon}</div>
                    <p className="text-xs font-medium">{f.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {f.desc}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">LinkedIn Accounts</CardTitle>
              <CardDescription>
                Authenticated sessions used for engagement and inbox access.
              </CardDescription>
            </div>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" /> Add Account
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {query.isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !hasAccounts ? (
            <EmptyState
              icon={<Linkedin className="h-6 w-6" />}
              title="No accounts yet"
              description='Click "Add Account" above to connect your first LinkedIn account.'
              className="py-8"
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Account</TableHead>
                  <TableHead>Handle</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Sync</TableHead>
                  <TableHead>Last synced</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((acc) => (
                  <TableRow key={acc.id}>
                    <TableCell className="font-medium">
                      {acc.accountName}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {acc.accountHandle ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={acc.isActive ? "default" : "secondary"}
                        className={
                          acc.isActive
                            ? "bg-emerald-100 text-emerald-700 border-emerald-200"
                            : ""
                        }
                      >
                        {acc.isActive ? "Active" : "Paused"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs capitalize">
                        {acc.syncStatus}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {acc.lastSyncedAt ? timeAgo(acc.lastSyncedAt) : "Never"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          onClick={() => setEditTarget(acc)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-destructive"
                          onClick={() => setDeleteTarget(acc)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Add / Edit dialog */}
      <AccountFormDialog
        open={addOpen || Boolean(editTarget)}
        editing={editTarget}
        onClose={() => {
          setAddOpen(false);
          setEditTarget(null);
        }}
        onSaved={invalidate}
      />

      {/* Delete dialog */}
      <Dialog
        open={Boolean(deleteTarget)}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove LinkedIn account?</DialogTitle>
            <DialogDescription>
              "{deleteTarget?.accountName}" and its stored session will be
              permanently removed. Scheduled engagement tasks will be cancelled.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Removing…" : "Remove"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function AccountFormDialog({
  open,
  editing,
  onClose,
  onSaved,
}: {
  open: boolean;
  editing: LinkedInConfigResponse | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [accountName, setAccountName] = useState("");
  const [accountHandle, setAccountHandle] = useState("");
  const [cookieJar, setCookieJar] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);

  useMemo(() => {
    setAccountName(editing?.accountName ?? "");
    setAccountHandle(editing?.accountHandle ?? "");
    setCookieJar("");
    setIsActive(editing?.isActive ?? true);
  }, [editing, open]);

  async function submit() {
    if (!accountName.trim()) return;
    setSaving(true);
    try {
      const payload = {
        accountName: accountName.trim(),
        accountHandle: accountHandle.trim() || null,
        isActive,
        cookieJar: cookieJar.trim() || null,
      };
      if (editing) {
        await http.put(`/api/v1/linkedin/config/${editing.id}`, payload);
        toast.success("Account updated");
      } else {
        await http.post("/api/v1/linkedin/config", payload);
        toast.success("Account added");
      }
      onSaved();
      onClose();
    } catch {
      toast.error("Failed to save account");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {editing ? "Edit Account" : "Add LinkedIn Account"}
          </DialogTitle>
          <DialogDescription>
            Provide the account email and LinkedIn session cookie (li_at) to
            authenticate.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="acc-name">Account Email *</Label>
            <Input
              id="acc-name"
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
              placeholder="you@company.com"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="acc-handle">LinkedIn Handle (optional)</Label>
            <Input
              id="acc-handle"
              value={accountHandle}
              onChange={(e) => setAccountHandle(e.target.value)}
              placeholder="e.g. in/yourname"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="acc-cookie">
              Session Cookie (li_at){" "}
              <span className="text-muted-foreground text-xs">
                — leave blank to keep existing
              </span>
            </Label>
            <Input
              id="acc-cookie"
              type="password"
              value={cookieJar}
              onChange={(e) => setCookieJar(e.target.value)}
              placeholder="paste li_at cookie value…"
            />
          </div>
          <div className="flex items-center gap-3">
            <Switch checked={isActive} onCheckedChange={setIsActive} />
            <Label>{isActive ? "Active" : "Paused"}</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={saving || !accountName.trim()}
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {editing ? "Save" : "Add Account"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── LI-3 — Engagement tab ───────────────────────────────────────────────── */

function EngagementTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [icpResult, setIcpResult] = useState<IcpMatchResponse | null>(null);

  const query = useQuery<LinkedInEngagementResponse[]>({
    queryKey: ["linkedin-engagements"],
    queryFn: () =>
      http.get<LinkedInEngagementResponse[]>("/api/v1/linkedin/engagements"),
    retry: false,
  });

  const tasks = query.data ?? [];

  const createMut = useMutation({
    mutationFn: (body: {
      prospectId: string | null;
      action: string;
      note: string | null;
      scheduledAt: string | null;
    }) => http.post<LinkedInEngagementResponse>("/api/v1/linkedin/engagements", body),
    onSuccess: () => {
      toast.success("Engagement task created");
      setCreateOpen(false);
      qc.invalidateQueries({ queryKey: ["linkedin-engagements"] });
    },
    onError: () => toast.error("Failed to create task"),
  });

  const icpCheckMut = useMutation({
    mutationFn: () =>
      http.post<IcpMatchResponse>("/api/v1/linkedin/engagements/check-icp", {}),
    onSuccess: (data) => {
      setIcpResult(data);
      if (data.success) {
        const n = data.matches.filter((m) => m.is_icp_match).length;
        toast.success(`ICP check complete: ${n} match(es) found`);
      } else {
        toast.error(data.error ?? "ICP check failed");
      }
    },
    onError: () => toast.error("ICP check failed"),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Engagement Tasks</CardTitle>
              <CardDescription>
                Scheduled connects, messages, and profile views.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => icpCheckMut.mutate()}
                disabled={icpCheckMut.isPending}
              >
                {icpCheckMut.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Target className="h-4 w-4" />
                )}
                Check ICP Matches
              </Button>
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" /> New Task
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {query.isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <EmptyState
              icon={<Target className="h-6 w-6" />}
              title="No engagement tasks"
              description='Create a task to schedule a connect, message, or profile view.'
              className="py-8"
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Action</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Scheduled</TableHead>
                  <TableHead>Note</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((t) => {
                  const meta = ACTION_META[t.action] ?? ACTION_META.connect;
                  const Icon = meta.icon;
                  return (
                    <TableRow key={t.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Icon className={cn("h-4 w-4", meta.color)} />
                          <span className="text-sm font-medium capitalize">
                            {meta.label}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize",
                            STATUS_CHIP[t.status] ?? STATUS_CHIP.pending
                          )}
                        >
                          {t.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {t.scheduledAt ? (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDateTime(t.scheduledAt)}
                          </span>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-xs">
                        {t.note ? truncate(t.note, 80) : "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ICP match results */}
      {icpResult && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">ICP Match Results</CardTitle>
                <CardDescription>
                  {icpResult.checked} checked ·{" "}
                  {icpResult.matches.filter((m) => m.is_icp_match).length}{" "}
                  matches found
                </CardDescription>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setIcpResult(null)}
              >
                Dismiss
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {icpResult.matches.filter((m) => m.is_icp_match).length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">
                No ICP matches found.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ICP Profile</TableHead>
                    <TableHead>Match Reason</TableHead>
                    <TableHead>Suggested Note</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {icpResult.matches
                    .filter((m) => m.is_icp_match)
                    .map((m, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          <Badge variant="outline">
                            {m.icp_profile_name ?? m.icp_profile_id ?? "—"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {m.match_reason ? truncate(m.match_reason, 80) : "—"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground max-w-xs">
                          {m.suggested_note
                            ? truncate(m.suggested_note, 100)
                            : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* New task dialog */}
      <EngagementFormDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={(body) => createMut.mutate(body)}
        isPending={createMut.isPending}
      />
    </div>
  );
}

function EngagementFormDialog({
  open,
  onClose,
  onSubmit,
  isPending,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (body: {
    prospectId: string | null;
    action: string;
    note: string | null;
    scheduledAt: string | null;
  }) => void;
  isPending: boolean;
}) {
  const [action, setAction] = useState<EngagementAction>("connect");
  const [scheduledAt, setScheduledAt] = useState("");
  const [note, setNote] = useState("");

  function submit() {
    onSubmit({
      prospectId: null,
      action,
      scheduledAt: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      note: note.trim() || null,
    });
    setAction("connect");
    setScheduledAt("");
    setNote("");
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Engagement Task</DialogTitle>
          <DialogDescription>
            Schedule a connect, message, view, or endorsement.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Action</Label>
              <Select
                value={action}
                onValueChange={(v) => setAction(v as EngagementAction)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="connect">Connect</SelectItem>
                  <SelectItem value="message">Message</SelectItem>
                  <SelectItem value="view">Profile View</SelectItem>
                  <SelectItem value="endorse">Endorse</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="eng-sched">Scheduled at</Label>
              <Input
                id="eng-sched"
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="eng-note">Note / Message</Label>
            <Textarea
              id="eng-note"
              rows={3}
              placeholder="Hi {firstName} — saw your post…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={isPending}>
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Create Task
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── LI-2 — Inbox tab ────────────────────────────────────────────────────── */

function InboxTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | "unread" | "triaged">("all");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const query = useQuery<LinkedInInboxMessageResponse[]>({
    queryKey: ["linkedin-inbox"],
    queryFn: () =>
      http.get<LinkedInInboxMessageResponse[]>("/api/v1/linkedin/inbox"),
    retry: false,
  });

  const allMessages = query.data ?? [];

  const messages = useMemo(() => {
    if (filter === "unread")
      return allMessages.filter((m) => m.status === "unread");
    if (filter === "triaged")
      return allMessages.filter((m) => Boolean(m.triagedAt));
    return allMessages;
  }, [allMessages, filter]);

  const triageMut = useMutation({
    mutationFn: (ids: string[]) =>
      http.post("/api/v1/linkedin/inbox/triage", {
        messageIds: ids,
        status: "converted_to_reply_draft",
      }),
    onSuccess: () => {
      toast.success("Triage complete — replies drafted in Reply Inbox");
      setSelectedIds(new Set());
      qc.invalidateQueries({ queryKey: ["linkedin-inbox"] });
    },
    onError: () => toast.error("Triage failed"),
  });

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="space-y-2">
            <CardTitle className="text-base">LinkedIn Inbox</CardTitle>
            <CardDescription>
              Triage messages to create reply drafts in Reply Inbox.
            </CardDescription>
            {/* Status breakdown chips */}
            {allMessages.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap pt-1">
                {([
                  { label: "Unread",   statuses: ["unread"],                   cls: "bg-blue-100 text-blue-700 border-blue-200" },
                  { label: "Read",     statuses: ["read"],                      cls: "bg-gray-100 text-gray-600 border-gray-200" },
                  { label: "Triaged",  statuses: ["converted_to_reply_draft"],  cls: "bg-emerald-100 text-emerald-700 border-emerald-200" },
                  { label: "Archived", statuses: ["archived"],                  cls: "bg-amber-100 text-amber-700 border-amber-200" },
                ] as const).map(({ label, statuses, cls }) => {
                  const count = allMessages.filter((m) => (statuses as readonly string[]).includes(m.status)).length;
                  if (count === 0) return null;
                  return (
                    <span key={label} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}>
                      {label} <span className="font-bold">{count}</span>
                    </span>
                  );
                })}
                <span className="text-[11px] text-muted-foreground">{allMessages.length} total</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {selectedIds.size > 0 && (
              <Button
                size="sm"
                onClick={() => triageMut.mutate([...selectedIds])}
                disabled={triageMut.isPending}
              >
                {triageMut.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                Triage {selectedIds.size} selected
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                qc.invalidateQueries({ queryKey: ["linkedin-inbox"] })
              }
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            {/* Filter toggle */}
            <div className="flex items-center gap-0.5 rounded-md border p-0.5">
              {(["all", "unread", "triaged"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={cn(
                    "rounded-sm px-3 py-1 text-xs font-medium capitalize transition-colors",
                    filter === f
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground"
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {query.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : messages.length === 0 ? (
          <EmptyState
            icon={<InboxIcon className="h-6 w-6" />}
            title="No messages"
            description="LinkedIn inbox is empty for this filter."
            className="py-8"
          />
        ) : (
          <ul className="divide-y">
            {messages.map((m) => {
              const isTriaged = Boolean(m.triagedAt);
              const isSelected = selectedIds.has(m.id);
              return (
                <li
                  key={m.id}
                  className={cn(
                    "flex items-start gap-3 p-4 cursor-pointer hover:bg-muted/30 transition-colors",
                    isSelected && "bg-primary/5"
                  )}
                  onClick={() => !isTriaged && toggleSelect(m.id)}
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 text-xs font-semibold">
                    {m.senderName.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium truncate">
                        {m.senderName}
                      </p>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {timeAgo(m.receivedAt)}
                      </span>
                    </div>
                    {m.senderHandle && (
                      <p className="text-xs text-muted-foreground">
                        {m.senderHandle}
                      </p>
                    )}
                    <p className="text-sm text-muted-foreground">
                      {truncate(m.body, 180)}
                    </p>
                    <div className="flex items-center gap-2 pt-1">
                      {isTriaged ? (
                        <Badge
                          variant="outline"
                          className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200"
                        >
                          Triaged {m.triagedAt ? timeAgo(m.triagedAt) : ""}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs">
                          {m.status}
                        </Badge>
                      )}
                    </div>
                  </div>
                  {!isTriaged && (
                    <Button
                      size="sm"
                      variant={isSelected ? "default" : "outline"}
                      className="shrink-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        triageMut.mutate([m.id]);
                      }}
                      disabled={triageMut.isPending}
                    >
                      <Sparkles className="h-4 w-4" />
                      Triage
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}