/**
 * ContentIdeasPage.tsx — Content ideas CRUD + AI generate.
 *
 * Matches Next.js reference design:
 *   - Card layout: status badge, "AI" badge (if generated), angle tag,
 *     title, body excerpt, date — with edit/delete icons top-right
 *   - Top actions: "AI Suggest Ideas" (generate dialog), "+ Manual Idea"
 *     (quick create), status filter
 *   - Generate dialog: topic, audience, count → POST /content-ideas/generate
 *   - Manual Idea dialog: title, angle, body → POST /content-ideas
 *   - Edit dialog: title, angle, body, status, isFavorite
 *   - Delete confirmation
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Heart,
  Lightbulb,
  Loader2,
  Pencil,
  Plus,
  Sparkles,
  Star,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatDate, truncate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
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

/* ── Backend types ──────────────────────────────────────────────────────── */

interface ContentIdeaResponse {
  id: string;
  icpProfileId: string | null;
  title: string;
  angle: string | null;
  body: string;
  status: string;
  isFavorite: boolean;
  generatedAt: string;
  createdAt: string;
  updatedAt: string;
}

interface ContentIdeaGenerateResponse {
  ideas: ContentIdeaResponse[];
}

/* ── Status config ──────────────────────────────────────────────────────── */

const STATUS_CHIP: Record<string, string> = {
  idea:      "bg-slate-100 text-slate-700 border-slate-200",
  draft:     "bg-slate-100 text-slate-700 border-slate-200",
  drafting:  "bg-amber-100 text-amber-700 border-amber-200",
  published: "bg-emerald-100 text-emerald-700 border-emerald-200",
};

/* ── Generate dialog ─────────────────────────────────────────────────────── */

function GenerateDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [count, setCount] = useState("3");
  const [preview, setPreview] = useState<ContentIdeaResponse[]>([]);

  function reset() {
    setTopic(""); setAudience(""); setCount("3"); setPreview([]);
  }

  const genMut = useMutation({
    mutationFn: (body: { topic: string; audience: string; count: number }) =>
      http.post<ContentIdeaGenerateResponse>("/api/v1/content-ideas/generate", body),
    onSuccess: (data) => {
      const ideas = data.ideas ?? [];
      setPreview(ideas);
      qc.invalidateQueries({ queryKey: ["content-ideas"] });
      toast.success(`${ideas.length} idea${ideas.length !== 1 ? "s" : ""} generated`);
    },
    onError: () => toast.error("Failed to generate ideas"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" /> AI Suggest Ideas
          </DialogTitle>
          <DialogDescription>
            AI-drafted content angles based on topic and audience. Ideas are
            automatically saved to your library.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="g-topic">Topic *</Label>
            <Input id="g-topic" value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Outbound reply speed, ICP scoring" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="g-aud">Target Audience</Label>
              <Input id="g-aud" value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g. VP Sales, SaaS" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="g-cnt">Count (1–5)</Label>
              <Input id="g-cnt" type="number" min={1} max={5} value={count}
                onChange={(e) => setCount(e.target.value)} />
            </div>
          </div>
          {preview.length > 0 && (
            <div className="max-h-56 space-y-2 overflow-y-auto rounded-md border p-2">
              {preview.map((idea) => (
                <div key={idea.id} className="rounded-md bg-muted/40 p-2 text-sm">
                  <p className="font-semibold">{idea.title}</p>
                  {idea.angle && (
                    <p className="text-xs text-muted-foreground">Angle: {idea.angle}</p>
                  )}
                  <p className="mt-1 text-xs text-muted-foreground whitespace-pre-wrap">
                    {truncate(idea.body, 120)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { reset(); onOpenChange(false); }}>
            {preview.length > 0 ? "Done" : "Cancel"}
          </Button>
          <Button onClick={() => {
            if (!topic.trim()) { toast.error("Enter a topic first"); return; }
            genMut.mutate({ topic: topic.trim(), audience: audience.trim(),
              count: Math.max(1, Math.min(5, Number(count) || 3)) });
          }} disabled={genMut.isPending}>
            {genMut.isPending
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <Sparkles className="h-4 w-4" />}
            Generate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── Manual Idea dialog ──────────────────────────────────────────────────── */

function ManualIdeaDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [angle, setAngle] = useState("");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);

  function reset() { setTitle(""); setAngle(""); setBody(""); }

  async function submit() {
    if (!title.trim()) { toast.error("Title is required"); return; }
    setSaving(true);
    try {
      await http.post("/api/v1/content-ideas", {
        title: title.trim(),
        angle: angle.trim() || null,
        body: body.trim() || title.trim(),
        isFavorite: false,
      });
      toast.success("Idea added");
      qc.invalidateQueries({ queryKey: ["content-ideas"] });
      reset();
      onOpenChange(false);
    } catch { toast.error("Failed to add idea"); }
    finally { setSaving(false); }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Manual Idea</DialogTitle>
          <DialogDescription>Add a content idea directly to your library.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="m-title">Title *</Label>
            <Input id="m-title" value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Why reply speed beats pitch perfection" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="m-angle">Angle</Label>
            <Input id="m-angle" value={angle} onChange={(e) => setAngle(e.target.value)}
              placeholder="e.g. Contrarian, How-to, Data-driven" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="m-body">Body / Outline</Label>
            <Textarea id="m-body" value={body} onChange={(e) => setBody(e.target.value)}
              rows={4} placeholder="Describe what this content will cover…" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { reset(); onOpenChange(false); }}>Cancel</Button>
          <Button onClick={submit} disabled={saving || !title.trim()}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add Idea
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── Edit dialog ─────────────────────────────────────────────────────────── */

function EditDialog({
  idea, onClose,
}: {
  idea: ContentIdeaResponse | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [angle, setAngle] = useState("");
  const [body, setBody] = useState("");
  const [status, setStatus] = useState("idea");
  const [isFavorite, setIsFavorite] = useState(false);

  useEffect(() => {
    if (idea) {
      setTitle(idea.title); setAngle(idea.angle ?? "");
      setBody(idea.body); setStatus(idea.status); setIsFavorite(idea.isFavorite);
    }
  }, [idea?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveMut = useMutation({
    mutationFn: (payload: object) =>
      http.put<ContentIdeaResponse>(`/api/v1/content-ideas/${idea?.id ?? ""}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["content-ideas"] });
      toast.success("Idea updated"); onClose();
    },
    onError: () => toast.error("Failed to update idea"),
  });

  if (!idea) return null;

  return (
    <Dialog open={Boolean(idea)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Idea</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="e-title">Title</Label>
            <Input id="e-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="e-angle">Angle / Tag</Label>
            <Input id="e-angle" value={angle} onChange={(e) => setAngle(e.target.value)}
              placeholder="e.g. Contrarian, How-to, funding" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="idea">Idea</SelectItem>
                  <SelectItem value="drafting">Drafting</SelectItem>
                  <SelectItem value="published">Published</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Favourite</Label>
              <Button variant={isFavorite ? "default" : "outline"} className="w-full"
                onClick={() => setIsFavorite((f) => !f)}>
                <Star className="h-4 w-4" />
                {isFavorite ? "Favourited" : "Mark favourite"}
              </Button>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="e-body">Body / Outline</Label>
            <Textarea id="e-body" value={body} onChange={(e) => setBody(e.target.value)} rows={5} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => saveMut.mutate({
            title: title.trim(), angle: angle.trim() || null,
            body: body.trim(), status, isFavorite,
          })} disabled={saveMut.isPending || !title.trim()}>
            {saveMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */

export function ContentIdeasPage() {
  const qc = useQueryClient();
  const [genOpen, setGenOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [editIdea, setEditIdea] = useState<ContentIdeaResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ContentIdeaResponse | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  const { data: ideas = [], isLoading } = useQuery<ContentIdeaResponse[]>({
    queryKey: ["content-ideas"],
    queryFn: () => http.get<ContentIdeaResponse[]>("/api/v1/content-ideas"),
    retry: false,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/content-ideas/${id}`),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ["content-ideas"] });
      const prev = qc.getQueryData<ContentIdeaResponse[]>(["content-ideas"]);
      if (prev) qc.setQueryData(["content-ideas"], prev.filter((i) => i.id !== id));
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(["content-ideas"], ctx.prev);
      toast.error("Delete failed");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["content-ideas"] });
      toast.success("Idea deleted"); setDeleteTarget(null);
    },
  });

  const filtered = useMemo(
    () => ideas.filter((i) => statusFilter === "all" || i.status === statusFilter),
    [ideas, statusFilter]
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Content Ideas"
        description="Capture, draft, and manage content angles for LinkedIn posts, blog articles, and outreach hooks."
        actions={
          <div className="flex items-center gap-2">
            <Button onClick={() => setGenOpen(true)}>
              <Sparkles className="h-4 w-4" /> AI Suggest Ideas
            </Button>
            <Button variant="outline" onClick={() => setManualOpen(true)}>
              <Plus className="h-4 w-4" /> Manual Idea
            </Button>
          </div>
        }
      />

      {/* Filter row */}
      <div className="flex items-center gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="idea">Idea</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="drafting">Drafting</SelectItem>
            <SelectItem value="published">Published</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-sm text-muted-foreground">
          {filtered.length} of {ideas.length} idea{ideas.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-52 w-full" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={<Lightbulb className="h-10 w-10" />}
              title={ideas.length > 0 ? "No ideas match the filter" : "No content ideas yet"}
              description={
                ideas.length > 0
                  ? "Try clearing the status filter."
                  : "Click \"AI Suggest Ideas\" to generate content angles, or add one manually."
              }
              action={ideas.length === 0 ? (
                <Button size="sm" onClick={() => setGenOpen(true)}>
                  <Sparkles className="h-4 w-4" /> AI Suggest Ideas
                </Button>
              ) : undefined}
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((idea) => (
            <Card key={idea.id}
              className="group flex flex-col hover:shadow-md transition-shadow relative"
            >
              {/* Top-right action icons — shown on hover */}
              <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                <button
                  className="rounded p-1 hover:bg-muted"
                  onClick={(e) => { e.stopPropagation(); setEditIdea(idea); }}
                >
                  <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
                <button
                  className="rounded p-1 hover:bg-muted"
                  onClick={(e) => { e.stopPropagation(); setDeleteTarget(idea); }}
                >
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </button>
              </div>

              <CardHeader className="pb-2 pr-14">
                {/* Tag row: status, AI badge, angle tag */}
                <div className="flex flex-wrap items-center gap-1.5 mb-2">
                  <span className={cn(
                    "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium",
                    STATUS_CHIP[idea.status] ?? STATUS_CHIP.idea
                  )}>
                    {idea.status}
                  </span>
                  {/* AI badge — shown when generated (no icpProfileId means AI-generated via topic) */}
                  <span className="inline-flex items-center gap-0.5 rounded-full bg-violet-100 border border-violet-200 px-2 py-0.5 text-[10px] font-medium text-violet-700">
                    <Sparkles className="h-2.5 w-2.5" /> AI
                  </span>
                  {idea.angle && (
                    <span className="inline-flex items-center rounded-full bg-slate-100 border border-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                      {idea.angle}
                    </span>
                  )}
                  {idea.isFavorite && (
                    <Heart className="h-3.5 w-3.5 fill-rose-500 text-rose-500 ml-auto" />
                  )}
                </div>
                {/* Title */}
                <h3 className="text-sm font-semibold leading-snug cursor-pointer hover:text-primary"
                  onClick={() => setEditIdea(idea)}>
                  {idea.title}
                </h3>
              </CardHeader>

              <CardContent className="flex-1 pb-2">
                <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
                  {idea.body}
                </p>
              </CardContent>

              <CardFooter className="pt-2 border-t">
                <span className="text-[11px] text-muted-foreground">
                  {formatDate(idea.generatedAt)}
                </span>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <GenerateDialog open={genOpen} onOpenChange={setGenOpen} />
      <ManualIdeaDialog open={manualOpen} onOpenChange={setManualOpen} />
      <EditDialog idea={editIdea} onClose={() => setEditIdea(null)} />

      {/* Delete confirmation */}
      <Dialog open={Boolean(deleteTarget)} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete content idea?</DialogTitle>
            <DialogDescription>
              "{deleteTarget?.title}" will be permanently removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive"
              onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
              disabled={deleteMut.isPending}>
              {deleteMut.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}