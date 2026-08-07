/**
 * PipelinePage.tsx — 5-stage GTM workflow orchestrator.
 *
 * Stages: Thesis → Signals → Scoring → Briefs → Campaign
 * Each stage can be run individually or the pipeline auto-advances.
 * Thesis requires user inputs; subsequent stages consume prior outputs.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  // Workflow,
  Play,
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  ChevronRight,
  Lightbulb,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";

import { pipelineApi, http } from "@/services/apiClient";
import type {
  PipelineStageName,
  PipelineStageResult,
  PipelineRunStageInput,
} from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
// import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
// import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/* ── Constants ───────────────────────────────────────────────────────────── */

const STAGES: {
  name: PipelineStageName;
  label: string;
  number: number;
  description: string;
}[] = [
  {
    name: "thesis",
    label: "Thesis",
    number: 1,
    description:
      "Generate your GTM thesis: define the product, ICP, and core value propositions.",
  },
  {
    name: "signals",
    label: "Signals",
    number: 2,
    description:
      "Discover buying signals and intent data that match your thesis ICP.",
  },
  {
    name: "scoring",
    label: "Scoring",
    number: 3,
    description:
      "Score and rank prospects using ICP fit + signal strength composite scoring.",
  },
  {
    name: "briefs",
    label: "Briefs",
    number: 4,
    description:
      "Generate personalized outreach briefs tailored to each top-scored prospect.",
  },
  {
    name: "campaign",
    label: "Campaign",
    number: 5,
    description:
      "Package scored prospects + briefs into a campaign ready for Email Studio.",
  },
];

/* ── Dropdown types (lightweight) ───────────────────────────────────────── */

interface IcpProfileLite {
  id: string;
  name: string;
}

interface LlmConfigLite {
  id: string;
  display_name: string;
  model_name: string;
}

/* ── Thesis form state ──────────────────────────────────────────────────── */

interface ThesisForm {
  productName: string;
  targetIndustries: string;
  productDescription: string;
  keyValueProps: string;
}

const EMPTY_THESIS: ThesisForm = {
  productName: "",
  targetIndustries: "",
  productDescription: "",
  keyValueProps: "",
};

/* ── Helper ─────────────────────────────────────────────────────────────── */

// function stageIndex(name: PipelineStageName): number {
//   return STAGES.findIndex((s) => s.name === name);
// }

function statusIcon(status: PipelineStageResult["status"]) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
    case "running":
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
    case "failed":
      return <XCircle className="h-5 w-5 text-red-500" />;
    case "skipped":
      return <Circle className="h-5 w-5 text-muted-foreground" />;
    default:
      return <Circle className="h-5 w-5 text-muted-foreground/50" />;
  }
}

function statusBadgeVariant(
  status: PipelineStageResult["status"],
): "default" | "success" | "destructive" | "secondary" | "outline" {
  switch (status) {
    case "completed":
      return "success";
    case "running":
      return "default";
    case "failed":
      return "destructive";
    default:
      return "outline";
  }
}

/* ── Component ──────────────────────────────────────────────────────────── */

export function PipelinePage() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  /* ── Local state ─────────────────────────────────────────────────────── */
  const [selectedIcpId, setSelectedIcpId] = useState<string>("");
  const [selectedLlmId, setSelectedLlmId] = useState<string>("");
  const [thesisForm, setThesisForm] = useState<ThesisForm>(EMPTY_THESIS);
  const [stageResults, setStageResults] = useState<
    Record<PipelineStageName, PipelineStageResult | null>
  >({
    thesis: null,
    signals: null,
    scoring: null,
    briefs: null,
    campaign: null,
  });

  /* ── Dropdown queries ────────────────────────────────────────────────── */
  const icpQuery = useQuery<IcpProfileLite[]>({
    queryKey: ["icp-profiles", "lite"],
    queryFn: () => http.get<IcpProfileLite[]>("/api/v1/icp-profiles"),
  });

  const llmQuery = useQuery<LlmConfigLite[]>({
    queryKey: ["llm-configs", "lite"],
    queryFn: () => http.get<LlmConfigLite[]>("/api/v1/llm-configs"),
  });

  /* ── Pipeline status query ───────────────────────────────────────────── */
  const statusQuery = useQuery({
    queryKey: ["pipeline", "status"],
    queryFn: () => pipelineApi.status(),
  });

  // Hydrate stageResults from server status on first load
  useEffect(() => {
    const data = statusQuery.data;
    if (data?.stages) {
      const mapped = {} as Record<
        PipelineStageName,
        PipelineStageResult | null
      >;
      for (const s of data.stages) {
        mapped[s.stage] = s;
      }
      // Only hydrate if we don't already have client-side results
      const hasClientResults = Object.values(stageResults).some(Boolean);
      if (!hasClientResults) {
        setStageResults(mapped);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusQuery.data]);

  /* ── Run-stage mutation ──────────────────────────────────────────────── */
  const runStageMut = useMutation({
    mutationFn: (body: PipelineRunStageInput) => pipelineApi.runStage(body),
    onSuccess: (result) => {
      setStageResults((prev) => ({ ...prev, [result.stage]: result }));
      toast.success(`${result.stage} stage completed`);
      qc.invalidateQueries({ queryKey: ["pipeline", "status"] });
    },
    onError: (err) => {
      toast.error("Stage failed", {
        description: (err as Error)?.message ?? "Unknown error",
      });
    },
  });

  /* ── Derived state ───────────────────────────────────────────────────── */
  const completedCount = Object.values(stageResults).filter(
    (r) => r?.status === "completed",
  ).length;

  const currentStage: PipelineStageName | null = useMemo(() => {
    // First non-completed, non-skipped stage
    for (const s of STAGES) {
      const r = stageResults[s.name];
      if (!r || r.status === "pending" || r.status === "failed") return s.name;
    }
    return null; // all done
  }, [stageResults]);

  const isRunning = runStageMut.isPending;

  /* ── Handlers ────────────────────────────────────────────────────────── */
  function handleRunStage(stageName: PipelineStageName) {
    const body: PipelineRunStageInput = {
      stage: stageName,
      icp_id: selectedIcpId || undefined,
      llm_config_id: selectedLlmId || undefined,
    };

    if (stageName === "thesis") {
      if (!thesisForm.productName.trim()) {
        toast.error("Product Name is required for the Thesis stage");
        return;
      }
      body.product_name = thesisForm.productName.trim();
      body.target_industries = thesisForm.targetIndustries
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      body.product_description = thesisForm.productDescription.trim() || undefined;
      body.key_value_props = thesisForm.keyValueProps
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }

    // Mark as running immediately for responsive UI
    setStageResults((prev) => ({
      ...prev,
      [stageName]: {
        stage: stageName,
        status: "running",
        output: null,
        startedAt: new Date().toISOString(),
        completedAt: null,
        error: null,
      },
    }));

    runStageMut.mutate(body);
  }

  function handleRunAll() {
    // Run thesis first; subsequent stages auto-chain from server side.
    if (!thesisForm.productName.trim()) {
      toast.error("Product Name is required before running the pipeline");
      return;
    }
    handleRunStage("thesis");
  }

  /* ── Render ──────────────────────────────────────────────────────────── */
  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline"
        description="5-stage GTM workflow: Thesis → Signals → Scoring → Briefs → Campaign"
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => statusQuery.refetch()}
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={handleRunAll} disabled={isRunning}>
              {isRunning ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Pipeline
            </Button>
          </>
        }
      />

      {/* ── Config row: ICP + LLM ─────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Configuration</CardTitle>
          <CardDescription>
            Select an ICP profile and LLM model to use across all pipeline
            stages.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="icp-select">ICP Profile</Label>
              <Select
                value={selectedIcpId}
                onValueChange={setSelectedIcpId}
              >
                <SelectTrigger id="icp-select">
                  <SelectValue placeholder="Select ICP profile…" />
                </SelectTrigger>
                <SelectContent>
                  {icpQuery.isLoading ? (
                    <SelectItem value="_loading" disabled>
                      Loading…
                    </SelectItem>
                  ) : (
                    (icpQuery.data ?? []).map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="llm-select">LLM Model</Label>
              <Select
                value={selectedLlmId}
                onValueChange={setSelectedLlmId}
              >
                <SelectTrigger id="llm-select">
                  <SelectValue placeholder="Select LLM model…" />
                </SelectTrigger>
                <SelectContent>
                  {llmQuery.isLoading ? (
                    <SelectItem value="_loading" disabled>
                      Loading…
                    </SelectItem>
                  ) : (
                    (llmQuery.data ?? []).map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.display_name} ({c.model_name})
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Progress bar ──────────────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="font-medium">Pipeline Progress</span>
            <span className="text-muted-foreground">
              {completedCount} / {STAGES.length} stages completed
            </span>
          </div>
          <Progress
            value={(completedCount / STAGES.length) * 100}
            className="h-3"
          />
        </CardContent>
      </Card>

      {/* ── Stage stepper ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {STAGES.map((stage, idx) => {
          const result = stageResults[stage.name];
          const isCurrent = currentStage === stage.name;
          const isDone = result?.status === "completed";
          const isFailed = result?.status === "failed";
          const isStageRunning = result?.status === "running";

          return (
            <Card
              key={stage.name}
              className={cn(
                "relative transition-all",
                isCurrent && "ring-2 ring-primary",
                isDone && "border-emerald-300 dark:border-emerald-700",
                isFailed && "border-red-300 dark:border-red-700",
              )}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  {statusIcon(result?.status ?? "pending")}
                  <span className="text-xs font-semibold text-muted-foreground">
                    Stage {stage.number}
                  </span>
                </div>
                <CardTitle className="text-base">{stage.label}</CardTitle>
                <CardDescription className="text-xs">
                  {stage.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {result && (
                  <Badge variant={statusBadgeVariant(result.status)}>
                    {result.status}
                  </Badge>
                )}

                {/* Thesis form (only on thesis stage) */}
                {stage.name === "thesis" && (
                  <div className="space-y-2">
                    <div>
                      <Label className="text-xs">Product Name</Label>
                      <Input
                        className="h-8 text-xs"
                        placeholder="e.g. Outrena"
                        value={thesisForm.productName}
                        onChange={(e) =>
                          setThesisForm((f) => ({
                            ...f,
                            productName: e.target.value,
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Label className="text-xs">
                        Target Industries (comma-separated)
                      </Label>
                      <Input
                        className="h-8 text-xs"
                        placeholder="e.g. B2B SaaS, FinTech"
                        value={thesisForm.targetIndustries}
                        onChange={(e) =>
                          setThesisForm((f) => ({
                            ...f,
                            targetIndustries: e.target.value,
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Product Description</Label>
                      <Textarea
                        className="text-xs"
                        rows={2}
                        placeholder="Brief description of your product…"
                        value={thesisForm.productDescription}
                        onChange={(e) =>
                          setThesisForm((f) => ({
                            ...f,
                            productDescription: e.target.value,
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Label className="text-xs">
                        Key Value Props (comma-separated)
                      </Label>
                      <Input
                        className="h-8 text-xs"
                        placeholder="e.g. AI-powered outreach, 10x pipeline"
                        value={thesisForm.keyValueProps}
                        onChange={(e) =>
                          setThesisForm((f) => ({
                            ...f,
                            keyValueProps: e.target.value,
                          }))
                        }
                      />
                    </div>
                  </div>
                )}

                {/* Campaign handoff */}
                {stage.name === "campaign" && isDone && (
                  <Button
                    variant="outline"
                    className="w-full text-xs"
                    onClick={() => navigate("/outreach/email-studio")}
                  >
                    <ExternalLink className="h-3 w-3" />
                    Open Email Studio
                  </Button>
                )}

                {/* Run Stage button */}
                <Button
                  size="sm"
                  className="w-full text-xs"
                  disabled={
                    isStageRunning ||
                    isRunning ||
                    (stage.name !== "thesis" &&
                      !stageResults.thesis?.output &&
                      stageResults.thesis?.status !== "completed")
                  }
                  onClick={() => handleRunStage(stage.name)}
                >
                  {isStageRunning ? (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Running…
                    </>
                  ) : (
                    <>
                      <Play className="h-3 w-3" />
                      Run Stage
                    </>
                  )}
                </Button>

                {/* Chevron connector */}
                {idx < STAGES.length - 1 && (
                  <ChevronRight className="absolute -right-3 top-1/2 h-4 w-4 text-muted-foreground hidden lg:block" />
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* ── Results panel ─────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Stage Results</CardTitle>
          <CardDescription>
            Output from each completed pipeline stage.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {Object.values(stageResults).every((r) => !r) ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No results yet. Run a stage to see its output here.
            </p>
          ) : (
            <div className="space-y-4">
              {STAGES.map((stage) => {
                const result = stageResults[stage.name];
                if (!result) return null;
                return (
                  <div
                    key={stage.name}
                    className="rounded-md border p-3 space-y-1"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">
                        {stage.number}. {stage.label}
                      </span>
                      <Badge variant={statusBadgeVariant(result.status)}>
                        {result.status}
                      </Badge>
                      {result.error && (
                        <span className="text-xs text-red-500">
                          {result.error}
                        </span>
                      )}
                    </div>
                    {result.output && (
                      <pre className="text-xs bg-muted p-2 rounded overflow-x-auto max-h-40">
                        {JSON.stringify(result.output, null, 2)}
                      </pre>
                    )}
                    {result.completedAt && (
                      <p className="text-xs text-muted-foreground">
                        Completed at{" "}
                        {new Date(result.completedAt).toLocaleString()}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── About section ─────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Lightbulb className="h-4 w-4" />
            About the 5-Stage Pipeline
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            The OUTRENA Pipeline is a 5-stage GTM workflow that transforms a
            product thesis into a ready-to-send campaign:
          </p>
          <ol className="list-decimal list-inside space-y-1 ml-2">
            <li>
              <strong>Thesis</strong> — Define your product, ICP, and value
              propositions. The LLM generates a structured GTM thesis.
            </li>
            <li>
              <strong>Signals</strong> — Source buying signals and intent data
              matching the thesis ICP across multiple platforms.
            </li>
            <li>
              <strong>Scoring</strong> — Composite scoring (ICP fit × signal
              strength) ranks and prioritizes prospects.
            </li>
            <li>
              <strong>Briefs</strong> — Personalized outreach briefs are
              generated for each top-scored prospect using the thesis context.
            </li>
            <li>
              <strong>Campaign</strong> — Scored prospects + briefs are packaged
              into a campaign, ready for Email Studio sequencing.
            </li>
          </ol>
          <p>
            Each stage builds on the outputs of prior stages. You can run the
            full pipeline with <strong>Run Pipeline</strong> or execute
            individual stages step-by-step.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
