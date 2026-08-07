/**
 * SenderIdentitiesPage.tsx — per-user sender identity management (REP+).
 *
 * Mounted at `/setup/sender-identities` (any authenticated user, manages
 * their OWN identities).
 *
 * Fetches:
 *   - GET /api/v1/users/me/sender-identities → list
 *   - GET /api/v1/users/me/email-quota → quota status card
 *
 * Mutations: POST create, DELETE, POST set-default.
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Mail,
  Plus,
  ShieldAlert,
  Star,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { senderIdentityApi } from "@/services/apiClient";
import type { SenderEmailType } from "@/types/common";
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
import { Progress } from "@/components/ui/progress";
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
import { cn, formatDate } from "@/lib/utils";

const MOCK_IDENTITIES = [
  {
    id: "si-1",
    email: "dev.rep@outrena.io",
    email_type: "platform_assigned" as SenderEmailType,
    display_name: "Dev Rep",
    is_verified: true,
    is_default: true,
    daily_send_quota: 1000,
    created_at: "2025-01-12T10:00:00Z",
  },
  {
    id: "si-2",
    email: "dev@acme.io",
    email_type: "corporate" as SenderEmailType,
    display_name: "Dev — Acme",
    is_verified: true,
    is_default: false,
    daily_send_quota: 2000,
    created_at: "2025-01-22T10:00:00Z",
  },
];

const MOCK_QUOTA = {
  date: new Date().toISOString().slice(0, 10),
  emails_sent: 412,
  daily_quota: 1000,
  remaining: 588,
  emails_bounced: 8,
  complaints: 0,
  is_throttled: false,
  throttled_until: null as string | null,
};

function typeVariant(type: SenderEmailType): "default" | "secondary" {
  return type === "platform_assigned" ? "default" : "secondary";
}

export function SenderIdentitiesPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState<string | null>(null);
  const [form, setForm] = useState({
    email: "",
    email_type: "platform_assigned" as SenderEmailType,
    display_name: "",
  });

  const { data, isLoading } = useQuery({
    queryKey: ["users", "me", "sender-identities"],
    queryFn: () => senderIdentityApi.list(),
  });

  const { data: quota } = useQuery({
    queryKey: ["users", "me", "email-quota"],
    queryFn: () => senderIdentityApi.myQuota(),
  });

  const identities = data ?? MOCK_IDENTITIES;
  const quotaCard = quota ?? MOCK_QUOTA;
  const quotaPct = Math.min(
    100,
    (quotaCard.emails_sent / Math.max(1, quotaCard.daily_quota)) * 100,
  );

  const createMutation = useMutation({
    mutationFn: () =>
      senderIdentityApi.create({
        email: form.email.trim(),
        email_type: form.email_type,
        display_name: form.display_name.trim() || undefined,
      }),
    onSuccess: () => {
      toast.success("Sender identity added");
      queryClient.invalidateQueries({
        queryKey: ["users", "me", "sender-identities"],
      });
      setDialogOpen(false);
      setForm({ email: "", email_type: "platform_assigned", display_name: "" });
    },
    onError: () => toast.error("Failed to add sender identity"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => senderIdentityApi.remove(id),
    onSuccess: () => {
      toast.success("Sender identity removed");
      queryClient.invalidateQueries({
        queryKey: ["users", "me", "sender-identities"],
      });
      setDeleteOpen(null);
    },
    onError: () => toast.error("Failed to remove sender identity"),
  });

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => senderIdentityApi.setDefault(id),
    onSuccess: () => {
      toast.success("Default sender updated");
      queryClient.invalidateQueries({
        queryKey: ["users", "me", "sender-identities"],
      });
    },
    onError: () => toast.error("Failed to set default"),
  });

  function handleVerify(id: string) {
    // Verification is a DNS check; we just toast for now (the backend
    // re-checks on next GET). In a real flow this could trigger a re-POST.
    toast.info(`DNS re-check requested for ${id}`);
    queryClient.invalidateQueries({
      queryKey: ["users", "me", "sender-identities"],
    });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.email.trim() || !form.email.includes("@")) {
      toast.error("Enter a valid email address");
      return;
    }
    createMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sender Identities"
        description="Manage the email addresses you send outreach from. The default is used for new sequences."
        actions={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Add Identity
          </Button>
        }
      />

      {/* Email quota card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            Email Quota Status
          </CardTitle>
          <CardDescription>{formatDate(quotaCard.date)}</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <div className="flex items-end justify-between">
              <span className="text-2xl font-bold tabular-nums">
                {quotaCard.emails_sent}
              </span>
              <span className="text-xs text-muted-foreground">
                / {quotaCard.daily_quota} today
              </span>
            </div>
            <Progress
              value={quotaPct}
              indicatorClassName={cn(
                quotaPct > 90
                  ? "bg-red-600"
                  : quotaPct > 75
                    ? "bg-amber-500"
                    : "bg-emerald-600",
              )}
            />
            <p className="text-xs text-muted-foreground">
              {quotaCard.remaining} remaining
            </p>
          </div>
          <div className="rounded-md border p-3 text-sm">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Bounces
            </p>
            <p className="mt-0.5 text-lg font-semibold">{quotaCard.emails_bounced}</p>
          </div>
          <div className="rounded-md border p-3 text-sm">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              Complaints
            </p>
            <p className="mt-0.5 text-lg font-semibold">{quotaCard.complaints}</p>
          </div>
          {quotaCard.is_throttled && (
            <div className="sm:col-span-3 flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
              <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                Throttled until{" "}
                <strong>{formatDate(quotaCard.throttled_until)}</strong>. Reduce
                send volume or contact your admin.
              </p>
            </div>
          )}
          {quotaCard.emails_bounced > 5 && (
            <div className="sm:col-span-3 flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-700 dark:text-red-300">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                Your bounce rate is elevated. Review your prospect list quality
                and consider enabling email verification on the source step.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Identities table */}
      <Card>
        <CardHeader>
          <CardTitle>My Sender Identities</CardTitle>
          <CardDescription>
            Platform-assigned addresses are provisioned by OUTRENA; corporate
            addresses require DNS verification.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : identities.length === 0 ? (
            <EmptyState
              icon={<Mail className="h-6 w-6" />}
              title="No sender identities"
              description="Add a sender identity to start sending outreach."
              action={
                <Button onClick={() => setDialogOpen(true)}>
                  <Plus className="h-4 w-4" />
                  Add Identity
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Display name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Verified</TableHead>
                  <TableHead>Default</TableHead>
                  <TableHead className="text-right">Daily quota</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {identities.map((id) => (
                  <TableRow key={id.id}>
                    <TableCell className="font-mono text-xs">{id.email}</TableCell>
                    <TableCell>{id.display_name ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={typeVariant(id.email_type)}>
                        {id.email_type === "platform_assigned"
                          ? "Platform"
                          : "Corporate"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {id.is_verified ? (
                        <Badge variant="success" className="gap-1">
                          <CheckCircle2 className="h-3 w-3" /> Verified
                        </Badge>
                      ) : (
                        <Badge variant="warning">Pending</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {id.is_default ? (
                        <Badge variant="default" className="gap-1">
                          <Star className="h-3 w-3" /> Default
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {id.daily_send_quota.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {id.email_type === "corporate" && !id.is_verified && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleVerify(id.id)}
                          >
                            Verify
                          </Button>
                        )}
                        {!id.is_default && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDefaultMutation.mutate(id.id)}
                            disabled={setDefaultMutation.isPending}
                          >
                            <Star className="h-3.5 w-3.5" />
                            Set default
                          </Button>
                        )}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label="Delete"
                              onClick={() => setDeleteOpen(id.id)}
                              disabled={id.is_default}
                            >
                              <Trash2 className="h-4 w-4 text-red-600" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{id.is_default ? "Default identity cannot be deleted" : "Delete sender identity"}</TooltipContent>
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

      {/* Add dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogClose onClose={() => setDialogOpen(false)} />
        <DialogHeader>
          <DialogTitle>Add Sender Identity</DialogTitle>
          <DialogDescription>
            Corporate addresses require DNS verification (SPF / DKIM) before
            they can be used.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="si-email">Email address</Label>
            <Input
              id="si-email"
              type="email"
              placeholder="you@yourcompany.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="si-type">Email type</Label>
            <Select
              id="si-type"
              value={form.email_type}
              onChange={(e) =>
                setForm({
                  ...form,
                  email_type: e.target.value as SenderEmailType,
                })
              }
            >
              <option value="platform_assigned">Platform-assigned</option>
              <option value="corporate">Corporate (your domain)</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="si-display">Display name (optional)</Label>
            <Input
              id="si-display"
              placeholder="Jane Doe"
              value={form.display_name}
              onChange={(e) =>
                setForm({ ...form, display_name: e.target.value })
              }
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
            <Button type="submit" disabled={createMutation.isPending}>
              Add identity
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={deleteOpen !== null} onOpenChange={(o) => !o && setDeleteOpen(null)}>
        <DialogClose onClose={() => setDeleteOpen(null)} />
        <DialogHeader>
          <DialogTitle>Remove sender identity?</DialogTitle>
          <DialogDescription>
            This will stop the address from being usable for new sequences. Any
            in-flight messages will still be sent from it.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteOpen(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={deleteMutation.isPending}
            onClick={() => deleteOpen && deleteMutation.mutate(deleteOpen)}
          >
            Remove identity
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
