/**
 * ProspectsPage.tsx — Full-feature Prospects page for OUTRENA React/FastAPI.
 *
 * Closes all PR-1 through PR-18 gap items:
 *   PR-1  AI Prospect Sourcing Panel (violet gradient, collapsible, source chips, import)
 *   PR-2  Intelligence Tools Panel (amber gradient, NL Search + Lookalike)
 *   PR-3  Per-row actions: Signals, Enrich, Domain Enrich, Validate Email,
 *         Competitor Radar, Ultimate Profile, Hook Generator, Log Call
 *   PR-4  Bulk selection — checkbox column, Select All, Add to Campaign dialog
 *   PR-5  CSV Import dialog (drag-drop zone, result summary)
 *   PR-6  Validate All Emails toolbar button
 *   PR-7  Export CSV button
 *   PR-8  ICP fit score (0-100) + P0/P1/P2 urgency tier badge with color
 *   PR-9  Add Prospect form: all fields incl. phone, notes, seniority, ICP
 *   PR-10 Domain Enrichment inline result card (below table)
 *   PR-11 Call Log dialog (phone, outcome, duration, notes)
 *   PR-12 Competitor Radar result dialog
 *   PR-13 Ultimate Profile result dialog
 *   PR-14 Hook Generator result dialog with copy-per-hook
 *   PR-15 Signals display as expandable badges in table row
 *   PR-16 Email validation badge (valid/catch-all/invalid/unverified)
 *   PR-17 Intent Source + Intent Strength in table
 *   PR-18 Table search/filter: live text search + seniority + score filter
 *
 * API routes (FastAPI backend):
 *   GET    /api/v1/prospects                    list
 *   POST   /api/v1/prospects                    create
 *   DELETE /api/v1/prospects/{id}               delete
 *   POST   /api/v1/prospects/import             CSV import (multipart)
 *   GET    /api/v1/prospects/export             CSV download
 *   POST   /api/v1/prospects/enrich             enrichment waterfall
 *   POST   /api/v1/prospects/email-validate     MX + syntax validation
 *   POST   /api/v1/prospects/source             multi-source discovery
 *   POST   /api/v1/prospects/search-nl          NL search
 *   POST   /api/v1/prospects/lookalike          lookalike finder
 *   POST   /api/v1/prospects/domain-enrich      domain intelligence
 *   POST   /api/v1/prospects/competitor-radar   competitor extraction
 *   POST   /api/v1/prospects/ultimate-profile   deep business profile
 *   POST   /api/v1/prospects/hook-generator     opener hooks
 *   POST   /api/v1/prospects/signals            signal research
 *   POST   /api/v1/call-logs                    call log
 *   GET    /api/v1/icp-profiles                 ICP list
 *   GET    /api/v1/campaigns                    campaign list (for bulk add)
 *   POST   /api/v1/campaigns/{id}/prospects     bulk add prospects
 */

import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  FileDown,
  Filter,
  Globe,
  Loader2,
  MailCheck,
  Phone,
  Plus,
  Radar,
  Search,
  ShieldAlert,
  Sparkles,
  Star,
  Trash2,
  Upload,
  UserSearch,
  Users,
  Wand2,
  X,
  ZapIcon,
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
import { Progress } from "@/components/ui/progress";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogClose,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
// import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/* ── Types ─────────────────────────────────────────────────────────── */

interface Prospect {
  id: string;
  firstName: string;
  lastName: string;
  email: string | null;
  title: string | null;
  company: string | null;
  domain: string | null;
  linkedinUrl: string | null;
  phone: string | null;
  seniority: string;
  signals: unknown[];
  qaScore: number | null;
  status: string;
  notes: string | null;
  emailValidated: boolean;
  emailValidationDetail: string | null;
  emailConfidence: number | null;
  isCatchAll: boolean;
  enrichmentTier: string;
  intentSource: string;
  intentDetail: string | null;
  intentStrength: number | null;
  timezone: string | null;
  icpProfileId: string | null;
  icpFitScore: number | null;
  icpPersona: string | null;
  urgencyTier: string | null;
  createdAt: string;
  updatedAt: string;
}

interface IcpProfile {
  id: string;
  name: string;
}

interface Campaign {
  id: string;
  name: string;
  status: string;
}

interface SourceChip {
  source: string;
  label: string;
  found: number;
  error?: string;
  durationMs?: number;
}

interface SourcedProspect {
  firstName: string;
  lastName: string;
  email?: string;
  title?: string;
  company?: string;
  domain?: string;
  linkedinUrl?: string;
  _source: string;
  _sourceLabel?: string;
  _isDuplicate?: boolean;
  matchReason?: string;
}

interface SourceResult {
  prospects: SourcedProspect[];
  totalFromPlatforms: number;
  totalAfterDedup: number;
  newProspects: number;
  duplicatesFound: number;
  sources: SourceChip[];
}

interface NlResult {
  interpretation: string | null;
  db_matches: Array<{ name: string; company: string; title: string; icp_score: number }> | null;
  web_results: Array<{ title: string; snippet: string; url: string }> | null;
}

interface LookalikeEntry {
  name: string | null;
  title: string | null;
  company: string | null;
  similarity_score: number | null;
  matched_features: string[] | null;
}

interface UltimateProfileResult {
  what_they_do: string | null;
  products: string[] | null;
  target_market: string | null;
  tech_stack: string[] | null;
  company_size: string | null;
  industry: string | null;
  pain_points: string[] | null;
  buying_signals: string[] | null;
  competitors: string[] | null;
  icp_fit_score: number | null;
  recommended_angle: string | null;
  confidence_score: number | null;
}

interface CompetitorEntry {
  name: string;
  domain?: string;
  description?: string;
  positioning?: string;
  overlap_score?: number;
}

interface HookEntry {
  text: string | null;
  type: string | null;
}

/* ── Constants ──────────────────────────────────────────────────────── */

const SOURCE_COLORS: Record<string, string> = {
  web_search: "bg-violet-100 text-violet-700 border-violet-200",
  apollo: "bg-sky-100 text-sky-700 border-sky-200",
  clay: "bg-orange-100 text-orange-700 border-orange-200",
  zoominfo: "bg-blue-100 text-blue-700 border-blue-200",
  clearbit: "bg-teal-100 text-teal-700 border-teal-200",
  hunter: "bg-amber-100 text-amber-700 border-amber-200",
  lusha: "bg-rose-100 text-rose-700 border-rose-200",
  kaspr: "bg-pink-100 text-pink-700 border-pink-200",
  snovio: "bg-cyan-100 text-cyan-700 border-cyan-200",
  linkedin: "bg-blue-600 text-white border-blue-700",
};

const SOURCE_ICONS: Record<string, string> = {
  web_search: "🤖",
  apollo: "🅰️",
  clay: "🟧",
  zoominfo: "🔵",
  clearbit: "🟢",
  hunter: "🟡",
  lusha: "🔴",
  kaspr: "🩷",
  snovio: "🔷",
  linkedin: "💼",
};

const URGENCY_META: Record<string, { label: string; bg: string; text: string; border: string }> = {
  P0: { label: "P0 — Hot", bg: "bg-red-50", text: "text-red-700", border: "border-red-300" },
  P1: { label: "P1 — Warm", bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-300" },
  P2: { label: "P2 — Cool", bg: "bg-slate-50", text: "text-slate-600", border: "border-slate-200" },
};

const INTENT_COLORS: Record<string, string> = {
  FUNDING_URGENCY: "bg-emerald-50 text-emerald-700 border-emerald-200",
  HIRING_BUDGET: "bg-purple-50 text-purple-700 border-purple-200",
  FORUM_PAIN: "bg-amber-50 text-amber-700 border-amber-200",
  LINKEDIN_DEMAND: "bg-cyan-50 text-cyan-700 border-cyan-200",
  REFERRAL: "bg-blue-50 text-blue-700 border-blue-200",
  INBOUND: "bg-green-50 text-green-700 border-green-200",
  OTHER: "bg-gray-50 text-gray-600 border-gray-200",
};

const STATUS_COLORS: Record<string, string> = {
  new: "bg-gray-100 text-gray-700",
  researching: "bg-blue-100 text-blue-700",
  drafted: "bg-violet-100 text-violet-700",
  queued: "bg-amber-100 text-amber-700",
  contacted: "bg-teal-100 text-teal-700",
  replied: "bg-emerald-100 text-emerald-700",
  converted: "bg-green-100 text-green-700",
  lost: "bg-red-100 text-red-700",
};

/* ── Page ──────────────────────────────────────────────────────────── */

export function ProspectsPage() {
  const qc = useQueryClient();

  /* ── Data queries ── */
  const prospectsQuery = useQuery<{ items: Prospect[]; total: number }>({
    queryKey: ["prospects"],
    queryFn: () =>
      http.get<any>("/api/v1/prospects").then((r) =>
        Array.isArray(r) ? { items: r, total: r.length } : { items: r?.items ?? [], total: r?.total ?? 0 }
      ),
  });
  const icpQuery = useQuery<IcpProfile[]>({
    queryKey: ["icp-profiles"],
    queryFn: () => http.get<any>("/api/v1/icp-profiles").then((r) => (Array.isArray(r) ? r : r?.items ?? [])),
  });
  const campaignQuery = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn: () => http.get<any>("/api/v1/campaigns").then((r) => (Array.isArray(r) ? r : r?.items ?? [])),
  });

  const allProspects: Prospect[] = prospectsQuery.data?.items ?? [];
  const icps: IcpProfile[] = icpQuery.data ?? [];
  const campaigns: Campaign[] = campaignQuery.data ?? [];

  /* ── Filter/search state (PR-18) ── */
  const [search, setSearch] = useState("");
  const [seniorityFilter, setSeniorityFilter] = useState("all");
  const [scoreMin, setScoreMin] = useState(0);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allProspects.filter((p) => {
      if (q && !`${p.firstName} ${p.lastName} ${p.email ?? ""} ${p.company ?? ""} ${p.title ?? ""}`.toLowerCase().includes(q)) return false;
      if (seniorityFilter !== "all" && p.seniority !== seniorityFilter) return false;
      if (scoreMin > 0 && (p.icpFitScore ?? 0) < scoreMin) return false;
      return true;
    });
  }, [allProspects, search, seniorityFilter, scoreMin]);

  /* ── Bulk selection (PR-4) ── */
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [addToCampaignOpen, setAddToCampaignOpen] = useState(false);
  const [addToCampaignId, setAddToCampaignId] = useState("");

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(filtered.map((p) => p.id)));
  };

  /* ── Add Prospect (PR-9) ── */
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState({
    firstName: "", lastName: "", email: "", title: "", company: "",
    domain: "", linkedinUrl: "", phone: "", seniority: "IC",
    icpProfileId: "", notes: "",
  });
  const resetAddForm = () =>
    setAddForm({ firstName: "", lastName: "", email: "", title: "", company: "", domain: "", linkedinUrl: "", phone: "", seniority: "IC", icpProfileId: "", notes: "" });

  const addMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => http.post("/api/v1/prospects", body),
    onSuccess: () => {
      toast.success("Prospect added");
      qc.invalidateQueries({ queryKey: ["prospects"] });
      setAddOpen(false);
      resetAddForm();
    },
    onError: () => toast.error("Failed to add prospect"),
  });

  /* ── Delete ── */
  const [deleteTarget, setDeleteTarget] = useState<Prospect | null>(null);
  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/prospects/${id}`),
    onSuccess: () => {
      toast.success("Prospect deleted");
      qc.invalidateQueries({ queryKey: ["prospects"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Delete failed"),
  });

  /* ── CSV Import (PR-5) ── */
  const [importOpen, setImportOpen] = useState(false);
  const [csvImporting, setCsvImporting] = useState(false);
  const [csvResult, setCsvResult] = useState<{ imported: number; skipped: number; errors: string[]; totalRows: number } | null>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);

  const handleCsvUpload = async (file: File) => {
    setCsvImporting(true);
    setCsvResult(null);
    const fd = new FormData();
    fd.append("file", file);
    if (icps.length > 0) fd.append("icp_profile_id", icps[0].id);
    try {
      const data = await http.post<any>("/api/v1/prospects/import", fd);
      setCsvResult(data);
      toast.success(`Imported ${data.imported} prospects`);
      qc.invalidateQueries({ queryKey: ["prospects"] });
    } catch {
      toast.error("CSV import failed");
    }
    setCsvImporting(false);
  };

  /* ── Export CSV (PR-7) ── */
  const handleExport = () => {
    window.open("/api/v1/prospects/export", "_blank");
  };

  /* ── Validate All Emails (PR-6) ── */
  const [validatingAll, setValidatingAll] = useState(false);
  const handleValidateAll = async () => {
    const withEmail = allProspects.filter((p) => p.email);
    if (withEmail.length === 0) { toast.error("No prospects with emails"); return; }
    setValidatingAll(true);
    let validated = 0, invalid = 0;
    for (const p of withEmail) {
      try {
        const data = await http.post<any>("/api/v1/prospects/email-validate", { email: p.email });
        if (data.valid) validated++; else invalid++;
      } catch { /* skip */ }
    }
    toast.success(`Validated: ${validated} valid, ${invalid} invalid`);
    qc.invalidateQueries({ queryKey: ["prospects"] });
    setValidatingAll(false);
  };

  /* ── Per-row: Validate Email (PR-16) ── */
  const [validatingId, setValidatingId] = useState<string | null>(null);
  const handleValidateEmail = async (p: Prospect) => {
    if (!p.email) return;
    setValidatingId(p.id);
    try {
      const data = await http.post<any>("/api/v1/prospects/email-validate", { email: p.email });
      if (data.valid) toast.success(`Valid email${data.isCatchAll ? " (catch-all)" : ""}`);
      else toast.error(`Invalid email: ${data.detail ?? "unknown reason"}`);
      qc.invalidateQueries({ queryKey: ["prospects"] });
    } catch { toast.error("Validation failed"); }
    setValidatingId(null);
  };

  /* ── Per-row: Enrich (PR-3) ── */
  const [enrichingId, setEnrichingId] = useState<string | null>(null);
  const handleEnrich = async (p: Prospect) => {
    setEnrichingId(p.id);
    try {
      const data = await http.post<any>("/api/v1/prospects/enrich", { prospectId: p.id });
      if (data.enriched) toast.success("Enriched successfully");
      else toast.info(data.detail ?? "No new data found — connect platforms in Integrations");
      qc.invalidateQueries({ queryKey: ["prospects"] });
    } catch { toast.error("Enrichment failed"); }
    setEnrichingId(null);
  };

  /* ── Per-row: Signal Research (PR-3, PR-15) ── */
  const [researchingId, setResearchingId] = useState<string | null>(null);
  // const handleResearchSignals = async (p: Prospect) => {
  //   setResearchingId(p.id);
  //   try {
  //     const data = await http.post<any>("/api/v1/prospects/signals", { prospectId: p.id });
  //     if (data.success) toast.success(`Found ${data.signals?.length ?? 0} signals`);
  //     else toast.error(data.error ?? "Signal research failed");
  //     qc.invalidateQueries({ queryKey: ["prospects"] });
  //   } catch { toast.error("Signal research failed"); }
  //   setResearchingId(null);
  // };

  const handleResearchSignals = (p: Prospect) => {
  setResearchingId(p.id);

  signalsMut.mutate(p.id, {
    onSettled: () => setResearchingId(null),
  });
};

const signalsMut = useMutation({
  mutationFn: (id: string) =>
    http.post("/api/v1/signals/scan", {
      prospectIds: [id],
    }),

  onSuccess: (data:any) => {
    // signals/scan returns {scanned, detected, signals:[]} — no success field
    if (Array.isArray(data.signals)) {
      if (data.signals.length > 0)
        toast.success(`Found ${data.signals.length} signals`);
      else
        toast.info("No new signals detected for this prospect.");
    } else {
      toast.error(data.error ?? "Signal research failed");
    }
    qc.invalidateQueries({ queryKey: ["prospects"] });
  },

  onError: () => toast.error("Signal research failed"),
});

  /* ── Per-row: Domain Enrich (PR-3, PR-10) ── */
  const [domainEnrichingId, setDomainEnrichingId] = useState<string | null>(null);
  const [domainEnrichResults, setDomainEnrichResults] = useState<Record<string, any>>({});
  const handleDomainEnrich = async (p: Prospect) => {
    if (!p.domain && !p.company) { toast.error("Need domain or company to enrich"); return; }
    setDomainEnrichingId(p.id);
    try {
      // domain-enrich returns the flat DomainEnrichment record directly:
      // {id, domain, companyName, industry, employeeCount, techStack, ...}
      // It does NOT wrap in {success, enrichment}.
      const data = await http.post<any>("/api/v1/domain-enrich", {
        domain: p.domain,
      });
      if (data && (data.domain || data.id)) {
        // Map flat response to the shape the inline results card expects
        const enrichment = {
          industry: data.industry ?? null,
          company_size: data.employeeCount ? String(data.employeeCount) : null,
          icp_fit_score: null,
          tech_stack: Array.isArray(data.techStack) ? data.techStack : [],
          pain_points: [],
          buying_signals: [],
          recommended_angle: data.description ?? null,
        };
        setDomainEnrichResults((prev) => ({ ...prev, [p.id]: enrichment }));
        toast.success("Domain enriched");
        qc.invalidateQueries({ queryKey: ["prospects"] });
      } else toast.error("Domain enrichment failed");
    } catch { toast.error("Domain enrichment failed"); }
    setDomainEnrichingId(null);
  };

  /* ── Per-row: Competitor Radar (PR-3, PR-12) ── */
  const [competitorLoadingId, setCompetitorLoadingId] = useState<string | null>(null);
  const [competitorResult, setCompetitorResult] = useState<{ prospect: Prospect; competitors: CompetitorEntry[] } | null>(null);
  const handleCompetitorRadar = async (p: Prospect) => {
    if (!p.company && !p.domain) { toast.error("Need company or domain"); return; }
    setCompetitorLoadingId(p.id);
    try {
      const data = await http.post<any>("/api/v1/prospects/competitor-radar", {
        prospect_id: p.id,
      });
      if (data.success) {
        setCompetitorResult({ prospect: p, competitors: data.competitors ?? [] });
        toast.success(`Found ${data.competitors?.length ?? 0} competitors`);
      } else toast.error(data.error ?? "Competitor radar failed");
    } catch { toast.error("Competitor radar failed"); }
    setCompetitorLoadingId(null);
  };

  /* ── Per-row: Ultimate Profile (PR-3, PR-13) ── */
  const [profileLoadingId, setProfileLoadingId] = useState<string | null>(null);
  const [profileResult, setProfileResult] = useState<{ prospect: Prospect; profile: UltimateProfileResult; sourcesAnalyzed: number } | null>(null);
  const handleUltimateProfile = async (p: Prospect) => {
    if (!p.company && !p.domain) { toast.error("Need company or domain"); return; }
    setProfileLoadingId(p.id);
    try {
      // Backend UltimateProfileRequest requires prospect_id (snake_case)
      const data = await http.post<any>("/api/v1/prospects/ultimate-profile", { prospect_id: p.id });
      if (data.success) {
        setProfileResult({ prospect: p, profile: data.profile, sourcesAnalyzed: data.sources_analyzed ?? 0 });
        toast.success(`Profile generated for ${p.company}`);
      } else toast.error(data.error ?? "Profile generation failed");
    } catch { toast.error("Profile generation failed"); }
    setProfileLoadingId(null);
  };

  /* ── Per-row: Hook Generator (PR-3, PR-14) ── */
  const [hookLoadingId, setHookLoadingId] = useState<string | null>(null);
  const [hookResult, setHookResult] = useState<{ prospect: Prospect; hooks: HookEntry[] } | null>(null);
  const handleHookGen = async (p: Prospect) => {
    setHookLoadingId(p.id);
    try {
      // Backend HookGeneratorRequest requires prospect_id (snake_case)
      const data = await http.post<any>("/api/v1/prospects/hook-generator", { prospect_id: p.id });
      if (data.success) {
        setHookResult({ prospect: p, hooks: data.hooks ?? [] });
        toast.success(`Generated ${data.hooks?.length ?? 0} hooks`);
      } else toast.error(data.error ?? "Hook generation failed");
    } catch { toast.error("Hook generation failed"); }
    setHookLoadingId(null);
  };

  /* ── Per-row: Log Call (PR-3, PR-11) ── */
  const [callLogProspect, setCallLogProspect] = useState<Prospect | null>(null);
  const [callLogForm, setCallLogForm] = useState({ phone: "", outcome: "connected", durationSec: "", notes: "" });
  const [callLogSaving, setCallLogSaving] = useState(false);
  const openCallLog = (p: Prospect) => {
    setCallLogProspect(p);
    setCallLogForm({ phone: p.phone ?? "", outcome: "connected", durationSec: "", notes: "" });
  };
  const handleLogCall = async () => {
    if (!callLogProspect || !callLogForm.phone.trim()) { toast.error("Phone required"); return; }
    setCallLogSaving(true);
    try {
      await http.post("/api/v1/call-logs", {
        prospectId: callLogProspect.id,
        phone: callLogForm.phone,
        outcome: callLogForm.outcome,
        durationSec: callLogForm.durationSec ? Number(callLogForm.durationSec) : null,
        notes: callLogForm.notes || null,
      });
      toast.success("Call logged");
      setCallLogProspect(null);
    } catch { toast.error("Failed to log call"); }
    setCallLogSaving(false);
  };

  /* ── AI Prospect Sourcing (PR-1) ── */
  const [sourcingOpen, setSourcingOpen] = useState(false);
  const [sourceIcpId, setSourceIcpId] = useState("");
  const [sourcing, setSourcing] = useState(false);
  const [sourceResult, setSourceResult] = useState<SourceResult | null>(null);
  const [importingSourced, setImportingSourced] = useState(false);

  const handleSourceProspects = async () => {
    if (!sourceIcpId) { toast.error("Select an ICP profile first"); return; }
    setSourcing(true);
    setSourceResult(null);
    try {
      // const data = await http.post<any>("/api/v1/prospects/source", {
      //   icpProfileId: sourceIcpId,
      //   maxProspects: 20,
      // });
      const icp = icps.find((i) => i.id === sourceIcpId);
    const data = await http.post<any>("/api/v1/prospect-source/nl-search", {
      query: `Find ${icp?.name ?? "B2B"} prospects matching our ICP`,
      icpProfileId: sourceIcpId,
      limit: 20,
    });
      if (data.success) {
        setSourceResult(data);
        toast.success(`Found ${data.totalAfterDedup} prospects from ${data.sources?.filter((s: SourceChip) => s.found > 0).length ?? 0} sources`);
      } else toast.error(data.error ?? "Sourcing failed");
    } catch { toast.error("Prospect sourcing failed"); }
    setSourcing(false);
  };

  const handleImportSourced = async () => {
    if (!sourceResult) return;
    const toImport = sourceResult.prospects.filter((p) => !p._isDuplicate && p.firstName);
    if (toImport.length === 0) { toast.error("No new prospects to import"); return; }
    setImportingSourced(true);
    let imported = 0;
    for (const p of toImport) {
      try {
        await http.post("/api/v1/prospects", {
          firstName: p.firstName,
          lastName: p.lastName || "Unknown",
          email: p.email || null,
          title: p.title || null,
          company: p.company || null,
          domain: p.domain || null,
          linkedinUrl: p.linkedinUrl || null,
          seniority: "IC",
          icpProfileId: sourceIcpId,
          notes: p.matchReason ? `[${p._sourceLabel ?? p._source}] ${p.matchReason}` : `[${p._sourceLabel ?? "Sourced"}]`,
        });
        imported++;
      } catch { /* skip duplicates */ }
    }
    toast.success(`Imported ${imported} of ${toImport.length} prospects`);
    setImportingSourced(false);
    setSourceResult(null);
    qc.invalidateQueries({ queryKey: ["prospects"] });
  };

  /* ── Intelligence Tools (PR-2) ── */
  const [intelOpen, setIntelOpen] = useState(false);
  const [nlQuery, setNlQuery] = useState("");
  const [nlSearching, setNlSearching] = useState(false);
  const [nlResult, setNlResult] = useState<NlResult | null>(null);
  const [lookalikeLoading, setLookalikeLoading] = useState(false);
  const [lookalikeResult, setLookalikeResult] = useState<{ lookalikes: LookalikeEntry[] } | null>(null);

  const handleNlSearch = async () => {
    if (!nlQuery.trim()) { toast.error("Enter a search query"); return; }
    setNlSearching(true);
    setNlResult(null);
    try {
      const data = await http.post<any>("/api/v1/prospects/search-nl", { query: nlQuery });
      if (data.success) {
        setNlResult(data);
        toast.success(`${data.db_matches?.length ?? 0} DB matches, ${data.web_results?.length ?? 0} web results`);
      } else toast.error(data.error ?? "NL search failed");
    } catch { toast.error("Natural-language search failed"); }
    setNlSearching(false);
  };

  const handleLookalike = async () => {
    setLookalikeLoading(true);
    setLookalikeResult(null);
    try {
      // const data = await http.post<any>("/api/v1/prospects/lookalike", {});
      const seed = allProspects[0];
    const data = await http.post<any>("/api/v1/prospects/lookalike", {
      seed_prospect_id: seed?.id ?? null,
    });
      if (data.success) {
        setLookalikeResult(data);
        toast.success(`Found ${data.lookalikes?.length ?? 0} lookalikes`);
      } else toast.error(data.error ?? "Lookalike search failed");
    } catch { toast.error("Lookalike search failed"); }
    setLookalikeLoading(false);
  };

  /* ── Bulk: Add to Campaign (PR-4) ── */
  const handleBulkAddToCampaign = async () => {
    if (!addToCampaignId || selectedIds.size === 0) return;
    try {
      const data = await http.post<any>(`/api/v1/campaigns/${addToCampaignId}/prospects`, {
        prospectIds: Array.from(selectedIds),
        action: "add",
      });
      toast.success(`${data.added ?? selectedIds.size} prospects added to campaign`);
      setAddToCampaignOpen(false);
      setSelectedIds(new Set());
      setAddToCampaignId("");
    } catch { toast.error("Failed to add to campaign"); }
  };

  /* ── Bulk: Validate Emails (PR-4) ── */
  const handleBulkValidate = async () => {
    const withEmail = Array.from(selectedIds)
      .map((id) => allProspects.find((p) => p.id === id))
      .filter((p): p is Prospect => !!p && !!p.email);
    if (withEmail.length === 0) { toast.error("Selected prospects have no emails"); return; }
    setValidatingAll(true);
    let valid = 0, invalid = 0;
    for (const p of withEmail) {
      try {
        const data = await http.post<any>("/api/v1/prospects/email-validate", { email: p.email });
        if (data.valid) valid++; else invalid++;
      } catch { /* skip */ }
    }
    toast.success(`Validated: ${valid} valid, ${invalid} invalid`);
    qc.invalidateQueries({ queryKey: ["prospects"] });
    setValidatingAll(false);
  };

  /* ── Helpers ── */
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => toast.success("Copied"));
  };

  const getSignalCount = (p: Prospect): number => {
    try {
      if (Array.isArray(p.signals)) return p.signals.length;
      if (typeof p.signals === "string") return JSON.parse(p.signals).length;
    } catch { /* ignore */ }
    return 0;
  };

  /* ── Loading state ── */
  const isLoading = prospectsQuery.isLoading;

  /* ═══════════════════════════════════════════ RENDER ═══════════════════════ */

  return (
    <div className="space-y-5">
      <PageHeader title="Prospects" description="Manage your target contacts, enrich data, and run AI intelligence tools." />

      {/* ══════════════ PR-1: AI PROSPECT SOURCING PANEL ══════════════ */}
      <Card className="border-violet-200 bg-gradient-to-r from-violet-50/80 to-purple-50/50">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-violet-100 flex items-center justify-center shrink-0">
                <Radar className="h-5 w-5 text-violet-700" />
              </div>
              <div>
                <CardTitle className="text-base">Multi-Source Prospect Discovery</CardTitle>
                <CardDescription className="text-xs">
                  Queries AI Web Search, LinkedIn, Apollo, Hunter, Lusha, Kaspr + all connected platforms in parallel
                </CardDescription>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="border-violet-300 text-violet-700 hover:bg-violet-50 shrink-0"
              onClick={() => { setSourcingOpen(!sourcingOpen); if (sourcingOpen) setSourceResult(null); }}
            >
              {sourcingOpen ? <ChevronUp className="h-4 w-4 mr-1" /> : <ChevronDown className="h-4 w-4 mr-1" />}
              {sourcingOpen ? "Hide" : "Auto-Discover Prospects"}
            </Button>
          </div>
        </CardHeader>

        {sourcingOpen && (
          <CardContent className="pt-0 space-y-4">
            {icps.length === 0 && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
                No ICP profiles yet. Create one in <b>ICP Profiles</b> first — the sourcing engine uses it to target the right personas.
              </p>
            )}
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1 space-y-1">
                <Label className="text-xs">ICP Profile *</Label>
                <Select value={sourceIcpId} onValueChange={setSourceIcpId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select ICP to source for…" />
                  </SelectTrigger>
                  <SelectContent>
                    {icps.map((icp) => (
                      <SelectItem key={icp.id} value={icp.id}>{icp.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end">
                <Button
                  onClick={handleSourceProspects}
                  disabled={sourcing || !sourceIcpId}
                  className="bg-violet-600 hover:bg-violet-700"
                >
                  {sourcing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Radar className="h-4 w-4 mr-2" />}
                  {sourcing ? "Discovering…" : "Discover Prospects"}
                </Button>
              </div>
            </div>

            {/* Source status chips */}
            {sourcing && !sourceResult && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" /> Querying all sources in parallel…
              </div>
            )}
            {sourceResult && (
              <div className="flex flex-wrap gap-1.5">
                {sourceResult.sources.map((s) => (
                  <span
                    key={s.source}
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border",
                      s.found > 0 ? (SOURCE_COLORS[s.source] ?? "bg-gray-100 text-gray-700") : "bg-gray-50 text-gray-400 border-gray-200"
                    )}
                  >
                    <span>{SOURCE_ICONS[s.source] ?? "🔍"}</span>
                    <span className="font-medium">{s.label}</span>
                    {s.error ? (
                      <span className="text-red-500" title={s.error}>✗</span>
                    ) : (
                      <span className="font-bold">{s.found}</span>
                    )}
                    {s.durationMs != null && (
                      <span className="opacity-60">{(s.durationMs / 1000).toFixed(1)}s</span>
                    )}
                  </span>
                ))}
              </div>
            )}

            {/* Sourcing results */}
            {sourceResult && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  <span className="text-muted-foreground">Sources: <b>{sourceResult.sources.length}</b></span>
                  <span className="text-muted-foreground">Total found: <b>{sourceResult.totalFromPlatforms}</b></span>
                  <span className="text-muted-foreground">After dedup: <b>{sourceResult.totalAfterDedup}</b></span>
                  <span className="text-emerald-600 font-medium">New: <b>{sourceResult.newProspects}</b></span>
                  {sourceResult.duplicatesFound > 0 && (
                    <span className="text-amber-600">Duplicates: <b>{sourceResult.duplicatesFound}</b></span>
                  )}
                </div>

                {sourceResult.prospects.length > 0 ? (
                  <ScrollArea className="max-h-64">
                    <div className="rounded-lg border overflow-hidden">
                      <table className="w-full text-xs">
                        <thead className="bg-muted/50 sticky top-0">
                          <tr>
                            <th className="text-left p-2 font-medium">Name</th>
                            <th className="text-left p-2 font-medium hidden sm:table-cell">Title</th>
                            <th className="text-left p-2 font-medium hidden md:table-cell">Company</th>
                            <th className="text-left p-2 font-medium">Source</th>
                            <th className="text-left p-2 font-medium">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sourceResult.prospects.map((p, i) => (
                            <tr key={i} className={cn("border-t", p._isDuplicate && "opacity-50 bg-muted/20")}>
                              <td className="p-2">
                                <div className="font-medium">{p.firstName} {p.lastName}</div>
                                <div className="text-muted-foreground">{p.email ?? p.domain}</div>
                              </td>
                              <td className="p-2 hidden sm:table-cell">{p.title ?? "—"}</td>
                              <td className="p-2 hidden md:table-cell">{p.company ?? "—"}</td>
                              <td className="p-2">
                                <Badge variant="outline" className={cn("text-[10px]", SOURCE_COLORS[p._source] ?? "")}>
                                  {SOURCE_ICONS[p._source] ?? "🔍"} {p._sourceLabel ?? p._source}
                                </Badge>
                              </td>
                              <td className="p-2">
                                {p._isDuplicate ? (
                                  <Badge variant="outline" className="text-[10px] bg-gray-100 text-gray-500">Duplicate</Badge>
                                ) : (
                                  <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200">New</Badge>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </ScrollArea>
                ) : (
                  <div className="text-center py-6 text-sm text-muted-foreground">
                    <Search className="h-8 w-8 mx-auto mb-2 opacity-40" />
                    No matches found. Try a different ICP or connect more platforms in Integrations.
                  </div>
                )}

                {sourceResult.prospects.some((p) => !p._isDuplicate && p.firstName) && (
                  <div className="flex justify-end">
                    <Button onClick={handleImportSourced} disabled={importingSourced}>
                      {importingSourced ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                      Import {sourceResult.prospects.filter((p) => !p._isDuplicate && p.firstName).length} Prospects
                    </Button>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* ══════════════ PR-2: INTELLIGENCE TOOLS PANEL ══════════════ */}
      <Card className="border-amber-200 bg-gradient-to-r from-amber-50/80 to-orange-50/50">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-amber-100 flex items-center justify-center shrink-0">
                <Sparkles className="h-5 w-5 text-amber-700" />
              </div>
              <div>
                <CardTitle className="text-base">Intelligence Tools</CardTitle>
                <CardDescription className="text-xs">Natural-language prospect search + lookalike discovery</CardDescription>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="border-amber-300 text-amber-700 hover:bg-amber-50 shrink-0"
              onClick={() => setIntelOpen(!intelOpen)}
            >
              {intelOpen ? <ChevronUp className="h-4 w-4 mr-1" /> : <ChevronDown className="h-4 w-4 mr-1" />}
              {intelOpen ? "Hide" : "Open Tools"}
            </Button>
          </div>
        </CardHeader>

        {intelOpen && (
          <CardContent className="pt-0 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* NL Search */}
              <div className="space-y-2">
                <Label className="text-xs font-semibold">Natural-Language Prospect Search</Label>
                <p className="text-[11px] text-muted-foreground">
                  Ask in plain English — AI parses into filters and matches against DB + web.
                </p>
                <div className="flex gap-2">
                  <Input
                    placeholder="e.g. Series B SaaS CTOs who raised in last 60 days"
                    value={nlQuery}
                    onChange={(e) => setNlQuery(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") handleNlSearch(); }}
                  />
                  <Button onClick={handleNlSearch} disabled={nlSearching} size="sm">
                    {nlSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  </Button>
                </div>
                {nlResult && (
                  <div className="mt-2 rounded-lg border bg-white p-3 space-y-3 text-xs">
                    {nlResult.interpretation && (
                      <div className="text-muted-foreground italic">{nlResult.interpretation}</div>
                    )}
                    {(nlResult.db_matches?.length ?? 0) > 0 && (
                      <div>
                        <p className="font-medium mb-1">DB Matches ({nlResult.db_matches!.length})</p>
                        <div className="space-y-1">
                          {nlResult.db_matches!.map((m, i) => (
                            <div key={i} className="flex items-center justify-between border rounded p-1.5">
                              <div>
                                <span className="font-medium">{m.name}</span>
                                {m.title && <span className="text-muted-foreground"> — {m.title}</span>}
                                {m.company && <span className="text-muted-foreground"> @ {m.company}</span>}
                              </div>
                              {m.icp_score != null && (
                                <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700">{m.icp_score}</Badge>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {(nlResult.web_results?.length ?? 0) > 0 && (
                      <div>
                        <p className="font-medium mb-1">Web Results ({nlResult.web_results!.length})</p>
                        <div className="space-y-1">
                          {nlResult.web_results!.slice(0, 3).map((r, i) => (
                            <div key={i} className="border rounded p-1.5">
                              <a href={r.url} target="_blank" rel="noreferrer" className="font-medium text-blue-600 hover:underline line-clamp-1">{r.title}</a>
                              <p className="text-muted-foreground line-clamp-1">{r.snippet}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Lookalike */}
              <div className="space-y-2">
                <Label className="text-xs font-semibold">Find Lookalike Companies</Label>
                <p className="text-[11px] text-muted-foreground">
                  Seeds from your best closed-won deal and ranks similar prospects by firmographic overlap.
                </p>
                <Button
                  onClick={handleLookalike}
                  disabled={lookalikeLoading}
                  variant="outline"
                  size="sm"
                  className="border-amber-300 text-amber-700 hover:bg-amber-50"
                >
                  {lookalikeLoading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <UserSearch className="h-4 w-4 mr-2" />}
                  Find Lookalikes
                </Button>
                {lookalikeResult && (lookalikeResult.lookalikes?.length ?? 0) > 0 && (
                  <ScrollArea className="max-h-52 mt-2">
                    <div className="space-y-1">
                      {lookalikeResult.lookalikes!.map((l, i) => (
                        <div key={i} className="border rounded-lg p-2 flex items-center gap-2 bg-white text-xs">
                          <div className="flex-1">
                            <div className="font-medium">{l.name ?? "—"}</div>
                            <div className="text-muted-foreground">{l.title} {l.company && `@ ${l.company}`}</div>
                            {(l.matched_features?.length ?? 0) > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1">
                                {l.matched_features!.map((f, j) => <Badge key={j} variant="outline" className="text-[10px]">{f}</Badge>)}
                              </div>
                            )}
                          </div>
                          {l.similarity_score != null && (
                            <div className="text-right shrink-0">
                              <div className="text-base font-bold text-amber-600">{Math.round(l.similarity_score * 100)}%</div>
                              <div className="text-[10px] text-muted-foreground">similarity</div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* ══════════════ TOOLBAR ══════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        {/* Search (PR-18) */}
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Search name, email, company…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Seniority filter (PR-18) */}
        <Select value={seniorityFilter} onValueChange={setSeniorityFilter}>
          <SelectTrigger className="w-36">
            <Filter className="h-4 w-4 mr-1 text-muted-foreground" />
            <SelectValue placeholder="Seniority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Seniority</SelectItem>
            <SelectItem value="C_Suite">C-Suite</SelectItem>
            <SelectItem value="Director">Director</SelectItem>
            <SelectItem value="IC">IC</SelectItem>
          </SelectContent>
        </Select>

        {/* Score filter (PR-18) */}
        <Select
          value={String(scoreMin)}
          onValueChange={(v) => setScoreMin(Number(v))}
        >
          <SelectTrigger className="w-36">
            <Star className="h-4 w-4 mr-1 text-muted-foreground" />
            <SelectValue placeholder="Min Score" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">All Scores</SelectItem>
            <SelectItem value="40">≥ 40</SelectItem>
            <SelectItem value="60">≥ 60 (P1+)</SelectItem>
            <SelectItem value="80">≥ 80 (P0)</SelectItem>
          </SelectContent>
        </Select>

        <Separator orientation="vertical" className="h-8 hidden sm:block" />

        {/* PR-6: Validate All */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              onClick={handleValidateAll}
              disabled={validatingAll || allProspects.length === 0}
            >
              {validatingAll ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <MailCheck className="h-4 w-4 mr-1" />}
              Validate All
            </Button>
          </TooltipTrigger>
          <TooltipContent>Validate MX records for all prospect emails</TooltipContent>
        </Tooltip>

        {/* PR-7: Export CSV */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="sm" onClick={handleExport} disabled={allProspects.length === 0}>
              <FileDown className="h-4 w-4 mr-1" /> Export CSV
            </Button>
          </TooltipTrigger>
          <TooltipContent>Download all prospects as CSV</TooltipContent>
        </Tooltip>

        {/* PR-5: Import CSV */}
        <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}>
          <Upload className="h-4 w-4 mr-1" /> Import CSV
        </Button>

        {/* Add Prospect */}
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Add Prospect
        </Button>
      </div>

      {/* ══════════════ PROSPECT TABLE ══════════════ */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No Prospects"
          description={allProspects.length === 0
            ? "Use Auto-Discover above to source prospects, or add them manually."
            : "No prospects match your current filters."}
        />
      ) : (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40">
                  {/* PR-4: Bulk select */}
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === filtered.length && filtered.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded"
                      aria-label="Select all"
                    />
                  </TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead className="hidden sm:table-cell">Company</TableHead>
                  <TableHead className="hidden md:table-cell">Title</TableHead>
                  <TableHead>Seniority</TableHead>
                  {/* PR-17: Intent */}
                  <TableHead className="hidden xl:table-cell">Intent</TableHead>
                  {/* PR-16: Email + validation */}
                  <TableHead>Email</TableHead>
                  {/* PR-8: Score */}
                  <TableHead className="hidden lg:table-cell">Score</TableHead>
                  <TableHead>Status</TableHead>
                  {/* PR-3: Row actions */}
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((p) => {
                  const signalCount = getSignalCount(p);
                  const urgencyMeta = p.urgencyTier ? URGENCY_META[p.urgencyTier] : null;

                  return (
                    <TableRow
                      key={p.id}
                      className={cn("hover:bg-muted/20", selectedIds.has(p.id) && "bg-primary/5")}
                    >
                      {/* Select */}
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(p.id)}
                          onChange={() => toggleSelect(p.id)}
                          className="rounded"
                        />
                      </TableCell>

                      {/* Name */}
                      <TableCell>
                        <div>
                          <p className="font-medium text-sm">{p.firstName} {p.lastName}</p>
                          {p.domain && <p className="text-xs text-muted-foreground">{p.domain}</p>}
                        </div>
                      </TableCell>

                      <TableCell className="hidden sm:table-cell text-sm">{p.company ?? "—"}</TableCell>
                      <TableCell className="hidden md:table-cell text-sm">{p.title ?? "—"}</TableCell>

                      {/* Seniority */}
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {p.seniority === "C_Suite" ? "C-Suite" : p.seniority}
                        </Badge>
                      </TableCell>

                      {/* PR-17: Intent Source + Strength */}
                      <TableCell className="hidden xl:table-cell">
                        {p.intentSource && p.intentSource !== "OTHER" ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Badge
                                variant="outline"
                                className={cn("text-[10px] cursor-help", INTENT_COLORS[p.intentSource] ?? "bg-gray-50 text-gray-600")}
                              >
                                {p.intentSource.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}
                                {p.intentStrength != null && ` · ${p.intentStrength}`}
                              </Badge>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-xs text-xs">
                              {p.intentDetail ?? p.intentSource}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>

                      {/* PR-16: Email validation badge */}
                      <TableCell>
                        {p.email ? (
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs truncate max-w-[130px]">{p.email}</span>
                            {p.emailValidated ? (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200 shrink-0">
                                    <MailCheck className="h-2.5 w-2.5 mr-0.5" /> Valid
                                  </Badge>
                                </TooltipTrigger>
                                <TooltipContent>Email validated{p.isCatchAll ? " (catch-all domain)" : ""}</TooltipContent>
                              </Tooltip>
                            ) : p.emailValidationDetail ? (
                              <Badge variant="outline" className="text-[10px] bg-red-50 text-red-700 border-red-200 shrink-0">
                                <ShieldAlert className="h-2.5 w-2.5 mr-0.5" /> Invalid
                              </Badge>
                            ) : p.isCatchAll ? (
                              <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-700 border-amber-200 shrink-0">
                                Catch-all
                              </Badge>
                            ) : (
                              <span className="text-[10px] text-muted-foreground shrink-0">Unverified</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>

                      {/* PR-8: ICP Fit Score + Urgency Tier */}
                      <TableCell className="hidden lg:table-cell">
                        {p.icpFitScore != null ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div className="flex items-center gap-1.5 cursor-help">
                                <Progress value={p.icpFitScore} className="h-1.5 w-12" />
                                <span className="text-xs font-semibold">{p.icpFitScore}</span>
                                {urgencyMeta && (
                                  <Badge
                                    variant="outline"
                                    className={cn("text-[10px]", urgencyMeta.bg, urgencyMeta.text, urgencyMeta.border)}
                                  >
                                    {p.urgencyTier}
                                  </Badge>
                                )}
                              </div>
                            </TooltipTrigger>
                            <TooltipContent side="top">
                              <p className="font-semibold">ICP Fit: {p.icpFitScore}/100</p>
                              {urgencyMeta && <p className="text-xs">{urgencyMeta.label}</p>}
                              {p.icpPersona && <p className="text-xs text-muted-foreground mt-1">{p.icpPersona}</p>}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>

                      {/* Status */}
                      <TableCell>
                        <span className={cn("text-xs px-2 py-1 rounded-full", STATUS_COLORS[p.status] ?? "bg-gray-100 text-gray-600")}>
                          {p.status}
                        </span>
                      </TableCell>

                      {/* PR-3: Row action buttons */}
                      <TableCell>
                        <div className="flex gap-1 flex-wrap">
                          {/* Validate Email */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="outline"
                                className="h-7 w-7 p-0"
                                onClick={() => handleValidateEmail(p)}
                                disabled={validatingId === p.id || !p.email}
                              >
                                {validatingId === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <MailCheck className="h-3 w-3" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Validate email</TooltipContent>
                          </Tooltip>

                          {/* Research Signals (PR-15) */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="outline"
                                className="h-7 px-1.5 text-xs"
                                onClick={() => handleResearchSignals(p)}
                                disabled={researchingId === p.id}
                              >
                                {researchingId === p.id ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <>
                                    <Search className="h-3 w-3" />
                                    {signalCount > 0 && <span className="ml-0.5">{signalCount}</span>}
                                  </>
                                )}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Research 90-day buying signals</TooltipContent>
                          </Tooltip>

                          {/* Enrich */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="outline"
                                className="h-7 px-1.5 text-xs"
                                onClick={() => handleEnrich(p)}
                                disabled={enrichingId === p.id}
                              >
                                {enrichingId === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Enrich via Apollo / Clearbit / Hunter</TooltipContent>
                          </Tooltip>

                          {/* Domain Enrich */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="outline"
                                className="h-7 px-1.5 text-xs"
                                onClick={() => handleDomainEnrich(p)}
                                disabled={domainEnrichingId === p.id || (!p.domain && !p.company)}
                              >
                                {domainEnrichingId === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Globe className="h-3 w-3" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Domain intelligence (website + news scrape)</TooltipContent>
                          </Tooltip>

                          {/* Competitor Radar */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="outline"
                                className="h-7 px-1.5 text-xs"
                                onClick={() => handleCompetitorRadar(p)}
                                disabled={competitorLoadingId === p.id || (!p.company && !p.domain)}
                              >
                                {competitorLoadingId === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Radar className="h-3 w-3" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Competitor Radar — research competitors via web + AI</TooltipContent>
                          </Tooltip>

                          {/* Ultimate Profile */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="outline"
                                className="h-7 px-1.5 text-xs"
                                onClick={() => handleUltimateProfile(p)}
                                disabled={profileLoadingId === p.id || (!p.company && !p.domain)}
                              >
                                {profileLoadingId === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Brain className="h-3 w-3" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Ultimate Business Profile — deep AI research</TooltipContent>
                          </Tooltip>

                          {/* Hook Generator */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="outline"
                                className="h-7 px-1.5 text-xs"
                                onClick={() => handleHookGen(p)}
                                disabled={hookLoadingId === p.id}
                              >
                                {hookLoadingId === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <ZapIcon className="h-3 w-3" />}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Generate 5 personalized opener hooks</TooltipContent>
                          </Tooltip>

                          {/* Log Call */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="outline"
                                className="h-7 w-7 p-0"
                                onClick={() => openCallLog(p)}
                              >
                                <Phone className="h-3 w-3" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Log a call</TooltipContent>
                          </Tooltip>

                          {/* Delete */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm" variant="ghost"
                                className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                                onClick={() => setDeleteTarget(p)}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Delete prospect</TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

            <div className="px-4 py-2 text-xs text-muted-foreground border-t">
              Showing {filtered.length} of {allProspects.length} prospects
            </div>
          </CardContent>
        </Card>
      )}

      {/* ══════════════ PR-10: DOMAIN ENRICHMENT INLINE RESULTS ══════════════ */}
      {Object.keys(domainEnrichResults).length > 0 && (
        <Card className="border-violet-200 bg-violet-50/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Globe className="h-4 w-4 text-violet-600" />
              Domain Enrichment Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(domainEnrichResults).map(([pid, enrich]) => {
              if (!enrich) return null;
              const p = allProspects.find((pr) => pr.id === pid);
              return (
                <div key={pid} className="bg-white rounded-lg border p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium">{p ? `${p.firstName} ${p.lastName} — ${p.company}` : pid}</p>
                    <Button
                      variant="ghost" size="sm" className="h-6 w-6 p-0"
                      onClick={() => setDomainEnrichResults((prev) => { const n = { ...prev }; delete n[pid]; return n; })}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    {enrich.industry && <div className="bg-muted/50 rounded p-2"><p className="text-[10px] text-muted-foreground">Industry</p><p className="font-medium">{enrich.industry}</p></div>}
                    {enrich.company_size && <div className="bg-muted/50 rounded p-2"><p className="text-[10px] text-muted-foreground">Size</p><p className="font-medium">{enrich.company_size}</p></div>}
                    {enrich.icp_fit_score != null && <div className="bg-muted/50 rounded p-2"><p className="text-[10px] text-muted-foreground">ICP Fit</p><p className="font-medium">{enrich.icp_fit_score}/100</p></div>}
                  </div>
                  {enrich.tech_stack?.length > 0 && (
                    <div>
                      <p className="text-[10px] font-medium text-muted-foreground mb-1">Tech Stack</p>
                      <div className="flex flex-wrap gap-1">{enrich.tech_stack.map((t: string, i: number) => <Badge key={i} variant="secondary" className="text-[10px]">{t}</Badge>)}</div>
                    </div>
                  )}
                  {enrich.pain_points?.length > 0 && (
                    <div>
                      <p className="text-[10px] font-medium text-muted-foreground mb-1">Pain Points</p>
                      <div className="flex flex-wrap gap-1">{enrich.pain_points.map((pp: string, i: number) => <Badge key={i} variant="outline" className="text-[10px] border-amber-200 text-amber-700">{pp}</Badge>)}</div>
                    </div>
                  )}
                  {enrich.buying_signals?.length > 0 && (
                    <div>
                      <p className="text-[10px] font-medium text-muted-foreground mb-1">Buying Signals</p>
                      <div className="flex flex-wrap gap-1">{enrich.buying_signals.map((bs: string, i: number) => <Badge key={i} className="text-[10px] bg-emerald-100 text-emerald-700">{bs}</Badge>)}</div>
                    </div>
                  )}
                  {enrich.recommended_angle && (
                    <p className="text-xs italic text-muted-foreground bg-muted/50 rounded p-2">
                      Angle: {enrich.recommended_angle}
                    </p>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* ══════════════ PR-4: BULK ACTION BAR ══════════════ */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-3 rounded-xl bg-card border shadow-xl">
          <span className="text-sm font-medium">{selectedIds.size} selected</span>
          <Button size="sm" onClick={() => setAddToCampaignOpen(true)}>
            <Users className="h-3 w-3 mr-1" /> Add to Campaign
          </Button>
          <Button size="sm" variant="outline" onClick={handleBulkValidate} disabled={validatingAll}>
            {validatingAll ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <MailCheck className="h-3 w-3 mr-1" />}
            Validate Emails
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
            <X className="h-3 w-3 mr-1" /> Clear
          </Button>
        </div>
      )}

      {/* ════════════════ DIALOGS ════════════════ */}

      {/* PR-9: Add Prospect */}
      <Dialog open={addOpen} onOpenChange={(o) => { setAddOpen(o); if (!o) resetAddForm(); }}>
        <DialogHeader>
          <DialogTitle>Add Prospect</DialogTitle>
          <DialogDescription>Fill in prospect details. Fields marked * are required.</DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[70vh]">
          <div className="space-y-4 py-4 px-1">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">First Name *</Label>
                <Input value={addForm.firstName} onChange={(e) => setAddForm((f) => ({ ...f, firstName: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Last Name *</Label>
                <Input value={addForm.lastName} onChange={(e) => setAddForm((f) => ({ ...f, lastName: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Email</Label>
                <Input type="email" value={addForm.email} onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Phone</Label>
                <Input placeholder="+1 555 000 0000" value={addForm.phone} onChange={(e) => setAddForm((f) => ({ ...f, phone: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Title</Label>
                <Input placeholder="VP Engineering" value={addForm.title} onChange={(e) => setAddForm((f) => ({ ...f, title: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Company</Label>
                <Input value={addForm.company} onChange={(e) => setAddForm((f) => ({ ...f, company: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Domain</Label>
                <Input placeholder="acme.com" value={addForm.domain} onChange={(e) => setAddForm((f) => ({ ...f, domain: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">LinkedIn URL</Label>
                <Input placeholder="linkedin.com/in/…" value={addForm.linkedinUrl} onChange={(e) => setAddForm((f) => ({ ...f, linkedinUrl: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs">Seniority</Label>
                <Select value={addForm.seniority} onValueChange={(v) => setAddForm((f) => ({ ...f, seniority: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="C_Suite">C-Suite</SelectItem>
                    <SelectItem value="Director">Director</SelectItem>
                    <SelectItem value="IC">Individual Contributor</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {icps.length > 0 && (
                <div className="space-y-1">
                  <Label className="text-xs">ICP Profile</Label>
                  <Select value={addForm.icpProfileId} onValueChange={(v) => setAddForm((f) => ({ ...f, icpProfileId: v }))}>
                    <SelectTrigger><SelectValue placeholder="Select ICP…" /></SelectTrigger>
                    <SelectContent>
                      {icps.map((icp) => <SelectItem key={icp.id} value={icp.id}>{icp.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Notes</Label>
              <Textarea
                rows={2}
                placeholder="Source, context, or any other notes…"
                value={addForm.notes}
                onChange={(e) => setAddForm((f) => ({ ...f, notes: e.target.value }))}
              />
            </div>
          </div>
        </ScrollArea>
        <DialogFooter>
          <DialogClose onClick={() => { setAddOpen(false); resetAddForm(); }}>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button
            onClick={() => {
              if (!addForm.firstName.trim() || !addForm.lastName.trim()) {
                toast.error("First name and last name are required");
                return;
              }
              addMutation.mutate({
                firstName: addForm.firstName,
                lastName: addForm.lastName,
                email: addForm.email || null,
                title: addForm.title || null,
                company: addForm.company || null,
                domain: addForm.domain || null,
                linkedinUrl: addForm.linkedinUrl || null,
                phone: addForm.phone || null,
                seniority: addForm.seniority,
                icpProfileId: addForm.icpProfileId || null,
                notes: addForm.notes || null,
              });
            }}
            disabled={addMutation.isPending}
          >
            {addMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Add Prospect
          </Button>
        </DialogFooter>
      </Dialog>

      {/* PR-5: CSV Import */}
      <Dialog open={importOpen} onOpenChange={(o) => { setImportOpen(o); if (!o) setCsvResult(null); }}>
        <DialogHeader>
          <DialogTitle>Bulk CSV Import</DialogTitle>
          <DialogDescription>
            Supported columns: first_name, last_name, email, title, company, domain, linkedin, seniority, phone, notes
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div
            className="border-2 border-dashed border-border rounded-lg p-10 text-center relative cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => csvInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files[0];
              if (file) handleCsvUpload(file);
            }}
          >
            <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
            <p className="text-sm font-medium">Drop your CSV here or click to browse</p>
            <p className="text-xs text-muted-foreground mt-1">Max 10 MB · UTF-8 encoding</p>
            <input
              ref={csvInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleCsvUpload(f); }}
            />
          </div>

          {csvImporting && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Importing…
            </div>
          )}

          {csvResult && (
            <Card className={cn("border", csvResult.errors.length > 0 ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50")}>
              <CardContent className="p-3 text-sm">
                <p className="font-medium mb-1">Import Complete</p>
                <p>Imported: <b>{csvResult.imported}</b> · Skipped: <b>{csvResult.skipped}</b> · Total rows: <b>{csvResult.totalRows}</b></p>
                {csvResult.errors.length > 0 && (
                  <div className="mt-2 text-xs text-amber-800">
                    <p className="font-medium">{csvResult.errors.length} row error(s):</p>
                    <ul className="list-disc list-inside mt-1 space-y-0.5">
                      {csvResult.errors.slice(0, 5).map((e, i) => <li key={i}>{e}</li>)}
                      {csvResult.errors.length > 5 && <li>…and {csvResult.errors.length - 5} more</li>}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <div className="text-xs text-muted-foreground bg-muted rounded-lg p-3">
            <p className="font-medium mb-1">Example CSV format:</p>
            <pre className="font-mono text-[10px] whitespace-pre-wrap">first_name,last_name,email,title,company,domain
John,Smith,john@acme.com,VP Engineering,Acme Inc,acme.com</pre>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setImportOpen(false)}>Close</Button>
        </DialogFooter>
      </Dialog>

      {/* PR-4: Add to Campaign */}
      <Dialog open={addToCampaignOpen} onOpenChange={setAddToCampaignOpen}>
        <DialogHeader>
          <DialogTitle>Add to Campaign</DialogTitle>
          <DialogDescription>Select a campaign to add {selectedIds.size} prospect{selectedIds.size !== 1 ? "s" : ""} to.</DialogDescription>
        </DialogHeader>
        <div className="py-4 space-y-2">
          <Label className="text-xs">Campaign</Label>
          <Select value={addToCampaignId} onValueChange={setAddToCampaignId}>
            <SelectTrigger><SelectValue placeholder="Select campaign…" /></SelectTrigger>
            <SelectContent>
              {campaigns.map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {campaigns.length === 0 && (
            <p className="text-xs text-muted-foreground">No campaigns yet. Create one first.</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setAddToCampaignOpen(false)}>Cancel</Button>
          <Button onClick={handleBulkAddToCampaign} disabled={!addToCampaignId}>
            Add {selectedIds.size} Prospects
          </Button>
        </DialogFooter>
      </Dialog>

      {/* PR-11: Call Log */}
      <Dialog open={callLogProspect !== null} onOpenChange={(o) => { if (!o) setCallLogProspect(null); }}>
        <DialogHeader>
          <DialogTitle>Log Call</DialogTitle>
          <DialogDescription>
            {callLogProspect && `${callLogProspect.firstName} ${callLogProspect.lastName}${callLogProspect.company ? ` — ${callLogProspect.company}` : ""}`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-3">
          <div className="space-y-1">
            <Label className="text-xs">Phone *</Label>
            <Input placeholder="+1 555 000 0000" value={callLogForm.phone} onChange={(e) => setCallLogForm((f) => ({ ...f, phone: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Outcome</Label>
            <Select value={callLogForm.outcome} onValueChange={(v) => setCallLogForm((f) => ({ ...f, outcome: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="connected">Connected</SelectItem>
                <SelectItem value="voicemail">Voicemail</SelectItem>
                <SelectItem value="no_answer">No Answer</SelectItem>
                <SelectItem value="busy">Busy</SelectItem>
                <SelectItem value="wrong_number">Wrong Number</SelectItem>
                <SelectItem value="scheduled">Scheduled Follow-up</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Duration (seconds)</Label>
            <Input type="number" min="0" placeholder="e.g. 180" value={callLogForm.durationSec} onChange={(e) => setCallLogForm((f) => ({ ...f, durationSec: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Notes</Label>
            <Textarea rows={3} placeholder="Conversation summary, next steps…" value={callLogForm.notes} onChange={(e) => setCallLogForm((f) => ({ ...f, notes: e.target.value }))} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setCallLogProspect(null)}>Cancel</Button>
          <Button onClick={handleLogCall} disabled={callLogSaving}>
            {callLogSaving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Phone className="h-4 w-4 mr-2" />}
            Log Call
          </Button>
        </DialogFooter>
      </Dialog>

      {/* PR-12: Competitor Radar */}
      <Dialog open={competitorResult !== null} onOpenChange={(o) => { if (!o) setCompetitorResult(null); }}>
        <DialogHeader>
          <DialogTitle>Competitor Radar — {competitorResult?.prospect.company}</DialogTitle>
          <DialogDescription>
            {competitorResult?.competitors.length ?? 0} competitors identified via web search + AI
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh] pr-2">
          {(competitorResult?.competitors.length ?? 0) > 0 ? (
            <div className="space-y-2 py-2">
              {competitorResult!.competitors.map((c, i) => (
                <div key={i} className="border rounded-lg p-3 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <p className="text-sm font-medium">
                        {c.name}
                        {c.domain && (
                          <a href={`https://${c.domain}`} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-xs ml-1.5">↗</a>
                        )}
                      </p>
                      {c.description && <p className="text-xs text-muted-foreground mt-0.5">{c.description}</p>}
                      {c.positioning && <p className="text-xs mt-1"><span className="font-medium">Positioning:</span> {c.positioning}</p>}
                    </div>
                    {c.overlap_score != null && (
                      <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-700 border-amber-200 shrink-0">
                        {Math.round(c.overlap_score * 100)}% overlap
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">No competitors found.</p>
          )}
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" onClick={() => setCompetitorResult(null)}>Close</Button>
        </DialogFooter>
      </Dialog>

      {/* PR-13: Ultimate Profile */}
      <Dialog open={profileResult !== null} onOpenChange={(o) => { if (!o) setProfileResult(null); }}>
        <DialogHeader>
          <DialogTitle>Ultimate Business Profile — {profileResult?.prospect.company}</DialogTitle>
          <DialogDescription>
            {profileResult?.sourcesAnalyzed} web sources analyzed
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[65vh] pr-2">
          {profileResult?.profile && (
            <div className="space-y-3 py-2">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {profileResult.profile.industry && <div className="bg-muted/50 rounded p-2"><p className="text-[10px] text-muted-foreground">Industry</p><p className="text-xs font-medium">{profileResult.profile.industry}</p></div>}
                {profileResult.profile.company_size && <div className="bg-muted/50 rounded p-2"><p className="text-[10px] text-muted-foreground">Size</p><p className="text-xs font-medium">{profileResult.profile.company_size}</p></div>}
                {profileResult.profile.icp_fit_score != null && <div className="bg-muted/50 rounded p-2"><p className="text-[10px] text-muted-foreground">ICP Fit</p><p className="text-xs font-medium">{profileResult.profile.icp_fit_score}/100</p></div>}
                {profileResult.profile.confidence_score != null && <div className="bg-muted/50 rounded p-2"><p className="text-[10px] text-muted-foreground">Confidence</p><p className="text-xs font-medium">{Math.round(profileResult.profile.confidence_score * 100)}%</p></div>}
              </div>
              {profileResult.profile.what_they_do && <div><p className="text-xs font-medium mb-0.5">What They Do</p><p className="text-xs text-muted-foreground">{profileResult.profile.what_they_do}</p></div>}
              {profileResult.profile.target_market && <div><p className="text-xs font-medium mb-0.5">Target Market</p><p className="text-xs text-muted-foreground">{profileResult.profile.target_market}</p></div>}
              {(profileResult.profile.tech_stack?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs font-medium mb-1">Tech Stack</p>
                  <div className="flex flex-wrap gap-1">{profileResult.profile.tech_stack!.map((t, i) => <Badge key={i} variant="outline" className="text-[10px]">{t}</Badge>)}</div>
                </div>
              )}
              {(profileResult.profile.pain_points?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs font-medium mb-1">Pain Points</p>
                  <div className="flex flex-wrap gap-1">{profileResult.profile.pain_points!.map((pp, i) => <Badge key={i} variant="outline" className="text-[10px] border-amber-200 text-amber-700">{pp}</Badge>)}</div>
                </div>
              )}
              {(profileResult.profile.buying_signals?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs font-medium mb-1">Buying Signals</p>
                  <div className="flex flex-wrap gap-1">{profileResult.profile.buying_signals!.map((s, i) => <Badge key={i} className="text-[10px] bg-emerald-100 text-emerald-700">{s}</Badge>)}</div>
                </div>
              )}
              {profileResult.profile.recommended_angle && (
                <Card className="bg-violet-50 border-violet-200">
                  <CardContent className="p-3">
                    <p className="text-[10px] text-muted-foreground">Recommended Outreach Angle</p>
                    <p className="text-xs font-medium mt-0.5">{profileResult.profile.recommended_angle}</p>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" onClick={() => setProfileResult(null)}>Close</Button>
        </DialogFooter>
      </Dialog>

      {/* PR-14: Hook Generator */}
      <Dialog open={hookResult !== null} onOpenChange={(o) => { if (!o) setHookResult(null); }}>
        <DialogHeader>
          <DialogTitle>Opener Hooks</DialogTitle>
          <DialogDescription>
            {hookResult && `5 personalized hooks for ${hookResult.prospect.firstName} ${hookResult.prospect.lastName}`}
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh] pr-2">
          {(hookResult?.hooks.length ?? 0) > 0 ? (
            <div className="space-y-2 py-2">
              {hookResult!.hooks.map((hook, i) => (
                <HookCard key={i} hook={hook} index={i + 1} onCopy={copyToClipboard} />
              ))}
              <Button
                variant="outline"
                className="w-full mt-2"
                onClick={() => copyToClipboard(hookResult!.hooks.map((h, i) => `${i + 1}. ${h.text}`).join("\n"))}
              >
                <Copy className="h-4 w-4 mr-2" /> Copy All
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">No hooks generated.</p>
          )}
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" onClick={() => setHookResult(null)}>Close</Button>
        </DialogFooter>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={deleteTarget !== null} onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete prospect?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget && `${deleteTarget.firstName} ${deleteTarget.lastName}${deleteTarget.company ? ` (${deleteTarget.company})` : ""} will be permanently removed.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive hover:bg-destructive/90"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/* ── Hook Card sub-component (PR-14) ───────────────────────────────── */

function HookCard({
  hook,
  index,
  onCopy,
}: {
  hook: HookEntry;
  index: number;
  onCopy: (text: string) => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!hook.text) return;
    onCopy(hook.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-muted-foreground">#{index}</span>
            {hook.type && <Badge variant="outline" className="text-[10px]">{hook.type}</Badge>}
          </div>
          <p className="text-sm">{hook.text ?? "—"}</p>
        </div>
        <Button size="sm" variant="ghost" className="h-7 w-7 p-0 shrink-0" onClick={handleCopy} disabled={!hook.text}>
          {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
        </Button>
      </div>
    </div>
  );
}