
// import { useState } from "react";
// import type { FormEvent } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   Plus,
//   Trash2,
//   Star,
//   TestTube2,
//   Loader2,
//   Cloud,
//   Cpu,
//   Bot,
//   Pencil,
//   AlertTriangle,
// } from "lucide-react";
// import { toast } from "sonner";
// import { http } from "@/services/apiClient";
// import { PageHeader } from "@/components/ui/page-header";
// import { Button } from "@/components/ui/button";
// import {
//   Card,
//   CardContent,
//   CardDescription,
//   CardHeader,
//   CardTitle,
// } from "@/components/ui/card";
// import { Badge } from "@/components/ui/badge";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { NativeSelect as Select } from "@/components/ui/select";
// import { Switch } from "@/components/ui/switch";
// import { Skeleton } from "@/components/ui/skeleton";
// import {
//   Dialog,
//   DialogContent,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
//   DialogTrigger,
// } from "@/components/ui/dialog";
// import { EmptyState } from "@/components/ui/empty-state";
// import { formatDateTime } from "@/lib/utils";

// /* ── Provider catalog (verbatim from the Next.js reference's shared providers.ts) ── */

// interface ProviderMeta {
//   id: string;
//   name: string;
//   models: string[];
// }

// const PROVIDERS: ProviderMeta[] = [
//   { id: "openai", name: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini", "o4-mini"] },
//   { id: "anthropic", name: "Anthropic", models: ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-opus-4-20250514"] },
//   { id: "google", name: "Google AI", models: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"] },
//   { id: "deepseek", name: "DeepSeek", models: ["deepseek-chat", "deepseek-reasoner"] },
//   { id: "groq", name: "Groq", models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"] },
//   { id: "mistral", name: "Mistral AI", models: ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"] },
//   { id: "cohere", name: "Cohere", models: ["command-r-plus", "command-r", "command-a"] },
//   { id: "local", name: "Ollama (Self-Hosted)", models: ["llama3.1", "mistral", "codellama", "phi3:latest", "gemma2", "qwen2.5"] },
//   { id: "azure_openai", name: "Azure OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] },
//   { id: "together", name: "Together AI", models: ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"] },
//   { id: "fireworks", name: "Fireworks AI", models: ["accounts/fireworks/models/llama-v3p3-70b-instruct"] },
//   { id: "perplexity", name: "Perplexity", models: ["sonar-pro", "sonar"] },
//   { id: "openrouter", name: "OpenRouter", models: ["anthropic/claude-sonnet-4", "openai/gpt-4o", "google/gemini-2.5-flash-preview", "deepseek/deepseek-chat"] },
//   { id: "zai", name: "ZAI (Built-in)", models: ["glm-4-plus", "glm-4", "glm-4-flash"] },
// ];

// function providerName(id: string): string {
//   return PROVIDERS.find((p) => p.id === id)?.name ?? id;
// }

// /* ── Types (aligned with LlmConfigResponse / LlmConfigCreate / LlmConfigUpdate) ── */

// interface LlmConfig {
//   id: number;
//   provider: string;
//   display_name: string;
//   api_key: string | null; // always masked by the backend
//   base_url: string | null;
//   model_name: string;
//   max_tokens: number;
//   temperature: number;
//   is_active: boolean;
//   is_default: boolean;
//   created_at: string;
//   updated_at: string;
// }

// interface TestLlmResponse {
//   ok: boolean;
//   content: string;
//   provider?: string;
//   model_id?: string;
//   latency_ms?: number;
//   error?: string;
// }

// interface FormState {
//   provider: string;
//   display_name: string;
//   model_name: string;
//   api_key: string;
//   base_url: string;
//   max_tokens: number;
//   temperature: number;
//   is_active: boolean;
//   is_default: boolean;
// }

// const EMPTY_FORM: FormState = {
//   provider: "openai",
//   display_name: "",
//   model_name: PROVIDERS[0].models[0],
//   api_key: "",
//   base_url: "",
//   max_tokens: 2048,
//   temperature: 0.7,
//   is_active: true,
//   is_default: false,
// };

// function needsBaseUrl(provider: string): boolean {
//   return provider === "local" || provider === "azure_openai";
// }

// function needsApiKey(provider: string): boolean {
//   return provider !== "local" && provider !== "zai";
// }

// function normaliseConfigs(raw: unknown): LlmConfig[] {
//   if (Array.isArray(raw)) return raw as LlmConfig[];
//   if (raw && typeof raw === "object" && "items" in raw)
//     return (raw as { items: LlmConfig[] }).items ?? [];
//   return [];
// }

// /* ── Page ──────────────────────────────────────────────────────────── */

// export function LlmConfigPage() {
//   const queryClient = useQueryClient();
//   const [dialogOpen, setDialogOpen] = useState(false);
//   const [editing, setEditing] = useState<LlmConfig | null>(null);
//   const [form, setForm] = useState<FormState>(EMPTY_FORM);
//   const [testingId, setTestingId] = useState<number | null>(null);
//   const [testResults, setTestResults] = useState<
//     Record<number, { ok: boolean; message: string }>
//   >({});
//   const [deleteTarget, setDeleteTarget] = useState<LlmConfig | null>(null);
//   const [confirmDeactivate, setConfirmDeactivate] = useState(false);

//   const { data, isLoading, isError, refetch } = useQuery({
//     queryKey: ["llm-configs"],
//     queryFn: () =>
//       http.get<unknown>("/api/v1/llm-configs").then(normaliseConfigs),
//   });

//   const configs = data ?? [];
//   const selectedProvider = PROVIDERS.find((p) => p.id === form.provider);

//   const saveMutation = useMutation({
//     mutationFn: (payload: FormState & { id?: number }) => {
//       const { id, ...body } = payload;
//       // Backend LlmConfigCreate derives display_name from provider/model_name
//       // when blank; keep that behavior by omitting an empty display_name.
//       const cleaned = {
//         ...body,
//         display_name: body.display_name.trim() || undefined,
//         api_key: body.api_key || undefined,
//       };
//       if (id) return http.put<LlmConfig>(`/api/v1/llm-configs/${id}`, cleaned);
//       return http.post<LlmConfig>("/api/v1/llm-configs", cleaned);
//     },
//     onSuccess: () => {
//       toast.success(editing ? "Model updated" : "Model added");
//       queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
//       setDialogOpen(false);
//       setForm(EMPTY_FORM);
//       setEditing(null);
//     },
//     onError: () =>
//       toast.error(editing ? "Failed to update model" : "Failed to add model"),
//   });

//   const deleteMutation = useMutation({
//     mutationFn: (id: number) => http.delete(`/api/v1/llm-configs/${id}`),
//     onSuccess: () => {
//       toast.success("Model deactivated");
//       queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
//       setDeleteTarget(null);
//     },
//     onError: () => toast.error("Failed to delete model"),
//   });

//   const setDefaultMutation = useMutation({
//     mutationFn: (id: number) =>
//       http.post<LlmConfig>(`/api/v1/llm-configs/${id}/set-default`, {}),
//     onSuccess: (res) => {
//       toast.success(`${res.display_name} set as default`);
//       queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
//     },
//     onError: () => toast.error("Failed to set default"),
//   });

//   const testMutation = useMutation({
//     mutationFn: (id: number) =>
//       http.post<TestLlmResponse>(`/api/v1/llm-configs/${id}/test`, {}),
//     onSuccess: (res, id) => {
//       setTestResults((prev) => ({
//         ...prev,
//         [id]: {
//           ok: res.ok,
//           message: res.ok
//             ? res.content.slice(0, 100) || "Connected!"
//             : res.error ?? "Connection failed",
//         },
//       }));
//       if (res.ok) {
//         toast.success(
//           `Test passed${res.latency_ms ? ` · ${res.latency_ms}ms` : ""}`,
//         );
//       } else {
//         toast.error(`Test failed${res.error ? ` · ${res.error}` : ""}`);
//       }
//     },
//     onError: () => toast.error("Test request failed"),
//     onSettled: () => setTestingId(null),
//   });

//   function openAdd() {
//     setEditing(null);
//     setForm(EMPTY_FORM);
//     setConfirmDeactivate(false);
//     setDialogOpen(true);
//   }

//   function openEdit(cfg: LlmConfig) {
//     setEditing(cfg);
//     setForm({
//       provider: cfg.provider,
//       display_name: cfg.display_name,
//       model_name: cfg.model_name,
//       api_key: "",
//       base_url: cfg.base_url ?? "",
//       max_tokens: cfg.max_tokens,
//       temperature: cfg.temperature,
//       is_active: cfg.is_active,
//       is_default: cfg.is_default,
//     });
//     setConfirmDeactivate(false);
//     setDialogOpen(true);
//   }

//   function handleSubmit(e: FormEvent) {
//     e.preventDefault();
//     if (!form.model_name.trim()) {
//       toast.error("Model is required");
//       return;
//     }
//     if (editing && editing.is_active && !form.is_active && !confirmDeactivate) {
//       toast.error(
//         "Confirm deactivation below — this will hide the model from the list.",
//       );
//       return;
//     }
//     saveMutation.mutate(editing ? { ...form, id: editing.id } : form);
//   }

//   function handleTest(id: number) {
//     setTestingId(id);
//     testMutation.mutate(id);
//   }

//   return (
//     <div className="space-y-6 p-6">
//       <PageHeader
//         title="LLM Models"
//         description="Configure the language models used for email generation, ICP scoring, and reply drafting."
//         actions={
//           <Dialog
//             open={dialogOpen}
//             onOpenChange={(o) => {
//               setDialogOpen(o);
//               if (!o) {
//                 setForm(EMPTY_FORM);
//                 setEditing(null);
//               }
//             }}
//           >
//             <DialogTrigger asChild>
//               <Button onClick={openAdd}>
//                 <Plus className="h-4 w-4" />
//                 Add Model
//               </Button>
//             </DialogTrigger>
//             <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
//               <DialogHeader>
//                 <DialogTitle>{editing ? "Edit Model" : "Add LLM Model"}</DialogTitle>
//                 <DialogDescription>
//                   Configure credentials and routing for a language model
//                   provider.
//                 </DialogDescription>
//               </DialogHeader>
//               <form onSubmit={handleSubmit} className="space-y-4">
//                 <div className="space-y-2">
//                   <Label htmlFor="provider">Provider</Label>
//                   <Select
//                     id="provider"
//                     value={form.provider}
//                     onChange={(e) => {
//                       const nextProvider = e.target.value;
//                       const nextModels =
//                         PROVIDERS.find((p) => p.id === nextProvider)?.models ?? [];
//                       setForm((f) => ({
//                         ...f,
//                         provider: nextProvider,
//                         model_name: nextModels[0] ?? "",
//                       }));
//                     }}
//                   >
//                     {PROVIDERS.map((p) => (
//                       <option key={p.id} value={p.id}>
//                         {p.name}
//                       </option>
//                     ))}
//                   </Select>
//                 </div>

//                 <div className="space-y-2">
//                   <Label htmlFor="display_name">Display Name</Label>
//                   <Input
//                     id="display_name"
//                     placeholder={`e.g. ${providerName(form.provider)} Production`}
//                     value={form.display_name}
//                     onChange={(e) =>
//                       setForm((f) => ({ ...f, display_name: e.target.value }))
//                     }
//                   />
//                   <p className="text-[11px] text-muted-foreground">
//                     Leave blank to auto-generate from provider + model.
//                   </p>
//                 </div>

//                 <div className="space-y-2">
//                   <Label htmlFor="model_name">Model</Label>
//                   {selectedProvider && selectedProvider.models.length > 0 ? (
//                     <Select
//                       id="model_name"
//                       value={form.model_name}
//                       onChange={(e) =>
//                         setForm((f) => ({ ...f, model_name: e.target.value }))
//                       }
//                     >
//                       {selectedProvider.models.map((m) => (
//                         <option key={m} value={m}>
//                           {m}
//                         </option>
//                       ))}
//                     </Select>
//                   ) : (
//                     <Input
//                       id="model_name"
//                       placeholder="Enter model ID"
//                       value={form.model_name}
//                       onChange={(e) =>
//                         setForm((f) => ({ ...f, model_name: e.target.value }))
//                       }
//                     />
//                   )}
//                 </div>

//                 {needsApiKey(form.provider) && (
//                   <div className="space-y-2">
//                     <Label htmlFor="api_key">
//                       API Key{" "}
//                       {editing && (
//                         <span className="text-muted-foreground font-normal">
//                           (leave blank to keep existing)
//                         </span>
//                       )}
//                     </Label>
//                     <Input
//                       id="api_key"
//                       type="password"
//                       placeholder="sk-..."
//                       value={form.api_key}
//                       onChange={(e) =>
//                         setForm((f) => ({ ...f, api_key: e.target.value }))
//                       }
//                       required={!editing}
//                     />
//                   </div>
//                 )}

//                 {needsBaseUrl(form.provider) && (
//                   <div className="space-y-2">
//                     <Label htmlFor="base_url">Base URL</Label>
//                     <Input
//                       id="base_url"
//                       placeholder={
//                         form.provider === "local"
//                           ? "http://localhost:11434"
//                           : "https://your-resource.openai.azure.com/openai/deployments/..."
//                       }
//                       value={form.base_url}
//                       onChange={(e) =>
//                         setForm((f) => ({ ...f, base_url: e.target.value }))
//                       }
//                     />
//                   </div>
//                 )}

//                 <div className="grid grid-cols-2 gap-4">
//                   <div className="space-y-2">
//                     <Label htmlFor="temperature">
//                       Temperature: {form.temperature}
//                     </Label>
//                     <Input
//                       id="temperature"
//                       type="range"
//                       min={0}
//                       max={2}
//                       step={0.1}
//                       value={form.temperature}
//                       onChange={(e) =>
//                         setForm((f) => ({
//                           ...f,
//                           temperature: parseFloat(e.target.value),
//                         }))
//                       }
//                       className="h-2"
//                     />
//                   </div>
//                   <div className="space-y-2">
//                     <Label htmlFor="max_tokens">Max Tokens</Label>
//                     <Input
//                       id="max_tokens"
//                       type="number"
//                       value={form.max_tokens}
//                       onChange={(e) =>
//                         setForm((f) => ({
//                           ...f,
//                           max_tokens: parseInt(e.target.value, 10) || 2048,
//                         }))
//                       }
//                     />
//                   </div>
//                 </div>

//                 <div className="flex items-center justify-between rounded-md border p-3">
//                   <div className="flex items-center gap-2">
//                     <Switch
//                       checked={form.is_default}
//                       onCheckedChange={(c) =>
//                         setForm((f) => ({ ...f, is_default: c }))
//                       }
//                     />
//                     <Label>Set as default</Label>
//                   </div>
//                   <div className="flex items-center gap-2">
//                     <Switch
//                       checked={form.is_active}
//                       onCheckedChange={(c) => {
//                         setForm((f) => ({ ...f, is_active: c }));
//                         setConfirmDeactivate(false);
//                       }}
//                     />
//                     <Label>Active</Label>
//                   </div>
//                 </div>

//                 {editing?.is_active && !form.is_active && (
//                   <div className="rounded-md border border-amber-300 bg-amber-50 p-3 space-y-2">
//                     <p className="text-xs text-amber-900 flex items-start gap-1.5">
//                       <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
//                       This list only shows active models. Deactivating will
//                       remove "{editing.display_name}" from view immediately —
//                       there is currently no way to browse or re-enable
//                       inactive models from this page.
//                     </p>
//                     <label className="flex items-center gap-2 text-xs text-amber-900">
//                       <input
//                         type="checkbox"
//                         checked={confirmDeactivate}
//                         onChange={(e) => setConfirmDeactivate(e.target.checked)}
//                       />
//                       I understand, deactivate this model
//                     </label>
//                   </div>
//                 )}

//                 <DialogFooter>
//                   <Button
//                     type="button"
//                     variant="outline"
//                     onClick={() => setDialogOpen(false)}
//                   >
//                     Cancel
//                   </Button>
//                   <Button type="submit" disabled={saveMutation.isPending}>
//                     {saveMutation.isPending ? (
//                       <Loader2 className="h-3.5 w-3.5 animate-spin" />
//                     ) : null}
//                     {editing ? "Save changes" : "Add model"}
//                   </Button>
//                 </DialogFooter>
//               </form>
//             </DialogContent>
//           </Dialog>
//         }
//       />

//       {isError ? (
//         <Card className="mt-6">
//           <CardContent className="py-12 text-center">
//             <p className="text-muted-foreground">
//               Failed to load LLM models. Please try again.
//             </p>
//             <Button onClick={() => refetch()} className="mt-4">
//               Retry
//             </Button>
//           </CardContent>
//         </Card>
//       ) : isLoading ? (
//         <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
//           {[0, 1, 2].map((i) => (
//             <Skeleton key={i} className="h-40 w-full" />
//           ))}
//         </div>
//       ) : configs.length === 0 ? (
//         <EmptyState
//           icon={<Bot className="h-6 w-6" />}
//           title="No LLM Models Configured"
//           description="Add your first AI model to start generating personalized outreach emails."
//           action={
//             <Button onClick={openAdd}>
//               <Plus className="h-4 w-4" />
//               Add Model
//             </Button>
//           }
//         />
//       ) : (
//         <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
//           {configs.map((cfg) => {
//             const result = testResults[cfg.id];
//             return (
//               <Card key={cfg.id} className={!cfg.is_active ? "opacity-60" : ""}>
//                 <CardHeader className="pb-3">
//                   <div className="flex items-center justify-between">
//                     <div className="flex items-center gap-2">
//                       {cfg.provider === "local" ? (
//                         <Cpu className="h-4 w-4 text-muted-foreground" />
//                       ) : (
//                         <Cloud className="h-4 w-4 text-muted-foreground" />
//                       )}
//                       <CardTitle className="text-sm">
//                         {cfg.display_name}
//                       </CardTitle>
//                     </div>
//                     {cfg.is_default && (
//                       <Badge variant="default" className="text-xs">
//                         Default
//                       </Badge>
//                     )}
//                   </div>
//                   <CardDescription className="text-xs">
//                     {providerName(cfg.provider)} — {cfg.model_name}
//                   </CardDescription>
//                 </CardHeader>
//                 <CardContent className="space-y-3">
//                   <div className="flex items-center gap-2">
//                     <div
//                       className={`h-2 w-2 rounded-full ${
//                         cfg.is_active ? "bg-emerald-500" : "bg-gray-300"
//                       }`}
//                     />
//                     <span className="text-xs text-muted-foreground">
//                       {cfg.is_active ? "Active" : "Inactive"}
//                     </span>
//                     {cfg.api_key && (
//                       <span className="text-xs font-mono text-muted-foreground ml-auto">
//                         {cfg.api_key}
//                       </span>
//                     )}
//                   </div>
//                   {cfg.base_url && (
//                     <p className="text-xs text-muted-foreground truncate">
//                       {cfg.base_url}
//                     </p>
//                   )}
//                   <p className="text-[11px] text-muted-foreground">
//                     Updated {formatDateTime(cfg.updated_at)}
//                   </p>

//                   {result && (
//                     <div
//                       className={`text-xs p-2 rounded ${
//                         result.ok
//                           ? "bg-emerald-50 text-emerald-700"
//                           : "bg-red-50 text-red-700"
//                       }`}
//                     >
//                       {result.message}
//                     </div>
//                   )}

//                   <div className="flex gap-2">
//                     <Button
//                       size="sm"
//                       variant="outline"
//                       className="flex-1"
//                       onClick={() => handleTest(cfg.id)}
//                       disabled={testingId === cfg.id}
//                     >
//                       {testingId === cfg.id ? (
//                         <Loader2 className="h-3 w-3 animate-spin" />
//                       ) : (
//                         <TestTube2 className="h-3 w-3" />
//                       )}
//                       Test
//                     </Button>
//                     {!cfg.is_default && (
//                       <Button
//                         size="sm"
//                         variant="outline"
//                         onClick={() => setDefaultMutation.mutate(cfg.id)}
//                         disabled={setDefaultMutation.isPending}
//                         title="Set as default LLM model"
//                       >
//                         <Star className="h-3 w-3" />
//                       </Button>
//                     )}
//                     <Button
//                       size="sm"
//                       variant="outline"
//                       onClick={() => openEdit(cfg)}
//                       title="Edit"
//                     >
//                       <Pencil className="h-3 w-3" />
//                     </Button>
//                     <Button
//                       size="sm"
//                       variant="ghost"
//                       className="text-destructive"
//                       onClick={() => setDeleteTarget(cfg)}
//                       title="Delete"
//                     >
//                       <Trash2 className="h-3 w-3" />
//                     </Button>
//                   </div>
//                 </CardContent>
//               </Card>
//             );
//           })}
//         </div>
//       )}

//       {/* Delete confirmation dialog */}
//       <Dialog
//         open={!!deleteTarget}
//         onOpenChange={(o) => !o && setDeleteTarget(null)}
//       >
//         <DialogContent>
//           <DialogHeader>
//             <DialogTitle>Delete LLM model?</DialogTitle>
//             <DialogDescription>
//               {deleteTarget
//                 ? `"${deleteTarget.display_name}" (${providerName(deleteTarget.provider)}) will be deactivated. This is a soft-delete — the row is kept for audit but will no longer appear in this list or be usable for generation, and cannot be restored from this page.`
//                 : "This LLM model will be deactivated. This action cannot be undone from this page."}
//             </DialogDescription>
//           </DialogHeader>
//           <DialogFooter>
//             <Button variant="outline" onClick={() => setDeleteTarget(null)}>
//               Cancel
//             </Button>
//             <Button
//               variant="destructive"
//               onClick={() =>
//                 deleteTarget && deleteMutation.mutate(deleteTarget.id)
//               }
//               disabled={deleteMutation.isPending}
//             >
//               {deleteMutation.isPending ? "Deactivating…" : "Delete"}
//             </Button>
//           </DialogFooter>
//         </DialogContent>
//       </Dialog>
//     </div>
//   );
// }

import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  Star,
  TestTube2,
  Loader2,
  Cloud,
  Cpu,
  Bot,
  Pencil,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { PageHeader } from "@/components/ui/page-header";
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
import { NativeSelect as Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime } from "@/lib/utils";
 
/* ── Provider catalog (verbatim from the Next.js reference's shared providers.ts) ── */
 
interface ProviderMeta {
  id: string;
  name: string;
  models: string[];
}
 
const PROVIDERS: ProviderMeta[] = [
  { id: "openai", name: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini", "o4-mini"] },
  { id: "anthropic", name: "Anthropic", models: ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-opus-4-20250514"] },
  { id: "google", name: "Google AI", models: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"] },
  { id: "deepseek", name: "DeepSeek", models: ["deepseek-chat", "deepseek-reasoner"] },
  // { id: "groq", name: "Groq", models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768","openai/gpt-oss-120b","openai/gpt-oss-20b"] },
  { id: "groq", name: "Groq", models: ["llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768", "gemma2-9b-it", "llama-3.1-8b-instant", "llama-3.3-70b-versatile","openai/gpt-oss-120b","openai/gpt-oss-20b"] },
  { id: "mistral", name: "Mistral AI", models: ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"] },
  { id: "cohere", name: "Cohere", models: ["command-r-plus", "command-r", "command-a"] },
  { id: "local", name: "Ollama (Self-Hosted)", models: ["llama3.1", "mistral", "codellama", "phi3:latest", "gemma2", "qwen2.5"] },
  { id: "azure_openai", name: "Azure OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] },
  { id: "together", name: "Together AI", models: ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"] },
  { id: "fireworks", name: "Fireworks AI", models: ["accounts/fireworks/models/llama-v3p3-70b-instruct"] },
  { id: "perplexity", name: "Perplexity", models: ["sonar-pro", "sonar"] },
  { id: "openrouter", name: "OpenRouter", models: ["anthropic/claude-sonnet-4", "openai/gpt-4o", "google/gemini-2.5-flash-preview", "deepseek/deepseek-chat"] },
  { id: "zai", name: "ZAI (Built-in)", models: ["glm-4-plus", "glm-4", "glm-4-flash"] },
];
 
function providerName(id: string): string {
  return PROVIDERS.find((p) => p.id === id)?.name ?? id;
}
 
/* ── Types (aligned with LlmConfigResponse / LlmConfigCreate / LlmConfigUpdate) ── */
 
interface LlmConfig {
  id: string;
  provider: string;
  display_name: string;
  api_key: string | null; // always masked by the backend
  base_url: string | null;
  model_name: string;
  max_tokens: number;
  temperature: number;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}
 
interface TestLlmResponse {
  ok: boolean;
  content: string;
  provider?: string;
  model_id?: string;
  latency_ms?: number;
  error?: string;
}
 
interface FormState {
  provider: string;
  display_name: string;
  model_name: string;
  api_key: string;
  base_url: string;
  max_tokens: number;
  temperature: number;
  is_active: boolean;
  is_default: boolean;
}
 
const EMPTY_FORM: FormState = {
  provider: "openai",
  display_name: "",
  model_name: PROVIDERS[0].models[0],
  api_key: "",
  base_url: "",
  max_tokens: 2048,
  temperature: 0.7,
  is_active: true,
  is_default: false,
};
 
function needsBaseUrl(provider: string): boolean {
  return provider === "local" || provider === "azure_openai";
}
 
function needsApiKey(provider: string): boolean {
  return provider !== "local" && provider !== "zai";
}
 
function normaliseConfigs(raw: unknown): LlmConfig[] {
  if (Array.isArray(raw)) return raw as LlmConfig[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: LlmConfig[] }).items ?? [];
  return [];
}
 
/* ── Page ──────────────────────────────────────────────────────────── */
 
export function LlmConfigPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<LlmConfig | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, { ok: boolean; message: string }>
  >({});
  const [deleteTarget, setDeleteTarget] = useState<LlmConfig | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
 
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["llm-configs"],
    queryFn: () =>
      http.get<unknown>("/api/v1/llm-configs").then(normaliseConfigs),
  });
 
  const configs = data ?? [];
  const selectedProvider = PROVIDERS.find((p) => p.id === form.provider);
 
  const saveMutation = useMutation({
    mutationFn: (payload: FormState & { id?: string }) => {
      const { id, ...body } = payload;
      // Backend LlmConfigCreate derives display_name from provider/model_name
      // when blank; keep that behavior by omitting an empty display_name.
      const cleaned = {
        ...body,
        display_name: body.display_name.trim() || undefined,
        api_key: body.api_key || undefined,
      };
      if (id) return http.put<LlmConfig>(`/api/v1/llm-configs/${id}`, cleaned);
      return http.post<LlmConfig>("/api/v1/llm-configs", cleaned);
    },
    onSuccess: () => {
      toast.success(editing ? "Model updated" : "Model added");
      queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setEditing(null);
    },
    onError: () =>
      toast.error(editing ? "Failed to update model" : "Failed to add model"),
  });
 
  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/llm-configs/${id}`),
    onSuccess: () => {
      toast.success("Model deactivated");
      queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete model"),
  });
 
  const setDefaultMutation = useMutation({
    mutationFn: (id: string) =>
      http.post<LlmConfig>(`/api/v1/llm-configs/${id}/set-default`, {}),
    onSuccess: (res) => {
      toast.success(`${res.display_name} set as default`);
      queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
    },
    onError: () => toast.error("Failed to set default"),
  });
 
  const testMutation = useMutation({
    mutationFn: (id: string) =>
      http.post<TestLlmResponse>(`/api/v1/llm-configs/${id}/test`, {}),
    onSuccess: (res, id) => {
      setTestResults((prev) => ({
        ...prev,
        [id]: {
          ok: res.ok,
          message: res.ok
            ? res.content.slice(0, 100) || "Connected!"
            : res.error ?? "Connection failed",
        },
      }));
      if (res.ok) {
        toast.success(
          `Test passed${res.latency_ms ? ` · ${res.latency_ms}ms` : ""}`,
        );
      } else {
        toast.error(`Test failed${res.error ? ` · ${res.error}` : ""}`);
      }
    },
    onError: () => toast.error("Test request failed"),
    onSettled: () => setTestingId(null),
  });
 
  function openAdd() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setConfirmDeactivate(false);
    setDialogOpen(true);
  }
 
  function openEdit(cfg: LlmConfig) {
    setEditing(cfg);
    setForm({
      provider: cfg.provider,
      display_name: cfg.display_name,
      model_name: cfg.model_name,
      api_key: "",
      base_url: cfg.base_url ?? "",
      max_tokens: cfg.max_tokens,
      temperature: cfg.temperature,
      is_active: cfg.is_active,
      is_default: cfg.is_default,
    });
    setConfirmDeactivate(false);
    setDialogOpen(true);
  }
 
  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.model_name.trim()) {
      toast.error("Model is required");
      return;
    }
    if (editing && editing.is_active && !form.is_active && !confirmDeactivate) {
      toast.error(
        "Confirm deactivation below — this will hide the model from the list.",
      );
      return;
    }
    saveMutation.mutate(editing ? { ...form, id: editing.id } : form);
  }
 
  function handleTest(id: string) {
    setTestingId(id);
    testMutation.mutate(id);
  }
 
  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="LLM Models"
        description="Configure the language models used for email generation, ICP scoring, and reply drafting."
        actions={
          <Dialog
            open={dialogOpen}
            onOpenChange={(o) => {
              setDialogOpen(o);
              if (!o) {
                setForm(EMPTY_FORM);
                setEditing(null);
              }
            }}
          >
            <DialogTrigger asChild>
              <Button onClick={openAdd}>
                <Plus className="h-4 w-4" />
                Add Model
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>{editing ? "Edit Model" : "Add LLM Model"}</DialogTitle>
                <DialogDescription>
                  Configure credentials and routing for a language model
                  provider.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="provider">Provider</Label>
                  <Select
                    id="provider"
                    value={form.provider}
                    onChange={(e) => {
                      const nextProvider = e.target.value;
                      const nextModels =
                        PROVIDERS.find((p) => p.id === nextProvider)?.models ?? [];
                      setForm((f) => ({
                        ...f,
                        provider: nextProvider,
                        model_name: nextModels[0] ?? "",
                      }));
                    }}
                  >
                    {PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </Select>
                </div>
 
                <div className="space-y-2">
                  <Label htmlFor="display_name">Display Name</Label>
                  <Input
                    id="display_name"
                    placeholder={`e.g. ${providerName(form.provider)} Production`}
                    value={form.display_name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, display_name: e.target.value }))
                    }
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Leave blank to auto-generate from provider + model.
                  </p>
                </div>
 
                <div className="space-y-2">
                  <Label htmlFor="model_name">Model</Label>
                  {selectedProvider && selectedProvider.models.length > 0 ? (
                    <Select
                      id="model_name"
                      value={form.model_name}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, model_name: e.target.value }))
                      }
                    >
                      {selectedProvider.models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <Input
                      id="model_name"
                      placeholder="Enter model ID"
                      value={form.model_name}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, model_name: e.target.value }))
                      }
                    />
                  )}
                </div>
 
                {needsApiKey(form.provider) && (
                  <div className="space-y-2">
                    <Label htmlFor="api_key">
                      API Key{" "}
                      {editing && (
                        <span className="text-muted-foreground font-normal">
                          (leave blank to keep existing)
                        </span>
                      )}
                    </Label>
                    <Input
                      id="api_key"
                      type="password"
                      placeholder="sk-..."
                      value={form.api_key}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, api_key: e.target.value }))
                      }
                      required={!editing}
                    />
                  </div>
                )}
 
                {needsBaseUrl(form.provider) && (
                  <div className="space-y-2">
                    <Label htmlFor="base_url">Base URL</Label>
                    <Input
                      id="base_url"
                      placeholder={
                        form.provider === "local"
                          ? "http://localhost:11434"
                          : "https://your-resource.openai.azure.com/openai/deployments/..."
                      }
                      value={form.base_url}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, base_url: e.target.value }))
                      }
                    />
                  </div>
                )}
 
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="temperature">
                      Temperature: {form.temperature}
                    </Label>
                    <Input
                      id="temperature"
                      type="range"
                      min={0}
                      max={2}
                      step={0.1}
                      value={form.temperature}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          temperature: parseFloat(e.target.value),
                        }))
                      }
                      className="h-2"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max_tokens">Max Tokens</Label>
                    <Input
                      id="max_tokens"
                      type="number"
                      value={form.max_tokens}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          max_tokens: parseInt(e.target.value, 10) || 2048,
                        }))
                      }
                    />
                  </div>
                </div>
 
                <div className="flex items-center justify-between rounded-md border p-3">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={form.is_default}
                      onCheckedChange={(c) =>
                        setForm((f) => ({ ...f, is_default: c }))
                      }
                    />
                    <Label>Set as default</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={form.is_active}
                      onCheckedChange={(c) => {
                        setForm((f) => ({ ...f, is_active: c }));
                        setConfirmDeactivate(false);
                      }}
                    />
                    <Label>Active</Label>
                  </div>
                </div>
 
                {editing?.is_active && !form.is_active && (
                  <div className="rounded-md border border-amber-300 bg-amber-50 p-3 space-y-2">
                    <p className="text-xs text-amber-900 flex items-start gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                      This list only shows active models. Deactivating will
                      remove "{editing.display_name}" from view immediately —
                      there is currently no way to browse or re-enable
                      inactive models from this page.
                    </p>
                    <label className="flex items-center gap-2 text-xs text-amber-900">
                      <input
                        type="checkbox"
                        checked={confirmDeactivate}
                        onChange={(e) => setConfirmDeactivate(e.target.checked)}
                      />
                      I understand, deactivate this model
                    </label>
                  </div>
                )}
 
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={saveMutation.isPending}>
                    {saveMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : null}
                    {editing ? "Save changes" : "Add model"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />
 
      {isError ? (
        <Card className="mt-6">
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Failed to load LLM models. Please try again.
            </p>
            <Button onClick={() => refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : configs.length === 0 ? (
        <EmptyState
          icon={<Bot className="h-6 w-6" />}
          title="No LLM Models Configured"
          description="Add your first AI model to start generating personalized outreach emails."
          action={
            <Button onClick={openAdd}>
              <Plus className="h-4 w-4" />
              Add Model
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {configs.map((cfg) => {
            const result = testResults[cfg.id];
            return (
              <Card key={cfg.id} className={!cfg.is_active ? "opacity-60" : ""}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {cfg.provider === "local" ? (
                        <Cpu className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Cloud className="h-4 w-4 text-muted-foreground" />
                      )}
                      <CardTitle className="text-sm">
                        {cfg.display_name}
                      </CardTitle>
                    </div>
                    {cfg.is_default && (
                      <Badge variant="default" className="text-xs">
                        Default
                      </Badge>
                    )}
                  </div>
                  <CardDescription className="text-xs">
                    {providerName(cfg.provider)} — {cfg.model_name}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-2">
                    <div
                      className={`h-2 w-2 rounded-full ${
                        cfg.is_active ? "bg-emerald-500" : "bg-gray-300"
                      }`}
                    />
                    <span className="text-xs text-muted-foreground">
                      {cfg.is_active ? "Active" : "Inactive"}
                    </span>
                    {cfg.api_key && (
                      <span className="text-xs font-mono text-muted-foreground ml-auto">
                        {cfg.api_key}
                      </span>
                    )}
                  </div>
                  {cfg.base_url && (
                    <p className="text-xs text-muted-foreground truncate">
                      {cfg.base_url}
                    </p>
                  )}
                  <p className="text-[11px] text-muted-foreground">
                    Updated {formatDateTime(cfg.updated_at)}
                  </p>
 
                  {result && (
                    <div
                      className={`text-xs p-2 rounded ${
                        result.ok
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-red-50 text-red-700"
                      }`}
                    >
                      {result.message}
                    </div>
                  )}
 
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1"
                      onClick={() => handleTest(cfg.id)}
                      disabled={testingId === cfg.id}
                    >
                      {testingId === cfg.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <TestTube2 className="h-3 w-3" />
                      )}
                      Test
                    </Button>
                    {!cfg.is_default && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setDefaultMutation.mutate(cfg.id)}
                        disabled={setDefaultMutation.isPending}
                        title="Set as default LLM model"
                      >
                        <Star className="h-3 w-3" />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openEdit(cfg)}
                      title="Edit"
                    >
                      <Pencil className="h-3 w-3" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive"
                      onClick={() => setDeleteTarget(cfg)}
                      title="Delete"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
 
      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete LLM model?</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `"${deleteTarget.display_name}" (${providerName(deleteTarget.provider)}) will be deactivated. This is a soft-delete — the row is kept for audit but will no longer appear in this list or be usable for generation, and cannot be restored from this page.`
                : "This LLM model will be deactivated. This action cannot be undone from this page."}
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
              {deleteMutation.isPending ? "Deactivating…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}