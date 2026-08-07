/**
 * BillingPage.tsx — tenant billing & subscription management (TENANT_ADMIN).
 *
 * Under <AppLayout>. Fetches:
 *   - GET /billing/subscription → current plan, status, seats, period end
 *   - GET /billing/plans → all plans (for switch)
 *   - GET /billing/invoices → invoice history
 *
 * Mutations:
 *   - POST /billing/subscribe { plan_id, integration_mode } → switch plan
 *   - POST /billing/cancel → cancel subscription
 *   - POST /billing/payment-method { payment_method_id } → update payment
 *
 * SAAS2-FE: shows integration-path pricing (platform-managed adds +$49/mo
 * delta from plan.feature_flags.integration_path_pricing) + an
 * `integration_mode` toggle (platform_managed vs tenant_managed) that is
 * forwarded to /billing/subscribe.
 *
 * All mutations invalidate queries + show toasts. Cancel opens confirm dialog.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  CheckCircle2,
  CreditCard,
  KeyRound,
  Plug,
  Receipt,
  Users2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import type { Invoice, IntegrationMode, Plan, Subscription } from "@/types/common";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { cn, formatCurrency, formatDate } from "@/lib/utils";

const FEATURE_FLAGS_LABELS: Record<string, string> = {
  autopilot: "Autopilot prospecting",
  icp_scoring: "ICP-driven scoring",
  email_sequences: "Email sequences",
  linkedin_sequences: "LinkedIn sequences",
  reply_autopilot: "Reply auto-pilot",
  ab_testing: "A/B testing",
  analytics: "Advanced analytics",
  api_access: "API access",
  sso: "SSO / SAML",
  audit_logs: "Audit logs",
  priority_support: "Priority support",
  dedicated_csm: "Dedicated CSM",
};

function statusVariant(status: string | undefined | null) {
  // BUG-07 FIX: Guard against undefined/null status before calling .toLowerCase()
  switch ((status ?? "").toLowerCase()) {
    case "active":
    case "trialing":
      return "success" as const;
    case "past_due":
      return "warning" as const;
    case "canceled":
    case "cancelled":
      return "destructive" as const;
    default:
      return "secondary" as const;
  }
}

export function BillingPage() {
  const queryClient = useQueryClient();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [paymentMethodId, setPaymentMethodId] = useState("");
  // SAAS2-FE: integration mode toggle — included in every /billing/subscribe
  // call so the backend can compute the effective price (base + delta).
  const [integrationMode, setIntegrationMode] =
    useState<IntegrationMode>("tenant_managed");

  const { data: subscription, isLoading: subLoading } = useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: () => http.get<Subscription>("/api/v1/billing/subscription"),
  });

  const { data: plans } = useQuery({
    queryKey: ["billing", "plans"],
    queryFn: () => http.get<Plan[]>("/api/v1/billing/plans"),
  });

  const { data: invoices, isLoading: invLoading } = useQuery({
    queryKey: ["billing", "invoices"],
    queryFn: () => http.get<Invoice[]>("/api/v1/billing/invoices"),
  });

  const subscribeMutation = useMutation({
    mutationFn: (planId: string) =>
      http.post<{ subscription_id: string; client_secret?: string; effective_price_cents?: number }>(
        "/api/v1/billing/subscribe",
        { plan_id: planId, integration_mode: integrationMode },
      ),
    onSuccess: (data) => {
      const extra =
        typeof data.effective_price_cents === "number"
          ? ` · ${formatCurrency(data.effective_price_cents / 100, true)}/mo`
          : "";
      toast.success(`Subscription updated${extra}`);
      queryClient.invalidateQueries({ queryKey: ["billing"] });
    },
    onError: () => toast.error("Failed to update subscription"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => http.post("/api/v1/billing/cancel"),
    onSuccess: () => {
      toast.success("Subscription cancelled");
      queryClient.invalidateQueries({ queryKey: ["billing"] });
      setCancelOpen(false);
    },
    onError: () => toast.error("Failed to cancel subscription"),
  });

  const paymentMutation = useMutation({
    mutationFn: (pmId: string) =>
      http.post("/api/v1/billing/payment-method", { payment_method_id: pmId }),
    onSuccess: () => {
      toast.success("Payment method updated");
      setPaymentMethodId("");
      queryClient.invalidateQueries({ queryKey: ["billing"] });
    },
    onError: () => toast.error("Failed to update payment method"),
  });

  const currentPlanId = subscription?.plan?.id;
  const seatPct = subscription
    ? Math.min(100, (subscription.seats_used / (subscription.plan?.seat_limit || 1)) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing"
        description="Manage your subscription, payment method, and invoice history."
      />

      {/* Current plan + usage */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Current Plan</CardTitle>
            <CardDescription>
              Your subscription details and renewal date.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {subLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : subscription ? (
              <>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-2xl font-bold">
                      {subscription.plan?.display_name || subscription.plan?.name || "Current Plan"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {subscription.plan?.description ?? ""}
                    </p>
                  </div>
                  <Badge variant={statusVariant(subscription.status)}>
                    {subscription.status}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-4 border-t pt-4">
                  <div>
                    <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      <CreditCard className="h-3 w-3" />
                      Price
                    </p>
                    <p className="mt-1 text-lg font-semibold">
                      {(subscription.plan?.price_monthly_cents ?? 0) === 0
                        ? "Free"
                        : formatCurrency((subscription.plan?.price_monthly_cents ?? 0) / 100, true) + "/mo"}
                    </p>
                  </div>
                  <div>
                    <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      <CalendarClock className="h-3 w-3" />
                      Renews
                    </p>
                    <p className="mt-1 text-lg font-semibold">
                      {formatDate(subscription.current_period_end)}
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <EmptyState
                title="No subscription"
                description="Choose a plan below to start your subscription."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users2 className="h-5 w-5" />
              Seat Usage
            </CardTitle>
            <CardDescription>Active seats in your tenant.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {subscription ? (
              <>
                <div className="flex items-end justify-between">
                  <span className="text-3xl font-bold tabular-nums">
                    {subscription.seats_used}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    of {subscription.plan?.seat_limit ?? "—"} seats
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full transition-all",
                      seatPct > 90 ? "bg-red-600" : "bg-emerald-600",
                    )}
                    style={{ width: `${seatPct}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {seatPct.toFixed(0)}% utilized
                </p>
              </>
            ) : (
              <Skeleton className="h-16 w-full" />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Switch plan */}
      <Card>
        <CardHeader>
          <CardTitle>Switch Plan</CardTitle>
          <CardDescription>
            Upgrade or downgrade at any time. Changes are prorated.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* SAAS2-FE: integration-mode toggle */}
          <div className="rounded-lg border bg-muted/30 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  <Plug className="h-4 w-4" />
                  Integration mode
                </p>
                <p className="text-xs text-muted-foreground">
                  Choose whether OUTRENA provides integration keys
                  (platform-managed, +$49/mo) or you provide your own.
                </p>
              </div>
              <div className="flex rounded-md border bg-background p-0.5">
                <button
                  type="button"
                  onClick={() => setIntegrationMode("tenant_managed")}
                  className={cn(
                    "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
                    integrationMode === "tenant_managed"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <KeyRound className="h-3 w-3" />
                  My own keys
                </button>
                <button
                  type="button"
                  onClick={() => setIntegrationMode("platform_managed")}
                  className={cn(
                    "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
                    integrationMode === "platform_managed"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <Plug className="h-3 w-3" />
                  Platform-managed (+$49/mo)
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {(plans ?? []).map((plan) => {
              const isCurrent = plan.id === currentPlanId;
              // SAAS2-FE: derive integration-path delta (defaults to $49 if
              // the backend hasn't populated feature_flags yet).
              const rawPricing = (plan.feature_flags as Record<string, unknown> | null)?.integration_path_pricing;
              const pricing = (rawPricing && typeof rawPricing === "object"
                ? (rawPricing as {
                    platform_managed_delta_cents?: number;
                    tenant_managed_delta_cents?: number;
                  })
                : {});
              const platformDelta =
                pricing.platform_managed_delta_cents ?? 4900;
              const effectivePriceCents =
                integrationMode === "platform_managed"
                  ? plan.price_monthly_cents + platformDelta
                  : plan.price_monthly_cents;
              return (
                <Card
                  key={plan.id}
                  className={cn(
                    "flex flex-col",
                    isCurrent && "border-primary ring-1 ring-primary",
                  )}
                >
                  <CardHeader>
                    <CardTitle className="text-base">
                      {plan.display_name || plan.name}
                    </CardTitle>
                    <CardDescription>{plan.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-1 flex-col gap-3">
                    <div>
                      <p className="text-2xl font-bold">
                        {effectivePriceCents === 0
                          ? "Free"
                          : formatCurrency(effectivePriceCents / 100, true) + "/mo"}
                      </p>
                      {integrationMode === "platform_managed" &&
                        platformDelta > 0 && (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            (base{" "}
                            {plan.price_monthly_cents === 0
                              ? "Free"
                              : formatCurrency(plan.price_monthly_cents / 100, true)}
                            {" "}+ {formatCurrency(platformDelta / 100, true)} platform fee)
                          </p>
                        )}
                    </div>
                    <ul className="flex-1 space-y-1.5 text-xs text-muted-foreground">
                      <li>Up to {plan.seat_limit} seats</li>
                      <li className="flex items-center gap-1.5">
                        <KeyRound className="h-3 w-3" />
                        {integrationMode === "platform_managed"
                          ? "Platform-provided integration keys"
                          : "Bring your own integration keys"}
                      </li>
                      {Object.entries(plan.feature_flags ?? {})
                        .filter(([k, v]) => v && k !== "integration_path_pricing")
                        .slice(0, 3)
                        .map(([k]) => (
                          <li key={k} className="flex items-center gap-1.5">
                            <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                            {FEATURE_FLAGS_LABELS[k] ?? k}
                          </li>
                        ))}
                    </ul>
                    <Button
                      size="sm"
                      variant={isCurrent ? "outline" : "default"}
                      disabled={isCurrent || subscribeMutation.isPending}
                      onClick={() => subscribeMutation.mutate(plan.id)}
                    >
                      {isCurrent ? "Current plan" : "Switch to this plan"}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Payment method + cancel */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Payment Method</CardTitle>
            <CardDescription>
              Update the card on file for your subscription.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-md border bg-muted/50 p-3 text-sm">
              <p className="font-mono text-xs text-muted-foreground">
                Current: **** **** **** 4242 (Visa)
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pm-id">New payment method ID</Label>
              <Input
                id="pm-id"
                value={paymentMethodId}
                onChange={(e) => setPaymentMethodId(e.target.value)}
                placeholder="pm_xxxxxxxxxxxxx"
              />
              <p className="text-xs text-muted-foreground">
                In production this is collected via Stripe Elements; here we
                accept the token directly.
              </p>
            </div>
            <Button
              onClick={() => paymentMutation.mutate(paymentMethodId)}
              disabled={!paymentMethodId.trim() || paymentMutation.isPending}
            >
              Update payment method
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-red-700 dark:text-red-300">
              Cancel Subscription
            </CardTitle>
            <CardDescription>
              Cancellation takes effect at the end of the current billing
              period.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              You'll retain access until{" "}
              <strong>
                {formatDate(subscription?.current_period_end)}
              </strong>
              . After that, your tenant will be read-only.
            </p>
            <Button
              variant="destructive"
              onClick={() => setCancelOpen(true)}
              disabled={!subscription}
            >
              <XCircle className="h-4 w-4" />
              Cancel subscription
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Invoices */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Receipt className="h-5 w-5" />
            Invoice History
          </CardTitle>
          <CardDescription>
            All invoices for this tenant, newest first.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {invLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (invoices ?? []).length === 0 ? (
            <EmptyState
              icon={<Receipt className="h-6 w-6" />}
              title="No invoices yet"
              description="Invoices will appear here once your trial ends."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Paid</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(invoices ?? []).map((inv) => (
                  <TableRow key={inv.id}>
                    <TableCell className="font-mono text-xs">{inv.id}</TableCell>
                    <TableCell className="font-medium tabular-nums">
                      {formatCurrency(inv.amount_cents / 100, true)}{" "}
                      <span className="text-xs text-muted-foreground">
                        {inv.currency.toUpperCase()}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(inv.period_start)} →{" "}
                      {formatDate(inv.period_end)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          inv.status === "paid"
                            ? "success"
                            : inv.status === "void"
                              ? "secondary"
                              : "warning"
                        }
                      >
                        {inv.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(inv.paid_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Cancel dialog */}
      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogClose onClose={() => setCancelOpen(false)} />
        <DialogHeader>
          <DialogTitle>Cancel subscription?</DialogTitle>
          <DialogDescription>
            This cannot be undone. You'll retain access until the end of your
            current billing period, after which your tenant will become
            read-only.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setCancelOpen(false)}>
            Keep subscription
          </Button>
          <Button
            variant="destructive"
            onClick={() => cancelMutation.mutate()}
            disabled={cancelMutation.isPending}
          >
            Confirm cancellation
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
