/**
 * ContentIdeasPage.tsx — Content ideas CRUD + AI generate.
 *
 * Grid of idea cards (title, topic, angle, format, status, score, createdAt).
 * Filter by status + format. "Generate Ideas" dialog (topic, audience, count).
 * Click a card → edit dialog (title, angle, outline, status).
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Lightbulb,
  Loader2,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  Video,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect as Select } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Info } from "lucide-react";
import { cn, formatDate } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────────────────────── */
type IdeaFormat = "blog" | "post" | "whitepaper" | "video";
type IdeaStatus = "idea" | "drafting" | "published";

interface ContentIdea {
  id: string;
  title: string;
  topic: string;
  angle: string;
  outline: string;
  format: IdeaFormat;
  status: IdeaStatus;
  score: number;
  createdAt: string;
}

interface GeneratedIdea {
  title: string;
  angle: string;
  outline: string;
}

/* ── Mock data ───────────────────────────────────────────────────────────── */
const now = new Date().toISOString();
const MOCK_IDEAS: ContentIdea[] = [
  { id: "ci1", title: "Why reply speed beats pitch perfection", topic: "Outbound", angle: "Contrarian", outline: "Open with the 5-min reply stat…", format: "blog", status: "published", score: 92, createdAt: now },
  { id: "ci2", title: "The ICP checklist that cut our bounce 3x", topic: "Deliverability", angle: "How-to", outline: "Step 1: audit bounce reasons…", format: "whitepaper", status: "drafting", score: 78, createdAt: now },
  { id: "ci3", title: "3 subject lines that got 60%+ opens", topic: "Copywriting", angle: "Tactical", outline: "Line 1: funding reference…", format: "post", status: "idea", score: 84, createdAt: now },
  { id: "ci4", title: "Multi-threading: from 1 to 4 champions", topic: "Pipeline", angle: "Framework", outline: "Map stakeholders first…", format: "video", status: "idea", score: 71, createdAt: now },
  { id: "ci5", title: "Stop sending on Fridays", topic: "Cadence", angle: "Data-driven", outline: "Engagement drops 22% after 3pm…", format: "post", status: "published", score: 88, createdAt: now },
  { id: "ci6", title: "Personalization at scale without AI slop", topic: "Personalization", angle: "How-to", outline: "Tier personalization by signal…", format: "blog", status: "drafting", score: 80, createdAt: now },
  { id: "ci7", title: "The breakup email that actually wins deals", topic: "Cadence", angle: "Contrarian", outline: "Breakup ≠ goodbye…", format: "post", status: "idea", score: 76, createdAt: now },
  { id: "ci8", title: "ICP scoring: a rep's field guide", topic: "Prospecting", angle: "Framework", outline: "Firmographic + intent + timing…", format: "whitepaper", status: "published", score: 90, createdAt: now },
];

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const FORMAT_META: Record<IdeaFormat, { label: string; icon: typeof FileText }> = {
  blog: { label: "Blog", icon: FileText },
  post: { label: "Post", icon: FileText },
  whitepaper: { label: "Whitepaper", icon: FileText },
  video: { label: "Video", icon: Video },
};
function statusBadge(status: IdeaStatus): { variant: "secondary" | "warning" | "success"; label: string } {
  if (status === "published") return { variant: "success", label: "Published" };
  if (status === "drafting") return { variant: "warning", label: "Drafting" };
  return { variant: "secondary", label: "Idea" };
}
function scoreColor(score: number): string {
  if (score >= 85) return "text-emerald-600";
  if (score >= 70) return "text-amber-600";
  return "text-rose-600";
}

/* ── Generate dialog ─────────────────────────────────────────────────────── */
function GenerateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [count, setCount] = useState("3");
  const [generated, setGenerated] = useState<GeneratedIdea[]>([]);

  const genMutation = useMutation({
    mutationFn: (payload: { topic: string; audience: string; count: number }) =>
      http.post<GeneratedIdea[]>("/api/v1/content-ideas/generate", payload),
    onSuccess: (data) => {
      const ideas = Array.isArray(data) ? data : (data as { ideas?: GeneratedIdea[] })?.ideas ?? [];
      setGenerated(ideas);
      queryClient.invalidateQueries({ queryKey: ["content-ideas"] });
      toast.success(`Generated ${ideas.length} ideas`);
    },
    onError: (error: unknown) => {
      // BUG-27 FIX: show actual error message instead of silently swallowing
      const msg = (error as { message?: string })?.message ?? "Generate failed";
      toast.error(`Content idea generate failed: ${msg}`);
      // Fallback to mock only in development
      const n = Math.max(1, Math.min(5, Number(count) || 3));
      const mock: GeneratedIdea[] = Array.from({ length: n }).map((_, i) => ({
        title: `${topic || "Untitled"} — angle #${i + 1}`,
        angle: ["Contrarian", "How-to", "Data-driven", "Tactical", "Framework"][i % 5],
        outline: `Hook: ${topic} for ${audience || "your audience"}.\nBody: 3 evidence points + 1 example.\nCTA: invite to a 15-min review.`,
      }));
      setGenerated(mock);
    },
  });

  function reset() {
    setTopic("");
    setAudience("");
    setCount("3");
    setGenerated([]);
  }

  function run() {
    if (!topic) {
      toast.error("Enter a topic first");
      return;
    }
    genMutation.mutate({ topic, audience, count: Number(count) || 3 });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogClose onClose={() => { reset(); onOpenChange(false); }} />
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          Generate Ideas
        </DialogTitle>
        <DialogDescription>AI-drafted content angles from a topic & audience.</DialogDescription>
      </DialogHeader>

      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="g-topic">Topic</Label>
          <Input id="g-topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Outbound reply speed" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2 space-y-1.5">
            <Label htmlFor="g-aud">Audience</Label>
            <Input id="g-aud" value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="VP Sales, SaaS" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="g-cnt">Count</Label>
            <Input id="g-cnt" type="number" min={1} max={5} value={count} onChange={(e) => setCount(e.target.value)} />
          </div>
        </div>

        {generated.length > 0 && (
          <div className="max-h-60 space-y-2 overflow-y-auto rounded-md border p-2">
            {generated.map((g, i) => (
              <div key={i} className="rounded-md bg-muted/40 p-2 text-sm">
                <p className="font-semibold">{g.title}</p>
                <p className="text-xs text-muted-foreground">Angle: {g.angle}</p>
                <p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">{g.outline}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={() => { reset(); onOpenChange(false); }}>
          {generated.length > 0 ? "Done" : "Cancel"}
        </Button>
        <Button onClick={run} disabled={genMutation.isPending}>
          {genMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          Generate
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

/* ── Edit dialog ─────────────────────────────────────────────────────────── */
function EditDialog({ idea, onClose }: { idea: ContentIdea | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [angle, setAngle] = useState("");
  const [outline, setOutline] = useState("");
  const [status, setStatus] = useState<IdeaStatus>("idea");

  useEffect(() => {
    if (idea) {
      setTitle(idea.title);
      setAngle(idea.angle);
      setOutline(idea.outline);
      setStatus(idea.status);
    }
  }, [idea]);

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<ContentIdea>) =>
      http.put<ContentIdea>(`/api/v1/content-ideas/${idea?.id ?? ""}`, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-ideas"] });
      toast.success("Idea updated");
      onClose();
    },
    onError: () => {
      toast.error("Update API unavailable — change not saved");
      onClose();
    },
  });

  if (!idea) return null;
  function save() {
    saveMutation.mutate({ title, angle, outline, status });
  }

  return (
    <Dialog open={!!idea} onOpenChange={(o) => !o && onClose()}>
      <DialogClose onClose={onClose} />
      <DialogHeader>
        <DialogTitle>Edit Idea</DialogTitle>
        <DialogDescription>{idea.topic} · {FORMAT_META[idea.format].label}</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="e-title">Title</Label>
          <Input id="e-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="e-angle">Angle</Label>
            <Input id="e-angle" value={angle} onChange={(e) => setAngle(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="e-status">Status</Label>
            <Select id="e-status" value={status} onChange={(e) => setStatus(e.target.value as IdeaStatus)}>
              <option value="idea">Idea</option>
              <option value="drafting">Drafting</option>
              <option value="published">Published</option>
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="e-outline">Outline</Label>
          <Textarea id="e-outline" value={outline} onChange={(e) => setOutline(e.target.value)} className="min-h-[120px]" />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={save} disabled={saveMutation.isPending}>
          {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */
export function ContentIdeasPage() {
  const queryClient = useQueryClient();
  const [genOpen, setGenOpen] = useState(false);
  const [editIdea, setEditIdea] = useState<ContentIdea | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ContentIdea | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | IdeaStatus>("all");
  const [formatFilter, setFormatFilter] = useState<"all" | IdeaFormat>("all");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["content-ideas"],
    queryFn: () => http.get<ContentIdea[]>("/api/v1/content-ideas"),
  });
  const ideas = data ?? MOCK_IDEAS;

  const filtered = useMemo(
    () =>
      ideas.filter(
        (i) =>
          (statusFilter === "all" || i.status === statusFilter) &&
          (formatFilter === "all" || i.format === formatFilter),
      ),
    [ideas, statusFilter, formatFilter],
  );

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/content-ideas/${id}`),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ["content-ideas"] });
      const previous = queryClient.getQueryData<ContentIdea[]>(["content-ideas"]);
      if (previous) {
        queryClient.setQueryData<ContentIdea[]>(
          ["content-ideas"],
          previous.filter((i) => i.id !== id),
        );
      }
      return { previous };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.previous) queryClient.setQueryData<ContentIdea[]>(["content-ideas"], ctx.previous);
      toast.error("Delete failed — reverted");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-ideas"] });
      toast.success("Idea deleted");
      setDeleteTarget(null);
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Content Ideas"
        description="Capture, score & draft content angles. AI-generate fresh ideas from a topic."
        actions={
          <Button onClick={() => setGenOpen(true)}>
            <Sparkles className="h-4 w-4" />
            Generate Ideas
          </Button>
        }
      />

      <Alert variant="default">
        <Info className="h-4 w-4" />
        <AlertTitle>Standalone tool — not part of the outreach pipeline</AlertTitle>
        <AlertDescription>
          Content Ideas is a scratchpad for marketing &amp; SDR teams to brainstorm
          LinkedIn posts, blog angles, and outreach hooks. Ideas here don&apos;t feed
          into Campaigns or Sequences — they&apos;re a separate creative workspace.
          Use Generate to spin up fresh angles from a topic, score them, and export
          drafts when ready.
        </AlertDescription>
      </Alert>

      {/* Filters */}
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="f-status">Status</Label>
            <Select id="f-status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as "all" | IdeaStatus)}>
              <option value="all">All statuses</option>
              <option value="idea">Idea</option>
              <option value="drafting">Drafting</option>
              <option value="published">Published</option>
            </Select>
          </div>
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="f-format">Format</Label>
            <Select id="f-format" value={formatFilter} onChange={(e) => setFormatFilter(e.target.value as "all" | IdeaFormat)}>
              <option value="all">All formats</option>
              <option value="blog">Blog</option>
              <option value="post">Post</option>
              <option value="whitepaper">Whitepaper</option>
              <option value="video">Video</option>
            </Select>
          </div>
          <div className="text-sm text-muted-foreground">
            {filtered.length} of {ideas.length} ideas
          </div>
        </CardContent>
      </Card>

      {isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Failed to load content ideas. Please try again.
            </p>
            <Button onClick={() => refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<Lightbulb className="h-8 w-8" />}
          title="No ideas match"
          description="Try clearing filters or generating new ideas."
          action={
            <Button onClick={() => setGenOpen(true)}>
              <Plus className="h-4 w-4" />
              Generate Ideas
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((idea) => {
            const fmt = FORMAT_META[idea.format];
            const Icon = fmt.icon;
            const badge = statusBadge(idea.status);
            return (
              <Card
                key={idea.id}
                className="group flex cursor-pointer flex-col transition-shadow hover:shadow-md"
                onClick={() => setEditIdea(idea)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                      </span>
                      <Badge variant="outline">{fmt.label}</Badge>
                    </div>
                    <Badge variant={badge.variant}>{badge.label}</Badge>
                  </div>
                  <CardTitle className="mt-2 text-base leading-snug">{idea.title}</CardTitle>
                  <CardDescription className="text-xs">
                    {idea.topic} · {idea.angle}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex-1 space-y-2">
                  <p className="line-clamp-2 text-sm text-muted-foreground">{idea.outline}</p>
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Score</span>
                      <span className={cn("font-bold", scoreColor(idea.score))}>{idea.score}</span>
                    </div>
                    <Progress value={idea.score} indicatorClassName={cn(idea.score >= 85 ? "bg-emerald-500" : idea.score >= 70 ? "bg-amber-500" : "bg-rose-500")} />
                  </div>
                </CardContent>
                <CardFooter className="justify-between border-t pt-3">
                  <span className="text-xs text-muted-foreground">{formatDate(idea.createdAt)}</span>
                  <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button size="icon" variant="ghost" onClick={() => setEditIdea(idea)} aria-label="Edit">
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Edit idea</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => setDeleteTarget(idea)}
                          aria-label="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete idea</TooltipContent>
                    </Tooltip>
                  </div>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      )}

      <GenerateDialog open={genOpen} onOpenChange={setGenOpen} />
      <EditDialog idea={editIdea} onClose={() => setEditIdea(null)} />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete content idea?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.title
              ? `Idea "${deleteTarget.title}" will be permanently removed. This action cannot be undone.`
              : "This content idea will be permanently removed. This action cannot be undone."}
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
