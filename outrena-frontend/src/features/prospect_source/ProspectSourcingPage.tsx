/**
 * ProspectSourcingPage.tsx — Prospect sourcing toolkit.
 *
 * 5 tabs:
 *  - Source Configs: table of {source, apiKey masked, isActive, dailyLimit} + edit
 *  - Natural Language Search: NL query → prospect results table
 *  - Lookalike: pick seed prospect → similar prospects table
 *  - Ultimate Profile: input prospect → enriched profile card
 *  - Prospect Brief: input prospect → 1-page brief
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Database,
  Search,
  Shuffle,
  Sparkles,
  FileText,
  Plus,
  Pencil,
  Loader2,
  Save,
  Trash2,
  KeyRound,
  Power,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatPercent, truncate, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InfoLabel } from "@/components/ui/info-label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";

/* ── Types ─────────────────────────────────────────────────────────── */

interface SourceConfig {
  id: string;
  source: string;
  name: string;
  apiKeyMasked: string;
  apiKey?: string;
  isActive: boolean;
  dailyLimit: number;
  usedToday: number;
}

interface SourcedProspect {
  id: string;
  name: string;
  title: string;
  company: string;
  email: string | null;
  linkedinUrl: string | null;
  icpScore: number;
  reason: string;
}

interface UltimateProfile {
  prospectName: string;
  company: string;
  title: string;
  bio: string;
  experienceYears: number;
  education: string[];
  skills: string[];
  recentActivity: string[];
  techStack: string[];
  icpFitScore: number;
}

interface ProspectBrief {
  prospectName: string;
  company: string;
  summary: string;
  painPoints: string[];
  whyNow: string[];
  openingHooks: string[];
  talkTrack: string;
}

/* ── Mock data ─────────────────────────────────────────────────────── */

// const MOCK_CONFIGS: SourceConfig[] = [
//   { id: "c1", source: "Apollo", name: "Apollo", apiKeyMasked: "apo_••••••3F9a", isActive: true, dailyLimit: 500, usedToday: 142 },
//   { id: "c2", source: "Clearbit", name: "Clearbit", apiKeyMasked: "sk_••••••b21Z", isActive: true, dailyLimit: 1000, usedToday: 312 },
//   { id: "c3", source: "LinkedIn Sales Navigator", name: "LinkedIn Sales Navigator", apiKeyMasked: "cookie_••••8c4d", isActive: false, dailyLimit: 200, usedToday: 0 },
//   { id: "c4", source: "Crunchbase", name: "Crunchbase", apiKeyMasked: "cb_••••••f7A2", isActive: true, dailyLimit: 250, usedToday: 87 },
// ];

// const MOCK_NL_RESULTS: SourcedProspect[] = [
//   mkSP("sp1", "Priya Shankar", "VP Sales", "Ledgerline", "priya@ledgerline.io", 0.92, "Series B fintech, hiring SDRs"),
//   mkSP("sp2", "Marcus Reuel", "VP RevOps", "Vaultnode", "marcus@vaultnode.com", 0.88, "Series B, uses Salesforce"),
//   mkSP("sp3", "Elena Voss", "Head of Sales", "Northbridge Pay", "elena@northbridgepay.com", 0.86, "Series B fintech"),
//   mkSP("sp4", "Daniel Okoro", "VP Sales", "Quartz Pay", "daniel@quartzpay.com", 0.83, "Series B, just raised"),
//   mkSP("sp5", "Asha Patel", "CMO", "LumenKart", "asha@lumenkart.com", 0.74, "Fintech-adjacent, growing team"),
// ];

// const MOCK_LOOKALIKE_RESULTS: SourcedProspect[] = [
//   mkSP("la1", "Renee Coleman", "VP Sales", "Nexbridge", "renee@nexbridge.io", 0.89, "Similar company stage + role"),
//   mkSP("la2", "Tobias Klein", "Head of Sales", "Helios Pay", "tobias@heliospay.com", 0.85, "Same ICP signals"),
//   mkSP("la3", "Mara Costa", "VP RevOps", "Pulseflow", "mara@pulseflow.io", 0.82, "Similar tech stack"),
//   mkSP("la4", "Hiro Tanaka", "VP Sales", "Meshgrid", "hiro@meshgrid.dev", 0.80, "Same funding stage"),
// ];

// const MOCK_ULTIMATE: UltimateProfile = {
//   prospectName: "Priya Shankar",
//   company: "Ledgerline",
//   title: "VP Sales",
//   bio: "Sales leader with 12+ years scaling B2B SaaS go-to-market teams at Series A–C fintech and developer-tool companies. Currently leading 14 SDRs/AEs at Ledgerline (Series B, $35M raise).",
//   experienceYears: 12,
//   education: ["MBA, Wharton", "BS Computer Science, UC Berkeley"],
//   skills: ["Salesforce", "Outreach", "Gong", "Sales Navigator", "Forecasting", "SDR enablement"],
//   recentActivity: [
//     "Posted about SDR ramp on LinkedIn (3d ago)",
//     "Hiring 2 SDRs (1w ago)",
//     "Speaking at SaaStr Annual (next month)",
//   ],
//   techStack: ["Salesforce", "Outreach", "Gong", "6sense", "LinkedIn Sales Navigator"],
//   icpFitScore: 0.92,
// };

// const MOCK_BRIEF: ProspectBrief = {
//   prospectName: "Priya Shankar",
//   company: "Ledgerline",
//   summary:
//     "Priya is a seasoned VP Sales at a Series B fintech. She's hiring SDRs and recently vented on LinkedIn about how slow ramp kills pipeline coverage. OUTRENA's value prop (cut SDR ramp 40% via auto-enrichment) aligns directly with her current pain.",
//   painPoints: [
//     "SDR ramp time exceeds 4 months",
//     "Salesforce data quality issues causing missed SLAs",
//     "Pipeline coverage running at 2.1x (under 3x target)",
//   ],
//   whyNow: [
//     "Just raised $35M Series B (8 weeks ago)",
//     "Active SDR hiring (2 open reqs)",
//     "Public LinkedIn posts about ramp pain",
//   ],
//   openingHooks: [
//     "Saw Ledgerline's Series B raise + the 2 SDR reqs — congrats. Most VPs at your stage tell me ramp is the bottleneck.",
//     "Your LinkedIn post on SDR ramp resonated. We help Series B fintech teams cut ramp ~40%.",
//   ],
//   talkTrack:
//     "Lead with empathy on the ramp problem → share 1 data point from a comparable customer (e.g. 'Vaultnode cut ramp from 4.2 → 2.6 months') → offer a 15-min live walk-through of the daily ICP-fit queue → soft CTA.",
// };

// function mkSP(
//   id: string,
//   name: string,
//   title: string,
//   company: string,
//   email: string,
//   icpScore: number,
//   reason: string,
// ): SourcedProspect {
//   return {
//     id,
//     name,
//     title,
//     company,
//     email,
//     linkedinUrl: `https://linkedin.com/in/${id}`,
//     icpScore,
//     reason,
//   };
// }

// const SEED_PROSPECTS = MOCK_NL_RESULTS;

/* ── Page ──────────────────────────────────────────────────────────── */

export function ProspectSourcingPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState("configs");

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Prospect Sourcing"
        description="Manage source connections, run natural-language searches, find lookalikes, generate ultimate profiles, and craft prospect briefs."
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="configs">
            <Database className="mr-1.5 h-4 w-4" />
            Source Configs
          </TabsTrigger>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="nl">
                <Search className="mr-1.5 h-4 w-4" />
                NL Search
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>Natural-language prospect search — describe who you want in plain English (e.g. &quot;Heads of RevOps at US B2B SaaS, 50–500 employees&quot;).</TooltipContent>
          </Tooltip>
          <TabsTrigger value="lookalike">
            <Shuffle className="mr-1.5 h-4 w-4" />
            Lookalike
          </TabsTrigger>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="ultimate">
                <Sparkles className="mr-1.5 h-4 w-4" />
                Ultimate Profile
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>Unified prospect profile — merges data from every connected source into one enriched view.</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="brief">
                <FileText className="mr-1.5 h-4 w-4" />
                Prospect Brief
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>AI-generated 1-page prospect brief — research, talking points, and email angle.</TooltipContent>
          </Tooltip>
        </TabsList>

        <TabsContent value="configs">
          <ConfigsTab qc={qc} />
        </TabsContent>
        <TabsContent value="nl">
          <NlSearchTab />
        </TabsContent>
        <TabsContent value="lookalike">
          <LookalikeTab />
        </TabsContent>
        <TabsContent value="ultimate">
          <UltimateProfileTab />
        </TabsContent>
        <TabsContent value="brief">
          <BriefTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ── Configs tab ───────────────────────────────────────────────────── */

function ConfigsTab({ qc }: { qc: ReturnType<typeof useQueryClient> }) {
  const [edit, setEdit] = useState<SourceConfig | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SourceConfig | null>(null);

  const query = useQuery<SourceConfig[]>({
    queryKey: ["prospect-source-configs"],
    queryFn: () => http.get<SourceConfig[]>("/api/v1/prospect-source/configs"),
  });
  const configs = query.data ?? [];

  const saveMutation = useMutation({
    mutationFn: (cfg: SourceConfig) => {
      if (configs.some((c) => c.id === cfg.id)) {
        return http.put(`/api/v1/prospect-source/configs/${cfg.id}`, cfg);
      }
      return http.post("/api/v1/prospect-source/configs", cfg);
    },
    onSuccess: () => {
      toast.success("Source config saved");
      setEdit(null);
      setAddOpen(false);
      qc.invalidateQueries({ queryKey: ["prospect-source-configs"] });
    },
    onError: () => toast.error("Save failed — backend unavailable"),
  });

  const toggleMutation = useMutation({
    mutationFn: (cfg: SourceConfig) =>
      http.put(`/api/v1/prospect-source/configs/${cfg.id}`, { ...cfg, isActive: !cfg.isActive }),
    onSuccess: () => {
      toast.success("Toggled");
      qc.invalidateQueries({ queryKey: ["prospect-source-configs"] });
    },
    onError: () => toast.error("Toggle failed — backend unavailable"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/prospect-source/configs/${id}`),
    onSuccess: () => {
      toast.success("Deleted");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["prospect-source-configs"] });
    },
    onError: () => toast.error("Delete failed — backend unavailable"),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Source Configurations</CardTitle>
            <CardDescription>API keys + rate limits per sourcing connector.</CardDescription>
          </div>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" />
            Add Source
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {query.isError ? (
          <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <p className="text-sm font-medium">Failed to load source configs</p>
            <Button variant="outline" onClick={() => query.refetch()}>
              Retry
            </Button>
          </div>
        ) : query.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Source</TableHead>
              <TableHead>API Key</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Today / Limit</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {configs.map((cfg) => (
              <TableRow key={cfg.id}>
                <TableCell className="font-medium">{cfg.source}</TableCell>
                <TableCell>
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{cfg.apiKeyMasked}</code>
                </TableCell>
                <TableCell>
                  <Badge variant={cfg.isActive ? "success" : "secondary"}>
                    {cfg.isActive ? "Active" : "Paused"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="space-y-1">
                    <Progress value={(cfg.usedToday / cfg.dailyLimit) * 100} className="h-1.5" />
                    <span className="text-xs text-muted-foreground">
                      {cfg.usedToday} / {cfg.dailyLimit}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label="Toggle active"
                          onClick={() => toggleMutation.mutate(cfg)}
                        >
                          <Power className={cn("h-4 w-4", cfg.isActive && "text-emerald-600")} />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{cfg.isActive ? "Pause source" : "Activate source"}</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label="Edit"
                          onClick={() => setEdit(cfg)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Edit source</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label="Delete"
                          onClick={() => setDeleteTarget(cfg)}
                        >
                          <Trash2 className="h-4 w-4 text-red-600" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete source</TooltipContent>
                    </Tooltip>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        )}
      </CardContent>

      <ConfigDialog
        open={!!edit || addOpen}
        config={edit}
        onClose={() => {
          setEdit(null);
          setAddOpen(false);
        }}
        onSubmit={(cfg) => saveMutation.mutate(cfg)}
        isPending={saveMutation.isPending}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete source config?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.source
              ? `Source "${deleteTarget.source}" and its stored API key will be permanently removed. This action cannot be undone.`
              : "This source configuration will be permanently removed. This action cannot be undone."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() =>
              deleteTarget && deleteMutation.mutate(deleteTarget.id)
            }
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </Dialog>
    </Card>
  );
}

function ConfigDialog({
  open,
  config,
  onClose,
  onSubmit,
  isPending,
}: {
  open: boolean;
  config: SourceConfig | null;
  onClose: () => void;
  onSubmit: (cfg: SourceConfig) => void;
  isPending: boolean;
}) {
  const [source, setSource] = useState("");
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [dailyLimit, setDailyLimit] = useState(500);
  const [isActive, setIsActive] = useState(true);

  // sync state when dialog target changes
  useMemo(() => {
    setSource(config?.source ?? "");
    setName(config?.name ?? config?.source ?? "");
    setApiKey("");
    setDailyLimit(config?.dailyLimit ?? 500);
    setIsActive(config?.isActive ?? true);
  }, [config, open]);

  function submit() {
    if (!source.trim()) return;
    onSubmit({
      id: config?.id ?? `c-${Date.now()}`,
      source: source.trim(),
      name: name.trim() || source.trim(),
      apiKey: apiKey || undefined,
      apiKeyMasked: apiKey ? maskKey(apiKey) : (config?.apiKeyMasked ?? "—"),
      isActive,
      dailyLimit,
      usedToday: config?.usedToday ?? 0,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>{config ? "Edit Source" : "Add Source"}</DialogTitle>
        <DialogDescription>Configure the connector credentials and daily quota.</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-2">
          <Label htmlFor="cfg-source">Source</Label>
          <Input id="cfg-source" value={source} onChange={(e) => setSource(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cfg-name">Display Name</Label>
          <Input id="cfg-name" value={name} onChange={(e) => setName(e.target.value)} placeholder={source} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cfg-key">
            API Key {config && <span className="text-muted-foreground">(leave blank to keep current)</span>}
          </Label>
          <div className="relative">
            <KeyRound className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="cfg-key"
              type="password"
              className="pl-9"
              placeholder="paste key…"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <InfoLabel
              htmlFor="cfg-limit"
              label="Daily Limit"
              info="Max API calls per UTC day. OUTRENA throttles requests once the limit is reached to avoid vendor overage charges."
            />
            <Input
              id="cfg-limit"
              type="number"
              value={dailyLimit}
              onChange={(e) => setDailyLimit(Number(e.target.value) || 0)}
            />
          </div>
          <div className="space-y-2">
            <Label>Active</Label>
            <div className="flex h-10 items-center gap-2">
              <Switch checked={isActive} onCheckedChange={setIsActive} />
              <span className="text-sm text-muted-foreground">
                {isActive ? "Active" : "Paused"}
              </span>
            </div>
          </div>
        </div>
      </div>
      <DialogFooter>
        <DialogClose onClose={onClose} />
        <Button onClick={submit} disabled={isPending || !source.trim()}>
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

/* ── NL Search tab ─────────────────────────────────────────────────── */

function NlSearchTab() {
  const [query, setQuery] = useState("Find CMOs at Series B SaaS in fintech");
  const [results, setResults] = useState<SourcedProspect[]>([]);
  const [searched, setSearched] = useState(false);

  const mutation = useMutation({
    mutationFn: (q: string) =>
      http.post<SourcedProspect[]>("/api/v1/prospect-source/nl-search", { query: q }),
    onSuccess: (data) => {
      setResults(data ?? []);
      setSearched(true);
      toast.success(`Found ${data?.length ?? 0} prospects`);
    },
    onError: (err) => {
      setSearched(true);
      toast.error("Search failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Search className="h-4 w-4" />
          Natural Language Search
        </CardTitle>
        <CardDescription>Describe the prospects you want in plain English.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="nl-query">Query</Label>
          <Textarea
            id="nl-query"
            rows={2}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button
          onClick={() => mutation.mutate(query)}
          disabled={!query.trim() || mutation.isPending}
        >
          {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Search Prospects
        </Button>

        {searched && (
          <ProspectResultsTable title={`${results.length} matching prospects`} results={results} />
        )}
      </CardContent>
    </Card>
  );
}

/* ── Lookalike tab ─────────────────────────────────────────────────── */

function LookalikeTab() {
  const [seedId, setSeedId] = useState("");
  const [results, setResults] = useState<SourcedProspect[]>([]);
  const [searched, setSearched] = useState(false);

  const seedQuery = useQuery<SourcedProspect[]>({
    queryKey: ["prospect-source-seeds"],
    queryFn: () => http.get<SourcedProspect[]>("/api/v1/prospects?limit=20"),
  });
  const seedProspects = seedQuery.data ?? [];

  const mutation = useMutation({
    mutationFn: (id: string) =>
      http.post<SourcedProspect[]>("/api/v1/prospect-source/lookalike", { prospectId: id }),
    onSuccess: (data) => {
      setResults(data ?? []);
      setSearched(true);
      toast.success(`Found ${data?.length ?? 0} lookalikes`);
    },
    onError: (err) => {
      setSearched(true);
      toast.error("Lookalike search failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  const seed = seedProspects.find((p) => p.id === seedId) ?? seedProspects[0];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Shuffle className="h-4 w-4" />
          Lookalike Search
        </CardTitle>
        <CardDescription>Pick a seed prospect; we find similar ones.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="seed">Seed Prospect</Label>
          <select
            id="seed"
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={seedId}
            onChange={(e) => setSeedId(e.target.value)}
          >
            {seedProspects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} — {p.title} @ {p.company}
              </option>
            ))}
          </select>
          {seed && (
            <p className="text-xs text-muted-foreground">
              Seed: {seed.name} ({seed.title} @ {seed.company}), ICP {formatPercent(seed.icpScore, 0)}
            </p>
          )}
        </div>
        <Button
          onClick={() => mutation.mutate(seedId)}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shuffle className="h-4 w-4" />}
          Find Lookalikes
        </Button>

        {searched && (
          <ProspectResultsTable
            title={`${results.length} lookalikes`}
            results={results}
          />
        )}
      </CardContent>
    </Card>
  );
}

/* ── Ultimate Profile tab ──────────────────────────────────────────── */

function UltimateProfileTab() {
  const [prospectName, setProspectName] = useState("Priya Shankar");
  const [profile, setProfile] = useState<UltimateProfile | null>(null);

  const mutation = useMutation({
    mutationFn: (name: string) =>
      http.post<UltimateProfile>("/api/v1/prospect-source/ultimate-profile", { prospectName: name }),
    onSuccess: (data) => {
      setProfile(data);
      toast.success("Ultimate profile generated");
    },
    onError: (err) => {
      toast.error("Profile generation failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4" />
          Ultimate Profile
        </CardTitle>
        <CardDescription>Enrich a prospect into a 360° profile card.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Prospect name (e.g. Priya Shankar)"
            value={prospectName}
            onChange={(e) => setProspectName(e.target.value)}
          />
          <Button
            onClick={() => mutation.mutate(prospectName)}
            disabled={!prospectName.trim() || mutation.isPending}
          >
            {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Generate
          </Button>
        </div>

        {profile && <UltimateProfileCard profile={profile} />}
      </CardContent>
    </Card>
  );
}

function UltimateProfileCard({ profile }: { profile: UltimateProfile }) {
  return (
    <div className="space-y-4 rounded-md border p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-base font-semibold">{profile.prospectName}</p>
          <p className="text-sm text-muted-foreground">
            {profile.title} @ {profile.company} · {profile.experienceYears}y experience
          </p>
        </div>
        <Badge variant="success">
          ICP Fit {formatPercent(profile.icpFitScore, 0)}
        </Badge>
      </div>
      <Separator />
      <p className="text-sm text-muted-foreground">{profile.bio}</p>

      <ProfileSection title="Education" items={profile.education} />
      <ProfileSection title="Skills" items={profile.skills} variant="badge" />
      <ProfileSection title="Tech Stack" items={profile.techStack} variant="badge" />
      <ProfileSection title="Recent Activity" items={profile.recentActivity} />
    </div>
  );
}

function ProfileSection({
  title,
  items,
  variant = "list",
}: {
  title: string;
  items: string[];
  variant?: "list" | "badge";
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">{title}</p>
      {variant === "badge" ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((s, i) => (
            <Badge key={i} variant="secondary">
              {s}
            </Badge>
          ))}
        </div>
      ) : (
        <ul className="space-y-1 text-sm text-muted-foreground">
          {items.map((s, i) => (
            <li key={i}>• {s}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ── Brief tab ─────────────────────────────────────────────────────── */

function BriefTab() {
  const [prospectName, setProspectName] = useState("Priya Shankar");
  const [brief, setBrief] = useState<ProspectBrief | null>(null);

  const mutation = useMutation({
    mutationFn: (name: string) =>
      http.post<ProspectBrief>("/api/v1/prospect-source/brief", { prospectName: name }),
    onSuccess: (data) => {
      setBrief(data);
      toast.success("Brief generated");
    },
    onError: (err) => {
      toast.error("Brief generation failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="h-4 w-4" />
          Prospect Brief
        </CardTitle>
        <CardDescription>One-page account brief for sales prep.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Prospect name"
            value={prospectName}
            onChange={(e) => setProspectName(e.target.value)}
          />
          <Button
            onClick={() => mutation.mutate(prospectName)}
            disabled={!prospectName.trim() || mutation.isPending}
          >
            {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Generate Brief
          </Button>
        </div>

        {brief && <BriefCard brief={brief} />}
      </CardContent>
    </Card>
  );
}

function BriefCard({ brief }: { brief: ProspectBrief }) {
  return (
    <div className="space-y-4 rounded-md border p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-base font-semibold">
            {brief.prospectName} <span className="font-normal text-muted-foreground">@ {brief.company}</span>
          </p>
          <p className="text-xs text-muted-foreground">Generated {timeAgo(new Date().toISOString())}</p>
        </div>
      </div>
      <Separator />
      <div className="space-y-1">
        <p className="text-xs font-medium uppercase text-muted-foreground">Summary</p>
        <p className="text-sm text-muted-foreground">{brief.summary}</p>
      </div>
      <BriefSection title="Pain Points" items={brief.painPoints} />
      <BriefSection title="Why Now?" items={brief.whyNow} />
      <BriefSection title="Opening Hooks" items={brief.openingHooks} />
      <div className="space-y-1">
        <p className="text-xs font-medium uppercase text-muted-foreground">Talk Track</p>
        <p className="rounded-md bg-muted/40 p-3 text-sm">{brief.talkTrack}</p>
      </div>
    </div>
  );
}

function BriefSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase text-muted-foreground">{title}</p>
      <ul className="space-y-1 text-sm text-muted-foreground">
        {items.map((s, i) => (
          <li key={i}>• {truncate(s, 220)}</li>
        ))}
      </ul>
    </div>
  );
}

/* ── Shared prospect results table ─────────────────────────────────── */

function ProspectResultsTable({
  title,
  results,
}: {
  title: string;
  results: SourcedProspect[];
}) {
  if (results.length === 0) {
    return (
      <EmptyState
        icon={<Search className="h-6 w-6" />}
        title="No results"
        description="Try refining your query or seed prospect."
      />
    );
  }
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{title}</p>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Company</TableHead>
              <TableHead className="w-32">ICP</TableHead>
              <TableHead>Reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <div className="space-y-0.5">
                    <p className="font-medium">{p.name}</p>
                    <p className="text-xs text-muted-foreground">{p.title}</p>
                  </div>
                </TableCell>
                <TableCell className="text-sm">{p.company}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Progress value={p.icpScore * 100} className="h-1.5" />
                    <span className="text-xs">{formatPercent(p.icpScore, 0)}</span>
                  </div>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">{p.reason}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

/* ── Helpers ───────────────────────────────────────────────────────── */

function maskKey(key: string): string {
  if (key.length <= 8) return `${key.slice(0, 3)}••••`;
  return `${key.slice(0, 4)}••••••${key.slice(-4)}`;
}
