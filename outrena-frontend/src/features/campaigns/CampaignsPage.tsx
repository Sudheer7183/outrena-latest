

// import { useEffect, useMemo, useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   AlertCircle,
//   ArrowLeft,
//   Briefcase,
//   CalendarClock,
//   Check,
//   CheckCircle2,
//   Copy,
//   Edit3,
//   FileDown,
//   Layers,
//   Link2,
//   Loader2,
//   Mail,
//   MessageCircleReply,
//   Paperclip,
//   Plus,
//   Send,
//   ShieldCheck,
//   Trash2,
//   Users,
//   Wand2,
//   Webhook,
// } from "lucide-react";
// import { toast } from "sonner";

// import { http } from "@/services/apiClient";
// import { cn } from "@/lib/utils";
// import { Button } from "@/components/ui/button";
// import {
//   Card,
//   CardContent,
//   CardDescription,
//   CardHeader,
//   CardTitle,
// } from "@/components/ui/card";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { Textarea } from "@/components/ui/textarea";
// import { Badge } from "@/components/ui/badge";
// import { Switch } from "@/components/ui/switch";
// import { Separator } from "@/components/ui/separator";
// import { ScrollArea } from "@/components/ui/scroll-area";
// import { Skeleton } from "@/components/ui/skeleton";
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from "@/components/ui/select";
// import {
//   Dialog,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
// } from "@/components/ui/dialog";
// import {
//   AlertDialog,
//   AlertDialogAction,
//   AlertDialogCancel,
//   AlertDialogContent,
//   AlertDialogDescription,
//   AlertDialogFooter,
//   AlertDialogHeader,
//   AlertDialogTitle,
// } from "@/components/ui/alert-dialog";
// import { PageHeader } from "@/components/ui/page-header";
// import { EmptyState } from "@/components/ui/empty-state";

// /* ── Types ─────────────────────────────────────────────────────────── */

// interface IcpProfile { id: string; name: string; senderRole?: string | null; senderCompany?: string | null; senderOffer?: string | null; proofMetric?: string | null; }
// interface Domain { id: string; domainName: string; }
// interface Prospect { id: string; firstName: string; lastName: string; email: string | null; title: string | null; company: string | null; seniority: string; }
// interface Collateral { id: string; name: string; type: string; url: string | null; content: string | null; description: string | null; }
// interface MailBridgeConfig { id: string; name: string; baseUrl: string; provider: string; fromEmail: string; fromName: string | null; isActive: boolean; }

// interface CampaignProspectRow {
//   id: string;
//   prospectId: string;
//   campaignId: string;
//   status: string;
//   prospect?: Prospect;
// }

// interface Campaign {
//   id: string;
//   name: string;
//   description: string | null;
//   status: string;
//   framework: string | null;
//   senderRole: string | null;
//   senderCompany: string | null;
//   senderOffer: string | null;
//   proofMetric: string | null;
//   senderProduct: string | null;
//   targetAudience: string | null;
//   icpProfileId: string | null;
//   llmConfigId: string | null;
//   domainId: string | null;
//   complianceFooter: boolean;
//   unsubscribeUrl: string | null;
//   physicalAddress: string | null;
//   webhookUrl: string | null;
//   icpProfile?: IcpProfile | null;
//   prospects?: CampaignProspectRow[];
//   _count?: { prospects: number; sequences: number; collaterals: number };
//   createdAt: string;
//   updatedAt: string;
// }

// interface Sequence {
//   id: string;
//   campaignId: string;
//   prospectId: string;
//   touchNumber: number;
//   sendDay: number;
//   angle: string;
//   framework: string | null;
//   subjectLine: string | null;
//   bodyCopy: string | null;
//   status: string;
//   sentAt: string | null;
//   openedAt: string | null;
//   repliedAt: string | null;
// }

// interface PreflightCheck { name: string; status: "pass" | "fail" | "warn"; detail: string; }
// interface PreflightResult { passed: boolean; checks: PreflightCheck[]; warnings?: string[]; allPassed?: boolean; }

// /* ── Constants ──────────────────────────────────────────────────────── */

// /** Human-readable label and colour for every campaign status. */
// const CAMPAIGN_STATUS_META: Record<string, { label: string; cls: string }> = {
//   draft:     { label: "Draft",     cls: "bg-gray-100 text-gray-700" },
//   active:    { label: "Active",    cls: "bg-emerald-100 text-emerald-700" },
//   paused:    { label: "Paused",    cls: "bg-amber-100 text-amber-700" },
//   completed: { label: "Completed", cls: "bg-blue-100 text-blue-700" },
//   archived:  { label: "Archived",  cls: "bg-slate-100 text-slate-500" },
//   sending:   { label: "Sending",   cls: "bg-violet-100 text-violet-700" },
//   failed:    { label: "Failed",    cls: "bg-red-100 text-red-700" },
// };



// const FRAMEWORK_NAMES: Record<string, string> = {
//   trigger: "Trigger-Based",
//   problem: "Problem-First",
//   mutual: "Mutual Connection",
//   value: "Value-First",
//   direct: "Direct Ask",
//   challenger: "Challenger",
//   meddpicc: "MEDDPICC",
//   spiced: "SPICED",
//   story: "Story-Led",
// };



// const SEQ_STATUS_COLORS: Record<string, string> = {
//   Draft: "bg-gray-100 text-gray-600",
//   QaPassed: "bg-emerald-100 text-emerald-700",
//   Sent: "bg-blue-100 text-blue-700",
//   Scheduled: "bg-violet-100 text-violet-700",
//   Replied: "bg-teal-100 text-teal-700",
//   Bounced: "bg-red-100 text-red-700",
// };

// function exportToCsv(rows: Record<string, unknown>[], filename: string) {
//   if (rows.length === 0) return;
//   const keys = Object.keys(rows[0]);
//   const lines = [keys.join(","), ...rows.map((r) => keys.map((k) => JSON.stringify(r[k] ?? "")).join(","))];
//   const blob = new Blob([lines.join("\n")], { type: "text/csv" });
//   const a = document.createElement("a");
//   a.href = URL.createObjectURL(blob);
//   a.download = `${filename}.csv`;
//   a.click();
// }

// /* ── Page ──────────────────────────────────────────────────────────── */

// export function CampaignsPage() {
//   const qc = useQueryClient();

//   /* ── Data queries ── */
//   const campaignsQ = useQuery<{ items: Campaign[]; total: number }>({
//     queryKey: ["campaigns"],
//     queryFn: () => http.get<any>("/api/v1/campaigns").then((r) =>
//       Array.isArray(r) ? { items: r, total: r.length } : { items: r?.items ?? [], total: r?.total ?? 0 }
//     ),
//   });
//   const icpQ = useQuery<IcpProfile[]>({ queryKey: ["icp-profiles"], queryFn: () => http.get<any>("/api/v1/icp-profiles").then((r) => Array.isArray(r) ? r : r?.items ?? []) });
//   // LLM configs use tenant default — /api/v1/llm-configs requires SUPER_ADMIN
//   // Campaign.llmConfigId is optional; null means "use tenant default LLM"
//   const domainsQ = useQuery<Domain[]>({ queryKey: ["domains"], queryFn: () => http.get<any>("/api/v1/domains").then((r) => Array.isArray(r) ? r : r?.items ?? []) });
//   const prospectsQ = useQuery<Prospect[]>({ queryKey: ["prospects-lite"], queryFn: () => http.get<any>("/api/v1/prospects").then((r) => Array.isArray(r) ? r : r?.items ?? []) });

//   const campaigns = campaignsQ.data?.items ?? [];
//   const icps = icpQ.data ?? [];
//   // const llmConfigs: { id: string; name: string; provider: string }[] = []; // campaigns use tenant default LLM
//   const domains = domainsQ.data ?? [];
//   const allProspects = prospectsQ.data ?? [];

//   /* ── View state ── */
//   const [view, setView] = useState<"list" | "detail">("list");
//   const [selectedId, setSelectedId] = useState("");
//   const [detailTab, setDetailTab] = useState("prospects");

//   const selectedCampaign = campaigns.find((c) => c.id === selectedId);

//   /* ── Detail: lazy-loaded data ── */
//   const campaignProspectsQ = useQuery<CampaignProspectRow[]>({
//     queryKey: ["campaign-prospects", selectedId],
//     queryFn: () =>
//       http.get<any>(`/api/v1/campaigns/campaign-prospects?campaign_id=${selectedId}`)
//         .then((r) => Array.isArray(r) ? r : r?.items ?? []),
//     enabled: view === "detail" && !!selectedId,
//   });

//   const sequencesQ = useQuery<Sequence[]>({
//     queryKey: ["sequences", selectedId],
//     queryFn: () => http.get<any>(`/api/v1/sequences?campaign_id=${selectedId}`).then((r) => Array.isArray(r) ? r : r?.items ?? []),
//     enabled: view === "detail" && !!selectedId,
//   });
//   const collateralsQ = useQuery<Collateral[]>({
//     queryKey: ["collaterals"],
//     queryFn: () => http.get<any>("/api/v1/collaterals").then((r) => Array.isArray(r) ? r : r?.items ?? []),
//     enabled: view === "detail" && !!selectedId,
//   });

//   // Fetch existing collateral links for this campaign so previously linked
//   // collaterals are visible when the detail view is opened.
//   // Endpoint: GET /api/v1/collaterals/links?campaign_id=X
//   const collateralLinksQ = useQuery<{ id: string; collateralId: string; campaignId: string }[]>({
//     queryKey: ["collateral-links", selectedId],
//     queryFn: () =>
//       http.get<any>(`/api/v1/collaterals/links?campaign_id=${selectedId}`)
//         .then((r) => Array.isArray(r) ? r : r?.items ?? []),
//     enabled: view === "detail" && !!selectedId,
//     staleTime: 0,
//   });
//   const mailbridgeQ = useQuery<MailBridgeConfig[]>({
//     queryKey: ["mailbridge-configs"],
//     queryFn: () => http.get<any>("/api/v1/mailbridge/config").then((r) => Array.isArray(r) ? r : r?.items ?? []),
//     enabled: view === "detail" && !!selectedId,
//   });

//   const sequences = sequencesQ.data ?? [];
//   const collateralLibrary = collateralsQ.data ?? [];
//   const mbConfigs = mailbridgeQ.data ?? [];

//   // Campaign prospects fetched directly from the API (not embedded in the campaign list response).
//   // Enrich each row with the full prospect object looked up from the allProspects list.
//   const campaignProspects: CampaignProspectRow[] = useMemo(
//     () =>
//       (campaignProspectsQ.data ?? []).map((cp) => ({
//         ...cp,
//         prospect: cp.prospect ?? allProspects.find((p) => p.id === cp.prospectId),
//       })),
//     [campaignProspectsQ.data, allProspects]
//   );

//   // Collaterals linked to this campaign (filter library by campaignId in links)
//   // The backend returns campaign with collateral links embedded or we filter collateralLibrary
//   // Since the API doesn't have a campaign-specific collaterals endpoint, we use the full library
//   // and track linked ones via the campaign's _count.collaterals or from a separate state.
//   const [linkedCollateralIds, setLinkedCollateralIds] = useState<Set<string>>(new Set());

//   /* ── Sequence local edits ── */
//   const [seqDrafts, setSeqDrafts] = useState<Record<string, { subjectLine: string; bodyCopy: string }>>({});

//   /* ── Create/Edit form ── */
//   const EMPTY_FORM = { name: "", description: "", status: "draft", framework: "trigger", targetAudience: "", senderRole: "", senderCompany: "", senderOffer: "", proofMetric: "", senderProduct: "", icpProfileId: "", llmConfigId: "", domainId: "" };
//   const [dialogOpen, setDialogOpen] = useState(false);
//   const [editingId, setEditingId] = useState<string | null>(null);
//   const [form, setForm] = useState({ ...EMPTY_FORM });
//   const [formTab, setFormTab] = useState("basics");

//   const resetForm = () => { setForm({ ...EMPTY_FORM }); setFormTab("basics"); setEditingId(null); };
//   const openCreate = () => { resetForm(); setDialogOpen(true); };
//   const openEdit = (c: Campaign) => {
//     setEditingId(c.id);
//     setForm({ name: c.name, description: c.description ?? "", status: c.status, framework: c.framework ?? "trigger", targetAudience: c.targetAudience ?? "", senderRole: c.senderRole ?? "", senderCompany: c.senderCompany ?? "", senderOffer: c.senderOffer ?? "", proofMetric: c.proofMetric ?? "", senderProduct: c.senderProduct ?? "", icpProfileId: c.icpProfileId ?? "", llmConfigId: c.llmConfigId ?? "", domainId: c.domainId ?? "" });
//     setFormTab("basics");
//     setDialogOpen(true);
//   };

//   /* ── Campaign CRUD mutations ── */
//   const saveMut = useMutation({
//     mutationFn: (body: Record<string, unknown>) =>
//       editingId
//         ? http.put(`/api/v1/campaigns/${editingId}`, body)
//         : http.post("/api/v1/campaigns", body),
//     onSuccess: () => {
//       toast.success(editingId ? "Campaign updated" : "Campaign created");
//       qc.invalidateQueries({ queryKey: ["campaigns"] });
//       setDialogOpen(false); resetForm();
//     },
//     onError: () => toast.error("Failed to save campaign"),
//   });

//   const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null);
//   const deleteMut = useMutation({
//     mutationFn: (id: string) => http.delete(`/api/v1/campaigns/${id}`),
//     onSuccess: () => {
//       toast.success("Campaign deleted");
//       qc.invalidateQueries({ queryKey: ["campaigns"] });
//       if (selectedId === deleteTarget?.id) { setView("list"); setSelectedId(""); }
//       setDeleteTarget(null);
//     },
//     onError: () => toast.error("Delete failed"),
//   });

//   const handleSave = () => {
//     if (!form.name.trim()) { toast.error("Campaign name is required"); return; }
//     saveMut.mutate({ ...form, icpProfileId: form.icpProfileId || null, llmConfigId: form.llmConfigId || null, domainId: form.domainId || null });
//   };

//   /* ── Status change ── */
//   const handleStatusChange = async (id: string, newStatus: string) => {
//     if (newStatus === "active") {
//       setPendingActivateId(id);
//       setPreflightOpen(true);
//       setPreflightLoading(true);
//       setPreflightResult(null);
//       try {
//         const data = await http.post<any>("/api/v1/campaigns/preflight", { campaignId: id });
//         setPreflightResult(data);
//       } catch { toast.error("Pre-flight check failed"); setPreflightOpen(false); }
//       setPreflightLoading(false);
//       return;
//     }
//     try {
//       await http.put(`/api/v1/campaigns/${id}`, { status: newStatus });
//       toast.success(`Campaign ${newStatus}`);
//       qc.invalidateQueries({ queryKey: ["campaigns"] });
//     } catch { toast.error("Status change failed"); }
//   };

//   /* ── Clone ── */
//   const cloneMut = useMutation({
//     mutationFn: (id: string) => http.post<any>("/api/v1/campaigns/clone", { campaignId: id }),
//     onSuccess: (data) => {
//       toast.success(`Cloned as "${data.name}"`);
//       qc.invalidateQueries({ queryKey: ["campaigns"] });
//     },
//     onError: () => toast.error("Clone failed"),
//   });

//   /* ── Pre-flight ── */
//   const [preflightOpen, setPreflightOpen] = useState(false);
//   const [preflightLoading, setPreflightLoading] = useState(false);
//   const [preflightResult, setPreflightResult] = useState<PreflightResult | null>(null);
//   const [pendingActivateId, setPendingActivateId] = useState("");

//   const confirmActivate = async () => {
//     try {
//       await http.put(`/api/v1/campaigns/${pendingActivateId}`, { status: "active" });
//       toast.success("Campaign activated");
//       qc.invalidateQueries({ queryKey: ["campaigns"] });
//     } catch { toast.error("Activation failed"); }
//     setPreflightOpen(false); setPreflightResult(null); setPendingActivateId("");
//   };

//   /* ── Add Prospects dialog ── */
//   const [addProspectOpen, setAddProspectOpen] = useState(false);
//   const [prospectSearch, setProspectSearch] = useState("");
//   const [addProspectIds, setAddProspectIds] = useState<Set<string>>(new Set());

//   const existingProspectIds = new Set(campaignProspects.map((cp) => cp.prospectId));
//   const availableProspects = allProspects.filter((p) =>
//     !existingProspectIds.has(p.id) &&
//     (prospectSearch === "" || `${p.firstName} ${p.lastName} ${p.company ?? ""} ${p.title ?? ""}`.toLowerCase().includes(prospectSearch.toLowerCase()))
//   );

//   const linkProspectMut = useMutation({
//     mutationFn: (prospectId: string) =>
//       http.post("/api/v1/campaigns/campaign-prospects", { campaignId: selectedId, prospectId }),
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["campaigns"] });
//       qc.invalidateQueries({ queryKey: ["campaign-prospects", selectedId] });
//     },
//   });

//   const handleAddProspects = async () => {
//     if (addProspectIds.size === 0) { toast.error("Select at least one prospect"); return; }
//     for (const pid of addProspectIds) {
//       await linkProspectMut.mutateAsync(pid).catch(() => {});
//     }
//     toast.success(`${addProspectIds.size} prospect(s) added`);
//     setAddProspectOpen(false); setAddProspectIds(new Set()); setProspectSearch("");
//   };

//   const handleRemoveProspect = async (prospectId: string) => {
//     try {
//       await fetch("/api/v1/campaigns/campaign-prospects", {
//         method: "DELETE",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ campaignId: selectedId, prospectId }),
//       });
//       toast.success("Prospect removed");
//       qc.invalidateQueries({ queryKey: ["campaigns"] });
//       qc.invalidateQueries({ queryKey: ["campaign-prospects", selectedId] });
//     } catch { toast.error("Remove failed"); }
//   };

//   /* ── Sequences ── */
//   const [seqFramework, setSeqFramework] = useState("trigger");
//   const [generating, setGenerating] = useState(false);
//   const [sendingId, setSendingId] = useState<string | null>(null);

//   const handleGenerateSequences = async () => {
//     setGenerating(true);
//     try {
//       const data = await http.post<any>(`/api/v1/campaigns/${selectedId}/generate-sequences`, {});
//       toast.success(data.message ?? `Generated ${data.created} sequences`);
//       qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
//     } catch { toast.error("Sequence generation failed"); }
//     setGenerating(false);
//   };

//   const handleSendEmail = async (seqId: string) => {
//     setSendingId(seqId);
//     try {
//       const data = await http.post<any>(`/api/v1/sequences/${seqId}/send-email`, {});
//       if (data.accepted || data.messageId) toast.success("Email sent");
//       else toast.error(data.error ?? "Send failed");
//       qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
//     } catch { toast.error("Send failed"); }
//     setSendingId(null);
//   };

//   const handleSendAllApproved = async () => {
//     const approved = sequences.filter((s) => s.status === "QaPassed");
//     if (approved.length === 0) { toast.error("No approved sequences to send"); return; }
//     setSendingId("bulk");
//     let sent = 0;
//     for (const seq of approved) {
//       try {
//         await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
//         sent++;
//       } catch { /* skip */ }
//     }
//     toast.success(`${sent}/${approved.length} emails sent`);
//     qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
//     setSendingId(null);
//   };

//   const handleScheduleCampaign = async () => {
//     const approved = sequences.filter((s) => s.status === "QaPassed");
//     if (approved.length === 0) { toast.error("No approved sequences to schedule"); return; }
//     let scheduled = 0;
//     for (const seq of approved) {
//       try {
//         const sendAt = new Date(Date.now() + seq.sendDay * 86400000).toISOString();
//         await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, { sendAt });
//         scheduled++;
//       } catch { /* skip */ }
//     }
//     toast.success(`${scheduled} sequences scheduled`);
//     qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
//   };

//   const handleApproveSequence = async (seq: Sequence, _idx: number) => {
//     const draft = seqDrafts[seq.id];
//     try {
//       await http.put(`/api/v1/sequences/${seq.id}`, {
//         subjectLine: draft?.subjectLine ?? seq.subjectLine,
//         bodyCopy: draft?.bodyCopy ?? seq.bodyCopy,
//         status: "QaPassed",
//       });
//       toast.success("Sequence approved");
//       qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
//     } catch { toast.error("Approve failed"); }
//   };

//   /* ── Collaterals ── */
//   const [collateralDialog, setCollateralDialog] = useState(false);
//   const [collForm, setCollForm] = useState({ name: "", type: "case_study", url: "", content: "", description: "" });
//   const [linkCollateralOpen, setLinkCollateralOpen] = useState(false);
//   const [linkCollateralId, setLinkCollateralId] = useState("");
//   const [campaignCollateralLinks, setCampaignCollateralLinks] = useState<{ linkId: string; collateralId: string; }[]>([]);

//   // Seed collateral link state from the API whenever the campaign detail opens
//   // or the collateral-links query result changes (e.g. after a link/unlink).
//   useEffect(() => {
//     const links = collateralLinksQ.data ?? [];
//     if (links.length > 0) {
//       setCampaignCollateralLinks(links.map((l) => ({ linkId: l.id, collateralId: l.collateralId })));
//       setLinkedCollateralIds(new Set(links.map((l) => l.collateralId)));
//     } else if (!collateralLinksQ.isFetching) {
//       // Only reset to empty if we've confirmed there are no links (not still loading)
//       setCampaignCollateralLinks([]);
//       setLinkedCollateralIds(new Set());
//     }
//   }, [collateralLinksQ.data, collateralLinksQ.isFetching]);

//   const createCollateralMut = useMutation({
//     mutationFn: (body: Record<string, unknown>) => http.post<any>("/api/v1/collaterals", body),
//     onSuccess: async (data) => {
//       // Link the new collateral to this campaign
//       try {
//         const link = await http.post<any>("/api/v1/collaterals/link", { collateralId: data.id, campaignId: selectedId });
//         setCampaignCollateralLinks((prev) => [...prev, { linkId: link.id ?? link.linkId, collateralId: data.id }]);
//         setLinkedCollateralIds((prev) => new Set([...prev, data.id]));
//       } catch { /* link failed but collateral created */ }
//       toast.success("Collateral added and linked");
//       qc.invalidateQueries({ queryKey: ["collaterals"] });
//       qc.invalidateQueries({ queryKey: ["collateral-links", selectedId] });
//       setCollateralDialog(false);
//       setCollForm({ name: "", type: "case_study", url: "", content: "", description: "" });
//     },
//     onError: () => toast.error("Failed to add collateral"),
//   });

//   const handleLinkCollateral = async () => {
//     if (!linkCollateralId) { toast.error("Select a collateral to link"); return; }
//     try {
//       const link = await http.post<any>("/api/v1/collaterals/link", { collateralId: linkCollateralId, campaignId: selectedId });
//       setCampaignCollateralLinks((prev) => [...prev, { linkId: link.id ?? link.linkId, collateralId: linkCollateralId }]);
//       setLinkedCollateralIds((prev) => new Set([...prev, linkCollateralId]));
//       toast.success("Collateral linked");
//       qc.invalidateQueries({ queryKey: ["collateral-links", selectedId] });
//       setLinkCollateralOpen(false); setLinkCollateralId("");
//     } catch { toast.error("Link failed"); }
//   };

//   const handleUnlinkCollateral = async (collateralId: string) => {
//     const link = campaignCollateralLinks.find((l) => l.collateralId === collateralId);
//     if (!link) { toast.error("Link not found"); return; }
//     try {
//       await http.delete(`/api/v1/collaterals/link/${link.linkId}`);
//       setCampaignCollateralLinks((prev) => prev.filter((l) => l.linkId !== link.linkId));
//       setLinkedCollateralIds((prev) => { const s = new Set(prev); s.delete(collateralId); return s; });
//       toast.success("Collateral unlinked");
//       qc.invalidateQueries({ queryKey: ["collateral-links", selectedId] });
//     } catch { toast.error("Unlink failed"); }
//   };

//   const linkedCollaterals = collateralLibrary.filter((c) => linkedCollateralIds.has(c.id));

//   /* ── MailBridge ── */
//   const [mbDialog, setMbDialog] = useState(false);
//   const [mbForm, setMbForm] = useState({ name: "", baseUrl: "", provider: "gmail", fromEmail: "", fromName: "" });

//   const createMbMut = useMutation({
//     mutationFn: (body: Record<string, unknown>) => http.post("/api/v1/mailbridge/config", body),
//     onSuccess: () => {
//       toast.success("MailBridge connection saved");
//       qc.invalidateQueries({ queryKey: ["mailbridge-configs"] });
//       setMbDialog(false);
//       setMbForm({ name: "", baseUrl: "", provider: "gmail", fromEmail: "", fromName: "" });
//     },
//     onError: () => toast.error("Failed to save MailBridge connection"),
//   });

//   const deleteMbMut = useMutation({
//     mutationFn: (id: string) => http.delete(`/api/v1/mailbridge/config/${id}`),
//     onSuccess: () => {
//       toast.success("Connection removed");
//       qc.invalidateQueries({ queryKey: ["mailbridge-configs"] });
//     },
//     onError: () => toast.error("Delete failed"),
//   });

//   const handleTestMb = async (cfg: MailBridgeConfig) => {
//     try {
//       const res = await fetch(`${cfg.baseUrl}/docs`);
//       if (res.ok) toast.success(`Connected to MailBridge at ${cfg.baseUrl}`);
//       else toast.error(`MailBridge returned status ${res.status}`);
//     } catch { toast.error(`Cannot reach MailBridge at ${cfg.baseUrl}`); }
//   };

//   /* ── Compliance inline save ── */
//   const handleComplianceUpdate = async (patch: Record<string, unknown>) => {
//     try {
//       await http.put(`/api/v1/campaigns/${selectedId}`, patch);
//       toast.success("Saved");
//       qc.invalidateQueries({ queryKey: ["campaigns"] });
//     } catch { toast.error("Save failed"); }
//   };

//   /* ── Reply categorization ── */
//   const [replyText, setReplyText] = useState("");
//   const [replyCategorizing, setReplyCategorizing] = useState(false);
//   const [replyResult, setReplyResult] = useState<any>(null);

//   const handleCategorizeReply = async () => {
//     if (!replyText.trim()) return;
//     setReplyCategorizing(true); setReplyResult(null);
//     try {
//       // Step 1: find a sequence+prospect pair to attach the draft to.
//       // Prefer a Replied sequence; fall back to any sequence with a known prospect.
//       const repliedSeq = sequences.find((s) => s.status === "Replied");
//       const anySeq = repliedSeq ?? sequences[0];
//       const prospectId = anySeq?.prospectId ?? campaignProspects[0]?.prospectId ?? null;

//       if (!anySeq || !prospectId) {
//         toast.error("Add prospects and generate sequences first, then paste a reply to categorize.");
//         setReplyCategorizing(false);
//         return;
//       }

//       // Step 2: create a ReplyDraft row with the required fields.
//       // ReplyDraftCreate requires: sequenceId, prospectId, originalReply.
//       const draft = await http.post<any>("/api/v1/reply-drafts", {
//         sequenceId: anySeq.id,
//         prospectId,
//         originalReply: replyText,  // correct field name (not replyText)
//         category: "other",         // will be overwritten by categorize call below
//       });

//       // Step 3: call the LLM categorize endpoint on the new draft.
//       const result = await http.post<any>(`/api/v1/reply-drafts/${draft.id}/reply-categorize`, {
//         originalReply: replyText,
//       });

//       setReplyResult(result);
//       toast.success(`Categorized as: ${result.category ?? "unknown"}`);
//     } catch (err: any) {
//       const msg = err?.response?.data?.message ?? err?.message ?? "Categorization failed";
//       toast.error(msg);
//     }
//     setReplyCategorizing(false);
//   };

//   /* ── Navigate to detail ── */
//   const openDetail = (id: string) => {
//     setSelectedId(id);
//     setView("detail");
//     setDetailTab("prospects");
//     setSeqDrafts({});
//   };

//   const goBack = () => { setView("list"); setSelectedId(""); setSequences([]); };

//   // local sequences state for inline editing (separate from queryCache)
//   const [localSeqs, setLocalSeqs] = useState<Sequence[]>([]);
//   useEffect(() => { setLocalSeqs(sequences); }, [sequences]);

//   const setSequences = (s: Sequence[]) => setLocalSeqs(s);
//   const displaySeqs = localSeqs.length > 0 ? localSeqs : sequences;

//   if (campaignsQ.isLoading) {
//     return (
//       <div className="space-y-4">
//         <PageHeader title="Campaigns" description="" />
//         {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 w-full" />)}
//       </div>
//     );
//   }

//   /* ═══════════════════════════════════════════════════════ RENDER ══════════ */
//   return (
//     <div className="space-y-5">
//       {view === "list" ? (
//         <>
//           {/* ── List header ── */}
//           <div className="flex items-center justify-between">
//             <div>
//               <h3 className="text-lg font-semibold">Campaigns</h3>
//               <p className="text-sm text-muted-foreground">Define your outreach, manage prospects, and send AI-generated sequences</p>
//             </div>
//             <div className="flex gap-2">
//               {/* C-11: Export CSV */}
//               <Button variant="outline" size="sm" onClick={() => exportToCsv(campaigns.map((c) => ({ name: c.name, description: c.description ?? "", status: c.status, framework: c.framework ?? "", senderRole: c.senderRole ?? "", senderCompany: c.senderCompany ?? "", createdAt: c.createdAt })), `campaigns-${new Date().toISOString().split("T")[0]}`)}>
//                 <FileDown className="h-4 w-4 mr-2" /> Export CSV
//               </Button>
//               <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4 mr-2" /> New Campaign</Button>
//             </div>
//           </div>

//           {/* ── Campaign card grid ── */}
//           {campaigns.length === 0 ? (
//             <EmptyState title="No Campaigns Yet" description="Create a campaign to define your sender identity, link prospects, and send AI-generated email sequences." />
//           ) : (
//             <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
//               {campaigns.map((c) => (
//                 <Card
//                   key={c.id}
//                   className="cursor-pointer hover:border-primary/50 transition-colors"
//                   onClick={() => openDetail(c.id)}
//                 >
//                   <CardHeader className="pb-3">
//                     <div className="flex items-center justify-between">
//                       <CardTitle className="text-sm line-clamp-1">{c.name}</CardTitle>
//                       {/* C-12: Status badge with colour */}
//                       <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", (CAMPAIGN_STATUS_META[c.status] ?? CAMPAIGN_STATUS_META.draft).cls)}>
//                         {(CAMPAIGN_STATUS_META[c.status] ?? { label: c.status }).label}
//                       </span>
//                     </div>
//                     {c.description && <CardDescription className="text-xs line-clamp-2">{c.description}</CardDescription>}
//                   </CardHeader>
//                   <CardContent>
//                     <div className="space-y-2 text-xs text-muted-foreground">
//                       <div className="flex items-center justify-between">
//                         <span>Framework</span>
//                         <span className="font-medium text-foreground">{FRAMEWORK_NAMES[c.framework ?? ""] ?? c.framework ?? "Not set"}</span>
//                       </div>
//                       {c.icpProfile && (
//                         <div className="flex items-center justify-between">
//                           <span>ICP</span>
//                           <span className="font-medium text-foreground">{c.icpProfile.name}</span>
//                         </div>
//                       )}
//                       {c.senderOffer && (
//                         <div className="flex items-center justify-between">
//                           <span>Offer</span>
//                           <span className="font-medium text-foreground truncate max-w-[150px]">{c.senderOffer}</span>
//                         </div>
//                       )}
//                       {/* C-13: _count badges */}
//                       {c._count && (
//                         <div className="flex items-center gap-4 pt-2 border-t border-border">
//                           <span><Users className="h-3 w-3 inline mr-1" />{c._count.prospects}</span>
//                           <span><Mail className="h-3 w-3 inline mr-1" />{c._count.sequences}</span>
//                           <span><Paperclip className="h-3 w-3 inline mr-1" />{c._count.collaterals}</span>
//                         </div>
//                       )}
//                     </div>
//                   </CardContent>
//                 </Card>
//               ))}
//             </div>
//           )}
//         </>
//       ) : (
//         <>
//           {/* ══════════════════════ DETAIL VIEW ══════════════════════ */}
//           {/* Back + header row */}
//           <div className="flex items-center gap-3 flex-wrap">
//             <Button variant="ghost" size="sm" onClick={() => { goBack(); }}>
//               <ArrowLeft className="h-4 w-4 mr-1" /> Back
//             </Button>
//             <div className="flex-1 min-w-0">
//               <h3 className="text-lg font-semibold truncate">{selectedCampaign?.name}</h3>
//               <p className="text-sm text-muted-foreground truncate">{selectedCampaign?.description ?? "No description"}</p>
//             </div>
//             <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", (CAMPAIGN_STATUS_META[selectedCampaign?.status ?? "draft"] ?? CAMPAIGN_STATUS_META.draft).cls)}>
//               {(CAMPAIGN_STATUS_META[selectedCampaign?.status ?? "draft"] ?? { label: selectedCampaign?.status }).label}
//             </span>
//             <Select value={selectedCampaign?.status ?? "draft"} onValueChange={(v) => handleStatusChange(selectedId, v)}>
//               <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
//               <SelectContent>
//                 <SelectItem value="draft">Draft</SelectItem>
//                 <SelectItem value="active">Active</SelectItem>
//                 <SelectItem value="paused">Paused</SelectItem>
//                 <SelectItem value="completed">Completed</SelectItem>
//               </SelectContent>
//             </Select>
//             <Button variant="outline" size="sm" onClick={() => selectedCampaign && openEdit(selectedCampaign)}><Edit3 className="h-3 w-3 mr-1" /> Edit</Button>
//             <Button variant="outline" size="sm" onClick={() => cloneMut.mutate(selectedId)} disabled={cloneMut.isPending}>
//               {cloneMut.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Copy className="h-3 w-3 mr-1" />} Clone
//             </Button>
//             <Button variant="ghost" size="sm" className="text-destructive" onClick={() => selectedCampaign && setDeleteTarget(selectedCampaign)}>
//               <Trash2 className="h-3 w-3" />
//             </Button>
//           </div>

//           {/* Sender identity card */}
//           {selectedCampaign?.senderOffer && (
//             <Card className="border-primary/20 bg-primary/5">
//               <CardContent className="p-4">
//                 <div className="flex items-start gap-3">
//                   <Briefcase className="h-5 w-5 text-primary mt-0.5 shrink-0" />
//                   <div className="space-y-1 text-sm flex-1 min-w-0">
//                     <div className="flex items-center gap-2 flex-wrap">
//                       <span className="font-medium">{selectedCampaign.senderRole ?? "Sender"}</span>
//                       <span className="text-muted-foreground">at</span>
//                       <span className="font-medium">{selectedCampaign.senderCompany ?? "Company"}</span>
//                     </div>
//                     <p className="text-muted-foreground"><b>Offer:</b> {selectedCampaign.senderOffer}</p>
//                     {selectedCampaign.proofMetric && <p className="text-muted-foreground"><b>Proof:</b> {selectedCampaign.proofMetric}</p>}
//                     {selectedCampaign.senderProduct && <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{selectedCampaign.senderProduct}</p>}
//                   </div>
//                 </div>
//               </CardContent>
//             </Card>
//           )}

//           {/* ── 6-tab detail ── */}
//           <Tabs value={detailTab} onValueChange={setDetailTab}>
//             <TabsList className="flex-wrap">
//               <TabsTrigger value="prospects"><Users className="h-3 w-3 mr-1" /> Prospects ({campaignProspects.length})</TabsTrigger>
//               <TabsTrigger value="sequences"><Mail className="h-3 w-3 mr-1" /> Sequences ({displaySeqs.length})</TabsTrigger>
//               <TabsTrigger value="collaterals"><Paperclip className="h-3 w-3 mr-1" /> Collaterals ({linkedCollaterals.length})</TabsTrigger>
//               <TabsTrigger value="mailbridge"><Send className="h-3 w-3 mr-1" /> Email Sending</TabsTrigger>
//               <TabsTrigger value="compliance"><ShieldCheck className="h-3 w-3 mr-1" /> Compliance</TabsTrigger>
//               <TabsTrigger value="tools"><Wand2 className="h-3 w-3 mr-1" /> Tools</TabsTrigger>
//             </TabsList>

//             {/* ══ C-3: PROSPECTS TAB ══ */}
//             <TabsContent value="prospects" className="space-y-4">
//               {/* <div className="flex items-center justify-between">
//                 <p className="text-sm text-muted-foreground">{campaignProspects.length} prospects linked</p>
//                 <Button size="sm" onClick={() => setAddProspectOpen(true)}><Plus className="h-3 w-3 mr-1" /> Add Prospects</Button>
//               </div> */}
//               {campaignProspects.length === 0 ? (
//                 <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No prospects added yet. Click "Add Prospects" to select from your list.</CardContent></Card>
//               ) : (
//                 <Card>
//                   <CardContent className="p-0">
//                     <ScrollArea className="max-h-[50vh]">
//                       <table className="w-full text-sm">
//                         <thead className="bg-muted/50 sticky top-0">
//                           <tr>
//                             <th className="text-left p-3 font-medium">Name</th>
//                             <th className="text-left p-3 font-medium hidden sm:table-cell">Company</th>
//                             <th className="text-left p-3 font-medium hidden md:table-cell">Title</th>
//                             <th className="text-left p-3 font-medium">Status</th>
//                             <th className="text-left p-3 font-medium">Actions</th>
//                           </tr>
//                         </thead>
//                         <tbody>
//                           {campaignProspects.map((cp) => (
//                             <tr key={cp.id} className="border-t">
//                               <td className="p-3 font-medium">{cp.prospect?.firstName} {cp.prospect?.lastName}</td>
//                               <td className="p-3 hidden sm:table-cell">{cp.prospect?.company ?? "—"}</td>
//                               <td className="p-3 hidden md:table-cell">{cp.prospect?.title ?? "—"}</td>
//                               <td className="p-3"><Badge variant="outline" className="text-xs">{cp.status}</Badge></td>
//                               <td className="p-3">
//                                 <Button size="sm" variant="ghost" className="text-destructive h-7" onClick={() => handleRemoveProspect(cp.prospectId)}>
//                                   <Trash2 className="h-3 w-3" />
//                                 </Button>
//                               </td>
//                             </tr>
//                           ))}
//                         </tbody>
//                       </table>
//                     </ScrollArea>
//                   </CardContent>
//                 </Card>
//               )}

//               {/* Add Prospects Dialog */}
//               <Dialog open={addProspectOpen} onOpenChange={setAddProspectOpen}>
//                 <DialogHeader>
//                   <DialogTitle>Add Prospects to Campaign</DialogTitle>
//                   <DialogDescription>Search and select prospects to link</DialogDescription>
//                 </DialogHeader>
//                 <div className="space-y-4 py-4">
//                   <Input placeholder="Search by name, company, or title…" value={prospectSearch} onChange={(e) => setProspectSearch(e.target.value)} />
//                   <div className="flex items-center justify-between text-sm">
//                     <span className="text-muted-foreground">{addProspectIds.size} selected</span>
//                     {addProspectIds.size > 0 && <Button size="sm" variant="ghost" onClick={() => setAddProspectIds(new Set())}>Clear</Button>}
//                   </div>
//                   <ScrollArea className="max-h-64">
//                     {availableProspects.length === 0 ? (
//                       <p className="text-sm text-muted-foreground text-center py-4">No prospects available.</p>
//                     ) : (
//                       <div className="space-y-1">
//                         {availableProspects.map((p) => (
//                           <button
//                             key={p.id}
//                             onClick={() => {
//                               const next = new Set(addProspectIds);
//                               if (next.has(p.id)) next.delete(p.id); else next.add(p.id);
//                               setAddProspectIds(next);
//                             }}
//                             className={cn("w-full flex items-center gap-3 p-2 rounded text-left text-sm hover:bg-accent transition-colors", addProspectIds.has(p.id) && "bg-primary/10")}
//                           >
//                             <div className={cn("h-4 w-4 rounded border flex items-center justify-center shrink-0", addProspectIds.has(p.id) ? "bg-primary border-primary" : "border-border")}>
//                               {addProspectIds.has(p.id) && <Check className="h-3 w-3 text-primary-foreground" />}
//                             </div>
//                             <span className="font-medium">{p.firstName} {p.lastName}</span>
//                             <span className="text-muted-foreground truncate">{p.company ?? ""}{p.title ? ` — ${p.title}` : ""}</span>
//                           </button>
//                         ))}
//                       </div>
//                     )}
//                   </ScrollArea>
//                 </div>
//                 <DialogFooter>
//                   <Button variant="outline" onClick={() => { setAddProspectOpen(false); setAddProspectIds(new Set()); }}>Cancel</Button>
//                   <Button onClick={handleAddProspects} disabled={addProspectIds.size === 0 || linkProspectMut.isPending}>
//                     {linkProspectMut.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
//                     Add {addProspectIds.size} Prospects
//                   </Button>
//                 </DialogFooter>
//               </Dialog>
//             </TabsContent>

//             {/* ══ C-4: SEQUENCES TAB ══ */}
//             <TabsContent value="sequences" className="space-y-4">
//               {/* Generation controls */}
//               <Card>
//                 <CardContent className="p-4">
//                   <div className="flex flex-wrap items-end gap-3">
//                     <div className="space-y-1">
//                       <Label className="text-xs">Framework</Label>
//                       <Select value={seqFramework} onValueChange={setSeqFramework}>
//                         <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
//                         <SelectContent>
//                           {Object.entries(FRAMEWORK_NAMES).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
//                         </SelectContent>
//                       </Select>
//                     </div>
//                     <Button onClick={handleGenerateSequences} disabled={generating || campaignProspects.length === 0}>
//                       {generating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Layers className="h-4 w-4 mr-2" />}
//                       {generating ? "Generating…" : "Generate Sequences"}
//                     </Button>
//                     {displaySeqs.some((s) => s.status === "QaPassed") && (
//                       <>
//                         <Button variant="outline" onClick={handleSendAllApproved} disabled={sendingId === "bulk"}>
//                           {sendingId === "bulk" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}
//                           Send All Approved
//                         </Button>
//                         <Button variant="outline" onClick={handleScheduleCampaign}>
//                           <CalendarClock className="h-4 w-4 mr-2" /> Schedule Campaign
//                         </Button>
//                       </>
//                     )}
//                   </div>
//                   {campaignProspects.length === 0 && (
//                     <p className="text-xs text-amber-600 mt-2">Add prospects to the campaign first before generating sequences.</p>
//                   )}
//                 </CardContent>
//               </Card>

//               {/* Sequence timeline */}
//               {displaySeqs.length === 0 ? (
//                 <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">Select prospects then generate sequences to see emails here.</CardContent></Card>
//               ) : (
//                 <div className="relative">
//                   <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />
//                   {displaySeqs.map((seq, i) => {
//                     const draft = seqDrafts[seq.id];
//                     const subject = draft?.subjectLine ?? seq.subjectLine ?? "";
//                     const body = draft?.bodyCopy ?? seq.bodyCopy ?? "";
//                     return (
//                       <div key={seq.id} className="relative pl-14 pb-6">
//                         <div className="absolute left-4 h-5 w-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold shrink-0">
//                           {seq.touchNumber}
//                         </div>
//                         <Card className={cn(seq.status === "Sent" && "border-blue-200", seq.status === "QaPassed" && "border-emerald-200")}>
//                           <CardHeader className="pb-2">
//                             <div className="flex items-center justify-between flex-wrap gap-2">
//                               <div>
//                                 <CardTitle className="text-sm">Touch {seq.touchNumber}: {seq.angle.replace(/([A-Z])/g, " $1").trim()}</CardTitle>
//                                 <CardDescription className="text-xs">Day {seq.sendDay}</CardDescription>
//                               </div>
//                               <div className="flex items-center gap-2">
//                                 <span className={cn("text-xs px-2 py-0.5 rounded-full", SEQ_STATUS_COLORS[seq.status] ?? "bg-gray-100 text-gray-600")}>{seq.status}</span>
//                                 {seq.status === "QaPassed" && (
//                                   <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleSendEmail(seq.id)} disabled={sendingId === seq.id}>
//                                     {sendingId === seq.id ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Send className="h-3 w-3 mr-1" />} Send
//                                   </Button>
//                                 )}
//                               </div>
//                             </div>
//                           </CardHeader>
//                           <CardContent className="space-y-2">
//                             <Input
//                               value={subject}
//                               onChange={(e) => setSeqDrafts((prev) => ({ ...prev, [seq.id]: { subjectLine: e.target.value, bodyCopy: prev[seq.id]?.bodyCopy ?? body } }))}
//                               placeholder="Subject line"
//                               className="text-sm"
//                             />
//                             <Textarea
//                               value={body}
//                               onChange={(e) => setSeqDrafts((prev) => ({ ...prev, [seq.id]: { subjectLine: prev[seq.id]?.subjectLine ?? subject, bodyCopy: e.target.value } }))}
//                               rows={5}
//                               className="text-sm font-mono"
//                             />
//                             <div className="flex justify-end gap-2">
//                               <Button size="sm" variant="outline" className="h-7" onClick={() => handleApproveSequence(seq, i)}>
//                                 <CheckCircle2 className="h-3 w-3 mr-1" /> Approve
//                               </Button>
//                               <Button size="sm" variant="ghost" className="h-7" onClick={() => navigator.clipboard.writeText(body).then(() => toast.success("Copied"))}>
//                                 <Copy className="h-3 w-3 mr-1" /> Copy
//                               </Button>
//                             </div>
//                           </CardContent>
//                         </Card>
//                       </div>
//                     );
//                   })}
//                 </div>
//               )}
//             </TabsContent>

//             {/* ══ C-5: COLLATERALS TAB ══ */}
//             <TabsContent value="collaterals" className="space-y-4">
//               <div className="flex items-center justify-between">
//                 <p className="text-sm text-muted-foreground">Case studies, decks, and other assets linked to this campaign</p>
//                 <div className="flex gap-2">
//                   <Button size="sm" variant="outline" onClick={() => setLinkCollateralOpen(true)}><Link2 className="h-3 w-3 mr-1" /> Link from Library</Button>
//                   <Button size="sm" onClick={() => setCollateralDialog(true)}><Plus className="h-3 w-3 mr-1" /> Add New</Button>
//                 </div>
//               </div>
//               {linkedCollaterals.length === 0 ? (
//                 <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No collaterals linked. Add from your library or create a new one.</CardContent></Card>
//               ) : (
//                 <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
//                   {linkedCollaterals.map((c) => (
//                     <Card key={c.id}>
//                       <CardHeader className="pb-2">
//                         <div className="flex items-center justify-between">
//                           <CardTitle className="text-sm flex items-center gap-2"><Paperclip className="h-3 w-3" /> {c.name}</CardTitle>
//                           <Button size="sm" variant="ghost" className="text-destructive h-7" onClick={() => handleUnlinkCollateral(c.id)}><Trash2 className="h-3 w-3" /></Button>
//                         </div>
//                         <Badge variant="outline" className="text-xs w-fit">{c.type.replace(/_/g, " ")}</Badge>
//                       </CardHeader>
//                       <CardContent>
//                         {c.description && <p className="text-xs text-muted-foreground mb-2">{c.description}</p>}
//                         {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline flex items-center gap-1"><Link2 className="h-3 w-3" /> {c.url}</a>}
//                       </CardContent>
//                     </Card>
//                   ))}
//                 </div>
//               )}

//               {/* Add collateral dialog */}
//               <Dialog open={collateralDialog} onOpenChange={setCollateralDialog}>
//                 <DialogHeader>
//                   <DialogTitle>Add Campaign Collateral</DialogTitle>
//                   <DialogDescription>Creates a new collateral in the library and links it to this campaign</DialogDescription>
//                 </DialogHeader>
//                 <div className="space-y-4 py-4">
//                   <div className="space-y-1"><Label className="text-xs">Name *</Label><Input placeholder="e.g. Q3 ROI Case Study" value={collForm.name} onChange={(e) => setCollForm((f) => ({ ...f, name: e.target.value }))} /></div>
//                   <div className="space-y-1">
//                     <Label className="text-xs">Type</Label>
//                     <Select value={collForm.type} onValueChange={(v) => setCollForm((f) => ({ ...f, type: v }))}>
//                       <SelectTrigger><SelectValue /></SelectTrigger>
//                       <SelectContent>
//                         {["case_study","deck","one_pager","testimonial","whitepaper","demo_link","video","other"].map((t) => <SelectItem key={t} value={t}>{t.replace(/_/g, " ")}</SelectItem>)}
//                       </SelectContent>
//                     </Select>
//                   </div>
//                   <div className="space-y-1"><Label className="text-xs">URL</Label><Input placeholder="https://…" value={collForm.url} onChange={(e) => setCollForm((f) => ({ ...f, url: e.target.value }))} /></div>
//                   <div className="space-y-1"><Label className="text-xs">Description</Label><Input placeholder="Brief description" value={collForm.description} onChange={(e) => setCollForm((f) => ({ ...f, description: e.target.value }))} /></div>
//                   <div className="space-y-1"><Label className="text-xs">Brand Content</Label><Textarea placeholder="Paste key quotes, talking points, or proof text…" value={collForm.content} onChange={(e) => setCollForm((f) => ({ ...f, content: e.target.value }))} rows={3} /></div>
//                 </div>
//                 <DialogFooter>
//                   <Button variant="outline" onClick={() => setCollateralDialog(false)}>Cancel</Button>
//                   <Button onClick={() => { if (!collForm.name) { toast.error("Name required"); return; } createCollateralMut.mutate({ name: collForm.name, type: collForm.type, url: collForm.url || null, content: collForm.content || null, description: collForm.description || null }); }} disabled={createCollateralMut.isPending}>
//                     {createCollateralMut.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null} Add Collateral
//                   </Button>
//                 </DialogFooter>
//               </Dialog>

//               {/* Link from library dialog */}
//               <Dialog open={linkCollateralOpen} onOpenChange={setLinkCollateralOpen}>
//                 <DialogHeader>
//                   <DialogTitle>Link Collateral from Library</DialogTitle>
//                   <DialogDescription>Select an existing collateral to attach to this campaign</DialogDescription>
//                 </DialogHeader>
//                 <div className="py-4 space-y-2">
//                   <Label className="text-xs">Collateral</Label>
//                   <Select value={linkCollateralId} onValueChange={setLinkCollateralId}>
//                     <SelectTrigger><SelectValue placeholder="Select collateral…" /></SelectTrigger>
//                     <SelectContent>
//                       {collateralLibrary.filter((c) => !linkedCollateralIds.has(c.id)).map((c) => <SelectItem key={c.id} value={c.id}>{c.name} ({c.type})</SelectItem>)}
//                     </SelectContent>
//                   </Select>
//                   {collateralLibrary.filter((c) => !linkedCollateralIds.has(c.id)).length === 0 && (
//                     <p className="text-xs text-muted-foreground">All library collaterals are already linked to this campaign.</p>
//                   )}
//                 </div>
//                 <DialogFooter>
//                   <Button variant="outline" onClick={() => { setLinkCollateralOpen(false); setLinkCollateralId(""); }}>Cancel</Button>
//                   <Button onClick={handleLinkCollateral} disabled={!linkCollateralId}>Link</Button>
//                 </DialogFooter>
//               </Dialog>
//             </TabsContent>

//             {/* ══ C-6: EMAIL SENDING TAB ══ */}
//             <TabsContent value="mailbridge" className="space-y-4">
//               <div className="flex items-center justify-between">
//                 <div>
//                   <p className="text-sm text-muted-foreground">Connect to your MailBridge server for email delivery and tracking</p>
//                   <p className="text-xs text-muted-foreground mt-1">MailBridge handles sending, bounce suppression, read receipts, and follow-up sequences</p>
//                 </div>
//                 <Button size="sm" onClick={() => setMbDialog(true)}><Plus className="h-3 w-3 mr-1" /> Add Connection</Button>
//               </div>
//               {mailbridgeQ.isLoading ? <Skeleton className="h-20 w-full" /> : mbConfigs.length === 0 ? (
//                 <Card><CardContent className="py-8 text-center">
//                   <Send className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
//                   <p className="text-sm text-muted-foreground mb-1">No MailBridge connections</p>
//                   <p className="text-xs text-muted-foreground">Add your MailBridge server URL to start sending emails</p>
//                 </CardContent></Card>
//               ) : (
//                 <div className="space-y-3">
//                   {mbConfigs.map((c) => (
//                     <Card key={c.id}><CardContent className="p-4 flex items-center justify-between">
//                       <div className="space-y-0.5">
//                         <p className="text-sm font-medium">{c.name}</p>
//                         <p className="text-xs text-muted-foreground">{c.baseUrl} — {c.fromEmail}</p>
//                         <p className="text-xs text-muted-foreground capitalize">{c.provider}</p>
//                       </div>
//                       <div className="flex items-center gap-2">
//                         <Badge variant={c.isActive ? "default" : "secondary"} className="text-xs">{c.isActive ? "Active" : "Inactive"}</Badge>
//                         <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleTestMb(c)}>Test</Button>
//                         <Button size="sm" variant="ghost" className="text-destructive h-7" onClick={() => deleteMbMut.mutate(c.id)} disabled={deleteMbMut.isPending}><Trash2 className="h-3 w-3" /></Button>
//                       </div>
//                     </CardContent></Card>
//                   ))}
//                 </div>
//               )}

//               {/* Add MailBridge dialog */}
//               <Dialog open={mbDialog} onOpenChange={setMbDialog}>
//                 <DialogHeader>
//                   <DialogTitle>Add MailBridge Connection</DialogTitle>
//                   <DialogDescription>Configure your MailBridge server for email delivery</DialogDescription>
//                 </DialogHeader>
//                 <div className="space-y-4 py-4">
//                   <div className="space-y-1"><Label className="text-xs">Display Name *</Label><Input placeholder="e.g. Gmail via MailBridge" value={mbForm.name} onChange={(e) => setMbForm((f) => ({ ...f, name: e.target.value }))} /></div>
//                   <div className="space-y-1">
//                     <Label className="text-xs">MailBridge Server URL *</Label>
//                     <Input placeholder="e.g. http://172.93.49.106:9000" value={mbForm.baseUrl} onChange={(e) => setMbForm((f) => ({ ...f, baseUrl: e.target.value }))} />
//                     <p className="text-xs text-muted-foreground">Base URL of your MailBridge FastAPI server (Swagger at /docs)</p>
//                   </div>
//                   <div className="space-y-1">
//                     <Label className="text-xs">Email Provider</Label>
//                     <Select value={mbForm.provider} onValueChange={(v) => setMbForm((f) => ({ ...f, provider: v }))}>
//                       <SelectTrigger><SelectValue /></SelectTrigger>
//                       <SelectContent>
//                         <SelectItem value="gmail">Gmail (Google Workspace)</SelectItem>
//                         <SelectItem value="outlook">Outlook (Microsoft 365)</SelectItem>
//                         <SelectItem value="smtp">Generic SMTP</SelectItem>
//                         <SelectItem value="sendgrid">SendGrid</SelectItem>
//                         <SelectItem value="ses">Amazon SES</SelectItem>
//                       </SelectContent>
//                     </Select>
//                   </div>
//                   <div className="grid grid-cols-2 gap-4">
//                     <div className="space-y-1"><Label className="text-xs">From Email *</Label><Input placeholder="john@myco.com" value={mbForm.fromEmail} onChange={(e) => setMbForm((f) => ({ ...f, fromEmail: e.target.value }))} /></div>
//                     <div className="space-y-1"><Label className="text-xs">From Name</Label><Input placeholder="John Smith" value={mbForm.fromName} onChange={(e) => setMbForm((f) => ({ ...f, fromName: e.target.value }))} /></div>
//                   </div>
//                 </div>
//                 <DialogFooter>
//                   <Button variant="outline" onClick={() => setMbDialog(false)}>Cancel</Button>
//                   <Button onClick={() => {
//                     if (!mbForm.name || !mbForm.baseUrl || !mbForm.fromEmail) { toast.error("Name, URL, and From Email are required"); return; }
//                     createMbMut.mutate({ name: mbForm.name, baseUrl: mbForm.baseUrl, provider: mbForm.provider, fromEmail: mbForm.fromEmail, fromName: mbForm.fromName || null });
//                   }} disabled={createMbMut.isPending}>
//                     {createMbMut.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null} Save Connection
//                   </Button>
//                 </DialogFooter>
//               </Dialog>
//             </TabsContent>

//             {/* ══ C-7: COMPLIANCE TAB ══ */}
//             <TabsContent value="compliance" className="space-y-4">
//               <div className="p-3 rounded-lg bg-muted text-xs text-muted-foreground">
//                 <b>CAN-SPAM Act</b> requires: (1) a physical mailing address, (2) a clear unsubscribe mechanism, (3) no deceptive subject lines. <b>GDPR</b> requires: lawful basis, right to erasure, and data minimization.
//               </div>

//               <Card>
//                 <CardHeader className="pb-3"><CardTitle className="text-sm">CAN-SPAM / GDPR Settings</CardTitle></CardHeader>
//                 <CardContent className="space-y-4">
//                   <div className="flex items-center justify-between">
//                     <div>
//                       <p className="text-sm font-medium">Auto-append Compliance Footer</p>
//                       <p className="text-xs text-muted-foreground">Adds physical address + unsubscribe link to every email</p>
//                     </div>
//                     <Switch
//                       checked={!!selectedCampaign?.complianceFooter}
//                       onCheckedChange={(v) => handleComplianceUpdate({ complianceFooter: v })}
//                     />
//                   </div>
//                   <Separator />
//                   <div className="space-y-1">
//                     <Label className="text-xs">Physical Mailing Address</Label>
//                     <Input
//                       placeholder="123 Business St, Suite 100, San Francisco, CA 94105"
//                       defaultValue={selectedCampaign?.physicalAddress ?? ""}
//                       onBlur={(e) => handleComplianceUpdate({ physicalAddress: e.target.value })}
//                     />
//                     <p className="text-xs text-muted-foreground">Required by CAN-SPAM. Appears in the footer of every email.</p>
//                   </div>
//                   <div className="space-y-1">
//                     <Label className="text-xs">Unsubscribe URL</Label>
//                     <Input
//                       placeholder="https://yourcompany.com/unsubscribe"
//                       defaultValue={selectedCampaign?.unsubscribeUrl ?? ""}
//                       onBlur={(e) => handleComplianceUpdate({ unsubscribeUrl: e.target.value })}
//                     />
//                     <p className="text-xs text-muted-foreground">If not set, "Reply STOP to unsubscribe" will be used.</p>
//                   </div>
//                 </CardContent>
//               </Card>

//               {/* Webhook URL card */}
//               <Card>
//                 <CardHeader className="pb-3"><CardTitle className="text-sm flex items-center gap-2"><Webhook className="h-4 w-4" /> MailBridge Webhook</CardTitle></CardHeader>
//                 <CardContent className="space-y-3">
//                   <p className="text-xs text-muted-foreground">
//                     Configure MailBridge to push real-time events (opens, bounces, replies) to this platform. Add this URL to your MailBridge <code className="bg-muted px-1 rounded">mailbridge.yaml</code>:
//                   </p>
//                   <div className="flex items-center gap-2">
//                     <code className="flex-1 bg-muted px-3 py-2 rounded-lg text-xs truncate">{typeof window !== "undefined" ? `${window.location.origin}/api/v1/mailbridge/webhook` : "/api/v1/mailbridge/webhook"}</code>
//                     <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(`${typeof window !== "undefined" ? window.location.origin : ""}/api/v1/mailbridge/webhook`); toast.success("Webhook URL copied"); }}>
//                       <Copy className="h-3 w-3" />
//                     </Button>
//                   </div>
//                   <p className="text-xs text-muted-foreground">Events: delivery.opened, delivery.bounced, email.replied, email.received</p>
//                 </CardContent>
//               </Card>
//             </TabsContent>

//             {/* ══ C-8: TOOLS TAB ══ */}
//             <TabsContent value="tools" className="space-y-4">
//               <Card>
//                 <CardHeader className="pb-3"><CardTitle className="text-sm flex items-center gap-2"><MessageCircleReply className="h-4 w-4" /> AI Reply Categorization</CardTitle></CardHeader>
//                 <CardContent className="space-y-4">
//                   <p className="text-xs text-muted-foreground">
//                     Paste a prospect reply to categorize it: Interested, Not Interested, Out of Office, Needs Info, Meeting Request, Counter Proposal, Positive Signal, Neutral.
//                   </p>
//                   <Textarea placeholder="Paste a prospect's reply email here…" value={replyText} onChange={(e) => setReplyText(e.target.value)} rows={4} />
//                   <Button onClick={handleCategorizeReply} disabled={replyCategorizing || !replyText.trim()}>
//                     {replyCategorizing ? <Loader2 className="h-3 w-3 mr-2 animate-spin" /> : <MessageCircleReply className="h-3 w-3 mr-2" />}
//                     {replyCategorizing ? "Categorizing…" : "Categorize Reply"}
//                   </Button>
//                   {replyResult && (
//                     <Card className={cn(
//                       "border",
//                       (replyResult.category === "interested" || replyResult.category === "meeting_request") ? "border-emerald-200 bg-emerald-50"
//                         : replyResult.category === "not_interested" ? "border-red-200 bg-red-50"
//                         : "border-blue-100 bg-blue-50"
//                     )}>
//                       <CardContent className="p-3 space-y-2">
//                         <div className="flex items-center justify-between">
//                           <Badge className={cn("text-xs",
//                             (replyResult.category === "interested" || replyResult.category === "meeting_request") ? "bg-emerald-100 text-emerald-800"
//                               : replyResult.category === "not_interested" ? "bg-red-100 text-red-800"
//                               : "bg-blue-100 text-blue-800"
//                           )}>{(replyResult.category ?? "unknown").replace(/_/g, " ")}</Badge>
//                           {replyResult.confidence != null && (
//                             <span className="text-xs text-muted-foreground">Confidence: {(replyResult.confidence * 100).toFixed(0)}%</span>
//                           )}
//                         </div>
//                         {replyResult.summary && <p className="text-xs"><b>Summary:</b> {replyResult.summary}</p>}
//                         {replyResult.suggestedAction && <p className="text-xs"><b>Suggested Action:</b> {replyResult.suggestedAction}</p>}
//                       </CardContent>
//                     </Card>
//                   )}
//                 </CardContent>
//               </Card>
//             </TabsContent>
//           </Tabs>
//         </>
//       )}

//       {/* ══════════════ C-1: CREATE / EDIT DIALOG ══════════════ */}
//       <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
//         <DialogHeader>
//           <DialogTitle>{editingId ? "Edit Campaign" : "Create Campaign"}</DialogTitle>
//           <DialogDescription>Define your campaign, sender identity, and product/service for AI-powered emails</DialogDescription>
//         </DialogHeader>
//         <Tabs value={formTab} onValueChange={setFormTab}>
//           <TabsList className="grid w-full grid-cols-3">
//             <TabsTrigger value="basics">Basics</TabsTrigger>
//             <TabsTrigger value="sender">Sender &amp; Product</TabsTrigger>
//             <TabsTrigger value="config">Configuration</TabsTrigger>
//           </TabsList>
//           <ScrollArea className="max-h-[60vh]">
//             <TabsContent value="basics" className="space-y-4 py-4 px-1">
//               <div className="space-y-1"><Label className="text-xs">Campaign Name *</Label><Input placeholder="e.g. Q3 SaaS CTO Outreach" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></div>
//               <div className="space-y-1"><Label className="text-xs">Description / Goal</Label><Textarea placeholder="What is this campaign trying to achieve?" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={3} /></div>
//               <div className="grid grid-cols-2 gap-4">
//                 <div className="space-y-1">
//                   <Label className="text-xs">Status</Label>
//                   <Select value={form.status} onValueChange={(v) => setForm((f) => ({ ...f, status: v }))}>
//                     <SelectTrigger><SelectValue /></SelectTrigger>
//                     <SelectContent>
//                       <SelectItem value="draft">Draft</SelectItem>
//                       <SelectItem value="active">Active</SelectItem>
//                       <SelectItem value="paused">Paused</SelectItem>
//                       <SelectItem value="completed">Completed</SelectItem>
//                     </SelectContent>
//                   </Select>
//                 </div>
//                 <div className="space-y-1">
//                   <Label className="text-xs">Framework</Label>
//                   <Select value={form.framework} onValueChange={(v) => setForm((f) => ({ ...f, framework: v }))}>
//                     <SelectTrigger><SelectValue /></SelectTrigger>
//                     <SelectContent>
//                       {Object.entries(FRAMEWORK_NAMES).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
//                     </SelectContent>
//                   </Select>
//                 </div>
//               </div>
//               <div className="space-y-1"><Label className="text-xs">Target Audience</Label><Input placeholder="e.g. VP Engineering at Series A-B SaaS companies" value={form.targetAudience} onChange={(e) => setForm((f) => ({ ...f, targetAudience: e.target.value }))} /></div>
//             </TabsContent>

//             <TabsContent value="sender" className="space-y-4 py-4 px-1">
//               <div className="p-3 rounded-lg bg-muted text-xs text-muted-foreground">
//                 <b>Why this matters:</b> The AI uses your sender identity and product description to write accurate, personalized emails. The more detail you provide, the better the output.
//               </div>
//               <div className="grid grid-cols-2 gap-4">
//                 <div className="space-y-1"><Label className="text-xs">Sender Role</Label><Input placeholder="e.g. CEO at MyCo" value={form.senderRole} onChange={(e) => setForm((f) => ({ ...f, senderRole: e.target.value }))} /></div>
//                 <div className="space-y-1"><Label className="text-xs">Sender Company</Label><Input placeholder="e.g. MyCo" value={form.senderCompany} onChange={(e) => setForm((f) => ({ ...f, senderCompany: e.target.value }))} /></div>
//               </div>
//               <div className="grid grid-cols-2 gap-4">
//                 <div className="space-y-1"><Label className="text-xs">Offer (Short)</Label><Input placeholder="e.g. AI lead gen platform" value={form.senderOffer} onChange={(e) => setForm((f) => ({ ...f, senderOffer: e.target.value }))} /></div>
//                 <div className="space-y-1"><Label className="text-xs">Proof Metric</Label><Input placeholder="e.g. 3x pipeline in 90 days" value={form.proofMetric} onChange={(e) => setForm((f) => ({ ...f, proofMetric: e.target.value }))} /></div>
//               </div>
//               <div className="space-y-1">
//                 <Label className="text-xs">Product/Service Description (Detailed)</Label>
//                 <Textarea placeholder="We provide an AI-powered sales development platform…" value={form.senderProduct} onChange={(e) => setForm((f) => ({ ...f, senderProduct: e.target.value }))} rows={5} />
//                 <p className="text-xs text-muted-foreground">Key context the AI uses to understand what you sell. Be specific about features, outcomes, and differentiators.</p>
//               </div>
//             </TabsContent>

//             <TabsContent value="config" className="space-y-4 py-4 px-1">
//               <div className="space-y-1">
//                 <Label className="text-xs">ICP Profile</Label>
//                 <Select
//                   value={form.icpProfileId}
//                   onValueChange={(v) => {
//                     const icp = icps.find((i) => i.id === v);
//                     if (icp && !editingId) {
//                       setForm((f) => ({ ...f, icpProfileId: v, senderRole: f.senderRole || icp.senderRole || "", senderCompany: f.senderCompany || icp.senderCompany || "", senderOffer: f.senderOffer || icp.senderOffer || "", proofMetric: f.proofMetric || icp.proofMetric || "" }));
//                     } else {
//                       setForm((f) => ({ ...f, icpProfileId: v }));
//                     }
//                   }}
//                 >
//                   <SelectTrigger><SelectValue placeholder="Select ICP profile…" /></SelectTrigger>
//                   <SelectContent>{icps.map((icp) => <SelectItem key={icp.id} value={icp.id}>{icp.name}</SelectItem>)}</SelectContent>
//                 </Select>
//                 <p className="text-xs text-muted-foreground">The ICP defines objections, pain points, and value props used in email generation.</p>
//               </div>
//               <div className="space-y-1">
//                 <Label className="text-xs">LLM Model</Label>
//                 <p className="text-xs text-muted-foreground bg-muted rounded p-2">
//                   Uses your tenant default LLM automatically. To configure LLM models, go to <b>Setup → LLM Models</b>.
//                 </p>
//               </div>
//               <div className="space-y-1">
//                 <Label className="text-xs">Sending Domain</Label>
//                 <Select value={form.domainId} onValueChange={(v) => setForm((f) => ({ ...f, domainId: v }))}>
//                   <SelectTrigger><SelectValue placeholder="Select domain…" /></SelectTrigger>
//                   <SelectContent>{domains.map((d) => <SelectItem key={d.id} value={d.id}>{d.domainName}</SelectItem>)}</SelectContent>
//                 </Select>
//               </div>
//             </TabsContent>
//           </ScrollArea>
//         </Tabs>
//         <DialogFooter>
//           <Button variant="outline" onClick={() => { setDialogOpen(false); resetForm(); }}>Cancel</Button>
//           <Button onClick={handleSave} disabled={saveMut.isPending}>
//             {saveMut.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
//             {editingId ? "Update Campaign" : "Create Campaign"}
//           </Button>
//         </DialogFooter>
//       </Dialog>

//       {/* ══════════════ C-9: PRE-FLIGHT DIALOG ══════════════ */}
//       <Dialog open={preflightOpen} onOpenChange={(o) => { setPreflightOpen(o); if (!o) { setPreflightResult(null); setPendingActivateId(""); } }}>
//         <DialogHeader>
//           <DialogTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Pre-Flight Activation Check</DialogTitle>
//           <DialogDescription>Deliverability checks run before activating. Prevents domain burn before it happens.</DialogDescription>
//         </DialogHeader>
//         {preflightLoading ? (
//           <div className="flex items-center justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
//         ) : preflightResult ? (
//           <div className="space-y-3 py-2">
//             {preflightResult.checks?.map((c, i) => (
//               <div key={i} className="flex items-start gap-2 text-sm">
//                 {c.status === "pass" ? <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
//                   : c.status === "fail" ? <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 shrink-0" />
//                   : <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />}
//                 <div>
//                   <span className="font-medium">{c.name}</span>
//                   <p className="text-xs text-muted-foreground">{c.detail}</p>
//                 </div>
//               </div>
//             ))}
//             {(preflightResult.warnings?.length ?? 0) > 0 && (
//               <div className="p-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
//                 <b>Warnings:</b> {preflightResult.warnings!.join(" ")}
//               </div>
//             )}
//           </div>
//         ) : (
//           <p className="text-sm text-muted-foreground text-center py-4">Running checks…</p>
//         )}
//         <DialogFooter>
//           <Button variant="outline" onClick={() => { setPreflightOpen(false); setPreflightResult(null); setPendingActivateId(""); }}>Cancel</Button>
//           <Button
//             onClick={confirmActivate}
//             disabled={!preflightResult || !(preflightResult.passed || preflightResult.allPassed)}
//           >
//             {(preflightResult?.passed || preflightResult?.allPassed)
//               ? <><CheckCircle2 className="h-3 w-3 mr-1" /> Activate Campaign</>
//               : "Blocked — fix errors first"}
//           </Button>
//         </DialogFooter>
//       </Dialog>

//       {/* Delete confirm */}
//       <AlertDialog open={deleteTarget !== null} onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
//         <AlertDialogContent>
//           <AlertDialogHeader>
//             <AlertDialogTitle>Delete campaign?</AlertDialogTitle>
//             <AlertDialogDescription>
//               "{deleteTarget?.name}" and all its sequences will be permanently removed.
//             </AlertDialogDescription>
//           </AlertDialogHeader>
//           <AlertDialogFooter>
//             <AlertDialogCancel>Cancel</AlertDialogCancel>
//             <AlertDialogAction className="bg-destructive hover:bg-destructive/90" onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}>
//               Delete
//             </AlertDialogAction>
//           </AlertDialogFooter>
//         </AlertDialogContent>
//       </AlertDialog>
//     </div>
//   );
// }

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  Briefcase,
  CalendarClock,
  Check,
  CheckCircle2,
  Copy,
  Edit3,
  FileDown,
  Layers,
  Link2,
  Loader2,
  Mail,
  MessageCircleReply,
  Paperclip,
  Plus,
  Send,
  ShieldCheck,
  Trash2,
  Users,
  Wand2,
  Webhook,
} from "lucide-react";
import { toast } from "sonner";
 
import { http } from "@/services/apiClient";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination, usePagination } from "@/components/ui/pagination";
 
/* ── Types ─────────────────────────────────────────────────────────── */
 
interface IcpProfile { id: string; name: string; senderRole?: string | null; senderCompany?: string | null; senderOffer?: string | null; proofMetric?: string | null; }
interface Domain { id: string; domainName: string; }
interface Prospect { id: string; firstName: string; lastName: string; email: string | null; title: string | null; company: string | null; seniority: string; }
interface Collateral { id: string; name: string; type: string; url: string | null; content: string | null; description: string | null; }
interface MailBridgeConfig { id: string; name: string; baseUrl: string; provider: string; fromEmail: string; fromName: string | null; isActive: boolean; }
 
interface CampaignProspectRow {
  id: string;
  prospectId: string;
  campaignId: string;
  status: string;
  prospect?: Prospect;
}
 
interface Campaign {
  id: string;
  name: string;
  description: string | null;
  status: string;
  framework: string | null;
  senderRole: string | null;
  senderCompany: string | null;
  senderOffer: string | null;
  proofMetric: string | null;
  senderProduct: string | null;
  targetAudience: string | null;
  icpProfileId: string | null;
  llmConfigId: string | null;
  domainId: string | null;
  complianceFooter: boolean;
  unsubscribeUrl: string | null;
  physicalAddress: string | null;
  webhookUrl: string | null;
  icpProfile?: IcpProfile | null;
  prospects?: CampaignProspectRow[];
  _count?: { prospects: number; sequences: number; collaterals: number };
  createdAt: string;
  updatedAt: string;
}
 
interface Sequence {
  id: string;
  campaignId: string;
  prospectId: string;
  touchNumber: number;
  sendDay: number;
  angle: string;
  framework: string | null;
  subjectLine: string | null;
  bodyCopy: string | null;
  status: string;
  sentAt: string | null;
  openedAt: string | null;
  repliedAt: string | null;
}
 
interface PreflightCheck { name: string; status: "pass" | "fail" | "warn"; detail: string; }
interface PreflightResult { passed: boolean; checks: PreflightCheck[]; warnings?: string[]; allPassed?: boolean; }
 
/* ── Constants ──────────────────────────────────────────────────────── */
 
/** Human-readable label and colour for every campaign status. */
const CAMPAIGN_STATUS_META: Record<string, { label: string; cls: string }> = {
  draft:     { label: "Draft",     cls: "bg-gray-100 text-gray-700" },
  active:    { label: "Active",    cls: "bg-emerald-100 text-emerald-700" },
  paused:    { label: "Paused",    cls: "bg-amber-100 text-amber-700" },
  completed: { label: "Completed", cls: "bg-blue-100 text-blue-700" },
  archived:  { label: "Archived",  cls: "bg-slate-100 text-slate-500" },
  sending:   { label: "Sending",   cls: "bg-violet-100 text-violet-700" },
  failed:    { label: "Failed",    cls: "bg-red-100 text-red-700" },
};
 
 
 
const FRAMEWORK_NAMES: Record<string, string> = {
  trigger: "Trigger-Based",
  problem: "Problem-First",
  mutual: "Mutual Connection",
  value: "Value-First",
  direct: "Direct Ask",
  challenger: "Challenger",
  meddpicc: "MEDDPICC",
  spiced: "SPICED",
  story: "Story-Led",
};
 
 
 
const SEQ_STATUS_COLORS: Record<string, string> = {
  Draft: "bg-gray-100 text-gray-600",
  QaPassed: "bg-emerald-100 text-emerald-700",
  Sent: "bg-blue-100 text-blue-700",
  Scheduled: "bg-violet-100 text-violet-700",
  Replied: "bg-teal-100 text-teal-700",
  Bounced: "bg-red-100 text-red-700",
};
 
function exportToCsv(rows: Record<string, unknown>[], filename: string) {
  if (rows.length === 0) return;
  const keys = Object.keys(rows[0]);
  const lines = [keys.join(","), ...rows.map((r) => keys.map((k) => JSON.stringify(r[k] ?? "")).join(","))];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${filename}.csv`;
  a.click();
}
 
/* ── Page ──────────────────────────────────────────────────────────── */
 
export function CampaignsPage() {
  const qc = useQueryClient();
 
  /* ── Data queries ── */
  const campaignsQ = useQuery<{ items: Campaign[]; total: number }>({
    queryKey: ["campaigns"],
    queryFn: () => http.get<any>("/api/v1/campaigns").then((r) =>
      Array.isArray(r) ? { items: r, total: r.length } : { items: r?.items ?? [], total: r?.total ?? 0 }
    ),
  });
  const icpQ = useQuery<IcpProfile[]>({ queryKey: ["icp-profiles"], queryFn: () => http.get<any>("/api/v1/icp-profiles").then((r) => Array.isArray(r) ? r : r?.items ?? []) });
  // LLM configs use tenant default — /api/v1/llm-configs requires SUPER_ADMIN
  // Campaign.llmConfigId is optional; null means "use tenant default LLM"
  const domainsQ = useQuery<Domain[]>({ queryKey: ["domains"], queryFn: () => http.get<any>("/api/v1/domains").then((r) => Array.isArray(r) ? r : r?.items ?? []) });
  const prospectsQ = useQuery<Prospect[]>({ queryKey: ["prospects-lite"], queryFn: () => http.get<any>("/api/v1/prospects").then((r) => Array.isArray(r) ? r : r?.items ?? []) });
 
  const campaigns = campaignsQ.data?.items ?? [];
  const icps = icpQ.data ?? [];
  // const llmConfigs: { id: string; name: string; provider: string }[] = []; // campaigns use tenant default LLM
  const domains = domainsQ.data ?? [];
  const allProspects = prospectsQ.data ?? [];
 
  /* ── View state ── */
  const [view, setView] = useState<"list" | "detail">("list");
  const [selectedId, setSelectedId] = useState("");
  const [detailTab, setDetailTab] = useState("prospects");
 
  const selectedCampaign = campaigns.find((c) => c.id === selectedId);
 
  /* ── Detail: lazy-loaded data ── */
  const campaignProspectsQ = useQuery<CampaignProspectRow[]>({
    queryKey: ["campaign-prospects", selectedId],
    queryFn: () =>
      http.get<any>(`/api/v1/campaigns/campaign-prospects?campaign_id=${selectedId}`)
        .then((r) => Array.isArray(r) ? r : r?.items ?? []),
    enabled: view === "detail" && !!selectedId,
  });
 
  const sequencesQ = useQuery<Sequence[]>({
    queryKey: ["sequences", selectedId],
    queryFn: () => http.get<any>(`/api/v1/sequences?campaign_id=${selectedId}&limit=500`).then((r) => Array.isArray(r) ? r : r?.items ?? []),
    enabled: view === "detail" && !!selectedId,
  });
  const collateralsQ = useQuery<Collateral[]>({
    queryKey: ["collaterals"],
    queryFn: () => http.get<any>("/api/v1/collaterals").then((r) => Array.isArray(r) ? r : r?.items ?? []),
    enabled: view === "detail" && !!selectedId,
  });
 
  // Fetch existing collateral links for this campaign so previously linked
  // collaterals are visible when the detail view is opened.
  // Endpoint: GET /api/v1/collaterals/links?campaign_id=X
  const collateralLinksQ = useQuery<{ id: string; collateralId: string; campaignId: string }[]>({
    queryKey: ["collateral-links", selectedId],
    queryFn: () =>
      http.get<any>(`/api/v1/collaterals/links?campaign_id=${selectedId}`)
        .then((r) => Array.isArray(r) ? r : r?.items ?? []),
    enabled: view === "detail" && !!selectedId,
    staleTime: 0,
  });
  const mailbridgeQ = useQuery<MailBridgeConfig[]>({
    queryKey: ["mailbridge-configs"],
    queryFn: () => http.get<any>("/api/v1/mailbridge/config").then((r) => Array.isArray(r) ? r : r?.items ?? []),
    enabled: view === "detail" && !!selectedId,
  });
 
  const sequences = sequencesQ.data ?? [];
  const collateralLibrary = collateralsQ.data ?? [];
  const mbConfigs = mailbridgeQ.data ?? [];
 
  // Campaign prospects fetched directly from the API (not embedded in the campaign list response).
  // Enrich each row with the full prospect object looked up from the allProspects list.
  const campaignProspects: CampaignProspectRow[] = useMemo(
    () =>
      (campaignProspectsQ.data ?? []).map((cp) => ({
        ...cp,
        prospect: cp.prospect ?? allProspects.find((p) => p.id === cp.prospectId),
      })),
    [campaignProspectsQ.data, allProspects]
  );
 
  // Collaterals linked to this campaign (filter library by campaignId in links)
  // The backend returns campaign with collateral links embedded or we filter collateralLibrary
  // Since the API doesn't have a campaign-specific collaterals endpoint, we use the full library
  // and track linked ones via the campaign's _count.collaterals or from a separate state.
  const [linkedCollateralIds, setLinkedCollateralIds] = useState<Set<string>>(new Set());
 
  /* ── Sequence local edits ── */
  const [seqDrafts, setSeqDrafts] = useState<Record<string, { subjectLine: string; bodyCopy: string }>>({});
 
  /* ── Create/Edit form ── */
  const EMPTY_FORM = { name: "", description: "", status: "draft", framework: "trigger", targetAudience: "", senderRole: "", senderCompany: "", senderOffer: "", proofMetric: "", senderProduct: "", icpProfileId: "", llmConfigId: "", domainId: "" };
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [formTab, setFormTab] = useState("basics");
 
  const resetForm = () => { setForm({ ...EMPTY_FORM }); setFormTab("basics"); setEditingId(null); };
  const openCreate = () => { resetForm(); setDialogOpen(true); };
  const openEdit = (c: Campaign) => {
    setEditingId(c.id);
    setForm({ name: c.name, description: c.description ?? "", status: c.status, framework: c.framework ?? "trigger", targetAudience: c.targetAudience ?? "", senderRole: c.senderRole ?? "", senderCompany: c.senderCompany ?? "", senderOffer: c.senderOffer ?? "", proofMetric: c.proofMetric ?? "", senderProduct: c.senderProduct ?? "", icpProfileId: c.icpProfileId ?? "", llmConfigId: c.llmConfigId ?? "", domainId: c.domainId ?? "" });
    setFormTab("basics");
    setDialogOpen(true);
  };
 
  /* ── Campaign CRUD mutations ── */
  const saveMut = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      editingId
        ? http.put(`/api/v1/campaigns/${editingId}`, body)
        : http.post("/api/v1/campaigns", body),
    onSuccess: () => {
      toast.success(editingId ? "Campaign updated" : "Campaign created");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      setDialogOpen(false); resetForm();
    },
    onError: () => toast.error("Failed to save campaign"),
  });
 
  const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null);
  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/campaigns/${id}`),
    onSuccess: () => {
      toast.success("Campaign deleted");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      if (selectedId === deleteTarget?.id) { setView("list"); setSelectedId(""); }
      setDeleteTarget(null);
    },
    onError: () => toast.error("Delete failed"),
  });
 
  const handleSave = () => {
    if (!form.name.trim()) { toast.error("Campaign name is required"); return; }
    saveMut.mutate({ ...form, icpProfileId: form.icpProfileId || null, llmConfigId: form.llmConfigId || null, domainId: form.domainId || null });
  };
 
  /* ── Status change ── */
  const handleStatusChange = async (id: string, newStatus: string) => {
    if (newStatus === "active") {
      setPendingActivateId(id);
      setPreflightOpen(true);
      setPreflightLoading(true);
      setPreflightResult(null);
      try {
        const data = await http.post<any>("/api/v1/campaigns/preflight", { campaignId: id });
        setPreflightResult(data);
      } catch { toast.error("Pre-flight check failed"); setPreflightOpen(false); }
      setPreflightLoading(false);
      return;
    }
    try {
      await http.put(`/api/v1/campaigns/${id}`, { status: newStatus });
      toast.success(`Campaign ${newStatus}`);
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    } catch { toast.error("Status change failed"); }
  };
 
  /* ── Clone ── */
  const cloneMut = useMutation({
    mutationFn: (id: string) => http.post<any>("/api/v1/campaigns/clone", { campaignId: id }),
    onSuccess: (data) => {
      toast.success(`Cloned as "${data.name}"`);
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: () => toast.error("Clone failed"),
  });
 
  /* ── Pre-flight ── */
  const [preflightOpen, setPreflightOpen] = useState(false);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightResult, setPreflightResult] = useState<PreflightResult | null>(null);
  const [pendingActivateId, setPendingActivateId] = useState("");
 
  const confirmActivate = async () => {
    try {
      await http.put(`/api/v1/campaigns/${pendingActivateId}`, { status: "active" });
      toast.success("Campaign activated");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    } catch { toast.error("Activation failed"); }
    setPreflightOpen(false); setPreflightResult(null); setPendingActivateId("");
  };
 
  /* ── Add Prospects dialog ── */
  const [addProspectOpen, setAddProspectOpen] = useState(false);
  const [prospectSearch, setProspectSearch] = useState("");
  const [addProspectIds, setAddProspectIds] = useState<Set<string>>(new Set());
 
  const existingProspectIds = new Set(campaignProspects.map((cp) => cp.prospectId));
  const availableProspects = allProspects.filter((p) =>
    !existingProspectIds.has(p.id) &&
    (prospectSearch === "" || `${p.firstName} ${p.lastName} ${p.company ?? ""} ${p.title ?? ""}`.toLowerCase().includes(prospectSearch.toLowerCase()))
  );
 
  const linkProspectMut = useMutation({
    mutationFn: (prospectId: string) =>
      http.post("/api/v1/campaigns/campaign-prospects", { campaignId: selectedId, prospectId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign-prospects", selectedId] });
    },
  });
 
  const handleAddProspects = async () => {
    if (addProspectIds.size === 0) { toast.error("Select at least one prospect"); return; }
    for (const pid of addProspectIds) {
      await linkProspectMut.mutateAsync(pid).catch(() => {});
    }
    toast.success(`${addProspectIds.size} prospect(s) added`);
    setAddProspectOpen(false); setAddProspectIds(new Set()); setProspectSearch("");
  };
 
  const handleRemoveProspect = async (prospectId: string) => {
    try {
      await fetch("/api/v1/campaigns/campaign-prospects", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ campaignId: selectedId, prospectId }),
      });
      toast.success("Prospect removed");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign-prospects", selectedId] });
    } catch { toast.error("Remove failed"); }
  };
 
  /* ── Sequences ── */
  const [seqFramework, setSeqFramework] = useState("trigger");
  const [generating, setGenerating] = useState(false);
  const [sendingId, setSendingId] = useState<string | null>(null);
 
  const handleGenerateSequences = async () => {
    setGenerating(true);
    try {
      const data = await http.post<any>(`/api/v1/campaigns/${selectedId}/generate-sequences`, {});
      toast.success(data.message ?? `Generated ${data.created} sequences`);
      qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
    } catch { toast.error("Sequence generation failed"); }
    setGenerating(false);
  };
 
  const handleSendEmail = async (seqId: string) => {
    setSendingId(seqId);
    try {
      const data = await http.post<any>(`/api/v1/sequences/${seqId}/send-email`, {});
      if (data.accepted || data.messageId) toast.success("Email sent");
      else toast.error(data.error ?? "Send failed");
      qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
    } catch { toast.error("Send failed"); }
    setSendingId(null);
  };
 
  const handleSendAllApproved = async () => {
    const approved = sequences.filter((s) => s.status === "QaPassed");
    if (approved.length === 0) { toast.error("No approved sequences to send"); return; }
    setSendingId("bulk");
    let sent = 0;
    for (const seq of approved) {
      try {
        await http.post(`/api/v1/sequences/${seq.id}/send-email`, {});
        sent++;
      } catch { /* skip */ }
    }
    toast.success(`${sent}/${approved.length} emails sent`);
    qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
    setSendingId(null);
  };
 
  const handleScheduleCampaign = async () => {
    const approved = sequences.filter((s) => s.status === "QaPassed");
    if (approved.length === 0) { toast.error("No approved sequences to schedule"); return; }
    let scheduled = 0;
    for (const seq of approved) {
      try {
        const sendAt = new Date(Date.now() + seq.sendDay * 86400000).toISOString();
        await http.post(`/api/v1/sequences/${seq.id}/scheduled-send`, { sendAt });
        scheduled++;
      } catch { /* skip */ }
    }
    toast.success(`${scheduled} sequences scheduled`);
    qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
  };
 
  const handleApproveSequence = async (seq: Sequence, _idx: number) => {
    const draft = seqDrafts[seq.id];
    try {
      await http.put(`/api/v1/sequences/${seq.id}`, {
        subjectLine: draft?.subjectLine ?? seq.subjectLine,
        bodyCopy: draft?.bodyCopy ?? seq.bodyCopy,
        status: "QaPassed",
      });
      toast.success("Sequence approved");
      qc.invalidateQueries({ queryKey: ["sequences", selectedId] });
    } catch { toast.error("Approve failed"); }
  };
 
  /* ── Collaterals ── */
  const [collateralDialog, setCollateralDialog] = useState(false);
  const [collForm, setCollForm] = useState({ name: "", type: "case_study", url: "", content: "", description: "" });
  const [linkCollateralOpen, setLinkCollateralOpen] = useState(false);
  const [linkCollateralId, setLinkCollateralId] = useState("");
  const [campaignCollateralLinks, setCampaignCollateralLinks] = useState<{ linkId: string; collateralId: string; }[]>([]);
 
  // Seed collateral link state from the API whenever the campaign detail opens
  // or the collateral-links query result changes (e.g. after a link/unlink).
  useEffect(() => {
    const links = collateralLinksQ.data ?? [];
    if (links.length > 0) {
      setCampaignCollateralLinks(links.map((l) => ({ linkId: l.id, collateralId: l.collateralId })));
      setLinkedCollateralIds(new Set(links.map((l) => l.collateralId)));
    } else if (!collateralLinksQ.isFetching) {
      // Only reset to empty if we've confirmed there are no links (not still loading)
      setCampaignCollateralLinks([]);
      setLinkedCollateralIds(new Set());
    }
  }, [collateralLinksQ.data, collateralLinksQ.isFetching]);
 
  const createCollateralMut = useMutation({
    mutationFn: (body: Record<string, unknown>) => http.post<any>("/api/v1/collaterals", body),
    onSuccess: async (data) => {
      // Link the new collateral to this campaign
      try {
        const link = await http.post<any>("/api/v1/collaterals/link", { collateralId: data.id, campaignId: selectedId });
        setCampaignCollateralLinks((prev) => [...prev, { linkId: link.id ?? link.linkId, collateralId: data.id }]);
        setLinkedCollateralIds((prev) => new Set([...prev, data.id]));
      } catch { /* link failed but collateral created */ }
      toast.success("Collateral added and linked");
      qc.invalidateQueries({ queryKey: ["collaterals"] });
      qc.invalidateQueries({ queryKey: ["collateral-links", selectedId] });
      setCollateralDialog(false);
      setCollForm({ name: "", type: "case_study", url: "", content: "", description: "" });
    },
    onError: () => toast.error("Failed to add collateral"),
  });
 
  const handleLinkCollateral = async () => {
    if (!linkCollateralId) { toast.error("Select a collateral to link"); return; }
    try {
      const link = await http.post<any>("/api/v1/collaterals/link", { collateralId: linkCollateralId, campaignId: selectedId });
      setCampaignCollateralLinks((prev) => [...prev, { linkId: link.id ?? link.linkId, collateralId: linkCollateralId }]);
      setLinkedCollateralIds((prev) => new Set([...prev, linkCollateralId]));
      toast.success("Collateral linked");
      qc.invalidateQueries({ queryKey: ["collateral-links", selectedId] });
      setLinkCollateralOpen(false); setLinkCollateralId("");
    } catch { toast.error("Link failed"); }
  };
 
  const handleUnlinkCollateral = async (collateralId: string) => {
    const link = campaignCollateralLinks.find((l) => l.collateralId === collateralId);
    if (!link) { toast.error("Link not found"); return; }
    try {
      await http.delete(`/api/v1/collaterals/link/${link.linkId}`);
      setCampaignCollateralLinks((prev) => prev.filter((l) => l.linkId !== link.linkId));
      setLinkedCollateralIds((prev) => { const s = new Set(prev); s.delete(collateralId); return s; });
      toast.success("Collateral unlinked");
      qc.invalidateQueries({ queryKey: ["collateral-links", selectedId] });
    } catch { toast.error("Unlink failed"); }
  };
 
  const linkedCollaterals = collateralLibrary.filter((c) => linkedCollateralIds.has(c.id));
 
  /* ── MailBridge ── */
  const [mbDialog, setMbDialog] = useState(false);
  const [mbForm, setMbForm] = useState({ name: "", baseUrl: "", provider: "gmail", fromEmail: "", fromName: "" });
 
  const createMbMut = useMutation({
    mutationFn: (body: Record<string, unknown>) => http.post("/api/v1/mailbridge/config", body),
    onSuccess: () => {
      toast.success("MailBridge connection saved");
      qc.invalidateQueries({ queryKey: ["mailbridge-configs"] });
      setMbDialog(false);
      setMbForm({ name: "", baseUrl: "", provider: "gmail", fromEmail: "", fromName: "" });
    },
    onError: () => toast.error("Failed to save MailBridge connection"),
  });
 
  const deleteMbMut = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/mailbridge/config/${id}`),
    onSuccess: () => {
      toast.success("Connection removed");
      qc.invalidateQueries({ queryKey: ["mailbridge-configs"] });
    },
    onError: () => toast.error("Delete failed"),
  });
 
  const handleTestMb = async (cfg: MailBridgeConfig) => {
    try {
      const res = await fetch(`${cfg.baseUrl}/docs`);
      if (res.ok) toast.success(`Connected to MailBridge at ${cfg.baseUrl}`);
      else toast.error(`MailBridge returned status ${res.status}`);
    } catch { toast.error(`Cannot reach MailBridge at ${cfg.baseUrl}`); }
  };
 
  /* ── Compliance inline save ── */
  const handleComplianceUpdate = async (patch: Record<string, unknown>) => {
    try {
      await http.put(`/api/v1/campaigns/${selectedId}`, patch);
      toast.success("Saved");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    } catch { toast.error("Save failed"); }
  };
 
  /* ── Reply categorization ── */
  const [replyText, setReplyText] = useState("");
  const [replyCategorizing, setReplyCategorizing] = useState(false);
  const [replyResult, setReplyResult] = useState<any>(null);
 
  const handleCategorizeReply = async () => {
    if (!replyText.trim()) return;
    setReplyCategorizing(true); setReplyResult(null);
    try {
      // Step 1: find a sequence+prospect pair to attach the draft to.
      // Prefer a Replied sequence; fall back to any sequence with a known prospect.
      const repliedSeq = sequences.find((s) => s.status === "Replied");
      const anySeq = repliedSeq ?? sequences[0];
      const prospectId = anySeq?.prospectId ?? campaignProspects[0]?.prospectId ?? null;
 
      if (!anySeq || !prospectId) {
        toast.error("Add prospects and generate sequences first, then paste a reply to categorize.");
        setReplyCategorizing(false);
        return;
      }
 
      // Step 2: create a ReplyDraft row with the required fields.
      // ReplyDraftCreate requires: sequenceId, prospectId, originalReply.
      const draft = await http.post<any>("/api/v1/reply-drafts", {
        sequenceId: anySeq.id,
        prospectId,
        originalReply: replyText,  // correct field name (not replyText)
        category: "other",         // will be overwritten by categorize call below
      });
 
      // Step 3: call the LLM categorize endpoint on the new draft.
      const result = await http.post<any>(`/api/v1/reply-drafts/${draft.id}/reply-categorize`, {
        originalReply: replyText,
      });
 
      setReplyResult(result);
      toast.success(`Categorized as: ${result.category ?? "unknown"}`);
    } catch (err: any) {
      const msg = err?.response?.data?.message ?? err?.message ?? "Categorization failed";
      toast.error(msg);
    }
    setReplyCategorizing(false);
  };
 
  /* ── Navigate to detail ── */
  const openDetail = (id: string) => {
    setSelectedId(id);
    setView("detail");
    setDetailTab("prospects");
    setSeqDrafts({});
  };
 
  const goBack = () => { setView("list"); setSelectedId(""); setSequences([]); };
 
  // local sequences state for inline editing (separate from queryCache)
  const [localSeqs, setLocalSeqs] = useState<Sequence[]>([]);
  useEffect(() => { setLocalSeqs(sequences); }, [sequences]);
 
  const setSequences = (s: Sequence[]) => setLocalSeqs(s);
  const displaySeqs = localSeqs.length > 0 ? localSeqs : sequences;
 
  // ── Tab pagination ────────────────────────────────────────────────────────
  const prospectsPagination = usePagination({ items: campaignProspects, initialPageSize: 25 });
  const seqsPagination = usePagination({ items: displaySeqs, initialPageSize: 20 });
  // Reset both paginations when the selected campaign changes.
  useEffect(() => {
    prospectsPagination.reset();
    seqsPagination.reset();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);
 
  if (campaignsQ.isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader title="Campaigns" description="" />
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 w-full" />)}
      </div>
    );
  }
 
  /* ═══════════════════════════════════════════════════════ RENDER ══════════ */
  return (
    <div className="space-y-5">
      {view === "list" ? (
        <>
          {/* ── List header ── */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">Campaigns</h3>
              <p className="text-sm text-muted-foreground">Define your outreach, manage prospects, and send AI-generated sequences</p>
            </div>
            <div className="flex gap-2">
              {/* C-11: Export CSV */}
              <Button variant="outline" size="sm" onClick={() => exportToCsv(campaigns.map((c) => ({ name: c.name, description: c.description ?? "", status: c.status, framework: c.framework ?? "", senderRole: c.senderRole ?? "", senderCompany: c.senderCompany ?? "", createdAt: c.createdAt })), `campaigns-${new Date().toISOString().split("T")[0]}`)}>
                <FileDown className="h-4 w-4 mr-2" /> Export CSV
              </Button>
              <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4 mr-2" /> New Campaign</Button>
            </div>
          </div>
 
          {/* ── Campaign card grid ── */}
          {campaigns.length === 0 ? (
            <EmptyState title="No Campaigns Yet" description="Create a campaign to define your sender identity, link prospects, and send AI-generated email sequences." />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {campaigns.map((c) => (
                <Card
                  key={c.id}
                  className="cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => openDetail(c.id)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm line-clamp-1">{c.name}</CardTitle>
                      {/* C-12: Status badge with colour */}
                      <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", (CAMPAIGN_STATUS_META[c.status] ?? CAMPAIGN_STATUS_META.draft).cls)}>
                        {(CAMPAIGN_STATUS_META[c.status] ?? { label: c.status }).label}
                      </span>
                    </div>
                    {c.description && <CardDescription className="text-xs line-clamp-2">{c.description}</CardDescription>}
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 text-xs text-muted-foreground">
                      <div className="flex items-center justify-between">
                        <span>Framework</span>
                        <span className="font-medium text-foreground">{FRAMEWORK_NAMES[c.framework ?? ""] ?? c.framework ?? "Not set"}</span>
                      </div>
                      {c.icpProfile && (
                        <div className="flex items-center justify-between">
                          <span>ICP</span>
                          <span className="font-medium text-foreground">{c.icpProfile.name}</span>
                        </div>
                      )}
                      {c.senderOffer && (
                        <div className="flex items-center justify-between">
                          <span>Offer</span>
                          <span className="font-medium text-foreground truncate max-w-[150px]">{c.senderOffer}</span>
                        </div>
                      )}
                      {/* C-13: _count badges */}
                      {c._count && (
                        <div className="flex items-center gap-4 pt-2 border-t border-border">
                          <span><Users className="h-3 w-3 inline mr-1" />{c._count.prospects}</span>
                          <span><Mail className="h-3 w-3 inline mr-1" />{c._count.sequences}</span>
                          <span><Paperclip className="h-3 w-3 inline mr-1" />{c._count.collaterals}</span>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {/* ══════════════════════ DETAIL VIEW ══════════════════════ */}
          {/* Back + header row */}
          <div className="flex items-center gap-3 flex-wrap">
            <Button variant="ghost" size="sm" onClick={() => { goBack(); }}>
              <ArrowLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            <div className="flex-1 min-w-0">
              <h3 className="text-lg font-semibold truncate">{selectedCampaign?.name}</h3>
              <p className="text-sm text-muted-foreground truncate">{selectedCampaign?.description ?? "No description"}</p>
            </div>
            <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", (CAMPAIGN_STATUS_META[selectedCampaign?.status ?? "draft"] ?? CAMPAIGN_STATUS_META.draft).cls)}>
              {(CAMPAIGN_STATUS_META[selectedCampaign?.status ?? "draft"] ?? { label: selectedCampaign?.status }).label}
            </span>
            <Select value={selectedCampaign?.status ?? "draft"} onValueChange={(v) => handleStatusChange(selectedId, v)}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="paused">Paused</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={() => selectedCampaign && openEdit(selectedCampaign)}><Edit3 className="h-3 w-3 mr-1" /> Edit</Button>
            <Button variant="outline" size="sm" onClick={() => cloneMut.mutate(selectedId)} disabled={cloneMut.isPending}>
              {cloneMut.isPending ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Copy className="h-3 w-3 mr-1" />} Clone
            </Button>
            <Button variant="ghost" size="sm" className="text-destructive" onClick={() => selectedCampaign && setDeleteTarget(selectedCampaign)}>
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
 
          {/* Sender identity card */}
          {selectedCampaign?.senderOffer && (
            <Card className="border-primary/20 bg-primary/5">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Briefcase className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                  <div className="space-y-1 text-sm flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium">{selectedCampaign.senderRole ?? "Sender"}</span>
                      <span className="text-muted-foreground">at</span>
                      <span className="font-medium">{selectedCampaign.senderCompany ?? "Company"}</span>
                    </div>
                    <p className="text-muted-foreground"><b>Offer:</b> {selectedCampaign.senderOffer}</p>
                    {selectedCampaign.proofMetric && <p className="text-muted-foreground"><b>Proof:</b> {selectedCampaign.proofMetric}</p>}
                    {selectedCampaign.senderProduct && <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{selectedCampaign.senderProduct}</p>}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
 
          {/* ── 6-tab detail ── */}
          <Tabs value={detailTab} onValueChange={setDetailTab}>
            <TabsList className="flex-wrap">
              <TabsTrigger value="prospects"><Users className="h-3 w-3 mr-1" /> Prospects ({campaignProspects.length})</TabsTrigger>
              <TabsTrigger value="sequences"><Mail className="h-3 w-3 mr-1" /> Sequences ({displaySeqs.length})</TabsTrigger>
              <TabsTrigger value="collaterals"><Paperclip className="h-3 w-3 mr-1" /> Collaterals ({linkedCollaterals.length})</TabsTrigger>
              <TabsTrigger value="mailbridge"><Send className="h-3 w-3 mr-1" /> Email Sending</TabsTrigger>
              <TabsTrigger value="compliance"><ShieldCheck className="h-3 w-3 mr-1" /> Compliance</TabsTrigger>
              <TabsTrigger value="tools"><Wand2 className="h-3 w-3 mr-1" /> Tools</TabsTrigger>
            </TabsList>
 
            {/* ══ C-3: PROSPECTS TAB ══ */}
            <TabsContent value="prospects" className="space-y-4">
              {/* <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">{campaignProspects.length} prospects linked</p>
                <Button size="sm" onClick={() => setAddProspectOpen(true)}><Plus className="h-3 w-3 mr-1" /> Add Prospects</Button>
              </div> */}
              {campaignProspects.length === 0 ? (
                <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No prospects added yet. Click "Add Prospects" to select from your list.</CardContent></Card>
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <ScrollArea className="max-h-[50vh]">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50 sticky top-0">
                          <tr>
                            <th className="text-left p-3 font-medium">Name</th>
                            <th className="text-left p-3 font-medium hidden sm:table-cell">Company</th>
                            <th className="text-left p-3 font-medium hidden md:table-cell">Title</th>
                            <th className="text-left p-3 font-medium">Status</th>
                            <th className="text-left p-3 font-medium">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {prospectsPagination.pageItems.map((cp) => (
                            <tr key={cp.id} className="border-t">
                              <td className="p-3 font-medium">{cp.prospect?.firstName} {cp.prospect?.lastName}</td>
                              <td className="p-3 hidden sm:table-cell">{cp.prospect?.company ?? "—"}</td>
                              <td className="p-3 hidden md:table-cell">{cp.prospect?.title ?? "—"}</td>
                              <td className="p-3"><Badge variant="outline" className="text-xs">{cp.status}</Badge></td>
                              <td className="p-3">
                                <Button size="sm" variant="ghost" className="text-destructive h-7" onClick={() => handleRemoveProspect(cp.prospectId)}>
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </ScrollArea>
                    <Pagination
                      page={prospectsPagination.page}
                      pageSize={prospectsPagination.pageSize}
                      total={prospectsPagination.total}
                      onPageChange={prospectsPagination.setPage}
                      onPageSizeChange={prospectsPagination.setPageSize}
                      pageSizeOptions={[10, 25, 50, 100]}
                    />
                  </CardContent>
                </Card>
              )}
 
              {/* Add Prospects Dialog */}
              <Dialog open={addProspectOpen} onOpenChange={setAddProspectOpen}>
                <DialogHeader>
                  <DialogTitle>Add Prospects to Campaign</DialogTitle>
                  <DialogDescription>Search and select prospects to link</DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <Input placeholder="Search by name, company, or title…" value={prospectSearch} onChange={(e) => setProspectSearch(e.target.value)} />
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{addProspectIds.size} selected</span>
                    {addProspectIds.size > 0 && <Button size="sm" variant="ghost" onClick={() => setAddProspectIds(new Set())}>Clear</Button>}
                  </div>
                  <ScrollArea className="max-h-64">
                    {availableProspects.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-4">No prospects available.</p>
                    ) : (
                      <div className="space-y-1">
                        {availableProspects.map((p) => (
                          <button
                            key={p.id}
                            onClick={() => {
                              const next = new Set(addProspectIds);
                              if (next.has(p.id)) next.delete(p.id); else next.add(p.id);
                              setAddProspectIds(next);
                            }}
                            className={cn("w-full flex items-center gap-3 p-2 rounded text-left text-sm hover:bg-accent transition-colors", addProspectIds.has(p.id) && "bg-primary/10")}
                          >
                            <div className={cn("h-4 w-4 rounded border flex items-center justify-center shrink-0", addProspectIds.has(p.id) ? "bg-primary border-primary" : "border-border")}>
                              {addProspectIds.has(p.id) && <Check className="h-3 w-3 text-primary-foreground" />}
                            </div>
                            <span className="font-medium">{p.firstName} {p.lastName}</span>
                            <span className="text-muted-foreground truncate">{p.company ?? ""}{p.title ? ` — ${p.title}` : ""}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </ScrollArea>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => { setAddProspectOpen(false); setAddProspectIds(new Set()); }}>Cancel</Button>
                  <Button onClick={handleAddProspects} disabled={addProspectIds.size === 0 || linkProspectMut.isPending}>
                    {linkProspectMut.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                    Add {addProspectIds.size} Prospects
                  </Button>
                </DialogFooter>
              </Dialog>
            </TabsContent>
 
            {/* ══ C-4: SEQUENCES TAB ══ */}
            <TabsContent value="sequences" className="space-y-4">
              {/* Generation controls */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Framework</Label>
                      <Select value={seqFramework} onValueChange={setSeqFramework}>
                        <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Object.entries(FRAMEWORK_NAMES).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <Button onClick={handleGenerateSequences} disabled={generating || campaignProspects.length === 0}>
                      {generating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Layers className="h-4 w-4 mr-2" />}
                      {generating ? "Generating…" : "Generate Sequences"}
                    </Button>
                    {displaySeqs.some((s) => s.status === "QaPassed") && (
                      <>
                        <Button variant="outline" onClick={handleSendAllApproved} disabled={sendingId === "bulk"}>
                          {sendingId === "bulk" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}
                          Send All Approved
                        </Button>
                        <Button variant="outline" onClick={handleScheduleCampaign}>
                          <CalendarClock className="h-4 w-4 mr-2" /> Schedule Campaign
                        </Button>
                      </>
                    )}
                  </div>
                  {campaignProspects.length === 0 && (
                    <p className="text-xs text-amber-600 mt-2">Add prospects to the campaign first before generating sequences.</p>
                  )}
                </CardContent>
              </Card>
 
              {/* Sequence timeline */}
              {displaySeqs.length === 0 ? (
                <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">Select prospects then generate sequences to see emails here.</CardContent></Card>
              ) : (
                <div className="relative">
                  <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />
                  {seqsPagination.pageItems.map((seq, i) => {
                    const draft = seqDrafts[seq.id];
                    const subject = draft?.subjectLine ?? seq.subjectLine ?? "";
                    const body = draft?.bodyCopy ?? seq.bodyCopy ?? "";
                    return (
                      <div key={seq.id} className="relative pl-14 pb-6">
                        <div className="absolute left-4 h-5 w-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold shrink-0">
                          {seq.touchNumber}
                        </div>
                        <Card className={cn(seq.status === "Sent" && "border-blue-200", seq.status === "QaPassed" && "border-emerald-200")}>
                          <CardHeader className="pb-2">
                            <div className="flex items-center justify-between flex-wrap gap-2">
                              <div>
                                <CardTitle className="text-sm">Touch {seq.touchNumber}: {seq.angle.replace(/([A-Z])/g, " $1").trim()}</CardTitle>
                                <CardDescription className="text-xs">Day {seq.sendDay}</CardDescription>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className={cn("text-xs px-2 py-0.5 rounded-full", SEQ_STATUS_COLORS[seq.status] ?? "bg-gray-100 text-gray-600")}>{seq.status}</span>
                                {seq.status === "QaPassed" && (
                                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleSendEmail(seq.id)} disabled={sendingId === seq.id}>
                                    {sendingId === seq.id ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Send className="h-3 w-3 mr-1" />} Send
                                  </Button>
                                )}
                              </div>
                            </div>
                          </CardHeader>
                          <CardContent className="space-y-2">
                            <Input
                              value={subject}
                              onChange={(e) => setSeqDrafts((prev) => ({ ...prev, [seq.id]: { subjectLine: e.target.value, bodyCopy: prev[seq.id]?.bodyCopy ?? body } }))}
                              placeholder="Subject line"
                              className="text-sm"
                            />
                            <Textarea
                              value={body}
                              onChange={(e) => setSeqDrafts((prev) => ({ ...prev, [seq.id]: { subjectLine: prev[seq.id]?.subjectLine ?? subject, bodyCopy: e.target.value } }))}
                              rows={5}
                              className="text-sm font-mono"
                            />
                            <div className="flex justify-end gap-2">
                              <Button size="sm" variant="outline" className="h-7" onClick={() => handleApproveSequence(seq, i)}>
                                <CheckCircle2 className="h-3 w-3 mr-1" /> Approve
                              </Button>
                              <Button size="sm" variant="ghost" className="h-7" onClick={() => navigator.clipboard.writeText(body).then(() => toast.success("Copied"))}>
                                <Copy className="h-3 w-3 mr-1" /> Copy
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      </div>
                    );
                  })}
                  <Pagination
                    page={seqsPagination.page}
                    pageSize={seqsPagination.pageSize}
                    total={seqsPagination.total}
                    onPageChange={seqsPagination.setPage}
                    onPageSizeChange={seqsPagination.setPageSize}
                    pageSizeOptions={[10, 20, 50]}
                  />
                </div>
              )}
            </TabsContent>
 
            {/* ══ C-5: COLLATERALS TAB ══ */}
            <TabsContent value="collaterals" className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">Case studies, decks, and other assets linked to this campaign</p>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setLinkCollateralOpen(true)}><Link2 className="h-3 w-3 mr-1" /> Link from Library</Button>
                  <Button size="sm" onClick={() => setCollateralDialog(true)}><Plus className="h-3 w-3 mr-1" /> Add New</Button>
                </div>
              </div>
              {linkedCollaterals.length === 0 ? (
                <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No collaterals linked. Add from your library or create a new one.</CardContent></Card>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {linkedCollaterals.map((c) => (
                    <Card key={c.id}>
                      <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-sm flex items-center gap-2"><Paperclip className="h-3 w-3" /> {c.name}</CardTitle>
                          <Button size="sm" variant="ghost" className="text-destructive h-7" onClick={() => handleUnlinkCollateral(c.id)}><Trash2 className="h-3 w-3" /></Button>
                        </div>
                        <Badge variant="outline" className="text-xs w-fit">{c.type.replace(/_/g, " ")}</Badge>
                      </CardHeader>
                      <CardContent>
                        {c.description && <p className="text-xs text-muted-foreground mb-2">{c.description}</p>}
                        {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline flex items-center gap-1"><Link2 className="h-3 w-3" /> {c.url}</a>}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
 
              {/* Add collateral dialog */}
              <Dialog open={collateralDialog} onOpenChange={setCollateralDialog}>
                <DialogHeader>
                  <DialogTitle>Add Campaign Collateral</DialogTitle>
                  <DialogDescription>Creates a new collateral in the library and links it to this campaign</DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-1"><Label className="text-xs">Name *</Label><Input placeholder="e.g. Q3 ROI Case Study" value={collForm.name} onChange={(e) => setCollForm((f) => ({ ...f, name: e.target.value }))} /></div>
                  <div className="space-y-1">
                    <Label className="text-xs">Type</Label>
                    <Select value={collForm.type} onValueChange={(v) => setCollForm((f) => ({ ...f, type: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {["case_study","deck","one_pager","testimonial","whitepaper","demo_link","video","other"].map((t) => <SelectItem key={t} value={t}>{t.replace(/_/g, " ")}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1"><Label className="text-xs">URL</Label><Input placeholder="https://…" value={collForm.url} onChange={(e) => setCollForm((f) => ({ ...f, url: e.target.value }))} /></div>
                  <div className="space-y-1"><Label className="text-xs">Description</Label><Input placeholder="Brief description" value={collForm.description} onChange={(e) => setCollForm((f) => ({ ...f, description: e.target.value }))} /></div>
                  <div className="space-y-1"><Label className="text-xs">Brand Content</Label><Textarea placeholder="Paste key quotes, talking points, or proof text…" value={collForm.content} onChange={(e) => setCollForm((f) => ({ ...f, content: e.target.value }))} rows={3} /></div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCollateralDialog(false)}>Cancel</Button>
                  <Button onClick={() => { if (!collForm.name) { toast.error("Name required"); return; } createCollateralMut.mutate({ name: collForm.name, type: collForm.type, url: collForm.url || null, content: collForm.content || null, description: collForm.description || null }); }} disabled={createCollateralMut.isPending}>
                    {createCollateralMut.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null} Add Collateral
                  </Button>
                </DialogFooter>
              </Dialog>
 
              {/* Link from library dialog */}
              <Dialog open={linkCollateralOpen} onOpenChange={setLinkCollateralOpen}>
                <DialogHeader>
                  <DialogTitle>Link Collateral from Library</DialogTitle>
                  <DialogDescription>Select an existing collateral to attach to this campaign</DialogDescription>
                </DialogHeader>
                <div className="py-4 space-y-2">
                  <Label className="text-xs">Collateral</Label>
                  <Select value={linkCollateralId} onValueChange={setLinkCollateralId}>
                    <SelectTrigger><SelectValue placeholder="Select collateral…" /></SelectTrigger>
                    <SelectContent>
                      {collateralLibrary.filter((c) => !linkedCollateralIds.has(c.id)).map((c) => <SelectItem key={c.id} value={c.id}>{c.name} ({c.type})</SelectItem>)}
                    </SelectContent>
                  </Select>
                  {collateralLibrary.filter((c) => !linkedCollateralIds.has(c.id)).length === 0 && (
                    <p className="text-xs text-muted-foreground">All library collaterals are already linked to this campaign.</p>
                  )}
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => { setLinkCollateralOpen(false); setLinkCollateralId(""); }}>Cancel</Button>
                  <Button onClick={handleLinkCollateral} disabled={!linkCollateralId}>Link</Button>
                </DialogFooter>
              </Dialog>
            </TabsContent>
 
            {/* ══ C-6: EMAIL SENDING TAB ══ */}
            <TabsContent value="mailbridge" className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Connect to your MailBridge server for email delivery and tracking</p>
                  <p className="text-xs text-muted-foreground mt-1">MailBridge handles sending, bounce suppression, read receipts, and follow-up sequences</p>
                </div>
                <Button size="sm" onClick={() => setMbDialog(true)}><Plus className="h-3 w-3 mr-1" /> Add Connection</Button>
              </div>
              {mailbridgeQ.isLoading ? <Skeleton className="h-20 w-full" /> : mbConfigs.length === 0 ? (
                <Card><CardContent className="py-8 text-center">
                  <Send className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground mb-1">No MailBridge connections</p>
                  <p className="text-xs text-muted-foreground">Add your MailBridge server URL to start sending emails</p>
                </CardContent></Card>
              ) : (
                <div className="space-y-3">
                  {mbConfigs.map((c) => (
                    <Card key={c.id}><CardContent className="p-4 flex items-center justify-between">
                      <div className="space-y-0.5">
                        <p className="text-sm font-medium">{c.name}</p>
                        <p className="text-xs text-muted-foreground">{c.baseUrl} — {c.fromEmail}</p>
                        <p className="text-xs text-muted-foreground capitalize">{c.provider}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={c.isActive ? "default" : "secondary"} className="text-xs">{c.isActive ? "Active" : "Inactive"}</Badge>
                        <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleTestMb(c)}>Test</Button>
                        <Button size="sm" variant="ghost" className="text-destructive h-7" onClick={() => deleteMbMut.mutate(c.id)} disabled={deleteMbMut.isPending}><Trash2 className="h-3 w-3" /></Button>
                      </div>
                    </CardContent></Card>
                  ))}
                </div>
              )}
 
              {/* Add MailBridge dialog */}
              <Dialog open={mbDialog} onOpenChange={setMbDialog}>
                <DialogHeader>
                  <DialogTitle>Add MailBridge Connection</DialogTitle>
                  <DialogDescription>Configure your MailBridge server for email delivery</DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-1"><Label className="text-xs">Display Name *</Label><Input placeholder="e.g. Gmail via MailBridge" value={mbForm.name} onChange={(e) => setMbForm((f) => ({ ...f, name: e.target.value }))} /></div>
                  <div className="space-y-1">
                    <Label className="text-xs">MailBridge Server URL *</Label>
                    <Input placeholder="e.g. http://172.93.49.106:9000" value={mbForm.baseUrl} onChange={(e) => setMbForm((f) => ({ ...f, baseUrl: e.target.value }))} />
                    <p className="text-xs text-muted-foreground">Base URL of your MailBridge FastAPI server (Swagger at /docs)</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Email Provider</Label>
                    <Select value={mbForm.provider} onValueChange={(v) => setMbForm((f) => ({ ...f, provider: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="gmail">Gmail (Google Workspace)</SelectItem>
                        <SelectItem value="outlook">Outlook (Microsoft 365)</SelectItem>
                        <SelectItem value="smtp">Generic SMTP</SelectItem>
                        <SelectItem value="sendgrid">SendGrid</SelectItem>
                        <SelectItem value="ses">Amazon SES</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1"><Label className="text-xs">From Email *</Label><Input placeholder="john@myco.com" value={mbForm.fromEmail} onChange={(e) => setMbForm((f) => ({ ...f, fromEmail: e.target.value }))} /></div>
                    <div className="space-y-1"><Label className="text-xs">From Name</Label><Input placeholder="John Smith" value={mbForm.fromName} onChange={(e) => setMbForm((f) => ({ ...f, fromName: e.target.value }))} /></div>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setMbDialog(false)}>Cancel</Button>
                  <Button onClick={() => {
                    if (!mbForm.name || !mbForm.baseUrl || !mbForm.fromEmail) { toast.error("Name, URL, and From Email are required"); return; }
                    createMbMut.mutate({ name: mbForm.name, baseUrl: mbForm.baseUrl, provider: mbForm.provider, fromEmail: mbForm.fromEmail, fromName: mbForm.fromName || null });
                  }} disabled={createMbMut.isPending}>
                    {createMbMut.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null} Save Connection
                  </Button>
                </DialogFooter>
              </Dialog>
            </TabsContent>
 
            {/* ══ C-7: COMPLIANCE TAB ══ */}
            <TabsContent value="compliance" className="space-y-4">
              <div className="p-3 rounded-lg bg-muted text-xs text-muted-foreground">
                <b>CAN-SPAM Act</b> requires: (1) a physical mailing address, (2) a clear unsubscribe mechanism, (3) no deceptive subject lines. <b>GDPR</b> requires: lawful basis, right to erasure, and data minimization.
              </div>
 
              <Card>
                <CardHeader className="pb-3"><CardTitle className="text-sm">CAN-SPAM / GDPR Settings</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Auto-append Compliance Footer</p>
                      <p className="text-xs text-muted-foreground">Adds physical address + unsubscribe link to every email</p>
                    </div>
                    <Switch
                      checked={!!selectedCampaign?.complianceFooter}
                      onCheckedChange={(v) => handleComplianceUpdate({ complianceFooter: v })}
                    />
                  </div>
                  <Separator />
                  <div className="space-y-1">
                    <Label className="text-xs">Physical Mailing Address</Label>
                    <Input
                      placeholder="123 Business St, Suite 100, San Francisco, CA 94105"
                      defaultValue={selectedCampaign?.physicalAddress ?? ""}
                      onBlur={(e) => handleComplianceUpdate({ physicalAddress: e.target.value })}
                    />
                    <p className="text-xs text-muted-foreground">Required by CAN-SPAM. Appears in the footer of every email.</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Unsubscribe URL</Label>
                    <Input
                      placeholder="https://yourcompany.com/unsubscribe"
                      defaultValue={selectedCampaign?.unsubscribeUrl ?? ""}
                      onBlur={(e) => handleComplianceUpdate({ unsubscribeUrl: e.target.value })}
                    />
                    <p className="text-xs text-muted-foreground">If not set, "Reply STOP to unsubscribe" will be used.</p>
                  </div>
                </CardContent>
              </Card>
 
              {/* Webhook URL card */}
              <Card>
                <CardHeader className="pb-3"><CardTitle className="text-sm flex items-center gap-2"><Webhook className="h-4 w-4" /> MailBridge Webhook</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    Configure MailBridge to push real-time events (opens, bounces, replies) to this platform. Add this URL to your MailBridge <code className="bg-muted px-1 rounded">mailbridge.yaml</code>:
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 bg-muted px-3 py-2 rounded-lg text-xs truncate">{typeof window !== "undefined" ? `${window.location.origin}/api/v1/mailbridge/webhook` : "/api/v1/mailbridge/webhook"}</code>
                    <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(`${typeof window !== "undefined" ? window.location.origin : ""}/api/v1/mailbridge/webhook`); toast.success("Webhook URL copied"); }}>
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">Events: delivery.opened, delivery.bounced, email.replied, email.received</p>
                </CardContent>
              </Card>
            </TabsContent>
 
            {/* ══ C-8: TOOLS TAB ══ */}
            <TabsContent value="tools" className="space-y-4">
              <Card>
                <CardHeader className="pb-3"><CardTitle className="text-sm flex items-center gap-2"><MessageCircleReply className="h-4 w-4" /> AI Reply Categorization</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-xs text-muted-foreground">
                    Paste a prospect reply to categorize it: Interested, Not Interested, Out of Office, Needs Info, Meeting Request, Counter Proposal, Positive Signal, Neutral.
                  </p>
                  <Textarea placeholder="Paste a prospect's reply email here…" value={replyText} onChange={(e) => setReplyText(e.target.value)} rows={4} />
                  <Button onClick={handleCategorizeReply} disabled={replyCategorizing || !replyText.trim()}>
                    {replyCategorizing ? <Loader2 className="h-3 w-3 mr-2 animate-spin" /> : <MessageCircleReply className="h-3 w-3 mr-2" />}
                    {replyCategorizing ? "Categorizing…" : "Categorize Reply"}
                  </Button>
                  {replyResult && (
                    <Card className={cn(
                      "border",
                      (replyResult.category === "interested" || replyResult.category === "meeting_request") ? "border-emerald-200 bg-emerald-50"
                        : replyResult.category === "not_interested" ? "border-red-200 bg-red-50"
                        : "border-blue-100 bg-blue-50"
                    )}>
                      <CardContent className="p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <Badge className={cn("text-xs",
                            (replyResult.category === "interested" || replyResult.category === "meeting_request") ? "bg-emerald-100 text-emerald-800"
                              : replyResult.category === "not_interested" ? "bg-red-100 text-red-800"
                              : "bg-blue-100 text-blue-800"
                          )}>{(replyResult.category ?? "unknown").replace(/_/g, " ")}</Badge>
                          {replyResult.confidence != null && (
                            <span className="text-xs text-muted-foreground">Confidence: {(replyResult.confidence * 100).toFixed(0)}%</span>
                          )}
                        </div>
                        {replyResult.summary && <p className="text-xs"><b>Summary:</b> {replyResult.summary}</p>}
                        {replyResult.suggestedAction && <p className="text-xs"><b>Suggested Action:</b> {replyResult.suggestedAction}</p>}
                      </CardContent>
                    </Card>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
 
      {/* ══════════════ C-1: CREATE / EDIT DIALOG ══════════════ */}
      <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
        <DialogHeader>
          <DialogTitle>{editingId ? "Edit Campaign" : "Create Campaign"}</DialogTitle>
          <DialogDescription>Define your campaign, sender identity, and product/service for AI-powered emails</DialogDescription>
        </DialogHeader>
        <Tabs value={formTab} onValueChange={setFormTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="basics">Basics</TabsTrigger>
            <TabsTrigger value="sender">Sender &amp; Product</TabsTrigger>
            <TabsTrigger value="config">Configuration</TabsTrigger>
          </TabsList>
          <ScrollArea className="max-h-[60vh]">
            <TabsContent value="basics" className="space-y-4 py-4 px-1">
              <div className="space-y-1"><Label className="text-xs">Campaign Name *</Label><Input placeholder="e.g. Q3 SaaS CTO Outreach" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></div>
              <div className="space-y-1"><Label className="text-xs">Description / Goal</Label><Textarea placeholder="What is this campaign trying to achieve?" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={3} /></div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs">Status</Label>
                  <Select value={form.status} onValueChange={(v) => setForm((f) => ({ ...f, status: v }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="paused">Paused</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Framework</Label>
                  <Select value={form.framework} onValueChange={(v) => setForm((f) => ({ ...f, framework: v }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(FRAMEWORK_NAMES).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1"><Label className="text-xs">Target Audience</Label><Input placeholder="e.g. VP Engineering at Series A-B SaaS companies" value={form.targetAudience} onChange={(e) => setForm((f) => ({ ...f, targetAudience: e.target.value }))} /></div>
            </TabsContent>
 
            <TabsContent value="sender" className="space-y-4 py-4 px-1">
              <div className="p-3 rounded-lg bg-muted text-xs text-muted-foreground">
                <b>Why this matters:</b> The AI uses your sender identity and product description to write accurate, personalized emails. The more detail you provide, the better the output.
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1"><Label className="text-xs">Sender Role</Label><Input placeholder="e.g. CEO at MyCo" value={form.senderRole} onChange={(e) => setForm((f) => ({ ...f, senderRole: e.target.value }))} /></div>
                <div className="space-y-1"><Label className="text-xs">Sender Company</Label><Input placeholder="e.g. MyCo" value={form.senderCompany} onChange={(e) => setForm((f) => ({ ...f, senderCompany: e.target.value }))} /></div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1"><Label className="text-xs">Offer (Short)</Label><Input placeholder="e.g. AI lead gen platform" value={form.senderOffer} onChange={(e) => setForm((f) => ({ ...f, senderOffer: e.target.value }))} /></div>
                <div className="space-y-1"><Label className="text-xs">Proof Metric</Label><Input placeholder="e.g. 3x pipeline in 90 days" value={form.proofMetric} onChange={(e) => setForm((f) => ({ ...f, proofMetric: e.target.value }))} /></div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Product/Service Description (Detailed)</Label>
                <Textarea placeholder="We provide an AI-powered sales development platform…" value={form.senderProduct} onChange={(e) => setForm((f) => ({ ...f, senderProduct: e.target.value }))} rows={5} />
                <p className="text-xs text-muted-foreground">Key context the AI uses to understand what you sell. Be specific about features, outcomes, and differentiators.</p>
              </div>
            </TabsContent>
 
            <TabsContent value="config" className="space-y-4 py-4 px-1">
              <div className="space-y-1">
                <Label className="text-xs">ICP Profile</Label>
                <Select
                  value={form.icpProfileId}
                  onValueChange={(v) => {
                    const icp = icps.find((i) => i.id === v);
                    if (icp && !editingId) {
                      setForm((f) => ({ ...f, icpProfileId: v, senderRole: f.senderRole || icp.senderRole || "", senderCompany: f.senderCompany || icp.senderCompany || "", senderOffer: f.senderOffer || icp.senderOffer || "", proofMetric: f.proofMetric || icp.proofMetric || "" }));
                    } else {
                      setForm((f) => ({ ...f, icpProfileId: v }));
                    }
                  }}
                >
                  <SelectTrigger><SelectValue placeholder="Select ICP profile…" /></SelectTrigger>
                  <SelectContent>{icps.map((icp) => <SelectItem key={icp.id} value={icp.id}>{icp.name}</SelectItem>)}</SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">The ICP defines objections, pain points, and value props used in email generation.</p>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">LLM Model</Label>
                <p className="text-xs text-muted-foreground bg-muted rounded p-2">
                  Uses your tenant default LLM automatically. To configure LLM models, go to <b>Setup → LLM Models</b>.
                </p>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Sending Domain</Label>
                <Select value={form.domainId} onValueChange={(v) => setForm((f) => ({ ...f, domainId: v }))}>
                  <SelectTrigger><SelectValue placeholder="Select domain…" /></SelectTrigger>
                  <SelectContent>{domains.map((d) => <SelectItem key={d.id} value={d.id}>{d.domainName}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </TabsContent>
          </ScrollArea>
        </Tabs>
        <DialogFooter>
          <Button variant="outline" onClick={() => { setDialogOpen(false); resetForm(); }}>Cancel</Button>
          <Button onClick={handleSave} disabled={saveMut.isPending}>
            {saveMut.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
            {editingId ? "Update Campaign" : "Create Campaign"}
          </Button>
        </DialogFooter>
      </Dialog>
 
      {/* ══════════════ C-9: PRE-FLIGHT DIALOG ══════════════ */}
      <Dialog open={preflightOpen} onOpenChange={(o) => { setPreflightOpen(o); if (!o) { setPreflightResult(null); setPendingActivateId(""); } }}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Pre-Flight Activation Check</DialogTitle>
          <DialogDescription>Deliverability checks run before activating. Prevents domain burn before it happens.</DialogDescription>
        </DialogHeader>
        {preflightLoading ? (
          <div className="flex items-center justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
        ) : preflightResult ? (
          <div className="space-y-3 py-2">
            {preflightResult.checks?.map((c, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                {c.status === "pass" ? <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                  : c.status === "fail" ? <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 shrink-0" />
                  : <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />}
                <div>
                  <span className="font-medium">{c.name}</span>
                  <p className="text-xs text-muted-foreground">{c.detail}</p>
                </div>
              </div>
            ))}
            {(preflightResult.warnings?.length ?? 0) > 0 && (
              <div className="p-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
                <b>Warnings:</b> {preflightResult.warnings!.join(" ")}
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">Running checks…</p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => { setPreflightOpen(false); setPreflightResult(null); setPendingActivateId(""); }}>Cancel</Button>
          <Button
            onClick={confirmActivate}
            disabled={!preflightResult || !(preflightResult.passed || preflightResult.allPassed)}
          >
            {(preflightResult?.passed || preflightResult?.allPassed)
              ? <><CheckCircle2 className="h-3 w-3 mr-1" /> Activate Campaign</>
              : "Blocked — fix errors first"}
          </Button>
        </DialogFooter>
      </Dialog>
 
      {/* Delete confirm */}
      <AlertDialog open={deleteTarget !== null} onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete campaign?</AlertDialogTitle>
            <AlertDialogDescription>
              "{deleteTarget?.name}" and all its sequences will be permanently removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive hover:bg-destructive/90" onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}