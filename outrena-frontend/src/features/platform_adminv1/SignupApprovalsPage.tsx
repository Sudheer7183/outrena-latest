/**
 * SignupApprovalsPage.tsx — pending tenant signup queue.
 *
 * Fetches `GET /admin/signups?status=pending`. Each row: company, subdomain,
 * owner email, plan, created. "Approve" button → `POST /admin/signups/{id}/approve`.
 * "Reject" button → opens dialog with reason → `POST /admin/signups/{id}/reject`
 * body `{ reason }`. Refresh button re-fetches.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileCheck2, RefreshCw, XCircle } from "lucide-react";
import { toast } from "sonner";
import { platformApi } from "@/services/apiClient";
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
import { EmptyState } from "@/components/ui/empty-state";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { timeAgo } from "@/lib/utils";

export function SignupApprovalsPage() {
  const queryClient = useQueryClient();
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const { data: signups, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["platform", "signups", "pending"],
    queryFn: () => platformApi.signups("pending"),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => platformApi.approveSignup(id),
    onSuccess: (data) => {
      toast.success(`Tenant approved: ${data.tenant_slug}`);
      queryClient.invalidateQueries({ queryKey: ["platform", "signups"] });
      queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
      queryClient.invalidateQueries({ queryKey: ["platform", "metrics"] });
    },
    onError: () => toast.error("Failed to approve signup"),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      platformApi.rejectSignup(id, reason),
    onSuccess: () => {
      toast.success("Signup rejected");
      queryClient.invalidateQueries({ queryKey: ["platform", "signups"] });
      setRejectId(null);
      setReason("");
    },
    onError: () => toast.error("Failed to reject signup"),
  });

  function submitReject() {
    if (!rejectId) return;
    if (!reason.trim()) {
      toast.error("Reason is required");
      return;
    }
    rejectMutation.mutate({ id: rejectId, reason: reason.trim() });
  }

  const list = signups ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Signup Approvals"
        description="Approve or reject new tenant signup requests."
        actions={
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Pending Requests</CardTitle>
          <CardDescription>
            {list.length} request{list.length === 1 ? "" : "s"} awaiting review.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : list.length === 0 ? (
            <EmptyState
              icon={<FileCheck2 className="h-6 w-6" />}
              title="No pending signups"
              description="All caught up. New requests will appear here automatically."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead>
                  <TableHead>Subdomain</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.company_name}</TableCell>
                    <TableCell className="text-muted-foreground">{s.subdomain}</TableCell>
                    <TableCell className="text-muted-foreground">
                      <div className="flex flex-col">
                        <span>{s.owner_email}</span>
                        <span className="text-xs">
                          {s.owner_first_name} {s.owner_last_name}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{s.plan_id}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {timeAgo(s.created_at)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="warning">{s.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => approveMutation.mutate(s.id)}
                          disabled={
                            approveMutation.isPending ||
                            rejectMutation.isPending
                          }
                          className="text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-950/40"
                        >
                          <CheckCircle2 className="h-4 w-4" />
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setRejectId(s.id);
                            setReason("");
                          }}
                          disabled={
                            approveMutation.isPending ||
                            rejectMutation.isPending
                          }
                          className="text-red-700 hover:bg-red-50 hover:text-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
                        >
                          <XCircle className="h-4 w-4" />
                          Reject
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Reject dialog */}
      <Dialog
        open={rejectId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRejectId(null);
            setReason("");
          }
        }}
      >
        <DialogClose onClose={() => setRejectId(null)} />
        <DialogHeader>
          <DialogTitle>Reject signup</DialogTitle>
          <DialogDescription>
            Provide a reason. The requester will see this message on the
            signup-status page and via email.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="reject-reason">Reason *</Label>
            <Textarea
              id="reject-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Subdomain violates trademark. Please choose another."
              rows={4}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setRejectId(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={submitReject}
            disabled={rejectMutation.isPending}
          >
            Reject signup
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
