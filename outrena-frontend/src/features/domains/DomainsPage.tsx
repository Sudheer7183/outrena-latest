/**
 * DomainsPage.tsx — sending-domain management + DNS check.
 *
 * API:
 *   GET    /api/v1/domains         → Domain[]
 *   POST   /api/v1/domains         → Domain
 *   PUT    /api/v1/domains/:id     → Domain
 *   DELETE /api/v1/domains/:id     → { message }
 *   POST   /api/v1/dns-check       → DnsResult
 *
 * Renders a table of sending domains with verification, SPF/DKIM/DMARC status
 * badges, warm-up date, an "Add Domain" dialog, and a per-row "Check DNS"
 * button.
 */
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, Plus, RefreshCw, ShieldCheck, Trash2, Zap } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { Pagination, usePagination } from "@/components/ui/pagination";
import { DomainCreateSchema, formatZodError } from "@/lib/validation";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
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
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/lib/utils";

interface DnsStatus {
  spf: "pass" | "fail" | "unknown";
  dkim: "pass" | "fail" | "unknown";
  dmarc: "pass" | "fail" | "unknown";
}

/** Raw shape returned by the backend API. */
interface DomainRow {
  id: string;
  domainName: string;
  domain?: string; // alias added by DomainResponse.model_dump
  isVerified?: boolean;
  isActive: boolean;
  spfStatus: boolean;
  dkimStatus: boolean;
  dmarcStatus: boolean;
  warmingWeek: number;
  dailySendLimit: number;
  lastChecked: string | null;
  createdAt: string;
  updatedAt: string;
}

interface Domain extends DnsStatus {
  id: string;
  domain: string;
  isVerified: boolean;
  warmingWeek: number;
  dailySendLimit: number;
  warmedUntil: string | null;
  lastCheckedAt: string | null;
}

/** Convert a boolean DNS status to the frontend enum. */
function dnsBool(v: boolean | undefined | null): "pass" | "fail" | "unknown" {
  if (v === true) return "pass";
  if (v === false) return "fail";
  return "unknown";
}

/** Map a raw backend row to the frontend Domain interface. */
function toDomain(r: DomainRow): Domain {
  return {
    id: r.id,
    domain: r.domain ?? r.domainName,
    isVerified: r.isVerified ?? r.isActive,
    spf: dnsBool(r.spfStatus),
    dkim: dnsBool(r.dkimStatus),
    dmarc: dnsBool(r.dmarcStatus),
    warmingWeek: r.warmingWeek ?? 1,
    dailySendLimit: r.dailySendLimit ?? 10,
    warmedUntil: null, // backend uses warmingWeek; no date equivalent
    lastCheckedAt: r.lastChecked ?? null,
  };
}

interface DomainInput {
  domain: string;
}

interface DnsResult extends DnsStatus {
  domain: string;
  isVerified: boolean;
  checkedAt: string;
}

const MOCK_DOMAINS: Domain[] = [
  {
    id: "dom-1",
    domain: "mail.acme.io",
    isVerified: true,
    spf: "pass",
    dkim: "pass",
    dmarc: "pass",
    warmingWeek: 4,
    dailySendLimit: 100,
    warmedUntil: "2025-04-01T00:00:00Z",
    lastCheckedAt: "2025-02-11T09:00:00Z",
  },
  {
    id: "dom-2",
    domain: "outreach.acme.io",
    isVerified: true,
    spf: "pass",
    dkim: "fail",
    dmarc: "pass",
    warmingWeek: 2,
    dailySendLimit: 30,
    warmedUntil: "2025-03-15T00:00:00Z",
    lastCheckedAt: "2025-02-10T16:30:00Z",
  },
  {
    id: "dom-3",
    domain: "go.acme.io",
    isVerified: false,
    spf: "unknown",
    dkim: "unknown",
    dmarc: "unknown",
    warmingWeek: 1,
    dailySendLimit: 10,
    warmedUntil: null,
    lastCheckedAt: null,
  },
];

function statusBadge(
  status: "pass" | "fail" | "unknown",
): ReactNode {
  if (status === "pass")
    return (
      <Badge variant="success" className="text-[10px]">
        pass
      </Badge>
    );
  if (status === "fail")
    return (
      <Badge variant="destructive" className="text-[10px]">
        fail
      </Badge>
    );
  return (
    <Badge variant="secondary" className="text-[10px]">
      unknown
    </Badge>
  );
}

export function DomainsPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [domainInput, setDomainInput] = useState("");
  const [checkingId, setCheckingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Domain | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["domains"],
    queryFn: () => http.get<DomainRow[]>("/api/v1/domains"),
  });

  const domains = (data?.map(toDomain) ?? MOCK_DOMAINS);


  const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: domains, initialPageSize: 15 });

  const createMutation = useMutation({
    mutationFn: (body: DomainInput) =>
      http.post<Domain>("/api/v1/domains", body),
    onSuccess: () => {
      toast.success("Domain added — run DNS check to verify");
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      setDialogOpen(false);
      setDomainInput("");
    },
    onError: () => toast.error("Failed to add domain"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/domains/${id}`),
    onSuccess: () => {
      toast.success("Domain removed");
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to remove domain"),
  });

  const dnsCheckMutation = useMutation({
    mutationFn: (domain: string) =>
      http.post<DnsResult>("/api/v1/domains/dns-check", { domain }),
    onSuccess: (res) => {
      const allPass =
        res.spf === "pass" && res.dkim === "pass" && res.dmarc === "pass";
      if (allPass) {
        toast.success(`DNS verified for ${res.domain}`);
      } else {
        toast.warning(
          `DNS incomplete for ${res.domain} — SPF:${res.spf} DKIM:${res.dkim} DMARC:${res.dmarc}`,
        );
      }
      queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: () => toast.error("DNS check failed"),
    onSettled: () => setCheckingId(null),
  });

  const autoWarmMutation = useMutation({
    mutationFn: (domainId: string) =>
      http.post<Domain>(`/api/v1/domains/${domainId}/auto-warm`, {}),
    onSuccess: (res) => {
      toast.success(`Domain advanced to week ${res.warmingWeek} (limit: ${res.dailySendLimit}/day)`);
      queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: () => toast.error("Failed to advance warming week"),
  });

  function handleAdd(e: FormEvent) {
    e.preventDefault();
    // Task 2-b finding 10: zod-validated form.
    const parsed = DomainCreateSchema.safeParse({
      domain: domainInput.trim(),
    });
    if (!parsed.success) {
      toast.error(formatZodError(parsed.error));
      return;
    }
    createMutation.mutate({ domain: parsed.data.domain });
  }

  function handleCheck(d: Domain) {
    setCheckingId(d.id);
    dnsCheckMutation.mutate(d.domain);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sending Domains"
        description="Manage sending domains, verify DNS records, and track warm-up status."
        actions={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Add Domain
          </Button>
        }
      />

      {isError ? (
        <Card className="mt-6">
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Failed to load sending domains. Please try again.
            </p>
            <Button onClick={() => refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : (
      <Card>
        <CardHeader>
          <CardTitle>Domains</CardTitle>
          <CardDescription>
            All three of SPF, DKIM, and DMARC must pass before a domain can
            send. Domains in warm-up send at a throttled rate.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : domains.length === 0 ? (
            <EmptyState
              icon={<Globe className="h-6 w-6" />}
              title="No sending domains"
              description="Add a domain to begin warm-up and DNS verification."
              action={
                <Button onClick={() => setDialogOpen(true)}>
                  <Plus className="h-4 w-4" />
                  Add Domain
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Domain</TableHead>
                  <TableHead>Verified</TableHead>
                  <TableHead>SPF</TableHead>
                  <TableHead>DKIM</TableHead>
                  <TableHead>DMARC</TableHead>
                  <TableHead>Warming Week</TableHead>
                  <TableHead>Daily Limit</TableHead>
                  <TableHead>Last Check</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageItems.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Globe className="h-4 w-4 text-muted-foreground" />
                        {d.domain}
                      </div>
                    </TableCell>
                    <TableCell>
                      {d.isVerified ? (
                        <Badge variant="success">
                          <ShieldCheck className="mr-1 h-3 w-3" />
                          Verified
                        </Badge>
                      ) : (
                        <Badge variant="warning">Pending</Badge>
                      )}
                    </TableCell>
                    <TableCell>{statusBadge(d.spf)}</TableCell>
                    <TableCell>{statusBadge(d.dkim)}</TableCell>
                    <TableCell>{statusBadge(d.dmarc)}</TableCell>
                    <TableCell>
                      <Badge variant={d.warmingWeek >= 7 ? "success" : d.warmingWeek >= 2 ? "warning" : "secondary"} className="text-[10px]">
                        Wk {d.warmingWeek}/7
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs tabular-nums">
                      {d.dailySendLimit}/day
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(d.lastCheckedAt)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {d.warmingWeek < 7 && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => autoWarmMutation.mutate(d.id)}
                            disabled={autoWarmMutation.isPending}
                            title="Advance one week in the 7-step warming schedule"
                          >
                            <Zap className="h-3.5 w-3.5" />
                            Auto-warm
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCheck(d)}
                          disabled={checkingId === d.id}
                        >
                          <RefreshCw
                            className={
                              checkingId === d.id
                                ? "h-3.5 w-3.5 animate-spin"
                                : "h-3.5 w-3.5"
                            }
                          />
                          {checkingId === d.id ? "Checking…" : "Check DNS"}
                        </Button>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeleteTarget(d)}
                              aria-label="Delete"
                            >
                              <Trash2 className="h-4 w-4 text-red-600" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Delete domain</TooltipContent>
                        </Tooltip>
                      </div>
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
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogClose onClose={() => setDialogOpen(false)} />
        <DialogHeader>
          <DialogTitle>Add Sending Domain</DialogTitle>
          <DialogDescription>
            Enter a subdomain you control (e.g. mail.yourcompany.com). You'll
            need to add SPF, DKIM, and DMARC DNS records.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleAdd} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="domain">Domain</Label>
            <Input
              id="domain"
              placeholder="mail.yourcompany.com"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              Add domain
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete sending domain?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.domain
              ? `Domain "${deleteTarget.domain}" will be permanently removed and any associated warm-up progress will be lost. This action cannot be undone.`
              : "This sending domain will be permanently removed. This action cannot be undone."}
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
