/**
 * PipelinePage.tsx — 5-stage GTM workflow orchestrator.
 *
 * Gaps closed:
 *   PL-1  5-stage board: Thesis → Signals → Scoring → Briefs → Campaign
 *   PL-2  Run each stage individually; button disabled until thesis is done
 *   PL-3  Pipeline progress metrics: completed count + progress bar
 *   PL-4  (handled via Prospects page add-to-campaign; pipeline itself is
 *          ICP-scoped, not per-prospect add)
 *
 * API contract (backend schemas.py):
 *   POST /api/v1/pipeline/run-stage
 *     body  : { stage, icp_id?, llm_config_id?, product_name?, target_industries?,
 *               product_description?, key_value_props?, prospect_ids? }
 *             note: target_industries and key_value_props are plain strings (not arrays)
 *     return: { success, stage, result, error }
 *
 *   GET /api/v1/pipeline/status?icp_id=
 *     return: { stages_completed, current_stage, thesis_result,
 *               signals_result, scoring_result, briefs_result }
 *
 *   GET /api/v1/llm-configs
 *     return: [{ id, display_name, model_name, is_active, is_default, ... }]
 *             id is integer (GlobalLlmConfig PK)
 *
 *   GET /api/v1/icp-profiles
 *     return: array or { items: [] }
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  FileText,
  Lightbulb,
  Loader2,
  Megaphone,
  Play,
  Radio,
  RefreshCw,
  Star,
  Target,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/* ── Backend response types (matching schemas.py exactly) ──────────────── */

interface RunStageResponse {
  success: boolean;
  stage: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

interface StatusResponse {
  stages_completed: string[];
  current_stage: string | null;
  thesis_result: Record<string, unknown> | null;
  signals_result: Record<string, unknown> | null;
  scoring_result: Record<string, unknown> | null;
  briefs_result: Record<string, unknown> | null;
}

/* ── Dropdown types ─────────────────────────────────────────────────────── */

interface IcpProfileLite {
  id: string;
  name: string;
}

interface LlmConfigLite {
  id: number; // integer PK on GlobalLlmConfig
  display_name: string;
  model_name: string;
  is_active: boolean;
  is_default: boolean;
}

/* ── Stage config ───────────────────────────────────────────────────────── */

type StageName = "thesis" | "signals" | "scoring" | "briefs" | "campaign";

const STAGES: {
  name: StageName;
  label: string;
  number: number;
  description: string;
  icon: React.ReactNode;
}[] = [
  {
    name: "thesis",
    label: "GTM Thesis",
    number: 1,
    description: "Generate campaign strategy and messaging pillars.",
    icon: <Target className="h-4 w-4" />,
  },
  {
    name: "signals",
    label: "Signal Monitor",
    number: 2,
    description: "Identify buying signals for each prospect.",
    icon: <Radio className="h-4 w-4" />,
  },
  {
    name: "scoring",
    label: "Lead Scoring",
    number: 3,
    description: "Score prospects 1–100 and assign priority tiers.",
    icon: <Star className="h-4 w-4" />,
  },
  {
    name: "briefs",
    label: "Prospect Briefs",
    number: 4,
    description: "Generate 60-second pre-call briefs for top prospects.",
    icon: <FileText className="h-4 w-4" />,
  },
  {
    name: "campaign",
    label: "Campaign Build",
    number: 5,
    description: "Hand off to Email Studio for sequence generation.",
    icon: <Megaphone className="h-4 w-4" />,
  },
];

/* ── Thesis form ────────────────────────────────────────────────────────── */

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

/* ── Local stage state (client-side tracking) ───────────────────────────── */

type StageStatus = "idle" | "running" | "completed" | "failed";

interface LocalStageState {
  status: StageStatus;
  result: Record<string, unknown> | null;
  error: string | null;
}

const IDLE_STATE: LocalStageState = {
  status: "idle",
  result: null,
  error: null,
};

/* ── Component ──────────────────────────────────────────────────────────── */

export function PipelinePage() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [selectedIcpId, setSelectedIcpId] = useState("");
  const [selectedLlmId, setSelectedLlmId] = useState("");
  const [thesisForm, setThesisForm] = useState<ThesisForm>(EMPTY_THESIS);
  const [stages, setStages] = useState<Record<StageName, LocalStageState>>({
    thesis: IDLE_STATE,
    signals: IDLE_STATE,
    scoring: IDLE_STATE,
    briefs: IDLE_STATE,
    campaign: IDLE_STATE,
  });

  /* ── Queries ── */

  const icpQuery = useQuery<IcpProfileLite[]>({
    queryKey: ["icp-profiles", "lite"],
    queryFn: () =>
      http
        .get<unknown>("/api/v1/icp-profiles")
        .then((r) =>
          Array.isArray(r)
            ? r
            : ((r as { items?: IcpProfileLite[] })?.items ?? [])
        ),
    retry: false,
  });

  const llmQuery = useQuery<LlmConfigLite[]>({
    queryKey: ["llm-configs"],
    queryFn: () =>
      http
        .get<unknown>("/api/v1/llm-configs")
        .then((r) =>
          Array.isArray(r)
            ? r
            : ((r as { items?: LlmConfigLite[] })?.items ?? [])
        ),
    retry: false,
  });

  const statusQuery = useQuery<StatusResponse>({
    queryKey: ["pipeline", "status", selectedIcpId],
    queryFn: () => {
      const params = selectedIcpId ? `?icp_id=${selectedIcpId}` : "";
      return http.get<StatusResponse>(`/api/v1/pipeline/status${params}`);
    },
    retry: false,
  });

  // Hydrate local stage state from server status on first load
  useEffect(() => {
    const data = statusQuery.data;
    if (!data) return;
    const completed = new Set(data.stages_completed ?? []);
    setStages((prev) => {
      // Only hydrate if client has no results yet
      const hasClient = Object.values(prev).some((s) => s.status !== "idle");
      if (hasClient) return prev;
      const next = { ...prev } as Record<StageName, LocalStageState>;
      if (completed.has("thesis"))
        next.thesis = {
          status: "completed",
          result: data.thesis_result,
          error: null,
        };
      if (completed.has("signals"))
        next.signals = {
          status: "completed",
          result: data.signals_result,
          error: null,
        };
      if (completed.has("scoring"))
        next.scoring = {
          status: "completed",
          result: data.scoring_result,
          error: null,
        };
      if (completed.has("briefs"))
        next.briefs = {
          status: "completed",
          result: data.briefs_result,
          error: null,
        };
      if (completed.has("campaign"))
        next.campaign = { status: "completed", result: null, error: null };
      return next;
    });
  }, [statusQuery.data]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Run-stage mutation ── */

  const runMut = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      http.post<RunStageResponse>("/api/v1/pipeline/run-stage", body),
    onSuccess: (data) => {
      const stageName = data.stage as StageName;
      if (data.success) {
        setStages((prev) => ({
          ...prev,
          [stageName]: {
            status: "completed",
            result: data.result,
            error: null,
          },
        }));
        toast.success(`${stageName} stage completed`);
      } else {
        setStages((prev) => ({
          ...prev,
          [stageName]: {
            status: "failed",
            result: null,
            error: data.error ?? "Unknown error",
          },
        }));
        toast.error(`${stageName} failed: ${data.error}`);
      }
      qc.invalidateQueries({ queryKey: ["pipeline", "status"] });
    },
    onError: (err, vars) => {
      const stageName = (vars.stage as StageName) ?? "thesis";
      setStages((prev) => ({
        ...prev,
        [stageName]: {
          status: "failed",
          result: null,
          error: (err as Error)?.message ?? "Unknown error",
        },
      }));
      toast.error("Stage failed: " + ((err as Error)?.message ?? ""));
    },
  });

  /* ── Handlers ── */

  function handleRunStage(stageName: StageName) {
    if (stageName === "thesis" && !thesisForm.productName.trim()) {
      toast.error("Product Name is required for the Thesis stage");
      return;
    }

    // Mark running immediately for responsive UI
    setStages((prev) => ({
      ...prev,
      [stageName]: { status: "running", result: null, error: null },
    }));

    const body: Record<string, unknown> = {
      stage: stageName,
      ...(selectedIcpId && { icp_id: selectedIcpId }),
      ...(selectedLlmId && { llm_config_id: selectedLlmId }),
    };

    if (stageName === "thesis") {
      body.product_name = thesisForm.productName.trim();
      // Backend expects plain string (not array) per schemas.py
      if (thesisForm.targetIndustries.trim())
        body.target_industries = thesisForm.targetIndustries.trim();
      if (thesisForm.productDescription.trim())
        body.product_description = thesisForm.productDescription.trim();
      if (thesisForm.keyValueProps.trim())
        body.key_value_props = thesisForm.keyValueProps.trim();
    }

    runMut.mutate(body);
  }

  function handleRunAll() {
    if (!thesisForm.productName.trim()) {
      toast.error("Product Name is required before running the pipeline");
      return;
    }
    handleRunStage("thesis");
  }

  /* ── Derived ── */

  const completedCount = Object.values(stages).filter(
    (s) => s.status === "completed"
  ).length;

  const thesisDone = stages.thesis.status === "completed";
  const isAnyRunning = runMut.isPending;

  const activeStages = useMemo(() => {
    const llms = llmQuery.data ?? [];
    const defaultLlm = llms.find((c) => c.is_default && c.is_active);
    if (defaultLlm && !selectedLlmId) {
      // Auto-select default LLM silently (string id for Select)
    }
    return llms;
  }, [llmQuery.data, selectedLlmId]);

  /* ── Render ── */

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline"
        description="5-stage GTM workflow: Thesis → Signals → Scoring → Briefs → Campaign"
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                qc.invalidateQueries({ queryKey: ["pipeline", "status"] })
              }
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button
              size="sm"
              onClick={handleRunAll}
              disabled={isAnyRunning}
            >
              {isAnyRunning ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Pipeline
            </Button>
          </>
        }
      />

      {/* PL-3 — Progress metrics */}
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
            className="h-2"
          />
        </CardContent>
      </Card>

      {/* Config row */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Configuration</CardTitle>
          <CardDescription>
            Select an ICP profile and LLM model used across all pipeline stages.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>ICP Profile (optional)</Label>
              <Select value={selectedIcpId} onValueChange={setSelectedIcpId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select ICP…" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">No ICP selected</SelectItem>
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
              <Label>LLM Model (optional)</Label>
              <Select value={selectedLlmId} onValueChange={setSelectedLlmId}>
                <SelectTrigger>
                  <SelectValue placeholder="Use platform default…" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Platform default</SelectItem>
                  {llmQuery.isLoading ? (
                    <SelectItem value="_loading" disabled>
                      Loading…
                    </SelectItem>
                  ) : (
                    activeStages
                      .filter((c) => c.is_active)
                      .map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.display_name}
                          {c.is_default ? " (default)" : ""} —{" "}
                          {c.model_name}
                        </SelectItem>
                      ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Prospects Available</Label>
              <div className="flex items-center h-9 px-3 rounded-md border bg-muted/50 text-sm text-muted-foreground">
                {statusQuery.isLoading
                  ? "Loading…"
                  : `${completedCount} stage${completedCount !== 1 ? "s" : ""} done`}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* PL-1 — 5-stage pipeline stepper */}
      <div className="space-y-3">
        {STAGES.map((stage, idx) => {
          const s = stages[stage.name];
          const isDone = s.status === "completed";
          const isFailed = s.status === "failed";
          const isRunning = s.status === "running";

          // Stage is runnable if: thesis done (for stages 2+), not currently running
          const canRun =
            stage.name === "thesis"
              ? true
              : thesisDone;

          return (
            <Card
              key={stage.name}
              className={cn(
                "transition-all",
                isDone && "border-emerald-300 bg-emerald-50/20",
                isFailed && "border-destructive/40",
                isRunning && "border-primary/50 bg-primary/[0.02]"
              )}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  {/* Stage number bubble */}
                  <div
                    className={cn(
                      "shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold",
                      isDone
                        ? "bg-emerald-500"
                        : isRunning
                        ? "bg-primary"
                        : isFailed
                        ? "bg-destructive"
                        : "bg-muted-foreground/30"
                    )}
                  >
                    {isDone ? (
                      <CheckCircle2 className="h-5 w-5" />
                    ) : (
                      stage.number
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    {/* Header row */}
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2">
                        {stage.icon}
                        <h4 className="font-semibold text-sm">
                          {stage.label}
                        </h4>
                        {isDone && (
                          <Badge
                            variant="outline"
                            className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200"
                          >
                            Done
                          </Badge>
                        )}
                        {isFailed && (
                          <Badge variant="destructive" className="text-xs">
                            Failed
                          </Badge>
                        )}
                        {isRunning && (
                          <Loader2 className="h-4 w-4 animate-spin text-primary" />
                        )}
                      </div>

                      {/* PL-2 — Run stage button */}
                      <Button
                        size="sm"
                        variant={isDone ? "outline" : "default"}
                        disabled={isRunning || isAnyRunning || !canRun}
                        onClick={() => handleRunStage(stage.name)}
                      >
                        {isRunning ? (
                          <>
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Running…
                          </>
                        ) : isDone ? (
                          <>
                            <RefreshCw className="h-3 w-3" />
                            Re-run
                          </>
                        ) : (
                          <>
                            <Play className="h-3 w-3" />
                            Run Stage
                          </>
                        )}
                      </Button>
                    </div>

                    <p className="text-xs text-muted-foreground mb-3">
                      {stage.description}
                    </p>

                    {/* Stage 1 — Thesis form */}
                    {stage.name === "thesis" && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 border-t pt-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Product Name *</Label>
                          <Input
                            className="h-8 text-xs"
                            placeholder="e.g. OUTRENA"
                            value={thesisForm.productName}
                            onChange={(e) =>
                              setThesisForm((f) => ({
                                ...f,
                                productName: e.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Target Industries</Label>
                          <Input
                            className="h-8 text-xs"
                            placeholder="e.g. SaaS, FinTech, B2B"
                            value={thesisForm.targetIndustries}
                            onChange={(e) =>
                              setThesisForm((f) => ({
                                ...f,
                                targetIndustries: e.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-1 sm:col-span-2">
                          <Label className="text-xs">
                            Product Description *
                          </Label>
                          <Textarea
                            className="text-xs"
                            rows={2}
                            placeholder="Describe what you sell, who it's for, and the key outcome it delivers…"
                            value={thesisForm.productDescription}
                            onChange={(e) =>
                              setThesisForm((f) => ({
                                ...f,
                                productDescription: e.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-1 sm:col-span-2">
                          <Label className="text-xs">Key Value Props</Label>
                          <Input
                            className="h-8 text-xs"
                            placeholder="e.g. 3x pipeline in 90 days, 40% reply rate"
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

                    {/* Thesis results */}
                    {stage.name === "thesis" && isDone && s.result && (
                      <div className="mt-3 border-t pt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                        {(
                          [
                            "targetSegment",
                            "outreachAngle",
                            "competitiveDifferentiator",
                            "objectionStrategy",
                          ] as const
                        ).map((key) =>
                          (s.result as Record<string, unknown>)[key] ? (
                            <div
                              key={key}
                              className="bg-muted/50 rounded-lg p-2"
                            >
                              <p className="text-xs font-medium capitalize mb-0.5">
                                {key.replace(/([A-Z])/g, " $1")}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {String(
                                  (s.result as Record<string, unknown>)[key]
                                )}
                              </p>
                            </div>
                          ) : null
                        )}
                      </div>
                    )}

                    {/* Signals results */}
                    {stage.name === "signals" && isDone && s.result && (
                      <div className="mt-3 border-t pt-3 flex gap-6 text-center">
                        {[
                          ["monitored", "Monitored"],
                          [
                            String(
                              (
                                (s.result as Record<string, unknown>)
                                  .signals as unknown[]
                              )?.length ?? 0
                            ),
                            "Signals Found",
                          ],
                        ].map(([val, label]) => (
                          <div key={label}>
                            <p className="text-lg font-bold">{val}</p>
                            <p className="text-xs text-muted-foreground">
                              {label}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Scoring results */}
                    {stage.name === "scoring" && isDone && s.result && (
                      <div className="mt-3 border-t pt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                        {(
                          [
                            ["scored", "Scored", ""],
                            ["TIER_1", "Tier 1 (80-100)", "text-emerald-600"],
                            ["TIER_2", "Tier 2 (60-79)", "text-amber-600"],
                            ["TIER_3", "Tier 3-4 (<60)", "text-muted-foreground"],
                          ] as const
                        ).map(([key, label, cls]) => {
                          const val =
                            key === "scored"
                              ? String(
                                  (s.result as Record<string, unknown>)
                                    .scored ?? 0
                                )
                              : String(
                                  (
                                    (s.result as Record<string, unknown>)
                                      .results as Record<string, unknown>[]
                                  )?.filter(
                                    (r) => r.tier === key
                                  ).length ?? 0
                                );
                          return (
                            <div
                              key={key}
                              className="bg-muted/40 rounded-lg p-2"
                            >
                              <p className={cn("text-lg font-bold", cls)}>
                                {val}
                              </p>
                              <p className="text-[10px] text-muted-foreground">
                                {label}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Briefs results */}
                    {stage.name === "briefs" && isDone && s.result && (
                      <div className="mt-3 border-t pt-3">
                        <p className="text-xs font-medium">
                          {String(
                            (s.result as Record<string, unknown>).count ?? 0
                          )}{" "}
                          prospect briefs generated
                        </p>
                      </div>
                    )}

                    {/* Campaign handoff */}
                    {stage.name === "campaign" && isDone && (
                      <div className="mt-3 border-t pt-3 text-center">
                        <p className="text-xs text-muted-foreground mb-3">
                          Pipeline complete! Use the thesis, signals, and
                          briefs in{" "}
                          <strong>Email Studio</strong> to build your campaign.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate("/outreach/email-studio")}
                        >
                          <ExternalLink className="h-3 w-3" />
                          Open Email Studio
                        </Button>
                      </div>
                    )}

                    {/* Error display */}
                    {isFailed && s.error && (
                      <p className="mt-2 text-xs text-destructive">
                        {s.error}
                      </p>
                    )}
                  </div>
                </div>

                {/* Connector arrow between cards */}
                {idx < STAGES.length - 1 && (
                  <div className="flex justify-center mt-2">
                    <ArrowRight className="h-4 w-4 text-muted-foreground/40 rotate-90" />
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* About section */}
      <Card className="border-blue-100 bg-blue-50/40">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-blue-600" />
            About the 5-Stage Outbound Pipeline
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            The OUTRENA Pipeline chains AI agents into a complete outbound
            workflow. Each stage builds on the previous one's output.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-xs">
            {[
              [<Target className="h-3 w-3" />, "Stage 1: Generate a GTM campaign thesis with messaging pillars and cadence"],
              [<Radio className="h-3 w-3" />, "Stage 2: Monitor all prospects for buying signals (job openings, funding, news)"],
              [<Star className="h-3 w-3" />, "Stage 3: Score every prospect 1–100 and assign TIER_1 through TIER_4"],
              [<FileText className="h-3 w-3" />, "Stage 4: Generate 60-second prospect briefs with talking points"],
              [<Megaphone className="h-3 w-3" />, "Stage 5: Hand off to Email Studio for sequence generation"],
            ].map(([icon, text], i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="shrink-0 mt-0.5">{icon as React.ReactNode}</span>
                <span>{text as string}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}