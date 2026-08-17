// // /**
// //  * CollateralsPage.tsx — OUTRENA Phase 4 (Task 3-C)
// //  *
// //  * Collaterals (case studies, whitepapers, demos, one-pagers) CRUD + campaign
// //  * linking. Table + add dialog + per-row link-to-campaign dialog.
// //  */
// // import { useState } from "react";
// // import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// // import {
// //   FileText,
// //   Link2,
// //   MoreHorizontal,
// //   Paperclip,
// //   Plus,
// //   Search,
// //   Trash2,
// //   Unlink,
// // } from "lucide-react";
// // import { toast } from "sonner";

// // import { http } from "@/services/apiClient";
// // import { ErrorState } from "@/components/ui/error-state";
// // import { Pagination, usePagination } from "@/components/ui/pagination";
// // import { formatDate } from "@/lib/utils";
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
// // import {
// //   DropdownMenu,
// //   DropdownMenuItem,
// //   DropdownMenuLabel,
// //   DropdownMenuSeparator,
// //   DropdownMenuTrigger,
// //   DropdownMenuContent,
// // } from "@/components/ui/dropdown-menu";
// // import {
// //   Tooltip,
// //   TooltipContent,
// //   TooltipTrigger,
// // } from "@/components/ui/tooltip";
// // import { EmptyState } from "@/components/ui/empty-state";
// // import { Input } from "@/components/ui/input";
// // import { Label } from "@/components/ui/label";
// // import { PageHeader } from "@/components/ui/page-header";
// // import { NativeSelect as Select } from "@/components/ui/select";
// // import { Skeleton } from "@/components/ui/skeleton";
// // import {
// //   Table,
// //   TableBody,
// //   TableCell,
// //   TableHead,
// //   TableHeader,
// //   TableRow,
// // } from "@/components/ui/table";

// // /* ── Types & mocks ──────────────────────────────────────────────────────── */

// // type CollateralType = "case_study" | "whitepaper" | "demo" | "one_pager";

// // interface Collateral {
// //   id: string;
// //   name: string;
// //   type: CollateralType;
// //   url: string;
// //   industry: string | null;
// //   linkedCampaigns: { id: string; name: string }[];
// //   createdAt: string;
// //   updatedAt: string;
// // }

// // interface CampaignLite {
// //   id: string;
// //   name: string;
// // }

// // const TYPES: CollateralType[] = ["case_study", "whitepaper", "demo", "one_pager"];

// // const TYPE_VARIANT: Record<CollateralType, "default" | "secondary" | "outline" | "success"> = {
// //   case_study: "success",
// //   whitepaper: "default",
// //   demo: "secondary",
// //   one_pager: "outline",
// // };

// // const MOCK_CAMPAIGNS: CampaignLite[] = [
// //   { id: "c1", name: "Q1 Outbound — Fintech Ops" },
// //   { id: "c2", name: "Cybersec SOC Automation" },
// //   { id: "c3", name: "Healthcare Payer RPA" },
// //   { id: "c4", name: "Manufacturing Supply-Chain" },
// // ];

// // const MOCK_COLLATERALS: Collateral[] = [
// //   {
// //     id: "col1",
// //     name: "Northbeam Case Study — 60% Faster Close",
// //     type: "case_study",
// //     url: "https://assets.outrena.io/case-studies/northbeam.pdf",
// //     industry: "Fintech",
// //     linkedCampaigns: [{ id: "c1", name: "Q1 Outbound — Fintech Ops" }],
// //     createdAt: "2024-11-10T10:00:00Z",
// //     updatedAt: "2024-12-15T14:00:00Z",
// //   },
// //   {
// //     id: "col2",
// //     name: "AI Reconciliation Whitepaper",
// //     type: "whitepaper",
// //     url: "https://assets.outrena.io/whitepapers/ai-reconciliation.pdf",
// //     industry: "Fintech",
// //     linkedCampaigns: [{ id: "c1", name: "Q1 Outbound — Fintech Ops" }],
// //     createdAt: "2024-10-05T09:00:00Z",
// //     updatedAt: "2024-12-01T12:00:00Z",
// //   },
// //   {
// //     id: "col3",
// //     name: "OUTRENA Product Demo (5 min)",
// //     type: "demo",
// //     url: "https://assets.outrena.io/demos/5min-overview.mp4",
// //     industry: null,
// //     linkedCampaigns: [
// //       { id: "c1", name: "Q1 Outbound — Fintech Ops" },
// //       { id: "c2", name: "Cybersec SOC Automation" },
// //     ],
// //     createdAt: "2024-09-20T08:00:00Z",
// //     updatedAt: "2024-11-25T15:00:00Z",
// //   },
// //   {
// //     id: "col4",
// //     name: "SOC Automation One-Pager",
// //     type: "one_pager",
// //     url: "https://assets.outrena.io/one-pagers/soc-automation.pdf",
// //     industry: "Cybersecurity",
// //     linkedCampaigns: [{ id: "c2", name: "Cybersec SOC Automation" }],
// //     createdAt: "2024-08-12T11:00:00Z",
// //     updatedAt: "2024-11-01T09:00:00Z",
// //   },
// //   {
// //     id: "col5",
// //     name: "Payer RPA ROI Calculator",
// //     type: "demo",
// //     url: "https://assets.outrena.io/demos/payer-roi-calc.html",
// //     industry: "Healthcare",
// //     linkedCampaigns: [],
// //     createdAt: "2024-12-01T13:00:00Z",
// //     updatedAt: "2024-12-20T10:00:00Z",
// //   },
// //   {
// //     id: "col6",
// //     name: "Supply-Chain Resilience Brief",
// //     type: "whitepaper",
// //     url: "https://assets.outrena.io/whitepapers/supply-chain.pdf",
// //     industry: "Manufacturing",
// //     linkedCampaigns: [{ id: "c4", name: "Manufacturing Supply-Chain" }],
// //     createdAt: "2024-11-18T16:00:00Z",
// //     updatedAt: "2024-12-22T11:30:00Z",
// //   },
// // ];

// // /* ── Page ───────────────────────────────────────────────────────────────── */

// // export function CollateralsPage() {
// //   const qc = useQueryClient();
// //   const [search, setSearch] = useState("");
// //   const [typeFilter, setTypeFilter] = useState<string>("all");
// //   const [addOpen, setAddOpen] = useState(false);
// //   const [deleteTarget, setDeleteTarget] = useState<Collateral | null>(null);
// //   const [linkTarget, setLinkTarget] = useState<Collateral | null>(null);
// //   const [linkCampaignId, setLinkCampaignId] = useState("");

// //   const [form, setForm] = useState<{ name: string; type: CollateralType; url: string; industry: string }>({
// //     name: "",
// //     type: "case_study",
// //     url: "",
// //     industry: "",
// //   });

// //   const { data: apiCampaigns } = useQuery<CampaignLite[]>({
// //     queryKey: ["campaigns"],
// //     queryFn: () => http.get<any>("/api/v1/campaigns")
// //       .then((r: any) => Array.isArray(r) ? r : (r?.items ?? [])),
// //     retry: false,
// //   });
// //   const campaigns = apiCampaigns ?? MOCK_CAMPAIGNS;

// //   const { data: apiCollaterals, isLoading , isError, error, refetch } = useQuery({
// //     queryKey: ["collaterals"],
// //     queryFn: () => http.get<Collateral[]>("/api/v1/collaterals"),
// //     retry: false,
// //   });
// //   const collaterals = apiCollaterals ?? MOCK_COLLATERALS;

// //   const filtered = collaterals.filter((c) => {
// //     const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase());
// //     const matchesType = typeFilter === "all" || c.type === typeFilter;
// //     return matchesSearch && matchesType;
// //   });


// //   const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: filtered, initialPageSize: 15 });

// //   const createMut = useMutation({
// //     mutationFn: (body: { name: string; type: CollateralType; url: string; industry: string }) =>
// //       http.post<Collateral>("/api/v1/collaterals", body),
// //     onSuccess: () => {
// //       toast.success("Collateral added");
// //       qc.invalidateQueries({ queryKey: ["collaterals"] });
// //       setAddOpen(false);
// //       setForm({ name: "", type: "case_study", url: "", industry: "" });
// //     },
// //     onError: () => toast.error("Failed to add collateral"),
// //   });

// //   const deleteMut = useMutation({
// //     mutationFn: (id: string) => http.delete<{ message: string }>(`/api/v1/collaterals/${id}`),
// //     onSuccess: () => {
// //       toast.success("Collateral deleted");
// //       qc.invalidateQueries({ queryKey: ["collaterals"] });
// //       setDeleteTarget(null);
// //     },
// //     onError: () => toast.error("Failed to delete collateral"),
// //   });

// //   const linkMut = useMutation({
// //     mutationFn: ({ collateralId, campaignId }: { collateralId: string; campaignId: string }) =>
// //       http.post<{ linkId: string }>("/api/v1/collaterals/link", { collateralId, campaignId }),
// //     onSuccess: () => {
// //       toast.success("Collateral linked to campaign");
// //       qc.invalidateQueries({ queryKey: ["collaterals"] });
// //       setLinkTarget(null);
// //       setLinkCampaignId("");
// //     },
// //     onError: () => toast.error("Failed to link collateral"),
// //   });

// //   function handleAdd() {
// //     if (!form.name.trim() || !form.url.trim()) {
// //       toast.error("Name and URL are required");
// //       return;
// //     }
// //     createMut.mutate(form);
// //   }

// //   function handleLink() {
// //     if (!linkTarget || !linkCampaignId) {
// //       toast.error("Pick a campaign to link");
// //       return;
// //     }
// //     linkMut.mutate({ collateralId: linkTarget.id, campaignId: linkCampaignId });
// //   }

// //   return (
// //     <div className="space-y-6">
// //       <PageHeader
// //         title="Collaterals"
// //         description="Case studies, whitepapers, demos, and one-pagers — linked to campaigns for personalisation."
// //         actions={
// //           <Button size="sm" onClick={() => setAddOpen(true)}>
// //             <Plus className="h-4 w-4" /> Add Collateral
// //           </Button>
// //         }
// //       />

// // {/* Task 2-b finding 14: explicit error + retry state */}
// //         {isError ? (
// //           <ErrorState
// //             title="Failed to load collaterals"
// //             error={error}
// //             onRetry={() => refetch()}
// //           />
// //         ) : null}

// //               <Card>
// //         <CardContent className="p-4">
// //           <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
// //             <div className="relative flex-1">
// //               <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
// //               <Input
// //                 placeholder="Search collaterals…"
// //                 value={search}
// //                 onChange={(e) => setSearch(e.target.value)}
// //                 className="pl-9"
// //               />
// //             </div>
// //             <Select
// //               value={typeFilter}
// //               onChange={(e) => setTypeFilter(e.target.value)}
// //               className="sm:w-44"
// //             >
// //               <option value="all">All types</option>
// //               {TYPES.map((t) => (
// //                 <option key={t} value={t}>
// //                   {t.replace("_", " ")}
// //                 </option>
// //               ))}
// //             </Select>
// //           </div>
// //         </CardContent>
// //       </Card>

// //       <Card>
// //         <CardContent className="p-0">
// //           {isLoading ? (
// //             <div className="space-y-2 p-4">
// //               {Array.from({ length: 5 }).map((_, i) => (
// //                 <Skeleton key={i} className="h-12 w-full" />
// //               ))}
// //             </div>
// //           ) : filtered.length === 0 ? (
// //             <EmptyState
// //               icon={<Paperclip className="h-6 w-6" />}
// //               title="No collaterals found"
// //               description="Add your first collateral to start linking it to campaigns."
// //             />
// //           ) : (
// //             <Table>
// //               <TableHeader>
// //                 <TableRow>
// //                   <TableHead>Name</TableHead>
// //                   <TableHead>Type</TableHead>
// //                   <TableHead>Industry</TableHead>
// //                   <TableHead>URL</TableHead>
// //                   <TableHead className="text-right">Linked campaigns</TableHead>
// //                   <TableHead>Updated</TableHead>
// //                   <TableHead className="text-right">Actions</TableHead>
// //                 </TableRow>
// //               </TableHeader>
// //               <TableBody>
// //                 {pageItems.map((c) => (
// //                   <TableRow key={c.id}>
// //                     <TableCell className="font-medium">{c.name}</TableCell>
// //                     <TableCell>
// //                       <Badge variant={TYPE_VARIANT[c.type]}>
// //                         {c.type.replace("_", " ")}
// //                       </Badge>
// //                     </TableCell>
// //                     <TableCell>{c.industry ?? "—"}</TableCell>
// //                     <TableCell className="max-w-[16rem]">
// //                       <a
// //                         href={c.url}
// //                         target="_blank"
// //                         rel="noreferrer"
// //                         className="truncate text-primary underline-offset-4 hover:underline"
// //                       >
// //                         {c.url}
// //                       </a>
// //                     </TableCell>
// //                     <TableCell className="text-right">
// //                       {(c.linkedCampaigns ?? []).length === 0 ? (  /* BUG-20 FIX */
// //                         <span className="text-muted-foreground">0</span>
// //                       ) : (
// //                         <Badge variant="secondary">{(c.linkedCampaigns ?? []).length}</Badge>
// //                       )}
// //                     </TableCell>
// //                     <TableCell className="text-muted-foreground">{formatDate(c.updatedAt)}</TableCell>
// //                     <TableCell className="text-right">
// //                       <DropdownMenu>
// //                         <Tooltip>
// //                           <TooltipTrigger asChild>
// //                             <DropdownMenuTrigger asChild>
// //                               <Button variant="ghost" size="icon" aria-label="Row actions">
// //                                 <MoreHorizontal className="h-4 w-4" />
// //                               </Button>
// //                             </DropdownMenuTrigger>
// //                           </TooltipTrigger>
// //                           <TooltipContent>More actions for this collateral</TooltipContent>
// //                         </Tooltip>
// //                         <DropdownMenuContent align="end">
// //                           <DropdownMenuLabel>Actions</DropdownMenuLabel>
// //                           <DropdownMenuItem
// //                             onClick={() => {
// //                               setLinkTarget(c);
// //                               setLinkCampaignId("");
// //                             }}
// //                           >
// //                             <Link2 className="h-4 w-4" /> Link to Campaign
// //                           </DropdownMenuItem>
// //                           <DropdownMenuSeparator />
// //                           <DropdownMenuItem destructive onClick={() => setDeleteTarget(c)}>
// //                             <Trash2 className="h-4 w-4" /> Delete
// //                           </DropdownMenuItem>
// //                         </DropdownMenuContent>
// //                       </DropdownMenu>
// //                     </TableCell>
// //                   </TableRow>
// //                 ))}
// //               </TableBody>
// //             </Table>
// //           )}
        
// //               <Pagination
// //                 page={page}
// //                 pageSize={pageSize}
// //                 total={total}
// //                 onPageChange={setPage}
// //                 onPageSizeChange={setPageSize}
// //               />
// //             </CardContent>
// //       </Card>

// //       {/* Add Collateral dialog */}
// //       <Dialog open={addOpen} onOpenChange={setAddOpen}>
// //         <DialogClose onClose={() => setAddOpen(false)} />
// //         <DialogHeader>
// //           <DialogTitle>Add Collateral</DialogTitle>
// //           <DialogDescription>
// //             Add a case study, whitepaper, demo, or one-pager to your library.
// //           </DialogDescription>
// //         </DialogHeader>
// //         <div className="space-y-4">
// //           <div className="space-y-2">
// //             <Label htmlFor="col-name">Name</Label>
// //             <Input
// //               id="col-name"
// //               value={form.name}
// //               onChange={(e) => setForm({ ...form, name: e.target.value })}
// //               placeholder="e.g. Northbeam Case Study"
// //             />
// //           </div>
// //           <div className="grid grid-cols-2 gap-3">
// //             <div className="space-y-2">
// //               <Label htmlFor="col-type">Type</Label>
// //               <Select
// //                 id="col-type"
// //                 value={form.type}
// //                 onChange={(e) => setForm({ ...form, type: e.target.value as CollateralType })}
// //               >
// //                 {TYPES.map((t) => (
// //                   <option key={t} value={t}>
// //                     {t.replace("_", " ")}
// //                   </option>
// //                 ))}
// //               </Select>
// //             </div>
// //             <div className="space-y-2">
// //               <Label htmlFor="col-industry">Industry (optional)</Label>
// //               <Input
// //                 id="col-industry"
// //                 value={form.industry}
// //                 onChange={(e) => setForm({ ...form, industry: e.target.value })}
// //                 placeholder="Fintech"
// //               />
// //             </div>
// //           </div>
// //           <div className="space-y-2">
// //             <Label htmlFor="col-url">URL</Label>
// //             <Input
// //               id="col-url"
// //               value={form.url}
// //               onChange={(e) => setForm({ ...form, url: e.target.value })}
// //               placeholder="https://assets.outrena.io/…"
// //             />
// //           </div>
// //         </div>
// //         <DialogFooter>
// //           <Button variant="outline" onClick={() => setAddOpen(false)}>
// //             Cancel
// //           </Button>
// //           <Button onClick={handleAdd} disabled={createMut.isPending}>
// //             {createMut.isPending ? "Adding…" : "Add Collateral"}
// //           </Button>
// //         </DialogFooter>
// //       </Dialog>

// //       {/* Delete dialog */}
// //       <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
// //         <DialogClose onClose={() => setDeleteTarget(null)} />
// //         <DialogHeader>
// //           <DialogTitle>Delete collateral?</DialogTitle>
// //           <DialogDescription>
// //             “{deleteTarget?.name}” will be removed from your library and unlinked from all campaigns.
// //           </DialogDescription>
// //         </DialogHeader>
// //         <DialogFooter>
// //           <Button variant="outline" onClick={() => setDeleteTarget(null)}>
// //             Cancel
// //           </Button>
// //           <Button
// //             variant="destructive"
// //             onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
// //             disabled={deleteMut.isPending}
// //           >
// //             {deleteMut.isPending ? "Deleting…" : "Delete"}
// //           </Button>
// //         </DialogFooter>
// //       </Dialog>

// //       {/* Link dialog */}
// //       <Dialog open={!!linkTarget} onOpenChange={(o) => !o && setLinkTarget(null)}>
// //         <DialogClose onClose={() => setLinkTarget(null)} />
// //         <DialogHeader>
// //           <DialogTitle>Link to Campaign</DialogTitle>
// //           <DialogDescription>
// //             {linkTarget && `Linking “${linkTarget.name}” — pick a campaign.`}
// //           </DialogDescription>
// //         </DialogHeader>
// //         <div className="space-y-3">
// //           {linkTarget && (linkTarget.linkedCampaigns ?? []).length > 0 && (  /* BUG-20 FIX */
// //             <div className="rounded-md border bg-muted/30 p-3">
// //               <p className="mb-2 text-xs font-medium text-muted-foreground">
// //                 Currently linked to
// //               </p>
// //               <div className="flex flex-wrap gap-1.5">
// //                 {linkTarget.linkedCampaigns.map((lc) => (
// //                   <Badge key={lc.id} variant="secondary" className="gap-1">
// //                     <Unlink className="h-3 w-3" />
// //                     {lc.name}
// //                   </Badge>
// //                 ))}
// //               </div>
// //             </div>
// //           )}
// //           <div className="space-y-2">
// //             <Label htmlFor="link-camp">Campaign</Label>
// //             <Select
// //               id="link-camp"
// //               value={linkCampaignId}
// //               onChange={(e) => setLinkCampaignId(e.target.value)}
// //             >
// //               <option value="">— Select campaign —</option>
// //               {campaigns.map((c) => (
// //                 <option key={c.id} value={c.id}>
// //                   {c.name}
// //                 </option>
// //               ))}
// //             </Select>
// //           </div>
// //         </div>
// //         <DialogFooter>
// //           <Button variant="outline" onClick={() => setLinkTarget(null)}>
// //             Cancel
// //           </Button>
// //           <Button onClick={handleLink} disabled={linkMut.isPending}>
// //             {linkMut.isPending ? (
// //               <>
// //                 <FileText className="h-4 w-4 animate-spin" /> Linking…
// //               </>
// //             ) : (
// //               <>
// //                 <Link2 className="h-4 w-4" /> Link
// //               </>
// //             )}
// //           </Button>
// //         </DialogFooter>
// //       </Dialog>
// //     </div>
// //   );
// // }

// /**
//  * CollateralsPage.tsx — Shared sales asset library.
//  *
//  * Gaps closed:
//  *   COL-1  List — grid cards with name, type badge+icon, URL/content
//  *          preview, campaign linkage count, description
//  *   COL-2  Add / Edit dialog: name, type selector, URL, content,
//  *          description — all wired to real API
//  *   COL-3  Link collateral to campaign — campaign selector dialog
//  *          POST /api/v1/collaterals/link { collateralId, campaignId }
//  *   COL-4  Type icons per collateral type
//  *
//  * API contract:
//  *   GET    /api/v1/collaterals              → CollateralResponse[]
//  *   POST   /api/v1/collaterals              → CollateralResponse (201)
//  *   PUT    /api/v1/collaterals/{id}         → CollateralResponse
//  *   DELETE /api/v1/collaterals/{id}         → 204
//  *   POST   /api/v1/collaterals/link         → CampaignCollateralLinkResponse (201)
//  *   GET    /api/v1/campaigns/my             → { items: CampaignItem[] }
//  *
//  * CollateralResponse: { id, name, type, url, content, description,
//  *   fileName, fileSize, mimeType, createdAt, updatedAt }
//  * Note: no `linkedCampaigns` or `industry` in the API response — these
//  * fields only existed in the old mock data and are absent from the schema.
//  */
// import { useState } from "react";
// import { useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   BookOpen,
//   Briefcase,
//   Calculator,
//   Edit3,
//   ExternalLink,
//   File,
//   FileText,
//   Link2,
//   Paperclip,
//   Plus,
//   Presentation,
//   Search,
//   Trash2,
//   Video,
// } from "lucide-react";
// import { toast } from "sonner";

// import { http } from "@/services/apiClient";
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
// import { Textarea } from "@/components/ui/textarea";
// import { formatDate, truncate } from "@/lib/utils";

// /* ── Types ──────────────────────────────────────────────────────────────── */

// interface CollateralResponse {
//   id: string;
//   name: string;
//   type: string;
//   url: string | null;
//   content: string | null;
//   description: string | null;
//   fileName: string | null;
//   fileSize: number | null;
//   mimeType: string | null;
//   createdAt: string;
//   updatedAt: string;
// }

// interface CampaignItem {
//   id: string;
//   name: string;
// }

// /* ── COL-4 — Type config with icons ─────────────────────────────────────── */

// const COLLATERAL_TYPES: {
//   id: string;
//   label: string;
//   icon: React.ReactNode;
//   badgeColor: string;
// }[] = [
//   {
//     id: "case_study",
//     label: "Case Study",
//     icon: <FileText className="h-4 w-4" />,
//     badgeColor: "bg-emerald-100 text-emerald-700 border-emerald-200",
//   },
//   {
//     id: "one_pager",
//     label: "One-Pager",
//     icon: <File className="h-4 w-4" />,
//     badgeColor: "bg-blue-100 text-blue-700 border-blue-200",
//   },
//   {
//     id: "demo",
//     label: "Demo",
//     icon: <Presentation className="h-4 w-4" />,
//     badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
//   },
//   {
//     id: "whitepaper",
//     label: "Whitepaper",
//     icon: <BookOpen className="h-4 w-4" />,
//     badgeColor: "bg-sky-100 text-sky-700 border-sky-200",
//   },
//   {
//     id: "roi_calculator",
//     label: "ROI Calculator",
//     icon: <Calculator className="h-4 w-4" />,
//     badgeColor: "bg-amber-100 text-amber-700 border-amber-200",
//   },
//   {
//     id: "video",
//     label: "Video",
//     icon: <Video className="h-4 w-4" />,
//     badgeColor: "bg-rose-100 text-rose-700 border-rose-200",
//   },
//   {
//     id: "blog_post",
//     label: "Blog Post",
//     icon: <FileText className="h-4 w-4" />,
//     badgeColor: "bg-orange-100 text-orange-700 border-orange-200",
//   },
//   {
//     id: "other",
//     label: "Other",
//     icon: <Briefcase className="h-4 w-4" />,
//     badgeColor: "bg-slate-100 text-slate-700 border-slate-200",
//   },
// ];

// function getTypeMeta(type: string) {
//   return (
//     COLLATERAL_TYPES.find((t) => t.id === type) ??
//     COLLATERAL_TYPES[COLLATERAL_TYPES.length - 1]
//   );
// }

// /* ── Form state ─────────────────────────────────────────────────────────── */

// interface CollateralForm {
//   name: string;
//   type: string;
//   url: string;
//   content: string;
//   description: string;
// }

// const EMPTY_FORM: CollateralForm = {
//   name: "",
//   type: "case_study",
//   url: "",
//   content: "",
//   description: "",
// };

// /* ── Add / Edit dialog ───────────────────────────────────────────────────── */

// function CollateralFormDialog({
//   open,
//   editing,
//   onOpenChange,
//   onSaved,
// }: {
//   open: boolean;
//   editing: CollateralResponse | null;
//   onOpenChange: (o: boolean) => void;
//   onSaved: () => void;
// }) {
//   const [form, setForm] = useState<CollateralForm>(EMPTY_FORM);
//   const [saving, setSaving] = useState(false);

//   // Sync form when editing target changes
//   useState(() => {
//     if (editing) {
//       setForm({
//         name: editing.name,
//         type: editing.type,
//         url: editing.url ?? "",
//         content: editing.content ?? "",
//         description: editing.description ?? "",
//       });
//     } else {
//       setForm(EMPTY_FORM);
//     }
//   });

//   // Reset on open/close
//   function handleOpenChange(o: boolean) {
//     if (!o) setForm(editing ? {
//       name: editing.name,
//       type: editing.type,
//       url: editing.url ?? "",
//       content: editing.content ?? "",
//       description: editing.description ?? "",
//     } : EMPTY_FORM);
//     onOpenChange(o);
//   }

//   async function handleSave() {
//     if (!form.name.trim()) {
//       toast.error("Name is required");
//       return;
//     }
//     setSaving(true);
//     try {
//       const payload = {
//         name: form.name.trim(),
//         type: form.type,
//         url: form.url.trim() || null,
//         content: form.content.trim() || null,
//         description: form.description.trim() || null,
//       };
//       if (editing) {
//         await http.put(`/api/v1/collaterals/${editing.id}`, payload);
//         toast.success("Collateral updated");
//       } else {
//         await http.post("/api/v1/collaterals", payload);
//         toast.success("Collateral added");
//       }
//       onSaved();
//       onOpenChange(false);
//     } catch {
//       toast.error(editing ? "Failed to update collateral" : "Failed to add collateral");
//     } finally {
//       setSaving(false);
//     }
//   }

//   return (
//     <Dialog open={open} onOpenChange={handleOpenChange}>
//       <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
//         <DialogHeader>
//           <DialogTitle>
//             {editing ? "Edit Collateral" : "Add Collateral"}
//           </DialogTitle>
//           <DialogDescription>
//             Add a sales asset to the shared library. Link it to a campaign so
//             the AI can reference it during email generation.
//           </DialogDescription>
//         </DialogHeader>
//         <div className="space-y-4 py-1">
//           <div className="space-y-2">
//             <Label htmlFor="col-name">Name *</Label>
//             <Input
//               id="col-name"
//               value={form.name}
//               onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
//               placeholder="e.g. Q3 ROI Case Study"
//             />
//           </div>
//           {/* COL-2 — type selector */}
//           <div className="space-y-2">
//             <Label>Type</Label>
//             <Select
//               value={form.type}
//               onValueChange={(v) => setForm((f) => ({ ...f, type: v }))}
//             >
//               <SelectTrigger>
//                 <SelectValue />
//               </SelectTrigger>
//               <SelectContent>
//                 {COLLATERAL_TYPES.map((t) => (
//                   <SelectItem key={t.id} value={t.id}>
//                     <div className="flex items-center gap-2">
//                       {t.icon}
//                       <span>{t.label}</span>
//                     </div>
//                   </SelectItem>
//                 ))}
//               </SelectContent>
//             </Select>
//           </div>
//           {/* COL-2 — URL */}
//           <div className="space-y-2">
//             <Label htmlFor="col-url">URL (link to the asset)</Label>
//             <Input
//               id="col-url"
//               value={form.url}
//               onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
//               placeholder="https://…"
//             />
//           </div>
//           {/* COL-2 — content */}
//           <div className="space-y-2">
//             <Label htmlFor="col-content">
//               Content{" "}
//               <span className="text-muted-foreground text-xs">
//                 (alternative to URL)
//               </span>
//             </Label>
//             <Textarea
//               id="col-content"
//               value={form.content}
//               onChange={(e) =>
//                 setForm((f) => ({ ...f, content: e.target.value }))
//               }
//               placeholder="Paste content directly if no URL…"
//               rows={3}
//             />
//           </div>
//           {/* COL-2 — description */}
//           <div className="space-y-2">
//             <Label htmlFor="col-desc">Description</Label>
//             <Textarea
//               id="col-desc"
//               value={form.description}
//               onChange={(e) =>
//                 setForm((f) => ({ ...f, description: e.target.value }))
//               }
//               placeholder="Brief description of what this collateral covers…"
//               rows={2}
//             />
//           </div>
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={() => onOpenChange(false)}>
//             Cancel
//           </Button>
//           <Button onClick={handleSave} disabled={saving || !form.name.trim()}>
//             {saving
//               ? editing
//                 ? "Saving…"
//                 : "Adding…"
//               : editing
//               ? "Save Changes"
//               : "Add Collateral"}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// /* ── Link to campaign dialog ─────────────────────────────────────────────── */

// function LinkCampaignDialog({
//   collateral,
//   campaigns,
//   onClose,
//   onLinked,
// }: {
//   collateral: CollateralResponse | null;
//   campaigns: CampaignItem[];
//   onClose: () => void;
//   onLinked: () => void;
// }) {
//   const [campaignId, setCampaignId] = useState("");
//   const [linking, setLinking] = useState(false);

//   async function handleLink() {
//     if (!collateral || !campaignId) {
//       toast.error("Pick a campaign to link");
//       return;
//     }
//     setLinking(true);
//     try {
//       await http.post("/api/v1/collaterals/link", {
//         collateralId: collateral.id,
//         campaignId,
//         sortOrder: 0,
//       });
//       toast.success("Linked to campaign");
//       onLinked();
//       onClose();
//     } catch {
//       toast.error("Failed to link collateral");
//     } finally {
//       setLinking(false);
//     }
//   }

//   return (
//     <Dialog open={Boolean(collateral)} onOpenChange={(o) => !o && onClose()}>
//       <DialogContent className="max-w-sm">
//         <DialogHeader>
//           <DialogTitle>Link to Campaign</DialogTitle>
//           <DialogDescription>
//             {collateral
//               ? `Link "${truncate(collateral.name, 40)}" to a campaign so the AI uses it during email generation.`
//               : ""}
//           </DialogDescription>
//         </DialogHeader>
//         <div className="space-y-2 py-1">
//           <Label>Campaign</Label>
//           <Select value={campaignId} onValueChange={setCampaignId}>
//             <SelectTrigger>
//               <SelectValue placeholder="Select a campaign…" />
//             </SelectTrigger>
//             <SelectContent className="max-h-60">
//               {campaigns.length === 0 ? (
//                 <SelectItem value="_none" disabled>
//                   No campaigns available
//                 </SelectItem>
//               ) : (
//                 campaigns.map((c) => (
//                   <SelectItem key={c.id} value={c.id}>
//                     {c.name}
//                   </SelectItem>
//                 ))
//               )}
//             </SelectContent>
//           </Select>
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={onClose}>
//             Cancel
//           </Button>
//           <Button
//             onClick={handleLink}
//             disabled={linking || !campaignId}
//           >
//             <Link2 className="h-4 w-4" />
//             {linking ? "Linking…" : "Link"}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// /* ── Delete dialog ───────────────────────────────────────────────────────── */

// function DeleteDialog({
//   collateral,
//   onClose,
//   onDeleted,
// }: {
//   collateral: CollateralResponse | null;
//   onClose: () => void;
//   onDeleted: () => void;
// }) {
//   const [deleting, setDeleting] = useState(false);

//   async function handleDelete() {
//     if (!collateral) return;
//     setDeleting(true);
//     try {
//       await http.delete(`/api/v1/collaterals/${collateral.id}`);
//       toast.success("Collateral deleted");
//       onDeleted();
//       onClose();
//     } catch {
//       toast.error("Failed to delete collateral");
//     } finally {
//       setDeleting(false);
//     }
//   }

//   return (
//     <Dialog open={Boolean(collateral)} onOpenChange={(o) => !o && onClose()}>
//       <DialogContent>
//         <DialogHeader>
//           <DialogTitle>Delete collateral?</DialogTitle>
//           <DialogDescription>
//             "{collateral?.name}" will be permanently removed from your library
//             and unlinked from all campaigns.
//           </DialogDescription>
//         </DialogHeader>
//         <DialogFooter>
//           <Button variant="outline" onClick={onClose}>
//             Cancel
//           </Button>
//           <Button
//             variant="destructive"
//             onClick={handleDelete}
//             disabled={deleting}
//           >
//             {deleting ? "Deleting…" : "Delete"}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// /* ── Main page ───────────────────────────────────────────────────────────── */

// export function CollateralsPage() {
//   const qc = useQueryClient();
//   const [search, setSearch] = useState("");
//   const [typeFilter, setTypeFilter] = useState("all");
//   const [formOpen, setFormOpen] = useState(false);
//   const [editingCollateral, setEditingCollateral] =
//     useState<CollateralResponse | null>(null);
//   const [deleteTarget, setDeleteTarget] =
//     useState<CollateralResponse | null>(null);
//   const [linkTarget, setLinkTarget] =
//     useState<CollateralResponse | null>(null);

//   /* ── Queries ── */

//   const { data: collaterals = [], isLoading } = useQuery<CollateralResponse[]>({
//     queryKey: ["collaterals"],
//     queryFn: () => http.get<CollateralResponse[]>("/api/v1/collaterals"),
//     retry: false,
//   });

//   const { data: campaignList = [] } = useQuery<CampaignItem[]>({
//     queryKey: ["campaigns", "my"],
//     queryFn: () =>
//       http
//         .get<{ items: CampaignItem[] }>("/api/v1/campaigns/my")
//         .then((r) => r.items ?? []),
//     retry: false,
//   });

//   function invalidate() {
//     qc.invalidateQueries({ queryKey: ["collaterals"] });
//   }

//   /* ── Filtering ── */

//   const filtered = collaterals.filter((c) => {
//     const matchSearch =
//       !search ||
//       c.name.toLowerCase().includes(search.toLowerCase()) ||
//       (c.description ?? "").toLowerCase().includes(search.toLowerCase());
//     const matchType = typeFilter === "all" || c.type === typeFilter;
//     return matchSearch && matchType;
//   });

//   /* ── Type stat counts ── */

//   const typeCounts = Object.fromEntries(
//     COLLATERAL_TYPES.map((t) => [
//       t.id,
//       collaterals.filter((c) => c.type === t.id).length,
//     ])
//   );

//   /* ── Handlers ── */

//   function openAdd() {
//     setEditingCollateral(null);
//     setFormOpen(true);
//   }

//   function openEdit(c: CollateralResponse) {
//     setEditingCollateral(c);
//     setFormOpen(true);
//   }

//   /* ── Render ── */

//   return (
//     <div className="space-y-6">
//       <PageHeader
//         title="Collaterals"
//         description="Shared library of sales assets — case studies, whitepapers, demos, ROI calculators — linked to campaigns as AI context for email generation."
//         actions={
//           <Button size="sm" onClick={openAdd}>
//             <Plus className="h-4 w-4" /> Add Collateral
//           </Button>
//         }
//       />

//       {/* COL-4 — Type stat chips */}
//       <div className="grid grid-cols-4 gap-2 sm:grid-cols-8">
//         {COLLATERAL_TYPES.map((t) => (
//           <Card
//             key={t.id}
//             className="p-3 cursor-pointer hover:bg-muted/40 transition-colors"
//             onClick={() =>
//               setTypeFilter(typeFilter === t.id ? "all" : t.id)
//             }
//           >
//             <div className="flex items-center gap-1.5 mb-1 text-muted-foreground">
//               {t.icon}
//             </div>
//             <p className="text-[10px] font-medium text-muted-foreground truncate">
//               {t.label}
//             </p>
//             <p className="text-xl font-bold">{typeCounts[t.id] ?? 0}</p>
//           </Card>
//         ))}
//       </div>

//       {/* Filters */}
//       <div className="flex items-center gap-3 flex-wrap">
//         <div className="relative flex-1 min-w-[200px]">
//           <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
//           <Input
//             placeholder="Search collaterals…"
//             value={search}
//             onChange={(e) => setSearch(e.target.value)}
//             className="pl-9"
//           />
//         </div>
//         <Select value={typeFilter} onValueChange={setTypeFilter}>
//           <SelectTrigger className="w-[180px]">
//             <SelectValue placeholder="Filter by type" />
//           </SelectTrigger>
//           <SelectContent>
//             <SelectItem value="all">All types</SelectItem>
//             {COLLATERAL_TYPES.map((t) => (
//               <SelectItem key={t.id} value={t.id}>
//                 <div className="flex items-center gap-2">
//                   {t.icon}
//                   {t.label}
//                 </div>
//               </SelectItem>
//             ))}
//           </SelectContent>
//         </Select>
//       </div>

//       {/* COL-1 — Grid */}
//       {isLoading ? (
//         <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
//           {Array.from({ length: 6 }).map((_, i) => (
//             <Skeleton key={i} className="h-44 w-full rounded-lg" />
//           ))}
//         </div>
//       ) : filtered.length === 0 ? (
//         <Card>
//           <CardContent className="py-12">
//             <EmptyState
//               icon={<Paperclip className="h-10 w-10" />}
//               title={
//                 collaterals.length > 0
//                   ? "No collaterals match your filters"
//                   : "No collaterals yet"
//               }
//               description={
//                 collaterals.length > 0
//                   ? "Try adjusting the search or type filter."
//                   : 'Click "Add Collateral" to create your first one.'
//               }
//               action={
//                 collaterals.length === 0 ? (
//                   <Button size="sm" onClick={openAdd}>
//                     <Plus className="h-4 w-4" /> Add Collateral
//                   </Button>
//                 ) : undefined
//               }
//             />
//           </CardContent>
//         </Card>
//       ) : (
//         <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
//           {filtered.map((c) => {
//             const meta = getTypeMeta(c.type);
//             return (
//               <Card
//                 key={c.id}
//                 className="hover:shadow-md transition-shadow flex flex-col"
//               >
//                 <CardHeader className="pb-3">
//                   <div className="flex items-start justify-between gap-2">
//                     {/* COL-4 — type icon + name */}
//                     <div className="flex items-center gap-2 min-w-0">
//                       <span className="text-primary shrink-0">{meta.icon}</span>
//                       <CardTitle className="text-base truncate">
//                         {c.name}
//                       </CardTitle>
//                     </div>
//                     <Badge
//                       variant="outline"
//                       className={`text-xs shrink-0 border ${meta.badgeColor}`}
//                     >
//                       {meta.label}
//                     </Badge>
//                   </div>
//                   {c.description && (
//                     <CardDescription className="text-xs line-clamp-2">
//                       {c.description}
//                     </CardDescription>
//                   )}
//                 </CardHeader>
//                 <CardContent className="flex-1 flex flex-col justify-between space-y-3">
//                   {/* URL or content preview */}
//                   {c.url ? (
//                     <a
//                       href={c.url}
//                       target="_blank"
//                       rel="noopener noreferrer"
//                       className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
//                       onClick={(e) => e.stopPropagation()}
//                     >
//                       <ExternalLink className="h-3 w-3" />
//                       {truncate(c.url, 48)}
//                     </a>
//                   ) : c.content ? (
//                     <p className="text-xs text-muted-foreground italic line-clamp-2">
//                       {truncate(c.content, 100)}
//                     </p>
//                   ) : (
//                     <p className="text-xs text-muted-foreground">
//                       No URL or content
//                     </p>
//                   )}
//                   {/* Meta row */}
//                   <p className="text-[11px] text-muted-foreground">
//                     Updated {formatDate(c.updatedAt)}
//                   </p>
//                   {/* Action buttons */}
//                   <div className="flex items-center gap-2 pt-1">
//                     <Button
//                       size="sm"
//                       variant="outline"
//                       className="h-7 text-xs"
//                       onClick={() => openEdit(c)}
//                     >
//                       <Edit3 className="h-3 w-3" /> Edit
//                     </Button>
//                     {/* COL-3 — link to campaign */}
//                     <Button
//                       size="sm"
//                       variant="outline"
//                       className="h-7 text-xs"
//                       onClick={() => setLinkTarget(c)}
//                     >
//                       <Link2 className="h-3 w-3" /> Link
//                     </Button>
//                     <Button
//                       size="icon"
//                       variant="ghost"
//                       className="h-7 w-7 text-destructive ml-auto"
//                       onClick={() => setDeleteTarget(c)}
//                     >
//                       <Trash2 className="h-3.5 w-3.5" />
//                     </Button>
//                   </div>
//                 </CardContent>
//               </Card>
//             );
//           })}
//         </div>
//       )}

//       {/* COL-2 — Add / Edit dialog */}
//       <CollateralFormDialog
//         open={formOpen}
//         editing={editingCollateral}
//         onOpenChange={(o) => {
//           setFormOpen(o);
//           if (!o) setEditingCollateral(null);
//         }}
//         onSaved={invalidate}
//       />

//       {/* COL-3 — Link to campaign dialog */}
//       <LinkCampaignDialog
//         collateral={linkTarget}
//         campaigns={campaignList}
//         onClose={() => setLinkTarget(null)}
//         onLinked={invalidate}
//       />

//       {/* Delete dialog */}
//       <DeleteDialog
//         collateral={deleteTarget}
//         onClose={() => setDeleteTarget(null)}
//         onDeleted={invalidate}
//       />
//     </div>
//   );
// }
/**
 * CollateralsPage.tsx — Shared sales asset library.
 *
 * FIX: Add Collateral dialog now has two tabs matching the Next.js reference:
 *   • External URL  — name + type + URL + description + brand content/snippet
 *   • Upload File   — file picker that reads the file client-side and submits
 *                     fileName/fileSize/mimeType + content (text) or url (data-url)
 *                     to the existing POST /api/v1/collaterals endpoint.
 *                     Backend CollateralCreate already accepts all these fields.
 *
 * No backend changes required — the existing schema supports all fields.
 */
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Briefcase,
  Calculator,
  Edit3,
  ExternalLink,
  File,
  FileText,
  Globe,
  Link2,
  Loader2,
  Paperclip,
  Plus,
  Presentation,
  Search,
  Trash2,
  Upload,
  Video,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
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
import { Textarea } from "@/components/ui/textarea";
import { formatDate, truncate } from "@/lib/utils";

/* ── Types ──────────────────────────────────────────────────────────────── */

interface CollateralResponse {
  id: string;
  name: string;
  type: string;
  url: string | null;
  content: string | null;
  description: string | null;
  fileName: string | null;
  fileSize: number | null;
  mimeType: string | null;
  createdAt: string;
  updatedAt: string;
}

interface CampaignItem {
  id: string;
  name: string;
}

/* ── Type config ─────────────────────────────────────────────────────────── */

const COLLATERAL_TYPES: {
  id: string;
  label: string;
  icon: React.ReactNode;
  badgeColor: string;
}[] = [
  {
    id: "case_study",
    label: "Case Study",
    icon: <FileText className="h-4 w-4" />,
    badgeColor: "bg-emerald-100 text-emerald-700 border-emerald-200",
  },
  {
    id: "one_pager",
    label: "One-Pager",
    icon: <File className="h-4 w-4" />,
    badgeColor: "bg-blue-100 text-blue-700 border-blue-200",
  },
  {
    id: "demo",
    label: "Demo",
    icon: <Presentation className="h-4 w-4" />,
    badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
  },
  {
    id: "whitepaper",
    label: "Whitepaper",
    icon: <BookOpen className="h-4 w-4" />,
    badgeColor: "bg-sky-100 text-sky-700 border-sky-200",
  },
  {
    id: "roi_calculator",
    label: "ROI Calculator",
    icon: <Calculator className="h-4 w-4" />,
    badgeColor: "bg-amber-100 text-amber-700 border-amber-200",
  },
  {
    id: "video",
    label: "Video",
    icon: <Video className="h-4 w-4" />,
    badgeColor: "bg-rose-100 text-rose-700 border-rose-200",
  },
  {
    id: "blog_post",
    label: "Blog Post",
    icon: <FileText className="h-4 w-4" />,
    badgeColor: "bg-orange-100 text-orange-700 border-orange-200",
  },
  {
    id: "other",
    label: "Other",
    icon: <Briefcase className="h-4 w-4" />,
    badgeColor: "bg-slate-100 text-slate-700 border-slate-200",
  },
];

function getTypeMeta(type: string) {
  return (
    COLLATERAL_TYPES.find((t) => t.id === type) ??
    COLLATERAL_TYPES[COLLATERAL_TYPES.length - 1]
  );
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Accepted file types for the file picker
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.ms-powerpoint",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain",
  "text/markdown",
  "text/csv",
].join(",");

/* ── Add / Edit dialog ───────────────────────────────────────────────────── */

type DialogTab = "url" | "upload";

interface UploadedFile {
  file: File;
  // For text-based files (PDF text, .txt, .md, .csv) we read as text → content field
  // For binary files we store as data-url → url field
  readAs: "text" | "dataurl";
  content: string | null;       // populated when readAs=text
  dataUrl: string | null;       // populated when readAs=dataurl
  reading: boolean;
}

function CollateralFormDialog({
  open,
  editing,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  editing: CollateralResponse | null;
  onOpenChange: (o: boolean) => void;
  onSaved: () => void;
}) {
  const isEdit = Boolean(editing);

  // Which tab is active — only shown when adding (edit always shows URL tab)
  const [tab, setTab] = useState<DialogTab>("url");

  // ── URL tab state ─────────────────────────────────────────────────────────
  const [name, setName]               = useState("");
  const [type, setType]               = useState("case_study");
  const [url, setUrl]                 = useState("");
  const [description, setDescription] = useState("");
  const [content, setContent]         = useState("");   // brand content / snippet

  // ── Upload tab state ──────────────────────────────────────────────────────
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [saving, setSaving] = useState(false);

  // Sync fields when dialog opens or editing target changes
  function resetToEditing() {
    if (editing) {
      setName(editing.name);
      setType(editing.type);
      setUrl(editing.url ?? "");
      setDescription(editing.description ?? "");
      setContent(editing.content ?? "");
      setTab("url");
    } else {
      setName("");
      setType("case_study");
      setUrl("");
      setDescription("");
      setContent("");
      setTab("url");
    }
    setUploadedFile(null);
  }

  // Run on every open (open=true) to pre-fill editing data
  // Using a ref flag avoids the anti-pattern of useState inside useState
  const prevOpenRef = useRef(false);
  if (open && !prevOpenRef.current) {
    resetToEditing();
  }
  prevOpenRef.current = open;

  function handleOpenChange(o: boolean) {
    if (!o) resetToEditing();
    onOpenChange(o);
  }

  // ── File selection handler ─────────────────────────────────────────────────
  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Auto-fill name from filename (strip extension)
    if (!name) {
      setName(file.name.replace(/\.[^.]+$/, ""));
    }

    // Text-based types → read as text for the content field
    const isText =
      file.type === "text/plain" ||
      file.type === "text/markdown" ||
      file.type === "text/csv";

    const entry: UploadedFile = {
      file,
      readAs: isText ? "text" : "dataurl",
      content: null,
      dataUrl: null,
      reading: true,
    };
    setUploadedFile(entry);

    const reader = new FileReader();
    reader.onload = (ev) => {
      const result = ev.target?.result as string;
      setUploadedFile((prev) =>
        prev
          ? {
              ...prev,
              reading: false,
              content: isText ? result : null,
              dataUrl: isText ? null : result,
            }
          : null
      );
    };
    reader.onerror = () => {
      toast.error("Failed to read file");
      setUploadedFile(null);
    };

    if (isText) {
      reader.readAsText(file);
    } else {
      reader.readAsDataURL(file);
    }

    // Reset input so the same file can be re-selected
    e.target.value = "";
  }

  function clearFile() {
    setUploadedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // ── Save ──────────────────────────────────────────────────────────────────
  async function handleSave() {
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }

    if (tab === "upload" && !isEdit) {
      if (!uploadedFile) {
        toast.error("Select a file to upload");
        return;
      }
      if (uploadedFile.reading) {
        toast.error("File is still being read — please wait");
        return;
      }
    }

    setSaving(true);
    try {
      let payload: Record<string, unknown>;

      if (tab === "upload" && !isEdit && uploadedFile) {
        // Upload tab: submit file metadata + content/data-url
        payload = {
          name: name.trim(),
          type,
          description: description.trim() || null,
          fileName: uploadedFile.file.name,
          fileSize: uploadedFile.file.size,
          mimeType: uploadedFile.file.type || null,
          // For text files → content field; for binary → url as data URL
          content: uploadedFile.content ?? null,
          url: uploadedFile.dataUrl ?? null,
        };
      } else {
        // URL tab (or edit mode)
        payload = {
          name: name.trim(),
          type,
          url: url.trim() || null,
          content: content.trim() || null,
          description: description.trim() || null,
        };
      }

      if (isEdit && editing) {
        await http.put(`/api/v1/collaterals/${editing.id}`, payload);
        toast.success("Collateral updated");
      } else {
        await http.post("/api/v1/collaterals", payload);
        toast.success("Collateral added");
      }
      onSaved();
      onOpenChange(false);
    } catch {
      toast.error(isEdit ? "Failed to update collateral" : "Failed to add collateral");
    } finally {
      setSaving(false);
    }
  }

  const canSave =
    name.trim().length > 0 &&
    !saving &&
    (tab === "url" || isEdit || (uploadedFile !== null && !uploadedFile.reading));

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Collateral" : "Add Collateral"}</DialogTitle>
          <DialogDescription>
            Add an asset to the shared library. You can link it to any campaign afterwards.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          {/* ── Tab switcher — only visible when adding ── */}
          {!isEdit && (
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setTab("url")}
                className={`flex items-center justify-center gap-2 rounded-lg border py-2.5 text-sm font-medium transition-colors ${
                  tab === "url"
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-muted-foreground hover:bg-muted/50"
                }`}
              >
                <Globe className="h-4 w-4" />
                External URL
              </button>
              <button
                type="button"
                onClick={() => setTab("upload")}
                className={`flex items-center justify-center gap-2 rounded-lg border py-2.5 text-sm font-medium transition-colors ${
                  tab === "upload"
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-muted-foreground hover:bg-muted/50"
                }`}
              >
                <Upload className="h-4 w-4" />
                Upload File
              </button>
            </div>
          )}

          {/* ── Name + Type (always shown) ── */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="col-name">Name *</Label>
              <Input
                id="col-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Q3 ROI Case Study"
              />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Select value={type} onValueChange={setType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COLLATERAL_TYPES.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      <div className="flex items-center gap-2">
                        {t.icon}
                        <span>{t.label}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* ── Tab-specific fields ── */}
          {tab === "url" || isEdit ? (
            <>
              {/* External URL field */}
              <div className="space-y-2">
                <Label htmlFor="col-url">
                  External URL {!isEdit && <span className="text-red-500">*</span>}
                </Label>
                <Input
                  id="col-url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://..."
                />
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="col-desc">Description</Label>
                <Textarea
                  id="col-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description of what this collateral covers..."
                  rows={2}
                />
              </div>

              {/* Brand Content / Snippet */}
              <div className="space-y-2">
                <Label htmlFor="col-content">Brand Content / Snippet</Label>
                <Textarea
                  id="col-content"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Paste the actual text the AI should read — case study quotes, testimonial language, deck talking points, value-prop phrasing..."
                  rows={4}
                />
                <p className="text-xs text-muted-foreground">
                  Paste the actual text the AI should read to match your brand voice — case
                  study quotes, testimonial language, deck talking points, value-prop phrasing.
                  This is what Email Studio and Campaigns inject into email generation. Kept
                  private to your workspace.
                </p>
              </div>
            </>
          ) : (
            <>
              {/* Upload File tab */}
              {!uploadedFile ? (
                <div
                  className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border p-8 text-center cursor-pointer hover:bg-muted/30 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const file = e.dataTransfer.files?.[0];
                    if (file && fileInputRef.current) {
                      const dt = new DataTransfer();
                      dt.items.add(file);
                      fileInputRef.current.files = dt.files;
                      fileInputRef.current.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                  }}
                >
                  <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
                    <Upload className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">Click to upload or drag &amp; drop</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      PDF, Word, PowerPoint, TXT, CSV, Markdown
                    </p>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                    Browse files
                  </Button>
                </div>
              ) : (
                <div className="rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-start gap-3">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                      {uploadedFile.reading
                        ? <Loader2 className="h-5 w-5 text-primary animate-spin" />
                        : <FileText className="h-5 w-5 text-primary" />
                      }
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{uploadedFile.file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(uploadedFile.file.size)}
                        {uploadedFile.file.type && ` · ${uploadedFile.file.type}`}
                      </p>
                      {uploadedFile.reading && (
                        <p className="text-xs text-muted-foreground mt-1">Reading file…</p>
                      )}
                      {!uploadedFile.reading && (
                        <p className="text-xs text-emerald-600 mt-1">✓ Ready to upload</p>
                      )}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                      onClick={clearFile}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}

              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_MIME_TYPES}
                className="hidden"
                onChange={handleFileChange}
              />

              {/* Description for uploaded file */}
              <div className="space-y-2">
                <Label htmlFor="col-upload-desc">Description</Label>
                <Textarea
                  id="col-upload-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description of what this collateral covers..."
                  rows={2}
                />
              </div>

              <p className="text-xs text-muted-foreground">
                The file content will be extracted and stored so the AI can read it during email
                generation. The original file is not stored — only its text content and metadata.
              </p>
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!canSave}>
            {saving
              ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />{isEdit ? "Saving…" : "Adding…"}</>
              : isEdit
                ? "Save Changes"
                : "Add Collateral"
            }
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── Link to campaign dialog ─────────────────────────────────────────────── */

function LinkCampaignDialog({
  collateral,
  campaigns,
  onClose,
  onLinked,
}: {
  collateral: CollateralResponse | null;
  campaigns: CampaignItem[];
  onClose: () => void;
  onLinked: () => void;
}) {
  const [campaignId, setCampaignId] = useState("");
  const [linking, setLinking] = useState(false);

  async function handleLink() {
    if (!collateral || !campaignId) {
      toast.error("Pick a campaign to link");
      return;
    }
    setLinking(true);
    try {
      await http.post("/api/v1/collaterals/link", {
        collateralId: collateral.id,
        campaignId,
        sortOrder: 0,
      });
      toast.success("Linked to campaign");
      onLinked();
      onClose();
    } catch {
      toast.error("Failed to link collateral");
    } finally {
      setLinking(false);
    }
  }

  return (
    <Dialog open={Boolean(collateral)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Link to Campaign</DialogTitle>
          <DialogDescription>
            {collateral
              ? `Link "${truncate(collateral.name, 40)}" to a campaign so the AI uses it during email generation.`
              : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-1">
          <Label>Campaign</Label>
          <Select value={campaignId} onValueChange={setCampaignId}>
            <SelectTrigger>
              <SelectValue placeholder="Select a campaign…" />
            </SelectTrigger>
            <SelectContent className="max-h-60">
              {campaigns.length === 0 ? (
                <SelectItem value="_none" disabled>
                  No campaigns available
                </SelectItem>
              ) : (
                campaigns.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleLink} disabled={linking || !campaignId}>
            <Link2 className="h-4 w-4" />
            {linking ? "Linking…" : "Link"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── Delete dialog ───────────────────────────────────────────────────────── */

function DeleteDialog({
  collateral,
  onClose,
  onDeleted,
}: {
  collateral: CollateralResponse | null;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!collateral) return;
    setDeleting(true);
    try {
      await http.delete(`/api/v1/collaterals/${collateral.id}`);
      toast.success("Collateral deleted");
      onDeleted();
      onClose();
    } catch {
      toast.error("Failed to delete collateral");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Dialog open={Boolean(collateral)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete collateral?</DialogTitle>
          <DialogDescription>
            "{collateral?.name}" will be permanently removed from your library
            and unlinked from all campaigns.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */

export function CollateralsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [formOpen, setFormOpen] = useState(false);
  const [editingCollateral, setEditingCollateral] =
    useState<CollateralResponse | null>(null);
  const [deleteTarget, setDeleteTarget] =
    useState<CollateralResponse | null>(null);
  const [linkTarget, setLinkTarget] =
    useState<CollateralResponse | null>(null);

  /* ── Queries ── */

  const { data: collaterals = [], isLoading } = useQuery<CollateralResponse[]>({
    queryKey: ["collaterals"],
    queryFn: () => http.get<CollateralResponse[]>("/api/v1/collaterals"),
    retry: false,
  });

  const { data: campaignList = [] } = useQuery<CampaignItem[]>({
    queryKey: ["campaigns", "my"],
    queryFn: () =>
      http
        .get<{ items: CampaignItem[] }>("/api/v1/campaigns/my")
        .then((r) => r.items ?? []),
    retry: false,
  });

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["collaterals"] });
  }

  /* ── Filtering ── */

  const filtered = collaterals.filter((c) => {
    const matchSearch =
      !search ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      (c.description ?? "").toLowerCase().includes(search.toLowerCase());
    const matchType = typeFilter === "all" || c.type === typeFilter;
    return matchSearch && matchType;
  });

  /* ── Stats ── */

  const totalUploaded = collaterals.filter((c) => c.fileName).length;
  const totalExternal = collaterals.filter((c) => c.url && !c.fileName).length;

  const typeCounts = Object.fromEntries(
    COLLATERAL_TYPES.map((t) => [
      t.id,
      collaterals.filter((c) => c.type === t.id).length,
    ])
  );

  /* ── Handlers ── */

  function openAdd() {
    setEditingCollateral(null);
    setFormOpen(true);
  }

  function openEdit(c: CollateralResponse) {
    setEditingCollateral(c);
    setFormOpen(true);
  }

  /* ── Render ── */

  return (
    <div className="space-y-6">
      <PageHeader
        title="Collaterals"
        description="Your brand's proof library. Add case studies, decks, testimonials, and one-pagers — then link them to campaigns. The AI reads these to keep every email's tone, language, and proof points on-brand."
        actions={
          <Button size="sm" onClick={openAdd}>
            <Plus className="h-4 w-4" /> Add Collateral
          </Button>
        }
      />

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-4">
          <p className="text-2xl font-bold">{collaterals.length}</p>
          <p className="text-xs text-muted-foreground mt-0.5">Total Collaterals</p>
        </Card>
        <Card className="p-4">
          <p className="text-2xl font-bold">{totalUploaded}</p>
          <p className="text-xs text-muted-foreground mt-0.5">Uploaded Files</p>
        </Card>
        <Card className="p-4">
          <p className="text-2xl font-bold">{totalExternal}</p>
          <p className="text-xs text-muted-foreground mt-0.5">External URLs</p>
        </Card>
        <Card className="p-4">
          <p className="text-2xl font-bold">{campaignList.length}</p>
          <p className="text-xs text-muted-foreground mt-0.5">Campaigns</p>
        </Card>
      </div>

      {/* How it works banner */}
      <div className="flex items-start gap-2 text-xs text-muted-foreground p-3 rounded-lg bg-muted/40 border">
        <span className="font-medium text-foreground">How it works:</span>
        Add collateral here → Link it to a campaign on the Campaigns page → The AI automatically
        uses it for context when generating emails and sequences.
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search collaterals by name, description, URL..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {COLLATERAL_TYPES.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                <div className="flex items-center gap-2">
                  {t.icon}
                  {t.label} ({typeCounts[t.id] ?? 0})
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm">
          Export CSV
        </Button>
        <span className="text-xs text-muted-foreground">
          Showing {filtered.length} of {collaterals.length}
        </span>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={<Paperclip className="h-10 w-10" />}
              title={
                collaterals.length > 0
                  ? "No collaterals match your filters"
                  : "No collaterals yet"
              }
              description={
                collaterals.length > 0
                  ? "Try adjusting the search or type filter."
                  : 'Click "Add Collateral" to create your first one.'
              }
              action={
                collaterals.length === 0 ? (
                  <Button size="sm" onClick={openAdd}>
                    <Plus className="h-4 w-4" /> Add Collateral
                  </Button>
                ) : undefined
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((c) => {
            const meta = getTypeMeta(c.type);
            const isUploaded = Boolean(c.fileName);
            return (
              <Card
                key={c.id}
                className="hover:shadow-md transition-shadow flex flex-col"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-primary shrink-0">{meta.icon}</span>
                      <CardTitle className="text-base truncate">{c.name}</CardTitle>
                    </div>
                    <Badge
                      variant="outline"
                      className={`text-xs shrink-0 border ${meta.badgeColor}`}
                    >
                      {meta.label}
                    </Badge>
                  </div>
                  {c.description && (
                    <CardDescription className="text-xs line-clamp-2">
                      {c.description}
                    </CardDescription>
                  )}
                </CardHeader>

                <CardContent className="flex-1 flex flex-col justify-between space-y-3">
                  {/* Source indicator */}
                  <div className="text-xs text-muted-foreground">
                    {isUploaded ? (
                      <span className="flex items-center gap-1">
                        <Upload className="h-3 w-3" />
                        {c.fileName}
                        {c.fileSize && ` · ${formatFileSize(c.fileSize)}`}
                      </span>
                    ) : c.url ? (
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="h-3 w-3" />
                        {truncate(c.url, 44)}
                      </a>
                    ) : c.content ? (
                      <p className="italic line-clamp-2">{truncate(c.content, 90)}</p>
                    ) : (
                      <span className="flex items-center gap-1 text-amber-600">
                        <Paperclip className="h-3 w-3" />
                        No URL or content
                      </span>
                    )}
                  </div>

                  {/* Brand content indicator */}
                  {c.content && !isUploaded && (
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">
                      Brand Content
                    </div>
                  )}

                  {/* Footer meta */}
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>{isUploaded ? "Uploaded File" : "External URL"} · Used in 0 campaigns</span>
                    <span>{formatDate(c.updatedAt)}</span>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-1 border-t">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs gap-1"
                      onClick={() => setLinkTarget(c)}
                    >
                      <Link2 className="h-3 w-3" /> Link
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 text-xs gap-1"
                      onClick={() => openEdit(c)}
                    >
                      <Edit3 className="h-3 w-3" /> Edit
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-destructive ml-auto"
                      onClick={() => setDeleteTarget(c)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Add / Edit dialog */}
      <CollateralFormDialog
        open={formOpen}
        editing={editingCollateral}
        onOpenChange={(o) => {
          setFormOpen(o);
          if (!o) setEditingCollateral(null);
        }}
        onSaved={invalidate}
      />

      {/* Link to campaign dialog */}
      <LinkCampaignDialog
        collateral={linkTarget}
        campaigns={campaignList}
        onClose={() => setLinkTarget(null)}
        onLinked={invalidate}
      />

      {/* Delete dialog */}
      <DeleteDialog
        collateral={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={invalidate}
      />
    </div>
  );
}