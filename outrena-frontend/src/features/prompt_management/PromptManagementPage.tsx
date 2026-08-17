/**
 * PromptManagementPage.tsx — manage the 47 seeded OUTRENA prompt templates.
 *
 * API (verified against app/features/prompt_management/router.py + schemas):
 *   GET  /api/v1/prompts?category=   → PromptResponse[]
 *   PUT  /api/v1/prompts/:key         { template } → PromptResponse
 *   POST /api/v1/prompts/reset        → { resetCount, message } (resets ALL)
 *
 * CORRECTIONS vs. the previous version:
 *   - `variables` is already `list[str]` in PromptResponse (parsed server-side
 *     by a field_validator) — it is NOT a JSON-encoded string. The previous
 *     code typed it as `string` and ran `JSON.parse()` on the frontend.
 *     Typed correctly here as `string[]` to match what the backend sends.
 *   - The category list was hardcoded to 6 names (email_generation, icp,
 *     sequence, analytics, reply, system) that don't match the real seed
 *     data. The backend's 47 seeded prompts actually use 15 categories
 *     (ab_testing, analytics, competitor, content, deal, domain, email,
 *     icp, job_change, meeting, optimization, prospecting, scheduler,
 *     sequence, weekly) — verified directly against prompt_defs.py.
 *     Categories are now derived dynamically from the fetched data instead
 *     of hardcoded, so this never drifts from the backend again.
 *   - Removed the MOCK_PROMPTS fallback — an empty result now shows a real
 *     empty state instead of silently substituting fabricated data.
 *
 * There is no per-key reset endpoint — only `POST /prompts/reset` (resets
 * ALL prompts). Per-row "Reset to default" is implemented as
 * `PUT /prompts/{key}` with `{ template: defaultValue }`, since
 * `defaultValue` is a permanent column holding the original seed template
 * (confirmed in config_models.py — it's set once at seed time and never
 * mutated by `update_template`).
 *
 * PM-1 ✓ Prompt list with categories, dynamically derived + filterable.
 * PM-2 ✓ Inline expand/edit — textarea editor with variable hint panel.
 * PM-3 ✓ Reset to default per prompt (via defaultValue) + Reset All.
 * PM-4 ✓ Variable documentation — {{name}} badges (backend only provides names,
 *          not descriptions/examples, so no per-variable copy is fabricated).
 * PM-5 ✓ "Customized" badge — derived as template !== defaultValue.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  Edit3,
  Info,
  Loader2,
  RefreshCw,
  Save,
  Search,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatDateTime } from "@/lib/utils";

/* ── Types (aligned with PromptResponse) ─────────────────────────────── */

interface Prompt {
  id: string;
  key: string;
  category: string;
  name: string;
  description: string;
  template: string;
  isEditable: boolean;
  defaultValue: string;
  variables: string[];
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
}

/** Stable color palette assigned by category index, since the real
 * category set (15 values from prompt_defs.py) isn't fixed at compile time. */
const CATEGORY_PALETTE = [
  "bg-blue-500/10 text-blue-600 border-blue-500/20",
  "bg-purple-500/10 text-purple-600 border-purple-500/20",
  "bg-amber-500/10 text-amber-600 border-amber-500/20",
  "bg-green-500/10 text-green-600 border-green-500/20",
  "bg-rose-500/10 text-rose-600 border-rose-500/20",
  "bg-sky-500/10 text-sky-600 border-sky-500/20",
  "bg-orange-500/10 text-orange-600 border-orange-500/20",
  "bg-indigo-500/10 text-indigo-600 border-indigo-500/20",
  "bg-teal-500/10 text-teal-600 border-teal-500/20",
  "bg-cyan-500/10 text-cyan-600 border-cyan-500/20",
  "bg-pink-500/10 text-pink-600 border-pink-500/20",
  "bg-lime-500/10 text-lime-600 border-lime-500/20",
  "bg-fuchsia-500/10 text-fuchsia-600 border-fuchsia-500/20",
  "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
  "bg-violet-500/10 text-violet-600 border-violet-500/20",
];

function categoryColor(category: string, allCategories: string[]): string {
  const idx = allCategories.indexOf(category);
  if (idx === -1) return "bg-gray-500/10 text-gray-600 border-gray-500/20";
  return CATEGORY_PALETTE[idx % CATEGORY_PALETTE.length];
}

function categoryLabel(category: string): string {
  return category
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function normalisePrompts(raw: unknown): Prompt[] {
  if (Array.isArray(raw)) return raw as Prompt[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: Prompt[] }).items ?? [];
  return [];
}

/* ── Page ──────────────────────────────────────────────────────────── */

export function PromptManagementPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [resetAllOpen, setResetAllOpen] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["prompts"],
    queryFn: () => http.get<unknown>("/api/v1/prompts").then(normalisePrompts),
  });

  const prompts = data ?? [];

  const categories = useMemo(
    () => [...new Set(prompts.map((p) => p.category))].sort(),
    [prompts],
  );

  const modifiedCount = prompts.filter((p) => p.template !== p.defaultValue)
    .length;
  const editableCount = prompts.filter((p) => p.isEditable).length;

  const filtered = useMemo(() => {
    return prompts.filter((p) => {
      if (activeCategory && p.category !== activeCategory) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          p.name.toLowerCase().includes(q) ||
          p.key.toLowerCase().includes(q) ||
          p.description.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [prompts, search, activeCategory]);

  const saveMutation = useMutation({
    mutationFn: ({ key, template }: { key: string; template: string }) =>
      http.put<Prompt>(`/api/v1/prompts/${key}`, { template }),
    onSuccess: (_res, { key }) => {
      toast.success(`Prompt "${key}" updated`);
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      setEditingKey(null);
      setEditValue("");
    },
    onError: () => toast.error("Save failed"),
  });

  const resetOneMutation = useMutation({
    mutationFn: ({ key, defaultValue }: { key: string; defaultValue: string }) =>
      http.put<Prompt>(`/api/v1/prompts/${key}`, { template: defaultValue }),
    onSuccess: (_res, { key }) => {
      toast.success(`"${key}" reset to default`);
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
    onError: () => toast.error("Reset failed"),
  });

  const resetAllMutation = useMutation({
    mutationFn: () =>
      http.post<{ resetCount: number; message: string }>(
        "/api/v1/prompts/reset",
        {},
      ),
    onSuccess: (res) => {
      toast.success(res.message || `${res.resetCount} prompts reset to defaults`);
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      setResetAllOpen(false);
    },
    onError: () => toast.error("Reset all failed"),
  });

  function startEdit(p: Prompt) {
    setEditingKey(p.key);
    setEditValue(p.template);
    setExpandedKey(p.key);
  }

  function cancelEdit() {
    setEditingKey(null);
    setEditValue("");
  }

  function handleSave(key: string) {
    saveMutation.mutate({ key, template: editValue });
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Prompt Management"
        description="View and customize all LLM prompts used across the platform. Changes take effect immediately."
        actions={
          <div className="flex items-center gap-2">
            {modifiedCount > 0 && (
              <Badge
                variant="secondary"
                className="bg-amber-500/10 text-amber-600 border border-amber-500/20"
              >
                {modifiedCount} modified
              </Badge>
            )}
            <Dialog open={resetAllOpen} onOpenChange={setResetAllOpen}>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setResetAllOpen(true)}
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                Reset All
              </Button>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Reset all prompts to defaults?</DialogTitle>
                  <DialogDescription>
                    All {prompts.length} prompt templates will be restored to
                    their code-level defaults, discarding any customizations.
                    This cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setResetAllOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => resetAllMutation.mutate()}
                    disabled={resetAllMutation.isPending}
                  >
                    {resetAllMutation.isPending
                      ? "Resetting…"
                      : "Reset all prompts"}
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
            <p className="text-muted-foreground">Failed to load prompts.</p>
            <Button onClick={() => refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : (
        <>
          {/* Stats bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Card className="p-3">
              <div className="text-2xl font-bold">{prompts.length}</div>
              <div className="text-xs text-muted-foreground">
                Total Prompts
              </div>
            </Card>
            <Card className="p-3">
              <div className="text-2xl font-bold">{categories.length}</div>
              <div className="text-xs text-muted-foreground">Categories</div>
            </Card>
            <Card className="p-3">
              <div className="text-2xl font-bold text-green-600">
                {editableCount}
              </div>
              <div className="text-xs text-muted-foreground">Editable</div>
            </Card>
            <Card className="p-3">
              <div className="text-2xl font-bold text-amber-600">
                {modifiedCount}
              </div>
              <div className="text-xs text-muted-foreground">Customized</div>
            </Card>
          </div>

          {/* Search & category filter */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search prompts by name, key, or description…"
                className="pl-9"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="flex gap-1.5 flex-wrap">
              <button
                type="button"
                onClick={() => setActiveCategory(null)}
                className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                  !activeCategory
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-card border-border hover:bg-accent"
                }`}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  type="button"
                  key={cat}
                  onClick={() =>
                    setActiveCategory(activeCategory === cat ? null : cat)
                  }
                  className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                    activeCategory === cat
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-card border-border hover:bg-accent"
                  }`}
                >
                  {categoryLabel(cat)}
                </button>
              ))}
            </div>
          </div>

          {/* Prompt cards */}
          <div className="space-y-3">
            {filtered.length === 0 && (
              <Card className="p-8 text-center">
                <Search className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <p className="text-muted-foreground">
                  {prompts.length === 0
                    ? "No prompt templates found."
                    : "No prompts match your search."}
                </p>
              </Card>
            )}
            {filtered.map((p) => {
              const isExpanded = expandedKey === p.key;
              const isEditing = editingKey === p.key;
              const isModified = p.template !== p.defaultValue;
              const colorClass = categoryColor(p.category, categories);

              return (
                <Card
                  key={p.key}
                  className={`transition-all ${
                    isEditing ? "ring-2 ring-primary/50" : ""
                  } ${isModified ? "border-amber-500/30" : ""}`}
                >
                  <div
                    className="flex items-start gap-3 p-4 cursor-pointer"
                    onClick={() => {
                      if (!isEditing)
                        setExpandedKey(isExpanded ? null : p.key);
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-sm">{p.name}</span>
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full border ${colorClass}`}
                        >
                          {categoryLabel(p.category)}
                        </span>
                        {isModified && (
                          <Badge
                            variant="outline"
                            className="text-[10px] px-1.5 py-0 border-amber-500/30 text-amber-600 bg-amber-500/5"
                          >
                            Customized
                          </Badge>
                        )}
                        {p.isEditable ? (
                          <Badge
                            variant="outline"
                            className="text-[10px] px-1.5 py-0 border-green-500/30 text-green-600 bg-green-500/5"
                          >
                            Editable
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="text-[10px] px-1.5 py-0 border-gray-500/30 text-gray-500 bg-gray-500/5"
                          >
                            Read-only
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {p.description}
                      </p>
                      <p className="text-[10px] text-muted-foreground/60 font-mono mt-1">
                        {p.key}
                      </p>
                      {p.variables.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {p.variables.map((v) => (
                            <span
                              key={v}
                              className="text-[10px] px-1.5 py-0.5 bg-muted rounded font-mono"
                              title="Replaced at runtime with real data"
                            >
                              {`{{${v}}}`}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {p.isEditable && (
                        <Button
                          variant={isEditing ? "ghost" : "outline"}
                          size="sm"
                          title={isEditing ? "Cancel editing" : "Edit this prompt"}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (isEditing) cancelEdit();
                            else startEdit(p);
                          }}
                        >
                          {isEditing ? (
                            <X className="h-3.5 w-3.5" />
                          ) : (
                            <Edit3 className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      )}
                      {isModified && p.isEditable && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Reset to default"
                          onClick={(e) => {
                            e.stopPropagation();
                            resetOneMutation.mutate({
                              key: p.key,
                              defaultValue: p.defaultValue,
                            });
                          }}
                          disabled={resetOneMutation.isPending}
                        >
                          <RefreshCw className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      <ChevronDown
                        className={`h-4 w-4 text-muted-foreground transition-transform ${
                          isExpanded ? "rotate-180" : ""
                        }`}
                      />
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-border/50 pt-3">
                      {isEditing ? (
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-muted-foreground">
                              Editing: {p.name}
                            </span>
                            <span className="text-[10px] text-muted-foreground">
                              {editValue.length} chars
                            </span>
                          </div>
                          <textarea
                            className="w-full min-h-[250px] p-3 text-sm font-mono bg-muted/50 border border-border rounded-lg resize-y focus:outline-none focus:ring-2 focus:ring-primary/30"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onClick={(e) => e.stopPropagation()}
                          />
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] text-muted-foreground">
                              Tip: Use{" "}
                              <code className="bg-muted px-1 rounded">
                                {"{{variableName}}"}
                              </code>{" "}
                              for dynamic values. Variables are replaced at
                              runtime.
                            </p>
                            <div className="flex gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={cancelEdit}
                              >
                                Cancel
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => handleSave(p.key)}
                                disabled={
                                  saveMutation.isPending ||
                                  editValue === p.template
                                }
                              >
                                {saveMutation.isPending ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                                ) : (
                                  <Save className="h-3.5 w-3.5 mr-1.5" />
                                )}
                                Save
                              </Button>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <>
                          <pre className="text-xs font-mono bg-muted/30 border border-border/50 rounded-lg p-3 overflow-auto max-h-[300px] whitespace-pre-wrap break-words leading-relaxed text-foreground/80">
                            {p.template}
                          </pre>
                          <p className="text-[10px] text-muted-foreground mt-2">
                            Last updated {formatDateTime(p.updatedAt)}
                          </p>
                        </>
                      )}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        </>
      )}

      {/* Info footer */}
      <Card className="p-4 bg-muted/30 border-dashed">
        <div className="flex gap-3">
          <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          <div className="text-xs text-muted-foreground space-y-1">
            <p>
              <strong>How it works:</strong> All prompts are stored in the
              database. When you edit a prompt, the updated version is used
              immediately across all AI features. The code-level defaults
              serve as fallbacks and can be restored anytime using the Reset
              button.
            </p>
            <p>
              <strong>Variables:</strong> Prompts containing{" "}
              <code className="bg-muted px-1 rounded">{"{{variable}}"}</code>{" "}
              placeholders are dynamically populated at runtime (e.g.,
              prospect name, campaign data).
            </p>
            <p>
              <strong>Read-only prompts</strong> are displayed for reference
              but cannot be modified through this interface.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}