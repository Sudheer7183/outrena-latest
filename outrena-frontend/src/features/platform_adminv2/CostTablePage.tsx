/**
 * CostTablePage.tsx — SUPER_ADMIN LLM cost per tenant.
 * Mounted at /platform-admin/cost-table.
 */
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function CostTablePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Cost Table"
        description="Per-tenant LLM token cost breakdown."
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cost Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Per-tenant cost table coming soon.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
