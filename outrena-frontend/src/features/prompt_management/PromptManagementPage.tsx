/**
 * PromptManagementPage.tsx — manage the 47 OUTRENA prompt templates.
 *
 * API:
 *   GET /api/v1/prompts         → Prompt[]
 *   PUT /api/v1/prompts/:key    → Prompt
 *
 * Renders a filterable, searchable table. Clicking a row opens a dialog with
 * a large Textarea to edit the template body; Save → PUT.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Save, Search } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatDateTime, truncate } from "@/lib/utils";

type PromptCategory =
  | "email_generation"
  | "icp"
  | "sequence"
  | "analytics"
  | "reply"
  | "system";

const CATEGORIES: PromptCategory[] = [
  "email_generation",
  "icp",
  "sequence",
  "analytics",
  "reply",
  "system",
];

interface Prompt {
  id: string;
  key: string;
  name: string;
  category: PromptCategory;
  description: string;
  template: string;
  isEditable: boolean;
  defaultValue: string;
  variables: string;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
}

const MOCK_PROMPTS: Prompt[] = [
  {
    id: "cl_mock_1",
    key: "email.first_touch",
    name: "First Touch Email",
    category: "email_generation",
    description: "Cold first-touch email using the PAS framework.",
    template:
      "Hi {{first_name}},\n\nI noticed {{company}} recently {{trigger}}. Most {{persona}} we work with tell us {{pain_point}}.\n\nWe help teams like yours {{outcome}} — would a 15-min call next week make sense?\n\nBest,\n{{sender_name}}",
    isEditable: true,
    defaultValue: "",
    variables: '["first_name", "company", "trigger", "persona", "pain_point", "outcome", "sender_name"]',
    sortOrder: 1,
    createdAt: "2025-01-22T10:00:00Z",
    updatedAt: "2025-02-10T11:00:00Z",
  },
  {
    id: "cl_mock_2",
    key: "icp.autodiscover",
    name: "ICP Auto-Discover",
    category: "icp",
    description: "Distils an ICP profile from 3 reference customers.",
    template:
      "You are a B2B ICP analyst. Given the following 3 reference customers: {{references}}.\n\nExtract firmographics, technographics, intent signals, and seniority tiers. Return as JSON.",
    isEditable: true,
    defaultValue: "",
    variables: '["references"]',
    sortOrder: 2,
    createdAt: "2025-01-22T10:00:00Z",
    updatedAt: "2025-02-04T16:30:00Z",
  },
  {
    id: "cl_mock_3",
    key: "sequence.plan",
    name: "Sequence Planner",
    category: "sequence",
    description: "Plans a 5-touch sequence given prospect + angle.",
    template:
      "Plan a 5-touch outreach sequence for {{prospect_name}} at {{company}}. Angle: {{angle}}. Framework: {{framework}}. Mix email + LinkedIn touches spaced 3-4 days apart.",
    isEditable: true,
    defaultValue: "",
    variables: '["prospect_name", "company", "angle", "framework"]',
    sortOrder: 3,
    createdAt: "2025-01-22T10:00:00Z",
    updatedAt: "2025-02-08T09:15:00Z",
  },
  {
    id: "cl_mock_4",
    key: "analytics.weekly_digest",
    name: "Weekly Digest Summary",
    category: "analytics",
    description: "Summarises the week's outreach into 3 bullet points.",
    template:
      "Summarise the following outreach metrics into 3 executive bullet points: sent={{sent}}, opened={{opened}}, replied={{replied}}, pipeline_value={{pipeline_value}}.",
    isEditable: true,
    defaultValue: "",
    variables: '["sent", "opened", "replied", "pipeline_value"]',
    sortOrder: 4,
    createdAt: "2025-01-22T10:00:00Z",
    updatedAt: "2025-02-09T18:00:00Z",
  },
  {
    id: "cl_mock_5",
    key: "reply.categorise",
    name: "Reply Categoriser",
    category: "reply",
    description: "Classifies inbound reply intent into positive/neutral/negative.",
    template:
      "Classify the following inbound reply into one of: positive, neutral, negative, ooo, unsubscribe. Reply:\n\n{{inbound_message}}\n\nReturn JSON: { category, confidence, suggested_reply }.",
    isEditable: true,
    defaultValue: "",
    variables: '["inbound_message"]',
    sortOrder: 5,
    createdAt: "2025-01-22T10:00:00Z",
    updatedAt: "2025-02-07T14:45:00Z",
  },
  {
    id: "cl_mock_6",
    key: "system.ground_rules",
    name: "System Ground Rules",
    category: "system",
    description: "System-level rules injected into every generation.",
    template:
      "You are OUTRENA, an AI outreach assistant. Always be: concise, specific, and respectful. Never fabricate case studies. Never claim to have spoken with the prospect before.",
    isEditable: false,
    defaultValue: "",
    variables: "[]",
    sortOrder: 6,
    createdAt: "2025-01-22T10:00:00Z",
    updatedAt: "2025-01-25T10:00:00Z",
  },
];

function categoryVariant(
  cat: PromptCategory,
): "default" | "secondary" | "success" | "warning" | "outline" {
  switch (cat) {
    case "email_generation":
      return "success";
    case "icp":
      return "default";
    case "sequence":
      return "warning";
    case "analytics":
      return "secondary";
    case "reply":
      return "default";
    case "system":
      return "outline";
  }
}

export function PromptManagementPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<"all" | PromptCategory>("all");
  const [editing, setEditing] = useState<Prompt | null>(null);
  const [draft, setDraft] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: () => http.get<Prompt[]>("/api/v1/prompts"),
  });

  // BUG-02 FIX: empty API response falls through to mock ([] is truthy, ?? does not catch it)
  const prompts = (data && data.length > 0) ? data : MOCK_PROMPTS;

  /** Parse the JSON-encoded variables string from the backend into a string array. */
  function parseVariables(varsStr: string): string[] {
    try {
      const parsed = JSON.parse(varsStr);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  const filtered = useMemo(() => {
    return prompts.filter((p) => {
      if (categoryFilter !== "all" && p.category !== categoryFilter) return false;
      if (
        search &&
        !p.name.toLowerCase().includes(search.toLowerCase()) &&
        !p.key.toLowerCase().includes(search.toLowerCase())
      )
        return false;
      return true;
    });
  }, [prompts, search, categoryFilter]);

  const saveMutation = useMutation({
    mutationFn: ({ key, template }: { key: string; template: string }) =>
      http.put<Prompt>(`/api/v1/prompts/${key}`, { template }),
    onSuccess: () => {
      toast.success("Prompt saved");
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      setEditing(null);
    },
    onError: () => toast.error("Failed to save prompt"),
  });

  function openEdit(p: Prompt) {
    setEditing(p);
    setDraft(p.template);
  }

  function handleSave() {
    if (!editing) return;
    saveMutation.mutate({ key: editing.key, template: draft });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Prompt Management"
        description="Edit the 47 prompt templates that drive OUTRENA's AI generations."
      />

      <Card>
        <CardHeader>
          <CardTitle>Prompt Library</CardTitle>
          <CardDescription>
            Filter by category or search by name. Click a row to edit the
            template body.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name or key…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={categoryFilter}
              onChange={(e) =>
                setCategoryFilter(e.target.value as "all" | PromptCategory)
              }
              className="sm:w-56"
            >
              <option value="all">All categories</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<FileText className="h-6 w-6" />}
              title="No prompts match"
              description="Try clearing the search or category filter."
            />
          ) : (
            <ScrollArea maxHeightClass="max-h-[28rem]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Key</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Variables</TableHead>
                    <TableHead>Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((p) => (
                    <TableRow
                      key={p.key}
                      onClick={() => openEdit(p)}
                      className="cursor-pointer"
                    >
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {p.key}
                      </TableCell>
                      <TableCell className="font-medium">
                        {truncate(p.name, 38)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={categoryVariant(p.category)}>
                          {p.category}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {parseVariables(p.variables).length === 0
                          ? "—"
                          : `${parseVariables(p.variables).length} vars`}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(p.updatedAt)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogClose onClose={() => setEditing(null)} />
        <DialogHeader>
          <DialogTitle>Edit prompt</DialogTitle>
          <DialogDescription>
            {editing ? `${editing.key} · ${editing.description}` : ""}
          </DialogDescription>
        </DialogHeader>

        {editing && (
          <div className="space-y-4">
            <div>
              <p className="mb-1 text-xs text-muted-foreground">
                Available variables
              </p>
              <div className="flex flex-wrap gap-1">
                {parseVariables(editing.variables).length === 0 ? (
                  <span className="text-xs text-muted-foreground">
                    None — this is a static system prompt.
                  </span>
                ) : (
                  parseVariables(editing.variables).map((v) => (
                    <Badge key={v} variant="outline" className="font-mono">
                      {`{{${v}}}`}
                    </Badge>
                  ))
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="template">Template body</Label>
              <Textarea
                id="template"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="min-h-[18rem] font-mono text-xs"
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => setEditing(null)}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saveMutation.isPending || draft === editing?.template}
          >
            <Save className="h-4 w-4" />
            Save changes
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
