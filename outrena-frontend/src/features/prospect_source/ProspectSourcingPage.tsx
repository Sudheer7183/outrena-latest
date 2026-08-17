/**
 * ProspectSourcingPage.tsx — Prospect sourcing toolkit.
 *
 * Bug fixes:
 *   Bug1  SourceConfigResponse has {id,source,name,isActive,apiKey,dailyQuota,
 *         usedToday,settings,createdAt,updatedAt} — frontend was using wrong
 *         field names (apiKeyMasked, dailyLimit). Fixed type + display.
 *   Bug2  NL search returns NaturalLanguageSearchResponse {interpretedFilters,
 *         prospects: ProspectSearchHit[], count} — NOT a plain array.
 *         Frontend was treating it as an array → .map crash. Fixed.
 *   Bug3  Lookalike: GET /prospects returns {items[],total,limit,offset} —
 *         NOT a plain array. Also LookalikeResponse is {seedProspectId,
 *         lookalikes: LookalikeHit[], count}. Both fixed.
 *   Bug4  UltimateProfileRequest expects {prospectId} not {prospectName}.
 *         Changed to prospect selector dropdown.
 *   Bug5  ProspectBriefRequest expects {prospectId,callType} not {prospectName}.
 *         Changed to prospect selector dropdown.
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
import { cn, formatPercent, timeAgo } from "@/lib/utils";
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
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";

/* ── Backend types (matching real schemas exactly) ──────────────────────── */

// Bug1 fix: real SourceConfigResponse shape
interface SourceConfig {
  id: string;
  source: string;
  name: string;
  apiKey: string | null;       // masked value from API
  isActive: boolean;
  dailyQuota: number;          // NOT dailyLimit
  usedToday: number;
  settings: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

// Bug2 fix: NL search returns an envelope, not a plain array
interface ProspectSearchHit {
  id: string;
  firstName: string;
  lastName: string;
  email: string | null;
  title: string | null;
  company: string | null;
}

interface NaturalLanguageSearchResponse {
  interpretedFilters: Record<string, unknown>;
  prospects: ProspectSearchHit[];
  count: number;
}

// Bug3 fix: Lookalike returns an envelope
interface LookalikeHit {
  id: string;
  firstName: string | null;
  lastName: string | null;
  title: string | null;
  company: string | null;
  similarityScore: number;
}

interface LookalikeResponse {
  seedProspectId: string;
  lookalikes: LookalikeHit[];
  count: number;
}

// Bug3 fix: GET /prospects returns {items[],total}
interface ProspectListResponse {
  items: ProspectSearchHit[];
  total: number;
}

// Bug4 fix: UltimateProfileResponse
interface UltimateProfileResponse {
  prospectId: string;
  profile: Record<string, unknown>;
}

// Bug5 fix: ProspectBriefResponse
interface ProspectBriefResponse {
  prospectId: string;
  brief: string;
}

/* ── Page ───────────────────────────────────────────────────────────────── */

export function ProspectSourcingPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState("configs");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Prospect Sourcing"
        description="Manage source connections, run natural-language searches, find lookalikes, generate ultimate profiles, and craft prospect briefs."
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="configs">
            <Database className="mr-1.5 h-4 w-4" /> Source Configs
          </TabsTrigger>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="nl">
                <Search className="mr-1.5 h-4 w-4" /> NL Search
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>Natural-language prospect search</TooltipContent>
          </Tooltip>
          <TabsTrigger value="lookalike">
            <Shuffle className="mr-1.5 h-4 w-4" /> Lookalike
          </TabsTrigger>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="ultimate">
                <Sparkles className="mr-1.5 h-4 w-4" /> Ultimate Profile
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>Unified enriched prospect profile</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="brief">
                <FileText className="mr-1.5 h-4 w-4" /> Prospect Brief
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>AI-generated 1-page prospect brief</TooltipContent>
          </Tooltip>
        </TabsList>

        <TabsContent value="configs" className="mt-4">
          <ConfigsTab qc={qc} />
        </TabsContent>
        <TabsContent value="nl" className="mt-4">
          <NlSearchTab />
        </TabsContent>
        <TabsContent value="lookalike" className="mt-4">
          <LookalikeTab />
        </TabsContent>
        <TabsContent value="ultimate" className="mt-4">
          <UltimateProfileTab />
        </TabsContent>
        <TabsContent value="brief" className="mt-4">
          <BriefTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ── Configs tab ─────────────────────────────────────────────────────────── */

function ConfigsTab({ qc }: { qc: ReturnType<typeof useQueryClient> }) {
  const [edit, setEdit] = useState<SourceConfig | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SourceConfig | null>(null);

  const query = useQuery<SourceConfig[]>({
    queryKey: ["prospect-source-configs"],
    queryFn: () =>
      http.get<SourceConfig[]>("/api/v1/prospect-source/configs"),
    retry: false,
  });
  const configs = query.data ?? [];

  const saveMutation = useMutation({
    mutationFn: (cfg: SourceConfig) => {
      const existing = configs.some((c) => c.id === cfg.id);
      if (existing) {
        return http.put(`/api/v1/prospect-source/configs/${cfg.source}`, {
          name: cfg.name,
          isActive: cfg.isActive,
          dailyQuota: cfg.dailyQuota,
          apiKey: cfg.apiKey || undefined,
        });
      }
      return http.post("/api/v1/prospect-source/configs", {
        source: cfg.source,
        name: cfg.name,
        isActive: cfg.isActive,
        dailyQuota: cfg.dailyQuota,
        apiKey: cfg.apiKey || undefined,
        settings: {},
      });
    },
    onSuccess: () => {
      toast.success("Source config saved");
      setEdit(null);
      setAddOpen(false);
      qc.invalidateQueries({ queryKey: ["prospect-source-configs"] });
    },
    onError: () => toast.error("Save failed"),
  });

  const toggleMutation = useMutation({
    mutationFn: (cfg: SourceConfig) =>
      http.put(`/api/v1/prospect-source/configs/${cfg.source}`, {
        isActive: !cfg.isActive,
      }),
    onSuccess: () => {
      toast.success("Toggled");
      qc.invalidateQueries({ queryKey: ["prospect-source-configs"] });
    },
    onError: () => toast.error("Toggle failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: (cfg: SourceConfig) =>
      http.delete(`/api/v1/prospect-source/configs/${cfg.source}`),
    onSuccess: () => {
      toast.success("Deleted");
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["prospect-source-configs"] });
    },
    onError: () => toast.error("Delete failed"),
  });

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Source Configurations</CardTitle>
              <CardDescription>
                API keys + rate limits per sourcing connector.
              </CardDescription>
            </div>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" /> Add Source
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
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : configs.length === 0 ? (
            <EmptyState
              icon={<Database className="h-8 w-8" />}
              title="No source configs yet"
              description='Click "Add Source" to connect your first prospect data source.'
              className="py-8"
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>API Key</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Today / Quota</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {configs.map((cfg) => (
                  <TableRow key={cfg.id}>
                    <TableCell className="font-medium">{cfg.source}</TableCell>
                    <TableCell>
                      {cfg.apiKey ? (
                        <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                          {cfg.apiKey}
                        </code>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-xs",
                          cfg.isActive
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : "bg-slate-50 text-slate-600 border-slate-200"
                        )}
                      >
                        {cfg.isActive ? "Active" : "Paused"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <Progress
                          value={
                            cfg.dailyQuota > 0
                              ? (cfg.usedToday / cfg.dailyQuota) * 100
                              : 0
                          }
                          className="h-1.5"
                        />
                        <span className="text-xs text-muted-foreground">
                          {cfg.usedToday} / {cfg.dailyQuota}
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
                              onClick={() => toggleMutation.mutate(cfg)}
                            >
                              <Power
                                className={cn(
                                  "h-4 w-4",
                                  cfg.isActive && "text-emerald-600"
                                )}
                              />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            {cfg.isActive ? "Pause" : "Activate"}
                          </TooltipContent>
                        </Tooltip>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => setEdit(cfg)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="text-destructive"
                          onClick={() => setDeleteTarget(cfg)}
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

      {/* Add/Edit dialog */}
      <ConfigDialog
        open={Boolean(edit) || addOpen}
        config={edit}
        onClose={() => {
          setEdit(null);
          setAddOpen(false);
        }}
        onSubmit={(cfg) => saveMutation.mutate(cfg)}
        isPending={saveMutation.isPending}
      />

      {/* Delete dialog */}
      <Dialog
        open={Boolean(deleteTarget)}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete source config?</DialogTitle>
            <DialogDescription>
              "{deleteTarget?.source}" and its stored API key will be permanently
              removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() =>
                deleteTarget && deleteMutation.mutate(deleteTarget)
              }
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
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
  const [dailyQuota, setDailyQuota] = useState(500);
  const [isActive, setIsActive] = useState(true);

  useMemo(() => {
    setSource(config?.source ?? "");
    setName(config?.name ?? config?.source ?? "");
    setApiKey("");
    setDailyQuota(config?.dailyQuota ?? 500);
    setIsActive(config?.isActive ?? true);
  }, [config, open]); // eslint-disable-line react-hooks/exhaustive-deps

  function submit() {
    if (!source.trim()) return;
    onSubmit({
      id: config?.id ?? `c-${Date.now()}`,
      source: source.trim(),
      name: name.trim() || source.trim(),
      apiKey: apiKey || null,
      isActive,
      dailyQuota,
      usedToday: config?.usedToday ?? 0,
      settings: config?.settings ?? {},
      createdAt: config?.createdAt ?? new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{config ? "Edit Source" : "Add Source"}</DialogTitle>
          <DialogDescription>
            Configure connector credentials and daily quota.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="cfg-source">Source</Label>
            <Input
              id="cfg-source"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="e.g. apollo, clay, zoominfo"
              disabled={Boolean(config)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cfg-name">Display Name</Label>
            <Input
              id="cfg-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={source}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cfg-key">
              API Key{" "}
              {config && (
                <span className="text-muted-foreground text-xs">
                  (leave blank to keep current)
                </span>
              )}
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
            <div className="space-y-1.5">
              <Label htmlFor="cfg-quota">Daily Quota</Label>
              <Input
                id="cfg-quota"
                type="number"
                value={dailyQuota}
                onChange={(e) => setDailyQuota(Number(e.target.value) || 0)}
              />
            </div>
            <div className="space-y-1.5">
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
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={isPending || !source.trim()}>
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── NL Search tab ───────────────────────────────────────────────────────── */

function NlSearchTab() {
  const [query, setQuery] = useState(
    "Find CMOs at Series B SaaS in fintech"
  );
  // Bug2 fix: state is ProspectSearchHit[] (extracted from envelope)
  const [results, setResults] = useState<ProspectSearchHit[]>([]);
  const [filters, setFilters] = useState<Record<string, unknown>>({});
  const [searched, setSearched] = useState(false);

  const mutation = useMutation({
    mutationFn: (q: string) =>
      http.post<NaturalLanguageSearchResponse>(
        "/api/v1/prospect-source/nl-search",
        { query: q }
      ),
    onSuccess: (data) => {
      // Bug2 fix: unwrap the envelope
      const prospects = data?.prospects ?? [];
      setResults(prospects);
      setFilters(data?.interpretedFilters ?? {});
      setSearched(true);
      toast.success(`Found ${prospects.length} prospects`);
    },
    onError: () => {
      setSearched(true);
      toast.error("Search failed");
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Search className="h-4 w-4" /> Natural Language Search
        </CardTitle>
        <CardDescription>
          Describe the prospects you want in plain English.
        </CardDescription>
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
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          Search Prospects
        </Button>

        {/* Interpreted filters */}
        {searched && Object.keys(filters).length > 0 && (
          <div className="rounded-md bg-muted/40 p-3 text-xs">
            <p className="font-medium mb-1">Interpreted filters:</p>
            {Object.entries(filters).map(([k, v]) => (
              <span key={k} className="mr-3">
                <span className="text-muted-foreground">{k}:</span>{" "}
                <span className="font-medium">{String(v)}</span>
              </span>
            ))}
          </div>
        )}

        {searched && (
          <ProspectHitsTable
            title={`${results.length} matching prospects`}
            hits={results}
          />
        )}
      </CardContent>
    </Card>
  );
}

/* ── Lookalike tab ───────────────────────────────────────────────────────── */

function LookalikeTab() {
  const [seedId, setSeedId] = useState("");
  // Bug3 fix: LookalikeHit[] not SourcedProspect[]
  const [results, setResults] = useState<LookalikeHit[]>([]);
  const [searched, setSearched] = useState(false);

  // Bug3 fix: GET /prospects returns {items[],total} not a plain array
  const seedQuery = useQuery<ProspectListResponse>({
    queryKey: ["prospects-lite"],
    queryFn: () =>
      http.get<ProspectListResponse>("/api/v1/prospects?limit=50"),
    retry: false,
  });
  // Bug3 fix: extract .items from the envelope
  const seedProspects = seedQuery.data?.items ?? [];

  const mutation = useMutation({
    mutationFn: (id: string) =>
      http.post<LookalikeResponse>(
        "/api/v1/prospect-source/lookalike",
        { prospectId: id }
      ),
    onSuccess: (data) => {
      // Bug3 fix: unwrap the envelope
      setResults(data?.lookalikes ?? []);
      setSearched(true);
      toast.success(`Found ${data?.count ?? 0} lookalikes`);
    },
    onError: () => {
      setSearched(true);
      toast.error("Lookalike search failed");
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Shuffle className="h-4 w-4" /> Lookalike Search
        </CardTitle>
        <CardDescription>
          Pick a seed prospect to find similar ones.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Seed Prospect</Label>
          {seedQuery.isLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (
            <Select value={seedId} onValueChange={setSeedId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a prospect as seed…" />
              </SelectTrigger>
              <SelectContent className="max-h-60">
                {seedProspects.length === 0 ? (
                  <SelectItem value="_none" disabled>
                    No prospects available
                  </SelectItem>
                ) : (
                  seedProspects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.firstName} {p.lastName}
                      {p.title ? ` — ${p.title}` : ""}
                      {p.company ? ` @ ${p.company}` : ""}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          )}
        </div>
        <Button
          onClick={() => mutation.mutate(seedId)}
          disabled={mutation.isPending || !seedId}
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Shuffle className="h-4 w-4" />
          )}
          Find Lookalikes
        </Button>

        {searched && (
          <LookalikeResultsTable
            title={`${results.length} lookalikes`}
            hits={results}
          />
        )}
      </CardContent>
    </Card>
  );
}

/* ── Ultimate Profile tab ────────────────────────────────────────────────── */

function UltimateProfileTab() {
  // Bug4 fix: use prospectId selector, not prospectName text input
  const [prospectId, setProspectId] = useState("");
  const [profile, setProfile] = useState<UltimateProfileResponse | null>(null);

  const prospectsQuery = useQuery<ProspectListResponse>({
    queryKey: ["prospects-lite"],
    queryFn: () =>
      http.get<ProspectListResponse>("/api/v1/prospects?limit=50"),
    retry: false,
  });
  const prospects = prospectsQuery.data?.items ?? [];

  const mutation = useMutation({
    mutationFn: (id: string) =>
      http.post<UltimateProfileResponse>(
        "/api/v1/prospect-source/ultimate-profile",
        { prospectId: id }       // Bug4 fix: send prospectId not prospectName
      ),
    onSuccess: (data) => {
      setProfile(data);
      toast.success("Ultimate profile generated");
    },
    onError: () => toast.error("Profile generation failed"),
  });

  const selectedProspect = prospects.find((p) => p.id === prospectId);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4" /> Ultimate Profile
        </CardTitle>
        <CardDescription>
          Enrich a prospect into a 360° profile card.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Select Prospect</Label>
          <div className="flex gap-2">
            <div className="flex-1">
              <Select value={prospectId} onValueChange={setProspectId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a prospect…" />
                </SelectTrigger>
                <SelectContent className="max-h-60">
                  {prospects.length === 0 ? (
                    <SelectItem value="_none" disabled>
                      No prospects available
                    </SelectItem>
                  ) : (
                    prospects.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.firstName} {p.lastName}
                        {p.title ? ` — ${p.title}` : ""}
                        {p.company ? ` @ ${p.company}` : ""}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => mutation.mutate(prospectId)}
              disabled={!prospectId || mutation.isPending}
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Generate
            </Button>
          </div>
        </div>

        {profile && (
          <div className="space-y-4 rounded-md border p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-base font-semibold">
                  {selectedProspect
                    ? `${selectedProspect.firstName} ${selectedProspect.lastName}`
                    : profile.prospectId}
                </p>
                {selectedProspect && (
                  <p className="text-sm text-muted-foreground">
                    {selectedProspect.title}
                    {selectedProspect.company
                      ? ` @ ${selectedProspect.company}`
                      : ""}
                  </p>
                )}
              </div>
            </div>
            <Separator />
            {/* Render the profile dict as readable key-value sections */}
            {Object.entries(profile.profile).map(([k, v]) => (
              <div key={k}>
                <p className="text-xs font-medium uppercase text-muted-foreground mb-1">
                  {k.replace(/([A-Z])/g, " $1").trim()}
                </p>
                {Array.isArray(v) ? (
                  <div className="flex flex-wrap gap-1.5">
                    {(v as string[]).map((s, i) => (
                      <Badge key={i} variant="secondary">
                        {String(s)}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">{String(v)}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ── Brief tab ───────────────────────────────────────────────────────────── */

function BriefTab() {
  // Bug5 fix: use prospectId selector + callType, not prospectName text input
  const [prospectId, setProspectId] = useState("");
  const [callType, setCallType] = useState("discovery");
  const [brief, setBrief] = useState<ProspectBriefResponse | null>(null);

  const prospectsQuery = useQuery<ProspectListResponse>({
    queryKey: ["prospects-lite"],
    queryFn: () =>
      http.get<ProspectListResponse>("/api/v1/prospects?limit=50"),
    retry: false,
  });
  const prospects = prospectsQuery.data?.items ?? [];
  const selectedProspect = prospects.find((p) => p.id === prospectId);

  const mutation = useMutation({
    mutationFn: (body: { prospectId: string; callType: string }) =>
      http.post<ProspectBriefResponse>(
        "/api/v1/prospect-source/brief",
        body    // Bug5 fix: send {prospectId, callType} not {prospectName}
      ),
    onSuccess: (data) => {
      setBrief(data);
      toast.success("Brief generated");
    },
    onError: () => toast.error("Brief generation failed"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="h-4 w-4" /> Prospect Brief
        </CardTitle>
        <CardDescription>
          AI-generated one-page brief — research, talking points, and
          email angle.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-2 space-y-1.5">
            <Label>Prospect</Label>
            <Select value={prospectId} onValueChange={setProspectId}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a prospect…" />
              </SelectTrigger>
              <SelectContent className="max-h-60">
                {prospects.length === 0 ? (
                  <SelectItem value="_none" disabled>
                    No prospects available
                  </SelectItem>
                ) : (
                  prospects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.firstName} {p.lastName}
                      {p.title ? ` — ${p.title}` : ""}
                      {p.company ? ` @ ${p.company}` : ""}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Call Type</Label>
            <Select value={callType} onValueChange={setCallType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="discovery">Discovery</SelectItem>
                <SelectItem value="demo">Demo</SelectItem>
                <SelectItem value="negotiation">Negotiation</SelectItem>
                <SelectItem value="follow_up">Follow-up</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <Button
          onClick={() => mutation.mutate({ prospectId, callType })}
          disabled={!prospectId || mutation.isPending}
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
          Generate Brief
        </Button>

        {brief && (
          <div className="space-y-4 rounded-md border p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-base font-semibold">
                  {selectedProspect
                    ? `${selectedProspect.firstName} ${selectedProspect.lastName}`
                    : brief.prospectId}
                </p>
                {selectedProspect && (
                  <p className="text-sm text-muted-foreground">
                    {selectedProspect.title}
                    {selectedProspect.company
                      ? ` @ ${selectedProspect.company}`
                      : ""}
                    {" · "}
                    {callType} call · {timeAgo(new Date().toISOString())}
                  </p>
                )}
              </div>
            </div>
            <Separator />
            <div>
              <p className="text-xs font-medium uppercase text-muted-foreground mb-1">
                Brief
              </p>
              <pre className="text-sm text-muted-foreground whitespace-pre-wrap font-sans leading-relaxed">
                {brief.brief}
              </pre>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ── Shared result tables ────────────────────────────────────────────────── */

// Bug2: NL search hits
function ProspectHitsTable({
  title,
  hits,
}: {
  title: string;
  hits: ProspectSearchHit[];
}) {
  if (hits.length === 0) {
    return (
      <EmptyState
        icon={<Search className="h-6 w-6" />}
        title="No results"
        description="Try refining your query."
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
              <TableHead>Title</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Email</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {hits.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium">
                  {p.firstName} {p.lastName}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {p.title ?? "—"}
                </TableCell>
                <TableCell className="text-sm">{p.company ?? "—"}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {p.email ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// Bug3: Lookalike hits
function LookalikeResultsTable({
  title,
  hits,
}: {
  title: string;
  hits: LookalikeHit[];
}) {
  if (hits.length === 0) {
    return (
      <EmptyState
        icon={<Shuffle className="h-6 w-6" />}
        title="No lookalikes found"
        description="Try a different seed prospect."
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
              <TableHead>Title</TableHead>
              <TableHead>Company</TableHead>
              <TableHead className="w-28">Similarity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {hits.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium">
                  {p.firstName ?? ""} {p.lastName ?? ""}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {p.title ?? "—"}
                </TableCell>
                <TableCell className="text-sm">{p.company ?? "—"}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Progress
                      value={p.similarityScore * 100}
                      className="h-1.5"
                    />
                    <span className="text-xs">
                      {formatPercent(p.similarityScore, 0)}
                    </span>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}