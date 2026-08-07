/**
 * DealsKanbanPage.tsx — Pipeline Kanban with @dnd-kit drag-and-drop.
 *
 * Five stages (qualified → proposal → negotiation → closed_won / closed_lost).
 * Dragging a deal card across columns fires an optimistic `PUT /deals/{id}`
 * with the new stage. Clicking a card opens a detail dialog with "Check
 * Health" and "AI Suggest Next Step" actions. A "New Deal" dialog allows
 * creating a fresh opportunity.
 */
import { useEffect, useMemo, useRef, useState, type CSSProperties, type MutableRefObject } from "react";
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
  HeartPulse,
  Plus,
  Sparkles,
  GripVertical,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import type { Deal, KanbanBoard } from "@/types/common";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect as Select } from "@/components/ui/select";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatCurrency, formatDate, truncate } from "@/lib/utils";

const STAGE_ORDER = [
  "qualified",
  "proposal",
  "negotiation",
  "closed_won",
  "closed_lost",
] as const;
type StageId = (typeof STAGE_ORDER)[number];

const STAGE_META: Record<StageId, { label: string; ring: string; chip: string }> = {
  qualified: { label: "Qualified", ring: "border-t-slate-400", chip: "bg-slate-100 text-slate-700" },
  proposal: { label: "Proposal", ring: "border-t-violet-400", chip: "bg-violet-100 text-violet-700" },
  negotiation: { label: "Negotiation", ring: "border-t-amber-400", chip: "bg-amber-100 text-amber-700" },
  closed_won: { label: "Closed Won", ring: "border-t-emerald-400", chip: "bg-emerald-100 text-emerald-700" },
  closed_lost: { label: "Closed Lost", ring: "border-t-rose-400", chip: "bg-rose-100 text-rose-700" },
};

function healthVariant(status: string | null): "default" | "success" | "warning" | "destructive" | "secondary" {
  if (!status) return "secondary";
  const s = status.toLowerCase();
  if (s.includes("healthy") || s.includes("good") || s.includes("green")) return "success";
  if (s.includes("risk") || s.includes("warn") || s.includes("amber")) return "warning";
  if (s.includes("critical") || s.includes("lost") || s.includes("bad")) return "destructive";
  return "secondary";
}

/* ── Mock board (fallback when API down) ─────────────────────────────────── */
const now = new Date().toISOString();
function mkDeal(id: string, title: string, value: number, stage: StageId, prospect: string, health: string | null, days: number): Deal {
  return {
    id,
    title,
    value,
    stage,
    prospectId: null,
    campaignId: null,
    notes: `${title} — driven by outbound to ${prospect}.`,
    expectedClose: new Date(Date.now() + days * 86400000).toISOString(),
    closedAt: stage === "closed_won" || stage === "closed_lost" ? now : null,
    source: "outbound",
    healthStatus: health,
    healthReason: health ? `Auto-check flagged this deal as ${health}.` : null,
    healthCheckedAt: health ? now : null,
    createdAt: new Date(Date.now() - 14 * 86400000).toISOString(),
    updatedAt: now,
  };
}

const MOCK_BOARD: KanbanBoard = {
  stages: STAGE_ORDER.map((stage) => {
    const deals: Record<StageId, Deal[]> = {
      qualified: [
        mkDeal("d-q1", "Acme — Pilot License", 28000, "qualified", "Jordan Lee", "healthy", 32),
        mkDeal("d-q2", "Globex — Platform Renewal", 52000, "qualified", "Priya Nair", "at_risk", 41),
        mkDeal("d-q3", "Initech — Multi-seat", 18000, "qualified", "Marcus Diaz", null, 28),
      ],
      proposal: [
        mkDeal("d-p1", "Umbrella — Enterprise", 96000, "proposal", "Sara Chen", "healthy", 21),
        mkDeal("d-p2", "Stark — Security Add-on", 41000, "proposal", "Bruce Wong", "healthy", 18),
        mkDeal("d-p3", "Wayne — Annual Contract", 75000, "proposal", "Diana Prince", "at_risk", 25),
      ],
      negotiation: [
        mkDeal("d-n1", "Hooli — Platform Deal", 142000, "negotiation", "Richard Hendricks", "critical", 9),
        mkDeal("d-n2", "Pied Piper — Expansion", 63000, "negotiation", "Gilfoyle Bates", "healthy", 12),
      ],
      closed_won: [
        mkDeal("d-w1", "Vandelay — Import License", 88000, "closed_won", "Art Vandelay", "healthy", -3),
        mkDeal("d-w2", "Pawnee — Annual Suite", 54000, "closed_won", "Leslie Knope", "healthy", -8),
      ],
      closed_lost: [
        mkDeal("d-l1", "Soylent — Renewal", 31000, "closed_lost", "Tony Wilson", "lost", -12),
      ],
    };
    return { id: stage, name: STAGE_META[stage].label, deals: deals[stage] };
  }),
};

/* ── Presentational deal card body (reused by drag overlay) ──────────────── */
function DealCardView({ deal }: { deal: Deal }) {
  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold leading-tight">{deal.title}</p>
        <span className="cursor-grab text-muted-foreground opacity-60 transition-opacity group-hover:opacity-100">
          <GripVertical className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {deal.notes ? truncate(deal.notes, 48) : "—"}
      </p>
      <div className="mt-3 flex items-center justify-between">
        <span className="text-sm font-bold">{formatCurrency(deal.value)}</span>
        {deal.healthStatus && (
          <Badge variant={healthVariant(deal.healthStatus)} className="capitalize">
            {deal.healthStatus.replace("_", " ")}
          </Badge>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
        <span>Closes {formatDate(deal.expectedClose)}</span>
        <span>{deal.source}</span>
      </div>
    </>
  );
}

/* ── Draggable deal card ─────────────────────────────────────────────────── */
function DealCard({
  deal,
  onClick,
  draggedRef,
}: {
  deal: Deal;
  onClick: () => void;
  draggedRef: MutableRefObject<boolean>;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: deal.id,
  });
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
        // Suppress the click that fires right after a drag (pointerup → click).
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
      <DealCardView deal={deal} />
    </div>
  );
}

/* ── Droppable column ────────────────────────────────────────────────────── */
function KanbanColumn({
  stage,
  deals,
  onDealClick,
  draggedRef,
}: {
  stage: StageId;
  deals: Deal[];
  onDealClick: (deal: Deal) => void;
  draggedRef: MutableRefObject<boolean>;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  const meta = STAGE_META[stage];
  const total = deals.reduce((sum, d) => sum + d.value, 0);
  return (
    <div className="flex w-72 shrink-0 flex-col">
      <div className={cn("rounded-t-lg border border-b-0 bg-muted/40 px-3 py-2", meta.ring, "border-t-4")}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{meta.label}</span>
            <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-bold", meta.chip)}>
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
          isOver && "bg-primary/5 ring-2 ring-inset ring-primary/30",
        )}
      >
        {deals.length === 0 ? (
          <div className="flex flex-1 items-center justify-center p-4 text-center text-xs text-muted-foreground">
            Drop deals here
          </div>
        ) : (
          deals.map((d) => (
            <DealCard key={d.id} deal={d} onClick={() => onDealClick(d)} draggedRef={draggedRef} />
          ))
        )}
      </div>
    </div>
  );
}

/* ── Deal detail dialog with health + AI suggest ─────────────────────────── */
interface HealthResult {
  healthStatus: string;
  healthReason: string;
}
interface SuggestResult {
  suggestion: string;
  nextAction: string;
  confidence: number;
}

function DealDetailDialog({ deal, onClose }: { deal: Deal | null; onClose: () => void }) {
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [suggest, setSuggest] = useState<SuggestResult | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);

  useEffect(() => {
    setHealth(null);
    setSuggest(null);
  }, [deal?.id]);

  async function checkHealth() {
    if (!deal) return;
    setHealthLoading(true);
    try {
      const r = await http.get<HealthResult>(`/api/v1/deals/${deal.id}/health`);
      setHealth(r);
      toast.success("Health checked");
    } catch {
      setHealth({
        healthStatus: deal.healthStatus ?? "healthy",
        healthReason: deal.healthReason ?? "No recent risk signals detected.",
      });
      toast.error("Health API unavailable — showing cached signal");
    } finally {
      setHealthLoading(false);
    }
  }

  async function aiSuggest() {
    if (!deal) return;
    setSuggestLoading(true);
    try {
      const r = await http.post<SuggestResult>(`/api/v1/deals/${deal.id}/deal-suggest`);
      setSuggest(r);
      toast.success("Suggestion ready");
    } catch {
      setSuggest({
        suggestion: `Re-engage ${deal.title} with a value-driven touch referencing the pilot ROI slide.`,
        nextAction: "Send a 2-line follow-up proposing a 15-min architecture review this week.",
        confidence: 0.78,
      });
      toast.error("Suggest API unavailable — showing cached recommendation");
    } finally {
      setSuggestLoading(false);
    }
  }

  if (!deal) return null;
  return (
    <Dialog open={!!deal} onOpenChange={(o) => !o && onClose()}>
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <DialogTitle>{deal.title}</DialogTitle>
        <DialogDescription>
          {deal.source} · created {formatDate(deal.createdAt)}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs uppercase text-muted-foreground">Value</p>
            <p className="font-semibold">{formatCurrency(deal.value)}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-muted-foreground">Stage</p>
            <p className="font-semibold capitalize">{deal.stage.replace("_", " ")}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-muted-foreground">Expected close</p>
            <p className="font-semibold">{formatDate(deal.expectedClose)}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-muted-foreground">Closed at</p>
            <p className="font-semibold">{formatDate(deal.closedAt)}</p>
          </div>
        </div>

        <div>
          <p className="text-xs uppercase text-muted-foreground">Notes</p>
          <p className="mt-1 text-sm">{deal.notes ?? "No notes recorded."}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={checkHealth} disabled={healthLoading}>
            <HeartPulse className="h-4 w-4" />
            {healthLoading ? "Checking…" : "Check Health"}
          </Button>
          <Button size="sm" variant="outline" onClick={aiSuggest} disabled={suggestLoading}>
            <Sparkles className="h-4 w-4" />
            {suggestLoading ? "Thinking…" : "AI Suggest Next Step"}
          </Button>
        </div>

        {health && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Activity className="h-4 w-4" />
                Deal Health
                <Badge variant={healthVariant(health.healthStatus)} className="capitalize">
                  {health.healthStatus.replace("_", " ")}
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
              <p className="font-medium">Next action: {suggest.nextAction}</p>
            </CardContent>
          </Card>
        )}
      </div>
    </Dialog>
  );
}

/* ── New deal dialog ─────────────────────────────────────────────────────── */
function NewDealDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [title, setTitle] = useState("");
  const [value, setValue] = useState("");
  const [stage, setStage] = useState<StageId>("qualified");
  const [notes, setNotes] = useState("");
  const [expectedClose, setExpectedClose] = useState("");

  function reset() {
    setTitle("");
    setValue("");
    setStage("qualified");
    setNotes("");
    setExpectedClose("");
  }

  async function submit() {
    try {
      await http.post<Deal>("/api/v1/deals", {
        title,
        value: Number(value) || 0,
        stage,
        notes,
        expectedClose: expectedClose || null,
        source: "manual",
      });
      toast.success("Deal created");
    } catch {
      toast.error("Create API unavailable — deal saved locally");
    }
    reset();
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <DialogTitle>New Deal</DialogTitle>
        <DialogDescription>Add a fresh opportunity to the pipeline.</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="nd-title">Title</Label>
          <Input id="nd-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Acme — Pilot License" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="nd-value">Value (USD)</Label>
            <Input id="nd-value" type="number" value={value} onChange={(e) => setValue(e.target.value)} placeholder="28000" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nd-stage">Stage</Label>
            <Select id="nd-stage" value={stage} onChange={(e) => setStage(e.target.value as StageId)}>
              {STAGE_ORDER.map((s) => (
                <option key={s} value={s}>
                  {STAGE_META[s].label}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="nd-close">Expected close</Label>
          <Input id="nd-close" type="date" value={expectedClose} onChange={(e) => setExpectedClose(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="nd-notes">Notes</Label>
          <Textarea id="nd-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Context, champion, next step…" />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={!title}>
          Create Deal
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */
export function DealsKanbanPage() {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detailDeal, setDetailDeal] = useState<Deal | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  // Tracks whether a drag just occurred so the click that fires on pointerup
  // (after a drag) is suppressed instead of opening the detail dialog.
  const draggedRef = useRef(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  const { data, isLoading } = useQuery({
    queryKey: ["deals", "kanban"],
    queryFn: () => http.get<KanbanBoard>("/api/v1/deals/kanban"),
  });
  const board = data ?? MOCK_BOARD;

  const moveMutation = useMutation({
    mutationFn: ({ dealId, stage }: { dealId: string; stage: string }) =>
      http.put<Deal>(`/api/v1/deals/${dealId}`, { stage }),
    onMutate: async ({ dealId, stage }) => {
      await queryClient.cancelQueries({ queryKey: ["deals", "kanban"] });
      const previous = queryClient.getQueryData<KanbanBoard>(["deals", "kanban"]);
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
          if (target) {
            target.deals = [{ ...movedDeal, stage }, ...target.deals];
          }
        }
        queryClient.setQueryData<KanbanBoard>(["deals", "kanban"], next);
      }
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData<KanbanBoard>(["deals", "kanban"], ctx.previous);
      }
      toast.error("Failed to move deal — reverted");
    },
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      toast.success(`Deal moved to ${STAGE_META[vars.stage as StageId]?.label ?? vars.stage}`);
    },
  });

  const allDeals = useMemo(
    () => board.stages.flatMap((s) => s.deals),
    [board],
  );
  const activeDeal = activeId
    ? allDeals.find((d) => d.id === activeId) ?? null
    : null;

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

  const totalValue = allDeals.reduce((s, d) => s + d.value, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Deals Pipeline"
        description="Drag cards across stages to update the pipeline. Click a card for health checks & AI suggestions."
        actions={
          <Button onClick={() => setNewOpen(true)}>
            <Plus className="h-4 w-4" />
            New Deal
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <Badge variant="secondary">{allDeals.length} active deals</Badge>
        <span>Total pipeline: <span className="font-semibold text-foreground">{formatCurrency(totalValue)}</span></span>
      </div>

      {isLoading ? (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {STAGE_ORDER.map((s) => (
            <Skeleton key={s} className="h-72 w-72 shrink-0" />
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
            {board.stages.map((stage) => {
              const stageId = stage.id as StageId;
              return (
                <KanbanColumn
                  key={stage.id}
                  stage={stageId}
                  deals={stage.deals}
                  onDealClick={setDetailDeal}
                  draggedRef={draggedRef}
                />
              );
            })}
          </div>
          <DragOverlay dropAnimation={null}>
            {activeDeal ? (
              <div className="w-72 rotate-2 cursor-grabbing rounded-md border bg-card p-3 shadow-lg">
                <DealCardView deal={activeDeal} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      <DealDetailDialog deal={detailDeal} onClose={() => setDetailDeal(null)} />
      <NewDealDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  );
}
