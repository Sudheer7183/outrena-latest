/**
 * DomainEnrichmentPage.tsx — FIX-FE-1
 *
 * Domain enrichment cache. Search by domain + trigger enrichment on demand.
 * Targets `POST /api/v1/domain-enrich` (enrich) + `GET /api/v1/domain-enrich/{domain}` (cached).
 *
 * Note: the backend does not expose a list endpoint, so this page keeps a
 * client-side list of enriched domains the user has touched this session and
 * joins it with the lookup result for each.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Globe,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";

import { domainEnrichApi } from "@/services/apiClient";
import type { DomainEnrichment } from "@/types/common";
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
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDateTime } from "@/lib/utils";

const SESSION_KEY = "outrena:domain-enrichment-history";

function loadHistory(): string[] {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, 50) : [];
  } catch {
    return [];
  }
}

function saveHistory(domains: string[]) {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(domains.slice(0, 50)));
  } catch {
    // ignore quota errors
  }
}

export function DomainEnrichmentPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [history, setHistory] = useState<string[]>(() => loadHistory());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [enrichOpen, setEnrichOpen] = useState(false);
  const [newDomain, setNewDomain] = useState("");

  // Look up each domain in history; results are cached by React Query
  const queries = useQuery({
    queryKey: ["domain-enrich", history],
    queryFn: async () => {
      const results = await Promise.all(
        history.map(async (d) => {
          try {
            const r = await domainEnrichApi.get(d);
            return [d, r] as const;
          } catch {
            return [d, null] as const;
          }
        }),
      );
      return new Map<string, DomainEnrichment | null>(results);
    },
    retry: false,
  });

  useEffect(() => {
    saveHistory(history);
  }, [history]);

  const enrichMut = useMutation({
    mutationFn: (domain: string) => domainEnrichApi.enrich(domain, true),
    onSuccess: (res) => {
      toast.success(`Enriched ${res.domain}`);
      setHistory((prev) => [res.domain, ...prev.filter((d) => d !== res.domain)].slice(0, 50));
      qc.invalidateQueries({ queryKey: ["domain-enrich"] });
      setEnrichOpen(false);
      setNewDomain("");
    },
    onError: () => toast.error("Failed to enrich domain"),
  });

  const filteredHistory = history.filter((d) =>
    d.toLowerCase().includes(search.toLowerCase()),
  );

  function toggleExpanded(domain: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  }

  function handleEnrich() {
    const d = newDomain.trim().toLowerCase();
    if (!d) {
      toast.error("Domain is required");
      return;
    }
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(d)) {
      toast.error("Enter a valid domain (e.g. acme.com)");
      return;
    }
    enrichMut.mutate(d);
  }

  const map = queries.data;

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="Domain Enrichment"
          description="Fetch and cache company firmographics + tech stack by domain. Cached results are reused across the autopilot pipeline."
          actions={
            <>
              <Button variant="outline" onClick={() => queries.refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={() => setEnrichOpen(true)}>
                <Plus className="h-4 w-4" />
                Enrich domain
              </Button>
            </>
          }
        />

        <Card>
          <CardContent className="p-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search enriched domains…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            {queries.isError ? (
              <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                <p className="text-sm font-medium">Failed to load enrichments</p>
                <Button variant="outline" onClick={() => queries.refetch()}>
                  Retry
                </Button>
              </div>
            ) : queries.isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : filteredHistory.length === 0 ? (
              <EmptyState
                icon={<Globe className="h-6 w-6" />}
                title="No enriched domains yet"
                description="Enrich your first domain to cache its firmographics + tech stack."
                action={
                  <Button onClick={() => setEnrichOpen(true)}>
                    <Plus className="h-4 w-4" /> Enrich domain
                  </Button>
                }
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8" />
                    <TableHead>Domain</TableHead>
                    <TableHead>Company</TableHead>
                    <TableHead>Industry</TableHead>
                    <TableHead>Employees</TableHead>
                    <TableHead>Revenue</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Last Enriched</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredHistory.map((d) => {
                    const item = map?.get(d) ?? null;
                    const isOpen = expanded.has(d);
                    return (
                      <>
                        <TableRow key={d}>
                          <TableCell className="w-8 p-2">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label={isOpen ? "Collapse" : "Expand"}
                                  onClick={() => toggleExpanded(d)}
                                >
                                  {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>{isOpen ? "Collapse domain row" : "Expand domain row"}</TooltipContent>
                            </Tooltip>
                          </TableCell>
                          <TableCell className="font-mono text-xs">{d}</TableCell>
                          <TableCell className="font-medium">{item?.companyName ?? "—"}</TableCell>
                          <TableCell className="text-muted-foreground">{item?.industry ?? "—"}</TableCell>
                          <TableCell className="tabular-nums">{item?.employeeCount ?? "—"}</TableCell>
                          <TableCell className="text-muted-foreground">{item?.revenueRange ?? "—"}</TableCell>
                          <TableCell className="text-muted-foreground">{item?.location ?? "—"}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {formatDateTime(item?.lastEnrichedAt ?? null)}
                          </TableCell>
                          <TableCell className="text-right">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label="Refresh enrichment"
                                  onClick={() => enrichMut.mutate(d)}
                                  disabled={enrichMut.isPending}
                                >
                                  <Sparkles className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Re-enrich</TooltipContent>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                        {isOpen && (
                          <TableRow key={`${d}-detail`} className="bg-muted/30 hover:bg-muted/30">
                            <TableCell colSpan={9} className="p-4">
                              {!item ? (
                                <p className="text-sm text-muted-foreground">
                                  No cached enrichment for this domain. Click the sparkle icon to fetch.
                                </p>
                              ) : (
                                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                  <div>
                                    <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                                      Description
                                    </p>
                                    <p className="text-sm">{item.description ?? "—"}</p>
                                  </div>
                                  <div>
                                    <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                                      Tech Stack
                                    </p>
                                    <div className="flex flex-wrap gap-1">
                                      {!item.techStack?.length ? (
                                        <span className="text-muted-foreground">—</span>
                                      ) : (
                                        item.techStack.map((t: string) => (
                                          <Badge key={t} variant="secondary" className="text-[10px]">
                                            {t}
                                          </Badge>
                                        ))
                                      )}
                                    </div>
                                  </div>
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        )}
                      </>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Enrich dialog */}
        <Dialog open={enrichOpen} onOpenChange={setEnrichOpen}>
          <DialogClose onClose={() => setEnrichOpen(false)} />
          <DialogHeader>
            <DialogTitle>Enrich Domain</DialogTitle>
            <DialogDescription>
              Fetch and cache firmographics + tech stack for a domain. Re-running for an existing domain forces a refresh.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="de-domain">Domain</Label>
              <Input
                id="de-domain"
                required
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                placeholder="acme.com"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEnrichOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEnrich} disabled={enrichMut.isPending}>
              {enrichMut.isPending ? "Enriching…" : "Enrich"}
            </Button>
          </DialogFooter>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
