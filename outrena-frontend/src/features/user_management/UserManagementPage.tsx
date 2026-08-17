// /**
//  * UserManagementPage.tsx — manage tenant users via Keycloak Admin API.
//  *
//  * API:
//  *   GET    /api/v1/users         → User[]
//  *   POST   /api/v1/users         → User (invite)
//  *   PUT    /api/v1/users/:id     → User (role change / status)
//  *   DELETE /api/v1/users/:id     → { message }
//  *
//  * Table of users (name, email, role, status, lastLogin). Invite dialog
//  * (email + role). Per-row role-change dropdown. Deactivate button.
//  *
//  * NOTE: this page is gated by ProtectedRoute minimumRole=TENANT_ADMIN.
//  */
// import { useState } from "react";
// import type { FormEvent } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   CheckCircle2,
//   Mail,
//   MoreVertical,
//   UserMinus,
//   UserPlus,
// } from "lucide-react";
// import { toast } from "sonner";
// import { http } from "@/services/apiClient";
// import { Pagination, usePagination } from "@/components/ui/pagination";
// import type { Role } from "@/types/common";
// import { PageHeader } from "@/components/ui/page-header";
// import { Button } from "@/components/ui/button";
// import {
//   Card,
//   CardContent,
//   CardDescription,
//   CardHeader,
//   CardTitle,
// } from "@/components/ui/card";
// import {
//   Table,
//   TableBody,
//   TableCell,
//   TableHead,
//   TableHeader,
//   TableRow,
// } from "@/components/ui/table";
// import { Badge } from "@/components/ui/badge";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { NativeSelect as Select } from "@/components/ui/select";
// import { Skeleton } from "@/components/ui/skeleton";
// import {
//   Dialog,
//   DialogClose,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
// } from "@/components/ui/dialog";
// import {
//   DropdownMenu,
//   DropdownMenuItem,
//   DropdownMenuLabel,
//   DropdownMenuSeparator,
//   DropdownMenuTrigger,
//   DropdownMenuContent,
// } from "@/components/ui/dropdown-menu";
// import {
//   Tooltip,
//   TooltipContent,
//   TooltipTrigger,
// } from "@/components/ui/tooltip";
// import { EmptyState } from "@/components/ui/empty-state";
// import { initials, timeAgo } from "@/lib/utils";

// interface UserRow {
//   id: string;
//   name: string;
//   email: string;
//   role: Role;
//   status: "active" | "invited" | "deactivated";
//   lastLogin: string | null;
//   createdAt: string;
// }

// interface InviteInput {
//   email: string;
//   role: Role;
//   firstName: string;
//   lastName: string;
// }

// const MOCK_USERS: UserRow[] = [
//   {
//     id: "u-1",
//     name: "Amelia Chen",
//     email: "amelia@acme.io",
//     role: "TENANT_ADMIN",
//     status: "active",
//     lastLogin: "2025-02-12T13:42:00Z",
//     createdAt: "2024-11-01T10:00:00Z",
//   },
//   {
//     id: "u-2",
//     name: "Marcus Lee",
//     email: "marcus@acme.io",
//     role: "MANAGER",
//     status: "active",
//     lastLogin: "2025-02-11T18:05:00Z",
//     createdAt: "2024-12-10T14:00:00Z",
//   },
//   {
//     id: "u-3",
//     name: "Priya Nair",
//     email: "priya@acme.io",
//     role: "REP",
//     status: "active",
//     lastLogin: "2025-02-12T09:21:00Z",
//     createdAt: "2025-01-05T08:00:00Z",
//   },
//   {
//     id: "u-4",
//     name: "Diego Santos",
//     email: "diego@acme.io",
//     role: "REP",
//     status: "invited",
//     lastLogin: null,
//     createdAt: "2025-02-08T11:30:00Z",
//   },
//   {
//     id: "u-5",
//     name: "Yuki Tanaka",
//     email: "yuki@acme.io",
//     role: "REP",
//     status: "deactivated",
//     lastLogin: "2025-01-20T17:55:00Z",
//     createdAt: "2024-10-15T09:00:00Z",
//   },
// ];

// const ROLE_OPTIONS: Role[] = ["REP", "MANAGER", "TENANT_ADMIN"];

// function roleVariant(
//   role: Role,
// ): "default" | "secondary" | "destructive" | "success" | "warning" | "outline" {
//   switch (role) {
//     case "SUPER_ADMIN":
//       return "destructive";
//     case "TENANT_ADMIN":
//       return "default";
//     case "MANAGER":
//       return "success";
//     case "REP":
//       return "secondary";
//     default:
//       return "outline";
//   }
// }

// function statusVariant(
//   status: UserRow["status"],
// ): "success" | "warning" | "secondary" {
//   switch (status) {
//     case "active":
//       return "success";
//     case "invited":
//       return "warning";
//     case "deactivated":
//       return "secondary";
//   }
// }

// export function UserManagementPage() {
//   const queryClient = useQueryClient();
//   const [inviteOpen, setInviteOpen] = useState(false);
//   const [inviteEmail, setInviteEmail] = useState("");
//   const [inviteRole, setInviteRole] = useState<Role>("REP");
//   const [inviteFirstName, setInviteFirstName] = useState("");
//   const [inviteLastName, setInviteLastName] = useState("");

//   const { data, isLoading } = useQuery({
//     queryKey: ["users"],
//     queryFn: () => http.get<UserRow[]>("/api/v1/users"),
//   });

//   const users = data ?? MOCK_USERS;


//   const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: users, initialPageSize: 15 });

//   const inviteMutation = useMutation({
//     mutationFn: (body: InviteInput) =>
//       http.post<UserRow>("/api/v1/users", body),
//     onSuccess: () => {
//       toast.success(`Invite sent to ${inviteEmail}`);
//       queryClient.invalidateQueries({ queryKey: ["users"] });
//       setInviteOpen(false);
//       setInviteEmail("");
//       setInviteRole("REP");
//     },
//     onError: () => toast.error("Failed to send invite"),
//   });

//   const updateMutation = useMutation({
//     mutationFn: ({ id, body }: { id: string; body: Partial<UserRow> }) =>
//       http.put<UserRow>(`/api/v1/users/${id}`, body),
//     onSuccess: () => {
//       toast.success("User updated");
//       queryClient.invalidateQueries({ queryKey: ["users"] });
//     },
//     onError: () => toast.error("Failed to update user"),
//   });

//   const deactivateMutation = useMutation({
//     mutationFn: (id: string) => http.delete(`/api/v1/users/${id}`),
//     onSuccess: () => {
//       toast.success("User deactivated");
//       queryClient.invalidateQueries({ queryKey: ["users"] });
//     },
//     onError: () => toast.error("Failed to deactivate user"),
//   });

//   function handleInvite(e: FormEvent) {
//     e.preventDefault();
//     if (!inviteEmail.trim() || !inviteEmail.includes("@")) {
//       toast.error("Enter a valid email");
//       return;
//     }
//     // BUG-30 FIX: include firstName/lastName required by backend UserCreate schema
//     inviteMutation.mutate({ email: inviteEmail.trim(), role: inviteRole, firstName: inviteFirstName.trim() || "User", lastName: inviteLastName.trim() || inviteEmail.split("@")[0] });
//   }

//   function changeRole(u: UserRow, role: Role) {
//     updateMutation.mutate({ id: u.id, body: { role } });
//   }

//   function toggleStatus(u: UserRow) {
//     const next: UserRow["status"] =
//       u.status === "deactivated" ? "active" : "deactivated";
//     updateMutation.mutate({ id: u.id, body: { status: next } });
//   }

//   return (
//     <div className="space-y-6">
//       <PageHeader
//         title="User Management"
//         description="Invite team members, assign roles, and manage account status. Backed by Keycloak Admin API."
//         actions={
//           <Button onClick={() => setInviteOpen(true)}>
//             <UserPlus className="h-4 w-4" />
//             Invite User
//           </Button>
//         }
//       />

//       <Card>
//         <CardHeader>
//           <CardTitle>Team Members</CardTitle>
//           <CardDescription>
//             {users.length} user{users.length === 1 ? "" : "s"} in this tenant.
//           </CardDescription>
//         </CardHeader>
//         <CardContent>
//           {isLoading ? (
//             <div className="space-y-2">
//               {Array.from({ length: 5 }).map((_, i) => (
//                 <Skeleton key={i} className="h-12 w-full" />
//               ))}
//             </div>
//           ) : users.length === 0 ? (
//             <EmptyState
//               icon={<UserPlus className="h-6 w-6" />}
//               title="No users yet"
//               description="Invite your first team member to get started."
//               action={
//                 <Button onClick={() => setInviteOpen(true)}>
//                   <UserPlus className="h-4 w-4" />
//                   Invite User
//                 </Button>
//               }
//             />
//           ) : (
//             <Table>
//               <TableHeader>
//                 <TableRow>
//                   <TableHead>Name</TableHead>
//                   <TableHead>Email</TableHead>
//                   <TableHead>Role</TableHead>
//                   <TableHead>Status</TableHead>
//                   <TableHead>Last Login</TableHead>
//                   <TableHead className="text-right">Actions</TableHead>
//                 </TableRow>
//               </TableHeader>
//               <TableBody>
//                 {pageItems.map((u) => (
//                   <TableRow key={u.id}>
//                     <TableCell>
//                       <div className="flex items-center gap-3">
//                         <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
//                           {initials(u.name)}
//                         </div>
//                         <span className="font-medium">{u.name}</span>
//                       </div>
//                     </TableCell>
//                     <TableCell className="text-muted-foreground">
//                       {u.email}
//                     </TableCell>
//                     <TableCell>
//                       <Badge variant={roleVariant(u.role)}>{u.role}</Badge>
//                     </TableCell>
//                     <TableCell>
//                       <Badge variant={statusVariant(u.status)}>{u.status}</Badge>
//                     </TableCell>
//                     <TableCell className="text-xs text-muted-foreground">
//                       {u.lastLogin ? timeAgo(u.lastLogin) : "—"}
//                     </TableCell>
//                     <TableCell className="text-right">
//                       <DropdownMenu>
//                         <Tooltip>
//                           <TooltipTrigger asChild>
//                             <DropdownMenuTrigger asChild>
//                               <Button variant="ghost" size="icon" aria-label="Actions">
//                                 <MoreVertical className="h-4 w-4" />
//                               </Button>
//                             </DropdownMenuTrigger>
//                           </TooltipTrigger>
//                           <TooltipContent>More actions for this user</TooltipContent>
//                         </Tooltip>
//                         <DropdownMenuContent align="end">
//                         <DropdownMenuLabel>Change role</DropdownMenuLabel>
//                         {ROLE_OPTIONS.map((r) => (
//                           <DropdownMenuItem
//                             key={r}
//                             onClick={() => changeRole(u, r)}
//                           >
//                             <span className="flex items-center justify-between gap-2">
//                               {r}
//                               {u.role === r && (
//                                 <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
//                               )}
//                             </span>
//                           </DropdownMenuItem>
//                         ))}
//                         <DropdownMenuSeparator />
//                         <DropdownMenuItem onClick={() => toggleStatus(u)}>
//                           <UserMinus className="h-3.5 w-3.5" />
//                           {u.status === "deactivated"
//                             ? "Reactivate user"
//                             : "Deactivate user"}
//                         </DropdownMenuItem>
//                         <DropdownMenuItem
//                           destructive
//                           onClick={() => deactivateMutation.mutate(u.id)}
//                         >
//                           Permanently delete
//                         </DropdownMenuItem>
//                         </DropdownMenuContent>
//                       </DropdownMenu>
//                     </TableCell>
//                   </TableRow>
//                 ))}
//               </TableBody>
//             </Table>
//           )}
        
//               <Pagination
//                 page={page}
//                 pageSize={pageSize}
//                 total={total}
//                 onPageChange={setPage}
//                 onPageSizeChange={setPageSize}
//               />
//             </CardContent>
//       </Card>

//       <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
//         <DialogClose onClose={() => setInviteOpen(false)} />
//         <DialogHeader>
//           <DialogTitle>Invite User</DialogTitle>
//           <DialogDescription>
//             An invite email will be sent via Keycloak. The invitee will create
//             their own password.
//           </DialogDescription>
//         </DialogHeader>
//         <form onSubmit={handleInvite} className="space-y-4">
//           <div className="space-y-2">
//             <Label htmlFor="email">Email address</Label>
//             <div className="relative">
//               <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
//               <Input
//                 id="email"
//                 type="email"
//                 placeholder="teammate@yourcompany.com"
//                 value={inviteEmail}
//                 onChange={(e) => setInviteEmail(e.target.value)}
//                 className="pl-9"
//                 required
//               />
//             </div>
//           </div>

//           {/* BUG-30 FIX: firstName/lastName required by backend */}
//           <div className="grid grid-cols-2 gap-2">
//             <div className="space-y-2">
//               <Label htmlFor="firstName">First name</Label>
//               <Input
//                 id="firstName"
//                 placeholder="Jane"
//                 value={inviteFirstName}
//                 onChange={(e) => setInviteFirstName(e.target.value)}
//               />
//             </div>
//             <div className="space-y-2">
//               <Label htmlFor="lastName">Last name</Label>
//               <Input
//                 id="lastName"
//                 placeholder="Smith"
//                 value={inviteLastName}
//                 onChange={(e) => setInviteLastName(e.target.value)}
//               />
//             </div>
//           </div>

//           <div className="space-y-2">
//             <Label htmlFor="role">Role</Label>
//             <Select
//               id="role"
//               value={inviteRole}
//               onChange={(e) => setInviteRole(e.target.value as Role)}
//             >
//               {ROLE_OPTIONS.map((r) => (
//                 <option key={r} value={r}>
//                   {r}
//                 </option>
//               ))}
//             </Select>
//             <p className="text-xs text-muted-foreground">
//               REP — run outreach · MANAGER — view all reps · TENANT_ADMIN — full
//               tenant control.
//             </p>
//           </div>

//           <DialogFooter>
//             <Button
//               type="button"
//               variant="outline"
//               onClick={() => setInviteOpen(false)}
//             >
//               Cancel
//             </Button>
//             <Button type="submit" disabled={inviteMutation.isPending}>
//               Send invite
//             </Button>
//           </DialogFooter>
//         </form>
//       </Dialog>
//     </div>
//   );
// }

/**
 * UserManagementPage.tsx — manage tenant users via Keycloak Admin API.
 *
 * Bugs fixed in this revision:
 *
 * BUG-1 (PAGE REFRESH — primary): The invite dialog used <Dialog> without
 *   <DialogContent>. The <form onSubmit> was placed naked inside <Dialog>
 *   with a rogue <DialogClose onClose={...}> prop (invalid on Radix) and no
 *   portal boundary. Result: form submission triggered a real browser
 *   navigation / page reload instead of calling handleInvite. Fixed by
 *   wrapping all dialog children inside proper <DialogContent>.
 *
 * BUG-2 (GET response shape mismatch): Backend GET /api/v1/users returns
 *   UserResponse[] with fields {id, email, firstName, lastName, role, enabled,
 *   tenant_slug, displayName}. Frontend UserRow expected {name, status,
 *   lastLogin} which don't exist, so the query always fell back to MOCK_USERS.
 *   Fixed: UserRow now matches UserResponse exactly; name/status are derived
 *   at render time from firstName+lastName and enabled fields.
 *
 * BUG-3 (invite never sent): handleInvite never set sendInvitation:true in
 *   the POST body. Backend defaulted to false → Keycloak created the user
 *   silently without a VERIFY_EMAIL required action and without sending an
 *   invite email. Fixed: sendInvitation is now always true for invites; a
 *   "Set password now" toggle allows setting a temporaryPassword instead.
 *
 * BUG-4 (role update body shape): PUT /api/v1/users/:id was sent with
 *   {status: "deactivated"} but UserUpdate has no status field — it uses
 *   {enabled: boolean}. Fixed toggleStatus to send {enabled: boolean}.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Loader2,
  Mail,
  MoreVertical,
  ShieldCheck,
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
import { NativeSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { EmptyState } from "@/components/ui/empty-state";
import { initials } from "@/lib/utils";

// ─── Types — matches backend UserResponse exactly ────────────────────────────

interface UserResponse {
  id: string;
  email: string | null;
  firstName: string | null;
  lastName: string | null;
  role: Role | null;
  enabled: boolean;
  tenant_slug: string | null;
  displayName: string | null;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function displayName(u: UserResponse): string {
  if (u.displayName) return u.displayName;
  const full = [u.firstName, u.lastName].filter(Boolean).join(" ");
  return full || u.email || "—";
}

function userStatus(u: UserResponse): "active" | "deactivated" {
  return u.enabled ? "active" : "deactivated";
}

const ROLE_OPTIONS: Role[] = ["REP", "MANAGER", "TENANT_ADMIN"];

function roleVariant(role: Role | null): "default" | "secondary" | "destructive" | "outline" {
  switch (role) {
    case "SUPER_ADMIN":    return "destructive";
    case "TENANT_ADMIN":   return "default";
    case "MANAGER":        return "secondary";
    case "REP":            return "secondary";
    default:               return "outline";
  }
}

function statusVariant(enabled: boolean): "default" | "secondary" {
  return enabled ? "default" : "secondary";
}

// ─── Component ───────────────────────────────────────────────────────────────

export function UserManagementPage() {
  const queryClient = useQueryClient();

  // ── Invite dialog state ───────────────────────────────────────────────────
  const [inviteOpen, setInviteOpen]           = useState(false);
  const [inviteEmail, setInviteEmail]         = useState("");
  const [inviteFirstName, setInviteFirstName] = useState("");
  const [inviteLastName, setInviteLastName]   = useState("");
  const [inviteRole, setInviteRole]           = useState<Role>("REP");
  // "Set password now" toggle — when true, send a temporaryPassword instead
  // of an invite email (useful for internal/SSO-less tenants).
  const [setPasswordNow, setSetPasswordNow]   = useState(false);
  const [tempPassword, setTempPassword]       = useState("");

  // ── Server state ──────────────────────────────────────────────────────────
  // BUG-2 FIX: useQuery now expects list[UserResponse] (the actual backend shape).
  const { data, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => http.get<UserResponse[]>("/api/v1/users"),
  });

  const users: UserResponse[] = data ?? [];

  const { page, pageSize, total, pageItems, setPage, setPageSize } =
    usePagination({ items: users, initialPageSize: 15 });

  // ── Mutations ─────────────────────────────────────────────────────────────

  const inviteMutation = useMutation({
    mutationFn: (body: {
      email: string;
      firstName: string;
      lastName: string;
      role: Role;
      sendInvitation: boolean;
      temporaryPassword?: string;
    }) => http.post<UserResponse>("/api/v1/users", body),
    onSuccess: (_data, vars) => {
      toast.success(
        vars.sendInvitation
          ? `Invite sent to ${vars.email}`
          : `User ${vars.email} created`,
      );
      queryClient.invalidateQueries({ queryKey: ["users"] });
      closeInviteDialog();
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to create user";
      toast.error(msg);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { role?: Role; enabled?: boolean } }) =>
      http.put<UserResponse>(`/api/v1/users/${id}`, body),
    onSuccess: () => {
      toast.success("User updated");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => toast.error("Failed to update user"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/users/${id}`),
    onSuccess: () => {
      toast.success("User deleted");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => toast.error("Failed to delete user"),
  });

  // ── Handlers ─────────────────────────────────────────────────────────────

  function closeInviteDialog() {
    setInviteOpen(false);
    setInviteEmail("");
    setInviteFirstName("");
    setInviteLastName("");
    setInviteRole("REP");
    setSetPasswordNow(false);
    setTempPassword("");
  }

  // BUG-1 FIX: handleInvite is called from a Button onClick (not form onSubmit)
  // so there is no HTML form submission to cause a page reload.
  // BUG-3 FIX: sendInvitation is true by default; temporaryPassword only sent
  // when the "set password now" toggle is active.
  function handleInvite() {
    const email = inviteEmail.trim();
    if (!email || !email.includes("@")) {
      toast.error("Enter a valid email address");
      return;
    }
    if (!inviteFirstName.trim()) {
      toast.error("First name is required");
      return;
    }
    if (!inviteLastName.trim()) {
      toast.error("Last name is required");
      return;
    }
    if (setPasswordNow && tempPassword.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }

    inviteMutation.mutate({
      email,
      firstName: inviteFirstName.trim(),
      lastName:  inviteLastName.trim(),
      role:      inviteRole,
      // BUG-3 FIX: always send sendInvitation unless using password mode
      sendInvitation: !setPasswordNow,
      temporaryPassword: setPasswordNow ? tempPassword : undefined,
    });
  }

  function changeRole(u: UserResponse, role: Role) {
    updateMutation.mutate({ id: u.id, body: { role } });
  }

  // BUG-4 FIX: send {enabled: boolean}, not {status: string} — UserUpdate
  // has no status field; backend uses enabled:bool to activate/deactivate.
  function toggleEnabled(u: UserResponse) {
    updateMutation.mutate({ id: u.id, body: { enabled: !u.enabled } });
  }

  // ── Render ────────────────────────────────────────────────────────────────

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
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageItems.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                          {initials(displayName(u))}
                        </div>
                        <span className="font-medium">{displayName(u)}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {u.email ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={roleVariant(u.role)}>
                        {u.role ?? "—"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(u.enabled)}>
                        {userStatus(u)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" aria-label="User actions">
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                          </TooltipTrigger>
                          <TooltipContent>User actions</TooltipContent>
                        </Tooltip>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Change role</DropdownMenuLabel>
                          {ROLE_OPTIONS.map((r) => (
                            <DropdownMenuItem
                              key={r}
                              onClick={() => changeRole(u, r)}
                            >
                              <span className="flex items-center justify-between gap-2 w-full">
                                {r}
                                {u.role === r && (
                                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                                )}
                              </span>
                            </DropdownMenuItem>
                          ))}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => toggleEnabled(u)}>
                            <UserMinus className="h-3.5 w-3.5" />
                            {u.enabled ? "Deactivate user" : "Reactivate user"}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            destructive
                            onClick={() => deleteMutation.mutate(u.id)}
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

      {/*
        BUG-1 FIX: All dialog children are now inside <DialogContent> so
        Radix mounts a proper portal overlay and no HTML <form> is rendered
        in the main page DOM.  The submit button uses onClick={handleInvite}
        (not type="submit") so there is no form submission event to intercept.
      */}
      <Dialog open={inviteOpen} onOpenChange={(o) => { if (!o) closeInviteDialog(); else setInviteOpen(true); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Invite User</DialogTitle>
            <DialogDescription>
              {setPasswordNow
                ? "Create the user with a temporary password they must change on first login."
                : "An invite email will be sent via Keycloak. The invitee sets their own password."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-1">
            {/* Email */}
            <div className="space-y-2">
              <Label htmlFor="inv-email">Email address *</Label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="inv-email"
                  type="email"
                  placeholder="teammate@yourcompany.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>

            {/* Name */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="inv-first">First name *</Label>
                <Input
                  id="inv-first"
                  placeholder="Jane"
                  value={inviteFirstName}
                  onChange={(e) => setInviteFirstName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="inv-last">Last name *</Label>
                <Input
                  id="inv-last"
                  placeholder="Smith"
                  value={inviteLastName}
                  onChange={(e) => setInviteLastName(e.target.value)}
                />
              </div>
            </div>

            {/* Role */}
            <div className="space-y-2">
              <Label htmlFor="inv-role">Role</Label>
              <NativeSelect
                id="inv-role"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as Role)}
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </NativeSelect>
              <p className="text-xs text-muted-foreground">
                REP — run outreach · MANAGER — view all reps · TENANT_ADMIN — full tenant control.
              </p>
            </div>

            {/* Password toggle */}
            <div className="flex items-center gap-3 rounded-lg border p-3 bg-muted/30">
              <ShieldCheck className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="flex-1 text-sm">
                <p className="font-medium">Set password now</p>
                <p className="text-xs text-muted-foreground">
                  Skip invite email; set a temporary password instead.
                </p>
              </div>
              <button
                type="button"
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                  setPasswordNow ? "bg-primary" : "bg-muted-foreground/30"
                }`}
                onClick={() => { setSetPasswordNow((v) => !v); setTempPassword(""); }}
                role="switch"
                aria-checked={setPasswordNow}
              >
                <span
                  className={`inline-block h-3 w-3 rounded-full bg-white transition-transform mx-1 ${
                    setPasswordNow ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            {setPasswordNow && (
              <div className="space-y-2">
                <Label htmlFor="inv-password">Temporary password (min 8 chars)</Label>
                <Input
                  id="inv-password"
                  type="password"
                  placeholder="••••••••"
                  value={tempPassword}
                  onChange={(e) => setTempPassword(e.target.value)}
                  minLength={8}
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeInviteDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleInvite}
              disabled={inviteMutation.isPending}
            >
              {inviteMutation.isPending
                ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Creating…</>
                : setPasswordNow ? "Create user" : "Send invite"
              }
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}