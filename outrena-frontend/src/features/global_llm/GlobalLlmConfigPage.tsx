/**
 * GlobalLlmConfigPage.tsx — SUPER_ADMIN global LLM config UI.
 *
 * Under <PlatformAdminLayout>. Mounted at `/platform-admin/llm-configs`.
 *
 * Fetches GET /api/platform/admin/llm-configs (masked keys).
 * Mutations: POST (create), PUT (update), DELETE, POST set-default, POST test.
 *
 * Warning banner: "These are global platform-level LLM configurations. All
 * tenants use these. Changes affect all users."
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Plus,
  Star,
  Trash2,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { globalLlmApi } from "@/services/apiClient";
import type {
  GlobalLlmConfig,
  GlobalLlmConfigInput,
} from "@/types/common";
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

const PROVIDERS = [
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

const MOCK_CONFIGS: GlobalLlmConfig[] = [
  {
    id: "gllm-1",
    provider: "openai",
    display_name: "OpenAI Primary",
    model_name: "gpt-4o-mini",
    base_url: null,
    max_tokens: 4096,
    temperature: 0.4,
    api_key_masked: "sk-••••••••••••3a9f",
    is_default: true,
    is_active: true,
    created_at: "2025-01-22T10:00:00Z",
    updated_at: "2025-02-10T14:30:00Z",
  },
  {
    id: "gllm-2",
    provider: "anthropic",
    display_name: "Anthropic Claude",
    model_name: "claude-3-5-sonnet-20241022",
    base_url: null,
    max_tokens: 8192,
    temperature: 0.5,
    api_key_masked: "sk-ant-••••••••7c2b",
    is_default: false,
    is_active: true,
    created_at: "2025-01-15T09:00:00Z",
    updated_at: "2025-02-01T08:15:00Z",
  },
  {
    id: "gllm-3",
    provider: "deepseek",
    display_name: "DeepSeek (cost-optimized)",
    model_name: "deepseek-chat",
    base_url: "https://api.deepseek.com",
    max_tokens: 4096,
    temperature: 0.6,
    api_key_masked: "••••••••••••1f8a",
    is_default: false,
    is_active: false,
    created_at: "2025-01-30T12:00:00Z",
    updated_at: "2025-02-05T16:45:00Z",
  },
];

const EMPTY_FORM: GlobalLlmConfigInput = {
  provider: "openai",
  display_name: "",
  api_key: "",
  base_url: "",
  model_name: "",
  max_tokens: 4096,
  temperature: 0.4,
  is_default: false,
  is_active: true,
};

export function GlobalLlmConfigPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<GlobalLlmConfigInput>(EMPTY_FORM);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["platform", "llm-configs"],
    queryFn: () => globalLlmApi.list(),
  });

  const configs = data ?? MOCK_CONFIGS;

  const createMutation = useMutation({
    mutationFn: (body: GlobalLlmConfigInput) => globalLlmApi.create(body),
    onSuccess: () => {
      toast.success("Global LLM config added");
      queryClient.invalidateQueries({ queryKey: ["platform", "llm-configs"] });
      setDialogOpen(false);
    },
    onError: () => toast.error("Failed to add LLM config"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: GlobalLlmConfigInput }) =>
      globalLlmApi.update(id, body),
    onSuccess: () => {
      toast.success("Global LLM config updated");
      queryClient.invalidateQueries({ queryKey: ["platform", "llm-configs"] });
      setDialogOpen(false);
    },
    onError: () => toast.error("Failed to update LLM config"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => globalLlmApi.remove(id),
    onSuccess: () => {
      toast.success("Global LLM config deleted");
      queryClient.invalidateQueries({ queryKey: ["platform", "llm-configs"] });
      setDeleteOpen(null);
    },
    onError: () => toast.error("Failed to delete LLM config"),
  });

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => globalLlmApi.setDefault(id),
    onSuccess: () => {
      toast.success("Default config updated");
      queryClient.invalidateQueries({ queryKey: ["platform", "llm-configs"] });
    },
    onError: () => toast.error("Failed to set default"),
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => globalLlmApi.test(id),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["llm-configs"] });
      if (res.success) {
        toast.success(
          `Test passed${res.latency_ms ? ` · ${res.latency_ms}ms` : ""}`,
        );
      } else {
        toast.error(`Test failed: ${res.message}`);
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

  function openEdit(cfg: GlobalLlmConfig) {
    setEditingId(cfg.id);
    setForm({
      provider: cfg.provider,
      display_name: cfg.display_name,
      api_key: "",
      base_url: cfg.base_url ?? "",
      model_name: cfg.model_name,
      max_tokens: cfg.max_tokens,
      temperature: cfg.temperature,
      is_default: cfg.is_default,
      is_active: cfg.is_active,
    });
    setDialogOpen(true);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.display_name.trim()) {
      toast.error("Display name is required");
      return;
    }
    if (!form.model_name.trim()) {
      toast.error("Model name is required");
      return;
    }
    if (!editingId && !form.api_key?.trim()) {
      toast.error("API key is required");
      return;
    }
    if (editingId) {
      updateMutation.mutate({ id: editingId, body: form });
    } else {
      createMutation.mutate(form);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Global LLM Config"
        description="Platform-level language-model configurations shared across all tenants."
        actions={
          <Button onClick={openAdd}>
            <Plus className="h-4 w-4" />
            Add Config
          </Button>
        }
      />

      {/* Warning banner */}
      <Card className="border-l-4 border-l-amber-500 bg-amber-500/5">
        <CardContent className="flex items-start gap-3 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <div>
            <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">
              These are global platform-level LLM configurations.
            </p>
            <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
              All tenants use these. Changes affect all users. Delete or disable
              a config and every tenant generation will fail-over to the next
              available provider.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configured Global Models</CardTitle>
          <CardDescription>
            One config may be marked as default. Active configs are eligible for
            routing; the default is preferred.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : configs.length === 0 ? (
            <EmptyState
              icon={<Plus className="h-6 w-6" />}
              title="No global LLM configs"
              description="Add the first platform-level LLM configuration."
              action={
                <Button onClick={openAdd}>
                  <Plus className="h-4 w-4" />
                  Add Config
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Display name</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>API key</TableHead>
                  <TableHead>Default</TableHead>
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
                    <TableCell>{cfg.display_name}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {cfg.model_name}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {cfg.api_key_masked}
                    </TableCell>
                    <TableCell>
                      {cfg.is_default ? (
                        <Badge variant="success" className="gap-1">
                          <Star className="h-3 w-3" /> Default
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
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
                          onClick={() => {
                            setTestingId(cfg.id);
                            testMutation.mutate(cfg.id);
                          }}
                          disabled={testingId === cfg.id}
                        >
                          <Zap className="h-3.5 w-3.5" />
                          {testingId === cfg.id ? "Testing…" : "Test"}
                        </Button>
                        {!cfg.is_default && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDefaultMutation.mutate(cfg.id)}
                            disabled={setDefaultMutation.isPending}
                          >
                            <Star className="h-3.5 w-3.5" />
                            Set default
                          </Button>
                        )}
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
                              aria-label="Delete"
                              onClick={() => setDeleteOpen(cfg.id)}
                            >
                              <Trash2 className="h-4 w-4 text-red-600" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Delete config</TooltipContent>
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

      {/* Add/Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogClose onClose={() => setDialogOpen(false)} />
        <DialogHeader>
          <DialogTitle>
            {editingId ? "Edit Global LLM Config" : "Add Global LLM Config"}
          </DialogTitle>
          <DialogDescription>
            Configure credentials and routing for a language model provider.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="gllm-provider">Provider</Label>
              <Select
                id="gllm-provider"
                value={form.provider}
                onChange={(e) =>
                  setForm({ ...form, provider: e.target.value })
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
              <Label htmlFor="gllm-display">Display name</Label>
              <Input
                id="gllm-display"
                placeholder="OpenAI Primary"
                value={form.display_name}
                onChange={(e) =>
                  setForm({ ...form, display_name: e.target.value })
                }
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="gllm-model">Model name</Label>
            <Input
              id="gllm-model"
              placeholder="gpt-4o-mini"
              value={form.model_name}
              onChange={(e) => setForm({ ...form, model_name: e.target.value })}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="gllm-key">
              API key {editingId && "(leave blank to keep existing)"}
            </Label>
            <Input
              id="gllm-key"
              type="password"
              placeholder="sk-..."
              value={form.api_key ?? ""}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              required={!editingId}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="gllm-base">Base URL (optional — for azure / local)</Label>
            <Input
              id="gllm-base"
              placeholder="https://api.example.com/v1"
              value={form.base_url ?? ""}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <InfoLabel
                htmlFor="gllm-max"
                label="Max tokens"
                info="Hard cap on the number of tokens the LLM will generate per call. Lower = cheaper + faster, but risks truncated emails. 600–1200 is typical for cold emails."
              />
              <Input
                id="gllm-max"
                type="number"
                min={1}
                value={form.max_tokens ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    max_tokens: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </div>
            <div className="space-y-2">
              <InfoLabel
                htmlFor="gllm-temp"
                label="Temperature"
                info="Randomness: 0 = deterministic, 2 = chaotic. 0.4–0.7 produces on-brand, repeatable cold emails; >1.0 risks hallucination."
              />
              <Input
                id="gllm-temp"
                type="number"
                step={0.1}
                min={0}
                max={2}
                value={form.temperature ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    temperature: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </div>
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">Default config</p>
              <p className="text-xs text-muted-foreground">
                Used as the preferred model for all tenant generations.
              </p>
            </div>
            <Switch
              checked={!!form.is_default}
              onCheckedChange={(c) => setForm({ ...form, is_default: c })}
            />
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="text-sm font-medium">Active</p>
              <p className="text-xs text-muted-foreground">
                Inactive configs are skipped during routing.
              </p>
            </div>
            <Switch
              checked={!!form.is_active}
              onCheckedChange={(c) => setForm({ ...form, is_active: c })}
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
              {editingId ? "Save changes" : "Add config"}
              <CheckCircle2 className="ml-1 h-4 w-4" />
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* Delete confirm dialog */}
      <Dialog open={deleteOpen !== null} onOpenChange={(o) => !o && setDeleteOpen(null)}>
        <DialogClose onClose={() => setDeleteOpen(null)} />
        <DialogHeader>
          <DialogTitle>Delete global LLM config?</DialogTitle>
          <DialogDescription>
            This config will be removed from the platform. Any tenant
            generations routed through it will fail over to the next available
            provider. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteOpen(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={deleteMutation.isPending}
            onClick={() => deleteOpen && deleteMutation.mutate(deleteOpen)}
          >
            Delete config
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
