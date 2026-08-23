/**
 * CostTablePage.tsx — SUPER_ADMIN cost pricing table editor.
 *
 * Under <PlatformAdminLayout>. Mounted at `/platform-admin/cost-table`.
 *
 * Fetches GET /api/v1/usage/cost-table → CostTableEntry[].
 * Mutations: PUT /api/v1/usage/cost-table (full array replacement).
 *
 * Renders an editable table: provider, model, event_type, unit, price_per_unit
 * (cents). Inline edit + save. Add row + delete row.
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Save, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { usageApi } from "@/services/apiClient";
import type { CostTableEntry, CostTableInput } from "@/types/common";
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
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const MOCK_ENTRIES: CostTableEntry[] = [
  {
    id: "ct-1",
    provider: "openai",
    model: "gpt-4o-mini",
    event_type: "llm_completion",
    unit: "1k_tokens",
    price_per_unit_cents: 0.15,
    updated_at: "2025-01-12T10:00:00Z",
  },
  {
    id: "ct-2",
    provider: "anthropic",
    model: "claude-3-5-sonnet-20241022",
    event_type: "llm_completion",
    unit: "1k_tokens",
    price_per_unit_cents: 0.30,
    updated_at: "2025-01-15T09:00:00Z",
  },
  {
    id: "ct-3",
    provider: "sendgrid",
    model: "standard",
    event_type: "email_send",
    unit: "1_email",
    price_per_unit_cents: 0.05,
    updated_at: "2025-01-22T12:00:00Z",
  },
  {
    id: "ct-4",
    provider: "apollo",
    model: "credits",
    event_type: "enrichment",
    unit: "1_credit",
    price_per_unit_cents: 0.50,
    updated_at: "2025-01-30T12:00:00Z",
  },
];

interface EditableRow extends CostTableInput {
  id: string;
}

function toEditable(entry: CostTableEntry): EditableRow {
  return {
    id: entry.id,
    provider: entry.provider,
    model: entry.model,
    event_type: entry.event_type,
    unit: entry.unit,
    price_per_unit_cents: entry.price_per_unit_cents,
  };
}

export function CostTablePage() {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<EditableRow[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditableRow | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["usage", "cost-table"],
    queryFn: () => usageApi.costTable(),
  });

  // Initialize editable rows once data arrives.
  const effectiveRows: EditableRow[] =
    rows ?? (data ?? MOCK_ENTRIES).map(toEditable);

  const saveMutation = useMutation({
    mutationFn: (entries: CostTableInput[]) =>
      usageApi.updateCostTable(entries),
    onSuccess: () => {
      toast.success("Cost table saved");
      queryClient.invalidateQueries({ queryKey: ["usage", "cost-table"] });
      setRows(null);
      setEditingId(null);
      setDraft(null);
    },
    onError: () => toast.error("Failed to save cost table"),
  });

  function startEdit(row: EditableRow) {
    setEditingId(row.id);
    setDraft({ ...row });
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft(null);
  }

  function commitEdit() {
    if (!draft) return;
    if (!draft.provider.trim() || !draft.model.trim()) {
      toast.error("Provider + model are required");
      return;
    }
    const next = effectiveRows.map((r) => (r.id === draft.id ? draft : r));
    setRows(next);
    setEditingId(null);
    setDraft(null);
  }

  function addRow() {
    const id = `new-${Date.now()}`;
    const newRow: EditableRow = {
      id,
      provider: "openai",
      model: "",
      event_type: "llm_completion",
      unit: "1k_tokens",
      price_per_unit_cents: 0,
    };
    const next = [...effectiveRows, newRow];
    setRows(next);
    setEditingId(id);
    setDraft(newRow);
  }

  function deleteRow(id: string) {
    setRows(effectiveRows.filter((r) => r.id !== id));
  }

  function handleSaveAll() {
    saveMutation.mutate(
      effectiveRows.map((r) => ({
        provider: r.provider,
        model: r.model,
        event_type: r.event_type,
        unit: r.unit,
        price_per_unit_cents: r.price_per_unit_cents,
      })),
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cost Table"
        description="Pricing per provider/model/event used to compute usage cost. Edits apply on the next usage rollup."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={addRow}>
              <Plus className="h-4 w-4" />
              Add row
            </Button>
            <Button
              size="sm"
              onClick={handleSaveAll}
              disabled={saveMutation.isPending}
            >
              <Save className="h-4 w-4" />
              {saveMutation.isPending ? "Saving…" : "Save all"}
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Pricing entries</CardTitle>
          <CardDescription>
            Price per unit is in cents. Use 0.15 to mean $0.0015 (i.e. 0.15
            cents). Common units: <code>1k_tokens</code>, <code>1_email</code>,
            <code>1_credit</code>, <code>1_call</code>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : effectiveRows.length === 0 ? (
            <EmptyState
              icon={<Plus className="h-6 w-6" />}
              title="No pricing entries"
              description="Add the first pricing entry to start computing usage cost."
              action={
                <Button onClick={addRow}>
                  <Plus className="h-4 w-4" />
                  Add row
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Event type</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead className="text-right">Price (cents)</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {effectiveRows.map((row) => {
                  const isEditing = editingId === row.id && draft !== null;
                  if (isEditing) {
                    return (
                      <TableRow key={row.id}>
                        <TableCell>
                          <Input
                            value={draft!.provider}
                            onChange={(e) =>
                              setDraft({ ...draft!, provider: e.target.value })
                            }
                            className="h-8 text-xs"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={draft!.model}
                            onChange={(e) =>
                              setDraft({ ...draft!, model: e.target.value })
                            }
                            className="h-8 text-xs"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={draft!.event_type}
                            onChange={(e) =>
                              setDraft({
                                ...draft!,
                                event_type: e.target.value,
                              })
                            }
                            className="h-8 text-xs"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={draft!.unit}
                            onChange={(e) =>
                              setDraft({ ...draft!, unit: e.target.value })
                            }
                            className="h-8 text-xs"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            step={0.01}
                            value={draft!.price_per_unit_cents}
                            onChange={(e) =>
                              setDraft({
                                ...draft!,
                                price_per_unit_cents: Number(e.target.value),
                              })
                            }
                            className="h-8 text-right text-xs"
                          />
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={commitEdit}
                                  aria-label="Save row"
                                >
                                  <Check className="h-4 w-4 text-emerald-600" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Save row</TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={cancelEdit}
                                  aria-label="Cancel"
                                >
                                  <X className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Cancel</TooltipContent>
                            </Tooltip>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  }
                  return (
                    <TableRow key={row.id}>
                      <TableCell className="font-medium uppercase">
                        {row.provider}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {row.model}
                      </TableCell>
                      <TableCell className="text-xs">{row.event_type}</TableCell>
                      <TableCell className="text-xs">{row.unit}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.price_per_unit_cents}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => startEdit(row)}
                          >
                            Edit
                          </Button>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label="Delete"
                                onClick={() => deleteRow(row.id)}
                              >
                                <Trash2 className="h-4 w-4 text-red-600" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Delete cost row</TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
