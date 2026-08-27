// // /**
// //  * MailBridgePage.tsx — FIX-FE-1
// //  *
// //  * Per-tenant MailBridge config CRUD (SMTP / Gmail / Outlook relay settings).
// //  * Targets `GET/POST/PUT/DELETE /api/v1/mailbridge/config` + `POST /mailbridge/send`
// //  * for the optional "send test email" action.
// //  */
// // import { useState } from "react";
// // import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// // import {
// //   Mail,
// //   Pencil,
// //   Plus,
// //   RefreshCw,
// //   Send,
// //   Trash2,
// // } from "lucide-react";
// // import { toast } from "sonner";

// // import { mailbridgeApi, http } from "@/services/apiClient";
// // import type { MailBridgeConfig, MailBridgeConfigInput } from "@/types/common";
// // import { Badge } from "@/components/ui/badge";
// // import { Button } from "@/components/ui/button";
// // import { Card, CardContent } from "@/components/ui/card";
// // import {
// //   Dialog,
// //   DialogClose,
// //   DialogDescription,
// //   DialogFooter,
// //   DialogHeader,
// //   DialogTitle,
// // } from "@/components/ui/dialog";
// // import { EmptyState } from "@/components/ui/empty-state";
// // import { Input } from "@/components/ui/input";
// // import { Label } from "@/components/ui/label";
// // import { NativeSelect as Select } from "@/components/ui/select";
// // import { PageHeader } from "@/components/ui/page-header";
// // import { Skeleton } from "@/components/ui/skeleton";
// // import { Switch } from "@/components/ui/switch";
// // import {
// //   Table,
// //   TableBody,
// //   TableCell,
// //   TableHead,
// //   TableHeader,
// //   TableRow,
// // } from "@/components/ui/table";
// // import {
// //   Tooltip,
// //   TooltipContent,
// //   TooltipProvider,
// //   TooltipTrigger,
// // } from "@/components/ui/tooltip";
// // import { formatDateTime } from "@/lib/utils";

// // const PROVIDERS = ["gmail", "smtp", "outlook", "sendgrid", "ses"] as const;

// // interface DomainLite {
// //   id: string;
// //   domain: string;
// // }

// // interface FormState {
// //   id?: string;
// //   name: string;
// //   baseUrl: string;
// //   provider: string;
// //   fromEmail: string;
// //   fromName: string;
// //   isActive: boolean;
// //   webhookSecret: string;
// //   domainId: string;
// // }

// // const EMPTY_FORM: FormState = {
// //   name: "",
// //   baseUrl: "",
// //   provider: "gmail",
// //   fromEmail: "",
// //   fromName: "",
// //   isActive: true,
// //   webhookSecret: "",
// //   domainId: "",
// // };

// // export function MailBridgePage() {
// //   const qc = useQueryClient();
// //   const [editorOpen, setEditorOpen] = useState(false);
// //   const [deleteTarget, setDeleteTarget] = useState<MailBridgeConfig | null>(null);
// //   const [form, setForm] = useState<FormState>(EMPTY_FORM);

// //   const { data: configs, isLoading, isError, error, refetch } = useQuery({
// //     queryKey: ["mailbridge", "configs"],
// //     queryFn: () => mailbridgeApi.list(),
// //     retry: false,
// //   });

// //   const { data: domains } = useQuery<DomainLite[]>({
// //     queryKey: ["domains"],
// //     queryFn: () => http.get("/api/v1/domains"),
// //     retry: false,
// //   });

// //   const createMut = useMutation({
// //     mutationFn: (body: MailBridgeConfigInput) => mailbridgeApi.create(body),
// //     onSuccess: () => {
// //       toast.success("MailBridge config created");
// //       qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
// //       closeEditor();
// //     },
// //     onError: () => toast.error("Failed to create MailBridge config"),
// //   });

// //   const updateMut = useMutation({
// //     mutationFn: ({ id, body }: { id: string; body: Partial<MailBridgeConfigInput> }) =>
// //       mailbridgeApi.update(id, body),
// //     onSuccess: () => {
// //       toast.success("MailBridge config saved");
// //       qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
// //       closeEditor();
// //     },
// //     onError: () => toast.error("Failed to save MailBridge config"),
// //   });

// //   const deleteMut = useMutation({
// //     mutationFn: (id: string) => mailbridgeApi.remove(id),
// //     onSuccess: () => {
// //       toast.success("MailBridge config deleted");
// //       qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
// //       setDeleteTarget(null);
// //     },
// //     onError: () => toast.error("Failed to delete config"),
// //   });

// //   const testMut = useMutation({
// //     mutationFn: (config: MailBridgeConfig) =>
// //       mailbridgeApi.sendTest({
// //         to: config.fromEmail,
// //         subject: "OUTRENA MailBridge test",
// //         body: "This is a test email from OUTRENA MailBridge.",
// //         configId: config.id,
// //       }),
// //     onSuccess: (res) => {
// //       qc.invalidateQueries({ queryKey: ["mailbridge-configs"] });
// //       if (res.accepted) {
// //         toast.success(`Test email sent (messageId: ${res.messageId})`);
// //       } else {
// //         toast.error(`Test email rejected (status: ${res.status})`);
// //       }
// //     },
// //     onError: () => toast.error("Failed to send test email"),
// //   });

// //   function openNew() {
// //     setForm(EMPTY_FORM);
// //     setEditorOpen(true);
// //   }
// //   function openEdit(c: MailBridgeConfig) {
// //     setForm({
// //       id: c.id,
// //       name: c.name,
// //       baseUrl: c.baseUrl,
// //       provider: c.provider,
// //       fromEmail: c.fromEmail,
// //       fromName: c.fromName ?? "",
// //       isActive: c.isActive,
// //       webhookSecret: c.webhookSecret ?? "",
// //       domainId: c.domainId ?? "",
// //     });
// //     setEditorOpen(true);
// //   }
// //   function closeEditor() {
// //     setEditorOpen(false);
// //     setForm(EMPTY_FORM);
// //   }

// //   function handleSave() {
// //     if (!form.name.trim() || !form.baseUrl.trim() || !form.fromEmail.trim()) {
// //       toast.error("Name, Base URL, and From Email are required");
// //       return;
// //     }
// //     const body: MailBridgeConfigInput = {
// //       name: form.name.trim(),
// //       baseUrl: form.baseUrl.trim(),
// //       provider: form.provider,
// //       fromEmail: form.fromEmail.trim(),
// //       fromName: form.fromName.trim() || null,
// //       isActive: form.isActive,
// //       webhookSecret: form.webhookSecret.trim() || null,
// //       domainId: form.domainId || null,
// //     };
// //     if (form.id) {
// //       updateMut.mutate({ id: form.id, body });
// //     } else {
// //       createMut.mutate(body);
// //     }
// //   }

// //   return (
// //     <TooltipProvider delayDuration={200}>
// //       <div className="space-y-6">
// //         <PageHeader
// //           title="MailBridge Config"
// //           description="Tenant-wide SMTP / Gmail / Outlook relay settings used by the scheduler to send and receive email."
// //           actions={
// //             <>
// //               <Button variant="outline" onClick={() => refetch()}>
// //                 <RefreshCw className="h-4 w-4" />
// //                 Refresh
// //               </Button>
// //               <Button onClick={openNew}>
// //                 <Plus className="h-4 w-4" />
// //                 New Config
// //               </Button>
// //             </>
// //           }
// //         />

// //         <Card>
// //           <CardContent className="p-0">
// //             {isError ? (
// //               <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
// //                 <p className="text-sm font-medium">Failed to load MailBridge configs</p>
// //                 <p className="text-xs text-muted-foreground">
// //                   {(error as Error)?.message ?? "Unknown error"}
// //                 </p>
// //                 <Button variant="outline" onClick={() => refetch()}>
// //                   Retry
// //                 </Button>
// //               </div>
// //             ) : isLoading ? (
// //               <div className="space-y-2 p-4">
// //                 {Array.from({ length: 4 }).map((_, i) => (
// //                   <Skeleton key={i} className="h-12 w-full" />
// //                 ))}
// //               </div>
// //             ) : !configs || configs.length === 0 ? (
// //               <EmptyState
// //                 icon={<Mail className="h-6 w-6" />}
// //                 title="No MailBridge configs yet"
// //                 description="Add your first SMTP / Gmail / Outlook relay config so the scheduler can send email."
// //                 action={
// //                   <Button onClick={openNew}>
// //                     <Plus className="h-4 w-4" /> New Config
// //                   </Button>
// //                 }
// //               />
// //             ) : (
// //               <Table>
// //                 <TableHeader>
// //                   <TableRow>
// //                     <TableHead>Name</TableHead>
// //                     <TableHead>Provider</TableHead>
// //                     <TableHead>From Email</TableHead>
// //                     <TableHead>Domain</TableHead>
// //                     <TableHead>Active</TableHead>
// //                     <TableHead>Last Updated</TableHead>
// //                     <TableHead className="text-right">Actions</TableHead>
// //                   </TableRow>
// //                 </TableHeader>
// //                 <TableBody>
// //                   {configs.map((c) => {
// //                     const domain = domains?.find((d) => d.id === c.domainId);
// //                     return (
// //                       <TableRow key={c.id}>
// //                         <TableCell className="font-medium">{c.name}</TableCell>
// //                         <TableCell>
// //                           <Badge variant="secondary">{c.provider}</Badge>
// //                         </TableCell>
// //                         <TableCell className="text-muted-foreground">{c.fromEmail}</TableCell>
// //                         <TableCell className="text-muted-foreground">
// //                           {domain?.domain ?? "—"}
// //                         </TableCell>
// //                         <TableCell>
// //                           <Badge variant={c.isActive ? "success" : "outline"}>
// //                             {c.isActive ? "Active" : "Inactive"}
// //                           </Badge>
// //                         </TableCell>
// //                         <TableCell className="text-xs text-muted-foreground">
// //                           {formatDateTime(c.updatedAt)}
// //                         </TableCell>
// //                         <TableCell className="text-right">
// //                           <div className="flex justify-end gap-1">
// //                             <Tooltip>
// //                               <TooltipTrigger asChild>
// //                                 <Button
// //                                   variant="ghost"
// //                                   size="icon"
// //                                   aria-label="Send test email"
// //                                   onClick={() => testMut.mutate(c)}
// //                                   disabled={testMut.isPending}
// //                                 >
// //                                   <Send className="h-4 w-4" />
// //                                 </Button>
// //                               </TooltipTrigger>
// //                               <TooltipContent>Send test email</TooltipContent>
// //                             </Tooltip>
// //                             <Tooltip>
// //                               <TooltipTrigger asChild>
// //                                 <Button
// //                                   variant="ghost"
// //                                   size="icon"
// //                                   aria-label="Edit config"
// //                                   onClick={() => openEdit(c)}
// //                                 >
// //                                   <Pencil className="h-4 w-4" />
// //                                 </Button>
// //                               </TooltipTrigger>
// //                               <TooltipContent>Edit</TooltipContent>
// //                             </Tooltip>
// //                             <Tooltip>
// //                               <TooltipTrigger asChild>
// //                                 <Button
// //                                   variant="ghost"
// //                                   size="icon"
// //                                   aria-label="Delete config"
// //                                   onClick={() => setDeleteTarget(c)}
// //                                 >
// //                                   <Trash2 className="h-4 w-4" />
// //                                 </Button>
// //                               </TooltipTrigger>
// //                               <TooltipContent>Delete</TooltipContent>
// //                             </Tooltip>
// //                           </div>
// //                         </TableCell>
// //                       </TableRow>
// //                     );
// //                   })}
// //                 </TableBody>
// //               </Table>
// //             )}
// //           </CardContent>
// //         </Card>

// //         {/* Editor dialog */}
// //         <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
// //           <DialogClose onClose={closeEditor} />
// //           <DialogHeader>
// //             <DialogTitle>{form.id ? "Edit MailBridge Config" : "New MailBridge Config"}</DialogTitle>
// //             <DialogDescription>
// //               Configure the SMTP / Gmail / Outlook relay used to send outbound email and receive tracking webhooks.
// //             </DialogDescription>
// //           </DialogHeader>
// //           <div className="space-y-4">
// //             <div className="space-y-2">
// //               <Label htmlFor="mb-name">Name</Label>
// //               <Input
// //                 id="mb-name"
// //                 required
// //                 value={form.name}
// //                 onChange={(e) => setForm({ ...form, name: e.target.value })}
// //                 placeholder="e.g. Primary SMTP relay"
// //               />
// //             </div>
// //             <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
// //               <div className="space-y-2">
// //                 <Label htmlFor="mb-provider">Provider</Label>
// //                 <Select
// //                   id="mb-provider"
// //                   value={form.provider}
// //                   onChange={(e) => setForm({ ...form, provider: e.target.value })}
// //                 >
// //                   {PROVIDERS.map((p) => (
// //                     <option key={p} value={p}>
// //                       {p}
// //                     </option>
// //                   ))}
// //                 </Select>
// //               </div>
// //               <div className="space-y-2">
// //                 <Label htmlFor="mb-domain">Domain (optional)</Label>
// //                 <Select
// //                   id="mb-domain"
// //                   value={form.domainId}
// //                   onChange={(e) => setForm({ ...form, domainId: e.target.value })}
// //                 >
// //                   <option value="">— Tenant-wide —</option>
// //                   {(domains ?? []).map((d) => (
// //                     <option key={d.id} value={d.id}>
// //                       {d.domain}
// //                     </option>
// //                   ))}
// //                 </Select>
// //               </div>
// //             </div>
// //             <div className="space-y-2">
// //               <Label htmlFor="mb-baseurl">Base URL</Label>
// //               <Input
// //                 id="mb-baseurl"
// //                 required
// //                 value={form.baseUrl}
// //                 onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
// //                 placeholder="https://mailbridge.example.com"
// //               />
// //             </div>
// //             <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
// //               <div className="space-y-2">
// //                 <Label htmlFor="mb-fromemail">From Email</Label>
// //                 <Input
// //                   id="mb-fromemail"
// //                   required
// //                   type="email"
// //                   value={form.fromEmail}
// //                   onChange={(e) => setForm({ ...form, fromEmail: e.target.value })}
// //                   placeholder="noreply@example.com"
// //                 />
// //               </div>
// //               <div className="space-y-2">
// //                 <Label htmlFor="mb-fromname">From Name (optional)</Label>
// //                 <Input
// //                   id="mb-fromname"
// //                   value={form.fromName}
// //                   onChange={(e) => setForm({ ...form, fromName: e.target.value })}
// //                   placeholder="OUTRENA Team"
// //                 />
// //               </div>
// //             </div>
// //             <div className="space-y-2">
// //               <Label htmlFor="mb-webhook">Webhook Secret (optional)</Label>
// //               <Input
// //                 id="mb-webhook"
// //                 value={form.webhookSecret}
// //                 onChange={(e) => setForm({ ...form, webhookSecret: e.target.value })}
// //                 placeholder="HMAC secret used to verify inbound MailBridge webhooks"
// //               />
// //             </div>
// //             <div className="flex items-center justify-between rounded-md border p-3">
// //               <div>
// //                 <p className="text-sm font-medium">Active</p>
// //                 <p className="text-xs text-muted-foreground">
// //                   Inactive configs are skipped by the scheduler.
// //                 </p>
// //               </div>
// //               <Switch
// //                 checked={form.isActive}
// //                 onCheckedChange={(v) => setForm({ ...form, isActive: v })}
// //               />
// //             </div>
// //           </div>
// //           <DialogFooter>
// //             <Button variant="outline" onClick={closeEditor}>
// //               Cancel
// //             </Button>
// //             <Button
// //               onClick={handleSave}
// //               disabled={createMut.isPending || updateMut.isPending}
// //             >
// //               {createMut.isPending || updateMut.isPending ? "Saving…" : "Save Config"}
// //             </Button>
// //           </DialogFooter>
// //         </Dialog>

// //         {/* Delete dialog */}
// //         <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
// //           <DialogClose onClose={() => setDeleteTarget(null)} />
// //           <DialogHeader>
// //             <DialogTitle>Delete MailBridge config?</DialogTitle>
// //             <DialogDescription>
// //               “{deleteTarget?.name}” will be permanently removed. The scheduler will
// //               no longer use this config to send or receive email.
// //             </DialogDescription>
// //           </DialogHeader>
// //           <DialogFooter>
// //             <Button variant="outline" onClick={() => setDeleteTarget(null)}>
// //               Cancel
// //             </Button>
// //             <Button
// //               variant="destructive"
// //               onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
// //               disabled={deleteMut.isPending}
// //             >
// //               {deleteMut.isPending ? "Deleting…" : "Delete"}
// //             </Button>
// //           </DialogFooter>
// //         </Dialog>
// //       </div>
// //     </TooltipProvider>
// //   );
// // }
// /**
//  * MailBridgePage.tsx — FIX-FE-1 + Tenancy Integration
//  *
//  * Per-tenant MailBridge config CRUD (SMTP / Gmail / Outlook relay settings)
//  * with tenancy-mode support: API key management, platform registration,
//  * mailbox OAuth connection (Gmail / Outlook), and connected accounts display.
//  *
//  * Targets:
//  *   GET/POST/PUT/DELETE /api/v1/mailbridge/config
//  *   POST /api/v1/mailbridge/send (test email)
//  *   POST /api/v1/mailbridge/platform/register
//  *   POST /api/v1/mailbridge/connect/{provider}/start
//  *   GET  /api/v1/mailbridge/mail-accounts
//  */
// /**
//  * MailBridgePage.tsx — FIX-FE-1 + Tenancy Integration
//  *
//  * Per-tenant MailBridge config CRUD (SMTP / Gmail / Outlook relay settings)
//  * with tenancy-mode support: API key management, platform registration,
//  * mailbox OAuth connection (Gmail / Outlook), and connected accounts display.
//  *
//  * Targets:
//  *   GET/POST/PUT/DELETE /api/v1/mailbridge/config
//  *   POST /api/v1/mailbridge/send (test email)
//  *   POST /api/v1/mailbridge/platform/register
//  *   POST /api/v1/mailbridge/connect/{provider}/start
//  *   GET  /api/v1/mailbridge/mail-accounts
//  */
// import { useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   Key,
//   Link2,
//   Mail,
//   Pencil,
//   Plus,
//   RefreshCw,
//   Send,
//   Server,
//   Trash2,
//   User,
// } from "lucide-react";
// import { toast } from "sonner";

// import { mailbridgeApi, http } from "@/services/apiClient";
// import type {
//   MailBridgeConfig,
//   MailBridgeConfigInput,
//   MailBridgeMailAccount,
// } from "@/types/common";
// import { Badge } from "@/components/ui/badge";
// import { Button } from "@/components/ui/button";
// import { Card, CardContent } from "@/components/ui/card";
// import {
//   Dialog,
//   DialogClose,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
// } from "@/components/ui/dialog";
// import { EmptyState } from "@/components/ui/empty-state";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { NativeSelect as Select } from "@/components/ui/select";
// import { PageHeader } from "@/components/ui/page-header";
// import { Separator } from "@/components/ui/separator";
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
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// import {
//   Tooltip,
//   TooltipContent,
//   TooltipProvider,
//   TooltipTrigger,
// } from "@/components/ui/tooltip";
// import { formatDateTime } from "@/lib/utils";

// const PROVIDERS = ["gmail", "smtp", "outlook", "sendgrid", "ses"] as const;

// // interface DomainLite {
// //   id: string;
// //   domain: string;
// // }

// interface DomainLite {
//   id: string;
//   domainName: string;
// }

// interface FormState {
//   id?: string;
//   name: string;
//   baseUrl: string;
//   provider: string;
//   fromEmail: string;
//   fromName: string;
//   isActive: boolean;
//   webhookSecret: string;
//   domainId: string;
//   mailbridge_api_key: string;
//   mailbridge_external_user_id: string;
// }

// const EMPTY_FORM: FormState = {
//   name: "",
//   baseUrl: "",
//   provider: "gmail",
//   fromEmail: "",
//   fromName: "",
//   isActive: true,
//   webhookSecret: "",
//   domainId: "",
//   mailbridge_api_key: "",
//   mailbridge_external_user_id: "",
// };

// interface RegisterFormState {
//   name: string;
//   slug: string;
// }

// export function MailBridgePage() {
//   const qc = useQueryClient();
//   const [editorOpen, setEditorOpen] = useState(false);
//   const [deleteTarget, setDeleteTarget] = useState<MailBridgeConfig | null>(null);
//   const [form, setForm] = useState<FormState>(EMPTY_FORM);
//   const [registerOpen, setRegisterOpen] = useState(false);
//   const [registerForm, setRegisterForm] = useState<RegisterFormState>({ name: "Outrena", slug: "outrena" });

//   /* ── Config CRUD queries ───────────────────────────────────────────────── */

//   const { data: configs, isLoading, isError, error, refetch } = useQuery({
//     queryKey: ["mailbridge", "configs"],
//     queryFn: () => mailbridgeApi.list(),
//     retry: false,
//   });

//   const { data: domains } = useQuery<DomainLite[]>({
//     queryKey: ["domains"],
//     queryFn: () => http.get("/api/v1/domains"),
//     retry: false,
//   });

//   /* ── Connected mail accounts query ─────────────────────────────────────── */

//   const {
//     data: mailAccounts,
//     isLoading: accountsLoading,
//     refetch: refetchAccounts,
//   } = useQuery<MailBridgeMailAccount[]>({
//     queryKey: ["mailbridge", "mail-accounts"],
//     queryFn: () => mailbridgeApi.listMailAccounts(),
//     retry: false,
//   });

//   /* ── Mutations ─────────────────────────────────────────────────────────── */

//   const createMut = useMutation({
//     mutationFn: (body: MailBridgeConfigInput) => mailbridgeApi.create(body),
//     onSuccess: () => {
//       toast.success("MailBridge config created");
//       qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
//       closeEditor();
//     },
//     onError: () => toast.error("Failed to create MailBridge config"),
//   });

//   const updateMut = useMutation({
//     mutationFn: ({ id, body }: { id: string; body: Partial<MailBridgeConfigInput> }) =>
//       mailbridgeApi.update(id, body),
//     onSuccess: () => {
//       toast.success("MailBridge config saved");
//       qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
//       closeEditor();
//     },
//     onError: () => toast.error("Failed to save MailBridge config"),
//   });

//   const deleteMut = useMutation({
//     mutationFn: (id: string) => mailbridgeApi.remove(id),
//     onSuccess: () => {
//       toast.success("MailBridge config deleted");
//       qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
//       setDeleteTarget(null);
//     },
//     onError: () => toast.error("Failed to delete config"),
//   });

//   const testMut = useMutation({
//     mutationFn: (config: MailBridgeConfig) =>
//       mailbridgeApi.sendTest({
//         to: config.fromEmail,
//         subject: "OUTRENA MailBridge test",
//         body: "This is a test email from OUTRENA MailBridge.",
//         configId: config.id,
//       }),
//     onSuccess: (res) => {
//       qc.invalidateQueries({ queryKey: ["mailbridge-configs"] });
//       if (res.accepted) {
//         toast.success(`Test email sent (messageId: ${res.messageId})`);
//       } else {
//         toast.error(`Test email rejected (status: ${res.status})`);
//       }
//     },
//     onError: () => toast.error("Failed to send test email"),
//   });

//   const registerMut = useMutation({
//     mutationFn: (body: { name: string; slug?: string }) =>
//       mailbridgeApi.registerPlatform(body),
//     onSuccess: (res) => {
//       toast.success(`Platform registered! API key: ${res.api_key.slice(0, 16)}...`);
//       qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
//       setRegisterOpen(false);
//     },
//     onError: () => toast.error("Platform registration failed — check MAILBRIDGE_PLATFORM_ADMIN_SECRET"),
//   });

//   const connectMut = useMutation({
//     mutationFn: (provider: string) => mailbridgeApi.connectStart(provider),
//     onSuccess: (res) => {
//       toast.success(`Redirecting to ${res.provider} OAuth...`);
//       window.open(res.authorize_url, "_blank");
//     },
//     onError: () => toast.error("Failed to start mailbox connection — is MailBridge configured?"),
//   });

//   /* ── Helpers ───────────────────────────────────────────────────────────── */

//   function openNew() {
//     setForm(EMPTY_FORM);
//     setEditorOpen(true);
//   }
//   function openEdit(c: MailBridgeConfig) {
//     setForm({
//       id: c.id,
//       name: c.name,
//       baseUrl: c.baseUrl,
//       provider: c.provider,
//       fromEmail: c.fromEmail,
//       fromName: c.fromName ?? "",
//       isActive: c.isActive,
//       webhookSecret: c.webhookSecret ?? "",
//       domainId: c.domainId ?? "",
//       mailbridge_api_key: c.mailbridge_api_key ?? "",
//       mailbridge_external_user_id: c.mailbridge_external_user_id ?? "",
//     });
//     setEditorOpen(true);
//   }
//   function closeEditor() {
//     setEditorOpen(false);
//     setForm(EMPTY_FORM);
//   }

//   function handleSave() {
//     if (!form.name.trim() || !form.baseUrl.trim() || !form.fromEmail.trim()) {
//       toast.error("Name, Base URL, and From Email are required");
//       return;
//     }
//     const body: MailBridgeConfigInput = {
//       name: form.name.trim(),
//       baseUrl: form.baseUrl.trim(),
//       provider: form.provider,
//       fromEmail: form.fromEmail.trim(),
//       fromName: form.fromName.trim() || null,
//       isActive: form.isActive,
//       webhookSecret: form.webhookSecret.trim() || null,
//       domainId: form.domainId || null,
//       mailbridge_api_key: form.mailbridge_api_key.trim() || null,
//       mailbridge_external_user_id: form.mailbridge_external_user_id.trim() || null,
//     };
//     if (form.id) {
//       updateMut.mutate({ id: form.id, body });
//     } else {
//       createMut.mutate(body);
//     }
//   }

//   /** Does the active config have an API key set? */
//   const activeConfig = configs?.find((c) => c.isActive);
//   const hasApiKey = !!(activeConfig?.mailbridge_api_key);

//   return (
//     <TooltipProvider delayDuration={200}>
//       <div className="space-y-6">
//         <PageHeader
//           title="MailBridge Config"
//           description="Tenant-wide SMTP / Gmail / Outlook relay settings used by the scheduler to send and receive email."
//           actions={
//             <>
//               <Button variant="outline" onClick={() => refetch()}>
//                 <RefreshCw className="h-4 w-4" />
//                 Refresh
//               </Button>
//               <Button onClick={openNew}>
//                 <Plus className="h-4 w-4" />
//                 New Config
//               </Button>
//             </>
//           }
//         />

//         <Tabs defaultValue="configs">
//           <TabsList>
//             <TabsTrigger value="configs">Configs</TabsTrigger>
//             <TabsTrigger value="accounts">Connected Accounts</TabsTrigger>
//             <TabsTrigger value="setup">Platform Setup</TabsTrigger>
//           </TabsList>

//           {/* ── Tab 1: Config Table ────────────────────────────────────────── */}
//           <TabsContent value="configs">
//             <Card>
//               <CardContent className="p-0">
//                 {isError ? (
//                   <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
//                     <p className="text-sm font-medium">Failed to load MailBridge configs</p>
//                     <p className="text-xs text-muted-foreground">
//                       {(error as Error)?.message ?? "Unknown error"}
//                     </p>
//                     <Button variant="outline" onClick={() => refetch()}>
//                       Retry
//                     </Button>
//                   </div>
//                 ) : isLoading ? (
//                   <div className="space-y-2 p-4">
//                     {Array.from({ length: 4 }).map((_, i) => (
//                       <Skeleton key={i} className="h-12 w-full" />
//                     ))}
//                   </div>
//                 ) : !configs || configs.length === 0 ? (
//                   <EmptyState
//                     icon={<Mail className="h-6 w-6" />}
//                     title="No MailBridge configs yet"
//                     description="Add your first SMTP / Gmail / Outlook relay config so the scheduler can send email."
//                     action={
//                       <Button onClick={openNew}>
//                         <Plus className="h-4 w-4" /> New Config
//                       </Button>
//                     }
//                   />
//                 ) : (
//                   <Table>
//                     <TableHeader>
//                       <TableRow>
//                         <TableHead>Name</TableHead>
//                         <TableHead>Provider</TableHead>
//                         <TableHead>From Email</TableHead>
//                         <TableHead>Domain</TableHead>
//                         <TableHead>API Key</TableHead>
//                         <TableHead>Active</TableHead>
//                         <TableHead>Last Updated</TableHead>
//                         <TableHead className="text-right">Actions</TableHead>
//                       </TableRow>
//                     </TableHeader>
//                     <TableBody>
//                       {configs.map((c) => {
//                         const domain = domains?.find((d) => d.id === c.domainId);
//                         return (
//                           <TableRow key={c.id}>
//                             <TableCell className="font-medium">{c.name}</TableCell>
//                             <TableCell>
//                               <Badge variant="secondary">{c.provider}</Badge>
//                             </TableCell>
//                             <TableCell className="text-muted-foreground">{c.fromEmail}</TableCell>
//                             <TableCell className="text-muted-foreground">
                              
//                               {domain?.domainName ?? "—"}
//                             </TableCell>
//                             <TableCell>
//                               {c.mailbridge_api_key ? (
//                                 <Badge variant="success">
//                                   <Key className="mr-1 h-3 w-3" />
//                                   {c.mailbridge_api_key.slice(0, 12)}...
//                                 </Badge>
//                               ) : (
//                                 <span className="text-xs text-muted-foreground">Not set</span>
//                               )}
//                             </TableCell>
//                             <TableCell>
//                               <Badge variant={c.isActive ? "success" : "outline"}>
//                                 {c.isActive ? "Active" : "Inactive"}
//                               </Badge>
//                             </TableCell>
//                             <TableCell className="text-xs text-muted-foreground">
//                               {formatDateTime(c.updatedAt)}
//                             </TableCell>
//                             <TableCell className="text-right">
//                               <div className="flex justify-end gap-1">
//                                 <Tooltip>
//                                   <TooltipTrigger asChild>
//                                     <Button
//                                       variant="ghost"
//                                       size="icon"
//                                       aria-label="Send test email"
//                                       onClick={() => testMut.mutate(c)}
//                                       disabled={testMut.isPending}
//                                     >
//                                       <Send className="h-4 w-4" />
//                                     </Button>
//                                   </TooltipTrigger>
//                                   <TooltipContent>Send test email</TooltipContent>
//                                 </Tooltip>
//                                 <Tooltip>
//                                   <TooltipTrigger asChild>
//                                     <Button
//                                       variant="ghost"
//                                       size="icon"
//                                       aria-label="Edit config"
//                                       onClick={() => openEdit(c)}
//                                     >
//                                       <Pencil className="h-4 w-4" />
//                                     </Button>
//                                   </TooltipTrigger>
//                                   <TooltipContent>Edit</TooltipContent>
//                                 </Tooltip>
//                                 <Tooltip>
//                                   <TooltipTrigger asChild>
//                                     <Button
//                                       variant="ghost"
//                                       size="icon"
//                                       aria-label="Delete config"
//                                       onClick={() => setDeleteTarget(c)}
//                                     >
//                                       <Trash2 className="h-4 w-4" />
//                                     </Button>
//                                   </TooltipTrigger>
//                                   <TooltipContent>Delete</TooltipContent>
//                                 </Tooltip>
//                               </div>
//                             </TableCell>
//                           </TableRow>
//                         );
//                       })}
//                     </TableBody>
//                   </Table>
//                 )}
//               </CardContent>
//             </Card>
//           </TabsContent>

//           {/* ── Tab 2: Connected Mail Accounts ─────────────────────────────── */}
//           <TabsContent value="accounts">
//             <Card>
//               <CardContent className="space-y-4 p-6">
//                 <div className="flex items-center justify-between">
//                   <div>
//                     <h3 className="text-sm font-medium">Connected Mailboxes</h3>
//                     <p className="text-xs text-muted-foreground">
//                       User mailboxes connected via OAuth (Gmail / Outlook). MailBridge routes
//                       outbound emails through the connected mailbox that matches the sender.
//                     </p>
//                   </div>
//                   <div className="flex gap-2">
//                     <Button
//                       variant="outline"
//                       size="sm"
//                       onClick={() => refetchAccounts()}
//                     >
//                       <RefreshCw className="mr-1 h-3 w-3" />
//                       Refresh
//                     </Button>
//                   </div>
//                 </div>

//                 <Separator />

//                 <div className="flex gap-2">
//                   <Button
//                     variant="outline"
//                     onClick={() => connectMut.mutate("gmail")}
//                     disabled={connectMut.isPending || !hasApiKey}
//                   >
//                     <Link2 className="mr-1 h-4 w-4" />
//                     Connect Gmail
//                   </Button>
//                   <Button
//                     variant="outline"
//                     onClick={() => connectMut.mutate("outlook")}
//                     disabled={connectMut.isPending || !hasApiKey}
//                   >
//                     <Link2 className="mr-1 h-4 w-4" />
//                     Connect Outlook
//                   </Button>
//                   {!hasApiKey && (
//                     <p className="self-center text-xs text-muted-foreground">
//                       Set an API key on your active config or register as a platform first.
//                     </p>
//                   )}
//                 </div>

//                 {accountsLoading ? (
//                   <div className="space-y-2">
//                     {Array.from({ length: 3 }).map((_, i) => (
//                       <Skeleton key={i} className="h-10 w-full" />
//                     ))}
//                   </div>
//                 ) : !mailAccounts || mailAccounts.length === 0 ? (
//                   <EmptyState
//                     icon={<User className="h-6 w-6" />}
//                     title="No mailboxes connected"
//                     description="Connect a Gmail or Outlook mailbox so MailBridge can send emails on your behalf."
//                   />
//                 ) : (
//                   <Table>
//                     <TableHeader>
//                       <TableRow>
//                         <TableHead>Email</TableHead>
//                         <TableHead>Provider</TableHead>
//                         <TableHead>Status</TableHead>
//                         <TableHead>Connected</TableHead>
//                       </TableRow>
//                     </TableHeader>
//                     <TableBody>
//                       {mailAccounts.map((a) => (
//                         <TableRow key={a.id}>
//                           <TableCell className="font-medium">{a.email_address}</TableCell>
//                           <TableCell>
//                             <Badge variant="secondary">{a.provider}</Badge>
//                           </TableCell>
//                           <TableCell>
//                             <Badge variant={a.status === "active" ? "success" : "outline"}>
//                               {a.status ?? "connected"}
//                             </Badge>
//                           </TableCell>
//                           <TableCell className="text-xs text-muted-foreground">
//                             {a.created_at ? formatDateTime(a.created_at) : "—"}
//                           </TableCell>
//                         </TableRow>
//                       ))}
//                     </TableBody>
//                   </Table>
//                 )}
//               </CardContent>
//             </Card>
//           </TabsContent>

//           {/* ── Tab 3: Platform Setup ──────────────────────────────────────── */}
//           <TabsContent value="setup">
//             <Card>
//               <CardContent className="space-y-6 p-6">
//                 <div>
//                   <h3 className="text-sm font-medium">Platform Registration</h3>
//                   <p className="mt-1 text-xs text-muted-foreground">
//                     Register Outrena as a MailBridge tenant. This creates a tenant record in
//                     your MailBridge instance and returns an API key (<code>mb_live_...</code>)
//                     that is automatically saved to the active MailBridge config.
//                   </p>
//                 </div>

//                 {hasApiKey ? (
//                   <div className="flex items-center gap-3 rounded-md border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
//                     <Key className="h-5 w-5 text-green-600" />
//                     <div>
//                       <p className="text-sm font-medium text-green-700 dark:text-green-400">
//                         Platform registered
//                       </p>
//                       <p className="text-xs text-green-600 dark:text-green-500">
//                         Active config has API key: {activeConfig?.mailbridge_api_key?.slice(0, 16)}...
//                       </p>
//                     </div>
//                   </div>
//                 ) : (
//                   <div className="flex items-center gap-3 rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
//                     <Server className="h-5 w-5 text-amber-600" />
//                     <div>
//                       <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
//                         Not registered yet
//                       </p>
//                       <p className="text-xs text-amber-600 dark:text-amber-500">
//                         Register to get an API key, or set one manually on your config.
//                       </p>
//                     </div>
//                   </div>
//                 )}

//                 <Button onClick={() => setRegisterOpen(true)}>
//                   <Server className="mr-1 h-4 w-4" />
//                   {hasApiKey ? "Re-register Platform" : "Register Platform"}
//                 </Button>

//                 <Separator />

//                 <div>
//                   <h3 className="text-sm font-medium">How it works</h3>
//                   <div className="mt-2 space-y-2 text-xs text-muted-foreground">
//                     <p>
//                       <strong>1. Register</strong> — Call MailBridge's <code>POST /platform/register</code> with
//                       the platform admin secret. This creates a tenant and returns an API key
//                       (<code>mb_live_...</code>) that is saved to your active config automatically.
//                     </p>
//                     <p>
//                       <strong>2. Connect mailboxes</strong> — Each user connects their Gmail or Outlook
//                       mailbox via OAuth. The user's Keycloak UUID is sent as <code>external_user_id</code>,
//                       so MailBridge knows which mailbox to use when sending on their behalf.
//                     </p>
//                     <p>
//                       <strong>3. Send emails</strong> — Outrena's scheduler and sequences automatically
//                       route through MailBridge using the tenant API key and the user's connected mailbox.
//                     </p>
//                   </div>
//                 </div>
//               </CardContent>
//             </Card>
//           </TabsContent>
//         </Tabs>

//         {/* ── Editor dialog ────────────────────────────────────────────────── */}
//         <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
//           <DialogClose onClose={closeEditor} />
//           <DialogHeader>
//             <DialogTitle>{form.id ? "Edit MailBridge Config" : "New MailBridge Config"}</DialogTitle>
//             <DialogDescription>
//               Configure the SMTP / Gmail / Outlook relay used to send outbound email and receive tracking webhooks.
//             </DialogDescription>
//           </DialogHeader>
//           <div className="space-y-4">
//             <div className="space-y-2">
//               <Label htmlFor="mb-name">Name</Label>
//               <Input
//                 id="mb-name"
//                 required
//                 value={form.name}
//                 onChange={(e) => setForm({ ...form, name: e.target.value })}
//                 placeholder="e.g. Primary SMTP relay"
//               />
//             </div>
//             <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
//               <div className="space-y-2">
//                 <Label htmlFor="mb-provider">Provider</Label>
//                 <Select
//                   id="mb-provider"
//                   value={form.provider}
//                   onChange={(e) => setForm({ ...form, provider: e.target.value })}
//                 >
//                   {PROVIDERS.map((p) => (
//                     <option key={p} value={p}>
//                       {p}
//                     </option>
//                   ))}
//                 </Select>
//               </div>
//               <div className="space-y-2">
//                 <Label htmlFor="mb-domain">Domain (optional)</Label>
//                 <Select
//                   id="mb-domain"
//                   value={form.domainId}
//                   onChange={(e) => setForm({ ...form, domainId: e.target.value })}
//                 >
//                   <option value="">— Tenant-wide —</option>
//                   {(domains ?? []).map((d) => (
//                     <option key={d.id} value={d.id}>
//                       {d.domainName}
//                     </option>
//                   ))}
//                 </Select>
//               </div>
//             </div>
//             <div className="space-y-2">
//               <Label htmlFor="mb-baseurl">Base URL</Label>
//               <Input
//                 id="mb-baseurl"
//                 required
//                 value={form.baseUrl}
//                 onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
//                 placeholder="https://mailbridge.example.com"
//               />
//             </div>
//             <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
//               {/* <div className="space-y-2">
//                 <Label htmlFor="mb-fromemail">From Email</Label>
//                 <Input
//                   id="mb-fromemail"
//                   required
//                   type="email"
//                   value={form.fromEmail}
//                   onChange={(e) => setForm({ ...form, fromEmail: e.target.value })}
//                   placeholder="noreply@example.com"
//                 />
//               </div> */}
//               <div className="space-y-2">
//                 <Label htmlFor="mb-fromname">From Name (optional)</Label>
//                 <Input
//                   id="mb-fromname"
//                   value={form.fromName}
//                   onChange={(e) => setForm({ ...form, fromName: e.target.value })}
//                   placeholder="OUTRENA Team"
//                 />
//               </div>
//             </div>

//             <Separator />

//             {/* ── Tenancy fields ─────────────────────────────────────────── */}
//             <div className="space-y-1">
//               <p className="text-sm font-medium">MailBridge Tenancy</p>
//               <p className="text-xs text-muted-foreground">
//                 API key and user mapping for MailBridge tenancy-mode integration.
//                 The API key is auto-populated when you register via Platform Setup.
//               </p>
//             </div>

//             <div className="space-y-2">
//               <Label htmlFor="mb-apikey">API Key</Label>
//               <Input
//                 id="mb-apikey"
//                 value={form.mailbridge_api_key}
//                 onChange={(e) => setForm({ ...form, mailbridge_api_key: e.target.value })}
//                 placeholder="mb_live_..."
//                 autoComplete="off"
//               />
//               <p className="text-xs text-muted-foreground">
//                 Tenant API key from MailBridge (<code>mb_live_...</code>). Used as Bearer token
//                 for all outbound API calls. Leave empty to fall back to the env-level
//                 MAILBRIDGE_API_KEY.
//               </p>
//             </div>

//             <div className="space-y-2">
//               <Label htmlFor="mb-extuserid">External User ID (optional)</Label>
//               <Input
//                 id="mb-extuserid"
//                 value={form.mailbridge_external_user_id}
//                 onChange={(e) => setForm({ ...form, mailbridge_external_user_id: e.target.value })}
//                 placeholder="Keycloak user UUID"
//               />
//               <p className="text-xs text-muted-foreground">
//                 Maps this config to a specific user's connected mailbox in MailBridge.
//                 Typically the user's Keycloak UUID. When set, emails are sent from that
//                 user's connected Gmail/Outlook account.
//               </p>
//             </div>

//             <Separator />

//             <div className="space-y-2">
//               <Label htmlFor="mb-webhook">Webhook Secret (optional)</Label>
//               <Input
//                 id="mb-webhook"
//                 value={form.webhookSecret}
//                 onChange={(e) => setForm({ ...form, webhookSecret: e.target.value })}
//                 placeholder="HMAC secret used to verify inbound MailBridge webhooks"
//               />
//             </div>
//             <div className="flex items-center justify-between rounded-md border p-3">
//               <div>
//                 <p className="text-sm font-medium">Active</p>
//                 <p className="text-xs text-muted-foreground">
//                   Inactive configs are skipped by the scheduler.
//                 </p>
//               </div>
//               <Switch
//                 checked={form.isActive}
//                 onCheckedChange={(v) => setForm({ ...form, isActive: v })}
//               />
//             </div>
//           </div>
//           <DialogFooter>
//             <Button variant="outline" onClick={closeEditor}>
//               Cancel
//             </Button>
//             <Button
//               onClick={handleSave}
//               disabled={createMut.isPending || updateMut.isPending}
//             >
//               {createMut.isPending || updateMut.isPending ? "Saving..." : "Save Config"}
//             </Button>
//           </DialogFooter>
//         </Dialog>

//         {/* ── Platform Registration dialog ─────────────────────────────────── */}
//         <Dialog open={registerOpen} onOpenChange={(o) => !o && setRegisterOpen(false)}>
//           <DialogClose onClose={() => setRegisterOpen(false)} />
//           <DialogHeader>
//             <DialogTitle>Register Platform with MailBridge</DialogTitle>
//             <DialogDescription>
//               This registers Outrena as a tenant on your MailBridge instance. The returned
//               API key (<code>mb_live_...</code>) is automatically saved to the active config.
//               Make sure <code>MAILBRIDGE_PLATFORM_ADMIN_SECRET</code> is set in your backend .env.
//             </DialogDescription>
//           </DialogHeader>
//           <div className="space-y-4">
//             <div className="space-y-2">
//               <Label htmlFor="reg-name">Platform Name</Label>
//               <Input
//                 id="reg-name"
//                 value={registerForm.name}
//                 onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
//                 placeholder="Outrena"
//               />
//             </div>
//             <div className="space-y-2">
//               <Label htmlFor="reg-slug">Slug (optional)</Label>
//               <Input
//                 id="reg-slug"
//                 value={registerForm.slug}
//                 onChange={(e) => setRegisterForm({ ...registerForm, slug: e.target.value })}
//                 placeholder="outrena"
//               />
//               <p className="text-xs text-muted-foreground">
//                 URL-safe identifier for the tenant. Defaults to a slugified version of the name.
//               </p>
//             </div>
//           </div>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setRegisterOpen(false)}>
//               Cancel
//             </Button>
//             <Button
//               onClick={() => registerMut.mutate({
//                 name: registerForm.name.trim(),
//                 slug: registerForm.slug.trim() || undefined,
//               })}
//               disabled={registerMut.isPending || !registerForm.name.trim()}
//             >
//               {registerMut.isPending ? "Registering..." : "Register"}
//             </Button>
//           </DialogFooter>
//         </Dialog>

//         {/* ── Delete dialog ────────────────────────────────────────────────── */}
//         <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
//           <DialogClose onClose={() => setDeleteTarget(null)} />
//           <DialogHeader>
//             <DialogTitle>Delete MailBridge config?</DialogTitle>
//             <DialogDescription>
//               "{deleteTarget?.name}" will be permanently removed. The scheduler will
//               no longer use this config to send or receive email.
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
//               {deleteMut.isPending ? "Deleting..." : "Delete"}
//             </Button>
//           </DialogFooter>
//         </Dialog>
//       </div>
//     </TooltipProvider>
//   );
// }

/**
 * MailBridgePage.tsx — FIX-FE-1 + Tenancy Integration
 *
 * Per-tenant MailBridge config CRUD (SMTP / Gmail / Outlook relay settings)
 * with tenancy-mode support: API key management, platform registration,
 * mailbox OAuth connection (Gmail / Outlook), and connected accounts display.
 *
 * Targets:
 *   GET/POST/PUT/DELETE /api/v1/mailbridge/config
 *   POST /api/v1/mailbridge/send (test email)
 *   POST /api/v1/mailbridge/platform/register
 *   POST /api/v1/mailbridge/connect/{provider}/start
 *   GET  /api/v1/mailbridge/mail-accounts
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Key,
  Link2,
  Mail,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Server,
  Trash2,
  User,
} from "lucide-react";
import { toast } from "sonner";

import { mailbridgeApi, http } from "@/services/apiClient";
import type {
  MailBridgeConfig,
  MailBridgeConfigInput,
  MailBridgeMailAccount,
} from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect as Select } from "@/components/ui/select";
import { PageHeader } from "@/components/ui/page-header";
import { Separator } from "@/components/ui/separator";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDateTime } from "@/lib/utils";

const PROVIDERS = ["gmail", "smtp", "outlook", "sendgrid", "ses"] as const;

interface DomainLite {
  id: string;
  domainName: string;
}

interface FormState {
  id?: string;
  name: string;
  baseUrl: string;
  provider: string;
  fromEmail: string;
  fromName: string;
  isActive: boolean;
  webhookSecret: string;
  domainId: string;
  mailbridge_api_key: string;
  mailbridge_external_user_id: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  baseUrl: "",
  provider: "gmail",
  fromEmail: "",
  fromName: "",
  isActive: true,
  webhookSecret: "",
  domainId: "",
  mailbridge_api_key: "",
  mailbridge_external_user_id: "",
};

interface RegisterFormState {
  name: string;
  slug: string;
}

export function MailBridgePage() {
  const qc = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<MailBridgeConfig | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [registerForm, setRegisterForm] = useState<RegisterFormState>({ name: "Outrena", slug: "outrena" });

  /* ── Config CRUD queries ───────────────────────────────────────────────── */

  const { data: configs, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["mailbridge", "configs"],
    queryFn: () => mailbridgeApi.list(),
    retry: false,
  });

  const { data: domains } = useQuery<DomainLite[]>({
    queryKey: ["domains"],
    queryFn: () => http.get("/api/v1/domains"),
    retry: false,
  });

  /* ── Connected mail accounts query ─────────────────────────────────────── */

  const {
    data: mailAccounts,
    isLoading: accountsLoading,
    refetch: refetchAccounts,
  } = useQuery<MailBridgeMailAccount[]>({
    queryKey: ["mailbridge", "mail-accounts"],
    queryFn: () => mailbridgeApi.listMailAccounts(),
    retry: false,
  });

  /* ── Mutations ─────────────────────────────────────────────────────────── */

  const createMut = useMutation({
    mutationFn: (body: MailBridgeConfigInput) => mailbridgeApi.create(body),
    onSuccess: () => {
      toast.success("MailBridge config created");
      qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create MailBridge config"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<MailBridgeConfigInput> }) =>
      mailbridgeApi.update(id, body),
    onSuccess: () => {
      toast.success("MailBridge config saved");
      qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save MailBridge config"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => mailbridgeApi.remove(id),
    onSuccess: () => {
      toast.success("MailBridge config deleted");
      qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete config"),
  });

  const testMut = useMutation({
    mutationFn: (config: MailBridgeConfig) =>
      mailbridgeApi.sendTest({
        to: config.fromEmail,
        subject: "OUTRENA MailBridge test",
        body: "This is a test email from OUTRENA MailBridge.",
        configId: config.id,
      }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["mailbridge-configs"] });
      if (res.accepted) {
        toast.success(`Test email sent (messageId: ${res.messageId})`);
      } else {
        toast.error(`Test email rejected (status: ${res.status})`);
      }
    },
    onError: () => toast.error("Failed to send test email"),
  });

  const registerMut = useMutation({
    mutationFn: (body: { name: string; slug?: string }) =>
      mailbridgeApi.registerPlatform(body),
    onSuccess: (res) => {
      toast.success(`Platform registered! API key: ${res.api_key.slice(0, 16)}...`);
      qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
      setRegisterOpen(false);
    },
    onError: () => toast.error("Platform registration failed — check MAILBRIDGE_PLATFORM_ADMIN_SECRET"),
  });

  const connectMut = useMutation({
    mutationFn: (provider: string) => mailbridgeApi.connectStart(provider),
    onSuccess: (res) => {
      toast.success(`Redirecting to ${res.provider} OAuth...`);
      window.open(res.authorize_url, "_blank");
    },
    onError: () => toast.error("Failed to start mailbox connection — is MailBridge configured?"),
  });

  /* ── Helpers ───────────────────────────────────────────────────────────── */

  function openNew() {
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  }
  function openEdit(c: MailBridgeConfig) {
    setForm({
      id: c.id,
      name: c.name,
      baseUrl: c.baseUrl,
      provider: c.provider,
      fromEmail: c.fromEmail,
      fromName: c.fromName ?? "",
      isActive: c.isActive,
      webhookSecret: c.webhookSecret ?? "",
      domainId: c.domainId ?? "",
      mailbridge_api_key: c.mailbridge_api_key ?? "",
      mailbridge_external_user_id: c.mailbridge_external_user_id ?? "",
    });
    setEditorOpen(true);
  }
  function closeEditor() {
    setEditorOpen(false);
    setForm(EMPTY_FORM);
  }

  function handleSave() {
    if (!form.name.trim() || !form.baseUrl.trim() || !form.fromEmail.trim()) {
      toast.error("Name, Base URL, and From Email are required");
      return;
    }
    const body: MailBridgeConfigInput = {
      name: form.name.trim(),
      baseUrl: form.baseUrl.trim(),
      provider: form.provider,
      fromEmail: form.fromEmail.trim(),
      fromName: form.fromName.trim() || null,
      isActive: form.isActive,
      webhookSecret: form.webhookSecret.trim() || null,
      domainId: form.domainId || null,
      mailbridge_api_key: form.mailbridge_api_key.trim() || null,
      mailbridge_external_user_id: form.mailbridge_external_user_id.trim() || null,
    };
    if (form.id) {
      updateMut.mutate({ id: form.id, body });
    } else {
      createMut.mutate(body);
    }
  }

  /** Does the active config have an API key set? */
  const activeConfig = configs?.find((c) => c.isActive);
  const hasApiKey = !!(activeConfig?.mailbridge_api_key);

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="MailBridge Config"
          description="Tenant-wide SMTP / Gmail / Outlook relay settings used by the scheduler to send and receive email."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={openNew}>
                <Plus className="h-4 w-4" />
                New Config
              </Button>
            </>
          }
        />

        <Tabs defaultValue="configs">
          <TabsList>
            <TabsTrigger value="configs">Configs</TabsTrigger>
            <TabsTrigger value="accounts">Connected Accounts</TabsTrigger>
            <TabsTrigger value="setup">Platform Setup</TabsTrigger>
          </TabsList>

          {/* ── Tab 1: Config Table ────────────────────────────────────────── */}
          <TabsContent value="configs">
            <Card>
              <CardContent className="p-0">
                {isError ? (
                  <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                    <p className="text-sm font-medium">Failed to load MailBridge configs</p>
                    <p className="text-xs text-muted-foreground">
                      {(error as Error)?.message ?? "Unknown error"}
                    </p>
                    <Button variant="outline" onClick={() => refetch()}>
                      Retry
                    </Button>
                  </div>
                ) : isLoading ? (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full" />
                    ))}
                  </div>
                ) : !configs || configs.length === 0 ? (
                  <EmptyState
                    icon={<Mail className="h-6 w-6" />}
                    title="No MailBridge configs yet"
                    description="Add your first SMTP / Gmail / Outlook relay config so the scheduler can send email."
                    action={
                      <Button onClick={openNew}>
                        <Plus className="h-4 w-4" /> New Config
                      </Button>
                    }
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Provider</TableHead>
                        <TableHead>Domain</TableHead>
                        <TableHead>API Key</TableHead>
                        <TableHead>Active</TableHead>
                        <TableHead>Last Updated</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {configs.map((c) => {
                        const domain = domains?.find((d) => d.id === c.domainId);
                        return (
                          <TableRow key={c.id}>
                            <TableCell className="font-medium">{c.name}</TableCell>
                            <TableCell>
                              <Badge variant="secondary">{c.provider}</Badge>
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {domain?.domainName ?? "—"}
                            </TableCell>
                            <TableCell>
                              {c.mailbridge_api_key ? (
                                <Badge variant="success">
                                  <Key className="mr-1 h-3 w-3" />
                                  {c.mailbridge_api_key.slice(0, 12)}...
                                </Badge>
                              ) : (
                                <span className="text-xs text-muted-foreground">Not set</span>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge variant={c.isActive ? "success" : "outline"}>
                                {c.isActive ? "Active" : "Inactive"}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {formatDateTime(c.updatedAt)}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-1">
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      aria-label="Send test email"
                                      onClick={() => testMut.mutate(c)}
                                      disabled={testMut.isPending}
                                    >
                                      <Send className="h-4 w-4" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>Send test email</TooltipContent>
                                </Tooltip>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      aria-label="Edit config"
                                      onClick={() => openEdit(c)}
                                    >
                                      <Pencil className="h-4 w-4" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>Edit</TooltipContent>
                                </Tooltip>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      aria-label="Delete config"
                                      onClick={() => setDeleteTarget(c)}
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>Delete</TooltipContent>
                                </Tooltip>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Tab 2: Connected Mail Accounts ─────────────────────────────── */}
          <TabsContent value="accounts">
            <Card>
              <CardContent className="space-y-4 p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-medium">Connected Mailboxes</h3>
                    <p className="text-xs text-muted-foreground">
                      User mailboxes connected via OAuth (Gmail / Outlook). MailBridge routes
                      outbound emails through the connected mailbox that matches the sender.
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => refetchAccounts()}
                    >
                      <RefreshCw className="mr-1 h-3 w-3" />
                      Refresh
                    </Button>
                  </div>
                </div>

                <Separator />

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => connectMut.mutate("gmail")}
                    disabled={connectMut.isPending || !hasApiKey}
                  >
                    <Link2 className="mr-1 h-4 w-4" />
                    Connect Gmail
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => connectMut.mutate("outlook")}
                    disabled={connectMut.isPending || !hasApiKey}
                  >
                    <Link2 className="mr-1 h-4 w-4" />
                    Connect Outlook
                  </Button>
                  {!hasApiKey && (
                    <p className="self-center text-xs text-muted-foreground">
                      Set an API key on your active config or register as a platform first.
                    </p>
                  )}
                </div>

                {accountsLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : !mailAccounts || mailAccounts.length === 0 ? (
                  <EmptyState
                    icon={<User className="h-6 w-6" />}
                    title="No mailboxes connected"
                    description="Connect a Gmail or Outlook mailbox so MailBridge can send emails on your behalf."
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Email</TableHead>
                        <TableHead>Provider</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {mailAccounts.map((a) => (
                        <TableRow key={a.id}>
                          <TableCell className="font-medium">{a.email_address}</TableCell>
                          <TableCell>
                            <Badge variant="secondary">{a.provider}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant={a.status === "active" ? "success" : "outline"}>
                              {a.status ?? "connected"}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Tab 3: Platform Setup ──────────────────────────────────────── */}
          <TabsContent value="setup">
            <Card>
              <CardContent className="space-y-6 p-6">
                <div>
                  <h3 className="text-sm font-medium">Platform Registration</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Register Outrena as a MailBridge tenant. This creates a tenant record in
                    your MailBridge instance and returns an API key (<code>mb_live_...</code>)
                    that is automatically saved to the active MailBridge config.
                  </p>
                </div>

                {hasApiKey ? (
                  <div className="flex items-center gap-3 rounded-md border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
                    <Key className="h-5 w-5 text-green-600" />
                    <div>
                      <p className="text-sm font-medium text-green-700 dark:text-green-400">
                        Platform registered
                      </p>
                      <p className="text-xs text-green-600 dark:text-green-500">
                        Active config has API key: {activeConfig?.mailbridge_api_key?.slice(0, 16)}...
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
                    <Server className="h-5 w-5 text-amber-600" />
                    <div>
                      <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
                        Not registered yet
                      </p>
                      <p className="text-xs text-amber-600 dark:text-amber-500">
                        Register to get an API key, or set one manually on your config.
                      </p>
                    </div>
                  </div>
                )}

                <Button onClick={() => setRegisterOpen(true)}>
                  <Server className="mr-1 h-4 w-4" />
                  {hasApiKey ? "Re-register Platform" : "Register Platform"}
                </Button>

                <Separator />

                <div>
                  <h3 className="text-sm font-medium">How it works</h3>
                  <div className="mt-2 space-y-2 text-xs text-muted-foreground">
                    <p>
                      <strong>1. Register</strong> — Call MailBridge's <code>POST /platform/register</code> with
                      the platform admin secret. This creates a tenant and returns an API key
                      (<code>mb_live_...</code>) that is saved to your active config automatically.
                    </p>
                    <p>
                      <strong>2. Connect mailboxes</strong> — Each user connects their Gmail or Outlook
                      mailbox via OAuth. The user's Keycloak UUID is sent as <code>external_user_id</code>,
                      so MailBridge knows which mailbox to use when sending on their behalf.
                    </p>
                    <p>
                      <strong>3. Send emails</strong> — Outrena's scheduler and sequences automatically
                      route through MailBridge using the tenant API key and the user's connected mailbox.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* ── Editor dialog ────────────────────────────────────────────────── */}
        <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
          <DialogClose onClose={closeEditor} />
          <DialogHeader>
            <DialogTitle>{form.id ? "Edit MailBridge Config" : "New MailBridge Config"}</DialogTitle>
            <DialogDescription>
              Configure the SMTP / Gmail / Outlook relay used to send outbound email and receive tracking webhooks.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mb-name">Name</Label>
              <Input
                id="mb-name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Primary SMTP relay"
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mb-provider">Provider</Label>
                <Select
                  id="mb-provider"
                  value={form.provider}
                  onChange={(e) => setForm({ ...form, provider: e.target.value })}
                >
                  {PROVIDERS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="mb-domain">Domain (optional)</Label>
                <Select
                  id="mb-domain"
                  value={form.domainId}
                  onChange={(e) => setForm({ ...form, domainId: e.target.value })}
                >
                  <option value="">— Tenant-wide —</option>
                  {(domains ?? []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.domainName}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mb-baseurl">Base URL</Label>
              <Input
                id="mb-baseurl"
                required
                value={form.baseUrl}
                onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
                placeholder="https://mailbridge.example.com"
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mb-fromname">From Name (optional)</Label>
                <Input
                  id="mb-fromname"
                  value={form.fromName}
                  onChange={(e) => setForm({ ...form, fromName: e.target.value })}
                  placeholder="OUTRENA Team"
                />
              </div>
            </div>

            <Separator />

            {/* ── Tenancy fields ─────────────────────────────────────────── */}
            <div className="space-y-1">
              <p className="text-sm font-medium">MailBridge Tenancy</p>
              <p className="text-xs text-muted-foreground">
                API key and user mapping for MailBridge tenancy-mode integration.
                The API key is auto-populated when you register via Platform Setup.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="mb-apikey">API Key</Label>
              <Input
                id="mb-apikey"
                value={form.mailbridge_api_key}
                onChange={(e) => setForm({ ...form, mailbridge_api_key: e.target.value })}
                placeholder="mb_live_..."
                autoComplete="off"
              />
              <p className="text-xs text-muted-foreground">
                Tenant API key from MailBridge (<code>mb_live_...</code>). Used as Bearer token
                for all outbound API calls. Leave empty to fall back to the env-level
                MAILBRIDGE_API_KEY.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="mb-extuserid">External User ID (optional)</Label>
              <Input
                id="mb-extuserid"
                value={form.mailbridge_external_user_id}
                onChange={(e) => setForm({ ...form, mailbridge_external_user_id: e.target.value })}
                placeholder="Keycloak user UUID"
              />
              <p className="text-xs text-muted-foreground">
                Maps this config to a specific user's connected mailbox in MailBridge.
                Typically the user's Keycloak UUID. When set, emails are sent from that
                user's connected Gmail/Outlook account.
              </p>
            </div>

            <Separator />

            <div className="space-y-2">
              <Label htmlFor="mb-webhook">Webhook Secret (optional)</Label>
              <Input
                id="mb-webhook"
                value={form.webhookSecret}
                onChange={(e) => setForm({ ...form, webhookSecret: e.target.value })}
                placeholder="HMAC secret used to verify inbound MailBridge webhooks"
              />
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Active</p>
                <p className="text-xs text-muted-foreground">
                  Inactive configs are skipped by the scheduler.
                </p>
              </div>
              <Switch
                checked={form.isActive}
                onCheckedChange={(v) => setForm({ ...form, isActive: v })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeEditor}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={createMut.isPending || updateMut.isPending}
            >
              {createMut.isPending || updateMut.isPending ? "Saving..." : "Save Config"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* ── Platform Registration dialog ─────────────────────────────────── */}
        <Dialog open={registerOpen} onOpenChange={(o) => !o && setRegisterOpen(false)}>
          <DialogClose onClose={() => setRegisterOpen(false)} />
          <DialogHeader>
            <DialogTitle>Register Platform with MailBridge</DialogTitle>
            <DialogDescription>
              This registers Outrena as a tenant on your MailBridge instance. The returned
              API key (<code>mb_live_...</code>) is automatically saved to the active config.
              Make sure <code>MAILBRIDGE_PLATFORM_ADMIN_SECRET</code> is set in your backend .env.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="reg-name">Platform Name</Label>
              <Input
                id="reg-name"
                value={registerForm.name}
                onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                placeholder="Outrena"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-slug">Slug (optional)</Label>
              <Input
                id="reg-slug"
                value={registerForm.slug}
                onChange={(e) => setRegisterForm({ ...registerForm, slug: e.target.value })}
                placeholder="outrena"
              />
              <p className="text-xs text-muted-foreground">
                URL-safe identifier for the tenant. Defaults to a slugified version of the name.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRegisterOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => registerMut.mutate({
                name: registerForm.name.trim(),
                slug: registerForm.slug.trim() || undefined,
              })}
              disabled={registerMut.isPending || !registerForm.name.trim()}
            >
              {registerMut.isPending ? "Registering..." : "Register"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* ── Delete dialog ────────────────────────────────────────────────── */}
        <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <DialogClose onClose={() => setDeleteTarget(null)} />
          <DialogHeader>
            <DialogTitle>Delete MailBridge config?</DialogTitle>
            <DialogDescription>
              "{deleteTarget?.name}" will be permanently removed. The scheduler will
              no longer use this config to send or receive email.
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
              {deleteMut.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}