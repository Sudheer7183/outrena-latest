/**
 * FlowsPage.tsx — FIX-FE-1
 *
 * ProspectingFlow definitions CRUD. JSON editor for source/enrichment/quality
 * step arrays. Targets `GET/POST/PUT/DELETE /api/v1/flows`.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  GitBranch,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { flowsApi } from "@/services/apiClient";
import type { ProspectingFlow, ProspectingFlowInput } from "@/types/common";
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
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

interface FormState {
  id?: string;
  name: string;
  description: string;
  isDefault: boolean;
  isActive: boolean;
  isTemplate: boolean;
  sourceSteps: string;
  enrichmentSteps: string;
  qualityGates: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  description: "",
  isDefault: false,
  isActive: true,
  isTemplate: false,
  sourceSteps: "[]",
  enrichmentSteps: "[]",
  qualityGates: "{}",
};

function countSteps(json: string): number {
  try {
    const parsed = JSON.parse(json);
    return Array.isArray(parsed) ? parsed.length : 0;
  } catch {
    return 0;
  }
}

export function FlowsPage() {
  const qc = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProspectingFlow | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["flows", "list"],
    queryFn: () => flowsApi.listFlows({ isTemplate: false }),
    retry: false,
  });
  const flows = useMemo(() => data?.items ?? [], [data]);

  const createMut = useMutation({
    mutationFn: (body: ProspectingFlowInput) => flowsApi.createFlow(body),
    onSuccess: () => {
      toast.success("Flow created");
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create flow"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<ProspectingFlowInput> }) =>
      flowsApi.updateFlow(id, body),
    onSuccess: () => {
      toast.success("Flow saved");
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save flow"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => flowsApi.removeFlow(id),
    onSuccess: () => {
      toast.success("Flow deleted");
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete flow"),
  });

  function openNew() {
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  }
  function openEdit(f: ProspectingFlow) {
    setForm({
      id: f.id,
      name: f.name,
      description: f.description ?? "",
      isDefault: f.isDefault,
      isActive: f.isActive,
      isTemplate: f.isTemplate,
      sourceSteps: f.sourceSteps,
      enrichmentSteps: f.enrichmentSteps,
      qualityGates: f.qualityGates,
    });
    setEditorOpen(true);
  }
  function closeEditor() {
    setEditorOpen(false);
    setForm(EMPTY_FORM);
  }

  function handleSave() {
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    for (const field of ["sourceSteps", "enrichmentSteps", "qualityGates"] as const) {
      try {
        JSON.parse(form[field]);
      } catch {
        toast.error(`Invalid JSON in ${field}`);
        return;
      }
    }
    const body: ProspectingFlowInput = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      isDefault: form.isDefault,
      isActive: form.isActive,
      isTemplate: form.isTemplate,
      sourceSteps: form.sourceSteps,
      enrichmentSteps: form.enrichmentSteps,
      qualityGates: form.qualityGates,
    };
    if (form.id) {
      updateMut.mutate({ id: form.id, body });
    } else {
      createMut.mutate(body);
    }
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="Prospecting Flows"
          description="Define source, enrichment, and quality-gate step arrays used by the autopilot pipeline."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={openNew}>
                <Plus className="h-4 w-4" />
                New Flow
              </Button>
            </>
          }
        />

        <Card>
          <CardContent className="p-0">
            {isError ? (
              <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                <p className="text-sm font-medium">Failed to load flows</p>
                <p className="text-xs text-muted-foreground">
                  {(error as Error)?.message ?? "Unknown error"}
                </p>
                <Button variant="outline" onClick={() => refetch()}>
                  Retry
                </Button>
              </div>
            ) : isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : flows.length === 0 ? (
              <EmptyState
                icon={<GitBranch className="h-6 w-6" />}
                title="No flows yet"
                description="Define your first prospecting flow to start running the autopilot pipeline."
                action={
                  <Button onClick={openNew}>
                    <Plus className="h-4 w-4" /> New Flow
                  </Button>
                }
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Default</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead>Template</TableHead>
                    <TableHead>Steps</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {flows.map((f) => (
                    <TableRow key={f.id}>
                      <TableCell className="font-medium">{f.name}</TableCell>
                      <TableCell className="max-w-xs truncate text-muted-foreground">
                        {f.description ?? "—"}
                      </TableCell>
                      <TableCell>
                        {f.isDefault ? <Badge variant="default">Default</Badge> : <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell>
                        <Badge variant={f.isActive ? "success" : "outline"}>
                          {f.isActive ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {f.isTemplate ? <Badge variant="secondary">Template</Badge> : <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="text-sm tabular-nums">
                        {countSteps(f.sourceSteps) + countSteps(f.enrichmentSteps)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(f.updatedAt)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label="Edit flow"
                                onClick={() => openEdit(f)}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Edit</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label="Delete flow"
                                onClick={() => setDeleteTarget(f)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Delete</TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Editor dialog */}
        <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
          <DialogClose onClose={closeEditor} />
          <DialogHeader>
            <DialogTitle>{form.id ? "Edit Flow" : "New Flow"}</DialogTitle>
            <DialogDescription>
              Define the source, enrichment, and quality-gate step arrays as JSON.
              The autopilot pipeline reads these arrays when running a flow.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="flow-name">Name</Label>
              <Input
                id="flow-name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Series B Fintech — Outbound"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="flow-desc">Description</Label>
              <Input
                id="flow-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Optional short description"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="flow-source">Source Steps (JSON array)</Label>
              <Textarea
                id="flow-source"
                rows={4}
                value={form.sourceSteps}
                onChange={(e) => setForm({ ...form, sourceSteps: e.target.value })}
                className="font-mono text-xs"
                placeholder='[{"type":"apollo","limit":50}]'
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="flow-enrich">Enrichment Steps (JSON array)</Label>
              <Textarea
                id="flow-enrich"
                rows={4}
                value={form.enrichmentSteps}
                onChange={(e) => setForm({ ...form, enrichmentSteps: e.target.value })}
                className="font-mono text-xs"
                placeholder='[{"type":"domain_enrich"}]'
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="flow-gates">Quality Gates (JSON object)</Label>
              <Textarea
                id="flow-gates"
                rows={3}
                value={form.qualityGates}
                onChange={(e) => setForm({ ...form, qualityGates: e.target.value })}
                className="font-mono text-xs"
                placeholder='{"minIcpScore":0.7}'
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="flex items-center justify-between rounded-md border p-3">
                <span className="text-sm font-medium">Default</span>
                <Switch
                  checked={form.isDefault}
                  onCheckedChange={(v) => setForm({ ...form, isDefault: v })}
                />
              </div>
              <div className="flex items-center justify-between rounded-md border p-3">
                <span className="text-sm font-medium">Active</span>
                <Switch
                  checked={form.isActive}
                  onCheckedChange={(v) => setForm({ ...form, isActive: v })}
                />
              </div>
              <div className="flex items-center justify-between rounded-md border p-3">
                <span className="text-sm font-medium">Template</span>
                <Switch
                  checked={form.isTemplate}
                  onCheckedChange={(v) => setForm({ ...form, isTemplate: v })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeEditor}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={createMut.isPending || updateMut.isPending}
            >
              {createMut.isPending || updateMut.isPending ? "Saving…" : "Save Flow"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Delete dialog */}
        <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <DialogClose onClose={() => setDeleteTarget(null)} />
          <DialogHeader>
            <DialogTitle>Delete flow?</DialogTitle>
            <DialogDescription>
              “{deleteTarget?.name}” will be permanently removed. Past FlowRun records
              will keep their reference but the flow definition will no longer be runnable.
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
