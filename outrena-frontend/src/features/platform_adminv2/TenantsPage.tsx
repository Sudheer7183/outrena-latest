/**
 * TenantsPage.tsx — SUPER_ADMIN tenant management console.
 *
 * Mounted at /platform-admin/tenants inside <PlatformAdminLayout>.
 *
 * Features:
 *   - List all tenants with status badges
 *   - Create a new tenant with direct password (skip_mfa=true, no TOTP prompt)
 *   - Suspend / reactivate tenants
 *
 * Key fix: when the super admin creates a tenant with a password directly,
 * skip_mfa=true is sent to the backend so the tenant admin can log in
 * immediately without being asked to set up an authenticator app.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  Loader2,
  PauseCircle,
  Plus,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { platformApi } from "@/services/apiClient";
import type { TenantRow } from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
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
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────

interface CreateForm {
  slug: string;
  name: string;
  admin_email: string;
  admin_first_name: string;
  admin_last_name: string;
  temporary_password: string;
  send_invitation: boolean;
}

const EMPTY_FORM: CreateForm = {
  slug: "",
  name: "",
  admin_email: "",
  admin_first_name: "",
  admin_last_name: "",
  temporary_password: "",
  send_invitation: false,
};

// ── Status badge ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const s = status.toUpperCase();
  if (s === "ACTIVE")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
        <CheckCircle2 className="h-3 w-3" />
        Active
      </span>
    );
  if (s === "SUSPENDED")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">
        <PauseCircle className="h-3 w-3" />
        Suspended
      </span>
    );
  if (s === "PROVISIONING")
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
        <Loader2 className="h-3 w-3 animate-spin" />
        Provisioning
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
      <XCircle className="h-3 w-3" />
      {status}
    </span>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export function TenantsPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [confirmSlug, setConfirmSlug] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<"suspend" | "reactivate" | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: tenants = [], isLoading, refetch } = useQuery<TenantRow[]>({
    queryKey: ["platform", "tenants"],
    queryFn: () => platformApi.tenants(),
    refetchInterval: 30_000,
  });

  // ── Mutations ─────────────────────────────────────────────────────────────

  const createMutation = useMutation({
    mutationFn: () =>
      platformApi.createTenant({
        slug: form.slug.trim().toLowerCase(),
        name: form.name.trim(),
        admin_email: form.admin_email.trim(),
        admin_first_name: form.admin_first_name.trim(),
        admin_last_name: form.admin_last_name.trim(),
        temporary_password: form.temporary_password || undefined,
        send_invitation: form.send_invitation,
        // When a password is set and no invitation is sent, skip TOTP so
        // the tenant admin can log in immediately — this is the key fix for
        // the "authenticator app on every login" issue.
        skip_mfa: !form.send_invitation && !!form.temporary_password,
      }),
    onSuccess: (data) => {
      toast.success(`Tenant "${data.slug}" created — ${data.url}`);
      qc.invalidateQueries({ queryKey: ["platform", "tenants"] });
      setCreateOpen(false);
      setForm(EMPTY_FORM);
    },
    onError: (err: Error) => {
      toast.error(`Failed to create tenant: ${err.message}`);
    },
  });

  const suspendMutation = useMutation({
    mutationFn: (slug: string) => platformApi.suspendTenant(slug),
    onSuccess: (_, slug) => {
      toast.success(`Tenant "${slug}" suspended.`);
      qc.invalidateQueries({ queryKey: ["platform", "tenants"] });
      setConfirmSlug(null);
    },
    onError: (err: Error) => toast.error(`Failed to suspend: ${err.message}`),
  });

  const reactivateMutation = useMutation({
    mutationFn: (slug: string) => platformApi.reactivateTenant(slug),
    onSuccess: (_, slug) => {
      toast.success(`Tenant "${slug}" reactivated.`);
      qc.invalidateQueries({ queryKey: ["platform", "tenants"] });
      setConfirmSlug(null);
    },
    onError: (err: Error) =>
      toast.error(`Failed to reactivate: ${err.message}`),
  });

  // ── Helpers ───────────────────────────────────────────────────────────────

  function handleCreateSubmit() {
    if (!form.slug || !form.name || !form.admin_email) {
      toast.error("Slug, name, and admin email are required.");
      return;
    }
    if (!form.send_invitation && !form.temporary_password) {
      toast.error(
        "Either set a temporary password or enable Send Invitation — the tenant admin needs a way to log in."
      );
      return;
    }
    createMutation.mutate();
  }

  function openConfirm(slug: string, action: "suspend" | "reactivate") {
    setConfirmSlug(slug);
    setConfirmAction(action);
  }

  function handleConfirm() {
    if (!confirmSlug || !confirmAction) return;
    if (confirmAction === "suspend") suspendMutation.mutate(confirmSlug);
    else reactivateMutation.mutate(confirmSlug);
  }

  const confirmLoading =
    suspendMutation.isPending || reactivateMutation.isPending;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Tenants"
        description="Create and manage workspace tenants on this platform instance."
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="mr-1.5 h-4 w-4" />
              Refresh
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="mr-1.5 h-4 w-4" />
              New Tenant
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            All Tenants ({tenants.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : tenants.length === 0 ? (
            <EmptyState
              icon={<Building2 className="h-8 w-8" />}
              title="No tenants yet"
              description="Click New Tenant to provision the first workspace."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Slug</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-mono text-sm">{t.slug}</TableCell>
                    <TableCell>{t.name}</TableCell>
                    <TableCell>
                      <StatusBadge status={t.status} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {t.plan_name}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDateTime(t.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {t.status === "ACTIVE" ? (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-yellow-600 border-yellow-300 hover:bg-yellow-50"
                          onClick={() => openConfirm(t.slug, "suspend")}
                        >
                          Suspend
                        </Button>
                      ) : t.status === "SUSPENDED" ? (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-green-600 border-green-300 hover:bg-green-50"
                          onClick={() => openConfirm(t.slug, "reactivate")}
                        >
                          Reactivate
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ── Create Tenant Dialog ─────────────────────────────────────────── */}
      <Dialog open={createOpen} onOpenChange={(o) => { setCreateOpen(o); if (!o) setForm(EMPTY_FORM); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create New Tenant</DialogTitle>
            <DialogDescription>
              Provision a new workspace with a TENANT_ADMIN user. Setting a
              password lets the admin log in immediately without an
              authenticator app prompt.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Slug */}
            <div className="space-y-1.5">
              <Label htmlFor="t-slug">
                Slug <span className="text-destructive">*</span>
              </Label>
              <Input
                id="t-slug"
                placeholder="acme"
                value={form.slug}
                onChange={(e) =>
                  setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })
                }
              />
              <p className="text-xs text-muted-foreground">
                Lowercase letters, numbers, hyphens only. This becomes the
                subdomain: <span className="font-mono">{form.slug || "slug"}.outrena.com</span>
              </p>
            </div>

            {/* Name */}
            <div className="space-y-1.5">
              <Label htmlFor="t-name">
                Company Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="t-name"
                placeholder="Acme Corp"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>

            {/* Admin */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="t-fname">First Name</Label>
                <Input
                  id="t-fname"
                  placeholder="Jane"
                  value={form.admin_first_name}
                  onChange={(e) =>
                    setForm({ ...form, admin_first_name: e.target.value })
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="t-lname">Last Name</Label>
                <Input
                  id="t-lname"
                  placeholder="Smith"
                  value={form.admin_last_name}
                  onChange={(e) =>
                    setForm({ ...form, admin_last_name: e.target.value })
                  }
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="t-email">
                Admin Email <span className="text-destructive">*</span>
              </Label>
              <Input
                id="t-email"
                type="email"
                placeholder="admin@acme.com"
                value={form.admin_email}
                onChange={(e) =>
                  setForm({ ...form, admin_email: e.target.value })
                }
              />
            </div>

            {/* Password / invitation toggle */}
            <div className="space-y-1.5">
              <Label htmlFor="t-password">Temporary Password</Label>
              <Input
                id="t-password"
                type="password"
                placeholder="Leave blank to send invitation instead"
                value={form.temporary_password}
                onChange={(e) =>
                  setForm({ ...form, temporary_password: e.target.value })
                }
              />
              <p className="text-xs text-muted-foreground">
                {form.temporary_password
                  ? "The admin can log in immediately with this password. No authenticator app will be required."
                  : "Enable Send Invitation below so Keycloak emails a setup link."}
              </p>
            </div>

            {/* Send invitation toggle — only shown when no password is set */}
            {!form.temporary_password && (
              <div className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">Send Invitation Email</p>
                  <p className="text-xs text-muted-foreground">
                    Keycloak sends a verification + password-setup link to the
                    admin email. The admin will be prompted to set up an
                    authenticator app on first login.
                  </p>
                </div>
                <Switch
                  checked={form.send_invitation}
                  onCheckedChange={(c) =>
                    setForm({ ...form, send_invitation: c })
                  }
                />
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <DialogClose asChild>
              <Button variant="outline" disabled={createMutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              onClick={handleCreateSubmit}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create Tenant
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Suspend / Reactivate Confirm Dialog ──────────────────────────── */}
      <Dialog
        open={confirmSlug !== null}
        onOpenChange={(o) => { if (!o) setConfirmSlug(null); }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {confirmAction === "suspend" ? "Suspend" : "Reactivate"} Tenant?
            </DialogTitle>
            <DialogDescription>
              {confirmAction === "suspend"
                ? `Suspending "${confirmSlug}" will block all logins and API access for this tenant immediately.`
                : `Reactivating "${confirmSlug}" will restore full access for this tenant.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <DialogClose asChild>
              <Button variant="outline" disabled={confirmLoading}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant={confirmAction === "suspend" ? "destructive" : "default"}
              onClick={handleConfirm}
              disabled={confirmLoading}
            >
              {confirmLoading && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {confirmAction === "suspend" ? "Suspend" : "Reactivate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}