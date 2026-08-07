/**
 * RateLimitsPage.tsx — FIX-FE-1
 *
 * Per-platform RateLimit configuration + counter + immutable event log.
 * Tab 1: RateLimit CRUD with reset-counter action.
 * Tab 2: RateLimitLog read-only list.
 * Targets `GET/POST/PUT/DELETE /api/v1/rate-limits` + `POST /:id/reset` + `GET /logs`.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Gauge,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  ScrollText,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { rateLimitsApi } from "@/services/apiClient";
import type {
  RateLimit,
  RateLimitInput,
  RateLimitWindow,
} from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect as Select } from "@/components/ui/select";
import { PageHeader } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDateTime } from "@/lib/utils";

const WINDOWS: RateLimitWindow[] = ["MINUTELY", "HOURLY", "DAILY"];
const THROTTLE_MODES = ["skip", "queue"] as const;

interface FormState {
  id?: string;
  key: string;
  label: string;
  platform: string;
  window: RateLimitWindow;
  limit: number;
  throttleMode: string;
  isActive: boolean;
}

const EMPTY_FORM: FormState = {
  key: "",
  label: "",
  platform: "",
  window: "HOURLY",
  limit: 100,
  throttleMode: "skip",
  isActive: true,
};

export function RateLimitsPage() {
  const qc = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<RateLimit | null>(null);
  const [resetTarget, setResetTarget] = useState<RateLimit | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["rate-limits", "list"],
    queryFn: () => rateLimitsApi.list(),
    retry: false,
  });
  const limits = useMemo(() => data?.items ?? [], [data]);

  const { data: logsData, isLoading: logsLoading, isError: logsError, error: logsErr, refetch: refetchLogs } = useQuery({
    queryKey: ["rate-limits", "logs"],
    queryFn: () => rateLimitsApi.listLogs({ limit: 100 }),
    retry: false,
  });
  const logs = useMemo(() => logsData?.items ?? [], [logsData]);

  const createMut = useMutation({
    mutationFn: (body: RateLimitInput) => rateLimitsApi.create(body),
    onSuccess: () => {
      toast.success("Rate limit created");
      qc.invalidateQueries({ queryKey: ["rate-limits", "list"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create rate limit"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<RateLimitInput> }) =>
      rateLimitsApi.update(id, body),
    onSuccess: () => {
      toast.success("Rate limit saved");
      qc.invalidateQueries({ queryKey: ["rate-limits", "list"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save rate limit"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => rateLimitsApi.remove(id),
    onSuccess: () => {
      toast.success("Rate limit deleted");
      qc.invalidateQueries({ queryKey: ["rate-limits", "list"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete rate limit"),
  });

  const resetMut = useMutation({
    mutationFn: (id: string) => rateLimitsApi.resetCounter(id),
    onSuccess: () => {
      toast.success("Counter reset");
      qc.invalidateQueries({ queryKey: ["rate-limits", "list"] });
      setResetTarget(null);
    },
    onError: () => toast.error("Failed to reset counter"),
  });

  function openNew() {
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  }
  function openEdit(r: RateLimit) {
    setForm({
      id: r.id,
      key: r.key,
      label: r.label,
      platform: r.platform ?? "",
      window: r.window,
      limit: r.limit,
      throttleMode: r.throttleMode,
      isActive: r.isActive,
    });
    setEditorOpen(true);
  }
  function closeEditor() {
    setEditorOpen(false);
    setForm(EMPTY_FORM);
  }

  function handleSave() {
    if (!form.key.trim() || !form.label.trim()) {
      toast.error("Key and Label are required");
      return;
    }
    if (form.limit < 1) {
      toast.error("Limit must be ≥ 1");
      return;
    }
    const body: RateLimitInput = {
      key: form.key.trim(),
      label: form.label.trim(),
      platform: form.platform.trim() || null,
      window: form.window,
      limit: form.limit,
      throttleMode: form.throttleMode,
      isActive: form.isActive,
    };
    if (form.id) {
      updateMut.mutate({ id: form.id, body });
    } else {
      createMut.mutate(body);
    }
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="Rate Limits"
          description="Per-platform rate-limit configuration + counters. Reset a counter manually or inspect the immutable event log."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={openNew}>
                <Plus className="h-4 w-4" />
                New Limit
              </Button>
            </>
          }
        />

        <Tabs defaultValue="limits">
          <TabsList>
            <TabsTrigger value="limits">
              <Gauge className="mr-1.5 h-4 w-4" /> Limits
            </TabsTrigger>
            <TabsTrigger value="logs">
              <ScrollText className="mr-1.5 h-4 w-4" /> Logs
            </TabsTrigger>
          </TabsList>

          {/* Tab 1: Limits */}
          <TabsContent value="limits">
            <Card>
              <CardContent className="p-0">
                {isError ? (
                  <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                    <p className="text-sm font-medium">Failed to load rate limits</p>
                    <p className="text-xs text-muted-foreground">
                      {(error as Error)?.message ?? "Unknown error"}
                    </p>
                    <Button variant="outline" onClick={() => refetch()}>
                      Retry
                    </Button>
                  </div>
                ) : isLoading ? (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full" />
                    ))}
                  </div>
                ) : limits.length === 0 ? (
                  <EmptyState
                    icon={<Gauge className="h-6 w-6" />}
                    title="No rate limits configured"
                    description="Add a per-platform rate limit to throttle outbound API calls."
                    action={
                      <Button onClick={openNew}>
                        <Plus className="h-4 w-4" /> New Limit
                      </Button>
                    }
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Key</TableHead>
                        <TableHead>Label</TableHead>
                        <TableHead>Platform</TableHead>
                        <TableHead>Window</TableHead>
                        <TableHead>Limit</TableHead>
                        <TableHead>% Used</TableHead>
                        <TableHead>Throttle</TableHead>
                        <TableHead>Active</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {limits.map((r) => {
                        const pct = r.limit > 0 ? Math.min(100, (r.count / r.limit) * 100) : 0;
                        const variant =
                          pct >= 90 ? "destructive" : pct >= 70 ? "warning" : "success";
                        return (
                          <TableRow key={r.id}>
                            <TableCell className="font-mono text-xs">{r.key}</TableCell>
                            <TableCell className="font-medium">{r.label}</TableCell>
                            <TableCell className="text-muted-foreground">{r.platform ?? "—"}</TableCell>
                            <TableCell>
                              <Badge variant="outline">{r.window}</Badge>
                            </TableCell>
                            <TableCell className="tabular-nums">{r.limit}</TableCell>
                            <TableCell className="min-w-[10rem]">
                              <div className="flex items-center gap-2">
                                <Progress
                                  value={pct}
                                  indicatorClassName={
                                    variant === "destructive"
                                      ? "bg-destructive"
                                      : variant === "warning"
                                        ? "bg-amber-500"
                                        : "bg-emerald-500"
                                  }
                                />
                                <span className="w-12 text-right text-xs tabular-nums text-muted-foreground">
                                  {pct.toFixed(0)}%
                                </span>
                              </div>
                              <p className="mt-1 text-[10px] text-muted-foreground">
                                {r.count} / {r.limit}
                              </p>
                            </TableCell>
                            <TableCell>
                              <Badge variant="secondary">{r.throttleMode}</Badge>
                            </TableCell>
                            <TableCell>
                              <Badge variant={r.isActive ? "success" : "outline"}>
                                {r.isActive ? "Active" : "Inactive"}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-1">
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      aria-label="Reset counter"
                                      onClick={() => setResetTarget(r)}
                                    >
                                      <RotateCcw className="h-4 w-4" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>Reset counter</TooltipContent>
                                </Tooltip>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      aria-label="Edit rate limit"
                                      onClick={() => openEdit(r)}
                                    >
                                      <Pencil className="h-4 w-4" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>Edit</TooltipContent>
                                </Tooltip>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      aria-label="Delete rate limit"
                                      onClick={() => setDeleteTarget(r)}
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>Delete</TooltipContent>
                                </Tooltip>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 2: Logs */}
          <TabsContent value="logs">
            <Card>
              <CardContent className="p-0">
                <div className="flex items-center justify-between p-4">
                  <p className="text-xs text-muted-foreground">
                    {logsData?.total ?? 0} log entries (immutable)
                  </p>
                  <Button variant="outline" size="sm" onClick={() => refetchLogs()}>
                    <RefreshCw className="h-4 w-4" />
                    Refresh logs
                  </Button>
                </div>
                {logsError ? (
                  <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                    <p className="text-sm font-medium">Failed to load logs</p>
                    <p className="text-xs text-muted-foreground">
                      {(logsErr as Error)?.message ?? "Unknown error"}
                    </p>
                    <Button variant="outline" onClick={() => refetchLogs()}>
                      Retry
                    </Button>
                  </div>
                ) : logsLoading ? (
                  <div className="space-y-2 p-4">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : logs.length === 0 ? (
                  <EmptyState
                    icon={<ScrollText className="h-6 w-6" />}
                    title="No log entries yet"
                    description="Rate-limit decisions will appear here as the autopilot pipeline runs."
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Key</TableHead>
                        <TableHead>Platform</TableHead>
                        <TableHead>Outcome</TableHead>
                        <TableHead>Flow Run</TableHead>
                        <TableHead>Detail</TableHead>
                        <TableHead>Created</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {logs.map((l) => (
                        <TableRow key={l.id}>
                          <TableCell className="font-mono text-xs">{l.key}</TableCell>
                          <TableCell className="text-muted-foreground">{l.platform ?? "—"}</TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                l.outcome === "allowed"
                                  ? "success"
                                  : l.outcome === "throttled"
                                    ? "warning"
                                    : "outline"
                              }
                            >
                              {l.outcome}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground">
                            {l.flowRunId ?? "—"}
                          </TableCell>
                          <TableCell className="max-w-md truncate text-xs text-muted-foreground">
                            {l.detail ?? "—"}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {formatDateTime(l.createdAt)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Editor dialog */}
        <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
          <DialogClose onClose={closeEditor} />
          <DialogHeader>
            <DialogTitle>{form.id ? "Edit Rate Limit" : "New Rate Limit"}</DialogTitle>
            <DialogDescription>
              Configure a per-platform limit. When the counter reaches the limit, the autopilot will {form.throttleMode === "skip" ? "skip" : "queue"} the API call.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="rl-key">Key</Label>
                <Input
                  id="rl-key"
                  required
                  value={form.key}
                  onChange={(e) => setForm({ ...form, key: e.target.value })}
                  placeholder="e.g. apollo:search"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rl-label">Label</Label>
                <Input
                  id="rl-label"
                  required
                  value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })}
                  placeholder="Apollo Search API"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="rl-platform">Platform (optional)</Label>
                <Input
                  id="rl-platform"
                  value={form.platform}
                  onChange={(e) => setForm({ ...form, platform: e.target.value })}
                  placeholder="apollo"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rl-window">Window</Label>
                <Select
                  id="rl-window"
                  value={form.window}
                  onChange={(e) => setForm({ ...form, window: e.target.value as RateLimitWindow })}
                >
                  {WINDOWS.map((w) => (
                    <option key={w} value={w}>
                      {w}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="rl-limit">Limit</Label>
                <Input
                  id="rl-limit"
                  type="number"
                  min={1}
                  required
                  value={form.limit}
                  onChange={(e) => setForm({ ...form, limit: Number(e.target.value) })}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="rl-throttle">Throttle Mode</Label>
                <Select
                  id="rl-throttle"
                  value={form.throttleMode}
                  onChange={(e) => setForm({ ...form, throttleMode: e.target.value })}
                >
                  {THROTTLE_MODES.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex items-center justify-between rounded-md border p-3">
                <div>
                  <p className="text-sm font-medium">Active</p>
                  <p className="text-xs text-muted-foreground">
                    Inactive limits are not enforced.
                  </p>
                </div>
                <Switch
                  checked={form.isActive}
                  onCheckedChange={(v) => setForm({ ...form, isActive: v })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeEditor}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={createMut.isPending || updateMut.isPending}
            >
              {createMut.isPending || updateMut.isPending ? "Saving…" : "Save Limit"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Reset counter confirmation */}
        <Dialog open={!!resetTarget} onOpenChange={(o) => !o && setResetTarget(null)}>
          <DialogClose onClose={() => setResetTarget(null)} />
          <DialogHeader>
            <DialogTitle>Reset counter?</DialogTitle>
            <DialogDescription>
              “{resetTarget?.label}” counter will be set to 0 and the window start moved to now.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResetTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => resetTarget && resetMut.mutate(resetTarget.id)}
              disabled={resetMut.isPending}
            >
              {resetMut.isPending ? "Resetting…" : "Reset Counter"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Delete dialog */}
        <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <DialogClose onClose={() => setDeleteTarget(null)} />
          <DialogHeader>
            <DialogTitle>Delete rate limit?</DialogTitle>
            <DialogDescription>
              “{deleteTarget?.label}” will be permanently removed. Past log entries are retained.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
