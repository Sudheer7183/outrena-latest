// /**
//  * SignupApprovalsPage.tsx — pending tenant signup queue.
//  *
//  * Fetches `GET /admin/signups?status=pending`. Each row: company, subdomain,
//  * owner email, plan, created. "Approve" button → `POST /admin/signups/{id}/approve`.
//  * "Reject" button → opens dialog with reason → `POST /admin/signups/{id}/reject`
//  * body `{ reason }`. Refresh button re-fetches.
//  */
// import { useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import { CheckCircle2, FileCheck2, RefreshCw, XCircle } from "lucide-react";
// import { toast } from "sonner";
// import { platformApi } from "@/services/apiClient";
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
// import { Skeleton } from "@/components/ui/skeleton";
// import { EmptyState } from "@/components/ui/empty-state";
// import {
//   Dialog,
//   DialogClose,
//   DialogDescription,
//   DialogFooter,
//   DialogHeader,
//   DialogTitle,
// } from "@/components/ui/dialog";
// import { Label } from "@/components/ui/label";
// import { Textarea } from "@/components/ui/textarea";
// import { timeAgo } from "@/lib/utils";

// export function SignupApprovalsPage() {
//   const queryClient = useQueryClient();
//   const [rejectId, setRejectId] = useState<string | null>(null);
//   const [reason, setReason] = useState("");

//   const { data: signups, isLoading, isFetching, refetch } = useQuery({
//     queryKey: ["platform", "signups", "pending"],
//     queryFn: () => platformApi.signups("pending"),
//   });

//   const approveMutation = useMutation({
//     mutationFn: (id: string) => platformApi.approveSignup(id),
//     onSuccess: (data) => {
//       toast.success(`Tenant approved: ${data.tenant_slug}`);
//       queryClient.invalidateQueries({ queryKey: ["platform", "signups"] });
//       queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
//       queryClient.invalidateQueries({ queryKey: ["platform", "metrics"] });
//     },
//     onError: () => toast.error("Failed to approve signup"),
//   });

//   const rejectMutation = useMutation({
//     mutationFn: ({ id, reason }: { id: string; reason: string }) =>
//       platformApi.rejectSignup(id, reason),
//     onSuccess: () => {
//       toast.success("Signup rejected");
//       queryClient.invalidateQueries({ queryKey: ["platform", "signups"] });
//       setRejectId(null);
//       setReason("");
//     },
//     onError: () => toast.error("Failed to reject signup"),
//   });

//   function submitReject() {
//     if (!rejectId) return;
//     if (!reason.trim()) {
//       toast.error("Reason is required");
//       return;
//     }
//     rejectMutation.mutate({ id: rejectId, reason: reason.trim() });
//   }

//   const list = signups ?? [];

//   return (
//     <div className="space-y-6">
//       <PageHeader
//         title="Signup Approvals"
//         description="Approve or reject new tenant signup requests."
//         actions={
//           <Button variant="outline" onClick={() => refetch()}>
//             <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
//             Refresh
//           </Button>
//         }
//       />

//       <Card>
//         <CardHeader>
//           <CardTitle>Pending Requests</CardTitle>
//           <CardDescription>
//             {list.length} request{list.length === 1 ? "" : "s"} awaiting review.
//           </CardDescription>
//         </CardHeader>
//         <CardContent>
//           {isLoading ? (
//             <div className="space-y-2">
//               {Array.from({ length: 4 }).map((_, i) => (
//                 <Skeleton key={i} className="h-12 w-full" />
//               ))}
//             </div>
//           ) : list.length === 0 ? (
//             <EmptyState
//               icon={<FileCheck2 className="h-6 w-6" />}
//               title="No pending signups"
//               description="All caught up. New requests will appear here automatically."
//             />
//           ) : (
//             <Table>
//               <TableHeader>
//                 <TableRow>
//                   <TableHead>Company</TableHead>
//                   <TableHead>Subdomain</TableHead>
//                   <TableHead>Owner</TableHead>
//                   <TableHead>Plan</TableHead>
//                   <TableHead>Submitted</TableHead>
//                   <TableHead>Status</TableHead>
//                   <TableHead className="text-right">Actions</TableHead>
//                 </TableRow>
//               </TableHeader>
//               <TableBody>
//                 {list.map((s) => (
//                   <TableRow key={s.id}>
//                     <TableCell className="font-medium">{s.company_name}</TableCell>
//                     <TableCell className="text-muted-foreground">{s.subdomain}</TableCell>
//                     <TableCell className="text-muted-foreground">
//                       <div className="flex flex-col">
//                         <span>{s.owner_email}</span>
//                         <span className="text-xs">
//                           {s.owner_first_name} {s.owner_last_name}
//                         </span>
//                       </div>
//                     </TableCell>
//                     <TableCell>
//                       <Badge variant="secondary">{s.plan_id}</Badge>
//                     </TableCell>
//                     <TableCell className="text-xs text-muted-foreground">
//                       {timeAgo(s.created_at)}
//                     </TableCell>
//                     <TableCell>
//                       <Badge variant="warning">{s.status}</Badge>
//                     </TableCell>
//                     <TableCell className="text-right">
//                       <div className="flex items-center justify-end gap-2">
//                         <Button
//                           size="sm"
//                           variant="outline"
//                           onClick={() => approveMutation.mutate(s.id)}
//                           disabled={
//                             approveMutation.isPending ||
//                             rejectMutation.isPending
//                           }
//                           className="text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-950/40"
//                         >
//                           <CheckCircle2 className="h-4 w-4" />
//                           Approve
//                         </Button>
//                         <Button
//                           size="sm"
//                           variant="outline"
//                           onClick={() => {
//                             setRejectId(s.id);
//                             setReason("");
//                           }}
//                           disabled={
//                             approveMutation.isPending ||
//                             rejectMutation.isPending
//                           }
//                           className="text-red-700 hover:bg-red-50 hover:text-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
//                         >
//                           <XCircle className="h-4 w-4" />
//                           Reject
//                         </Button>
//                       </div>
//                     </TableCell>
//                   </TableRow>
//                 ))}
//               </TableBody>
//             </Table>
//           )}
//         </CardContent>
//       </Card>

//       {/* Reject dialog */}
//       <Dialog
//         open={rejectId !== null}
//         onOpenChange={(open) => {
//           if (!open) {
//             setRejectId(null);
//             setReason("");
//           }
//         }}
//       >
//         <DialogClose onClose={() => setRejectId(null)} />
//         <DialogHeader>
//           <DialogTitle>Reject signup</DialogTitle>
//           <DialogDescription>
//             Provide a reason. The requester will see this message on the
//             signup-status page and via email.
//           </DialogDescription>
//         </DialogHeader>
//         <div className="space-y-4">
//           <div className="space-y-2">
//             <Label htmlFor="reject-reason">Reason *</Label>
//             <Textarea
//               id="reject-reason"
//               value={reason}
//               onChange={(e) => setReason(e.target.value)}
//               placeholder="e.g. Subdomain violates trademark. Please choose another."
//               rows={4}
//             />
//           </div>
//         </div>
//         <DialogFooter>
//           <Button variant="outline" onClick={() => setRejectId(null)}>
//             Cancel
//           </Button>
//           <Button
//             variant="destructive"
//             onClick={submitReject}
//             disabled={rejectMutation.isPending}
//           >
//             Reject signup
//           </Button>
//         </DialogFooter>
//       </Dialog>
//     </div>
//   );
// }

/**
 * SignupApprovalsPage.tsx — SUPER_ADMIN signup approval queue.
 *
 * FIX: This file was 0 bytes. Without it, the superadmin panel had no
 * approval UI — signup requests sitting in the DB were invisible to admins,
 * so no one could approve them and provisioning never ran.
 *
 * Fetches GET /api/platform/admin/signups
 * Approve: POST /api/platform/admin/signups/:id/approve
 * Reject:  POST /api/platform/admin/signups/:id/reject
 */
import { useEffect, useState } from "react";
import { platformApi } from "@/services/apiClient";

type SignupRow = {
  id: number;
  company_name: string;
  subdomain: string;
  owner_email: string;
  owner_first_name: string;
  owner_last_name: string;
  plan_id: number;
  status: string;
  rejection_reason: string | null;
  created_at: string;
};

const STATUS_BADGE: Record<string, string> = {
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-blue-100 text-blue-800",
  PROVISIONED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
};

export function SignupApprovalsPage() {
  const [signups, setSignups] = useState<SignupRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<number | null>(null);
  const [rejectId, setRejectId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await platformApi.signups();
      setSignups((res as unknown as SignupRow[]) ?? []);
    } catch {
      setError("Failed to load signups.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const approve = async (id: number) => {
    setActionId(id);
    try {
      await platformApi.approveSignup(String(id));
      await load();
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ?? "Approval failed. Check backend logs."
      );
    } finally {
      setActionId(null);
    }
  };

  const reject = async () => {
    if (!rejectId) return;
    setActionId(rejectId);
    try {
      await platformApi.rejectSignup(String(rejectId), rejectReason);
      setRejectId(null);
      setRejectReason("");
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Rejection failed.");
    } finally {
      setActionId(null);
    }
  };

  const pending = signups.filter((s) => s.status === "PENDING_APPROVAL");
  const others = signups.filter((s) => s.status !== "PENDING_APPROVAL");

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Signup Approvals</h1>
          <p className="text-sm text-gray-500 mt-1">
            Review and approve self-serve signup requests.
          </p>
        </div>
        <button
          onClick={load}
          className="text-sm text-blue-600 hover:underline"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700 flex justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-4 text-red-500">✕</button>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading…</div>
      ) : signups.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          No signup requests found.
        </div>
      ) : (
        <>
          {pending.length > 0 && (
            <section className="mb-8">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                Pending ({pending.length})
              </h2>
              <div className="space-y-3">
                {pending.map((s) => (
                  <SignupCard
                    key={s.id}
                    signup={s}
                    busy={actionId === s.id}
                    onApprove={() => approve(s.id)}
                    onReject={() => setRejectId(s.id)}
                  />
                ))}
              </div>
            </section>
          )}

          {others.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                History
              </h2>
              <div className="space-y-2">
                {others.map((s) => (
                  <SignupCard key={s.id} signup={s} busy={false} />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* Reject modal */}
      {rejectId !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-semibold text-gray-900 mb-2">Reject signup</h3>
            <p className="text-sm text-gray-500 mb-4">
              Provide an optional reason. It will be stored but not emailed automatically.
            </p>
            <textarea
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm mb-4 h-24 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Reason (optional)"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setRejectId(null); setRejectReason(""); }}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Cancel
              </button>
              <button
                onClick={reject}
                disabled={actionId !== null}
                className="bg-red-600 text-white text-sm px-4 py-2 rounded hover:bg-red-700 disabled:opacity-50"
              >
                {actionId !== null ? "Rejecting…" : "Confirm reject"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SignupCard({
  signup,
  busy,
  onApprove,
  onReject,
}: {
  signup: SignupRow;
  busy: boolean;
  onApprove?: () => void;
  onReject?: () => void;
}) {
  const badgeCls =
    STATUS_BADGE[signup.status] ?? "bg-gray-100 text-gray-700";

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-gray-900 truncate">{signup.company_name}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeCls}`}>
            {signup.status.replace("_", " ")}
          </span>
        </div>
        <p className="text-sm text-gray-500 truncate">
          <span className="font-mono">{signup.subdomain}.outrena.com</span>
          {" · "}
          {signup.owner_first_name} {signup.owner_last_name} ({signup.owner_email})
        </p>
        <p className="text-xs text-gray-400 mt-0.5">
          Submitted {new Date(signup.created_at).toLocaleString()}
        </p>
        {signup.rejection_reason && (
          <p className="text-xs text-red-600 mt-1">Reason: {signup.rejection_reason}</p>
        )}
      </div>
      {onApprove && onReject && (
        <div className="flex gap-2 shrink-0">
          <button
            onClick={onReject}
            disabled={busy}
            className="text-sm text-red-600 border border-red-200 px-3 py-1 rounded hover:bg-red-50 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            onClick={onApprove}
            disabled={busy}
            className="text-sm text-white bg-blue-600 px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? "…" : "Approve"}
          </button>
        </div>
      )}
    </div>
  );
}

