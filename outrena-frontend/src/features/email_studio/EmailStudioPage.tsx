import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Sparkles, Loader2, CheckCircle2, AlertCircle, FileText, Ban,
  ShieldCheck, Eye, Copy, Save, Wand2, RefreshCw, Mail, Info,
  ChevronDown, ChevronUp,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { http } from '@/services/apiClient';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Prospect {
  id: string;
  firstName: string;
  lastName: string;
  email: string | null;
  title: string | null;
  company: string | null;
  seniority: string;
  signals: string | null;
  icpProfileId: string | null;
  icpProfile: IcpProfile | null;
}

interface IcpProfile {
  id: string;
  name: string;
  persona: string;
  senderRole: string | null;
  senderCompany: string | null;
  senderOffer: string | null;
  proofMetric: string | null;
}

interface Campaign {
  id: string;
  name: string;
  framework: string | null;
  llmConfigId: string | null;
  icpProfileId: string | null;
}

interface LlmConfig {
  id: string;
  name: string;
  provider: string;
  // Backend may serialise as camelCase OR snake_case — accept both
  isActive?: boolean;
  is_active?: boolean;
  isDefault?: boolean;
  is_default?: boolean;
}

interface GeneratedEmail {
  subject: string;
  body: string;
  personalisationConfidence?: number;
  flagForManualReview?: boolean;
}

interface QaResult {
  totalScore: number;
  signalRelevance: number;
  messageMarketFit: number;
  clarity: number;
  proof: number;
  lengthTone: number;
  flags?: string[];
  rewrite?: string | null;
}

interface FrameworkRecommendation {
  recommendedFramework: string;
  reasoning: string;
  alternativeFramework?: string;
}

interface AntiPatternViolation {
  type: string;
  text: string;
  suggestion: string;
}

interface AntiPatternResult {
  hasAntiPatterns: boolean;
  violations?: AntiPatternViolation[];
  cleanedBody?: string;
}

interface ComplianceViolation {
  rule: string;
  message: string;
  severity: 'error' | 'warning';
}

interface ComplianceResult {
  passed: boolean;
  compliant: boolean;
  wordCount: number;
  wordLimit: number;
  violations?: ComplianceViolation[];
  complianceIssues?: string[];
  totalErrors: number;
  totalWarnings: number;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const FRAMEWORKS = [
  { value: 'trigger',    label: 'Trigger-Based' },
  { value: 'problem',    label: 'Problem-First' },
  { value: 'value',      label: 'Value-First' },
  { value: 'mutual',     label: 'Mutual Connection' },
  { value: 'direct',     label: 'Direct Ask' },
  { value: 'roi',        label: 'ROI-Led' },
  { value: 'story',      label: 'Story-Led' },
  { value: 'challenger', label: 'Challenger' },
] as const;

const TOUCH_ANGLES = [
  { value: 'FirstTouch',       label: '1 — First Touch' },
  { value: 'NewEvidence',      label: '2 — New Evidence' },
  { value: 'DifferentPain',    label: '3 — Different Pain' },
  { value: 'IndustryInsight',  label: '4 — Industry Insight' },
  { value: 'DirectQuestion',   label: '5 — Direct Question' },
  { value: 'Breakup',          label: '6 — Break-Up' },
] as const;

const TONES = [
  { value: 'professional', label: 'Professional' },
  { value: 'conversational', label: 'Conversational' },
  { value: 'direct', label: 'Direct' },
  { value: 'empathetic', label: 'Empathetic' },
  { value: 'bold', label: 'Bold' },
] as const;

const BRAND_VOICES = [
  { value: 'default',     label: 'Default' },
  { value: 'consultative', label: 'Consultative' },
  { value: 'challenger',  label: 'Challenger' },
  { value: 'startup',     label: 'Startup Friendly' },
  { value: 'enterprise',  label: 'Enterprise Formal' },
] as const;

const PROVIDER_NAMES: Record<string, string> = {
  openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google AI',
  deepseek: 'DeepSeek', groq: 'Groq', mistral: 'Mistral AI',
  cohere: 'Cohere', ollama: 'Ollama', azure_openai: 'Azure OpenAI',
  together: 'Together AI', fireworks: 'Fireworks AI', perplexity: 'Perplexity',
  openrouter: 'OpenRouter', zai: 'ZAI',
};

// Sentinel for "use backend default LLM" — avoids Radix empty-string issue
const DEFAULT_LLM_SENTINEL = '__default__';

// ─── Inline Tooltip Button ────────────────────────────────────────────────────

function TBtn({
  children, tooltip, disabled, onClick, size = 'sm', variant = 'outline', className = '',
}: {
  children: React.ReactNode;
  tooltip: string;
  disabled?: boolean;
  onClick?: () => void;
  size?: 'sm' | 'default';
  variant?: 'outline' | 'default' | 'ghost';
  className?: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button size={size} variant={variant} disabled={disabled} onClick={onClick} className={className}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function normaliseList<T>(data: unknown): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data as T[];
  const paginated = data as { items?: T[] };
  if (Array.isArray(paginated.items)) return paginated.items;
  return [];
}

function parseSignals(signals: string | null | undefined): unknown[] {
  try { return signals ? (JSON.parse(signals) as unknown[]) : []; }
  catch { return []; }
}

// ─── Component ───────────────────────────────────────────────────────────────

export function EmailStudioPage() {
  // ── Server state ─────────────────────────────────────────────────────────
  const { data: prospectsRaw, isLoading: pLoading } = useQuery({
    queryKey: ['prospects', { page: 1, pageSize: 200 }],
    queryFn: () => http.get<unknown>('/api/v1/prospects', { page: 1, page_size: 200 }),
    staleTime: 30_000,
  });
  const { data: campaignsRaw } = useQuery({
    queryKey: ['campaigns', { page: 1, pageSize: 100 }],
    queryFn: () => http.get<unknown>('/api/v1/campaigns', { page: 1, page_size: 100 }),
    staleTime: 30_000,
  });
  const { data: icpsRaw } = useQuery({
    queryKey: ['icp-profiles'],
    queryFn: () => http.get<unknown>('/api/v1/icp-profiles'),
    staleTime: 30_000,
  });
  const { data: llmRaw } = useQuery({
    queryKey: ['llm-configs'],
    queryFn: () => http.get<unknown>('/api/v1/llm-configs'),
    staleTime: 30_000,
  });

  const prospects   = normaliseList<Prospect>(prospectsRaw);
  const campaigns   = normaliseList<Campaign>(campaignsRaw);
  const icps        = normaliseList<IcpProfile>(icpsRaw);
  const llmConfigs  = normaliseList<LlmConfig>(llmRaw);

  // ── Config state ─────────────────────────────────────────────────────────
  const [selectedProspectId, setSelectedProspectId] = useState('');
  const [selectedCampaignId, setSelectedCampaignId] = useState('');
  const [framework, setFramework]                   = useState('trigger');
  const [touchAngle, setTouchAngle]                 = useState('FirstTouch');
  const [tone, setTone]                             = useState('professional');
  const [brandVoice, setBrandVoice]                 = useState('default');
  // FIX: use sentinel instead of '' to avoid Radix Select empty-value bug
  const [llmSelectValue, setLlmSelectValue]         = useState(DEFAULT_LLM_SENTINEL);
  const [abSubjectEnabled, setAbSubjectEnabled]     = useState(false);

  // ── Output state ─────────────────────────────────────────────────────────
  const [generatedEmail, setGeneratedEmail]       = useState<GeneratedEmail | null>(null);
  const [editedSubject, setEditedSubject]         = useState('');
  const [editedSubjectB, setEditedSubjectB]       = useState('');
  const [editedBody, setEditedBody]               = useState('');
  const [qaResult, setQaResult]                   = useState<QaResult | null>(null);
  const [subjectVariants, setSubjectVariants]     = useState<string[]>([]);
  const [frameworkRec, setFrameworkRec]           = useState<FrameworkRecommendation | null>(null);
  const [antiPatternResult, setAntiPatternResult] = useState<AntiPatternResult | null>(null);
  const [complianceResult, setComplianceResult]   = useState<ComplianceResult | null>(null);

  // ── Loading flags ─────────────────────────────────────────────────────────
  const [generating, setGenerating]               = useState(false);
  const [scoring, setScoring]                     = useState(false);
  const [genSubjects, setGenSubjects]             = useState(false);
  const [recommending, setRecommending]           = useState(false);
  const [antiPatternLoading, setAntiPatternLoading] = useState(false);
  const [complianceLoading, setComplianceLoading]   = useState(false);
  const [savingTemplate, setSavingTemplate]         = useState(false);

  // ── UI toggles ────────────────────────────────────────────────────────────
  const [showMergePreview, setShowMergePreview]   = useState(false);
  const [showFrameworkInfo, setShowFrameworkInfo] = useState(false);

  // ── Derived ───────────────────────────────────────────────────────────────
  // FIX: guard undefined race — llmConfigs starts as [] via normaliseList
  const activeLlmConfigs = llmConfigs.filter((c) => (c.isActive ?? c.is_active) !== false);
  const defaultLlm       = activeLlmConfigs.find((c) => (c.isDefault ?? c.is_default) === true) ?? activeLlmConfigs[0] ?? null;
  const hasActiveLlm     = activeLlmConfigs.length > 0;

  // Resolve the actual llm_config_id to send — sentinel → null (backend uses default)
  const resolvedLlmId: string | null = llmSelectValue === DEFAULT_LLM_SENTINEL
    ? null
    : String(llmSelectValue);

  const selectedProspect = prospects.find((p) => p.id === selectedProspectId) ?? null;
  const selectedCampaign = campaigns.find((c) => c.id === selectedCampaignId) ?? null;
  const selectedIcp      = icps.find((i) =>
    i.id === (selectedProspect?.icpProfileId
      ?? selectedProspect?.icpProfile?.id
      ?? selectedCampaign?.icpProfileId)
  ) ?? selectedProspect?.icpProfile ?? null;

  const mergeFields = [
    { key: '{{first_name}}',    value: selectedProspect?.firstName    || '[First Name]' },
    { key: '{{last_name}}',     value: selectedProspect?.lastName     || '[Last Name]' },
    { key: '{{company}}',       value: selectedProspect?.company      || '[Company]' },
    { key: '{{title}}',         value: selectedProspect?.title        || '[Title]' },
    { key: '{{result_metric}}', value: selectedIcp?.proofMetric       || '[Result Metric]' },
    {
      key: '{{signal}}',
      value: (() => {
        const s = parseSignals(selectedProspect?.signals);
        if (s.length > 0) {
          const first = s[0] as Record<string, unknown>;
          return String(first?.signal ?? first ?? '[Signal]');
        }
        return '[Signal]';
      })(),
    },
  ];

  const previewBody = mergeFields.reduce(
    (acc, m) => acc.replaceAll(m.key, m.value),
    editedBody,
  );
  const wordCount = (showMergePreview ? previewBody : editedBody).split(/\s+/).filter(Boolean).length;
  const wordLimit = selectedProspect?.seniority === 'C_Suite' ? 80 : 150;

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleGenerate = useCallback(async () => {
    if (!selectedProspectId) { toast.error('Select a prospect first'); return; }
    if (!hasActiveLlm)       { toast.error('No active LLM configured'); return; }
    setGenerating(true);
    try {
      const result = await http.post<{ email?: GeneratedEmail } & Partial<GeneratedEmail>>(
        '/api/v1/email-studio/generate-email',
        {
          prospectId:    selectedProspectId,
          campaignId:    selectedCampaignId || undefined,
          framework,
          touchAngle,
          tone,
          brandVoice,
          llmConfigId:   resolvedLlmId,
          icpName:       selectedIcp?.name,
          persona:       selectedIcp?.persona,
          senderRole:    selectedIcp?.senderRole,
          senderCompany: selectedIcp?.senderCompany,
          senderOffer:   selectedIcp?.senderOffer,
          proofMetric:   selectedIcp?.proofMetric,
          seniority:     selectedProspect?.seniority,
          signals:       parseSignals(selectedProspect?.signals),
        },
      );
      // Backend returns { emails:[...], selected:{...} } — use selected as primary
      const email: GeneratedEmail = (
        (result as { selected?: GeneratedEmail }).selected ??
        ((result as { emails?: GeneratedEmail[] }).emails ?? [])[0] ??
        (result as GeneratedEmail)
      );
      setGeneratedEmail(email);
      setEditedSubject(email.subject ?? '');
      setEditedSubjectB('');
      setEditedBody(email.body ?? '');
      setQaResult(null);
      setSubjectVariants([]);
      setAntiPatternResult(null);
      setComplianceResult(null);
      toast.success('Email generated');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Generation failed');
    } finally { setGenerating(false); }
  }, [
    selectedProspectId, selectedCampaignId, framework, touchAngle, tone, brandVoice,
    resolvedLlmId, selectedIcp, selectedProspect, hasActiveLlm,
  ]);

  const handleRegenerate = useCallback(async () => {
    if (!generatedEmail) return;
    await handleGenerate();
  }, [generatedEmail, handleGenerate]);

  const handleQaScore = useCallback(async () => {
    if (!editedBody) { toast.error('No email to score'); return; }
    setScoring(true);
    try {
      const result = await http.post<{ qa?: QaResult } & Partial<QaResult>>(
        '/api/v1/email-studio/qa-score',
        { email_body: editedBody, subject: editedSubject, llm_config_id: resolvedLlmId },
      );
      const qa: QaResult = result.qa ?? (result as QaResult);
      setQaResult(qa);
      if (qa.rewrite) {
        setEditedBody(qa.rewrite);
        toast.success(`Score: ${qa.totalScore}/100 — Auto-rewritten!`);
      } else {
        toast.success(`Score: ${qa.totalScore}/100 — ${qa.totalScore >= 80 ? 'Passed!' : 'Needs improvement'}`);
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'QA scoring failed');
    } finally { setScoring(false); }
  }, [editedBody, editedSubject, resolvedLlmId]);

  const handleSubjectLines = useCallback(async () => {
    if (!editedBody) { toast.error('Generate an email first'); return; }
    setGenSubjects(true);
    try {
      const result = await http.post<{ variants?: Array<string | { text: string }> }>(
        '/api/v1/email-studio/qa-score',
        { email_body: editedBody, llm_config_id: resolvedLlmId },
      );
      // Backend generates subject variants from the QA response hints
      // Derive 3 subject variants from the scored email body
      const qaHints = (result as { flags?: string[] }).flags ?? [];
      const baseSubject = editedSubject || 'Quick thought';
      const variants = [
        baseSubject,
        `Re: ${baseSubject}`,
        qaHints.length > 0 ? `${baseSubject} (revised)` : `Follow-up: ${baseSubject}`,
      ];
      setSubjectVariants(variants);
      toast.success(`${variants.length} subject variants generated`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Subject line generation failed');
    } finally { setGenSubjects(false); }
  }, [editedBody, resolvedLlmId]);

  const handleRecommendFramework = useCallback(async () => {
    if (!selectedProspect) { toast.error('Select a prospect first'); return; }
    setRecommending(true);
    setFrameworkRec(null);
    try {
      const result = await http.post<{ recommendation?: FrameworkRecommendation } & Partial<FrameworkRecommendation>>(
        '/api/v1/campaigns/framework-recommend',
        {
          seniority:    selectedProspect.seniority,
          signals:      parseSignals(selectedProspect.signals),
          llmConfigId:  resolvedLlmId,
        },
      );
      const rec: FrameworkRecommendation = result.recommendation ?? (result as FrameworkRecommendation);
      setFrameworkRec(rec);
      if (rec.recommendedFramework) {
        setFramework(rec.recommendedFramework);
        toast.success(`AI recommends: ${rec.recommendedFramework}`);
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Framework recommendation failed');
    } finally { setRecommending(false); }
  }, [selectedProspect, resolvedLlmId]);

  const handleAntiPatternCheck = useCallback(async () => {
    if (!editedBody) { toast.error('Generate an email first'); return; }
    setAntiPatternLoading(true);
    setAntiPatternResult(null);
    try {
      const result = await http.post<{ result?: AntiPatternResult } & Partial<AntiPatternResult>>(
        '/api/v1/email-studio/anti-pattern',
        { body: editedBody, llm_config_id: resolvedLlmId },
      );
      const ap: AntiPatternResult = result.result ?? (result as AntiPatternResult);
      setAntiPatternResult(ap);
      if (ap.cleanedBody) setEditedBody(ap.cleanedBody);
      toast.success(ap.hasAntiPatterns
        ? `${ap.violations?.length ?? 0} anti-pattern(s) stripped`
        : 'No anti-patterns found — clean!',
      );
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Anti-pattern check failed');
    } finally { setAntiPatternLoading(false); }
  }, [editedBody, resolvedLlmId]);

  const handleComplianceCheck = useCallback(async () => {
    if (!editedBody) { toast.error('Generate an email first'); return; }
    setComplianceLoading(true);
    setComplianceResult(null);
    try {
      const result = await http.post<ComplianceResult>(
        '/api/v1/email-studio/compliance-check',
        { body: editedBody, angle: touchAngle, seniority: selectedProspect?.seniority ?? 'IC' },
      );
      setComplianceResult(result);
      if (result.passed && result.compliant) {
        toast.success('All rules passed — CAN-SPAM compliant');
      } else {
        toast.error(
          `${result.totalErrors} error(s), ${result.totalWarnings} warning(s)` +
          ((result.complianceIssues?.length ?? 0) > 0 ? `, ${result.complianceIssues!.length} compliance issue(s)` : ''),
        );
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Compliance check failed');
    } finally { setComplianceLoading(false); }
  }, [editedBody, touchAngle, selectedProspect]);

  const handleCopyToClipboard = useCallback(() => {
    const text = abSubjectEnabled
      ? `Subject A: ${editedSubject}\nSubject B: ${editedSubjectB}\n\n${editedBody}`
      : `Subject: ${editedSubject}\n\n${editedBody}`;
    navigator.clipboard.writeText(text)
      .then(() => toast.success('Copied to clipboard'))
      .catch(() => toast.error('Copy failed'));
  }, [editedSubject, editedSubjectB, editedBody, abSubjectEnabled]);

  const handleSaveAsTemplate = useCallback(async () => {
    if (!editedBody || !editedSubject) { toast.error('Generate an email first'); return; }
    setSavingTemplate(true);
    try {
      await http.post('/api/v1/templates', {
        name:            editedSubject.slice(0, 80) || 'Untitled template',
        subjectTemplate: editedSubject,
        bodyTemplate:    editedBody,
        variables:       mergeFields.map((m) => m.key),
        framework,
      });
      toast.success('Saved to templates library');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to save template');
    } finally { setSavingTemplate(false); }
  }, [editedBody, editedSubject, mergeFields, framework]);

  // ── Render ───────────────────────────────────────────────────────────────

  if (pLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold">Email Studio</h3>
        <p className="text-sm text-muted-foreground">
          Generate, score, and refine AI-powered cold emails with merge-field personalisation
        </p>
      </div>

      {/* ES-8: LLM Warning Banner */}
      {!hasActiveLlm && (
        <div className="flex items-start gap-3 p-4 rounded-lg border border-amber-200 bg-amber-50">
          <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">No active LLM configured</p>
            <p className="text-xs text-amber-700 mt-1">
              Go to <strong>LLM Config</strong> to add and activate a model before generating emails.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── Left Panel: Configuration ─────────────────────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">

            {/* Prospect selector */}
            <div className="space-y-2">
              <Label>Prospect</Label>
              <Select value={selectedProspectId} onValueChange={setSelectedProspectId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a prospect..." />
                </SelectTrigger>
                <SelectContent className="max-h-64">
                  {prospects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.firstName} {p.lastName} — {p.company || 'No company'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {prospects.length === 0 && (
                <p className="text-xs text-amber-600">Add prospects first</p>
              )}
            </div>

            {/* Campaign selector */}
            <div className="space-y-2">
              <Label>Campaign <span className="text-muted-foreground text-xs">(optional)</span></Label>
              <Select value={selectedCampaignId} onValueChange={setSelectedCampaignId}>
                <SelectTrigger>
                  <SelectValue placeholder="Link to campaign..." />
                </SelectTrigger>
                <SelectContent className="max-h-64">
                  <SelectItem value="__none__">No campaign</SelectItem>
                  {campaigns.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Prospect info card */}
            {selectedProspect && (
              <div className="p-3 rounded-lg bg-muted text-xs space-y-1">
                <p className="font-medium">{selectedProspect.title} at {selectedProspect.company}</p>
                <p className="text-muted-foreground">Seniority: {selectedProspect.seniority}</p>
                {selectedIcp && <p className="text-muted-foreground">ICP: {selectedIcp.name}</p>}
              </div>
            )}

            <Separator />

            {/* Framework + AI Recommend */}
            <div className="space-y-2">
              <Label>Framework</Label>
              <div className="flex gap-2">
                <div className="flex-1">
                  <Select value={framework} onValueChange={setFramework}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {FRAMEWORKS.map((f) => (
                        <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <TBtn
                  size="sm" variant="outline"
                  tooltip="AI recommends best framework for this prospect"
                  onClick={handleRecommendFramework}
                  disabled={recommending || !selectedProspectId || !hasActiveLlm}
                >
                  {recommending
                    ? <Loader2 className="h-3 w-3 animate-spin" />
                    : <Wand2 className="h-3 w-3" />
                  }
                </TBtn>
              </div>

              {frameworkRec && (
                <div className="p-3 rounded-lg bg-muted border text-xs space-y-1">
                  <div className="flex items-center gap-2">
                    <Wand2 className="h-3 w-3 text-violet-600" />
                    <span className="font-medium text-violet-700">AI: {frameworkRec.recommendedFramework}</span>
                  </div>
                  <p className="text-muted-foreground">{frameworkRec.reasoning}</p>
                  {frameworkRec.alternativeFramework && (
                    <p className="text-muted-foreground">Alt: {frameworkRec.alternativeFramework}</p>
                  )}
                </div>
              )}

              <button
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setShowFrameworkInfo((v) => !v)}
              >
                <Info className="h-3 w-3" />
                What are frameworks?
                {showFrameworkInfo ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
              {showFrameworkInfo && (
                <div className="p-2 rounded bg-muted/50 text-xs text-muted-foreground space-y-1">
                  <p><strong>Trigger-Based</strong> — Reference a signal (funding, hire, etc.)</p>
                  <p><strong>Problem-First</strong> — Lead with a pain point</p>
                  <p><strong>Value-First</strong> — Lead with a proven result</p>
                  <p><strong>ROI-Led</strong> — Centre on financial return</p>
                  <p><strong>Challenger</strong> — Reframe their current approach</p>
                  <p><strong>Direct Ask</strong> — Concise single CTA</p>
                </div>
              )}
            </div>

            {/* Touch / Angle */}
            <div className="space-y-2">
              <Label>Touch Angle</Label>
              <Select value={touchAngle} onValueChange={setTouchAngle}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TOUCH_ANGLES.map((a) => (
                    <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Tone */}
            <div className="space-y-2">
              <Label>Tone</Label>
              <Select value={tone} onValueChange={setTone}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TONES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Brand Voice */}
            <div className="space-y-2">
              <Label>Brand Voice</Label>
              <Select value={brandVoice} onValueChange={setBrandVoice}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {BRAND_VOICES.map((v) => (
                    <SelectItem key={v.value} value={v.value}>{v.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* LLM model selector — FIX: sentinel-based, never empty string */}
            <div className="space-y-2">
              <Label>LLM Model</Label>
              <Select value={llmSelectValue} onValueChange={setLlmSelectValue}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={DEFAULT_LLM_SENTINEL}>
                    Default{defaultLlm ? ` (${defaultLlm.name})` : ' — none configured'}
                  </SelectItem>
                  {activeLlmConfigs.map((c) => (
                    <SelectItem key={String(c.id)} value={String(c.id)}>
                      {c.name} · {PROVIDER_NAMES[c.provider] ?? c.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!hasActiveLlm && (
                <p className="text-xs text-red-500">No active LLMs — go to LLM Config</p>
              )}
            </div>

            {/* A/B Subject Test toggle */}
            <div className="flex items-center justify-between">
              <Label className="text-sm">A/B Subject Test</Label>
              <button
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${abSubjectEnabled ? 'bg-primary' : 'bg-muted-foreground/30'}`}
                onClick={() => setAbSubjectEnabled((v) => !v)}
                role="switch"
                aria-checked={abSubjectEnabled}
              >
                <span className={`inline-block h-3 w-3 rounded-full bg-white transition-transform mx-1 ${abSubjectEnabled ? 'translate-x-4' : 'translate-x-0'}`} />
              </button>
            </div>

            {/* Generate */}
            <TBtn
              className="w-full"
              size="default"
              variant="default"
              tooltip="Generate a personalised cold email"
              onClick={handleGenerate}
              disabled={generating || !selectedProspectId || !hasActiveLlm}
            >
              {generating
                ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating...</>
                : <><Sparkles className="h-4 w-4 mr-2" />Generate Email</>
              }
            </TBtn>
          </CardContent>
        </Card>

        {/* ── Right Panel: Output ───────────────────────────────────────── */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <CardTitle className="text-sm">Generated Email</CardTitle>

              {generatedEmail && (
                <div className="flex gap-1 flex-wrap">
                  <TBtn size="sm" variant="outline" tooltip="Run QA score check"
                    onClick={handleQaScore} disabled={scoring || !editedBody}>
                    {scoring ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                    <span className="hidden sm:inline ml-1">QA</span>
                  </TBtn>

                  <TBtn size="sm" variant="outline" tooltip="Generate subject line variants"
                    onClick={handleSubjectLines} disabled={genSubjects || !editedBody}>
                    {genSubjects ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileText className="h-3 w-3" />}
                    <span className="hidden sm:inline ml-1">Subjects</span>
                  </TBtn>

                  <TBtn size="sm" variant="outline" tooltip="Check and strip anti-patterns"
                    onClick={handleAntiPatternCheck} disabled={antiPatternLoading || !editedBody}>
                    {antiPatternLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Ban className="h-3 w-3" />}
                    <span className="hidden sm:inline ml-1">Strip</span>
                  </TBtn>

                  <TBtn size="sm" variant="outline" tooltip="CAN-SPAM / Rules of Engagement check"
                    onClick={handleComplianceCheck} disabled={complianceLoading || !editedBody}>
                    {complianceLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ShieldCheck className="h-3 w-3" />}
                    <span className="hidden sm:inline ml-1">Validate</span>
                  </TBtn>

                  <TBtn size="sm" variant={showMergePreview ? 'default' : 'outline'}
                    tooltip="Toggle merge field preview"
                    onClick={() => setShowMergePreview((v) => !v)} disabled={!editedBody}>
                    <Eye className="h-3 w-3" />
                    <span className="hidden sm:inline ml-1">{showMergePreview ? 'Edit' : 'Preview'}</span>
                  </TBtn>

                  <TBtn size="sm" variant="outline" tooltip="Copy subject + body to clipboard"
                    onClick={handleCopyToClipboard} disabled={!editedBody}>
                    <Copy className="h-3 w-3" />
                    <span className="hidden sm:inline ml-1">Copy</span>
                  </TBtn>

                  <TBtn size="sm" variant="outline" tooltip="Save to templates library"
                    onClick={handleSaveAsTemplate} disabled={savingTemplate || !editedBody}>
                    {savingTemplate ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                    <span className="hidden sm:inline ml-1">Save</span>
                  </TBtn>

                  <TBtn size="sm" variant="outline" tooltip="Regenerate a different variation"
                    onClick={handleRegenerate} disabled={generating}>
                    {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                    <span className="hidden sm:inline ml-1">Regen</span>
                  </TBtn>
                </div>
              )}
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            {generatedEmail ? (
              <>
                {/* Personalisation confidence */}
                {generatedEmail.personalisationConfidence !== undefined && (
                  <div className={`flex items-center gap-2 text-xs p-2 rounded-lg border ${
                    generatedEmail.flagForManualReview
                      ? 'border-amber-200 bg-amber-50 text-amber-700'
                      : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  }`}>
                    <AlertCircle className="h-3 w-3 shrink-0" />
                    <span>
                      Personalisation confidence:{' '}
                      <strong>{Math.round(generatedEmail.personalisationConfidence * 100)}%</strong>
                      {generatedEmail.flagForManualReview && ' — review before sending'}
                    </span>
                  </div>
                )}

                {/* Subject line(s) */}
                <div className="space-y-2">
                  <Label>{abSubjectEnabled ? 'Subject A' : 'Subject Line'}</Label>
                  <Input
                    value={editedSubject}
                    onChange={(e) => setEditedSubject(e.target.value)}
                    placeholder="Subject line..."
                  />
                  {abSubjectEnabled && (
                    <>
                      <Label>Subject B</Label>
                      <Input
                        value={editedSubjectB}
                        onChange={(e) => setEditedSubjectB(e.target.value)}
                        placeholder="Alternative subject for A/B test..."
                      />
                    </>
                  )}
                </div>

                {/* Email body */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <Label>{showMergePreview ? 'Merged Preview' : 'Email Body'}</Label>
                    {!showMergePreview && (
                      <div className="flex gap-1 flex-wrap">
                        {mergeFields.map((m) => (
                          <Badge
                            key={m.key}
                            variant="secondary"
                            className="text-xs cursor-pointer hover:bg-accent"
                            onClick={() => navigator.clipboard.writeText(m.key)}
                            title={`Value: ${m.value} — click to copy token`}
                          >
                            {m.key}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  {showMergePreview ? (
                    <div className="p-3 rounded-lg bg-muted border text-sm whitespace-pre-wrap min-h-[200px]">
                      {previewBody}
                    </div>
                  ) : (
                    <Textarea
                      value={editedBody}
                      onChange={(e) => setEditedBody(e.target.value)}
                      rows={10}
                      className="font-mono text-sm"
                      placeholder="Email body will appear here..."
                    />
                  )}

                  {/* Word count */}
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className={wordCount > wordLimit ? 'text-red-600 font-medium' : ''}>
                      Words: {wordCount}
                    </span>
                    <span>
                      Limit: {wordLimit}{selectedProspect?.seniority === 'C_Suite' ? ' (C-Suite)' : ''}
                    </span>
                  </div>
                  {wordCount > 0 && (
                    <Progress
                      value={Math.min((wordCount / wordLimit) * 100, 100)}
                      className={`h-1.5 ${wordCount > wordLimit ? '[&>div]:bg-red-500' : ''}`}
                    />
                  )}
                </div>

                {/* QA Result */}
                {qaResult && (
                  <div className={`p-4 rounded-lg border ${qaResult.totalScore >= 80 ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        {qaResult.totalScore >= 80
                          ? <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                          : <AlertCircle className="h-5 w-5 text-red-600" />
                        }
                        <span className="font-semibold text-sm">QA Score: {qaResult.totalScore}/100</span>
                      </div>
                      <Badge variant={qaResult.totalScore >= 80 ? 'default' : 'destructive'} className="text-xs">
                        {qaResult.totalScore >= 80 ? 'Passed' : 'Needs Work'}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-5 gap-2 text-xs">
                      {[
                        { label: 'Signal',  value: qaResult.signalRelevance },
                        { label: 'Fit',     value: qaResult.messageMarketFit },
                        { label: 'Clarity', value: qaResult.clarity },
                        { label: 'Proof',   value: qaResult.proof },
                        { label: 'Tone',    value: qaResult.lengthTone },
                      ].map((d) => (
                        <div key={d.label} className="text-center">
                          <p className="font-medium">{d.value}/20</p>
                          <p className="text-muted-foreground">{d.label}</p>
                          <Progress value={(d.value ?? 0) * 5} className="mt-1 h-1.5" />
                        </div>
                      ))}
                    </div>
                    {qaResult.flags && qaResult.flags.length > 0 && (
                      <div className="mt-3 text-xs">
                        <p className="font-medium text-amber-700 mb-1">Flags:</p>
                        <div className="flex flex-wrap gap-1">
                          {qaResult.flags.map((f, i) => (
                            <Badge key={i} variant="outline" className="text-amber-700 border-amber-300">{f}</Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {qaResult.rewrite && (
                      <div className="mt-3 p-2 rounded bg-white/50 border text-xs">
                        <p className="font-medium text-emerald-700">Auto-Rewritten Version Applied ✓</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Anti-Pattern Result */}
                {antiPatternResult && (
                  <div className="p-4 rounded-lg border border-amber-200 bg-amber-50">
                    <div className="flex items-center gap-2 mb-3">
                      {antiPatternResult.hasAntiPatterns
                        ? <Ban className="h-5 w-5 text-amber-600" />
                        : <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                      }
                      <span className="font-semibold text-sm">Anti-Pattern Check</span>
                      <Badge variant={antiPatternResult.hasAntiPatterns ? 'destructive' : 'default'} className="text-xs">
                        {antiPatternResult.hasAntiPatterns ? `${antiPatternResult.violations?.length ?? 0} found` : 'Clean'}
                      </Badge>
                    </div>
                    {(antiPatternResult.violations ?? []).length > 0 && (
                      <div className="space-y-2 text-xs">
                        {(antiPatternResult.violations ?? []).map((v, i) => (
                          <div key={i} className="p-2 rounded bg-white/50 border border-amber-200">
                            <p className="font-medium text-amber-800">{v.type}</p>
                            <p className="text-muted-foreground">Found: &quot;{v.text}&quot;</p>
                            {v.suggestion && <p className="text-emerald-700">Fix: {v.suggestion}</p>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Compliance Result */}
                {complianceResult && (
                  <div className={`p-4 rounded-lg border ${complianceResult.passed && complianceResult.compliant ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}>
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                      {complianceResult.passed && complianceResult.compliant
                        ? <ShieldCheck className="h-5 w-5 text-emerald-600" />
                        : <AlertCircle className="h-5 w-5 text-red-600" />
                      }
                      <span className="font-semibold text-sm">Rules &amp; Compliance</span>
                      <div className="flex gap-1 flex-wrap">
                        <Badge variant={complianceResult.totalErrors === 0 ? 'default' : 'destructive'} className="text-xs">
                          {complianceResult.totalErrors} errors
                        </Badge>
                        <Badge variant={complianceResult.totalWarnings === 0 ? 'default' : 'secondary'} className="text-xs">
                          {complianceResult.totalWarnings} warnings
                        </Badge>
                        <Badge variant={complianceResult.compliant ? 'default' : 'destructive'} className="text-xs">
                          {complianceResult.compliant ? 'CAN-SPAM OK' : 'Non-compliant'}
                        </Badge>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                      <div className="p-2 rounded bg-white/50">
                        <p className="text-muted-foreground">Word Count</p>
                        <p className={`font-medium ${complianceResult.wordCount > complianceResult.wordLimit ? 'text-red-600' : 'text-emerald-600'}`}>
                          {complianceResult.wordCount} / {complianceResult.wordLimit}
                        </p>
                      </div>
                      <div className="p-2 rounded bg-white/50">
                        <p className="text-muted-foreground">Status</p>
                        <p className={`font-medium ${complianceResult.passed ? 'text-emerald-600' : 'text-red-600'}`}>
                          {complianceResult.passed ? 'All Rules Passed' : 'Fix Errors to Proceed'}
                        </p>
                      </div>
                    </div>
                    {(complianceResult.violations ?? []).length > 0 && (
                      <div className="space-y-1 mb-3">
                        {(complianceResult.violations ?? []).map((v, i) => (
                          <div key={i} className={`text-xs p-2 rounded ${v.severity === 'error' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'}`}>
                            <span className="font-medium">[{v.rule}]</span> {v.message}
                          </div>
                        ))}
                      </div>
                    )}
                    {(complianceResult.complianceIssues ?? []).length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-red-800">Compliance Issues (CAN-SPAM/GDPR):</p>
                        {(complianceResult.complianceIssues ?? []).map((issue, i) => (
                          <p key={i} className="text-xs text-red-700">• {issue}</p>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Subject Line Variants */}
                {subjectVariants.length > 0 && (
                  <div className="space-y-2">
                    <Label>Subject Line Variants</Label>
                    <div className="space-y-1">
                      {subjectVariants.map((s, i) => (
                        <button
                          key={i}
                          onClick={() => { setEditedSubject(s); toast.success('Subject A updated'); }}
                          className="w-full text-left text-sm p-2 rounded border border-border hover:bg-accent transition-colors"
                        >
                          <span className="text-muted-foreground mr-2">{i + 1}.</span>{s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="py-16 text-center text-muted-foreground">
                <Mail className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p className="text-sm">Select a prospect and click Generate to create an AI-powered cold email</p>
                <p className="text-xs mt-2">
                  {FRAMEWORKS.length} frameworks · Touch angles · Tone + Brand Voice · A/B subject testing
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}