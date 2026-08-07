/**
 * LandingPage.tsx — public marketing hero.
 *
 * Fetches `GET /public/landing` for product features + headline stats. Renders:
 *   - Hero (headline + subhead + "Start free" / "Book demo" CTAs)
 *   - Stats band (tenants, users, messages sent)
 *   - Features grid (from API, with icon fallbacks)
 *   - How-it-works (3 steps)
 *   - Pricing preview (top 3 plans via `GET /public/plans`)
 *   - Testimonials placeholder
 *   - Final CTA band
 *
 * Uses framer-motion for subtle entrance animations. No indigo/blue.
 */
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  LineChart,
  Mail,
  Sparkles,
  Target,
  Users2,
  Zap,
} from "lucide-react";
import { Link } from "react-router-dom";
import { publicApi } from "@/services/apiClient";
import type { LandingContent, Plan } from "@/types/common";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";

const MOCK_LANDING: LandingContent = {
  product: {
    name: "OUTRENA",
    tagline: "The AI-Powered Outreach Operating System",
    description:
      "OUTRENA unifies prospecting, outreach, and pipeline optimization into a single autonomous workflow — so your team can run a 10x motion without 10x the headcount.",
    features: [
      {
        icon: "bot",
        title: "Autopilot Prospecting",
        description:
          "Continuously source and enrich net-new prospects matching your ICP, on a schedule you control.",
      },
      {
        icon: "target",
        title: "ICP-Driven Scoring",
        description:
          "Define Ideal Customer Profiles with firmographic, technographic, and intent signals.",
      },
      {
        icon: "mail",
        title: "Multi-Channel Sequences",
        description:
          "Generate framework-aware Email + LinkedIn sequences per prospect, QA-scored before send.",
      },
      {
        icon: "bot",
        title: "Reply Auto-Pilot",
        description:
          "Categorize inbound replies and respond automatically with context-aware follow-ups.",
      },
      {
        icon: "chart",
        title: "Analytics & A/B Testing",
        description:
          "Reply rates, A/B winners, pipeline value, and weekly digest roll up automatically.",
      },
      {
        icon: "users",
        title: "Team Roles & RBAC",
        description:
          "Granular role hierarchy and per-feature permission gating across your tenant.",
      },
    ],
  },
  stats: {
    tenants: 420,
    users: 3_200,
    messages_sent: 12_800_000,
  },
};

const HOW_IT_WORKS = [
  {
    icon: <Target className="h-5 w-5" />,
    title: "Define your ICP",
    description:
      "Auto-discover from your top customers or hand-craft firmographic + intent filters.",
  },
  {
    icon: <Bot className="h-5 w-5" />,
    title: "Run Autopilot",
    description:
      "OUTRENA sources, enriches, and scores net-new prospects continuously.",
  },
  {
    icon: <Mail className="h-5 w-5" />,
    title: "Send & Optimize",
    description:
      "Multi-touch sequences with QA-scored copy, then optimize with A/B tests.",
  },
];

const TESTIMONIALS = [
  {
    quote:
      "OUTRENA tripled our qualified pipeline in one quarter. The autopilot alone replaced two SDRs.",
    name: "Amelia Chen",
    role: "VP Sales, Acme",
  },
  {
    quote:
      "The reply auto-pilot handles 70% of inbound replies hands-off. Our team focuses on the 30% that matter.",
    name: "Marcus Lee",
    role: "Head of GTM, Globex",
  },
  {
    quote:
      "Best-in-class ICP scoring. We finally know which prospects are worth our time before we send.",
    name: "Priya Nair",
    role: "Director RevOps, Initech",
  },
];

function featureIcon(name: string) {
  switch (name) {
    case "bot":
      return <Bot className="h-5 w-5" />;
    case "target":
      return <Target className="h-5 w-5" />;
    case "mail":
      return <Mail className="h-5 w-5" />;
    case "chart":
      return <LineChart className="h-5 w-5" />;
    case "users":
      return <Users2 className="h-5 w-5" />;
    default:
      return <Sparkles className="h-5 w-5" />;
  }
}

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.4, ease: "easeOut" as const },
};

export function LandingPage() {
  const { data: landing, isLoading: landingLoading } = useQuery({
    queryKey: ["public", "landing"],
    queryFn: () => publicApi.landing(),
  });
  const { data: plans } = useQuery({
    queryKey: ["public", "plans"],
    queryFn: () => publicApi.plans(),
  });

  const content = landing ?? MOCK_LANDING;
  const features = content.product?.features ?? MOCK_LANDING.product.features;
  const stats = content.stats ?? MOCK_LANDING.stats;
  const topPlans = (plans ?? []).slice(0, 3);

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden border-b">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-50"
          style={{
            background:
              "radial-gradient(40rem 30rem at 80% -20%, hsl(var(--primary)/0.08), transparent 60%), radial-gradient(40rem 25rem at 0% 100%, hsl(var(--primary)/0.05), transparent 60%)",
          }}
        />
        <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="mx-auto max-w-3xl text-center"
          >
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5" />
              AI-Powered Outreach Operating System
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
              {content.product?.tagline ?? "Outreach on autopilot."}
            </h1>
            <p className="mt-6 text-lg text-muted-foreground sm:text-xl">
              {content.product?.description ?? MOCK_LANDING.product.description}
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild size="lg">
                <Link to="/signup">
                  Start free <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/p/contact">Book a demo</Link>
              </Button>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              No credit card required · 14-day trial · Cancel anytime
            </p>
          </motion.div>
        </div>
      </section>

      {/* Stats band */}
      <section className="border-b bg-card">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-10 sm:grid-cols-3 sm:px-6 lg:px-8">
          {[
            { label: "Tenants onboarded", value: stats.tenants.toLocaleString() },
            { label: "Active users", value: stats.users.toLocaleString() },
            {
              label: "Messages sent",
              value: `${(stats.messages_sent / 1_000_000).toFixed(1)}M`,
            },
          ].map((s) => (
            <motion.div key={s.label} {...fadeUp} className="text-center">
              <p className="text-3xl font-bold tabular-nums sm:text-4xl">
                {s.value}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{s.label}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Features grid */}
      <section id="features" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need to run outreach at scale
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Six pillars of the OUTRENA platform, working together as one
            autonomous workflow.
          </p>
        </motion.div>

        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {landingLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-44 w-full" />
              ))
            : features.map((feature, i) => (
                <motion.div key={feature.title} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.05 }}>
                  <Card className="h-full">
                    <CardHeader>
                      <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                        {featureIcon(feature.icon)}
                      </div>
                      <CardTitle className="mt-2">{feature.title}</CardTitle>
                      <CardDescription>{feature.description}</CardDescription>
                    </CardHeader>
                  </Card>
                </motion.div>
              ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y bg-card">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              From zero to sending in 5 minutes
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Three steps. One autonomous pipeline.
            </p>
          </motion.div>
          <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
            {HOW_IT_WORKS.map((step, i) => (
              <motion.div key={step.title} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.08 }}>
                <Card className="h-full">
                  <CardContent className="p-6">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
                        {step.icon}
                      </div>
                      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        Step {i + 1}
                      </span>
                    </div>
                    <p className="mt-3 text-base font-semibold">{step.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {step.description}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing preview */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Simple, transparent pricing
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Start free. Upgrade when you grow.
          </p>
        </motion.div>
        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
          {topPlans.length > 0
            ? topPlans.map((plan, i) => (
                <motion.div key={plan.id} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.05 }}>
                  <PlanPreviewCard plan={plan} highlight={i === 1} />
                </motion.div>
              ))
            : Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-64 w-full" />
              ))}
        </div>
        <div className="mt-8 text-center">
          <Button asChild variant="outline">
            <Link to="/p/pricing">
              Compare all plans <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </section>

      {/* Testimonials */}
      <section className="border-t bg-card">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Loved by revenue teams
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Don't take our word for it.
            </p>
          </motion.div>
          <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
            {TESTIMONIALS.map((t, i) => (
              <motion.div key={t.name} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card className="h-full">
                  <CardContent className="flex h-full flex-col p-6">
                    <Zap className="h-5 w-5 text-primary" />
                    <p className="mt-3 flex-1 text-sm leading-relaxed">
                      "{t.quote}"
                    </p>
                    <div className="mt-4 border-t pt-4">
                      <p className="text-sm font-semibold">{t.name}</p>
                      <p className="text-xs text-muted-foreground">{t.role}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t">
        <div className="mx-auto max-w-4xl px-4 py-20 text-center sm:px-6 lg:px-8">
          <motion.div {...fadeUp}>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Ready to put your outreach on autopilot?
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Start your 14-day free trial. No credit card required.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild size="lg">
                <Link to="/signup">
                  Start free <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/p/contact">Talk to sales</Link>
              </Button>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}

function PlanPreviewCard({ plan, highlight }: { plan: Plan; highlight?: boolean }) {
  return (
    <Card className={highlight ? "border-primary ring-1 ring-primary" : ""}>
      <CardHeader>
        <CardTitle>{plan.display_name || plan.name}</CardTitle>
        <CardDescription>{plan.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <span className="text-3xl font-bold">
            {formatCurrency(plan.price_monthly_cents / 100, true)}
          </span>
          <span className="text-sm text-muted-foreground"> /mo</span>
        </div>
        <ul className="space-y-2 text-sm">
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            Up to {plan.seat_limit} seats
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            All core features
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            Email + LinkedIn sequences
          </li>
        </ul>
        <Button asChild className="w-full" variant={highlight ? "default" : "outline"}>
          <Link to={`/signup?plan=${plan.id}`}>Start free trial</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
