
// /**
//  * FlowsPage.tsx — Prospecting Flows Builder (complete rewrite)
//  *
//  * Matches Next.js ProspectingFlowsPage + VisualFlowBuilder reference exactly:
//  *
//  *   ┌──────────────┬──────────────────────────────────────────────────────┐
//  *   │ FLOWS LIST   │  Header (name, badges, view toggle, action buttons)  │
//  *   │ (left panel) │  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐  │
//  *   │              │  │ 1. SOURCE    │ │ 2. ENRICH    │ │ 3. QUALITY  │  │
//  *   │              │  │    STEPS     │ │    STEPS     │ │    GATES    │  │
//  *   │              │  │              │ │   (optional) │ │             │  │
//  *   │              │  └──────────────┘ └──────────────┘ └─────────────┘  │
//  *   │              │  ─── Pipeline Preview ──────────────────────────────  │
//  *   └──────────────┴──────────────────────────────────────────────────────┘
//  *
//  * Key behaviours:
//  *  - Enrichment is OPTIONAL. Empty enrichment steps array is fully valid.
//  *  - Platform palette shows connected (✓) vs not-connected (⚠) status.
//  *  - Save is BLOCKED when enabled steps have no API key (with clear toast).
//  *  - Free sources (AI Web Search, LinkedIn) never need a key.
//  *  - Run dialog shows ICP selector + LLM config selector + Dry Run toggle.
//  *  - After clicking Run the dialog switches to a live RunMonitor that polls
//  *    GET /flows/runs/{run_id} every 2 seconds until terminal state.
//  *  - View toggle: "Form View" (3-card JSON editors) vs "Visual Builder" (dnd-kit).
//  *
//  * Backend step format: { "platform": "apollo", "enabled": true, "order": 0 }
//  * The parseSteps() helper also accepts legacy keys: provider, key, type.
//  */

// import {
//   useCallback,
//   useEffect,
//   useMemo,
//   useRef,
//   useState,
// } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   DndContext,
//   closestCenter,
//   KeyboardSensor,
//   PointerSensor,
//   useSensor,
//   useSensors,
// } from "@dnd-kit/core";
// import type { DragEndEvent } from "@dnd-kit/core";
// import {
//   SortableContext,
//   sortableKeyboardCoordinates,
//   useSortable,
//   verticalListSortingStrategy,
//   arrayMove,
// } from "@dnd-kit/sortable";
// import { CSS } from "@dnd-kit/utilities";
// import {
//   Activity,
//   AlertCircle,
//   ArrowRight,
//   BarChart2,
//   Brain,
//   Building2,
//   Ban,
  
//   CheckCircle2,
//   ChevronDown,
//   ChevronUp,
//   Copy,
//   Download,
  
//   GripVertical,
//   Inbox,
//   Layers,
//   Loader2,
//   Mail,
//   Pencil,
//   Plus,
//   PlayCircle,
//   RefreshCw,
//   Save,
//   Search,
//   Settings2,
//   ShieldCheck,
//   Sparkles,
//   Star,
//   StarOff,
//   Trash2,
//   Upload,
//   Workflow,
//   X,
//   XCircle,
//   Zap,
// } from "lucide-react";
// import { toast } from "sonner";

// import { flowsApi, integrationConfigApi, http } from "@/services/apiClient";
// import type {
//   ProspectingFlow,
//   ProspectingFlowInput,
//   TenantIntegration,
// } from "@/types/common";
// import { Badge } from "@/components/ui/badge";
// import { Button } from "@/components/ui/button";
// import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from "@/components/ui/select";
// import { Skeleton } from "@/components/ui/skeleton";
// import { Switch } from "@/components/ui/switch";
// import { Textarea } from "@/components/ui/textarea";
// import {
//   Tooltip,
//   TooltipContent,
//   TooltipProvider,
//   TooltipTrigger,
// } from "@/components/ui/tooltip";
// import { Separator } from "@/components/ui/separator";
// import { cn } from "@/lib/utils";

// // ─────────────────────────────────────────────────────────────────────────────
// // Platform registry
// // ─────────────────────────────────────────────────────────────────────────────

// interface PlatformMeta {
//   key: string;
//   label: string;
//   canSource: boolean;
//   canEnrich: boolean;
//   free: boolean; // free = no API key required
//   badgeColor: string; // Tailwind classes for the badge chip
//   sourceFields: { key: string; label: string; placeholder: string }[];
//   enrichFields: { key: string; label: string }[];
// }

// const PLATFORM_META: Record<string, PlatformMeta> = {
//   ai_web_search: {
//     key: "ai_web_search",
//     label: "AI Web Search",
//     canSource: true,
//     canEnrich: false,
//     free: true,
//     badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
//     sourceFields: [
//       { key: "query", label: "Search Query", placeholder: "CTO fintech series B" },
//     ],
//     enrichFields: [],
//   },
//   web_search: {
//     key: "web_search",
//     label: "AI Web Search",
//     canSource: true,
//     canEnrich: false,
//     free: true,
//     badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
//     sourceFields: [
//       { key: "query", label: "Search Query", placeholder: "CTO fintech series B" },
//     ],
//     enrichFields: [],
//   },
//   linkedin: {
//     key: "linkedin",
//     label: "LinkedIn",
//     canSource: true,
//     canEnrich: false,
//     free: true,
//     badgeColor: "bg-sky-100 text-sky-700 border-sky-200",
//     sourceFields: [
//       { key: "job_title", label: "Job Title", placeholder: "Chief Technology Officer" },
//       { key: "industry", label: "Industry", placeholder: "SaaS" },
//       { key: "location", label: "Location", placeholder: "San Francisco, CA" },
//     ],
//     enrichFields: [],
//   },
//   apollo: {
//     key: "apollo",
//     label: "Apollo.io",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-blue-100 text-blue-700 border-blue-200",
//     sourceFields: [
//       { key: "person_titles", label: "Job Titles", placeholder: "CTO, VP Engineering" },
//       { key: "q_keywords", label: "Keywords", placeholder: "series A SaaS" },
//       { key: "organization_locations", label: "Locations", placeholder: "San Francisco, CA" },
//     ],
//     enrichFields: [
//       { key: "email", label: "Email" },
//       { key: "phone", label: "Phone" },
//       { key: "linkedin", label: "LinkedIn URL" },
//     ],
//   },
//   zoominfo: {
//     key: "zoominfo",
//     label: "ZoomInfo",
//     canSource: true,
//     canEnrich: false,
//     free: false,
//     badgeColor: "bg-indigo-100 text-indigo-700 border-indigo-200",
//     sourceFields: [
//       { key: "jobTitle", label: "Job Title", placeholder: "Chief Technology Officer" },
//       { key: "companyIndustry", label: "Industry", placeholder: "Software" },
//       { key: "employees", label: "Employees", placeholder: "50-200" },
//     ],
//     enrichFields: [],
//   },
//   clearbit: {
//     key: "clearbit",
//     label: "Clearbit",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-teal-100 text-teal-700 border-teal-200",
//     sourceFields: [
//       { key: "query", label: "Company", placeholder: "acme.com" },
//     ],
//     enrichFields: [
//       { key: "company_size", label: "Company Size" },
//       { key: "revenue", label: "Revenue" },
//       { key: "tech_stack", label: "Tech Stack" },
//       { key: "industry", label: "Industry" },
//     ],
//   },
//   hunter: {
//     key: "hunter",
//     label: "Hunter.io",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-amber-100 text-amber-700 border-amber-200",
//     sourceFields: [
//       { key: "domain", label: "Domain", placeholder: "acme.com" },
//     ],
//     enrichFields: [
//       { key: "email", label: "Email" },
//       { key: "email_pattern", label: "Email Pattern" },
//     ],
//   },
//   lusha: {
//     key: "lusha",
//     label: "Lusha",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-rose-100 text-rose-700 border-rose-200",
//     sourceFields: [
//       { key: "company_name", label: "Company", placeholder: "Acme Inc" },
//     ],
//     enrichFields: [
//       { key: "email", label: "Email" },
//       { key: "phone", label: "Phone" },
//     ],
//   },
//   kaspr: {
//     key: "kaspr",
//     label: "Kaspr",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-pink-100 text-pink-700 border-pink-200",
//     sourceFields: [
//       { key: "query", label: "Query", placeholder: "CTO Acme" },
//     ],
//     enrichFields: [
//       { key: "email", label: "Email" },
//       { key: "phone", label: "Phone" },
//     ],
//   },
//   clay: {
//     key: "clay",
//     label: "Clay",
//     canSource: true,
//     canEnrich: false,
//     free: false,
//     badgeColor: "bg-orange-100 text-orange-700 border-orange-200",
//     sourceFields: [
//       { key: "table_name", label: "Table Name", placeholder: "my-icp-table" },
//     ],
//     enrichFields: [],
//   },
//   email_waterfall: {
//     key: "email_waterfall",
//     label: "Email Waterfall",
//     canSource: false,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-emerald-100 text-emerald-700 border-emerald-200",
//     sourceFields: [],
//     enrichFields: [
//       { key: "email", label: "Email" },
//     ],
//   },
// };

// function getMeta(key: string): PlatformMeta {
//   return (
//     PLATFORM_META[key] ?? {
//       key,
//       label: key,
//       canSource: false,
//       canEnrich: false,
//       free: false,
//       badgeColor: "bg-gray-100 text-gray-700 border-gray-200",
//       sourceFields: [],
//       enrichFields: [],
//     }
//   );
// }

// const ALL_SOURCE_KEYS = Object.values(PLATFORM_META)
//   .filter((m) => m.canSource)
//   .map((m) => m.key)
//   .filter((k) => k !== "web_search"); // deduplicate alias

// const ALL_ENRICH_KEYS = Object.values(PLATFORM_META)
//   .filter((m) => m.canEnrich)
//   .map((m) => m.key);

// // ─────────────────────────────────────────────────────────────────────────────
// // Step + QualityGates types
// // ─────────────────────────────────────────────────────────────────────────────

// interface SourceStep {
//   platform: string;
//   enabled: boolean;
//   priority: number;
//   queryOverrides: Record<string, string>;
// }

// interface EnrichmentStep {
//   platform: string;
//   enabled: boolean;
//   priority: number;
//   targetFields: string[];
//   fallbackTo: string | null;
// }

// interface QualityGates {
//   requireEmail: boolean;
//   requireVerifiedEmail: boolean;
//   requireCompanySize: boolean;
//   minCompanySize: number;
//   llmScoreThreshold: number;
//   excludeDomains: string[];
// }

// const DEFAULT_GATES: QualityGates = {
//   requireEmail: true,
//   requireVerifiedEmail: false,
//   requireCompanySize: false,
//   minCompanySize: 10,
//   llmScoreThreshold: 0.6,
//   excludeDomains: ["gmail.com", "yahoo.com", "hotmail.com"],
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // EditableFlow — parsed editor state
// // ─────────────────────────────────────────────────────────────────────────────

// interface EditableFlow {
//   id: string | null;
//   name: string;
//   description: string;
//   isDefault: boolean;
//   isActive: boolean;
//   isTemplate: boolean;
//   sourceSteps: SourceStep[];
//   enrichmentSteps: EnrichmentStep[];
//   qualityGates: QualityGates;
// }

// function parseStepsFromRaw(raw: unknown): SourceStep[] | EnrichmentStep[] {
//   if (!raw) return [];
//   try {
//     const arr = Array.isArray(raw) ? raw : JSON.parse(String(raw));
//     return (arr as Record<string, unknown>[]).map((s, i) => ({
//       platform: String(s.platform ?? s.provider ?? s.key ?? s.type ?? ""),
//       enabled: s.enabled !== false,
//       priority: typeof s.priority === "number" ? s.priority : typeof s.order === "number" ? s.order : i,
//       queryOverrides: (s.queryOverrides as Record<string, string>) ?? {},
//       targetFields: Array.isArray(s.targetFields) ? (s.targetFields as string[]) : [],
//       fallbackTo: (s.fallbackTo as string | null) ?? null,
//     }));
//   } catch {
//     return [];
//   }
// }

// function parseGates(raw: unknown): QualityGates {
//   if (!raw) return { ...DEFAULT_GATES };
//   try {
//     const parsed =
//       typeof raw === "object" && !Array.isArray(raw)
//         ? raw
//         : JSON.parse(String(raw));
//     return { ...DEFAULT_GATES, ...(parsed as Partial<QualityGates>) };
//   } catch {
//     return { ...DEFAULT_GATES };
//   }
// }

// function flowToEditable(f: ProspectingFlow): EditableFlow {
//   return {
//     id: f.id,
//     name: f.name,
//     description: f.description ?? "",
//     isDefault: f.isDefault,
//     isActive: f.isActive,
//     isTemplate: f.isTemplate,
//     sourceSteps: parseStepsFromRaw(f.sourceSteps) as SourceStep[],
//     enrichmentSteps: parseStepsFromRaw(f.enrichmentSteps) as EnrichmentStep[],
//     qualityGates: parseGates(f.qualityGates),
//   };
// }

// function newEditable(): EditableFlow {
//   return {
//     id: null,
//     name: "Untitled Flow",
//     description: "",
//     isDefault: false,
//     isActive: true,
//     isTemplate: false,
//     sourceSteps: [],
//     enrichmentSteps: [],
//     qualityGates: { ...DEFAULT_GATES },
//   };
// }

// function editableToInput(e: EditableFlow): ProspectingFlowInput {
//   const serializeSourceSteps = e.sourceSteps.map((s, i) => ({
//     platform: s.platform,
//     enabled: s.enabled,
//     order: i,
//     priority: i,
//     queryOverrides: s.queryOverrides,
//   }));
//   const serializeEnrichSteps = e.enrichmentSteps.map((s, i) => ({
//     platform: s.platform,
//     enabled: s.enabled,
//     order: i,
//     priority: i,
//     targetFields: s.targetFields,
//     fallbackTo: s.fallbackTo,
//   }));
//   return {
//     name: e.name.trim(),
//     description: e.description.trim() || null,
//     isDefault: e.isDefault,
//     isActive: e.isActive,
//     isTemplate: e.isTemplate,
//     sourceSteps: serializeSourceSteps as unknown as Record<string, unknown>[],
//     enrichmentSteps: serializeEnrichSteps as unknown as Record<string, unknown>[],
//     qualityGates: e.qualityGates as unknown as Record<string, unknown>,
//   };
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // connectedMap helper
// // ─────────────────────────────────────────────────────────────────────────────

// function buildConnectedMap(integrations: TenantIntegration[]): Record<string, boolean> {
//   const m: Record<string, boolean> = {};
//   for (const i of integrations) {
//     m[i.platform] = !!(i.isActive && (i.apiKey || i.key_source === "platform"));
//   }
//   // Free sources are always "connected"
//   m["ai_web_search"] = true;
//   m["web_search"] = true;
//   m["linkedin"] = m["linkedin"] ?? true; // treat as free unless explicitly disconnected
//   return m;
// }

// function isConnected(platform: string, connectedMap: Record<string, boolean>): boolean {
//   const meta = getMeta(platform);
//   if (meta.free) return true;
//   return connectedMap[platform] ?? false;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Validation — block save when enabled steps lack API keys
// // ─────────────────────────────────────────────────────────────────────────────

// function findUnconnectedEnabledSteps(
//   draft: EditableFlow,
//   connectedMap: Record<string, boolean>,
// ): string[] {
//   const missing = new Set<string>();
//   for (const s of draft.sourceSteps) {
//     if (!s.enabled) continue;
//     if (!isConnected(s.platform, connectedMap)) missing.add(getMeta(s.platform).label);
//   }
//   for (const s of draft.enrichmentSteps) {
//     if (!s.enabled) continue;
//     if (!isConnected(s.platform, connectedMap)) missing.add(getMeta(s.platform).label);
//   }
//   return Array.from(missing).sort();
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // ICP profile lite
// // ─────────────────────────────────────────────────────────────────────────────

// interface IcpLite {
//   id: string;
//   name: string;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Flow Templates
// // ─────────────────────────────────────────────────────────────────────────────

// interface FlowTemplate {
//   id: string;
//   name: string;
//   description: string;
//   source_platforms: string[];
//   enrichment_platforms: string[];
//   gate_config: Partial<QualityGates>;
//   gate_strictness: string;
//   recommended_for: string;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Run-monitor types
// // ─────────────────────────────────────────────────────────────────────────────

// interface FlowRunStep {
//   id: string;
//   kind: string;
//   stepKey: string;
//   status: string;
//   durationMs?: number | null;
//   metrics?: unknown;
//   errorMessage?: string | null;
// }

// interface FlowRunDetail {
//   id: string;
//   status: string;
//   stats?: unknown;
//   importedProspectIds?: unknown;
//   errorMessage?: string | null;
//   steps?: FlowRunStep[];
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: GateRow
// // ─────────────────────────────────────────────────────────────────────────────

// function GateRow({
//   icon,
//   label,
//   description,
//   checked,
//   onCheckedChange,
// }: {
//   icon: React.ReactNode;
//   label: string;
//   description: string;
//   checked: boolean;
//   onCheckedChange: (v: boolean) => void;
// }) {
//   return (
//     <div className="flex items-center justify-between">
//       <div className="flex items-center gap-2">
//         <span className="text-muted-foreground">{icon}</span>
//         <div>
//           <p className="text-sm font-medium leading-none">{label}</p>
//           <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
//         </div>
//       </div>
//       <Switch checked={checked} onCheckedChange={onCheckedChange} />
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: QualityGatesCard
// // ─────────────────────────────────────────────────────────────────────────────

// function QualityGatesCard({
//   gates,
//   onChange,
// }: {
//   gates: QualityGates;
//   onChange: (patch: Partial<QualityGates>) => void;
// }) {
//   const [domainInput, setDomainInput] = useState("");

//   function addDomain() {
//     const d = domainInput.trim().toLowerCase().replace(/^@/, "");
//     if (!d) return;
//     if (gates.excludeDomains.includes(d)) {
//       setDomainInput("");
//       return;
//     }
//     onChange({ excludeDomains: [...gates.excludeDomains, d] });
//     setDomainInput("");
//   }

//   return (
//     <Card>
//       <CardHeader className="pb-3">
//         <CardTitle className="text-sm flex items-center gap-2">
//           <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-red-700 text-[11px] font-bold">3</span>
//           Quality Gates
//         </CardTitle>
//         <CardDescription className="text-xs">
//           Auto-reject prospects that don&apos;t meet your quality bar.
//         </CardDescription>
//       </CardHeader>
//       <CardContent className="space-y-3">
//         <GateRow
//           icon={<Mail className="h-4 w-4" />}
//           label="Require email"
//           description="Reject prospects without an email address"
//           checked={gates.requireEmail}
//           onCheckedChange={(v) => onChange({ requireEmail: v })}
//         />
//         <Separator />
//         <GateRow
//           icon={<ShieldCheck className="h-4 w-4" />}
//           label="Require verified email"
//           description="Reject prospects whose email failed validation"
//           checked={gates.requireVerifiedEmail}
//           onCheckedChange={(v) => onChange({ requireVerifiedEmail: v })}
//         />
//         <Separator />
//         <div className="space-y-2">
//           <GateRow
//             icon={<Building2 className="h-4 w-4" />}
//             label="Minimum company size"
//             description="Reject prospects from companies below this employee count"
//             checked={gates.requireCompanySize}
//             onCheckedChange={(v) => onChange({ requireCompanySize: v })}
//           />
//           {gates.requireCompanySize && (
//             <div className="pl-7 flex items-center gap-2">
//               <Input
//                 type="number"
//                 min={0}
//                 value={gates.minCompanySize}
//                 onChange={(e) =>
//                   onChange({ minCompanySize: Math.max(0, Number(e.target.value) || 0) })
//                 }
//                 className="h-7 w-24 text-xs"
//               />
//               <span className="text-xs text-muted-foreground">employees minimum</span>
//             </div>
//           )}
//         </div>
//         <Separator />
//         <div className="space-y-2">
//           <div className="flex items-center justify-between">
//             <div className="flex items-center gap-2">
//               <Brain className="h-4 w-4 text-primary" />
//               <div>
//                 <p className="text-sm font-medium leading-none">LLM score threshold</p>
//                 <p className="text-xs text-muted-foreground mt-0.5">
//                   Reject prospects scoring below this ICP-fit score
//                 </p>
//               </div>
//             </div>
//             <Badge variant="outline" className="font-mono">
//               {gates.llmScoreThreshold.toFixed(2)}
//             </Badge>
//           </div>
//           <input
//             type="range"
//             min={0}
//             max={1}
//             step={0.05}
//             value={gates.llmScoreThreshold}
//             onChange={(e) => onChange({ llmScoreThreshold: Number(e.target.value) })}
//             className="w-full accent-primary"
//           />
//           <div className="flex justify-between text-[10px] text-muted-foreground">
//             <span>0.00 (off)</span>
//             <span>0.50</span>
//             <span>1.00 (strict)</span>
//           </div>
//         </div>
//         <Separator />
//         <div className="space-y-2">
//           <div className="flex items-center gap-2">
//             <Ban className="h-4 w-4" />
//             <div>
//               <p className="text-sm font-medium leading-none">Exclude domains</p>
//               <p className="text-xs text-muted-foreground mt-0.5">
//                 Reject prospects with these email domains
//               </p>
//             </div>
//           </div>
//           <div className="pl-7 space-y-2">
//             <div className="flex flex-wrap gap-1.5">
//               {gates.excludeDomains.length === 0 && (
//                 <span className="text-xs text-muted-foreground">No domains excluded.</span>
//               )}
//               {gates.excludeDomains.map((d) => (
//                 <Badge key={d} variant="secondary" className="text-xs gap-1 pr-1">
//                   {d}
//                   <button
//                     onClick={() =>
//                       onChange({ excludeDomains: gates.excludeDomains.filter((x) => x !== d) })
//                     }
//                     className="ml-0.5 hover:text-destructive"
//                   >
//                     <X className="h-3 w-3" />
//                   </button>
//                 </Badge>
//               ))}
//             </div>
//             <div className="flex gap-1.5">
//               <Input
//                 value={domainInput}
//                 onChange={(e) => setDomainInput(e.target.value)}
//                 onKeyDown={(e) => {
//                   if (e.key === "Enter") {
//                     e.preventDefault();
//                     addDomain();
//                   }
//                 }}
//                 placeholder="gmail.com"
//                 className="h-7 text-xs flex-1"
//               />
//               <Button variant="outline" size="sm" className="h-7 px-2" onClick={addDomain}>
//                 <Plus className="h-3.5 w-3.5" />
//               </Button>
//             </div>
//           </div>
//         </div>
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: SourceStepsCard (Form View)
// // ─────────────────────────────────────────────────────────────────────────────

// function SourceStepsCard({
//   steps,
//   connectedMap,
//   onChange,
// }: {
//   steps: SourceStep[];
//   connectedMap: Record<string, boolean>;
//   onChange: (steps: SourceStep[]) => void;
// }) {
//   const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

//   function update(idx: number, patch: Partial<SourceStep>) {
//     const next = steps.map((s, i) => (i === idx ? { ...s, ...patch } : s));
//     onChange(next);
//   }

//   function addStep(platform: string) {
//     const meta = getMeta(platform);
//     const queryOverrides: Record<string, string> = {};
//     for (const f of meta.sourceFields) queryOverrides[f.key] = "";
//     onChange([
//       ...steps,
//       { platform, enabled: true, priority: steps.length + 1, queryOverrides },
//     ]);
//     setExpandedIdx(steps.length);
//   }

//   function removeStep(idx: number) {
//     const next = steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, priority: i + 1 }));
//     onChange(next);
//     setExpandedIdx(null);
//   }

//   function moveStep(idx: number, dir: -1 | 1) {
//     const ni = idx + dir;
//     if (ni < 0 || ni >= steps.length) return;
//     const next = [...steps];
//     [next[idx], next[ni]] = [next[ni], next[idx]];
//     onChange(next.map((s, i) => ({ ...s, priority: i + 1 })));
//     setExpandedIdx(ni);
//   }

//   const available = ALL_SOURCE_KEYS.filter((k) => !steps.some((s) => s.platform === k));

//   return (
//     <Card>
//       <CardHeader className="pb-3">
//         <CardTitle className="text-sm flex items-center gap-2">
//           <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary text-[11px] font-bold">1</span>
//           Source Steps
//         </CardTitle>
//         <CardDescription className="text-xs">
//           Search platforms in priority order. Only enabled + connected platforms run.
//         </CardDescription>
//       </CardHeader>
//       <CardContent className="space-y-2">
//         {steps.length === 0 && (
//           <p className="text-xs text-muted-foreground text-center py-4">
//             No source steps. Add a platform below to start sourcing prospects.
//           </p>
//         )}
//         {steps.map((step, idx) => {
//           const meta = getMeta(step.platform);
//           const connected = isConnected(step.platform, connectedMap);
//           const isExpanded = expandedIdx === idx;
//           return (
//             <div key={`${step.platform}-${idx}`} className="rounded-md border">
//               <div className="flex items-center gap-1.5 p-2 flex-wrap">
//                 <GripVertical className="h-4 w-4 text-muted-foreground/50 shrink-0" />
//                 <span className="text-xs font-medium text-muted-foreground w-4 shrink-0">{idx + 1}</span>
//                 <Badge variant="outline" className={cn(meta.badgeColor, "shrink-0")}>
//                   {meta.label}
//                 </Badge>
//                 {!connected && (
//                   <Tooltip>
//                     <TooltipTrigger asChild>
//                       <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
//                     </TooltipTrigger>
//                     <TooltipContent>Not connected — add an API key in Integrations</TooltipContent>
//                   </Tooltip>
//                 )}
//                 {connected && !meta.free && (
//                   <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
//                 )}
//                 {meta.free && (
//                   <span className="text-[10px] text-green-600 font-medium shrink-0">free</span>
//                 )}
//                 <div className="flex-1 min-w-0" />
//                 <div className="flex items-center gap-1 shrink-0">
//                   <Switch
//                     checked={step.enabled}
//                     onCheckedChange={(v) => update(idx, { enabled: v })}
//                   />
//                   <Button
//                     variant="ghost" size="icon" className="h-7 w-7"
//                     disabled={idx === 0}
//                     onClick={() => moveStep(idx, -1)}
//                   >
//                     <ChevronUp className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button
//                     variant="ghost" size="icon" className="h-7 w-7"
//                     disabled={idx === steps.length - 1}
//                     onClick={() => moveStep(idx, 1)}
//                   >
//                     <ChevronDown className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button
//                     variant="ghost" size="icon" className="h-7 w-7"
//                     onClick={() => setExpandedIdx(isExpanded ? null : idx)}
//                   >
//                     <Settings2 className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button
//                     variant="ghost" size="icon" className="h-7 w-7 text-destructive"
//                     onClick={() => removeStep(idx)}
//                   >
//                     <Trash2 className="h-3.5 w-3.5" />
//                   </Button>
//                 </div>
//               </div>
//               {isExpanded && meta.sourceFields.length > 0 && (
//                 <div className="border-t px-3 pb-3 pt-2.5 space-y-2 bg-muted/30">
//                   <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
//                     Search Overrides
//                   </p>
//                   {meta.sourceFields.map((field) => (
//                     <div key={field.key} className="grid grid-cols-[110px_1fr] items-center gap-2">
//                       <Label className="text-xs text-muted-foreground">{field.label}</Label>
//                       <Input
//                         value={step.queryOverrides[field.key] ?? ""}
//                         onChange={(e) =>
//                           update(idx, {
//                             queryOverrides: { ...step.queryOverrides, [field.key]: e.target.value },
//                           })
//                         }
//                         placeholder={field.placeholder}
//                         className="h-7 text-xs"
//                       />
//                     </div>
//                   ))}
//                   {!connected && (
//                     <p className="text-[11px] text-amber-600 flex items-center gap-1 pt-1">
//                       <AlertCircle className="h-3 w-3" /> Connect this platform in Integrations to use it.
//                     </p>
//                   )}
//                 </div>
//               )}
//             </div>
//           );
//         })}

//         {available.length > 0 && (
//           <Select onValueChange={addStep}>
//             <SelectTrigger className="h-8 text-xs mt-2">
//               <SelectValue placeholder="+ Add source platform" />
//             </SelectTrigger>
//             <SelectContent>
//               {available.map((k) => {
//                 const meta = getMeta(k);
//                 const connected = isConnected(k, connectedMap);
//                 return (
//                   <SelectItem key={k} value={k} className="text-xs">
//                     {meta.label}
//                     {meta.free ? " (free)" : connected ? " ✓" : " (not connected)"}
//                   </SelectItem>
//                 );
//               })}
//             </SelectContent>
//           </Select>
//         )}
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: EnrichmentStepsCard (Form View — OPTIONAL)
// // ─────────────────────────────────────────────────────────────────────────────

// function EnrichmentStepsCard({
//   steps,
//   connectedMap,
//   onChange,
// }: {
//   steps: EnrichmentStep[];
//   connectedMap: Record<string, boolean>;
//   onChange: (steps: EnrichmentStep[]) => void;
// }) {
//   const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

//   function update(idx: number, patch: Partial<EnrichmentStep>) {
//     const next = steps.map((s, i) => (i === idx ? { ...s, ...patch } : s));
//     onChange(next);
//   }

//   function addStep(platform: string) {
//     const meta = getMeta(platform);
//     onChange([
//       ...steps,
//       {
//         platform,
//         enabled: true,
//         priority: steps.length + 1,
//         targetFields: meta.enrichFields.map((f) => f.key),
//         fallbackTo: null,
//       },
//     ]);
//     setExpandedIdx(steps.length);
//   }

//   function removeStep(idx: number) {
//     const next = steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, priority: i + 1 }));
//     onChange(next);
//     setExpandedIdx(null);
//   }

//   function moveStep(idx: number, dir: -1 | 1) {
//     const ni = idx + dir;
//     if (ni < 0 || ni >= steps.length) return;
//     const next = [...steps];
//     [next[idx], next[ni]] = [next[ni], next[idx]];
//     onChange(next.map((s, i) => ({ ...s, priority: i + 1 })));
//     setExpandedIdx(ni);
//   }

//   function toggleField(idx: number, fieldKey: string) {
//     const step = steps[idx];
//     const has = step.targetFields.includes(fieldKey);
//     const next = has
//       ? step.targetFields.filter((f) => f !== fieldKey)
//       : [...step.targetFields, fieldKey];
//     update(idx, { targetFields: next });
//   }

//   const available = ALL_ENRICH_KEYS.filter((k) => !steps.some((s) => s.platform === k));
//   const fallbackPlatforms = ALL_ENRICH_KEYS;

//   return (
//     <Card>
//       <CardHeader className="pb-3">
//         <CardTitle className="text-sm flex items-center gap-2">
//           <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-[11px] font-bold">2</span>
//           Enrichment Steps
//           <span className="ml-auto text-[10px] text-muted-foreground font-normal">optional</span>
//         </CardTitle>
//         <CardDescription className="text-xs">
//           Fill prospect fields in order. If a step fails, fall back to the next platform.{" "}
//           <strong>Leave empty to skip enrichment.</strong>
//         </CardDescription>
//       </CardHeader>
//       <CardContent className="space-y-2">
//         {steps.length === 0 && (
//           <p className="text-xs text-muted-foreground text-center py-4 border border-dashed rounded-md">
//             No enrichment steps — flow will run without enrichment. Add a platform below to enable.
//           </p>
//         )}
//         {steps.map((step, idx) => {
//           const meta = getMeta(step.platform);
//           const connected = isConnected(step.platform, connectedMap);
//           const isExpanded = expandedIdx === idx;
//           return (
//             <div key={`${step.platform}-${idx}`} className="rounded-md border">
//               <div className="flex items-center gap-1.5 p-2 flex-wrap">
//                 <GripVertical className="h-4 w-4 text-muted-foreground/50 shrink-0" />
//                 <span className="text-xs font-medium text-muted-foreground w-4 shrink-0">{idx + 1}</span>
//                 <Badge variant="outline" className={cn(meta.badgeColor, "shrink-0")}>
//                   {meta.label}
//                 </Badge>
//                 {!connected && (
//                   <Tooltip>
//                     <TooltipTrigger asChild>
//                       <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
//                     </TooltipTrigger>
//                     <TooltipContent>Not connected</TooltipContent>
//                   </Tooltip>
//                 )}
//                 {connected && <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />}
//                 {step.fallbackTo && (
//                   <Badge variant="secondary" className="text-[10px] py-0 h-4 shrink-0">
//                     ↳ {getMeta(step.fallbackTo).label}
//                   </Badge>
//                 )}
//                 <div className="flex-1 min-w-0" />
//                 <div className="flex items-center gap-1 shrink-0">
//                   <Switch
//                     checked={step.enabled}
//                     onCheckedChange={(v) => update(idx, { enabled: v })}
//                   />
//                   <Button variant="ghost" size="icon" className="h-7 w-7" disabled={idx === 0} onClick={() => moveStep(idx, -1)}>
//                     <ChevronUp className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button variant="ghost" size="icon" className="h-7 w-7" disabled={idx === steps.length - 1} onClick={() => moveStep(idx, 1)}>
//                     <ChevronDown className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setExpandedIdx(isExpanded ? null : idx)}>
//                     <Settings2 className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => removeStep(idx)}>
//                     <Trash2 className="h-3.5 w-3.5" />
//                   </Button>
//                 </div>
//               </div>
//               {isExpanded && (
//                 <div className="border-t px-3 pb-3 pt-2.5 space-y-3 bg-muted/30">
//                   {meta.enrichFields.length > 0 && (
//                     <div>
//                       <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide mb-1.5">
//                         Target Fields
//                       </p>
//                       <div className="flex flex-wrap gap-1.5">
//                         {meta.enrichFields.map((field) => {
//                           const checked = step.targetFields.includes(field.key);
//                           return (
//                             <label key={field.key} className="flex items-center gap-1 text-xs cursor-pointer">
//                               <Switch
//                                 checked={checked}
//                                 onCheckedChange={() => toggleField(idx, field.key)}
//                                 className="scale-75"
//                               />
//                               {field.label}
//                             </label>
//                           );
//                         })}
//                       </div>
//                     </div>
//                   )}
//                   <div className="grid grid-cols-[110px_1fr] items-center gap-2">
//                     <Label className="text-xs text-muted-foreground">Fallback to</Label>
//                     <Select
//                       value={step.fallbackTo ?? "__none__"}
//                       onValueChange={(v) => update(idx, { fallbackTo: v === "__none__" ? null : v })}
//                     >
//                       <SelectTrigger className="h-7 text-xs">
//                         <SelectValue />
//                       </SelectTrigger>
//                       <SelectContent>
//                         <SelectItem value="__none__" className="text-xs">None</SelectItem>
//                         {fallbackPlatforms
//                           .filter((p) => p !== step.platform)
//                           .map((p) => (
//                             <SelectItem key={p} value={p} className="text-xs">
//                               {getMeta(p).label}
//                             </SelectItem>
//                           ))}
//                       </SelectContent>
//                     </Select>
//                   </div>
//                 </div>
//               )}
//             </div>
//           );
//         })}

//         {available.length > 0 && (
//           <Select onValueChange={addStep}>
//             <SelectTrigger className="h-8 text-xs mt-2">
//               <SelectValue placeholder="+ Add enrichment platform" />
//             </SelectTrigger>
//             <SelectContent>
//               {available.map((k) => {
//                 const meta = getMeta(k);
//                 const connected = isConnected(k, connectedMap);
//                 return (
//                   <SelectItem key={k} value={k} className="text-xs">
//                     {meta.label}{connected ? " ✓" : " (not connected)"}
//                   </SelectItem>
//                 );
//               })}
//             </SelectContent>
//           </Select>
//         )}
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: FlowSummary (Pipeline preview under Form View)
// // ─────────────────────────────────────────────────────────────────────────────

// function FlowSummary({
//   draft,
//   connectedMap,
// }: {
//   draft: EditableFlow;
//   connectedMap: Record<string, boolean>;
// }) {
//   const activeSources = draft.sourceSteps.filter((s) => s.enabled);
//   const activeEnrich = draft.enrichmentSteps.filter((s) => s.enabled);
//   const g = draft.qualityGates;
//   const gateCount =
//     (g.requireEmail ? 1 : 0) +
//     (g.requireVerifiedEmail ? 1 : 0) +
//     (g.requireCompanySize ? 1 : 0) +
//     (g.excludeDomains.length > 0 ? 1 : 0) +
//     (g.llmScoreThreshold > 0 ? 1 : 0);

//   return (
//     <Card>
//       <CardHeader className="pb-3">
//         <CardTitle className="text-sm flex items-center gap-2">
//           <Zap className="h-4 w-4 text-primary" /> Pipeline Preview
//         </CardTitle>
//         <CardDescription className="text-xs">
//           How prospects flow through this configuration at execution time.
//         </CardDescription>
//       </CardHeader>
//       <CardContent>
//         <div className="flex items-center gap-2 overflow-x-auto pb-2">
//           {/* Source */}
//           <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
//             <div className="flex items-center justify-between mb-2">
//               <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Source</p>
//               <Badge variant="secondary" className="text-[10px] h-4 py-0">{activeSources.length}</Badge>
//             </div>
//             <div className="space-y-1">
//               {activeSources.length === 0 && <p className="text-xs text-muted-foreground/70">No active sources</p>}
//               {activeSources.map((s) => {
//                 const meta = getMeta(s.platform);
//                 return (
//                   <div key={s.platform} className="flex items-center gap-1.5">
//                     <Badge variant="outline" className={cn("text-xs", meta.badgeColor)}>{meta.label}</Badge>
//                     {!isConnected(s.platform, connectedMap) && <AlertCircle className="h-3 w-3 text-amber-500" />}
//                   </div>
//                 );
//               })}
//             </div>
//           </div>

//           <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

//           {/* Enrich */}
//           <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
//             <div className="flex items-center justify-between mb-2">
//               <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Enrich</p>
//               <Badge variant="secondary" className="text-[10px] h-4 py-0">{activeEnrich.length}</Badge>
//             </div>
//             <div className="space-y-1">
//               {activeEnrich.length === 0 && <p className="text-xs text-muted-foreground/70">None (optional)</p>}
//               {activeEnrich.map((s) => {
//                 const meta = getMeta(s.platform);
//                 return (
//                   <div key={s.platform} className="flex items-center gap-1.5">
//                     <Badge variant="outline" className={cn("text-xs", meta.badgeColor)}>{meta.label}</Badge>
//                     {!isConnected(s.platform, connectedMap) && <AlertCircle className="h-3 w-3 text-amber-500" />}
//                   </div>
//                 );
//               })}
//             </div>
//           </div>

//           <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

//           {/* Gates */}
//           <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
//             <div className="flex items-center justify-between mb-2">
//               <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Gates</p>
//               <Badge variant="secondary" className="text-[10px] h-4 py-0">{gateCount}</Badge>
//             </div>
//             <div className="space-y-1">
//               {gateCount === 0 && <p className="text-xs text-muted-foreground/70">No gates active</p>}
//               {g.requireEmail && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">Email</Badge>}
//               {g.requireVerifiedEmail && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">Verified</Badge>}
//               {g.requireCompanySize && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">≥{g.minCompanySize} emp</Badge>}
//               {g.llmScoreThreshold > 0 && <Badge variant="outline" className="text-xs bg-violet-100 text-violet-700 border-violet-200">LLM ≥{g.llmScoreThreshold.toFixed(2)}</Badge>}
//               {g.excludeDomains.length > 0 && <Badge variant="outline" className="text-xs bg-red-100 text-red-700 border-red-200">{g.excludeDomains.length} domains</Badge>}
//             </div>
//           </div>

//           <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

//           {/* Output */}
//           <div className="rounded-lg border border-primary/40 bg-primary/5 p-3 min-w-[130px] flex-1">
//             <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Qualified Prospects</p>
//             <div className="flex items-center gap-1.5 text-primary">
//               <CheckCircle2 className="h-4 w-4" />
//               <span className="text-sm font-medium">Ready for campaign</span>
//             </div>
//           </div>
//         </div>
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: DraggableStepCard (used inside Visual Builder)
// // ─────────────────────────────────────────────────────────────────────────────

// function DraggableStepCard({
//   id,
//   platform,
//   enabled,
//   priority,
//   isEnrich,
//   connected,
//   free,
//   onToggle,
//   onRemove,
// }: {
//   id: string;
//   platform: string;
//   enabled: boolean;
//   priority: number;
//   isEnrich?: boolean;
//   connected: boolean;
//   free: boolean;
//   onToggle: (enabled: boolean) => void;
//   onRemove: () => void;
// }) {
//   const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
//   const meta = getMeta(platform);

//   return (
//     <div
//       ref={setNodeRef}
//       style={{ transform: CSS.Transform.toString(transform), transition }}
//       className={cn(
//         "group relative flex items-center gap-2 rounded-lg border bg-card p-2.5 shadow-sm transition-all",
//         isDragging && "opacity-50 shadow-lg ring-2 ring-primary/40",
//         !enabled && "opacity-60",
//         meta.badgeColor,
//         !connected && !free && "ring-1 ring-amber-300/60",
//       )}
//     >
//       <button
//         type="button"
//         className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground touch-none"
//         {...attributes}
//         {...listeners}
//       >
//         <GripVertical className="h-4 w-4" />
//       </button>
//       <Badge variant="outline" className={cn("shrink-0 font-mono text-[10px] h-5 w-5 justify-center p-0", meta.badgeColor)}>
//         {priority}
//       </Badge>
//       <div className="flex-1 min-w-0">
//         <div className="flex items-center gap-1.5">
//           <p className="text-sm font-medium truncate">{meta.label}</p>
//           {free ? (
//             <span className="text-[10px] font-medium text-green-700">free</span>
//           ) : connected ? (
//             <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-emerald-700">
//               <CheckCircle2 className="h-3 w-3" /> ✓
//             </span>
//           ) : (
//             <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-700">
//               <AlertCircle className="h-3 w-3" /> Not Connected
//             </span>
//           )}
//         </div>
//         {isEnrich && <p className="text-[10px] text-muted-foreground">Enrichment step</p>}
//       </div>
//       <Switch checked={enabled} onCheckedChange={onToggle} className="scale-75" />
//       <button
//         type="button"
//         onClick={onRemove}
//         className="text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
//         aria-label="Remove step"
//       >
//         <X className="h-3.5 w-3.5" />
//       </button>
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: VisualFlowBuilder
// // ─────────────────────────────────────────────────────────────────────────────

// function VisualFlowBuilder({
//   draft,
//   connectedMap,
//   onUpdate,
// }: {
//   draft: EditableFlow;
//   connectedMap: Record<string, boolean>;
//   onUpdate: (patch: Partial<EditableFlow>) => void;
// }) {
//   const sensors = useSensors(
//     useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
//     useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
//   );

//   const sourceItems = draft.sourceSteps.map((s, i) => ({ id: `src-${i}-${s.platform}`, ...s }));
//   const enrichItems = draft.enrichmentSteps.map((s, i) => ({ id: `enr-${i}-${s.platform}`, ...s }));

//   function handleSourceDragEnd(e: DragEndEvent) {
//     const { active, over } = e;
//     if (!over || active.id === over.id) return;
//     const oldIdx = sourceItems.findIndex((s) => s.id === active.id);
//     const newIdx = sourceItems.findIndex((s) => s.id === over.id);
//     if (oldIdx < 0 || newIdx < 0) return;
//     const reordered = arrayMove(draft.sourceSteps, oldIdx, newIdx);
//     reordered.forEach((s, i) => (s.priority = i + 1));
//     onUpdate({ sourceSteps: reordered });
//   }

//   function handleEnrichDragEnd(e: DragEndEvent) {
//     const { active, over } = e;
//     if (!over || active.id === over.id) return;
//     const oldIdx = enrichItems.findIndex((s) => s.id === active.id);
//     const newIdx = enrichItems.findIndex((s) => s.id === over.id);
//     if (oldIdx < 0 || newIdx < 0) return;
//     const reordered = arrayMove(draft.enrichmentSteps, oldIdx, newIdx);
//     reordered.forEach((s, i) => (s.priority = i + 1));
//     onUpdate({ enrichmentSteps: reordered });
//   }

//   function addSourceStep(platform: string) {
//     const meta = getMeta(platform);
//     const queryOverrides: Record<string, string> = {};
//     for (const f of meta.sourceFields) queryOverrides[f.key] = "";
//     onUpdate({
//       sourceSteps: [
//         ...draft.sourceSteps,
//         { platform, enabled: true, priority: draft.sourceSteps.length + 1, queryOverrides },
//       ],
//     });
//   }

//   function addEnrichStep(platform: string) {
//     const meta = getMeta(platform);
//     onUpdate({
//       enrichmentSteps: [
//         ...draft.enrichmentSteps,
//         {
//           platform,
//           enabled: true,
//           priority: draft.enrichmentSteps.length + 1,
//           targetFields: meta.enrichFields.map((f) => f.key),
//           fallbackTo: null,
//         },
//       ],
//     });
//   }

//   // Palettes — connected first
//   const sourcePalette = ALL_SOURCE_KEYS
//     .filter((k) => !draft.sourceSteps.some((s) => s.platform === k))
//     .sort((a, b) => {
//       const aConn = isConnected(a, connectedMap) ? 1 : 0;
//       const bConn = isConnected(b, connectedMap) ? 1 : 0;
//       return bConn - aConn;
//     });

//   const enrichPalette = ALL_ENRICH_KEYS
//     .filter((k) => !draft.enrichmentSteps.some((s) => s.platform === k))
//     .sort((a, b) => {
//       const aConn = isConnected(a, connectedMap) ? 1 : 0;
//       const bConn = isConnected(b, connectedMap) ? 1 : 0;
//       return bConn - aConn;
//     });

//   // Unconnected warning
//   const unconnectedSrc = draft.sourceSteps.filter((s) => s.enabled && !isConnected(s.platform, connectedMap));
//   const unconnectedEnr = draft.enrichmentSteps.filter((s) => s.enabled && !isConnected(s.platform, connectedMap));
//   const totalUnconn = unconnectedSrc.length + unconnectedEnr.length;

//   return (
//     <div className="space-y-4">
//       <Card>
//         <CardHeader className="pb-3">
//           <div className="flex items-center gap-2">
//             <Workflow className="h-5 w-5 text-primary" />
//             <CardTitle className="text-base">Visual Flow Builder</CardTitle>
//           </div>
//           <p className="text-xs text-muted-foreground mt-1">
//             Drag steps to reorder priority. Click in the palette to add platforms. Toggle the Switch to enable/disable a step.
//             Enrichment is optional — leave the ENRICH column empty to skip it.
//           </p>
//           {totalUnconn > 0 && (
//             <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 flex items-start gap-2">
//               <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
//               <div className="leading-relaxed">
//                 <p className="font-medium">
//                   {totalUnconn} enabled step{totalUnconn > 1 ? "s" : ""} missing API key:{" "}
//                   {Array.from(new Set([...unconnectedSrc, ...unconnectedEnr].map((s) => getMeta(s.platform).label))).join(", ")}
//                 </p>
//                 <p className="mt-0.5">
//                   Save is blocked until you toggle them off or wire the API key in{" "}
//                   <em>Setup → Integrations</em>. Free sources (AI Web Search, LinkedIn) never need a key.
//                 </p>
//               </div>
//             </div>
//           )}
//         </CardHeader>
//       </Card>

//       <div className="flex gap-4">
//         {/* Left palette */}
//         <div className="w-56 shrink-0 space-y-4">
//           <div>
//             <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
//               <Search className="h-3 w-3" /> Source Platforms
//             </p>
//             <div className="space-y-1.5">
//               {sourcePalette.length === 0 && (
//                 <p className="text-[11px] text-muted-foreground italic px-1">All sources added</p>
//               )}
//               {sourcePalette.map((k) => {
//                 const meta = getMeta(k);
//                 const connected = isConnected(k, connectedMap);
//                 return (
//                   <button
//                     key={k}
//                     type="button"
//                     onClick={() => addSourceStep(k)}
//                     className={cn(
//                       "w-full flex items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm transition-all hover:shadow-sm hover:scale-[1.02]",
//                       meta.badgeColor,
//                     )}
//                   >
//                     <Plus className="h-3.5 w-3.5 shrink-0" />
//                     <span className="truncate flex-1">{meta.label}</span>
//                     {meta.free ? (
//                       <span className="text-[10px] text-green-700">free</span>
//                     ) : connected ? (
//                       <CheckCircle2 className="h-3 w-3 text-emerald-700 shrink-0" />
//                     ) : (
//                       <AlertCircle className="h-3 w-3 text-amber-700 shrink-0" />
//                     )}
//                   </button>
//                 );
//               })}
//             </div>
//           </div>

//           <div>
//             <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
//               <Sparkles className="h-3 w-3" /> Enrichment Platforms
//               <span className="ml-auto text-muted-foreground font-normal">(optional)</span>
//             </p>
//             <div className="space-y-1.5">
//               {enrichPalette.length === 0 && (
//                 <p className="text-[11px] text-muted-foreground italic px-1">All enrichers added</p>
//               )}
//               {enrichPalette.map((k) => {
//                 const meta = getMeta(k);
//                 const connected = isConnected(k, connectedMap);
//                 return (
//                   <button
//                     key={k}
//                     type="button"
//                     onClick={() => addEnrichStep(k)}
//                     className={cn(
//                       "w-full flex items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm transition-all hover:shadow-sm hover:scale-[1.02]",
//                       meta.badgeColor,
//                     )}
//                   >
//                     <Plus className="h-3.5 w-3.5 shrink-0" />
//                     <span className="truncate flex-1">{meta.label}</span>
//                     {connected ? (
//                       <CheckCircle2 className="h-3 w-3 text-emerald-700 shrink-0" />
//                     ) : (
//                       <AlertCircle className="h-3 w-3 text-amber-700 shrink-0" />
//                     )}
//                   </button>
//                 );
//               })}
//             </div>
//           </div>
//         </div>

//         {/* Canvas */}
//         <div className="flex-1 overflow-x-auto">
//           <div className="flex gap-3 min-w-[700px]">
//             {/* SOURCE */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-violet-500">
//                   <Search className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Source</h4>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
//                 <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleSourceDragEnd}>
//                   <SortableContext items={sourceItems.map((s) => s.id)} strategy={verticalListSortingStrategy}>
//                     {sourceItems.map((s, i) => (
//                       <DraggableStepCard
//                         key={s.id}
//                         id={s.id}
//                         platform={s.platform}
//                         enabled={s.enabled}
//                         priority={s.priority}
//                         free={getMeta(s.platform).free}
//                         connected={isConnected(s.platform, connectedMap)}
//                         onToggle={(en) => {
//                           const next = [...draft.sourceSteps];
//                           next[i] = { ...next[i], enabled: en };
//                           onUpdate({ sourceSteps: next });
//                         }}
//                         onRemove={() => {
//                           const next = draft.sourceSteps.filter((_, idx) => idx !== i);
//                           next.forEach((st, idx) => (st.priority = idx + 1));
//                           onUpdate({ sourceSteps: next });
//                         }}
//                       />
//                     ))}
//                   </SortableContext>
//                 </DndContext>
//                 {sourceItems.length === 0 && (
//                   <p className="text-[11px] text-muted-foreground italic text-center py-4">
//                     No source steps. Add platforms from the palette.
//                   </p>
//                 )}
//               </div>
//             </div>

//             <div className="flex items-center pt-7">
//               <ArrowRight className="h-4 w-4 text-muted-foreground" />
//             </div>

//             {/* ENRICH */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-500">
//                   <Sparkles className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Enrich</h4>
//                 <span className="text-[10px] text-muted-foreground ml-1">(optional)</span>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
//                 <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleEnrichDragEnd}>
//                   <SortableContext items={enrichItems.map((s) => s.id)} strategy={verticalListSortingStrategy}>
//                     {enrichItems.map((s, i) => (
//                       <DraggableStepCard
//                         key={s.id}
//                         id={s.id}
//                         platform={s.platform}
//                         enabled={s.enabled}
//                         priority={s.priority}
//                         isEnrich
//                         free={false}
//                         connected={isConnected(s.platform, connectedMap)}
//                         onToggle={(en) => {
//                           const next = [...draft.enrichmentSteps];
//                           next[i] = { ...next[i], enabled: en };
//                           onUpdate({ enrichmentSteps: next });
//                         }}
//                         onRemove={() => {
//                           const next = draft.enrichmentSteps.filter((_, idx) => idx !== i);
//                           next.forEach((st, idx) => (st.priority = idx + 1));
//                           onUpdate({ enrichmentSteps: next });
//                         }}
//                       />
//                     ))}
//                   </SortableContext>
//                 </DndContext>
//                 {enrichItems.length === 0 && (
//                   <p className="text-[11px] text-muted-foreground italic text-center py-4">
//                     Empty — enrichment skipped.
//                   </p>
//                 )}
//               </div>
//             </div>

//             <div className="flex items-center pt-7">
//               <ArrowRight className="h-4 w-4 text-muted-foreground" />
//             </div>

//             {/* GATE */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-red-500">
//                   <ShieldCheck className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Gate</h4>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2.5">
//                 {(
//                   [
//                     { label: "Require Email", checked: draft.qualityGates.requireEmail, key: "requireEmail" as keyof QualityGates },
//                     { label: "Verified Email", checked: draft.qualityGates.requireVerifiedEmail, key: "requireVerifiedEmail" as keyof QualityGates },
//                   ] as Array<{ label: string; checked: boolean; key: keyof QualityGates }>
//                 ).map(({ label, checked, key }) => (
//                   <div key={key} className="flex items-center justify-between rounded-lg border bg-card p-2.5">
//                     <Label className="text-xs">{label}</Label>
//                     <Switch
//                       checked={checked as boolean}
//                       onCheckedChange={(v) => onUpdate({ qualityGates: { ...draft.qualityGates, [key]: v } })}
//                       className="scale-75"
//                     />
//                   </div>
//                 ))}
//                 <div className="rounded-lg border bg-card p-2.5">
//                   <Label className="text-xs">Min Company Size</Label>
//                   <Input
//                     type="number"
//                     value={draft.qualityGates.minCompanySize}
//                     onChange={(e) =>
//                       onUpdate({
//                         qualityGates: {
//                           ...draft.qualityGates,
//                           minCompanySize: Number(e.target.value),
//                           requireCompanySize: Number(e.target.value) > 0,
//                         },
//                       })
//                     }
//                     className="h-7 w-full text-xs mt-1"
//                   />
//                 </div>
//                 <div className="rounded-lg border bg-card p-2.5">
//                   <Label className="text-xs">LLM Threshold (0–1)</Label>
//                   <Input
//                     type="number"
//                     min={0}
//                     max={1}
//                     step={0.05}
//                     value={draft.qualityGates.llmScoreThreshold}
//                     onChange={(e) =>
//                       onUpdate({ qualityGates: { ...draft.qualityGates, llmScoreThreshold: Number(e.target.value) } })
//                     }
//                     className="h-7 w-full text-xs mt-1"
//                   />
//                 </div>
//               </div>
//             </div>

//             <div className="flex items-center pt-7">
//               <ArrowRight className="h-4 w-4 text-muted-foreground" />
//             </div>

//             {/* SCORE */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-500">
//                   <BarChart2 className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Score</h4>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
//                 <div className="rounded-lg border bg-blue-50 border-blue-200 p-2.5 text-xs text-blue-700">
//                   <p className="font-medium">ICP Fit Score</p>
//                   <p className="text-[11px] text-muted-foreground mt-0.5">Auto-computed from ICP + persona + intent signals.</p>
//                 </div>
//                 <div className="rounded-lg border bg-blue-50 border-blue-200 p-2.5 text-xs text-blue-700">
//                   <p className="font-medium">Urgency Tier</p>
//                   <p className="text-[11px] text-muted-foreground mt-0.5">TIER_1–TIER_3 based on signal recency.</p>
//                 </div>
//               </div>
//             </div>

//             <div className="flex items-center pt-7">
//               <ArrowRight className="h-4 w-4 text-muted-foreground" />
//             </div>

//             {/* IMPORT */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-500">
//                   <Download className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Import</h4>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
//                 <div className="rounded-lg border bg-emerald-50 border-emerald-200 p-2.5 text-xs text-emerald-700">
//                   <p className="font-medium">Prospect Table</p>
//                   <p className="text-[11px] text-muted-foreground mt-0.5">Surviving prospects imported with ICP + intent tags.</p>
//                 </div>
//                 <div className="rounded-lg border bg-emerald-50 border-emerald-200 p-2.5 text-xs text-emerald-700">
//                   <p className="font-medium">Fire Webhooks</p>
//                   <p className="text-[11px] text-muted-foreground mt-0.5">FLOW_RUN_COMPLETED fires to all active webhooks.</p>
//                 </div>
//               </div>
//             </div>
//           </div>
//         </div>
//       </div>

//       {/* Status summary */}
//       <Card>
//         <CardContent className="pt-4">
//           <div className="flex flex-wrap gap-3 text-xs">
//             <Badge variant="outline" className="gap-1">
//               <Search className="h-3 w-3" />
//               {draft.sourceSteps.filter((s) => s.enabled).length}/{draft.sourceSteps.length} source steps active
//             </Badge>
//             <Badge variant="outline" className="gap-1">
//               <Sparkles className="h-3 w-3" />
//               {draft.enrichmentSteps.filter((s) => s.enabled).length}/{draft.enrichmentSteps.length} enrich steps active
//             </Badge>
//             <Badge variant="outline" className="gap-1">
//               <ShieldCheck className="h-3 w-3" />
//               {[
//                 draft.qualityGates.requireEmail && "Email",
//                 draft.qualityGates.requireVerifiedEmail && "Verified",
//                 draft.qualityGates.requireCompanySize && `Size≥${draft.qualityGates.minCompanySize}`,
//                 draft.qualityGates.llmScoreThreshold > 0 && `Score≥${draft.qualityGates.llmScoreThreshold.toFixed(2)}`,
//                 (draft.qualityGates.excludeDomains?.length || 0) > 0 &&
//                   `${draft.qualityGates.excludeDomains.length} excluded`,
//               ]
//                 .filter(Boolean)
//                 .join(", ") || "No gates"}
//             </Badge>
//           </div>
//         </CardContent>
//       </Card>
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: RunMonitor (live polling inside Run dialog)
// // ─────────────────────────────────────────────────────────────────────────────

// function RunMonitor({
//   flowName,
//   runId,
// }: {
//   flowName: string;
//   runId: string;
// }) {
//   const [elapsed, setElapsed] = useState(0);
//   const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

//   const { data: run, isError } = useQuery<FlowRunDetail>({
//     queryKey: ["flow-run-monitor", runId],
//     queryFn: () => flowsApi.getRun(runId) as Promise<FlowRunDetail>,
//     refetchInterval: (query) => {
//       const s = (query.state.data as FlowRunDetail | undefined)?.status;
//       if (s === "COMPLETED" || s === "FAILED" || s === "CANCELLED") return false;
//       return 2000;
//     },
//     retry: 3,
//   });

//   useEffect(() => {
//     timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
//     return () => { if (timerRef.current) clearInterval(timerRef.current); };
//   }, []);

//   useEffect(() => {
//     if (run?.status === "COMPLETED" || run?.status === "FAILED" || run?.status === "CANCELLED") {
//       if (timerRef.current) clearInterval(timerRef.current);
//     }
//   }, [run?.status]);

//   const status = run?.status ?? "RUNNING";
//   const isTerminal = status === "COMPLETED" || status === "FAILED" || status === "CANCELLED";

//   const steps = run?.steps ?? [];

//   let stats: Record<string, unknown> = {};
//   try {
//     if (run?.stats && typeof run.stats === "object") stats = run.stats as Record<string, unknown>;
//     else if (typeof run?.stats === "string") stats = JSON.parse(run.stats as string);
//   } catch { /* ignore */ }

//   let importedCount = 0;
//   try {
//     if (Array.isArray(run?.importedProspectIds)) importedCount = (run.importedProspectIds as string[]).length;
//     else if (typeof run?.importedProspectIds === "string") importedCount = JSON.parse(run.importedProspectIds as string).length;
//   } catch { /* ignore */ }

//   const sourced = Number(stats.sourced ?? stats.source_count ?? stats.totalSourced ?? 0);
//   const deduped = Number(stats.deduped ?? stats.dedup_count ?? stats.totalDeduped ?? 0);
//   const enriched = Number(stats.enriched ?? stats.enrich_count ?? stats.totalEnriched ?? 0);
//   const gated = Number(stats.gated ?? stats.gate_count ?? stats.totalGatedOut ?? 0);
//   const imported_ = Number(stats.imported ?? importedCount ?? stats.totalImported ?? 0);

//   function fmt(s: number) {
//     if (s < 60) return `${s}s`;
//     return `${Math.floor(s / 60)}m ${s % 60}s`;
//   }

//   const statusBanner = {
//     RUNNING:   { border: "border-blue-200 bg-blue-50",   icon: <Activity className="h-4 w-4 animate-pulse" />, color: "text-blue-600",  label: "Running" },
//     COMPLETED: { border: "border-green-200 bg-green-50", icon: <CheckCircle2 className="h-4 w-4" />,           color: "text-green-600", label: "Completed" },
//     FAILED:    { border: "border-red-200 bg-red-50",     icon: <XCircle className="h-4 w-4" />,                color: "text-red-600",   label: "Failed" },
//     CANCELLED: { border: "border-gray-200 bg-gray-50",   icon: <XCircle className="h-4 w-4" />,                color: "text-gray-500",  label: "Cancelled" },
//     PENDING:   { border: "border-amber-200 bg-amber-50", icon: <Activity className="h-4 w-4 animate-pulse" />, color: "text-amber-600", label: "Pending" },
//   } as Record<string, { border: string; icon: React.ReactNode; color: string; label: string }>;

//   const sb = statusBanner[status] ?? statusBanner["RUNNING"];

//   return (
//     <div className="space-y-4">
//       {/* Header */}
//       <div className={`flex items-center gap-3 rounded-lg border p-4 ${sb.border}`}>
//         <span className={sb.color}>{sb.icon}</span>
//         <div className="flex-1 min-w-0">
//           <p className={`text-sm font-semibold ${sb.color}`}>{sb.label}</p>
//           <p className="text-xs text-muted-foreground truncate">{flowName}</p>
//         </div>
//         <div className="text-right flex-shrink-0">
//           <p className="text-xs font-mono text-muted-foreground">{fmt(elapsed)}</p>
//           <p className="text-[10px] text-muted-foreground">elapsed</p>
//         </div>
//       </div>

//       <div className="flex items-center gap-2 text-xs text-muted-foreground">
//         <span className="font-medium">Run ID:</span>
//         <span className="font-mono truncate">{runId}</span>
//       </div>

//       {/* Step rows */}
//       {steps.length > 0 ? (
//         <div className="space-y-1.5">
//           <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Steps</p>
//           {steps.map((step) => {
//             const dotColors: Record<string, string> = {
//               COMPLETED: "bg-green-500",
//               SUCCESS:   "bg-green-500",
//               RUNNING:   "bg-blue-500 animate-pulse",
//               FAILED:    "bg-red-500",
//               SKIPPED:   "bg-gray-300",
//               PENDING:   "bg-gray-200",
//             };
//             const badgeColors: Record<string, string> = {
//               COMPLETED: "bg-green-100 text-green-700",
//               SUCCESS:   "bg-green-100 text-green-700",
//               RUNNING:   "bg-blue-100 text-blue-700",
//               FAILED:    "bg-red-100 text-red-700",
//               SKIPPED:   "bg-gray-100 text-gray-500",
//               PENDING:   "bg-gray-100 text-gray-500",
//             };
//             let stepMetrics: Record<string, unknown> = {};
//             try {
//               if (step.metrics && typeof step.metrics === "object") stepMetrics = step.metrics as Record<string, unknown>;
//               else if (typeof step.metrics === "string") stepMetrics = JSON.parse(step.metrics as string);
//             } catch { /* ignore */ }
//             return (
//               <div key={step.id} className="flex items-center gap-2.5 rounded-md border px-3 py-2 text-xs">
//                 <span className={`h-2 w-2 rounded-full flex-shrink-0 ${dotColors[step.status] ?? "bg-gray-200"}`} />
//                 <span className="font-medium capitalize flex-1 truncate">
//                   {step.kind.toLowerCase()} — {step.stepKey}
//                 </span>
//                 {step.durationMs != null && <span className="text-muted-foreground">{step.durationMs}ms</span>}
//                 {stepMetrics.count !== undefined && <span className="text-muted-foreground">{String(stepMetrics.count)} results</span>}
//                 <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${badgeColors[step.status] ?? "bg-gray-100 text-gray-500"}`}>
//                   {step.status}
//                 </span>
//               </div>
//             );
//           })}
//         </div>
//       ) : !isTerminal ? (
//         <div className="flex items-center gap-3 rounded-md border border-dashed px-4 py-5 text-xs text-muted-foreground">
//           <Activity className="h-4 w-4 animate-pulse text-blue-500 flex-shrink-0" />
//           <div>
//             <p className="font-medium">Pipeline executing…</p>
//             <p>Step details will appear here as the flow progresses.</p>
//           </div>
//         </div>
//       ) : null}

//       {/* Funnel results */}
//       {isTerminal && status === "COMPLETED" && (
//         <div className="rounded-lg border bg-muted/30 p-3">
//           <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Results</p>
//           <div className="grid grid-cols-5 gap-1 text-center">
//             {[
//               { label: "Sourced",  value: sourced || "—",   color: "text-blue-600" },
//               { label: "Deduped",  value: deduped || "—",   color: "text-indigo-600" },
//               { label: "Enriched", value: enriched || "—",  color: "text-orange-600" },
//               { label: "Gated",    value: gated || "—",     color: "text-red-600" },
//               { label: "Imported", value: imported_ || "—", color: "text-green-600" },
//             ].map((item) => (
//               <div key={item.label} className="rounded-md border bg-background p-2">
//                 <p className={`text-lg font-bold ${item.color}`}>{String(item.value)}</p>
//                 <p className="text-[10px] text-muted-foreground">{item.label}</p>
//               </div>
//             ))}
//           </div>
//           {imported_ > 0 && (
//             <p className="text-xs text-green-700 mt-2 text-center font-medium">
//               ✓ {imported_} prospect{imported_ !== 1 ? "s" : ""} added to your Prospects table
//             </p>
//           )}
//         </div>
//       )}

//       {run?.errorMessage && (
//         <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
//           <p className="font-semibold mb-0.5">Error</p>
//           <p>{run.errorMessage}</p>
//         </div>
//       )}

//       {isError && (
//         <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
//           Could not fetch run status. The run may still be executing in the background.
//         </div>
//       )}

//       {!isTerminal && (
//         <div className="flex items-center gap-2 text-xs text-blue-600">
//           <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
//           Polling for updates every 2 seconds…
//         </div>
//       )}
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: RunFlowDialog
// // ─────────────────────────────────────────────────────────────────────────────

// function RunFlowDialog({
//   flow,
//   open,
//   onClose,
//   onRun,
//   isRunning,
//   activeRunId,
// }: {
//   flow: ProspectingFlow;
//   open: boolean;
//   onClose: () => void;
//   onRun: (icpProfileId: string, maxProspects: number, dryRun: boolean, llmConfigId?: string) => void;
//   isRunning: boolean;
//   activeRunId: string | null;
// }) {
//   const [selectedIcp, setSelectedIcp] = useState("");
//   const [maxProspects, setMaxProspects] = useState(10);
//   const [dryRun, setDryRun] = useState(false);
//   const [llmConfigId, setLlmConfigId] = useState("");

//   const phase = activeRunId ? "running" : "configure";

//   const { data: icpData } = useQuery({
//     queryKey: ["icp-profiles-for-run"],
//     queryFn: () =>
//       http.get<unknown>("/api/v1/icp-profiles").then((r) =>
//         Array.isArray(r) ? (r as IcpLite[]) : ((r as { items?: IcpLite[] })?.items ?? []),
//       ),
//     enabled: open && phase === "configure",
//   });
//   const icpProfiles = (icpData ?? []) as IcpLite[];

//   function handleClose() {
//     setSelectedIcp("");
//     onClose();
//   }

//   // Live monitor phase
//   if (phase === "running" && activeRunId) {
//     return (
//       <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
//         <DialogContent className="max-w-lg">
//           <DialogHeader>
//             <DialogTitle className="flex items-center gap-2">
//               <PlayCircle className="h-4 w-4 text-emerald-600" /> Flow Running
//             </DialogTitle>
//             <DialogDescription>
//               Live progress for &ldquo;{flow.name}&rdquo;. Updates every 2 seconds.
//             </DialogDescription>
//           </DialogHeader>
//           <RunMonitor flowName={flow.name} runId={activeRunId} />
//           <DialogFooter>
//             <Button variant="outline" onClick={handleClose}>Close</Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>
//     );
//   }

//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
//       <DialogContent className="max-w-md">
//         <DialogHeader>
//           <DialogTitle className="flex items-center gap-2">
//             <PlayCircle className="h-4 w-4 text-emerald-600" /> Run Flow
//           </DialogTitle>
//           <DialogDescription>
//             Execute &ldquo;{flow.name}&rdquo; against an ICP profile. Runs take ~30–60s for 10 prospects.
//           </DialogDescription>
//         </DialogHeader>
//         <div className="space-y-4 py-2">
//           <div className="space-y-2">
//             <Label>ICP Profile *</Label>
//             <Select value={selectedIcp} onValueChange={setSelectedIcp}>
//               <SelectTrigger><SelectValue placeholder="Select ICP" /></SelectTrigger>
//               <SelectContent>
//                 {icpProfiles.map((p) => (
//                   <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
//                 ))}
//                 {icpProfiles.length === 0 && (
//                   <SelectItem value="__none__" disabled>No ICP profiles found</SelectItem>
//                 )}
//               </SelectContent>
//             </Select>
//             {icpProfiles.length === 0 && (
//               <p className="text-xs text-amber-600">
//                 No ICP profiles found — create one in ICP Profiles first.
//               </p>
//             )}
//           </div>
//           <div className="grid grid-cols-2 gap-4">
//             <div className="space-y-2">
//               <Label>Max Prospects</Label>
//               <Input
//                 type="number"
//                 min={1}
//                 max={1000}
//                 value={maxProspects}
//                 onChange={(e) => setMaxProspects(Math.max(1, Number(e.target.value) || 1))}
//               />
//             </div>
//             <div className="space-y-2">
//               <Label>LLM Config (optional)</Label>
//               <Select
//                 value={llmConfigId || "__default__"}
//                 onValueChange={(v) => setLlmConfigId(v === "__default__" ? "" : v)}
//               >
//                 <SelectTrigger><SelectValue /></SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="__default__">Default (auto-select)</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>
//           </div>
//           <div className="flex items-center justify-between rounded-md border p-3">
//             <div>
//               <div className="text-sm font-medium flex items-center gap-1.5">
//                 <AlertCircle className="h-3.5 w-3.5 text-amber-500" /> Dry Run
//               </div>
//               <div className="text-[11px] text-muted-foreground">
//                 Execute the pipeline without persisting prospects (useful for testing).
//               </div>
//             </div>
//             <Switch checked={dryRun} onCheckedChange={setDryRun} />
//           </div>
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={handleClose} disabled={isRunning}>Cancel</Button>
//           <Button
//             onClick={() => onRun(selectedIcp, maxProspects, dryRun, llmConfigId || undefined)}
//             disabled={isRunning || !selectedIcp}
//             className="bg-emerald-600 hover:bg-emerald-700 text-white"
//           >
//             {isRunning ? (
//               <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Starting…</>
//             ) : (
//               <><PlayCircle className="h-4 w-4 mr-2" /> Run Flow</>
//             )}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: TemplatesDialog
// // ─────────────────────────────────────────────────────────────────────────────

// function TemplatesDialog({
//   open,
//   onClose,
//   onClone,
// }: {
//   open: boolean;
//   onClose: () => void;
//   onClone: (templateId: string, name: string) => void;
// }) {
//   const [selected, setSelected] = useState<FlowTemplate | null>(null);
//   const [newName, setNewName] = useState("");

//   const { data, isLoading } = useQuery<FlowTemplate[]>({
//     queryKey: ["flow-templates"],
//     queryFn: () =>
//       http.get<{ items: FlowTemplate[]; total: number }>("/api/v1/flow-templates").then(
//         (r) => (Array.isArray(r) ? (r as FlowTemplate[]) : (r?.items ?? [])),
//       ),
//     enabled: open,
//   });
//   const templates = data ?? [];

//   const STRICTNESS_COLORS: Record<string, string> = {
//     strict: "bg-red-100 text-red-700",
//     medium: "bg-amber-100 text-amber-700",
//     loose:  "bg-green-100 text-green-700",
//   };

//   function handleClose() {
//     setSelected(null);
//     setNewName("");
//     onClose();
//   }

//   if (selected) {
//     return (
//       <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
//         <DialogContent className="max-w-md">
//           <DialogHeader>
//             <DialogTitle>Name your new flow</DialogTitle>
//             <DialogDescription>Cloning &ldquo;{selected.name}&rdquo; — give the new flow a name.</DialogDescription>
//           </DialogHeader>
//           <div className="space-y-3 py-2">
//             <div className="space-y-1.5">
//               <Label>Flow name *</Label>
//               <Input
//                 value={newName}
//                 onChange={(e) => setNewName(e.target.value)}
//                 placeholder={`${selected.name} (Copy)`}
//                 onKeyDown={(e) => {
//                   if (e.key === "Enter" && newName.trim()) {
//                     onClone(selected.id, newName.trim());
//                     handleClose();
//                   }
//                 }}
//                 autoFocus
//               />
//             </div>
//           </div>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setSelected(null)}>← Back</Button>
//             <Button
//               disabled={!newName.trim()}
//               onClick={() => { onClone(selected.id, newName.trim()); handleClose(); }}
//             >
//               Create flow
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>
//     );
//   }

//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
//       <DialogContent className="max-w-2xl">
//         <DialogHeader>
//           <DialogTitle>Flow Templates</DialogTitle>
//           <DialogDescription>Choose a pre-built template to start from. You can customise it after cloning.</DialogDescription>
//         </DialogHeader>
//         <div className="space-y-3 py-2 max-h-[60vh] overflow-y-auto">
//           {isLoading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
//           {templates.map((t) => (
//             <div key={t.id} className="border rounded-lg p-4">
//               <div className="flex items-start justify-between gap-3">
//                 <div className="flex-1 min-w-0">
//                   <div className="flex items-center gap-2 mb-1">
//                     <p className="font-medium text-sm">{t.name}</p>
//                     <span className={cn("text-[10px] rounded px-1.5 py-0.5 font-medium", STRICTNESS_COLORS[t.gate_strictness] ?? "bg-gray-100 text-gray-700")}>
//                       {t.gate_strictness}
//                     </span>
//                   </div>
//                   <p className="text-xs text-muted-foreground mb-2">{t.description}</p>
//                   <p className="text-[10px] text-muted-foreground mb-2">
//                     <span className="font-medium">Best for:</span> {t.recommended_for}
//                   </p>
//                   <div className="flex flex-wrap gap-1">
//                     {t.source_platforms.map((p) => {
//                       const meta = getMeta(p);
//                       return (
//                         <span key={p} className={cn("text-[10px] rounded px-1.5 py-0.5 font-medium border", meta.badgeColor)}>
//                           {meta.label}
//                         </span>
//                       );
//                     })}
//                     {t.enrichment_platforms.length > 0 && (
//                       <span className="text-[10px] text-muted-foreground ml-1">
//                         + {t.enrichment_platforms.map((p) => getMeta(p).label).join(", ")}
//                       </span>
//                     )}
//                   </div>
//                 </div>
//                 <Button
//                   size="sm"
//                   className="flex-shrink-0"
//                   onClick={() => { setSelected(t); setNewName(`${t.name} (Copy)`); }}
//                 >
//                   Use template
//                 </Button>
//               </div>
//             </div>
//           ))}
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={handleClose}>Close</Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: DeleteDialog
// // ─────────────────────────────────────────────────────────────────────────────

// function DeleteDialog({
//   flow,
//   open,
//   onClose,
//   onConfirm,
//   isDeleting,
// }: {
//   flow: ProspectingFlow | null;
//   open: boolean;
//   onClose: () => void;
//   onConfirm: () => void;
//   isDeleting: boolean;
// }) {
//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
//       <DialogContent className="max-w-sm">
//         <DialogHeader>
//           <DialogTitle>Delete flow?</DialogTitle>
//           <DialogDescription>
//             &ldquo;{flow?.name}&rdquo; will be permanently removed. Past run records are kept.
//           </DialogDescription>
//         </DialogHeader>
//         <DialogFooter>
//           <Button variant="outline" onClick={onClose}>Cancel</Button>
//           <Button variant="destructive" onClick={onConfirm} disabled={isDeleting}>
//             {isDeleting ? "Deleting…" : "Delete"}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Main Page Component
// // ─────────────────────────────────────────────────────────────────────────────

// export function FlowsPage() {
//   const qc = useQueryClient();

//   // ── UI state
//   const [selectedId, setSelectedId] = useState<string | null>(null);
//   const [draft, setDraft] = useState<EditableFlow | null>(null);
//   const [dirty, setDirty] = useState(false);
//   const [viewMode, setViewMode] = useState<"form" | "visual">("form");
//   const [runOpen, setRunOpen] = useState(false);
//   const [activeRunId, setActiveRunId] = useState<string | null>(null);
//   const [templatesOpen, setTemplatesOpen] = useState(false);
//   const [deleteTarget, setDeleteTarget] = useState<ProspectingFlow | null>(null);
//   const importRef = useRef<HTMLInputElement>(null);

//   // ── Queries
//   const { data, isLoading, isError, refetch } = useQuery({
//     queryKey: ["flows", "list"],
//     queryFn: () => flowsApi.listFlows({ isTemplate: false }),
//     retry: false,
//   });
//   const flows = useMemo(() => data?.items ?? [], [data]);

//   const { data: integrations } = useQuery<TenantIntegration[]>({
//     queryKey: ["integrations-for-flows"],
//     queryFn: () => integrationConfigApi.tenantList(),
//   });

//   const connectedMap = useMemo(
//     () => buildConnectedMap(integrations ?? []),
//     [integrations],
//   );

//   // Auto-select first (or default) flow
//   useEffect(() => {
//     if (flows.length > 0 && !selectedId && !draft) {
//       const def = flows.find((f) => f.isDefault) ?? flows[0];
//       setSelectedId(def.id);
//       setDraft(flowToEditable(def));
//       setDirty(false);
//     }
//   }, [flows, selectedId, draft]);

//   const selectedFlow = useMemo(() => flows.find((f) => f.id === selectedId) ?? null, [flows, selectedId]);

//   function selectFlow(f: ProspectingFlow) {
//     if (dirty && !window.confirm("You have unsaved changes. Discard them and switch flows?")) return;
//     setSelectedId(f.id);
//     setDraft(flowToEditable(f));
//     setDirty(false);
//   }

//   function startNew() {
//     if (dirty && !window.confirm("You have unsaved changes. Discard them?")) return;
//     setSelectedId(null);
//     setDraft(newEditable());
//     setDirty(true);
//   }

//   function updateDraft(patch: Partial<EditableFlow>) {
//     setDraft((prev) => prev ? { ...prev, ...patch } : prev);
//     setDirty(true);
//   }

//   // ── Mutations
//   const createMut = useMutation({
//     mutationFn: (body: ProspectingFlowInput) => flowsApi.createFlow(body),
//     onSuccess: (created) => {
//       toast.success("Flow created");
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       setSelectedId(created.id);
//       setDraft(flowToEditable(created));
//       setDirty(false);
//     },
//     onError: () => toast.error("Failed to create flow"),
//   });

//   const updateMut = useMutation({
//     mutationFn: ({ id, body }: { id: string; body: Partial<ProspectingFlowInput> }) =>
//       flowsApi.updateFlow(id, body),
//     onSuccess: (updated) => {
//       toast.success("Flow saved");
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       setDraft(flowToEditable(updated));
//       setDirty(false);
//     },
//     onError: () => toast.error("Failed to save flow"),
//   });

//   const deleteMut = useMutation({
//     mutationFn: (id: string) => flowsApi.removeFlow(id),
//     onSuccess: () => {
//       toast.success("Flow deleted");
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       setDeleteTarget(null);
//       setSelectedId(null);
//       setDraft(null);
//       setDirty(false);
//     },
//     onError: () => toast.error("Failed to delete flow"),
//   });

//   const runMut = useMutation({
//     mutationFn: ({ flowId, icpId }: { flowId: string; icpId: string }) =>
//       flowsApi.runFlow(flowId, icpId),
//     onSuccess: (result) => {
//       setActiveRunId(result.run_id);
//     },
//     onError: () => toast.error("Failed to start flow run"),
//   });

//   const cloneMut = useMutation({
//     mutationFn: ({ templateId, name }: { templateId: string; name: string }) =>
//       http.post<{ success: boolean; flow_id?: string }>("/api/v1/flow-templates/clone", {
//         template_id: templateId,
//         new_name: name,
//       }),
//     onSuccess: (result) => {
//       toast.success("Template cloned as new flow");
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       if (result.flow_id) setSelectedId(result.flow_id);
//     },
//     onError: () => toast.error("Failed to clone template"),
//   });

//   // ── Save
//   const handleSave = useCallback(() => {
//     if (!draft) return;
//     if (!draft.name.trim()) { toast.error("Flow name is required"); return; }

//     const missing = findUnconnectedEnabledSteps(draft, connectedMap);
//     if (missing.length > 0) {
//       toast.error("Save blocked — missing API keys", {
//         description: `${missing.length} enabled step${missing.length > 1 ? "s" : ""} need API keys: ${missing.join(", ")}. Toggle them off or wire keys in Setup → Integrations.`,
//         duration: 9000,
//       });
//       return;
//     }

//     const input = editableToInput(draft);
//     if (draft.id) {
//       updateMut.mutate({ id: draft.id, body: input });
//     } else {
//       createMut.mutate(input);
//     }
//   }, [draft, connectedMap, updateMut, createMut]);

//   // ── Duplicate
//   const handleDuplicate = useCallback(() => {
//     if (!draft?.id) { toast.error("Save the flow before duplicating"); return; }
//     const missing = findUnconnectedEnabledSteps(draft, connectedMap);
//     if (missing.length > 0) {
//       toast.error("Duplicate blocked — missing API keys", {
//         description: `Fix ${missing.join(", ")} in Setup → Integrations first.`,
//         duration: 9000,
//       });
//       return;
//     }
//     const input = editableToInput(draft);
//     createMut.mutate({ ...input, name: `${draft.name} (Copy)`, isDefault: false });
//   }, [draft, connectedMap, createMut]);

//   // ── Set Default
//   async function handleSetDefault(f: ProspectingFlow) {
//     if (f.isDefault) return;
//     try {
//       await flowsApi.updateFlow(f.id, { isDefault: true } as Partial<ProspectingFlowInput>);
//       toast.success(`"${f.name}" is now the default flow`);
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       if (selectedId === f.id && draft) setDraft({ ...draft, isDefault: true });
//     } catch {
//       toast.error("Failed to set default");
//     }
//   }

//   // ── Export
//   async function handleExport() {
//     if (!draft?.id) { toast.error("Save the flow before exporting"); return; }
//     try {
//       const res = await fetch(`/api/v1/flows/${draft.id}/export`, { credentials: "include" });
//       if (!res.ok) throw new Error(`HTTP ${res.status}`);
//       const blob = await res.blob();
//       const url = URL.createObjectURL(blob);
//       const a = document.createElement("a");
//       a.href = url;
//       a.download = `${(draft.name || "flow").replace(/[^a-z0-9_-]+/gi, "_")}.json`;
//       a.click();
//       URL.revokeObjectURL(url);
//       toast.success("Flow exported");
//     } catch {
//       toast.error("Export failed");
//     }
//   }

//   // ── Import
//   async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
//     const file = e.target.files?.[0];
//     e.target.value = "";
//     if (!file) return;
//     try {
//       const text = await file.text();
//       const obj = JSON.parse(text);
//       const res = await fetch("/api/v1/flows/import", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         credentials: "include",
//         body: JSON.stringify(obj),
//       });
//       const data = await res.json().catch(() => ({}));
//       if (!res.ok) throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
//       toast.success(`Flow imported: ${(data as ProspectingFlow).name}`);
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       setSelectedId((data as ProspectingFlow).id);
//       setDraft(flowToEditable(data as ProspectingFlow));
//       setDirty(false);
//     } catch (err) {
//       toast.error("Import failed", {
//         description: err instanceof Error ? err.message : "Invalid JSON file",
//       });
//     }
//   }

//   const isSaving = createMut.isPending || updateMut.isPending;
//   const canRun = !!draft?.id && !dirty;

//   return (
//     <TooltipProvider delayDuration={200}>
//       <div className="space-y-4">
//         {/* Hidden import input */}
//         <input
//           ref={importRef}
//           type="file"
//           accept=".json,application/json"
//           onChange={handleImportFile}
//           className="hidden"
//         />

//         {/* Page header */}
//         <div className="flex items-center justify-between flex-wrap gap-2">
//           <div>
//             <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
//               <Workflow className="h-6 w-6 text-primary" />
//               Prospecting Flows
//             </h2>
//             <p className="text-sm text-muted-foreground mt-1">
//               Orchestrate how your connected platforms work together — ordered sourcing, chained enrichment with
//               fallbacks, and quality gates.
//             </p>
//           </div>
//           <div className="flex items-center gap-2">
//             <Button variant="outline" onClick={() => refetch()}>
//               <RefreshCw className="h-4 w-4 mr-2" /> Refresh
//             </Button>
//             <Button variant="outline" onClick={() => setTemplatesOpen(true)}>
//               <Layers className="h-4 w-4 mr-2" /> Templates
//             </Button>
//             <Button variant="outline" onClick={() => importRef.current?.click()}>
//               <Upload className="h-4 w-4 mr-2" /> Import
//             </Button>
//             <Button onClick={startNew}>
//               <Plus className="h-4 w-4 mr-2" /> New Flow
//             </Button>
//           </div>
//         </div>

//         <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
//           {/* ═══ LEFT PANEL: Flow list ═══ */}
//           <Card className="h-fit">
//             <CardHeader className="pb-3">
//               <CardTitle className="text-sm font-medium flex items-center justify-between">
//                 Flows
//                 <Badge variant="secondary">{flows.length}</Badge>
//               </CardTitle>
//             </CardHeader>
//             <CardContent className="p-2">
//               <div className="space-y-1 max-h-[calc(100vh-280px)] min-h-[300px] overflow-y-auto pr-1">
//                 {isLoading && Array.from({ length: 3 }).map((_, i) => (
//                   <div key={i} className="px-2 py-1"><Skeleton className="h-16 w-full" /></div>
//                 ))}
//                 {isError && (
//                   <div className="text-xs text-muted-foreground text-center py-6 px-2">
//                     Failed to load.{" "}
//                     <button onClick={() => refetch()} className="underline text-primary">Retry</button>
//                   </div>
//                 )}
//                 {!isLoading && !isError && flows.length === 0 && (
//                   <p className="text-xs text-muted-foreground text-center py-6 px-2">
//                     No flows yet. Create your first flow.
//                   </p>
//                 )}
//                 {flows.map((f) => {
//                   const isSelected = f.id === selectedId;
//                   return (
//                     <div
//                       key={f.id}
//                       className={cn(
//                         "group rounded-md border px-3 py-2.5 cursor-pointer transition-colors",
//                         isSelected ? "border-primary bg-primary/5" : "border-transparent hover:bg-muted/50",
//                       )}
//                       onClick={() => selectFlow(f)}
//                     >
//                       <div className="flex items-start justify-between gap-2">
//                         <div className="min-w-0 flex-1">
//                           <div className="flex items-center gap-1.5">
//                             <span className="font-medium text-sm truncate">{f.name}</span>
//                             {f.isDefault && <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400 shrink-0" />}
//                           </div>
//                           <p className="text-xs text-muted-foreground truncate mt-0.5">
//                             {f.description || "No description"}
//                           </p>
//                           <div className="flex items-center gap-1.5 mt-1.5">
//                             <Badge variant="outline" className="text-[10px] py-0 h-4">
//                               {parseStepsFromRaw(f.sourceSteps).length} src
//                             </Badge>
//                             <Badge variant="outline" className="text-[10px] py-0 h-4">
//                               {parseStepsFromRaw(f.enrichmentSteps).length} enr
//                             </Badge>
//                             {!f.isActive && (
//                               <Badge variant="secondary" className="text-[10px] py-0 h-4">inactive</Badge>
//                             )}
//                           </div>
//                         </div>
//                         {!f.isDefault && (
//                           <Tooltip>
//                             <TooltipTrigger asChild>
//                               <Button
//                                 variant="ghost"
//                                 size="icon"
//                                 className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
//                                 onClick={(e) => { e.stopPropagation(); handleSetDefault(f); }}
//                               >
//                                 <StarOff className="h-3.5 w-3.5" />
//                               </Button>
//                             </TooltipTrigger>
//                             <TooltipContent>Set as default</TooltipContent>
//                           </Tooltip>
//                         )}
//                       </div>
//                     </div>
//                   );
//                 })}
//               </div>
//               <Button variant="outline" className="w-full mt-2" onClick={startNew}>
//                 <Plus className="h-4 w-4 mr-2" /> New Flow
//               </Button>
//             </CardContent>
//           </Card>

//           {/* ═══ RIGHT PANEL: Editor ═══ */}
//           {!draft ? (
//             <Card className="flex items-center justify-center min-h-[400px]">
//               <CardContent className="text-center text-muted-foreground py-12">
//                 <Inbox className="h-12 w-12 mx-auto mb-3 opacity-40" />
//                 <p className="font-medium">No flow selected</p>
//                 <p className="text-sm mt-1">Select a flow from the list, or create a new one.</p>
//                 <Button className="mt-4" onClick={startNew}>
//                   <Plus className="h-4 w-4 mr-2" /> New Flow
//                 </Button>
//               </CardContent>
//             </Card>
//           ) : (
//             <div className="space-y-4">
//               {/* Editor header card */}
//               <Card>
//                 <CardHeader className="pb-3">
//                   <div className="flex items-start justify-between gap-3 flex-wrap">
//                     <div className="flex-1 min-w-0 space-y-2">
//                       <div className="flex items-center gap-2 flex-wrap">
//                         {draft.isDefault && (
//                           <Badge className="bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-100">
//                             <Star className="h-3 w-3 fill-amber-400 text-amber-400 mr-1" /> Default
//                           </Badge>
//                         )}
//                         <Badge variant={draft.isActive ? "default" : "secondary"}>
//                           {draft.isActive ? "Active" : "Inactive"}
//                         </Badge>
//                         {dirty && (
//                           <Badge variant="outline" className="text-amber-600 border-amber-300">
//                             <AlertCircle className="h-3 w-3 mr-1" /> Unsaved
//                           </Badge>
//                         )}
//                         {/* View toggle */}
//                         <div className="ml-auto flex items-center rounded-md border bg-muted/40 p-0.5">
//                           <button
//                             type="button"
//                             onClick={() => setViewMode("form")}
//                             className={cn(
//                               "px-2.5 py-1 text-xs rounded transition-colors",
//                               viewMode === "form" ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground",
//                             )}
//                           >
//                             Form View
//                           </button>
//                           <button
//                             type="button"
//                             onClick={() => setViewMode("visual")}
//                             className={cn(
//                               "px-2.5 py-1 text-xs rounded transition-colors flex items-center gap-1",
//                               viewMode === "visual" ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground",
//                             )}
//                           >
//                             <Workflow className="h-3 w-3" /> Visual Builder
//                           </button>
//                         </div>
//                       </div>
//                       {/* Inline name / description editors */}
//                       <Input
//                         value={draft.name}
//                         onChange={(e) => updateDraft({ name: e.target.value })}
//                         placeholder="Flow name"
//                         className="text-lg font-semibold h-9 border-none px-0 focus-visible:ring-0"
//                       />
//                       <Textarea
//                         value={draft.description}
//                         onChange={(e) => updateDraft({ description: e.target.value })}
//                         placeholder="Add a description for this flow…"
//                         className="min-h-[40px] resize-none border-none px-0 focus-visible:ring-0 text-sm text-muted-foreground"
//                       />
//                     </div>

//                     {/* Action buttons */}
//                     <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
//                       <Tooltip>
//                         <TooltipTrigger asChild>
//                           <Button
//                             variant="outline"
//                             size="icon"
//                             className="h-8 w-8"
//                             onClick={() => updateDraft({ isDefault: !draft.isDefault })}
//                             disabled={isSaving}
//                           >
//                             <Star className={`h-4 w-4 ${draft.isDefault ? "fill-amber-400 text-amber-400" : ""}`} />
//                           </Button>
//                         </TooltipTrigger>
//                         <TooltipContent>{draft.isDefault ? "Unset default" : "Set as default"}</TooltipContent>
//                       </Tooltip>
//                       <Tooltip>
//                         <TooltipTrigger asChild>
//                           <Button
//                             variant="outline" size="icon" className="h-8 w-8"
//                             onClick={handleExport}
//                             disabled={!draft.id}
//                           >
//                             <Download className="h-4 w-4" />
//                           </Button>
//                         </TooltipTrigger>
//                         <TooltipContent>Export as JSON</TooltipContent>
//                       </Tooltip>
//                       <Tooltip>
//                         <TooltipTrigger asChild>
//                           <Button
//                             variant="outline" size="icon" className="h-8 w-8"
//                             onClick={handleDuplicate}
//                             disabled={isSaving || !draft.id}
//                           >
//                             <Copy className="h-4 w-4" />
//                           </Button>
//                         </TooltipTrigger>
//                         <TooltipContent>Duplicate</TooltipContent>
//                       </Tooltip>
//                       <Tooltip>
//                         <TooltipTrigger asChild>
//                           <Button
//                             variant="outline" size="icon" className="h-8 w-8"
//                             onClick={() => updateDraft({ isActive: !draft.isActive })}
//                           >
//                             <Pencil className="h-4 w-4" />
//                           </Button>
//                         </TooltipTrigger>
//                         <TooltipContent>Toggle Active</TooltipContent>
//                       </Tooltip>
//                       <Button
//                         variant="outline" size="icon" className="h-8 w-8 text-destructive"
//                         onClick={() => selectedFlow && setDeleteTarget(selectedFlow)}
//                         disabled={isSaving || !draft.id}
//                       >
//                         <Trash2 className="h-4 w-4" />
//                       </Button>
//                       <Button
//                         size="sm"
//                         onClick={() => { setActiveRunId(null); setRunOpen(true); }}
//                         disabled={!canRun}
//                         className="bg-emerald-600 hover:bg-emerald-700 text-white"
//                       >
//                         <PlayCircle className="h-4 w-4 mr-1.5" /> Run
//                       </Button>
//                       <Button size="sm" onClick={handleSave} disabled={isSaving || !dirty}>
//                         {isSaving ? (
//                           <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Saving…</>
//                         ) : (
//                           <><Save className="h-4 w-4 mr-1.5" /> Save</>
//                         )}
//                       </Button>
//                     </div>
//                   </div>
//                   {dirty && (
//                     <p className="text-[11px] text-amber-600 mt-2 flex items-center gap-1">
//                       <AlertCircle className="h-3 w-3" />
//                       Save your changes before running the flow — Run is disabled while there are unsaved edits.
//                     </p>
//                   )}
//                 </CardHeader>
//               </Card>

//               {/* Form View — 3-panel */}
//               {viewMode === "form" ? (
//                 <>
//                   <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
//                     <SourceStepsCard
//                       steps={draft.sourceSteps}
//                       connectedMap={connectedMap}
//                       onChange={(sourceSteps) => updateDraft({ sourceSteps })}
//                     />
//                     <EnrichmentStepsCard
//                       steps={draft.enrichmentSteps}
//                       connectedMap={connectedMap}
//                       onChange={(enrichmentSteps) => updateDraft({ enrichmentSteps })}
//                     />
//                     <QualityGatesCard
//                       gates={draft.qualityGates}
//                       onChange={(patch) => updateDraft({ qualityGates: { ...draft.qualityGates, ...patch } })}
//                     />
//                   </div>
//                   <FlowSummary draft={draft} connectedMap={connectedMap} />
//                 </>
//               ) : (
//                 <VisualFlowBuilder
//                   draft={draft}
//                   connectedMap={connectedMap}
//                   onUpdate={updateDraft}
//                 />
//               )}
//             </div>
//           )}
//         </div>

//         {/* Dialogs */}
//         {selectedFlow && (
//           <RunFlowDialog
//             flow={selectedFlow}
//             open={runOpen}
//             onClose={() => { setRunOpen(false); setActiveRunId(null); }}
//             onRun={(icpId, _maxProspects, _dryRun, _llmConfigId) =>
//               runMut.mutate({ flowId: selectedFlow.id, icpId })
//             }
//             isRunning={runMut.isPending}
//             activeRunId={activeRunId}
//           />
//         )}

//         <TemplatesDialog
//           open={templatesOpen}
//           onClose={() => setTemplatesOpen(false)}
//           onClone={(templateId, name) => cloneMut.mutate({ templateId, name })}
//         />

//         <DeleteDialog
//           flow={deleteTarget}
//           open={!!deleteTarget}
//           onClose={() => setDeleteTarget(null)}
//           onConfirm={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
//           isDeleting={deleteMut.isPending}
//         />
//       </div>
//     </TooltipProvider>
//   );
// }

/**
 * FlowsPage.tsx — Prospecting Flows Builder (complete rewrite)
 *
 * Matches Next.js ProspectingFlowsPage + VisualFlowBuilder reference exactly:
 *
 *   ┌──────────────┬──────────────────────────────────────────────────────┐
 *   │ FLOWS LIST   │  Header (name, badges, view toggle, action buttons)  │
 *   │ (left panel) │  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐  │
 *   │              │  │ 1. SOURCE    │ │ 2. ENRICH    │ │ 3. QUALITY  │  │
 *   │              │  │    STEPS     │ │    STEPS     │ │    GATES    │  │
 *   │              │  │              │ │   (optional) │ │             │  │
 *   │              │  └──────────────┘ └──────────────┘ └─────────────┘  │
 *   │              │  ─── Pipeline Preview ──────────────────────────────  │
 *   └──────────────┴──────────────────────────────────────────────────────┘
 *
 * Key behaviours:
 *  - Enrichment is OPTIONAL. Empty enrichment steps array is fully valid.
 *  - Platform palette shows connected (✓) vs not-connected (⚠) status.
 *  - Save is BLOCKED when enabled steps have no API key (with clear toast).
 *  - Free sources (AI Web Search, LinkedIn) never need a key.
 *  - Run dialog shows ICP selector + LLM config selector + Dry Run toggle.
 *  - After clicking Run the dialog switches to a live RunMonitor that polls
 *    GET /flows/runs/{run_id} every 2 seconds until terminal state.
 *  - View toggle: "Form View" (3-card JSON editors) vs "Visual Builder" (dnd-kit).
 *
 * Backend step format: { "platform": "apollo", "enabled": true, "order": 0 }
 * The parseSteps() helper also accepts legacy keys: provider, key, type.
 */

// import {
//   useCallback,
//   useEffect,
//   useMemo,
//   useRef,
//   useState,
// } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   DndContext,
//   closestCenter,
//   KeyboardSensor,
//   PointerSensor,
//   useSensor,
//   useSensors,
// } from "@dnd-kit/core";
// import type { DragEndEvent } from "@dnd-kit/core";
// import {
//   SortableContext,
//   sortableKeyboardCoordinates,
//   useSortable,
//   verticalListSortingStrategy,
//   arrayMove,
// } from "@dnd-kit/sortable";
// import { CSS } from "@dnd-kit/utilities";
// import {
//   Activity,
//   AlertCircle,
//   ArrowRight,
//   BarChart2,
//   Brain,
//   Building2,
//   Ban,
  
//   CheckCircle2,
//   ChevronDown,
//   ChevronUp,
//   Copy,
//   Download,
  
//   GripVertical,
//   Inbox,
//   Layers,
//   Loader2,
//   Mail,
//   Pencil,
//   Plus,
//   PlayCircle,
//   RefreshCw,
//   Save,
//   Search,
//   Settings2,
//   ShieldCheck,
//   Sparkles,
//   Star,
//   StarOff,
//   Trash2,
//   Upload,
//   Workflow,
//   X,
//   XCircle,
//   Zap,
// } from "lucide-react";
// import { toast } from "sonner";

// import { flowsApi, integrationConfigApi, http } from "@/services/apiClient";
// import type {
//   ProspectingFlow,
//   ProspectingFlowInput,
//   TenantIntegration,
// } from "@/types/common";
// import { Badge } from "@/components/ui/badge";
// import { Button } from "@/components/ui/button";
// import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from "@/components/ui/select";
// import { Skeleton } from "@/components/ui/skeleton";
// import { Switch } from "@/components/ui/switch";
// import { Textarea } from "@/components/ui/textarea";
// import {
//   Tooltip,
//   TooltipContent,
//   TooltipProvider,
//   TooltipTrigger,
// } from "@/components/ui/tooltip";
// import { Separator } from "@/components/ui/separator";
// import { cn } from "@/lib/utils";

// // ─────────────────────────────────────────────────────────────────────────────
// // Platform registry
// // ─────────────────────────────────────────────────────────────────────────────

// interface PlatformMeta {
//   key: string;
//   label: string;
//   canSource: boolean;
//   canEnrich: boolean;
//   free: boolean; // free = no API key required
//   badgeColor: string; // Tailwind classes for the badge chip
//   sourceFields: { key: string; label: string; placeholder: string }[];
//   enrichFields: { key: string; label: string }[];
// }

// const PLATFORM_META: Record<string, PlatformMeta> = {
//   ai_web_search: {
//     key: "ai_web_search",
//     label: "AI Web Search",
//     canSource: true,
//     canEnrich: false,
//     free: true,
//     badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
//     sourceFields: [
//       { key: "query", label: "Search Query", placeholder: "CTO fintech series B" },
//     ],
//     enrichFields: [],
//   },
//   web_search: {
//     key: "web_search",
//     label: "AI Web Search",
//     canSource: true,
//     canEnrich: false,
//     free: true,
//     badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
//     sourceFields: [
//       { key: "query", label: "Search Query", placeholder: "CTO fintech series B" },
//     ],
//     enrichFields: [],
//   },
//   linkedin: {
//     key: "linkedin",
//     label: "LinkedIn",
//     canSource: true,
//     canEnrich: false,
//     free: true,
//     badgeColor: "bg-sky-100 text-sky-700 border-sky-200",
//     sourceFields: [
//       { key: "job_title", label: "Job Title", placeholder: "Chief Technology Officer" },
//       { key: "industry", label: "Industry", placeholder: "SaaS" },
//       { key: "location", label: "Location", placeholder: "San Francisco, CA" },
//     ],
//     enrichFields: [],
//   },
//   apollo: {
//     key: "apollo",
//     label: "Apollo.io",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-blue-100 text-blue-700 border-blue-200",
//     sourceFields: [
//       { key: "person_titles", label: "Job Titles", placeholder: "CTO, VP Engineering" },
//       { key: "q_keywords", label: "Keywords", placeholder: "series A SaaS" },
//       { key: "organization_locations", label: "Locations", placeholder: "San Francisco, CA" },
//     ],
//     enrichFields: [
//       { key: "email", label: "Email" },
//       { key: "phone", label: "Phone" },
//       { key: "linkedin", label: "LinkedIn URL" },
//     ],
//   },
//   zoominfo: {
//     key: "zoominfo",
//     label: "ZoomInfo",
//     canSource: true,
//     canEnrich: false,
//     free: false,
//     badgeColor: "bg-indigo-100 text-indigo-700 border-indigo-200",
//     sourceFields: [
//       { key: "jobTitle", label: "Job Title", placeholder: "Chief Technology Officer" },
//       { key: "companyIndustry", label: "Industry", placeholder: "Software" },
//       { key: "employees", label: "Employees", placeholder: "50-200" },
//     ],
//     enrichFields: [],
//   },
//   clearbit: {
//     key: "clearbit",
//     label: "Clearbit",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-teal-100 text-teal-700 border-teal-200",
//     sourceFields: [
//       { key: "query", label: "Company", placeholder: "acme.com" },
//     ],
//     enrichFields: [
//       { key: "company_size", label: "Company Size" },
//       { key: "revenue", label: "Revenue" },
//       { key: "tech_stack", label: "Tech Stack" },
//       { key: "industry", label: "Industry" },
//     ],
//   },
//   hunter: {
//     key: "hunter",
//     label: "Hunter.io",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-amber-100 text-amber-700 border-amber-200",
//     sourceFields: [
//       { key: "domain", label: "Domain", placeholder: "acme.com" },
//     ],
//     enrichFields: [
//       { key: "email", label: "Email" },
//       { key: "email_pattern", label: "Email Pattern" },
//     ],
//   },
//   lusha: {
//     key: "lusha",
//     label: "Lusha",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-rose-100 text-rose-700 border-rose-200",
//     sourceFields: [
//       { key: "company_name", label: "Company", placeholder: "Acme Inc" },
//     ],
//     enrichFields: [
//       { key: "email", label: "Email" },
//       { key: "phone", label: "Phone" },
//     ],
//   },
//   kaspr: {
//     key: "kaspr",
//     label: "Kaspr",
//     canSource: true,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-pink-100 text-pink-700 border-pink-200",
//     sourceFields: [
//       { key: "query", label: "Query", placeholder: "CTO Acme" },
//     ],
//     enrichFields: [
//       { key: "email", label: "Email" },
//       { key: "phone", label: "Phone" },
//     ],
//   },
//   clay: {
//     key: "clay",
//     label: "Clay",
//     canSource: true,
//     canEnrich: false,
//     free: false,
//     badgeColor: "bg-orange-100 text-orange-700 border-orange-200",
//     sourceFields: [
//       { key: "table_name", label: "Table Name", placeholder: "my-icp-table" },
//     ],
//     enrichFields: [],
//   },
//   email_waterfall: {
//     key: "email_waterfall",
//     label: "Email Waterfall",
//     canSource: false,
//     canEnrich: true,
//     free: false,
//     badgeColor: "bg-emerald-100 text-emerald-700 border-emerald-200",
//     sourceFields: [],
//     enrichFields: [
//       { key: "email", label: "Email" },
//     ],
//   },
// };

// function getMeta(key: string): PlatformMeta {
//   return (
//     PLATFORM_META[key] ?? {
//       key,
//       label: key,
//       canSource: false,
//       canEnrich: false,
//       free: false,
//       badgeColor: "bg-gray-100 text-gray-700 border-gray-200",
//       sourceFields: [],
//       enrichFields: [],
//     }
//   );
// }

// const ALL_SOURCE_KEYS = Object.values(PLATFORM_META)
//   .filter((m) => m.canSource)
//   .map((m) => m.key)
//   .filter((k) => k !== "web_search"); // deduplicate alias

// const ALL_ENRICH_KEYS = Object.values(PLATFORM_META)
//   .filter((m) => m.canEnrich)
//   .map((m) => m.key);

// // ─────────────────────────────────────────────────────────────────────────────
// // Step + QualityGates types
// // ─────────────────────────────────────────────────────────────────────────────

// interface SourceStep {
//   platform: string;
//   enabled: boolean;
//   priority: number;
//   queryOverrides: Record<string, string>;
// }

// interface EnrichmentStep {
//   platform: string;
//   enabled: boolean;
//   priority: number;
//   targetFields: string[];
//   fallbackTo: string | null;
// }

// interface QualityGates {
//   requireEmail: boolean;
//   requireVerifiedEmail: boolean;
//   requireCompanySize: boolean;
//   minCompanySize: number;
//   llmScoreThreshold: number;
//   excludeDomains: string[];
// }

// const DEFAULT_GATES: QualityGates = {
//   requireEmail: true,
//   requireVerifiedEmail: false,
//   requireCompanySize: false,
//   minCompanySize: 10,
//   llmScoreThreshold: 0.6,
//   excludeDomains: ["gmail.com", "yahoo.com", "hotmail.com"],
// };

// // ─────────────────────────────────────────────────────────────────────────────
// // EditableFlow — parsed editor state
// // ─────────────────────────────────────────────────────────────────────────────

// interface EditableFlow {
//   id: string | null;
//   name: string;
//   description: string;
//   isDefault: boolean;
//   isActive: boolean;
//   isTemplate: boolean;
//   sourceSteps: SourceStep[];
//   enrichmentSteps: EnrichmentStep[];
//   qualityGates: QualityGates;
// }

// function parseStepsFromRaw(raw: unknown): SourceStep[] | EnrichmentStep[] {
//   if (!raw) return [];
//   try {
//     const arr = Array.isArray(raw) ? raw : JSON.parse(String(raw));
//     return (arr as Record<string, unknown>[]).map((s, i) => ({
//       platform: String(s.platform ?? s.provider ?? s.key ?? s.type ?? ""),
//       enabled: s.enabled !== false,
//       priority: typeof s.priority === "number" ? s.priority : typeof s.order === "number" ? s.order : i,
//       queryOverrides: (s.queryOverrides as Record<string, string>) ?? {},
//       targetFields: Array.isArray(s.targetFields) ? (s.targetFields as string[]) : [],
//       fallbackTo: (s.fallbackTo as string | null) ?? null,
//     }));
//   } catch {
//     return [];
//   }
// }

// function parseGates(raw: unknown): QualityGates {
//   if (!raw) return { ...DEFAULT_GATES };
//   try {
//     const parsed =
//       typeof raw === "object" && !Array.isArray(raw)
//         ? raw
//         : JSON.parse(String(raw));
//     return { ...DEFAULT_GATES, ...(parsed as Partial<QualityGates>) };
//   } catch {
//     return { ...DEFAULT_GATES };
//   }
// }

// function flowToEditable(f: ProspectingFlow): EditableFlow {
//   return {
//     id: f.id,
//     name: f.name,
//     description: f.description ?? "",
//     isDefault: f.isDefault,
//     isActive: f.isActive,
//     isTemplate: f.isTemplate,
//     sourceSteps: parseStepsFromRaw(f.sourceSteps) as SourceStep[],
//     enrichmentSteps: parseStepsFromRaw(f.enrichmentSteps) as EnrichmentStep[],
//     qualityGates: parseGates(f.qualityGates),
//   };
// }

// function newEditable(): EditableFlow {
//   return {
//     id: null,
//     name: "Untitled Flow",
//     description: "",
//     isDefault: false,
//     isActive: true,
//     isTemplate: false,
//     sourceSteps: [],
//     enrichmentSteps: [],
//     qualityGates: { ...DEFAULT_GATES },
//   };
// }

// function editableToInput(e: EditableFlow): ProspectingFlowInput {
//   const serializeSourceSteps = e.sourceSteps.map((s, i) => ({
//     platform: s.platform,
//     enabled: s.enabled,
//     order: i,
//     priority: i,
//     queryOverrides: s.queryOverrides,
//   }));
//   const serializeEnrichSteps = e.enrichmentSteps.map((s, i) => ({
//     platform: s.platform,
//     enabled: s.enabled,
//     order: i,
//     priority: i,
//     targetFields: s.targetFields,
//     fallbackTo: s.fallbackTo,
//   }));
//   return {
//     name: e.name.trim(),
//     description: e.description.trim() || null,
//     isDefault: e.isDefault,
//     isActive: e.isActive,
//     isTemplate: e.isTemplate,
//     sourceSteps: serializeSourceSteps as unknown as Record<string, unknown>[],
//     enrichmentSteps: serializeEnrichSteps as unknown as Record<string, unknown>[],
//     qualityGates: e.qualityGates as unknown as Record<string, unknown>,
//   };
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // connectedMap helper
// // ─────────────────────────────────────────────────────────────────────────────

// function buildConnectedMap(integrations: TenantIntegration[]): Record<string, boolean> {
//   const m: Record<string, boolean> = {};
//   for (const i of integrations) {
//     m[i.platform] = !!(i.isActive && (i.apiKey || i.key_source === "platform"));
//   }
//   // Free sources are always "connected"
//   m["ai_web_search"] = true;
//   m["web_search"] = true;
//   m["linkedin"] = m["linkedin"] ?? true; // treat as free unless explicitly disconnected
//   return m;
// }

// function isConnected(platform: string, connectedMap: Record<string, boolean>): boolean {
//   const meta = getMeta(platform);
//   if (meta.free) return true;
//   return connectedMap[platform] ?? false;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Validation — block save when enabled steps lack API keys
// // ─────────────────────────────────────────────────────────────────────────────

// function findUnconnectedEnabledSteps(
//   draft: EditableFlow,
//   connectedMap: Record<string, boolean>,
// ): string[] {
//   const missing = new Set<string>();
//   for (const s of draft.sourceSteps) {
//     if (!s.enabled) continue;
//     if (!isConnected(s.platform, connectedMap)) missing.add(getMeta(s.platform).label);
//   }
//   for (const s of draft.enrichmentSteps) {
//     if (!s.enabled) continue;
//     if (!isConnected(s.platform, connectedMap)) missing.add(getMeta(s.platform).label);
//   }
//   return Array.from(missing).sort();
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // ICP profile lite
// // ─────────────────────────────────────────────────────────────────────────────

// interface IcpLite {
//   id: string;
//   name: string;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Flow Templates
// // ─────────────────────────────────────────────────────────────────────────────

// interface FlowTemplate {
//   id: string;
//   name: string;
//   description: string;
//   source_platforms: string[];
//   enrichment_platforms: string[];
//   gate_config: Partial<QualityGates>;
//   gate_strictness: string;
//   recommended_for: string;
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Run-monitor types
// // ─────────────────────────────────────────────────────────────────────────────

// interface FlowRunStep {
//   id: string;
//   kind: string;
//   stepKey: string;
//   status: string;
//   durationMs?: number | null;
//   metrics?: unknown;
//   errorMessage?: string | null;
// }

// interface FlowRunDetail {
//   id: string;
//   status: string;
//   stats?: unknown;
//   importedProspectIds?: unknown;
//   errorMessage?: string | null;
//   steps?: FlowRunStep[];
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: GateRow
// // ─────────────────────────────────────────────────────────────────────────────

// function GateRow({
//   icon,
//   label,
//   description,
//   checked,
//   onCheckedChange,
// }: {
//   icon: React.ReactNode;
//   label: string;
//   description: string;
//   checked: boolean;
//   onCheckedChange: (v: boolean) => void;
// }) {
//   return (
//     <div className="flex items-center justify-between">
//       <div className="flex items-center gap-2">
//         <span className="text-muted-foreground">{icon}</span>
//         <div>
//           <p className="text-sm font-medium leading-none">{label}</p>
//           <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
//         </div>
//       </div>
//       <Switch checked={checked} onCheckedChange={onCheckedChange} />
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: QualityGatesCard
// // ─────────────────────────────────────────────────────────────────────────────

// function QualityGatesCard({
//   gates,
//   onChange,
// }: {
//   gates: QualityGates;
//   onChange: (patch: Partial<QualityGates>) => void;
// }) {
//   const [domainInput, setDomainInput] = useState("");

//   function addDomain() {
//     const d = domainInput.trim().toLowerCase().replace(/^@/, "");
//     if (!d) return;
//     if (gates.excludeDomains.includes(d)) {
//       setDomainInput("");
//       return;
//     }
//     onChange({ excludeDomains: [...gates.excludeDomains, d] });
//     setDomainInput("");
//   }

//   return (
//     <Card>
//       <CardHeader className="pb-3">
//         <CardTitle className="text-sm flex items-center gap-2">
//           <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-red-700 text-[11px] font-bold">3</span>
//           Quality Gates
//         </CardTitle>
//         <CardDescription className="text-xs">
//           Auto-reject prospects that don&apos;t meet your quality bar.
//         </CardDescription>
//       </CardHeader>
//       <CardContent className="space-y-3">
//         <GateRow
//           icon={<Mail className="h-4 w-4" />}
//           label="Require email"
//           description="Reject prospects without an email address"
//           checked={gates.requireEmail}
//           onCheckedChange={(v) => onChange({ requireEmail: v })}
//         />
//         <Separator />
//         <GateRow
//           icon={<ShieldCheck className="h-4 w-4" />}
//           label="Require verified email"
//           description="Reject prospects whose email failed validation"
//           checked={gates.requireVerifiedEmail}
//           onCheckedChange={(v) => onChange({ requireVerifiedEmail: v })}
//         />
//         <Separator />
//         <div className="space-y-2">
//           <GateRow
//             icon={<Building2 className="h-4 w-4" />}
//             label="Minimum company size"
//             description="Reject prospects from companies below this employee count"
//             checked={gates.requireCompanySize}
//             onCheckedChange={(v) => onChange({ requireCompanySize: v })}
//           />
//           {gates.requireCompanySize && (
//             <div className="pl-7 flex items-center gap-2">
//               <Input
//                 type="number"
//                 min={0}
//                 value={gates.minCompanySize}
//                 onChange={(e) =>
//                   onChange({ minCompanySize: Math.max(0, Number(e.target.value) || 0) })
//                 }
//                 className="h-7 w-24 text-xs"
//               />
//               <span className="text-xs text-muted-foreground">employees minimum</span>
//             </div>
//           )}
//         </div>
//         <Separator />
//         <div className="space-y-2">
//           <div className="flex items-center justify-between">
//             <div className="flex items-center gap-2">
//               <Brain className="h-4 w-4 text-primary" />
//               <div>
//                 <p className="text-sm font-medium leading-none">LLM score threshold</p>
//                 <p className="text-xs text-muted-foreground mt-0.5">
//                   Reject prospects scoring below this ICP-fit score
//                 </p>
//               </div>
//             </div>
//             <Badge variant="outline" className="font-mono">
//               {gates.llmScoreThreshold.toFixed(2)}
//             </Badge>
//           </div>
//           <input
//             type="range"
//             min={0}
//             max={1}
//             step={0.05}
//             value={gates.llmScoreThreshold}
//             onChange={(e) => onChange({ llmScoreThreshold: Number(e.target.value) })}
//             className="w-full accent-primary"
//           />
//           <div className="flex justify-between text-[10px] text-muted-foreground">
//             <span>0.00 (off)</span>
//             <span>0.50</span>
//             <span>1.00 (strict)</span>
//           </div>
//         </div>
//         <Separator />
//         <div className="space-y-2">
//           <div className="flex items-center gap-2">
//             <Ban className="h-4 w-4" />
//             <div>
//               <p className="text-sm font-medium leading-none">Exclude domains</p>
//               <p className="text-xs text-muted-foreground mt-0.5">
//                 Reject prospects with these email domains
//               </p>
//             </div>
//           </div>
//           <div className="pl-7 space-y-2">
//             <div className="flex flex-wrap gap-1.5">
//               {gates.excludeDomains.length === 0 && (
//                 <span className="text-xs text-muted-foreground">No domains excluded.</span>
//               )}
//               {gates.excludeDomains.map((d) => (
//                 <Badge key={d} variant="secondary" className="text-xs gap-1 pr-1">
//                   {d}
//                   <button
//                     onClick={() =>
//                       onChange({ excludeDomains: gates.excludeDomains.filter((x) => x !== d) })
//                     }
//                     className="ml-0.5 hover:text-destructive"
//                   >
//                     <X className="h-3 w-3" />
//                   </button>
//                 </Badge>
//               ))}
//             </div>
//             <div className="flex gap-1.5">
//               <Input
//                 value={domainInput}
//                 onChange={(e) => setDomainInput(e.target.value)}
//                 onKeyDown={(e) => {
//                   if (e.key === "Enter") {
//                     e.preventDefault();
//                     addDomain();
//                   }
//                 }}
//                 placeholder="gmail.com"
//                 className="h-7 text-xs flex-1"
//               />
//               <Button variant="outline" size="sm" className="h-7 px-2" onClick={addDomain}>
//                 <Plus className="h-3.5 w-3.5" />
//               </Button>
//             </div>
//           </div>
//         </div>
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: SourceStepsCard (Form View)
// // ─────────────────────────────────────────────────────────────────────────────

// function SourceStepsCard({
//   steps,
//   connectedMap,
//   onChange,
// }: {
//   steps: SourceStep[];
//   connectedMap: Record<string, boolean>;
//   onChange: (steps: SourceStep[]) => void;
// }) {
//   const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

//   function update(idx: number, patch: Partial<SourceStep>) {
//     const next = steps.map((s, i) => (i === idx ? { ...s, ...patch } : s));
//     onChange(next);
//   }

//   function addStep(platform: string) {
//     const meta = getMeta(platform);
//     const queryOverrides: Record<string, string> = {};
//     for (const f of meta.sourceFields) queryOverrides[f.key] = "";
//     onChange([
//       ...steps,
//       { platform, enabled: true, priority: steps.length + 1, queryOverrides },
//     ]);
//     setExpandedIdx(steps.length);
//   }

//   function removeStep(idx: number) {
//     const next = steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, priority: i + 1 }));
//     onChange(next);
//     setExpandedIdx(null);
//   }

//   function moveStep(idx: number, dir: -1 | 1) {
//     const ni = idx + dir;
//     if (ni < 0 || ni >= steps.length) return;
//     const next = [...steps];
//     [next[idx], next[ni]] = [next[ni], next[idx]];
//     onChange(next.map((s, i) => ({ ...s, priority: i + 1 })));
//     setExpandedIdx(ni);
//   }

//   const available = ALL_SOURCE_KEYS.filter((k) => !steps.some((s) => s.platform === k));

//   return (
//     <Card>
//       <CardHeader className="pb-3">
//         <CardTitle className="text-sm flex items-center gap-2">
//           <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary text-[11px] font-bold">1</span>
//           Source Steps
//         </CardTitle>
//         <CardDescription className="text-xs">
//           Search platforms in priority order. Only enabled + connected platforms run.
//         </CardDescription>
//       </CardHeader>
//       <CardContent className="space-y-2">
//         {steps.length === 0 && (
//           <p className="text-xs text-muted-foreground text-center py-4">
//             No source steps. Add a platform below to start sourcing prospects.
//           </p>
//         )}
//         {steps.map((step, idx) => {
//           const meta = getMeta(step.platform);
//           const connected = isConnected(step.platform, connectedMap);
//           const isExpanded = expandedIdx === idx;
//           return (
//             <div key={`${step.platform}-${idx}`} className="rounded-md border">
//               <div className="flex items-center gap-1.5 p-2 flex-wrap">
//                 <GripVertical className="h-4 w-4 text-muted-foreground/50 shrink-0" />
//                 <span className="text-xs font-medium text-muted-foreground w-4 shrink-0">{idx + 1}</span>
//                 <Badge variant="outline" className={cn(meta.badgeColor, "shrink-0")}>
//                   {meta.label}
//                 </Badge>
//                 {!connected && (
//                   <Tooltip>
//                     <TooltipTrigger asChild>
//                       <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
//                     </TooltipTrigger>
//                     <TooltipContent>Not connected — add an API key in Integrations</TooltipContent>
//                   </Tooltip>
//                 )}
//                 {connected && !meta.free && (
//                   <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
//                 )}
//                 {meta.free && (
//                   <span className="text-[10px] text-green-600 font-medium shrink-0">free</span>
//                 )}
//                 <div className="flex-1 min-w-0" />
//                 <div className="flex items-center gap-1 shrink-0">
//                   <Switch
//                     checked={step.enabled}
//                     onCheckedChange={(v) => update(idx, { enabled: v })}
//                   />
//                   <Button
//                     variant="ghost" size="icon" className="h-7 w-7"
//                     disabled={idx === 0}
//                     onClick={() => moveStep(idx, -1)}
//                   >
//                     <ChevronUp className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button
//                     variant="ghost" size="icon" className="h-7 w-7"
//                     disabled={idx === steps.length - 1}
//                     onClick={() => moveStep(idx, 1)}
//                   >
//                     <ChevronDown className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button
//                     variant="ghost" size="icon" className="h-7 w-7"
//                     onClick={() => setExpandedIdx(isExpanded ? null : idx)}
//                   >
//                     <Settings2 className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button
//                     variant="ghost" size="icon" className="h-7 w-7 text-destructive"
//                     onClick={() => removeStep(idx)}
//                   >
//                     <Trash2 className="h-3.5 w-3.5" />
//                   </Button>
//                 </div>
//               </div>
//               {isExpanded && meta.sourceFields.length > 0 && (
//                 <div className="border-t px-3 pb-3 pt-2.5 space-y-2 bg-muted/30">
//                   <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
//                     Search Overrides
//                   </p>
//                   {meta.sourceFields.map((field) => (
//                     <div key={field.key} className="grid grid-cols-[110px_1fr] items-center gap-2">
//                       <Label className="text-xs text-muted-foreground">{field.label}</Label>
//                       <Input
//                         value={step.queryOverrides[field.key] ?? ""}
//                         onChange={(e) =>
//                           update(idx, {
//                             queryOverrides: { ...step.queryOverrides, [field.key]: e.target.value },
//                           })
//                         }
//                         placeholder={field.placeholder}
//                         className="h-7 text-xs"
//                       />
//                     </div>
//                   ))}
//                   {!connected && (
//                     <p className="text-[11px] text-amber-600 flex items-center gap-1 pt-1">
//                       <AlertCircle className="h-3 w-3" /> Connect this platform in Integrations to use it.
//                     </p>
//                   )}
//                 </div>
//               )}
//             </div>
//           );
//         })}

//         {available.length > 0 && (
//           <Select onValueChange={addStep}>
//             <SelectTrigger className="h-8 text-xs mt-2">
//               <SelectValue placeholder="+ Add source platform" />
//             </SelectTrigger>
//             <SelectContent>
//               {available.map((k) => {
//                 const meta = getMeta(k);
//                 const connected = isConnected(k, connectedMap);
//                 return (
//                   <SelectItem key={k} value={k} className="text-xs">
//                     {meta.label}
//                     {meta.free ? " (free)" : connected ? " ✓" : " (not connected)"}
//                   </SelectItem>
//                 );
//               })}
//             </SelectContent>
//           </Select>
//         )}
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: EnrichmentStepsCard (Form View — OPTIONAL)
// // ─────────────────────────────────────────────────────────────────────────────

// function EnrichmentStepsCard({
//   steps,
//   connectedMap,
//   onChange,
// }: {
//   steps: EnrichmentStep[];
//   connectedMap: Record<string, boolean>;
//   onChange: (steps: EnrichmentStep[]) => void;
// }) {
//   const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

//   function update(idx: number, patch: Partial<EnrichmentStep>) {
//     const next = steps.map((s, i) => (i === idx ? { ...s, ...patch } : s));
//     onChange(next);
//   }

//   function addStep(platform: string) {
//     const meta = getMeta(platform);
//     onChange([
//       ...steps,
//       {
//         platform,
//         enabled: true,
//         priority: steps.length + 1,
//         targetFields: meta.enrichFields.map((f) => f.key),
//         fallbackTo: null,
//       },
//     ]);
//     setExpandedIdx(steps.length);
//   }

//   function removeStep(idx: number) {
//     const next = steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, priority: i + 1 }));
//     onChange(next);
//     setExpandedIdx(null);
//   }

//   function moveStep(idx: number, dir: -1 | 1) {
//     const ni = idx + dir;
//     if (ni < 0 || ni >= steps.length) return;
//     const next = [...steps];
//     [next[idx], next[ni]] = [next[ni], next[idx]];
//     onChange(next.map((s, i) => ({ ...s, priority: i + 1 })));
//     setExpandedIdx(ni);
//   }

//   function toggleField(idx: number, fieldKey: string) {
//     const step = steps[idx];
//     const has = step.targetFields.includes(fieldKey);
//     const next = has
//       ? step.targetFields.filter((f) => f !== fieldKey)
//       : [...step.targetFields, fieldKey];
//     update(idx, { targetFields: next });
//   }

//   const available = ALL_ENRICH_KEYS.filter((k) => !steps.some((s) => s.platform === k));
//   const fallbackPlatforms = ALL_ENRICH_KEYS;

//   return (
//     <Card>
//       <CardHeader className="pb-3">
//         <CardTitle className="text-sm flex items-center gap-2">
//           <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-[11px] font-bold">2</span>
//           Enrichment Steps
//           <span className="ml-auto text-[10px] text-muted-foreground font-normal">optional</span>
//         </CardTitle>
//         <CardDescription className="text-xs">
//           Fill prospect fields in order. If a step fails, fall back to the next platform.{" "}
//           <strong>Leave empty to skip enrichment.</strong>
//         </CardDescription>
//       </CardHeader>
//       <CardContent className="space-y-2">
//         {steps.length === 0 && (
//           <p className="text-xs text-muted-foreground text-center py-4 border border-dashed rounded-md">
//             No enrichment steps — flow will run without enrichment. Add a platform below to enable.
//           </p>
//         )}
//         {steps.map((step, idx) => {
//           const meta = getMeta(step.platform);
//           const connected = isConnected(step.platform, connectedMap);
//           const isExpanded = expandedIdx === idx;
//           return (
//             <div key={`${step.platform}-${idx}`} className="rounded-md border">
//               <div className="flex items-center gap-1.5 p-2 flex-wrap">
//                 <GripVertical className="h-4 w-4 text-muted-foreground/50 shrink-0" />
//                 <span className="text-xs font-medium text-muted-foreground w-4 shrink-0">{idx + 1}</span>
//                 <Badge variant="outline" className={cn(meta.badgeColor, "shrink-0")}>
//                   {meta.label}
//                 </Badge>
//                 {!connected && (
//                   <Tooltip>
//                     <TooltipTrigger asChild>
//                       <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
//                     </TooltipTrigger>
//                     <TooltipContent>Not connected</TooltipContent>
//                   </Tooltip>
//                 )}
//                 {connected && <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />}
//                 {step.fallbackTo && (
//                   <Badge variant="secondary" className="text-[10px] py-0 h-4 shrink-0">
//                     ↳ {getMeta(step.fallbackTo).label}
//                   </Badge>
//                 )}
//                 <div className="flex-1 min-w-0" />
//                 <div className="flex items-center gap-1 shrink-0">
//                   <Switch
//                     checked={step.enabled}
//                     onCheckedChange={(v) => update(idx, { enabled: v })}
//                   />
//                   <Button variant="ghost" size="icon" className="h-7 w-7" disabled={idx === 0} onClick={() => moveStep(idx, -1)}>
//                     <ChevronUp className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button variant="ghost" size="icon" className="h-7 w-7" disabled={idx === steps.length - 1} onClick={() => moveStep(idx, 1)}>
//                     <ChevronDown className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setExpandedIdx(isExpanded ? null : idx)}>
//                     <Settings2 className="h-3.5 w-3.5" />
//                   </Button>
//                   <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => removeStep(idx)}>
//                     <Trash2 className="h-3.5 w-3.5" />
//                   </Button>
//                 </div>
//               </div>
//               {isExpanded && (
//                 <div className="border-t px-3 pb-3 pt-2.5 space-y-3 bg-muted/30">
//                   {meta.enrichFields.length > 0 && (
//                     <div>
//                       <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide mb-1.5">
//                         Target Fields
//                       </p>
//                       <div className="flex flex-wrap gap-1.5">
//                         {meta.enrichFields.map((field) => {
//                           const checked = step.targetFields.includes(field.key);
//                           return (
//                             <label key={field.key} className="flex items-center gap-1 text-xs cursor-pointer">
//                               <Switch
//                                 checked={checked}
//                                 onCheckedChange={() => toggleField(idx, field.key)}
//                                 className="scale-75"
//                               />
//                               {field.label}
//                             </label>
//                           );
//                         })}
//                       </div>
//                     </div>
//                   )}
//                   <div className="grid grid-cols-[110px_1fr] items-center gap-2">
//                     <Label className="text-xs text-muted-foreground">Fallback to</Label>
//                     <Select
//                       value={step.fallbackTo ?? "__none__"}
//                       onValueChange={(v) => update(idx, { fallbackTo: v === "__none__" ? null : v })}
//                     >
//                       <SelectTrigger className="h-7 text-xs">
//                         <SelectValue />
//                       </SelectTrigger>
//                       <SelectContent>
//                         <SelectItem value="__none__" className="text-xs">None</SelectItem>
//                         {fallbackPlatforms
//                           .filter((p) => p !== step.platform)
//                           .map((p) => (
//                             <SelectItem key={p} value={p} className="text-xs">
//                               {getMeta(p).label}
//                             </SelectItem>
//                           ))}
//                       </SelectContent>
//                     </Select>
//                   </div>
//                 </div>
//               )}
//             </div>
//           );
//         })}

//         {available.length > 0 && (
//           <Select onValueChange={addStep}>
//             <SelectTrigger className="h-8 text-xs mt-2">
//               <SelectValue placeholder="+ Add enrichment platform" />
//             </SelectTrigger>
//             <SelectContent>
//               {available.map((k) => {
//                 const meta = getMeta(k);
//                 const connected = isConnected(k, connectedMap);
//                 return (
//                   <SelectItem key={k} value={k} className="text-xs">
//                     {meta.label}{connected ? " ✓" : " (not connected)"}
//                   </SelectItem>
//                 );
//               })}
//             </SelectContent>
//           </Select>
//         )}
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: FlowSummary (Pipeline preview under Form View)
// // ─────────────────────────────────────────────────────────────────────────────

// function FlowSummary({
//   draft,
//   connectedMap,
// }: {
//   draft: EditableFlow;
//   connectedMap: Record<string, boolean>;
// }) {
//   const activeSources = draft.sourceSteps.filter((s) => s.enabled);
//   const activeEnrich = draft.enrichmentSteps.filter((s) => s.enabled);
//   const g = draft.qualityGates;
//   const gateCount =
//     (g.requireEmail ? 1 : 0) +
//     (g.requireVerifiedEmail ? 1 : 0) +
//     (g.requireCompanySize ? 1 : 0) +
//     (g.excludeDomains.length > 0 ? 1 : 0) +
//     (g.llmScoreThreshold > 0 ? 1 : 0);

//   return (
//     <Card>
//       <CardHeader className="pb-3">
//         <CardTitle className="text-sm flex items-center gap-2">
//           <Zap className="h-4 w-4 text-primary" /> Pipeline Preview
//         </CardTitle>
//         <CardDescription className="text-xs">
//           How prospects flow through this configuration at execution time.
//         </CardDescription>
//       </CardHeader>
//       <CardContent>
//         <div className="flex items-center gap-2 overflow-x-auto pb-2">
//           {/* Source */}
//           <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
//             <div className="flex items-center justify-between mb-2">
//               <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Source</p>
//               <Badge variant="secondary" className="text-[10px] h-4 py-0">{activeSources.length}</Badge>
//             </div>
//             <div className="space-y-1">
//               {activeSources.length === 0 && <p className="text-xs text-muted-foreground/70">No active sources</p>}
//               {activeSources.map((s) => {
//                 const meta = getMeta(s.platform);
//                 return (
//                   <div key={s.platform} className="flex items-center gap-1.5">
//                     <Badge variant="outline" className={cn("text-xs", meta.badgeColor)}>{meta.label}</Badge>
//                     {!isConnected(s.platform, connectedMap) && <AlertCircle className="h-3 w-3 text-amber-500" />}
//                   </div>
//                 );
//               })}
//             </div>
//           </div>

//           <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

//           {/* Enrich */}
//           <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
//             <div className="flex items-center justify-between mb-2">
//               <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Enrich</p>
//               <Badge variant="secondary" className="text-[10px] h-4 py-0">{activeEnrich.length}</Badge>
//             </div>
//             <div className="space-y-1">
//               {activeEnrich.length === 0 && <p className="text-xs text-muted-foreground/70">None (optional)</p>}
//               {activeEnrich.map((s) => {
//                 const meta = getMeta(s.platform);
//                 return (
//                   <div key={s.platform} className="flex items-center gap-1.5">
//                     <Badge variant="outline" className={cn("text-xs", meta.badgeColor)}>{meta.label}</Badge>
//                     {!isConnected(s.platform, connectedMap) && <AlertCircle className="h-3 w-3 text-amber-500" />}
//                   </div>
//                 );
//               })}
//             </div>
//           </div>

//           <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

//           {/* Gates */}
//           <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
//             <div className="flex items-center justify-between mb-2">
//               <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Gates</p>
//               <Badge variant="secondary" className="text-[10px] h-4 py-0">{gateCount}</Badge>
//             </div>
//             <div className="space-y-1">
//               {gateCount === 0 && <p className="text-xs text-muted-foreground/70">No gates active</p>}
//               {g.requireEmail && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">Email</Badge>}
//               {g.requireVerifiedEmail && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">Verified</Badge>}
//               {g.requireCompanySize && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">≥{g.minCompanySize} emp</Badge>}
//               {g.llmScoreThreshold > 0 && <Badge variant="outline" className="text-xs bg-violet-100 text-violet-700 border-violet-200">LLM ≥{g.llmScoreThreshold.toFixed(2)}</Badge>}
//               {g.excludeDomains.length > 0 && <Badge variant="outline" className="text-xs bg-red-100 text-red-700 border-red-200">{g.excludeDomains.length} domains</Badge>}
//             </div>
//           </div>

//           <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

//           {/* Output */}
//           <div className="rounded-lg border border-primary/40 bg-primary/5 p-3 min-w-[130px] flex-1">
//             <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Qualified Prospects</p>
//             <div className="flex items-center gap-1.5 text-primary">
//               <CheckCircle2 className="h-4 w-4" />
//               <span className="text-sm font-medium">Ready for campaign</span>
//             </div>
//           </div>
//         </div>
//       </CardContent>
//     </Card>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: DraggableStepCard (used inside Visual Builder)
// // ─────────────────────────────────────────────────────────────────────────────

// function DraggableStepCard({
//   id,
//   platform,
//   enabled,
//   priority,
//   isEnrich,
//   connected,
//   free,
//   onToggle,
//   onRemove,
// }: {
//   id: string;
//   platform: string;
//   enabled: boolean;
//   priority: number;
//   isEnrich?: boolean;
//   connected: boolean;
//   free: boolean;
//   onToggle: (enabled: boolean) => void;
//   onRemove: () => void;
// }) {
//   const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
//   const meta = getMeta(platform);

//   return (
//     <div
//       ref={setNodeRef}
//       style={{ transform: CSS.Transform.toString(transform), transition }}
//       className={cn(
//         "group relative flex items-center gap-2 rounded-lg border bg-card p-2.5 shadow-sm transition-all",
//         isDragging && "opacity-50 shadow-lg ring-2 ring-primary/40",
//         !enabled && "opacity-60",
//         meta.badgeColor,
//         !connected && !free && "ring-1 ring-amber-300/60",
//       )}
//     >
//       <button
//         type="button"
//         className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground touch-none"
//         {...attributes}
//         {...listeners}
//       >
//         <GripVertical className="h-4 w-4" />
//       </button>
//       <Badge variant="outline" className={cn("shrink-0 font-mono text-[10px] h-5 w-5 justify-center p-0", meta.badgeColor)}>
//         {priority}
//       </Badge>
//       <div className="flex-1 min-w-0">
//         <div className="flex items-center gap-1.5">
//           <p className="text-sm font-medium truncate">{meta.label}</p>
//           {free ? (
//             <span className="text-[10px] font-medium text-green-700">free</span>
//           ) : connected ? (
//             <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-emerald-700">
//               <CheckCircle2 className="h-3 w-3" /> ✓
//             </span>
//           ) : (
//             <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-700">
//               <AlertCircle className="h-3 w-3" /> Not Connected
//             </span>
//           )}
//         </div>
//         {isEnrich && <p className="text-[10px] text-muted-foreground">Enrichment step</p>}
//       </div>
//       <Switch checked={enabled} onCheckedChange={onToggle} className="scale-75" />
//       <button
//         type="button"
//         onClick={onRemove}
//         className="text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
//         aria-label="Remove step"
//       >
//         <X className="h-3.5 w-3.5" />
//       </button>
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: VisualFlowBuilder
// // ─────────────────────────────────────────────────────────────────────────────

// function VisualFlowBuilder({
//   draft,
//   connectedMap,
//   onUpdate,
// }: {
//   draft: EditableFlow;
//   connectedMap: Record<string, boolean>;
//   onUpdate: (patch: Partial<EditableFlow>) => void;
// }) {
//   const sensors = useSensors(
//     useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
//     useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
//   );

//   const sourceItems = draft.sourceSteps.map((s, i) => ({ id: `src-${i}-${s.platform}`, ...s }));
//   const enrichItems = draft.enrichmentSteps.map((s, i) => ({ id: `enr-${i}-${s.platform}`, ...s }));

//   function handleSourceDragEnd(e: DragEndEvent) {
//     const { active, over } = e;
//     if (!over || active.id === over.id) return;
//     const oldIdx = sourceItems.findIndex((s) => s.id === active.id);
//     const newIdx = sourceItems.findIndex((s) => s.id === over.id);
//     if (oldIdx < 0 || newIdx < 0) return;
//     const reordered = arrayMove(draft.sourceSteps, oldIdx, newIdx);
//     reordered.forEach((s, i) => (s.priority = i + 1));
//     onUpdate({ sourceSteps: reordered });
//   }

//   function handleEnrichDragEnd(e: DragEndEvent) {
//     const { active, over } = e;
//     if (!over || active.id === over.id) return;
//     const oldIdx = enrichItems.findIndex((s) => s.id === active.id);
//     const newIdx = enrichItems.findIndex((s) => s.id === over.id);
//     if (oldIdx < 0 || newIdx < 0) return;
//     const reordered = arrayMove(draft.enrichmentSteps, oldIdx, newIdx);
//     reordered.forEach((s, i) => (s.priority = i + 1));
//     onUpdate({ enrichmentSteps: reordered });
//   }

//   function addSourceStep(platform: string) {
//     const meta = getMeta(platform);
//     const queryOverrides: Record<string, string> = {};
//     for (const f of meta.sourceFields) queryOverrides[f.key] = "";
//     onUpdate({
//       sourceSteps: [
//         ...draft.sourceSteps,
//         { platform, enabled: true, priority: draft.sourceSteps.length + 1, queryOverrides },
//       ],
//     });
//   }

//   function addEnrichStep(platform: string) {
//     const meta = getMeta(platform);
//     onUpdate({
//       enrichmentSteps: [
//         ...draft.enrichmentSteps,
//         {
//           platform,
//           enabled: true,
//           priority: draft.enrichmentSteps.length + 1,
//           targetFields: meta.enrichFields.map((f) => f.key),
//           fallbackTo: null,
//         },
//       ],
//     });
//   }

//   // Palettes — connected first
//   const sourcePalette = ALL_SOURCE_KEYS
//     .filter((k) => !draft.sourceSteps.some((s) => s.platform === k))
//     .sort((a, b) => {
//       const aConn = isConnected(a, connectedMap) ? 1 : 0;
//       const bConn = isConnected(b, connectedMap) ? 1 : 0;
//       return bConn - aConn;
//     });

//   const enrichPalette = ALL_ENRICH_KEYS
//     .filter((k) => !draft.enrichmentSteps.some((s) => s.platform === k))
//     .sort((a, b) => {
//       const aConn = isConnected(a, connectedMap) ? 1 : 0;
//       const bConn = isConnected(b, connectedMap) ? 1 : 0;
//       return bConn - aConn;
//     });

//   // Unconnected warning
//   const unconnectedSrc = draft.sourceSteps.filter((s) => s.enabled && !isConnected(s.platform, connectedMap));
//   const unconnectedEnr = draft.enrichmentSteps.filter((s) => s.enabled && !isConnected(s.platform, connectedMap));
//   const totalUnconn = unconnectedSrc.length + unconnectedEnr.length;

//   return (
//     <div className="space-y-4">
//       <Card>
//         <CardHeader className="pb-3">
//           <div className="flex items-center gap-2">
//             <Workflow className="h-5 w-5 text-primary" />
//             <CardTitle className="text-base">Visual Flow Builder</CardTitle>
//           </div>
//           <p className="text-xs text-muted-foreground mt-1">
//             Drag steps to reorder priority. Click in the palette to add platforms. Toggle the Switch to enable/disable a step.
//             Enrichment is optional — leave the ENRICH column empty to skip it.
//           </p>
//           {totalUnconn > 0 && (
//             <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 flex items-start gap-2">
//               <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
//               <div className="leading-relaxed">
//                 <p className="font-medium">
//                   {totalUnconn} enabled step{totalUnconn > 1 ? "s" : ""} missing API key:{" "}
//                   {Array.from(new Set([...unconnectedSrc, ...unconnectedEnr].map((s) => getMeta(s.platform).label))).join(", ")}
//                 </p>
//                 <p className="mt-0.5">
//                   Save is blocked until you toggle them off or wire the API key in{" "}
//                   <em>Setup → Integrations</em>. Free sources (AI Web Search, LinkedIn) never need a key.
//                 </p>
//               </div>
//             </div>
//           )}
//         </CardHeader>
//       </Card>

//       <div className="flex gap-4">
//         {/* Left palette */}
//         <div className="w-56 shrink-0 space-y-4">
//           <div>
//             <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
//               <Search className="h-3 w-3" /> Source Platforms
//             </p>
//             <div className="space-y-1.5">
//               {sourcePalette.length === 0 && (
//                 <p className="text-[11px] text-muted-foreground italic px-1">All sources added</p>
//               )}
//               {sourcePalette.map((k) => {
//                 const meta = getMeta(k);
//                 const connected = isConnected(k, connectedMap);
//                 return (
//                   <button
//                     key={k}
//                     type="button"
//                     onClick={() => addSourceStep(k)}
//                     className={cn(
//                       "w-full flex items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm transition-all hover:shadow-sm hover:scale-[1.02]",
//                       meta.badgeColor,
//                     )}
//                   >
//                     <Plus className="h-3.5 w-3.5 shrink-0" />
//                     <span className="truncate flex-1">{meta.label}</span>
//                     {meta.free ? (
//                       <span className="text-[10px] text-green-700">free</span>
//                     ) : connected ? (
//                       <CheckCircle2 className="h-3 w-3 text-emerald-700 shrink-0" />
//                     ) : (
//                       <AlertCircle className="h-3 w-3 text-amber-700 shrink-0" />
//                     )}
//                   </button>
//                 );
//               })}
//             </div>
//           </div>

//           <div>
//             <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
//               <Sparkles className="h-3 w-3" /> Enrichment Platforms
//               <span className="ml-auto text-muted-foreground font-normal">(optional)</span>
//             </p>
//             <div className="space-y-1.5">
//               {enrichPalette.length === 0 && (
//                 <p className="text-[11px] text-muted-foreground italic px-1">All enrichers added</p>
//               )}
//               {enrichPalette.map((k) => {
//                 const meta = getMeta(k);
//                 const connected = isConnected(k, connectedMap);
//                 return (
//                   <button
//                     key={k}
//                     type="button"
//                     onClick={() => addEnrichStep(k)}
//                     className={cn(
//                       "w-full flex items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm transition-all hover:shadow-sm hover:scale-[1.02]",
//                       meta.badgeColor,
//                     )}
//                   >
//                     <Plus className="h-3.5 w-3.5 shrink-0" />
//                     <span className="truncate flex-1">{meta.label}</span>
//                     {connected ? (
//                       <CheckCircle2 className="h-3 w-3 text-emerald-700 shrink-0" />
//                     ) : (
//                       <AlertCircle className="h-3 w-3 text-amber-700 shrink-0" />
//                     )}
//                   </button>
//                 );
//               })}
//             </div>
//           </div>
//         </div>

//         {/* Canvas */}
//         <div className="flex-1 overflow-x-auto">
//           <div className="flex gap-3 min-w-[700px]">
//             {/* SOURCE */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-violet-500">
//                   <Search className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Source</h4>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
//                 <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleSourceDragEnd}>
//                   <SortableContext items={sourceItems.map((s) => s.id)} strategy={verticalListSortingStrategy}>
//                     {sourceItems.map((s, i) => (
//                       <DraggableStepCard
//                         key={s.id}
//                         id={s.id}
//                         platform={s.platform}
//                         enabled={s.enabled}
//                         priority={s.priority}
//                         free={getMeta(s.platform).free}
//                         connected={isConnected(s.platform, connectedMap)}
//                         onToggle={(en) => {
//                           const next = [...draft.sourceSteps];
//                           next[i] = { ...next[i], enabled: en };
//                           onUpdate({ sourceSteps: next });
//                         }}
//                         onRemove={() => {
//                           const next = draft.sourceSteps.filter((_, idx) => idx !== i);
//                           next.forEach((st, idx) => (st.priority = idx + 1));
//                           onUpdate({ sourceSteps: next });
//                         }}
//                       />
//                     ))}
//                   </SortableContext>
//                 </DndContext>
//                 {sourceItems.length === 0 && (
//                   <p className="text-[11px] text-muted-foreground italic text-center py-4">
//                     No source steps. Add platforms from the palette.
//                   </p>
//                 )}
//               </div>
//             </div>

//             <div className="flex items-center pt-7">
//               <ArrowRight className="h-4 w-4 text-muted-foreground" />
//             </div>

//             {/* ENRICH */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-500">
//                   <Sparkles className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Enrich</h4>
//                 <span className="text-[10px] text-muted-foreground ml-1">(optional)</span>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
//                 <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleEnrichDragEnd}>
//                   <SortableContext items={enrichItems.map((s) => s.id)} strategy={verticalListSortingStrategy}>
//                     {enrichItems.map((s, i) => (
//                       <DraggableStepCard
//                         key={s.id}
//                         id={s.id}
//                         platform={s.platform}
//                         enabled={s.enabled}
//                         priority={s.priority}
//                         isEnrich
//                         free={false}
//                         connected={isConnected(s.platform, connectedMap)}
//                         onToggle={(en) => {
//                           const next = [...draft.enrichmentSteps];
//                           next[i] = { ...next[i], enabled: en };
//                           onUpdate({ enrichmentSteps: next });
//                         }}
//                         onRemove={() => {
//                           const next = draft.enrichmentSteps.filter((_, idx) => idx !== i);
//                           next.forEach((st, idx) => (st.priority = idx + 1));
//                           onUpdate({ enrichmentSteps: next });
//                         }}
//                       />
//                     ))}
//                   </SortableContext>
//                 </DndContext>
//                 {enrichItems.length === 0 && (
//                   <p className="text-[11px] text-muted-foreground italic text-center py-4">
//                     Empty — enrichment skipped.
//                   </p>
//                 )}
//               </div>
//             </div>

//             <div className="flex items-center pt-7">
//               <ArrowRight className="h-4 w-4 text-muted-foreground" />
//             </div>

//             {/* GATE */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-red-500">
//                   <ShieldCheck className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Gate</h4>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2.5">
//                 {(
//                   [
//                     { label: "Require Email", checked: draft.qualityGates.requireEmail, key: "requireEmail" as keyof QualityGates },
//                     { label: "Verified Email", checked: draft.qualityGates.requireVerifiedEmail, key: "requireVerifiedEmail" as keyof QualityGates },
//                   ] as Array<{ label: string; checked: boolean; key: keyof QualityGates }>
//                 ).map(({ label, checked, key }) => (
//                   <div key={key} className="flex items-center justify-between rounded-lg border bg-card p-2.5">
//                     <Label className="text-xs">{label}</Label>
//                     <Switch
//                       checked={checked as boolean}
//                       onCheckedChange={(v) => onUpdate({ qualityGates: { ...draft.qualityGates, [key]: v } })}
//                       className="scale-75"
//                     />
//                   </div>
//                 ))}
//                 <div className="rounded-lg border bg-card p-2.5">
//                   <Label className="text-xs">Min Company Size</Label>
//                   <Input
//                     type="number"
//                     value={draft.qualityGates.minCompanySize}
//                     onChange={(e) =>
//                       onUpdate({
//                         qualityGates: {
//                           ...draft.qualityGates,
//                           minCompanySize: Number(e.target.value),
//                           requireCompanySize: Number(e.target.value) > 0,
//                         },
//                       })
//                     }
//                     className="h-7 w-full text-xs mt-1"
//                   />
//                 </div>
//                 <div className="rounded-lg border bg-card p-2.5">
//                   <Label className="text-xs">LLM Threshold (0–1)</Label>
//                   <Input
//                     type="number"
//                     min={0}
//                     max={1}
//                     step={0.05}
//                     value={draft.qualityGates.llmScoreThreshold}
//                     onChange={(e) =>
//                       onUpdate({ qualityGates: { ...draft.qualityGates, llmScoreThreshold: Number(e.target.value) } })
//                     }
//                     className="h-7 w-full text-xs mt-1"
//                   />
//                 </div>
//               </div>
//             </div>

//             <div className="flex items-center pt-7">
//               <ArrowRight className="h-4 w-4 text-muted-foreground" />
//             </div>

//             {/* SCORE */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-500">
//                   <BarChart2 className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Score</h4>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
//                 <div className="rounded-lg border bg-blue-50 border-blue-200 p-2.5 text-xs text-blue-700">
//                   <p className="font-medium">ICP Fit Score</p>
//                   <p className="text-[11px] text-muted-foreground mt-0.5">Auto-computed from ICP + persona + intent signals.</p>
//                 </div>
//                 <div className="rounded-lg border bg-blue-50 border-blue-200 p-2.5 text-xs text-blue-700">
//                   <p className="font-medium">Urgency Tier</p>
//                   <p className="text-[11px] text-muted-foreground mt-0.5">TIER_1–TIER_3 based on signal recency.</p>
//                 </div>
//               </div>
//             </div>

//             <div className="flex items-center pt-7">
//               <ArrowRight className="h-4 w-4 text-muted-foreground" />
//             </div>

//             {/* IMPORT */}
//             <div className="flex-1">
//               <div className="flex items-center gap-1.5 px-1 mb-2">
//                 <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-500">
//                   <Download className="h-3.5 w-3.5 text-white" />
//                 </div>
//                 <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Import</h4>
//               </div>
//               <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
//                 <div className="rounded-lg border bg-emerald-50 border-emerald-200 p-2.5 text-xs text-emerald-700">
//                   <p className="font-medium">Prospect Table</p>
//                   <p className="text-[11px] text-muted-foreground mt-0.5">Surviving prospects imported with ICP + intent tags.</p>
//                 </div>
//                 <div className="rounded-lg border bg-emerald-50 border-emerald-200 p-2.5 text-xs text-emerald-700">
//                   <p className="font-medium">Fire Webhooks</p>
//                   <p className="text-[11px] text-muted-foreground mt-0.5">FLOW_RUN_COMPLETED fires to all active webhooks.</p>
//                 </div>
//               </div>
//             </div>
//           </div>
//         </div>
//       </div>

//       {/* Status summary */}
//       <Card>
//         <CardContent className="pt-4">
//           <div className="flex flex-wrap gap-3 text-xs">
//             <Badge variant="outline" className="gap-1">
//               <Search className="h-3 w-3" />
//               {draft.sourceSteps.filter((s) => s.enabled).length}/{draft.sourceSteps.length} source steps active
//             </Badge>
//             <Badge variant="outline" className="gap-1">
//               <Sparkles className="h-3 w-3" />
//               {draft.enrichmentSteps.filter((s) => s.enabled).length}/{draft.enrichmentSteps.length} enrich steps active
//             </Badge>
//             <Badge variant="outline" className="gap-1">
//               <ShieldCheck className="h-3 w-3" />
//               {[
//                 draft.qualityGates.requireEmail && "Email",
//                 draft.qualityGates.requireVerifiedEmail && "Verified",
//                 draft.qualityGates.requireCompanySize && `Size≥${draft.qualityGates.minCompanySize}`,
//                 draft.qualityGates.llmScoreThreshold > 0 && `Score≥${draft.qualityGates.llmScoreThreshold.toFixed(2)}`,
//                 (draft.qualityGates.excludeDomains?.length || 0) > 0 &&
//                   `${draft.qualityGates.excludeDomains.length} excluded`,
//               ]
//                 .filter(Boolean)
//                 .join(", ") || "No gates"}
//             </Badge>
//           </div>
//         </CardContent>
//       </Card>
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: RunMonitor (live polling inside Run dialog)
// // ─────────────────────────────────────────────────────────────────────────────

// function RunMonitor({
//   flowName,
//   runId,
// }: {
//   flowName: string;
//   runId: string;
// }) {
//   const [elapsed, setElapsed] = useState(0);
//   const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

//   const { data: run, isError } = useQuery<FlowRunDetail>({
//     queryKey: ["flow-run-monitor", runId],
//     queryFn: () => flowsApi.getRun(runId) as Promise<FlowRunDetail>,
//     refetchInterval: (query) => {
//       const s = (query.state.data as FlowRunDetail | undefined)?.status;
//       if (s === "COMPLETED" || s === "FAILED" || s === "CANCELLED") return false;
//       return 2000;
//     },
//     retry: 3,
//   });

//   useEffect(() => {
//     timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
//     return () => { if (timerRef.current) clearInterval(timerRef.current); };
//   }, []);

//   useEffect(() => {
//     if (run?.status === "COMPLETED" || run?.status === "FAILED" || run?.status === "CANCELLED") {
//       if (timerRef.current) clearInterval(timerRef.current);
//     }
//   }, [run?.status]);

//   const status = run?.status ?? "RUNNING";
//   const isTerminal = status === "COMPLETED" || status === "FAILED" || status === "CANCELLED";

//   const steps = run?.steps ?? [];

//   let stats: Record<string, unknown> = {};
//   try {
//     if (run?.stats && typeof run.stats === "object") stats = run.stats as Record<string, unknown>;
//     else if (typeof run?.stats === "string") stats = JSON.parse(run.stats as string);
//   } catch { /* ignore */ }

//   let importedCount = 0;
//   try {
//     if (Array.isArray(run?.importedProspectIds)) importedCount = (run.importedProspectIds as string[]).length;
//     else if (typeof run?.importedProspectIds === "string") importedCount = JSON.parse(run.importedProspectIds as string).length;
//   } catch { /* ignore */ }

//   const sourced = Number(stats.sourced ?? stats.source_count ?? stats.totalSourced ?? 0);
//   const deduped = Number(stats.deduped ?? stats.dedup_count ?? stats.totalDeduped ?? 0);
//   const enriched = Number(stats.enriched ?? stats.enrich_count ?? stats.totalEnriched ?? 0);
//   const gated = Number(stats.gated ?? stats.gate_count ?? stats.totalGatedOut ?? 0);
//   const imported_ = Number(stats.imported ?? importedCount ?? stats.totalImported ?? 0);

//   function fmt(s: number) {
//     if (s < 60) return `${s}s`;
//     return `${Math.floor(s / 60)}m ${s % 60}s`;
//   }

//   const statusBanner = {
//     RUNNING:   { border: "border-blue-200 bg-blue-50",   icon: <Activity className="h-4 w-4 animate-pulse" />, color: "text-blue-600",  label: "Running" },
//     COMPLETED: { border: "border-green-200 bg-green-50", icon: <CheckCircle2 className="h-4 w-4" />,           color: "text-green-600", label: "Completed" },
//     FAILED:    { border: "border-red-200 bg-red-50",     icon: <XCircle className="h-4 w-4" />,                color: "text-red-600",   label: "Failed" },
//     CANCELLED: { border: "border-gray-200 bg-gray-50",   icon: <XCircle className="h-4 w-4" />,                color: "text-gray-500",  label: "Cancelled" },
//     PENDING:   { border: "border-amber-200 bg-amber-50", icon: <Activity className="h-4 w-4 animate-pulse" />, color: "text-amber-600", label: "Pending" },
//   } as Record<string, { border: string; icon: React.ReactNode; color: string; label: string }>;

//   const sb = statusBanner[status] ?? statusBanner["RUNNING"];

//   return (
//     <div className="space-y-4">
//       {/* Header */}
//       <div className={`flex items-center gap-3 rounded-lg border p-4 ${sb.border}`}>
//         <span className={sb.color}>{sb.icon}</span>
//         <div className="flex-1 min-w-0">
//           <p className={`text-sm font-semibold ${sb.color}`}>{sb.label}</p>
//           <p className="text-xs text-muted-foreground truncate">{flowName}</p>
//         </div>
//         <div className="text-right flex-shrink-0">
//           <p className="text-xs font-mono text-muted-foreground">{fmt(elapsed)}</p>
//           <p className="text-[10px] text-muted-foreground">elapsed</p>
//         </div>
//       </div>

//       <div className="flex items-center gap-2 text-xs text-muted-foreground">
//         <span className="font-medium">Run ID:</span>
//         <span className="font-mono truncate">{runId}</span>
//       </div>

//       {/* Step rows */}
//       {steps.length > 0 ? (
//         <div className="space-y-1.5">
//           <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Steps</p>
//           {steps.map((step) => {
//             const dotColors: Record<string, string> = {
//               COMPLETED: "bg-green-500",
//               SUCCESS:   "bg-green-500",
//               RUNNING:   "bg-blue-500 animate-pulse",
//               FAILED:    "bg-red-500",
//               SKIPPED:   "bg-gray-300",
//               PENDING:   "bg-gray-200",
//             };
//             const badgeColors: Record<string, string> = {
//               COMPLETED: "bg-green-100 text-green-700",
//               SUCCESS:   "bg-green-100 text-green-700",
//               RUNNING:   "bg-blue-100 text-blue-700",
//               FAILED:    "bg-red-100 text-red-700",
//               SKIPPED:   "bg-gray-100 text-gray-500",
//               PENDING:   "bg-gray-100 text-gray-500",
//             };
//             let stepMetrics: Record<string, unknown> = {};
//             try {
//               if (step.metrics && typeof step.metrics === "object") stepMetrics = step.metrics as Record<string, unknown>;
//               else if (typeof step.metrics === "string") stepMetrics = JSON.parse(step.metrics as string);
//             } catch { /* ignore */ }
//             return (
//               <div key={step.id} className="flex items-center gap-2.5 rounded-md border px-3 py-2 text-xs">
//                 <span className={`h-2 w-2 rounded-full flex-shrink-0 ${dotColors[step.status] ?? "bg-gray-200"}`} />
//                 <span className="font-medium capitalize flex-1 truncate">
//                   {step.kind.toLowerCase()} — {step.stepKey}
//                 </span>
//                 {step.durationMs != null && <span className="text-muted-foreground">{step.durationMs}ms</span>}
//                 {stepMetrics.count !== undefined && <span className="text-muted-foreground">{String(stepMetrics.count)} results</span>}
//                 <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${badgeColors[step.status] ?? "bg-gray-100 text-gray-500"}`}>
//                   {step.status}
//                 </span>
//               </div>
//             );
//           })}
//         </div>
//       ) : !isTerminal ? (
//         <div className="flex items-center gap-3 rounded-md border border-dashed px-4 py-5 text-xs text-muted-foreground">
//           <Activity className="h-4 w-4 animate-pulse text-blue-500 flex-shrink-0" />
//           <div>
//             <p className="font-medium">Pipeline executing…</p>
//             <p>Step details will appear here as the flow progresses.</p>
//           </div>
//         </div>
//       ) : null}

//       {/* Funnel results */}
//       {isTerminal && status === "COMPLETED" && (
//         <div className="rounded-lg border bg-muted/30 p-3">
//           <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Results</p>
//           <div className="grid grid-cols-5 gap-1 text-center">
//             {[
//               { label: "Sourced",  value: sourced || "—",   color: "text-blue-600" },
//               { label: "Deduped",  value: deduped || "—",   color: "text-indigo-600" },
//               { label: "Enriched", value: enriched || "—",  color: "text-orange-600" },
//               { label: "Gated",    value: gated || "—",     color: "text-red-600" },
//               { label: "Imported", value: imported_ || "—", color: "text-green-600" },
//             ].map((item) => (
//               <div key={item.label} className="rounded-md border bg-background p-2">
//                 <p className={`text-lg font-bold ${item.color}`}>{String(item.value)}</p>
//                 <p className="text-[10px] text-muted-foreground">{item.label}</p>
//               </div>
//             ))}
//           </div>
//           {imported_ > 0 && (
//             <p className="text-xs text-green-700 mt-2 text-center font-medium">
//               ✓ {imported_} prospect{imported_ !== 1 ? "s" : ""} added to your Prospects table
//             </p>
//           )}
//         </div>
//       )}

//       {run?.errorMessage && (
//         <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
//           <p className="font-semibold mb-0.5">Error</p>
//           <p>{run.errorMessage}</p>
//         </div>
//       )}

//       {isError && (
//         <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
//           Could not fetch run status. The run may still be executing in the background.
//         </div>
//       )}

//       {!isTerminal && (
//         <div className="flex items-center gap-2 text-xs text-blue-600">
//           <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
//           Polling for updates every 2 seconds…
//         </div>
//       )}
//     </div>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: RunFlowDialog
// // ─────────────────────────────────────────────────────────────────────────────

// // LLM config shape returned by GET /api/v1/llm-configs
// interface LlmConfigOption {
//   id: string;
//   provider: string;
//   display_name: string;
//   model_name: string;
//   is_active: boolean;
//   is_default: boolean;
// }

// function RunFlowDialog({
//   flow,
//   open,
//   onClose,
//   onRun,
//   isRunning,
//   activeRunId,
// }: {
//   flow: ProspectingFlow;
//   open: boolean;
//   onClose: () => void;
//   onRun: (icpProfileId: string, maxProspects: number, dryRun: boolean, llmConfigId?: string) => void;
//   isRunning: boolean;
//   activeRunId: string | null;
// }) {
//   const [selectedIcp, setSelectedIcp] = useState("");
//   const [maxProspects, setMaxProspects] = useState(10);
//   const [dryRun, setDryRun] = useState(false);
//   const [llmConfigId, setLlmConfigId] = useState("__default__");

//   const phase = activeRunId ? "running" : "configure";

//   // Fetch ICP profiles
//   const { data: icpData } = useQuery({
//     queryKey: ["icp-profiles-for-run"],
//     queryFn: () =>
//       http.get<unknown>("/api/v1/icp-profiles").then((r) =>
//         Array.isArray(r) ? (r as IcpLite[]) : ((r as { items?: IcpLite[] })?.items ?? []),
//       ),
//     enabled: open && phase === "configure",
//   });
//   const icpProfiles = (icpData ?? []) as IcpLite[];

//   // Fetch configured LLM models from the tenant LLM config endpoint
//   const { data: llmData, isLoading: llmLoading } = useQuery({
//     queryKey: ["llm-configs-for-run"],
//     queryFn: () =>
//       http.get<LlmConfigOption[] | { items?: LlmConfigOption[] }>("/api/v1/llm-configs").then((r) =>
//         Array.isArray(r) ? r : (r as { items?: LlmConfigOption[] })?.items ?? [],
//       ),
//     enabled: open && phase === "configure",
//     staleTime: 60_000,
//   });
//   const llmConfigs = ((llmData ?? []) as LlmConfigOption[]).filter((c) => c.is_active);
//   const defaultLlm = llmConfigs.find((c) => c.is_default);

//   // Auto-select the default LLM when configs load
//   useEffect(() => {
//     if (defaultLlm && llmConfigId === "__default__") {
//       // Keep "__default__" selected — the backend resolves it automatically
//       // Just shows the default name in the UI
//     }
//   }, [defaultLlm, llmConfigId]);

//   function handleClose() {
//     setSelectedIcp("");
//     setLlmConfigId("__default__");
//     onClose();
//   }

//   function handleRun() {
//     const configToSend = llmConfigId === "__default__" ? undefined : llmConfigId;
//     onRun(selectedIcp, maxProspects, dryRun, configToSend);
//   }

//   // Live monitor phase — switch dialog to progress view
//   if (phase === "running" && activeRunId) {
//     return (
//       <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
//         <DialogContent className="max-w-lg">
//           <DialogHeader>
//             <DialogTitle className="flex items-center gap-2">
//               <PlayCircle className="h-4 w-4 text-emerald-600" /> Flow Running
//             </DialogTitle>
//             <DialogDescription>
//               Live progress for &ldquo;{flow.name}&rdquo;. Updates every 2 seconds.
//             </DialogDescription>
//           </DialogHeader>
//           <RunMonitor flowName={flow.name} runId={activeRunId} />
//           <DialogFooter>
//             <Button variant="outline" onClick={handleClose}>Close</Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>
//     );
//   }

//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
//       <DialogContent className="max-w-md">
//         <DialogHeader>
//           <DialogTitle className="flex items-center gap-2">
//             <PlayCircle className="h-4 w-4 text-emerald-600" /> Run Flow
//           </DialogTitle>
//           <DialogDescription>
//             Execute &ldquo;{flow.name}&rdquo; against an ICP profile. The pipeline runs in the
//             background — results appear in 30–90 seconds depending on your source platforms.
//           </DialogDescription>
//         </DialogHeader>
//         <div className="space-y-4 py-2">
//           {/* ICP Profile selector */}
//           <div className="space-y-2">
//             <Label>ICP Profile *</Label>
//             <Select value={selectedIcp} onValueChange={setSelectedIcp}>
//               <SelectTrigger><SelectValue placeholder="Select ICP profile…" /></SelectTrigger>
//               <SelectContent>
//                 {icpProfiles.map((p) => (
//                   <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
//                 ))}
//                 {icpProfiles.length === 0 && (
//                   <SelectItem value="__none__" disabled>No ICP profiles — create one first</SelectItem>
//                 )}
//               </SelectContent>
//             </Select>
//             {icpProfiles.length === 0 && (
//               <p className="text-xs text-amber-600">
//                 Go to ICP Profiles and create a profile before running a flow.
//               </p>
//             )}
//           </div>

//           <div className="grid grid-cols-2 gap-4">
//             {/* Max Prospects */}
//             <div className="space-y-2">
//               <Label>Max Prospects</Label>
//               <Input
//                 type="number"
//                 min={1}
//                 max={500}
//                 value={maxProspects}
//                 onChange={(e) => setMaxProspects(Math.max(1, Number(e.target.value) || 1))}
//               />
//               <p className="text-[11px] text-muted-foreground">
//                 Higher = longer run time
//               </p>
//             </div>

//             {/* LLM Config — now populated from real API */}
//             <div className="space-y-2">
//               <Label className="flex items-center gap-1">
//                 LLM Model
//                 {llmLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
//               </Label>
//               <Select
//                 value={llmConfigId}
//                 onValueChange={setLlmConfigId}
//               >
//                 <SelectTrigger>
//                   <SelectValue placeholder="Select model…" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="__default__">
//                     {defaultLlm
//                       ? `Default — ${defaultLlm.display_name || defaultLlm.model_name}`
//                       : "Default (auto-select)"}
//                   </SelectItem>
//                   {llmConfigs
//                     .filter((c) => !c.is_default)
//                     .map((c) => (
//                       <SelectItem key={c.id} value={c.id}>
//                         {c.display_name || c.model_name}
//                         <span className="ml-1 text-xs text-muted-foreground capitalize">
//                           ({c.provider})
//                         </span>
//                       </SelectItem>
//                     ))}
//                   {llmConfigs.length === 0 && !llmLoading && (
//                     <SelectItem value="__none__" disabled>
//                       No models configured — go to Setup → LLM Models
//                     </SelectItem>
//                   )}
//                 </SelectContent>
//               </Select>
//               {llmConfigs.length === 0 && !llmLoading && (
//                 <p className="text-[11px] text-amber-600">
//                   No LLM configured — prospects will use fallback data.
//                 </p>
//               )}
//             </div>
//           </div>

//           {/* Dry Run toggle */}
//           <div className="flex items-center justify-between rounded-md border p-3">
//             <div>
//               <div className="text-sm font-medium flex items-center gap-1.5">
//                 <AlertCircle className="h-3.5 w-3.5 text-amber-500" /> Dry Run
//               </div>
//               <div className="text-[11px] text-muted-foreground">
//                 Run the full pipeline without saving prospects to your database.
//               </div>
//             </div>
//             <Switch checked={dryRun} onCheckedChange={setDryRun} />
//           </div>

//           {/* Info banner about what happens */}
//           <div className="rounded-md bg-blue-50 border border-blue-200 px-3 py-2.5 text-xs text-blue-700 space-y-1">
//             <p className="font-medium">What happens when you click Run:</p>
//             <ol className="list-decimal list-inside space-y-0.5 text-[11px]">
//               <li>Flow starts immediately in the background (HTTP returns in ~1s)</li>
//               <li>This dialog switches to the live progress monitor</li>
//               <li>Source → Enrich → Gate → Score → Import pipeline runs</li>
//               <li>Results appear in Prospects when complete</li>
//             </ol>
//           </div>
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={handleClose} disabled={isRunning}>Cancel</Button>
//           <Button
//             onClick={handleRun}
//             disabled={isRunning || !selectedIcp}
//             className="bg-emerald-600 hover:bg-emerald-700 text-white"
//           >
//             {isRunning ? (
//               <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Starting…</>
//             ) : (
//               <><PlayCircle className="h-4 w-4 mr-2" /> Run Flow</>
//             )}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: TemplatesDialog
// // ─────────────────────────────────────────────────────────────────────────────

// function TemplatesDialog({
//   open,
//   onClose,
//   onClone,
// }: {
//   open: boolean;
//   onClose: () => void;
//   onClone: (templateId: string, name: string) => void;
// }) {
//   const [selected, setSelected] = useState<FlowTemplate | null>(null);
//   const [newName, setNewName] = useState("");

//   const { data, isLoading } = useQuery<FlowTemplate[]>({
//     queryKey: ["flow-templates"],
//     queryFn: () =>
//       http.get<{ items: FlowTemplate[]; total: number }>("/api/v1/flow-templates").then(
//         (r) => (Array.isArray(r) ? (r as FlowTemplate[]) : (r?.items ?? [])),
//       ),
//     enabled: open,
//   });
//   const templates = data ?? [];

//   const STRICTNESS_COLORS: Record<string, string> = {
//     strict: "bg-red-100 text-red-700",
//     medium: "bg-amber-100 text-amber-700",
//     loose:  "bg-green-100 text-green-700",
//   };

//   function handleClose() {
//     setSelected(null);
//     setNewName("");
//     onClose();
//   }

//   if (selected) {
//     return (
//       <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
//         <DialogContent className="max-w-md">
//           <DialogHeader>
//             <DialogTitle>Name your new flow</DialogTitle>
//             <DialogDescription>Cloning &ldquo;{selected.name}&rdquo; — give the new flow a name.</DialogDescription>
//           </DialogHeader>
//           <div className="space-y-3 py-2">
//             <div className="space-y-1.5">
//               <Label>Flow name *</Label>
//               <Input
//                 value={newName}
//                 onChange={(e) => setNewName(e.target.value)}
//                 placeholder={`${selected.name} (Copy)`}
//                 onKeyDown={(e) => {
//                   if (e.key === "Enter" && newName.trim()) {
//                     onClone(selected.id, newName.trim());
//                     handleClose();
//                   }
//                 }}
//                 autoFocus
//               />
//             </div>
//           </div>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setSelected(null)}>← Back</Button>
//             <Button
//               disabled={!newName.trim()}
//               onClick={() => { onClone(selected.id, newName.trim()); handleClose(); }}
//             >
//               Create flow
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>
//     );
//   }

//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
//       <DialogContent className="max-w-2xl">
//         <DialogHeader>
//           <DialogTitle>Flow Templates</DialogTitle>
//           <DialogDescription>Choose a pre-built template to start from. You can customise it after cloning.</DialogDescription>
//         </DialogHeader>
//         <div className="space-y-3 py-2 max-h-[60vh] overflow-y-auto">
//           {isLoading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
//           {templates.map((t) => (
//             <div key={t.id} className="border rounded-lg p-4">
//               <div className="flex items-start justify-between gap-3">
//                 <div className="flex-1 min-w-0">
//                   <div className="flex items-center gap-2 mb-1">
//                     <p className="font-medium text-sm">{t.name}</p>
//                     <span className={cn("text-[10px] rounded px-1.5 py-0.5 font-medium", STRICTNESS_COLORS[t.gate_strictness] ?? "bg-gray-100 text-gray-700")}>
//                       {t.gate_strictness}
//                     </span>
//                   </div>
//                   <p className="text-xs text-muted-foreground mb-2">{t.description}</p>
//                   <p className="text-[10px] text-muted-foreground mb-2">
//                     <span className="font-medium">Best for:</span> {t.recommended_for}
//                   </p>
//                   <div className="flex flex-wrap gap-1">
//                     {t.source_platforms.map((p) => {
//                       const meta = getMeta(p);
//                       return (
//                         <span key={p} className={cn("text-[10px] rounded px-1.5 py-0.5 font-medium border", meta.badgeColor)}>
//                           {meta.label}
//                         </span>
//                       );
//                     })}
//                     {t.enrichment_platforms.length > 0 && (
//                       <span className="text-[10px] text-muted-foreground ml-1">
//                         + {t.enrichment_platforms.map((p) => getMeta(p).label).join(", ")}
//                       </span>
//                     )}
//                   </div>
//                 </div>
//                 <Button
//                   size="sm"
//                   className="flex-shrink-0"
//                   onClick={() => { setSelected(t); setNewName(`${t.name} (Copy)`); }}
//                 >
//                   Use template
//                 </Button>
//               </div>
//             </div>
//           ))}
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={handleClose}>Close</Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Sub-component: DeleteDialog
// // ─────────────────────────────────────────────────────────────────────────────

// function DeleteDialog({
//   flow,
//   open,
//   onClose,
//   onConfirm,
//   isDeleting,
// }: {
//   flow: ProspectingFlow | null;
//   open: boolean;
//   onClose: () => void;
//   onConfirm: () => void;
//   isDeleting: boolean;
// }) {
//   return (
//     <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
//       <DialogContent className="max-w-sm">
//         <DialogHeader>
//           <DialogTitle>Delete flow?</DialogTitle>
//           <DialogDescription>
//             &ldquo;{flow?.name}&rdquo; will be permanently removed. Past run records are kept.
//           </DialogDescription>
//         </DialogHeader>
//         <DialogFooter>
//           <Button variant="outline" onClick={onClose}>Cancel</Button>
//           <Button variant="destructive" onClick={onConfirm} disabled={isDeleting}>
//             {isDeleting ? "Deleting…" : "Delete"}
//           </Button>
//         </DialogFooter>
//       </DialogContent>
//     </Dialog>
//   );
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Main Page Component
// // ─────────────────────────────────────────────────────────────────────────────

// export function FlowsPage() {
//   const qc = useQueryClient();

//   // ── UI state
//   const [selectedId, setSelectedId] = useState<string | null>(null);
//   const [draft, setDraft] = useState<EditableFlow | null>(null);
//   const [dirty, setDirty] = useState(false);
//   const [viewMode, setViewMode] = useState<"form" | "visual">("form");
//   const [runOpen, setRunOpen] = useState(false);
//   const [activeRunId, setActiveRunId] = useState<string | null>(null);
//   const [templatesOpen, setTemplatesOpen] = useState(false);
//   const [deleteTarget, setDeleteTarget] = useState<ProspectingFlow | null>(null);
//   const importRef = useRef<HTMLInputElement>(null);

//   // ── Queries
//   const { data, isLoading, isError, refetch } = useQuery({
//     queryKey: ["flows", "list"],
//     queryFn: () => flowsApi.listFlows({ isTemplate: false }),
//     retry: false,
//   });
//   const flows = useMemo(() => data?.items ?? [], [data]);

//   const { data: integrations } = useQuery<TenantIntegration[]>({
//     queryKey: ["integrations-for-flows"],
//     queryFn: () => integrationConfigApi.tenantList(),
//   });

//   const connectedMap = useMemo(
//     () => buildConnectedMap(integrations ?? []),
//     [integrations],
//   );

//   // Auto-select first (or default) flow
//   useEffect(() => {
//     if (flows.length > 0 && !selectedId && !draft) {
//       const def = flows.find((f) => f.isDefault) ?? flows[0];
//       setSelectedId(def.id);
//       setDraft(flowToEditable(def));
//       setDirty(false);
//     }
//   }, [flows, selectedId, draft]);

//   const selectedFlow = useMemo(() => flows.find((f) => f.id === selectedId) ?? null, [flows, selectedId]);

//   function selectFlow(f: ProspectingFlow) {
//     if (dirty && !window.confirm("You have unsaved changes. Discard them and switch flows?")) return;
//     setSelectedId(f.id);
//     setDraft(flowToEditable(f));
//     setDirty(false);
//   }

//   function startNew() {
//     if (dirty && !window.confirm("You have unsaved changes. Discard them?")) return;
//     setSelectedId(null);
//     setDraft(newEditable());
//     setDirty(true);
//   }

//   function updateDraft(patch: Partial<EditableFlow>) {
//     setDraft((prev) => prev ? { ...prev, ...patch } : prev);
//     setDirty(true);
//   }

//   // ── Mutations
//   const createMut = useMutation({
//     mutationFn: (body: ProspectingFlowInput) => flowsApi.createFlow(body),
//     onSuccess: (created) => {
//       toast.success("Flow created");
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       setSelectedId(created.id);
//       setDraft(flowToEditable(created));
//       setDirty(false);
//     },
//     onError: () => toast.error("Failed to create flow"),
//   });

//   const updateMut = useMutation({
//     mutationFn: ({ id, body }: { id: string; body: Partial<ProspectingFlowInput> }) =>
//       flowsApi.updateFlow(id, body),
//     onSuccess: (updated) => {
//       toast.success("Flow saved");
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       setDraft(flowToEditable(updated));
//       setDirty(false);
//     },
//     onError: () => toast.error("Failed to save flow"),
//   });

//   const deleteMut = useMutation({
//     mutationFn: (id: string) => flowsApi.removeFlow(id),
//     onSuccess: () => {
//       toast.success("Flow deleted");
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       setDeleteTarget(null);
//       setSelectedId(null);
//       setDraft(null);
//       setDirty(false);
//     },
//     onError: () => toast.error("Failed to delete flow"),
//   });

//   const runMut = useMutation({
//     mutationFn: ({ flowId, icpId, llmConfigId }: { flowId: string; icpId: string; llmConfigId?: string }) =>
//       flowsApi.runFlow(flowId, icpId, llmConfigId),
//     onSuccess: (result) => {
//       setActiveRunId(result.run_id);
//     },
//     onError: () => toast.error("Failed to start flow run"),
//   });

//   const cloneMut = useMutation({
//     mutationFn: ({ templateId, name }: { templateId: string; name: string }) =>
//       http.post<{ success: boolean; flow_id?: string }>("/api/v1/flow-templates/clone", {
//         template_id: templateId,
//         new_name: name,
//       }),
//     onSuccess: (result) => {
//       toast.success("Template cloned as new flow");
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       if (result.flow_id) setSelectedId(result.flow_id);
//     },
//     onError: () => toast.error("Failed to clone template"),
//   });

//   // ── Save
//   const handleSave = useCallback(() => {
//     if (!draft) return;
//     if (!draft.name.trim()) { toast.error("Flow name is required"); return; }

//     const missing = findUnconnectedEnabledSteps(draft, connectedMap);
//     if (missing.length > 0) {
//       toast.error("Save blocked — missing API keys", {
//         description: `${missing.length} enabled step${missing.length > 1 ? "s" : ""} need API keys: ${missing.join(", ")}. Toggle them off or wire keys in Setup → Integrations.`,
//         duration: 9000,
//       });
//       return;
//     }

//     const input = editableToInput(draft);
//     if (draft.id) {
//       updateMut.mutate({ id: draft.id, body: input });
//     } else {
//       createMut.mutate(input);
//     }
//   }, [draft, connectedMap, updateMut, createMut]);

//   // ── Duplicate
//   const handleDuplicate = useCallback(() => {
//     if (!draft?.id) { toast.error("Save the flow before duplicating"); return; }
//     const missing = findUnconnectedEnabledSteps(draft, connectedMap);
//     if (missing.length > 0) {
//       toast.error("Duplicate blocked — missing API keys", {
//         description: `Fix ${missing.join(", ")} in Setup → Integrations first.`,
//         duration: 9000,
//       });
//       return;
//     }
//     const input = editableToInput(draft);
//     createMut.mutate({ ...input, name: `${draft.name} (Copy)`, isDefault: false });
//   }, [draft, connectedMap, createMut]);

//   // ── Set Default
//   async function handleSetDefault(f: ProspectingFlow) {
//     if (f.isDefault) return;
//     try {
//       await flowsApi.updateFlow(f.id, { isDefault: true } as Partial<ProspectingFlowInput>);
//       toast.success(`"${f.name}" is now the default flow`);
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       if (selectedId === f.id && draft) setDraft({ ...draft, isDefault: true });
//     } catch {
//       toast.error("Failed to set default");
//     }
//   }

//   // ── Export
//   async function handleExport() {
//     if (!draft?.id) { toast.error("Save the flow before exporting"); return; }
//     try {
//       const res = await fetch(`/api/v1/flows/${draft.id}/export`, { credentials: "include" });
//       if (!res.ok) throw new Error(`HTTP ${res.status}`);
//       const blob = await res.blob();
//       const url = URL.createObjectURL(blob);
//       const a = document.createElement("a");
//       a.href = url;
//       a.download = `${(draft.name || "flow").replace(/[^a-z0-9_-]+/gi, "_")}.json`;
//       a.click();
//       URL.revokeObjectURL(url);
//       toast.success("Flow exported");
//     } catch {
//       toast.error("Export failed");
//     }
//   }

//   // ── Import
//   async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
//     const file = e.target.files?.[0];
//     e.target.value = "";
//     if (!file) return;
//     try {
//       const text = await file.text();
//       const obj = JSON.parse(text);
//       const res = await fetch("/api/v1/flows/import", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         credentials: "include",
//         body: JSON.stringify(obj),
//       });
//       const data = await res.json().catch(() => ({}));
//       if (!res.ok) throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
//       toast.success(`Flow imported: ${(data as ProspectingFlow).name}`);
//       qc.invalidateQueries({ queryKey: ["flows", "list"] });
//       setSelectedId((data as ProspectingFlow).id);
//       setDraft(flowToEditable(data as ProspectingFlow));
//       setDirty(false);
//     } catch (err) {
//       toast.error("Import failed", {
//         description: err instanceof Error ? err.message : "Invalid JSON file",
//       });
//     }
//   }

//   const isSaving = createMut.isPending || updateMut.isPending;
//   const canRun = !!draft?.id && !dirty;

//   return (
//     <TooltipProvider delayDuration={200}>
//       <div className="space-y-4">
//         {/* Hidden import input */}
//         <input
//           ref={importRef}
//           type="file"
//           accept=".json,application/json"
//           onChange={handleImportFile}
//           className="hidden"
//         />

//         {/* Page header */}
//         <div className="flex items-center justify-between flex-wrap gap-2">
//           <div>
//             <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
//               <Workflow className="h-6 w-6 text-primary" />
//               Prospecting Flows
//             </h2>
//             <p className="text-sm text-muted-foreground mt-1">
//               Orchestrate how your connected platforms work together — ordered sourcing, chained enrichment with
//               fallbacks, and quality gates.
//             </p>
//           </div>
//           <div className="flex items-center gap-2">
//             <Button variant="outline" onClick={() => refetch()}>
//               <RefreshCw className="h-4 w-4 mr-2" /> Refresh
//             </Button>
//             <Button variant="outline" onClick={() => setTemplatesOpen(true)}>
//               <Layers className="h-4 w-4 mr-2" /> Templates
//             </Button>
//             <Button variant="outline" onClick={() => importRef.current?.click()}>
//               <Upload className="h-4 w-4 mr-2" /> Import
//             </Button>
//             <Button onClick={startNew}>
//               <Plus className="h-4 w-4 mr-2" /> New Flow
//             </Button>
//           </div>
//         </div>

//         <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
//           {/* ═══ LEFT PANEL: Flow list ═══ */}
//           <Card className="h-fit">
//             <CardHeader className="pb-3">
//               <CardTitle className="text-sm font-medium flex items-center justify-between">
//                 Flows
//                 <Badge variant="secondary">{flows.length}</Badge>
//               </CardTitle>
//             </CardHeader>
//             <CardContent className="p-2">
//               <div className="space-y-1 max-h-[calc(100vh-280px)] min-h-[300px] overflow-y-auto pr-1">
//                 {isLoading && Array.from({ length: 3 }).map((_, i) => (
//                   <div key={i} className="px-2 py-1"><Skeleton className="h-16 w-full" /></div>
//                 ))}
//                 {isError && (
//                   <div className="text-xs text-muted-foreground text-center py-6 px-2">
//                     Failed to load.{" "}
//                     <button onClick={() => refetch()} className="underline text-primary">Retry</button>
//                   </div>
//                 )}
//                 {!isLoading && !isError && flows.length === 0 && (
//                   <p className="text-xs text-muted-foreground text-center py-6 px-2">
//                     No flows yet. Create your first flow.
//                   </p>
//                 )}
//                 {flows.map((f) => {
//                   const isSelected = f.id === selectedId;
//                   return (
//                     <div
//                       key={f.id}
//                       className={cn(
//                         "group rounded-md border px-3 py-2.5 cursor-pointer transition-colors",
//                         isSelected ? "border-primary bg-primary/5" : "border-transparent hover:bg-muted/50",
//                       )}
//                       onClick={() => selectFlow(f)}
//                     >
//                       <div className="flex items-start justify-between gap-2">
//                         <div className="min-w-0 flex-1">
//                           <div className="flex items-center gap-1.5">
//                             <span className="font-medium text-sm truncate">{f.name}</span>
//                             {f.isDefault && <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400 shrink-0" />}
//                           </div>
//                           <p className="text-xs text-muted-foreground truncate mt-0.5">
//                             {f.description || "No description"}
//                           </p>
//                           <div className="flex items-center gap-1.5 mt-1.5">
//                             <Badge variant="outline" className="text-[10px] py-0 h-4">
//                               {parseStepsFromRaw(f.sourceSteps).length} src
//                             </Badge>
//                             <Badge variant="outline" className="text-[10px] py-0 h-4">
//                               {parseStepsFromRaw(f.enrichmentSteps).length} enr
//                             </Badge>
//                             {!f.isActive && (
//                               <Badge variant="secondary" className="text-[10px] py-0 h-4">inactive</Badge>
//                             )}
//                           </div>
//                         </div>
//                         {!f.isDefault && (
//                           <Tooltip>
//                             <TooltipTrigger asChild>
//                               <Button
//                                 variant="ghost"
//                                 size="icon"
//                                 className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
//                                 onClick={(e) => { e.stopPropagation(); handleSetDefault(f); }}
//                               >
//                                 <StarOff className="h-3.5 w-3.5" />
//                               </Button>
//                             </TooltipTrigger>
//                             <TooltipContent>Set as default</TooltipContent>
//                           </Tooltip>
//                         )}
//                       </div>
//                     </div>
//                   );
//                 })}
//               </div>
//               <Button variant="outline" className="w-full mt-2" onClick={startNew}>
//                 <Plus className="h-4 w-4 mr-2" /> New Flow
//               </Button>
//             </CardContent>
//           </Card>

//           {/* ═══ RIGHT PANEL: Editor ═══ */}
//           {!draft ? (
//             <Card className="flex items-center justify-center min-h-[400px]">
//               <CardContent className="text-center text-muted-foreground py-12">
//                 <Inbox className="h-12 w-12 mx-auto mb-3 opacity-40" />
//                 <p className="font-medium">No flow selected</p>
//                 <p className="text-sm mt-1">Select a flow from the list, or create a new one.</p>
//                 <Button className="mt-4" onClick={startNew}>
//                   <Plus className="h-4 w-4 mr-2" /> New Flow
//                 </Button>
//               </CardContent>
//             </Card>
//           ) : (
//             <div className="space-y-4">
//               {/* Editor header card */}
//               <Card>
//                 <CardHeader className="pb-3">
//                   <div className="flex items-start justify-between gap-3 flex-wrap">
//                     <div className="flex-1 min-w-0 space-y-2">
//                       <div className="flex items-center gap-2 flex-wrap">
//                         {draft.isDefault && (
//                           <Badge className="bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-100">
//                             <Star className="h-3 w-3 fill-amber-400 text-amber-400 mr-1" /> Default
//                           </Badge>
//                         )}
//                         <Badge variant={draft.isActive ? "default" : "secondary"}>
//                           {draft.isActive ? "Active" : "Inactive"}
//                         </Badge>
//                         {dirty && (
//                           <Badge variant="outline" className="text-amber-600 border-amber-300">
//                             <AlertCircle className="h-3 w-3 mr-1" /> Unsaved
//                           </Badge>
//                         )}
//                         {/* View toggle */}
//                         <div className="ml-auto flex items-center rounded-md border bg-muted/40 p-0.5">
//                           <button
//                             type="button"
//                             onClick={() => setViewMode("form")}
//                             className={cn(
//                               "px-2.5 py-1 text-xs rounded transition-colors",
//                               viewMode === "form" ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground",
//                             )}
//                           >
//                             Form View
//                           </button>
//                           <button
//                             type="button"
//                             onClick={() => setViewMode("visual")}
//                             className={cn(
//                               "px-2.5 py-1 text-xs rounded transition-colors flex items-center gap-1",
//                               viewMode === "visual" ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground",
//                             )}
//                           >
//                             <Workflow className="h-3 w-3" /> Visual Builder
//                           </button>
//                         </div>
//                       </div>
//                       {/* Inline name / description editors */}
//                       <Input
//                         value={draft.name}
//                         onChange={(e) => updateDraft({ name: e.target.value })}
//                         placeholder="Flow name"
//                         className="text-lg font-semibold h-9 border-none px-0 focus-visible:ring-0"
//                       />
//                       <Textarea
//                         value={draft.description}
//                         onChange={(e) => updateDraft({ description: e.target.value })}
//                         placeholder="Add a description for this flow…"
//                         className="min-h-[40px] resize-none border-none px-0 focus-visible:ring-0 text-sm text-muted-foreground"
//                       />
//                     </div>

//                     {/* Action buttons */}
//                     <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
//                       <Tooltip>
//                         <TooltipTrigger asChild>
//                           <Button
//                             variant="outline"
//                             size="icon"
//                             className="h-8 w-8"
//                             onClick={() => updateDraft({ isDefault: !draft.isDefault })}
//                             disabled={isSaving}
//                           >
//                             <Star className={`h-4 w-4 ${draft.isDefault ? "fill-amber-400 text-amber-400" : ""}`} />
//                           </Button>
//                         </TooltipTrigger>
//                         <TooltipContent>{draft.isDefault ? "Unset default" : "Set as default"}</TooltipContent>
//                       </Tooltip>
//                       <Tooltip>
//                         <TooltipTrigger asChild>
//                           <Button
//                             variant="outline" size="icon" className="h-8 w-8"
//                             onClick={handleExport}
//                             disabled={!draft.id}
//                           >
//                             <Download className="h-4 w-4" />
//                           </Button>
//                         </TooltipTrigger>
//                         <TooltipContent>Export as JSON</TooltipContent>
//                       </Tooltip>
//                       <Tooltip>
//                         <TooltipTrigger asChild>
//                           <Button
//                             variant="outline" size="icon" className="h-8 w-8"
//                             onClick={handleDuplicate}
//                             disabled={isSaving || !draft.id}
//                           >
//                             <Copy className="h-4 w-4" />
//                           </Button>
//                         </TooltipTrigger>
//                         <TooltipContent>Duplicate</TooltipContent>
//                       </Tooltip>
//                       <Tooltip>
//                         <TooltipTrigger asChild>
//                           <Button
//                             variant="outline" size="icon" className="h-8 w-8"
//                             onClick={() => updateDraft({ isActive: !draft.isActive })}
//                           >
//                             <Pencil className="h-4 w-4" />
//                           </Button>
//                         </TooltipTrigger>
//                         <TooltipContent>Toggle Active</TooltipContent>
//                       </Tooltip>
//                       <Button
//                         variant="outline" size="icon" className="h-8 w-8 text-destructive"
//                         onClick={() => selectedFlow && setDeleteTarget(selectedFlow)}
//                         disabled={isSaving || !draft.id}
//                       >
//                         <Trash2 className="h-4 w-4" />
//                       </Button>
//                       <Button
//                         size="sm"
//                         onClick={() => { setActiveRunId(null); setRunOpen(true); }}
//                         disabled={!canRun}
//                         className="bg-emerald-600 hover:bg-emerald-700 text-white"
//                       >
//                         <PlayCircle className="h-4 w-4 mr-1.5" /> Run
//                       </Button>
//                       <Button size="sm" onClick={handleSave} disabled={isSaving || !dirty}>
//                         {isSaving ? (
//                           <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Saving…</>
//                         ) : (
//                           <><Save className="h-4 w-4 mr-1.5" /> Save</>
//                         )}
//                       </Button>
//                     </div>
//                   </div>
//                   {dirty && (
//                     <p className="text-[11px] text-amber-600 mt-2 flex items-center gap-1">
//                       <AlertCircle className="h-3 w-3" />
//                       Save your changes before running the flow — Run is disabled while there are unsaved edits.
//                     </p>
//                   )}
//                 </CardHeader>
//               </Card>

//               {/* Form View — 3-panel */}
//               {viewMode === "form" ? (
//                 <>
//                   <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
//                     <SourceStepsCard
//                       steps={draft.sourceSteps}
//                       connectedMap={connectedMap}
//                       onChange={(sourceSteps) => updateDraft({ sourceSteps })}
//                     />
//                     <EnrichmentStepsCard
//                       steps={draft.enrichmentSteps}
//                       connectedMap={connectedMap}
//                       onChange={(enrichmentSteps) => updateDraft({ enrichmentSteps })}
//                     />
//                     <QualityGatesCard
//                       gates={draft.qualityGates}
//                       onChange={(patch) => updateDraft({ qualityGates: { ...draft.qualityGates, ...patch } })}
//                     />
//                   </div>
//                   <FlowSummary draft={draft} connectedMap={connectedMap} />
//                 </>
//               ) : (
//                 <VisualFlowBuilder
//                   draft={draft}
//                   connectedMap={connectedMap}
//                   onUpdate={updateDraft}
//                 />
//               )}
//             </div>
//           )}
//         </div>

//         {/* Dialogs */}
//         {selectedFlow && (
//           <RunFlowDialog
//             flow={selectedFlow}
//             open={runOpen}
//             onClose={() => { setRunOpen(false); setActiveRunId(null); }}
//             onRun={(icpId, _maxProspects, _dryRun, llmConfigId) =>
//               runMut.mutate({ flowId: selectedFlow.id, icpId, llmConfigId })
//             }
//             isRunning={runMut.isPending}
//             activeRunId={activeRunId}
//           />
//         )}

//         <TemplatesDialog
//           open={templatesOpen}
//           onClose={() => setTemplatesOpen(false)}
//           onClone={(templateId, name) => cloneMut.mutate({ templateId, name })}
//         />

//         <DeleteDialog
//           flow={deleteTarget}
//           open={!!deleteTarget}
//           onClose={() => setDeleteTarget(null)}
//           onConfirm={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
//           isDeleting={deleteMut.isPending}
//         />
//       </div>
//     </TooltipProvider>
//   );
// }


/**
 * FlowsPage.tsx — Prospecting Flows Builder (complete rewrite)
 *
 * Matches Next.js ProspectingFlowsPage + VisualFlowBuilder reference exactly:
 *
 *   ┌──────────────┬──────────────────────────────────────────────────────┐
 *   │ FLOWS LIST   │  Header (name, badges, view toggle, action buttons)  │
 *   │ (left panel) │  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐  │
 *   │              │  │ 1. SOURCE    │ │ 2. ENRICH    │ │ 3. QUALITY  │  │
 *   │              │  │    STEPS     │ │    STEPS     │ │    GATES    │  │
 *   │              │  │              │ │   (optional) │ │             │  │
 *   │              │  └──────────────┘ └──────────────┘ └─────────────┘  │
 *   │              │  ─── Pipeline Preview ──────────────────────────────  │
 *   └──────────────┴──────────────────────────────────────────────────────┘
 *
 * Key behaviours:
 *  - Enrichment is OPTIONAL. Empty enrichment steps array is fully valid.
 *  - Platform palette shows connected (✓) vs not-connected (⚠) status.
 *  - Save is BLOCKED when enabled steps have no API key (with clear toast).
 *  - Free sources (AI Web Search, LinkedIn) never need a key.
 *  - Run dialog shows ICP selector + LLM config selector + Dry Run toggle.
 *  - After clicking Run the dialog switches to a live RunMonitor that polls
 *    GET /flows/runs/{run_id} every 2 seconds until terminal state.
 *  - View toggle: "Form View" (3-card JSON editors) vs "Visual Builder" (dnd-kit).
 *
 * Backend step format: { "platform": "apollo", "enabled": true, "order": 0 }
 * The parseSteps() helper also accepts legacy keys: provider, key, type.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  BarChart2,
  Brain,
  Building2,
  Ban,
  
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  
  GripVertical,
  Inbox,
  Layers,
  Loader2,
  Mail,
  Pencil,
  Plus,
  PlayCircle,
  RefreshCw,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Star,
  StarOff,
  Trash2,
  Upload,
  Workflow,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { flowsApi, integrationConfigApi, http } from "@/services/apiClient";
import type {
  ProspectingFlow,
  ProspectingFlowInput,
  TenantIntegration,
} from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

// ─────────────────────────────────────────────────────────────────────────────
// Platform registry
// ─────────────────────────────────────────────────────────────────────────────

interface PlatformMeta {
  key: string;
  label: string;
  canSource: boolean;
  canEnrich: boolean;
  free: boolean; // free = no API key required
  badgeColor: string; // Tailwind classes for the badge chip
  sourceFields: { key: string; label: string; placeholder: string }[];
  enrichFields: { key: string; label: string }[];
}

const PLATFORM_META: Record<string, PlatformMeta> = {
  ai_web_search: {
    key: "ai_web_search",
    label: "AI Web Search",
    canSource: true,
    canEnrich: false,
    free: true,
    badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
    sourceFields: [
      { key: "query", label: "Search Query", placeholder: "CTO fintech series B" },
    ],
    enrichFields: [],
  },
  web_search: {
    key: "web_search",
    label: "AI Web Search",
    canSource: true,
    canEnrich: false,
    free: true,
    badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
    sourceFields: [
      { key: "query", label: "Search Query", placeholder: "CTO fintech series B" },
    ],
    enrichFields: [],
  },
  linkedin: {
    key: "linkedin",
    label: "LinkedIn",
    canSource: true,
    canEnrich: false,
    free: true,
    badgeColor: "bg-sky-100 text-sky-700 border-sky-200",
    sourceFields: [
      { key: "job_title", label: "Job Title", placeholder: "Chief Technology Officer" },
      { key: "industry", label: "Industry", placeholder: "SaaS" },
      { key: "location", label: "Location", placeholder: "San Francisco, CA" },
    ],
    enrichFields: [],
  },
  apollo: {
    key: "apollo",
    label: "Apollo.io",
    canSource: true,
    canEnrich: true,
    free: false,
    badgeColor: "bg-blue-100 text-blue-700 border-blue-200",
    sourceFields: [
      { key: "person_titles", label: "Job Titles", placeholder: "CTO, VP Engineering" },
      { key: "q_keywords", label: "Keywords", placeholder: "series A SaaS" },
      { key: "organization_locations", label: "Locations", placeholder: "San Francisco, CA" },
    ],
    enrichFields: [
      { key: "email", label: "Email" },
      { key: "phone", label: "Phone" },
      { key: "linkedin", label: "LinkedIn URL" },
    ],
  },
  zoominfo: {
    key: "zoominfo",
    label: "ZoomInfo",
    canSource: true,
    canEnrich: false,
    free: false,
    badgeColor: "bg-indigo-100 text-indigo-700 border-indigo-200",
    sourceFields: [
      { key: "jobTitle", label: "Job Title", placeholder: "Chief Technology Officer" },
      { key: "companyIndustry", label: "Industry", placeholder: "Software" },
      { key: "employees", label: "Employees", placeholder: "50-200" },
    ],
    enrichFields: [],
  },
  clearbit: {
    key: "clearbit",
    label: "Clearbit",
    canSource: true,
    canEnrich: true,
    free: false,
    badgeColor: "bg-teal-100 text-teal-700 border-teal-200",
    sourceFields: [
      { key: "query", label: "Company", placeholder: "acme.com" },
    ],
    enrichFields: [
      { key: "company_size", label: "Company Size" },
      { key: "revenue", label: "Revenue" },
      { key: "tech_stack", label: "Tech Stack" },
      { key: "industry", label: "Industry" },
    ],
  },
  hunter: {
    key: "hunter",
    label: "Hunter.io",
    canSource: true,
    canEnrich: true,
    free: false,
    badgeColor: "bg-amber-100 text-amber-700 border-amber-200",
    sourceFields: [
      { key: "domain", label: "Domain", placeholder: "acme.com" },
    ],
    enrichFields: [
      { key: "email", label: "Email" },
      { key: "email_pattern", label: "Email Pattern" },
    ],
  },
  lusha: {
    key: "lusha",
    label: "Lusha",
    canSource: true,
    canEnrich: true,
    free: false,
    badgeColor: "bg-rose-100 text-rose-700 border-rose-200",
    sourceFields: [
      { key: "company_name", label: "Company", placeholder: "Acme Inc" },
    ],
    enrichFields: [
      { key: "email", label: "Email" },
      { key: "phone", label: "Phone" },
    ],
  },
  kaspr: {
    key: "kaspr",
    label: "Kaspr",
    canSource: true,
    canEnrich: true,
    free: false,
    badgeColor: "bg-pink-100 text-pink-700 border-pink-200",
    sourceFields: [
      { key: "query", label: "Query", placeholder: "CTO Acme" },
    ],
    enrichFields: [
      { key: "email", label: "Email" },
      { key: "phone", label: "Phone" },
    ],
  },
  clay: {
    key: "clay",
    label: "Clay",
    canSource: true,
    canEnrich: false,
    free: false,
    badgeColor: "bg-orange-100 text-orange-700 border-orange-200",
    sourceFields: [
      { key: "table_name", label: "Table Name", placeholder: "my-icp-table" },
    ],
    enrichFields: [],
  },
  email_waterfall: {
    key: "email_waterfall",
    label: "Email Waterfall",
    canSource: false,
    canEnrich: true,
    free: false,
    badgeColor: "bg-emerald-100 text-emerald-700 border-emerald-200",
    sourceFields: [],
    enrichFields: [
      { key: "email", label: "Email" },
    ],
  },
};

function getMeta(key: string): PlatformMeta {
  return (
    PLATFORM_META[key] ?? {
      key,
      label: key,
      canSource: false,
      canEnrich: false,
      free: false,
      badgeColor: "bg-gray-100 text-gray-700 border-gray-200",
      sourceFields: [],
      enrichFields: [],
    }
  );
}

const ALL_SOURCE_KEYS = Object.values(PLATFORM_META)
  .filter((m) => m.canSource)
  .map((m) => m.key)
  .filter((k) => k !== "web_search"); // deduplicate alias

const ALL_ENRICH_KEYS = Object.values(PLATFORM_META)
  .filter((m) => m.canEnrich)
  .map((m) => m.key);

// ─────────────────────────────────────────────────────────────────────────────
// Step + QualityGates types
// ─────────────────────────────────────────────────────────────────────────────

interface SourceStep {
  platform: string;
  enabled: boolean;
  priority: number;
  queryOverrides: Record<string, string>;
}

interface EnrichmentStep {
  platform: string;
  enabled: boolean;
  priority: number;
  targetFields: string[];
  fallbackTo: string | null;
}

interface QualityGates {
  requireEmail: boolean;
  requireVerifiedEmail: boolean;
  requireCompanySize: boolean;
  minCompanySize: number;
  llmScoreThreshold: number;
  excludeDomains: string[];
}

const DEFAULT_GATES: QualityGates = {
  requireEmail: true,
  requireVerifiedEmail: false,
  requireCompanySize: false,
  minCompanySize: 10,
  llmScoreThreshold: 0.6,
  excludeDomains: ["gmail.com", "yahoo.com", "hotmail.com"],
};

// ─────────────────────────────────────────────────────────────────────────────
// EditableFlow — parsed editor state
// ─────────────────────────────────────────────────────────────────────────────

interface EditableFlow {
  id: string | null;
  name: string;
  description: string;
  isDefault: boolean;
  isActive: boolean;
  isTemplate: boolean;
  sourceSteps: SourceStep[];
  enrichmentSteps: EnrichmentStep[];
  qualityGates: QualityGates;
}

function parseStepsFromRaw(raw: unknown): SourceStep[] | EnrichmentStep[] {
  if (!raw) return [];
  try {
    const arr = Array.isArray(raw) ? raw : JSON.parse(String(raw));
    return (arr as Record<string, unknown>[]).map((s, i) => ({
      platform: String(s.platform ?? s.provider ?? s.key ?? s.type ?? ""),
      enabled: s.enabled !== false,
      priority: typeof s.priority === "number" ? s.priority : typeof s.order === "number" ? s.order : i,
      queryOverrides: (s.queryOverrides as Record<string, string>) ?? {},
      targetFields: Array.isArray(s.targetFields) ? (s.targetFields as string[]) : [],
      fallbackTo: (s.fallbackTo as string | null) ?? null,
    }));
  } catch {
    return [];
  }
}

function parseGates(raw: unknown): QualityGates {
  if (!raw) return { ...DEFAULT_GATES };
  try {
    const parsed =
      typeof raw === "object" && !Array.isArray(raw)
        ? raw
        : JSON.parse(String(raw));
    return { ...DEFAULT_GATES, ...(parsed as Partial<QualityGates>) };
  } catch {
    return { ...DEFAULT_GATES };
  }
}

function flowToEditable(f: ProspectingFlow): EditableFlow {
  return {
    id: f.id,
    name: f.name,
    description: f.description ?? "",
    isDefault: f.isDefault,
    isActive: f.isActive,
    isTemplate: f.isTemplate,
    sourceSteps: parseStepsFromRaw(f.sourceSteps) as SourceStep[],
    enrichmentSteps: parseStepsFromRaw(f.enrichmentSteps) as EnrichmentStep[],
    qualityGates: parseGates(f.qualityGates),
  };
}

function newEditable(): EditableFlow {
  return {
    id: null,
    name: "Untitled Flow",
    description: "",
    isDefault: false,
    isActive: true,
    isTemplate: false,
    sourceSteps: [],
    enrichmentSteps: [],
    qualityGates: { ...DEFAULT_GATES },
  };
}

function editableToInput(e: EditableFlow): ProspectingFlowInput {
  const serializeSourceSteps = e.sourceSteps.map((s, i) => ({
    platform: s.platform,
    enabled: s.enabled,
    order: i,
    priority: i,
    queryOverrides: s.queryOverrides,
  }));
  const serializeEnrichSteps = e.enrichmentSteps.map((s, i) => ({
    platform: s.platform,
    enabled: s.enabled,
    order: i,
    priority: i,
    targetFields: s.targetFields,
    fallbackTo: s.fallbackTo,
  }));
  return {
    name: e.name.trim(),
    description: e.description.trim() || null,
    isDefault: e.isDefault,
    isActive: e.isActive,
    isTemplate: e.isTemplate,
    sourceSteps: serializeSourceSteps as unknown as Record<string, unknown>[],
    enrichmentSteps: serializeEnrichSteps as unknown as Record<string, unknown>[],
    qualityGates: e.qualityGates as unknown as Record<string, unknown>,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// connectedMap helper
// ─────────────────────────────────────────────────────────────────────────────

function buildConnectedMap(integrations: TenantIntegration[]): Record<string, boolean> {
  const m: Record<string, boolean> = {};
  for (const i of integrations) {
    m[i.platform] = !!(i.isActive && (i.apiKey || i.key_source === "platform"));
  }
  // Free sources are always "connected"
  m["ai_web_search"] = true;
  m["web_search"] = true;
  m["linkedin"] = m["linkedin"] ?? true; // treat as free unless explicitly disconnected
  return m;
}

function isConnected(platform: string, connectedMap: Record<string, boolean>): boolean {
  const meta = getMeta(platform);
  if (meta.free) return true;
  return connectedMap[platform] ?? false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Validation — block save when enabled steps lack API keys
// ─────────────────────────────────────────────────────────────────────────────

function findUnconnectedEnabledSteps(
  draft: EditableFlow,
  connectedMap: Record<string, boolean>,
): string[] {
  const missing = new Set<string>();
  for (const s of draft.sourceSteps) {
    if (!s.enabled) continue;
    if (!isConnected(s.platform, connectedMap)) missing.add(getMeta(s.platform).label);
  }
  for (const s of draft.enrichmentSteps) {
    if (!s.enabled) continue;
    if (!isConnected(s.platform, connectedMap)) missing.add(getMeta(s.platform).label);
  }
  return Array.from(missing).sort();
}

// ─────────────────────────────────────────────────────────────────────────────
// ICP profile lite
// ─────────────────────────────────────────────────────────────────────────────

interface IcpLite {
  id: string;
  name: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Flow Templates
// ─────────────────────────────────────────────────────────────────────────────

interface FlowTemplate {
  id: string;
  name: string;
  description: string;
  source_platforms: string[];
  enrichment_platforms: string[];
  gate_config: Partial<QualityGates>;
  gate_strictness: string;
  recommended_for: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Run-monitor types
// ─────────────────────────────────────────────────────────────────────────────

interface FlowRunStep {
  id: string;
  kind: string;
  stepKey: string;
  status: string;
  durationMs?: number | null;
  metrics?: unknown;
  errorMessage?: string | null;
}

interface FlowRunDetail {
  id: string;
  status: string;
  stats?: unknown;
  importedProspectIds?: unknown;
  errorMessage?: string | null;
  steps?: FlowRunStep[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: GateRow
// ─────────────────────────────────────────────────────────────────────────────

function GateRow({
  icon,
  label,
  description,
  checked,
  onCheckedChange,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">{icon}</span>
        <div>
          <p className="text-sm font-medium leading-none">{label}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        </div>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: QualityGatesCard
// ─────────────────────────────────────────────────────────────────────────────

function QualityGatesCard({
  gates,
  onChange,
}: {
  gates: QualityGates;
  onChange: (patch: Partial<QualityGates>) => void;
}) {
  const [domainInput, setDomainInput] = useState("");

  function addDomain() {
    const d = domainInput.trim().toLowerCase().replace(/^@/, "");
    if (!d) return;
    if (gates.excludeDomains.includes(d)) {
      setDomainInput("");
      return;
    }
    onChange({ excludeDomains: [...gates.excludeDomains, d] });
    setDomainInput("");
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-red-700 text-[11px] font-bold">3</span>
          Quality Gates
        </CardTitle>
        <CardDescription className="text-xs">
          Auto-reject prospects that don&apos;t meet your quality bar.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <GateRow
          icon={<Mail className="h-4 w-4" />}
          label="Require email"
          description="Reject prospects without an email address"
          checked={gates.requireEmail}
          onCheckedChange={(v) => onChange({ requireEmail: v })}
        />
        <Separator />
        <GateRow
          icon={<ShieldCheck className="h-4 w-4" />}
          label="Require verified email"
          description="Reject prospects whose email failed validation"
          checked={gates.requireVerifiedEmail}
          onCheckedChange={(v) => onChange({ requireVerifiedEmail: v })}
        />
        <Separator />
        <div className="space-y-2">
          <GateRow
            icon={<Building2 className="h-4 w-4" />}
            label="Minimum company size"
            description="Reject prospects from companies below this employee count"
            checked={gates.requireCompanySize}
            onCheckedChange={(v) => onChange({ requireCompanySize: v })}
          />
          {gates.requireCompanySize && (
            <div className="pl-7 flex items-center gap-2">
              <Input
                type="number"
                min={0}
                value={gates.minCompanySize}
                onChange={(e) =>
                  onChange({ minCompanySize: Math.max(0, Number(e.target.value) || 0) })
                }
                className="h-7 w-24 text-xs"
              />
              <span className="text-xs text-muted-foreground">employees minimum</span>
            </div>
          )}
        </div>
        <Separator />
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-primary" />
              <div>
                <p className="text-sm font-medium leading-none">LLM score threshold</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Reject prospects scoring below this ICP-fit score
                </p>
              </div>
            </div>
            <Badge variant="outline" className="font-mono">
              {gates.llmScoreThreshold.toFixed(2)}
            </Badge>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={gates.llmScoreThreshold}
            onChange={(e) => onChange({ llmScoreThreshold: Number(e.target.value) })}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>0.00 (off)</span>
            <span>0.50</span>
            <span>1.00 (strict)</span>
          </div>
        </div>
        <Separator />
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Ban className="h-4 w-4" />
            <div>
              <p className="text-sm font-medium leading-none">Exclude domains</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Reject prospects with these email domains
              </p>
            </div>
          </div>
          <div className="pl-7 space-y-2">
            <div className="flex flex-wrap gap-1.5">
              {gates.excludeDomains.length === 0 && (
                <span className="text-xs text-muted-foreground">No domains excluded.</span>
              )}
              {gates.excludeDomains.map((d) => (
                <Badge key={d} variant="secondary" className="text-xs gap-1 pr-1">
                  {d}
                  <button
                    onClick={() =>
                      onChange({ excludeDomains: gates.excludeDomains.filter((x) => x !== d) })
                    }
                    className="ml-0.5 hover:text-destructive"
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
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addDomain();
                  }
                }}
                placeholder="gmail.com"
                className="h-7 text-xs flex-1"
              />
              <Button variant="outline" size="sm" className="h-7 px-2" onClick={addDomain}>
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: SourceStepsCard (Form View)
// ─────────────────────────────────────────────────────────────────────────────

function SourceStepsCard({
  steps,
  connectedMap,
  onChange,
}: {
  steps: SourceStep[];
  connectedMap: Record<string, boolean>;
  onChange: (steps: SourceStep[]) => void;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  function update(idx: number, patch: Partial<SourceStep>) {
    const next = steps.map((s, i) => (i === idx ? { ...s, ...patch } : s));
    onChange(next);
  }

  function addStep(platform: string) {
    const meta = getMeta(platform);
    const queryOverrides: Record<string, string> = {};
    for (const f of meta.sourceFields) queryOverrides[f.key] = "";
    onChange([
      ...steps,
      { platform, enabled: true, priority: steps.length + 1, queryOverrides },
    ]);
    setExpandedIdx(steps.length);
  }

  function removeStep(idx: number) {
    const next = steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, priority: i + 1 }));
    onChange(next);
    setExpandedIdx(null);
  }

  function moveStep(idx: number, dir: -1 | 1) {
    const ni = idx + dir;
    if (ni < 0 || ni >= steps.length) return;
    const next = [...steps];
    [next[idx], next[ni]] = [next[ni], next[idx]];
    onChange(next.map((s, i) => ({ ...s, priority: i + 1 })));
    setExpandedIdx(ni);
  }

  const available = ALL_SOURCE_KEYS.filter((k) => !steps.some((s) => s.platform === k));

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary text-[11px] font-bold">1</span>
          Source Steps
        </CardTitle>
        <CardDescription className="text-xs">
          Search platforms in priority order. Only enabled + connected platforms run.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {steps.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            No source steps. Add a platform below to start sourcing prospects.
          </p>
        )}
        {steps.map((step, idx) => {
          const meta = getMeta(step.platform);
          const connected = isConnected(step.platform, connectedMap);
          const isExpanded = expandedIdx === idx;
          return (
            <div key={`${step.platform}-${idx}`} className="rounded-md border">
              <div className="flex items-center gap-1.5 p-2 flex-wrap">
                <GripVertical className="h-4 w-4 text-muted-foreground/50 shrink-0" />
                <span className="text-xs font-medium text-muted-foreground w-4 shrink-0">{idx + 1}</span>
                <Badge variant="outline" className={cn(meta.badgeColor, "shrink-0")}>
                  {meta.label}
                </Badge>
                {!connected && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                    </TooltipTrigger>
                    <TooltipContent>Not connected — add an API key in Integrations</TooltipContent>
                  </Tooltip>
                )}
                {connected && !meta.free && (
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                )}
                {meta.free && (
                  <span className="text-[10px] text-green-600 font-medium shrink-0">free</span>
                )}
                <div className="flex-1 min-w-0" />
                <div className="flex items-center gap-1 shrink-0">
                  <Switch
                    checked={step.enabled}
                    onCheckedChange={(v) => update(idx, { enabled: v })}
                  />
                  <Button
                    variant="ghost" size="icon" className="h-7 w-7"
                    disabled={idx === 0}
                    onClick={() => moveStep(idx, -1)}
                  >
                    <ChevronUp className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost" size="icon" className="h-7 w-7"
                    disabled={idx === steps.length - 1}
                    onClick={() => moveStep(idx, 1)}
                  >
                    <ChevronDown className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost" size="icon" className="h-7 w-7"
                    onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                  >
                    <Settings2 className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost" size="icon" className="h-7 w-7 text-destructive"
                    onClick={() => removeStep(idx)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              {isExpanded && meta.sourceFields.length > 0 && (
                <div className="border-t px-3 pb-3 pt-2.5 space-y-2 bg-muted/30">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
                    Search Overrides
                  </p>
                  {meta.sourceFields.map((field) => (
                    <div key={field.key} className="grid grid-cols-[110px_1fr] items-center gap-2">
                      <Label className="text-xs text-muted-foreground">{field.label}</Label>
                      <Input
                        value={step.queryOverrides[field.key] ?? ""}
                        onChange={(e) =>
                          update(idx, {
                            queryOverrides: { ...step.queryOverrides, [field.key]: e.target.value },
                          })
                        }
                        placeholder={field.placeholder}
                        className="h-7 text-xs"
                      />
                    </div>
                  ))}
                  {!connected && (
                    <p className="text-[11px] text-amber-600 flex items-center gap-1 pt-1">
                      <AlertCircle className="h-3 w-3" /> Connect this platform in Integrations to use it.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {available.length > 0 && (
          <Select onValueChange={addStep}>
            <SelectTrigger className="h-8 text-xs mt-2">
              <SelectValue placeholder="+ Add source platform" />
            </SelectTrigger>
            <SelectContent>
              {available.map((k) => {
                const meta = getMeta(k);
                const connected = isConnected(k, connectedMap);
                return (
                  <SelectItem key={k} value={k} className="text-xs">
                    {meta.label}
                    {meta.free ? " (free)" : connected ? " ✓" : " (not connected)"}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        )}
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: EnrichmentStepsCard (Form View — OPTIONAL)
// ─────────────────────────────────────────────────────────────────────────────

function EnrichmentStepsCard({
  steps,
  connectedMap,
  onChange,
}: {
  steps: EnrichmentStep[];
  connectedMap: Record<string, boolean>;
  onChange: (steps: EnrichmentStep[]) => void;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  function update(idx: number, patch: Partial<EnrichmentStep>) {
    const next = steps.map((s, i) => (i === idx ? { ...s, ...patch } : s));
    onChange(next);
  }

  function addStep(platform: string) {
    const meta = getMeta(platform);
    onChange([
      ...steps,
      {
        platform,
        enabled: true,
        priority: steps.length + 1,
        targetFields: meta.enrichFields.map((f) => f.key),
        fallbackTo: null,
      },
    ]);
    setExpandedIdx(steps.length);
  }

  function removeStep(idx: number) {
    const next = steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, priority: i + 1 }));
    onChange(next);
    setExpandedIdx(null);
  }

  function moveStep(idx: number, dir: -1 | 1) {
    const ni = idx + dir;
    if (ni < 0 || ni >= steps.length) return;
    const next = [...steps];
    [next[idx], next[ni]] = [next[ni], next[idx]];
    onChange(next.map((s, i) => ({ ...s, priority: i + 1 })));
    setExpandedIdx(ni);
  }

  function toggleField(idx: number, fieldKey: string) {
    const step = steps[idx];
    const has = step.targetFields.includes(fieldKey);
    const next = has
      ? step.targetFields.filter((f) => f !== fieldKey)
      : [...step.targetFields, fieldKey];
    update(idx, { targetFields: next });
  }

  const available = ALL_ENRICH_KEYS.filter((k) => !steps.some((s) => s.platform === k));
  const fallbackPlatforms = ALL_ENRICH_KEYS;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-[11px] font-bold">2</span>
          Enrichment Steps
          <span className="ml-auto text-[10px] text-muted-foreground font-normal">optional</span>
        </CardTitle>
        <CardDescription className="text-xs">
          Fill prospect fields in order. If a step fails, fall back to the next platform.{" "}
          <strong>Leave empty to skip enrichment.</strong>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {steps.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4 border border-dashed rounded-md">
            No enrichment steps — flow will run without enrichment. Add a platform below to enable.
          </p>
        )}
        {steps.map((step, idx) => {
          const meta = getMeta(step.platform);
          const connected = isConnected(step.platform, connectedMap);
          const isExpanded = expandedIdx === idx;
          return (
            <div key={`${step.platform}-${idx}`} className="rounded-md border">
              <div className="flex items-center gap-1.5 p-2 flex-wrap">
                <GripVertical className="h-4 w-4 text-muted-foreground/50 shrink-0" />
                <span className="text-xs font-medium text-muted-foreground w-4 shrink-0">{idx + 1}</span>
                <Badge variant="outline" className={cn(meta.badgeColor, "shrink-0")}>
                  {meta.label}
                </Badge>
                {!connected && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                    </TooltipTrigger>
                    <TooltipContent>Not connected</TooltipContent>
                  </Tooltip>
                )}
                {connected && <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />}
                {step.fallbackTo && (
                  <Badge variant="secondary" className="text-[10px] py-0 h-4 shrink-0">
                    ↳ {getMeta(step.fallbackTo).label}
                  </Badge>
                )}
                <div className="flex-1 min-w-0" />
                <div className="flex items-center gap-1 shrink-0">
                  <Switch
                    checked={step.enabled}
                    onCheckedChange={(v) => update(idx, { enabled: v })}
                  />
                  <Button variant="ghost" size="icon" className="h-7 w-7" disabled={idx === 0} onClick={() => moveStep(idx, -1)}>
                    <ChevronUp className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7" disabled={idx === steps.length - 1} onClick={() => moveStep(idx, 1)}>
                    <ChevronDown className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setExpandedIdx(isExpanded ? null : idx)}>
                    <Settings2 className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => removeStep(idx)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              {isExpanded && (
                <div className="border-t px-3 pb-3 pt-2.5 space-y-3 bg-muted/30">
                  {meta.enrichFields.length > 0 && (
                    <div>
                      <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide mb-1.5">
                        Target Fields
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {meta.enrichFields.map((field) => {
                          const checked = step.targetFields.includes(field.key);
                          return (
                            <label key={field.key} className="flex items-center gap-1 text-xs cursor-pointer">
                              <Switch
                                checked={checked}
                                onCheckedChange={() => toggleField(idx, field.key)}
                                className="scale-75"
                              />
                              {field.label}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-[110px_1fr] items-center gap-2">
                    <Label className="text-xs text-muted-foreground">Fallback to</Label>
                    <Select
                      value={step.fallbackTo ?? "__none__"}
                      onValueChange={(v) => update(idx, { fallbackTo: v === "__none__" ? null : v })}
                    >
                      <SelectTrigger className="h-7 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__" className="text-xs">None</SelectItem>
                        {fallbackPlatforms
                          .filter((p) => p !== step.platform)
                          .map((p) => (
                            <SelectItem key={p} value={p} className="text-xs">
                              {getMeta(p).label}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {available.length > 0 && (
          <Select onValueChange={addStep}>
            <SelectTrigger className="h-8 text-xs mt-2">
              <SelectValue placeholder="+ Add enrichment platform" />
            </SelectTrigger>
            <SelectContent>
              {available.map((k) => {
                const meta = getMeta(k);
                const connected = isConnected(k, connectedMap);
                return (
                  <SelectItem key={k} value={k} className="text-xs">
                    {meta.label}{connected ? " ✓" : " (not connected)"}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        )}
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: FlowSummary (Pipeline preview under Form View)
// ─────────────────────────────────────────────────────────────────────────────

function FlowSummary({
  draft,
  connectedMap,
}: {
  draft: EditableFlow;
  connectedMap: Record<string, boolean>;
}) {
  const activeSources = draft.sourceSteps.filter((s) => s.enabled);
  const activeEnrich = draft.enrichmentSteps.filter((s) => s.enabled);
  const g = draft.qualityGates;
  const gateCount =
    (g.requireEmail ? 1 : 0) +
    (g.requireVerifiedEmail ? 1 : 0) +
    (g.requireCompanySize ? 1 : 0) +
    (g.excludeDomains.length > 0 ? 1 : 0) +
    (g.llmScoreThreshold > 0 ? 1 : 0);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Zap className="h-4 w-4 text-primary" /> Pipeline Preview
        </CardTitle>
        <CardDescription className="text-xs">
          How prospects flow through this configuration at execution time.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {/* Source */}
          <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Source</p>
              <Badge variant="secondary" className="text-[10px] h-4 py-0">{activeSources.length}</Badge>
            </div>
            <div className="space-y-1">
              {activeSources.length === 0 && <p className="text-xs text-muted-foreground/70">No active sources</p>}
              {activeSources.map((s) => {
                const meta = getMeta(s.platform);
                return (
                  <div key={s.platform} className="flex items-center gap-1.5">
                    <Badge variant="outline" className={cn("text-xs", meta.badgeColor)}>{meta.label}</Badge>
                    {!isConnected(s.platform, connectedMap) && <AlertCircle className="h-3 w-3 text-amber-500" />}
                  </div>
                );
              })}
            </div>
          </div>

          <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

          {/* Enrich */}
          <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Enrich</p>
              <Badge variant="secondary" className="text-[10px] h-4 py-0">{activeEnrich.length}</Badge>
            </div>
            <div className="space-y-1">
              {activeEnrich.length === 0 && <p className="text-xs text-muted-foreground/70">None (optional)</p>}
              {activeEnrich.map((s) => {
                const meta = getMeta(s.platform);
                return (
                  <div key={s.platform} className="flex items-center gap-1.5">
                    <Badge variant="outline" className={cn("text-xs", meta.badgeColor)}>{meta.label}</Badge>
                    {!isConnected(s.platform, connectedMap) && <AlertCircle className="h-3 w-3 text-amber-500" />}
                  </div>
                );
              })}
            </div>
          </div>

          <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

          {/* Gates */}
          <div className="rounded-lg border bg-muted/30 p-3 min-w-[130px] flex-1">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Gates</p>
              <Badge variant="secondary" className="text-[10px] h-4 py-0">{gateCount}</Badge>
            </div>
            <div className="space-y-1">
              {gateCount === 0 && <p className="text-xs text-muted-foreground/70">No gates active</p>}
              {g.requireEmail && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">Email</Badge>}
              {g.requireVerifiedEmail && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">Verified</Badge>}
              {g.requireCompanySize && <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">≥{g.minCompanySize} emp</Badge>}
              {g.llmScoreThreshold > 0 && <Badge variant="outline" className="text-xs bg-violet-100 text-violet-700 border-violet-200">LLM ≥{g.llmScoreThreshold.toFixed(2)}</Badge>}
              {g.excludeDomains.length > 0 && <Badge variant="outline" className="text-xs bg-red-100 text-red-700 border-red-200">{g.excludeDomains.length} domains</Badge>}
            </div>
          </div>

          <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />

          {/* Output */}
          <div className="rounded-lg border border-primary/40 bg-primary/5 p-3 min-w-[130px] flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Qualified Prospects</p>
            <div className="flex items-center gap-1.5 text-primary">
              <CheckCircle2 className="h-4 w-4" />
              <span className="text-sm font-medium">Ready for campaign</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: DraggableStepCard (used inside Visual Builder)
// ─────────────────────────────────────────────────────────────────────────────

function DraggableStepCard({
  id,
  platform,
  enabled,
  priority,
  isEnrich,
  connected,
  free,
  onToggle,
  onRemove,
}: {
  id: string;
  platform: string;
  enabled: boolean;
  priority: number;
  isEnrich?: boolean;
  connected: boolean;
  free: boolean;
  onToggle: (enabled: boolean) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const meta = getMeta(platform);

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "group relative flex items-center gap-2 rounded-lg border bg-card p-2.5 shadow-sm transition-all",
        isDragging && "opacity-50 shadow-lg ring-2 ring-primary/40",
        !enabled && "opacity-60",
        meta.badgeColor,
        !connected && !free && "ring-1 ring-amber-300/60",
      )}
    >
      <button
        type="button"
        className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground touch-none"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <Badge variant="outline" className={cn("shrink-0 font-mono text-[10px] h-5 w-5 justify-center p-0", meta.badgeColor)}>
        {priority}
      </Badge>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="text-sm font-medium truncate">{meta.label}</p>
          {free ? (
            <span className="text-[10px] font-medium text-green-700">free</span>
          ) : connected ? (
            <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-emerald-700">
              <CheckCircle2 className="h-3 w-3" /> ✓
            </span>
          ) : (
            <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-700">
              <AlertCircle className="h-3 w-3" /> Not Connected
            </span>
          )}
        </div>
        {isEnrich && <p className="text-[10px] text-muted-foreground">Enrichment step</p>}
      </div>
      <Switch checked={enabled} onCheckedChange={onToggle} className="scale-75" />
      <button
        type="button"
        onClick={onRemove}
        className="text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
        aria-label="Remove step"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: VisualFlowBuilder
// ─────────────────────────────────────────────────────────────────────────────

function VisualFlowBuilder({
  draft,
  connectedMap,
  onUpdate,
}: {
  draft: EditableFlow;
  connectedMap: Record<string, boolean>;
  onUpdate: (patch: Partial<EditableFlow>) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const sourceItems = draft.sourceSteps.map((s, i) => ({ id: `src-${i}-${s.platform}`, ...s }));
  const enrichItems = draft.enrichmentSteps.map((s, i) => ({ id: `enr-${i}-${s.platform}`, ...s }));

  function handleSourceDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIdx = sourceItems.findIndex((s) => s.id === active.id);
    const newIdx = sourceItems.findIndex((s) => s.id === over.id);
    if (oldIdx < 0 || newIdx < 0) return;
    const reordered = arrayMove(draft.sourceSteps, oldIdx, newIdx);
    reordered.forEach((s, i) => (s.priority = i + 1));
    onUpdate({ sourceSteps: reordered });
  }

  function handleEnrichDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIdx = enrichItems.findIndex((s) => s.id === active.id);
    const newIdx = enrichItems.findIndex((s) => s.id === over.id);
    if (oldIdx < 0 || newIdx < 0) return;
    const reordered = arrayMove(draft.enrichmentSteps, oldIdx, newIdx);
    reordered.forEach((s, i) => (s.priority = i + 1));
    onUpdate({ enrichmentSteps: reordered });
  }

  function addSourceStep(platform: string) {
    const meta = getMeta(platform);
    const queryOverrides: Record<string, string> = {};
    for (const f of meta.sourceFields) queryOverrides[f.key] = "";
    onUpdate({
      sourceSteps: [
        ...draft.sourceSteps,
        { platform, enabled: true, priority: draft.sourceSteps.length + 1, queryOverrides },
      ],
    });
  }

  function addEnrichStep(platform: string) {
    const meta = getMeta(platform);
    onUpdate({
      enrichmentSteps: [
        ...draft.enrichmentSteps,
        {
          platform,
          enabled: true,
          priority: draft.enrichmentSteps.length + 1,
          targetFields: meta.enrichFields.map((f) => f.key),
          fallbackTo: null,
        },
      ],
    });
  }

  // Palettes — connected first
  const sourcePalette = ALL_SOURCE_KEYS
    .filter((k) => !draft.sourceSteps.some((s) => s.platform === k))
    .sort((a, b) => {
      const aConn = isConnected(a, connectedMap) ? 1 : 0;
      const bConn = isConnected(b, connectedMap) ? 1 : 0;
      return bConn - aConn;
    });

  const enrichPalette = ALL_ENRICH_KEYS
    .filter((k) => !draft.enrichmentSteps.some((s) => s.platform === k))
    .sort((a, b) => {
      const aConn = isConnected(a, connectedMap) ? 1 : 0;
      const bConn = isConnected(b, connectedMap) ? 1 : 0;
      return bConn - aConn;
    });

  // Unconnected warning
  const unconnectedSrc = draft.sourceSteps.filter((s) => s.enabled && !isConnected(s.platform, connectedMap));
  const unconnectedEnr = draft.enrichmentSteps.filter((s) => s.enabled && !isConnected(s.platform, connectedMap));
  const totalUnconn = unconnectedSrc.length + unconnectedEnr.length;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Workflow className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">Visual Flow Builder</CardTitle>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Drag steps to reorder priority. Click in the palette to add platforms. Toggle the Switch to enable/disable a step.
            Enrichment is optional — leave the ENRICH column empty to skip it.
          </p>
          {totalUnconn > 0 && (
            <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="leading-relaxed">
                <p className="font-medium">
                  {totalUnconn} enabled step{totalUnconn > 1 ? "s" : ""} missing API key:{" "}
                  {Array.from(new Set([...unconnectedSrc, ...unconnectedEnr].map((s) => getMeta(s.platform).label))).join(", ")}
                </p>
                <p className="mt-0.5">
                  Save is blocked until you toggle them off or wire the API key in{" "}
                  <em>Setup → Integrations</em>. Free sources (AI Web Search, LinkedIn) never need a key.
                </p>
              </div>
            </div>
          )}
        </CardHeader>
      </Card>

      <div className="flex gap-4">
        {/* Left palette */}
        <div className="w-56 shrink-0 space-y-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
              <Search className="h-3 w-3" /> Source Platforms
            </p>
            <div className="space-y-1.5">
              {sourcePalette.length === 0 && (
                <p className="text-[11px] text-muted-foreground italic px-1">All sources added</p>
              )}
              {sourcePalette.map((k) => {
                const meta = getMeta(k);
                const connected = isConnected(k, connectedMap);
                return (
                  <button
                    key={k}
                    type="button"
                    onClick={() => addSourceStep(k)}
                    className={cn(
                      "w-full flex items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm transition-all hover:shadow-sm hover:scale-[1.02]",
                      meta.badgeColor,
                    )}
                  >
                    <Plus className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate flex-1">{meta.label}</span>
                    {meta.free ? (
                      <span className="text-[10px] text-green-700">free</span>
                    ) : connected ? (
                      <CheckCircle2 className="h-3 w-3 text-emerald-700 shrink-0" />
                    ) : (
                      <AlertCircle className="h-3 w-3 text-amber-700 shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
              <Sparkles className="h-3 w-3" /> Enrichment Platforms
              <span className="ml-auto text-muted-foreground font-normal">(optional)</span>
            </p>
            <div className="space-y-1.5">
              {enrichPalette.length === 0 && (
                <p className="text-[11px] text-muted-foreground italic px-1">All enrichers added</p>
              )}
              {enrichPalette.map((k) => {
                const meta = getMeta(k);
                const connected = isConnected(k, connectedMap);
                return (
                  <button
                    key={k}
                    type="button"
                    onClick={() => addEnrichStep(k)}
                    className={cn(
                      "w-full flex items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm transition-all hover:shadow-sm hover:scale-[1.02]",
                      meta.badgeColor,
                    )}
                  >
                    <Plus className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate flex-1">{meta.label}</span>
                    {connected ? (
                      <CheckCircle2 className="h-3 w-3 text-emerald-700 shrink-0" />
                    ) : (
                      <AlertCircle className="h-3 w-3 text-amber-700 shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Canvas */}
        <div className="flex-1 overflow-x-auto">
          <div className="flex gap-3 min-w-[700px]">
            {/* SOURCE */}
            <div className="flex-1">
              <div className="flex items-center gap-1.5 px-1 mb-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-violet-500">
                  <Search className="h-3.5 w-3.5 text-white" />
                </div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Source</h4>
              </div>
              <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleSourceDragEnd}>
                  <SortableContext items={sourceItems.map((s) => s.id)} strategy={verticalListSortingStrategy}>
                    {sourceItems.map((s, i) => (
                      <DraggableStepCard
                        key={s.id}
                        id={s.id}
                        platform={s.platform}
                        enabled={s.enabled}
                        priority={s.priority}
                        free={getMeta(s.platform).free}
                        connected={isConnected(s.platform, connectedMap)}
                        onToggle={(en) => {
                          const next = [...draft.sourceSteps];
                          next[i] = { ...next[i], enabled: en };
                          onUpdate({ sourceSteps: next });
                        }}
                        onRemove={() => {
                          const next = draft.sourceSteps.filter((_, idx) => idx !== i);
                          next.forEach((st, idx) => (st.priority = idx + 1));
                          onUpdate({ sourceSteps: next });
                        }}
                      />
                    ))}
                  </SortableContext>
                </DndContext>
                {sourceItems.length === 0 && (
                  <p className="text-[11px] text-muted-foreground italic text-center py-4">
                    No source steps. Add platforms from the palette.
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center pt-7">
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>

            {/* ENRICH */}
            <div className="flex-1">
              <div className="flex items-center gap-1.5 px-1 mb-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-500">
                  <Sparkles className="h-3.5 w-3.5 text-white" />
                </div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Enrich</h4>
                <span className="text-[10px] text-muted-foreground ml-1">(optional)</span>
              </div>
              <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleEnrichDragEnd}>
                  <SortableContext items={enrichItems.map((s) => s.id)} strategy={verticalListSortingStrategy}>
                    {enrichItems.map((s, i) => (
                      <DraggableStepCard
                        key={s.id}
                        id={s.id}
                        platform={s.platform}
                        enabled={s.enabled}
                        priority={s.priority}
                        isEnrich
                        free={false}
                        connected={isConnected(s.platform, connectedMap)}
                        onToggle={(en) => {
                          const next = [...draft.enrichmentSteps];
                          next[i] = { ...next[i], enabled: en };
                          onUpdate({ enrichmentSteps: next });
                        }}
                        onRemove={() => {
                          const next = draft.enrichmentSteps.filter((_, idx) => idx !== i);
                          next.forEach((st, idx) => (st.priority = idx + 1));
                          onUpdate({ enrichmentSteps: next });
                        }}
                      />
                    ))}
                  </SortableContext>
                </DndContext>
                {enrichItems.length === 0 && (
                  <p className="text-[11px] text-muted-foreground italic text-center py-4">
                    Empty — enrichment skipped.
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center pt-7">
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>

            {/* GATE */}
            <div className="flex-1">
              <div className="flex items-center gap-1.5 px-1 mb-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-red-500">
                  <ShieldCheck className="h-3.5 w-3.5 text-white" />
                </div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Gate</h4>
              </div>
              <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2.5">
                {(
                  [
                    { label: "Require Email", checked: draft.qualityGates.requireEmail, key: "requireEmail" as keyof QualityGates },
                    { label: "Verified Email", checked: draft.qualityGates.requireVerifiedEmail, key: "requireVerifiedEmail" as keyof QualityGates },
                  ] as Array<{ label: string; checked: boolean; key: keyof QualityGates }>
                ).map(({ label, checked, key }) => (
                  <div key={key} className="flex items-center justify-between rounded-lg border bg-card p-2.5">
                    <Label className="text-xs">{label}</Label>
                    <Switch
                      checked={checked as boolean}
                      onCheckedChange={(v) => onUpdate({ qualityGates: { ...draft.qualityGates, [key]: v } })}
                      className="scale-75"
                    />
                  </div>
                ))}
                <div className="rounded-lg border bg-card p-2.5">
                  <Label className="text-xs">Min Company Size</Label>
                  <Input
                    type="number"
                    value={draft.qualityGates.minCompanySize}
                    onChange={(e) =>
                      onUpdate({
                        qualityGates: {
                          ...draft.qualityGates,
                          minCompanySize: Number(e.target.value),
                          requireCompanySize: Number(e.target.value) > 0,
                        },
                      })
                    }
                    className="h-7 w-full text-xs mt-1"
                  />
                </div>
                <div className="rounded-lg border bg-card p-2.5">
                  <Label className="text-xs">LLM Threshold (0–1)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={draft.qualityGates.llmScoreThreshold}
                    onChange={(e) =>
                      onUpdate({ qualityGates: { ...draft.qualityGates, llmScoreThreshold: Number(e.target.value) } })
                    }
                    className="h-7 w-full text-xs mt-1"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center pt-7">
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>

            {/* SCORE */}
            <div className="flex-1">
              <div className="flex items-center gap-1.5 px-1 mb-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-500">
                  <BarChart2 className="h-3.5 w-3.5 text-white" />
                </div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Score</h4>
              </div>
              <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
                <div className="rounded-lg border bg-blue-50 border-blue-200 p-2.5 text-xs text-blue-700">
                  <p className="font-medium">ICP Fit Score</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">Auto-computed from ICP + persona + intent signals.</p>
                </div>
                <div className="rounded-lg border bg-blue-50 border-blue-200 p-2.5 text-xs text-blue-700">
                  <p className="font-medium">Urgency Tier</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">TIER_1–TIER_3 based on signal recency.</p>
                </div>
              </div>
            </div>

            <div className="flex items-center pt-7">
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>

            {/* IMPORT */}
            <div className="flex-1">
              <div className="flex items-center gap-1.5 px-1 mb-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-500">
                  <Download className="h-3.5 w-3.5 text-white" />
                </div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Import</h4>
              </div>
              <div className="min-h-[120px] rounded-lg border-2 border-dashed border-muted-foreground/20 p-2 space-y-2">
                <div className="rounded-lg border bg-emerald-50 border-emerald-200 p-2.5 text-xs text-emerald-700">
                  <p className="font-medium">Prospect Table</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">Surviving prospects imported with ICP + intent tags.</p>
                </div>
                <div className="rounded-lg border bg-emerald-50 border-emerald-200 p-2.5 text-xs text-emerald-700">
                  <p className="font-medium">Fire Webhooks</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">FLOW_RUN_COMPLETED fires to all active webhooks.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Status summary */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-3 text-xs">
            <Badge variant="outline" className="gap-1">
              <Search className="h-3 w-3" />
              {draft.sourceSteps.filter((s) => s.enabled).length}/{draft.sourceSteps.length} source steps active
            </Badge>
            <Badge variant="outline" className="gap-1">
              <Sparkles className="h-3 w-3" />
              {draft.enrichmentSteps.filter((s) => s.enabled).length}/{draft.enrichmentSteps.length} enrich steps active
            </Badge>
            <Badge variant="outline" className="gap-1">
              <ShieldCheck className="h-3 w-3" />
              {[
                draft.qualityGates.requireEmail && "Email",
                draft.qualityGates.requireVerifiedEmail && "Verified",
                draft.qualityGates.requireCompanySize && `Size≥${draft.qualityGates.minCompanySize}`,
                draft.qualityGates.llmScoreThreshold > 0 && `Score≥${draft.qualityGates.llmScoreThreshold.toFixed(2)}`,
                (draft.qualityGates.excludeDomains?.length || 0) > 0 &&
                  `${draft.qualityGates.excludeDomains.length} excluded`,
              ]
                .filter(Boolean)
                .join(", ") || "No gates"}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: RunMonitor (live polling inside Run dialog)
// ─────────────────────────────────────────────────────────────────────────────

function RunMonitor({
  flowName,
  runId,
}: {
  flowName: string;
  runId: string;
}) {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { data: run, isError } = useQuery<FlowRunDetail>({
    queryKey: ["flow-run-monitor", runId],
    queryFn: () => flowsApi.getRun(runId) as Promise<FlowRunDetail>,
    refetchInterval: (query) => {
      const s = (query.state.data as FlowRunDetail | undefined)?.status;
      if (s === "COMPLETED" || s === "FAILED" || s === "CANCELLED") return false;
      return 2000;
    },
    retry: 3,
  });

  useEffect(() => {
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  useEffect(() => {
    if (run?.status === "COMPLETED" || run?.status === "FAILED" || run?.status === "CANCELLED") {
      if (timerRef.current) clearInterval(timerRef.current);
    }
  }, [run?.status]);

  const status = run?.status ?? "RUNNING";
  const isTerminal = status === "COMPLETED" || status === "FAILED" || status === "CANCELLED";

  const steps = run?.steps ?? [];

  let stats: Record<string, unknown> = {};
  try {
    if (run?.stats && typeof run.stats === "object") stats = run.stats as Record<string, unknown>;
    else if (typeof run?.stats === "string") stats = JSON.parse(run.stats as string);
  } catch { /* ignore */ }

  let importedCount = 0;
  try {
    if (Array.isArray(run?.importedProspectIds)) importedCount = (run.importedProspectIds as string[]).length;
    else if (typeof run?.importedProspectIds === "string") importedCount = JSON.parse(run.importedProspectIds as string).length;
  } catch { /* ignore */ }

  const sourced = Number(stats.sourced ?? stats.source_count ?? stats.totalSourced ?? 0);
  const deduped = Number(stats.deduped ?? stats.dedup_count ?? stats.totalDeduped ?? 0);
  const enriched = Number(stats.enriched ?? stats.enrich_count ?? stats.totalEnriched ?? 0);
  const gated = Number(stats.gated ?? stats.gate_count ?? stats.totalGatedOut ?? 0);
  const imported_ = Number(stats.imported ?? importedCount ?? stats.totalImported ?? 0);

  function fmt(s: number) {
    if (s < 60) return `${s}s`;
    return `${Math.floor(s / 60)}m ${s % 60}s`;
  }

  const statusBanner = {
    RUNNING:   { border: "border-blue-200 bg-blue-50",   icon: <Activity className="h-4 w-4 animate-pulse" />, color: "text-blue-600",  label: "Running" },
    COMPLETED: { border: "border-green-200 bg-green-50", icon: <CheckCircle2 className="h-4 w-4" />,           color: "text-green-600", label: "Completed" },
    FAILED:    { border: "border-red-200 bg-red-50",     icon: <XCircle className="h-4 w-4" />,                color: "text-red-600",   label: "Failed" },
    CANCELLED: { border: "border-gray-200 bg-gray-50",   icon: <XCircle className="h-4 w-4" />,                color: "text-gray-500",  label: "Cancelled" },
    PENDING:   { border: "border-amber-200 bg-amber-50", icon: <Activity className="h-4 w-4 animate-pulse" />, color: "text-amber-600", label: "Pending" },
  } as Record<string, { border: string; icon: React.ReactNode; color: string; label: string }>;

  const sb = statusBanner[status] ?? statusBanner["RUNNING"];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className={`flex items-center gap-3 rounded-lg border p-4 ${sb.border}`}>
        <span className={sb.color}>{sb.icon}</span>
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold ${sb.color}`}>{sb.label}</p>
          <p className="text-xs text-muted-foreground truncate">{flowName}</p>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-xs font-mono text-muted-foreground">{fmt(elapsed)}</p>
          <p className="text-[10px] text-muted-foreground">elapsed</p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium">Run ID:</span>
        <span className="font-mono truncate">{runId}</span>
      </div>

      {/* Step rows */}
      {steps.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Steps</p>
          {steps.map((step) => {
            const dotColors: Record<string, string> = {
              COMPLETED: "bg-green-500",
              SUCCESS:   "bg-green-500",
              RUNNING:   "bg-blue-500 animate-pulse",
              FAILED:    "bg-red-500",
              SKIPPED:   "bg-gray-300",
              PENDING:   "bg-gray-200",
            };
            const badgeColors: Record<string, string> = {
              COMPLETED: "bg-green-100 text-green-700",
              SUCCESS:   "bg-green-100 text-green-700",
              RUNNING:   "bg-blue-100 text-blue-700",
              FAILED:    "bg-red-100 text-red-700",
              SKIPPED:   "bg-gray-100 text-gray-500",
              PENDING:   "bg-gray-100 text-gray-500",
            };
            let stepMetrics: Record<string, unknown> = {};
            try {
              if (step.metrics && typeof step.metrics === "object") stepMetrics = step.metrics as Record<string, unknown>;
              else if (typeof step.metrics === "string") stepMetrics = JSON.parse(step.metrics as string);
            } catch { /* ignore */ }
            return (
              <div key={step.id} className="flex items-center gap-2.5 rounded-md border px-3 py-2 text-xs">
                <span className={`h-2 w-2 rounded-full flex-shrink-0 ${dotColors[step.status] ?? "bg-gray-200"}`} />
                <span className="font-medium capitalize flex-1 truncate">
                  {step.kind.toLowerCase()} — {step.stepKey}
                </span>
                {step.durationMs != null && <span className="text-muted-foreground">{step.durationMs}ms</span>}
                {stepMetrics.count !== undefined && <span className="text-muted-foreground">{String(stepMetrics.count)} results</span>}
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${badgeColors[step.status] ?? "bg-gray-100 text-gray-500"}`}>
                  {step.status}
                </span>
              </div>
            );
          })}
        </div>
      ) : !isTerminal ? (
        <div className="flex items-center gap-3 rounded-md border border-dashed px-4 py-5 text-xs text-muted-foreground">
          <Activity className="h-4 w-4 animate-pulse text-blue-500 flex-shrink-0" />
          <div>
            <p className="font-medium">Pipeline executing…</p>
            <p>Step details will appear here as the flow progresses.</p>
          </div>
        </div>
      ) : null}

      {/* Funnel results */}
      {isTerminal && status === "COMPLETED" && (
        <div className="rounded-lg border bg-muted/30 p-3">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Results</p>
          <div className="grid grid-cols-5 gap-1 text-center">
            {[
              { label: "Sourced",  value: sourced || "—",   color: "text-blue-600" },
              { label: "Deduped",  value: deduped || "—",   color: "text-indigo-600" },
              { label: "Enriched", value: enriched || "—",  color: "text-orange-600" },
              { label: "Gated",    value: gated || "—",     color: "text-red-600" },
              { label: "Imported", value: imported_ || "—", color: "text-green-600" },
            ].map((item) => (
              <div key={item.label} className="rounded-md border bg-background p-2">
                <p className={`text-lg font-bold ${item.color}`}>{String(item.value)}</p>
                <p className="text-[10px] text-muted-foreground">{item.label}</p>
              </div>
            ))}
          </div>
          {imported_ > 0 && (
            <p className="text-xs text-green-700 mt-2 text-center font-medium">
              ✓ {imported_} prospect{imported_ !== 1 ? "s" : ""} added to your Prospects table
            </p>
          )}
        </div>
      )}

      {run?.errorMessage && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          <p className="font-semibold mb-0.5">Error</p>
          <p>{run.errorMessage}</p>
        </div>
      )}

      {isError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          Could not fetch run status. The run may still be executing in the background.
        </div>
      )}

      {!isTerminal && (
        <div className="flex items-center gap-2 text-xs text-blue-600">
          <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
          Polling for updates every 2 seconds…
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: RunFlowDialog
// ─────────────────────────────────────────────────────────────────────────────

function RunFlowDialog({
  flow,
  open,
  onClose,
  onRun,
  isRunning,
  activeRunId,
}: {
  flow: ProspectingFlow;
  open: boolean;
  onClose: () => void;
  onRun: (icpProfileId: string, maxProspects: number, dryRun: boolean, llmConfigId?: string) => void;
  isRunning: boolean;
  activeRunId: string | null;
}) {
  const [selectedIcp, setSelectedIcp] = useState("");
  const [maxProspects, setMaxProspects] = useState(10);
  const [dryRun, setDryRun] = useState(false);
  const [llmConfigId, setLlmConfigId] = useState("");

  const phase = activeRunId ? "running" : "configure";

  const { data: icpData } = useQuery({
    queryKey: ["icp-profiles-for-run"],
    queryFn: () =>
      http.get<unknown>("/api/v1/icp-profiles").then((r) =>
        Array.isArray(r) ? (r as IcpLite[]) : ((r as { items?: IcpLite[] })?.items ?? []),
      ),
    enabled: open && phase === "configure",
  });
  const icpProfiles = (icpData ?? []) as IcpLite[];

  function handleClose() {
    setSelectedIcp("");
    onClose();
  }

  // Live monitor phase
  if (phase === "running" && activeRunId) {
    return (
      <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <PlayCircle className="h-4 w-4 text-emerald-600" /> Flow Running
            </DialogTitle>
            <DialogDescription>
              Live progress for &ldquo;{flow.name}&rdquo;. Updates every 2 seconds.
            </DialogDescription>
          </DialogHeader>
          <RunMonitor flowName={flow.name} runId={activeRunId} />
          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <PlayCircle className="h-4 w-4 text-emerald-600" /> Run Flow
          </DialogTitle>
          <DialogDescription>
            Execute &ldquo;{flow.name}&rdquo; against an ICP profile. Runs take ~30–60s for 10 prospects.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>ICP Profile *</Label>
            <Select value={selectedIcp} onValueChange={setSelectedIcp}>
              <SelectTrigger><SelectValue placeholder="Select ICP" /></SelectTrigger>
              <SelectContent>
                {icpProfiles.map((p) => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
                {icpProfiles.length === 0 && (
                  <SelectItem value="__none__" disabled>No ICP profiles found</SelectItem>
                )}
              </SelectContent>
            </Select>
            {icpProfiles.length === 0 && (
              <p className="text-xs text-amber-600">
                No ICP profiles found — create one in ICP Profiles first.
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Max Prospects</Label>
              <Input
                type="number"
                min={1}
                max={1000}
                value={maxProspects}
                onChange={(e) => setMaxProspects(Math.max(1, Number(e.target.value) || 1))}
              />
            </div>
            <div className="space-y-2">
              <Label>LLM Config (optional)</Label>
              <Select
                value={llmConfigId || "__default__"}
                onValueChange={(v) => setLlmConfigId(v === "__default__" ? "" : v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__default__">Default (auto-select)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <div className="text-sm font-medium flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 text-amber-500" /> Dry Run
              </div>
              <div className="text-[11px] text-muted-foreground">
                Execute the pipeline without persisting prospects (useful for testing).
              </div>
            </div>
            <Switch checked={dryRun} onCheckedChange={setDryRun} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isRunning}>Cancel</Button>
          <Button
            onClick={() => onRun(selectedIcp, maxProspects, dryRun, llmConfigId || undefined)}
            disabled={isRunning || !selectedIcp}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {isRunning ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Starting…</>
            ) : (
              <><PlayCircle className="h-4 w-4 mr-2" /> Run Flow</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: TemplatesDialog
// ─────────────────────────────────────────────────────────────────────────────

function TemplatesDialog({
  open,
  onClose,
  onClone,
}: {
  open: boolean;
  onClose: () => void;
  onClone: (templateId: string, name: string) => void;
}) {
  const [selected, setSelected] = useState<FlowTemplate | null>(null);
  const [newName, setNewName] = useState("");

  const { data, isLoading } = useQuery<FlowTemplate[]>({
    queryKey: ["flow-templates-dialog"],  // separate key — avoids cache collision with FlowTemplatesPage which normalises to camelCase
    queryFn: () =>
      http.get<{ items: FlowTemplate[]; total: number }>("/api/v1/flow-templates").then(
        (r) => (Array.isArray(r) ? (r as FlowTemplate[]) : (r?.items ?? [])),
      ),
    enabled: open,
  });
  const templates = data ?? [];

  const STRICTNESS_COLORS: Record<string, string> = {
    strict: "bg-red-100 text-red-700",
    medium: "bg-amber-100 text-amber-700",
    loose:  "bg-green-100 text-green-700",
  };

  function handleClose() {
    setSelected(null);
    setNewName("");
    onClose();
  }

  if (selected) {
    return (
      <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Name your new flow</DialogTitle>
            <DialogDescription>Cloning &ldquo;{selected.name}&rdquo; — give the new flow a name.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <Label>Flow name *</Label>
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder={`${selected.name} (Copy)`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newName.trim()) {
                    onClone(selected.id, newName.trim());
                    handleClose();
                  }
                }}
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)}>← Back</Button>
            <Button
              disabled={!newName.trim()}
              onClick={() => { onClone(selected.id, newName.trim()); handleClose(); }}
            >
              Create flow
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Flow Templates</DialogTitle>
          <DialogDescription>Choose a pre-built template to start from. You can customise it after cloning.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2 max-h-[60vh] overflow-y-auto">
          {isLoading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
          {templates.map((t) => (
            <div key={t.id} className="border rounded-lg p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="font-medium text-sm">{t.name}</p>
                    <span className={cn("text-[10px] rounded px-1.5 py-0.5 font-medium", STRICTNESS_COLORS[t.gate_strictness] ?? "bg-gray-100 text-gray-700")}>
                      {t.gate_strictness}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2">{t.description}</p>
                  <p className="text-[10px] text-muted-foreground mb-2">
                    <span className="font-medium">Best for:</span> {t.recommended_for}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {Array.isArray(t.source_platforms) && t.source_platforms.map((p) => {
                      const meta = getMeta(p);
                      return (
                        <span key={p} className={cn("text-[10px] rounded px-1.5 py-0.5 font-medium border", meta.badgeColor)}>
                          {meta.label}
                        </span>
                      );
                    })}
                    {Array.isArray(t.enrichment_platforms) && t.enrichment_platforms.length > 0 && (
                      <span className="text-[10px] text-muted-foreground ml-1">
                        + {t.enrichment_platforms.map((p) => getMeta(p).label).join(", ")}
                      </span>
                    )}
                  </div>
                </div>
                <Button
                  size="sm"
                  className="flex-shrink-0"
                  onClick={() => { setSelected(t); setNewName(`${t.name} (Copy)`); }}
                >
                  Use template
                </Button>
              </div>
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-component: DeleteDialog
// ─────────────────────────────────────────────────────────────────────────────

function DeleteDialog({
  flow,
  open,
  onClose,
  onConfirm,
  isDeleting,
}: {
  flow: ProspectingFlow | null;
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isDeleting: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete flow?</DialogTitle>
          <DialogDescription>
            &ldquo;{flow?.name}&rdquo; will be permanently removed. Past run records are kept.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page Component
// ─────────────────────────────────────────────────────────────────────────────

export function FlowsPage() {
  const qc = useQueryClient();

  // ── UI state
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditableFlow | null>(null);
  const [dirty, setDirty] = useState(false);
  const [viewMode, setViewMode] = useState<"form" | "visual">("form");
  const [runOpen, setRunOpen] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProspectingFlow | null>(null);
  const importRef = useRef<HTMLInputElement>(null);

  // ── Queries
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["flows", "list"],
    queryFn: () => flowsApi.listFlows({ isTemplate: false }),
    retry: false,
  });
  const flows = useMemo(() => data?.items ?? [], [data]);

  const { data: integrations } = useQuery<TenantIntegration[]>({
    queryKey: ["integrations-for-flows"],
    queryFn: () => integrationConfigApi.tenantList(),
  });

  const connectedMap = useMemo(
    () => buildConnectedMap(integrations ?? []),
    [integrations],
  );

  // Auto-select first (or default) flow
  useEffect(() => {
    if (flows.length > 0 && !selectedId && !draft) {
      const def = flows.find((f) => f.isDefault) ?? flows[0];
      setSelectedId(def.id);
      setDraft(flowToEditable(def));
      setDirty(false);
    }
  }, [flows, selectedId, draft]);

  const selectedFlow = useMemo(() => flows.find((f) => f.id === selectedId) ?? null, [flows, selectedId]);

  function selectFlow(f: ProspectingFlow) {
    if (dirty && !window.confirm("You have unsaved changes. Discard them and switch flows?")) return;
    setSelectedId(f.id);
    setDraft(flowToEditable(f));
    setDirty(false);
  }

  function startNew() {
    if (dirty && !window.confirm("You have unsaved changes. Discard them?")) return;
    setSelectedId(null);
    setDraft(newEditable());
    setDirty(true);
  }

  function updateDraft(patch: Partial<EditableFlow>) {
    setDraft((prev) => prev ? { ...prev, ...patch } : prev);
    setDirty(true);
  }

  // ── Mutations
  const createMut = useMutation({
    mutationFn: (body: ProspectingFlowInput) => flowsApi.createFlow(body),
    onSuccess: (created) => {
      toast.success("Flow created");
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      setSelectedId(created.id);
      setDraft(flowToEditable(created));
      setDirty(false);
    },
    onError: () => toast.error("Failed to create flow"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<ProspectingFlowInput> }) =>
      flowsApi.updateFlow(id, body),
    onSuccess: (updated) => {
      toast.success("Flow saved");
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      setDraft(flowToEditable(updated));
      setDirty(false);
    },
    onError: () => toast.error("Failed to save flow"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => flowsApi.removeFlow(id),
    onSuccess: () => {
      toast.success("Flow deleted");
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      setDeleteTarget(null);
      setSelectedId(null);
      setDraft(null);
      setDirty(false);
    },
    onError: () => toast.error("Failed to delete flow"),
  });

  const runMut = useMutation({
    mutationFn: ({ flowId, icpId }: { flowId: string; icpId: string }) =>
      flowsApi.runFlow(flowId, icpId),
    onSuccess: (result) => {
      setActiveRunId(result.run_id);
    },
    onError: () => toast.error("Failed to start flow run"),
  });

  const cloneMut = useMutation({
    mutationFn: ({ templateId, name }: { templateId: string; name: string }) =>
      http.post<{ success: boolean; flow_id?: string }>("/api/v1/flow-templates/clone", {
        template_id: templateId,
        new_name: name,
      }),
    onSuccess: (result) => {
      toast.success("Template cloned as new flow");
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      if (result.flow_id) setSelectedId(result.flow_id);
    },
    onError: () => toast.error("Failed to clone template"),
  });

  // ── Save
  const handleSave = useCallback(() => {
    if (!draft) return;
    if (!draft.name.trim()) { toast.error("Flow name is required"); return; }

    const missing = findUnconnectedEnabledSteps(draft, connectedMap);
    if (missing.length > 0) {
      toast.error("Save blocked — missing API keys", {
        description: `${missing.length} enabled step${missing.length > 1 ? "s" : ""} need API keys: ${missing.join(", ")}. Toggle them off or wire keys in Setup → Integrations.`,
        duration: 9000,
      });
      return;
    }

    const input = editableToInput(draft);
    if (draft.id) {
      updateMut.mutate({ id: draft.id, body: input });
    } else {
      createMut.mutate(input);
    }
  }, [draft, connectedMap, updateMut, createMut]);

  // ── Duplicate
  const handleDuplicate = useCallback(() => {
    if (!draft?.id) { toast.error("Save the flow before duplicating"); return; }
    const missing = findUnconnectedEnabledSteps(draft, connectedMap);
    if (missing.length > 0) {
      toast.error("Duplicate blocked — missing API keys", {
        description: `Fix ${missing.join(", ")} in Setup → Integrations first.`,
        duration: 9000,
      });
      return;
    }
    const input = editableToInput(draft);
    createMut.mutate({ ...input, name: `${draft.name} (Copy)`, isDefault: false });
  }, [draft, connectedMap, createMut]);

  // ── Set Default
  async function handleSetDefault(f: ProspectingFlow) {
    if (f.isDefault) return;
    try {
      await flowsApi.updateFlow(f.id, { isDefault: true } as Partial<ProspectingFlowInput>);
      toast.success(`"${f.name}" is now the default flow`);
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      if (selectedId === f.id && draft) setDraft({ ...draft, isDefault: true });
    } catch {
      toast.error("Failed to set default");
    }
  }

  // ── Export
  async function handleExport() {
    if (!draft?.id) { toast.error("Save the flow before exporting"); return; }
    try {
      const res = await fetch(`/api/v1/flows/${draft.id}/export`, { credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(draft.name || "flow").replace(/[^a-z0-9_-]+/gi, "_")}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Flow exported");
    } catch {
      toast.error("Export failed");
    }
  }

  // ── Import
  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const text = await file.text();
      const obj = JSON.parse(text);
      const res = await fetch("/api/v1/flows/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(obj),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
      toast.success(`Flow imported: ${(data as ProspectingFlow).name}`);
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      setSelectedId((data as ProspectingFlow).id);
      setDraft(flowToEditable(data as ProspectingFlow));
      setDirty(false);
    } catch (err) {
      toast.error("Import failed", {
        description: err instanceof Error ? err.message : "Invalid JSON file",
      });
    }
  }

  const isSaving = createMut.isPending || updateMut.isPending;
  const canRun = !!draft?.id && !dirty;

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-4">
        {/* Hidden import input */}
        <input
          ref={importRef}
          type="file"
          accept=".json,application/json"
          onChange={handleImportFile}
          className="hidden"
        />

        {/* Page header */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Workflow className="h-6 w-6 text-primary" />
              Prospecting Flows
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Orchestrate how your connected platforms work together — ordered sourcing, chained enrichment with
              fallbacks, and quality gates.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" /> Refresh
            </Button>
            <Button variant="outline" onClick={() => setTemplatesOpen(true)}>
              <Layers className="h-4 w-4 mr-2" /> Templates
            </Button>
            <Button variant="outline" onClick={() => importRef.current?.click()}>
              <Upload className="h-4 w-4 mr-2" /> Import
            </Button>
            <Button onClick={startNew}>
              <Plus className="h-4 w-4 mr-2" /> New Flow
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
          {/* ═══ LEFT PANEL: Flow list ═══ */}
          <Card className="h-fit">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center justify-between">
                Flows
                <Badge variant="secondary">{flows.length}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-2">
              <div className="space-y-1 max-h-[calc(100vh-280px)] min-h-[300px] overflow-y-auto pr-1">
                {isLoading && Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="px-2 py-1"><Skeleton className="h-16 w-full" /></div>
                ))}
                {isError && (
                  <div className="text-xs text-muted-foreground text-center py-6 px-2">
                    Failed to load.{" "}
                    <button onClick={() => refetch()} className="underline text-primary">Retry</button>
                  </div>
                )}
                {!isLoading && !isError && flows.length === 0 && (
                  <p className="text-xs text-muted-foreground text-center py-6 px-2">
                    No flows yet. Create your first flow.
                  </p>
                )}
                {flows.map((f) => {
                  const isSelected = f.id === selectedId;
                  return (
                    <div
                      key={f.id}
                      className={cn(
                        "group rounded-md border px-3 py-2.5 cursor-pointer transition-colors",
                        isSelected ? "border-primary bg-primary/5" : "border-transparent hover:bg-muted/50",
                      )}
                      onClick={() => selectFlow(f)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-sm truncate">{f.name}</span>
                            {f.isDefault && <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400 shrink-0" />}
                          </div>
                          <p className="text-xs text-muted-foreground truncate mt-0.5">
                            {f.description || "No description"}
                          </p>
                          <div className="flex items-center gap-1.5 mt-1.5">
                            <Badge variant="outline" className="text-[10px] py-0 h-4">
                              {parseStepsFromRaw(f.sourceSteps).length} src
                            </Badge>
                            <Badge variant="outline" className="text-[10px] py-0 h-4">
                              {parseStepsFromRaw(f.enrichmentSteps).length} enr
                            </Badge>
                            {!f.isActive && (
                              <Badge variant="secondary" className="text-[10px] py-0 h-4">inactive</Badge>
                            )}
                          </div>
                        </div>
                        {!f.isDefault && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
                                onClick={(e) => { e.stopPropagation(); handleSetDefault(f); }}
                              >
                                <StarOff className="h-3.5 w-3.5" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Set as default</TooltipContent>
                          </Tooltip>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <Button variant="outline" className="w-full mt-2" onClick={startNew}>
                <Plus className="h-4 w-4 mr-2" /> New Flow
              </Button>
            </CardContent>
          </Card>

          {/* ═══ RIGHT PANEL: Editor ═══ */}
          {!draft ? (
            <Card className="flex items-center justify-center min-h-[400px]">
              <CardContent className="text-center text-muted-foreground py-12">
                <Inbox className="h-12 w-12 mx-auto mb-3 opacity-40" />
                <p className="font-medium">No flow selected</p>
                <p className="text-sm mt-1">Select a flow from the list, or create a new one.</p>
                <Button className="mt-4" onClick={startNew}>
                  <Plus className="h-4 w-4 mr-2" /> New Flow
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {/* Editor header card */}
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        {draft.isDefault && (
                          <Badge className="bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-100">
                            <Star className="h-3 w-3 fill-amber-400 text-amber-400 mr-1" /> Default
                          </Badge>
                        )}
                        <Badge variant={draft.isActive ? "default" : "secondary"}>
                          {draft.isActive ? "Active" : "Inactive"}
                        </Badge>
                        {dirty && (
                          <Badge variant="outline" className="text-amber-600 border-amber-300">
                            <AlertCircle className="h-3 w-3 mr-1" /> Unsaved
                          </Badge>
                        )}
                        {/* View toggle */}
                        <div className="ml-auto flex items-center rounded-md border bg-muted/40 p-0.5">
                          <button
                            type="button"
                            onClick={() => setViewMode("form")}
                            className={cn(
                              "px-2.5 py-1 text-xs rounded transition-colors",
                              viewMode === "form" ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground",
                            )}
                          >
                            Form View
                          </button>
                          <button
                            type="button"
                            onClick={() => setViewMode("visual")}
                            className={cn(
                              "px-2.5 py-1 text-xs rounded transition-colors flex items-center gap-1",
                              viewMode === "visual" ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground",
                            )}
                          >
                            <Workflow className="h-3 w-3" /> Visual Builder
                          </button>
                        </div>
                      </div>
                      {/* Inline name / description editors */}
                      <Input
                        value={draft.name}
                        onChange={(e) => updateDraft({ name: e.target.value })}
                        placeholder="Flow name"
                        className="text-lg font-semibold h-9 border-none px-0 focus-visible:ring-0"
                      />
                      <Textarea
                        value={draft.description}
                        onChange={(e) => updateDraft({ description: e.target.value })}
                        placeholder="Add a description for this flow…"
                        className="min-h-[40px] resize-none border-none px-0 focus-visible:ring-0 text-sm text-muted-foreground"
                      />
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => updateDraft({ isDefault: !draft.isDefault })}
                            disabled={isSaving}
                          >
                            <Star className={`h-4 w-4 ${draft.isDefault ? "fill-amber-400 text-amber-400" : ""}`} />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>{draft.isDefault ? "Unset default" : "Set as default"}</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline" size="icon" className="h-8 w-8"
                            onClick={handleExport}
                            disabled={!draft.id}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Export as JSON</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline" size="icon" className="h-8 w-8"
                            onClick={handleDuplicate}
                            disabled={isSaving || !draft.id}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Duplicate</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline" size="icon" className="h-8 w-8"
                            onClick={() => updateDraft({ isActive: !draft.isActive })}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Toggle Active</TooltipContent>
                      </Tooltip>
                      <Button
                        variant="outline" size="icon" className="h-8 w-8 text-destructive"
                        onClick={() => selectedFlow && setDeleteTarget(selectedFlow)}
                        disabled={isSaving || !draft.id}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => { setActiveRunId(null); setRunOpen(true); }}
                        disabled={!canRun}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        <PlayCircle className="h-4 w-4 mr-1.5" /> Run
                      </Button>
                      <Button size="sm" onClick={handleSave} disabled={isSaving || !dirty}>
                        {isSaving ? (
                          <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Saving…</>
                        ) : (
                          <><Save className="h-4 w-4 mr-1.5" /> Save</>
                        )}
                      </Button>
                    </div>
                  </div>
                  {dirty && (
                    <p className="text-[11px] text-amber-600 mt-2 flex items-center gap-1">
                      <AlertCircle className="h-3 w-3" />
                      Save your changes before running the flow — Run is disabled while there are unsaved edits.
                    </p>
                  )}
                </CardHeader>
              </Card>

              {/* Form View — 3-panel */}
              {viewMode === "form" ? (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <SourceStepsCard
                      steps={draft.sourceSteps}
                      connectedMap={connectedMap}
                      onChange={(sourceSteps) => updateDraft({ sourceSteps })}
                    />
                    <EnrichmentStepsCard
                      steps={draft.enrichmentSteps}
                      connectedMap={connectedMap}
                      onChange={(enrichmentSteps) => updateDraft({ enrichmentSteps })}
                    />
                    <QualityGatesCard
                      gates={draft.qualityGates}
                      onChange={(patch) => updateDraft({ qualityGates: { ...draft.qualityGates, ...patch } })}
                    />
                  </div>
                  <FlowSummary draft={draft} connectedMap={connectedMap} />
                </>
              ) : (
                <VisualFlowBuilder
                  draft={draft}
                  connectedMap={connectedMap}
                  onUpdate={updateDraft}
                />
              )}
            </div>
          )}
        </div>

        {/* Dialogs */}
        {selectedFlow && (
          <RunFlowDialog
            flow={selectedFlow}
            open={runOpen}
            onClose={() => { setRunOpen(false); setActiveRunId(null); }}
            onRun={(icpId, _maxProspects, _dryRun, _llmConfigId) =>
              runMut.mutate({ flowId: selectedFlow.id, icpId })
            }
            isRunning={runMut.isPending}
            activeRunId={activeRunId}
          />
        )}

        <TemplatesDialog
          open={templatesOpen}
          onClose={() => setTemplatesOpen(false)}
          onClone={(templateId, name) => cloneMut.mutate({ templateId, name })}
        />

        <DeleteDialog
          flow={deleteTarget}
          open={!!deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onConfirm={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
          isDeleting={deleteMut.isPending}
        />
      </div>
    </TooltipProvider>
  );
}