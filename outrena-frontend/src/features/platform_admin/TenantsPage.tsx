/**
 * TenantsPage.tsx — SUPER_ADMIN tenant management.
 *
 * ISSUE-3 FIX: Added "Create Tenant" dialog wired to POST /api/platform/tenants.
 *
 * Fetches `GET /platform/admin/tenants` → table of all tenants (name, slug,
 * status, plan, seats used/limit, created). Search + status filter. Per-row
 * actions (suspend/reactivate). Create Tenant dialog provisions a new tenant
 * end-to-end via POST /api/platform/tenants (not the /admin sub-router —
 * provisioning lives on the base platform router).
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  PauseCircle,
  PlayCircle,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { http, platformApi } from "@/services/apiClient";
import type { TenantRow } from "@/types/common";
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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { NativeSelect as Select } from "@/components/ui/select";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatDate } from "@/lib/utils";

function statusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "success" | "warning" | "outline" {
  switch (status.toLowerCase()) {
    case "active":
      return "success";
    case "suspended":
      return "destructive";
    case "trialing":
      return "warning";
    case "canceled":
      return "secondary";
    default:
      return "outline";
  }
}

interface CreateTenantForm {
  slug: string;
  name: string;
  adminEmail: string;
  adminFirstName: string;
  adminLastName: string;
  temporaryPassword: string;
}

const EMPTY_FORM: CreateTenantForm = {
  slug: "",
  name: "",
  adminEmail: "",
  adminFirstName: "",
  adminLastName: "",
  temporaryPassword: "",
};

interface TenantCreatedResponse {
  slug: string;
  status: string;
  url: string;
}

export function TenantsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<CreateTenantForm>(EMPTY_FORM);

  const { data: tenants, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["platform", "tenants"],
    queryFn: () => platformApi.tenants(),
  });

  const filtered = (tenants ?? []).filter((t) => {
    const matchesSearch =
      !search ||
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.slug.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || t.status.toLowerCase() === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const suspendMutation = useMutation({
    mutationFn: (id: string) => platformApi.suspendTenant(id),
    onSuccess: () => {
      toast.success("Tenant suspended");
      queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
    },
    onError: () => toast.error("Failed to suspend tenant"),
  });

  const reactivateMutation = useMutation({
    mutationFn: (id: string) => platformApi.reactivateTenant(id),
    onSuccess: () => {
      toast.success("Tenant reactivated");
      queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
    },
    onError: () => toast.error("Failed to reactivate tenant"),
  });

  // ISSUE-3 FIX: Create tenant mutation — POST /api/platform/tenants (provisioning endpoint)
  const createMutation = useMutation({
    mutationFn: (body: {
      slug: string;
      name: string;
      admin_email: string;
      admin_first_name: string;
      admin_last_name: string;
      temporary_password?: string;
      send_invitation: boolean;
    }) => http.post<TenantCreatedResponse>("/api/platform/tenants", body),  // ISSUE-3 FIX
    onSuccess: (data) => {
      toast.success(`Tenant "${data.slug}" created`, {
        description: `Accessible at ${data.url}`,
      });
      queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
    },
    onError: (err: unknown) => {
      const detail =
        (err as { detail?: string })?.detail ?? "Tenant creation failed";
      toast.error(detail);
    },
  });

  function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!form.slug.trim() || !form.name.trim() || !form.adminEmail.trim()) {
      toast.error("Slug, company name, and admin email are required");
      return;
    }
    createMutation.mutate({
      slug: form.slug.trim().toLowerCase(),
      name: form.name.trim(),
      admin_email: form.adminEmail.trim(),
      admin_first_name: form.adminFirstName.trim() || "Admin",
      admin_last_name: form.adminLastName.trim() || form.slug.trim(),
      temporary_password: form.temporaryPassword.trim() || undefined,
      send_invitation: true,
    });
  }

  function set(key: keyof CreateTenantForm, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tenants"
        description="Manage all tenant workspaces on the platform."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw
                className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"}
              />
              Refresh
            </Button>
            {/* ISSUE-3 FIX: Create Tenant button */}
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              Create Tenant
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>All Tenants</CardTitle>
          <CardDescription>
            {tenants?.length ?? 0} tenant
            {(tenants?.length ?? 0) === 1 ? "" : "s"} on the platform.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filters */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name or slug…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="sm:w-44"
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="trialing">Trialing</option>
              <option value="suspended">Suspended</option>
              <option value="canceled">Canceled</option>
            </Select>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<Building2 className="h-6 w-6" />}
              title="No tenants found"
              description={
                tenants?.length === 0
                  ? 'No tenants yet. Click "Create Tenant" to provision the first one.'
                  : "Try adjusting your search or filter."
              }
              action={
                tenants?.length === 0 ? (
                  <Button onClick={() => setCreateOpen(true)}>
                    <Plus className="h-4 w-4" />
                    Create first tenant
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tenant</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Seats</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((t: TenantRow) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {t.slug}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(t.status)}>
                        {t.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {t.plan_name}
                    </TableCell>
                    <TableCell className="tabular-nums text-sm">
                      {t.seats_used}/{t.seats_limit}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(t.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {t.status.toLowerCase() === "suspended" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => reactivateMutation.mutate(t.id)}
                          disabled={reactivateMutation.isPending}
                        >
                          <PlayCircle className="h-4 w-4" />
                          Reactivate
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => suspendMutation.mutate(t.id)}
                          disabled={suspendMutation.isPending}
                        >
                          <PauseCircle className="h-4 w-4" />
                          Suspend
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ISSUE-3 FIX: Create Tenant Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogClose onClose={() => setCreateOpen(false)} />
        <DialogHeader>
          <DialogTitle>Create Tenant</DialogTitle>
          <DialogDescription>
            Provision a new tenant workspace end-to-end: database schema,
            migrations, seed data, and initial admin user in Keycloak.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="ct-slug">Slug *</Label>
              <Input
                id="ct-slug"
                placeholder="acme-corp"
                value={form.slug}
                onChange={(e) => set("slug", e.target.value)}
                pattern="[a-z0-9][a-z0-9\-]{1,30}[a-z0-9]"
                title="3–32 lowercase letters, digits, hyphens. Must start and end with letter or digit."
                required
              />
              <p className="text-xs text-muted-foreground">
                Lowercase letters, digits, hyphens. E.g. acme-corp
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ct-name">Company name *</Label>
              <Input
                id="ct-name"
                placeholder="Acme Corp"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="ct-email">Admin email *</Label>
            <Input
              id="ct-email"
              type="email"
              placeholder="admin@acme-corp.com"
              value={form.adminEmail}
              onChange={(e) => set("adminEmail", e.target.value)}
              required
            />
            <p className="text-xs text-muted-foreground">
              A Keycloak user with TENANT_ADMIN role will be created for this
              email.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="ct-first">Admin first name</Label>
              <Input
                id="ct-first"
                placeholder="Jane"
                value={form.adminFirstName}
                onChange={(e) => set("adminFirstName", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ct-last">Admin last name</Label>
              <Input
                id="ct-last"
                placeholder="Smith"
                value={form.adminLastName}
                onChange={(e) => set("adminLastName", e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="ct-pass">
              Temporary password{" "}
              <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="ct-pass"
              type="password"
              placeholder="Auto-generated if blank"
              value={form.temporaryPassword}
              onChange={(e) => set("temporaryPassword", e.target.value)}
              minLength={8}
            />
            <p className="text-xs text-muted-foreground">
              If blank, Keycloak will require the admin to set a password on
              first login. An invitation email is sent automatically.
            </p>
          </div>

          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            <strong>This action provisions a live tenant.</strong> A new
            PostgreSQL schema is created and Alembic migrations run immediately.
            This cannot be undone from the UI.
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Provisioning…" : "Create tenant"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}