/**
 * MailBridgePage.tsx — FIX-FE-1
 *
 * Per-tenant MailBridge config CRUD (SMTP / Gmail / Outlook relay settings).
 * Targets `GET/POST/PUT/DELETE /api/v1/mailbridge/config` + `POST /mailbridge/send`
 * for the optional "send test email" action.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Mail,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { mailbridgeApi, http } from "@/services/apiClient";
import type { MailBridgeConfig, MailBridgeConfigInput } from "@/types/common";
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

const PROVIDERS = ["gmail", "smtp", "outlook", "sendgrid", "ses"] as const;

interface DomainLite {
  id: string;
  domain: string;
}

interface FormState {
  id?: string;
  name: string;
  baseUrl: string;
  provider: string;
  fromEmail: string;
  fromName: string;
  isActive: boolean;
  webhookSecret: string;
  domainId: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  baseUrl: "",
  provider: "gmail",
  fromEmail: "",
  fromName: "",
  isActive: true,
  webhookSecret: "",
  domainId: "",
};

export function MailBridgePage() {
  const qc = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<MailBridgeConfig | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const { data: configs, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["mailbridge", "configs"],
    queryFn: () => mailbridgeApi.list(),
    retry: false,
  });

  const { data: domains } = useQuery<DomainLite[]>({
    queryKey: ["domains"],
    queryFn: () => http.get("/api/v1/domains"),
    retry: false,
  });

  const createMut = useMutation({
    mutationFn: (body: MailBridgeConfigInput) => mailbridgeApi.create(body),
    onSuccess: () => {
      toast.success("MailBridge config created");
      qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create MailBridge config"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<MailBridgeConfigInput> }) =>
      mailbridgeApi.update(id, body),
    onSuccess: () => {
      toast.success("MailBridge config saved");
      qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save MailBridge config"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => mailbridgeApi.remove(id),
    onSuccess: () => {
      toast.success("MailBridge config deleted");
      qc.invalidateQueries({ queryKey: ["mailbridge", "configs"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete config"),
  });

  const testMut = useMutation({
    mutationFn: (config: MailBridgeConfig) =>
      mailbridgeApi.sendTest({
        to: config.fromEmail,
        subject: "OUTRENA MailBridge test",
        body: "This is a test email from OUTRENA MailBridge.",
        configId: config.id,
      }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["mailbridge-configs"] });
      if (res.accepted) {
        toast.success(`Test email sent (messageId: ${res.messageId})`);
      } else {
        toast.error(`Test email rejected (status: ${res.status})`);
      }
    },
    onError: () => toast.error("Failed to send test email"),
  });

  function openNew() {
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  }
  function openEdit(c: MailBridgeConfig) {
    setForm({
      id: c.id,
      name: c.name,
      baseUrl: c.baseUrl,
      provider: c.provider,
      fromEmail: c.fromEmail,
      fromName: c.fromName ?? "",
      isActive: c.isActive,
      webhookSecret: c.webhookSecret ?? "",
      domainId: c.domainId ?? "",
    });
    setEditorOpen(true);
  }
  function closeEditor() {
    setEditorOpen(false);
    setForm(EMPTY_FORM);
  }

  function handleSave() {
    if (!form.name.trim() || !form.baseUrl.trim() || !form.fromEmail.trim()) {
      toast.error("Name, Base URL, and From Email are required");
      return;
    }
    const body: MailBridgeConfigInput = {
      name: form.name.trim(),
      baseUrl: form.baseUrl.trim(),
      provider: form.provider,
      fromEmail: form.fromEmail.trim(),
      fromName: form.fromName.trim() || null,
      isActive: form.isActive,
      webhookSecret: form.webhookSecret.trim() || null,
      domainId: form.domainId || null,
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
          title="MailBridge Config"
          description="Tenant-wide SMTP / Gmail / Outlook relay settings used by the scheduler to send and receive email."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={openNew}>
                <Plus className="h-4 w-4" />
                New Config
              </Button>
            </>
          }
        />

        <Card>
          <CardContent className="p-0">
            {isError ? (
              <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                <p className="text-sm font-medium">Failed to load MailBridge configs</p>
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
            ) : !configs || configs.length === 0 ? (
              <EmptyState
                icon={<Mail className="h-6 w-6" />}
                title="No MailBridge configs yet"
                description="Add your first SMTP / Gmail / Outlook relay config so the scheduler can send email."
                action={
                  <Button onClick={openNew}>
                    <Plus className="h-4 w-4" /> New Config
                  </Button>
                }
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>From Email</TableHead>
                    <TableHead>Domain</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead>Last Updated</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {configs.map((c) => {
                    const domain = domains?.find((d) => d.id === c.domainId);
                    return (
                      <TableRow key={c.id}>
                        <TableCell className="font-medium">{c.name}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{c.provider}</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{c.fromEmail}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {domain?.domain ?? "—"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={c.isActive ? "success" : "outline"}>
                            {c.isActive ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDateTime(c.updatedAt)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label="Send test email"
                                  onClick={() => testMut.mutate(c)}
                                  disabled={testMut.isPending}
                                >
                                  <Send className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Send test email</TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label="Edit config"
                                  onClick={() => openEdit(c)}
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
                                  aria-label="Delete config"
                                  onClick={() => setDeleteTarget(c)}
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
            <DialogTitle>{form.id ? "Edit MailBridge Config" : "New MailBridge Config"}</DialogTitle>
            <DialogDescription>
              Configure the SMTP / Gmail / Outlook relay used to send outbound email and receive tracking webhooks.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mb-name">Name</Label>
              <Input
                id="mb-name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Primary SMTP relay"
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mb-provider">Provider</Label>
                <Select
                  id="mb-provider"
                  value={form.provider}
                  onChange={(e) => setForm({ ...form, provider: e.target.value })}
                >
                  {PROVIDERS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="mb-domain">Domain (optional)</Label>
                <Select
                  id="mb-domain"
                  value={form.domainId}
                  onChange={(e) => setForm({ ...form, domainId: e.target.value })}
                >
                  <option value="">— Tenant-wide —</option>
                  {(domains ?? []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.domain}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mb-baseurl">Base URL</Label>
              <Input
                id="mb-baseurl"
                required
                value={form.baseUrl}
                onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
                placeholder="https://mailbridge.example.com"
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mb-fromemail">From Email</Label>
                <Input
                  id="mb-fromemail"
                  required
                  type="email"
                  value={form.fromEmail}
                  onChange={(e) => setForm({ ...form, fromEmail: e.target.value })}
                  placeholder="noreply@example.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mb-fromname">From Name (optional)</Label>
                <Input
                  id="mb-fromname"
                  value={form.fromName}
                  onChange={(e) => setForm({ ...form, fromName: e.target.value })}
                  placeholder="OUTRENA Team"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mb-webhook">Webhook Secret (optional)</Label>
              <Input
                id="mb-webhook"
                value={form.webhookSecret}
                onChange={(e) => setForm({ ...form, webhookSecret: e.target.value })}
                placeholder="HMAC secret used to verify inbound MailBridge webhooks"
              />
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Active</p>
                <p className="text-xs text-muted-foreground">
                  Inactive configs are skipped by the scheduler.
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
              {createMut.isPending || updateMut.isPending ? "Saving…" : "Save Config"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Delete dialog */}
        <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <DialogClose onClose={() => setDeleteTarget(null)} />
          <DialogHeader>
            <DialogTitle>Delete MailBridge config?</DialogTitle>
            <DialogDescription>
              “{deleteTarget?.name}” will be permanently removed. The scheduler will
              no longer use this config to send or receive email.
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
