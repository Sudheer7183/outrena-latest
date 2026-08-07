/**
 * CollateralsPage.tsx — OUTRENA Phase 4 (Task 3-C)
 *
 * Collaterals (case studies, whitepapers, demos, one-pagers) CRUD + campaign
 * linking. Table + add dialog + per-row link-to-campaign dialog.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Link2,
  MoreHorizontal,
  Paperclip,
  Plus,
  Search,
  Trash2,
  Unlink,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { ErrorState } from "@/components/ui/error-state";
import { Pagination, usePagination } from "@/components/ui/pagination";
import { formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { PageHeader } from "@/components/ui/page-header";
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

/* ── Types & mocks ──────────────────────────────────────────────────────── */

type CollateralType = "case_study" | "whitepaper" | "demo" | "one_pager";

interface Collateral {
  id: string;
  name: string;
  type: CollateralType;
  url: string;
  industry: string | null;
  linkedCampaigns: { id: string; name: string }[];
  createdAt: string;
  updatedAt: string;
}

interface CampaignLite {
  id: string;
  name: string;
}

const TYPES: CollateralType[] = ["case_study", "whitepaper", "demo", "one_pager"];

const TYPE_VARIANT: Record<CollateralType, "default" | "secondary" | "outline" | "success"> = {
  case_study: "success",
  whitepaper: "default",
  demo: "secondary",
  one_pager: "outline",
};

const MOCK_CAMPAIGNS: CampaignLite[] = [
  { id: "c1", name: "Q1 Outbound — Fintech Ops" },
  { id: "c2", name: "Cybersec SOC Automation" },
  { id: "c3", name: "Healthcare Payer RPA" },
  { id: "c4", name: "Manufacturing Supply-Chain" },
];

const MOCK_COLLATERALS: Collateral[] = [
  {
    id: "col1",
    name: "Northbeam Case Study — 60% Faster Close",
    type: "case_study",
    url: "https://assets.outrena.io/case-studies/northbeam.pdf",
    industry: "Fintech",
    linkedCampaigns: [{ id: "c1", name: "Q1 Outbound — Fintech Ops" }],
    createdAt: "2024-11-10T10:00:00Z",
    updatedAt: "2024-12-15T14:00:00Z",
  },
  {
    id: "col2",
    name: "AI Reconciliation Whitepaper",
    type: "whitepaper",
    url: "https://assets.outrena.io/whitepapers/ai-reconciliation.pdf",
    industry: "Fintech",
    linkedCampaigns: [{ id: "c1", name: "Q1 Outbound — Fintech Ops" }],
    createdAt: "2024-10-05T09:00:00Z",
    updatedAt: "2024-12-01T12:00:00Z",
  },
  {
    id: "col3",
    name: "OUTRENA Product Demo (5 min)",
    type: "demo",
    url: "https://assets.outrena.io/demos/5min-overview.mp4",
    industry: null,
    linkedCampaigns: [
      { id: "c1", name: "Q1 Outbound — Fintech Ops" },
      { id: "c2", name: "Cybersec SOC Automation" },
    ],
    createdAt: "2024-09-20T08:00:00Z",
    updatedAt: "2024-11-25T15:00:00Z",
  },
  {
    id: "col4",
    name: "SOC Automation One-Pager",
    type: "one_pager",
    url: "https://assets.outrena.io/one-pagers/soc-automation.pdf",
    industry: "Cybersecurity",
    linkedCampaigns: [{ id: "c2", name: "Cybersec SOC Automation" }],
    createdAt: "2024-08-12T11:00:00Z",
    updatedAt: "2024-11-01T09:00:00Z",
  },
  {
    id: "col5",
    name: "Payer RPA ROI Calculator",
    type: "demo",
    url: "https://assets.outrena.io/demos/payer-roi-calc.html",
    industry: "Healthcare",
    linkedCampaigns: [],
    createdAt: "2024-12-01T13:00:00Z",
    updatedAt: "2024-12-20T10:00:00Z",
  },
  {
    id: "col6",
    name: "Supply-Chain Resilience Brief",
    type: "whitepaper",
    url: "https://assets.outrena.io/whitepapers/supply-chain.pdf",
    industry: "Manufacturing",
    linkedCampaigns: [{ id: "c4", name: "Manufacturing Supply-Chain" }],
    createdAt: "2024-11-18T16:00:00Z",
    updatedAt: "2024-12-22T11:30:00Z",
  },
];

/* ── Page ───────────────────────────────────────────────────────────────── */

export function CollateralsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [addOpen, setAddOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Collateral | null>(null);
  const [linkTarget, setLinkTarget] = useState<Collateral | null>(null);
  const [linkCampaignId, setLinkCampaignId] = useState("");

  const [form, setForm] = useState<{ name: string; type: CollateralType; url: string; industry: string }>({
    name: "",
    type: "case_study",
    url: "",
    industry: "",
  });

  const { data: apiCampaigns } = useQuery<CampaignLite[]>({
    queryKey: ["campaigns"],
    queryFn: () => http.get<any>("/api/v1/campaigns")
      .then((r: any) => Array.isArray(r) ? r : (r?.items ?? [])),
    retry: false,
  });
  const campaigns = apiCampaigns ?? MOCK_CAMPAIGNS;

  const { data: apiCollaterals, isLoading , isError, error, refetch } = useQuery({
    queryKey: ["collaterals"],
    queryFn: () => http.get<Collateral[]>("/api/v1/collaterals"),
    retry: false,
  });
  const collaterals = apiCollaterals ?? MOCK_COLLATERALS;

  const filtered = collaterals.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === "all" || c.type === typeFilter;
    return matchesSearch && matchesType;
  });


  const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: filtered, initialPageSize: 15 });

  const createMut = useMutation({
    mutationFn: (body: { name: string; type: CollateralType; url: string; industry: string }) =>
      http.post<Collateral>("/api/v1/collaterals", body),
    onSuccess: () => {
      toast.success("Collateral added");
      qc.invalidateQueries({ queryKey: ["collaterals"] });
      setAddOpen(false);
      setForm({ name: "", type: "case_study", url: "", industry: "" });
    },
    onError: () => toast.error("Failed to add collateral"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete<{ message: string }>(`/api/v1/collaterals/${id}`),
    onSuccess: () => {
      toast.success("Collateral deleted");
      qc.invalidateQueries({ queryKey: ["collaterals"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete collateral"),
  });

  const linkMut = useMutation({
    mutationFn: ({ collateralId, campaignId }: { collateralId: string; campaignId: string }) =>
      http.post<{ linkId: string }>("/api/v1/collaterals/link", { collateralId, campaignId }),
    onSuccess: () => {
      toast.success("Collateral linked to campaign");
      qc.invalidateQueries({ queryKey: ["collaterals"] });
      setLinkTarget(null);
      setLinkCampaignId("");
    },
    onError: () => toast.error("Failed to link collateral"),
  });

  function handleAdd() {
    if (!form.name.trim() || !form.url.trim()) {
      toast.error("Name and URL are required");
      return;
    }
    createMut.mutate(form);
  }

  function handleLink() {
    if (!linkTarget || !linkCampaignId) {
      toast.error("Pick a campaign to link");
      return;
    }
    linkMut.mutate({ collateralId: linkTarget.id, campaignId: linkCampaignId });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Collaterals"
        description="Case studies, whitepapers, demos, and one-pagers — linked to campaigns for personalisation."
        actions={
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" /> Add Collateral
          </Button>
        }
      />

{/* Task 2-b finding 14: explicit error + retry state */}
        {isError ? (
          <ErrorState
            title="Failed to load collaterals"
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
                placeholder="Search collaterals…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="sm:w-44"
            >
              <option value="all">All types</option>
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace("_", " ")}
                </option>
              ))}
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
              icon={<Paperclip className="h-6 w-6" />}
              title="No collaterals found"
              description="Add your first collateral to start linking it to campaigns."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Industry</TableHead>
                  <TableHead>URL</TableHead>
                  <TableHead className="text-right">Linked campaigns</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageItems.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell>
                      <Badge variant={TYPE_VARIANT[c.type]}>
                        {c.type.replace("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell>{c.industry ?? "—"}</TableCell>
                    <TableCell className="max-w-[16rem]">
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noreferrer"
                        className="truncate text-primary underline-offset-4 hover:underline"
                      >
                        {c.url}
                      </a>
                    </TableCell>
                    <TableCell className="text-right">
                      {(c.linkedCampaigns ?? []).length === 0 ? (  /* BUG-20 FIX */
                        <span className="text-muted-foreground">0</span>
                      ) : (
                        <Badge variant="secondary">{(c.linkedCampaigns ?? []).length}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(c.updatedAt)}</TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" aria-label="Row actions">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                          </TooltipTrigger>
                          <TooltipContent>More actions for this collateral</TooltipContent>
                        </Tooltip>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Actions</DropdownMenuLabel>
                          <DropdownMenuItem
                            onClick={() => {
                              setLinkTarget(c);
                              setLinkCampaignId("");
                            }}
                          >
                            <Link2 className="h-4 w-4" /> Link to Campaign
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem destructive onClick={() => setDeleteTarget(c)}>
                            <Trash2 className="h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
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

      {/* Add Collateral dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogClose onClose={() => setAddOpen(false)} />
        <DialogHeader>
          <DialogTitle>Add Collateral</DialogTitle>
          <DialogDescription>
            Add a case study, whitepaper, demo, or one-pager to your library.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="col-name">Name</Label>
            <Input
              id="col-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Northbeam Case Study"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="col-type">Type</Label>
              <Select
                id="col-type"
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value as CollateralType })}
              >
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace("_", " ")}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="col-industry">Industry (optional)</Label>
              <Input
                id="col-industry"
                value={form.industry}
                onChange={(e) => setForm({ ...form, industry: e.target.value })}
                placeholder="Fintech"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="col-url">URL</Label>
            <Input
              id="col-url"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              placeholder="https://assets.outrena.io/…"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setAddOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleAdd} disabled={createMut.isPending}>
            {createMut.isPending ? "Adding…" : "Add Collateral"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Delete dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete collateral?</DialogTitle>
          <DialogDescription>
            “{deleteTarget?.name}” will be removed from your library and unlinked from all campaigns.
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

      {/* Link dialog */}
      <Dialog open={!!linkTarget} onOpenChange={(o) => !o && setLinkTarget(null)}>
        <DialogClose onClose={() => setLinkTarget(null)} />
        <DialogHeader>
          <DialogTitle>Link to Campaign</DialogTitle>
          <DialogDescription>
            {linkTarget && `Linking “${linkTarget.name}” — pick a campaign.`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {linkTarget && (linkTarget.linkedCampaigns ?? []).length > 0 && (  /* BUG-20 FIX */
            <div className="rounded-md border bg-muted/30 p-3">
              <p className="mb-2 text-xs font-medium text-muted-foreground">
                Currently linked to
              </p>
              <div className="flex flex-wrap gap-1.5">
                {linkTarget.linkedCampaigns.map((lc) => (
                  <Badge key={lc.id} variant="secondary" className="gap-1">
                    <Unlink className="h-3 w-3" />
                    {lc.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="link-camp">Campaign</Label>
            <Select
              id="link-camp"
              value={linkCampaignId}
              onChange={(e) => setLinkCampaignId(e.target.value)}
            >
              <option value="">— Select campaign —</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setLinkTarget(null)}>
            Cancel
          </Button>
          <Button onClick={handleLink} disabled={linkMut.isPending}>
            {linkMut.isPending ? (
              <>
                <FileText className="h-4 w-4 animate-spin" /> Linking…
              </>
            ) : (
              <>
                <Link2 className="h-4 w-4" /> Link
              </>
            )}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}