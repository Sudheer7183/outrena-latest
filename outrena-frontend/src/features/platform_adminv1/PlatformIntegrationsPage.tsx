/**
 * PlatformIntegrationsPage.tsx — SUPER_ADMIN dual-path integrations console.
 *
 * Under <PlatformAdminLayout>. Mounted at `/platform-admin/integrations`.
 *
 * Two panels:
 *   1. Per-tenant integration mode — table of tenants (from platformApi.tenants)
 *      with their current `integration_mode`. The SUPER_ADMIN can flip a
 *      tenant's mode between `platform_managed` and `tenant_managed` via the
 *      PATCH /admin/tenants/{id}/integration-mode endpoint.
 *   2. Platform integration catalog — read-only list of integration types
 *      showing which have a platform activation key configured
 *      (`has_platform_key`).
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  KeyRound,
  Library,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { platformApi, integrationConfigApi } from "@/services/apiClient";
import type {
  IntegrationCatalogEntry,
  IntegrationMode,
  TenantRow,
} from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
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
import { Skeleton } from "@/components/ui/skeleton";
import { NativeSelect as Select } from "@/components/ui/select";
import { EmptyState } from "@/components/ui/empty-state";

const MOCK_CATALOG: IntegrationCatalogEntry[] = [
  { type: "apollo", name: "Apollo.io", has_platform_key: true, description: "B2B contact data" },
  { type: "hunter", name: "Hunter.io", has_platform_key: true, description: "Email finder + verifier" },
  { type: "snov", name: "Snov.io", has_platform_key: false, description: "Prospecting + drip" },
  { type: "rocketreach", name: "RocketReach", has_platform_key: false, description: "Contact lookup" },
  { type: "clearbit", name: "Clearbit", has_platform_key: true, description: "Enrichment" },
  { type: "linkedin", name: "LinkedIn", has_platform_key: false, description: "Social selling" },
  { type: "gmail", name: "Gmail API", has_platform_key: true, description: "Mailbox integration" },
  { type: "outlook", name: "Outlook API", has_platform_key: true, description: "Microsoft mailbox" },
  { type: "sendgrid", name: "SendGrid", has_platform_key: true, description: "Email delivery" },
  { type: "postmark", name: "Postmark", has_platform_key: false, description: "Transactional email" },
  { type: "twilio", name: "Twilio", has_platform_key: false, description: "SMS + voice" },
];

// Tenant mode cache — in production, this is fetched per-tenant from
// /admin/tenants/{id}/config. Here we keep a local map for the mock fallback.
const MOCK_TENANT_MODES: Record<string, IntegrationMode> = {
  "t-1": "platform_managed",
  "t-2": "tenant_managed",
  "t-3": "platform_managed",
};

export function PlatformIntegrationsPage() {
  const queryClient = useQueryClient();
  const [tenantModes, setTenantModes] = useState<Record<string, IntegrationMode>>(
    { ...MOCK_TENANT_MODES },
  );

  const { data: tenants, isLoading: tenantsLoading } = useQuery({
    queryKey: ["platform", "tenants"],
    queryFn: () => platformApi.tenants(),
  });

  const { data: catalog, isLoading: catalogLoading } = useQuery({
    queryKey: ["platform", "integration-catalog"],
    queryFn: () => integrationConfigApi.catalog(),
  });

  const modeMutation = useMutation({
    mutationFn: ({ id, mode }: { id: string; mode: IntegrationMode }) =>
      integrationConfigApi.platformSetMode(id, mode),
    onSuccess: (_data, vars) => {
      setTenantModes((prev) => ({ ...prev, [vars.id]: vars.mode }));
      toast.success(`Tenant integration mode updated → ${vars.mode}`);
      queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
    },
    onError: () => toast.error("Failed to update integration mode"),
  });

  const tenantRows = tenants ?? [];
  const catalogRows = catalog ?? MOCK_CATALOG;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Integrations"
        description="Manage per-tenant integration mode (platform vs tenant keys) and the platform integration catalog."
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            Per-Tenant Integration Mode
          </CardTitle>
          <CardDescription>
            Flip a tenant between <strong>platform-managed</strong> (OUTRENA
            provides activation keys, +$49/mo) and <strong>tenant-managed</strong>{" "}
            (tenant provides their own API keys).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {tenantsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : tenantRows.length === 0 ? (
            <EmptyState
              icon={<ShieldCheck className="h-6 w-6" />}
              title="No tenants yet"
              description="Tenants will appear here once they sign up."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tenant</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Current mode</TableHead>
                  <TableHead className="text-right">Change mode</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenantRows.map((t: TenantRow) => {
                  const current =
                    tenantModes[t.id] ?? (t.id in MOCK_TENANT_MODES
                      ? MOCK_TENANT_MODES[t.id]
                      : "tenant_managed");
                  return (
                    <TableRow key={t.id}>
                      <TableCell className="font-medium">{t.name}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {t.slug}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{t.plan_name}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            t.status === "active"
                              ? "success"
                              : t.status === "suspended"
                                ? "destructive"
                                : "secondary"
                          }
                        >
                          {t.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={current === "platform_managed" ? "default" : "secondary"}
                        >
                          {current === "platform_managed"
                            ? "Platform-managed"
                            : "Tenant-managed"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Select
                            value={current}
                            onChange={(e) => {
                              const next = e.target.value as IntegrationMode;
                              modeMutation.mutate({ id: t.id, mode: next });
                            }}
                            className="h-8 w-44 text-xs"
                            disabled={
                              modeMutation.isPending &&
                              modeMutation.variables?.id === t.id
                            }
                          >
                            <option value="platform_managed">Platform-managed</option>
                            <option value="tenant_managed">Tenant-managed</option>
                          </Select>
                          {modeMutation.isPending &&
                            modeMutation.variables?.id === t.id && (
                              <RefreshCw className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                            )}
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

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Library className="h-5 w-5" />
            Platform Integration Catalog
          </CardTitle>
          <CardDescription>
            List of all supported integration types and whether the platform
            has an activation key configured. Without a platform key, tenants
            cannot use the platform-managed path for that integration.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {catalogLoading ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : catalogRows.length === 0 ? (
            <EmptyState
              icon={<Library className="h-6 w-6" />}
              title="No catalog entries"
              description="Integration catalog entries will appear here once configured."
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {catalogRows.map((entry) => (
                <div
                  key={entry.type}
                  className="flex flex-col gap-2 rounded-lg border p-4"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-semibold">{entry.name}</p>
                      <p className="font-mono text-xs uppercase text-muted-foreground">
                        {entry.type}
                      </p>
                    </div>
                    {entry.has_platform_key ? (
                      <Badge variant="success" className="gap-1">
                        <CheckCircle2 className="h-3 w-3" /> Platform key
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="gap-1">
                        <XCircle className="h-3 w-3" /> Tenant only
                      </Badge>
                    )}
                  </div>
                  {entry.description && (
                    <p className="text-xs text-muted-foreground">
                      {entry.description}
                    </p>
                  )}
                  <div className="mt-auto flex items-center gap-1 text-xs text-muted-foreground">
                    <KeyRound className="h-3 w-3" />
                    {entry.has_platform_key
                      ? "Available for platform-managed tenants"
                      : "Tenants must provide their own key"}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
