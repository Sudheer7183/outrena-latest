/**
 * SystemParamsPage.tsx — manage the 31 seeded tenant system parameters.
 *
 * API (verified against app/features/system_params/router.py + schemas):
 *   GET  /api/v1/system-params?category=  -> SystemParamResponse[]
 *   PUT  /api/v1/system-params/:key         { value } -> SystemParamResponse
 *   POST /api/v1/system-params/reset        -> { resetCount, message } (resets ALL)
 *
 * CORRECTIONS vs. the previous version: the previous page invented its own
 * shape (type: string|number|boolean|json, 4 hardcoded categories, 13 fake
 * MOCK_PARAMS) that doesn't match the real backend at all. The actual
 * SystemParamResponse has: key, category, label, description, impact,
 * valueType, value, defaultValue, minValue, maxValue, unit, isAdvanced.
 * The real 31 seeded params use 6 categories (analytics, email, llm,
 * mailbridge, prospecting, scheduler) - verified directly against
 * param_defs.py. Categories are derived dynamically from fetched data so
 * this never drifts from the backend again.
 *
 * Backend behavior note: `update_value` silently returns the UNCHANGED row
 * (200 OK, no error) if a numeric value falls outside [minValue, maxValue]
 * - it does not raise. This page checks the returned value against what was
 * sent and surfaces a client-side error when the save was silently rejected.
 *
 * SP-1: Grouped category cards (collapsible, count + modified badges).
 * SP-2: Per-param editor: label, value control, description, impact, range, save.
 * SP-3: Per-param save + reset, plus bulk "Save all changes" and "Reset All".
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Info,
  Loader2,
  RotateCcw,
  Save,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/* Types (aligned with SystemParamResponse) */

interface SystemParam {
  id: string;
  key: string;
  category: string;
  label: string;
  description: string;
  impact: string;
  valueType: "string" | "number" | "boolean" | "json";
  value: string;
  defaultValue: string;
  minValue: string | null;
  maxValue: string | null;
  unit: string | null;
  isAdvanced: boolean;
  createdAt: string;
  updatedAt: string;
}

function categoryLabel(category: string): string {
  return category.charAt(0).toUpperCase() + category.slice(1);
}

function validateDraft(p: SystemParam, draft: string): string | null {
  if (p.valueType === "number") {
    if (draft.trim() === "" || Number.isNaN(Number(draft))) return "Must be a number";
    const n = Number(draft);
    if (p.minValue !== null && n < Number(p.minValue))
      return `Must be >= ${p.minValue}${p.unit ? ` ${p.unit}` : ""}`;
    if (p.maxValue !== null && n > Number(p.maxValue))
      return `Must be <= ${p.maxValue}${p.unit ? ` ${p.unit}` : ""}`;
  }
  if (p.valueType === "boolean" && draft !== "true" && draft !== "false") {
    return "Must be true or false";
  }
  if (p.valueType === "json") {
    try {
      JSON.parse(draft);
    } catch {
      return "Invalid JSON";
    }
  }
  return null;
}

function normaliseParams(raw: unknown): SystemParam[] {
  if (Array.isArray(raw)) return raw as SystemParam[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: SystemParam[] }).items ?? [];
  return [];
}

export function SystemParamsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(),
  );
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [resetAllOpen, setResetAllOpen] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system-params"],
    queryFn: () =>
      http.get<unknown>("/api/v1/system-params").then(normaliseParams),
  });

  const params = data ?? [];

  const categories = useMemo(
    () => [...new Set(params.map((p) => p.category))].sort(),
    [params],
  );

  const modifiedCount = params.filter((p) => p.value !== p.defaultValue).length;
  const advancedCount = params.filter((p) => p.isAdvanced).length;

  const filtered = useMemo(() => {
    return params.filter((p) => {
      if (!showAdvanced && p.isAdvanced) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          p.label.toLowerCase().includes(q) ||
          p.key.toLowerCase().includes(q) ||
          p.description.toLowerCase().includes(q) ||
          p.category.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [params, search, showAdvanced]);

  const byCategory = useMemo(() => {
    const map: Record<string, SystemParam[]> = {};
    filtered.forEach((p) => {
      (map[p.category] ??= []).push(p);
    });
    return map;
  }, [filtered]);

  const saveMutation = useMutation({
    mutationFn: async ({ key, value }: { key: string; value: string }) => {
      const res = await http.put<SystemParam>(
        `/api/v1/system-params/${encodeURIComponent(key)}`,
        { value },
      );
      return { requested: value, result: res };
    },
    onSuccess: ({ requested, result }) => {
      if (result.value !== requested) {
        toast.error(
          `"${result.label}" was not updated - value outside allowed range (${result.minValue ?? "-inf"} to ${result.maxValue ?? "inf"}).`,
        );
      } else {
        toast.success(`Updated "${result.key}" - takes effect within 60s`);
      }
      setDrafts((d) => {
        const next = { ...d };
        delete next[result.key];
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ["system-params"] });
    },
    onError: () => toast.error("Failed to update parameter"),
    onSettled: () => setSavingKey(null),
  });

  const resetOneMutation = useMutation({
    mutationFn: ({ key, defaultValue }: { key: string; defaultValue: string }) =>
      http.put<SystemParam>(`/api/v1/system-params/${encodeURIComponent(key)}`, {
        value: defaultValue,
      }),
    onSuccess: (res) => {
      toast.success(`Reset "${res.key}" to default`);
      setDrafts((d) => {
        const next = { ...d };
        delete next[res.key];
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ["system-params"] });
    },
    onError: () => toast.error("Failed to reset parameter"),
  });

  const resetAllMutation = useMutation({
    mutationFn: () =>
      http.post<{ resetCount: number; message: string }>(
        "/api/v1/system-params/reset",
        {},
      ),
    onSuccess: (res) => {
      toast.success(
        res.message || `${res.resetCount} parameters reset to defaults`,
      );
      setDrafts({});
      queryClient.invalidateQueries({ queryKey: ["system-params"] });
      setResetAllOpen(false);
    },
    onError: () => toast.error("Failed to reset all parameters"),
  });

  function toggleCategory(cat: string) {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }

  function setDraft(key: string, value: string) {
    setDrafts((d) => ({ ...d, [key]: value }));
  }

  function handleSaveOne(p: SystemParam) {
    const draft = drafts[p.key];
    if (draft === undefined) return;
    const err = validateDraft(p, draft);
    if (err) {
      toast.error(`${p.label}: ${err}`);
      return;
    }
    setSavingKey(p.key);
    saveMutation.mutate({ key: p.key, value: draft });
  }

  function handleSaveAllDirty() {
    const dirty = params.filter(
      (p) => drafts[p.key] !== undefined && drafts[p.key] !== p.value,
    );
    if (dirty.length === 0) return;
    for (const p of dirty) {
      const err = validateDraft(p, drafts[p.key]);
      if (err) {
        toast.error(`${p.label}: ${err}`);
        return;
      }
    }
    dirty.forEach((p) => saveMutation.mutate({ key: p.key, value: drafts[p.key] }));
  }

  const dirtyCount = params.filter(
    (p) => drafts[p.key] !== undefined && drafts[p.key] !== p.value,
  ).length;

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="System Parameters"
        description="Every statistical threshold, benchmark, and tunable number in the platform is stored here. Changes take effect within 60 seconds - no redeploy needed."
        actions={
          <div className="flex items-center gap-2">
            {dirtyCount > 0 && (
              <Button onClick={handleSaveAllDirty} disabled={saveMutation.isPending}>
                <Save className="h-4 w-4 mr-2" />
                Save {dirtyCount} change{dirtyCount > 1 ? "s" : ""}
              </Button>
            )}
            <Dialog open={resetAllOpen} onOpenChange={setResetAllOpen}>
              <Button
                variant="outline"
                onClick={() => setResetAllOpen(true)}
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                Reset All
              </Button>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Reset all system parameters?</DialogTitle>
                  <DialogDescription>
                    All {params.length} parameters - thresholds, benchmarks,
                    and rate limits across every category - will be restored
                    to their code-level defaults. This affects live platform
                    behavior within 60 seconds and cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setResetAllOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => resetAllMutation.mutate()}
                    disabled={resetAllMutation.isPending}
                  >
                    {resetAllMutation.isPending ? "Resetting..." : "Reset all parameters"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Failed to load system parameters.
            </p>
            <Button onClick={() => refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card>
              <CardContent className="p-4">
                <div className="text-xs text-muted-foreground">
                  Total Parameters
                </div>
                <div className="text-2xl font-bold mt-1">{params.length}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-xs text-muted-foreground">Categories</div>
                <div className="text-2xl font-bold mt-1">
                  {categories.length}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-xs text-muted-foreground">
                  Modified from Default
                </div>
                <div className="text-2xl font-bold mt-1 text-amber-600">
                  {modifiedCount}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-xs text-muted-foreground">
                  Advanced (hidden)
                </div>
                <div className="text-2xl font-bold mt-1 text-muted-foreground">
                  {advancedCount}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="border-amber-200 bg-amber-50/50">
            <CardContent className="p-4 flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-sm text-amber-900">
                <p className="font-medium">
                  These parameters control core platform behavior.
                </p>
                <p className="text-xs mt-1 text-amber-800">
                  Read the "Impact" note before saving - each parameter
                  explains exactly what happens if you modify it. Changes
                  take effect within 60 seconds via the in-memory cache.
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex-1 min-w-[200px] relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search parameters by name, key, or description..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={showAdvanced}
                onCheckedChange={setShowAdvanced}
                id="advanced"
              />
              <Label htmlFor="advanced" className="text-xs cursor-pointer">
                Show advanced params
              </Label>
            </div>
          </div>

          <div className="space-y-3">
            {Object.entries(byCategory).map(([category, catParams]) => {
              const isExpanded = expandedCategories.has(category) || !!search;
              const catModified = catParams.filter(
                (p) => p.value !== p.defaultValue,
              ).length;
              return (
                <Card key={category}>
                  <div
                    className="pb-3 pt-6 px-6 cursor-pointer"
                    onClick={() => toggleCategory(category)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                        <CardTitle className="text-base">
                          {categoryLabel(category)}
                        </CardTitle>
                        <Badge variant="secondary" className="text-xs">
                          {catParams.length}
                        </Badge>
                        {catModified > 0 && (
                          <Badge
                            variant="outline"
                            className="text-xs text-amber-700 border-amber-300 bg-amber-50"
                          >
                            {catModified} modified
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  {isExpanded && (
                    <CardContent className="pt-0">
                      <div className="space-y-3">
                        {catParams.map((p) => (
                          <ParamRow
                            key={p.key}
                            param={p}
                            draft={drafts[p.key]}
                            onEdit={(val) => setDraft(p.key, val)}
                            onSave={() => handleSaveOne(p)}
                            onReset={() =>
                              resetOneMutation.mutate({
                                key: p.key,
                                defaultValue: p.defaultValue,
                              })
                            }
                            saving={savingKey === p.key}
                          />
                        ))}
                      </div>
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>

          {filtered.length === 0 && (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                <Info className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No parameters match your search.</p>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function ParamRow({
  param,
  draft,
  onEdit,
  onSave,
  onReset,
  saving,
}: {
  param: SystemParam;
  draft: string | undefined;
  onEdit: (val: string) => void;
  onSave: () => void;
  onReset: () => void;
  saving: boolean;
}) {
  const isModified = param.value !== param.defaultValue;
  const currentValue = draft !== undefined ? draft : param.value;
  const isEditing = draft !== undefined && draft !== param.value;
  const err = isEditing ? validateDraft(param, draft) : null;

  return (
    <div
      className={`border rounded-lg p-4 ${
        isModified ? "border-amber-200 bg-amber-50/30" : "border-border"
      }`}
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-semibold text-sm">{param.label}</h4>
            {param.isAdvanced && (
              <Badge variant="outline" className="text-[10px] text-muted-foreground">
                advanced
              </Badge>
            )}
            {isModified && (
              <Badge
                variant="outline"
                className="text-[10px] text-amber-700 border-amber-300 bg-amber-50"
              >
                modified
              </Badge>
            )}
            <code className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded font-mono">
              {param.key}
            </code>
          </div>
          <p className="text-xs text-muted-foreground">{param.description}</p>
          <div className="text-xs p-2 rounded bg-muted/50 border border-border">
            <span className="font-medium text-foreground">
              Impact if changed:{" "}
            </span>
            <span className="text-muted-foreground">{param.impact}</span>
          </div>
          {param.minValue !== null && param.maxValue !== null && (
            <p className="text-[10px] text-muted-foreground">
              Allowed range: {param.minValue} - {param.maxValue}{" "}
              {param.unit || ""}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label className="text-xs">
            Current value{" "}
            {param.unit && (
              <span className="text-muted-foreground">({param.unit})</span>
            )}
          </Label>
          <div className="flex items-center gap-2">
            {param.valueType === "boolean" ? (
              <div className="flex items-center gap-3 rounded-md border p-2 flex-1">
                <Switch
                  checked={currentValue === "true"}
                  onCheckedChange={(c) => onEdit(String(c))}
                />
                <span className="text-sm">
                  {currentValue === "true" ? "Enabled" : "Disabled"}
                </span>
              </div>
            ) : param.valueType === "json" ? (
              <textarea
                value={currentValue}
                onChange={(e) => onEdit(e.target.value)}
                className={`flex-1 min-h-[6rem] p-2 font-mono text-xs border rounded-md ${
                  err ? "border-red-500" : "border-border"
                }`}
              />
            ) : (
              <Input
                type={param.valueType === "number" ? "number" : "text"}
                value={currentValue}
                onChange={(e) => onEdit(e.target.value)}
                min={param.minValue ?? undefined}
                max={param.maxValue ?? undefined}
                step={param.valueType === "number" ? "any" : undefined}
                className={`font-mono text-sm ${err ? "border-red-500" : ""}`}
              />
            )}
            {isEditing && (
              <Button size="sm" onClick={onSave} disabled={saving || !!err}>
                {saving ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Save className="h-3 w-3" />
                )}
              </Button>
            )}
            {isModified && !isEditing && (
              <Button size="sm" variant="outline" onClick={onReset} title="Reset to default">
                <RotateCcw className="h-3 w-3" />
              </Button>
            )}
          </div>
          {err && <p className="text-xs text-red-600">{err}</p>}
          {isModified && (
            <p className="text-[10px] text-amber-700">
              Default was: <code className="font-mono">{param.defaultValue}</code>
            </p>
          )}
          {isEditing && !err && (
            <p className="text-[10px] text-blue-600">
              Press save to apply - takes effect within 60s
            </p>
          )}
        </div>
      </div>
    </div>
  );
}