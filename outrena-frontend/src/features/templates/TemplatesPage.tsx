// /**
//  * TemplatesPage.tsx — Local email template CRUD.
//  *
//  * Gaps closed:
//  *   TM-1  MailBridge connection warning — shown when no MailBridge config
//  *         is configured (links to Domains > MailBridge)
//  *   TM-2  Template list from real API — GET /api/v1/templates
//  *   TM-3  Create Template dialog: name, category, subject, Jinja2 body
//  *         editor with {{ variable_name }} syntax hint
//  *   TM-4  Preview template (live variable substitution in sidebar)
//  *   TM-5  Delete template — DELETE /api/v1/templates/{id}
//  *
//  * API contract (EmailTemplateResponse):
//  *   { id, name, category, framework, subjectTemplate, bodyTemplate,
//  *     variables, isShared, createdAt, updatedAt }
//  *   POST/PUT accept aliases: body→bodyTemplate, subject→subjectTemplate
//  */
// import { useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   AlertCircle,
//   BookOpen,
//   Edit3,
//   Eye,
//   LayoutTemplate,
//   Plus,
//   RefreshCw,
//   Search,
//   Trash2,
// } from "lucide-react";
// import { toast } from "sonner";

// import { http } from "@/services/apiClient";
// import { formatDate, truncate } from "@/lib/utils";
// import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
// import { Badge } from "@/components/ui/badge";
// import { Button } from "@/components/ui/button";
// import {
//   Card,
//   CardContent,
//   CardDescription,
//   CardHeader,
//   CardTitle,
// } from "@/components/ui/card";
// import {
//   Dialog,
//   DialogContent,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
// } from "@/components/ui/dialog";
// import { EmptyState } from "@/components/ui/empty-state";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { PageHeader } from "@/components/ui/page-header";
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from "@/components/ui/select";
// import { Skeleton } from "@/components/ui/skeleton";
// import { Textarea } from "@/components/ui/textarea";

// /* ── Types ──────────────────────────────────────────────────────────────── */

// interface EmailTemplateResponse {
//   id: string;
//   name: string;
//   category: string;
//   framework: string | null;
//   subjectTemplate: string | null;
//   bodyTemplate: string;
//   variables: string[];
//   isShared: boolean;
//   createdAt: string;
//   updatedAt: string;
// }

// interface MailBridgeConfig {
//   id: string;
//   name: string;
//   baseUrl: string;
//   isActive: boolean;
// }

// /* ── Constants ──────────────────────────────────────────────────────────── */

// const CATEGORIES = [
//   { id: "cold_outreach", label: "Cold Outreach" },
//   { id: "follow_up", label: "Follow-up" },
//   { id: "breakup", label: "Breakup" },
//   { id: "value", label: "Value Touch" },
//   { id: "invitation", label: "Meeting Invitation" },
//   { id: "general", label: "General" },
// ] as const;

// const CATEGORY_COLORS: Record<string, string> = {
//   cold_outreach: "bg-blue-100 text-blue-700 border-blue-200",
//   follow_up: "bg-violet-100 text-violet-700 border-violet-200",
//   breakup: "bg-rose-100 text-rose-700 border-rose-200",
//   value: "bg-emerald-100 text-emerald-700 border-emerald-200",
//   invitation: "bg-amber-100 text-amber-700 border-amber-200",
//   general: "bg-slate-100 text-slate-700 border-slate-200",
// };

// // Standard Jinja2 variables available in OUTRENA templates
// const JINJA_VARIABLES = [
//   "{{ first_name }}",
//   "{{ last_name }}",
//   "{{ company }}",
//   "{{ title }}",
//   "{{ signal }}",
//   "{{ sender_name }}",
//   "{{ sender_company }}",
//   "{{ result_metric }}",
// ];

// /* ── Form state ─────────────────────────────────────────────────────────── */

// interface TemplateForm {
//   id?: string;
//   name: string;
//   category: string;
//   subjectTemplate: string;
//   bodyTemplate: string;
// }

// const EMPTY_FORM: TemplateForm = {
//   name: "",
//   category: "cold_outreach",
//   subjectTemplate: "",
//   bodyTemplate: "",
// };

// /* ── Preview helper ─────────────────────────────────────────────────────── */

// const SAMPLE_VARS: Record<string, string> = {
//   first_name: "Jordan",
//   last_name: "Avery",
//   company: "Acme Corp",
//   title: "VP Revenue",
//   signal: "raised Series B",
//   sender_name: "Alex",
//   sender_company: "OUTRENA",
//   result_metric: "60% faster close",
// };

// function applyPreview(template: string): string {
//   return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key: string) =>
//     SAMPLE_VARS[key] ?? `{{${key}}}`
//   );
// }

// /* ── Page ───────────────────────────────────────────────────────────────── */

// export function TemplatesPage() {
//   const qc = useQueryClient();
//   const [search, setSearch] = useState("");
//   const [categoryFilter, setCategoryFilter] = useState("all");
//   const [editorOpen, setEditorOpen] = useState(false);
//   const [previewTarget, setPreviewTarget] =
//     useState<EmailTemplateResponse | null>(null);
//   const [deleteTarget, setDeleteTarget] =
//     useState<EmailTemplateResponse | null>(null);
//   const [form, setForm] = useState<TemplateForm>(EMPTY_FORM);

//   /* ── Queries ── */

//   // TM-1 — check if MailBridge is configured
//   const { data: mbConfigs = [] } = useQuery<MailBridgeConfig[]>({
//     queryKey: ["mailbridge-config"],
//     queryFn: () => http.get<MailBridgeConfig[]>("/api/v1/mailbridge/config"),
//     retry: false,
//   });

//   const hasMailBridge = mbConfigs.some((c) => c.isActive);

//   // TM-2 — template list from real API
//   const { data: templates = [], isLoading } = useQuery<EmailTemplateResponse[]>(
//     {
//       queryKey: ["templates"],
//       queryFn: () => http.get<EmailTemplateResponse[]>("/api/v1/templates"),
//       retry: false,
//     }
//   );

//   /* ── Mutations ── */

//   const createMut = useMutation({
//     mutationFn: (body: Omit<TemplateForm, "id">) =>
//       http.post<EmailTemplateResponse>("/api/v1/templates", body),
//     onSuccess: () => {
//       toast.success("Template created");
//       qc.invalidateQueries({ queryKey: ["templates"] });
//       closeEditor();
//     },
//     onError: () => toast.error("Failed to create template"),
//   });

//   const updateMut = useMutation({
//     mutationFn: ({ id, body }: { id: string; body: Omit<TemplateForm, "id"> }) =>
//       http.put<EmailTemplateResponse>(`/api/v1/templates/${id}`, body),
//     onSuccess: () => {
//       toast.success("Template saved");
//       qc.invalidateQueries({ queryKey: ["templates"] });
//       closeEditor();
//     },
//     onError: () => toast.error("Failed to save template"),
//   });

//   // TM-5 — delete
//   const deleteMut = useMutation({
//     mutationFn: (id: string) => http.delete(`/api/v1/templates/${id}`),
//     onSuccess: () => {
//       toast.success("Template deleted");
//       qc.invalidateQueries({ queryKey: ["templates"] });
//       setDeleteTarget(null);
//     },
//     onError: () => toast.error("Failed to delete template"),
//   });

//   /* ── Handlers ── */

//   function openNew() {
//     setForm(EMPTY_FORM);
//     setEditorOpen(true);
//   }

//   function openEdit(t: EmailTemplateResponse) {
//     setForm({
//       id: t.id,
//       name: t.name,
//       category: t.category,
//       subjectTemplate: t.subjectTemplate ?? "",
//       bodyTemplate: t.bodyTemplate,
//     });
//     setEditorOpen(true);
//   }

//   function closeEditor() {
//     setEditorOpen(false);
//     setForm(EMPTY_FORM);
//   }

//   function handleSave() {
//     if (!form.name.trim()) {
//       toast.error("Name is required");
//       return;
//     }
//     const payload = {
//       name: form.name.trim(),
//       category: form.category,
//       subjectTemplate: form.subjectTemplate.trim(),
//       bodyTemplate: form.bodyTemplate.trim(),
//       variables: JINJA_VARIABLES.filter((v) =>
//         form.bodyTemplate.includes(v.replace(/\s/g, ""))
//       ).map((v) => v.replace(/\{\{\s*|\s*\}\}/g, "")),
//       isShared: true,
//     };
//     if (form.id) {
//       updateMut.mutate({ id: form.id, body: payload });
//     } else {
//       createMut.mutate(payload);
//     }
//   }

//   /* ── Filter ── */

//   const filtered = templates.filter((t) => {
//     const matchSearch =
//       !search || t.name.toLowerCase().includes(search.toLowerCase());
//     const matchCat = categoryFilter === "all" || t.category === categoryFilter;
//     return matchSearch && matchCat;
//   });

//   const isSaving = createMut.isPending || updateMut.isPending;

//   /* ── Render ── */

//   return (
//     <div className="space-y-6">
//       <PageHeader
//         title="Templates"
//         description="Reusable Jinja2 email templates with variable substitution — used by Sequences and Email Studio."
//         actions={
//           <Button size="sm" onClick={openNew}>
//             <Plus className="h-4 w-4" /> New Template
//           </Button>
//         }
//       />

//       {/* TM-1 — MailBridge warning */}
//       {!hasMailBridge && (
//         <Alert variant="default" className="border-amber-300 bg-amber-50">
//           <AlertCircle className="h-4 w-4 text-amber-600" />
//           <AlertTitle className="text-amber-800">
//             No active MailBridge connection
//           </AlertTitle>
//           <AlertDescription className="text-amber-700">
//             Templates are stored locally and can be used in Sequences. To send
//             via MailBridge, configure a connection in{" "}
//             <a
//               href="/setup/domains"
//               className="underline font-medium hover:no-underline"
//             >
//               Domains → MailBridge
//             </a>
//             .
//           </AlertDescription>
//         </Alert>
//       )}

//       {/* Info card */}
//       <Card className="border-blue-100 bg-blue-50/50">
//         <CardContent className="p-4">
//           <div className="flex items-start gap-3">
//             <BookOpen className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
//             <div className="text-xs space-y-1">
//               <p className="font-medium text-blue-900">
//                 Jinja2 Template Syntax
//               </p>
//               <p className="text-blue-800">
//                 Use{" "}
//                 <code className="bg-blue-100 px-1 rounded">
//                   {"{{ first_name }}"}
//                 </code>
//                 ,{" "}
//                 <code className="bg-blue-100 px-1 rounded">
//                   {"{{ company }}"}
//                 </code>
//                 , and{" "}
//                 <code className="bg-blue-100 px-1 rounded">
//                   {"{{ signal }}"}
//                 </code>{" "}
//                 for dynamic personalisation. Click variable chips in the editor
//                 to insert them.
//               </p>
//             </div>
//           </div>
//         </CardContent>
//       </Card>

//       {/* Filters */}
//       <div className="flex items-center gap-3 flex-wrap">
//         <div className="relative flex-1 min-w-[200px]">
//           <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
//           <Input
//             placeholder="Search templates…"
//             value={search}
//             onChange={(e) => setSearch(e.target.value)}
//             className="pl-9"
//           />
//         </div>
//         <Select value={categoryFilter} onValueChange={setCategoryFilter}>
//           <SelectTrigger className="w-[180px]">
//             <SelectValue placeholder="All categories" />
//           </SelectTrigger>
//           <SelectContent>
//             <SelectItem value="all">All categories</SelectItem>
//             {CATEGORIES.map((c) => (
//               <SelectItem key={c.id} value={c.id}>
//                 {c.label}
//               </SelectItem>
//             ))}
//           </SelectContent>
//         </Select>
//         <Button
//           variant="outline"
//           size="sm"
//           onClick={() => qc.invalidateQueries({ queryKey: ["templates"] })}
//         >
//           <RefreshCw className="h-4 w-4" />
//         </Button>
//       </div>

//       {/* TM-2 — Template grid */}
//       {isLoading ? (
//         <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
//           {Array.from({ length: 6 }).map((_, i) => (
//             <Skeleton key={i} className="h-48 w-full" />
//           ))}
//         </div>
//       ) : filtered.length === 0 ? (
//         <Card>
//           <CardContent className="py-12">
//             <EmptyState
//               icon={<LayoutTemplate className="h-10 w-10" />}
//               title={
//                 templates.length > 0
//                   ? "No templates match your filters"
//                   : "No templates yet"
//               }
//               description={
//                 templates.length > 0
//                   ? "Try adjusting the search or category filter."
//                   : 'Click "New Template" to create your first one.'
//               }
//               action={
//                 templates.length === 0 ? (
//                   <Button size="sm" onClick={openNew}>
//                     <Plus className="h-4 w-4" /> New Template
//                   </Button>
//                 ) : undefined
//               }
//             />
//           </CardContent>
//         </Card>
//       ) : (
//         <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
//           {filtered.map((t) => (
//             <Card key={t.id} className="flex flex-col hover:shadow-md transition-shadow">
//               <CardHeader className="pb-3">
//                 <div className="flex items-start justify-between gap-2">
//                   <div className="min-w-0 flex-1">
//                     <CardTitle className="text-base truncate">{t.name}</CardTitle>
//                     <CardDescription className="mt-1">
//                       <Badge
//                         variant="outline"
//                         className={`text-xs border ${CATEGORY_COLORS[t.category] ?? CATEGORY_COLORS.general}`}
//                       >
//                         {CATEGORIES.find((c) => c.id === t.category)?.label ??
//                           t.category}
//                       </Badge>
//                     </CardDescription>
//                   </div>
//                   <div className="flex shrink-0 gap-1">
//                     {/* TM-4 — Preview */}
//                     <Button
//                       variant="ghost"
//                       size="icon"
//                       className="h-7 w-7"
//                       onClick={() => setPreviewTarget(t)}
//                     >
//                       <Eye className="h-4 w-4" />
//                     </Button>
//                     <Button
//                       variant="ghost"
//                       size="icon"
//                       className="h-7 w-7"
//                       onClick={() => openEdit(t)}
//                     >
//                       <Edit3 className="h-4 w-4" />
//                     </Button>
//                     {/* TM-5 — Delete */}
//                     <Button
//                       variant="ghost"
//                       size="icon"
//                       className="h-7 w-7 text-destructive"
//                       onClick={() => setDeleteTarget(t)}
//                     >
//                       <Trash2 className="h-4 w-4" />
//                     </Button>
//                   </div>
//                 </div>
//               </CardHeader>
//               <CardContent className="flex flex-1 flex-col gap-2">
//                 {t.subjectTemplate && (
//                   <div>
//                     <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
//                       Subject
//                     </p>
//                     <p className="text-sm truncate">{t.subjectTemplate}</p>
//                   </div>
//                 )}
//                 <div className="flex-1">
//                   <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
//                     Body preview
//                   </p>
//                   <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">
//                     {truncate(t.bodyTemplate, 120)}
//                   </p>
//                 </div>
//                 <p className="text-xs text-muted-foreground">
//                   Updated {formatDate(t.updatedAt)}
//                 </p>
//               </CardContent>
//             </Card>
//           ))}
//         </div>
//       )}

//       {/* TM-3 — Create / Edit dialog */}
//       <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
//         <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
//           <DialogHeader>
//             <DialogTitle>
//               {form.id ? "Edit Template" : "New Template"}
//             </DialogTitle>
//             <DialogDescription>
//               Use{" "}
//               <code className="bg-muted px-1 rounded text-xs">
//                 {"{{ variable_name }}"}
//               </code>{" "}
//               syntax for dynamic personalisation. Click chips to insert.
//             </DialogDescription>
//           </DialogHeader>
//           <div className="space-y-4">
//             <div className="grid grid-cols-2 gap-3">
//               <div className="space-y-1.5">
//                 <Label htmlFor="tpl-name">Name *</Label>
//                 <Input
//                   id="tpl-name"
//                   value={form.name}
//                   onChange={(e) =>
//                     setForm((f) => ({ ...f, name: e.target.value }))
//                   }
//                   placeholder="e.g. Cold First Touch — Trigger"
//                 />
//               </div>
//               <div className="space-y-1.5">
//                 <Label>Category</Label>
//                 <Select
//                   value={form.category}
//                   onValueChange={(v) =>
//                     setForm((f) => ({ ...f, category: v }))
//                   }
//                 >
//                   <SelectTrigger>
//                     <SelectValue />
//                   </SelectTrigger>
//                   <SelectContent>
//                     {CATEGORIES.map((c) => (
//                       <SelectItem key={c.id} value={c.id}>
//                         {c.label}
//                       </SelectItem>
//                     ))}
//                   </SelectContent>
//                 </Select>
//               </div>
//             </div>
//             <div className="space-y-1.5">
//               <Label htmlFor="tpl-subject">Subject line</Label>
//               <Input
//                 id="tpl-subject"
//                 value={form.subjectTemplate}
//                 onChange={(e) =>
//                   setForm((f) => ({ ...f, subjectTemplate: e.target.value }))
//                 }
//                 placeholder="e.g. {{ company }}'s close-cycle SLA — late again?"
//               />
//             </div>
//             {/* Variable chips */}
//             <div className="space-y-1.5">
//               <Label>Insert variable</Label>
//               <div className="flex flex-wrap gap-1.5">
//                 {JINJA_VARIABLES.map((v) => (
//                   <button
//                     key={v}
//                     type="button"
//                     onClick={() =>
//                       setForm((f) => ({
//                         ...f,
//                         bodyTemplate: `${f.bodyTemplate}${v}`,
//                       }))
//                     }
//                     className="rounded bg-muted px-2 py-0.5 font-mono text-xs hover:bg-muted/70 transition-colors"
//                   >
//                     {v}
//                   </button>
//                 ))}
//               </div>
//             </div>
//             <div className="space-y-1.5">
//               <Label htmlFor="tpl-body">Body (Jinja2)</Label>
//               <Textarea
//                 id="tpl-body"
//                 value={form.bodyTemplate}
//                 onChange={(e) =>
//                   setForm((f) => ({ ...f, bodyTemplate: e.target.value }))
//                 }
//                 placeholder={"Hi {{ first_name }},\n\nNoticed {{ company }} just {{ signal }}…\n\nBest,\n{{ sender_name }}"}
//                 rows={10}
//                 className="font-mono text-sm"
//               />
//             </div>
//           </div>
//           <DialogFooter>
//             <Button variant="outline" onClick={closeEditor}>
//               Cancel
//             </Button>
//             <Button onClick={handleSave} disabled={isSaving || !form.name.trim()}>
//               {isSaving ? "Saving…" : form.id ? "Save Changes" : "Create Template"}
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>

//       {/* TM-4 — Preview dialog */}
//       <Dialog
//         open={Boolean(previewTarget)}
//         onOpenChange={(o) => !o && setPreviewTarget(null)}
//       >
//         <DialogContent className="max-w-lg">
//           <DialogHeader>
//             <DialogTitle>Preview — {previewTarget?.name}</DialogTitle>
//             <DialogDescription>
//               Sample variables applied:{" "}
//               {Object.entries(SAMPLE_VARS)
//                 .slice(0, 3)
//                 .map(([k, v]) => `${k}="${v}"`)
//                 .join(", ")}
//               …
//             </DialogDescription>
//           </DialogHeader>
//           <div className="space-y-3">
//             {previewTarget?.subjectTemplate && (
//               <div>
//                 <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
//                   Subject
//                 </p>
//                 <p className="text-sm font-medium">
//                   {applyPreview(previewTarget.subjectTemplate)}
//                 </p>
//               </div>
//             )}
//             <div>
//               <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
//                 Body
//               </p>
//               <div className="rounded-md border bg-muted/30 p-3">
//                 <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed">
//                   {applyPreview(previewTarget?.bodyTemplate ?? "")}
//                 </pre>
//               </div>
//             </div>
//           </div>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setPreviewTarget(null)}>
//               Close
//             </Button>
//             {previewTarget && (
//               <Button onClick={() => { setPreviewTarget(null); openEdit(previewTarget); }}>
//                 <Edit3 className="h-4 w-4" /> Edit
//               </Button>
//             )}
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>

//       {/* TM-5 — Delete dialog */}
//       <Dialog
//         open={Boolean(deleteTarget)}
//         onOpenChange={(o) => !o && setDeleteTarget(null)}
//       >
//         <DialogContent>
//           <DialogHeader>
//             <DialogTitle>Delete template?</DialogTitle>
//             <DialogDescription>
//               "{deleteTarget?.name}" will be permanently removed and can no
//               longer be used in sequences.
//             </DialogDescription>
//           </DialogHeader>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setDeleteTarget(null)}>
//               Cancel
//             </Button>
//             <Button
//               variant="destructive"
//               onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
//               disabled={deleteMut.isPending}
//             >
//               {deleteMut.isPending ? "Deleting…" : "Delete"}
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>
//     </div>
//   );
// }

/**
 * TemplatesPage.tsx — Local email template CRUD.
 *
 * RTE UPGRADE (this version):
 *   - Replaced plain <Textarea> for bodyTemplate with RichTextEditor (Tiptap WYSIWYG).
 *   - Variable insertion chips moved inside RichTextEditor toolbar via the `variables`
 *     prop — removed the separate "Insert variable" chip section from the form.
 *   - openEdit() wraps legacy plain-text bodies in ensureHtml() so they load cleanly.
 *   - Card body preview uses stripHtml() — raw <p> tags no longer visible.
 *   - Preview dialog renders the bodyTemplate as HTML instead of in a <pre>.
 *
 * Original gaps retained unchanged:
 *   TM-1  MailBridge connection warning
 *   TM-2  Template list from real API
 *   TM-3  Create / Edit dialog (now with WYSIWYG body)
 *   TM-4  Preview template with sample variable substitution
 *   TM-5  Delete template
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  BookOpen,
  Edit3,
  Eye,
  LayoutTemplate,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { formatDate, truncate } from "@/lib/utils";
import { ensureHtml, stripHtml } from "@/lib/htmlUtils";
import { RichTextEditor } from "@/components/RichTextEditor";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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

/* ── Types ──────────────────────────────────────────────────────────────── */

interface EmailTemplateResponse {
  id: string;
  name: string;
  category: string;
  framework: string | null;
  subjectTemplate: string | null;
  bodyTemplate: string;
  variables: string[];
  isShared: boolean;
  createdAt: string;
  updatedAt: string;
}

interface MailBridgeConfig {
  id: string;
  name: string;
  baseUrl: string;
  isActive: boolean;
}

/* ── Constants ──────────────────────────────────────────────────────────── */

const CATEGORIES = [
  { id: "cold_outreach", label: "Cold Outreach" },
  { id: "follow_up", label: "Follow-up" },
  { id: "breakup", label: "Breakup" },
  { id: "value", label: "Value Touch" },
  { id: "invitation", label: "Meeting Invitation" },
  { id: "general", label: "General" },
] as const;

const CATEGORY_COLORS: Record<string, string> = {
  cold_outreach: "bg-blue-100 text-blue-700 border-blue-200",
  follow_up: "bg-violet-100 text-violet-700 border-violet-200",
  breakup: "bg-rose-100 text-rose-700 border-rose-200",
  value: "bg-emerald-100 text-emerald-700 border-emerald-200",
  invitation: "bg-amber-100 text-amber-700 border-amber-200",
  general: "bg-slate-100 text-slate-700 border-slate-200",
};

/**
 * Jinja2 variables available in OUTRENA templates.
 * Passed to RichTextEditor as insertion chips — clicking inserts at cursor.
 */
const JINJA_VARIABLES = [
  "{{ first_name }}",
  "{{ last_name }}",
  "{{ company }}",
  "{{ title }}",
  "{{ signal }}",
  "{{ sender_name }}",
  "{{ sender_company }}",
  "{{ result_metric }}",
];

/* ── Form state ─────────────────────────────────────────────────────────── */

interface TemplateForm {
  id?: string;
  name: string;
  category: string;
  subjectTemplate: string;
  bodyTemplate: string; // stored as HTML after RTE upgrade
}

const EMPTY_FORM: TemplateForm = {
  name: "",
  category: "cold_outreach",
  subjectTemplate: "",
  bodyTemplate: "",
};

/* ── Preview helper ─────────────────────────────────────────────────────── */

const SAMPLE_VARS: Record<string, string> = {
  first_name: "Jordan",
  last_name: "Avery",
  company: "Acme Corp",
  title: "VP Revenue",
  signal: "raised Series B",
  sender_name: "Alex",
  sender_company: "OUTRENA",
  result_metric: "60% faster close",
};

/**
 * Substitute Jinja2 tokens in the template (plain-text or HTML).
 * Works on HTML bodies: {{ var }} tokens are text nodes inside elements.
 */
function applyPreview(template: string): string {
  return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key: string) =>
    SAMPLE_VARS[key] ?? `{{ ${key} }}`
  );
}

/* ── Page ───────────────────────────────────────────────────────────────── */

export function TemplatesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [editorOpen, setEditorOpen] = useState(false);
  const [previewTarget, setPreviewTarget] =
    useState<EmailTemplateResponse | null>(null);
  const [deleteTarget, setDeleteTarget] =
    useState<EmailTemplateResponse | null>(null);
  const [form, setForm] = useState<TemplateForm>(EMPTY_FORM);

  /* ── Queries ── */

  // TM-1 — check if MailBridge is configured
  const { data: mbConfigs = [] } = useQuery<MailBridgeConfig[]>({
    queryKey: ["mailbridge-config"],
    queryFn: () => http.get<MailBridgeConfig[]>("/api/v1/mailbridge/config"),
    retry: false,
  });

  const hasMailBridge = mbConfigs.some((c) => c.isActive);

  // TM-2 — template list from real API
  const { data: templates = [], isLoading } = useQuery<
    EmailTemplateResponse[]
  >({
    queryKey: ["templates"],
    queryFn: () =>
      http.get<EmailTemplateResponse[]>("/api/v1/templates"),
    retry: false,
  });

  /* ── Mutations ── */

  const createMut = useMutation({
    mutationFn: (body: Omit<TemplateForm, "id">) =>
      http.post<EmailTemplateResponse>("/api/v1/templates", body),
    onSuccess: () => {
      toast.success("Template created");
      qc.invalidateQueries({ queryKey: ["templates"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to create template"),
  });

  const updateMut = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: Omit<TemplateForm, "id">;
    }) =>
      http.put<EmailTemplateResponse>(`/api/v1/templates/${id}`, body),
    onSuccess: () => {
      toast.success("Template saved");
      qc.invalidateQueries({ queryKey: ["templates"] });
      closeEditor();
    },
    onError: () => toast.error("Failed to save template"),
  });

  // TM-5 — delete
  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/templates/${id}`),
    onSuccess: () => {
      toast.success("Template deleted");
      qc.invalidateQueries({ queryKey: ["templates"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete template"),
  });

  /* ── Handlers ── */

  function openNew() {
    setForm(EMPTY_FORM);
    setEditorOpen(true);
  }

  function openEdit(t: EmailTemplateResponse) {
    setForm({
      id: t.id,
      name: t.name,
      category: t.category,
      subjectTemplate: t.subjectTemplate ?? "",
      // ensureHtml converts legacy plain-text bodies to <p> paragraphs so
      // they load cleanly into Tiptap. Bodies already stored as HTML pass through.
      bodyTemplate: ensureHtml(t.bodyTemplate),
    });
    setEditorOpen(true);
  }

  function closeEditor() {
    setEditorOpen(false);
    setForm(EMPTY_FORM);
  }

  function handleSave() {
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    // Extract which Jinja2 variables are present in the HTML body.
    // Strip tags first so {{ var }} tokens in HTML attributes aren't missed.
    const bodyText = stripHtml(form.bodyTemplate);
    const payload = {
      name: form.name.trim(),
      category: form.category,
      subjectTemplate: form.subjectTemplate.trim(),
      bodyTemplate: form.bodyTemplate,
      variables: JINJA_VARIABLES.filter((v) =>
        bodyText.includes(v.replace(/\s/g, ""))
      ).map((v) => v.replace(/\{\{\s*|\s*\}\}/g, "")),
      isShared: true,
    };
    if (form.id) {
      updateMut.mutate({ id: form.id, body: payload });
    } else {
      createMut.mutate(payload);
    }
  }

  /* ── Filter ── */

  const filtered = templates.filter((t) => {
    const matchSearch =
      !search || t.name.toLowerCase().includes(search.toLowerCase());
    const matchCat =
      categoryFilter === "all" || t.category === categoryFilter;
    return matchSearch && matchCat;
  });

  const isSaving = createMut.isPending || updateMut.isPending;

  /* ── Render ── */

  return (
    <div className="space-y-6">
      <PageHeader
        title="Templates"
        description="Reusable email templates with Jinja2 variable substitution — rich text, sent as HTML by MailBridge."
        actions={
          <Button size="sm" onClick={openNew}>
            <Plus className="h-4 w-4" /> New Template
          </Button>
        }
      />

      {/* TM-1 — MailBridge warning */}
      {!hasMailBridge && (
        <Alert variant="default" className="border-amber-300 bg-amber-50">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <AlertTitle className="text-amber-800">
            No active MailBridge connection
          </AlertTitle>
          <AlertDescription className="text-amber-700">
            Templates are stored locally and can be used in Sequences. To send
            via MailBridge, configure a connection in{" "}
            <a
              href="/setup/domains"
              className="underline font-medium hover:no-underline"
            >
              Domains → MailBridge
            </a>
            .
          </AlertDescription>
        </Alert>
      )}

      {/* Info card */}
      <Card className="border-blue-100 bg-blue-50/50">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <BookOpen className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
            <div className="text-xs space-y-1">
              <p className="font-medium text-blue-900">
                Jinja2 Template Syntax — Rich Text
              </p>
              <p className="text-blue-800">
                Use{" "}
                <code className="bg-blue-100 px-1 rounded">
                  {"{{ first_name }}"}
                </code>
                ,{" "}
                <code className="bg-blue-100 px-1 rounded">
                  {"{{ company }}"}
                </code>
                , and{" "}
                <code className="bg-blue-100 px-1 rounded">
                  {"{{ signal }}"}
                </code>{" "}
                for personalisation. Click variable chips in the editor toolbar
                to insert at cursor. The body is sent as HTML email by
                MailBridge.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search templates…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {CATEGORIES.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            qc.invalidateQueries({ queryKey: ["templates"] })
          }
        >
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* TM-2 — Template grid */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={<LayoutTemplate className="h-10 w-10" />}
              title={
                templates.length > 0
                  ? "No templates match your filters"
                  : "No templates yet"
              }
              description={
                templates.length > 0
                  ? "Try adjusting the search or category filter."
                  : 'Click "New Template" to create your first one.'
              }
              action={
                templates.length === 0 ? (
                  <Button size="sm" onClick={openNew}>
                    <Plus className="h-4 w-4" /> New Template
                  </Button>
                ) : undefined
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((t) => (
            <Card
              key={t.id}
              className="flex flex-col hover:shadow-md transition-shadow"
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-base truncate">
                      {t.name}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      <Badge
                        variant="outline"
                        className={`text-xs border ${
                          CATEGORY_COLORS[t.category] ??
                          CATEGORY_COLORS.general
                        }`}
                      >
                        {CATEGORIES.find((c) => c.id === t.category)?.label ??
                          t.category}
                      </Badge>
                    </CardDescription>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    {/* TM-4 — Preview */}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => setPreviewTarget(t)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => openEdit(t)}
                    >
                      <Edit3 className="h-4 w-4" />
                    </Button>
                    {/* TM-5 — Delete */}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive"
                      onClick={() => setDeleteTarget(t)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-2">
                {t.subjectTemplate && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Subject
                    </p>
                    <p className="text-sm truncate">{t.subjectTemplate}</p>
                  </div>
                )}
                <div className="flex-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Body preview
                  </p>
                  {/* stripHtml prevents raw <p>/<strong> tags appearing in the card */}
                  <p className="mt-1 text-sm text-muted-foreground line-clamp-3">
                    {truncate(stripHtml(t.bodyTemplate), 120)}
                  </p>
                </div>
                <p className="text-xs text-muted-foreground">
                  Updated {formatDate(t.updatedAt)}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* TM-3 — Create / Edit dialog */}
      <Dialog open={editorOpen} onOpenChange={(o) => !o && closeEditor()}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {form.id ? "Edit Template" : "New Template"}
            </DialogTitle>
            <DialogDescription>
              Use{" "}
              <code className="bg-muted px-1 rounded text-xs">
                {"{{ variable_name }}"}
              </code>{" "}
              syntax for personalisation. Click variable chips in the editor
              toolbar to insert at the cursor position.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="tpl-name">Name *</Label>
                <Input
                  id="tpl-name"
                  value={form.name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, name: e.target.value }))
                  }
                  placeholder="e.g. Cold First Touch — Trigger"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Category</Label>
                <Select
                  value={form.category}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, category: v }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tpl-subject">Subject line</Label>
              <Input
                id="tpl-subject"
                value={form.subjectTemplate}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    subjectTemplate: e.target.value,
                  }))
                }
                placeholder="e.g. {{ company }}'s close-cycle SLA — late again?"
              />
            </div>
            {/*
              Body — WYSIWYG HTML editor.
              Variable chips ({{ first_name }}, etc.) are rendered inside the
              RichTextEditor toolbar via the `variables` prop. Clicking a chip
              inserts the token at the cursor position. The body is stored as
              HTML and sent as text/html by MailBridge.

              The separate "Insert variable" chip section that existed in the
              old plain-text form has been removed — it is now part of the editor.
            */}
            <div className="space-y-1.5">
              <Label htmlFor="tpl-body">
                Body{" "}
                <span className="font-normal text-muted-foreground">
                  — rich text, sent as HTML email
                </span>
              </Label>
              <RichTextEditor
                value={form.bodyTemplate}
                onChange={(html) =>
                  setForm((f) => ({ ...f, bodyTemplate: html }))
                }
                placeholder={
                  "Hi {{ first_name }},\n\nNoticed {{ company }} just {{ signal }}…\n\nBest,\n{{ sender_name }}"
                }
                minHeight={300}
                variables={JINJA_VARIABLES}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeEditor}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isSaving || !form.name.trim()}
            >
              {isSaving
                ? "Saving…"
                : form.id
                ? "Save Changes"
                : "Create Template"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* TM-4 — Preview dialog */}
      <Dialog
        open={Boolean(previewTarget)}
        onOpenChange={(o) => !o && setPreviewTarget(null)}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Preview — {previewTarget?.name}</DialogTitle>
            <DialogDescription>
              Sample variables applied:{" "}
              {Object.entries(SAMPLE_VARS)
                .slice(0, 3)
                .map(([k, v]) => `${k}="${v}"`)
                .join(", ")}
              …
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {previewTarget?.subjectTemplate && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
                  Subject
                </p>
                <p className="text-sm font-medium">
                  {applyPreview(previewTarget.subjectTemplate)}
                </p>
              </div>
            )}
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
                Body
              </p>
              {/* Render as HTML when the body is from the RTE, plain text otherwise */}
              <div className="rounded-md border bg-muted/30 p-3 max-h-72 overflow-y-auto">
                {previewTarget && /^<[a-zA-Z]/.test((previewTarget.bodyTemplate ?? "").trim()) ? (
                  <div
                    className="text-sm leading-relaxed prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{
                      __html: applyPreview(previewTarget.bodyTemplate),
                    }}
                  />
                ) : (
                  <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed">
                    {applyPreview(previewTarget?.bodyTemplate ?? "")}
                  </pre>
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPreviewTarget(null)}
            >
              Close
            </Button>
            {previewTarget && (
              <Button
                onClick={() => {
                  setPreviewTarget(null);
                  openEdit(previewTarget);
                }}
              >
                <Edit3 className="h-4 w-4" /> Edit
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* TM-5 — Delete dialog */}
      <Dialog
        open={Boolean(deleteTarget)}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete template?</DialogTitle>
            <DialogDescription>
              "{deleteTarget?.name}" will be permanently removed and can no
              longer be used in sequences.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() =>
                deleteTarget && deleteMut.mutate(deleteTarget.id)
              }
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
