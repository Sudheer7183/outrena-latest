/**
 * IntegrationsPage.tsx — prospecting integrations CRUD + connection test.
 *
 * API:
 *   GET  /api/v1/integrations         → Integration[]
 *   POST /api/v1/integrations         → Integration
 *   PUT  /api/v1/integrations/:id     → Integration
 *   POST /api/v1/prospecting-test     → { ok, latencyMs?, sample? }
 *
 * Renders a table of integrations (name, type, masked API key, isActive,
 * lastTestedAt), an Add/Edit dialog, and a per-row "Test connection" button.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plug, Plus, Zap } from "lucide-react";
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
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime } from "@/lib/utils";

type IntegrationType =
  | "apollo"
  | "zoominfo"
  | "hunter"
  | "clearbit"
  | "apollo-api";

const TYPES: IntegrationType[] = [
  "apollo",
  "zoominfo",
  "hunter",
  "clearbit",
  "apollo-api",
];

interface Integration {
  id: string;
  name: string;
  platform: IntegrationType;
  apiKey: string | null;
  key_source: string;
  baseUrl: string | null;
  isActive: boolean;
  lastTestedAt: string | null;
  lastTestResult: string | null;
}

interface IntegrationInput {
  name: string;
  type: IntegrationType;
  apiKey: string;
  baseUrl?: string;
  isActive: boolean;
}

interface TestResponse {
  ok: boolean;
  latencyMs?: number;
  sample?: string;
  error?: string;
}

const MOCK_INTEGRATIONS: Integration[] = [
  {
    id: "int-1",
    name: "Apollo — Sales",
    platform: "apollo",
    apiKey: "ap-••••••••••9c1d",
    key_source: "tenant",
    baseUrl: null,
    isActive: true,
    lastTestedAt: "2025-02-11T15:00:00Z",
    lastTestResult: "ok",
  },
  {
    id: "int-2",
    name: "ZoomInfo — Enrichment",
    platform: "zoominfo",
    apiKey: "zi-••••••••••4a8b",
    key_source: "tenant",
    baseUrl: null,
    isActive: true,
    lastTestedAt: "2025-02-09T11:30:00Z",
    lastTestResult: "ok",
  },
  {
    id: "int-3",
    name: "Hunter — Email Finder",
    platform: "hunter",
    apiKey: "hu-••••••••2f7e",
    key_source: "tenant",
    baseUrl: "https://api.hunter.io",
    isActive: false,
    lastTestedAt: "2025-01-28T08:00:00Z",
    lastTestResult: "failed",
  },
  {
    id: "int-4",
    name: "Clearbit — Firmographics",
    platform: "clearbit",
    apiKey: "cb-••••••••6d3a",
    key_source: "tenant",
    baseUrl: null,
    isActive: true,
    lastTestedAt: null,
    lastTestResult: null,
  },
];

const EMPTY_FORM: IntegrationInput = {
  name: "",
  type: "apollo",
  apiKey: "",
  baseUrl: "",
  isActive: true,
};

export function IntegrationsPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<IntegrationInput>(EMPTY_FORM);
  const [testingId, setTestingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["integrations"],
    queryFn: () => http.get<Integration[]>("/api/v1/integrations"),
  });

  const integrations = data ?? MOCK_INTEGRATIONS;

  const createMutation = useMutation({
    mutationFn: (body: IntegrationInput) =>
      http.post<Integration>("/api/v1/integrations", body),
    onSuccess: () => {
      toast.success("Integration added");
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setDialogOpen(false);
    },
    onError: () => toast.error("Failed to add integration"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: IntegrationInput }) =>
      http.put<Integration>(`/api/v1/integrations/${id}`, body),
    onSuccess: () => {
      toast.success("Integration updated");
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setDialogOpen(false);
    },
    onError: () => toast.error("Failed to update integration"),
  });

  const testMutation = useMutation({
    mutationFn: (id: string) =>
      http.post<TestResponse>("/api/v1/prospecting-test", { integrationId: id }),
    onSuccess: (res) => {
      if (res.ok) {
        toast.success(
          `Connection OK${res.latencyMs ? ` · ${res.latencyMs}ms` : ""}`,
        );
      } else {
        toast.error(`Connection failed${res.error ? ` · ${res.error}` : ""}`);
      }
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    },
    onError: () => toast.error("Test request failed"),
    onSettled: () => setTestingId(null),
  });

  function openAdd() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(int: Integration) {
    setEditingId(int.id);
    setForm({
      name: int.name,
      type: int.platform as IntegrationType,
      apiKey: "",
      baseUrl: int.baseUrl ?? "",
      isActive: int.isActive,
    });
    setDialogOpen(true);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    if (editingId) {
      updateMutation.mutate({ id: editingId, body: form });
    } else {
      createMutation.mutate(form);
    }
  }

  function handleTest(id: string) {
    setTestingId(id);
    testMutation.mutate(id);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Prospecting Integrations"
        description="Connect Apollo, ZoomInfo, Hunter, and Clearbit to source and enrich prospects."
        actions={
          <Button onClick={openAdd}>
            <Plus className="h-4 w-4" />
            Add Integration
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Connected Integrations</CardTitle>
          <CardDescription>
            Test each integration before relying on it for autopilot sourcing.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : integrations.length === 0 ? (
            <EmptyState
              icon={<Plug className="h-6 w-6" />}
              title="No integrations yet"
              description="Add your first prospecting integration to enable sourcing."
              action={
                <Button onClick={openAdd}>
                  <Plus className="h-4 w-4" />
                  Add Integration
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>API Key</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Test</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {integrations.map((int) => (
                  <TableRow key={int.id}>
                    <TableCell className="font-medium">{int.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{int.platform}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {int.apiKey}
                    </TableCell>
                    <TableCell>
                      {int.isActive ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="secondary">Inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {int.lastTestedAt ? (
                        <span className="flex items-center gap-1.5">
                          {formatDateTime(int.lastTestedAt)}
                          {int.lastTestResult === "ok" && (
                            <Badge variant="success" className="text-[10px]">
                              OK
                            </Badge>
                          )}
                          {int.lastTestResult === "failed" && (
                            <Badge variant="destructive" className="text-[10px]">
                              Failed
                            </Badge>
                          )}
                        </span>
                      ) : (
                        "Never"
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleTest(int.id)}
                          disabled={testingId === int.id}
                        >
                          <Zap className="h-3.5 w-3.5" />
                          {testingId === int.id ? "Testing…" : "Test"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(int)}
                        >
                          Edit
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogClose onClose={() => setDialogOpen(false)} />
        <DialogHeader>
          <DialogTitle>
            {editingId ? "Edit Integration" : "Add Integration"}
          </DialogTitle>
          <DialogDescription>
            Connect a prospecting data provider with API credentials.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Display name</Label>
            <Input
              id="name"
              placeholder="Apollo — Sales"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="type">Type</Label>
            <Select
              id="type"
              value={form.type}
              onChange={(e) =>
                setForm({ ...form, type: e.target.value as IntegrationType })
              }
            >
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
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
            <Label htmlFor="baseUrl">Base URL (optional)</Label>
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
                Inactive integrations are skipped by autopilot.
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
              {editingId ? "Save changes" : "Add integration"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}
