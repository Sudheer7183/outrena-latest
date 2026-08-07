/**
 * GdprRightsPage.tsx — public data-subject rights info + DSR submission form.
 *
 * Mounted at `/p/gdpr-rights` (no auth, inside <PublicLayout>). Explains the
 * six GDPR rights, the DPO contact, and a DSR submission form (email, tenant
 * name, request type, details). On submit → POST /api/v1/gdpr/dsr → 201 with
 * { dsr_id, status } → show success card with reference + link to status page.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  FileText,
  Loader2,
  Mail,
  Scale,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { gdprApi } from "@/services/apiClient";
import type { DsrRequestType } from "@/types/common";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect as Select } from "@/components/ui/select";

const RIGHTS = [
  {
    title: "Right of Access",
    body: "You can request a copy of all personal data we hold about you, in a portable machine-readable format.",
  },
  {
    title: "Right to Rectification",
    body: "You can ask us to correct any inaccurate or incomplete personal data we hold about you.",
  },
  {
    title: "Right to Erasure",
    body: "Also known as the 'right to be forgotten'. You can request deletion of your personal data, subject to legal retention obligations.",
  },
  {
    title: "Right to Data Portability",
    body: "You can receive your personal data in a structured, commonly used, machine-readable format and transmit it to another controller.",
  },
  {
    title: "Right to Object",
    body: "You can object to processing of your personal data for direct marketing or other legitimate-interest-based processing.",
  },
  {
    title: "Right to Restrict Processing",
    body: "You can request that we restrict processing of your personal data pending verification of accuracy or lawful basis.",
  },
];

const LAWFUL_BASES = [
  { name: "Consent", body: "You have given clear, informed consent for a specific processing activity." },
  { name: "Contract", body: "Processing is necessary to perform under a contract you have with us." },
  { name: "Legal Obligation", body: "Processing is required to comply with a legal obligation (e.g., tax records)." },
  { name: "Vital Interests", body: "Processing is necessary to protect your vital interests (rare; life/safety)." },
  { name: "Public Task", body: "Processing is necessary for a task carried out in the public interest." },
  { name: "Legitimate Interests", body: "Processing is necessary for our legitimate interests, balanced against your rights." },
];

const REQUEST_TYPES: { value: DsrRequestType; label: string }[] = [
  { value: "access", label: "Access — I want a copy of my data" },
  { value: "rectification", label: "Rectification — Fix inaccurate data" },
  { value: "erasure", label: "Erasure — Delete my data" },
  { value: "portability", label: "Portability — Export my data" },
  { value: "objection", label: "Object — Stop processing for marketing" },
  { value: "restriction", label: "Restrict — Limit processing" },
];

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.35, ease: "easeOut" as const },
};

export function GdprRightsPage() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [requestType, setRequestType] = useState<DsrRequestType>("access");
  const [details, setDetails] = useState("");
  const [submittedId, setSubmittedId] = useState<string | null>(null);

  const submitMutation = useMutation({
    mutationFn: () =>
      gdprApi.submitDsr({
        email: email.trim(),
        tenant_slug: tenantSlug.trim() || undefined,
        request_type: requestType,
        details: details.trim() || undefined,
      }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["dsrs"] });
      setSubmittedId(res.dsr_id);
      toast.success("DSR submitted");
    },
    onError: () => toast.error("Failed to submit request"),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || !email.includes("@")) {
      toast.error("Enter a valid email address");
      return;
    }
    submitMutation.mutate();
  }

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
              GDPR · Data Subject Rights
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Your Data, Your Rights
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
              Under the GDPR, you have six core rights over your personal data.
              You can exercise any of them by submitting a Data Subject Request
              below. We respond within 30 days.
            </p>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {RIGHTS.map((r, i) => (
            <motion.div key={r.title} {...fadeUp} transition={{ duration: 0.35, delay: i * 0.03 }}>
              <Card className="h-full">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Scale className="h-4 w-4 text-primary" />
                    {r.title}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{r.body}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* DPO contact + lawful bases */}
        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Data Protection Officer
              </CardTitle>
              <CardDescription>
                Our DPO is your point of contact for any privacy concern.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>
                <strong>Email:</strong>{" "}
                <a
                  href="mailto:dpo@outrena.io"
                  className="text-primary hover:underline"
                >
                  dpo@outrena.io
                </a>
              </p>
              <p>
                <strong>Response SLA:</strong> 30 days (per GDPR Art 12).
              </p>
              <p className="text-xs text-muted-foreground">
                You may also file a complaint with your local data protection
                authority. We commit to working with you to resolve any concern
                before you need to do so.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Lawful Bases We Rely On
              </CardTitle>
              <CardDescription>
                GDPR Article 6 — the bases under which we process personal data.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                {LAWFUL_BASES.map((b) => (
                  <li key={b.name} className="flex gap-2">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                    <span>
                      <strong>{b.name}</strong> —{" "}
                      <span className="text-muted-foreground">{b.body}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Submission form / success card */}
        <div className="mt-12">
          {submittedId ? (
            <Card className="border-l-4 border-l-emerald-500">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  Your request has been submitted
                </CardTitle>
                <CardDescription>
                  We'll respond within 30 days. Save your reference number.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-md border bg-muted/50 p-3">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground">
                    Your reference number
                  </p>
                  <p className="font-mono text-lg font-bold">{submittedId}</p>
                </div>
                <p className="text-sm text-muted-foreground">
                  We've sent a confirmation email to{" "}
                  <strong>{email}</strong>. You can check the status of your
                  request at any time using your reference number.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button asChild>
                    <Link to={`/p/gdpr-status?dsr_id=${submittedId}`}>
                      Check status
                    </Link>
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setSubmittedId(null);
                      setEmail("");
                      setTenantSlug("");
                      setDetails("");
                    }}
                  >
                    Submit another request
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Submit a Data Subject Request</CardTitle>
                <CardDescription>
                  Use this form to exercise any of your GDPR rights. Fields
                  marked * are required.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="dsr-email">Your email *</Label>
                      <Input
                        id="dsr-email"
                        type="email"
                        placeholder="you@example.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="dsr-tenant">
                        Tenant / workspace slug (optional)
                      </Label>
                      <Input
                        id="dsr-tenant"
                        placeholder="acme"
                        value={tenantSlug}
                        onChange={(e) => setTenantSlug(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="dsr-type">Request type *</Label>
                    <Select
                      id="dsr-type"
                      value={requestType}
                      onChange={(e) =>
                        setRequestType(e.target.value as DsrRequestType)
                      }
                    >
                      {REQUEST_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="dsr-details">Details (optional)</Label>
                    <Textarea
                      id="dsr-details"
                      placeholder="Provide any additional context — e.g. what data you want access to, why you're requesting erasure, etc."
                      value={details}
                      onChange={(e) => setDetails(e.target.value)}
                      rows={4}
                    />
                  </div>

                  <p className="text-xs text-muted-foreground">
                    By submitting, you confirm that the email above belongs to
                    you. We may contact you to verify your identity before
                    processing the request.
                  </p>

                  <Button
                    type="submit"
                    disabled={submitMutation.isPending}
                    className="w-full sm:w-auto"
                  >
                    {submitMutation.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Submitting…
                      </>
                    ) : (
                      "Submit request"
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}
        </div>
      </section>
    </div>
  );
}
