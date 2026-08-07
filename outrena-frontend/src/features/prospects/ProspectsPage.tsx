/**
 * ProspectsPage.tsx — Prospects CRUD + CSV import + enrich + email-validate
 * + AI features (Ultimate Profile, Lookalike, Hook Gen, Brief, NL Search).
 *
 * Table (search, icpScore range filter, seniority filter) → row click opens
 * detail dialog with intent signals. Add Prospect + Import CSV dialogs.
 * Enrich button per row → toast. Mock fallback so the page always renders.
 *
 * AI feature buttons per row open dedicated dialogs that POST to the
 * corresponding /api/v1/prospects/* endpoints and render structured results.
 * NL search bar above the table provides natural-language prospect search.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Upload,
  Sparkles,
  Mail,
  Search,
  Filter,
  Users,
  Loader2,
  Save,
  Trash2,
  Brain,
  UserSearch,
  MessageSquare,
  FileText,
  Languages,
  Copy,
  Check,
  Globe,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { ProspectImportSchema, formatZodError } from "@/lib/validation";
import { cn, formatPercent, timeAgo, truncate } from "@/lib/utils";
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
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
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
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
// import { Skeleton } from "@/components/ui/skeleton";
import type { Prospect, SeniorityTier } from "@/types/common";

/* ── Mock data ─────────────────────────────────────────────────────── */

const SENIORITY_BADGE: Record<SeniorityTier, "default" | "secondary" | "outline"> = {
  C_Suite: "default",
  Director: "secondary",
  IC: "outline",
};

const MOCK_PROSPECTS: Prospect[] = [
  mkP("p1", "Priya Shankar", "priya@ledgerline.io", "Ledgerline", "VP Sales", "C_Suite", 0.92, "tier1", ["Series B raise", "Hiring SDRs"]),
  mkP("p2", "Marcus Reuel", "marcus@vaultnode.com", "Vaultnode", "VP RevOps", "C_Suite", 0.88, "tier1", ["Posted on LinkedIn"]),
  mkP("p3", "Elena Voss", "elena@northbridgepay.com", "Northbridge Pay", "Head of Sales", "C_Suite", 0.85, "tier2", ["Hiring SDRs"]),
  mkP("p4", "Daniel Okoro", "daniel@swiftforge.dev", "SwiftForge", "Director of Engineering", "Director", 0.79, "tier1", ["GitHub activity", "KubeCon talk"]),
  mkP("p5", "Sara Lindqvist", "sara@blueharbor.io", "Blue Harbor", "Head of People Ops", "Director", 0.74, "tier2", ["Posted HR Ops role"]),
  mkP("p6", "Tom Bauermann", "tom@feldstein.co", "Feldstein", "RevOps Lead", "Director", 0.71, "tier1", ["Using Sales Navigator"]),
  mkP("p7", "Asha Patel", "asha@lumenkart.com", "LumenKart", "CMO", "C_Suite", 0.68, "tier2", ["Hiring growth team"]),
  mkP("p8", "Wei Chen", "wei@northpeak.dev", "NorthPeak", "Staff Engineer", "IC", 0.66, "tier1", ["Starred repos"]),
  mkP("p9", "Olivia Marchetti", "olivia@castellano.io", "Castellano", "VP Marketing", "C_Suite", 0.63, "tier2", []),
  mkP("p10", "Hugo Lefebvre", "hugo@maisonverte.fr", "Maison Verte", "Head of Growth", "Director", 0.59, "tier1", ["Funding announcement"]),
  mkP("p11", "Ingrid Solberg", "ingrid@fjordtech.no", "Fjord Tech", "SDR Manager", "Director", 0.55, "tier2", []),
  mkP("p12", "Raj Malhotra", "raj@spicelane.in", "Spice Lane", "Senior AE", "IC", 0.48, "tier1", ["Job change"]),
];

function mkP(
  id: string,
  name: string,
  email: string,
  company: string,
  title: string,
  seniority: SeniorityTier,
  icpScore: number,
  enrichmentTier: string,
  signals: string[],
): Prospect {
  return {
    id,
    name,
    email,
    company,
    title,
    linkedinUrl: `https://linkedin.com/in/${id}`,
    icpScore,
    seniority,
    enrichmentTier,
    intentSignals: JSON.stringify(signals),
    createdAt: "2025-01-01T10:00:00Z",
    updatedAt: new Date(Date.now() - Math.random() * 7 * 86400_000).toISOString(),
  };
}

/* ── Page ──────────────────────────────────────────────────────────── */

export function ProspectsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [scoreMin, setScoreMin] = useState(0);
  const [seniorityFilter, setSeniorityFilter] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [selectedProspect, setSelectedProspect] = useState<Prospect | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Prospect | null>(null);

  /* AI feature dialog state */
  const [ultimateProfileTarget, setUltimateProfileTarget] = useState<Prospect | null>(null);
  const [lookalikeTarget, setLookalikeTarget] = useState<Prospect | null>(null);
  const [hookGenTarget, setHookGenTarget] = useState<Prospect | null>(null);
  const [briefTarget, setBriefTarget] = useState<Prospect | null>(null);

  /* NL search state */
  const [nlQuery, setNlQuery] = useState("");
  const [nlSearchOpen, setNlSearchOpen] = useState(false);

  const listQuery = useQuery<Prospect[]>({
    queryKey: ["prospects"],
    queryFn: () => http.get<{ items: Prospect[]; total: number } | Prospect[]>("/api/v1/prospects")
      .then((r) => (Array.isArray(r) ? r : (r as any)?.items ?? [])),
  });
  const allProspects: Prospect[] = listQuery.data ?? MOCK_PROSPECTS;

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allProspects.filter((p) => {
      if (q && !`${p.name} ${p.email ?? ""} ${p.company ?? ""} ${p.title ?? ""}`.toLowerCase().includes(q)) {
        return false;
      }
      if ((p.icpScore ?? 0) < scoreMin / 100) return false;
      if (seniorityFilter !== "all" && p.seniority !== seniorityFilter) return false;
      return true;
    });
  }, [allProspects, search, scoreMin, seniorityFilter]);

  const pageSize = 20;
  const pageItems = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const hasNext = (page + 1) * pageSize < filtered.length;

  /* mutations */
  const enrichMutation = useMutation({
    mutationFn: (id: string) => http.post(`/api/v1/prospects/enrich`, { prospectId: id }),
    onSuccess: (_d, id) => {
      toast.success("Enrichment queued", { description: `Prospect ${id} queued for enrichment.` });
      qc.invalidateQueries({ queryKey: ["prospects"] });
    },
    onError: () => toast.error("Enrichment failed — backend unavailable"),
  });

  const validateMutation = useMutation({
    mutationFn: (email: string) => http.post(`/api/v1/prospects/email-validate`, { email }),
    onSuccess: () => toast.success("Email validated"),
    onError: () => toast.error("Validation failed — backend unavailable"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/prospects/${id}`),
    onSuccess: () => {
      toast.success("Prospect deleted");
      qc.invalidateQueries({ queryKey: ["prospects"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Delete failed — backend unavailable"),
  });

  const addMutation = useMutation({
    mutationFn: (body: Partial<Prospect>) => http.post<Prospect>("/api/v1/prospects", body),
    onSuccess: () => {
      toast.success("Prospect added");
      setAddOpen(false);
      qc.invalidateQueries({ queryKey: ["prospects"] });
    },
    onError: () => toast.error("Add failed — backend unavailable"),
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return http.post<{ imported: number }>(`/api/v1/csv-import`, fd);
    },
    onSuccess: (data) => {
      toast.success(`Imported ${data?.imported ?? 0} prospects`);
      setImportOpen(false);
      qc.invalidateQueries({ queryKey: ["prospects"] });
    },
    onError: () => toast.error("Import failed — backend unavailable"),
  });

  /* ── AI feature mutations ─────────────────────────────────────────── */

  const ultimateProfileMut = useMutation({
    mutationFn: (prospectId: string) =>
      http.post<UltimateProfileResult>("/api/v1/prospects/ultimate-profile", { prospect_id: prospectId }),
    onError: () => toast.error("Ultimate profile generation failed"),
  });

  const lookalikeMut = useMutation({
    mutationFn: (seedProspectId: string) =>
      http.post<LookalikeResult>("/api/v1/prospects/lookalike", { seed_prospect_id: seedProspectId }),
    onError: () => toast.error("Lookalike search failed"),
  });

  const hookGenMut = useMutation({
    mutationFn: (prospectId: string) =>
      http.post<HookGenResult>("/api/v1/prospects/hook-generator", { prospect_id: prospectId }),
    onError: () => toast.error("Hook generation failed"),
  });

  const briefMut = useMutation({
    mutationFn: (prospectId: string) =>
      http.post<ProspectBriefResult>("/api/v1/prospects/prospect-brief", { prospect_id: prospectId }),
    onError: () => toast.error("Brief generation failed"),
  });

  const nlSearchMut = useMutation({
    mutationFn: (query: string) =>
      http.post<NlSearchResult>("/api/v1/prospects/search-nl", { query }),
    onError: () => toast.error("Natural language search failed"),
  });

  function handleRowClick(p: Prospect) {
    setSelectedProspect(p);
  }

  if (listQuery.isError) {
    return (
      <div className="space-y-6 p-6">
        <PageHeader
          title="Prospects"
          description="Manage your prospect database, enrich, validate emails, and import via CSV."
        />
        <Card className="mt-6">
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Failed to load prospects. Please try again.
            </p>
            <Button
              onClick={() => listQuery.refetch()}
              className="mt-4"
            >
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Prospects"
        description="Manage your prospect database, enrich, validate emails, and import via CSV."
        actions={
          <>
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
              <Upload className="h-4 w-4" />
              Import CSV
            </Button>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" />
              Add Prospect
            </Button>
          </>
        }
      />

      {/* Natural Language Search */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Languages className="h-4 w-4" />
            Natural Language Search
          </CardTitle>
          <CardDescription>
            Describe the prospects you&apos;re looking for in plain English.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="e.g. VP of Sales at fintech startups who recently raised Series B"
                value={nlQuery}
                onChange={(e) => setNlQuery(e.target.value)}
                className="pl-9"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && nlQuery.trim()) {
                    nlSearchMut.mutate(nlQuery.trim());
                    setNlSearchOpen(true);
                  }
                }}
              />
            </div>
            <Button
              onClick={() => {
                if (!nlQuery.trim()) {
                  toast.error("Enter a search query");
                  return;
                }
                nlSearchMut.mutate(nlQuery.trim());
                setNlSearchOpen(true);
              }}
              disabled={nlSearchMut.isPending}
            >
              {nlSearchMut.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Brain className="h-4 w-4" />
              )}
              Search
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="search">Search</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Name, email, company, title…"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(0);
                  }}
                  className="pl-9"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="scoreMin">
                Min ICP Score: <span className="font-medium">{scoreMin}</span>
              </Label>
              <input
                id="scoreMin"
                type="range"
                min={0}
                max={100}
                value={scoreMin}
                onChange={(e) => {
                  setScoreMin(Number(e.target.value));
                  setPage(0);
                }}
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="seniority">Seniority</Label>
              <Select
                value={seniorityFilter}
                onValueChange={(v) => {
                  setSeniorityFilter(v);
                  setPage(0);
                }}
              >
                <SelectTrigger id="seniority" className="w-full">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="C_Suite">C-Suite</SelectItem>
                  <SelectItem value="Director">Director</SelectItem>
                  <SelectItem value="IC">IC</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {filtered.length} prospect{filtered.length === 1 ? "" : "s"}
          </CardTitle>
          <CardDescription>
            Showing {pageItems.length} of {filtered.length}. Click a row for details.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {listQuery.isLoading ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2, 3, 4].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded-md bg-muted" />
              ))}
            </div>
          ) : pageItems.length === 0 ? (
            <EmptyState
              icon={<Users className="h-6 w-6" />}
              title="No prospects match"
              description="Adjust filters or import a CSV to get started."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Seniority</TableHead>
                  <TableHead className="w-40">ICP Score</TableHead>
                  <TableHead>Enrichment</TableHead>
                  <TableHead>Next Touch</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageItems.map((p) => (
                  <TableRow
                    key={p.id}
                    className="cursor-pointer"
                    onClick={() => handleRowClick(p)}
                  >
                    <TableCell>
                      <div className="space-y-0.5">
                        <p className="font-medium">{p.name}</p>
                        <p className="text-xs text-muted-foreground">{p.email ?? "—"}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-0.5">
                        <p className="text-sm">{p.company ?? "—"}</p>
                        <p className="text-xs text-muted-foreground">{p.title ?? "—"}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      {p.seniority && (
                        <Badge variant={SENIORITY_BADGE[p.seniority]}>
                          {p.seniority === "C_Suite" ? "C-Suite" : p.seniority}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <Progress
                          value={(p.icpScore ?? 0) * 100}
                          indicatorClassName={
                            (p.icpScore ?? 0) >= 0.75
                              ? "bg-emerald-600"
                              : (p.icpScore ?? 0) >= 0.5
                                ? "bg-amber-500"
                                : "bg-red-500"
                          }
                        />
                        <span className="text-xs text-muted-foreground">
                          {formatPercent(p.icpScore ?? 0, 0)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.enrichmentTier === "tier1" ? "success" : "secondary"}>
                        {p.enrichmentTier ?? "—"}
                      </Badge>
                    </TableCell>
                    {/* Next Touch — Help Guide §Prospects: earliest Scheduled sequence */}
                    <TableCell className="text-xs text-muted-foreground">
                      {/* TODO: wire to /api/v1/prospects/next-touches when backend implements */}
                      —
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {timeAgo(p.updatedAt)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div
                        className="flex justify-end gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Ultimate Profile"
                              onClick={() => {
                                setUltimateProfileTarget(p);
                                ultimateProfileMut.mutate(p.id);
                              }}
                            >
                              <Brain className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Ultimate Profile</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Lookalike"
                              onClick={() => {
                                setLookalikeTarget(p);
                                lookalikeMut.mutate(p.id);
                              }}
                            >
                              <UserSearch className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Lookalike</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Hook Gen"
                              onClick={() => {
                                setHookGenTarget(p);
                                hookGenMut.mutate(p.id);
                              }}
                            >
                              <MessageSquare className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Hook Generator</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Brief"
                              onClick={() => {
                                setBriefTarget(p);
                                briefMut.mutate(p.id);
                              }}
                            >
                              <FileText className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Prospect Brief</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Enrich"
                              onClick={() => enrichMutation.mutate(p.id)}
                            >
                              {enrichMutation.isPending && enrichMutation.variables === p.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Sparkles className="h-4 w-4" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Enrich prospect</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Validate email"
                              disabled={!p.email}
                              onClick={() => p.email && validateMutation.mutate(p.email)}
                            >
                              <Mail className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Validate email</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Delete"
                              onClick={() => setDeleteTarget(p)}
                            >
                              <Trash2 className="h-4 w-4 text-red-600" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Delete prospect</TooltipContent>
                        </Tooltip>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
        {(filtered.length > pageSize || page > 0) && (
          <div className="flex items-center justify-between border-t p-4">
            <Button
              size="sm"
              variant="outline"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {page + 1} of {Math.max(1, Math.ceil(filtered.length / pageSize))}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={!hasNext}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </Card>

      {/* Detail dialog */}
      <ProspectDetailDialog
        prospect={selectedProspect}
        onClose={() => setSelectedProspect(null)}
        onEnrich={(id) => enrichMutation.mutate(id)}
      />

      {/* Add dialog */}
      <AddProspectDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onSubmit={(body) => addMutation.mutate(body)}
        isPending={addMutation.isPending}
      />

      {/* Import dialog */}
      <ImportCsvDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onSubmit={(file) => importMutation.mutate(file)}
        isPending={importMutation.isPending}
      />

      {/* Delete confirmation dialog — AlertDialog prevents click-outside dismissal
          so an accidental backdrop click won't lose the warning. */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete prospect?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget?.name
                ? `Prospect "${deleteTarget.name}"${deleteTarget.company ? ` at ${deleteTarget.company}` : ""} will be permanently removed. This action cannot be undone.`
                : "This prospect will be permanently removed. This action cannot be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                // Prevent auto-close so the dialog stays open while pending and
                // closes only via the mutation's onSuccess → setDeleteTarget(null).
                e.preventDefault();
                if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
              }}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Ultimate Profile Dialog */}
      <Dialog
        open={!!ultimateProfileTarget}
        onOpenChange={(o) => !o && setUltimateProfileTarget(null)}
      >
        {ultimateProfileTarget && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5" />
                Ultimate Profile — {ultimateProfileTarget.name}
              </DialogTitle>
              <DialogDescription>
                AI-generated deep profile for {ultimateProfileTarget.company ?? "—"}
              </DialogDescription>
            </DialogHeader>
            {ultimateProfileMut.isPending ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Generating profile…</span>
              </div>
            ) : ultimateProfileMut.isError ? (
              <div className="py-6 text-center text-sm text-destructive">
                Failed to generate profile. Please try again.
              </div>
            ) : ultimateProfileMut.data ? (
              <ScrollArea className="max-h-[60vh] pr-2">
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <DetailRow label="What they do" value={ultimateProfileMut.data.what_they_do ?? "—"} />
                    <DetailRow label="Target market" value={ultimateProfileMut.data.target_market ?? "—"} />
                    <DetailRow label="Company size" value={ultimateProfileMut.data.company_size ?? "—"} />
                    <DetailRow label="Industry" value={ultimateProfileMut.data.industry ?? "—"} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">Products</p>
                    <div className="flex flex-wrap gap-1">
                      {(ultimateProfileMut.data.products ?? []).length === 0 ? (
                        <span className="text-sm text-muted-foreground">—</span>
                      ) : (
                        ultimateProfileMut.data.products!.map((p: string) => (
                          <Badge key={p} variant="secondary" className="text-xs">{p}</Badge>
                        ))
                      )}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">Tech Stack</p>
                    <div className="flex flex-wrap gap-1">
                      {(ultimateProfileMut.data.tech_stack ?? []).length === 0 ? (
                        <span className="text-sm text-muted-foreground">—</span>
                      ) : (
                        ultimateProfileMut.data.tech_stack!.map((t: string) => (
                          <Badge key={t} variant="outline" className="text-xs">{t}</Badge>
                        ))
                      )}
                    </div>
                  </div>
                  <Separator />
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">Pain Points</p>
                    <ul className="ml-4 list-disc space-y-1 text-sm">
                      {(ultimateProfileMut.data.pain_points ?? []).length === 0 ? (
                        <li className="text-muted-foreground">—</li>
                      ) : (
                        ultimateProfileMut.data.pain_points!.map((pp: string, i: number) => (
                          <li key={i}>{pp}</li>
                        ))
                      )}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">Buying Signals</p>
                    <ul className="ml-4 list-disc space-y-1 text-sm">
                      {(ultimateProfileMut.data.buying_signals ?? []).length === 0 ? (
                        <li className="text-muted-foreground">—</li>
                      ) : (
                        ultimateProfileMut.data.buying_signals!.map((bs: string, i: number) => (
                          <li key={i}>{bs}</li>
                        ))
                      )}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">Competitors</p>
                    <ul className="ml-4 list-disc space-y-1 text-sm">
                      {(ultimateProfileMut.data.competitors ?? []).length === 0 ? (
                        <li className="text-muted-foreground">—</li>
                      ) : (
                        ultimateProfileMut.data.competitors!.map((c: string, i: number) => (
                          <li key={i}>{c}</li>
                        ))
                      )}
                    </ul>
                  </div>
                  <Separator />
                  <div className="space-y-2">
                    <div>
                      <p className="text-xs font-medium uppercase text-muted-foreground">ICP Fit Score</p>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={(ultimateProfileMut.data.icp_fit_score ?? 0) * 100}
                          className="h-2 flex-1"
                          indicatorClassName={
                            (ultimateProfileMut.data.icp_fit_score ?? 0) >= 0.75
                              ? "bg-emerald-600"
                              : (ultimateProfileMut.data.icp_fit_score ?? 0) >= 0.5
                                ? "bg-amber-500"
                                : "bg-red-500"
                          }
                        />
                        <span className="text-sm font-medium">
                          {formatPercent(ultimateProfileMut.data.icp_fit_score ?? 0, 0)}
                        </span>
                      </div>
                    </div>
                    <DetailRow label="Recommended Angle" value={ultimateProfileMut.data.recommended_angle ?? "—"} />
                    <div>
                      <p className="text-xs font-medium uppercase text-muted-foreground">Confidence Score</p>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={(ultimateProfileMut.data.confidence_score ?? 0) * 100}
                          className="h-2 flex-1"
                        />
                        <span className="text-sm font-medium">
                          {formatPercent(ultimateProfileMut.data.confidence_score ?? 0, 0)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </ScrollArea>
            ) : null}
            <DialogFooter>
              <DialogClose onClose={() => setUltimateProfileTarget(null)} />
            </DialogFooter>
          </>
        )}
      </Dialog>

      {/* Lookalike Dialog */}
      <Dialog
        open={!!lookalikeTarget}
        onOpenChange={(o) => !o && setLookalikeTarget(null)}
      >
        {lookalikeTarget && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <UserSearch className="h-5 w-5" />
                Lookalikes — {lookalikeTarget.name}
              </DialogTitle>
              <DialogDescription>
                Prospects similar to {lookalikeTarget.name} at {lookalikeTarget.company ?? "—"}
              </DialogDescription>
            </DialogHeader>
            {lookalikeMut.isPending ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Finding lookalikes…</span>
              </div>
            ) : lookalikeMut.isError ? (
              <div className="py-6 text-center text-sm text-destructive">
                Failed to find lookalikes. Please try again.
              </div>
            ) : lookalikeMut.data ? (
              <ScrollArea className="max-h-[60vh] pr-2">
                {(lookalikeMut.data.lookalikes ?? []).length === 0 ? (
                  <div className="py-6 text-center text-sm text-muted-foreground">
                    No lookalikes found.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Title</TableHead>
                        <TableHead>Company</TableHead>
                        <TableHead className="w-28">Similarity</TableHead>
                        <TableHead>Matched Features</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {lookalikeMut.data.lookalikes!.map((lk: LookalikeEntry, i: number) => (
                        <TableRow key={i}>
                          <TableCell className="font-medium">{lk.name ?? "—"}</TableCell>
                          <TableCell className="text-sm">{lk.title ?? "—"}</TableCell>
                          <TableCell className="text-sm">{lk.company ?? "—"}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1.5">
                              <Progress
                                value={(lk.similarity_score ?? 0) * 100}
                                className="h-2 w-14"
                                indicatorClassName={
                                  (lk.similarity_score ?? 0) >= 0.75
                                    ? "bg-emerald-600"
                                    : "bg-amber-500"
                                }
                              />
                              <span className="text-xs">
                                {formatPercent(lk.similarity_score ?? 0, 0)}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1">
                              {(lk.matched_features ?? []).map((f: string) => (
                                <Badge key={f} variant="secondary" className="text-[10px]">
                                  {f}
                                </Badge>
                              ))}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </ScrollArea>
            ) : null}
            <DialogFooter>
              <DialogClose onClose={() => setLookalikeTarget(null)} />
            </DialogFooter>
          </>
        )}
      </Dialog>

      {/* Hook Generator Dialog */}
      <Dialog
        open={!!hookGenTarget}
        onOpenChange={(o) => !o && setHookGenTarget(null)}
      >
        {hookGenTarget && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Hook Generator — {hookGenTarget.name}
              </DialogTitle>
              <DialogDescription>
                AI-generated outreach hooks for {hookGenTarget.company ?? "—"}
              </DialogDescription>
            </DialogHeader>
            {hookGenMut.isPending ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Generating hooks…</span>
              </div>
            ) : hookGenMut.isError ? (
              <div className="py-6 text-center text-sm text-destructive">
                Failed to generate hooks. Please try again.
              </div>
            ) : hookGenMut.data ? (
              <ScrollArea className="max-h-[60vh] pr-2">
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={hookGenMut.data.source === "llm" ? "default" : "secondary"}
                    >
                      {hookGenMut.data.source === "llm" ? "LLM" : "Fallback"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {hookGenMut.data.hooks?.length ?? 0} hooks generated
                    </span>
                  </div>
                  {(hookGenMut.data.hooks ?? []).map((hook: HookEntry, i: number) => (
                    <HookCard key={i} hook={hook} index={i + 1} />
                  ))}
                </div>
              </ScrollArea>
            ) : null}
            <DialogFooter>
              <DialogClose onClose={() => setHookGenTarget(null)} />
            </DialogFooter>
          </>
        )}
      </Dialog>

      {/* Prospect Brief Dialog */}
      <Dialog
        open={!!briefTarget}
        onOpenChange={(o) => !o && setBriefTarget(null)}
      >
        {briefTarget && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Prospect Brief — {briefTarget.name}
              </DialogTitle>
              <DialogDescription>
                AI-generated outreach brief for {briefTarget.company ?? "—"}
              </DialogDescription>
            </DialogHeader>
            {briefMut.isPending ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Generating brief…</span>
              </div>
            ) : briefMut.isError ? (
              <div className="py-6 text-center text-sm text-destructive">
                Failed to generate brief. Please try again.
              </div>
            ) : briefMut.data ? (
              <ScrollArea className="max-h-[60vh] pr-2">
                <div className="space-y-4">
                  <BriefSection title="Summary" content={briefMut.data.summary} />
                  <BriefSection title="Key Insights" items={briefMut.data.key_insights} />
                  <BriefSection title="Recommended Approach" content={briefMut.data.recommended_approach} />
                  <BriefSection title="Talking Points" items={briefMut.data.talking_points} />
                  <BriefSection title="Risk Factors" items={briefMut.data.risk_factors} />
                </div>
              </ScrollArea>
            ) : null}
            <DialogFooter>
              <DialogClose onClose={() => setBriefTarget(null)} />
            </DialogFooter>
          </>
        )}
      </Dialog>

      {/* NL Search Results Dialog */}
      <Dialog open={nlSearchOpen} onOpenChange={setNlSearchOpen}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Languages className="h-5 w-5" />
            Natural Language Search Results
          </DialogTitle>
          <DialogDescription>
            {nlQuery ? `Results for: "${nlQuery}"` : "Search results"}
          </DialogDescription>
        </DialogHeader>
        {nlSearchMut.isPending ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">Searching…</span>
          </div>
        ) : nlSearchMut.isError ? (
          <div className="py-6 text-center text-sm text-destructive">
            Search failed. Please try again.
          </div>
        ) : nlSearchMut.data ? (
          <ScrollArea className="max-h-[60vh] pr-2">
            <div className="space-y-4">
              {/* AI Interpretation */}
              {nlSearchMut.data.interpretation && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">AI Interpretation</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm">{nlSearchMut.data.interpretation}</p>
                  </CardContent>
                </Card>
              )}

              {/* DB Matches */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">
                    Database Matches ({(nlSearchMut.data.db_matches ?? []).length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  {(nlSearchMut.data.db_matches ?? []).length === 0 ? (
                    <p className="p-4 text-center text-sm text-muted-foreground">
                      No database matches found.
                    </p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Company</TableHead>
                          <TableHead>Title</TableHead>
                          <TableHead className="w-28">ICP Score</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {nlSearchMut.data.db_matches!.map((m: NlMatchEntry, i: number) => (
                          <TableRow key={i}>
                            <TableCell className="font-medium">{m.name ?? "—"}</TableCell>
                            <TableCell className="text-sm">{m.company ?? "—"}</TableCell>
                            <TableCell className="text-sm">{m.title ?? "—"}</TableCell>
                            <TableCell>
                              <span className="text-sm">
                                {formatPercent(m.icp_score ?? 0, 0)}
                              </span>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* Web Results */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">
                    Web Results ({(nlSearchMut.data.web_results ?? []).length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {(nlSearchMut.data.web_results ?? []).length === 0 ? (
                    <p className="text-center text-sm text-muted-foreground">
                      No web results found.
                    </p>
                  ) : (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {nlSearchMut.data.web_results!.map((w: NlWebResult, i: number) => (
                        <Card key={i} className="border-dashed">
                          <CardContent className="p-3">
                            <p className="text-sm font-medium">{w.title ?? "—"}</p>
                            <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                              {w.snippet ?? "—"}
                            </p>
                            {w.url && (
                              <a
                                href={w.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                              >
                                <Globe className="h-3 w-3" />
                                {truncate(w.url, 50)}
                              </a>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </ScrollArea>
        ) : null}
        <DialogFooter>
          <DialogClose onClose={() => setNlSearchOpen(false)} />
        </DialogFooter>
      </Dialog>
    </div>
  );
}

/* ── Subcomponents ─────────────────────────────────────────────────── */

function ProspectDetailDialog({
  prospect,
  onClose,
  onEnrich,
}: {
  prospect: Prospect | null;
  onClose: () => void;
  onEnrich: (id: string) => void;
}) {
  const signals: string[] = useMemo(() => {
    if (!prospect?.intentSignals) return [];
    try {
      const parsed = JSON.parse(prospect.intentSignals) as unknown;
      return Array.isArray(parsed) ? parsed.filter((s): s is string => typeof s === "string") : [];
    } catch {
      return [];
    }
  }, [prospect]);

  return (
    <Dialog open={!!prospect} onOpenChange={(o) => !o && onClose()}>
      {prospect && (
        <>
          <DialogHeader>
            <DialogTitle>{prospect.name}</DialogTitle>
            <DialogDescription>
              {prospect.title ?? "—"} at {prospect.company ?? "—"}
            </DialogDescription>
          </DialogHeader>

          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="signals">Intent Signals</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-3">
              <DetailRow label="Email" value={prospect.email ?? "—"} />
              <DetailRow label="LinkedIn" value={prospect.linkedinUrl ?? "—"} />
              <DetailRow
                label="Seniority"
                value={prospect.seniority ? (prospect.seniority === "C_Suite" ? "C-Suite" : prospect.seniority) : "—"}
              />
              <DetailRow label="Enrichment Tier" value={prospect.enrichmentTier ?? "—"} />
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase text-muted-foreground">ICP Score</p>
                <div className="flex items-center gap-2">
                  <Progress value={(prospect.icpScore ?? 0) * 100} className="h-2 flex-1" />
                  <span className="text-sm font-medium">
                    {formatPercent(prospect.icpScore ?? 0, 0)}
                  </span>
                </div>
              </div>
              <Separator />
              <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
                <div>Created: {prospect.createdAt.slice(0, 10)}</div>
                <div>Updated: {timeAgo(prospect.updatedAt)}</div>
              </div>
            </TabsContent>

            <TabsContent value="signals" className="space-y-2">
              {signals.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No intent signals detected yet. Run enrichment to discover signals.
                </p>
              ) : (
                <ul className="space-y-1">
                  {signals.map((s, i) => (
                    <li
                      key={i}
                      className="rounded-md border bg-muted/30 px-3 py-2 text-sm"
                    >
                      {s}
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
          </Tabs>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onEnrich(prospect.id)}
            >
              <Sparkles className="h-4 w-4" />
              Enrich Now
            </Button>
            <DialogClose onClose={onClose} />
          </DialogFooter>
        </>
      )}
    </Dialog>
  );
}

function AddProspectDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSubmit: (body: Partial<Prospect>) => void;
  isPending: boolean;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [seniority, setSeniority] = useState<SeniorityTier>("Director");

  function submit() {
    if (!name.trim()) return;
    onSubmit({
      name: name.trim(),
      email: email.trim() || null,
      company: company.trim() || null,
      title: title.trim() || null,
      seniority,
    });
    setName(""); setEmail(""); setCompany(""); setTitle("");
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogHeader>
        <DialogTitle>Add Prospect</DialogTitle>
        <DialogDescription>Manually add a single prospect.</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-2">
          <Label htmlFor="add-name">Name</Label>
          <Input id="add-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="add-email">Email</Label>
          <Input id="add-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="add-company">Company</Label>
            <Input id="add-company" value={company} onChange={(e) => setCompany(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-title">Title</Label>
            <Input id="add-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="add-seniority">Seniority</Label>
          <Select
            value={seniority}
            onValueChange={(v) => setSeniority(v as SeniorityTier)}
          >
            <SelectTrigger id="add-seniority" className="w-full">
              <SelectValue placeholder="Select seniority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="C_Suite">C-Suite</SelectItem>
              <SelectItem value="Director">Director</SelectItem>
              <SelectItem value="IC">IC</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={isPending || !name.trim()}>
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

function ImportCsvDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSubmit: (file: File) => void;
  isPending: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogHeader>
        <DialogTitle>Import Prospects (CSV)</DialogTitle>
        <DialogDescription>
          CSV must include columns: name, email, company, title. Other columns are ignored.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="rounded-md border border-dashed p-6 text-center">
          <Upload className="mx-auto mb-2 h-6 w-6 text-muted-foreground" />
          <input
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setFile(f);
            }}
          />
          <Label htmlFor="csv-file" className="cursor-pointer text-sm text-primary underline">
            {file ? file.name : "Choose a CSV file"}
          </Label>
          <p className="mt-1 text-xs text-muted-foreground">
            {file ? `${(file.size / 1024).toFixed(1)} KB` : "Max 5MB"}
          </p>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button
          disabled={!file || isPending}
          onClick={() => {
            if (!file) return;
            // Task 2-b finding 10: client-side file validation mirroring the
            // ProspectImportSchema (paste/URL variant) — extension + size guard.
            const MAX_BYTES = 5 * 1024 * 1024; // 5 MB
            if (!/\.csv$/i.test(file.name)) {
              toast.error("File must be a .csv");
              return;
            }
            if (file.size > MAX_BYTES) {
              toast.error(
                `File is ${(file.size / 1024 / 1024).toFixed(1)} MB — max 5 MB`,
              );
              return;
            }
            // Also exercise the zod schema (source=paste path) so the schema
            // is referenced + stays in sync if a paste mode is added later.
            const parsed = ProspectImportSchema.safeParse({
              source: "paste",
              text: file.name,
            });
            if (!parsed.success) {
              toast.error(formatZodError(parsed.error));
              return;
            }
            onSubmit(file);
          }}
        >
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          Import
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[120px_1fr] items-center gap-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">{label}</p>
      <p className={cn("text-sm", value === "—" && "text-muted-foreground")}>{truncate(value, 80)}</p>
    </div>
  );
}

/* ── AI feature result types ──────────────────────────────────────── */

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

interface LookalikeEntry {
  name: string | null;
  title: string | null;
  company: string | null;
  similarity_score: number | null;
  matched_features: string[] | null;
}

interface LookalikeResult {
  lookalikes: LookalikeEntry[] | null;
}

interface HookEntry {
  text: string | null;
  type: string | null;
}

interface HookGenResult {
  hooks: HookEntry[] | null;
  source: "llm" | "fallback" | null;
}

interface ProspectBriefResult {
  summary: string | null;
  key_insights: string[] | null;
  recommended_approach: string | null;
  talking_points: string[] | null;
  risk_factors: string[] | null;
}

interface NlMatchEntry {
  name: string | null;
  company: string | null;
  title: string | null;
  icp_score: number | null;
}

interface NlWebResult {
  title: string | null;
  snippet: string | null;
  url: string | null;
}

interface NlSearchResult {
  interpretation: string | null;
  db_matches: NlMatchEntry[] | null;
  web_results: NlWebResult[] | null;
}

/* ── AI feature sub-components ────────────────────────────────────── */

function HookCard({ hook, index }: { hook: HookEntry; index: number }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    if (!hook.text) return;
    navigator.clipboard.writeText(hook.text).then(() => {
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">#{index}</span>
            {hook.type && (
              <Badge variant="outline" className="text-[10px]">{hook.type}</Badge>
            )}
          </div>
          <p className="mt-1 text-sm">{hook.text ?? "—"}</p>
        </div>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 shrink-0"
          aria-label="Copy hook"
          onClick={handleCopy}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-emerald-600" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
    </div>
  );
}

function BriefSection({
  title,
  content,
  items,
}: {
  title: string;
  content?: string | null;
  items?: string[] | null;
}) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">{title}</p>
      {content && <p className="text-sm">{content}</p>}
      {items && items.length > 0 && (
        <ul className="ml-4 list-disc space-y-1 text-sm">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
      {(!content && (!items || items.length === 0)) && (
        <p className="text-sm text-muted-foreground">—</p>
      )}
    </div>
  );
}
