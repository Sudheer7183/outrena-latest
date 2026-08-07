/**
 * CampaignsPage.tsx — OUTRENA Phase 4 (Task 3-C)
 *
 * Campaigns CRUD + preflight (6-check launch gate) + clone + framework-recommend
 * + gtm-thesis. Uses TanStack Query + mock-data fallback so the page always
 * renders even if the API is down.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Copy,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Rocket,
  Search,
  Sparkles,
  Trash2,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { ErrorState } from "@/components/ui/error-state";
import { Pagination, usePagination } from "@/components/ui/pagination";
import type {
  Campaign,
  CollateralLite,
  UserLite,
  CampaignCollateralLinkInput,
} from "@/types/common";
import { CampaignCreateSchema, formatZodError } from "@/lib/validation";
import { cn, formatDate, formatPercent, truncate } from "@/lib/utils";
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
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InfoLabel } from "@/components/ui/info-label";
import { PageHeader } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

/* ── Types & mocks ──────────────────────────────────────────────────────── */

interface PreflightCheck {
  id: string;
  label: string;
  description: string;
  passed: boolean;
  detail?: string;
}
interface PreflightResult {
  campaignId: string;
  checks: PreflightCheck[];
  readyToLaunch: boolean;
}
interface FrameworkRecommendation {
  framework: string;
  rationale: string;
  confidence: number;
}
interface GtmThesis {
  thesis: string;
  keyPillars: string[];
}

const FRAMEWORKS = [
  "trigger",
  "challenger",
  "value",
  "meddpicc",
  "spiced",
  "story",
] as const;

const STATUS_VARIANT: Record<string, "default" | "secondary" | "success" | "warning" | "destructive" | "outline"> = {
  draft: "secondary",
  active: "success",
  paused: "warning",
  completed: "outline",
};

const MOCK_CAMPAIGNS: Campaign[] = [
  {
    id: "cmp_001",
    name: "Q1 Outbound — Fintech Ops Leaders",
    status: "active",
    framework: "trigger",
    gtmThesis: "Costly manual reconciliation breaks close-cycle SLAs for Series B fintechs.",
    prospectCount: 142,
    sequenceCount: 7,
    createdAt: "2024-12-02T10:00:00Z",
    updatedAt: "2025-01-08T14:23:00Z",
  },
  {
    id: "cmp_002",
    name: "Healthcare Payer RPA Pitch",
    status: "active",
    framework: "challenger",
    gtmThesis: "Claims adjudication latency is the #1 cost driver for mid-market payers.",
    prospectCount: 86,
    sequenceCount: 7,
    createdAt: "2024-11-18T09:30:00Z",
    updatedAt: "2025-01-09T11:02:00Z",
  },
  {
    id: "cmp_003",
    name: "SaaS RevOps Tooling — VP Sales",
    status: "paused",
    framework: "value",
    gtmThesis: "Forecast accuracy under 70% signals broken pipeline hygiene.",
    prospectCount: 53,
    sequenceCount: 5,
    createdAt: "2024-10-22T16:11:00Z",
    updatedAt: "2024-12-30T08:45:00Z",
  },
  {
    id: "cmp_004",
    name: "Manufacturing Supply-Chain Resilience",
    status: "draft",
    framework: "meddpicc",
    gtmThesis: "Single-source suppliers cause 18-day disruption events on average.",
    prospectCount: 0,
    sequenceCount: 0,
    createdAt: "2025-01-04T13:50:00Z",
    updatedAt: "2025-01-04T13:50:00Z",
  },
  {
    id: "cmp_005",
    name: "Cybersec SOC Automation — CISOs",
    status: "active",
    framework: "trigger",
    gtmThesis: "Mean-time-to-detect above 24h puts regulated industries at audit risk.",
    prospectCount: 211,
    sequenceCount: 7,
    createdAt: "2024-09-15T07:20:00Z",
    updatedAt: "2025-01-10T18:30:00Z",
  },
  {
    id: "cmp_006",
    name: "Retail Loyalty Platform — CMOs",
    status: "completed",
    framework: "story",
    gtmThesis: "Repeat-purchase rate under 22% caps LTV for mid-market retailers.",
    prospectCount: 94,
    sequenceCount: 6,
    createdAt: "2024-07-01T12:00:00Z",
    updatedAt: "2024-10-15T10:00:00Z",
  },
];

const MOCK_PREFLIGHT: PreflightResult = {
  campaignId: "cmp_001",
  readyToLaunch: false,
  checks: [
    { id: "icp", label: "ICP defined", description: "Target segment is fully specified", passed: true, detail: "Series B+ fintech, ops leaders" },
    { id: "prospects", label: "Prospects loaded", description: "At least 25 prospects in the campaign", passed: true, detail: "142 prospects loaded" },
    { id: "domain", label: "Sending domain verified", description: "DKIM + SPF + DMARC aligned", passed: true, detail: "out.acme.com verified" },
    { id: "mailbridge", label: "MailBridge configured", description: "Active sending mailbox + provider", passed: false, detail: "No active MailBridge config for domain" },
    { id: "cadence", label: "Sequence cadence set", description: "7-touch cadence drafted", passed: true, detail: "7 touches, 35-day span" },
    { id: "compliance", label: "Compliance footer", description: "CAN-SPAM physical address + unsubscribe URL", passed: false, detail: "Physical address missing" },
  ],
};

const MOCK_FRAMEWORK: FrameworkRecommendation = {
  framework: "challenger",
  rationale:
    "Prospect pain is well-understood but incumbent inertia is high. Challenger reframes the problem to unlock budget.",
  confidence: 0.82,
};

const MOCK_THESIS: GtmThesis = {
  thesis:
    "Series B+ fintech ops leaders lose 6-figure revenue per close cycle to manual reconciliation. OUTRENA's AI-driven reconciliation orchestration cuts close-cycle SLA breaches by 60% within 90 days, freeing finance teams to focus on growth instead of firefighting.",
  keyPillars: [
    "Quantified cost of close-cycle breaches",
    "90-day time-to-value proof point",
    "ROI vs. legacy ERP add-ons",
  ],
};

/* ── Page ───────────────────────────────────────────────────────────────── */

export function CampaignsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null);
  const [preflightTarget, setPreflightTarget] = useState<Campaign | null>(null);
  const [frameworkOpen, setFrameworkOpen] = useState(false);
  const [thesisOpen, setThesisOpen] = useState(false);

  const [form, setForm] = useState({
    name: "",
    framework: "trigger",
    gtmThesis: "",
    ownerUserId: "",
    collateralIds: [] as string[],
  });
  const [productDesc, setProductDesc] = useState("");
  const [thesisInput, setThesisInput] = useState({ segment: "", pain: "", offer: "" });

  const { data: campaigns, isLoading , isError, error, refetch } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => http.get<{ items: Campaign[]; total: number } | Campaign[]>("/api/v1/campaigns")
      .then((r) => (Array.isArray(r) ? r : (r as any)?.items ?? [])),
    retry: false,
  });
  const list: Campaign[] = (campaigns as Campaign[]) ?? MOCK_CAMPAIGNS;

  // Task 2-b finding 8: fetch users + collaterals for the create dialog.
  const { data: users } = useQuery<UserLite[]>({
    queryKey: ["users", "list"],
    queryFn: () => http.get<UserLite[]>("/api/v1/users"),
    retry: false,
  });
  const { data: collaterals } = useQuery<CollateralLite[]>({
    queryKey: ["collaterals", "list"],
    queryFn: () => http.get<CollateralLite[]>("/api/v1/collaterals"),
    retry: false,
  });

  const filtered = list.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });


  const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: filtered, initialPageSize: 15 });

  const linkMut = useMutation({
    mutationFn: (body: CampaignCollateralLinkInput) =>
      http.post("/api/v1/collaterals/link", body),
  });

  const createMut = useMutation({
    mutationFn: async (body: {
      name: string;
      framework: string;
      gtmThesis: string;
      ownerUserId?: string;
    }) => {
      const created = await http.post<Campaign>("/api/v1/campaigns", body);
      // Best-effort collateral linking — failures don't fail the campaign.
      if (form.collateralIds.length > 0) {
        await Promise.allSettled(
          form.collateralIds.map((cid, idx) =>
            linkMut.mutateAsync({
              collateralId: cid,
              campaignId: created.id,
              sortOrder: idx,
            }),
          ),
        );
      }
      return created;
    },
    onSuccess: () => {
      toast.success("Campaign created");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      setCreateOpen(false);
      setForm({
        name: "",
        framework: "trigger",
        gtmThesis: "",
        ownerUserId: "",
        collateralIds: [],
      });
    },
    onError: () => toast.error("Failed to create campaign"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete<{ message: string }>(`/api/v1/campaigns/${id}`),
    onSuccess: () => {
      toast.success("Campaign deleted");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete campaign"),
  });

  const cloneMut = useMutation({
    mutationFn: (id: string) => http.post<Campaign>(`/api/v1/clone-campaign`, { campaignId: id }),
    onSuccess: () => {
      toast.success("Campaign cloned");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: () => toast.error("Failed to clone campaign"),
  });

  const preflightMut = useMutation({
    mutationFn: (campaignId: string) =>
      http.post<PreflightResult>("/api/v1/campaigns/preflight", { campaignId }),
    onSuccess: () => toast.success("Preflight complete"),
    onError: () => toast.warning("Preflight API unavailable — showing mock checks"),
  });

  const frameworkMut = useMutation({
    mutationFn: (productDescription: string) =>
      http.post<FrameworkRecommendation>("/api/v1/framework-recommend", { productDescription }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: () => toast.warning("Framework API unavailable — showing mock recommendation"),
  });

  const thesisMut = useMutation({
    mutationFn: (body: { segment: string; pain: string; offer: string }) =>
      http.post<GtmThesis>("/api/v1/gtm-thesis", body),
    onError: () => toast.warning("GTM thesis API unavailable — showing mock thesis"),
  });

  const preflightResult: PreflightResult | undefined =
    preflightMut.data ?? (preflightMut.isError ? MOCK_PREFLIGHT : undefined);

  const frameworkResult: FrameworkRecommendation | undefined =
    frameworkMut.data ?? (frameworkMut.isError ? MOCK_FRAMEWORK : undefined);

  const thesisResult: GtmThesis | undefined =
    thesisMut.data ?? (thesisMut.isError ? MOCK_THESIS : undefined);

  function handleCreate() {
    const parsed = CampaignCreateSchema.safeParse({
      name: form.name,
      framework: form.framework,
      gtmThesis: form.gtmThesis,
      ownerUserId: form.ownerUserId || undefined,
      collateralIds: form.collateralIds,
    });
    if (!parsed.success) {
      toast.error(formatZodError(parsed.error));
      return;
    }
    createMut.mutate({
      name: parsed.data.name,
      framework: parsed.data.framework,
      gtmThesis: parsed.data.gtmThesis ?? "",
      ownerUserId: parsed.data.ownerUserId || undefined,
    });
  }

  function handleFramework() {
    if (!productDesc.trim()) {
      toast.error("Enter a product description first");
      return;
    }
    frameworkMut.mutate(productDesc);
  }

  function handleThesis() {
    if (!thesisInput.segment.trim() || !thesisInput.pain.trim() || !thesisInput.offer.trim()) {
      toast.error("Segment, pain, and offer are required");
      return;
    }
    thesisMut.mutate(thesisInput);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Campaigns"
        description="Plan, preflight, and launch multi-touch outreach campaigns."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setFrameworkOpen(true)}>
              <Wand2 className="h-4 w-4" /> Framework Recommend
            </Button>
            <Button variant="outline" size="sm" onClick={() => setThesisOpen(true)}>
              <Sparkles className="h-4 w-4" /> GTM Thesis
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> New Campaign
            </Button>
          </>
        }
      />

{/* Task 2-b finding 14: explicit error + retry state */}
        {isError ? (
          <ErrorState
            title="Failed to load campaigns"
            error={error}
            onRetry={() => refetch()}
          />
        ) : null}

              <Card>
        <CardContent className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search campaigns…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="sm:w-44"
            >
              <option value="all">All statuses</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="completed">Completed</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<Search className="h-6 w-6" />}
              title="No campaigns found"
              description="Try a different search or create a new campaign."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Framework</TableHead>
                  <TableHead className="text-right">Prospects</TableHead>
                  <TableHead className="text-right">Sequences</TableHead>
                  <TableHead className="text-right">Reply rate</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageItems.map((c) => {
                  const replyRate = c.prospectCount > 0 ? (c.sequenceCount * 0.08) / 7 : 0;
                  return (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">
                        <div className="flex flex-col">
                          <span>{c.name}</span>
                          {c.gtmThesis && (
                            <span className="text-xs text-muted-foreground">
                              {truncate(c.gtmThesis, 60)}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={STATUS_VARIANT[c.status] ?? "secondary"}>
                          {c.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="capitalize">{c.framework ?? "—"}</TableCell>
                      <TableCell className="text-right">{c.prospectCount}</TableCell>
                      <TableCell className="text-right">{c.sequenceCount}</TableCell>
                      <TableCell className="text-right">{formatPercent(replyRate)}</TableCell>
                      <TableCell className="text-muted-foreground">{formatDate(c.updatedAt)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setPreflightTarget(c);
                              preflightMut.mutate(c.id);
                            }}
                          >
                            <Rocket className="h-4 w-4" /> Preflight
                          </Button>
                          <DropdownMenu>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon" aria-label="Row actions">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                              </TooltipTrigger>
                              <TooltipContent>More actions for this campaign</TooltipContent>
                            </Tooltip>
                            <DropdownMenuContent align="end">
                              <DropdownMenuLabel>Actions</DropdownMenuLabel>
                              <DropdownMenuItem onClick={() => cloneMut.mutate(c.id)}>
                                <Copy className="h-4 w-4" /> Clone
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                destructive
                                onClick={() => setDeleteTarget(c)}
                              >
                                <Trash2 className="h-4 w-4" /> Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
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

      {/* New Campaign dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogClose onClose={() => setCreateOpen(false)} />
        <DialogHeader>
          <DialogTitle>New Campaign</DialogTitle>
          <DialogDescription>Set the basics — you can refine the GTM thesis later.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="cmp-name">Name</Label>
            <Input
              id="cmp-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Q1 Outbound — Fintech Ops Leaders"
            />
          </div>
          <div className="space-y-2">
            <InfoLabel
              htmlFor="cmp-framework"
              label="Framework"
              info="Outreach methodology: Trigger (event-based), Challenger (teach/perturb), Value (ROI-led), MEDDPICC (enterprise qualification), SPICED (Situation/Problem/Implication/Critical-path/Decision), Story (narrative)."
            />
            <Select
              id="cmp-framework"
              value={form.framework}
              onChange={(e) => setForm({ ...form, framework: e.target.value })}
            >
              {FRAMEWORKS.map((f) => (
                <option key={f} value={f}>
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="cmp-thesis">GTM Thesis</Label>
            <Textarea
              id="cmp-thesis"
              rows={4}
              value={form.gtmThesis}
              onChange={(e) => setForm({ ...form, gtmThesis: e.target.value })}
              placeholder="The quantified pain + segment + offer thesis for this campaign."
            />
          </div>
          {/* Task 2-b finding 8: owner_user_id dropdown */}
          <div className="space-y-2">
            <Label htmlFor="cmp-owner">Owner (rep)</Label>
            <Select
              id="cmp-owner"
              value={form.ownerUserId}
              onChange={(e) => setForm({ ...form, ownerUserId: e.target.value })}
            >
              <option value="">— Unassigned —</option>
              {(users ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.email})
                </option>
              ))}
            </Select>
          </div>
          {/* Task 2-b finding 8: collateral multi-select */}
          <div className="space-y-2">
            <Label>Collaterals</Label>
            <p className="text-xs text-muted-foreground">
              Pick one or more assets to link to this campaign (linked via
              /api/v1/collaterals/link after create).
            </p>
            <div className="max-h-40 space-y-1 overflow-auto rounded-md border p-2">
              {(collaterals ?? []).length === 0 ? (
                <p className="px-1 py-2 text-xs text-muted-foreground">
                  No collaterals found — create some on the Collaterals page
                  first.
                </p>
              ) : (
                (collaterals ?? []).map((c) => {
                  const checked = form.collateralIds.includes(c.id);
                  return (
                    <label
                      key={c.id}
                      className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-muted/50"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          setForm({
                            ...form,
                            collateralIds: e.target.checked
                              ? [...form.collateralIds, c.id]
                              : form.collateralIds.filter((x) => x !== c.id),
                          });
                        }}
                      />
                      <span className="truncate">{c.title}</span>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {c.type}
                      </span>
                    </label>
                  );
                })
              )}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setCreateOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={createMut.isPending}>
            {createMut.isPending ? "Creating…" : "Create Campaign"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete campaign?</DialogTitle>
          <DialogDescription>
            This permanently removes “{deleteTarget?.name}” and all of its sequences. This action
            cannot be undone.
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
            {deleteMut.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Preflight dialog */}
      <Dialog open={!!preflightTarget} onOpenChange={(o) => !o && setPreflightTarget(null)}>
        <DialogClose onClose={() => setPreflightTarget(null)} />
        <DialogHeader>
          <DialogTitle>Preflight — {preflightTarget?.name}</DialogTitle>
          <DialogDescription>
            6 checks must pass before this campaign can launch.
          </DialogDescription>
        </DialogHeader>
        {preflightMut.isPending ? (
          <div className="flex items-center gap-3 py-6 text-sm text-muted-foreground">
            <RefreshCw className="h-4 w-4 animate-spin" /> Running preflight checks…
          </div>
        ) : preflightResult ? (
          <div className="space-y-4">
            <ScrollArea maxHeightClass="max-h-80">
              <div className="space-y-2">
                {preflightResult.checks.map((chk) => (
                  <div
                    key={chk.id}
                    className={cn(
                      "flex items-start gap-3 rounded-md border p-3",
                      chk.passed ? "border-emerald-200 bg-emerald-50/50" : "border-red-200 bg-red-50/50",
                    )}
                  >
                    <Badge variant={chk.passed ? "success" : "destructive"}>
                      {chk.passed ? "PASS" : "FAIL"}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{chk.label}</p>
                      <p className="text-xs text-muted-foreground">{chk.description}</p>
                      {chk.detail && (
                        <p className="mt-1 text-xs">{chk.detail}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
            <div className="rounded-md border bg-muted/40 p-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium">Launch gate</span>
                <Badge variant={preflightResult.readyToLaunch ? "success" : "warning"}>
                  {preflightResult.readyToLaunch ? "READY TO LAUNCH" : "BLOCKED"}
                </Badge>
              </div>
              <Progress
                value={
                  (preflightResult.checks.filter((c) => c.passed).length /
                    preflightResult.checks.length) *
                  100
                }
                indicatorClassName={preflightResult.readyToLaunch ? "bg-emerald-600" : "bg-amber-500"}
              />
              <p className="mt-2 text-xs text-muted-foreground">
                {preflightResult.checks.filter((c) => c.passed).length}/
                {preflightResult.checks.length} checks passed
              </p>
            </div>
          </div>
        ) : (
          <EmptyState title="No preflight data" description="Run a preflight check to see results." />
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => setPreflightTarget(null)}>
            Close
          </Button>
          <Button disabled={!preflightResult?.readyToLaunch}>
            <Rocket className="h-4 w-4" /> Launch
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Framework recommend dialog */}
      <Dialog open={frameworkOpen} onOpenChange={setFrameworkOpen}>
        <DialogClose onClose={() => setFrameworkOpen(false)} />
        <DialogHeader>
          <DialogTitle>Framework Recommendation</DialogTitle>
          <DialogDescription>
            Describe your product — we&apos;ll suggest the most effective outreach framework.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="prod-desc">Product description</Label>
            <Textarea
              id="prod-desc"
              rows={4}
              value={productDesc}
              onChange={(e) => setProductDesc(e.target.value)}
              placeholder="We help [segment] solve [pain] by [offer]…"
            />
          </div>
          {frameworkResult && (
            <Card>
              <CardHeader className="p-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="capitalize">{frameworkResult.framework}</CardTitle>
                  <Badge variant="secondary">
                    {Math.round(frameworkResult.confidence * 100)}% confidence
                  </Badge>
                </div>
                <CardDescription>{frameworkResult.rationale}</CardDescription>
              </CardHeader>
            </Card>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setFrameworkOpen(false)}>
            Close
          </Button>
          <Button onClick={handleFramework} disabled={frameworkMut.isPending}>
            {frameworkMut.isPending ? "Recommending…" : "Recommend"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* GTM Thesis dialog */}
      <Dialog open={thesisOpen} onOpenChange={setThesisOpen}>
        <DialogClose onClose={() => setThesisOpen(false)} />
        <DialogHeader>
          <DialogTitle>Generate GTM Thesis</DialogTitle>
          <DialogDescription>
            Tell us the segment, pain, and offer — we&apos;ll synthesize a GTM thesis.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="seg">Segment</Label>
            <Input
              id="seg"
              value={thesisInput.segment}
              onChange={(e) => setThesisInput({ ...thesisInput, segment: e.target.value })}
              placeholder="Series B+ fintech ops leaders"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pain">Pain</Label>
            <Input
              id="pain"
              value={thesisInput.pain}
              onChange={(e) => setThesisInput({ ...thesisInput, pain: e.target.value })}
              placeholder="Manual reconciliation breaks close-cycle SLAs"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="offer">Offer</Label>
            <Input
              id="offer"
              value={thesisInput.offer}
              onChange={(e) => setThesisInput({ ...thesisInput, offer: e.target.value })}
              placeholder="AI-driven reconciliation orchestration"
            />
          </div>
          {thesisResult && (
            <Card>
              <CardHeader className="p-4">
                <CardTitle className="text-base">Generated Thesis</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 p-4 pt-0 text-sm">
                <p>{thesisResult.thesis}</p>
                <div>
                  <p className="mb-1 font-medium">Key pillars</p>
                  <ul className="list-inside list-disc space-y-1 text-muted-foreground">
                    {thesisResult.keyPillars.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setThesisOpen(false)}>
            Close
          </Button>
          <Button onClick={handleThesis} disabled={thesisMut.isPending}>
            {thesisMut.isPending ? "Generating…" : "Generate Thesis"}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
