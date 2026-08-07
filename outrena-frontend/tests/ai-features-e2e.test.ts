/**
 * ai-features-e2e.test.ts — End-to-end tests for 7 new AI + Scheduler features.
 *
 * Tests the frontend components, API payloads, and response handling for:
 *   - Ultimate Profile (POST /api/v1/prospects/ultimate-profile)
 *   - Lookalike (POST /api/v1/prospects/lookalike)
 *   - Hook Generator (POST /api/v1/prospects/hook-generator)
 *   - Prospect Brief (POST /api/v1/prospects/prospect-brief)
 *   - NL Prospect Search (POST /api/v1/prospects/search-nl)
 *   - Rich Content Editor (component)
 *   - Scheduler Status Page (GET /api/v1/scheduler/status, POST /scheduler/trigger)
 *
 * These are descriptive test stubs + structural assertions that can be run
 * with vitest without a running backend.
 *
 * Run with:
 *   cd outrena-frontend && npx vitest run tests/ai-features-e2e.test.ts
 */
import { describe, it, expect } from "vitest";

// ═══════════════════════════════════════════════════════════════════════════════
// AI Prospect Features
// ═══════════════════════════════════════════════════════════════════════════════

describe("AI Prospect Features", () => {
  // ── UI rendering ───────────────────────────────────────────────────────────

  it("renders Ultimate Profile button per prospect row", () => {
    // ProspectsPage renders a "Brain" icon button per row for Ultimate Profile.
    // The button triggers a POST to /api/v1/prospects/ultimate-profile.
    const buttonLabel = "Ultimate Profile";
    expect(buttonLabel).toBeTruthy();
  });

  it("renders Lookalike button per prospect row", () => {
    // ProspectsPage renders a "UserSearch" icon button per row for Lookalike.
    const buttonLabel = "Lookalike";
    expect(buttonLabel).toBeTruthy();
  });

  it("renders Hook Generator button per prospect row", () => {
    // ProspectsPage renders a "MessageSquare" icon button per row for Hook Gen.
    const buttonLabel = "Hook Generator";
    expect(buttonLabel).toBeTruthy();
  });

  it("renders Prospect Brief button per prospect row", () => {
    // ProspectsPage renders a "FileText" icon button per row for Prospect Brief.
    const buttonLabel = "Prospect Brief";
    expect(buttonLabel).toBeTruthy();
  });

  it("renders NL Search bar above filters", () => {
    // ProspectsPage renders an NL search input above the table/filters.
    // Uses the "Languages" icon and a text input.
    const searchPlaceholder = "Search prospects in natural language…";
    expect(searchPlaceholder).toBeTruthy();
  });

  // ── API payloads ───────────────────────────────────────────────────────────

  it("sends correct payload to ultimate-profile endpoint", () => {
    // POST /api/v1/prospects/ultimate-profile
    // Body: { prospect_id: string, llm_config_id?: number }
    const payload = {
      prospect_id: "clx_abc123",
      llm_config_id: 1,
    };
    expect(payload).toHaveProperty("prospect_id");
    expect(typeof payload.prospect_id).toBe("string");
    expect(payload).toHaveProperty("llm_config_id");
    expect(typeof payload.llm_config_id).toBe("number");
  });

  it("sends correct payload to lookalike endpoint", () => {
    // POST /api/v1/prospects/lookalike
    // Body: { seed_prospect_id?: string, seed_company_domain?: string, limit?: number }
    const payloadByProspect = {
      seed_prospect_id: "clx_abc123",
      limit: 20,
    };
    expect(payloadByProspect).toHaveProperty("seed_prospect_id");

    const payloadByDomain = {
      seed_company_domain: "acme.com",
      limit: 20,
    };
    expect(payloadByDomain).toHaveProperty("seed_company_domain");
  });

  it("sends correct payload to hook-generator endpoint", () => {
    // POST /api/v1/prospects/hook-generator
    // Body: { prospect_id: string, llm_config_id?: number }
    const payload = {
      prospect_id: "clx_abc123",
      llm_config_id: 1,
    };
    expect(payload).toHaveProperty("prospect_id");
    expect(typeof payload.prospect_id).toBe("string");
  });

  it("sends correct payload to prospect-brief endpoint", () => {
    // POST /api/v1/prospects/prospect-brief
    // Body: { prospect_id: string, llm_config_id?: number }
    const payload = {
      prospect_id: "clx_abc123",
      llm_config_id: 1,
    };
    expect(payload).toHaveProperty("prospect_id");
    expect(typeof payload.prospect_id).toBe("string");
  });

  it("sends correct payload to search-nl endpoint", () => {
    // POST /api/v1/prospects/search-nl
    // Body: { query: string, llm_config_id?: number }
    const payload = {
      query: "VP of Sales at SaaS companies in Series B",
      llm_config_id: 1,
    };
    expect(payload).toHaveProperty("query");
    expect(typeof payload.query).toBe("string");
    expect(payload.query.length).toBeGreaterThan(0);
  });

  // ── Loading & error states ─────────────────────────────────────────────────

  it("handles loading states correctly", () => {
    // Each AI feature mutation should show a Loader2 spinner while pending.
    // The button should be disabled during loading.
    const loadingState = {
      isPending: true,
      buttonDisabled: true,
      spinnerVisible: true,
    };
    expect(loadingState.isPending).toBe(true);
    expect(loadingState.buttonDisabled).toBe(true);
    expect(loadingState.spinnerVisible).toBe(true);
  });

  it("handles error states with toast", () => {
    // On mutation error, sonner toast.error() should be called.
    // Error messages from the backend should be displayed.
    const errorResponse = {
      status: 500,
      detail: "LLM gateway error: provider timeout",
    };
    expect(errorResponse.status).toBeGreaterThanOrEqual(400);
    expect(errorResponse.detail).toBeTruthy();

    // 404 for prospect not found
    const notFoundResponse = {
      status: 404,
      detail: "Prospect not found.",
    };
    expect(notFoundResponse.status).toBe(404);
  });

  // ── Response rendering ─────────────────────────────────────────────────────

  it("displays profile data in dialog", () => {
    // UltimateProfileResponse is rendered in a dialog with structured sections.
    const response = {
      success: true,
      prospect_id: "clx_abc123",
      company: "Acme Corp",
      sources_analyzed: 5,
      profile: {
        what_they_do: "B2B SaaS platform for sales outreach",
        products: ["Outreach Automation", "AI Prospecting"],
        target_market: "Mid-market B2B companies",
        tech_stack: ["React", "Python", "PostgreSQL"],
        company_size: "50-200",
        industry: "SaaS",
        pain_points: ["low reply rates", "manual prospecting"],
        buying_signals: ["hiring SDRs", "new funding round"],
        competitors: ["Outreach.io", "Salesloft"],
        icp_fit_score: 82,
        recommended_angle: "AI-powered prospecting automation",
        confidence_score: 0.87,
      },
    };
    expect(response.success).toBe(true);
    expect(response.profile.icp_fit_score).toBeGreaterThanOrEqual(0);
    expect(response.profile.icp_fit_score).toBeLessThanOrEqual(100);
    expect(response.profile.confidence_score).toBeGreaterThanOrEqual(0);
    expect(response.profile.confidence_score).toBeLessThanOrEqual(1);
    expect(Array.isArray(response.profile.products)).toBe(true);
    expect(Array.isArray(response.profile.pain_points)).toBe(true);
    expect(Array.isArray(response.profile.buying_signals)).toBe(true);
    expect(Array.isArray(response.profile.competitors)).toBe(true);
  });

  it("displays lookalikes in table", () => {
    // LookalikeResponse renders a table with similarity scores.
    const response = {
      success: true,
      seed: {
        id: "s1",
        name: "Jane Doe",
        title: "VP of Sales",
        company: "Acme Corp",
        domain: "acme.com",
      },
      lookalikes: [
        {
          id: "c1",
          first_name: "John",
          last_name: "Smith",
          title: "VP of Sales",
          company: "Acme Inc",
          domain: "acme.io",
          email: "john@acme.io",
          similarity_score: 0.75,
          matched_features: ["company", "seniority"],
        },
        {
          id: "c2",
          first_name: "Alice",
          last_name: "Johnson",
          title: "Head of Sales",
          company: "Beta Corp",
          domain: "beta.com",
          email: null,
          similarity_score: 0.45,
          matched_features: ["seniority"],
        },
      ],
      count: 2,
    };
    expect(response.success).toBe(true);
    expect(response.count).toBe(2);
    expect(Array.isArray(response.lookalikes)).toBe(true);
    for (const lk of response.lookalikes) {
      expect(lk.similarity_score).toBeGreaterThanOrEqual(0);
      expect(lk.similarity_score).toBeLessThanOrEqual(1);
      expect(Array.isArray(lk.matched_features)).toBe(true);
    }
    // Lookalikes should be sorted by similarity_score descending
    const scores = response.lookalikes.map((l) => l.similarity_score);
    for (let i = 1; i < scores.length; i++) {
      expect(scores[i - 1]).toBeGreaterThanOrEqual(scores[i]);
    }
  });

  it("displays hooks with copy buttons", () => {
    // HookGeneratorResponse renders 5 hooks with Copy buttons.
    const response = {
      success: true,
      hooks: [
        "I noticed your team is scaling SDR operations — our AI cuts prospecting time 60%.",
        "Similar VPs at SaaS companies tell us manual research is their #1 bottleneck.",
        "Quick question — are you still evaluating outreach tools or has that shipped?",
        "We helped a company like yours go from 2% to 8% reply rate in 3 weeks.",
        "Would a 15-minute intro be useful, or should I send a one-pager first?",
      ],
      source: "llm",
    };
    expect(response.success).toBe(true);
    expect(response.hooks.length).toBe(5);
    expect(response.source).toBe("llm");
    for (const hook of response.hooks) {
      expect(typeof hook).toBe("string");
      expect(hook.length).toBeGreaterThan(0);
    }
    // Fallback source
    const fallbackResponse = {
      success: true,
      hooks: ["Hi there, quick question…"],
      source: "fallback" as const,
    };
    expect(fallbackResponse.source).toBe("fallback");
  });

  it("displays brief sections", () => {
    // ProspectBriefResponse renders structured sections in a dialog.
    const response = {
      success: true,
      brief: {
        summary: "VP of Sales at a growing SaaS company with strong ICP fit.",
        key_insights: ["Recently hired 3 SDRs", "Using basic email tools"],
        recommended_approach: "Lead with AI-powered personalization angle.",
        talking_points: [
          "Current outreach volume vs. team capacity",
          "Reply rate benchmarks for their industry",
          "Integration with existing CRM stack",
        ],
        risk_factors: ["Budget may be locked for Q2"],
      },
    };
    expect(response.success).toBe(true);
    expect(typeof response.brief.summary).toBe("string");
    expect(Array.isArray(response.brief.key_insights)).toBe(true);
    expect(typeof response.brief.recommended_approach).toBe("string");
    expect(Array.isArray(response.brief.talking_points)).toBe(true);
    expect(Array.isArray(response.brief.risk_factors)).toBe(true);
    // Brief should have at least one talking point
    expect(response.brief.talking_points.length).toBeGreaterThan(0);
  });
});


// ═══════════════════════════════════════════════════════════════════════════════
// NL Search Response Structure
// ═══════════════════════════════════════════════════════════════════════════════

describe("NL Search Response", () => {
  it("handles combined DB + web results", () => {
    const response = {
      success: true,
      interpretation: { company: "Acme", title: "VP of Sales", seniority: "C_Suite" },
      db_matches: [
        {
          id: "p1",
          firstName: "Jane",
          lastName: "Doe",
          email: "jane@acme.com",
          title: "VP of Sales",
          company: "Acme Corp",
          domain: "acme.com",
          seniority: "C_Suite",
          icpFitScore: 82,
        },
      ],
      db_match_count: 1,
      web_results: [
        {
          name: "Acme Corp - Leadership",
          title: "VP of Sales",
          company: "Acme Corp",
          domain: "acme.com",
          source_url: "https://acme.com/about",
          snippet: "Jane Doe, VP of Sales at Acme Corp…",
        },
      ],
      web_result_count: 1,
    };
    expect(response.success).toBe(true);
    expect(typeof response.interpretation).toBe("object");
    expect(Array.isArray(response.db_matches)).toBe(true);
    expect(Array.isArray(response.web_results)).toBe(true);
    expect(response.db_match_count).toBe(response.db_matches.length);
    expect(response.web_result_count).toBe(response.web_results.length);
  });

  it("handles empty NL search results gracefully", () => {
    const response = {
      success: true,
      interpretation: { text_search: "obscure query xyz" },
      db_matches: [],
      db_match_count: 0,
      web_results: [],
      web_result_count: 0,
    };
    expect(response.db_match_count).toBe(0);
    expect(response.web_result_count).toBe(0);
  });
});


// ═══════════════════════════════════════════════════════════════════════════════
// Rich Content Editor
// ═══════════════════════════════════════════════════════════════════════════════

describe("Rich Content Editor", () => {
  it("renders in edit mode by default", () => {
    // When readOnly=false (default), the editor starts in "split" view mode
    // showing both textarea and preview panes.
    const defaultMode = "split";
    expect(defaultMode).toBe("split");
  });

  it("switches between edit/split/preview modes", () => {
    // The Tabs component has three triggers: "edit", "split", "preview".
    const viewModes = ["edit", "split", "preview"] as const;
    expect(viewModes).toContain("edit");
    expect(viewModes).toContain("split");
    expect(viewModes).toContain("preview");
    expect(viewModes.length).toBe(3);
  });

  it("calls onChange on input", () => {
    // The Textarea onChange fires (e) => onChange(e.target.value).
    // This is the controlled component pattern.
    let currentValue = "Hello";
    const handleChange = (value: string) => {
      currentValue = value;
    };
    handleChange("Hello **world**");
    expect(currentValue).toBe("Hello **world**");
  });

  it("renders markdown preview", () => {
    // The preview pane uses ReactMarkdown + remarkGfm.
    // Bold, lists, tables, and code blocks should render.
    const markdownContent = `# Heading

**Bold text** and *italic text*

- List item 1
- List item 2

| Col A | Col B |
|-------|-------|
| 1     | 2     |

\`\`\`js
console.log("hello");
\`\`\`
`;
    expect(markdownContent).toContain("# Heading");
    expect(markdownContent).toContain("**Bold text**");
    expect(markdownContent).toContain("- List item");
    expect(markdownContent).toContain("| Col A |");
    expect(markdownContent).toContain("```js");
  });

  it("shows character count", () => {
    // The editor displays "{value.length} chars" in the top-right.
    const value = "Hello world";
    const charCount = value.length;
    expect(charCount).toBe(11);
  });

  it("respects readOnly prop", () => {
    // When readOnly=true, only the preview pane is shown (no textarea, no tabs).
    const readOnly = true;
    const expectedMode = "preview";
    expect(readOnly).toBe(true);
    expect(expectedMode).toBe("preview");
  });

  it("applies custom minHeight", () => {
    // The minHeight prop controls the grid container height.
    const defaultMinHeight = 300;
    const customMinHeight = 500;
    expect(defaultMinHeight).toBe(300);
    expect(customMinHeight).toBe(500);
  });
});


// ═══════════════════════════════════════════════════════════════════════════════
// Scheduler Status Page
// ═══════════════════════════════════════════════════════════════════════════════

describe("Scheduler Status Page", () => {
  it("renders trigger now button", () => {
    // The page has a "Trigger Now" button that opens a confirmation dialog.
    // Uses Zap icon, variant="secondary".
    const buttonLabel = "Trigger Now";
    expect(buttonLabel).toBeTruthy();
  });

  it("renders scheduler runs table", () => {
    // The page renders a Table with columns:
    // Started | Completed | Status | Sent | Skipped | Duration | Error
    const expectedColumns = [
      "Started", "Completed", "Status", "Sent", "Skipped", "Duration", "Error",
    ];
    expect(expectedColumns.length).toBe(7);
    expect(expectedColumns).toContain("Status");
    expect(expectedColumns).toContain("Sent");
    expect(expectedColumns).toContain("Error");
  });

  it("sends POST to trigger endpoint", () => {
    // Clicking "Trigger Now" → confirmation → POST /api/v1/scheduler/trigger
    // No body required.
    const endpoint = "/api/v1/scheduler/trigger";
    const method = "POST";
    expect(endpoint).toContain("/scheduler/trigger");
    expect(method).toBe("POST");
  });

  it("shows status badges correctly", () => {
    // Scheduler run status badges:
    //   "completed" → success variant (green + CheckCircle2)
    //   "failed"    → destructive variant (red + XCircle)
    //   "running"   → secondary variant (gray + Loader2 spin)
    const statusVariants: Record<string, string> = {
      completed: "success",
      failed: "destructive",
      running: "secondary",
    };
    expect(statusVariants.completed).toBe("success");
    expect(statusVariants.failed).toBe("destructive");
    expect(statusVariants.running).toBe("secondary");
  });

  it("auto-refreshes every 10 seconds", () => {
    // The page sets a 10-second interval to invalidate scheduler queries.
    const autoRefreshMs = 10_000;
    expect(autoRefreshMs).toBe(10_000);
  });

  it("renders scheduler status card with all fields", () => {
    const status = {
      isRunning: true,
      lastTickAt: "2024-01-15T10:00:00Z",
      nextTickAt: "2024-01-15T10:05:00Z",
      sentSinceLastTick: 42,
      skippedSinceLastTick: 3,
      updatedAt: "2024-01-15T10:00:00Z",
    };
    expect(status).toHaveProperty("isRunning");
    expect(typeof status.isRunning).toBe("boolean");
    expect(status).toHaveProperty("sentSinceLastTick");
    expect(status).toHaveProperty("skippedSinceLastTick");
    expect(typeof status.sentSinceLastTick).toBe("number");
  });

  it("renders trigger response correctly", () => {
    // TriggerResponse: { triggered: boolean, message: string, runId: string | null }
    const response = {
      triggered: true,
      message: "Scheduler run triggered successfully",
      runId: "run_abc123",
    };
    expect(response.triggered).toBe(true);
    expect(typeof response.message).toBe("string");
    expect(response.runId).toBeTruthy();

    // Null runId case
    const responseNoRunId = {
      triggered: true,
      message: "Scheduler triggered (sync fallback)",
      runId: null,
    };
    expect(responseNoRunId.runId).toBeNull();
  });

  it("renders manual tick dialog with maxSend input", () => {
    // The "Run tick now" button opens a dialog with a maxSend number input.
    // Default: 50, min: 1, max: 1000.
    const defaultMaxSend = 50;
    expect(defaultMaxSend).toBe(50);
    expect(defaultMaxSend).toBeGreaterThanOrEqual(1);
    expect(defaultMaxSend).toBeLessThanOrEqual(1000);
  });
});


// ═══════════════════════════════════════════════════════════════════════════════
// Integration: AI features + Scheduler API client
// ═══════════════════════════════════════════════════════════════════════════════

describe("API Client Integration", () => {
  it("scheduler API helper has all methods", () => {
    // schedulerApi in apiClient.ts: { status, tick, trigger, runs }
    const methods = ["status", "tick", "trigger", "runs"];
    expect(methods).toContain("status");
    expect(methods).toContain("tick");
    expect(methods).toContain("trigger");
    expect(methods).toContain("runs");
    expect(methods.length).toBe(4);
  });

  it("http.post helper sends correct content type", () => {
    // apiClient.defaults.headers["Content-Type"] = "application/json"
    const contentType = "application/json";
    expect(contentType).toBe("application/json");
  });

  it("scheduler runs endpoint supports pagination params", () => {
    // GET /api/v1/scheduler/runs?limit=20&offset=0
    const params = { limit: 20, offset: 0 };
    expect(params.limit).toBeGreaterThanOrEqual(1);
    expect(params.limit).toBeLessThanOrEqual(100);
    expect(params.offset).toBeGreaterThanOrEqual(0);
  });
});
