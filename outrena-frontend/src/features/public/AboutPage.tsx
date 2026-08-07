/**
 * AboutPage.tsx — public About page.
 *
 * Static content: mission, story, values, and a team placeholder grid.
 * Uses framer-motion for entrance animations.
 */
import { motion } from "framer-motion";
import {
  Compass,
  Globe2,
  Heart,
  Lightbulb,
  ShieldCheck,
  Target,
  Users2,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const VALUES = [
  {
    icon: <ShieldCheck className="h-5 w-5" />,
    title: "Trust & Security",
    description:
      "SOC2-aligned controls, encryption at rest and in transit, and tenant-isolated data by default.",
  },
  {
    icon: <Lightbulb className="h-5 w-5" />,
    title: "Craftsmanship",
    description:
      "We sweat the details — every interaction, every error state, every millisecond of latency.",
  },
  {
    icon: <Heart className="h-5 w-5" />,
    title: "Customer Obsession",
    description:
      "We measure success by our customers' pipeline, not our vanity metrics.",
  },
  {
    icon: <Compass className="h-5 w-5" />,
    title: "Bias for Action",
    description:
      "Ship fast, learn faster. We prefer a working prototype over a perfect plan.",
  },
];

const TEAM = [
  { name: "Founding Engineer", role: "Architecture & AI" },
  { name: "Head of Product", role: "Product Strategy" },
  { name: "Design Lead", role: "UX & Brand" },
  { name: "GTM Lead", role: "Sales & Customer Success" },
];

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.4, ease: "easeOut" as const },
};

export function AboutPage() {
  return (
    <div>
      {/* Hero */}
      <section className="border-b bg-card">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="mx-auto max-w-3xl text-center"
          >
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
              <Globe2 className="h-3.5 w-3.5" />
              Our Story
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Building the operating system for revenue teams
            </h1>
            <p className="mt-6 text-lg text-muted-foreground">
              OUTRENA started with a simple question: why does outreach still
              feel like a factory line when every other part of GTM has been
              automated? We're here to fix that.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Mission */}
      <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <motion.div {...fadeUp}>
          <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Target className="h-6 w-6 text-primary" />
            Our mission
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
            To give every revenue team — regardless of size — the same
            autonomous outreach capabilities that the top 1% of companies build
            in-house. We believe the next decade of B2B growth will be won by
            teams that can run a 10x motion without 10x the headcount, and
            we're building the platform to make that possible.
          </p>
        </motion.div>
      </section>

      {/* Story */}
      <section className="border-y bg-card">
        <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
          <motion.div {...fadeUp}>
            <h2 className="text-2xl font-bold tracking-tight">Our story</h2>
            <div className="mt-4 space-y-4 text-base leading-relaxed text-muted-foreground">
              <p>
                OUTRENA was founded in 2024 by a team of ex-revenue operators
                and ML engineers who had personally felt the pain of stitching
                together prospecting, enrichment, sequencing, and analytics
                across a dozen disconnected tools.
              </p>
              <p>
                We started with a simple bet: if we could put a modern LLM at
                the center of an outreach workflow — not as a chatbot, but as
                the actual operator — we could collapse the entire stack into
                one product. Two years and 12 million messages later, that bet
                is paying off.
              </p>
              <p>
                Today, OUTRENA serves hundreds of tenants across SaaS,
                fintech, healthcare, and DTC — and we're just getting started.
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Values */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight">Our values</h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Four principles that guide every decision we make.
          </p>
        </motion.div>
        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2">
          {VALUES.map((value, i) => (
            <motion.div key={value.title} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.05 }}>
              <Card className="h-full">
                <CardHeader>
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                    {value.icon}
                  </div>
                  <CardTitle className="mt-2">{value.title}</CardTitle>
                  <CardDescription>{value.description}</CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Team placeholder */}
      <section className="border-t bg-card">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
            <h2 className="flex items-center justify-center gap-2 text-3xl font-bold tracking-tight">
              <Users2 className="h-6 w-6" />
              The team
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              A small, senior team. Hiring selectively.
            </p>
          </motion.div>
          <div className="mt-12 grid grid-cols-2 gap-6 sm:grid-cols-4">
            {TEAM.map((member, i) => (
              <motion.div
                key={member.name}
                {...fadeUp}
                transition={{ duration: 0.4, delay: i * 0.05 }}
              >
                <Card>
                  <CardContent className="flex flex-col items-center p-6 text-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted text-xl font-bold text-muted-foreground">
                      {member.name.split(" ").map((s) => s[0]).join("")}
                    </div>
                    <p className="mt-3 text-sm font-semibold">{member.name}</p>
                    <p className="text-xs text-muted-foreground">{member.role}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
