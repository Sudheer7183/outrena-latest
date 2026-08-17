// /**
//  * DomainsPage.tsx — sending-domain management, DNS verification, warm-up.
//  *
//  * API (verified against app/features/domains/router.py + schemas/domains.py):
//  *   GET    /api/v1/domains                    → DomainResponse[]
//  *   POST   /api/v1/domains                    → DomainResponse
//  *   PUT    /api/v1/domains/:id                → DomainResponse
//  *   DELETE /api/v1/domains/:id                → 204
//  *   POST   /api/v1/domains/dns-check          { domain, selector? } → DnsCheckResult
//  *   POST   /api/v1/domains/:id/auto-warm       → DomainResponse (advances 1 week; 409 at week 7)
//  *
//  * CRITICAL FIX vs. the previous version: DnsCheckResult.spf/dkim/dmarc/mx are
//  * OBJECTS ({ name, found, records, detail }), not "pass"/"fail" strings. The
//  * previous code compared `res.spf === "pass"` against an object, which is
//  * always false — DNS verification silently never reported success. Fixed to
//  * read `.found` and persist the result via PUT so the domain row's stored
//  * spfStatus/dkimStatus/dmarcStatus reflect the real DNS state (mirroring the
//  * backend's own unexposed `refresh_domain_status` helper).
//  *
//  * There is no `/domains/{id}/verify` endpoint on the backend — verification
//  * is client-orchestrated as dns-check → PUT, same as the Next.js reference.
//  * There is also no `provider` column on the Domain model (Google Workspace /
//  * Microsoft 365 / etc. selection lives on MailBridgeConfig, a different
//  * entity), so the Add Domain dialog does not offer a provider field — adding
//  * one would be a no-op against the real schema.
//  *
//  * DOM-1 ✓ Add Domain dialog + real DNS-check results shown immediately after creation.
//  * DOM-2 ✓ DNS Verification button → dns-check + persist → pass/fail per record type.
//  * DOM-3 ✓ Domain Warming Schedule card (7-week ramp table + current week + auto-advance note).
//  * DOM-4 ✓ Six-state domain status badge (unverified/verifying/verified/warming/ready/suspended).
//  * DOM-5 ✓ Delete domain with confirmation (already correct; retained).
//  */
// import { useState } from "react";
// import type { FormEvent, ReactNode } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   Globe,
//   Plus,
//   RefreshCw,
//   Trash2,
//   Zap,
//   Loader2,
//   Info,
// } from "lucide-react";
// import { toast } from "sonner";
// import { http } from "@/services/apiClient";
// import { Pagination, usePagination } from "@/components/ui/pagination";
// import { DomainCreateSchema, formatZodError } from "@/lib/validation";
// import { PageHeader } from "@/components/ui/page-header";
// import { Button } from "@/components/ui/button";
// import {
//   Card,
//   CardContent,
//   CardDescription,
//   CardHeader,
//   CardTitle,
// } from "@/components/ui/card";
// import {
//   Table,
//   TableBody,
//   TableCell,
//   TableHead,
//   TableHeader,
//   TableRow,
// } from "@/components/ui/table";
// import { Badge } from "@/components/ui/badge";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { Skeleton } from "@/components/ui/skeleton";
// import {
//   Dialog,
//   DialogClose,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
// } from "@/components/ui/dialog";
// import {
//   Tooltip,
//   TooltipContent,
//   TooltipTrigger,
// } from "@/components/ui/tooltip";
// import { EmptyState } from "@/components/ui/empty-state";
// import { formatDate } from "@/lib/utils";

// /* ── Warming schedule (mirrors backend WARMING_SCHEDULE exactly) ────── */
// const WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500];

// /* ── Types (aligned with DomainResponse / DnsCheckResult schemas) ───── */

// interface DomainRow {
//   id: string;
//   domainName: string;
//   domain?: string; // alias added by DomainResponse.model_dump
//   isActive: boolean;
//   spfStatus: boolean;
//   dkimStatus: boolean;
//   dmarcStatus: boolean;
//   warmingWeek: number;
//   dailySendLimit: number;
//   lastChecked: string | null;
//   createdAt: string;
//   updatedAt: string;
// }

// interface DnsRecordResult {
//   name: string;
//   found: boolean;
//   records: string[];
//   detail: string | null;
// }

// interface DnsCheckResult {
//   domain: string;
//   mx: DnsRecordResult;
//   spf: DnsRecordResult;
//   dkim: DnsRecordResult;
//   dmarc: DnsRecordResult;
//   allPassed: boolean;
// }

// type DomainStatus =
//   | "unverified"
//   | "verifying"
//   | "verified"
//   | "warming"
//   | "ready"
//   | "suspended";

// /** Derive the DOM-4 six-state status from the fields the backend actually has. */
// function deriveStatus(d: DomainRow, isChecking: boolean): DomainStatus {
//   if (!d.isActive) return "suspended";
//   if (isChecking) return "verifying";
//   const dnsOk = d.spfStatus && d.dkimStatus && d.dmarcStatus;
//   if (!dnsOk) return "unverified";
//   if (d.warmingWeek >= WARMING_SCHEDULE.length) return "ready";
//   if (d.warmingWeek >= 1) return "warming";
//   return "verified";
// }

// const STATUS_META: Record<
//   DomainStatus,
//   { label: string; variant: "success" | "warning" | "secondary" | "destructive" }
// > = {
//   unverified: { label: "Unverified", variant: "secondary" },
//   verifying: { label: "Verifying…", variant: "warning" },
//   verified: { label: "Verified", variant: "success" },
//   warming: { label: "Warming", variant: "warning" },
//   ready: { label: "Ready", variant: "success" },
//   suspended: { label: "Suspended", variant: "destructive" },
// };

// function statusBadge(status: DomainStatus): ReactNode {
//   const meta = STATUS_META[status];
//   return <Badge variant={meta.variant}>{meta.label}</Badge>;
// }

// function recordBadge(result: DnsRecordResult | undefined): ReactNode {
//   if (!result)
//     return (
//       <Badge variant="secondary" className="text-[10px]">
//         unknown
//       </Badge>
//     );
//   return result.found ? (
//     <Badge variant="success" className="text-[10px]">
//       pass
//     </Badge>
//   ) : (
//     <Badge variant="destructive" className="text-[10px]">
//       fail
//     </Badge>
//   );
// }

// /* ── Helpers ────────────────────────────────────────────────────────── */

// function normaliseDomains(raw: unknown): DomainRow[] {
//   if (Array.isArray(raw)) return raw as DomainRow[];
//   if (raw && typeof raw === "object" && "items" in raw)
//     return (raw as { items: DomainRow[] }).items ?? [];
//   return [];
// }

// /* ── Page ──────────────────────────────────────────────────────────── */

// export function DomainsPage() {
//   const queryClient = useQueryClient();
//   const [dialogOpen, setDialogOpen] = useState(false);
//   const [domainInput, setDomainInput] = useState("");
//   const [checkingId, setCheckingId] = useState<string | null>(null);
//   const [deleteTarget, setDeleteTarget] = useState<DomainRow | null>(null);
//   const [lastCheckResults, setLastCheckResults] = useState<
//     Record<string, DnsCheckResult>
//   >({});
//   const [creationResult, setCreationResult] = useState<DnsCheckResult | null>(
//     null,
//   );

//   const { data, isLoading, isError, refetch } = useQuery({
//     queryKey: ["domains"],
//     queryFn: () =>
//       http.get<unknown>("/api/v1/domains").then(normaliseDomains),
//   });

//   const domains = data ?? [];

//   const { page, pageSize, total, pageItems, setPage, setPageSize } =
//     usePagination({ items: domains, initialPageSize: 15 });

//   const createMutation = useMutation({
//     mutationFn: (body: { domain: string }) =>
//       http.post<DomainRow>("/api/v1/domains", body),
//     onSuccess: async (created) => {
//       toast.success("Domain added — running initial DNS check…");
//       queryClient.invalidateQueries({ queryKey: ["domains"] });
//       setDomainInput("");
//       // DOM-1: show real DNS record status right after creation.
//       try {
//         const result = await http.post<DnsCheckResult>(
//           "/api/v1/domains/dns-check",
//           { domain: created.domainName },
//         );
//         setCreationResult(result);
//         // Persist so the list reflects the just-checked status immediately.
//         await http.put(`/api/v1/domains/${created.id}`, {
//           spfStatus: result.spf.found,
//           dkimStatus: result.dkim.found,
//           dmarcStatus: result.dmarc.found,
//         });
//         queryClient.invalidateQueries({ queryKey: ["domains"] });
//       } catch {
//         toast.error("Initial DNS check failed — you can retry from the list");
//       }
//     },
//     onError: () => toast.error("Failed to add domain"),
//   });

//   const deleteMutation = useMutation({
//     mutationFn: (id: string) => http.delete(`/api/v1/domains/${id}`),
//     onSuccess: () => {
//       toast.success("Domain removed");
//       queryClient.invalidateQueries({ queryKey: ["domains"] });
//       setDeleteTarget(null);
//     },
//     onError: () => toast.error("Failed to remove domain"),
//   });

//   const dnsCheckMutation = useMutation({
//     mutationFn: async ({ id, domain }: { id: string; domain: string }) => {
//       const result = await http.post<DnsCheckResult>(
//         "/api/v1/domains/dns-check",
//         { domain },
//       );
//       // DOM-2: persist the real result so status/badges reflect it.
//       await http.put(`/api/v1/domains/${id}`, {
//         spfStatus: result.spf.found,
//         dkimStatus: result.dkim.found,
//         dmarcStatus: result.dmarc.found,
//       });
//       return { id, result };
//     },
//     onSuccess: ({ id, result }) => {
//       setLastCheckResults((prev) => ({ ...prev, [id]: result }));
//       if (result.allPassed) {
//         toast.success(`DNS verified for ${result.domain}`);
//       } else {
//         const failed = [
//           !result.mx.found && "MX",
//           !result.spf.found && "SPF",
//           !result.dkim.found && "DKIM",
//           !result.dmarc.found && "DMARC",
//         ]
//           .filter(Boolean)
//           .join(", ");
//         toast.warning(`DNS incomplete for ${result.domain} — missing: ${failed}`);
//       }
//       queryClient.invalidateQueries({ queryKey: ["domains"] });
//     },
//     onError: () => toast.error("DNS check failed"),
//     onSettled: () => setCheckingId(null),
//   });

//   const autoWarmMutation = useMutation({
//     mutationFn: (domainId: string) =>
//       http.post<DomainRow>(`/api/v1/domains/${domainId}/auto-warm`, {}),
//     onSuccess: (res) => {
//       toast.success(
//         `Domain advanced to week ${res.warmingWeek} (limit: ${res.dailySendLimit}/day)`,
//       );
//       queryClient.invalidateQueries({ queryKey: ["domains"] });
//     },
//     onError: () =>
//       toast.error("Failed to advance warming week — may already be fully warm"),
//   });

//   function handleAdd(e: FormEvent) {
//     e.preventDefault();
//     const parsed = DomainCreateSchema.safeParse({ domain: domainInput.trim() });
//     if (!parsed.success) {
//       toast.error(formatZodError(parsed.error));
//       return;
//     }
//     setCreationResult(null);
//     createMutation.mutate({ domain: parsed.data.domain });
//   }

//   function handleCheck(d: DomainRow) {
//     setCheckingId(d.id);
//     dnsCheckMutation.mutate({ id: d.id, domain: d.domainName });
//   }

//   return (
//     <div className="space-y-6 p-6">
//       <PageHeader
//         title="Sending Domains"
//         description="Manage sending domains, verify DNS records, and track warm-up status."
//         actions={
//           <Button
//             onClick={() => {
//               setCreationResult(null);
//               setDialogOpen(true);
//             }}
//           >
//             <Plus className="h-4 w-4" />
//             Add Domain
//           </Button>
//         }
//       />

//       {/* Domain Warming Schedule (DOM-3) */}
//       <Card>
//         <CardHeader className="pb-3">
//           <CardTitle className="text-sm">Domain Warming Schedule</CardTitle>
//           <CardDescription className="text-xs">
//             Warming week advances automatically every night once a domain
//             has been active for 7+ days at its current step. Use
//             "Auto-warm" on a domain below to advance it immediately instead
//             of waiting.
//           </CardDescription>
//         </CardHeader>
//         <CardContent>
//           <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
//             {WARMING_SCHEDULE.map((limit, i) => {
//               const week = i + 1;
//               const domainsAtWeek = domains.filter(
//                 (d) => d.warmingWeek === week,
//               ).length;
//               return (
//                 <div
//                   key={week}
//                   className="text-center p-2 rounded-lg bg-muted relative"
//                 >
//                   {domainsAtWeek > 0 && (
//                     <span className="absolute -top-1.5 -right-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
//                       {domainsAtWeek}
//                     </span>
//                   )}
//                   <p className="text-lg font-bold">{limit}</p>
//                   <p className="text-xs text-muted-foreground">emails/day</p>
//                   <p className="text-xs text-muted-foreground">Week {week}</p>
//                 </div>
//               );
//             })}
//           </div>
//         </CardContent>
//       </Card>

//       {isError ? (
//         <Card className="mt-6">
//           <CardContent className="py-12 text-center">
//             <p className="text-muted-foreground">
//               Failed to load sending domains. Please try again.
//             </p>
//             <Button onClick={() => refetch()} className="mt-4">
//               Retry
//             </Button>
//           </CardContent>
//         </Card>
//       ) : (
//         <Card>
//           <CardHeader>
//             <CardTitle>Domains</CardTitle>
//             <CardDescription>
//               All three of SPF, DKIM, and DMARC must pass before a domain
//               can send. Domains in warm-up send at a throttled rate.
//             </CardDescription>
//           </CardHeader>
//           <CardContent>
//             {isLoading ? (
//               <div className="space-y-2">
//                 {Array.from({ length: 3 }).map((_, i) => (
//                   <Skeleton key={i} className="h-14 w-full" />
//                 ))}
//               </div>
//             ) : domains.length === 0 ? (
//               <EmptyState
//                 icon={<Globe className="h-6 w-6" />}
//                 title="No sending domains"
//                 description="Add a domain to begin warm-up and DNS verification."
//                 action={
//                   <Button onClick={() => setDialogOpen(true)}>
//                     <Plus className="h-4 w-4" />
//                     Add Domain
//                   </Button>
//                 }
//               />
//             ) : (
//               <Table>
//                 <TableHeader>
//                   <TableRow>
//                     <TableHead>Domain</TableHead>
//                     <TableHead>Status</TableHead>
//                     <TableHead>MX</TableHead>
//                     <TableHead>SPF</TableHead>
//                     <TableHead>DKIM</TableHead>
//                     <TableHead>DMARC</TableHead>
//                     <TableHead>Warming Week</TableHead>
//                     <TableHead>Daily Limit</TableHead>
//                     <TableHead>Last Check</TableHead>
//                     <TableHead className="text-right">Actions</TableHead>
//                   </TableRow>
//                 </TableHeader>
//                 <TableBody>
//                   {pageItems.map((d) => {
//                     const isChecking = checkingId === d.id;
//                     const lastResult = lastCheckResults[d.id];
//                     const status = deriveStatus(d, isChecking);
//                     return (
//                       <TableRow key={d.id}>
//                         <TableCell className="font-medium">
//                           <div className="flex items-center gap-2">
//                             <Globe className="h-4 w-4 text-muted-foreground" />
//                             {d.domainName}
//                           </div>
//                         </TableCell>
//                         <TableCell>{statusBadge(status)}</TableCell>
//                         <TableCell>
//                           {lastResult ? (
//                             recordBadge(lastResult.mx)
//                           ) : (
//                             recordBadge(undefined)
//                           )}
//                         </TableCell>
//                         <TableCell>
//                           {lastResult
//                             ? recordBadge(lastResult.spf)
//                             : recordBadge(
//                                 d.spfStatus
//                                   ? {
//                                       name: "SPF",
//                                       found: true,
//                                       records: [],
//                                       detail: null,
//                                     }
//                                   : undefined,
//                               )}
//                         </TableCell>
//                         <TableCell>
//                           {lastResult
//                             ? recordBadge(lastResult.dkim)
//                             : recordBadge(
//                                 d.dkimStatus
//                                   ? {
//                                       name: "DKIM",
//                                       found: true,
//                                       records: [],
//                                       detail: null,
//                                     }
//                                   : undefined,
//                               )}
//                         </TableCell>
//                         <TableCell>
//                           {lastResult
//                             ? recordBadge(lastResult.dmarc)
//                             : recordBadge(
//                                 d.dmarcStatus
//                                   ? {
//                                       name: "DMARC",
//                                       found: true,
//                                       records: [],
//                                       detail: null,
//                                     }
//                                   : undefined,
//                               )}
//                         </TableCell>
//                         <TableCell>
//                           <Badge
//                             variant={
//                               d.warmingWeek >= WARMING_SCHEDULE.length
//                                 ? "success"
//                                 : d.warmingWeek >= 2
//                                   ? "warning"
//                                   : "secondary"
//                             }
//                             className="text-[10px]"
//                           >
//                             Wk {d.warmingWeek}/{WARMING_SCHEDULE.length}
//                           </Badge>
//                         </TableCell>
//                         <TableCell className="text-xs tabular-nums">
//                           {d.dailySendLimit}/day
//                         </TableCell>
//                         <TableCell className="text-xs text-muted-foreground">
//                           {formatDate(d.lastChecked)}
//                         </TableCell>
//                         <TableCell className="text-right">
//                           <div className="flex justify-end gap-1">
//                             {d.warmingWeek < WARMING_SCHEDULE.length && (
//                               <Tooltip>
//                                 <TooltipTrigger asChild>
//                                   <Button
//                                     variant="outline"
//                                     size="sm"
//                                     onClick={() =>
//                                       autoWarmMutation.mutate(d.id)
//                                     }
//                                     disabled={autoWarmMutation.isPending}
//                                   >
//                                     <Zap className="h-3.5 w-3.5" />
//                                     Auto-warm
//                                   </Button>
//                                 </TooltipTrigger>
//                                 <TooltipContent>
//                                   Advance one week in the 7-step warming
//                                   schedule
//                                 </TooltipContent>
//                               </Tooltip>
//                             )}
//                             <Button
//                               variant="ghost"
//                               size="sm"
//                               onClick={() => handleCheck(d)}
//                               disabled={isChecking}
//                             >
//                               {isChecking ? (
//                                 <Loader2 className="h-3.5 w-3.5 animate-spin" />
//                               ) : (
//                                 <RefreshCw className="h-3.5 w-3.5" />
//                               )}
//                               {isChecking ? "Checking…" : "Verify DNS"}
//                             </Button>
//                             <Tooltip>
//                               <TooltipTrigger asChild>
//                                 <Button
//                                   variant="ghost"
//                                   size="icon"
//                                   onClick={() => setDeleteTarget(d)}
//                                   aria-label="Delete"
//                                 >
//                                   <Trash2 className="h-4 w-4 text-red-600" />
//                                 </Button>
//                               </TooltipTrigger>
//                               <TooltipContent>Delete domain</TooltipContent>
//                             </Tooltip>
//                           </div>
//                         </TableCell>
//                       </TableRow>
//                     );
//                   })}
//                 </TableBody>
//               </Table>
//             )}

//             <Pagination
//               page={page}
//               pageSize={pageSize}
//               total={total}
//               onPageChange={setPage}
//               onPageSizeChange={setPageSize}
//             />
//           </CardContent>
//         </Card>
//       )}

//       {/* Add Domain dialog */}
//       <Dialog
//         open={dialogOpen}
//         onOpenChange={(o) => {
//           setDialogOpen(o);
//           if (!o) {
//             setDomainInput("");
//             setCreationResult(null);
//           }
//         }}
//       >
//         <DialogClose onClose={() => setDialogOpen(false)} />
//         <DialogHeader>
//           <DialogTitle>Add Sending Domain</DialogTitle>
//           <DialogDescription>
//             Enter a subdomain you control (e.g. mail.yourcompany.com).
//             You'll need to add SPF, DKIM, and DMARC DNS records with your
//             registrar or email provider before it can send.
//           </DialogDescription>
//         </DialogHeader>
//         <form onSubmit={handleAdd} className="space-y-4">
//           <div className="space-y-2">
//             <Label htmlFor="domain">Domain</Label>
//             <Input
//               id="domain"
//               placeholder="mail.yourcompany.com"
//               value={domainInput}
//               onChange={(e) => setDomainInput(e.target.value)}
//               required
//             />
//           </div>

//           {createMutation.isPending && (
//             <p className="text-xs text-muted-foreground flex items-center gap-1.5">
//               <Loader2 className="h-3 w-3 animate-spin" />
//               Adding domain and checking DNS records…
//             </p>
//           )}

//           {creationResult && (
//             <div className="space-y-2 rounded-md border p-3 bg-muted/30">
//               <p className="text-xs font-medium flex items-center gap-1.5">
//                 <Info className="h-3.5 w-3.5" />
//                 DNS check for {creationResult.domain}
//               </p>
//               <div className="grid grid-cols-2 gap-2 text-xs">
//                 {(["mx", "spf", "dkim", "dmarc"] as const).map((key) => {
//                   const r = creationResult[key];
//                   return (
//                     <div
//                       key={key}
//                       className="flex items-center justify-between rounded border bg-background px-2 py-1.5"
//                     >
//                       <span className="font-medium uppercase">{key}</span>
//                       {recordBadge(r)}
//                     </div>
//                   );
//                 })}
//               </div>
//               {!creationResult.allPassed && (
//                 <p className="text-[11px] text-muted-foreground">
//                   Missing records won't block adding the domain — configure
//                   them with your DNS provider, then click "Verify DNS" on
//                   the domain row to re-check.
//                 </p>
//               )}
//             </div>
//           )}

//           <DialogFooter>
//             <Button
//               type="button"
//               variant="outline"
//               onClick={() => setDialogOpen(false)}
//             >
//               {creationResult ? "Close" : "Cancel"}
//             </Button>
//             {!creationResult && (
//               <Button type="submit" disabled={createMutation.isPending}>
//                 {createMutation.isPending ? (
//                   <Loader2 className="h-3.5 w-3.5 animate-spin" />
//                 ) : null}
//                 Add domain
//               </Button>
//             )}
//           </DialogFooter>
//         </form>
//       </Dialog>

//       {/* Delete confirmation dialog (DOM-5) */}
//       <Dialog
//         open={!!deleteTarget}
//         onOpenChange={(o) => !o && setDeleteTarget(null)}
//       >
//         <DialogClose onClose={() => setDeleteTarget(null)} />
//         <DialogHeader>
//           <DialogTitle>Delete sending domain?</DialogTitle>
//           <DialogDescription>
//             {deleteTarget?.domainName
//               ? `Domain "${deleteTarget.domainName}" will be permanently removed and any associated warm-up progress will be lost. This action cannot be undone.`
//               : "This sending domain will be permanently removed. This action cannot be undone."}
//           </DialogDescription>
//         </DialogHeader>
//         <DialogFooter>
//           <Button variant="outline" onClick={() => setDeleteTarget(null)}>
//             Cancel
//           </Button>
//           <Button
//             variant="destructive"
//             onClick={() =>
//               deleteTarget && deleteMutation.mutate(deleteTarget.id)
//             }
//             disabled={deleteMutation.isPending}
//           >
//             {deleteMutation.isPending ? "Deleting…" : "Delete"}
//           </Button>
//         </DialogFooter>
//       </Dialog>
//     </div>
//   );
// }

/**
 * DomainsPage.tsx — sending-domain management, DNS verification, warm-up.
 *
 * KEY ADDITION: DNS Setup Guide panel — when a domain fails verification,
 * shows the user the EXACT DNS records they need to add to their registrar.
 * Records are generated from the domain name using standard formats:
 *   - SPF:   TXT record on the root domain
 *   - DMARC: TXT record on _dmarc.<domain>
 *   - DKIM:  TXT record on <selector>._domainkey.<domain>
 *            (public key must come from their email provider — we show a placeholder)
 *   - MX:    Points to their email provider (Google/Microsoft/etc.)
 *
 * API:
 *   GET    /api/v1/domains                    → DomainResponse[]
 *   POST   /api/v1/domains                    → DomainResponse
 *   PUT    /api/v1/domains/:id                → DomainResponse
 *   DELETE /api/v1/domains/:id                → 204
 *   POST   /api/v1/domains/dns-check          { domain, selector? } → DnsCheckResult
 *   POST   /api/v1/domains/:id/auto-warm      → DomainResponse
 */
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Globe,
  Plus,
  RefreshCw,
  Trash2,
  Zap,
  Loader2,
  Info,
  Copy,
  CheckCircle2,
  AlertCircle,
  BookOpen,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { Pagination, usePagination } from "@/components/ui/pagination";
import { DomainCreateSchema, formatZodError } from "@/lib/validation";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/lib/utils";

/* ── Warming schedule ───────────────────────────────────────────────── */
const WARMING_SCHEDULE = [10, 30, 50, 100, 200, 350, 500];

/* ── Types ──────────────────────────────────────────────────────────── */

interface DomainRow {
  id: string;
  domainName: string;
  isActive: boolean;
  spfStatus: boolean;
  dkimStatus: boolean;
  dmarcStatus: boolean;
  warmingWeek: number;
  dailySendLimit: number;
  lastChecked: string | null;
  createdAt: string;
  updatedAt: string;
}

interface DnsRecordResult {
  name: string;
  found: boolean;
  records: string[];
  detail: string | null;
}

interface DnsCheckResult {
  domain: string;
  mx: DnsRecordResult;
  spf: DnsRecordResult;
  dkim: DnsRecordResult;
  dmarc: DnsRecordResult;
  allPassed: boolean;
}

type DomainStatus =
  | "unverified" | "verifying" | "verified" | "warming" | "ready" | "suspended";

function deriveStatus(d: DomainRow, isChecking: boolean): DomainStatus {
  if (!d.isActive) return "suspended";
  if (isChecking) return "verifying";
  const dnsOk = d.spfStatus && d.dkimStatus && d.dmarcStatus;
  if (!dnsOk) return "unverified";
  if (d.warmingWeek >= WARMING_SCHEDULE.length) return "ready";
  if (d.warmingWeek >= 1) return "warming";
  return "verified";
}

const STATUS_META: Record<DomainStatus, { label: string; variant: "success" | "warning" | "secondary" | "destructive" }> = {
  unverified: { label: "Unverified", variant: "secondary" },
  verifying: { label: "Verifying…", variant: "warning" },
  verified: { label: "Verified", variant: "success" },
  warming: { label: "Warming", variant: "warning" },
  ready: { label: "Ready", variant: "success" },
  suspended: { label: "Suspended", variant: "destructive" },
};

function statusBadge(status: DomainStatus): ReactNode {
  const meta = STATUS_META[status];
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}

function recordBadge(result: DnsRecordResult | undefined): ReactNode {
  if (!result) return <Badge variant="secondary" className="text-[10px]">unknown</Badge>;
  return result.found
    ? <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200">pass</Badge>
    : <Badge variant="outline" className="text-[10px] bg-rose-50 text-rose-700 border-rose-200">fail</Badge>;
}

function normaliseDomains(raw: unknown): DomainRow[] {
  if (Array.isArray(raw)) return raw as DomainRow[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: DomainRow[] }).items ?? [];
  return [];
}

/* ── DNS Setup Guide ────────────────────────────────────────────────── */
/**
 * Generates the standard DNS records a user needs to add to their registrar.
 *
 * SPF and DMARC values follow the RFC standard format.
 * DKIM requires a public key from the email provider — we show a placeholder
 * and instruct the user to get the value from their provider's admin console.
 * MX depends on the email provider — we show the Google Workspace example
 * and note they should use their provider's MX values.
 */
function generateRequiredRecords(domain: string, selector = "google") {
  return {
    spf: {
      type: "TXT",
      host: domain,
      value: `v=spf1 include:_spf.google.com include:sendgrid.net ~all`,
      note: "Adjust include: directives to match your email provider (Google, Microsoft, SendGrid, etc.)",
    },
    dkim: {
      type: "TXT",
      host: `${selector}._domainkey.${domain}`,
      value: `v=DKIM1; k=rsa; p=<YOUR_PUBLIC_KEY>`,
      note: `Get the DKIM public key from your email provider's admin console (Google Workspace: Admin → Apps → Gmail → Authenticate email). The selector is typically "google" for Google or "selector1" for Microsoft.`,
    },
    dmarc: {
      type: "TXT",
      host: `_dmarc.${domain}`,
      value: `v=DMARC1; p=none; rua=mailto:dmarc@${domain}; ruf=mailto:dmarc@${domain}; fo=1`,
      note: 'Start with p=none (monitoring only), then tighten to p=quarantine or p=reject once SPF and DKIM are confirmed passing.',
    },
    mx: {
      type: "MX",
      host: domain,
      value: `ASPMX.L.GOOGLE.COM (priority 1)\nALT1.ASPMX.L.GOOGLE.COM (priority 5)`,
      note: "Use your email provider's MX values. Shown here: Google Workspace. For Microsoft 365, use <yourdomain>.mail.protection.outlook.com.",
    },
  };
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        });
      }}
      className="shrink-0 rounded p-1 hover:bg-muted transition-colors"
      title="Copy to clipboard"
    >
      {copied
        ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
        : <Copy className="h-3.5 w-3.5 text-muted-foreground" />}
    </button>
  );
}

function DnsSetupGuide({
  domain,
  checkResult,
}: {
  domain: string;
  checkResult: DnsCheckResult | null;
}) {
  const records = generateRequiredRecords(domain);

  const needed = {
    mx: !checkResult?.mx.found,
    spf: !checkResult?.spf.found,
    dkim: !checkResult?.dkim.found,
    dmarc: !checkResult?.dmarc.found,
  };

  const anyNeeded = Object.values(needed).some(Boolean);

  return (
    <Card className={anyNeeded ? "border-amber-300 bg-amber-50/30" : "border-emerald-300 bg-emerald-50/20"}>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-amber-600" />
          DNS Setup Guide — {domain}
        </CardTitle>
        <CardDescription>
          {anyNeeded
            ? "Add the following DNS records to your domain registrar (GoDaddy, Namecheap, Cloudflare, Route53, etc.) then click Verify DNS."
            : "All DNS records verified. Your domain is ready to send."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {anyNeeded && (
          <div className="rounded-md bg-blue-50 border border-blue-200 p-3 text-xs text-blue-800">
            <p className="font-medium mb-1">Where to add these records</p>
            <p>Log into your domain registrar (where you bought the domain) → DNS Management / DNS Zone Editor → Add Record. Changes can take 5–48 hours to propagate.</p>
          </div>
        )}

        {(["spf", "dkim", "dmarc", "mx"] as const).map((key) => {
          const rec = records[key];
          const found = checkResult ? !needed[key] : null;

          return (
            <div key={key} className={`rounded-md border p-3 space-y-2 ${
              found === true ? "border-emerald-200 bg-emerald-50/40" :
              found === false ? "border-rose-200 bg-rose-50/20" :
              "border-border bg-background"
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase bg-muted px-1.5 py-0.5 rounded">
                    {key.toUpperCase()}
                  </span>
                  <span className="text-xs text-muted-foreground">{rec.type} record</span>
                </div>
                {found === true && <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />}
                {found === false && <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />}
              </div>

              <div className="grid grid-cols-[80px_1fr] gap-x-3 gap-y-1.5 text-xs">
                {/* Host */}
                <span className="text-muted-foreground font-medium pt-0.5">Host / Name</span>
                <div className="flex items-start gap-1">
                  <code className="bg-muted rounded px-1.5 py-0.5 font-mono text-[11px] break-all flex-1">
                    {rec.host}
                  </code>
                  <CopyButton value={rec.host} />
                </div>
                {/* Type */}
                <span className="text-muted-foreground font-medium pt-0.5">Type</span>
                <code className="bg-muted rounded px-1.5 py-0.5 font-mono text-[11px] w-fit">
                  {rec.type}
                </code>
                {/* Value */}
                <span className="text-muted-foreground font-medium pt-0.5">Value</span>
                <div className="flex items-start gap-1">
                  <code className="bg-muted rounded px-1.5 py-0.5 font-mono text-[11px] break-all flex-1 whitespace-pre-wrap">
                    {rec.value}
                  </code>
                  <CopyButton value={rec.value} />
                </div>
              </div>

              <p className="text-[11px] text-muted-foreground leading-relaxed border-t pt-2">
                ℹ️ {rec.note}
              </p>

              {/* Show what was actually found if it failed */}
              {found === false && checkResult && (checkResult[key] as DnsRecordResult).detail && (
                <p className="text-[11px] text-rose-600 bg-rose-50 rounded px-2 py-1">
                  DNS lookup result: {(checkResult[key] as DnsRecordResult).detail}
                </p>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

/* ── Page ──────────────────────────────────────────────────────────── */

export function DomainsPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [domainInput, setDomainInput] = useState("");
  const [checkingId, setCheckingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DomainRow | null>(null);
  const [lastCheckResults, setLastCheckResults] = useState<Record<string, DnsCheckResult>>({});
  const [creationResult, setCreationResult] = useState<DnsCheckResult | null>(null);
  // Which domain's DNS Guide is open
  const [guideTarget, setGuideTarget] = useState<{ domain: DomainRow; result: DnsCheckResult | null } | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["domains"],
    queryFn: () => http.get<unknown>("/api/v1/domains").then(normaliseDomains),
  });

  const domains = data ?? [];

  const { page, pageSize, total, pageItems, setPage, setPageSize } =
    usePagination({ items: domains, initialPageSize: 15 });

  const createMutation = useMutation({
    mutationFn: (body: { domain: string }) =>
      http.post<DomainRow>("/api/v1/domains", body),
    onSuccess: async (created) => {
      toast.success("Domain added — running initial DNS check…");
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      setDomainInput("");
      try {
        const result = await http.post<DnsCheckResult>("/api/v1/domains/dns-check", {
          domain: created.domainName,
        });
        setCreationResult(result);
        await http.put(`/api/v1/domains/${created.id}`, {
          spfStatus: result.spf.found,
          dkimStatus: result.dkim.found,
          dmarcStatus: result.dmarc.found,
        });
        queryClient.invalidateQueries({ queryKey: ["domains"] });
      } catch {
        toast.error("Initial DNS check failed — you can retry from the list");
      }
    },
    onError: () => toast.error("Failed to add domain"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/domains/${id}`),
    onSuccess: () => {
      toast.success("Domain removed");
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to remove domain"),
  });

  const dnsCheckMutation = useMutation({
    mutationFn: async ({ id, domain }: { id: string; domain: string }) => {
      const result = await http.post<DnsCheckResult>("/api/v1/domains/dns-check", { domain });
      await http.put(`/api/v1/domains/${id}`, {
        spfStatus: result.spf.found,
        dkimStatus: result.dkim.found,
        dmarcStatus: result.dmarc.found,
      });
      return { id, result };
    },
    onSuccess: ({ id, result }) => {
      setLastCheckResults((prev) => ({ ...prev, [id]: result }));
      // Auto-open the DNS guide if any record failed
      const dom = domains.find((d) => d.id === id);
      if (dom && !result.allPassed) {
        setGuideTarget({ domain: dom, result });
        const failed = [
          !result.mx.found && "MX",
          !result.spf.found && "SPF",
          !result.dkim.found && "DKIM",
          !result.dmarc.found && "DMARC",
        ].filter(Boolean).join(", ");
        toast.warning(`Missing records: ${failed} — DNS Setup Guide opened below`);
      } else {
        toast.success(`All DNS records verified for ${result.domain} ✓`);
      }
      queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: () => toast.error("DNS check failed"),
    onSettled: () => setCheckingId(null),
  });

  const autoWarmMutation = useMutation({
    mutationFn: (domainId: string) =>
      http.post<DomainRow>(`/api/v1/domains/${domainId}/auto-warm`, {}),
    onSuccess: (res) => {
      toast.success(`Advanced to week ${res.warmingWeek} (${res.dailySendLimit}/day)`);
      queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: () => toast.error("Failed to advance warming — may already be fully warm"),
  });

  function handleAdd(e: FormEvent) {
    e.preventDefault();
    const parsed = DomainCreateSchema.safeParse({ domain: domainInput.trim() });
    if (!parsed.success) { toast.error(formatZodError(parsed.error)); return; }
    setCreationResult(null);
    createMutation.mutate({ domain: parsed.data.domain });
  }

  function handleCheck(d: DomainRow) {
    setCheckingId(d.id);
    dnsCheckMutation.mutate({ id: d.id, domain: d.domainName });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sending Domains"
        description="Manage sending domains, verify DNS records, and track warm-up status."
        actions={
          <Button onClick={() => { setCreationResult(null); setDialogOpen(true); }}>
            <Plus className="h-4 w-4" /> Add Domain
          </Button>
        }
      />

      {/* Warming schedule */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Domain Warming Schedule</CardTitle>
          <CardDescription className="text-xs">
            7-step ramp — OUTRENA throttles sends to protect your sender reputation.
            Use "Auto-warm" to advance a step immediately.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
            {WARMING_SCHEDULE.map((limit, i) => {
              const week = i + 1;
              const domainsAtWeek = domains.filter((d) => d.warmingWeek === week).length;
              return (
                <div key={week} className="text-center p-2 rounded-lg bg-muted relative">
                  {domainsAtWeek > 0 && (
                    <span className="absolute -top-1.5 -right-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
                      {domainsAtWeek}
                    </span>
                  )}
                  <p className="text-lg font-bold">{limit}</p>
                  <p className="text-xs text-muted-foreground">emails/day</p>
                  <p className="text-xs text-muted-foreground">Week {week}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* DNS Setup Guide — shown when a check fails */}
      {guideTarget && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-amber-600" />
              DNS Setup Required for {guideTarget.domain.domainName}
            </h3>
            <Button variant="ghost" size="sm" onClick={() => setGuideTarget(null)}>
              Dismiss
            </Button>
          </div>
          <DnsSetupGuide
            domain={guideTarget.domain.domainName}
            checkResult={guideTarget.result}
          />
        </div>
      )}

      {/* Domains table */}
      {isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Failed to load sending domains.</p>
            <Button onClick={() => refetch()} className="mt-4">Retry</Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Domains</CardTitle>
            <CardDescription>
              SPF, DKIM, and DMARC must all pass. Click "Verify DNS" to check — if any
              fail, a setup guide will appear showing exactly what to add.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : domains.length === 0 ? (
              <EmptyState
                icon={<Globe className="h-6 w-6" />}
                title="No sending domains"
                description="Add a domain to begin warm-up and DNS verification."
                action={<Button onClick={() => setDialogOpen(true)}><Plus className="h-4 w-4" /> Add Domain</Button>}
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Domain</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>MX</TableHead>
                    <TableHead>SPF</TableHead>
                    <TableHead>DKIM</TableHead>
                    <TableHead>DMARC</TableHead>
                    <TableHead>Warming Week</TableHead>
                    <TableHead>Daily Limit</TableHead>
                    <TableHead>Last Check</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pageItems.map((d) => {
                    const isChecking = checkingId === d.id;
                    const lastResult = lastCheckResults[d.id];
                    const status = deriveStatus(d, isChecking);
                    return (
                      <TableRow key={d.id}>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            <Globe className="h-4 w-4 text-muted-foreground" />
                            {d.domainName}
                          </div>
                        </TableCell>
                        <TableCell>{statusBadge(status)}</TableCell>
                        <TableCell>{recordBadge(lastResult?.mx ?? (d.spfStatus ? { name:"MX", found:true, records:[], detail:null } : undefined))}</TableCell>
                        <TableCell>{recordBadge(lastResult?.spf ?? (d.spfStatus ? { name:"SPF", found:true, records:[], detail:null } : undefined))}</TableCell>
                        <TableCell>{recordBadge(lastResult?.dkim ?? (d.dkimStatus ? { name:"DKIM", found:true, records:[], detail:null } : undefined))}</TableCell>
                        <TableCell>{recordBadge(lastResult?.dmarc ?? (d.dmarcStatus ? { name:"DMARC", found:true, records:[], detail:null } : undefined))}</TableCell>
                        <TableCell>
                          <Badge
                            variant={d.warmingWeek >= WARMING_SCHEDULE.length ? "outline" : d.warmingWeek >= 2 ? "outline" : "secondary"}
                            className={d.warmingWeek >= WARMING_SCHEDULE.length ? "bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px]" : "text-[10px]"}
                          >
                            Wk {d.warmingWeek}/{WARMING_SCHEDULE.length}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs tabular-nums">{d.dailySendLimit}/day</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{formatDate(d.lastChecked)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            {/* DNS Setup Guide button */}
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setGuideTarget({ domain: d, result: lastResult ?? null })}
                                >
                                  <BookOpen className="h-3.5 w-3.5" />
                                  Setup
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Show DNS records to add to your registrar</TooltipContent>
                            </Tooltip>
                            {d.warmingWeek < WARMING_SCHEDULE.length && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => autoWarmMutation.mutate(d.id)}
                                    disabled={autoWarmMutation.isPending}
                                  >
                                    <Zap className="h-3.5 w-3.5" /> Auto-warm
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>Advance one warming week</TooltipContent>
                              </Tooltip>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleCheck(d)}
                              disabled={isChecking}
                            >
                              {isChecking
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <RefreshCw className="h-3.5 w-3.5" />}
                              {isChecking ? "Checking…" : "Verify DNS"}
                            </Button>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => setDeleteTarget(d)}
                                >
                                  <Trash2 className="h-4 w-4 text-destructive" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Delete domain</TooltipContent>
                            </Tooltip>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          </CardContent>
        </Card>
      )}

      {/* Add Domain dialog */}
      <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) { setDomainInput(""); setCreationResult(null); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Sending Domain</DialogTitle>
            <DialogDescription>
              Enter a subdomain you control (e.g. mail.yourcompany.com). After adding,
              we'll check your DNS and show you exactly which records to configure.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAdd} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="domain">Domain</Label>
              <Input
                id="domain"
                placeholder="mail.yourcompany.com"
                value={domainInput}
                onChange={(e) => setDomainInput(e.target.value)}
                required
              />
            </div>

            {createMutation.isPending && (
              <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                <Loader2 className="h-3 w-3 animate-spin" />
                Adding domain and checking DNS records…
              </p>
            )}

            {/* Show DNS check result + required records inline after creation */}
            {creationResult && (
              <div className="space-y-3">
                <div className="space-y-2 rounded-md border p-3 bg-muted/30">
                  <p className="text-xs font-medium flex items-center gap-1.5">
                    <Info className="h-3.5 w-3.5" />
                    Initial DNS check for {creationResult.domain}
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {(["mx", "spf", "dkim", "dmarc"] as const).map((key) => (
                      <div key={key} className="flex items-center justify-between rounded border bg-background px-2 py-1.5">
                        <span className="font-medium uppercase">{key}</span>
                        {recordBadge(creationResult[key])}
                      </div>
                    ))}
                  </div>
                </div>
                {!creationResult.allPassed && (
                  <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3">
                    <p className="font-medium mb-1">Some records are missing — that's normal for a new domain.</p>
                    <p>Close this dialog and click <strong>Setup</strong> on the domain row to see the exact DNS records to add to your registrar.</p>
                  </div>
                )}
              </div>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                {creationResult ? "Close" : "Cancel"}
              </Button>
              {!creationResult && (
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Add domain
                </Button>
              )}
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={Boolean(deleteTarget)} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete sending domain?</DialogTitle>
            <DialogDescription>
              "{deleteTarget?.domainName}" will be permanently removed and all warm-up progress lost.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}