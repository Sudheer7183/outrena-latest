/**
 * IntegrationConfigPage.tsx — dual-path integration config UI (TENANT_ADMIN).
 *
 * Under <AppLayout>. Fetches:
 *   - GET /api/v1/integrations → tenant integrations with key_source + masked_key
 *
 * Shows:
 *   - Current `integration_mode` (read-only for TENANT_ADMIN; SUPER_ADMIN can
 *     flip it via the platform admin integrations tab — surfaced here as a
 *     banner explaining the platform-managed price impact).
 *   - Pricing impact banner: "Platform-managed mode adds $49/mo".
 *   - Table of integrations: name, type, key_source badge, masked key, status,
 *     Test + Edit buttons.
 *   - Edit dialog: when key_source=tenant, show API key input; when platform,
 *     show "Using platform-provided key" info card.
 *
 * All mutations invalidate ["integrations"] + toast.
 * Falls back to inline mock data so the page renders without backend.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Info,
  Plug,
  Plus,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { integrationConfigApi } from "@/services/apiClient";
import type {
  IntegrationKeySource,
  TenantIntegration,
} from "@/types/common";
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
import { InfoLabel } from "@/components/ui/info-label";
import { NativeSelect as Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { cn, formatDateTime } from "@/lib/utils";

const PLATFORM_MANAGED_DELTA_CENTS = 4900; // $49/mo

const INTEGRATION_TYPES = [
  "apollo",
  "hunter",
  "snov",
  "rocketreach",
  "clearbit",
  "linkedin",
  "gmail",
  "outlook",
  "sendgrid",
  "postmark",
  "twilio",
];

const MOCK_INTEGRATIONS: TenantIntegration[] = [
  {
    id: "int-1",
    platform: "apollo",
    name: "Apollo.io",
    key_source: "platform",
    isActive: true,
    apiKey: "••••••••••••3a9f (platform)",
    createdAt: "2025-01-12T10:00:00Z",
    updatedAt: "2025-02-09T14:30:00Z",
  },
  {
    id: "int-2",
    platform: "hunter",
    name: "Hunter.io",
    key_source: "tenant",
    isActive: true,
    apiKey: "hk-••••••••7c2b",
    createdAt: "2025-01-22T09:00:00Z",
    updatedAt: "2025-02-01T08:15:00Z",
  },
  {
    id: "int-3",
    platform: "sendgrid",
    name: "SendGrid",
    key_source: "platform",
    isActive: true,
    apiKey: "SG.••••••••••••1f8a (platform)",
    createdAt: "2025-01-30T12:00:00Z",
    updatedAt: "2025-02-05T16:45:00Z",
  },
];

interface EditForm {
  type: string;
  name: string;
  key_source: IntegrationKeySource;
  api_key: string;
  is_active: boolean;
}

const EMPTY_FORM: EditForm = {
  type: "apollo",
  name: "",
  key_source: "platform",
  api_key: "",
  is_active: true,
};

function sourceVariant(
  src: IntegrationKeySource,
): "default" | "secondary" {
  return src === "platform" ? "default" : "secondary";
}

export function IntegrationConfigPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<EditForm>(EMPTY_FORM);
  const [testingId, setTestingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["integrations"],
    queryFn: () => integrationConfigApi.tenantList(),
  });

  const integrations = data ?? MOCK_INTEGRATIONS;

  // Best-effort: read tenant mode from the integrations themselves (if any
  // platform-keyed rows exist, the tenant is in platform_managed mode). The
  // authoritative source is platform admin; this is a hint for the banner.
  const hasPlatformKeyed = integrations.some((i) => i.key_source === "platform");
  const inferredMode = hasPlatformKeyed ? "platform_managed" : "tenant_managed";

  const createMutation = useMutation({
    mutationFn: (body: EditForm) =>
      integrationConfigApi.tenantCreate({
        type: body.type,
        name: body.name,
        key_source: body.key_source,
        api_key: body.key_source === "tenant" ? body.api_key : undefined,
      }),
    onSuccess: () => {
      toast.success("Integration added");
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setDialogOpen(false);
    },
    onError: () => toast.error("Failed to add integration"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: EditForm }) =>
      integrationConfigApi.tenantUpdate(id, {
        name: body.name,
        key_source: body.key_source,
        api_key: body.key_source === "tenant" ? body.api_key : undefined,
        is_active: body.is_active,
      }),
    onSuccess: () => {
      toast.success("Integration updated");
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setDialogOpen(false);
    },
    onError: () => toast.error("Failed to update integration"),
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => integrationConfigApi.tenantTest(id),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      if (res.ok) {
        toast.success(
          `Connection OK${res.latencyMs ? ` · ${res.latencyMs}ms` : ""}`,
        );
      } else {
        toast.error(`Test failed: ${res.detail ?? "Unknown error"}`);
      }
    },
    onError: () => toast.error("Test request failed"),
    onSettled: () => setTestingId(null),
  });

  function openAdd() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(row: TenantIntegration) {
    setEditingId(row.id);
    setForm({
      type: row.platform,
      name: row.name,
      key_source: row.key_source,
      api_key: "",
      is_active: row.isActive,
    });
    setDialogOpen(true);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    if (form.key_source === "tenant" && !form.api_key.trim() && !editingId) {
      toast.error("API key is required for tenant-managed integrations");
      return;
    }
    if (editingId) {
      updateMutation.mutate({ id: editingId, body: form });
    } else {
      createMutation.mutate(form);
    }
  }

  function handleTest(id: string) {
    setTestingId(id);
    testMutation.mutate(id);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Integration Config"
        description="Manage prospecting + outreach integrations and your dual-path integration mode."
        actions={
          <Button onClick={openAdd}>
            <Plus className="h-4 w-4" />
            Add Integration
          </Button>
        }
      />

      {/* Integration-mode banner */}
      <Card
        className={cn(
          "border-l-4",
          inferredMode === "platform_managed"
            ? "border-l-emerald-500"
            : "border-l-amber-500",
        )}
      >
        <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-md bg-emerald-100 p-2 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">
                Integration mode:{" "}
                <Badge variant={inferredMode === "platform_managed" ? "success" : "warning"}>
                  {inferredMode === "platform_managed"
                    ? "Platform-managed"
                    : "Tenant-managed"}
                </Badge>
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {inferredMode === "platform_managed"
                  ? "OUTRENA provides activation keys for all supported integrations. A platform-managed surcharge is added to your monthly plan."
                  : "You provide your own API keys for each integration. Only your tenant admin can change this mode — contact your platform admin to switch."}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Pricing impact
            </p>
            <p className="text-lg font-bold">
              +${PLATFORM_MANAGED_DELTA_CENTS / 100}/mo
            </p>
            <p className="text-xs text-muted-foreground">in platform mode</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configured Integrations</CardTitle>
          <CardDescription>
            Each row shows the integration name, type, key source (platform =
            OUTRENA-provided, tenant = your own key), masked key, and status.
            Click Test to verify connectivity.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : integrations.length === 0 ? (
            <EmptyState
              icon={<Plug className="h-6 w-6" />}
              title="No integrations configured"
              description="Add your first integration to enable prospecting + outreach data sources."
              action={
                <Button onClick={openAdd}>
                  <Plus className="h-4 w-4" />
                  Add Integration
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Key source</TableHead>
                  <TableHead>Masked key</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {integrations.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.name}</TableCell>
                    <TableCell className="uppercase text-xs text-muted-foreground">
                      {row.platform}
                    </TableCell>
                    <TableCell>
                      <Badge variant={sourceVariant(row.key_source)}>
                        {row.key_source === "platform"
                          ? "Platform key"
                          : "Tenant key"}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {row.apiKey}
                    </TableCell>
                    <TableCell>
                      {row.isActive ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="secondary">Inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {row.updatedAt ? formatDateTime(row.updatedAt) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleTest(row.id)}
                          disabled={testingId === row.id}
                        >
                          <Zap className="h-3.5 w-3.5" />
                          {testingId === row.id ? "Testing…" : "Test"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(row)}
                        >
                          Edit
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogClose onClose={() => setDialogOpen(false)} />
        <DialogHeader>
          <DialogTitle>
            {editingId ? "Edit Integration" : "Add Integration"}
          </DialogTitle>
          <DialogDescription>
            Choose a key source. Platform keys are managed by OUTRENA; tenant
            keys are stored encrypted in your tenant schema.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="int-type">Type</Label>
              <Select
                id="int-type"
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
                disabled={!!editingId}
              >
                {INTEGRATION_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="int-name">Display name</Label>
              <Input
                id="int-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Apollo.io"
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <InfoLabel
              htmlFor="int-source"
              label="Key source"
              info="Platform = OUTRENA holds + pays for the API key (billed through your subscription). Tenant = you bring your own key (costs flow through your vendor account directly)."
            />
            <Select
              id="int-source"
              value={form.key_source}
              onChange={(e) =>
                setForm({
                  ...form,
                  key_source: e.target.value as IntegrationKeySource,
                })
              }
            >
              <option value="platform">Platform (OUTRENA-provided)</option>
              <option value="tenant">Tenant (your own API key)</option>
            </Select>
          </div>

          {form.key_source === "tenant" ? (
            <div className="space-y-2">
              <Label htmlFor="int-key">
                API key {editingId && "(leave blank to keep existing)"}
              </Label>
              <Input
                id="int-key"
                type="password"
                placeholder="sk-..."
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                required={!editingId}
              />
              <p className="text-xs text-muted-foreground">
                Encrypted at rest with the tenant Fernet key.
              </p>
            </div>
          ) : (
            <div className="flex items-start gap-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-300">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">Using platform-provided key</p>
                <p className="mt-0.5 text-xs">
                  OUTRENA maintains the activation key centrally. No secret is
                  stored in your tenant schema.
                </p>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">Active</p>
              <p className="text-xs text-muted-foreground">
                Inactive integrations are skipped by sourcing + sending jobs.
              </p>
            </div>
            <Switch
              checked={form.is_active}
              onCheckedChange={(c) => setForm({ ...form, is_active: c })}
            />
          </div>

          {inferredMode === "tenant_managed" && form.key_source === "platform" && (
            <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                Your tenant is currently in tenant-managed mode. Platform keys
                are only available after a platform admin flips the integration
                mode. This row will be created but may stay inactive until then.
              </p>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {editingId ? "Save changes" : "Add integration"}
              <CheckCircle2 className="ml-1 h-4 w-4" />
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}
