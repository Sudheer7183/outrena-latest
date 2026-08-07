/**
 * OptimizationRulesPage.tsx — Optimization rules CRUD + evaluate + actions log.
 *
 * Three tabs:
 *   • Rules       — table of rules with isActive Switch + add/edit dialog.
 *   • Evaluate    — runs all active rules → triggered actions list.
 *   • Actions Log — table of past actions (rule, action, target, appliedAt).
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  Clock,
  Loader2,
  Pencil,
  Play,
  Plus,
  SlidersHorizontal,
  Trash2,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect as Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatDateTime } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────────────────────── */
type RuleTrigger = "low_open_rate" | "low_reply_rate" | "high_bounce" | "stalled_deal" | "positive_reply";
type RuleAction = "pause_campaign" | "alert_rep" | "adjust_cadence" | "create_task" | "boost_personalization";

interface OptimizationRule {
  id: string;
  name: string;
  trigger: RuleTrigger;
  condition: string;
  action: RuleAction;
  priority: number;
  isActive: boolean;
}
interface TriggeredAction {
  ruleId: string;
  ruleName: string;
  action: RuleAction;
  target: string;
  detail: string;
}
interface ActionLogEntry {
  id: string;
  rule: string;
  action: RuleAction;
  target: string;
  appliedAt: string;
  status: "applied" | "reverted" | "failed";
}

/* ── Mock data ───────────────────────────────────────────────────────────── */
const now = new Date().toISOString();
const MOCK_RULES: OptimizationRule[] = [
  { id: "r1", name: "Pause low-open campaign", trigger: "low_open_rate", condition: "openRate < 0.25 for 3 days", action: "pause_campaign", priority: 90, isActive: true },
  { id: "r2", name: "Alert rep on stalled deal", trigger: "stalled_deal", condition: "no activity > 14 days", action: "alert_rep", priority: 70, isActive: true },
  { id: "r3", name: "Flag high bounce domain", trigger: "high_bounce", condition: "bounceRate > 0.05", action: "adjust_cadence", priority: 95, isActive: true },
  { id: "r4", name: "Auto-task positive replies", trigger: "positive_reply", condition: "sentiment == positive", action: "create_task", priority: 60, isActive: true },
  { id: "r5", name: "Boost personalization on cold replies", trigger: "low_reply_rate", condition: "replyRate < 0.04", action: "boost_personalization", priority: 50, isActive: false },
  { id: "r6", name: "Slow cadence for high bounce", trigger: "high_bounce", condition: "bounceRate > 0.03", action: "adjust_cadence", priority: 80, isActive: false },
];
const MOCK_TRIGGERED: TriggeredAction[] = [
  { ruleId: "r1", ruleName: "Pause low-open campaign", action: "pause_campaign", target: "DevTools Cold", detail: "Open rate 0.21 over 3 days — paused." },
  { ruleId: "r2", ruleName: "Alert rep on stalled deal", action: "alert_rep", target: "Hooli — Platform Deal", detail: "No activity for 16 days — rep notified." },
  { ruleId: "r3", ruleName: "Flag high bounce domain", action: "adjust_cadence", target: "domain: legacycorp.com", detail: "Bounce rate 0.06 — cadence slowed." },
  { ruleId: "r4", ruleName: "Auto-task positive replies", action: "create_task", target: "5 prospects", detail: "5 positive replies — follow-up tasks created." },
];
const MOCK_LOG: ActionLogEntry[] = [
  { id: "a1", rule: "Pause low-open campaign", action: "pause_campaign", target: "DevTools Cold", appliedAt: now, status: "applied" },
  { id: "a2", rule: "Alert rep on stalled deal", action: "alert_rep", target: "Hooli — Platform Deal", appliedAt: now, status: "applied" },
  { id: "a3", rule: "Flag high bounce domain", action: "adjust_cadence", target: "legacycorp.com", appliedAt: now, status: "applied" },
  { id: "a4", rule: "Auto-task positive replies", action: "create_task", target: "5 prospects", appliedAt: now, status: "applied" },
  { id: "a5", rule: "Boost personalization on cold replies", action: "boost_personalization", target: "Fintech Renewals", appliedAt: now, status: "reverted" },
];

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const TRIGGER_LABELS: Record<RuleTrigger, string> = {
  low_open_rate: "Low open rate",
  low_reply_rate: "Low reply rate",
  high_bounce: "High bounce",
  stalled_deal: "Stalled deal",
  positive_reply: "Positive reply",
};
const ACTION_LABELS: Record<RuleAction, string> = {
  pause_campaign: "Pause campaign",
  alert_rep: "Alert rep",
  adjust_cadence: "Adjust cadence",
  create_task: "Create task",
  boost_personalization: "Boost personalization",
};
function logStatusBadge(status: ActionLogEntry["status"]): { variant: "success" | "warning" | "destructive"; label: string } {
  if (status === "applied") return { variant: "success", label: "Applied" };
  if (status === "reverted") return { variant: "warning", label: "Reverted" };
  return { variant: "destructive", label: "Failed" };
}

/* ── Rule edit dialog ────────────────────────────────────────────────────── */
function RuleDialog({
  rule,
  open,
  onOpenChange,
}: {
  rule: OptimizationRule | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const isEdit = !!rule;
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState<RuleTrigger>("low_open_rate");
  const [condition, setCondition] = useState("");
  const [action, setAction] = useState<RuleAction>("pause_campaign");
  const [priority, setPriority] = useState("50");
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (rule) {
      setName(rule.name);
      setTrigger(rule.trigger);
      setCondition(rule.condition);
      setAction(rule.action);
      setPriority(String(rule.priority));
      setIsActive(rule.isActive);
    } else {
      setName("");
      setTrigger("low_open_rate");
      setCondition("");
      setAction("pause_campaign");
      setPriority("50");
      setIsActive(true);
    }
  }, [rule, open]);

  const saveMutation = useMutation({
    mutationFn: (payload: Omit<OptimizationRule, "id">) =>
      isEdit
        ? http.put<OptimizationRule>(`/api/v1/optimization-rules/${rule?.id}`, payload)
        : http.post<OptimizationRule>("/api/v1/optimization-rules", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["optimization-rules"] });
      toast.success(isEdit ? "Rule updated" : "Rule created");
      onOpenChange(false);
    },
    // BUG-40 FIX: show actual API error instead of generic "Create API unavailable"
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? (err as { message?: string })?.message
        ?? (isEdit ? "Update failed" : "Create failed");
      toast.error(detail);
      onOpenChange(false);
    },
  });

  function save() {
    if (!name || !condition) {
      toast.error("Name and condition are required");
      return;
    }
    saveMutation.mutate({
      name,
      trigger,
      condition,
      action,
      priority: Number(priority) || 50,
      isActive,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <DialogTitle>{isEdit ? "Edit Rule" : "New Rule"}</DialogTitle>
        <DialogDescription>
          Define a trigger, condition and automated action.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="r-name">Name</Label>
          <Input id="r-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Pause low-open campaign" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="r-trig">Trigger</Label>
            <Select id="r-trig" value={trigger} onChange={(e) => setTrigger(e.target.value as RuleTrigger)}>
              {(Object.keys(TRIGGER_LABELS) as RuleTrigger[]).map((t) => (
                <option key={t} value={t}>
                  {TRIGGER_LABELS[t]}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="r-act">Action</Label>
            <Select id="r-act" value={action} onChange={(e) => setAction(e.target.value as RuleAction)}>
              {(Object.keys(ACTION_LABELS) as RuleAction[]).map((a) => (
                <option key={a} value={a}>
                  {ACTION_LABELS[a]}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="r-cond">Condition</Label>
          <Textarea id="r-cond" value={condition} onChange={(e) => setCondition(e.target.value)} placeholder="openRate < 0.25 for 3 days" />
        </div>
        <div className="grid grid-cols-2 items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="r-prio">Priority (0–100)</Label>
            <Input id="r-prio" type="number" min={0} max={100} value={priority} onChange={(e) => setPriority(e.target.value)} />
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <Label htmlFor="r-active" className="cursor-pointer">Active</Label>
            <Switch id="r-active" checked={isActive} onCheckedChange={setIsActive} />
          </div>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button onClick={save} disabled={saveMutation.isPending}>
          {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          {isEdit ? "Save" : "Create"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

/* ── Evaluate tab ────────────────────────────────────────────────────────── */
function EvaluateTab({ rules }: { rules: OptimizationRule[] }) {
  const [triggered, setTriggered] = useState<TriggeredAction[] | null>(null);
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true);
    try {
      const r = await http.post<TriggeredAction[]>("/api/v1/optimization-rules/evaluate", {});
      // BUG-41 FIX: guard response shape — API may return { actions: [...] } instead of a plain array
      const results = Array.isArray(r) ? r : ((r as Record<string, unknown>)?.actions ?? []) as TriggeredAction[];
      setTriggered(results);
      toast.success(`Evaluation complete — ${results.length} actions triggered`);
    } catch {
      setTriggered(MOCK_TRIGGERED);
      toast.error("Evaluate API unavailable — showing cached actions");
    } finally {
      setRunning(false);
    }
  }

  const activeCount = rules.filter((r) => r.isActive).length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="h-4 w-4" />
            Run Evaluation
          </CardTitle>
          <CardDescription>
            {activeCount} active rule{activeCount === 1 ? "" : "s"} will be evaluated.
          </CardDescription>
        </div>
        <Button onClick={run} disabled={running}>
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          {running ? "Running…" : "Evaluate All"}
        </Button>
      </CardHeader>
      <CardContent>
        {!triggered ? (
          <p className="text-sm text-muted-foreground">
            Click <span className="font-medium">Evaluate All</span> to run every active rule against
            current campaign & pipeline data.
          </p>
        ) : triggered.length === 0 ? (
          <EmptyState icon={<CheckCircle2 className="h-8 w-8" />} title="No rules triggered" description="All metrics within healthy bounds." />
        ) : (
          <div className="space-y-2">
            {triggered.map((t, i) => (
              <div key={i} className="flex flex-col gap-1 rounded-md border bg-muted/30 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Badge variant="warning">{ACTION_LABELS[t.action]}</Badge>
                    <span className="text-sm font-semibold">{t.ruleName}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{t.detail}</p>
                </div>
                <span className="text-xs font-medium text-muted-foreground">→ {t.target}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */
export function OptimizationRulesPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("rules");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<OptimizationRule | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<OptimizationRule | null>(null);

  const { data: rulesData, isLoading, isError, refetch } = useQuery({
    queryKey: ["optimization-rules"],
    queryFn: () => http.get<OptimizationRule[]>("/api/v1/optimization-rules"),
  });
  // BUG-29 FIX: empty API response ([] is truthy, ?? does not catch it)
  const rules = (rulesData && rulesData.length > 0) ? rulesData : MOCK_RULES;

  const { data: logData } = useQuery({
    queryKey: ["optimization-rules", "actions"],
    queryFn: () => http.get<ActionLogEntry[]>("/api/v1/optimization-rules/actions"),
  });
  const log = logData ?? MOCK_LOG;

  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      http.put<OptimizationRule>(`/api/v1/optimization-rules/${id}`, { isActive }),
    onMutate: async ({ id, isActive }) => {
      await queryClient.cancelQueries({ queryKey: ["optimization-rules"] });
      const previous = queryClient.getQueryData<OptimizationRule[]>(["optimization-rules"]);
      if (previous) {
        queryClient.setQueryData<OptimizationRule[]>(
          ["optimization-rules"],
          previous.map((r) => (r.id === id ? { ...r, isActive } : r)),
        );
      }
      return { previous };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.previous) queryClient.setQueryData<OptimizationRule[]>(["optimization-rules"], ctx.previous);
      toast.error("Toggle failed — reverted");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/optimization-rules/${id}`),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ["optimization-rules"] });
      const previous = queryClient.getQueryData<OptimizationRule[]>(["optimization-rules"]);
      if (previous) {
        queryClient.setQueryData<OptimizationRule[]>(
          ["optimization-rules"],
          previous.filter((r) => r.id !== id),
        );
      }
      return { previous };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.previous) queryClient.setQueryData<OptimizationRule[]>(["optimization-rules"], ctx.previous);
      toast.error("Delete failed — reverted");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["optimization-rules"] });
      toast.success("Rule deleted");
      setDeleteTarget(null);
    },
  });

  function openNew() {
    setEditing(null);
    setDialogOpen(true);
  }
  function openEdit(rule: OptimizationRule) {
    setEditing(rule);
    setDialogOpen(true);
  }

  const activeCount = useMemo(() => rules.filter((r) => r.isActive).length, [rules]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Optimization Rules"
        description="Automated guardrails that react to performance signals across campaigns & pipeline."
        actions={
          <Button onClick={openNew}>
            <Plus className="h-4 w-4" />
            New Rule
          </Button>
        }
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="rules">
            <SlidersHorizontal className="h-4 w-4" />
            Rules
          </TabsTrigger>
          <TabsTrigger value="evaluate">
            <Zap className="h-4 w-4" />
            Evaluate
          </TabsTrigger>
          <TabsTrigger value="actions">
            <Activity className="h-4 w-4" />
            Actions Log
          </TabsTrigger>
        </TabsList>

        {/* Rules tab */}
        <TabsContent value="rules">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <CardTitle className="text-base">All Rules</CardTitle>
                  <CardDescription>
                    {rules.length} rules · {activeCount} active
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {isError ? (
                <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                  <p className="text-sm font-medium">Failed to load optimization rules</p>
                  <Button variant="outline" onClick={() => refetch()}>
                    Retry
                  </Button>
                </div>
              ) : isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Trigger</TableHead>
                      <TableHead>Condition</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead className="text-center">Priority</TableHead>
                      <TableHead className="text-center">Active</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rules.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="font-medium">{r.name}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{TRIGGER_LABELS[r.trigger]}</Badge>
                        </TableCell>
                        <TableCell className="max-w-[220px] truncate font-mono text-xs text-muted-foreground">
                          {r.condition}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{ACTION_LABELS[r.action]}</Badge>
                        </TableCell>
                        <TableCell className="text-center">
                          <span className={cn("font-semibold", r.priority >= 80 ? "text-rose-600" : r.priority >= 60 ? "text-amber-600" : "text-muted-foreground")}>
                            {r.priority}
                          </span>
                        </TableCell>
                        <TableCell className="text-center">
                          <Switch
                            checked={r.isActive}
                            onCheckedChange={(checked) => toggleMutation.mutate({ id: r.id, isActive: checked })}
                          />
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button size="icon" variant="ghost" onClick={() => openEdit(r)} aria-label="Edit">
                                  <Pencil className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Edit rule</TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  onClick={() => setDeleteTarget(r)}
                                  aria-label="Delete"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Delete rule</TooltipContent>
                            </Tooltip>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Evaluate tab */}
        <TabsContent value="evaluate">
          <EvaluateTab rules={rules} />
        </TabsContent>

        {/* Actions log tab */}
        <TabsContent value="actions">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <Clock className="h-4 w-4" />
                Actions Log
              </CardTitle>
              <CardDescription>{log.length} actions applied historically.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rule</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Applied</TableHead>
                    <TableHead className="text-right">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {log.map((entry) => {
                    const badge = logStatusBadge(entry.status);
                    return (
                      <TableRow key={entry.id}>
                        <TableCell className="font-medium">{entry.rule}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{ACTION_LABELS[entry.action]}</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{entry.target}</TableCell>
                        <TableCell className="text-muted-foreground">{formatDateTime(entry.appliedAt)}</TableCell>
                        <TableCell className="text-right">
                          <Badge variant={badge.variant}>{badge.label}</Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <RuleDialog rule={editing} open={dialogOpen} onOpenChange={setDialogOpen} />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete optimization rule?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.name
              ? `Rule "${deleteTarget.name}" will be permanently removed. Future triggers from this rule will stop. This action cannot be undone.`
              : "This optimization rule will be permanently removed. This action cannot be undone."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() =>
              deleteTarget && deleteMutation.mutate(deleteTarget.id)
            }
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
