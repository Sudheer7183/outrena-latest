/**
 * UserManagementPage.tsx — manage tenant users via Keycloak Admin API.
 *
 * API:
 *   GET    /api/v1/users         → User[]
 *   POST   /api/v1/users         → User (invite)
 *   PUT    /api/v1/users/:id     → User (role change / status)
 *   DELETE /api/v1/users/:id     → { message }
 *
 * Table of users (name, email, role, status, lastLogin). Invite dialog
 * (email + role). Per-row role-change dropdown. Deactivate button.
 *
 * NOTE: this page is gated by ProtectedRoute minimumRole=TENANT_ADMIN.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Mail,
  MoreVertical,
  UserMinus,
  UserPlus,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { Pagination, usePagination } from "@/components/ui/pagination";
import type { Role } from "@/types/common";
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
import { initials, timeAgo } from "@/lib/utils";

interface UserRow {
  id: string;
  name: string;
  email: string;
  role: Role;
  status: "active" | "invited" | "deactivated";
  lastLogin: string | null;
  createdAt: string;
}

interface InviteInput {
  email: string;
  role: Role;
  firstName: string;
  lastName: string;
}

const MOCK_USERS: UserRow[] = [
  {
    id: "u-1",
    name: "Amelia Chen",
    email: "amelia@acme.io",
    role: "TENANT_ADMIN",
    status: "active",
    lastLogin: "2025-02-12T13:42:00Z",
    createdAt: "2024-11-01T10:00:00Z",
  },
  {
    id: "u-2",
    name: "Marcus Lee",
    email: "marcus@acme.io",
    role: "MANAGER",
    status: "active",
    lastLogin: "2025-02-11T18:05:00Z",
    createdAt: "2024-12-10T14:00:00Z",
  },
  {
    id: "u-3",
    name: "Priya Nair",
    email: "priya@acme.io",
    role: "REP",
    status: "active",
    lastLogin: "2025-02-12T09:21:00Z",
    createdAt: "2025-01-05T08:00:00Z",
  },
  {
    id: "u-4",
    name: "Diego Santos",
    email: "diego@acme.io",
    role: "REP",
    status: "invited",
    lastLogin: null,
    createdAt: "2025-02-08T11:30:00Z",
  },
  {
    id: "u-5",
    name: "Yuki Tanaka",
    email: "yuki@acme.io",
    role: "REP",
    status: "deactivated",
    lastLogin: "2025-01-20T17:55:00Z",
    createdAt: "2024-10-15T09:00:00Z",
  },
];

const ROLE_OPTIONS: Role[] = ["REP", "MANAGER", "TENANT_ADMIN"];

function roleVariant(
  role: Role,
): "default" | "secondary" | "destructive" | "success" | "warning" | "outline" {
  switch (role) {
    case "SUPER_ADMIN":
      return "destructive";
    case "TENANT_ADMIN":
      return "default";
    case "MANAGER":
      return "success";
    case "REP":
      return "secondary";
    default:
      return "outline";
  }
}

function statusVariant(
  status: UserRow["status"],
): "success" | "warning" | "secondary" {
  switch (status) {
    case "active":
      return "success";
    case "invited":
      return "warning";
    case "deactivated":
      return "secondary";
  }
}

export function UserManagementPage() {
  const queryClient = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<Role>("REP");
  const [inviteFirstName, setInviteFirstName] = useState("");
  const [inviteLastName, setInviteLastName] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => http.get<UserRow[]>("/api/v1/users"),
  });

  const users = data ?? MOCK_USERS;


  const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: users, initialPageSize: 15 });

  const inviteMutation = useMutation({
    mutationFn: (body: InviteInput) =>
      http.post<UserRow>("/api/v1/users", body),
    onSuccess: () => {
      toast.success(`Invite sent to ${inviteEmail}`);
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setInviteOpen(false);
      setInviteEmail("");
      setInviteRole("REP");
    },
    onError: () => toast.error("Failed to send invite"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<UserRow> }) =>
      http.put<UserRow>(`/api/v1/users/${id}`, body),
    onSuccess: () => {
      toast.success("User updated");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => toast.error("Failed to update user"),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/users/${id}`),
    onSuccess: () => {
      toast.success("User deactivated");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => toast.error("Failed to deactivate user"),
  });

  function handleInvite(e: FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim() || !inviteEmail.includes("@")) {
      toast.error("Enter a valid email");
      return;
    }
    // BUG-30 FIX: include firstName/lastName required by backend UserCreate schema
    inviteMutation.mutate({ email: inviteEmail.trim(), role: inviteRole, firstName: inviteFirstName.trim() || "User", lastName: inviteLastName.trim() || inviteEmail.split("@")[0] });
  }

  function changeRole(u: UserRow, role: Role) {
    updateMutation.mutate({ id: u.id, body: { role } });
  }

  function toggleStatus(u: UserRow) {
    const next: UserRow["status"] =
      u.status === "deactivated" ? "active" : "deactivated";
    updateMutation.mutate({ id: u.id, body: { status: next } });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="User Management"
        description="Invite team members, assign roles, and manage account status. Backed by Keycloak Admin API."
        actions={
          <Button onClick={() => setInviteOpen(true)}>
            <UserPlus className="h-4 w-4" />
            Invite User
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Team Members</CardTitle>
          <CardDescription>
            {users.length} user{users.length === 1 ? "" : "s"} in this tenant.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : users.length === 0 ? (
            <EmptyState
              icon={<UserPlus className="h-6 w-6" />}
              title="No users yet"
              description="Invite your first team member to get started."
              action={
                <Button onClick={() => setInviteOpen(true)}>
                  <UserPlus className="h-4 w-4" />
                  Invite User
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Login</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageItems.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                          {initials(u.name)}
                        </div>
                        <span className="font-medium">{u.name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {u.email}
                    </TableCell>
                    <TableCell>
                      <Badge variant={roleVariant(u.role)}>{u.role}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(u.status)}>{u.status}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {u.lastLogin ? timeAgo(u.lastLogin) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" aria-label="Actions">
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                          </TooltipTrigger>
                          <TooltipContent>More actions for this user</TooltipContent>
                        </Tooltip>
                        <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Change role</DropdownMenuLabel>
                        {ROLE_OPTIONS.map((r) => (
                          <DropdownMenuItem
                            key={r}
                            onClick={() => changeRole(u, r)}
                          >
                            <span className="flex items-center justify-between gap-2">
                              {r}
                              {u.role === r && (
                                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                              )}
                            </span>
                          </DropdownMenuItem>
                        ))}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => toggleStatus(u)}>
                          <UserMinus className="h-3.5 w-3.5" />
                          {u.status === "deactivated"
                            ? "Reactivate user"
                            : "Deactivate user"}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          destructive
                          onClick={() => deactivateMutation.mutate(u.id)}
                        >
                          Permanently delete
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

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogClose onClose={() => setInviteOpen(false)} />
        <DialogHeader>
          <DialogTitle>Invite User</DialogTitle>
          <DialogDescription>
            An invite email will be sent via Keycloak. The invitee will create
            their own password.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleInvite} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email address</Label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="email"
                type="email"
                placeholder="teammate@yourcompany.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="pl-9"
                required
              />
            </div>
          </div>

          {/* BUG-30 FIX: firstName/lastName required by backend */}
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-2">
              <Label htmlFor="firstName">First name</Label>
              <Input
                id="firstName"
                placeholder="Jane"
                value={inviteFirstName}
                onChange={(e) => setInviteFirstName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lastName">Last name</Label>
              <Input
                id="lastName"
                placeholder="Smith"
                value={inviteLastName}
                onChange={(e) => setInviteLastName(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="role">Role</Label>
            <Select
              id="role"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as Role)}
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
            <p className="text-xs text-muted-foreground">
              REP — run outreach · MANAGER — view all reps · TENANT_ADMIN — full
              tenant control.
            </p>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setInviteOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={inviteMutation.isPending}>
              Send invite
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}