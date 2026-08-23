/**
 * PlatformSettingsPage.tsx — SUPER_ADMIN global platform settings.
 * Mounted at /platform-admin/settings.
 */
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function PlatformSettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Settings"
        description="Global configuration for this OUTRENA instance."
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">LLM Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Manage global LLM provider credentials at{" "}
            <a href="/platform-admin/llm-configs" className="text-primary underline">
              /platform-admin/llm-configs
            </a>.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
