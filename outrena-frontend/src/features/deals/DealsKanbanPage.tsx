/**
 * DealsKanbanPage.tsx — Pipeline Kanban with @dnd-kit drag-and-drop.
 *
 * Gaps closed:
 *   DL-1  Kanban board — 5 columns (Qualified → Proposal → Negotiation →
 *         Closed Won → Closed Lost) with drag-and-drop via @dnd-kit
 *   DL-2  Deal card fields: title, prospect name+company (looked up by
 *         prospectId), deal value, close date, health badge, notes excerpt
 *   DL-3  Add Deal dialog + Edit Deal dialog (title, value, stage, close
 *         date, notes)
 *   DL-4  Total pipeline value in header (active stages only)
 *   DL-5  Won / Lost totals displayed prominently in header metrics
 *
 * API contract:
 *   GET  /api/v1/deals/kanban  → KanbanBoardResponse { stages: KanbanStage[] }
 *   POST /api/v1/deals         → DealCreate body, returns DealResponse
 *   PUT  /api/v1/deals/{id}    → DealUpdate body, returns DealResponse
 *   DELETE /api/v1/deals/{id}  → 204
 *   GET  /api/v1/deals/{id}/health
 *   POST /api/v1/deals/{id}/deal-suggest
 *   GET  /api/v1/prospects     → list for prospect name lookup
 */
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MutableRefObject,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import {
  Activity,
  Edit3,
  GripVertical,
  HeartPulse,
  Plus,
  Sparkles,
  Trash2,
  TrendingUp,
  TrendingDown,
  DollarSign,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import type { Deal, KanbanBoard } from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn, formatCurrency, formatDate, truncate } from "@/lib/utils";

/* ── Stage config ───────────────────────────────────────────────────────── */

const STAGE_ORDER = [
  "qualified",
  "proposal",
  "negotiation",
  "closed_won",
  "closed_lost",
] as const;
type StageId = (typeof STAGE_ORDER)[number];

const STAGE_META: Record<
  StageId,
  { label: string; topBorder: string; chip: string }
> = {
  qualified: {
    label: "Qualified",
    topBorder: "border-t-slate-400",
    chip: "bg-slate-100 text-slate-700",
  },
  proposal: {
    label: "Proposal",
    topBorder: "border-t-violet-400",
    chip: "bg-violet-100 text-violet-700",
  },
  negotiation: {
    label: "Negotiation",
    topBorder: "border-t-amber-400",
    chip: "bg-amber-100 text-amber-700",
  },
  closed_won: {
    label: "Closed Won",
    topBorder: "border-t-emerald-400",
    chip: "bg-emerald-100 text-emerald-700",
  },
  closed_lost: {
    label: "Closed Lost",
    topBorder: "border-t-rose-400",
    chip: "bg-rose-100 text-rose-700",
  },
};

/* ── Prospect lookup type ───────────────────────────────────────────────── */

interface ProspectLite {
  id: string;
  firstName: string;
  lastName: string;
  company: string | null;
}

/* ── Health badge variant ───────────────────────────────────────────────── */

function healthVariant(
  status: string | null
): "default" | "success" | "warning" | "destructive" | "secondary" {
  if (!status) return "secondary";
  const s = status.toLowerCase();
  if (s === "green" || s.includes("healthy") || s.includes("good"))
    return "success";
  if (s === "yellow" || s.includes("risk") || s.includes("warn"))
    return "warning";
  if (s === "red" || s.includes("critical") || s.includes("lost"))
    return "destructive";
  return "secondary";
}

/* ── Deal card body (reused by DragOverlay) ─────────────────────────────── */

function DealCardView({
  deal,
  prospectName,
}: {
  deal: Deal;
  prospectName: string | null;
}) {
  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold leading-tight">{deal.title}</p>
        <span className="cursor-grab text-muted-foreground opacity-60 transition-opacity group-hover:opacity-100">
          <GripVertical className="h-4 w-4" />
        </span>
      </div>
      {/* DL-2 — prospect name + company */}
      {prospectName && (
        <p className="mt-0.5 text-xs text-muted-foreground">{prospectName}</p>
      )}
      {deal.notes && (
        <p className="mt-1 text-xs text-muted-foreground">
          {truncate(deal.notes, 56)}
        </p>
      )}
      <div className="mt-3 flex items-center justify-between">
        {/* DL-2 — deal value */}
        <span className="text-sm font-bold">{formatCurrency(deal.value)}</span>
        {deal.healthStatus && (
          <Badge
            variant={healthVariant(deal.healthStatus)}
            className="capitalize text-[10px]"
          >
            {deal.healthStatus.replace(/_/g, " ")}
          </Badge>
        )}
      </div>
      {/* DL-2 — close date */}
      <p className="mt-1 text-[11px] text-muted-foreground">
        Closes {formatDate(deal.expectedClose)}
      </p>
    </>
  );
}

/* ── Draggable deal card ─────────────────────────────────────────────────── */

function DealCard({
  deal,
  prospectName,
  onClick,
  draggedRef,
}: {
  deal: Deal;
  prospectName: string | null;
  onClick: () => void;
  draggedRef: MutableRefObject<boolean>;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: deal.id });
  const style: CSSProperties = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={() => {
        if (draggedRef.current) {
          draggedRef.current = false;
          return;
        }
        onClick();
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className="group cursor-grab rounded-md border bg-card p-3 shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <DealCardView deal={deal} prospectName={prospectName} />
    </div>
  );
}

/* ── Droppable column ────────────────────────────────────────────────────── */

function KanbanColumn({
  stage,
  deals,
  prospectMap,
  onDealClick,
  draggedRef,
}: {
  stage: StageId;
  deals: Deal[];
  prospectMap: Record<string, ProspectLite>;
  onDealClick: (deal: Deal) => void;
  draggedRef: MutableRefObject<boolean>;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  const meta = STAGE_META[stage];
  const total = deals.reduce((s, d) => s + d.value, 0);

  return (
    <div className="flex w-72 shrink-0 flex-col">
      <div
        className={cn(
          "rounded-t-lg border border-b-0 bg-muted/40 px-3 py-2 border-t-4",
          meta.topBorder
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{meta.label}</span>
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 text-[10px] font-bold",
                meta.chip
              )}
            >
              {deals.length}
            </span>
          </div>
          <span className="text-xs font-medium text-muted-foreground">
            {formatCurrency(total)}
          </span>
        </div>
      </div>
      <div
        ref={setNodeRef}
        className={cn(
          "flex min-h-[200px] flex-1 flex-col gap-2 rounded-b-lg border bg-muted/20 p-2 transition-colors",
          isOver && "bg-primary/5 ring-2 ring-inset ring-primary/30"
        )}
      >
        {deals.length === 0 ? (
          <div className="flex flex-1 items-center justify-center p-4 text-center text-xs text-muted-foreground">
            Drop deals here
          </div>
        ) : (
          deals.map((d) => {
            const p = d.prospectId ? prospectMap[d.prospectId] : null;
            const prospectName = p
              ? `${p.firstName} ${p.lastName}${p.company ? ` · ${p.company}` : ""}`
              : null;
            return (
              <DealCard
                key={d.id}
                deal={d}
                prospectName={prospectName}
                onClick={() => onDealClick(d)}
                draggedRef={draggedRef}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

/* ── Deal detail / edit dialog ───────────────────────────────────────────── */

interface HealthResult {
  healthStatus: string;
  healthReason: string;
  score?: number;
}
interface SuggestResult {
  suggestion: string;
  nextAction: string;
  confidence: number;
}

function DealDetailDialog({
  deal,
  onClose,
  onEdited,
  onDeleted,
}: {
  deal: Deal | null;
  onClose: () => void;
  onEdited: () => void;
  onDeleted: () => void;
}) {
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [suggest, setSuggest] = useState<SuggestResult | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    title: "",
    value: "",
    stage: "qualified" as StageId,
    expectedClose: "",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setHealth(null);
    setSuggest(null);
    setEditing(false);
    if (deal) {
      setEditForm({
        title: deal.title,
        value: String(deal.value),
        stage: (STAGE_ORDER.includes(deal.stage as StageId)
          ? deal.stage
          : "qualified") as StageId,
        expectedClose: deal.expectedClose
          ? deal.expectedClose.slice(0, 10)
          : "",
        notes: deal.notes ?? "",
      });
    }
  }, [deal?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function checkHealth() {
    if (!deal) return;
    setHealthLoading(true);
    try {
      const r = await http.get<HealthResult>(`/api/v1/deals/${deal.id}/health`);
      setHealth(r);
      toast.success("Health checked");
    } catch {
      toast.error("Health check failed");
    } finally {
      setHealthLoading(false);
    }
  }

  async function aiSuggest() {
    if (!deal) return;
    setSuggestLoading(true);
    try {
      const r = await http.post<SuggestResult>(
        `/api/v1/deals/${deal.id}/deal-suggest`,
        {}
      );
      setSuggest(r);
      toast.success("Suggestion ready");
    } catch {
      toast.error("AI suggest failed");
    } finally {
      setSuggestLoading(false);
    }
  }

  async function saveEdit() {
    if (!deal) return;
    setSaving(true);
    try {
      await http.put(`/api/v1/deals/${deal.id}`, {
        title: editForm.title.trim(),
        value: Number(editForm.value) || 0,
        stage: editForm.stage,
        expectedClose: editForm.expectedClose
          ? new Date(editForm.expectedClose).toISOString()
          : null,
        notes: editForm.notes.trim() || null,
      });
      toast.success("Deal updated");
      onEdited();
      onClose();
    } catch {
      toast.error("Failed to update deal");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deal) return;
    setDeleting(true);
    try {
      await http.delete(`/api/v1/deals/${deal.id}`);
      toast.success("Deal deleted");
      onDeleted();
      onClose();
    } catch {
      toast.error("Failed to delete deal");
    } finally {
      setDeleting(false);
    }
  }

  if (!deal) return null;

  return (
    <Dialog open={Boolean(deal)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {editing ? "Edit Deal" : deal.title}
          </DialogTitle>
          <DialogDescription>
            {deal.source} · created {formatDate(deal.createdAt)}
          </DialogDescription>
        </DialogHeader>

        {editing ? (
          /* DL-3 — Edit form */
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Title</Label>
              <Input
                value={editForm.title}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, title: e.target.value }))
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Value (USD)</Label>
                <Input
                  type="number"
                  value={editForm.value}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, value: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label>Stage</Label>
                <Select
                  value={editForm.stage}
                  onValueChange={(v) =>
                    setEditForm((f) => ({ ...f, stage: v as StageId }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STAGE_ORDER.map((s) => (
                      <SelectItem key={s} value={s}>
                        {STAGE_META[s].label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Expected close</Label>
              <Input
                type="date"
                value={editForm.expectedClose}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    expectedClose: e.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label>Notes</Label>
              <Textarea
                value={editForm.notes}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, notes: e.target.value }))
                }
                rows={3}
              />
            </div>
          </div>
        ) : (
          /* Read-only view */
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs uppercase text-muted-foreground">Value</p>
                <p className="font-semibold">{formatCurrency(deal.value)}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">Stage</p>
                <p className="font-semibold capitalize">
                  {deal.stage.replace(/_/g, " ")}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">
                  Expected close
                </p>
                <p className="font-semibold">
                  {formatDate(deal.expectedClose)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase text-muted-foreground">
                  Closed at
                </p>
                <p className="font-semibold">{formatDate(deal.closedAt)}</p>
              </div>
            </div>
            {deal.notes && (
              <div>
                <p className="text-xs uppercase text-muted-foreground">Notes</p>
                <p className="mt-1 text-sm">{deal.notes}</p>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={checkHealth}
                disabled={healthLoading}
              >
                <HeartPulse className="h-4 w-4" />
                {healthLoading ? "Checking…" : "Check Health"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={aiSuggest}
                disabled={suggestLoading}
              >
                <Sparkles className="h-4 w-4" />
                {suggestLoading ? "Thinking…" : "AI Next Step"}
              </Button>
            </div>
            {health && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Activity className="h-4 w-4" />
                    Deal Health
                    <Badge
                      variant={healthVariant(health.healthStatus)}
                      className="capitalize"
                    >
                      {health.healthStatus.replace(/_/g, " ")}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-sm text-muted-foreground">
                  {health.healthReason}
                </CardContent>
              </Card>
            )}
            {suggest && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <TrendingUp className="h-4 w-4" />
                    AI Recommendation
                    <Badge variant="secondary">
                      {Math.round(suggest.confidence * 100)}% confidence
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 pt-0 text-sm">
                  <p>{suggest.suggestion}</p>
                  <p className="font-medium">
                    Next action: {suggest.nextAction}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        <DialogFooter>
          {editing ? (
            <>
              <Button variant="outline" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button onClick={saveEdit} disabled={saving || !editForm.title.trim()}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive mr-auto"
                onClick={handleDelete}
                disabled={deleting}
              >
                <Trash2 className="h-4 w-4" />
                {deleting ? "Deleting…" : "Delete"}
              </Button>
              <Button variant="outline" onClick={() => setEditing(true)}>
                <Edit3 className="h-4 w-4" />
                Edit
              </Button>
              <Button variant="outline" onClick={onClose}>
                Close
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── New Deal dialog ─────────────────────────────────────────────────────── */

function NewDealDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [value, setValue] = useState("");
  const [stage, setStage] = useState<StageId>("qualified");
  const [expectedClose, setExpectedClose] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  function reset() {
    setTitle("");
    setValue("");
    setStage("qualified");
    setExpectedClose("");
    setNotes("");
  }

  async function submit() {
    if (!title.trim()) return;
    setSaving(true);
    try {
      await http.post<Deal>("/api/v1/deals", {
        title: title.trim(),
        value: Number(value) || 0,
        stage,
        notes: notes.trim() || null,
        expectedClose: expectedClose
          ? new Date(expectedClose).toISOString()
          : null,
        source: "manual",
      });
      toast.success("Deal created");
      onCreated();
      reset();
      onOpenChange(false);
    } catch {
      toast.error("Failed to create deal");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New Deal</DialogTitle>
          <DialogDescription>
            Add a fresh opportunity to the pipeline.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="nd-title">Title *</Label>
            <Input
              id="nd-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Acme — Pilot License"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="nd-value">Value (USD)</Label>
              <Input
                id="nd-value"
                type="number"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="28000"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Stage</Label>
              <Select
                value={stage}
                onValueChange={(v) => setStage(v as StageId)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STAGE_ORDER.map((s) => (
                    <SelectItem key={s} value={s}>
                      {STAGE_META[s].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nd-close">Expected close</Label>
            <Input
              id="nd-close"
              type="date"
              value={expectedClose}
              onChange={(e) => setExpectedClose(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nd-notes">Notes</Label>
            <Textarea
              id="nd-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Context, champion, next step…"
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              reset();
              onOpenChange(false);
            }}
          >
            Cancel
          </Button>
          <Button onClick={submit} disabled={saving || !title.trim()}>
            {saving ? "Creating…" : "Create Deal"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */

export function DealsKanbanPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detailDeal, setDetailDeal] = useState<Deal | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const draggedRef = useRef(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  /* ── Queries ── */

  const { data: boardData, isLoading } = useQuery<KanbanBoard>({
    queryKey: ["deals", "kanban"],
    queryFn: () => http.get<KanbanBoard>("/api/v1/deals/kanban"),
    retry: false,
  });

  // Prospects for name lookup (DL-2)
  const { data: prospects = [] } = useQuery<ProspectLite[]>({
    queryKey: ["prospects", "lite"],
    queryFn: () =>
      http
        .get<unknown>("/api/v1/prospects")
        .then((r) =>
          Array.isArray(r)
            ? r
            : ((r as { items?: ProspectLite[] })?.items ?? [])
        ),
    retry: false,
  });

  const prospectMap = useMemo(
    () => Object.fromEntries(prospects.map((p) => [p.id, p])),
    [prospects]
  ) as Record<string, ProspectLite>;

  // Use empty board when no data — never fall back to mocks
  const board = boardData ?? { stages: [] };

  /* ── Move mutation (optimistic) ── */

  const moveMutation = useMutation({
    mutationFn: ({
      dealId,
      stage,
    }: {
      dealId: string;
      stage: string;
    }) => http.put<Deal>(`/api/v1/deals/${dealId}`, { stage }),
    onMutate: async ({ dealId, stage }) => {
      await qc.cancelQueries({ queryKey: ["deals", "kanban"] });
      const previous = qc.getQueryData<KanbanBoard>(["deals", "kanban"]);
      if (previous) {
        const movedDeal = previous.stages
          .flatMap((s) => s.deals)
          .find((d) => d.id === dealId);
        const next: KanbanBoard = {
          stages: previous.stages.map((s) => ({
            ...s,
            deals: s.deals.filter((d) => d.id !== dealId),
          })),
        };
        if (movedDeal) {
          const target = next.stages.find((s) => s.id === stage);
          if (target)
            target.deals = [{ ...movedDeal, stage }, ...target.deals];
        }
        qc.setQueryData<KanbanBoard>(["deals", "kanban"], next);
      }
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous)
        qc.setQueryData<KanbanBoard>(["deals", "kanban"], ctx.previous);
      toast.error("Failed to move deal — reverted");
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["deals"] });
      toast.success(
        `Moved to ${STAGE_META[vars.stage as StageId]?.label ?? vars.stage}`
      );
    },
  });

  /* ── Derived metrics ── */

  const allDeals = useMemo(
    () => board.stages.flatMap((s) => s.deals),
    [board]
  );

  const activeDeal = activeId
    ? allDeals.find((d) => d.id === activeId) ?? null
    : null;

  // DL-4 — total pipeline value (active stages only, exclude closed)
  const pipelineValue = useMemo(
    () =>
      allDeals
        .filter((d) => d.stage !== "closed_won" && d.stage !== "closed_lost")
        .reduce((s, d) => s + d.value, 0),
    [allDeals]
  );

  // DL-5 — won and lost totals
  const wonTotal = useMemo(
    () =>
      allDeals
        .filter((d) => d.stage === "closed_won")
        .reduce((s, d) => s + d.value, 0),
    [allDeals]
  );
  const lostTotal = useMemo(
    () =>
      allDeals
        .filter((d) => d.stage === "closed_lost")
        .reduce((s, d) => s + d.value, 0),
    [allDeals]
  );

  /* ── Drag handlers ── */

  function handleDragStart(event: DragStartEvent) {
    draggedRef.current = true;
    setActiveId(String(event.active.id));
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;
    const dealId = String(active.id);
    const newStage = String(over.id) as StageId;
    const deal = allDeals.find((d) => d.id === dealId);
    if (!deal || deal.stage === newStage) return;
    if (!STAGE_ORDER.includes(newStage)) return;
    moveMutation.mutate({ dealId, stage: newStage });
  }

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["deals"] });
  }

  /* ── Render ── */

  return (
    <div className="space-y-6">
      <PageHeader
        title="Deals Pipeline"
        description="Drag cards across stages to update the pipeline. Click a card to view, edit, or get AI suggestions."
        actions={
          <Button onClick={() => setNewOpen(true)}>
            <Plus className="h-4 w-4" />
            New Deal
          </Button>
        }
      />

      {/* DL-4 + DL-5 — metrics header */}
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <div className="flex items-center gap-1.5">
          <DollarSign className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground">Pipeline:</span>
          <span className="font-semibold">{formatCurrency(pipelineValue)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <TrendingUp className="h-4 w-4 text-emerald-500" />
          <span className="text-muted-foreground">Won:</span>
          <span className="font-semibold text-emerald-600">
            {formatCurrency(wonTotal)}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <TrendingDown className="h-4 w-4 text-rose-500" />
          <span className="text-muted-foreground">Lost:</span>
          <span className="font-semibold text-rose-600">
            {formatCurrency(lostTotal)}
          </span>
        </div>
        <Badge variant="secondary" className="ml-auto">
          {allDeals.length} deal{allDeals.length !== 1 ? "s" : ""}
        </Badge>
      </div>

      {/* DL-1 — Kanban board */}
      {isLoading ? (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {STAGE_ORDER.map((s) => (
            <Skeleton key={s} className="h-72 w-72 shrink-0 rounded-lg" />
          ))}
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-4 overflow-x-auto pb-4">
            {STAGE_ORDER.map((stageId) => {
              const stageData = board.stages.find((s) => s.id === stageId);
              return (
                <KanbanColumn
                  key={stageId}
                  stage={stageId}
                  deals={stageData?.deals ?? []}
                  prospectMap={prospectMap}
                  onDealClick={setDetailDeal}
                  draggedRef={draggedRef}
                />
              );
            })}
          </div>
          <DragOverlay dropAnimation={null}>
            {activeDeal ? (
              <div className="w-72 rotate-2 cursor-grabbing rounded-md border bg-card p-3 shadow-lg">
                <DealCardView
                  deal={activeDeal}
                  prospectName={
                    activeDeal.prospectId
                      ? (() => {
                          const p = prospectMap[activeDeal.prospectId];
                          return p
                            ? `${p.firstName} ${p.lastName}`
                            : null;
                        })()
                      : null
                  }
                />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      {/* DL-3 — Detail / Edit dialog */}
      <DealDetailDialog
        deal={detailDeal}
        onClose={() => setDetailDeal(null)}
        onEdited={invalidate}
        onDeleted={invalidate}
      />

      {/* DL-3 — New Deal dialog */}
      <NewDealDialog
        open={newOpen}
        onOpenChange={setNewOpen}
        onCreated={invalidate}
      />
    </div>
  );
}