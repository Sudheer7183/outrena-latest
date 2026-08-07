/**
 * GdprCenterPage.tsx — tenant-admin GDPR center (TENANT_ADMIN).
 *
 * Mounted at `/admin/gdpr` inside <AppLayout>. Three tabs:
 *   1. Data Subject Requests — table of DSRs; click row → detail panel with
 *      process/complete/reject buttons + export download link.
 *   2. Consent Center — search by email → consent status + history + withdraw.
 *   3. Retention — show retention policies + status, "Enforce now" button
 *      (delegates to the RetentionPage component for clarity).
 *
 * Falls back to inline mock data so the page renders without backend.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  FileCheck2,
  Mail,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { gdprApi } from "@/services/apiClient";
import { ErrorState } from "@/components/ui/error-state";
import { Pagination, usePagination } from "@/components/ui/pagination";
import type {
  DsrRow,
  DsrStatus,
  RetentionStatus,
} from "@/types/common";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { EmptyState } from "@/components/ui/empty-state";
import { cn, formatDate, formatDateTime } from "@/lib/utils";
import { RetentionPolicyViewer } from "@/features/retention/RetentionPolicyViewer";

const MOCK_DSRS: DsrRow[] = [
  {
    id: "dsr-1",
    email: "jane.prospect@example.com",
    request_type: "access",
    status: "pending",
    tenant_slug: "acme",
    details: "Requesting a copy of all data held about me.",
    created_at: "2025-02-08T10:00:00Z",
    updated_at: "2025-02-08T10:00:00Z",
    assigned_to: null,
    export_url: null,
    rejection_reason: null,
  },
  {
    id: "dsr-2",
    email: "mark.lead@example.com",
    request_type: "erasure",
    status: "processing",
    tenant_slug: "acme",
    details: "Please delete my account and all associated data.",
    created_at: "2025-02-05T14:30:00Z",
    updated_at: "2025-02-09T08:15:00Z",
    assigned_to: "Amelia Chen",
    export_url: null,
    rejection_reason: null,
  },
  {
    id: "dsr-3",
    email: "sarah.buyer@example.com",
    request_type: "portability",
    status: "completed",
    tenant_slug: "acme",
    details: "Please send me a machine-readable export.",
    created_at: "2025-01-28T09:00:00Z",
    updated_at: "2025-02-02T11:45:00Z",
    assigned_to: "Marcus Lee",
    export_url: null,
    rejection_reason: null,
  },
];
// Derive export_url from id for completed portability requests (mock data).
MOCK_DSRS.forEach((dsr) => {
  if (dsr.status === "completed" && dsr.request_type === "portability") {
    dsr.export_url = `/api/v1/gdpr/export/${dsr.id}`;
  }
});

const MOCK_RETENTION: RetentionStatus = {
  policies: [
    {
      id: "rp-1",
      data_category: "Prospect data",
      retention_days: 730,
      auto_purge: true,
      description: "B2B prospect records retained for 2 years from last contact.",
    },
    {
      id: "rp-2",
      data_category: "Email engagement events",
      retention_days: 365,
      auto_purge: true,
      description: "Open / click / reply events retained for 1 year.",
    },
    {
      id: "rp-3",
      data_category: "Audit logs",
      retention_days: 90,
      auto_purge: true,
      description: "Tenant-scoped audit log retention per SOC2 policy.",
    },
    {
      id: "rp-4",
      data_category: "Cancelled tenant data",
      retention_days: 30,
      auto_purge: true,
      description: "Soft-deleted after cancellation; purged after 30-day grace.",
    },
  ],
  last_enforced_at: "2025-02-09T03:00:00Z",
  pending_purge_count: 12,
  next_run_at: "2025-02-10T03:00:00Z",
};

function dsrStatusVariant(
  status: DsrStatus,
): "default" | "secondary" | "success" | "warning" | "destructive" {
  switch (status) {
    case "pending":
      return "warning";
    case "processing":
      return "default";
    case "completed":
      return "success";
    case "rejected":
      return "destructive";
    case "cancelled":
      return "secondary";
    default:
      return "secondary";
  }
}

export function GdprCenterPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("dsrs");
  const [selectedDsrId, setSelectedDsrId] = useState<string | null>(null);
  const [consentEmail, setConsentEmail] = useState("");
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const { data: dsrs, isLoading: dsrsLoading , isError, error, refetch } = useQuery({
    queryKey: ["gdpr", "dsrs"],
    queryFn: () => gdprApi.list(),
  });

  const dsrRows = dsrs ?? MOCK_DSRS;


  const { page, pageSize, total, pageItems, setPage, setPageSize } = usePagination({ items: dsrRows, initialPageSize: 15 });
  const selectedDsr = dsrRows.find((d) => d.id === selectedDsrId) ?? null;

  const { data: consent, isLoading: consentLoading } = useQuery({
    queryKey: ["gdpr", "consent", consentEmail],
    queryFn: () => gdprApi.getConsent(consentEmail),
    enabled: consentEmail.length > 3 && consentEmail.includes("@"),
  });

  const processMutation = useMutation({
    mutationFn: (id: string) => gdprApi.process(id),
    onSuccess: () => {
      toast.success("DSR marked as processing");
      queryClient.invalidateQueries({ queryKey: ["gdpr", "dsrs"] });
    },
    onError: () => toast.error("Failed to update DSR"),
  });

  const completeMutation = useMutation({
    mutationFn: (id: string) => gdprApi.complete(id),
    onSuccess: () => {
      toast.success("DSR completed");
      queryClient.invalidateQueries({ queryKey: ["gdpr", "dsrs"] });
    },
    onError: () => toast.error("Failed to complete DSR"),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      gdprApi.reject(id, reason),
    onSuccess: () => {
      toast.success("DSR rejected");
      queryClient.invalidateQueries({ queryKey: ["gdpr", "dsrs"] });
      setRejectingId(null);
      setRejectReason("");
    },
    onError: () => toast.error("Failed to reject DSR"),
  });

  const withdrawMutation = useMutation({
    mutationFn: (email: string) => gdprApi.withdraw(email),
    onSuccess: () => {
      toast.success("Consent withdrawn");
      queryClient.invalidateQueries({
        queryKey: ["gdpr", "consent", consentEmail],
      });
    },
    onError: () => toast.error("Failed to withdraw consent"),
  });

  function handleConsentSearch(e: FormEvent) {
    e.preventDefault();
    if (!consentEmail.trim() || !consentEmail.includes("@")) {
      toast.error("Enter a valid email");
      return;
    }
    queryClient.invalidateQueries({
      queryKey: ["gdpr", "consent", consentEmail],
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="GDPR Center"
        description="Manage Data Subject Requests, consent records, and retention policies."
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <Tooltip>
            <TooltipTrigger asChild>
              <TabsTrigger value="dsrs">
                <FileCheck2 className="mr-1.5 h-3.5 w-3.5" /> Data Subject Requests
              </TabsTrigger>
            </TooltipTrigger>
            <TooltipContent>DSRs — access, erasure, and portability requests from EU/UK data subjects under GDPR/UK-GDPR.</TooltipContent>
          </Tooltip>
          <TabsTrigger value="consent">
            <ShieldCheck className="mr-1.5 h-3.5 w-3.5" /> Consent Center
          </TabsTrigger>
          <TabsTrigger value="retention">
            <Clock className="mr-1.5 h-3.5 w-3.5" /> Retention
          </TabsTrigger>
        </TabsList>

        {/* ── DSR tab ────────────────────────────────────────────── */}
{/* Task 2-b finding 14: explicit error + retry state */}
        {isError ? (
          <ErrorState
            title="Failed to load DSR list"
            error={error}
            onRetry={() => refetch()}
          />
        ) : null}

                <TabsContent value="dsrs" className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Requests</CardTitle>
                <CardDescription>
                  All DSRs across this tenant. Click a row to open the detail
                  panel.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {dsrsLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full" />
                    ))}
                  </div>
                ) : dsrRows.length === 0 ? (
                  <EmptyState
                    icon={<FileCheck2 className="h-6 w-6" />}
                    title="No DSRs yet"
                    description="Data Subject Requests submitted via /p/gdpr-rights will appear here."
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Email</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Submitted</TableHead>
                        <TableHead>Assigned</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {pageItems.map((d) => (
                        <TableRow
                          key={d.id}
                          onClick={() => setSelectedDsrId(d.id)}
                          className={cn(
                            "cursor-pointer",
                            selectedDsrId === d.id && "bg-muted",
                          )}
                        >
                          <TableCell className="font-mono text-xs">
                            {d.email}
                          </TableCell>
                          <TableCell className="capitalize">
                            {d.request_type}
                          </TableCell>
                          <TableCell>
                            <Badge variant={dsrStatusVariant(d.status)}>
                              {d.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {formatDate(d.created_at)}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {d.assigned_to ?? "—"}
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

            {/* Detail panel */}
            <Card>
              <CardHeader>
                <CardTitle>Request Details</CardTitle>
                <CardDescription>
                  {selectedDsr ? `ID: ${selectedDsr.id}` : "Select a row"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {!selectedDsr ? (
                  <EmptyState
                    icon={<FileCheck2 className="h-6 w-6" />}
                    title="No request selected"
                    description="Click a row to view details and take action."
                  />
                ) : (
                  <>
                    <div className="space-y-2 text-sm">
                      <div>
                        <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                          Email
                        </Label>
                        <p className="font-mono text-xs">{selectedDsr.email}</p>
                      </div>
                      <div>
                        <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                          Request type
                        </Label>
                        <p className="capitalize">{selectedDsr.request_type}</p>
                      </div>
                      <div>
                        <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                          Status
                        </Label>
                        <p>
                          <Badge variant={dsrStatusVariant(selectedDsr.status)}>
                            {selectedDsr.status}
                          </Badge>
                        </p>
                      </div>
                      <div>
                        <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                          Details
                        </Label>
                        <p className="text-sm text-muted-foreground">
                          {selectedDsr.details ?? "—"}
                        </p>
                      </div>
                      <div>
                        <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                          Submitted
                        </Label>
                        <p className="text-xs">
                          {formatDateTime(selectedDsr.created_at)}
                        </p>
                      </div>
                      {selectedDsr.rejection_reason && (
                        <div className="rounded-md border border-red-500/40 bg-red-500/10 p-2 text-xs text-red-700 dark:text-red-300">
                          <p className="font-medium">Rejection reason:</p>
                          <p>{selectedDsr.rejection_reason}</p>
                        </div>
                      )}
                      {selectedDsr.export_url && (
                        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-2 text-xs">
                          <p className="font-medium text-emerald-700 dark:text-emerald-300">
                            Export ready
                          </p>
                          <a
                            href={selectedDsr.export_url}
                            className="mt-1 inline-flex items-center gap-1 font-mono text-emerald-700 hover:underline dark:text-emerald-300"
                          >
                            <Download className="h-3 w-3" />
                            Download export
                          </a>
                        </div>
                      )}
                    </div>

                    <div className="space-y-2">
                      {selectedDsr.status === "pending" && (
                        <Button
                          className="w-full"
                          onClick={() => processMutation.mutate(selectedDsr.id)}
                          disabled={processMutation.isPending}
                        >
                          <ArrowRight className="h-4 w-4" />
                          Start processing
                        </Button>
                      )}
                      {selectedDsr.status === "processing" && (
                        <>
                          <Button
                            className="w-full"
                            variant="default"
                            onClick={() =>
                              completeMutation.mutate(selectedDsr.id)
                            }
                            disabled={completeMutation.isPending}
                          >
                            <CheckCircle2 className="h-4 w-4" />
                            Mark completed
                          </Button>
                          <Button
                            className="w-full"
                            variant="outline"
                            onClick={() => setRejectingId(selectedDsr.id)}
                          >
                            <XCircle className="h-4 w-4 text-red-600" />
                            Reject
                          </Button>
                        </>
                      )}
                    </div>

                    {rejectingId === selectedDsr.id && (
                      <div className="space-y-2 rounded-md border border-red-500/40 bg-red-500/5 p-3">
                        <Label htmlFor="reject-reason">Rejection reason</Label>
                        <Input
                          id="reject-reason"
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          placeholder="Reason this request is being rejected"
                        />
                        <div className="flex gap-2">
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={rejectMutation.isPending}
                            onClick={() =>
                              rejectMutation.mutate({
                                id: selectedDsr.id,
                                reason: rejectReason,
                              })
                            }
                          >
                            Confirm rejection
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setRejectingId(null);
                              setRejectReason("");
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ── Consent tab ───────────────────────────────────────── */}
        <TabsContent value="consent" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Consent Lookup</CardTitle>
              <CardDescription>
                Search for a data subject by email to view their consent
                status + history.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={handleConsentSearch}
                className="flex items-end gap-2"
              >
                <div className="flex-1 space-y-2">
                  <Label htmlFor="consent-email">Email address</Label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      id="consent-email"
                      type="email"
                      placeholder="prospect@example.com"
                      value={consentEmail}
                      onChange={(e) => setConsentEmail(e.target.value)}
                      className="pl-9"
                    />
                  </div>
                </div>
                <Button type="submit" disabled={consentLoading}>
                  <Search className="h-4 w-4" />
                  Search
                </Button>
              </form>
            </CardContent>
          </Card>

          {consentEmail && (
            <Card>
              <CardHeader>
                <CardTitle>Consent Status</CardTitle>
                <CardDescription>
                  {consent?.email ?? consentEmail}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {consentLoading ? (
                  <Skeleton className="h-32 w-full" />
                ) : !consent ? (
                  <EmptyState
                    icon={<ShieldCheck className="h-6 w-6" />}
                    title="No consent records"
                    description="No consent data found for this email."
                  />
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                      <div className="rounded-md border p-3">
                        <p className="text-xs uppercase tracking-wider text-muted-foreground">
                          Status
                        </p>
                        <Badge
                          variant={consent.has_active_consent ? "success" : "secondary"}
                          className="mt-1"
                        >
                          {consent.has_active_consent ? "Active" : "Withdrawn"}
                        </Badge>
                      </div>
                      <div className="rounded-md border p-3">
                        <p className="text-xs uppercase tracking-wider text-muted-foreground">
                          Lawful basis
                        </p>
                        <p className="mt-1 text-sm capitalize">
                          {consent.lawful_basis ?? "—"}
                        </p>
                      </div>
                      <div className="rounded-md border p-3">
                        <p className="text-xs uppercase tracking-wider text-muted-foreground">
                          Granted
                        </p>
                        <p className="mt-1 text-xs">
                          {formatDate(consent.granted_at)}
                        </p>
                      </div>
                    </div>

                    <div>
                      <p className="text-sm font-semibold">History</p>
                      <Table className="mt-2">
                        <TableHeader>
                          <TableRow>
                            <TableHead>Date</TableHead>
                            <TableHead>Action</TableHead>
                            <TableHead>Basis</TableHead>
                            <TableHead>Prospect</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {(consent.history ?? []).map((h) => (
                            <TableRow key={h.id}>
                              <TableCell className="text-xs">
                                {formatDateTime(h.granted_at ?? h.withdrawn_at)}
                              </TableCell>
                              <TableCell>
                                <Badge
                                  variant={
                                    h.is_active ? "success" : "secondary"
                                  }
                                >
                                  {h.is_active ? "Granted" : "Withdrawn"}
                                </Badge>
                              </TableCell>
                              <TableCell className="capitalize">
                                {h.lawful_basis}
                              </TableCell>
                              <TableCell className="font-mono text-xs">
                                {h.prospect_id ?? "—"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>

                    {consent.has_active_consent && (
                      <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <div>
                          <p className="font-medium">Withdraw consent</p>
                          <p>
                            This will stop all processing for this email
                            immediately. The action is audited.
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          className="ml-auto"
                          disabled={withdrawMutation.isPending}
                          onClick={() => withdrawMutation.mutate(consent.email)}
                        >
                          Withdraw consent
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ── Retention tab ─────────────────────────────────────── */}
        <TabsContent value="retention" className="space-y-4">
          <RetentionPolicyViewer fallbackData={MOCK_RETENTION} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
