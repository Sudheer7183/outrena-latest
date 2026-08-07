/**
 * FlowWebhooksPage.tsx — FIX-FE-1
 *
 * Outbound webhook trigger config. Lists FlowWebhook rows, supports create /
 * edit / delete. Targets `GET/POST/PUT/DELETE /api/v1/flows/webhooks`.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Webhook,
} from "lucide-react";
import { toast } from "sonner";

import { flowsApi } from "@/services/apiClient";
import type {
  FlowWebhook,
  FlowWebhookInput,
  WebhookTriggerEvent,
} from "@/types/common";
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
import { Switch } from "@/components/ui/switch";
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

const EVENT_OPTIONS: WebhookTriggerEvent[] = [
  "ICP_CREATED",
  "FLOW_RUN_COMPLETED",
  "FLOW_RUN_FAILED",
  "PROSPECT_IMPORTED",
];

function parseEvents(raw: string): WebhookTriggerEvent[] {
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as WebhookTriggerEvent[]) : [];
  } catch {
    return [];
  }
}

interface FormState {
  id?: string;
  name: string;
  url: string;
  secret: string;
  events: WebhookTriggerEvent[];
  flowId: string;
  isActive: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  url: "",
  secret: "",
  events: [],
  flowId: "",
  isActive: true,
};

export function FlowWebhooksPage() {
  const qc = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FlowWebhook | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["flows", "webhooks"],
    queryFn: () => flowsApi.listWebhooks(),
    retry: false,
  });
  const webhooks = useMemo(() => data?.items ?? [], [data]);

  const { data: flowsData } = useQuery({
    queryKey: ["flows", "list", "for-webhooks"],
    queryFn: () => flowsApi.listFlows(),
    retry: false,
  });
  const flows = useMemo(() => flowsData?.items ?? [], [flowsData]);

  const createMut = useMutation({
    mutationFn: (body: FlowWebhookInput) => flowsApi.createWebhook(body),
    onSuccess: () => {
      toast.success("Webhook created");
      qc.invalidateQueries({ queryKey: ["flows", "webhooks"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create webhook"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<FlowWebhookInput> }) =>
      flowsApi.updateWebhook(id, body),
    onSuccess: () => {
      toast.success("Webhook saved");
      qc.invalidateQueries({ queryKey: ["flows", "webhooks"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save webhook"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => flowsApi.removeWebhook(id),
    onSuccess: () => {
      toast.success("Webhook deleted");
      qc.invalidateQueries({ queryKey: ["flows", "webhooks"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete webhook"),
  });

  function openNew() {
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  }
  function openEdit(w: FlowWebhook) {
    setForm({
      id: w.id,
      name: w.name,
      url: w.url,
      secret: w.secret ?? "",
      events: parseEvents(w.events),
      flowId: w.flowId ?? "",
      isActive: w.isActive,
    });
    setEditorOpen(true);
  }
  function closeEditor() {
    setEditorOpen(false);
    setForm(EMPTY_FORM);
  }

  function toggleEvent(ev: WebhookTriggerEvent) {
    setForm((prev) => ({
      ...prev,
      events: prev.events.includes(ev)
        ? prev.events.filter((x) => x !== ev)
        : [...prev.events, ev],
    }));
  }

  function handleSave() {
    if (!form.name.trim() || !form.url.trim()) {
      toast.error("Name and URL are required");
      return;
    }
    try {
      new URL(form.url);
    } catch {
      toast.error("URL is not valid");
      return;
    }
    const body: FlowWebhookInput = {
      name: form.name.trim(),
      url: form.url.trim(),
      secret: form.secret.trim() || null,
      events: JSON.stringify(form.events),
      flowId: form.flowId || null,
      isActive: form.isActive,
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
          title="Flow Webhooks"
          description="Outbound webhook triggers fired on flow events (ICP_CREATED, FLOW_RUN_COMPLETED, etc.)."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={openNew}>
                <Plus className="h-4 w-4" />
                New Webhook
              </Button>
            </>
          }
        />

        <Card>
          <CardContent className="p-0">
            {isError ? (
              <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                <p className="text-sm font-medium">Failed to load webhooks</p>
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
            ) : webhooks.length === 0 ? (
              <EmptyState
                icon={<Webhook className="h-6 w-6" />}
                title="No webhooks yet"
                description="Register an outbound webhook to receive flow lifecycle events at your own service."
                action={
                  <Button onClick={openNew}>
                    <Plus className="h-4 w-4" /> New Webhook
                  </Button>
                }
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>URL</TableHead>
                    <TableHead>Events</TableHead>
                    <TableHead>Flow</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {webhooks.map((w) => {
                    const events = parseEvents(w.events);
                    const flow = flows.find((f) => f.id === w.flowId);
                    return (
                      <TableRow key={w.id}>
                        <TableCell className="font-medium">{w.name}</TableCell>
                        <TableCell className="max-w-xs truncate text-muted-foreground">
                          <a
                            href={w.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary underline-offset-4 hover:underline"
                          >
                            {w.url}
                          </a>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {events.length === 0 ? (
                              <span className="text-muted-foreground">—</span>
                            ) : (
                              events.map((e) => (
                                <Badge key={e} variant="secondary" className="text-[10px]">
                                  {e}
                                </Badge>
                              ))
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {flow?.name ?? (w.flowId ? <code className="font-mono text-xs">{w.flowId}</code> : "—")}
                        </TableCell>
                        <TableCell>
                          <Badge variant={w.isActive ? "success" : "outline"}>
                            {w.isActive ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDateTime(w.updatedAt)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label="Edit webhook"
                                  onClick={() => openEdit(w)}
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
                                  aria-label="Delete webhook"
                                  onClick={() => setDeleteTarget(w)}
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

        {/* Editor dialog */}
        <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
          <DialogClose onClose={closeEditor} />
          <DialogHeader>
            <DialogTitle>{form.id ? "Edit Webhook" : "New Webhook"}</DialogTitle>
            <DialogDescription>
              Register an outbound webhook. OUTRENA will POST a signed JSON payload to the URL on each selected event.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="wh-name">Name</Label>
              <Input
                id="wh-name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. CRM sync — ICP_CREATED"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wh-url">URL</Label>
              <Input
                id="wh-url"
                required
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://hooks.example.com/outrena"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wh-secret">Secret (optional)</Label>
              <Input
                id="wh-secret"
                value={form.secret}
                onChange={(e) => setForm({ ...form, secret: e.target.value })}
                placeholder="HMAC secret used to sign outbound deliveries"
              />
            </div>
            <div className="space-y-2">
              <Label>Events</Label>
              <div className="flex flex-wrap gap-2">
                {EVENT_OPTIONS.map((ev) => {
                  const active = form.events.includes(ev);
                  return (
                    <button
                      key={ev}
                      type="button"
                      onClick={() => toggleEvent(ev)}
                      className={
                        "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors " +
                        (active
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background hover:bg-accent")
                      }
                      aria-pressed={active}
                    >
                      {ev}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="wh-flow">Flow (optional)</Label>
              <Select
                id="wh-flow"
                value={form.flowId}
                onChange={(e) => setForm({ ...form, flowId: e.target.value })}
              >
                <option value="">— All flows —</option>
                {flows.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Active</p>
                <p className="text-xs text-muted-foreground">
                  Inactive webhooks are skipped when firing events.
                </p>
              </div>
              <Switch
                checked={form.isActive}
                onCheckedChange={(v) => setForm({ ...form, isActive: v })}
              />
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
              {createMut.isPending || updateMut.isPending ? "Saving…" : "Save Webhook"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Delete dialog */}
        <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <DialogClose onClose={() => setDeleteTarget(null)} />
          <DialogHeader>
            <DialogTitle>Delete webhook?</DialogTitle>
            <DialogDescription>
              “{deleteTarget?.name}” will be permanently removed. Future events will no longer be delivered.
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
