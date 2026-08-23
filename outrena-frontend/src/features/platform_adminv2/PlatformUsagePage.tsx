/**
 * PlatformUsagePage.tsx — SUPER_ADMIN LLM and API usage overview.
 * Mounted at /platform-admin/usage.
 */
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function PlatformUsagePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Usage"
        description="Aggregate LLM token consumption and API call volumes."
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Usage Analytics</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Usage analytics and cost breakdown coming soon.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
