/**
 * FlowTemplatesPage.tsx — Pre-built flow templates for quick setup.
 *
 * Shows 3 canonical templates (Enterprise ABM, Partner Recruitment, PLG Volume)
 * with source/enrichment platform badges, gate strictness, and recommended-for
 * tags. "Use Template" clones via API; "Create from Scratch" navigates to
 * /prospecting/flows.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  LayoutTemplate,
  Plus,
  Copy,
  RefreshCw,
  Loader2,
  Lightbulb,
  ShieldCheck,
  Building2,
  Users2,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { flowTemplatesApi } from "@/services/apiClient";
import type { FlowTemplate } from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/* ── Hardcoded fallback templates ────────────────────────────────────────── */

const FALLBACK_TEMPLATES: FlowTemplate[] = [
  {
    id: "tpl-enterprise-abm",
    name: "Enterprise ABM",
    description:
      "Account-based marketing for enterprise targets. Uses high-firmographic sources, deep enrichment, and strict quality gates to ensure only best-fit accounts enter the pipeline.",
    sourcePlatforms: ["Apollo", "LinkedIn Sales Nav", "Clearbit"],
    enrichmentPlatforms: ["Clearbit Enrichment", "Hunter", "Domain Enrich"],
    gateStrictness: "strict",
    recommendedFor: ["Enterprise SaaS", "High-ACV deals", "Named-account lists"],
    isTemplate: true,
    createdAt: "2025-01-01T00:00:00Z",
    updatedAt: "2025-01-01T00:00:00Z",
  },
  {
    id: "tpl-partner-recruit",
    name: "Partner Recruitment",
    description:
      "Source and qualify channel/reseller partners. Prioritizes partner-fit signals (existing integrations, vertical alignment) with moderate gate strictness.",
    sourcePlatforms: ["Apollo", "LinkedIn", "Google Maps"],
    enrichmentPlatforms: ["Domain Enrich", "Clearbit Enrichment"],
    gateStrictness: "moderate",
    recommendedFor: ["Channel programs", "Reseller recruitment", "ISV partnerships"],
    isTemplate: true,
    createdAt: "2025-01-01T00:00:00Z",
    updatedAt: "2025-01-01T00:00:00Z",
  },
  {
    id: "tpl-plg-volume",
    name: "PLG Volume",
    description:
      "High-volume prospecting for product-led-growth motions. Casts a wide net with lenient gates, then relies on in-product signals to narrow down.",
    sourcePlatforms: ["Apollo", "Hunter", "Google Maps"],
    enrichmentPlatforms: ["Domain Enrich", "Hunter"],
    gateStrictness: "lenient",
    recommendedFor: ["PLG SaaS", "SMB/ Mid-market", "Freemium-to-paid"],
    isTemplate: true,
    createdAt: "2025-01-01T00:00:00Z",
    updatedAt: "2025-01-01T00:00:00Z",
  },
];

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function strictnessBadge(
  strictness: FlowTemplate["gateStrictness"],
): { label: string; variant: "destructive" | "warning" | "success" } {
  switch (strictness) {
    case "strict":
      return { label: "Strict", variant: "destructive" };
    case "moderate":
      return { label: "Moderate", variant: "warning" };
    case "lenient":
      return { label: "Lenient", variant: "success" };
  }
}

function templateIcon(name: string) {
  if (name.includes("Enterprise")) return <Building2 className="h-5 w-5" />;
  if (name.includes("Partner")) return <Users2 className="h-5 w-5" />;
  if (name.includes("PLG")) return <Zap className="h-5 w-5" />;
  return <LayoutTemplate className="h-5 w-5" />;
}

/* ── Component ──────────────────────────────────────────────────────────── */

export function FlowTemplatesPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  /* ── Clone dialog state ──────────────────────────────────────────────── */
  const [cloneTarget, setCloneTarget] = useState<FlowTemplate | null>(null);
  const [cloneName, setCloneName] = useState("");

  /* ── Query ───────────────────────────────────────────────────────────── */
  const {
    data: serverTemplates,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<FlowTemplate[]>({
    queryKey: ["flow-templates"],
    queryFn: () => flowTemplatesApi.list(),
    retry: false,
  });

  const templates = serverTemplates?.length
    ? serverTemplates
    : FALLBACK_TEMPLATES;

  /* ── Clone mutation ──────────────────────────────────────────────────── */
  const cloneMut = useMutation({
    mutationFn: (body: { template_id: string; new_name?: string }) =>
      flowTemplatesApi.clone(body),
    onSuccess: (data) => {
      toast.success("Template cloned", {
        description: `"${data.name}" is now available in Flows.`,
      });
      qc.invalidateQueries({ queryKey: ["flows", "list"] });
      setCloneTarget(null);
      setCloneName("");
    },
    onError: () => toast.error("Failed to clone template"),
  });

  function openCloneDialog(tpl: FlowTemplate) {
    setCloneName(tpl.name + " (Copy)");
    setCloneTarget(tpl);
  }

  function handleClone() {
    if (!cloneTarget) return;
    cloneMut.mutate({
      template_id: cloneTarget.id,
      new_name: cloneName.trim() || undefined,
    });
  }

  /* ── Render ──────────────────────────────────────────────────────────── */
  return (
    <div className="space-y-6">
      <PageHeader
        title="Flow Templates"
        description="Pre-built prospecting flow templates to get started fast. Clone a template or build from scratch."
        actions={
          <>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={() => navigate("/prospecting/flows")}>
              <Plus className="h-4 w-4" />
              Create from Scratch
            </Button>
          </>
        }
      />

      {/* ── Template cards ─────────────────────────────────────────────── */}
      {isError ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <p className="text-sm font-medium">Failed to load templates</p>
            <p className="text-xs text-muted-foreground">
              {(error as Error)?.message ?? "Unknown error"}
            </p>
            <Button variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-64 w-full rounded-lg" />
          ))}
        </div>
      ) : templates.length === 0 ? (
        <EmptyState
          icon={<LayoutTemplate className="h-6 w-6" />}
          title="No templates available"
          description="Pre-built templates will appear here once configured by your admin."
          action={
            <Button onClick={() => navigate("/prospecting/flows")}>
              <Plus className="h-4 w-4" /> Create from Scratch
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {templates.map((tpl) => {
            const sb = strictnessBadge(tpl.gateStrictness);
            return (
              <Card key={tpl.id} className="flex flex-col">
                <CardHeader>
                  <div className="flex items-center gap-2 mb-1">
                    {templateIcon(tpl.name)}
                    <CardTitle className="text-lg">{tpl.name}</CardTitle>
                  </div>
                  <CardDescription>{tpl.description}</CardDescription>
                </CardHeader>
                <CardContent className="flex-1 space-y-3">
                  {/* Source platforms */}
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      Source Platforms
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {tpl.sourcePlatforms.map((p) => (
                        <Badge key={p} variant="secondary">
                          {p}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Enrichment platforms */}
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      Enrichment Platforms
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {tpl.enrichmentPlatforms.map((p) => (
                        <Badge key={p} variant="outline">
                          {p}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Gate strictness */}
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">
                      Gate strictness:
                    </span>
                    <Badge variant={sb.variant}>{sb.label}</Badge>
                  </div>

                  {/* Recommended for */}
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      Recommended For
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {tpl.recommendedFor.map((r) => (
                        <Badge key={r} variant="default" className="text-[10px]">
                          {r}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Use Template button */}
                  <Button
                    className="w-full mt-2"
                    onClick={() => openCloneDialog(tpl)}
                  >
                    <Copy className="h-4 w-4" />
                    Use Template
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* ── Pro Tips ───────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Lightbulb className="h-4 w-4" />
            When to Use Each Template
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-3">
          <div className="flex gap-2">
            <Building2 className="h-4 w-4 mt-0.5 shrink-0" />
            <p>
              <strong>Enterprise ABM</strong> — Best when you have a named
              account list, high-ACV deals, and need deep firmographic
              enrichment. Strict gates ensure only top-fit accounts reach your
              SDRs.
            </p>
          </div>
          <div className="flex gap-2">
            <Users2 className="h-4 w-4 mt-0.5 shrink-0" />
            <p>
              <strong>Partner Recruitment</strong> — Ideal for building channel
              or ISV programs. Sources partner-fit signals (existing tech stack
              overlap, vertical alignment) with moderate gate strictness.
            </p>
          </div>
          <div className="flex gap-2">
            <Zap className="h-4 w-4 mt-0.5 shrink-0" />
            <p>
              <strong>PLG Volume</strong> — Designed for product-led-growth
              motions where you want to cast a wide net. Lenient gates let more
              prospects through; rely on in-product usage signals to qualify
              downstream.
            </p>
          </div>
          <p className="italic">
            Tip: You can always edit a cloned flow after creation to fine-tune
            source steps, enrichment steps, and quality gates to your exact
            needs.
          </p>
        </CardContent>
      </Card>

      {/* ── Clone dialog ───────────────────────────────────────────────── */}
      <Dialog
        open={!!cloneTarget}
        onOpenChange={(o) => !o && setCloneTarget(null)}
      >
        <DialogClose onClose={() => setCloneTarget(null)} />
        <DialogHeader>
          <DialogTitle>Use Template</DialogTitle>
          <DialogDescription>
            Clone &ldquo;{cloneTarget?.name}&rdquo; into a new flow. You can
            rename it or keep the default name.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="clone-name">New Flow Name</Label>
            <Input
              id="clone-name"
              value={cloneName}
              onChange={(e) => setCloneName(e.target.value)}
              placeholder="My Flow Name"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setCloneTarget(null)}>
            Cancel
          </Button>
          <Button
            onClick={handleClone}
            disabled={cloneMut.isPending || !cloneName.trim()}
          >
            {cloneMut.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Cloning…
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Clone Template
              </>
            )}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
