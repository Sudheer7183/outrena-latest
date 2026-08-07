/**
 * FlowAbTestsPage.tsx — FIX-FE-1
 *
 * Flow-level A/B testing. Lists FlowAbTest rows, supports create + view
 * results (significance + summary JSON). Targets `GET/POST/DELETE /api/v1/flows/ab-tests`.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FlaskConical,
  Plus,
  RefreshCw,
  Trash2,
  Eye,
} from "lucide-react";
import { toast } from "sonner";

import { flowsApi } from "@/services/apiClient";
import type { FlowAbTest, FlowAbTestInput, FlowAbTestStatus } from "@/types/common";
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
import { NativeSelect as Select } from "@/components/ui/select";
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

function statusVariant(
  status: FlowAbTestStatus,
): "default" | "secondary" | "destructive" | "success" | "warning" | "outline" {
  switch (status) {
    case "COMPLETED":
      return "success";
    case "RUNNING":
      return "default";
    case "DRAFT":
      return "warning";
    case "CANCELLED":
      return "outline";
    default:
      return "secondary";
  }
}

interface FormState {
  name: string;
  description: string;
  icpProfileId: string;
  flowAId: string;
  flowBId: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  description: "",
  icpProfileId: "",
  flowAId: "",
  flowBId: "",
};

function safeJsonParse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}


// BUG-13 FIX: Inline ICP profile select populated from /icp-profiles API
function IcpSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { data: profiles = [] } = useQuery({
    queryKey: ["icp-profiles"],
    queryFn: () => import("@/services/apiClient").then(m => m.http.get<{ id: string; name: string }[]>("/api/v1/icp-profiles")),
  });
  return (
    <select
      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required
    >
      <option value="">Select an ICP Profile</option>
      {profiles.map((p) => (
        <option key={p.id} value={p.id}>{p.name}</option>
      ))}
    </select>
  );
}

export function FlowAbTestsPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FlowAbTest | null>(null);
  const [viewTarget, setViewTarget] = useState<FlowAbTest | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["flows", "ab-tests"],
    queryFn: () => flowsApi.listAbTests(),
    retry: false,
  });
  const abTests = useMemo(() => data?.items ?? [], [data]);

  const { data: flowsData } = useQuery({
    queryKey: ["flows", "list", "for-ab"],
    queryFn: () => flowsApi.listFlows(),
    retry: false,
  });
  const flows = useMemo(() => flowsData?.items ?? [], [flowsData]);

  const createMut = useMutation({
    mutationFn: (body: FlowAbTestInput) => flowsApi.createAbTest(body),
    onSuccess: () => {
      toast.success("A/B test created");
      qc.invalidateQueries({ queryKey: ["flows", "ab-tests"] });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
    },
    onError: () => toast.error("Failed to create A/B test"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => flowsApi.removeAbTest(id),
    onSuccess: () => {
      toast.success("A/B test deleted");
      qc.invalidateQueries({ queryKey: ["flows", "ab-tests"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete A/B test"),
  });

  function handleCreate() {
    if (!form.name.trim() || !form.icpProfileId || !form.flowAId || !form.flowBId) {
      toast.error("Name, ICP Profile, Flow A, and Flow B are required");
      return;
    }
    if (form.flowAId === form.flowBId) {
      toast.error("Flow A and Flow B must be different");
      return;
    }
    createMut.mutate({
      name: form.name.trim(),
      description: form.description.trim() || null,
      icpProfileId: form.icpProfileId,
      flowAId: form.flowAId,
      flowBId: form.flowBId,
    });
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="Flow A/B Tests"
          description="Compare two prospecting flows head-to-head on the same ICP profile."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                New A/B Test
              </Button>
            </>
          }
        />

        <Card>
          <CardContent className="p-0">
            {isError ? (
              <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                <p className="text-sm font-medium">Failed to load A/B tests</p>
                <p className="text-xs text-muted-foreground">
                  {(error as Error)?.message ?? "Unknown error"}
                </p>
                <Button variant="outline" onClick={() => refetch()}>
                  Retry
                </Button>
              </div>
            ) : isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : abTests.length === 0 ? (
              <EmptyState
                icon={<FlaskConical className="h-6 w-6" />}
                title="No A/B tests yet"
                description="Create your first flow A/B test to compare two flows on the same ICP profile."
                action={
                  <Button onClick={() => setCreateOpen(true)}>
                    <Plus className="h-4 w-4" /> New A/B Test
                  </Button>
                }
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>ICP Profile</TableHead>
                    <TableHead>Flow A</TableHead>
                    <TableHead>Flow B</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Significance</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {abTests.map((t) => {
                    const sig = safeJsonParse(t.significance);
                    const winner =
                      sig && typeof sig === "object" && "winner" in sig
                        ? String((sig as { winner: unknown }).winner)
                        : null;
                    return (
                      <TableRow key={t.id}>
                        <TableCell className="font-medium">{t.name}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {t.icpProfileId}
                        </TableCell>
                        <TableCell className="font-mono text-xs">{t.flowAId}</TableCell>
                        <TableCell className="font-mono text-xs">{t.flowBId}</TableCell>
                        <TableCell>
                          <Badge variant={statusVariant(t.status)}>{t.status}</Badge>
                        </TableCell>
                        <TableCell>
                          {winner ? (
                            <Badge variant={winner === "tie" ? "outline" : "default"}>
                              Winner: {winner}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDateTime(t.updatedAt)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label="View results"
                                  onClick={() => setViewTarget(t)}
                                >
                                  <Eye className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>View results</TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label="Delete A/B test"
                                  onClick={() => setDeleteTarget(t)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Delete</TooltipContent>
                            </Tooltip>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Create dialog */}
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogClose onClose={() => setCreateOpen(false)} />
          <DialogHeader>
            <DialogTitle>New Flow A/B Test</DialogTitle>
            <DialogDescription>
              Run two flows against the same ICP profile and compare import / enrich / qualify counts.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="abt-name">Name</Label>
              <Input
                id="abt-name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Apollo vs LinkedIn — Q1"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="abt-desc">Description (optional)</Label>
              <Input
                id="abt-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="abt-icp">ICP Profile</Label>
              {/* BUG-13 FIX: use select populated from /icp-profiles instead of free-text */}
              <IcpSelect
                value={form.icpProfileId}
                onChange={(v: string) => setForm({ ...form, icpProfileId: v })}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="abt-flowa">Flow A</Label>
                <Select
                  id="abt-flowa"
                  value={form.flowAId}
                  onChange={(e) => setForm({ ...form, flowAId: e.target.value })}
                >
                  <option value="">— Select flow A —</option>
                  {flows.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="abt-flowb">Flow B</Label>
                <Select
                  id="abt-flowb"
                  value={form.flowBId}
                  onChange={(e) => setForm({ ...form, flowBId: e.target.value })}
                >
                  <option value="">— Select flow B —</option>
                  {flows.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMut.isPending}>
              {createMut.isPending ? "Creating…" : "Create A/B Test"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* View results dialog */}
        <Dialog open={!!viewTarget} onOpenChange={(o) => !o && setViewTarget(null)}>
          <DialogClose onClose={() => setViewTarget(null)} />
          <DialogHeader>
            <DialogTitle>A/B Test Results — {viewTarget?.name}</DialogTitle>
            <DialogDescription>
              Status: {viewTarget?.status} · Started {formatDateTime(viewTarget?.startedAt ?? null)} · Completed{" "}
              {formatDateTime(viewTarget?.completedAt ?? null)}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                Significance
              </p>
              <pre className="max-h-48 overflow-auto rounded bg-muted p-3 font-mono text-xs">
                {viewTarget
                  ? JSON.stringify(safeJsonParse(viewTarget.significance) ?? viewTarget.significance, null, 2)
                  : ""}
              </pre>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                Summary
              </p>
              <pre className="max-h-48 overflow-auto rounded bg-muted p-3 font-mono text-xs">
                {viewTarget
                  ? JSON.stringify(safeJsonParse(viewTarget.summary) ?? viewTarget.summary, null, 2)
                  : ""}
              </pre>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewTarget(null)}>
              Close
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Delete dialog */}
        <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <DialogClose onClose={() => setDeleteTarget(null)} />
          <DialogHeader>
            <DialogTitle>Delete A/B test?</DialogTitle>
            <DialogDescription>
              “{deleteTarget?.name}” will be permanently removed.
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
      </div>
    </TooltipProvider>
  );
}
