/**
 * PlatformSettingsPage.tsx — SUPER_ADMIN platform-level tenant config.
 *
 * FIX-FE-1: previously a static placeholder. Now wired to
 *   GET   /api/platform/admin/tenants/{tenant_id}/config           → full TenantConfig
 *   PATCH /api/platform/admin/tenants/{tenant_id}/integration-mode  → update integration_mode
 *
 * Plan / max_seats / features / integrations_shared / llm_provider_default are
 * read-only here (no backend write endpoint exists yet). The Integration Mode
 * selector is editable and explains the dual-path (platform_managed vs tenant_managed).
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  Building2,
  Cpu,
  Mail,
  Save,
  Shield,
  ToggleLeft,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";

import { platformApi, platformConfigApi } from "@/services/apiClient";
import type { IntegrationMode, PlatformTenantConfig, TenantRow } from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import { formatDateTime } from "@/lib/utils";

export function PlatformSettingsPage() {
  const qc = useQueryClient();
  const [tenantId, setTenantId] = useState<string>("");
  const [integrationMode, setIntegrationMode] = useState<IntegrationMode>("tenant_managed");
  const [featuresText, setFeaturesText] = useState<string>("{}");

  // Tenant list (for the selector)
  const { data: tenants, isLoading: tenantsLoading } = useQuery<TenantRow[]>({
    queryKey: ["platform", "tenants"],
    queryFn: () => platformApi.tenants(),
    retry: false,
  });

  // Auto-select first tenant when list loads
  useEffect(() => {
    if (!tenantId && tenants && tenants.length > 0) {
      setTenantId(String(tenants[0].id));
    }
  }, [tenants, tenantId]);

  // Fetch config for the selected tenant
  const { data: config, isLoading, isError, error, refetch } = useQuery<PlatformTenantConfig>({
    queryKey: ["platform", "tenant-config", tenantId],
    queryFn: () => platformConfigApi.get(tenantId),
    enabled: !!tenantId,
    retry: false,
  });

  // Sync local form state with fetched config
  useEffect(() => {
    if (config) {
      setIntegrationMode(config.integration_mode);
      setFeaturesText(JSON.stringify(config.features ?? {}, null, 2));
    }
  }, [config]);

  const updateModeMut = useMutation({
    mutationFn: (mode: IntegrationMode) =>
      platformConfigApi.setIntegrationMode(tenantId, mode),
    onSuccess: (res) => {
      toast.success(`Integration mode set to ${res.integration_mode}`);
      qc.invalidateQueries({ queryKey: ["platform", "tenant-config", tenantId] });
    },
    onError: () => toast.error("Failed to update integration mode"),
  });

  function handleSaveIntegrationMode() {
    if (!tenantId) {
      toast.error("Pick a tenant first");
      return;
    }
    if (integrationMode !== "platform_managed" && integrationMode !== "tenant_managed") {
      toast.error("Invalid integration mode");
      return;
    }
    updateModeMut.mutate(integrationMode);
  }

  function handleSaveFeatures() {
    // No backend write endpoint exists for features — show a toast instead of
    // misleading the user that the change persisted.
    try {
      JSON.parse(featuresText);
      toast.info("Features JSON is read-only at the API level — wire a backend write endpoint to persist.");
    } catch {
      toast.error("Features JSON is invalid");
    }
  }

  const selectedTenant = useMemo(
    () => tenants?.find((t) => String(t.id) === tenantId),
    [tenants, tenantId],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Settings"
        description="Per-tenant platform configuration: plan, seats, feature flags, and dual-path integration mode."
        actions={
          <Button variant="outline" onClick={() => refetch()} disabled={!tenantId}>
            <Building2 className="h-4 w-4" />
            Refresh
          </Button>
        }
      />

        {/* Tenant selector */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Tenant
            </CardTitle>
            <CardDescription>
              Pick a tenant to view and edit its platform-level configuration.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {tenantsLoading ? (
              <Skeleton className="h-10 w-full max-w-md" />
            ) : (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="space-y-2 sm:w-80">
                  <Label htmlFor="tenant-select">Tenant</Label>
                  <Select
                    id="tenant-select"
                    value={tenantId}
                    onChange={(e) => setTenantId(e.target.value)}
                  >
                    <option value="">— Select tenant —</option>
                    {(tenants ?? []).map((t: TenantRow) => (
                      <option key={t.id} value={String(t.id)}>
                        {t.name} ({t.slug})
                      </option>
                    ))}
                  </Select>
                </div>
                {selectedTenant && (
                  <div className="text-xs text-muted-foreground">
                    Plan: <Badge variant="secondary">{selectedTenant.plan_name}</Badge> · Seats{" "}
                    {selectedTenant.seats_used}/{selectedTenant.seats_limit} · Status{" "}
                    <Badge variant={selectedTenant.status === "active" ? "success" : "outline"}>
                      {selectedTenant.status}
                    </Badge>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {!tenantId ? (
          <Card>
            <CardContent className="p-10 text-center text-sm text-muted-foreground">
              Select a tenant to view its configuration.
            </CardContent>
          </Card>
        ) : isError ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
              <p className="text-sm font-medium">Failed to load tenant config</p>
              <p className="text-xs text-muted-foreground">
                {(error as Error)?.message ?? "Unknown error"}
              </p>
              <Button variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </CardContent>
          </Card>
        ) : isLoading || !config ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Read-only tenant config */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ToggleLeft className="h-5 w-5" />
                  Tenant Config
                </CardTitle>
                <CardDescription>
                  Read-only view of the tenant_config row (public schema). Last updated{" "}
                  {formatDateTime(config.updated_at)}.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Plan</p>
                  <Badge variant="secondary">{config.plan}</Badge>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Max Seats</p>
                  <p className="tabular-nums">{config.max_seats}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted-foreground">LLM Default Provider</p>
                  <p className="flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                    {config.llm_provider_default}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Integrations Shared</p>
                  <Badge variant={config.integrations_shared ? "success" : "outline"}>
                    {config.integrations_shared ? "Shared" : "Per-user"}
                  </Badge>
                </div>
                <div className="col-span-2">
                  <p className="mb-1 text-xs uppercase text-muted-foreground">Features (JSON)</p>
                  <Textarea
                    value={featuresText}
                    onChange={(e) => setFeaturesText(e.target.value)}
                    rows={6}
                    className="font-mono text-xs"
                  />
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    Editing this field is informational only — no backend write endpoint exists yet.
                  </p>
                  <Button variant="outline" size="sm" className="mt-2" onClick={handleSaveFeatures}>
                    <Save className="h-4 w-4" />
                    Save features
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Editable integration mode */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wrench className="h-5 w-5" />
                  Integration Mode
                </CardTitle>
                <CardDescription>
                  Dual-path integration config. Determines how outbound API keys are resolved for this tenant.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="int-mode">Mode</Label>
                  <Select
                    id="int-mode"
                    value={integrationMode}
                    onChange={(e) => setIntegrationMode(e.target.value as IntegrationMode)}
                  >
                    <option value="tenant_managed">tenant_managed — tenant provides its own keys</option>
                    <option value="platform_managed">platform_managed — use platform keys (+$49/mo)</option>
                  </Select>
                  <p className="rounded-md border bg-muted/40 p-2 text-xs text-muted-foreground">
                    <strong>platform_managed</strong> — OUTRENA resolves the API key from the platform
                    secret store at call time. Tenant pays a +$49/mo delta per{" "}
                    <code>Plan.feature_flags.integration_path_pricing</code>.
                    <br />
                    <strong>tenant_managed</strong> — tenant provides its own keys (encrypted at rest
                    via Fernet in the tenant schema's <code>ProspectingIntegration.api_key_encrypted</code>).
                  </p>
                </div>
                <Button onClick={handleSaveIntegrationMode} disabled={updateModeMut.isPending}>
                  <Save className="h-4 w-4" />
                  {updateModeMut.isPending ? "Saving…" : "Save Integration Mode"}
                </Button>
              </CardContent>
            </Card>

            {/* Notifications (placeholder) */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bell className="h-5 w-5" />
                  Notifications
                </CardTitle>
                <CardDescription>Alert channels for platform events.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <div className="flex items-center gap-2 rounded-md border p-3">
                  <Mail className="h-4 w-4" />
                  <span>Email alerts: ops@outrena.io</span>
                  <Badge variant="success" className="ml-auto">
                    Configured
                  </Badge>
                </div>
                <div className="flex items-center gap-2 rounded-md border p-3">
                  <Shield className="h-4 w-4" />
                  <span>Slack webhook: #outrena-alerts</span>
                  <Badge variant="success" className="ml-auto">
                    Configured
                  </Badge>
                </div>
                <div className="flex items-center gap-2 rounded-md border p-3">
                  <Bell className="h-4 w-4" />
                  <span>PagerDuty: critical only</span>
                  <Badge variant="success" className="ml-auto">
                    Configured
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  Audit Trail
                </CardTitle>
                <CardDescription>
                  Integration mode changes are written to <code>platform_audit_log</code> server-side.
                </CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                <p>
                  Created {formatDateTime(config.created_at)} · Last updated {formatDateTime(config.updated_at)}.
                </p>
                <p className="mt-2 text-xs">
                  Visit <code>Platform Admin → Audit Logs</code> for the full history of integration_mode
                  transitions on this tenant.
                </p>
              </CardContent>
            </Card>
          </div>
        )}
    </div>
  );
}
