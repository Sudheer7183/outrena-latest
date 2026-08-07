/**
 * IcpProfilesPage.tsx — ICP profiles CRUD + AI Suggest + Auto-Discover.
 *
 * Left: list of profiles (name, segment, avg ICP score, prospect count).
 * Right: detail panel with tabs (Profile / Scoring / Signals) + edit form.
 * "AI Suggest" → icp-suggest w/ seed description fills the form.
 * "Auto-Discover" → icp-auto-discover w/ a URL generates a profile.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Sparkles,
  Globe,
  Plus,
  Pencil,
  Trash2,
  Users,
  Target,
  Loader2,
  Save,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { Pagination, usePagination } from "@/components/ui/pagination";
import { cn, formatPercent, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InfoLabel } from "@/components/ui/info-label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogClose,
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
import type { SeniorityTier } from "@/types/common";

/* ── Types ─────────────────────────────────────────────────────────── */

interface ScoreWeights {
  industry: number;
  companySize: number;
  seniority: number;
  intent: number;
  engagement: number;
}

interface IcpProfile {
  id: string;
  name: string;
  targetSegment: string;
  industry: string;
  companySize: string;
  seniority: SeniorityTier;
  painPoints: string[];
  buyingSignals: string[];
  scoreWeights: ScoreWeights;
  icpScoreAvg: number;
  prospectCount: number;
  createdAt: string;
  updatedAt: string;
}

type IcpSuggestResponse = {
  name?: string;
  persona?: string;
  companyType?: string | null;
  painPoints?: string[];
  valueProps?: string[];
  topObjections?: string[];
  raw?: string | null;
};

type IcpAutoDiscoverResponse = {
  name?: string;
  persona?: string;
  companyType?: string | null;
  industries?: string[];
  companySizes?: string[];
  seniorityTiers?: string[];
  painPoints?: string[];
  valueProps?: string[];
  topObjections?: string[];
  raw?: string | null;
};

const EMPTY_PROFILE: Omit<IcpProfile, "id" | "createdAt" | "updatedAt" | "icpScoreAvg" | "prospectCount"> = {
  name: "",
  targetSegment: "",
  industry: "",
  companySize: "",
  seniority: "Director",
  painPoints: [],
  buyingSignals: [],
  scoreWeights: { industry: 25, companySize: 20, seniority: 15, intent: 25, engagement: 15 },
};

/* ── Mock data ─────────────────────────────────────────────────────── */

const MOCK_PROFILES: IcpProfile[] = [
  {
    id: "icp-1",
    name: "Fintech VP Sales (Series B/C)",
    targetSegment: "B2B Fintech / Payments",
    industry: "Financial Services",
    companySize: "50–200",
    seniority: "Director",
    painPoints: [
      "SDR ramp time too long",
      "Salesforce data quality is poor",
      "Pipeline coverage < 3x",
    ],
    buyingSignals: [
      "Hiring SDRs in last 90d",
      "Just raised Series B",
      "Using Sales Navigator",
    ],
    scoreWeights: { industry: 25, companySize: 20, seniority: 15, intent: 25, engagement: 15 },
    icpScoreAvg: 0.78,
    prospectCount: 142,
    createdAt: "2024-11-20T10:00:00Z",
    updatedAt: "2025-01-08T14:30:00Z",
  },
  {
    id: "icp-2",
    name: "Mid-Market HR Ops Director",
    targetSegment: "HR Tech / People Ops",
    industry: "Software / SaaS",
    companySize: "200–1000",
    seniority: "Director",
    painPoints: [
      "Manual onboarding workflows",
      "HRIS data siloed from LMS",
      "Compliance reporting is slow",
    ],
    buyingSignals: [
      "Posted HR Ops role",
      "Using Workday",
      "Mentioned onboarding pain on LinkedIn",
    ],
    scoreWeights: { industry: 20, companySize: 25, seniority: 20, intent: 20, engagement: 15 },
    icpScoreAvg: 0.71,
    prospectCount: 89,
    createdAt: "2024-12-01T09:00:00Z",
    updatedAt: "2025-01-05T11:15:00Z",
  },
  {
    id: "icp-3",
    name: "DevTools Eng Lead (IC)",
    targetSegment: "Developer Tools / Platform Eng",
    industry: "Software / Infrastructure",
    companySize: "20–100",
    seniority: "IC",
    painPoints: [
      "CI/CD pipeline flakiness",
      "Observability costs ballooning",
      "On-call burnout",
    ],
    buyingSignals: [
      "Starred relevant GH repos",
      "Posted hiring req for SRE",
      "Talked at KubeCon",
    ],
    scoreWeights: { industry: 30, companySize: 15, seniority: 10, intent: 30, engagement: 15 },
    icpScoreAvg: 0.83,
    prospectCount: 56,
    createdAt: "2024-12-15T16:00:00Z",
    updatedAt: "2025-01-09T08:45:00Z",
  },
];

/* ── Page ──────────────────────────────────────────────────────────── */

export function IcpProfilesPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(MOCK_PROFILES[0].id);
  const [draft, setDraft] = useState<IcpProfile | null>(null);
  const [seedDesc, setSeedDesc] = useState("");
  const [discoverUrl, setDiscoverUrl] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<IcpProfile | null>(null);

  const listQuery = useQuery<IcpProfile[]>({
    queryKey: ["icp-profiles"],
    queryFn: () => http.get<IcpProfile[]>("/api/v1/icp-profiles"),
  });
  const profiles = listQuery.data ?? MOCK_PROFILES;

  const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: profiles, initialPageSize: 15 });

  const selected = useMemo(() => {
    if (draft) return draft;
    return profiles.find((p) => p.id === selectedId) ?? null;
  }, [draft, profiles, selectedId]);

  /* mutations */
  const suggestMutation = useMutation({
    mutationFn: (seed: string) =>
      http.post<IcpSuggestResponse>("/api/v1/icp-suggest", { seed }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["icp-profiles"] });
      toast.success("AI suggestion applied", {
        description: "Profile fields filled from seed description.",
      });
      /* BUG-15 FIX: Backend returns flat fields (name, persona, painPoints, etc.)
         not a nested IcpProfile object.  Construct the profile manually. */
      setDraft((prev) => ({
        ...(prev ?? EMPTY_PROFILE),
        name: data.name ?? prev?.name ?? "",
        targetSegment: data.companyType ?? prev?.targetSegment ?? "",
        industry: data.companyType ?? prev?.industry ?? "",
        painPoints: data.painPoints ?? prev?.painPoints ?? [],
        buyingSignals: prev?.buyingSignals ?? [],
        scoreWeights: prev?.scoreWeights ?? EMPTY_PROFILE.scoreWeights,
        id: prev?.id ?? "draft",
        createdAt: prev?.createdAt ?? new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        icpScoreAvg: prev?.icpScoreAvg ?? 0,
        prospectCount: prev?.prospectCount ?? 0,
      }) as IcpProfile);
    },
    onError: (err) => {
      toast.error("AI suggestion failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  const discoverMutation = useMutation({
    mutationFn: (url: string) =>
      http.post<IcpAutoDiscoverResponse>("/api/v1/icp-auto-discover", { url }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["icp-profiles"] });
      toast.success("Auto-discovered profile", {
        description: `From ${urlOrDomain(discoverUrl)}`,
      });
      setDraft({
        ...EMPTY_PROFILE,
        ...data,
        name: data.name ?? `Profile from ${urlOrDomain(discoverUrl)}`,
        id: "draft",
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        icpScoreAvg: 0.69,
        prospectCount: 0,
      } as IcpProfile);
    },
    onError: (err) => {
      toast.error("Auto-discover failed", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    },
  });

  const saveMutation = useMutation({
    mutationFn: (profile: IcpProfile) => {
      const body = stripPersisted(profile);
      if (profile.id === "draft" || !profiles.some((p) => p.id === profile.id)) {
        return http.post<IcpProfile>("/api/v1/icp-profiles", body);
      }
      return http.put<IcpProfile>(`/api/v1/icp-profiles/${profile.id}`, body);
    },
    onSuccess: () => {
      toast.success("Profile saved");
      setDraft(null);
      qc.invalidateQueries({ queryKey: ["icp-profiles"] });
    },
    onError: () => {
      toast.error("Failed to save — backend unavailable");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/icp-profiles/${id}`),
    onSuccess: () => {
      toast.success("Profile deleted");
      setSelectedId(profiles[0]?.id ?? null);
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["icp-profiles"] });
    },
    onError: () => toast.error("Delete failed — backend unavailable"),
  });

  function handleSelect(p: IcpProfile) {
    setDraft(null);
    setSelectedId(p.id);
  }

  function handleNew() {
    setDraft({
      ...EMPTY_PROFILE,
      id: "draft",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      icpScoreAvg: 0,
      prospectCount: 0,
    });
    setSelectedId(null);
  }

  function handleSave() {
    if (!selected) return;
    if (!selected.name.trim()) {
      toast.error("Profile name is required");
      return;
    }
    saveMutation.mutate(selected);
  }

  function patch<K extends keyof IcpProfile>(key: K, value: IcpProfile[K]) {
    if (!selected) return;
    const target = draft ?? selected;
    setDraft({ ...target, [key]: value, updatedAt: new Date().toISOString() });
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="ICP Profiles"
        description="Define, score, and refine your Ideal Customer Profiles. AI Suggest and Auto-Discover accelerate profile creation."
        actions={
          <Button size="sm" onClick={handleNew}>
            <Plus className="h-4 w-4" />
            New Profile
          </Button>
        }
      />

      {listQuery.isError ? (
        <Card className="mt-6">
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Failed to load ICP profiles. Please try again.
            </p>
            <Button
              onClick={() => listQuery.refetch()}
              className="mt-4"
            >
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : (
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* Left list */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">Profiles</CardTitle>
            <CardDescription>{profiles.length} configured</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {listQuery.isLoading ? (
              <div className="space-y-2 p-4">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-16 animate-pulse rounded-md bg-muted" />
                ))}
              </div>
            ) : profiles.length === 0 ? (
              <EmptyState
                icon={<Target className="h-6 w-6" />}
                title="No ICP profiles yet"
                description="Create one to start sourcing prospects."
              />
            ) : (
              <ul className="divide-y">
                {pageItems.map((p) => {
                  const active = (draft?.id === p.id) || (!draft && selectedId === p.id);
                  return (
                    <li key={p.id}>
                      <button
                        type="button"
                        onClick={() => handleSelect(p)}
                        className={cn(
                          "flex w-full flex-col gap-1 p-4 text-left transition-colors hover:bg-muted/50",
                          active && "bg-muted",
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-sm font-medium">{p.name}</p>
                          <Badge variant="secondary">{p.prospectCount}</Badge>
                        </div>
                        <p className="truncate text-xs text-muted-foreground">
                          {p.targetSegment}
                        </p>
                        <div className="flex items-center gap-2">
                          <Progress value={(p.icpScoreAvg ?? 0) * 100} className="h-1.5" />
                          <span className="text-xs font-medium text-muted-foreground">
                            {formatPercent(p.icpScoreAvg ?? 0)}
                          </span>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
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

        {/* Right detail */}
        {selected ? (
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <CardTitle className="flex items-center gap-2">
                    <Pencil className="h-4 w-4" />
                    {selected.name || "Untitled Profile"}
                  </CardTitle>
                  <CardDescription>
                    Updated {timeAgo(selected.updatedAt)} · {selected.prospectCount} prospects · avg ICP{" "}
                    {formatPercent(selected.icpScoreAvg ?? 0)}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleSave}
                    disabled={saveMutation.isPending}
                  >
                    {saveMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Save
                  </Button>
                  {selected.id !== "draft" && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => setDeleteTarget(selected)}
                          aria-label="Delete profile"
                        >
                          <Trash2 className="h-4 w-4 text-red-600" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete profile</TooltipContent>
                    </Tooltip>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="profile">
                <TabsList>
                  <TabsTrigger value="profile">Profile</TabsTrigger>
                  <TabsTrigger value="scoring">Scoring</TabsTrigger>
                  <TabsTrigger value="signals">Signals</TabsTrigger>
                </TabsList>

                {/* Profile tab */}
                <TabsContent value="profile" className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="name">Name</Label>
                      <Input
                        id="name"
                        value={selected.name}
                        onChange={(e) => patch("name", e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="targetSegment">Target Segment</Label>
                      <Input
                        id="targetSegment"
                        value={selected.targetSegment}
                        onChange={(e) => patch("targetSegment", e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="industry">Industry</Label>
                      <Input
                        id="industry"
                        value={selected.industry}
                        onChange={(e) => patch("industry", e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="companySize">Company Size</Label>
                      <Input
                        id="companySize"
                        value={selected.companySize}
                        onChange={(e) => patch("companySize", e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <InfoLabel
                        htmlFor="seniority"
                        label="Seniority Tier"
                        info="Which seniority level to target: C-Suite = C-level execs (CEO/CTO/CRO), Director = VP/Director层, IC = Individual Contributors (SDRs/AEs/PMs)."
                      />
                      <select
                        id="seniority"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        value={selected.seniority}
                        onChange={(e) => patch("seniority", e.target.value as SeniorityTier)}
                      >
                        <option value="C_Suite">C-Suite</option>
                        <option value="Director">Director</option>
                        <option value="IC">IC</option>
                      </select>
                    </div>
                  </div>

                  <Separator />

                  {/* AI tools */}
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="rounded-md border p-4 space-y-3">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-amber-500" />
                        <p className="text-sm font-medium">AI Suggest</p>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Describe the ICP in plain English. OUTRENA fills the form.
                      </p>
                      <Textarea
                        rows={3}
                        placeholder="e.g. Heads of RevOps at US-based B2B SaaS, 50–500 employees, Series A+"
                        value={seedDesc}
                        onChange={(e) => setSeedDesc(e.target.value)}
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        className="w-full"
                        disabled={!seedDesc.trim() || suggestMutation.isPending}
                        onClick={() => suggestMutation.mutate(seedDesc)}
                      >
                        {suggestMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                        Suggest Profile
                      </Button>
                    </div>

                    <div className="rounded-md border p-4 space-y-3">
                      <div className="flex items-center gap-2">
                        <Globe className="h-4 w-4 text-emerald-600" />
                        <p className="text-sm font-medium">Auto-Discover</p>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Paste a company URL. OUTRENA infers an ICP from public data.
                      </p>
                      <Input
                        placeholder="https://acme.com"
                        value={discoverUrl}
                        onChange={(e) => setDiscoverUrl(e.target.value)}
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        className="w-full"
                        disabled={!discoverUrl.trim() || discoverMutation.isPending}
                        onClick={() => discoverMutation.mutate(discoverUrl)}
                      >
                        {discoverMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Globe className="h-4 w-4" />
                        )}
                        Discover Profile
                      </Button>
                    </div>
                  </div>
                </TabsContent>

                {/* Scoring tab */}
                <TabsContent value="scoring" className="space-y-4">
                  <InfoLabel
                    label="ICP Score Weights"
                    info="Weight each dimension (should sum to 100). ICP score = weighted average of: industry match, company size match, seniority match, intent signal strength, and engagement history."
                  />
                  <div className="space-y-3">
                    {(Object.keys(selected.scoreWeights) as (keyof ScoreWeights)[]).map((key) => (
                      <div key={key} className="grid grid-cols-[140px_1fr_60px] items-center gap-3">
                        <Label className="capitalize">{key}</Label>
                        <input
                          type="range"
                          min={0}
                          max={50}
                          value={selected.scoreWeights[key]}
                          onChange={(e) =>
                            patch("scoreWeights", {
                              ...selected.scoreWeights,
                              [key]: Number(e.target.value),
                            })
                          }
                          className="w-full"
                        />
                        <span className="text-right text-sm font-medium">
                          {selected.scoreWeights[key]}
                        </span>
                      </div>
                    ))}
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Total weight</span>
                    <Badge
                      variant={
                        totalWeight(selected.scoreWeights) === 100 ? "success" : "warning"
                      }
                    >
                      {totalWeight(selected.scoreWeights)} / 100
                    </Badge>
                  </div>
                </TabsContent>

                {/* Signals tab */}
                <TabsContent value="signals" className="space-y-4">
                  <SignalEditor
                    title="Pain Points"
                    items={selected.painPoints}
                    onChange={(items) => patch("painPoints", items)}
                    placeholder="e.g. SDR ramp time too long"
                  />
                  <SignalEditor
                    title="Buying Signals"
                    items={selected.buyingSignals}
                    onChange={(items) => patch("buyingSignals", items)}
                    placeholder="e.g. Hiring SDRs in last 90d"
                  />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0">
              <EmptyState
                icon={<Users className="h-6 w-6" />}
                title="Select a profile"
                description="Pick a profile on the left, or create a new one to get started."
                action={
                  <Button size="sm" onClick={handleNew}>
                    <Plus className="h-4 w-4" />
                    New Profile
                  </Button>
                }
              />
            </CardContent>
          </Card>
        )}
      </div>
      )}

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete ICP profile?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.name
              ? `Profile "${deleteTarget.name}" will be permanently removed. Prospects linked to this profile will lose their ICP scoring. This action cannot be undone.`
              : "This ICP profile will be permanently removed. This action cannot be undone."}
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
    </div>
  );
}

/* ── Subcomponents ─────────────────────────────────────────────────── */

function SignalEditor({
  title,
  items,
  onChange,
  placeholder,
}: {
  title: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");
  function add() {
    const v = draft.trim();
    if (!v) return;
    onChange([...items, v]);
    setDraft("");
  }
  return (
    <div className="space-y-2">
      <Label>{title}</Label>
      <div className="flex gap-2">
        <Input
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button size="sm" variant="outline" onClick={add} type="button">
          <Plus className="h-4 w-4" />
          Add
        </Button>
      </div>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li
            key={`${item}-${i}`}
            className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-1.5 text-sm"
          >
            <span>{item}</span>
            <button
              type="button"
              className="text-muted-foreground hover:text-red-600"
              onClick={() => onChange(items.filter((_, idx) => idx !== i))}
              aria-label={`Remove ${item}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function urlOrDomain(input: string): string {
  try {
    const u = new URL(input);
    return u.hostname;
  } catch {
    return input;
  }
}

function totalWeight(w: ScoreWeights): number {
  return Object.values(w).reduce((s, n) => s + n, 0);
}

function stripPersisted(p: IcpProfile): Omit<IcpProfile, "id" | "createdAt" | "updatedAt"> {
  const { id: _id, createdAt: _c, updatedAt: _u, ...rest } = p;
  void _id; void _c; void _u;
  return rest;
}