/**
 * ExclusionRulesPage.tsx - prospect suppression list (competitors, DNC,
 * blocked domains/emails, etc.) with type cards, add/edit, bulk import,
 * and a Verify Prospect checker.
 *
 * API (verified against app/features/exclusions/router.py + schemas):
 *   GET    /api/v1/exclusion-rules?type=&active_only=   -> ExclusionRuleResponse[]
 *   POST   /api/v1/exclusion-rules                        { type, value, reason?, isActive? }
 *   POST   /api/v1/exclusion-rules/bulk                    { rules: [...] } -> { inserted, skipped }
 *   PUT    /api/v1/exclusion-rules/:id                     { reason?, isActive? } (type/value immutable)
 *   DELETE /api/v1/exclusion-rules/:id
 *   POST   /api/v1/exclusion-rules/check?email=&domain=&company=  -> ExclusionRuleResponse[] (matched rules)
 *
 * CORRECTIONS vs. the previous version (which used a completely invented
 * field/operator shape that doesn't exist on the backend):
 *   - The real model only has `type`, `value`, `reason`, `isActive` - there
 *     is NO `matchMode` (exact/contains/startsWith/endsWith/regex) and NO
 *     `scope` (all/campaign/icp) field anywhere in the schema or DB model.
 *     The Add/Edit form only exposes fields that actually exist.
 *   - `ExclusionRuleUpdate` only allows changing `reason` and `isActive` -
 *     `type`/`value` cannot be edited after creation (enforced here; the
 *     edit dialog shows them read-only with an explanatory note).
 *   - `POST /check` takes email/domain/company as QUERY PARAMS, not a JSON
 *     body, and returns the matched rules directly (not a wrapper object
 *     with `{blocked, matchedRules}`). Fixed both the call and the response
 *     handling; `blocked` is now derived client-side from array length.
 *   - There is no `hitCount` field anywhere in the model or response schema
 *     - EX-4 (hit count per rule) is NOT implemented since the backend does
 *     not track or expose it. No fabricated numbers are shown.
 *   - Bulk import now sends the real `{ rules: [{ type, value, reason,
 *     isActive }] }` shape and reads `{ inserted, skipped }` from the
 *     response, instead of the previous `{ field, operator, value }` /
 *     `{ imported }` shapes that don't match the backend at all.
 *   - (type, value) has a unique DB constraint; duplicate creates are
 *     caught and shown as a friendly error instead of a raw failure.
 *   - check_prospect() only matches rule.type literally equal to "email",
 *     "domain", "company", or "dnc" - "competitor"/"customer" rules are
 *     stored but never matched against anything by the current backend
 *     logic (their RULE_TYPES description implies company-name matching,
 *     but the code doesn't check for those type strings). This is called
 *     out in the UI rather than silently implying they work.
 *
 * EX-1: Rule type cards grouped by type, showing count + active count.
 * EX-2: Add/Edit form with the fields that actually exist (type, value,
 *        reason, isActive) - no fabricated matchMode/scope controls.
 * EX-3: Verify Prospect card (email/domain/company - the only fields the
 *        backend's check endpoint accepts).
 * EX-4: Not implemented - no backend field exists (documented above).
 * EX-5: Bulk import, fixed to the real request/response shape.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  Briefcase,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  Globe,
  Loader2,
  Mail,
  MapPin,
  Plus,
  Search,
  ShieldQuestion,
  Trash2,
  Upload,
  UserX,
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
import { Textarea } from "@/components/ui/textarea";
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

/* Types (aligned with ExclusionRuleResponse) */

interface ExclusionRule {
  id: string;
  type: string;
  value: string;
  reason: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

interface RuleTypeMeta {
  id: string;
  label: string;
  icon: ReactNode;
  color: string;
  description: string;
  matched: boolean; // whether check_prospect() actually checks this type
}

const RULE_TYPES: RuleTypeMeta[] = [
  { id: "competitor", label: "Competitors", icon: <Building2 className="h-4 w-4" />, color: "text-red-600", description: "Competitor companies. Stored for reference; not currently matched by the check endpoint.", matched: false },
  { id: "customer", label: "Customers", icon: <CheckCircle2 className="h-4 w-4" />, color: "text-blue-600", description: "Existing customers. Stored for reference; not currently matched by the check endpoint.", matched: false },
  { id: "dnc", label: "DNC Contacts", icon: <UserX className="h-4 w-4" />, color: "text-orange-600", description: "Do-Not-Contact list - matched against the Email field.", matched: true },
  { id: "domain", label: "Domains", icon: <Globe className="h-4 w-4" />, color: "text-purple-600", description: "Blocked email domains - matched against the Domain field.", matched: true },
  { id: "email", label: "Emails", icon: <Mail className="h-4 w-4" />, color: "text-cyan-600", description: "Specific blocked email addresses - matched against the Email field.", matched: true },
  { id: "company", label: "Companies", icon: <Building2 className="h-4 w-4" />, color: "text-emerald-600", description: "Blocked company names - matched (substring) against the Company field.", matched: true },
  { id: "geography", label: "Geographies", icon: <MapPin className="h-4 w-4" />, color: "text-green-600", description: "Blocked cities, states, or countries. Stored for reference; not currently matched by the check endpoint.", matched: false },
  { id: "industry", label: "Industries", icon: <Briefcase className="h-4 w-4" />, color: "text-amber-600", description: "Blocked industries. Stored for reference; not currently matched by the check endpoint.", matched: false },
  { id: "title", label: "Titles", icon: <UserX className="h-4 w-4" />, color: "text-pink-600", description: "Blocked job titles. Stored for reference; not currently matched by the check endpoint.", matched: false },
];

function ruleTypeMeta(type: string): RuleTypeMeta | undefined {
  return RULE_TYPES.find((rt) => rt.id === type);
}

function normaliseRules(raw: unknown): ExclusionRule[] {
  if (Array.isArray(raw)) return raw as ExclusionRule[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: ExclusionRule[] }).items ?? [];
  return [];
}

const EMPTY_FORM = {
  type: "domain",
  value: "",
  reason: "",
  isActive: true,
};

export function ExclusionRulesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [addOpen, setAddOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<ExclusionRule | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ExclusionRule | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [bulkText, setBulkText] = useState("");

  const [vpEmail, setVpEmail] = useState("");
  const [vpDomain, setVpDomain] = useState("");
  const [vpCompany, setVpCompany] = useState("");
  const [vpResult, setVpResult] = useState<ExclusionRule[] | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["exclusion-rules"],
    queryFn: () =>
      http.get<unknown>("/api/v1/exclusion-rules").then(normaliseRules),
  });

  const rules = data ?? [];

  const filtered = rules.filter((r) => {
    if (filterType !== "all" && r.type !== filterType) return false;
    if (search && !r.value.toLowerCase().includes(search.toLowerCase()))
      return false;
    return true;
  });

  const rulesByType = rules.reduce<Record<string, number>>((acc, r) => {
    acc[r.type] = (acc[r.type] || 0) + 1;
    return acc;
  }, {});

  const createMutation = useMutation({
    mutationFn: (body: typeof EMPTY_FORM) =>
      http.post<ExclusionRule>("/api/v1/exclusion-rules", {
        type: body.type,
        value: body.value,
        reason: body.reason || null,
        isActive: body.isActive,
      }),
    onSuccess: () => {
      toast.success("Rule created");
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
      setAddOpen(false);
      setForm(EMPTY_FORM);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("409") || msg.toLowerCase().includes("unique") || msg.toLowerCase().includes("duplicate")) {
        toast.error("A rule with this type and value already exists");
      } else {
        toast.error("Failed to create rule");
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      reason,
      isActive,
    }: {
      id: string;
      reason: string | null;
      isActive: boolean;
    }) =>
      http.put<ExclusionRule>(`/api/v1/exclusion-rules/${id}`, {
        reason,
        isActive,
      }),
    onSuccess: () => {
      toast.success("Rule updated");
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
      setEditingRule(null);
    },
    onError: () => toast.error("Failed to update rule"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      http.put<ExclusionRule>(`/api/v1/exclusion-rules/${id}`, { isActive }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exclusion-rules"] }),
    onError: () => toast.error("Failed to toggle rule"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/exclusion-rules/${id}`),
    onSuccess: () => {
      toast.success("Rule deleted");
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
      setDeleteTarget(null);
    },
    onError: () => toast.error("Failed to delete rule"),
  });

  const bulkMutation = useMutation({
    mutationFn: (
      parsedRules: { type: string; value: string; reason: string | null; isActive: boolean }[],
    ) =>
      http.post<{ inserted: number; skipped: number }>(
        "/api/v1/exclusion-rules/bulk",
        { rules: parsedRules },
      ),
    onSuccess: (res) => {
      toast.success(
        `Imported ${res.inserted} rule${res.inserted === 1 ? "" : "s"}${
          res.skipped > 0 ? ` (${res.skipped} duplicate${res.skipped === 1 ? "" : "s"} skipped)` : ""
        }`,
      );
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
      setBulkOpen(false);
      setBulkText("");
    },
    onError: () => toast.error("Bulk import failed"),
  });

  const checkMutation = useMutation({
    mutationFn: (vars: { email: string; domain: string; company: string }) => {
      const params = new URLSearchParams();
      if (vars.email) params.set("email", vars.email);
      if (vars.domain) params.set("domain", vars.domain);
      if (vars.company) params.set("company", vars.company);
      return http.post<ExclusionRule[]>(
        `/api/v1/exclusion-rules/check?${params.toString()}`,
        {},
      );
    },
    onSuccess: (matches) => {
      setVpResult(matches);
      if (matches.length > 0) {
        toast.warning(`Blocked - ${matches.length} rule(s) matched`);
      } else {
        toast.success("No exclusion rules matched - prospect is allowed");
      }
      qc.invalidateQueries({ queryKey: ["exclusion-rules"] });
    },
    onError: () => toast.error("Failed to check prospect"),
  });

  function openAdd() {
    setEditingRule(null);
    setForm(EMPTY_FORM);
    setAddOpen(true);
  }

  function openEdit(rule: ExclusionRule) {
    setEditingRule(rule);
    setForm({
      type: rule.type,
      value: rule.value,
      reason: rule.reason ?? "",
      isActive: rule.isActive,
    });
    setAddOpen(true);
  }

  function handleSave() {
    if (editingRule) {
      updateMutation.mutate({
        id: editingRule.id,
        reason: form.reason.trim() || null,
        isActive: form.isActive,
      });
      return;
    }
    if (!form.value.trim()) {
      toast.error("Value is required");
      return;
    }
    createMutation.mutate(form);
  }

  function handleBulk() {
    const lines = bulkText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length === 0) {
      toast.error("Paste at least one rule (type,value,reason)");
      return;
    }
    const parsed = lines.map((line) => {
      const [type, value, ...rest] = line.split(",").map((s) => s.trim());
      return {
        type: type || "domain",
        value: value || "",
        reason: rest.join(",").trim() || null,
        isActive: true,
      };
    }).filter((r) => r.value);
    if (parsed.length === 0) {
      toast.error("No valid rows found - format is type,value,reason");
      return;
    }
    bulkMutation.mutate(parsed);
  }

  function handleCheck() {
    if (!vpEmail.trim() && !vpDomain.trim() && !vpCompany.trim()) {
      toast.error("Enter at least one field to check");
      return;
    }
    setVpResult(null);
    checkMutation.mutate({
      email: vpEmail.trim(),
      domain: vpDomain.trim(),
      company: vpCompany.trim(),
    });
  }

  function clearVerifyForm() {
    setVpEmail("");
    setVpDomain("");
    setVpCompany("");
    setVpResult(null);
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Exclusion Rules"
        description="Block competitors, customers, DNC contacts, domains, emails, and companies from being added to campaigns."
        actions={
          <div className="flex items-center gap-2">
            <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <Upload className="h-4 w-4 mr-1.5" />
                  Bulk Import
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Bulk import exclusion rules</DialogTitle>
                  <DialogDescription>
                    One rule per line: <code className="bg-muted px-1 rounded">type,value,reason</code>{" "}
                    (reason optional). Example:{" "}
                    <code className="bg-muted px-1 rounded">domain,spam.com,known spam</code>
                  </DialogDescription>
                </DialogHeader>
                <Textarea
                  placeholder={"domain,gmail.com\nemail,test@example.com,test account\ncompany,Acme Corp,competitor"}
                  value={bulkText}
                  onChange={(e) => setBulkText(e.target.value)}
                  className="min-h-[200px] font-mono text-xs"
                />
                <DialogFooter>
                  <Button variant="outline" onClick={() => setBulkOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleBulk} disabled={bulkMutation.isPending}>
                    {bulkMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                    ) : null}
                    Import
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog
              open={addOpen}
              onOpenChange={(o) => {
                setAddOpen(o);
                if (!o) {
                  setForm(EMPTY_FORM);
                  setEditingRule(null);
                }
              }}
            >
              <DialogTrigger asChild>
                <Button size="sm" onClick={openAdd}>
                  <Plus className="h-4 w-4 mr-1.5" />
                  Add Rule
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>
                    {editingRule ? "Edit exclusion rule" : "Add exclusion rule"}
                  </DialogTitle>
                  <DialogDescription>
                    {editingRule
                      ? "Type and value cannot be changed after creation - delete and recreate if they need to change."
                      : "Prospects matching this rule will be blocked from import and campaigns."}
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                  <div className="space-y-2">
                    <Label>Type</Label>
                    <Select
                      value={form.type}
                      onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                      disabled={!!editingRule}
                    >
                      {RULE_TYPES.map((rt) => (
                        <option key={rt.id} value={rt.id}>
                          {rt.label}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Value</Label>
                    <Input
                      placeholder="e.g. gmail.com, competitor@email.com, Acme Corp"
                      value={form.value}
                      onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
                      disabled={!!editingRule}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Reason (optional)</Label>
                    <Input
                      placeholder="Why is this excluded?"
                      value={form.reason}
                      onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
                    />
                  </div>
                  <div className="flex items-center justify-between rounded-md border p-3">
                    <Label>Active</Label>
                    <Switch
                      checked={form.isActive}
                      onCheckedChange={(c) => setForm((f) => ({ ...f, isActive: c }))}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setAddOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={createMutation.isPending || updateMutation.isPending}
                  >
                    {editingRule ? "Save changes" : "Add rule"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Failed to load exclusion rules.</p>
            <Button onClick={() => refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : (
        <>
          {/* EX-1: type cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-9 gap-3">
            {RULE_TYPES.map((rt) => (
              <Card key={rt.id} className="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className={rt.color}>{rt.icon}</span>
                  <span className="text-xs font-medium text-muted-foreground truncate">
                    {rt.label}
                  </span>
                </div>
                <p className="text-2xl font-bold">{rulesByType[rt.id] || 0}</p>
                {!rt.matched && (
                  <p className="text-[9px] text-muted-foreground mt-0.5">not matched</p>
                )}
              </Card>
            ))}
          </div>

          <Card className="border-amber-200 bg-amber-50/50">
            <CardContent className="py-3 flex items-center gap-3">
              <Ban className="h-5 w-5 text-amber-600 shrink-0" />
              <p className="text-sm text-amber-900">
                <strong>{rules.length}</strong> exclusion rule{rules.length === 1 ? "" : "s"} configured ·{" "}
                <strong>{rules.filter((r) => r.isActive).length}</strong> active
              </p>
            </CardContent>
          </Card>

          {/* Filters */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex-1 min-w-[200px] relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search rules by value..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="sm:w-56"
            >
              <option value="all">All types</option>
              {RULE_TYPES.map((rt) => (
                <option key={rt.id} value={rt.id}>
                  {rt.label}
                </option>
              ))}
            </Select>
          </div>

          {/* Rules grouped by type */}
          {filtered.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Ban className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
                <p className="text-muted-foreground">
                  {rules.length > 0
                    ? "No rules match your filters."
                    : 'No exclusion rules yet. Click "Add Rule" to create your first one.'}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {RULE_TYPES.map((rt) => {
                const typeRules = filtered.filter((r) => r.type === rt.id);
                if (typeRules.length === 0) return null;
                return (
                  <Card key={rt.id}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center gap-2">
                        <span className={rt.color}>{rt.icon}</span>
                        <CardTitle className="text-base">{rt.label}</CardTitle>
                        <Badge variant="secondary" className="ml-1">
                          {typeRules.length}
                        </Badge>
                      </div>
                      <CardDescription className="text-xs">{rt.description}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {typeRules.map((rule) => (
                        <div
                          key={rule.id}
                          className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                            rule.isActive ? "border-border bg-card" : "border-border bg-muted/50 opacity-60"
                          }`}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <code className="text-sm font-mono bg-muted px-2 py-0.5 rounded">
                                {rule.value}
                              </code>
                            </div>
                            {rule.reason && (
                              <p className="text-xs text-muted-foreground mt-1">{rule.reason}</p>
                            )}
                          </div>
                          <Switch
                            checked={rule.isActive}
                            onCheckedChange={() =>
                              toggleMutation.mutate({ id: rule.id, isActive: !rule.isActive })
                            }
                          />
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8"
                            onClick={() => openEdit(rule)}
                          >
                            <ClipboardCheck className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-red-500 hover:text-red-600"
                            onClick={() => setDeleteTarget(rule)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* EX-3: Verify Prospect */}
      <Card className="border-violet-200">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <ShieldQuestion className="h-5 w-5 text-violet-600" />
            <div>
              <CardTitle className="text-base">Verify Prospect</CardTitle>
              <CardDescription className="text-xs">
                Check a prospect against all active exclusion rules before importing.
                Only Email, Domain, and Company are checked (the backend's check
                endpoint does not accept title or name fields).
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1">
                <Mail className="h-3 w-3" /> Email
              </Label>
              <Input
                type="email"
                value={vpEmail}
                onChange={(e) => setVpEmail(e.target.value)}
                placeholder="prospect@example.com"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1">
                <Globe className="h-3 w-3" /> Domain
              </Label>
              <Input
                value={vpDomain}
                onChange={(e) => setVpDomain(e.target.value)}
                placeholder="example.com"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1">
                <Building2 className="h-3 w-3" /> Company
              </Label>
              <Input
                value={vpCompany}
                onChange={(e) => setVpCompany(e.target.value)}
                placeholder="Acme Inc."
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleCheck} disabled={checkMutation.isPending}>
              {checkMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              ) : (
                <ShieldQuestion className="h-3.5 w-3.5 mr-1.5" />
              )}
              Check
            </Button>
            <Button variant="outline" onClick={clearVerifyForm}>
              Clear
            </Button>
          </div>

          {vpResult !== null && (
            <div
              className={`rounded-md p-3 text-sm ${
                vpResult.length > 0
                  ? "bg-red-50 text-red-800 border border-red-200"
                  : "bg-emerald-50 text-emerald-800 border border-emerald-200"
              }`}
            >
              {vpResult.length > 0 ? (
                <>
                  <p className="font-medium mb-2">
                    Blocked - {vpResult.length} rule{vpResult.length === 1 ? "" : "s"} matched
                  </p>
                  <div className="space-y-1">
                    {vpResult.map((r) => (
                      <div key={r.id} className="flex items-center gap-2 text-xs">
                        <span className={ruleTypeMeta(r.type)?.color ?? ""}>
                          {ruleTypeMeta(r.type)?.icon}
                        </span>
                        <Badge variant="outline" className="text-[10px]">
                          {ruleTypeMeta(r.type)?.label ?? r.type}
                        </Badge>
                        <code className="font-mono">{r.value}</code>
                        {r.reason && <span className="text-muted-foreground">- {r.reason}</span>}
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="font-medium">No exclusion rules matched - prospect is allowed.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete exclusion rule?</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `"${deleteTarget.value}" (${ruleTypeMeta(deleteTarget.type)?.label ?? deleteTarget.type}) will be permanently removed. This action cannot be undone.`
                : "This exclusion rule will be permanently removed."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* Retained for empty-state icon prop-shape parity with sibling pages. */
void EmptyState;