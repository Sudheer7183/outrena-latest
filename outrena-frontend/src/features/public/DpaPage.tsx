/**
 * DpaPage.tsx — public Data Processing Agreement (DPA).
 *
 * Mounted at `/p/dpa` (no auth, inside <PublicLayout>). Static but
 * well-structured DPA covering parties, definitions, processing details,
 * data subject rights, confidentiality, security measures, sub-processors,
 * audit rights, breach notification, term + termination, governing law.
 */
import { motion } from "framer-motion";
import { FileText, Scale } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface Section {
  title: string;
  body: string[];
}

const SECTIONS: Section[] = [
  {
    title: "1. Parties",
    body: [
      "This Data Processing Agreement (\"DPA\") is entered into between OUTRENA (\"Processor\") and the customer entity that has executed the OUTRENA Terms of Service (\"Controller\").",
      "By signing the master agreement or activating the OUTRENA platform, the Controller agrees to be bound by this DPA in respect of their use of the OUTRENA service.",
    ],
  },
  {
    title: "2. Definitions",
    body: [
      "\"Personal Data\" has the meaning given in the EU General Data Protection Regulation (GDPR).",
      "\"Processing\" means any operation performed on Personal Data, whether or not by automated means.",
      "\"Sub-processor\" means any third party engaged by OUTRENA to process Personal Data on behalf of the Controller.",
      "\"Data Subject\" means an identified or identifiable natural person to whom Personal Data relates.",
    ],
  },
  {
    title: "3. Roles + Processing Details",
    body: [
      "OUTRENA acts as a Processor on behalf of the Controller. The Controller is the controller of the Personal Data submitted to the Service.",
      "Subject matter of processing: provision of the OUTRENA AI-powered outreach operating system.",
      "Duration of processing: for the term of the master agreement until deletion of the Controller's data per the retention schedule.",
      "Nature + purpose of processing: storage, retrieval, enrichment, and analysis of prospect + campaign data to facilitate outreach workflows.",
      "Types of Personal Data: name, work email, company, job title, LinkedIn URL, and any other data the Controller chooses to upload.",
      "Categories of Data Subjects: prospects, leads, customers, and other contacts uploaded by the Controller.",
    ],
  },
  {
    title: "4. Data Subject Rights",
    body: [
      "OUTRENA will assist the Controller in responding to Data Subject requests (access, rectification, erasure, portability, objection, restriction) using reasonable technical and organizational measures.",
      "Where Personal Data is processed at the Controller's direction, OUTRENA will not respond to a Data Subject request without the Controller's prior authorization, except where required by law.",
    ],
  },
  {
    title: "5. Confidentiality",
    body: [
      "OUTRENA personnel authorized to process Personal Data are subject to confidentiality obligations under their employment or contractor agreements.",
      "Access to Personal Data is restricted to those personnel whose role requires it, on a least-privilege basis.",
    ],
  },
  {
    title: "6. Security Measures",
    body: [
      "Encryption in transit: TLS 1.2+ for all external traffic and TLS for internal service-to-service communication.",
      "Encryption at rest: AES-256 with customer-managed KMS keys on RDS, S3, Redis, and CloudTrail / CloudWatch Logs.",
      "Access control: least-privilege IAM, MFA-enforced admin access, role-based access control (RBAC) within the application, and per-tenant data isolation by PostgreSQL schema.",
      "Monitoring: continuous security logging, anomaly detection, and quarterly third-party penetration tests.",
      "Incident response: 24/7 on-call with a sub-72-hour breach notification commitment per GDPR Article 33.",
    ],
  },
  {
    title: "7. Sub-Processors",
    body: [
      "OUTRENA engages the following categories of sub-processors: cloud infrastructure (AWS / Azure), payment processing (Stripe), identity provider (Keycloak), LLM providers (OpenAI, Anthropic, Google, etc.), email delivery (SendGrid / Postmark), and analytics.",
      "The current list of sub-processors is maintained in the SOC2 runbook and is available on request from dpo@outrena.io.",
      "OUTRENA will notify the Controller in advance of any addition or replacement of a sub-processor. The Controller may object to a new sub-processor on reasonable grounds.",
    ],
  },
  {
    title: "8. Audit Rights",
    body: [
      "Upon reasonable notice, OUTRENA will make available to the Controller information necessary to demonstrate compliance with this DPA.",
      "Where required by Article 28 of the GDPR, OUTRENA will permit the Controller or an independent auditor mandated by the Controller to conduct an audit, subject to confidentiality obligations.",
    ],
  },
  {
    title: "9. Breach Notification",
    body: [
      "OUTRENA will notify the Controller without undue delay (and in any event within 72 hours) of becoming aware of a Personal Data breach affecting the Controller's data.",
      "The notification will describe the nature of the breach, the categories and approximate number of Data Subjects + records concerned, the likely consequences, and the measures taken or proposed to address the breach.",
    ],
  },
  {
    title: "10. Term + Termination",
    body: [
      "This DPA remains in effect for the duration of the master agreement.",
      "Upon termination, OUTRENA will, at the Controller's choice, delete or return all Personal Data, and delete existing copies, unless EU or member-state law requires storage.",
    ],
  },
  {
    title: "11. Governing Law",
    body: [
      "This DPA is governed by the same law as the master agreement.",
      "Any dispute arising out of or in connection with this DPA shall be subject to the exclusive jurisdiction of the courts specified in the master agreement.",
    ],
  },
];

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.35, ease: "easeOut" as const },
};

export function DpaPage() {
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
              <FileText className="h-3.5 w-3.5" />
              Legal · Data Processing Agreement
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Data Processing Agreement
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
              Last updated: {new Date().getFullYear()}. This DPA forms part of
              the OUTRENA Terms of Service and applies to all customers who
              process Personal Data through the OUTRENA platform.
            </p>
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
                  <CardTitle className="flex items-center gap-2 text-xl">
                    <Scale className="h-4 w-4 text-primary" />
                    {section.title}
                  </CardTitle>
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

          <Card className="border-l-4 border-l-primary bg-primary/5">
            <CardContent className="p-4 text-sm">
              <p className="font-semibold">Questions about this DPA?</p>
              <p className="mt-1 text-muted-foreground">
                Contact our DPO at{" "}
                <a
                  href="mailto:dpo@outrena.io"
                  className="font-medium text-foreground hover:underline"
                >
                  dpo@outrena.io
                </a>
                .
              </p>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
