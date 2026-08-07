/**
 * CallLogsPage.tsx — FIX-FE-1
 *
 * CallLog CRUD: phone-call outcomes logged against prospects. Filter by
 * prospect and outcome. Targets `GET/POST/PATCH/DELETE /api/v1/call-logs`.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { callLogsApi, http } from "@/services/apiClient";
import type { CallLog, CallLogInput, CallOutcome, Prospect } from "@/types/common";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
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

const OUTCOMES: CallOutcome[] = [
  "connected",
  "voicemail",
  "gatekeeper",
  "no-answer",
  "pending",
];

function outcomeVariant(o: string): "default" | "secondary" | "destructive" | "success" | "warning" | "outline" {
  switch (o) {
    case "connected":
      return "success";
    case "voicemail":
      return "warning";
    case "gatekeeper":
      return "secondary";
    case "no-answer":
      return "outline";
    case "pending":
      return "default";
    default:
      return "outline";
  }
}

function toLocalDatetime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

interface FormState {
  id?: string;
  prospectId: string;
  phone: string;
  outcome: CallOutcome;
  durationSec: string;
  notes: string;
  calledAt: string;
}

function emptyForm(): FormState {
  return {
    prospectId: "",
    phone: "",
    outcome: "pending",
    durationSec: "",
    notes: "",
    calledAt: toLocalDatetime(new Date().toISOString()),
  };
}

export function CallLogsPage() {
  const qc = useQueryClient();
  const [prospectFilter, setProspectFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CallLog | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["call-logs", "list", prospectFilter, outcomeFilter],
    queryFn: () =>
      callLogsApi.list({
        prospectId: prospectFilter || undefined,
        outcome: outcomeFilter || undefined,
        limit: 200,
      }),
    retry: false,
  });
  const logs = useMemo(() => data?.items ?? [], [data]);

  const { data: prospects } = useQuery<Prospect[]>({
    queryKey: ["prospects", "list"],
    queryFn: () => http.get<{ items: Prospect[] } | Prospect[]>("/api/v1/prospects")
      .then((r: any) => Array.isArray(r) ? r : (r?.items ?? [])),
    retry: false,
  });

  const createMut = useMutation({
    mutationFn: (body: CallLogInput) => callLogsApi.create(body),
    onSuccess: () => {
      toast.success("Call log created");
      qc.invalidateQueries({ queryKey: ["call-logs"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create call log"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<CallLogInput> }) =>
      callLogsApi.update(id, body),
    onSuccess: () => {
      toast.success("Call log saved");
      qc.invalidateQueries({ queryKey: ["call-logs"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save call log"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => callLogsApi.remove(id),
    onSuccess: () => {
      toast.success("Call log deleted");
      qc.invalidateQueries({ queryKey: ["call-logs"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete call log"),
  });

  function openNew() {
    setForm(emptyForm());
    setEditorOpen(true);
  }
  function openEdit(c: CallLog) {
    setForm({
      id: c.id,
      prospectId: c.prospectId,
      phone: c.phone,
      outcome: (c.outcome as CallOutcome) ?? "pending",
      durationSec: c.durationSec != null ? String(c.durationSec) : "",
      notes: c.notes ?? "",
      calledAt: toLocalDatetime(c.calledAt),
    });
    setEditorOpen(true);
  }
  function closeEditor() {
    setEditorOpen(false);
    setForm(emptyForm());
  }

  function handleSave() {
    if (!form.prospectId || !form.phone.trim()) {
      toast.error("Prospect and phone are required");
      return;
    }
    const body: CallLogInput = {
      prospectId: form.prospectId,
      phone: form.phone.trim(),
      outcome: form.outcome,
      durationSec: form.durationSec ? Number(form.durationSec) : null,
      notes: form.notes.trim() || null,
      calledAt: form.calledAt ? new Date(form.calledAt).toISOString() : null,
    };
    if (form.id) {
      updateMut.mutate({ id: form.id, body });
    } else {
      createMut.mutate(body);
    }
  }

  const prospectName = useMemo(() => {
    return (id: string) => prospects?.find((p) => p.id === id)?.name ?? id;
  }, [prospects]);

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="Call Logs"
          description="Log phone-call outcomes against prospects. Filter by prospect or outcome."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={openNew}>
                <Plus className="h-4 w-4" />
                Log Call
              </Button>
            </>
          }
        />

        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Select
                value={prospectFilter}
                onChange={(e) => setProspectFilter(e.target.value)}
                className="sm:w-64"
                aria-label="Filter by prospect"
              >
                <option value="">All prospects</option>
                {(prospects ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} {p.company ? `(${p.company})` : ""}
                  </option>
                ))}
              </Select>
              <Select
                value={outcomeFilter}
                onChange={(e) => setOutcomeFilter(e.target.value)}
                className="sm:w-44"
                aria-label="Filter by outcome"
              >
                <option value="">All outcomes</option>
                {OUTCOMES.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground">
                {data?.total ?? 0} call{(data?.total ?? 0) === 1 ? "" : "s"}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            {isError ? (
              <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                <p className="text-sm font-medium">Failed to load call logs</p>
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
            ) : logs.length === 0 ? (
              <EmptyState
                icon={<Phone className="h-6 w-6" />}
                title="No call logs yet"
                description="Log your first call to track outcomes against prospects."
                action={
                  <Button onClick={openNew}>
                    <Plus className="h-4 w-4" /> Log Call
                  </Button>
                }
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Prospect</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Called At</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">{prospectName(c.prospectId)}</TableCell>
                      <TableCell className="font-mono text-xs">{c.phone}</TableCell>
                      <TableCell>
                        <Badge variant={outcomeVariant(c.outcome)}>{c.outcome}</Badge>
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {c.durationSec != null ? `${c.durationSec}s` : "—"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(c.calledAt)}
                      </TableCell>
                      <TableCell className="max-w-xs truncate text-muted-foreground">
                        {c.notes ?? "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label="Edit call log"
                                onClick={() => openEdit(c)}
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
                                aria-label="Delete call log"
                                onClick={() => setDeleteTarget(c)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Delete</TooltipContent>
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

        {/* Editor dialog */}
        <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
          <DialogClose onClose={closeEditor} />
          <DialogHeader>
            <DialogTitle>{form.id ? "Edit Call Log" : "Log Call"}</DialogTitle>
            <DialogDescription>
              Record the outcome of a phone call to a prospect.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="cl-prospect">Prospect</Label>
              <Select
                id="cl-prospect"
                value={form.prospectId}
                onChange={(e) => setForm({ ...form, prospectId: e.target.value })}
              >
                <option value="">— Select prospect —</option>
                {(prospects ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} {p.company ? `(${p.company})` : ""}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="cl-phone">Phone</Label>
                <Input
                  id="cl-phone"
                  required
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  placeholder="+1 555 0100"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cl-outcome">Outcome</Label>
                <Select
                  id="cl-outcome"
                  value={form.outcome}
                  onChange={(e) => setForm({ ...form, outcome: e.target.value as CallOutcome })}
                >
                  {OUTCOMES.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="cl-dur">Duration (sec)</Label>
                <Input
                  id="cl-dur"
                  type="number"
                  min={0}
                  max={86400}
                  value={form.durationSec}
                  onChange={(e) => setForm({ ...form, durationSec: e.target.value })}
                  placeholder="120"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cl-when">Called At</Label>
                <Input
                  id="cl-when"
                  type="datetime-local"
                  value={form.calledAt}
                  onChange={(e) => setForm({ ...form, calledAt: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="cl-notes">Notes (optional)</Label>
              <Textarea
                id="cl-notes"
                rows={3}
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
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
              {createMut.isPending || updateMut.isPending ? "Saving…" : "Save Call Log"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Delete dialog */}
        <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <DialogClose onClose={() => setDeleteTarget(null)} />
          <DialogHeader>
            <DialogTitle>Delete call log?</DialogTitle>
            <DialogDescription>
              The call log for {deleteTarget ? prospectName(deleteTarget.prospectId) : ""} on{" "}
              {deleteTarget ? formatDateTime(deleteTarget.calledAt) : ""} will be permanently removed.
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
