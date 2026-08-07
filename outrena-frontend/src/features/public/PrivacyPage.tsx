/**
 * PrivacyPage.tsx — enhanced static privacy policy.
 *
 * Sections: overview, data we collect, how we use, sharing, security, GDPR
 * rights, lawful bases, data retention, sub-processors, DPA link, contact.
 *
 * Enhanced (SAAS2-FE) to add:
 *   - GDPR rights section (6 rights) with link to /p/gdpr-rights
 *   - DPO contact section (dpo@outrena.io + 30-day SLA)
 *   - Lawful bases section (Art 6)
 *   - Sub-processors section (AWS / Azure / Stripe / Keycloak / LLM providers)
 *   - Data retention summary
 *   - Link to DPA at /p/dpa
 */
import { motion } from "framer-motion";
import { ExternalLink, Scale, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const SECTIONS = [
  {
    title: "1. Overview",
    body: [
      "This Privacy Policy describes how OUTRENA ('we', 'us', 'our') collects, uses, and protects information about you when you use our SaaS platform, marketing site, and related services (the 'Service').",
      "We are committed to being transparent about our data practices and to giving you meaningful control over your information. This policy is structured to make it easy to find the answers to the questions that matter most to you.",
    ],
  },
  {
    title: "2. Data we collect",
    body: [
      "Account data: name, email address, company, role, and authentication identifiers submitted during signup or invite flows.",
      "Usage data: feature engagement, page views, API calls, IP address, browser type, and device identifiers collected automatically when you use the Service.",
      "Content data: any prospect, campaign, sequence, and message content you or your team create or upload to the Service.",
      "Billing data: payment method tokens (we never store full card numbers — billing is handled by our PCI-compliant payment processor).",
    ],
  },
  {
    title: "3. How we use your data",
    body: [
      "To provide, operate, and improve the Service — including generating AI-powered outreach content based on your inputs.",
      "To authenticate you, enforce role-based access control, and audit actions inside your tenant.",
      "To communicate with you about your account, security alerts, billing, and (with your consent) product updates.",
      "To monitor for abuse, fraud, and security threats, and to comply with our legal obligations.",
    ],
  },
  {
    title: "4. Sharing",
    body: [
      "We do not sell your data. We share data only with sub-processors who help us operate the Service (see §9 Sub-Processors), under written agreements that meet or exceed GDPR Article 28 requirements.",
      "We disclose data to authorities only when required by valid legal process, and we notify affected customers whenever legally permissible.",
      "Cross-tenant data isolation is enforced at the database layer — your content is never accessible to other tenants.",
    ],
  },
  {
    title: "5. Security",
    body: [
      "Encryption: all data is encrypted in transit (TLS 1.2+) and at rest (AES-256 with customer-managed KMS keys in production environments).",
      "Access control: least-privilege IAM, MFA-enforced admin access, and per-tenant data isolation by schema.",
      "Monitoring: continuous security logging, anomaly detection, and quarterly third-party penetration tests.",
      "Incidents: we maintain a 24/7 incident response process with a sub-72-hour breach notification commitment per GDPR Article 33.",
    ],
  },
];

const GDPR_RIGHTS = [
  {
    title: "Right of Access",
    body: "Request a copy of all personal data we hold about you.",
  },
  {
    title: "Right to Rectification",
    body: "Correct inaccurate or incomplete personal data via the Service or by contacting us.",
  },
  {
    title: "Right to Erasure",
    body: "Request deletion of your personal data, subject to legal retention obligations.",
  },
  {
    title: "Right to Data Portability",
    body: "Export your tenant data in standard formats at any time.",
  },
  {
    title: "Right to Object",
    body: "Object to processing for direct marketing — we will honor the request immediately.",
  },
  {
    title: "Right to Restrict Processing",
    body: "Request that we restrict processing pending verification of accuracy or lawful basis.",
  },
];

const LAWFUL_BASES = [
  {
    name: "Consent",
    body: "You have given clear, informed consent for a specific processing activity (e.g., marketing emails).",
  },
  {
    name: "Contract",
    body: "Processing is necessary to perform under the contract you have with us (the Terms of Service).",
  },
  {
    name: "Legal Obligation",
    body: "Processing is required to comply with a legal obligation (e.g., tax + billing records).",
  },
  {
    name: "Vital Interests",
    body: "Processing is necessary to protect your vital interests (rare; life/safety).",
  },
  {
    name: "Public Task",
    body: "Processing is necessary for a task carried out in the public interest or in the exercise of official authority.",
  },
  {
    name: "Legitimate Interests",
    body: "Processing is necessary for our legitimate interests, balanced against your rights (e.g., security monitoring, abuse prevention).",
  },
];

const SUB_PROCESSORS = [
  { name: "AWS", purpose: "Cloud infrastructure (RDS, S3, CloudTrail, CloudWatch) — primary cloud" },
  { name: "Azure", purpose: "Secondary cloud (Container Apps, Key Vault, Monitor)" },
  { name: "Stripe", purpose: "Payment processing (PCI-compliant)" },
  { name: "Keycloak", purpose: "Identity provider + SSO" },
  { name: "OpenAI", purpose: "LLM provider (outreach copy generation)" },
  { name: "Anthropic", purpose: "LLM provider (Claude models)" },
  { name: "Google", purpose: "LLM provider (Gemini models)" },
  { name: "SendGrid / Postmark", purpose: "Transactional + outreach email delivery" },
  { name: "Apollo / Hunter", purpose: "B2B contact data enrichment" },
];

const RETENTION_SUMMARY = [
  {
    category: "Active tenant content",
    days: "Lifetime of subscription",
    detail: "Retained while the subscription is active.",
  },
  {
    category: "Cancelled tenant data",
    days: "30-day grace, then 30-day purge",
    detail: "Soft-deleted after cancellation; permanently purged within 60 days unless legally required.",
  },
  {
    category: "Audit logs",
    days: "90 days",
    detail: "Tenant-scoped audit log retention per SOC2 policy.",
  },
  {
    category: "Security logs (CloudTrail / Activity Log)",
    days: "1 year",
    detail: "Platform-wide security logging.",
  },
  {
    category: "Backup snapshots",
    days: "35 days",
    detail: "Point-in-time recovery, then automatically purged.",
  },
];

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.35, ease: "easeOut" as const },
};

export function PrivacyPage() {
  return (
    <div>
      <section className="border-b bg-card">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          >
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5" />
              Privacy
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Privacy Policy
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
              Last updated: {new Date().getFullYear()}. We are committed to
              protecting your data and being transparent about how we use it.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm">
                <Link to="/p/gdpr-rights">
                  <ShieldCheck className="h-4 w-4" />
                  Exercise your GDPR rights
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link to="/p/dpa">
                  <Scale className="h-4 w-4" />
                  Data Processing Agreement
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="space-y-6">
          {SECTIONS.map((section, i) => (
            <motion.div
              key={section.title}
              {...fadeUp}
              transition={{ duration: 0.35, delay: i * 0.03 }}
            >
              <Card>
                <CardHeader>
                  <CardTitle className="text-xl">{section.title}</CardTitle>
                  <CardDescription>
                    {section.body.length} paragraph
                    {section.body.length === 1 ? "" : "s"}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
                  {section.body.map((p, idx) => (
                    <p key={idx}>{p}</p>
                  ))}
                </CardContent>
              </Card>
            </motion.div>
          ))}

          {/* GDPR Rights — expanded section */}
          <motion.div {...fadeUp}>
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <CardTitle className="text-xl">6. Your GDPR Rights</CardTitle>
                <CardDescription>
                  Under the GDPR, you have six core rights over your personal
                  data. Exercise any of them via our self-serve portal.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {GDPR_RIGHTS.map((r) => (
                    <div
                      key={r.title}
                      className="rounded-md border bg-card p-3"
                    >
                      <p className="text-sm font-semibold">{r.title}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {r.body}
                      </p>
                    </div>
                  ))}
                </div>
                <Button asChild size="sm" className="mt-2">
                  <Link to="/p/gdpr-rights">
                    <ShieldCheck className="h-4 w-4" />
                    Submit a Data Subject Request
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </motion.div>

          {/* Lawful bases */}
          <motion.div {...fadeUp}>
            <Card>
              <CardHeader>
                <CardTitle className="text-xl">7. Lawful Bases</CardTitle>
                <CardDescription>
                  GDPR Article 6 — the bases under which we process personal
                  data.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {LAWFUL_BASES.map((b) => (
                    <li key={b.name} className="flex gap-2">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      <span>
                        <strong className="text-foreground">{b.name}</strong> —{" "}
                        {b.body}
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </motion.div>

          {/* Data retention */}
          <motion.div {...fadeUp}>
            <Card>
              <CardHeader>
                <CardTitle className="text-xl">8. Data Retention</CardTitle>
                <CardDescription>
                  Summary of retention periods per data category.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="overflow-hidden rounded-md border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                          Category
                        </th>
                        <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                          Retention
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {RETENTION_SUMMARY.map((r) => (
                        <tr key={r.category}>
                          <td className="px-3 py-2">
                            <p className="font-medium">{r.category}</p>
                            <p className="text-xs text-muted-foreground">
                              {r.detail}
                            </p>
                          </td>
                          <td className="px-3 py-2 text-xs">{r.days}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-muted-foreground">
                  Active tenant data is retained for the lifetime of your
                  subscription. Backup snapshots are retained for 35 days
                  (point-in-time recovery) and then automatically purged.
                </p>
              </CardContent>
            </Card>
          </motion.div>

          {/* Sub-processors */}
          <motion.div {...fadeUp}>
            <Card>
              <CardHeader>
                <CardTitle className="text-xl">9. Sub-Processors</CardTitle>
                <CardDescription>
                  We share data with the following categories of sub-processors
                  under GDPR Article 28-compliant agreements.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {SUB_PROCESSORS.map((s) => (
                    <div
                      key={s.name}
                      className="flex items-start gap-2 rounded-md border p-2.5"
                    >
                      <span className="mt-0.5 inline-flex h-6 min-w-6 items-center justify-center rounded bg-primary/10 px-1.5 text-xs font-semibold text-primary">
                        {s.name[0]}
                      </span>
                      <div>
                        <p className="text-sm font-medium">{s.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {s.purpose}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* DPA + DPO contact */}
          <motion.div {...fadeUp}>
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <CardTitle className="text-xl">10. DPA + DPO Contact</CardTitle>
                <CardDescription>
                  Data Processing Agreement + Data Protection Officer.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div>
                  <p className="font-medium">Data Processing Agreement</p>
                  <p className="mt-1 text-muted-foreground">
                    Our DPA forms part of the master agreement and covers
                    parties, processing details, sub-processors, audit rights,
                    and breach notification.
                  </p>
                  <Button asChild variant="outline" size="sm" className="mt-2">
                    <Link to="/p/dpa">
                      <Scale className="h-4 w-4" />
                      Read the DPA
                    </Link>
                  </Button>
                </div>
                <div className="border-t pt-4">
                  <p className="font-medium">Data Protection Officer (DPO)</p>
                  <ul className="mt-1 space-y-1 text-muted-foreground">
                    <li>
                      Email:{" "}
                      <a
                        href="mailto:dpo@outrena.io"
                        className="font-medium text-foreground hover:underline"
                      >
                        dpo@outrena.io
                      </a>
                    </li>
                    <li>Response SLA: 30 days (per GDPR Article 12).</li>
                    <li>
                      You may also file a complaint with your local data
                      protection authority.
                    </li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Contact */}
          <motion.div {...fadeUp}>
            <Card>
              <CardHeader>
                <CardTitle className="text-xl">11. Contact</CardTitle>
                <CardDescription>General privacy questions.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <p>
                  For questions about this Privacy Policy, contact{" "}
                  <a
                    href="mailto:privacy@outrena.io"
                    className="font-medium text-foreground hover:underline"
                  >
                    privacy@outrena.io
                  </a>
                  .
                </p>
                <p>
                  For DSR / GDPR matters specifically, contact{" "}
                  <a
                    href="mailto:dpo@outrena.io"
                    className="font-medium text-foreground hover:underline"
                  >
                    dpo@outrena.io
                  </a>{" "}
                  or use our{" "}
                  <Link
                    to="/p/gdpr-rights"
                    className="font-medium text-foreground hover:underline"
                  >
                    self-serve DSR portal
                  </Link>
                  .
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
