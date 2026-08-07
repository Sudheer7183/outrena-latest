/**
 * MeetingsPage.tsx — FIX-FE-1
 *
 * Lightweight calendar entries. Meeting CRUD + "Generate Meeting Prep" action
 * that calls the existing /api/v1/meeting-prep/generate endpoint. Click a row
 * to view the meeting prep brief (if any) in a side dialog.
 *
 * Targets:
 *   GET/POST /api/v1/meetings + PATCH/DELETE /api/v1/meetings/:id
 *   POST /api/v1/meeting-prep/generate + GET /api/v1/meeting-prep/:id
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { meetingsApi } from "@/services/apiClient";
import type { Meeting, MeetingInput, MeetingPrep, Prospect } from "@/types/common";
import { http } from "@/services/apiClient";
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

const MEETING_STATUSES = ["scheduled", "completed", "cancelled", "no_show"] as const;

interface FormState {
  id?: string;
  title: string;
  prospectId: string;
  scheduledAt: string;
  durationMin: number;
  meetingUrl: string;
  status: string;
  notes: string;
}

function toLocalDatetime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  // yyyy-MM-ddTHH:mm in local time, the format <input type="datetime-local"> expects
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const EMPTY_FORM: FormState = {
  title: "",
  prospectId: "",
  scheduledAt: toLocalDatetime(new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()),
  durationMin: 30,
  meetingUrl: "",
  status: "scheduled",
  notes: "",
};

export function MeetingsPage() {
  const qc = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Meeting | null>(null);
  const [viewTarget, setViewTarget] = useState<Meeting | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const { data: meetings, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["meetings", "list"],
    queryFn: () => meetingsApi.list(),
    retry: false,
  });

  const { data: prospects } = useQuery<Prospect[]>({
    queryKey: ["prospects", "list"],
    queryFn: () => http.get<{ items: Prospect[] } | Prospect[]>("/api/v1/prospects")
      .then((r: any) => Array.isArray(r) ? r : (r?.items ?? [])),
    retry: false,
  });

  const prepQuery = useQuery({
    queryKey: ["meeting-prep", viewTarget?.meetingPrepId],
    queryFn: () => meetingsApi.getPrep(viewTarget!.meetingPrepId!),
    enabled: !!viewTarget?.meetingPrepId,
    retry: false,
  });

  const createMut = useMutation({
    mutationFn: (body: MeetingInput) => meetingsApi.create(body),
    onSuccess: () => {
      toast.success("Meeting created");
      qc.invalidateQueries({ queryKey: ["meetings", "list"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create meeting"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<MeetingInput> }) =>
      meetingsApi.update(id, body),
    onSuccess: () => {
      toast.success("Meeting saved");
      qc.invalidateQueries({ queryKey: ["meetings", "list"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save meeting"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => meetingsApi.remove(id),
    onSuccess: () => {
      toast.success("Meeting deleted");
      qc.invalidateQueries({ queryKey: ["meetings", "list"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete meeting"),
  });

  const generatePrepMut = useMutation({
    mutationFn: (meeting: Meeting) =>
      meetingsApi.generatePrep(
        meeting.prospectId ?? "",
        meeting.title.toLowerCase().includes("discovery") ? "discovery" : "demo",
      ),
    onSuccess: async (res, meeting) => {
      toast.success("Meeting prep brief generated");
      // Link the brief back to the meeting (best-effort)
      try {
        await updateMut.mutateAsync({
          id: meeting.id,
          body: { meetingPrepId: res.id },
        });
      } catch {
        // The brief exists; the link is best-effort
      }
      qc.invalidateQueries({ queryKey: ["meetings", "list"] });
    },
    onError: () => toast.error("Failed to generate meeting prep"),
  });

  function openNew() {
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  }
  function openEdit(m: Meeting) {
    setForm({
      id: m.id,
      title: m.title,
      prospectId: m.prospectId ?? "",
      scheduledAt: toLocalDatetime(m.scheduledAt),
      durationMin: m.durationMin,
      meetingUrl: m.meetingUrl ?? "",
      status: m.status,
      notes: m.notes ?? "",
    });
    setEditorOpen(true);
  }
  function closeEditor() {
    setEditorOpen(false);
    setForm(EMPTY_FORM);
  }

  function handleSave() {
    if (!form.title.trim() || !form.scheduledAt) {
      toast.error("Title and Scheduled At are required");
      return;
    }
    const iso = new Date(form.scheduledAt).toISOString();
    const body: MeetingInput = {
      title: form.title.trim(),
      prospectId: form.prospectId || null,
      scheduledAt: iso,
      durationMin: form.durationMin,
      meetingUrl: form.meetingUrl.trim() || null,
      status: form.status,
      notes: form.notes.trim() || null,
    };
    if (form.id) {
      updateMut.mutate({ id: form.id, body });
    } else {
      createMut.mutate(body);
    }
  }

  const prospectName = useMemo(() => {
    return (id: string | null | undefined) =>
      id ? (prospects?.find((p) => p.id === id)?.name ?? id) : "—";
  }, [prospects]);

  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-6">
        <PageHeader
          title="Meetings"
          description="Calendar entries tied to prospects. Generate an AI brief for any meeting via Meeting Prep."
          actions={
            <>
              <Button variant="outline" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={openNew}>
                <Plus className="h-4 w-4" />
                New Meeting
              </Button>
            </>
          }
        />

        <Card>
          <CardContent className="p-0">
            {isError ? (
              <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
                <p className="text-sm font-medium">Failed to load meetings</p>
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
            ) : !meetings || meetings.length === 0 ? (
              <EmptyState
                icon={<CalendarClock className="h-6 w-6" />}
                title="No meetings yet"
                description="Add your first meeting to start generating AI briefs."
                action={
                  <Button onClick={openNew}>
                    <Plus className="h-4 w-4" /> New Meeting
                  </Button>
                }
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead>Prospect</TableHead>
                    <TableHead>Scheduled At</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Meeting URL</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {meetings.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell className="font-medium">{m.title}</TableCell>
                      <TableCell className="text-muted-foreground">{prospectName(m.prospectId)}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(m.scheduledAt)}
                      </TableCell>
                      <TableCell className="tabular-nums">{m.durationMin}m</TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            m.status === "completed"
                              ? "success"
                              : m.status === "cancelled"
                                ? "destructive"
                                : m.status === "no_show"
                                  ? "warning"
                                  : "default"
                          }
                        >
                          {m.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[14rem] truncate">
                        {m.meetingUrl ? (
                          <a
                            href={m.meetingUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary underline-offset-4 hover:underline"
                          >
                            {m.meetingUrl}
                          </a>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label="Generate meeting prep"
                                onClick={() => generatePrepMut.mutate(m)}
                                disabled={generatePrepMut.isPending || !m.prospectId}
                              >
                                <Sparkles className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {m.prospectId ? "Generate AI brief" : "No prospect linked"}
                            </TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label="View meeting brief"
                                onClick={() => setViewTarget(m)}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>View brief</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label="Edit meeting"
                                onClick={() => openEdit(m)}
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
                                aria-label="Delete meeting"
                                onClick={() => setDeleteTarget(m)}
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
            <DialogTitle>{form.id ? "Edit Meeting" : "New Meeting"}</DialogTitle>
            <DialogDescription>
              Calendar entry for a prospect meeting. Optional fields can be left blank.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mtg-title">Title</Label>
              <Input
                id="mtg-title"
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Discovery call — Acme Corp"
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mtg-prospect">Prospect</Label>
                <Select
                  id="mtg-prospect"
                  value={form.prospectId}
                  onChange={(e) => setForm({ ...form, prospectId: e.target.value })}
                >
                  <option value="">— None —</option>
                  {(prospects ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} {p.company ? `(${p.company})` : ""}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="mtg-status">Status</Label>
                <Select
                  id="mtg-status"
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                >
                  {MEETING_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="mtg-when">Scheduled At</Label>
                <Input
                  id="mtg-when"
                  type="datetime-local"
                  required
                  value={form.scheduledAt}
                  onChange={(e) => setForm({ ...form, scheduledAt: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mtg-dur">Duration (min)</Label>
                <Input
                  id="mtg-dur"
                  type="number"
                  min={5}
                  max={480}
                  value={form.durationMin}
                  onChange={(e) => setForm({ ...form, durationMin: Number(e.target.value) })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mtg-url">Meeting URL (optional)</Label>
              <Input
                id="mtg-url"
                value={form.meetingUrl}
                onChange={(e) => setForm({ ...form, meetingUrl: e.target.value })}
                placeholder="https://meet.example.com/xyz"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mtg-notes">Notes (optional)</Label>
              <Textarea
                id="mtg-notes"
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
              {createMut.isPending || updateMut.isPending ? "Saving…" : "Save Meeting"}
            </Button>
          </DialogFooter>
        </Dialog>

        {/* View brief dialog */}
        <Dialog open={!!viewTarget} onOpenChange={(o) => !o && setViewTarget(null)}>
          <DialogClose onClose={() => setViewTarget(null)} />
          <DialogHeader>
            <DialogTitle>Meeting Brief — {viewTarget?.title}</DialogTitle>
            <DialogDescription>
              {viewTarget?.meetingPrepId
                ? "AI-generated brief for this meeting."
                : "No brief generated yet. Click the sparkle icon on the meeting row to generate one."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {viewTarget?.meetingPrepId ? (
              prepQuery.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : prepQuery.isError ? (
                <p className="text-sm text-destructive">
                  Failed to load brief: {(prepQuery.error as Error)?.message}
                </p>
              ) : prepQuery.data ? (
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs">
                  {(prepQuery.data as MeetingPrep).brief}
                </pre>
              ) : null
            ) : (
              <p className="text-sm text-muted-foreground">
                Generate a brief to see the AI meeting prep here.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewTarget(null)}>
              Close
            </Button>
          </DialogFooter>
        </Dialog>

        {/* Delete dialog */}
        <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <DialogClose onClose={() => setDeleteTarget(null)} />
          <DialogHeader>
            <DialogTitle>Delete meeting?</DialogTitle>
            <DialogDescription>
              “{deleteTarget?.title}” will be permanently removed.
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
