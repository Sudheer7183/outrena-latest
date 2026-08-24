/**
 * ProfileSettingsPage — lets each logged-in rep save the sender profile
 * fields that are appended to every generated email sequence.
 *
 * Fields (all optional, merged on PUT):
 *   firstName / lastName  — read-only from Keycloak; shown for context
 *   senderTitle           — e.g. "Account Executive"
 *   senderCompany         — e.g. "Acme Corp"
 *   senderOffer           — one-line value prop used in LLM prompt
 *   emailSignature        — full plain-text signature block
 *   physicalAddress       — CAN-SPAM §5(a)(5) postal address
 *
 * Backend endpoints:
 *   GET  /api/v1/users/me/profile   → load current values
 *   PUT  /api/v1/users/me/profile   → save changes (merge, not replace)
 */

import { useEffect, useState } from "react";
import { Loader2, Save, CheckCircle2, User, Mail, Building2, FileText, MapPin, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { http } from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import type { UserProfile } from "@/context/AuthContext";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ProfileFormState {
  senderTitle: string;
  senderCompany: string;
  senderOffer: string;
  emailSignature: string;
  physicalAddress: string;
}

const EMPTY_FORM: ProfileFormState = {
  senderTitle: "",
  senderCompany: "",
  senderOffer: "",
  emailSignature: "",
  physicalAddress: "",
};

// ─── Component ───────────────────────────────────────────────────────────────

export function ProfileSettingsPage() {
  const { user, profile } = useAuth();

  const [form, setForm] = useState<ProfileFormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // ── Load current profile on mount ──────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    http
      .get<UserProfile>("/api/v1/users/me/profile")
      .then((data) => {
        if (cancelled) return;
        setForm({
          senderTitle:     data.senderTitle     ?? "",
          senderCompany:   data.senderCompany   ?? "",
          senderOffer:     data.senderOffer     ?? "",
          emailSignature:  data.emailSignature  ?? "",
          physicalAddress: data.physicalAddress ?? "",
        });
      })
      .catch(() => {
        if (!cancelled) toast.error("Could not load profile — check your connection");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  // ── Handlers ─────────────────────────────────────────────────────────────

  function set(field: keyof ProfileFormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await http.put("/api/v1/users/me/profile", {
        senderTitle:     form.senderTitle     || null,
        senderCompany:   form.senderCompany   || null,
        senderOffer:     form.senderOffer     || null,
        emailSignature:  form.emailSignature  || null,
        physicalAddress: form.physicalAddress || null,
      });
      setSaved(true);
      toast.success("Profile saved — your next generated sequence will use these details");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Build a live preview of what the signature block will look like
  const signaturePreview = [
    form.emailSignature,
    form.physicalAddress
      ? `\n---\nTo unsubscribe: {{unsubscribe_url}}\n${form.physicalAddress}`
      : "\n---\nTo unsubscribe: {{unsubscribe_url}}",
  ]
    .filter(Boolean)
    .join("\n\n");

  return (
    <div className="max-w-2xl mx-auto space-y-6 py-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">My Sender Profile</h2>
        <p className="text-sm text-muted-foreground mt-1">
          These details are automatically included in every email sequence you generate —
          no more <code className="text-xs bg-muted px-1 py-0.5 rounded">[Your Name]</code> placeholders.
        </p>
      </div>

      {/* Identity (read-only from Keycloak) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <User className="h-4 w-4" /> Your Identity
          </CardTitle>
          <CardDescription className="text-xs">
            Name and email come from your login account. Contact your admin to change them.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label className="text-xs">First name</Label>
            <Input
              value={profile?.firstName ?? user?.name?.split(" ")[0] ?? ""}
              disabled
              className="bg-muted text-muted-foreground"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Last name</Label>
            <Input
              value={profile?.lastName ?? user?.name?.split(" ").slice(1).join(" ") ?? ""}
              disabled
              className="bg-muted text-muted-foreground"
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label className="text-xs flex items-center gap-1.5">
              <Mail className="h-3 w-3" /> Email
            </Label>
            <Input
              value={user?.email ?? ""}
              disabled
              className="bg-muted text-muted-foreground"
            />
          </div>
        </CardContent>
      </Card>

      {/* Sender context (used in LLM prompt) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Building2 className="h-4 w-4" /> Sender Context
          </CardTitle>
          <CardDescription className="text-xs">
            Used in the AI prompt so generated emails reference your real role and offer —
            not placeholder text.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="senderTitle" className="text-xs">Your title</Label>
            <Input
              id="senderTitle"
              placeholder="e.g. Account Executive"
              value={form.senderTitle}
              onChange={(e) => set("senderTitle", e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="senderCompany" className="text-xs">Your company</Label>
            <Input
              id="senderCompany"
              placeholder="e.g. Acme Corp"
              value={form.senderCompany}
              onChange={(e) => set("senderCompany", e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="senderOffer" className="text-xs flex items-center gap-1.5">
              <Zap className="h-3 w-3" /> One-line value proposition
            </Label>
            <Input
              id="senderOffer"
              placeholder="e.g. We help SaaS teams cut onboarding time by 40%"
              value={form.senderOffer}
              onChange={(e) => set("senderOffer", e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              This is woven into the AI prompt as your offer. Keep it punchy — under 15 words.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Signature */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <FileText className="h-4 w-4" /> Email Signature
          </CardTitle>
          <CardDescription className="text-xs">
            Appended verbatim after every generated email body. Plain text only — no HTML.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="emailSignature" className="text-xs">Signature block</Label>
            <Textarea
              id="emailSignature"
              rows={5}
              placeholder={`Best,\nJane Doe\nAccount Executive | Acme Corp\n+1 555 000 0000\njane@acmecorp.com`}
              value={form.emailSignature}
              onChange={(e) => set("emailSignature", e.target.value)}
              className="font-mono text-sm"
            />
          </div>
        </CardContent>
      </Card>

      {/* Physical address (CAN-SPAM) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <MapPin className="h-4 w-4" /> Physical Address
          </CardTitle>
          <CardDescription className="text-xs">
            Required by CAN-SPAM §5(a)(5). Appended to the unsubscribe footer of every email.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-1.5">
          <Label htmlFor="physicalAddress" className="text-xs">Registered postal address</Label>
          <Input
            id="physicalAddress"
            placeholder="e.g. 123 Main St, San Francisco, CA 94105, USA"
            value={form.physicalAddress}
            onChange={(e) => set("physicalAddress", e.target.value)}
          />
        </CardContent>
      </Card>

      {/* Preview */}
      {(form.emailSignature || form.physicalAddress) && (
        <Card className="border-dashed border-muted-foreground/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground">Preview — email footer</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs font-mono whitespace-pre-wrap text-muted-foreground bg-muted rounded p-3">
              {signaturePreview}
            </pre>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Save button */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Changes take effect on the next generated sequence — existing sequences are not retroactively updated.
        </p>
        <Button onClick={handleSave} disabled={saving} className="gap-2">
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : saved ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {saving ? "Saving…" : saved ? "Saved" : "Save profile"}
        </Button>
      </div>
    </div>
  );
}
