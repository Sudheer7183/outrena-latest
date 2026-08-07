/**
 * SystemParamsPage.tsx — manage 30+ tenant system parameters.
 *
 * API:
 *   GET /api/v1/system-params    → SystemParam[]
 *   PUT /api/v1/system-params/{key} → SystemParam   (single update)
 *
 * Two-column layout: left = category sidebar list, right = form of inputs for
 * that category's params. Each param has key, label, value, type
 * (string/number/boolean/json). Save button → PUT all params in the active
 * category.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Settings } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { PageHeader } from "@/components/ui/page-header";
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
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type ParamType = "string" | "number" | "boolean" | "json";

interface SystemParam {
  key: string;
  label: string;
  category: string;
  value: string; // serialised — parsed by `type`
  type: ParamType;
  description?: string;
}

const CATEGORIES = ["autopilot", "email", "scoring", "limits"] as const;
type Category = (typeof CATEGORIES)[number];

const MOCK_PARAMS: SystemParam[] = [
  // autopilot
  {
    key: "autopilot.daily_cap",
    label: "Daily Prospect Cap",
    category: "autopilot",
    value: "200",
    type: "number",
    description: "Max new prospects sourced per autopilot run per day.",
  },
  {
    key: "autopilot.enrich_enabled",
    label: "Auto-Enrich Prospects",
    category: "autopilot",
    value: "true",
    type: "boolean",
    description: "Enrich new prospects with email + LinkedIn immediately.",
  },
  {
    key: "autopilot.cron",
    label: "Schedule (cron)",
    category: "autopilot",
    value: "0 8 * * 1-5",
    type: "string",
    description: "When the autopilot pipeline runs (weekdays 8am UTC).",
  },
  // email
  {
    key: "email.qa_threshold",
    label: "QA Score Threshold",
    category: "email",
    value: "0.75",
    type: "number",
    description: "Minimum QA score for an email to auto-pass.",
  },
  {
    key: "email.max_touches",
    label: "Max Touches per Sequence",
    category: "email",
    value: "7",
    type: "number",
    description: "Hard ceiling on touches in any single sequence.",
  },
  {
    key: "email.default_sender_name",
    label: "Default Sender Name",
    category: "email",
    value: "Outrena Team",
    type: "string",
  },
  {
    key: "email.unsubscribe_footer",
    label: "Unsubscribe Footer (JSON)",
    category: "email",
    value: '{"enabled": true, "text": "Reply STOP to unsubscribe"}',
    type: "json",
  },
  // scoring
  {
    key: "scoring.icp_weight",
    label: "ICP Match Weight",
    category: "scoring",
    value: "0.5",
    type: "number",
  },
  {
    key: "scoring.intent_weight",
    label: "Intent Signal Weight",
    category: "scoring",
    value: "0.3",
    type: "number",
  },
  {
    key: "scoring.seniority_boost",
    label: "Seniority Boost (JSON)",
    category: "scoring",
    value: '{"C_Suite": 1.2, "Director": 1.0, "IC": 0.6}',
    type: "json",
  },
  // limits
  {
    key: "limits.tenant_daily_sends",
    label: "Tenant Daily Send Limit",
    category: "limits",
    value: "5000",
    type: "number",
  },
  {
    key: "limits.per_domain_hourly",
    label: "Per-Domain Hourly Limit",
    category: "limits",
    value: "120",
    type: "number",
  },
  {
    key: "limits.warmup_enabled",
    label: "Auto-Warmup New Domains",
    category: "limits",
    value: "true",
    type: "boolean",
  },
];

function validateValue(p: SystemParam): string | null {
  if (p.type === "number") {
    if (Number.isNaN(Number(p.value))) return "Must be a number";
  }
  if (p.type === "boolean") {
    if (p.value !== "true" && p.value !== "false") return "Must be true or false";
  }
  if (p.type === "json") {
    try {
      JSON.parse(p.value);
    } catch {
      return "Invalid JSON";
    }
  }
  return null;
}

export function SystemParamsPage() {
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<Category>("autopilot");
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["system-params"],
    queryFn: () => http.get<SystemParam[]>("/api/v1/system-params"),
  });

  // BUG-03 FIX: empty API response falls through to mock ([] is truthy, ?? does not catch it)
  const params = (data && data.length > 0) ? data : MOCK_PARAMS;

  // Initialise drafts when params load or category changes.
  useEffect(() => {
    const next: Record<string, string> = {};
    params.forEach((p) => {
      next[p.key] = drafts[p.key] ?? p.value;
    });
    setDrafts(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const byCategory = useMemo(() => {
    const map: Record<string, SystemParam[]> = {};
    params.forEach((p) => {
      (map[p.category] ??= []).push(p);
    });
    return map;
  }, [params]);

  const activeParams = byCategory[activeCategory] ?? [];

  const saveMutation = useMutation({
    mutationFn: async (changedParams: SystemParam[]) => {
      // Backend only supports PUT /system-params/{key} for single params.
      // Iterate and call each individually.
      const results: SystemParam[] = [];
      for (const p of changedParams) {
        const res = await http.put<SystemParam>(
          `/api/v1/system-params/${encodeURIComponent(p.key)}`,
          { value: p.value },
        );
        results.push(res);
      }
      return results;
    },
    onSuccess: () => {
      toast.success("Parameters saved");
      queryClient.invalidateQueries({ queryKey: ["system-params"] });
    },
    onError: () => toast.error("Failed to save parameters"),
  });

  function setDraft(key: string, value: string) {
    setDrafts((d) => ({ ...d, [key]: value }));
  }

  function handleSave() {
    const payload = activeParams.map((p) => ({
      ...p,
      value: drafts[p.key] ?? p.value,
    }));
    // Validate
    for (const p of payload) {
      const err = validateValue(p);
      if (err) {
        toast.error(`${p.label}: ${err}`);
        return;
      }
    }
    saveMutation.mutate(payload);
  }

  function isDirty(p: SystemParam): boolean {
    return (drafts[p.key] ?? p.value) !== p.value;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Parameters"
        description="Tune the operational knobs that control autopilot, email, scoring, and limits."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[16rem_1fr]">
        {/* Category sidebar */}
        <Card className="h-fit">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Categories</CardTitle>
          </CardHeader>
          <CardContent className="p-2">
            <nav className="space-y-1">
              {CATEGORIES.map((c) => {
                const count = byCategory[c]?.length ?? 0;
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setActiveCategory(c)}
                    className={cn(
                      "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors",
                      activeCategory === c
                        ? "bg-accent font-medium text-accent-foreground"
                        : "hover:bg-accent/50",
                    )}
                  >
                    <span className="capitalize">{c}</span>
                    <Badge variant="secondary" className="text-xs">
                      {count}
                    </Badge>
                  </button>
                );
              })}
            </nav>
          </CardContent>
        </Card>

        {/* Active category form */}
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div className="space-y-1">
              <CardTitle className="capitalize">{activeCategory}</CardTitle>
              <CardDescription>
                {activeParams.length} parameter
                {activeParams.length === 1 ? "" : "s"} in this category.
              </CardDescription>
            </div>
            <Button
              onClick={handleSave}
              disabled={
                saveMutation.isPending ||
                !activeParams.some(isDirty)
              }
            >
              <Save className="h-4 w-4" />
              Save changes
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : activeParams.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed p-10 text-center">
                <Settings className="h-6 w-6 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  No parameters in this category.
                </p>
              </div>
            ) : (
              <div className="space-y-5">
                {activeParams.map((p) => {
                  const draftValue = drafts[p.key] ?? p.value;
                  const err = validateValue({ ...p, value: draftValue });
                  const dirty = isDirty(p);
                  return (
                    <div
                      key={p.key}
                      className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_2fr]"
                    >
                      <div className="space-y-1">
                        <Label
                          htmlFor={p.key}
                          className="flex items-center gap-2"
                        >
                          {p.label}
                          {dirty && (
                            <Badge variant="warning" className="text-[10px]">
                              edited
                            </Badge>
                          )}
                        </Label>
                        <p className="font-mono text-[11px] text-muted-foreground">
                          {p.key}
                        </p>
                        {p.description && (
                          <p className="text-xs text-muted-foreground">
                            {p.description}
                          </p>
                        )}
                      </div>

                      <div className="space-y-1">
                        {p.type === "boolean" ? (
                          <div className="flex items-center gap-3 rounded-md border p-3">
                            <Switch
                              checked={draftValue === "true"}
                              onCheckedChange={(c) =>
                                setDraft(p.key, String(c))
                              }
                            />
                            <span className="text-sm">
                              {draftValue === "true" ? "Enabled" : "Disabled"}
                            </span>
                          </div>
                        ) : p.type === "json" ? (
                          <Textarea
                            id={p.key}
                            value={draftValue}
                            onChange={(e) => setDraft(p.key, e.target.value)}
                            className={cn(
                              "min-h-[6rem] font-mono text-xs",
                              err && "border-red-500",
                            )}
                          />
                        ) : (
                          <Input
                            id={p.key}
                            type={p.type === "number" ? "number" : "text"}
                            value={draftValue}
                            onChange={(e) => setDraft(p.key, e.target.value)}
                            className={err ? "border-red-500" : ""}
                          />
                        )}
                        {err && (
                          <p className="text-xs text-red-600">{err}</p>
                        )}
                        <p className="text-[11px] uppercase text-muted-foreground">
                          type: {p.type}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
