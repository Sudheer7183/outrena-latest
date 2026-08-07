/**
 * LlmConfigPage.tsx — CRUD for tenant LLM model configurations.
 *
 * API:
 *   GET    /api/v1/llm-configs         → LlmConfig[]
 *   POST   /api/v1/llm-configs         → LlmConfig
 *   PUT    /api/v1/llm-configs/:id     → LlmConfig
 *   DELETE /api/v1/llm-configs/:id     → { message }
 *   POST   /api/v1/llm-configs/test-llm → { ok, latency_ms?, content?, error? }
 *
 * Renders a table of configs with masked API keys, an "Add Model" dialog
 * (provider select with 13 providers, model, key, base URL, isActive switch),
 * and a per-row "Test" button that calls /test-llm and toasts the result.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Zap } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { LlmConfigCreateSchema, formatZodError } from "@/lib/validation";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InfoLabel } from "@/components/ui/info-label";
import { NativeSelect as Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
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
import { formatDateTime } from "@/lib/utils";

type LlmProvider =
  | "zai"
  | "openai"
  | "anthropic"
  | "google"
  | "deepseek"
  | "groq"
  | "mistral"
  | "together"
  | "fireworks"
  | "perplexity"
  | "openrouter"
  | "ollama"
  | "azure";

const PROVIDERS: LlmProvider[] = [
  "zai",
  "openai",
  "anthropic",
  "google",
  "deepseek",
  "groq",
  "mistral",
  "together",
  "fireworks",
  "perplexity",
  "openrouter",
  "ollama",
  "azure",
];

interface LlmConfig {
  id: number;
  provider: LlmProvider;
  display_name: string;
  model_name: string;
  api_key: string | null;
  base_url: string | null;
  max_tokens: number;
  temperature: number;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

interface LlmConfigInput {
  provider: LlmProvider;
  model: string;
  apiKey: string;
  baseUrl?: string;
  isActive: boolean;
}

interface TestLlmResponse {
  ok: boolean;
  latency_ms?: number;
  content?: string;
  error?: string;
}

const MOCK_CONFIGS: LlmConfig[] = [
  {
    id: 1,
    provider: "openai",
    display_name: "openai/gpt-4o-mini",
    model_name: "gpt-4o-mini",
    api_key: "sk-••••••••••••3a9f",
    base_url: null,
    max_tokens: 2048,
    temperature: 0.7,
    is_active: true,
    is_default: true,
    created_at: "2025-01-22T10:00:00Z",
    updated_at: "2025-02-10T14:30:00Z",
  },
  {
    id: 2,
    provider: "anthropic",
    display_name: "anthropic/claude-3-5-sonnet-20241022",
    model_name: "claude-3-5-sonnet-20241022",
    api_key: "sk-ant-••••••••7c2b",
    base_url: null,
    max_tokens: 2048,
    temperature: 0.7,
    is_active: false,
    is_default: false,
    created_at: "2025-01-15T09:00:00Z",
    updated_at: "2025-02-01T08:15:00Z",
  },
  {
    id: 3,
    provider: "deepseek",
    display_name: "deepseek/deepseek-chat",
    model_name: "deepseek-chat",
    api_key: "••••••••••••1f8a",
    base_url: "https://api.deepseek.com",
    max_tokens: 2048,
    temperature: 0.7,
    is_active: false,
    is_default: false,
    created_at: "2025-01-30T12:00:00Z",
    updated_at: "2025-02-05T16:45:00Z",
  },
];

const EMPTY_FORM: LlmConfigInput = {
  provider: "openai",
  model: "",
  apiKey: "",
  baseUrl: "",
  isActive: true,
};

export function LlmConfigPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<LlmConfigInput>(EMPTY_FORM);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<LlmConfig | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["llm-configs"],
    queryFn: () => http.get<LlmConfig[]>("/api/v1/llm-configs"),
  });

  const configs = data ?? MOCK_CONFIGS;

  const createMutation = useMutation({
    mutationFn: (body: LlmConfigInput) =>
      http.post<LlmConfig>("/api/v1/llm-configs", body),
    onSuccess: () => {
      toast.success("Model added");
      queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
      setDialogOpen(false);
    },
    onError: () => toast.error("Failed to add model"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: LlmConfigInput }) =>
      http.put<LlmConfig>(`/api/v1/llm-configs/${id}`, body),
    onSuccess: () => {
      toast.success("Model updated");
      queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
      setDialogOpen(false);
    },
    onError: () => toast.error("Failed to update model"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/llm-configs/${id}`),
    onSuccess: () => {
      toast.success("Model deleted");
      queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete model"),
  });

  const testMutation = useMutation({
    mutationFn: (id: string) =>
      http.post<TestLlmResponse>("/api/v1/llm-configs/test-llm", { config_id: Number(id) }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
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
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(cfg: LlmConfig) {
    setEditingId(String(cfg.id));
    setForm({
      provider: cfg.provider,
      model: cfg.model_name,
      apiKey: "",
      baseUrl: cfg.base_url ?? "",
      isActive: cfg.is_active,
    });
    setDialogOpen(true);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    // Task 2-b finding 10: zod-validated form.
    const parsed = LlmConfigCreateSchema.safeParse({
      name: form.model, // LlmConfig doesn't have a separate name; use model
      provider: form.provider,
      model: form.model,
      apiKey: form.apiKey || undefined,
      baseUrl: form.baseUrl || undefined,
      isActive: form.isActive,
    });
    if (!parsed.success) {
      toast.error(formatZodError(parsed.error));
      return;
    }
    if (editingId) {
      updateMutation.mutate({ id: editingId, body: form });
    } else {
      createMutation.mutate(form);
    }
  }

  function handleTest(id: number) {
    setTestingId(id);
    testMutation.mutate(String(id));
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="LLM Models"
        description="Configure the language models used for email generation, ICP scoring, and reply drafting."
        actions={
          <Button onClick={openAdd}>
            <Plus className="h-4 w-4" />
            Add Model
          </Button>
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
      ) : (
      <Card>
        <CardHeader>
          <CardTitle>Configured Models</CardTitle>
          <CardDescription>
            Only one model can be active at a time per provider. Active models
            are used for new generations.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : configs.length === 0 ? (
            <EmptyState
              icon={<Plus className="h-6 w-6" />}
              title="No LLM models configured"
              description="Add your first model to start generating outreach copy."
              action={
                <Button onClick={openAdd}>
                  <Plus className="h-4 w-4" />
                  Add Model
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>API Key</TableHead>
                  <TableHead>Base URL</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {configs.map((cfg) => (
                  <TableRow key={cfg.id}>
                    <TableCell className="font-medium uppercase">
                      {cfg.provider}
                    </TableCell>
                    <TableCell>{cfg.model_name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {cfg.api_key}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {cfg.base_url ?? "—"}
                    </TableCell>
                    <TableCell>
                      {cfg.is_active ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="secondary">Inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(cfg.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleTest(cfg.id)}
                          disabled={testingId === cfg.id}
                        >
                          <Zap className="h-3.5 w-3.5" />
                          {testingId === cfg.id ? "Testing…" : "Test"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(cfg)}
                        >
                          Edit
                        </Button>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeleteTarget(cfg)}
                              aria-label="Delete"
                            >
                              <Trash2 className="h-4 w-4 text-red-600" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Delete model</TooltipContent>
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
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogClose onClose={() => setDialogOpen(false)} />
        <DialogHeader>
          <DialogTitle>
            {editingId ? "Edit Model" : "Add LLM Model"}
          </DialogTitle>
          <DialogDescription>
            Configure credentials and routing for a language model provider.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <InfoLabel
              htmlFor="provider"
              label="Provider"
              info="Which LLM vendor hosts this model. OUTRENA routes generation calls to the provider's chat-completions API."
            />
            <Select
              id="provider"
              value={form.provider}
              onChange={(e) =>
                setForm({ ...form, provider: e.target.value as LlmProvider })
              }
            >
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          </div>

          <div className="space-y-2">
            <InfoLabel
              htmlFor="model"
              label="Model name"
              info="The exact model identifier the provider expects (e.g. gpt-4o-mini, claude-3-5-sonnet-20241022, gemini-1.5-flash)."
            />
            <Input
              id="model"
              placeholder="gpt-4o-mini"
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="apiKey">
              API key {editingId && "(leave blank to keep existing)"}
            </Label>
            <Input
              id="apiKey"
              type="password"
              placeholder="sk-..."
              value={form.apiKey}
              onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
              required={!editingId}
            />
          </div>

          <div className="space-y-2">
            <InfoLabel
              htmlFor="baseUrl"
              label="Base URL (optional)"
              info="Override the provider's default API endpoint. Required for OpenAI-compatible proxies (vLLM, Together, Ollama, Azure OpenAI). Leave blank for hosted providers."
            />
            <Input
              id="baseUrl"
              placeholder="https://api.example.com/v1"
              value={form.baseUrl}
              onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
            />
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">Active</p>
              <p className="text-xs text-muted-foreground">
                Use this model for new generations.
              </p>
            </div>
            <Switch
              checked={form.isActive}
              onCheckedChange={(c) => setForm({ ...form, isActive: c })}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {editingId ? "Save changes" : "Add model"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete LLM model?</DialogTitle>
          <DialogDescription>
            {deleteTarget?.model_name
              ? `Model "${deleteTarget.model_name}" (${deleteTarget.provider}) will be permanently removed. This action cannot be undone.`
              : "This LLM model will be permanently removed. This action cannot be undone."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() =>
              deleteTarget && deleteMutation.mutate(String(deleteTarget.id))
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
