/**
 * EmailStudioPage.tsx — OUTRENA Phase 4 (Task 3-C)
 *
 * Email generation + QA (anti-pattern scan + compliance check). Three-column
 * layout: generation form | preview | QA results. Multiple variants shown as
 * tabs. Mock-data fallback so the page always renders.
 */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  FileText,
  FlaskConical,
  Mail,
  Palette,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Wand2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { http } from "@/services/apiClient";
import { cn, formatPercent, truncate } from "@/lib/utils";
import type { TouchAngle } from "@/types/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { InfoLabel } from "@/components/ui/info-label";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { NativeSelect as Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

/* ── Types & mocks ──────────────────────────────────────────────────────── */

interface EmailVariant {
  id: string;
  subject: string;
  body: string;
  qaScore: number;
  personalisationConfidence: number;
  flagForManualReview: boolean;
  framework: string;
}
interface AntiPatternFinding {
  pattern: string;
  severity: "high" | "medium" | "low";
  snippet: string;
  suggestion: string;
}
interface AntiPatternResult {
  overallScore: number;
  findings: AntiPatternFinding[];
}
interface ComplianceCheck {
  id: string;
  label: string;
  regulation: "CAN-SPAM" | "GDPR";
  passed: boolean;
  detail: string;
}
interface ComplianceResult {
  checks: ComplianceCheck[];
  overallPassed: boolean;
}
/* ── AI QA Score types ──────────────────────────────────────────────────── */

interface QaDimension {
  name: string;
  score: number;
  max: number;
  feedback: string;
}

interface QaScoreResult {
  totalScore: number;
  maxScore: number;
  dimensions: QaDimension[];
  flags: string[];
  suggestedRewrite: string | null;
}

/* ── Subject Line types ────────────────────────────────────────────────── */

interface SubjectLineVariant {
  subject: string;
  predictedOpenRate: number;
  rationale: string;
}

interface SubjectLinesResult {
  variants: SubjectLineVariant[];
}

interface ProspectLite {
  id: string;
  name: string;
  company: string | null;
}
interface CampaignLite {
  id: string;
  name: string;
}

const ANGLES: TouchAngle[] = [
  "FirstTouch",
  "NewEvidence",
  "DifferentPain",
  "IndustryInsight",
  "DirectQuestion",
  "Breakup",
];

const TONES = ["consultative", "direct", "curious", "challenger", "warm"] as const;

const MOCK_PROSPECTS: ProspectLite[] = [
  { id: "p1", name: "Jordan Avery", company: "Northbeam" },
  { id: "p2", name: "Priya Shah", company: "Helix Pay" },
  { id: "p3", name: "Marcus Chen", company: "Loop Capital" },
];

const MOCK_CAMPAIGNS: CampaignLite[] = [
  { id: "c1", name: "Q1 Outbound — Fintech Ops" },
  { id: "c2", name: "Cybersec SOC Automation" },
];

const MOCK_VARIANTS: EmailVariant[] = [
  {
    id: "v1",
    subject: "Northbeam's close-cycle SLA — 12 hours late, again?",
    body: `Hi Jordan,

I noticed Northbeam recently expanded the finance team — congratulations on the Series B extension.

Most ops leaders I speak with at Series B fintechs tell me the close cycle keeps slipping past 10 business days. The cost isn't just audit risk — it's the 30+ hours finance spends reconciling multi-entity ledgers every month.

OUTRENA automates reconciliation orchestration so finance teams close 60% faster within 90 days. Worth a 15-minute call next Tuesday?

— Alex`,
    qaScore: 0.88,
    personalisationConfidence: 0.82,
    flagForManualReview: false,
    framework: "trigger",
  },
  {
    id: "v2",
    subject: "12 hours late, again? (Northbeam close cycle)",
    body: `Hi Jordan,

Quick one: is Northbeam's close cycle still running 12+ hours past SLA?

The teams we work with at Series B fintechs cut reconciliation time by 60% in 90 days with OUTRENA. Happy to walk through how on a 15-min call.

— Alex`,
    qaScore: 0.74,
    personalisationConfidence: 0.68,
    flagForManualReview: true,
    framework: "challenger",
  },
];

const MOCK_ANTI_PATTERN: AntiPatternResult = {
  overallScore: 0.82,
  findings: [
    {
      pattern: "Generic opener",
      severity: "medium",
      snippet: "I hope this email finds you well",
      suggestion: "Open with a specific, observed trigger instead.",
    },
    {
      pattern: "Vague value claim",
      severity: "high",
      snippet: "saves time and money",
      suggestion: "Quantify: 'cuts close cycle by 60% within 90 days'.",
    },
    {
      pattern: "Weak CTA",
      severity: "low",
      snippet: "let me know",
      suggestion: "Use a specific time-bound ask: '15-min call next Tuesday'.",
    },
  ],
};

const MOCK_COMPLIANCE: ComplianceResult = {
  overallPassed: false,
  checks: [
    { id: "address", label: "Physical postal address", regulation: "CAN-SPAM", passed: true, detail: "Present in footer: 100 Market St, San Francisco, CA 94105" },
    { id: "unsubscribe", label: "Unsubscribe link", regulation: "CAN-SPAM", passed: true, detail: "Footer unsubscribe URL detected" },
    { id: "identity", label: "Sender identity", regulation: "CAN-SPAM", passed: true, detail: "From name + company present" },
    { id: "subject", label: "Subject truthfulness", regulation: "CAN-SPAM", passed: true, detail: "Subject aligns with body content" },
    { id: "consent", label: "Lawful basis / consent", regulation: "GDPR", passed: false, detail: "No explicit lawful basis recorded for this prospect" },
  ],
};

/* ── Page ───────────────────────────────────────────────────────────────── */

export function EmailStudioPage() {
  const qc = useQueryClient();
  const [prospectId, setProspectId] = useState(MOCK_PROSPECTS[0].id);
  const [campaignId, setCampaignId] = useState("");
  const [touchNumber, setTouchNumber] = useState(1);
  const [angle, setAngle] = useState<TouchAngle>("FirstTouch");
  const [tone, setTone] = useState<(typeof TONES)[number]>("consultative");
  // Brand Voice — Help Guide §Email Studio: "Brand Voice section"
  const [brandVoiceCampaign, setBrandVoiceCampaign] = useState("");
  const hasBrandVoice = brandVoiceCampaign !== "";
  // Subject Line A/B Test — Help Guide §Email Studio: "A/B Test Switch toggle"
  const [abTestEnabled, setAbTestEnabled] = useState(false);
  const [subjectB, setSubjectB] = useState("");
  const [maxLength, setMaxLength] = useState(180);
  const [activeVariant, setActiveVariant] = useState("v1");
  // FR-029: plain-text vs HTML preview toggle
  const [previewMode, setPreviewMode] = useState<"text" | "html">("text");

  const [variants, setVariants] = useState<EmailVariant[]>([]);
  const [antiPattern, setAntiPattern] = useState<AntiPatternResult | null>(null);
  const [compliance, setCompliance] = useState<ComplianceResult | null>(null);

  // AI QA Score state
  const [qaScoreOpen, setQaScoreOpen] = useState(false);
  const [qaScoreResult, setQaScoreResult] = useState<QaScoreResult | null>(null);

  // Subject Lines state
  const [subjectsOpen, setSubjectsOpen] = useState(false);
  const [subjectLines, setSubjectLines] = useState<SubjectLineVariant[]>([]);

  const generateMut = useMutation({
    mutationFn: (body: {
      prospectId: string;
      campaignId?: string;
      touchNumber: number;
      angle: TouchAngle;
      tone: string;
      maxLength: number;
    }) => http.post<EmailVariant[]>("/api/v1/email-studio/generate-email", body),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["email-variants"] });
      setVariants(data);
      setActiveVariant(data[0]?.id ?? "");
      toast.success(`Generated ${data.length} variant${data.length === 1 ? "" : "s"}`);
    },
    onError: () => {
      setVariants(MOCK_VARIANTS);
      setActiveVariant(MOCK_VARIANTS[0].id);
      toast.warning("Email Studio API unavailable — showing mock variants");
    },
  });

  const antiPatternMut = useMutation({
    mutationFn: (body: { body: string; subject?: string }) =>
      http.post<AntiPatternResult>("/api/v1/email-studio/anti-pattern", body),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["email-variants"] });
      setAntiPattern(data);
      toast.success("Anti-pattern scan complete");
    },
    onError: () => {
      setAntiPattern(MOCK_ANTI_PATTERN);
      toast.warning("Anti-pattern API unavailable — showing mock results");
    },
  });

  const complianceMut = useMutation({
    mutationFn: (body: {
      body: string;
      subject?: string;
      senderCompany?: string;
      physicalAddress?: string;
      unsubscribeUrl?: string;
    }) => http.post<ComplianceResult>("/api/v1/email-studio/compliance-check", body),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["email-variants"] });
      setCompliance(data);
      toast.success("Compliance check complete");
    },
    onError: () => {
      setCompliance(MOCK_COMPLIANCE);
      toast.warning("Compliance API unavailable — showing mock results");
    },
  });

  // AI QA Score mutation
  const qaScoreMut = useMutation({
    mutationFn: (body: { body: string; subject?: string }) =>
      http.post<QaScoreResult>("/api/v1/email-studio/qa-score", body),
    onSuccess: (data) => {
      setQaScoreResult(data);
      setQaScoreOpen(true);
      toast.success("AI QA score computed");
    },
    onError: () => {
      toast.error("AI QA Score API unavailable");
    },
  });

  // Subject Lines mutation
  const subjectLinesMut = useMutation({
    mutationFn: (body: { body: string; subject?: string; prospectId?: string }) =>
      http.post<SubjectLinesResult>("/api/v1/email-studio/subject-lines-generate", body),
    onSuccess: (data) => {
      setSubjectLines(data.variants ?? []);
      setSubjectsOpen(true);
      toast.success(`${(data.variants ?? []).length} subject lines generated`);
    },
    onError: () => {
      toast.error("Subject Lines API unavailable");
    },
  });

  // Seed mock variants on first render so the page is never empty.
  const displayedVariants = variants.length > 0 ? variants : MOCK_VARIANTS;
  const currentVariant =
    displayedVariants.find((v) => v.id === activeVariant) ?? displayedVariants[0];

  function handleGenerate() {
    generateMut.mutate({
      prospectId,
      campaignId: campaignId || undefined,
      touchNumber,
      angle,
      tone,
      maxLength,
    });
  }

  function handleRunQA() {
    if (!currentVariant) {
      toast.error("Generate an email first");
      return;
    }
    antiPatternMut.mutate({ body: currentVariant.body, subject: currentVariant.subject });
    complianceMut.mutate({
      body: currentVariant.body,
      subject: currentVariant.subject,
      senderCompany: "OUTRENA",
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">Email Studio</h1>
          <p className="text-sm text-muted-foreground">
            Generate personalised, QA-checked emails with anti-pattern + compliance guardrails.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => {
              if (!currentVariant) { toast.error("Generate an email first"); return; }
              qaScoreMut.mutate({ body: currentVariant.body, subject: currentVariant.subject });
            }}
            disabled={!currentVariant || qaScoreMut.isPending}
          >
            <ShieldCheck className="h-4 w-4" />
            {qaScoreMut.isPending ? "Scoring…" : "QA"}
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              if (!currentVariant) { toast.error("Generate an email first"); return; }
              subjectLinesMut.mutate({ body: currentVariant.body, subject: currentVariant.subject, prospectId });
            }}
            disabled={!currentVariant || subjectLinesMut.isPending}
          >
            <Mail className="h-4 w-4" />
            {subjectLinesMut.isPending ? "Generating…" : "Subjects"}
          </Button>
          <Button onClick={handleRunQA} disabled={!currentVariant || antiPatternMut.isPending || complianceMut.isPending}>
            <ShieldCheck className="h-4 w-4" />
            {antiPatternMut.isPending || complianceMut.isPending ? "Running QA…" : "Run QA"}
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        {/* Left: Generation form */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-base">Generation</CardTitle>
            <CardDescription>Tune inputs and generate fresh variants.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="prospect">Prospect</Label>
              <Select id="prospect" value={prospectId} onChange={(e) => setProspectId(e.target.value)}>
                {MOCK_PROSPECTS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {p.company}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="campaign">Campaign (optional)</Label>
              <Select id="campaign" value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
                <option value="">— None —</option>
                {MOCK_CAMPAIGNS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="touch">Touch #</Label>
                <Select
                  id="touch"
                  value={String(touchNumber)}
                  onChange={(e) => setTouchNumber(Number(e.target.value))}
                >
                  {[1, 2, 3, 4, 5, 6, 7].map((n) => (
                    <option key={n} value={n}>
                      Touch {n}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <InfoLabel
                  htmlFor="tone"
                  label="Tone"
                  info="The emotional register of the email: consultative (advisor), direct (no-fluff), curious (question-led), challenger (provocative), warm (friendly)."
                />
                <Select id="tone" value={tone} onChange={(e) => setTone(e.target.value as typeof tone)}>
                  {TONES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <InfoLabel
                htmlFor="angle"
                label="Angle"
                info="The opening hook for this touch: FirstTouch (intro), FollowUp (no-reply nudge), Breakup (closing the loop), Value (ROI proof), Invitation (CTA to meet)."
              />
              <Select id="angle" value={angle} onChange={(e) => setAngle(e.target.value as TouchAngle)}>
                {ANGLES.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="maxlen">Max length</Label>
                <span className="text-xs text-muted-foreground">{maxLength} words</span>
              </div>
              <input
                id="maxlen"
                type="range"
                min={60}
                max={400}
                step={10}
                value={maxLength}
                onChange={(e) => setMaxLength(Number(e.target.value))}
                className="w-full accent-primary"
              />
            </div>
            <Button className="w-full" onClick={handleGenerate} disabled={generateMut.isPending}>
              {generateMut.isPending ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" /> Generating…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" /> Generate
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Brand Voice + A/B Test controls — Help Guide §Email Studio */}
        <div className="space-y-4 lg:col-span-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Palette className="h-4 w-4" />
                Brand Voice
              </CardTitle>
              <CardDescription>
                Attach a campaign so AI writes in your brand's tone.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="brand-voice-campaign">Campaign for tone</Label>
                <Select id="brand-voice-campaign" value={brandVoiceCampaign} onChange={(e) => setBrandVoiceCampaign(e.target.value)}>
                  <option value="">— No brand voice —</option>
                  {MOCK_CAMPAIGNS.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </Select>
              </div>
              {!hasBrandVoice ? (
                <Badge variant="warning" className="text-xs">
                  No brand voice
                </Badge>
              ) : (
                <Badge variant="success" className="text-xs">
                  Brand voice: {MOCK_CAMPAIGNS.find((c) => c.id === brandVoiceCampaign)?.name}
                </Badge>
              )}
              {/* TODO: Collateral attachment UI — attach PDFs, decks, etc. for tone extraction */}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <FlaskConical className="h-4 w-4" />
                Subject Line A/B Test
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="flex items-center gap-2 text-sm">
                <Switch checked={abTestEnabled} onCheckedChange={setAbTestEnabled} />
                Enable A/B test
              </label>
              {abTestEnabled && (
                <div className="space-y-2">
                  <Label htmlFor="subject-b">Variant B subject</Label>
                  <Input
                    id="subject-b"
                    placeholder="Enter variant B subject line…"
                    value={subjectB}
                    onChange={(e) => setSubjectB(e.target.value)}
                  />
                  <Button size="sm" variant="outline" className="w-full" disabled={!subjectB} onClick={() => toast.info("A/B test saved — results available after send")}>
                    Save A/B Test
                  </Button>
                  <Button size="sm" variant="ghost" className="w-full" disabled={!subjectB} onClick={() => toast.info("Load results: no sends yet")}>
                    Load Results
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Center: Preview */}
        <Card className="lg:col-span-5">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Preview</CardTitle>
                <CardDescription>Variant QA scores shown below subject.</CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex rounded-md border" role="group" aria-label="Preview mode">
                  <Button
                    variant={previewMode === "text" ? "secondary" : "ghost"}
                    size="sm"
                    className="rounded-r-none"
                    onClick={() => setPreviewMode("text")}
                  >
                    Plain text
                  </Button>
                  <Button
                    variant={previewMode === "html" ? "secondary" : "ghost"}
                    size="sm"
                    className="rounded-l-none"
                    onClick={() => setPreviewMode("html")}
                  >
                    HTML
                  </Button>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleGenerate}
                  disabled={generateMut.isPending}
                >
                  <RefreshCw className="h-4 w-4" /> Regenerate
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {generateMut.isPending ? (
              <div className="space-y-3">
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-32 w-full" />
                <Skeleton className="h-6 w-1/2" />
              </div>
            ) : displayedVariants.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 rounded-md border border-dashed p-10 text-center">
                <FileText className="h-6 w-6 text-muted-foreground" />
                <p className="text-sm font-medium">No variants yet</p>
                <p className="text-sm text-muted-foreground">Click Generate to create email variants.</p>
              </div>
            ) : (
              <Tabs value={activeVariant} onValueChange={setActiveVariant}>
                <TabsList className="mb-3">
                  {displayedVariants.map((v, i) => (
                    <TabsTrigger key={v.id} value={v.id}>
                      Variant {i + 1}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {displayedVariants.map((v) => (
                  <TabsContent key={v.id} value={v.id}>
                    <div className="space-y-3">
                      <div className="rounded-md border bg-muted/30 p-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">Subject</p>
                        <p className="mt-1 font-medium">{v.subject}</p>
                      </div>
                      {previewMode === "text" ? (
                        <Textarea
                          aria-label="Email body (plain text)"
                          rows={12}
                          value={v.body}
                          readOnly
                          className="resize-none whitespace-pre-wrap font-mono text-xs"
                        />
                      ) : (
                        /* FR-029: HTML preview — line breaks become paragraphs,
                           rendered in a mail-client-like frame. Body text is
                           inserted as React text nodes (no raw-HTML injection),
                           so prospect-interpolated content cannot inject markup. */
                        <div
                          aria-label="Email body (HTML preview)"
                          className="min-h-[18rem] rounded-md border bg-white p-4 text-sm text-neutral-900 shadow-inner dark:bg-neutral-50"
                        >
                          {v.body.split(/\n{2,}/).map((para, pi) => (
                            <p key={pi} className="mb-3 leading-relaxed">
                              {para.split("\n").map((line, li, arr) => (
                                <span key={li}>
                                  {line}
                                  {li < arr.length - 1 && <br />}
                                </span>
                              ))}
                            </p>
                          ))}
                        </div>
                      )}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="space-y-1 rounded-md border p-3">
                          <p className="text-xs text-muted-foreground">QA Score</p>
                          <p className="text-sm font-semibold">{formatPercent(v.qaScore)}</p>
                          <Progress value={v.qaScore * 100} />
                        </div>
                        <div className="space-y-1 rounded-md border p-3">
                          <p className="text-xs text-muted-foreground">Personalisation</p>
                          <p className="text-sm font-semibold">
                            {formatPercent(v.personalisationConfidence)}
                          </p>
                          <Progress
                            value={v.personalisationConfidence * 100}
                            indicatorClassName="bg-emerald-600"
                          />
                        </div>
                        <div className="space-y-1 rounded-md border p-3">
                          <p className="text-xs text-muted-foreground">Manual review</p>
                          {v.flagForManualReview ? (
                            <Badge variant="warning">Flagged</Badge>
                          ) : (
                            <Badge variant="success">Cleared</Badge>
                          )}
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Framework: <span className="font-medium capitalize">{v.framework}</span>
                      </p>
                    </div>
                  </TabsContent>
                ))}
              </Tabs>
            )}
          </CardContent>
        </Card>

        {/* Right: QA results */}
        <div className="space-y-4 lg:col-span-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">Anti-Pattern Scan</CardTitle>
                  <CardDescription>Detects generic, vague, or weak copy.</CardDescription>
                </div>
                {antiPattern && (
                  <Badge variant={antiPattern.overallScore >= 0.8 ? "success" : "warning"}>
                    {formatPercent(antiPattern.overallScore)}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {antiPatternMut.isPending ? (
                <Skeleton className="h-24 w-full" />
              ) : !antiPattern ? (
                <p className="text-sm text-muted-foreground">Run QA to see anti-pattern findings.</p>
              ) : antiPattern.findings.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" /> No anti-patterns detected.
                </div>
              ) : (
                <ScrollArea maxHeightClass="max-h-72">
                  <div className="space-y-2">
                    {antiPattern.findings.map((f) => (
                      <div key={f.pattern} className="rounded-md border p-3">
                        <div className="mb-1 flex items-center justify-between">
                          <span className="text-sm font-medium">{f.pattern}</span>
                          <Badge
                            variant={
                              f.severity === "high"
                                ? "destructive"
                                : f.severity === "medium"
                                  ? "warning"
                                  : "secondary"
                            }
                          >
                            {f.severity}
                          </Badge>
                        </div>
                        <p className="rounded bg-muted/40 px-2 py-1 text-xs italic">
                          “{truncate(f.snippet, 80)}”
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          <Wand2 className="mr-1 inline h-3 w-3" />
                          {f.suggestion}
                        </p>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">Compliance Check</CardTitle>
                  <CardDescription>CAN-SPAM + GDPR guardrails.</CardDescription>
                </div>
                {compliance && (
                  <Badge variant={compliance.overallPassed ? "success" : "destructive"}>
                    {compliance.overallPassed ? "PASS" : "FAIL"}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {complianceMut.isPending ? (
                <Skeleton className="h-24 w-full" />
              ) : !compliance ? (
                <p className="text-sm text-muted-foreground">Run QA to see compliance results.</p>
              ) : (
                <div className="space-y-2">
                  {compliance.checks.map((chk) => (
                    <div
                      key={chk.id}
                      className={cn(
                        "flex items-start gap-2 rounded-md border p-2.5 text-sm",
                        chk.passed ? "border-emerald-200 bg-emerald-50/40" : "border-red-200 bg-red-50/40",
                      )}
                    >
                      {chk.passed ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                      ) : (
                        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{chk.label}</span>
                          <Badge variant="outline" className="text-[10px]">
                            {chk.regulation}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">{chk.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {(antiPattern?.overallScore !== undefined && antiPattern.overallScore < 0.8) ||
          (compliance && !compliance.overallPassed) ? (
            <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>This variant has QA issues. Consider regenerating or editing manually before sending.</p>
            </div>
          ) : null}
        </div>
      </div>

      {/* ── AI QA Score Dialog ──────────────────────────────────────────── */}
      <Dialog open={qaScoreOpen} onOpenChange={setQaScoreOpen}>
        <DialogHeader>
          <DialogTitle>AI QA Score</DialogTitle>
          <DialogDescription>
            Multi-dimensional quality assessment of your email.
          </DialogDescription>
        </DialogHeader>
        {qaScoreResult && (
          <div className="space-y-5">
            {/* Total score */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Total Score</span>
                <span className="text-2xl font-bold">
                  {qaScoreResult.totalScore} / {qaScoreResult.maxScore}
                </span>
              </div>
              <Progress
                value={(qaScoreResult.totalScore / qaScoreResult.maxScore) * 100}
                indicatorClassName={
                  qaScoreResult.totalScore / qaScoreResult.maxScore >= 0.8
                    ? "bg-emerald-600"
                    : qaScoreResult.totalScore / qaScoreResult.maxScore >= 0.6
                      ? "bg-amber-500"
                      : "bg-red-500"
                }
              />
            </div>

            {/* Dimension scores */}
            <div className="space-y-3">
              <p className="text-xs font-medium uppercase text-muted-foreground">Dimensions</p>
              {qaScoreResult.dimensions.map((d) => (
                <div key={d.name} className="space-y-1 rounded-md border p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{d.name}</span>
                    <span className="text-sm font-semibold">
                      {d.score} / {d.max}
                    </span>
                  </div>
                  <Progress
                    value={(d.score / d.max) * 100}
                    indicatorClassName={
                      d.score / d.max >= 0.8
                        ? "bg-emerald-600"
                        : d.score / d.max >= 0.6
                          ? "bg-amber-500"
                          : "bg-red-500"
                    }
                  />
                  <p className="text-xs text-muted-foreground">{d.feedback}</p>
                </div>
              ))}
            </div>

            {/* Flags */}
            {qaScoreResult.flags.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase text-muted-foreground">Flags</p>
                <div className="flex flex-wrap gap-1.5">
                  {qaScoreResult.flags.map((flag, i) => (
                    <Badge key={i} variant="warning">{flag}</Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Suggested Rewrite */}
            {qaScoreResult.suggestedRewrite && (
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase text-muted-foreground">Suggested Rewrite</p>
                <div className="rounded-md border bg-muted/30 p-3 text-sm whitespace-pre-wrap">
                  {qaScoreResult.suggestedRewrite}
                </div>
              </div>
            )}
          </div>
        )}
        <DialogFooter>
          <DialogClose onClose={() => setQaScoreOpen(false)} />
        </DialogFooter>
      </Dialog>

      {/* ── Subject Lines Dialog ────────────────────────────────────────── */}
      <Dialog open={subjectsOpen} onOpenChange={setSubjectsOpen}>
        <DialogHeader>
          <DialogTitle>Subject Line Variants</DialogTitle>
          <DialogDescription>
            AI-generated subject lines with predicted open rates.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {subjectLines.length === 0 ? (
            <p className="text-sm text-muted-foreground">No variants generated yet.</p>
          ) : (
            subjectLines.map((sl, i) => (
              <div key={i} className="space-y-1.5 rounded-md border p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">{sl.subject}</p>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="shrink-0"
                    onClick={() => {
                      navigator.clipboard.writeText(sl.subject);
                      toast.success("Copied to clipboard");
                    }}
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="text-xs">
                    Open rate: {(sl.predictedOpenRate * 100).toFixed(1)}%
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">{sl.rationale}</p>
              </div>
            ))
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              if (!currentVariant) return;
              subjectLinesMut.mutate({ body: currentVariant.body, subject: currentVariant.subject, prospectId });
            }}
            disabled={subjectLinesMut.isPending}
          >
            {subjectLinesMut.isPending ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Regenerate
          </Button>
          <DialogClose onClose={() => setSubjectsOpen(false)} />
        </DialogFooter>
      </Dialog>
    </div>
  );
}
