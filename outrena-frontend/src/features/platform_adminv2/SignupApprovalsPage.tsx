/**
 * SignupApprovalsPage.tsx — SUPER_ADMIN self-serve signup request management.
 * Mounted at /platform-admin/signups.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, RefreshCw, XCircle } from "lucide-react";
import { toast } from "sonner";
import { platformApi } from "@/services/apiClient";
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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDateTime } from "@/lib/utils";

interface SignupRequest {
  id: string;
  company_name: string;
  subdomain: string;
  owner_email: string;
  owner_first_name: string;
  owner_last_name: string;
  status: string;
  created_at: string;
}

export function SignupApprovalsPage() {
  const qc = useQueryClient();
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  // approveMutation.isPending tracks in-flight approval; no separate loading state needed

  const { data: signupList = [], isLoading: listLoading, refetch: refetchList } = useQuery<SignupRequest[]>({
    queryKey: ["platform", "signups", "list"],
    queryFn: async () => {
      // platformApi doesn't expose a listSignups helper yet — call via http directly
      const { http } = await import("@/services/apiClient");
      return http.get<SignupRequest[]>("/api/platform/admin/signups");
    },
    refetchInterval: 30_000,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => platformApi.approveSignup(id),
    onSuccess: () => {
      toast.success("Signup approved and tenant provisioned.");
      qc.invalidateQueries({ queryKey: ["platform", "signups"] });
      qc.invalidateQueries({ queryKey: ["platform", "tenants"] });
    },
    onError: (err: Error) => toast.error(`Approval failed: ${err.message}`),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      platformApi.rejectSignup(id, reason),
    onSuccess: () => {
      toast.success("Signup request rejected.");
      qc.invalidateQueries({ queryKey: ["platform", "signups"] });
      setRejectId(null);
      setRejectReason("");
    },
    onError: (err: Error) => toast.error(`Rejection failed: ${err.message}`),
  });

  function statusBadge(status: string) {
    const s = status.toUpperCase();
    const cls =
      s === "PENDING_APPROVAL"
        ? "bg-yellow-100 text-yellow-700"
        : s === "APPROVED"
        ? "bg-green-100 text-green-700"
        : "bg-red-100 text-red-700";
    return (
      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
        {status}
      </span>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Signup Approvals"
        description="Review and approve self-serve tenant workspace requests."
        actions={
          <Button variant="outline" size="sm" onClick={() => refetchList()}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Refresh
          </Button>
        }
      />

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            Signup Requests ({signupList.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {listLoading ? (
            <div className="space-y-2 p-4">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : signupList.length === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="h-8 w-8" />}
              title="No pending signups"
              description="All signup requests have been reviewed."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead>
                  <TableHead>Subdomain</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {signupList.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.company_name}</TableCell>
                    <TableCell className="font-mono text-sm">{s.subdomain}</TableCell>
                    <TableCell className="text-sm">
                      {s.owner_first_name} {s.owner_last_name}
                      <br />
                      <span className="text-muted-foreground">{s.owner_email}</span>
                    </TableCell>
                    <TableCell>{statusBadge(s.status)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDateTime(s.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {s.status === "PENDING_APPROVAL" && (
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-green-600 border-green-300 hover:bg-green-50"
                            disabled={approveMutation.isPending}
                            onClick={() => approveMutation.mutate(s.id)}
                          >
                            <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-red-600 border-red-300 hover:bg-red-50"
                            onClick={() => setRejectId(s.id)}
                          >
                            <XCircle className="mr-1 h-3.5 w-3.5" />
                            Reject
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Reject dialog */}
      <Dialog open={rejectId !== null} onOpenChange={(o) => { if (!o) { setRejectId(null); setRejectReason(""); } }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Reject Signup Request</DialogTitle>
            <DialogDescription>
              Provide a reason for rejection (optional — sent to the applicant).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="reject-reason">Reason</Label>
            <Input
              id="reject-reason"
              placeholder="e.g. Duplicate account, incomplete information…"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
          </div>
          <DialogFooter className="gap-2">
            <DialogClose asChild>
              <Button variant="outline" disabled={rejectMutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={rejectMutation.isPending}
              onClick={() =>
                rejectId &&
                rejectMutation.mutate({ id: rejectId, reason: rejectReason })
              }
            >
              {rejectMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}