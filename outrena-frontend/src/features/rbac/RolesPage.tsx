/**
 * RolesPage.tsx — RBAC role management (TENANT_ADMIN).
 *
 * Fetches `GET /roles` (data-driven roles) + `GET /permissions` (catalog).
 * Renders a table of roles (name, description, # permissions, system badge).
 * Create / edit / delete via dialogs. Permission multi-select grouped by
 * category. System roles cannot be deleted (blocked, 409 if attempted).
 */
import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Lock,
  Pencil,
  Plus,
  Shield,
  Trash2,
  Users2,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import type { Permission, RoleDefinition } from "@/types/common";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { cn } from "@/lib/utils";

const MOCK_ROLES: RoleDefinition[] = [
  {
    id: "r-1",
    name: "REP",
    description: "Front-line rep — runs outreach.",
    is_system: true,
    permissions: [
      { key: "prospects.read", display_name: "View prospects", description: "", category: "Prospecting" },
      { key: "campaigns.write", display_name: "Manage campaigns", description: "", category: "Outreach" },
    ],
  },
  {
    id: "r-2",
    name: "MANAGER",
    description: "Team lead — view all reps.",
    is_system: true,
    permissions: [
      { key: "prospects.read", display_name: "View prospects", description: "", category: "Prospecting" },
      { key: "campaigns.write", display_name: "Manage campaigns", description: "", category: "Outreach" },
      { key: "analytics.read", display_name: "View analytics", description: "", category: "Optimize" },
    ],
  },
  {
    id: "r-3",
    name: "TENANT_ADMIN",
    description: "Full tenant control.",
    is_system: true,
    permissions: [
      { key: "*.*", display_name: "All permissions", description: "", category: "Admin" },
    ],
  },
];

const MOCK_PERMISSIONS: Permission[] = [
  { key: "prospects.read", display_name: "View prospects", description: "Read prospect records.", category: "Prospecting" },
  { key: "prospects.write", display_name: "Edit prospects", description: "Create/update prospects.", category: "Prospecting" },
  { key: "campaigns.read", display_name: "View campaigns", description: "Read campaigns.", category: "Outreach" },
  { key: "campaigns.write", display_name: "Manage campaigns", description: "Create/update campaigns.", category: "Outreach" },
  { key: "sequences.send", display_name: "Send sequences", description: "Schedule + send sequences.", category: "Outreach" },
  { key: "analytics.read", display_name: "View analytics", description: "Read analytics dashboards.", category: "Optimize" },
  { key: "users.manage", display_name: "Manage users", description: "Invite / deactivate users.", category: "Admin" },
  { key: "billing.manage", display_name: "Manage billing", description: "Update subscription.", category: "Admin" },
];

interface RoleForm {
  name: string;
  description: string;
  permissionKeys: string[];
}

export function RolesPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<RoleDefinition | null>(null);
  const [deleting, setDeleting] = useState<RoleDefinition | null>(null);
  const [form, setForm] = useState<RoleForm>({
    name: "",
    description: "",
    permissionKeys: [],
  });

  const { data: roles, isLoading: rolesLoading } = useQuery({
    queryKey: ["roles"],
    queryFn: () => http.get<RoleDefinition[]>("/api/v1/roles"),
  });
  const { data: permissions } = useQuery({
    queryKey: ["permissions"],
    queryFn: () => http.get<Permission[]>("/api/v1/permissions"),
  });

  const roleList = roles ?? MOCK_ROLES;
  const permissionList = permissions ?? MOCK_PERMISSIONS;

  const grouped = useMemo(() => {
    const map = new Map<string, Permission[]>();
    for (const p of permissionList) {
      const list = map.get(p.category) ?? [];
      list.push(p);
      map.set(p.category, list);
    }
    return Array.from(map.entries());
  }, [permissionList]);

  const createMutation = useMutation({
    mutationFn: (body: RoleForm) =>
      http.post<RoleDefinition>("/api/v1/roles", {
        name: body.name,
        description: body.description,
        // BUG-31 FIX: filter out null/undefined permission keys before sending
        permission_keys: (body.permissionKeys ?? []).filter(Boolean),
      }),
    onSuccess: () => {
      toast.success("Role created");
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setCreateOpen(false);
      resetForm();
    },
    onError: () => toast.error("Failed to create role"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<RoleForm> }) =>
      http.put<RoleDefinition>(`/api/v1/roles/${id}`, {
        name: body.name,
        description: body.description,
        // BUG-31 FIX: filter out null/undefined permission keys before sending
        permission_keys: (body.permissionKeys ?? []).filter(Boolean),
      }),
    onSuccess: () => {
      toast.success("Role updated");
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setEditing(null);
    },
    onError: () => toast.error("Failed to update role"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/roles/${id}`),
    onSuccess: () => {
      toast.success("Role deleted");
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setDeleting(null);
    },
    onError: () => toast.error("Failed to delete role (system roles cannot be deleted)"),
  });

  function resetForm() {
    setForm({ name: "", description: "", permissionKeys: [] });
  }

  function openCreate() {
    resetForm();
    setCreateOpen(true);
  }

  function openEdit(role: RoleDefinition) {
    setForm({
      name: role.name,
      description: role.description,
      // BUG-31 FIX: filter null keys from permissions
      permissionKeys: (role.permissions ?? []).map((p) => p?.key).filter(Boolean),
    });
    setEditing(role);
  }

  function togglePermission(key: string) {
    setForm((prev) => ({
      ...prev,
      permissionKeys: prev.permissionKeys.includes(key)
        ? prev.permissionKeys.filter((k) => k !== key)
        : [...prev.permissionKeys, key],
    }));
  }

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return toast.error("Role name is required");
    createMutation.mutate(form);
  }

  function submitUpdate(e: FormEvent) {
    e.preventDefault();
    if (!editing) return;
    updateMutation.mutate({ id: editing.id, body: form });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Roles & Permissions"
        description="Define custom roles with granular permission control. System roles cannot be deleted."
        actions={
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Create role
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Roles</CardTitle>
          <CardDescription>
            {roleList.length} role{roleList.length === 1 ? "" : "s"} defined for this tenant.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {rolesLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : roleList.length === 0 ? (
            <EmptyState
              icon={<Users2 className="h-6 w-6" />}
              title="No roles"
              description="Create your first role to get started."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Permissions</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {roleList.map((role) => (
                  <TableRow key={role.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-muted-foreground" />
                        {role.name}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {role.description}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {role.permissions.length} permission
                        {role.permissions.length === 1 ? "" : "s"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {role.is_system ? (
                        <Badge variant="outline">
                          <Lock className="mr-1 h-3 w-3" />
                          System
                        </Badge>
                      ) : (
                        <Badge variant="default">Custom</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => openEdit(role)}
                              aria-label="Edit role"
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Edit role</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => setDeleting(role)}
                              disabled={role.is_system}
                              aria-label="Delete role"
                              className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{role.is_system ? "System roles cannot be deleted" : "Delete role"}</TooltipContent>
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

      {/* Create / Edit dialog (shared) */}
      <RoleFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Create Role"
        description="Define a new role with custom permissions."
        form={form}
        setForm={setForm}
        grouped={grouped}
        onSubmit={submitCreate}
        onToggle={togglePermission}
        isPending={createMutation.isPending}
      />
      <RoleFormDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        title={`Edit Role: ${editing?.name ?? ""}`}
        description="Update role name, description, or permissions."
        form={form}
        setForm={setForm}
        grouped={grouped}
        onSubmit={submitUpdate}
        onToggle={togglePermission}
        isPending={updateMutation.isPending}
      />

      {/* Delete confirm */}
      <Dialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
      >
        <DialogClose onClose={() => setDeleting(null)} />
        <DialogHeader>
          <DialogTitle>Delete role "{deleting?.name}"?</DialogTitle>
          <DialogDescription>
            Users assigned this role will need to be reassigned. This cannot be
            undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleting(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => deleting && deleteMutation.mutate(deleting.id)}
            disabled={deleteMutation.isPending}
          >
            Delete role
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}

function RoleFormDialog({
  open,
  onOpenChange,
  title,
  description,
  form,
  setForm,
  grouped,
  onSubmit,
  onToggle,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  form: RoleForm;
  setForm: (f: RoleForm) => void;
  grouped: [string, Permission[]][];
  onSubmit: (e: FormEvent) => void;
  onToggle: (key: string) => void;
  isPending: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogClose onClose={() => onOpenChange(false)} />
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="role-name">Name *</Label>
          <Input
            id="role-name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. Sales Manager"
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="role-description">Description</Label>
          <Textarea
            id="role-description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="What can this role do?"
            rows={2}
          />
        </div>
        <div className="space-y-2">
          <Label>Permissions</Label>
          <div className="max-h-72 space-y-3 overflow-y-auto rounded-md border p-3">
            {grouped.map(([category, perms]) => (
              <div key={category} className="space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {category}
                </p>
                <div className="space-y-1">
                  {perms.map((p) => {
                    const checked = form.permissionKeys.includes(p.key);
                    return (
                      <label
                        key={p.key}
                        className={cn(
                          "flex cursor-pointer items-start gap-2 rounded-sm p-2 text-sm transition-colors hover:bg-accent",
                          checked && "bg-accent",
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => onToggle(p.key)}
                          className="mt-0.5 h-4 w-4 rounded border-input"
                        />
                        <div className="min-w-0">
                          <p className="font-medium">{p.display_name}</p>
                          <p className="font-mono text-[10px] text-muted-foreground">
                            {p.key}
                          </p>
                          {p.description && (
                            <p className="text-xs text-muted-foreground">
                              {p.description}
                            </p>
                          )}
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            {form.permissionKeys.length} permission
            {form.permissionKeys.length === 1 ? "" : "s"} selected
          </p>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={isPending}>
            Save
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
