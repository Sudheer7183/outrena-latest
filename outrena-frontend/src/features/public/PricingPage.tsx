/**
 * PricingPage.tsx — full public pricing table.
 *
 * Fetches `GET /public/plans`, renders plan cards with a monthly/yearly toggle,
 * feature lists, and CTAs to `/signup?plan={id}`. Includes a static FAQ
 * accordion at the bottom.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, Check, ChevronDown, Minus, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { publicApi } from "@/services/apiClient";
import type { Plan } from "@/types/common";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { cn, formatCurrency } from "@/lib/utils";

const FAQS = [
  {
    q: "Can I change plans later?",
    a: "Yes — upgrade or downgrade at any time. Changes are prorated automatically and reflected on your next invoice.",
  },
  {
    q: "Is there a free trial?",
    a: "Every plan includes a 14-day free trial. No credit card required to start. You can cancel anytime during the trial.",
  },
  {
    q: "What counts as a 'seat'?",
    a: "A seat is a single named user with login access to your tenant. You can deactivate users to free up seats.",
  },
  {
    q: "Do you offer discounts for startups?",
    a: "Yes — we offer 50% off the first 6 months for seed-stage companies. Reach out via the Contact page to apply.",
  },
  {
    q: "What payment methods do you accept?",
    a: "All major credit cards (Visa, Mastercard, Amex) and ACH/SEPA for annual plans over $5k.",
  },
];

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

export function PricingPage() {
  const { data: plans, isLoading } = useQuery({
    queryKey: ["public", "plans"],
    queryFn: () => publicApi.plans(),
  });
  const [yearly, setYearly] = useState(false);

  return (
    <div>
      {/* Hero */}
      <section className="border-b bg-card">
        <div className="mx-auto max-w-7xl px-4 py-16 text-center sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          >
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5" />
              Pricing
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Pricing that scales with you
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Start free. Upgrade when you grow. Cancel anytime.
            </p>
            <div className="mt-8 inline-flex items-center gap-3 rounded-full border bg-background p-1 pl-4">
              <span
                className={cn(
                  "text-sm font-medium",
                  !yearly ? "text-foreground" : "text-muted-foreground",
                )}
              >
                Monthly
              </span>
              <Switch checked={yearly} onCheckedChange={setYearly} />
              <span
                className={cn(
                  "text-sm font-medium",
                  yearly ? "text-foreground" : "text-muted-foreground",
                )}
              >
                Yearly
              </span>
              <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">
                Save 20%
              </span>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Plan cards */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        {isLoading ? (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-96 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {(plans ?? []).map((plan, i) => (
              <PlanCard key={plan.id} plan={plan} yearly={yearly} highlight={i === 1} />
            ))}
          </div>
        )}
      </section>

      {/* FAQ */}
      <section className="border-t bg-card">
        <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:px-8">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Frequently asked questions
          </h2>
          <div className="mt-8 space-y-3">
            {FAQS.map((faq) => (
              <FaqItem key={faq.q} q={faq.q} a={faq.a} />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function PlanCard({
  plan,
  yearly,
  highlight,
}: {
  plan: Plan;
  yearly: boolean;
  highlight?: boolean;
}) {
  const priceCents = yearly
    ? plan.price_yearly_cents
    : plan.price_monthly_cents;
  const featureEntries = Object.entries(plan.feature_flags ?? {});
  return (
    <Card
      className={cn(
        "flex h-full flex-col",
        highlight && "border-primary ring-1 ring-primary",
      )}
    >
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{plan.display_name || plan.name}</CardTitle>
          {highlight && (
            <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-semibold text-primary-foreground">
              Most popular
            </span>
          )}
        </div>
        <CardDescription>{plan.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div>
          <span className="text-3xl font-bold">
            {priceCents === 0
              ? "Free"
              : formatCurrency(priceCents / 100, true)}
          </span>
          {priceCents > 0 && (
            <span className="text-sm text-muted-foreground">
              {" "}
              /{yearly ? "mo, billed yearly" : "mo"}
            </span>
          )}
        </div>

        <p className="text-sm text-muted-foreground">
          Up to <strong className="text-foreground">{plan.seat_limit}</strong>{" "}
          seats
        </p>

        <ul className="flex-1 space-y-2 text-sm">
          {featureEntries.length === 0 ? (
            <li className="flex items-center gap-2 text-muted-foreground">
              <Minus className="h-4 w-4" />
              Core features included
            </li>
          ) : (
            featureEntries.map(([key, enabled]) => (
              <li key={key} className="flex items-center gap-2">
                {enabled ? (
                  <Check className="h-4 w-4 text-emerald-600" />
                ) : (
                  <Minus className="h-4 w-4 text-muted-foreground" />
                )}
                <span className={enabled ? "" : "text-muted-foreground line-through"}>
                  {FEATURE_FLAGS_LABELS[key] ?? key}
                </span>
              </li>
            ))
          )}
        </ul>

        <Button
          asChild
          className="w-full"
          variant={highlight ? "default" : "outline"}
        >
          <Link to={`/signup?plan=${plan.id}`}>
            Start free trial <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-4 p-5 text-left"
        aria-expanded={open}
      >
        <span className="text-sm font-semibold">{q}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div className="px-5 pb-5 text-sm text-muted-foreground">{a}</div>
      )}
    </Card>
  );
}
