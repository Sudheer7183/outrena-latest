/**
 * ContactPage.tsx — public contact form + info.
 *
 * Left: form (name/email/company/message → POST /public/contact).
 * Right: contact info from GET /public/contact-info + map placeholder.
 *
 * Form uses local state + useMutation; on success shows toast + resets.
 */
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Building2, Clock, Mail, MapPin, Phone, Send } from "lucide-react";
import { toast } from "sonner";
import { publicApi } from "@/services/apiClient";
import type { ContactInfo } from "@/types/common";
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
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";

const MOCK_CONTACT: ContactInfo = {
  email: "hello@outrena.io",
  phone: "+1 (415) 555-0192",
  address: "548 Market St, San Francisco, CA 94104",
  support_hours: "Mon–Fri, 9am–6pm PT",
};

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.4, ease: "easeOut" as const },
};

export function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [message, setMessage] = useState("");

  const { data: contact, isLoading } = useQuery({
    queryKey: ["public", "contact-info"],
    queryFn: () => publicApi.contactInfo(),
  });

  const info = contact ?? MOCK_CONTACT;

  const submitMutation = useMutation({
    mutationFn: () =>
      publicApi.contact({
        name: name.trim(),
        email: email.trim(),
        company: company.trim() || undefined,
        message: message.trim(),
      }),
    onSuccess: () => {
      toast.success("Message sent — we'll be in touch within 24 hours.");
      setName("");
      setEmail("");
      setCompany("");
      setMessage("");
    },
    onError: () =>
      toast.error("Failed to send message. Please try again or email us directly."),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !message.trim()) {
      toast.error("Name, email, and message are required.");
      return;
    }
    if (!email.includes("@")) {
      toast.error("Enter a valid email address.");
      return;
    }
    submitMutation.mutate();
  }

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
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Get in touch
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Questions about pricing, deployment, or a custom plan? We
              typically reply within one business day.
            </p>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          {/* Form */}
          <motion.div {...fadeUp}>
            <Card>
              <CardHeader>
                <CardTitle>Send us a message</CardTitle>
                <CardDescription>
                  Fill out the form below and our team will get back to you.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="name">Full name *</Label>
                      <Input
                        id="name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Jane Doe"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email *</Label>
                      <Input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="jane@company.com"
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="company">Company (optional)</Label>
                    <Input
                      id="company"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      placeholder="Acme Inc."
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="message">Message *</Label>
                    <Textarea
                      id="message"
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      placeholder="Tell us how we can help…"
                      rows={6}
                      required
                    />
                  </div>
                  <Button type="submit" disabled={submitMutation.isPending} className="w-full">
                    {submitMutation.isPending ? (
                      <>
                        <Send className="h-4 w-4 animate-pulse" />
                        Sending…
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4" />
                        Send message
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </motion.div>

          {/* Contact info + map placeholder */}
          <motion.div {...fadeUp} className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Contact information</CardTitle>
                <CardDescription>
                  Prefer to reach out directly? Here's how.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full" />
                    ))}
                  </div>
                ) : (
                  <>
                    <InfoRow icon={<Mail className="h-5 w-5" />} label="Email" value={info.email} />
                    <InfoRow icon={<Phone className="h-5 w-5" />} label="Phone" value={info.phone} />
                    <InfoRow
                      icon={<Building2 className="h-5 w-5" />}
                      label="Address"
                      value={info.address}
                    />
                    <InfoRow
                      icon={<Clock className="h-5 w-5" />}
                      label="Support hours"
                      value={info.support_hours}
                    />
                  </>
                )}
              </CardContent>
            </Card>

            {/* Map placeholder */}
            <Card>
              <CardContent className="p-0">
                <div className="relative flex h-64 items-center justify-center overflow-hidden rounded-lg bg-muted">
                  <div
                    aria-hidden
                    className="absolute inset-0 opacity-30"
                    style={{
                      backgroundImage:
                        "linear-gradient(to right, hsl(var(--muted-foreground)/0.2) 1px, transparent 1px), linear-gradient(to bottom, hsl(var(--muted-foreground)/0.2) 1px, transparent 1px)",
                      backgroundSize: "32px 32px",
                    }}
                  />
                  <div className="relative flex flex-col items-center gap-2 text-center text-muted-foreground">
                    <MapPin className="h-8 w-8" />
                    <p className="text-sm font-medium">San Francisco, CA</p>
                    <p className="text-xs">Map placeholder</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </section>
    </div>
  );
}

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className="text-sm break-words">{value}</p>
      </div>
    </div>
  );
}
