/**
 * TemplatesPage.tsx — OUTRENA Phase 4 (Task 3-C)
 *
 * Email templates CRUD. Grid + edit dialog with variable hints.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LayoutTemplate,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { ErrorState } from "@/components/ui/error-state";
import { formatDate, truncate } from "@/lib/utils";
import type { EmailTemplate } from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { RichContentEditor } from "@/components/RichContentEditor";

/* ── Types & mocks ──────────────────────────────────────────────────────── */

type TemplateCategory =
  | "cold_followup"
  | "introbreakup"
  | "value"
  | "invitation";

const CATEGORIES: TemplateCategory[] = [
  "cold_followup",
  "introbreakup",
  "value",
  "invitation",
];

const CATEGORY_VARIANT: Record<TemplateCategory, "default" | "secondary" | "outline" | "success"> = {
  cold_followup: "default",
  introbreakup: "secondary",
  value: "success",
  invitation: "outline",
};

const MOCK_TEMPLATES: EmailTemplate[] = [
  {
    id: "t1",
    name: "Cold First Touch — Trigger",
    subject: "{{company}}'s close-cycle SLA — late again?",
    body: `Hi {{firstName}},\n\nNoticed {{company}} recently expanded the finance team — congrats.\n\nMost ops leaders at Series B fintechs tell me the close cycle keeps slipping past 10 business days. The cost isn't just audit risk — it's the 30+ hours finance spends reconciling multi-entity ledgers every month.\n\nOUTRENA automates reconciliation orchestration so finance teams close 60% faster within 90 days. Worth a 15-min call next Tuesday?\n\n— Alex`,
    category: "cold_followup",
    createdAt: "2024-11-01T10:00:00Z",
    updatedAt: "2024-12-15T14:00:00Z",
  },
  {
    id: "t2",
    name: "Follow-up #2 — New Evidence",
    subject: "Re: {{company}} close cycle — new benchmark",
    body: `Hi {{firstName}},\n\nFollowing up with fresh data: we benchmarked 40 Series B fintechs and {{company}}'s segment averages 11.4-day close cycles. The top quartile closes in 6 days.\n\nHappy to share the benchmark + how OUTRENA gets teams into the top quartile within 90 days.\n\n— Alex`,
    category: "cold_followup",
    createdAt: "2024-11-08T09:30:00Z",
    updatedAt: "2024-12-18T11:00:00Z",
  },
  {
    id: "t3",
    name: "Breakup Email",
    subject: "Closing the loop — should I break up with you?",
    body: `Hi {{firstName}},\n\nI'll stop here — happy to circle back when reconciliation becomes a priority for {{company}}. If timing changes, just reply.\n\n— Alex`,
    category: "introbreakup",
    createdAt: "2024-10-22T16:11:00Z",
    updatedAt: "2024-11-30T08:45:00Z",
  },
  {
    id: "t4",
    name: "Value Touch — ROI Model",
    subject: "{{company}} ROI model attached",
    body: `Hi {{firstName}},\n\nAttached a 1-page ROI model for {{company}} based on a 200-person fintech. Conservative case: 47% close-cycle reduction in 90 days.\n\nWorth a 15-min walkthrough?\n\n— Alex`,
    category: "value",
    createdAt: "2024-12-04T13:50:00Z",
    updatedAt: "2025-01-04T13:50:00Z",
  },
  {
    id: "t5",
    name: "Meeting Invitation — Discovery",
    subject: "OUTRENA × {{company}} — 30 min next Tuesday?",
    body: `Hi {{firstName}},\n\nI'd love to set up a 30-min discovery call. Tuesday at 10am or Wednesday at 2pm PT both work — let me know which fits.\n\nI'll bring a tailored ROI breakdown for {{company}}.\n\n— Alex`,
    category: "invitation",
    createdAt: "2024-09-15T07:20:00Z",
    updatedAt: "2024-12-22T18:30:00Z",
  },
  {
    id: "t6",
    name: "Intro Touch — Mutual Connection",
    subject: "Intro: {{company}} × OUTRENA (via {{referrer}})",
    body: `Hi {{firstName}},\n\n{{referrer}} suggested we connect. Quick context: OUTRENA helps ops leaders at fintechs like {{company}} cut close cycles by 60% within 90 days.\n\nWorth a 15-min intro next week?\n\n— Alex`,
    category: "introbreakup",
    createdAt: "2024-07-01T12:00:00Z",
    updatedAt: "2024-10-15T10:00:00Z",
  },
];

interface FormState {
  id?: string;
  name: string;
  category: TemplateCategory;
  subject: string;
  body: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  category: "cold_followup",
  subject: "",
  body: "",
};

const VARIABLES = ["{{firstName}}", "{{company}}", "{{title}}", "{{referrer}}", "{{campaignName}}"];

/* ── Page ───────────────────────────────────────────────────────────────── */

export function TemplatesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<EmailTemplate | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const { data: apiTemplates, isLoading , isError, error, refetch } = useQuery({
    queryKey: ["templates"],
    queryFn: () => http.get<EmailTemplate[]>("/api/v1/templates"),
    retry: false,
  });
  const templates = apiTemplates ?? MOCK_TEMPLATES;

  const filtered = templates.filter((t) => {
    const matchesSearch = t.name.toLowerCase().includes(search.toLowerCase());
    const matchesCat = categoryFilter === "all" || t.category === categoryFilter;
    return matchesSearch && matchesCat;
  });

  const createMut = useMutation({
    mutationFn: (body: { name: string; category: string; subject: string; body: string }) =>
      http.post<EmailTemplate>("/api/v1/templates", body),
    onSuccess: () => {
      toast.success("Template created");
      qc.invalidateQueries({ queryKey: ["templates"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create template"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<EmailTemplate> }) =>
      http.put<EmailTemplate>(`/api/v1/templates/${id}`, body),
    onSuccess: () => {
      toast.success("Template saved");
      qc.invalidateQueries({ queryKey: ["templates"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save template"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete<{ message: string }>(`/api/v1/templates/${id}`),
    onSuccess: () => {
      toast.success("Template deleted");
      qc.invalidateQueries({ queryKey: ["templates"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete template"),
  });

  function openNew() {
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  }
  function openEdit(t: EmailTemplate) {
    setForm({
      id: t.id,
      name: t.name,
      category: (t.category as TemplateCategory) ?? "cold_followup",
      subject: t.subject,
      body: t.body,
    });
    setEditorOpen(true);
  }
  function closeEditor() {
    setEditorOpen(false);
    setForm(EMPTY_FORM);
  }

  function handleSave() {
    if (!form.name.trim() || !form.subject.trim()) {
      toast.error("Name and subject are required");
      return;
    }
    if (form.id) {
      updateMut.mutate({ id: form.id, body: form });
    } else {
      createMut.mutate(form);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Templates"
        description="Reusable email templates with variable substitution. Categories: cold_followup, introbreakup, value, invitation."
        actions={
          <Button size="sm" onClick={openNew}>
            <Plus className="h-4 w-4" /> New Template
          </Button>
        }
      />

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search templates…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="sm:w-44"
            >
              <option value="all">All categories</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {isError ? (
        <ErrorState
          title="Failed to load templates"
          error={error}
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<LayoutTemplate className="h-6 w-6" />}
          title="No templates found"
          description="Create your first template to standardise outreach."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((t) => (
            <Card key={t.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-base">{t.name}</CardTitle>
                    <CardDescription className="mt-1">
                      {t.category && (
                        <Badge variant={CATEGORY_VARIANT[t.category as TemplateCategory] ?? "secondary"}>
                          {t.category}
                        </Badge>
                      )}
                    </CardDescription>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEdit(t)}
                          aria-label="Edit template"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Edit template</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteTarget(t)}
                          aria-label="Delete template"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete template</TooltipContent>
                    </Tooltip>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Subject</p>
                  <p className="text-sm font-medium">{t.subject}</p>
                </div>
                <div className="flex-1">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Body preview</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
                    {truncate(t.body, 160)}
                  </p>
                </div>
                <p className="text-xs text-muted-foreground">Updated {formatDate(t.updatedAt)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Editor dialog */}
      <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
        <DialogClose onClose={closeEditor} />
        <DialogHeader>
          <DialogTitle>{form.id ? "Edit Template" : "New Template"}</DialogTitle>
          <DialogDescription>
            Use variables like <code>{"{{firstName}}"}</code> and <code>{"{{company}}"}</code> for personalisation.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="tpl-name">Name</Label>
            <Input
              id="tpl-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Cold First Touch — Trigger"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="tpl-cat">Category</Label>
              <Select
                id="tpl-cat"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value as TemplateCategory })}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Available variables</Label>
              <div className="flex flex-wrap gap-1 pt-2">
                {VARIABLES.map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setForm((prev) => ({ ...prev, body: `${prev.body}${v}` }))}
                    className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs hover:bg-muted/70"
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="tpl-subject">Subject</Label>
            <Input
              id="tpl-subject"
              value={form.subject}
              onChange={(e) => setForm({ ...form, subject: e.target.value })}
              placeholder="{{company}}'s close-cycle SLA — late again?"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tpl-body">Body</Label>
            <RichContentEditor
              value={form.body}
              onChange={(val) => setForm({ ...form, body: val })}
              placeholder="Hi {{firstName}},…"
              minHeight={300}
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
            {createMut.isPending || updateMut.isPending ? "Saving…" : "Save Template"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Delete dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete template?</DialogTitle>
          <DialogDescription>
            “{deleteTarget?.name}” will be permanently removed.
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
  );
}
