// /**
//  * FlowTemplatesPage.tsx — Pre-built flow templates gallery.
//  *
//  * Fixes from previous version:
//  *  - API returns { items: [...], total: N } not a plain array → normalised here
//  *  - Backend uses snake_case (source_platforms, gate_strictness, recommended_for
//  *    as string) → mapped to frontend camelCase on receipt
//  *  - Dialog was broken (DialogClose as top-level child) → fixed structure
//  *  - Added Create Template dialog and Edit Template dialog (matching Next.js ref)
//  *  - Clone navigates to Prospecting Flows after success
//  */

// import { useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import { useNavigate } from "react-router-dom";
// import {
//   Building2,
//   CheckCircle2,
//   Copy,
//   Edit2,
//   Handshake,
//   Layers,
//   Loader2,
//   Mail,
//   Plus,
//   RefreshCw,
//   Rocket,
//   ShieldCheck,
//   Sparkles,
//   Target,
//   Trash2,
//   X,
//   Zap,
// } from "lucide-react";
// import { toast } from "sonner";

// import { http } from "@/services/apiClient";
// import { Badge } from "@/components/ui/badge";
// import { Button } from "@/components/ui/button";
// import {
//   Card,
//   CardContent,
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
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { Skeleton } from "@/components/ui/skeleton";
// import { Separator } from "@/components/ui/separator";
// import { Switch } from "@/components/ui/switch";
// import { Textarea } from "@/components/ui/textarea";
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from "@/components/ui/select";
// import { cn } from "@/lib/utils";

// // ─────────────────────────────────────────────────────────────────────────────
// // Types
// // ─────────────────────────────────────────────────────────────────────────────

// /** Raw shape from the backend (snake_case, recommended_for is a string) */
// interface TemplateRaw {
//   id: string;
//   name: string;
//   description: string;
//   source_platforms: string[];
//   enrichment_platforms: string[];
//   gate_config: Record<string, unknown>;
//   gate_strictness: "strict" | "medium" | "loose" | "moderate" | "lenient";
//   recommended_for: string;
// }

// /** Normalised frontend shape */
// interface FlowTemplate {
//   id: string;
//   name: string;
//   description: string;
//   sourcePlatforms: string[];
//   enrichmentPlatforms: string[];
//   gateConfig: {
//     requireEmail: boolean;
//     requireVerifiedEmail: boolean;
//     requireCompanySize: boolean;
//     minCompanySize: number;
//     llmScoreThreshold: number;
//     excludeDomains: string[];
//   };
//   gateStrictness: "strict" | "medium" | "loose";
//   recommendedFor: string;
// }

// /** Draft state for Create / Edit dialog */
// interface TemplateDraft {
//   name: string;
//   description: string;
//   sourcePlatforms: string[];
//   enrichmentPlatforms: string[];
//   gateStrictness: "strict" | "medium" | "loose";
//   requireEmail: boolean;
//   requireVerifiedEmail: boolean;
//   requireCompanySize: boolean;
//   minCompanySize: number;
//   llmScoreThreshold: number;
//   excludeDomains: string[];
//   recommendedFor: string;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Normalise backend → frontend
// // ─────────────────────────────────────────────────────────────────────────────

// function normaliseStrictness(raw: string): "strict" | "medium" | "loose" {
//   if (raw === "moderate") return "medium";
//   if (raw === "lenient") return "loose";
//   if (raw === "strict" || raw === "medium" || raw === "loose") return raw;
//   return "medium";
// }

// function normalise(raw: TemplateRaw): FlowTemplate {
//   const gc = (raw.gate_config ?? {}) as Record<string, unknown>;
//   return {
//     id: raw.id,
//     name: raw.name,
//     description: raw.description ?? "",
//     sourcePlatforms: Array.isArray(raw.source_platforms) ? raw.source_platforms : [],
//     enrichmentPlatforms: Array.isArray(raw.enrichment_platforms) ? raw.enrichment_platforms : [],
//     gateConfig: {
//       requireEmail: Boolean(gc.requireEmail ?? true),
//       requireVerifiedEmail: Boolean(gc.requireVerifiedEmail),
//       requireCompanySize: Boolean(gc.requireCompanySize),
//       minCompanySize: Number(gc.minCompanySize ?? 0),
//       llmScoreThreshold: Number(gc.llmScoreThreshold ?? 0),
//       excludeDomains: Array.isArray(gc.excludeDomains) ? (gc.excludeDomains as string[]) : [],
//     },
//     gateStrictness: normaliseStrictness(raw.gate_strictness ?? "medium"),
//     recommendedFor: typeof raw.recommended_for === "string" ? raw.recommended_for : "",
//   };
// }

// function extractItems(data: unknown): FlowTemplate[] {
//   if (!data) return [];
//   // Backend returns { items: [...], total: N }
//   if (typeof data === "object" && !Array.isArray(data)) {
//     const obj = data as Record<string, unknown>;
//     if (Array.isArray(obj.items)) {
//       return (obj.items as TemplateRaw[]).map(normalise);
//     }
//   }
//   // Fallback: plain array
//   if (Array.isArray(data)) {
//     return (data as TemplateRaw[]).map(normalise);
//   }
//   return [];
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Available platforms (for multi-select in Create/Edit)
// // ─────────────────────────────────────────────────────────────────────────────

// const SOURCE_PLATFORMS = [
//   { key: "ai_web_search", label: "AI Web Search" },
//   { key: "linkedin", label: "LinkedIn" },
//   { key: "apollo", label: "Apollo.io" },
//   { key: "zoominfo", label: "ZoomInfo" },
//   { key: "clearbit", label: "Clearbit" },
//   { key: "hunter", label: "Hunter.io" },
//   { key: "clay", label: "Clay" },
//   { key: "lusha", label: "Lusha" },
//   { key: "kaspr", label: "Kaspr" },
// ];

// const ENRICH_PLATFORMS = [
//   { key: "hunter", label: "Hunter.io" },
//   { key: "clearbit", label: "Clearbit" },
//   { key: "lusha", label: "Lusha" },
//   { key: "kaspr", label: "Kaspr" },
//   { key: "apollo", label: "Apollo.io" },
//   { key: "email_waterfall", label: "Email Waterfall" },
// ];

// // ─────────────────────────────────────────────────────────────────────────────
// // Visual registry (maps template id/name keywords → display metadata)
// // ─────────────────────────────────────────────────────────────────────────────

// interface TemplateMeta {
//   Icon: React.ComponentType<{ className?: string }>;
//   iconBg: string;
//   iconColor: string;
//   accent: string;
// }

// function getTemplateMeta(t: FlowTemplate): TemplateMeta {
//   const n = t.name.toLowerCase();
//   const id = t.id.toLowerCase();
//   if (n.includes("enterprise") || id.includes("enterprise") || id.includes("abm")) {
//     return {
//       Icon: Building2,
//       iconBg: "bg-violet-100",
//       iconColor: "text-violet-600",
//       accent: "border-violet-200 hover:border-violet-300",
//     };
//   }
//   if (n.includes("plg") || n.includes("volume") || n.includes("self-serve")) {
//     return {
//       Icon: Rocket,
//       iconBg: "bg-emerald-100",
//       iconColor: "text-emerald-600",
//       accent: "border-emerald-200 hover:border-emerald-300",
//     };
//   }
//   if (n.includes("partner") || n.includes("recruit")) {
//     return {
//       Icon: Handshake,
//       iconBg: "bg-amber-100",
//       iconColor: "text-amber-600",
//       accent: "border-amber-200 hover:border-amber-300",
//     };
//   }
//   return {
//     Icon: Sparkles,
//     iconBg: "bg-slate-100",
//     iconColor: "text-slate-600",
//     accent: "border-border hover:border-primary/30",
//   };
// }

// const STRICTNESS_STYLE: Record<string, { label: string; class: string }> = {
//   strict: { label: "Strict", class: "bg-red-100 text-red-700 border-red-200" },
//   medium: { label: "Medium", class: "bg-amber-100 text-amber-700 border-amber-200" },
//   loose:  { label: "Loose",  class: "bg-emerald-100 text-emerald-700 border-emerald-200" },
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // PlatformToggle — checkbox-style toggle for platform lists
// // ─────────────────────────────────────────────────────────────────────────────

// function PlatformToggle({
//   label,
//   checked,
//   onToggle,
// }: {
//   label: string;
//   checked: boolean;
//   onToggle: () => void;
// }) {
//   return (
//     <label
//       className={cn(
//         "flex items-center gap-2 cursor-pointer rounded-md border px-2.5 py-1.5 text-xs transition-colors select-none",
//         checked
//           ? "bg-primary/10 border-primary/40 text-primary font-medium"
//           : "bg-muted/30 border-muted text-muted-foreground hover:bg-muted/60",
//       )}
//     >
//       <input type="checkbox" className="sr-only" checked={checked} onChange={onToggle} />
//       {checked && <CheckCircle2 className="h-3 w-3 shrink-0" />}
//       {label}
//     </label>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // CreateEditDialog — shared dialog for both Create and Edit
// // ─────────────────────────────────────────────────────────────────────────────

// function emptyDraft(): TemplateDraft {
//   return {
//     name: "",
//     description: "",
//     sourcePlatforms: ["ai_web_search"],
//     enrichmentPlatforms: [],
//     gateStrictness: "medium",
//     requireEmail: true,
//     requireVerifiedEmail: false,
//     requireCompanySize: false,
//     minCompanySize: 0,
//     llmScoreThreshold: 0.6,
//     excludeDomains: ["gmail.com", "yahoo.com", "hotmail.com"],
//     recommendedFor: "",
//   };
// }

// function templateToDraft(t: FlowTemplate): TemplateDraft {
//   return {
//     name: t.name,
//     description: t.description,
//     sourcePlatforms: [...t.sourcePlatforms],
//     enrichmentPlatforms: [...t.enrichmentPlatforms],
//     gateStrictness: t.gateStrictness,
//     requireEmail: t.gateConfig.requireEmail,
//     requireVerifiedEmail: t.gateConfig.requireVerifiedEmail,
//     requireCompanySize: t.gateConfig.requireCompanySize,
//     minCompanySize: t.gateConfig.minCompanySize,
//     llmScoreThreshold: t.gateConfig.llmScoreThreshold,
//     excludeDomains: [...t.gateConfig.excludeDomains],
//     recommendedFor: t.recommendedFor,
//   };
// }

// function draftToPayload(draft: TemplateDraft) {
//   return {
//     name: draft.name.trim(),
//     description: draft.description.trim(),
//     source_platforms: draft.sourcePlatforms,
//     enrichment_platforms: draft.enrichmentPlatforms,
//     gate_config: {
//       requireEmail: draft.requireEmail,
//       requireVerifiedEmail: draft.requireVerifiedEmail,
//       requireCompanySize: draft.requireCompanySize,
//       minCompanySize: draft.minCompanySize,
//       llmScoreThreshold: draft.llmScoreThreshold,
//       excludeDomains: draft.excludeDomains,
//     },
//     gate_strictness: draft.gateStrictness,
//     recommended_for: draft.recommendedFor.trim(),
//   };
// }

// function CreateEditDialog({
//   open,
//   onClose,
//   initialDraft,
//   mode,
//   templateId,
//   onSuccess,
// }: {
//   open: boolean;
//   onClose: () => void;
//   initialDraft: TemplateDraft;
//   mode: "create" | "edit";
//   templateId?: string;
//   onSuccess: () => void;
// }) {
//   const [draft, setDraft] = useState<TemplateDraft>(initialDraft);
//   const [domainInput, setDomainInput] = useState("");

//   // Reset draft when dialog opens with new initial values
//   const [lastInitial, setLastInitial] = useState(initialDraft);
//   if (initialDraft !== lastInitial) {
//     setLastInitial(initialDraft);
//     setDraft(initialDraft);
//   }

//   const saveMut = useMutation({
//     mutationFn: async () => {
//       const payload = draftToPayload(draft);
//       if (mode === "create") {
//         return http.post<TemplateRaw>("/api/v1/flow-templates", payload);
//       } else {
//         return http.put<TemplateRaw>(`/api/v1/flow-templates/${templateId}`, payload);
//       }
//     },
//     onSuccess: () => {
//       toast.success(mode === "create" ? "Template created" : "Template updated");
//       onSuccess();
//       onClose();
//     },
//     onError: (err) => {
//       toast.error(mode === "create" ? "Failed to create template" : "Failed to update template", {
//         description: err instanceof Error ? err.message : "Unknown error",
//       });
//     },
//   });

//   function update(patch: Partial<TemplateDraft>) {
//     setDraft((d) => ({ ...d, ...patch }));
//   }

//   function togglePlatform(list: "sourcePlatforms" | "enrichmentPlatforms", key: string) {
//     const current = draft[list];
//     if (current.includes(key)) {
//       update({ [list]: current.filter((k) => k !== key) });
//     } else {
//       update({ [list]: [...current, key] });
//     }
//   }

//   function addDomain() {
//     const d = domainInput.trim().toLowerCase().replace(/^@/, "");
//     if (!d || draft.excludeDomains.includes(d)) { setDomainInput(""); return; }
//     update({ excludeDomains: [...draft.excludeDomains, d] });
//     setDomainInput("");
//   }

//   const isValid = draft.name.trim().length > 0 && draft.sourcePlatforms.length > 0;

//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
//       <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
//         <DialogHeader>
//           <DialogTitle>
//             {mode === "create" ? "Create New Template" : `Edit Template — ${initialDraft.name}`}
//           </DialogTitle>
//           <DialogDescription>
//             {mode === "create"
//               ? "Define a reusable prospecting flow template. Users can clone it to create a customised flow."
//               : "Update the template configuration. Existing clones are not affected."}
//           </DialogDescription>
//         </DialogHeader>

//         <div className="space-y-5 py-2">
//           {/* Basic info */}
//           <div className="grid grid-cols-1 gap-3">
//             <div className="space-y-1.5">
//               <Label>Template Name *</Label>
//               <Input
//                 value={draft.name}
//                 onChange={(e) => update({ name: e.target.value })}
//                 placeholder="e.g. Enterprise ABM Flow"
//               />
//             </div>
//             <div className="space-y-1.5">
//               <Label>Description</Label>
//               <Textarea
//                 value={draft.description}
//                 onChange={(e) => update({ description: e.target.value })}
//                 placeholder="What this template is designed for…"
//                 className="min-h-[70px] resize-none"
//               />
//             </div>
//             <div className="space-y-1.5">
//               <Label>Recommended For</Label>
//               <Input
//                 value={draft.recommendedFor}
//                 onChange={(e) => update({ recommendedFor: e.target.value })}
//                 placeholder="e.g. Fortune 500 / enterprise targets where precision > volume"
//               />
//             </div>
//           </div>

//           <Separator />

//           {/* Source platforms */}
//           <div className="space-y-2">
//             <Label className="flex items-center gap-1.5">
//               Source Platforms *
//               <span className="text-xs font-normal text-muted-foreground">(at least one required)</span>
//             </Label>
//             <div className="flex flex-wrap gap-1.5">
//               {SOURCE_PLATFORMS.map((p) => (
//                 <PlatformToggle
//                   key={p.key}
//                   label={p.label}
//                   checked={draft.sourcePlatforms.includes(p.key)}
//                   onToggle={() => togglePlatform("sourcePlatforms", p.key)}
//                 />
//               ))}
//             </div>
//           </div>

//           {/* Enrichment platforms */}
//           <div className="space-y-2">
//             <Label className="flex items-center gap-1.5">
//               Enrichment Platforms
//               <span className="text-xs font-normal text-muted-foreground">(optional)</span>
//             </Label>
//             <div className="flex flex-wrap gap-1.5">
//               {ENRICH_PLATFORMS.map((p) => (
//                 <PlatformToggle
//                   key={p.key}
//                   label={p.label}
//                   checked={draft.enrichmentPlatforms.includes(p.key)}
//                   onToggle={() => togglePlatform("enrichmentPlatforms", p.key)}
//                 />
//               ))}
//             </div>
//           </div>

//           <Separator />

//           {/* Gate strictness + gates */}
//           <div className="space-y-3">
//             <div className="flex items-center gap-4">
//               <Label>Gate Strictness</Label>
//               <Select
//                 value={draft.gateStrictness}
//                 onValueChange={(v) => update({ gateStrictness: v as TemplateDraft["gateStrictness"] })}
//               >
//                 <SelectTrigger className="w-36 h-8">
//                   <SelectValue />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="strict">Strict</SelectItem>
//                   <SelectItem value="medium">Medium</SelectItem>
//                   <SelectItem value="loose">Loose</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>

//             <div className="rounded-lg border p-3 space-y-3">
//               <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Quality Gates</p>

//               <div className="flex items-center justify-between">
//                 <div className="flex items-center gap-2">
//                   <Mail className="h-4 w-4 text-muted-foreground" />
//                   <Label className="text-sm">Require email</Label>
//                 </div>
//                 <Switch checked={draft.requireEmail} onCheckedChange={(v) => update({ requireEmail: v })} />
//               </div>

//               <div className="flex items-center justify-between">
//                 <div className="flex items-center gap-2">
//                   <ShieldCheck className="h-4 w-4 text-muted-foreground" />
//                   <Label className="text-sm">Require verified email</Label>
//                 </div>
//                 <Switch checked={draft.requireVerifiedEmail} onCheckedChange={(v) => update({ requireVerifiedEmail: v })} />
//               </div>

//               <div className="space-y-2">
//                 <div className="flex items-center justify-between">
//                   <div className="flex items-center gap-2">
//                     <Building2 className="h-4 w-4 text-muted-foreground" />
//                     <Label className="text-sm">Minimum company size</Label>
//                   </div>
//                   <Switch
//                     checked={draft.requireCompanySize}
//                     onCheckedChange={(v) => update({ requireCompanySize: v })}
//                   />
//                 </div>
//                 {draft.requireCompanySize && (
//                   <div className="flex items-center gap-2 pl-6">
//                     <Input
//                       type="number"
//                       min={0}
//                       value={draft.minCompanySize}
//                       onChange={(e) => update({ minCompanySize: Number(e.target.value) || 0 })}
//                       className="h-7 w-24 text-xs"
//                     />
//                     <span className="text-xs text-muted-foreground">employees minimum</span>
//                   </div>
//                 )}
//               </div>

//               <div className="space-y-1.5">
//                 <div className="flex items-center justify-between">
//                   <div className="flex items-center gap-2">
//                     <Target className="h-4 w-4 text-muted-foreground" />
//                     <Label className="text-sm">LLM score threshold</Label>
//                     <Badge variant="outline" className="font-mono text-xs">
//                       {draft.llmScoreThreshold.toFixed(2)}
//                     </Badge>
//                   </div>
//                 </div>
//                 <input
//                   type="range"
//                   min={0}
//                   max={1}
//                   step={0.05}
//                   value={draft.llmScoreThreshold}
//                   onChange={(e) => update({ llmScoreThreshold: Number(e.target.value) })}
//                   className="w-full accent-primary"
//                 />
//                 <div className="flex justify-between text-[10px] text-muted-foreground">
//                   <span>0.00 (off)</span><span>0.50</span><span>1.00 (strict)</span>
//                 </div>
//               </div>

//               <div className="space-y-1.5">
//                 <Label className="text-sm">Exclude domains</Label>
//                 <div className="flex flex-wrap gap-1.5">
//                   {draft.excludeDomains.map((d) => (
//                     <Badge key={d} variant="secondary" className="text-xs gap-1 pr-1">
//                       {d}
//                       <button
//                         onClick={() => update({ excludeDomains: draft.excludeDomains.filter((x) => x !== d) })}
//                         className="hover:text-destructive ml-0.5"
//                       >
//                         <X className="h-3 w-3" />
//                       </button>
//                     </Badge>
//                   ))}
//                 </div>
//                 <div className="flex gap-1.5">
//                   <Input
//                     value={domainInput}
//                     onChange={(e) => setDomainInput(e.target.value)}
//                     onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addDomain(); } }}
//                     placeholder="gmail.com"
//                     className="h-7 text-xs flex-1"
//                   />
//                   <Button variant="outline" size="sm" className="h-7 px-2" onClick={addDomain}>
//                     <Plus className="h-3.5 w-3.5" />
//                   </Button>
//                 </div>
//               </div>
//             </div>
//           </div>
//         </div>

//         <DialogFooter>
//           <Button variant="outline" onClick={onClose} disabled={saveMut.isPending}>Cancel</Button>
//           <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending || !isValid}>
//             {saveMut.isPending ? (
//               <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving…</>
//             ) : mode === "create" ? (
//               <><Plus className="h-4 w-4 mr-2" /> Create Template</>
//             ) : (
//               <><CheckCircle2 className="h-4 w-4 mr-2" /> Save Changes</>
//             )}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // CloneDialog
// // ─────────────────────────────────────────────────────────────────────────────

// function CloneDialog({
//   template,
//   open,
//   onClose,
//   onCloned,
// }: {
//   template: FlowTemplate | null;
//   open: boolean;
//   onClose: () => void;
//   onCloned: (flowId: string) => void;
// }) {
//   const [cloneName, setCloneName] = useState("");

//   const cloneMut = useMutation({
//     mutationFn: () =>
//       http.post<{ success: boolean; flow_id?: string; name?: string }>(
//         "/api/v1/flow-templates/clone",
//         {
//           template_id: template!.id,
//           new_name: cloneName.trim() || undefined,
//         },
//       ),
//     onSuccess: (data) => {
//       toast.success("Template cloned", {
//         description: `"${cloneName.trim() || template?.name}" is now available in Prospecting Flows.`,
//       });
//       onClose();
//       if (data.flow_id) onCloned(data.flow_id);
//     },
//     onError: () => toast.error("Failed to clone template"),
//   });

//   function handleOpen(o: boolean) {
//     if (!o) { onClose(); setCloneName(""); }
//   }

//   return (
//     <Dialog open={open} onOpenChange={handleOpen}>
//       <DialogContent className="max-w-sm">
//         <DialogHeader>
//           <DialogTitle className="flex items-center gap-2">
//             <Copy className="h-4 w-4 text-primary" /> Use Template
//           </DialogTitle>
//           <DialogDescription>
//             Clone &ldquo;{template?.name}&rdquo; into a new editable flow. All
//             source steps, enrichment, and gates are pre-configured — customise
//             freely after cloning.
//           </DialogDescription>
//         </DialogHeader>
//         <div className="space-y-2 py-1">
//           <Label>New Flow Name</Label>
//           <Input
//             value={cloneName}
//             onChange={(e) => setCloneName(e.target.value)}
//             placeholder={`${template?.name ?? "My Flow"} (Copy)`}
//             onKeyDown={(e) => {
//               if (e.key === "Enter" && !cloneMut.isPending) cloneMut.mutate();
//             }}
//             autoFocus
//           />
//           <p className="text-xs text-muted-foreground">
//             Leave blank to use the default name.
//           </p>
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={() => { onClose(); setCloneName(""); }}>
//             Cancel
//           </Button>
//           <Button
//             onClick={() => cloneMut.mutate()}
//             disabled={cloneMut.isPending}
//             className="bg-emerald-600 hover:bg-emerald-700 text-white"
//           >
//             {cloneMut.isPending ? (
//               <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Cloning…</>
//             ) : (
//               <><Copy className="h-4 w-4 mr-2" /> Clone &amp; Edit</>
//             )}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // TemplateCard
// // ─────────────────────────────────────────────────────────────────────────────

// function TemplateCard({
//   template,
//   onClone,
//   onEdit,
//   onDelete,
// }: {
//   template: FlowTemplate;
//   onClone: () => void;
//   onEdit: () => void;
//   onDelete: () => void;
// }) {
//   const meta = getTemplateMeta(template);
//   const { Icon, iconBg, iconColor, accent } = meta;
//   const strictness = STRICTNESS_STYLE[template.gateStrictness] ?? STRICTNESS_STYLE.medium;
//   const gc = template.gateConfig;

//   return (
//     <Card className={cn("flex flex-col transition-colors", accent)}>
//       <CardHeader>
//         <div className="flex items-start gap-3">
//           <div className={cn("flex h-12 w-12 items-center justify-center rounded-full shrink-0", iconBg)}>
//             <Icon className={cn("h-6 w-6", iconColor)} />
//           </div>
//           <div className="min-w-0 flex-1">
//             <CardTitle className="text-base leading-tight">{template.name}</CardTitle>
//             <div className="flex items-center gap-1.5 mt-1">
//               <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded border", strictness.class)}>
//                 {strictness.label}
//               </span>
//             </div>
//           </div>
//           <div className="flex gap-1 shrink-0">
//             <button
//               onClick={onEdit}
//               className="text-muted-foreground hover:text-foreground p-1 rounded transition-colors"
//               title="Edit template"
//             >
//               <Edit2 className="h-3.5 w-3.5" />
//             </button>
//             <button
//               onClick={onDelete}
//               className="text-muted-foreground hover:text-destructive p-1 rounded transition-colors"
//               title="Delete template"
//             >
//               <Trash2 className="h-3.5 w-3.5" />
//             </button>
//           </div>
//         </div>
//         <p className="text-sm text-muted-foreground mt-2 line-clamp-3">
//           {template.description || "No description."}
//         </p>
//       </CardHeader>

//       <CardContent className="flex-1 flex flex-col gap-3">
//         {/* Source platforms */}
//         <div>
//           <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
//             Source Platforms
//           </p>
//           <div className="flex flex-wrap gap-1">
//             {template.sourcePlatforms.length === 0 ? (
//               <span className="text-xs text-muted-foreground italic">None</span>
//             ) : (
//               template.sourcePlatforms.map((p) => (
//                 <Badge key={p} variant="secondary" className="text-xs">
//                   {SOURCE_PLATFORMS.find((s) => s.key === p)?.label ?? p}
//                 </Badge>
//               ))
//             )}
//           </div>
//         </div>

//         {/* Enrichment platforms */}
//         <div>
//           <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
//             Enrichment
//             <span className="ml-1 font-normal normal-case">(optional)</span>
//           </p>
//           <div className="flex flex-wrap gap-1">
//             {template.enrichmentPlatforms.length === 0 ? (
//               <span className="text-xs text-muted-foreground italic">None (skipped)</span>
//             ) : (
//               template.enrichmentPlatforms.map((p) => (
//                 <Badge key={p} variant="outline" className="text-xs">
//                   {ENRICH_PLATFORMS.find((e) => e.key === p)?.label ?? p}
//                 </Badge>
//               ))
//             )}
//           </div>
//         </div>

//         {/* Gate summary */}
//         <div className="rounded-md bg-muted/30 border px-2.5 py-2 space-y-1">
//           <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
//             Gate Summary
//           </p>
//           <div className="flex flex-wrap gap-1">
//             {gc.requireEmail && <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">Email</Badge>}
//             {gc.requireVerifiedEmail && <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">Verified</Badge>}
//             {gc.requireCompanySize && gc.minCompanySize > 0 && (
//               <Badge variant="outline" className="text-[10px] bg-purple-50 text-purple-700 border-purple-200">
//                 ≥{gc.minCompanySize} emp
//               </Badge>
//             )}
//             {gc.llmScoreThreshold > 0 && (
//               <Badge variant="outline" className="text-[10px] bg-violet-50 text-violet-700 border-violet-200">
//                 Score ≥{gc.llmScoreThreshold.toFixed(2)}
//               </Badge>
//             )}
//             {gc.excludeDomains.length > 0 && (
//               <Badge variant="outline" className="text-[10px] bg-red-50 text-red-700 border-red-200">
//                 {gc.excludeDomains.length} excl.
//               </Badge>
//             )}
//             {!gc.requireEmail && !gc.requireVerifiedEmail && !gc.requireCompanySize && gc.llmScoreThreshold === 0 && (
//               <span className="text-xs text-muted-foreground italic">No gates active</span>
//             )}
//           </div>
//         </div>

//         {/* Recommended for */}
//         {template.recommendedFor && (
//           <p className="text-xs text-muted-foreground">
//             <span className="font-medium">Best for:</span> {template.recommendedFor}
//           </p>
//         )}

//         {/* CTA */}
//         <Button className="w-full mt-auto" onClick={onClone}>
//           <Copy className="h-4 w-4 mr-2" /> Use Template
//         </Button>
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // DeleteDialog
// // ─────────────────────────────────────────────────────────────────────────────

// function DeleteDialog({
//   template,
//   open,
//   onClose,
//   onDeleted,
// }: {
//   template: FlowTemplate | null;
//   open: boolean;
//   onClose: () => void;
//   onDeleted: () => void;
// }) {
//   const deleteMut = useMutation({
//     mutationFn: () => http.delete(`/api/v1/flow-templates/${template!.id}`),
//     onSuccess: () => {
//       toast.success("Template deleted");
//       onDeleted();
//       onClose();
//     },
//     onError: () => toast.error("Failed to delete template"),
//   });

//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
//       <DialogContent className="max-w-sm">
//         <DialogHeader>
//           <DialogTitle>Delete template?</DialogTitle>
//           <DialogDescription>
//             &ldquo;{template?.name}&rdquo; will be permanently removed. Flows
//             already cloned from it are unaffected.
//           </DialogDescription>
//         </DialogHeader>
//         <DialogFooter>
//           <Button variant="outline" onClick={onClose}>Cancel</Button>
//           <Button
//             variant="destructive"
//             onClick={() => deleteMut.mutate()}
//             disabled={deleteMut.isPending}
//           >
//             {deleteMut.isPending ? "Deleting…" : "Delete"}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Main Page
// // ─────────────────────────────────────────────────────────────────────────────

// export function FlowTemplatesPage() {
//   const qc = useQueryClient();
//   const navigate = useNavigate();

//   // Dialog states
//   const [createOpen, setCreateOpen] = useState(false);
//   const [editTarget, setEditTarget] = useState<FlowTemplate | null>(null);
//   const [cloneTarget, setCloneTarget] = useState<FlowTemplate | null>(null);
//   const [deleteTarget, setDeleteTarget] = useState<FlowTemplate | null>(null);

//   // Fetch templates — handles { items: [...] } response shape
//   const { data: raw, isLoading, isError, refetch } = useQuery({
//     queryKey: ["flow-templates"],
//     queryFn: () => http.get<unknown>("/api/v1/flow-templates"),
//     retry: false,
//   });

//   const templates = extractItems(raw);

//   function invalidate() {
//     qc.invalidateQueries({ queryKey: ["flow-templates"] });
//   }

//   return (
//     <div className="space-y-6">
//       {/* Header */}
//       <div className="flex items-start justify-between flex-wrap gap-4">
//         <div>
//           <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
//             <Layers className="h-6 w-6 text-primary" />
//             Flow Templates
//           </h2>
//           <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
//             Pre-built prospecting flows for common B2B use cases. Clone a template to get a
//             working flow in seconds, then customise it in the Flow Builder.
//           </p>
//         </div>
//         <div className="flex items-center gap-2">
//           <Button variant="outline" onClick={() => refetch()}>
//             <RefreshCw className="h-4 w-4 mr-2" /> Refresh
//           </Button>
//           <Button variant="outline" onClick={() => navigate("/prospecting/flows")}>
//             <Zap className="h-4 w-4 mr-2" /> Build from Scratch
//           </Button>
//           <Button onClick={() => setCreateOpen(true)}>
//             <Plus className="h-4 w-4 mr-2" /> New Template
//           </Button>
//         </div>
//       </div>

//       {/* Grid */}
//       {isLoading ? (
//         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
//           {[0, 1, 2].map((i) => (
//             <Card key={i}>
//               <CardHeader>
//                 <div className="flex gap-3">
//                   <Skeleton className="h-12 w-12 rounded-full" />
//                   <div className="flex-1 space-y-2">
//                     <Skeleton className="h-4 w-32" />
//                     <Skeleton className="h-3 w-16" />
//                   </div>
//                 </div>
//                 <Skeleton className="h-4 w-full mt-2" />
//                 <Skeleton className="h-4 w-3/4" />
//               </CardHeader>
//               <CardContent className="space-y-3">
//                 <Skeleton className="h-4 w-full" />
//                 <Skeleton className="h-4 w-2/3" />
//                 <Skeleton className="h-9 w-full" />
//               </CardContent>
//             </Card>
//           ))}
//         </div>
//       ) : isError ? (
//         <Card>
//           <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
//             <p className="font-medium text-sm">Failed to load templates</p>
//             <Button variant="outline" onClick={() => refetch()}>Retry</Button>
//           </CardContent>
//         </Card>
//       ) : templates.length === 0 ? (
//         <Card>
//           <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
//             <Layers className="h-12 w-12 text-muted-foreground/40" />
//             <p className="font-medium">No templates yet</p>
//             <p className="text-sm text-muted-foreground">
//               Create your first template or use the built-in ones.
//             </p>
//             <Button onClick={() => setCreateOpen(true)}>
//               <Plus className="h-4 w-4 mr-2" /> Create Template
//             </Button>
//           </CardContent>
//         </Card>
//       ) : (
//         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
//           {templates.map((tpl) => (
//             <TemplateCard
//               key={tpl.id}
//               template={tpl}
//               onClone={() => setCloneTarget(tpl)}
//               onEdit={() => setEditTarget(tpl)}
//               onDelete={() => setDeleteTarget(tpl)}
//             />
//           ))}
//         </div>
//       )}

//       {/* Info card */}
//       <Card>
//         <CardHeader>
//           <CardTitle className="text-base flex items-center gap-2">
//             <ShieldCheck className="h-4 w-4 text-primary" />
//             When to use each template
//           </CardTitle>
//         </CardHeader>
//         <CardContent className="text-sm text-muted-foreground space-y-3">
//           <div className="flex gap-2">
//             <Building2 className="h-4 w-4 mt-0.5 shrink-0 text-violet-600" />
//             <p>
//               <strong className="text-foreground">Enterprise ABM</strong> — Strict gates,
//               requires verified email and 500+ employee companies. Best for Fortune 500 targets
//               where precision beats volume.
//             </p>
//           </div>
//           <div className="flex gap-2">
//             <Handshake className="h-4 w-4 mt-0.5 shrink-0 text-amber-600" />
//             <p>
//               <strong className="text-foreground">Partner Recruitment</strong> — Medium gates,
//               balanced sourcing for recruiting agencies and consultancies as channel partners.
//             </p>
//           </div>
//           <div className="flex gap-2">
//             <Rocket className="h-4 w-4 mt-0.5 shrink-0 text-emerald-600" />
//             <p>
//               <strong className="text-foreground">PLG Volume</strong> — Loose gates, maximum
//               volume for product-led growth motions where speed and coverage win.
//             </p>
//           </div>
//           <p className="italic text-xs pt-1">
//             Tip: A cloned flow is a regular editable flow — change sources, enrichment, and
//             gates freely without affecting the original template.
//           </p>
//         </CardContent>
//       </Card>

//       {/* Create dialog */}
//       <CreateEditDialog
//         open={createOpen}
//         onClose={() => setCreateOpen(false)}
//         initialDraft={emptyDraft()}
//         mode="create"
//         onSuccess={() => { invalidate(); }}
//       />

//       {/* Edit dialog */}
//       <CreateEditDialog
//         open={!!editTarget}
//         onClose={() => setEditTarget(null)}
//         initialDraft={editTarget ? templateToDraft(editTarget) : emptyDraft()}
//         mode="edit"
//         templateId={editTarget?.id}
//         onSuccess={() => { invalidate(); setEditTarget(null); }}
//       />

//       {/* Clone dialog */}
//       <CloneDialog
//         template={cloneTarget}
//         open={!!cloneTarget}
//         onClose={() => setCloneTarget(null)}
//         onCloned={(_flowId) => {
//           qc.invalidateQueries({ queryKey: ["flows", "list"] });
//           navigate("/prospecting/flows");
//         }}
//       />

//       {/* Delete dialog */}
//       <DeleteDialog
//         template={deleteTarget}
//         open={!!deleteTarget}
//         onClose={() => setDeleteTarget(null)}
//         onDeleted={invalidate}
//       />
//     </div>
//   );
// }

/**
 * FlowTemplatesPage.tsx — Pre-built flow templates gallery.
 *
 * Fixes from previous version:
 *  - API returns { items: [...], total: N } not a plain array → normalised here
 *  - Backend uses snake_case (source_platforms, gate_strictness, recommended_for
 *    as string) → mapped to frontend camelCase on receipt
 *  - Dialog was broken (DialogClose as top-level child) → fixed structure
 *  - Added Create Template dialog and Edit Template dialog (matching Next.js ref)
 *  - Clone navigates to Prospecting Flows after success
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Building2,
  CheckCircle2,
  Copy,
  Edit2,
  Handshake,
  Layers,
  Loader2,
  Mail,
  Plus,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

/** Raw shape from the backend (snake_case, recommended_for is a string) */
interface TemplateRaw {
  id: string;
  name: string;
  description: string;
  source_platforms: string[];
  enrichment_platforms: string[];
  gate_config: Record<string, unknown>;
  gate_strictness: "strict" | "medium" | "loose" | "moderate" | "lenient";
  recommended_for: string;
}

/** Normalised frontend shape */
interface FlowTemplate {
  id: string;
  name: string;
  description: string;
  sourcePlatforms: string[];
  enrichmentPlatforms: string[];
  gateConfig: {
    requireEmail: boolean;
    requireVerifiedEmail: boolean;
    requireCompanySize: boolean;
    minCompanySize: number;
    llmScoreThreshold: number;
    excludeDomains: string[];
  };
  gateStrictness: "strict" | "medium" | "loose";
  recommendedFor: string;
}

/** Draft state for Create / Edit dialog */
interface TemplateDraft {
  name: string;
  description: string;
  sourcePlatforms: string[];
  enrichmentPlatforms: string[];
  gateStrictness: "strict" | "medium" | "loose";
  requireEmail: boolean;
  requireVerifiedEmail: boolean;
  requireCompanySize: boolean;
  minCompanySize: number;
  llmScoreThreshold: number;
  excludeDomains: string[];
  recommendedFor: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Normalise backend → frontend
// ─────────────────────────────────────────────────────────────────────────────

function normaliseStrictness(raw: string): "strict" | "medium" | "loose" {
  if (raw === "moderate") return "medium";
  if (raw === "lenient") return "loose";
  if (raw === "strict" || raw === "medium" || raw === "loose") return raw;
  return "medium";
}

function normalise(raw: TemplateRaw): FlowTemplate {
  const gc = (raw.gate_config ?? {}) as Record<string, unknown>;
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description ?? "",
    sourcePlatforms: Array.isArray(raw.source_platforms) ? raw.source_platforms : [],
    enrichmentPlatforms: Array.isArray(raw.enrichment_platforms) ? raw.enrichment_platforms : [],
    gateConfig: {
      requireEmail: Boolean(gc.requireEmail ?? true),
      requireVerifiedEmail: Boolean(gc.requireVerifiedEmail),
      requireCompanySize: Boolean(gc.requireCompanySize),
      minCompanySize: Number(gc.minCompanySize ?? 0),
      llmScoreThreshold: Number(gc.llmScoreThreshold ?? 0),
      excludeDomains: Array.isArray(gc.excludeDomains) ? (gc.excludeDomains as string[]) : [],
    },
    gateStrictness: normaliseStrictness(raw.gate_strictness ?? "medium"),
    recommendedFor: typeof raw.recommended_for === "string" ? raw.recommended_for : "",
  };
}

function extractItems(data: unknown): FlowTemplate[] {
  if (!data) return [];
  // Backend returns { items: [...], total: N }
  if (typeof data === "object" && !Array.isArray(data)) {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.items)) {
      return (obj.items as TemplateRaw[]).map(normalise);
    }
  }
  // Fallback: plain array
  if (Array.isArray(data)) {
    return (data as TemplateRaw[]).map(normalise);
  }
  return [];
}

// ─────────────────────────────────────────────────────────────────────────────
// Available platforms (for multi-select in Create/Edit)
// ─────────────────────────────────────────────────────────────────────────────

const SOURCE_PLATFORMS = [
  { key: "ai_web_search", label: "AI Web Search" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "apollo", label: "Apollo.io" },
  { key: "zoominfo", label: "ZoomInfo" },
  { key: "clearbit", label: "Clearbit" },
  { key: "hunter", label: "Hunter.io" },
  { key: "clay", label: "Clay" },
  { key: "lusha", label: "Lusha" },
  { key: "kaspr", label: "Kaspr" },
];

const ENRICH_PLATFORMS = [
  { key: "hunter", label: "Hunter.io" },
  { key: "clearbit", label: "Clearbit" },
  { key: "lusha", label: "Lusha" },
  { key: "kaspr", label: "Kaspr" },
  { key: "apollo", label: "Apollo.io" },
  { key: "email_waterfall", label: "Email Waterfall" },
];

// ─────────────────────────────────────────────────────────────────────────────
// Visual registry (maps template id/name keywords → display metadata)
// ─────────────────────────────────────────────────────────────────────────────

interface TemplateMeta {
  Icon: React.ComponentType<{ className?: string }>;
  iconBg: string;
  iconColor: string;
  accent: string;
}

function getTemplateMeta(t: FlowTemplate): TemplateMeta {
  const n = t.name.toLowerCase();
  const id = t.id.toLowerCase();
  if (n.includes("enterprise") || id.includes("enterprise") || id.includes("abm")) {
    return {
      Icon: Building2,
      iconBg: "bg-violet-100",
      iconColor: "text-violet-600",
      accent: "border-violet-200 hover:border-violet-300",
    };
  }
  if (n.includes("plg") || n.includes("volume") || n.includes("self-serve")) {
    return {
      Icon: Rocket,
      iconBg: "bg-emerald-100",
      iconColor: "text-emerald-600",
      accent: "border-emerald-200 hover:border-emerald-300",
    };
  }
  if (n.includes("partner") || n.includes("recruit")) {
    return {
      Icon: Handshake,
      iconBg: "bg-amber-100",
      iconColor: "text-amber-600",
      accent: "border-amber-200 hover:border-amber-300",
    };
  }
  return {
    Icon: Sparkles,
    iconBg: "bg-slate-100",
    iconColor: "text-slate-600",
    accent: "border-border hover:border-primary/30",
  };
}

const STRICTNESS_STYLE: Record<string, { label: string; class: string }> = {
  strict: { label: "Strict", class: "bg-red-100 text-red-700 border-red-200" },
  medium: { label: "Medium", class: "bg-amber-100 text-amber-700 border-amber-200" },
  loose:  { label: "Loose",  class: "bg-emerald-100 text-emerald-700 border-emerald-200" },
};

// ─────────────────────────────────────────────────────────────────────────────
// PlatformToggle — checkbox-style toggle for platform lists
// ─────────────────────────────────────────────────────────────────────────────

function PlatformToggle({
  label,
  checked,
  onToggle,
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={cn(
        "flex items-center gap-2 cursor-pointer rounded-md border px-2.5 py-1.5 text-xs transition-colors select-none",
        checked
          ? "bg-primary/10 border-primary/40 text-primary font-medium"
          : "bg-muted/30 border-muted text-muted-foreground hover:bg-muted/60",
      )}
    >
      <input type="checkbox" className="sr-only" checked={checked} onChange={onToggle} />
      {checked && <CheckCircle2 className="h-3 w-3 shrink-0" />}
      {label}
    </label>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CreateEditDialog — shared dialog for both Create and Edit
// ─────────────────────────────────────────────────────────────────────────────

function emptyDraft(): TemplateDraft {
  return {
    name: "",
    description: "",
    sourcePlatforms: ["ai_web_search"],
    enrichmentPlatforms: [],
    gateStrictness: "medium",
    requireEmail: true,
    requireVerifiedEmail: false,
    requireCompanySize: false,
    minCompanySize: 0,
    llmScoreThreshold: 0.6,
    excludeDomains: ["gmail.com", "yahoo.com", "hotmail.com"],
    recommendedFor: "",
  };
}

function templateToDraft(t: FlowTemplate): TemplateDraft {
  return {
    name: t.name,
    description: t.description,
    sourcePlatforms: [...t.sourcePlatforms],
    enrichmentPlatforms: [...t.enrichmentPlatforms],
    gateStrictness: t.gateStrictness,
    requireEmail: t.gateConfig.requireEmail,
    requireVerifiedEmail: t.gateConfig.requireVerifiedEmail,
    requireCompanySize: t.gateConfig.requireCompanySize,
    minCompanySize: t.gateConfig.minCompanySize,
    llmScoreThreshold: t.gateConfig.llmScoreThreshold,
    excludeDomains: [...t.gateConfig.excludeDomains],
    recommendedFor: t.recommendedFor,
  };
}

function draftToPayload(draft: TemplateDraft) {
  return {
    name: draft.name.trim(),
    description: draft.description.trim(),
    source_platforms: draft.sourcePlatforms,
    enrichment_platforms: draft.enrichmentPlatforms,
    gate_config: {
      requireEmail: draft.requireEmail,
      requireVerifiedEmail: draft.requireVerifiedEmail,
      requireCompanySize: draft.requireCompanySize,
      minCompanySize: draft.minCompanySize,
      llmScoreThreshold: draft.llmScoreThreshold,
      excludeDomains: draft.excludeDomains,
    },
    gate_strictness: draft.gateStrictness,
    recommended_for: draft.recommendedFor.trim(),
  };
}

function CreateEditDialog({
  open,
  onClose,
  initialDraft,
  mode,
  templateId,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  initialDraft: TemplateDraft;
  mode: "create" | "edit";
  templateId?: string;
  onSuccess: () => void;
}) {
  const [draft, setDraft] = useState<TemplateDraft>(initialDraft);
  const [domainInput, setDomainInput] = useState("");

  // Reset draft when dialog opens with new initial values
  const [lastInitial, setLastInitial] = useState(initialDraft);
  if (initialDraft !== lastInitial) {
    setLastInitial(initialDraft);
    setDraft(initialDraft);
  }

  const saveMut = useMutation({
    mutationFn: async () => {
      const payload = draftToPayload(draft);
      if (mode === "create") {
        return http.post<TemplateRaw>("/api/v1/flow-templates", payload);
      } else {
        return http.put<TemplateRaw>(`/api/v1/flow-templates/${templateId}`, payload);
      }
    },
    onSuccess: () => {
      toast.success(mode === "create" ? "Template created" : "Template updated");
      onSuccess();
      onClose();
    },
    onError: (err) => {
      toast.error(mode === "create" ? "Failed to create template" : "Failed to update template", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  function update(patch: Partial<TemplateDraft>) {
    setDraft((d) => ({ ...d, ...patch }));
  }

  function togglePlatform(list: "sourcePlatforms" | "enrichmentPlatforms", key: string) {
    const current = draft[list];
    if (current.includes(key)) {
      update({ [list]: current.filter((k) => k !== key) });
    } else {
      update({ [list]: [...current, key] });
    }
  }

  function addDomain() {
    const d = domainInput.trim().toLowerCase().replace(/^@/, "");
    if (!d || draft.excludeDomains.includes(d)) { setDomainInput(""); return; }
    update({ excludeDomains: [...draft.excludeDomains, d] });
    setDomainInput("");
  }

  const isValid = draft.name.trim().length > 0 && draft.sourcePlatforms.length > 0;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Create New Template" : `Edit Template — ${initialDraft.name}`}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Define a reusable prospecting flow template. Users can clone it to create a customised flow."
              : "Update the template configuration. Existing clones are not affected."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Basic info */}
          <div className="grid grid-cols-1 gap-3">
            <div className="space-y-1.5">
              <Label>Template Name *</Label>
              <Input
                value={draft.name}
                onChange={(e) => update({ name: e.target.value })}
                placeholder="e.g. Enterprise ABM Flow"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Textarea
                value={draft.description}
                onChange={(e) => update({ description: e.target.value })}
                placeholder="What this template is designed for…"
                className="min-h-[70px] resize-none"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Recommended For</Label>
              <Input
                value={draft.recommendedFor}
                onChange={(e) => update({ recommendedFor: e.target.value })}
                placeholder="e.g. Fortune 500 / enterprise targets where precision > volume"
              />
            </div>
          </div>

          <Separator />

          {/* Source platforms */}
          <div className="space-y-2">
            <Label className="flex items-center gap-1.5">
              Source Platforms *
              <span className="text-xs font-normal text-muted-foreground">(at least one required)</span>
            </Label>
            <div className="flex flex-wrap gap-1.5">
              {SOURCE_PLATFORMS.map((p) => (
                <PlatformToggle
                  key={p.key}
                  label={p.label}
                  checked={draft.sourcePlatforms.includes(p.key)}
                  onToggle={() => togglePlatform("sourcePlatforms", p.key)}
                />
              ))}
            </div>
          </div>

          {/* Enrichment platforms */}
          <div className="space-y-2">
            <Label className="flex items-center gap-1.5">
              Enrichment Platforms
              <span className="text-xs font-normal text-muted-foreground">(optional)</span>
            </Label>
            <div className="flex flex-wrap gap-1.5">
              {ENRICH_PLATFORMS.map((p) => (
                <PlatformToggle
                  key={p.key}
                  label={p.label}
                  checked={draft.enrichmentPlatforms.includes(p.key)}
                  onToggle={() => togglePlatform("enrichmentPlatforms", p.key)}
                />
              ))}
            </div>
          </div>

          <Separator />

          {/* Gate strictness + gates */}
          <div className="space-y-3">
            <div className="flex items-center gap-4">
              <Label>Gate Strictness</Label>
              <Select
                value={draft.gateStrictness}
                onValueChange={(v) => update({ gateStrictness: v as TemplateDraft["gateStrictness"] })}
              >
                <SelectTrigger className="w-36 h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="strict">Strict</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="loose">Loose</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="rounded-lg border p-3 space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Quality Gates</p>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <Label className="text-sm">Require email</Label>
                </div>
                <Switch checked={draft.requireEmail} onCheckedChange={(v) => update({ requireEmail: v })} />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                  <Label className="text-sm">Require verified email</Label>
                </div>
                <Switch checked={draft.requireVerifiedEmail} onCheckedChange={(v) => update({ requireVerifiedEmail: v })} />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    <Label className="text-sm">Minimum company size</Label>
                  </div>
                  <Switch
                    checked={draft.requireCompanySize}
                    onCheckedChange={(v) => update({ requireCompanySize: v })}
                  />
                </div>
                {draft.requireCompanySize && (
                  <div className="flex items-center gap-2 pl-6">
                    <Input
                      type="number"
                      min={0}
                      value={draft.minCompanySize}
                      onChange={(e) => update({ minCompanySize: Number(e.target.value) || 0 })}
                      className="h-7 w-24 text-xs"
                    />
                    <span className="text-xs text-muted-foreground">employees minimum</span>
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Target className="h-4 w-4 text-muted-foreground" />
                    <Label className="text-sm">LLM score threshold</Label>
                    <Badge variant="outline" className="font-mono text-xs">
                      {draft.llmScoreThreshold.toFixed(2)}
                    </Badge>
                  </div>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={draft.llmScoreThreshold}
                  onChange={(e) => update({ llmScoreThreshold: Number(e.target.value) })}
                  className="w-full accent-primary"
                />
                <div className="flex justify-between text-[10px] text-muted-foreground">
                  <span>0.00 (off)</span><span>0.50</span><span>1.00 (strict)</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-sm">Exclude domains</Label>
                <div className="flex flex-wrap gap-1.5">
                  {draft.excludeDomains.map((d) => (
                    <Badge key={d} variant="secondary" className="text-xs gap-1 pr-1">
                      {d}
                      <button
                        onClick={() => update({ excludeDomains: draft.excludeDomains.filter((x) => x !== d) })}
                        className="hover:text-destructive ml-0.5"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-1.5">
                  <Input
                    value={domainInput}
                    onChange={(e) => setDomainInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addDomain(); } }}
                    placeholder="gmail.com"
                    className="h-7 text-xs flex-1"
                  />
                  <Button variant="outline" size="sm" className="h-7 px-2" onClick={addDomain}>
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saveMut.isPending}>Cancel</Button>
          <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending || !isValid}>
            {saveMut.isPending ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving…</>
            ) : mode === "create" ? (
              <><Plus className="h-4 w-4 mr-2" /> Create Template</>
            ) : (
              <><CheckCircle2 className="h-4 w-4 mr-2" /> Save Changes</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CloneDialog
// ─────────────────────────────────────────────────────────────────────────────

function CloneDialog({
  template,
  open,
  onClose,
  onCloned,
}: {
  template: FlowTemplate | null;
  open: boolean;
  onClose: () => void;
  onCloned: (flowId: string) => void;
}) {
  const [cloneName, setCloneName] = useState("");

  const cloneMut = useMutation({
    mutationFn: () =>
      http.post<{ success: boolean; flow_id?: string; name?: string }>(
        "/api/v1/flow-templates/clone",
        {
          template_id: template!.id,
          new_name: cloneName.trim() || undefined,
        },
      ),
    onSuccess: (data) => {
      toast.success("Template cloned", {
        description: `"${cloneName.trim() || template?.name}" is now available in Prospecting Flows.`,
      });
      onClose();
      if (data.flow_id) onCloned(data.flow_id);
    },
    onError: () => toast.error("Failed to clone template"),
  });

  function handleOpen(o: boolean) {
    if (!o) { onClose(); setCloneName(""); }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Copy className="h-4 w-4 text-primary" /> Use Template
          </DialogTitle>
          <DialogDescription>
            Clone &ldquo;{template?.name}&rdquo; into a new editable flow. All
            source steps, enrichment, and gates are pre-configured — customise
            freely after cloning.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-1">
          <Label>New Flow Name</Label>
          <Input
            value={cloneName}
            onChange={(e) => setCloneName(e.target.value)}
            placeholder={`${template?.name ?? "My Flow"} (Copy)`}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !cloneMut.isPending) cloneMut.mutate();
            }}
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            Leave blank to use the default name.
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { onClose(); setCloneName(""); }}>
            Cancel
          </Button>
          <Button
            onClick={() => cloneMut.mutate()}
            disabled={cloneMut.isPending}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {cloneMut.isPending ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Cloning…</>
            ) : (
              <><Copy className="h-4 w-4 mr-2" /> Clone &amp; Edit</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TemplateCard
// ─────────────────────────────────────────────────────────────────────────────

function TemplateCard({
  template,
  onClone,
  onEdit,
  onDelete,
}: {
  template: FlowTemplate;
  onClone: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const meta = getTemplateMeta(template);
  const { Icon, iconBg, iconColor, accent } = meta;
  const strictness = STRICTNESS_STYLE[template.gateStrictness] ?? STRICTNESS_STYLE.medium;
  const gc = template.gateConfig;

  return (
    <Card className={cn("flex flex-col transition-colors", accent)}>
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className={cn("flex h-12 w-12 items-center justify-center rounded-full shrink-0", iconBg)}>
            <Icon className={cn("h-6 w-6", iconColor)} />
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base leading-tight">{template.name}</CardTitle>
            <div className="flex items-center gap-1.5 mt-1">
              <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded border", strictness.class)}>
                {strictness.label}
              </span>
            </div>
          </div>
          <div className="flex gap-1 shrink-0">
            <button
              onClick={onEdit}
              className="text-muted-foreground hover:text-foreground p-1 rounded transition-colors"
              title="Edit template"
            >
              <Edit2 className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={onDelete}
              className="text-muted-foreground hover:text-destructive p-1 rounded transition-colors"
              title="Delete template"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
        <p className="text-sm text-muted-foreground mt-2 line-clamp-3">
          {template.description || "No description."}
        </p>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col gap-3">
        {/* Source platforms */}
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Source Platforms
          </p>
          <div className="flex flex-wrap gap-1">
            {template.sourcePlatforms.length === 0 ? (
              <span className="text-xs text-muted-foreground italic">None</span>
            ) : (
              template.sourcePlatforms.map((p) => (
                <Badge key={p} variant="secondary" className="text-xs">
                  {SOURCE_PLATFORMS.find((s) => s.key === p)?.label ?? p}
                </Badge>
              ))
            )}
          </div>
        </div>

        {/* Enrichment platforms */}
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Enrichment
            <span className="ml-1 font-normal normal-case">(optional)</span>
          </p>
          <div className="flex flex-wrap gap-1">
            {template.enrichmentPlatforms.length === 0 ? (
              <span className="text-xs text-muted-foreground italic">None (skipped)</span>
            ) : (
              template.enrichmentPlatforms.map((p) => (
                <Badge key={p} variant="outline" className="text-xs">
                  {ENRICH_PLATFORMS.find((e) => e.key === p)?.label ?? p}
                </Badge>
              ))
            )}
          </div>
        </div>

        {/* Gate summary */}
        <div className="rounded-md bg-muted/30 border px-2.5 py-2 space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Gate Summary
          </p>
          <div className="flex flex-wrap gap-1">
            {gc.requireEmail && <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">Email</Badge>}
            {gc.requireVerifiedEmail && <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">Verified</Badge>}
            {gc.requireCompanySize && gc.minCompanySize > 0 && (
              <Badge variant="outline" className="text-[10px] bg-purple-50 text-purple-700 border-purple-200">
                ≥{gc.minCompanySize} emp
              </Badge>
            )}
            {gc.llmScoreThreshold > 0 && (
              <Badge variant="outline" className="text-[10px] bg-violet-50 text-violet-700 border-violet-200">
                Score ≥{gc.llmScoreThreshold.toFixed(2)}
              </Badge>
            )}
            {gc.excludeDomains.length > 0 && (
              <Badge variant="outline" className="text-[10px] bg-red-50 text-red-700 border-red-200">
                {gc.excludeDomains.length} excl.
              </Badge>
            )}
            {!gc.requireEmail && !gc.requireVerifiedEmail && !gc.requireCompanySize && gc.llmScoreThreshold === 0 && (
              <span className="text-xs text-muted-foreground italic">No gates active</span>
            )}
          </div>
        </div>

        {/* Recommended for */}
        {template.recommendedFor && (
          <p className="text-xs text-muted-foreground">
            <span className="font-medium">Best for:</span> {template.recommendedFor}
          </p>
        )}

        {/* CTA */}
        <Button className="w-full mt-auto" onClick={onClone}>
          <Copy className="h-4 w-4 mr-2" /> Use Template
        </Button>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DeleteDialog
// ─────────────────────────────────────────────────────────────────────────────

function DeleteDialog({
  template,
  open,
  onClose,
  onDeleted,
}: {
  template: FlowTemplate | null;
  open: boolean;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const deleteMut = useMutation({
    mutationFn: () => http.delete(`/api/v1/flow-templates/${template!.id}`),
    onSuccess: () => {
      toast.success("Template deleted");
      onDeleted();
      onClose();
    },
    onError: () => toast.error("Failed to delete template"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete template?</DialogTitle>
          <DialogDescription>
            &ldquo;{template?.name}&rdquo; will be permanently removed. Flows
            already cloned from it are unaffected.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            variant="destructive"
            onClick={() => deleteMut.mutate()}
            disabled={deleteMut.isPending}
          >
            {deleteMut.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export function FlowTemplatesPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  // Dialog states
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<FlowTemplate | null>(null);
  const [cloneTarget, setCloneTarget] = useState<FlowTemplate | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<FlowTemplate | null>(null);

  // Fetch templates — handles { items: [...] } response shape
  const { data: raw, isLoading, isError, refetch } = useQuery({
    queryKey: ["flow-templates-page"],  // distinct from TemplatesDialog key in FlowsPage
    queryFn: () => http.get<unknown>("/api/v1/flow-templates"),
    retry: false,
  });

  const templates = extractItems(raw);

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["flow-templates-page"] });
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Layers className="h-6 w-6 text-primary" />
            Flow Templates
          </h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Pre-built prospecting flows for common B2B use cases. Clone a template to get a
            working flow in seconds, then customise it in the Flow Builder.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" /> Refresh
          </Button>
          <Button variant="outline" onClick={() => navigate("/prospecting/flows")}>
            <Zap className="h-4 w-4 mr-2" /> Build from Scratch
          </Button>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" /> New Template
          </Button>
        </div>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardHeader>
                <div className="flex gap-3">
                  <Skeleton className="h-12 w-12 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-16" />
                  </div>
                </div>
                <Skeleton className="h-4 w-full mt-2" />
                <Skeleton className="h-4 w-3/4" />
              </CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-9 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : isError ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
            <p className="font-medium text-sm">Failed to load templates</p>
            <Button variant="outline" onClick={() => refetch()}>Retry</Button>
          </CardContent>
        </Card>
      ) : templates.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <Layers className="h-12 w-12 text-muted-foreground/40" />
            <p className="font-medium">No templates yet</p>
            <p className="text-sm text-muted-foreground">
              Create your first template or use the built-in ones.
            </p>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-2" /> Create Template
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((tpl) => (
            <TemplateCard
              key={tpl.id}
              template={tpl}
              onClone={() => setCloneTarget(tpl)}
              onEdit={() => setEditTarget(tpl)}
              onDelete={() => setDeleteTarget(tpl)}
            />
          ))}
        </div>
      )}

      {/* Info card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            When to use each template
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-3">
          <div className="flex gap-2">
            <Building2 className="h-4 w-4 mt-0.5 shrink-0 text-violet-600" />
            <p>
              <strong className="text-foreground">Enterprise ABM</strong> — Strict gates,
              requires verified email and 500+ employee companies. Best for Fortune 500 targets
              where precision beats volume.
            </p>
          </div>
          <div className="flex gap-2">
            <Handshake className="h-4 w-4 mt-0.5 shrink-0 text-amber-600" />
            <p>
              <strong className="text-foreground">Partner Recruitment</strong> — Medium gates,
              balanced sourcing for recruiting agencies and consultancies as channel partners.
            </p>
          </div>
          <div className="flex gap-2">
            <Rocket className="h-4 w-4 mt-0.5 shrink-0 text-emerald-600" />
            <p>
              <strong className="text-foreground">PLG Volume</strong> — Loose gates, maximum
              volume for product-led growth motions where speed and coverage win.
            </p>
          </div>
          <p className="italic text-xs pt-1">
            Tip: A cloned flow is a regular editable flow — change sources, enrichment, and
            gates freely without affecting the original template.
          </p>
        </CardContent>
      </Card>

      {/* Create dialog */}
      <CreateEditDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        initialDraft={emptyDraft()}
        mode="create"
        onSuccess={() => { invalidate(); }}
      />

      {/* Edit dialog */}
      <CreateEditDialog
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        initialDraft={editTarget ? templateToDraft(editTarget) : emptyDraft()}
        mode="edit"
        templateId={editTarget?.id}
        onSuccess={() => { invalidate(); setEditTarget(null); }}
      />

      {/* Clone dialog */}
      <CloneDialog
        template={cloneTarget}
        open={!!cloneTarget}
        onClose={() => setCloneTarget(null)}
        onCloned={(_flowId) => {
          qc.invalidateQueries({ queryKey: ["flows", "list"] });
          navigate("/prospecting/flows");
        }}
      />

      {/* Delete dialog */}
      <DeleteDialog
        template={deleteTarget}
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={invalidate}
      />
    </div>
  );
}