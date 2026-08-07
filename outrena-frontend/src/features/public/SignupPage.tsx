/**
 * SignupPage.tsx — self-serve tenant signup wizard.
 *
 * 5 steps (SAAS2-FE adds the Integration Setup step between Plan and Review):
 *   1. Company name + subdomain (with live availability check)
 *   2. Owner details (first/last/email/password)
 *   3. Choose plan (from GET /public/plans; preselected via ?plan= query)
 *   4. Integration setup (platform-managed +$49/mo vs tenant-managed)
 *   5. Review + submit → POST /tenant-signup → redirect to /signup/status/:id
 *
 * Uses TanStack Query for plan list + subdomain check, useMutation for submit.
 * All steps handled with local state + a step index.
 */
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  CreditCard,
  KeyRound,
  Loader2,
  Lock,
  Plug,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { publicApi } from "@/services/apiClient";
import type { IntegrationMode, Plan } from "@/types/common";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatCurrency } from "@/lib/utils";

const DOMAIN_HINT = "outrena.app";

const SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$/;

type Step = 1 | 2 | 3 | 4 | 5;

export function SignupPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const presetPlan = searchParams.get("plan");

  const [step, setStep] = useState<Step>(1);
  const [companyName, setCompanyName] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [planId, setPlanId] = useState<string>("");
  // SAAS2-FE: integration mode selected during signup
  const [integrationMode, setIntegrationMode] =
    useState<IntegrationMode>("tenant_managed");

  const { data: plans, isLoading: plansLoading } = useQuery({
    queryKey: ["public", "plans"],
    queryFn: () => publicApi.plans(),
  });

  // Preset plan from URL once data loads.
  useEffect(() => {
    if (presetPlan && plans && !planId) {
      setPlanId(presetPlan);
    }
  }, [presetPlan, plans, planId]);

  const selectedPlan = useMemo(
    () => (plans ?? []).find((p) => p.id === planId),
    [plans, planId],
  );

  const submitMutation = useMutation({
    mutationFn: () =>
      publicApi.submitSignup({
        company_name: companyName.trim(),
        subdomain: subdomain.trim().toLowerCase(),
        owner_email: email.trim(),
        owner_first_name: firstName.trim(),
        owner_last_name: lastName.trim(),
        plan_id: planId,
        integration_mode: integrationMode,
      }),
    onSuccess: (data) => {
      toast.success("Signup submitted! Your workspace is being provisioned.");
      navigate(`/signup/status/${data.signup_id}`, { replace: true });
    },
    onError: () => {
      toast.error("Failed to submit signup. Please try again.");
    },
  });

  function next() {
    if (step === 1) {
      if (!companyName.trim()) return toast.error("Company name is required.");
      if (!SLUG_PATTERN.test(subdomain.trim()))
        return toast.error(
          "Subdomain must be 3–32 chars, lowercase letters, numbers, and hyphens (no leading/trailing hyphen).",
        );
    }
    if (step === 2) {
      if (!firstName.trim() || !lastName.trim())
        return toast.error("First and last name are required.");
      if (!email.includes("@"))
        return toast.error("Enter a valid email address.");
      if (password.length < 8)
        return toast.error("Password must be at least 8 characters.");
    }
    if (step === 3) {
      if (!planId) return toast.error("Please select a plan.");
    }
    setStep((s) => (Math.min(5, s + 1) as Step));
  }

  function back() {
    setStep((s) => (Math.max(1, s - 1) as Step));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    submitMutation.mutate();
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Stepper */}
        <div className="mb-8 flex items-center justify-between">
          {[
            { n: 1, label: "Company", icon: Building2 },
            { n: 2, label: "Your details", icon: User },
            { n: 3, label: "Plan", icon: CreditCard },
            { n: 4, label: "Integration", icon: Plug },
            { n: 5, label: "Review", icon: CheckCircle2 },
          ].map(({ n, label, icon: Icon }, idx, arr) => (
            <div key={n} className="flex flex-1 items-center">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                    step >= n
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card text-muted-foreground",
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <span
                  className={cn(
                    "hidden text-xs font-medium sm:block",
                    step >= n ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {label}
                </span>
              </div>
              {idx < arr.length - 1 && (
                <div
                  className={cn(
                    "mx-2 h-0.5 flex-1",
                    step > n ? "bg-primary" : "bg-border",
                  )}
                />
              )}
            </div>
          ))}
        </div>

        <motion.div
          key={step}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
        >
          <Card>
            <CardHeader>
              <CardTitle>
                {step === 1 && "Tell us about your company"}
                {step === 2 && "Your account details"}
                {step === 3 && "Choose your plan"}
                {step === 4 && "Integration setup"}
                {step === 5 && "Review & submit"}
              </CardTitle>
              <CardDescription>
                {step === 1 && "This is the workspace your team will use to sign in."}
                {step === 2 && "You'll be the workspace owner and TENANT_ADMIN."}
                {step === 3 && "You can change this anytime from billing settings."}
                {step === 4 && "Choose whether OUTRENA provides integration keys or you bring your own."}
                {step === 5 && "Confirm the details below and we'll provision your workspace."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {step === 1 && (
                  <StepCompany
                    companyName={companyName}
                    setCompanyName={setCompanyName}
                    subdomain={subdomain}
                    setSubdomain={setSubdomain}
                  />
                )}

                {step === 2 && (
                  <StepOwner
                    firstName={firstName}
                    setFirstName={setFirstName}
                    lastName={lastName}
                    setLastName={setLastName}
                    email={email}
                    setEmail={setEmail}
                    password={password}
                    setPassword={setPassword}
                  />
                )}

                {step === 3 && (
                  <StepPlan
                    plans={plans ?? []}
                    loading={plansLoading}
                    planId={planId}
                    setPlanId={setPlanId}
                  />
                )}

                {step === 4 && (
                  <StepIntegration
                    mode={integrationMode}
                    setMode={setIntegrationMode}
                    selectedPlan={selectedPlan}
                  />
                )}

                {step === 5 && (
                  <StepReview
                    companyName={companyName}
                    subdomain={subdomain}
                    firstName={firstName}
                    lastName={lastName}
                    email={email}
                    plan={selectedPlan}
                    integrationMode={integrationMode}
                  />
                )}

                {/* Nav buttons */}
                <div className="flex items-center justify-between pt-4">
                  {step > 1 ? (
                    <Button type="button" variant="outline" onClick={back}>
                      <ArrowLeft className="h-4 w-4" /> Back
                    </Button>
                  ) : (
                    <span />
                  )}

                  {step < 5 ? (
                    <Button type="button" onClick={next}>
                      Continue <ArrowRight className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      type="submit"
                      disabled={submitMutation.isPending}
                    >
                      {submitMutation.isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Submitting…
                        </>
                      ) : (
                        <>
                          Submit signup <ArrowRight className="h-4 w-4" />
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </form>
            </CardContent>
          </Card>
        </motion.div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Already have an account?{" "}
          <a href="/login" className="font-medium text-foreground hover:underline">
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
}

function StepCompany({
  companyName,
  setCompanyName,
  subdomain,
  setSubdomain,
}: {
  companyName: string;
  setCompanyName: (v: string) => void;
  subdomain: string;
  setSubdomain: (v: string) => void;
}) {
  // Live availability check (debounced via TanStack Query staleTime).
  const { data: availability, isLoading } = useQuery({
    queryKey: ["public", "subdomain-check", subdomain],
    queryFn: () => publicApi.checkSubdomain(subdomain.trim().toLowerCase()),
    enabled: SLUG_PATTERN.test(subdomain.trim()),
    staleTime: 30_000,
  });

  const valid = SLUG_PATTERN.test(subdomain.trim());
  const available = availability?.available === true;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="company-name">Company name *</Label>
        <Input
          id="company-name"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          placeholder="Acme Inc."
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="subdomain">Workspace subdomain *</Label>
        <div className="flex items-center gap-2">
          <Input
            id="subdomain"
            value={subdomain}
            onChange={(e) => setSubdomain(e.target.value.toLowerCase())}
            placeholder="acme"
            className="flex-1"
            required
          />
          <span className="text-sm text-muted-foreground">.{DOMAIN_HINT}</span>
        </div>
        <SubdomainStatus
          loading={isLoading}
          valid={valid}
          available={available}
          subdomain={subdomain}
        />
      </div>
    </div>
  );
}

function SubdomainStatus({
  loading,
  valid,
  available,
  subdomain,
}: {
  loading: boolean;
  valid: boolean;
  available: boolean;
  subdomain: string;
}) {
  if (!subdomain) {
    return (
      <p className="text-xs text-muted-foreground">
        Choose a unique subdomain for your workspace (e.g.{" "}
        <code className="rounded bg-muted px-1 py-0.5">acme.{DOMAIN_HINT}</code>).
      </p>
    );
  }
  if (!valid) {
    return (
      <p className="text-xs text-amber-600">
        Must be 3–32 chars: lowercase letters, numbers, hyphens. No
        leading/trailing hyphen.
      </p>
    );
  }
  if (loading) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Checking availability…
      </p>
    );
  }
  if (available) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-emerald-600">
        <CheckCircle2 className="h-3 w-3" />
        <code>{subdomain}.{DOMAIN_HINT}</code> is available.
      </p>
    );
  }
  return (
    <p className="text-xs text-red-600">
      <code>{subdomain}.{DOMAIN_HINT}</code> is already taken. Try another.
    </p>
  );
}

function StepOwner({
  firstName,
  setFirstName,
  lastName,
  setLastName,
  email,
  setEmail,
  password,
  setPassword,
}: {
  firstName: string;
  setFirstName: (v: string) => void;
  lastName: string;
  setLastName: (v: string) => void;
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="first-name">First name *</Label>
          <Input
            id="first-name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            placeholder="Jane"
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="last-name">Last name *</Label>
          <Input
            id="last-name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            placeholder="Doe"
            required
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="signup-email">Work email *</Label>
        <Input
          id="signup-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jane@acme.com"
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="signup-password">Password *</Label>
        <div className="relative">
          <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="signup-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            className="pl-9"
            required
          />
        </div>
        <p className="text-xs text-muted-foreground">
          You'll use this email and password to sign in to your workspace.
        </p>
      </div>
    </div>
  );
}

function StepPlan({
  plans,
  loading,
  planId,
  setPlanId,
}: {
  plans: Plan[];
  loading: boolean;
  planId: string;
  setPlanId: (v: string) => void;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {plans.map((plan) => {
        const selected = plan.id === planId;
        return (
          <button
            key={plan.id}
            type="button"
            onClick={() => setPlanId(plan.id)}
            className={cn(
              "flex flex-col gap-2 rounded-lg border p-4 text-left transition-colors",
              selected
                ? "border-primary ring-1 ring-primary"
                : "hover:border-primary/50",
            )}
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold">{plan.display_name || plan.name}</p>
              {selected && (
                <CheckCircle2 className="h-4 w-4 text-primary" />
              )}
            </div>
            <p className="text-sm text-muted-foreground">{plan.description}</p>
            <p className="mt-auto text-lg font-bold">
              {plan.price_monthly_cents === 0
                ? "Free"
                : formatCurrency(plan.price_monthly_cents / 100, true) + "/mo"}
            </p>
            <p className="text-xs text-muted-foreground">
              Up to {plan.seat_limit} seats
            </p>
          </button>
        );
      })}
    </div>
  );
}

function StepReview({
  companyName,
  subdomain,
  firstName,
  lastName,
  email,
  plan,
  integrationMode,
}: {
  companyName: string;
  subdomain: string;
  firstName: string;
  lastName: string;
  email: string;
  plan?: Plan;
  integrationMode: IntegrationMode;
}) {
  const platformDelta = 49;
  const rows = [
    { label: "Company", value: companyName },
    { label: "Workspace URL", value: `${subdomain}.${DOMAIN_HINT}` },
    { label: "Owner", value: `${firstName} ${lastName}` },
    { label: "Email", value: email },
    {
      label: "Plan",
      value: plan
        ? `${plan.display_name || plan.name} (${plan.price_monthly_cents === 0 ? "Free" : formatCurrency(plan.price_monthly_cents / 100, true) + "/mo"})`
        : "—",
    },
    {
      label: "Integration mode",
      value:
        integrationMode === "platform_managed"
          ? `Platform-managed (+$${platformDelta}/mo)`
          : "Tenant-managed (your own keys)",
    },
  ];
  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-lg border">
        <dl className="divide-y">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex items-center justify-between gap-4 px-4 py-3"
            >
              <dt className="text-sm font-medium text-muted-foreground">
                {row.label}
              </dt>
              <dd className="text-sm font-semibold">{row.value}</dd>
            </div>
          ))}
        </dl>
      </div>
      <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
        After submitting, your workspace will be provisioned and pending
        approval. You'll receive an email when it's ready.
      </p>
    </div>
  );
}

function StepIntegration({
  mode,
  setMode,
  selectedPlan,
}: {
  mode: IntegrationMode;
  setMode: (m: IntegrationMode) => void;
  selectedPlan?: Plan;
}) {
  const platformDelta = 49;
  const baseLabel = selectedPlan
    ? selectedPlan.price_monthly_cents === 0
      ? "Free"
      : formatCurrency(selectedPlan.price_monthly_cents / 100, true) + "/mo"
    : "";
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Choose how you want to handle integrations (Apollo, Hunter, SendGrid,
        etc.). You can switch later from the Integration Config page.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => setMode("platform_managed")}
          className={cn(
            "flex flex-col gap-2 rounded-lg border p-4 text-left transition-colors",
            mode === "platform_managed"
              ? "border-primary ring-1 ring-primary"
              : "hover:border-primary/50",
          )}
        >
          <div className="flex items-center justify-between">
            <Plug className="h-5 w-5 text-primary" />
            {mode === "platform_managed" && (
              <CheckCircle2 className="h-4 w-4 text-primary" />
            )}
          </div>
          <p className="font-semibold">Platform-managed</p>
          <p className="text-sm text-muted-foreground">
            OUTRENA provides activation keys for all supported integrations.
          </p>
          <p className="mt-auto text-xs font-medium text-amber-700 dark:text-amber-300">
            +${platformDelta}/mo added to your plan
          </p>
        </button>

        <button
          type="button"
          onClick={() => setMode("tenant_managed")}
          className={cn(
            "flex flex-col gap-2 rounded-lg border p-4 text-left transition-colors",
            mode === "tenant_managed"
              ? "border-primary ring-1 ring-primary"
              : "hover:border-primary/50",
          )}
        >
          <div className="flex items-center justify-between">
            <KeyRound className="h-5 w-5 text-primary" />
            {mode === "tenant_managed" && (
              <CheckCircle2 className="h-4 w-4 text-primary" />
            )}
          </div>
          <p className="font-semibold">Tenant-managed</p>
          <p className="text-sm text-muted-foreground">
            You provide your own API keys for integrations after signup.
          </p>
          <p className="mt-auto text-xs font-medium text-muted-foreground">
            No additional fee — base plan price{selectedPlan ? ` (${baseLabel})` : ""}
          </p>
        </button>
      </div>
      <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
        {mode === "platform_managed" ? (
          <p>
            <strong>Platform-managed:</strong> OUTRENA maintains a shared pool
            of activation keys. New integrations work out-of-the-box. A
            surcharge is added to your monthly plan.
          </p>
        ) : (
          <p>
            <strong>Tenant-managed:</strong> You'll provide API keys for each
            integration via the Integration Config page after signup. Keys are
            encrypted at rest in your tenant schema.
          </p>
        )}
      </div>
    </div>
  );
}
