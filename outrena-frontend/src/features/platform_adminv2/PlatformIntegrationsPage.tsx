/**
 * PlatformIntegrationsPage.tsx — SUPER_ADMIN platform-managed integrations.
 * Mounted at /platform-admin/integrations.
 */
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function PlatformIntegrationsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Integrations"
        description="Manage platform-level integration credentials shared across tenants."
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Shared Integrations</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Platform-managed integration configuration coming soon.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
