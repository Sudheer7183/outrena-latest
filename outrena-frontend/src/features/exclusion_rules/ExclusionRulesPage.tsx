/**
 * ExclusionRulesPage.tsx — OUTRENA Phase 4 (Task 3-C)
 *
 * Exclusion rules CRUD + bulk import + check-prospect. Table with active
 * toggle, add dialog, bulk import dialog, check-prospect dialog.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  CheckCircle2,
  ClipboardCheck,
  MoreHorizontal,
  Plus,
  Search,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { ErrorState } from "@/components/ui/error-state";
import { Pagination, usePagination } from "@/components/ui/pagination";
import { formatDate } from "@/lib/utils";
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
  DropdownMenu,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { ScrollArea } from "@/components/ui/scroll-area";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

/* ── Types & mocks ──────────────────────────────────────────────────────── */

type RuleField = "email" | "domain" | "company" | "title";
type RuleOperator = "contains" | "equals" | "regex";

interface ExclusionRule {
  id: string;
  field: RuleField;
  operator: RuleOperator;
  value: string;
  isActive: boolean;
  createdAt: string;
}

interface CheckResult {
  email: string;
  matched: boolean;
  matches: { ruleId: string; field: RuleField; value: string }[];
}

const FIELDS: RuleField[] = ["email", "domain", "company", "title"];
const OPERATORS: RuleOperator[] = ["contains", "equals", "regex"];

const MOCK_RULES: ExclusionRule[] = [
  { id: "r1", field: "domain", operator: "equals", value: "gmail.com", isActive: true, createdAt: "2024-11-01T10:00:00Z" },
  { id: "r2", field: "company", operator: "equals", value: "OUTRENA", isActive: true, createdAt: "2024-11-04T09:30:00Z" },
  { id: "r3", field: "title", operator: "contains", value: "Intern", isActive: true, createdAt: "2024-11-12T14:20:00Z" },
  { id: "r4", field: "domain", operator: "contains", value: ".edu", isActive: false, createdAt: "2024-12-01T11:00:00Z" },
  { id: "r5", field: "email", operator: "regex", value: "^[a-z]+\\.(test|demo)@", isActive: true, createdAt: "2024-12-15T13:45:00Z" },
  { id: "r6", field: "company", operator: "contains", value: "Competitor", isActive: true, createdAt: "2025-01-02T08:00:00Z" },
];

/* ── Page ───────────────────────────────────────────────────────────────── */

export function ExclusionRulesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [fieldFilter, setFieldFilter] = useState<string>("all");
  const [addOpen, setAddOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [checkOpen, setCheckOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ExclusionRule | null>(null);

  const [form, setForm] = useState<{ field: RuleField; operator: RuleOperator; value: string }>({
    field: "domain",
    operator: "equals",
    value: "",
  });
  const [bulkText, setBulkText] = useState("");
  const [checkEmail, setCheckEmail] = useState("");
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);

  const { data: apiRules, isLoading , isError, error, refetch } = useQuery({
    queryKey: ["exclusion-rules"],
    queryFn: () => http.get<ExclusionRule[]>("/api/v1/exclusion-rules"),
    retry: false,
  });
  const rules = apiRules ?? MOCK_RULES;

  const filtered = rules.filter((r) => {
    const matchesSearch = r.value.toLowerCase().includes(search.toLowerCase());
    const matchesField = fieldFilter === "all" || r.field === fieldFilter;
    return matchesSearch && matchesField;
  });


  const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: filtered, initialPageSize: 15 });

  const createMut = useMutation({
    mutationFn: (body: { field: RuleField; operator: RuleOperator; value: string }) =>
      http.post<ExclusionRule>("/api/v1/exclusion-rules", body),
    onSuccess: () => {
      toast.success("Rule added");
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
      setAddOpen(false);
      setForm({ field: "domain", operator: "equals", value: "" });
    },
    onError: () => toast.error("Failed to add rule"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => http.delete<{ message: string }>(`/api/v1/exclusion-rules/${id}`),
    onSuccess: () => {
      toast.success("Rule deleted");
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete rule"),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      http.put<ExclusionRule>(`/api/v1/exclusion-rules/${id}`, { isActive }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
    },
    onError: () => toast.error("Failed to update rule"),
  });

  const bulkMut = useMutation({
    mutationFn: (rules: { field: RuleField; operator: RuleOperator; value: string }[]) =>
      http.post<{ imported: number }>("/api/v1/exclusion-rules/bulk", { rules }),
    onSuccess: (data) => {
      toast.success(`Imported ${data.imported} rules`);
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
      setBulkOpen(false);
      setBulkText("");
    },
    onError: () => toast.error("Failed to bulk import rules"),
  });

  const checkMut = useMutation({
    mutationFn: (email: string) =>
      http.post<CheckResult>("/api/v1/exclusion-rules/check", { email }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
      setCheckResult(data);
    },
    onError: () => toast.error("Failed to check prospect"),
  });

  function handleAdd() {
    if (!form.value.trim()) {
      toast.error("Value is required");
      return;
    }
    createMut.mutate(form);
  }

  function handleBulk() {
    const lines = bulkText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length === 0) {
      toast.error("Paste at least one rule");
      return;
    }
    const parsed: { field: RuleField; operator: RuleOperator; value: string }[] = lines.map((line) => {
      const [field, operator, ...rest] = line.split(",");
      const value = rest.join(",").trim();
      return {
        field: (FIELDS.includes(field as RuleField) ? field : "domain") as RuleField,
        operator: (OPERATORS.includes(operator as RuleOperator) ? operator : "equals") as RuleOperator,
        value,
      };
    });
    bulkMut.mutate(parsed);
  }

  function handleCheck() {
    if (!checkEmail.trim()) {
      toast.error("Enter an email");
      return;
    }
    setCheckResult(null);
    checkMut.mutate(checkEmail);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Exclusion Rules"
        description="Prevent prospects matching specific email/domain/company/title patterns from being added to campaigns."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setBulkOpen(true)}>
              <Upload className="h-4 w-4" /> Bulk Import
            </Button>
            <Button variant="outline" size="sm" onClick={() => setCheckOpen(true)}>
              <ClipboardCheck className="h-4 w-4" /> Check Prospect
            </Button>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" /> Add Rule
            </Button>
          </>
        }
      />

{/* Task 2-b finding 14: explicit error + retry state */}
        {isError ? (
          <ErrorState
            title="Failed to load exclusion rules"
            error={error}
            onRetry={() => refetch()}
          />
        ) : null}

              <Card>
        <CardContent className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search rule values…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={fieldFilter}
              onChange={(e) => setFieldFilter(e.target.value)}
              className="sm:w-40"
            >
              <option value="all">All fields</option>
              {FIELDS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<Ban className="h-6 w-6" />}
              title="No exclusion rules"
              description="Add a rule to start filtering prospects."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Field</TableHead>
                  <TableHead>Operator</TableHead>
                  <TableHead>Value</TableHead>
                  <TableHead className="text-center">Active</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageItems.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Badge variant="outline">{r.field}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{r.operator}</TableCell>
                    <TableCell className="font-mono text-sm">{r.value}</TableCell>
                    <TableCell className="text-center">
                      <Switch
                        checked={r.isActive}
                        onCheckedChange={(checked) =>
                          toggleMut.mutate({ id: r.id, isActive: checked })
                        }
                      />
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(r.createdAt)}</TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" aria-label="Row actions">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                          </TooltipTrigger>
                          <TooltipContent>More actions for this exclusion rule</TooltipContent>
                        </Tooltip>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Actions</DropdownMenuLabel>
                          <DropdownMenuItem destructive onClick={() => setDeleteTarget(r)}>
                            <Trash2 className="h-4 w-4" /> Delete
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => {
                              setCheckEmail("");
                              setCheckResult(null);
                              setCheckOpen(true);
                            }}
                          >
                            <ClipboardCheck className="h-4 w-4" /> Check Prospect
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        
              <Pagination
                page={page}
                pageSize={pageSize}
                total={total}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
              />
            </CardContent>
      </Card>

      {/* Add dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogClose onClose={() => setAddOpen(false)} />
        <DialogHeader>
          <DialogTitle>Add Exclusion Rule</DialogTitle>
          <DialogDescription>
            Prospects matching this rule will be excluded from campaigns.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="rule-field">Field</Label>
              <Select
                id="rule-field"
                value={form.field}
                onChange={(e) => setForm({ ...form, field: e.target.value as RuleField })}
              >
                {FIELDS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rule-op">Operator</Label>
              <Select
                id="rule-op"
                value={form.operator}
                onChange={(e) => setForm({ ...form, operator: e.target.value as RuleOperator })}
              >
                {OPERATORS.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="rule-value">Value</Label>
            <Input
              id="rule-value"
              value={form.value}
              onChange={(e) => setForm({ ...form, value: e.target.value })}
              placeholder={
                form.field === "domain"
                  ? "gmail.com"
                  : form.field === "title"
                    ? "Intern"
                    : form.field === "email"
                      ? "test@example.com"
                      : "Competitor Inc"
              }
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setAddOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleAdd} disabled={createMut.isPending}>
            {createMut.isPending ? "Adding…" : "Add Rule"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Bulk import dialog */}
      <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
        <DialogClose onClose={() => setBulkOpen(false)} />
        <DialogHeader>
          <DialogTitle>Bulk Import Rules</DialogTitle>
          <DialogDescription>
            One rule per line, CSV format: <code>field,operator,value</code>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="bulk-text">Rules</Label>
          <Textarea
            id="bulk-text"
            rows={8}
            value={bulkText}
            onChange={(e) => setBulkText(e.target.value)}
            placeholder={"domain,equals,gmail.com\ncompany,equals,Competitor\ntitle,contains,Intern"}
            className="font-mono text-xs"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setBulkOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleBulk} disabled={bulkMut.isPending}>
            {bulkMut.isPending ? "Importing…" : "Import"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Check prospect dialog */}
      <Dialog open={checkOpen} onOpenChange={setCheckOpen}>
        <DialogClose onClose={() => setCheckOpen(false)} />
        <DialogHeader>
          <DialogTitle>Check Prospect</DialogTitle>
          <DialogDescription>
            Enter an email to see which active exclusion rules match.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="check-email">Email</Label>
            <Input
              id="check-email"
              value={checkEmail}
              onChange={(e) => setCheckEmail(e.target.value)}
              placeholder="prospect@company.com"
            />
          </div>
          {checkResult && (
            <Card>
              <CardHeader className="p-4">
                <div className="flex items-center gap-2">
                  {checkResult.matched ? (
                    <XCircle className="h-5 w-5 text-red-600" />
                  ) : (
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  )}
                  <CardTitle className="text-base">
                    {checkResult.matched ? "Excluded" : "Allowed"}
                  </CardTitle>
                </div>
                <CardDescription>
                  {checkResult.matched
                    ? `Matches ${checkResult.matches.length} rule(s).`
                    : "No exclusion rules matched."}
                </CardDescription>
              </CardHeader>
              {checkResult.matches.length > 0 && (
                <CardContent className="p-4 pt-0">
                  <ScrollArea maxHeightClass="max-h-40">
                    <ul className="space-y-1.5 text-sm">
                      {checkResult.matches.map((m) => (
                        <li
                          key={m.ruleId}
                          className="flex items-center justify-between rounded bg-muted/40 px-2 py-1"
                        >
                          <Badge variant="outline">{m.field}</Badge>
                          <span className="font-mono text-xs">{m.value}</span>
                        </li>
                      ))}
                    </ul>
                  </ScrollArea>
                </CardContent>
              )}
            </Card>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setCheckOpen(false)}>
            Close
          </Button>
          <Button onClick={handleCheck} disabled={checkMut.isPending}>
            {checkMut.isPending ? "Checking…" : "Check"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Delete dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogClose onClose={() => setDeleteTarget(null)} />
        <DialogHeader>
          <DialogTitle>Delete rule?</DialogTitle>
          <DialogDescription>
            Rule <code className="font-mono">{deleteTarget?.field} {deleteTarget?.operator} {deleteTarget?.value}</code> will be permanently removed.
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
