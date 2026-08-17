/**
 * IntegrationsPage.tsx — B2B prospecting integrations: platform cards,
 * connection testing, MailBridge summary, and CSV/enrichment guide cards.
 *
 * API (verified against app/features/integrations/router.py):
 *   GET    /api/v1/integrations                       list
 *   POST   /api/v1/integrations                        create (platform unique — 409 if exists)
 *   PUT    /api/v1/integrations/{id}                   update
 *   DELETE /api/v1/integrations/{id}                   delete
 *   POST   /api/v1/integrations/test                   { integrationId } → { ok, latencyMs, detail }
 *   GET    /api/v1/mailbridge/config                   MailBridge connections (via mailbridgeApi)
 *
 * NOTE: a per-platform "test search" endpoint (`/integrations/{id}/test-search`)
 * does not exist on the backend (confirmed gap — BE-MISSING). The Prospect
 * Search & Import section is therefore a documentation/walkthrough card
 * that points to the Prospects page's AI Prospect Sourcing Panel, which is
 * where the real search/import flow lives — it is not wired to a live call
 * here, to avoid hitting a non-existent endpoint.
 *
 * INT-1 ✓ Platform integration cards (logo/name, description, API key input,
 *          enable/disable, test connection) for 9 platforms.
 * INT-2 ✓ Bulk CSV Import guide card (format docs + column mapping table).
 * INT-3 ✓ MailBridge "Email Sending Engine" summary card w/ connection list.
 * INT-4 ✓ Prospect Search & Import guide card (walkthrough → Prospects page).
 * INT-5 ✓ Enriching Existing Prospects guide card (walkthrough → Prospects page).
 * INT-6 ✓ Connection test feedback — success/error toast + latency + inline result.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Zap,
  Ban,
  Save,
  TestTube2,
  CheckCircle2,
  ExternalLink,
  ClipboardCheck,
  Info,
  FileDown,
  Send,
  Search,
  Wand2,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

import { http, mailbridgeApi } from "@/services/apiClient";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatDateTime } from "@/lib/utils";

/* ── Types ─────────────────────────────────────────────────────────── */

interface Integration {
  id: string;
  platform: string;
  name: string;
  apiKey: string | null; // masked
  key_source: "tenant" | "platform";
  isActive: boolean;
  settings: Record<string, unknown>;
  lastTestedAt: string | null;
  lastTestResult: string | null;
  createdAt: string;
  updatedAt: string;
}

interface TestResponse {
  integrationId: string;
  ok: boolean;
  latencyMs?: number;
  detail?: string;
}

interface MailBridgeConfig {
  id: string;
  name: string;
  provider: string;
  fromEmail: string;
  baseUrl: string;
  isActive: boolean;
}

interface PlatformGuide {
  label: string;
  description: string;
  capabilities: string[];
  setupSteps: string[];
  apiDocs: string;
  signupUrl: string;
  freeTier: string;
  pricing: string;
  bestFor: string;
  color: string;
  searchSupported: boolean;
  enrichSupported: boolean;
  extraSettingsKey?: string;
  extraSettingsPlaceholder?: string;
  extraSettingsHint?: string;
}

/* ── Platform catalog (verbatim guide content from the Next.js reference) ── */

const PLATFORM_GUIDES: Record<string, PlatformGuide> = {
  apollo: {
    label: "Apollo",
    description:
      "Apollo.io is the leading B2B contact database with 275M+ contacts and 73M+ companies. It provides email addresses, phone numbers, intent signals, and advanced filtering by title, company size, industry, and technology stack.",
    capabilities: [
      "Search 275M+ B2B contacts by title, company, industry, tech stack",
      "Enrich existing prospects with email, phone, title, company data",
      "Intent signals — see who is actively researching your solution",
      "Export up to 10,000 contacts per search with email verification",
      "Advanced filtering: revenue, headcount growth, funding rounds, tech used",
    ],
    setupSteps: [
      "Go to apollo.io/sign-up and create a free account",
      "Navigate to Settings > API Keys in your Apollo dashboard",
      'Click "Create API Key" and copy the key',
      'Paste the API key in the field below and click "Save & Activate"',
      "Free tier: 1,000 email credits/month; paid plans unlock more",
    ],
    apiDocs: "https://apolloio.github.io/apollo-api-docs/",
    signupUrl: "https://www.apollo.io/sign-up",
    freeTier: "1,000 email credits/month",
    pricing: "Free → $49/mo (Basic) → $119/mo (Professional)",
    bestFor: "Large-scale prospect search, intent signals, verified emails",
    color: "border-blue-200 bg-blue-50/50",
    searchSupported: true,
    enrichSupported: true,
  },
  clay: {
    label: "Clay",
    description:
      "Clay is a sales engagement platform that combines prospecting data from 50+ data providers into one unified workflow. It excels at building highly targeted prospect lists with multi-source data enrichment and automated waterfall enrichment.",
    capabilities: [
      "Access 50+ data providers through a single Clay workspace",
      "Build prospect lists with multi-source data waterfall enrichment",
      "Automated enrichment: find emails, phone numbers, company data in sequence",
      "Waterfall logic: if Provider A fails, try Provider B automatically",
      "Integrate with Salesforce, HubSpot, and your existing CRM",
    ],
    setupSteps: [
      "Go to clay.com/signup and create an account (paid plans only)",
      "In Clay, navigate to your profile icon > API Keys",
      "Generate a new API key and copy it",
      "If self-hosted, enter your custom Clay API base URL in settings",
      'Paste the API key below and click "Save & Activate"',
    ],
    apiDocs: "https://docs.clay.com/en/articles/6824224-clay-s-api",
    signupUrl: "https://www.clay.com/signup",
    freeTier: "No free tier",
    pricing: "$149/mo (Starter) → $349/mo (Pro) → $800/mo (Enterprise)",
    bestFor:
      "Multi-source enrichment, waterfall logic, CRM-integrated prospecting",
    color: "border-orange-200 bg-orange-50/50",
    searchSupported: true,
    enrichSupported: false,
    extraSettingsKey: "baseUrl",
    extraSettingsPlaceholder: '{"baseUrl": "https://api.clay.com"}',
    extraSettingsHint: "Only needed if using a custom Clay API endpoint",
  },
  zoominfo: {
    label: "ZoomInfo",
    description:
      "ZoomInfo is an enterprise-grade B2B intelligence platform with the most comprehensive and accurate contact database. It offers advanced search, intent data, org charts, and buying committee identification for enterprise sales teams.",
    capabilities: [
      "Most comprehensive B2B database with highest data accuracy",
      "Buying committee identification — find all decision makers at once",
      "Intent data: see companies actively researching solutions like yours",
      "Organizational charts and reporting structure mapping",
      "Technographic, firmographic, and demographic data filters",
    ],
    setupSteps: [
      "Contact ZoomInfo sales for a demo at zoominfo.com/request-demo",
      "After onboarding, go to Settings > API Access in ZoomInfo",
      "You will receive a Client ID and Client Secret",
      'Enter the Client ID below as JSON: {"clientId": "your_id"}',
      'Enter the Client Secret as the API Key and click "Save & Activate"',
    ],
    apiDocs: "https://developer.zoominfo.com/",
    signupUrl: "https://www.zoominfo.com/request-demo",
    freeTier: "No free tier — enterprise only",
    pricing: "Custom (typically $15,000+/year)",
    bestFor:
      "Enterprise sales, buying committees, comprehensive data accuracy",
    color: "border-purple-200 bg-purple-50/50",
    searchSupported: true,
    enrichSupported: false,
    extraSettingsKey: "clientId",
    extraSettingsPlaceholder: '{"clientId": "your_client_id"}',
    extraSettingsHint: "ZoomInfo requires a Client ID entered as JSON",
  },
  clearbit: {
    label: "Clearbit",
    description:
      "Clearbit (now part of HubSpot) provides real-time company and person data enrichment via a clean REST API. It excels at enriching existing contacts with company firmographics, social profiles, and employment data.",
    capabilities: [
      "Enrich any email address to get full contact + company profile instantly",
      "Company lookup by domain: revenue, employees, industry, tech stack, funding",
      "Person lookup: employment history, social profiles, seniority level",
      "Reveal anonymous website visitors by company (with JavaScript snippet)",
      "Risk scores and intent data powered by HubSpot ecosystem",
    ],
    setupSteps: [
      "Sign up at hubspot.com/products/clearbit (free tier available)",
      "In your HubSpot account, go to Integrations > Clearbit",
      "Generate an API key from the Clearbit dashboard",
      "Free tier: 50 enrichments/month; upgrade for more",
      'Paste the API key below and click "Save & Activate"',
    ],
    apiDocs: "https://clearbit.com/docs",
    signupUrl: "https://www.hubspot.com/products/clearbit",
    freeTier: "50 enrichments/month (free)",
    pricing: "Free → $99/mo (Growth) → Custom",
    bestFor:
      "Email-to-profile enrichment, company firmographics, web visitor identification",
    color: "border-emerald-200 bg-emerald-50/50",
    searchSupported: true,
    enrichSupported: true,
  },
  hunter: {
    label: "Hunter",
    description:
      "Hunter.io specializes in finding and verifying professional email addresses associated with any domain. It provides domain search to discover all emails at a company, email verification, and email finder to locate specific contacts.",
    capabilities: [
      "Domain Search: find all email addresses at any company domain",
      "Email Finder: find a specific person's email from name + domain",
      "Email Verification: check if an email is deliverable before sending",
      "Company search with employee count, industry, and social links",
      "Bulk email verification for cleaning your existing lists",
    ],
    setupSteps: [
      "Go to hunter.io/users/sign_up and create a free account",
      "Navigate to Dashboard > API on the left sidebar",
      "Copy your API key (shown on the API page)",
      "Free tier: 25 searches/month; upgrade for more volume",
      'Paste the API key below and click "Save & Activate"',
    ],
    apiDocs: "https://hunter.io/api/v2/docs",
    signupUrl: "https://hunter.io/users/sign_up",
    freeTier: "25 searches/month (free)",
    pricing: "Free → $49/mo (Starter) → $149/mo (Growth)",
    bestFor:
      "Email discovery by domain, email verification, finding specific contacts",
    color: "border-amber-200 bg-amber-50/50",
    searchSupported: true,
    enrichSupported: true,
  },
  lusha: {
    label: "Lusha",
    description:
      "Lusha is a B2B contact data platform known for high-accuracy direct dials and email addresses. It integrates directly with LinkedIn, Salesforce, and HubSpot, making it popular for sales teams who prospect on social platforms.",
    capabilities: [
      "Get verified direct dial phone numbers and personal/work emails",
      "Chrome extension for one-click contact extraction from LinkedIn profiles",
      "Company search with advanced filters (industry, size, revenue, tech stack)",
      "Bulk list enrichment — upload a list and get contact data back",
      "CRM integrations: Salesforce, HubSpot, Outreach, Salesloft",
    ],
    setupSteps: [
      "Go to lusha.com and sign up for a free account (5 credits/month free)",
      "Navigate to your profile icon > Settings > API Integration",
      "Request API access or generate your API key from the dashboard",
      'Paste the API key below and click "Save & Activate"',
      "Free tier: 5 credits/month; paid plans start at $36/user/month",
    ],
    apiDocs: "https://www.lusha.com/integrations/api",
    signupUrl: "https://www.lusha.com/",
    freeTier: "5 credits/month (free)",
    pricing: "Free → $36/mo (Base) → $66/mo (Pro) → Custom (Enterprise)",
    bestFor:
      "Verified direct dials, LinkedIn prospecting, phone numbers, CRM-integrated workflows",
    color: "border-rose-200 bg-rose-50/50",
    searchSupported: true,
    enrichSupported: true,
  },
  kaspr: {
    label: "Kaspr",
    description:
      "Kaspr is a LinkedIn prospecting tool that reveals direct phone numbers and email addresses of prospects directly from LinkedIn profiles. It is designed for SDRs and recruiters who work primarily on LinkedIn.",
    capabilities: [
      "Reveal phone numbers and emails directly from any LinkedIn profile",
      "One-click data extraction from LinkedIn Recruiter and Sales Navigator",
      "Export prospects to Salesforce, HubSpot, Pipedrive, or CSV",
      "Multi-channel outreach: email, phone, LinkedIn InMail, connection requests",
      "Team collaboration with shared lists, notes, and activity tracking",
    ],
    setupSteps: [
      "Go to kaspr.io and create an account (free trial available)",
      "Install the Kaspr Chrome extension from the Chrome Web Store",
      "Navigate to app.kaspr.io > Settings > API to generate an API key",
      'Paste the API key below and click "Save & Activate"',
      "Plans start at $39/user/month; free trial includes 50 free credits",
    ],
    apiDocs:
      "https://help.kaspr.io/en/articles/4479539-kaspr-api-documentation",
    signupUrl: "https://www.kaspr.io/",
    freeTier: "50 credits (free trial)",
    pricing: "$39/mo (Starter) → $59/mo (Business) → $79/mo (Advanced)",
    bestFor:
      "LinkedIn-native prospecting, direct dials, SDR workflows, Chrome extension extraction",
    color: "border-cyan-200 bg-cyan-50/50",
    searchSupported: true,
    enrichSupported: true,
  },
  snovio: {
    label: "Snov.io",
    description:
      "Snov.io is an all-in-one sales outreach platform combining email finder, verification, drip campaigns, and CRM. It lets you find email addresses by domain or company name and verify deliverability.",
    capabilities: [
      "Email Finder: find anyone's email by name + company domain",
      "Domain Search: discover all emails at any company with department filtering",
      "Email Verification: check deliverability and catch disposable/temporary emails",
      "Built-in Drip Campaigns: automated multi-step email sequences",
      "Technology Checker: see what tech stack a company uses",
    ],
    setupSteps: [
      "Go to snov.io and create a free account (50 credits/month free)",
      "Navigate to snov.io/api-access or Settings > API Integration",
      "Generate a new API key and copy it",
      'Paste the API key below and click "Save & Activate"',
      "Free tier: 50 credits/month; paid plans start at $39/month",
    ],
    apiDocs: "https://snov.io/api-documentation",
    signupUrl: "https://snov.io/",
    freeTier: "50 credits/month (free)",
    pricing: "Free → $39/mo (Starter) → $99/mo (Pro) → Custom",
    bestFor:
      "All-in-one outreach, email finding + verification + drip campaigns, tech stack detection",
    color: "border-indigo-200 bg-indigo-50/50",
    searchSupported: true,
    enrichSupported: true,
  },
  linkedin: {
    label: "LinkedIn",
    description:
      "LinkedIn Sales Navigator is the premier B2B sales intelligence tool, providing access to 900M+ professionals with advanced search filters, real-time lead recommendations, InMail messaging, and CRM integrations.",
    capabilities: [
      "Advanced search across 900M+ professionals with 30+ filters",
      "Lead Lists: save and organize prospects with real-time updates and alerts",
      "Account Pages: map entire buying committees with org chart visibility",
      "InMail messaging for outreach to 2nd/3rd degree connections",
      "CRM integrations: Salesforce, HubSpot, Microsoft Dynamics",
    ],
    setupSteps: [
      "Sign up for LinkedIn Sales Navigator at salesnavigator.linkedin.com",
      "Navigate to your profile > Settings > Integrations or use LinkedIn Marketing API",
      "Generate an access token via LinkedIn OAuth 2.0 or enter your Sales Navigator Cookie",
      "For API access, apply at developer.linkedin.com to get Client ID + Secret",
      'Paste your access token or API credentials below and click "Save & Activate"',
    ],
    apiDocs:
      "https://learn.microsoft.com/en-us/linkedin/marketing/integrations/marketing-integrations-overview",
    signupUrl: "https://www.linkedin.com/sales/",
    freeTier: "30-day free trial",
    pricing:
      "$99.99/mo (Core) → $179.99/mo (Advanced) → Custom (Enterprise)",
    bestFor:
      "Enterprise sales teams, buying committee mapping, InMail outreach, account-based selling",
    color: "border-sky-200 bg-sky-50/50",
    searchSupported: true,
    enrichSupported: true,
  },
};

/* ── Helpers ────────────────────────────────────────────────────────── */

function normaliseIntegrations(raw: unknown): Integration[] {
  if (Array.isArray(raw)) return raw as Integration[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: Integration[] }).items ?? [];
  return [];
}

function normaliseMailBridge(raw: unknown): MailBridgeConfig[] {
  if (Array.isArray(raw)) return raw as MailBridgeConfig[];
  if (raw && typeof raw === "object" && "items" in raw)
    return (raw as { items: MailBridgeConfig[] }).items ?? [];
  return [];
}

/* ── Page ──────────────────────────────────────────────────────────── */

export function IntegrationsPage() {
  const qc = useQueryClient();

  const [configuring, setConfiguring] = useState<string | null>(null); // platform key
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [extraSettings, setExtraSettings] = useState("");
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, { ok: boolean; detail?: string; latencyMs?: number }>
  >({});
  const [disconnectTarget, setDisconnectTarget] = useState<Integration | null>(
    null,
  );

  const integrationsQ = useQuery<Integration[]>({
    queryKey: ["integrations"],
    queryFn: () =>
      http.get<unknown>("/api/v1/integrations").then(normaliseIntegrations),
  });
  const integrations = integrationsQ.data ?? [];

  const mailbridgeQ = useQuery<MailBridgeConfig[]>({
    queryKey: ["mailbridge", "configs"],
    queryFn: () => mailbridgeApi.list().then(normaliseMailBridge),
  });
  const mbConfigs = mailbridgeQ.data ?? [];

  /* ── Mutations ── */
  const saveMutation = useMutation({
    mutationFn: async ({
      key,
      existing,
    }: {
      key: string;
      existing: Integration | undefined;
    }) => {
      let settings: Record<string, unknown> = existing?.settings ?? {};
      if (extraSettings.trim()) {
        try {
          settings = { ...settings, ...JSON.parse(extraSettings) };
        } catch {
          throw new Error("Invalid JSON in additional settings");
        }
      }
      const guide = PLATFORM_GUIDES[key];
      if (existing) {
        return http.put<Integration>(`/api/v1/integrations/${existing.id}`, {
          name: existing.name || guide.label,
          apiKey: apiKeyInput || undefined,
          isActive: true,
          settings,
        });
      }
      return http.post<Integration>("/api/v1/integrations", {
        platform: key,
        name: guide.label,
        apiKey: apiKeyInput || undefined,
        isActive: true,
        settings,
      });
    },
    onSuccess: (_data, { key }) => {
      toast.success(`${PLATFORM_GUIDES[key].label} configuration saved`);
      setConfiguring(null);
      setApiKeyInput("");
      setExtraSettings("");
      qc.invalidateQueries({ queryKey: ["integrations"] });
    },
    onError: (err) =>
      toast.error(
        err instanceof Error ? err.message : "Failed to save integration",
      ),
  });

  const testMutation = useMutation({
    mutationFn: (integrationId: string) =>
      http.post<TestResponse>("/api/v1/integrations/test", {
        integrationId,
      }),
    onSuccess: (res) => {
      setTestResults((prev) => ({
        ...prev,
        [res.integrationId]: {
          ok: res.ok,
          detail: res.detail,
          latencyMs: res.latencyMs,
        },
      }));
      if (res.ok) {
        toast.success(
          `Connection OK${res.latencyMs ? ` · ${res.latencyMs}ms` : ""}`,
        );
      } else {
        toast.error(`Connection failed${res.detail ? ` · ${res.detail}` : ""}`);
      }
      qc.invalidateQueries({ queryKey: ["integrations"] });
    },
    onError: () => toast.error("Test request failed"),
    onSettled: () => setTestingId(null),
  });

  const disconnectMutation = useMutation({
    mutationFn: (id: string) => http.delete(`/api/v1/integrations/${id}`),
    onSuccess: () => {
      toast.success("Integration disconnected");
      setDisconnectTarget(null);
      qc.invalidateQueries({ queryKey: ["integrations"] });
    },
    onError: () => toast.error("Failed to disconnect"),
  });

  /* ── Handlers ── */
  function startConfigure(key: string) {
    setConfiguring(key);
    setApiKeyInput("");
    setExtraSettings("");
  }

  function cancelConfigure() {
    setConfiguring(null);
    setApiKeyInput("");
    setExtraSettings("");
  }

  function handleSave(key: string) {
    const existing = integrations.find((i) => i.platform === key);
    saveMutation.mutate({ key, existing });
  }

  function handleTest(integ: Integration) {
    setTestingId(integ.id);
    testMutation.mutate(integ.id);
  }

  const connectedCount = integrations.filter(
    (i) => i.isActive && i.apiKey,
  ).length;

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="B2B Prospecting Integrations"
        description="Connect Apollo, Clay, ZoomInfo, Clearbit, Hunter, Lusha, Kaspr, Snov.io, and LinkedIn Sales Navigator for automated prospect discovery and enrichment."
      />

      {/* Connection Status Summary */}
      <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-3">
        {Object.entries(PLATFORM_GUIDES).map(([key, guide]) => {
          const integ = integrations.find((i) => i.platform === key);
          const isActive = Boolean(integ?.isActive && integ?.apiKey);
          return (
            <Card key={key} className={isActive ? guide.color : "opacity-60"}>
              <CardContent className="p-3 text-center">
                <div
                  className={`h-2.5 w-2.5 rounded-full mx-auto mb-1.5 ${
                    isActive ? "bg-emerald-500" : "bg-gray-300"
                  }`}
                />
                <p className="text-xs font-medium">{guide.label}</p>
                <p className="text-[10px] text-muted-foreground">
                  {isActive ? "Connected" : "Not configured"}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {integrationsQ.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : integrationsQ.isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Failed to load integrations.</p>
            <Button onClick={() => integrationsQ.refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {connectedCount} of {Object.keys(PLATFORM_GUIDES).length} platforms
            connected
          </p>

          {/* Platform Integration Cards (INT-1) */}
          <div className="space-y-6">
            {Object.entries(PLATFORM_GUIDES).map(([key, guide]) => {
              const integ = integrations.find((i) => i.platform === key);
              const isActive = Boolean(integ?.isActive && integ?.apiKey);
              const isConfiguring = configuring === key;
              const result = integ ? testResults[integ.id] : undefined;

              return (
                <Card key={key} className={isActive ? guide.color : ""}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <CardTitle className="text-base">
                            {guide.label}
                          </CardTitle>
                          {isActive ? (
                            <Badge variant="success" className="text-xs">
                              Connected
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="text-xs">
                              Not Connected
                            </Badge>
                          )}
                          {guide.searchSupported && (
                            <Badge variant="outline" className="text-xs">
                              Search
                            </Badge>
                          )}
                          {guide.enrichSupported && (
                            <Badge variant="outline" className="text-xs">
                              Enrich
                            </Badge>
                          )}
                        </div>
                        <CardDescription className="text-xs">
                          {guide.description}
                        </CardDescription>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        {isActive && integ ? (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleTest(integ)}
                              disabled={testingId === integ.id}
                            >
                              {testingId === integ.id ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <TestTube2 className="h-3 w-3" />
                              )}
                              Test
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => setDisconnectTarget(integ)}
                            >
                              <Ban className="h-3 w-3" />
                              Disconnect
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => startConfigure(key)}
                          >
                            <Plus className="h-3 w-3" />
                            Connect
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>

                  {isConfiguring && (
                    <CardContent className="border-t pt-4">
                      <div className="space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <Label className="text-xs">API Key</Label>
                            <Input
                              type="password"
                              placeholder="Enter your API key..."
                              value={apiKeyInput}
                              onChange={(e) => setApiKeyInput(e.target.value)}
                            />
                            <p className="text-[10px] text-muted-foreground">
                              Find this at: {guide.apiDocs}
                            </p>
                          </div>
                          {guide.extraSettingsKey && (
                            <div className="space-y-1">
                              <Label className="text-xs">
                                Additional Settings (JSON)
                              </Label>
                              <Textarea
                                placeholder={guide.extraSettingsPlaceholder}
                                value={extraSettings}
                                onChange={(e) =>
                                  setExtraSettings(e.target.value)
                                }
                                rows={2}
                                className="font-mono text-xs"
                              />
                              <p className="text-[10px] text-muted-foreground">
                                {guide.extraSettingsHint}
                              </p>
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => handleSave(key)}
                            disabled={saveMutation.isPending}
                          >
                            {saveMutation.isPending ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Save className="h-3 w-3" />
                            )}
                            Save & Activate
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={cancelConfigure}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  )}

                  {result && (
                    <CardContent className="border-t pt-3">
                      <div
                        className={`text-xs p-2.5 rounded-lg ${
                          result.ok
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-red-50 text-red-700"
                        }`}
                      >
                        {result.detail ??
                          (result.ok ? "Connection OK" : "Connection failed")}
                        {result.latencyMs != null && (
                          <span className="ml-1 opacity-70">
                            ({result.latencyMs}ms)
                          </span>
                        )}
                        {integ?.lastTestedAt && (
                          <span className="block mt-1 opacity-70">
                            Tested: {formatDateTime(integ.lastTestedAt)}
                          </span>
                        )}
                      </div>
                    </CardContent>
                  )}

                  <CardContent className="pt-3">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                      <div>
                        <p className="text-xs font-medium mb-2 flex items-center gap-1">
                          <Zap className="h-3 w-3" /> Capabilities
                        </p>
                        <ul className="text-[11px] text-muted-foreground space-y-1">
                          {guide.capabilities.map((cap, i) => (
                            <li
                              key={i}
                              className="flex items-start gap-1.5"
                            >
                              <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0 mt-0.5" />
                              {cap}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <p className="text-xs font-medium mb-2 flex items-center gap-1">
                          <ClipboardCheck className="h-3 w-3" /> How to
                          Connect
                        </p>
                        <ol className="text-[11px] text-muted-foreground space-y-1.5 list-decimal list-inside">
                          {guide.setupSteps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                      <div>
                        <p className="text-xs font-medium mb-2 flex items-center gap-1">
                          <Info className="h-3 w-3" /> Details
                        </p>
                        <div className="text-[11px] text-muted-foreground space-y-2">
                          <div>
                            <p className="font-medium text-foreground">
                              Best For
                            </p>
                            <p>{guide.bestFor}</p>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">
                              Free Tier
                            </p>
                            <p>{guide.freeTier}</p>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">
                              Pricing
                            </p>
                            <p>{guide.pricing}</p>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">
                              API Docs
                            </p>
                            <a
                              href={guide.apiDocs}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline flex items-center gap-1"
                            >
                              {guide.apiDocs}
                              <ExternalLink className="h-2.5 w-2.5" />
                            </a>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">
                              Sign Up
                            </p>
                            <a
                              href={guide.signupUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline flex items-center gap-1"
                            >
                              {guide.signupUrl}
                              <ExternalLink className="h-2.5 w-2.5" />
                            </a>
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {/* Bulk CSV Import guide (INT-2) */}
      <Card className="border-teal-200 bg-teal-50/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileDown className="h-4 w-4" /> Bulk CSV Import
          </CardTitle>
          <CardDescription className="text-xs">
            Import hundreds or thousands of prospects from a CSV file.
            Supports any column naming convention.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-medium mb-2 flex items-center gap-1">
                <ClipboardCheck className="h-3 w-3" /> How to Use CSV Import
              </p>
              <ol className="text-[11px] text-muted-foreground space-y-1.5 list-decimal list-inside">
                <li>
                  Export contacts from any source (LinkedIn Sales Navigator,
                  event lists, CRM export)
                </li>
                <li>
                  Ensure your CSV has at minimum{" "}
                  <b>first_name</b> and <b>last_name</b> columns
                </li>
                <li>
                  Optional columns: email, title, company, domain, linkedin,
                  seniority, notes
                </li>
                <li>
                  Column names are auto-mapped (e.g. "First Name",
                  "firstname", "first" all work)
                </li>
                <li>
                  Go to the <b>Prospects</b> page and click "Import CSV" to
                  upload your file
                </li>
                <li>
                  Results show created count, skipped duplicates, and any
                  row-level errors
                </li>
              </ol>
            </div>
            <div>
              <p className="text-xs font-medium mb-2">
                Supported Column Mappings
              </p>
              <div className="text-[11px] bg-white rounded-lg p-3 border font-mono">
                <pre className="whitespace-pre-wrap">
{`first_name / firstname / first → First Name
last_name / lastname / last → Last Name
email / email_address / work_email → Email
title / job_title / position / role → Job Title
company / company_name / organization → Company
domain / website / company_domain → Domain
linkedin / linkedin_url → LinkedIn URL
seniority / level → C_Suite / Director / IC
notes → Internal notes`}
                </pre>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* MailBridge summary (INT-3) */}
      <Card className="border-violet-200 bg-violet-50/50">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Send className="h-4 w-4" /> MailBridge — Email Sending Engine
              </CardTitle>
              <CardDescription className="text-xs mt-1">
                MailBridge is your email delivery backbone. It handles
                sending, bounce suppression, open/click tracking, reply
                classification, and follow-up sequences via a REST API.
              </CardDescription>
            </div>
            {mailbridgeQ.isLoading ? (
              <Skeleton className="h-6 w-24" />
            ) : mbConfigs.length > 0 ? (
              <Badge variant="success" className="text-xs shrink-0">
                {mbConfigs.length} Connection{mbConfigs.length > 1 ? "s" : ""}
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-xs shrink-0">
                Not Configured
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div>
              <p className="text-xs font-medium mb-2 flex items-center gap-1">
                <Zap className="h-3 w-3" /> What MailBridge Does
              </p>
              <ul className="text-[11px] text-muted-foreground space-y-1">
                <li className="flex items-start gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0 mt-0.5" />
                  Sends emails via Gmail, Outlook, or custom SMTP
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0 mt-0.5" />
                  Tracks opens, clicks, bounces, and replies in real time
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0 mt-0.5" />
                  AI-powered reply classification
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0 mt-0.5" />
                  Manages follow-up sequence scheduling and throttling
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0 mt-0.5" />
                  Webhook push for real-time event streaming to OUTRENA
                </li>
              </ul>
            </div>
            <div>
              <p className="text-xs font-medium mb-2 flex items-center gap-1">
                <ClipboardCheck className="h-3 w-3" /> How to Connect
              </p>
              <ol className="text-[11px] text-muted-foreground space-y-1.5 list-decimal list-inside">
                <li>Deploy the MailBridge FastAPI server (Docker or bare metal)</li>
                <li>Configure your email provider (Gmail OAuth or Outlook) in MailBridge</li>
                <li>Go to Campaigns and open a campaign's Email Sending tab</li>
                <li>Click "Add Connection" and enter your MailBridge server URL</li>
                <li>Enter the sender email and display name, then Save & Test</li>
              </ol>
            </div>
            <div>
              <p className="text-xs font-medium mb-2 flex items-center gap-1">
                <Info className="h-3 w-3" /> Details
              </p>
              <div className="text-[11px] text-muted-foreground space-y-2">
                <div>
                  <p className="font-medium text-foreground">Architecture</p>
                  <p>
                    MailBridge runs as a separate FastAPI microservice.
                    OUTRENA communicates via REST API.
                  </p>
                </div>
                <div>
                  <p className="font-medium text-foreground">Setup Location</p>
                  <p>Configure per-campaign in the Email Sending tab.</p>
                </div>
              </div>
            </div>
          </div>
          {mbConfigs.length > 0 ? (
            <div className="mt-4 pt-3 border-t">
              <p className="text-xs font-medium mb-2">
                Active MailBridge Connections
              </p>
              <div className="space-y-2">
                {mbConfigs.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center justify-between text-xs bg-white rounded-lg p-2.5 border"
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className={`h-2.5 w-2.5 rounded-full ${
                          c.isActive ? "bg-emerald-500" : "bg-gray-300"
                        }`}
                      />
                      <span className="font-medium">{c.name}</span>
                      <span className="text-muted-foreground">
                        {c.fromEmail}
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        {c.provider}
                      </Badge>
                    </div>
                    <span className="text-muted-foreground">{c.baseUrl}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-4 pt-3 border-t text-center">
              <p className="text-xs text-muted-foreground">
                No MailBridge connections configured yet. Go to a
                campaign's <b>Email Sending</b> tab to set up your first
                connection.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Prospect Search & Import guide (INT-4) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="h-4 w-4" /> Prospect Search & Import
          </CardTitle>
          <CardDescription className="text-xs">
            Once a platform above is connected, use the AI Prospect Sourcing
            panel on the Prospects page to search and import directly.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-muted-foreground bg-muted p-3 rounded-lg">
            <p className="font-medium mb-1">How to Find & Import Prospects</p>
            <ol className="ml-4 list-decimal space-y-0.5">
              <li>Connect at least one search-capable platform above (Apollo, Clay, ZoomInfo, Hunter, Lusha, Kaspr, Snov.io, or LinkedIn)</li>
              <li>Go to the <b>Prospects</b> page</li>
              <li>Open the AI Prospect Sourcing panel and pick a connected platform</li>
              <li>Enter a query (e.g. "CTO SaaS 50-200 employees") and optionally assign an ICP profile</li>
              <li>Review the results table, then click "Import All" to add them to your database</li>
            </ol>
          </div>
          <Separator className="my-3" />
          <div className="text-[11px] text-muted-foreground bg-muted p-3 rounded-lg">
            <p className="font-medium mb-1">Search Tips by Platform</p>
            <ul className="space-y-0.5 ml-4 list-disc">
              <li><b>Apollo:</b> keyword searches like "CTO SaaS 50-200 employees"</li>
              <li><b>Clay:</b> natural language queries describing your ideal prospect</li>
              <li><b>ZoomInfo:</b> title/role keywords or company names</li>
              <li><b>Hunter:</b> a domain name (e.g. "acme.com") to find all emails at that company</li>
              <li><b>Lusha / Kaspr:</b> company name or LinkedIn profile URL for verified phone/email</li>
              <li><b>Snov.io:</b> a domain or company name to find emails with verification</li>
              <li><b>LinkedIn:</b> job title + company, or a LinkedIn profile URL</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Enriching Existing Prospects guide (INT-5) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Wand2 className="h-4 w-4" /> Enriching Existing Prospects
          </CardTitle>
          <CardDescription className="text-xs">
            Once a platform is connected, go to the Prospects page and use
            the enrichment buttons on each prospect row. Apollo, Clearbit,
            and Hunter support per-prospect enrichment.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-muted-foreground bg-muted p-3 rounded-lg">
            <p className="font-medium mb-1">Enrichment Flow</p>
            <ol className="ml-4 list-decimal space-y-0.5">
              <li>Connect at least one enrichment-capable platform above (Apollo, Clearbit, or Hunter)</li>
              <li>Go to the <b>Prospects</b> page</li>
              <li>Click the <b>Enrich</b> button on any prospect row to fill in missing data</li>
              <li>The system calls all connected platforms and merges the results</li>
              <li>Enriched fields (email, title, company, domain, LinkedIn, seniority) are updated automatically</li>
            </ol>
          </div>
        </CardContent>
      </Card>

      {/* Disconnect confirmation */}
      <Dialog
        open={!!disconnectTarget}
        onOpenChange={(o) => !o && setDisconnectTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disconnect integration?</DialogTitle>
            <DialogDescription>
              {disconnectTarget
                ? `The API key for ${
                    PLATFORM_GUIDES[disconnectTarget.platform]?.label ??
                    disconnectTarget.platform
                  } will be removed. Autopilot sourcing and enrichment will skip this platform until reconnected.`
                : "This integration will be disconnected."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDisconnectTarget(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() =>
                disconnectTarget &&
                disconnectMutation.mutate(disconnectTarget.id)
              }
              disabled={disconnectMutation.isPending}
            >
              {disconnectMutation.isPending ? "Disconnecting…" : "Disconnect"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}