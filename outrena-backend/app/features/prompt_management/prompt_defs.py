"""
prompt_defs.py — 47 seeded LLM prompt templates (per migration doc §5.1 + §10 Phase 2).

Transcribed from the TS ``src/lib/prompts.ts`` constants. Each PromptDef
becomes a row in the tenant's ``PromptTemplate`` table at provisioning
(see ``app.services.prompt_service.PromptService.seed_prompts``).

Categories (47 total):
  - email (15)             — first_touch, new_evidence, different_pain, ...
  - icp + prospecting (10) — suggest, auto_discover, brief, lookalike, ...
  - analytics + content (10) — diagnose, campaign_results, idea_generate, ...
  - sequencing + optimization (8) — cadence_plan, touch_angle, rule_suggest, ...
  - misc (4)               — domain.enrich, domain.dns_suggest, ...

Each ``default_body`` is a multi-line Jinja2-style string with ``{{var}}``
placeholders. Bodies are 100-300 chars. Admins can override per-tenant via
the prompt_management router (PUT /api/v1/prompts/{key}); the
``defaultValue`` column preserves the seeded body so the admin UI can show
diffs and offer a Reset action.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class PromptDef(BaseModel):
    """Static definition of one seeded prompt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    category: str
    description: str
    default_body: str = Field(min_length=10)
    name: str | None = None  # defaults to title-cased key segment
    variables: list[str] | None = None  # auto-extracted from default_body if None
    sortOrder: int | None = None  # auto-assigned by index if None

    def resolved_name(self) -> str:
        if self.name:
            return self.name
        # email.first_touch -> "Email First Touch"
        tail = self.key.split(".")[-1]
        return " ".join(p.capitalize() for p in tail.split("_"))

    def resolved_variables(self) -> list[str]:
        if self.variables is not None:
            return list(self.variables)
        seen: list[str] = []
        for m in _VAR_RE.findall(self.default_body):
            if m not in seen:
                seen.append(m)
        return seen


# ── Email generation (15) ───────────────────────────────────────────────────

_EMAIL_PROMPTS: list[PromptDef] = [
    PromptDef(
        key="email.first_touch",
        category="email",
        description="Cold-outreach first-touch email body generator.",
        default_body=(
            "You are an SDR writing the first cold email to {{prospect_name}} "
            "({{prospect_title}} at {{company}}).\n"
            "ICP context: {{icp_persona}}\n"
            "Sender: {{sender_name}} ({{sender_role}} at {{sender_company}})\n"
            "Value prop: {{value_prop}}\n"
            "Proof metric: {{proof_metric}}\n"
            "Constraints: max {{max_length}} chars, no buzzwords, one CTA, "
            "reference one specific signal from {{signal}}.\n"
            "Return JSON: {subject, body, qaScore, personalisationConfidence}."
        ),
    ),
    PromptDef(
        key="email.new_evidence",
        category="email",
        description="Follow-up email citing new evidence (funding, hire, launch).",
        default_body=(
            "Write touch #{{touch_number}} to {{prospect_name}} at {{company}}.\n"
            "New evidence: {{evidence}}\n"
            "Original angle: {{previous_angle}}\n"
            "ICP pain point: {{pain_point}}\n"
            "Max {{max_length}} chars. Cite the evidence with a one-line interpretation. "
            "End with a soft question, not a meeting ask.\n"
            "Return JSON: {subject, body, qaScore}."
        ),
    ),
    PromptDef(
        key="email.different_pain",
        category="email",
        description="Follow-up pivoting to a different ICP pain point.",
        default_body=(
            "Touch #{{touch_number}} to {{prospect_name}} ({{prospect_title}}).\n"
            "Previous pain: {{previous_pain}}\n"
            "New pain angle: {{new_pain}}\n"
            "Reference recent activity: {{recent_activity}}\n"
            "Max {{max_length}} chars. Acknowledge prior context briefly, then pivot. "
            "No apologies, no 'just checking in'.\n"
            "Return JSON: {subject, body, qaScore}."
        ),
    ),
    PromptDef(
        key="email.industry_insight",
        category="email",
        description="Follow-up sharing a non-obvious industry insight.",
        default_body=(
            "Touch #{{touch_number}} to {{prospect_name}} at {{company}} ({{industry}}).\n"
            "Insight: {{insight}}\n"
            "Implication for {{company}}: {{implication}}\n"
            "Max {{max_length}} chars. Lead with the insight, link to one peer at "
            "{{peer_company}} who fixed this. Soft CTA.\n"
            "Return JSON: {subject, body, qaScore}."
        ),
    ),
    PromptDef(
        key="email.direct_question",
        category="email",
        description="Touch that opens with a direct, specific question.",
        default_body=(
            "Touch #{{touch_number}} to {{prospect_name}} ({{prospect_title}}).\n"
            "Direct question to lead with: {{question}}\n"
            "Why this question: {{rationale}}\n"
            "ICP context: {{icp_persona}}\n"
            "Max {{max_length}} chars. Open with the question — no preamble. "
            "Two sentences max after the question.\n"
            "Return JSON: {subject, body, qaScore}."
        ),
    ),
    PromptDef(
        key="email.breakup",
        category="email",
        description="Final-touch breakup email (graceful exit).",
        default_body=(
            "Write the breakup email (touch #{{touch_number}}) to {{prospect_name}}.\n"
            "Sender: {{sender_name}}\n"
            "Tone: warm, no guilt, leave the door open.\n"
            "Max {{max_length}} chars. Acknowledge they're busy, restate the value "
            "prop in one line ({{value_prop}}), offer to reconnect on their timeline.\n"
            "Return JSON: {subject, body, qaScore}."
        ),
    ),
    PromptDef(
        key="email.subject_line",
        category="email",
        description="Generate 5 subject-line variants for an A/B test.",
        default_body=(
            "Generate 5 cold-email subject lines for a touch to {{prospect_name}} "
            "({{prospect_title}} at {{company}}).\n"
            "Email body preview: {{body_preview}}\n"
            "Constraints: max 50 chars each, lowercase, no exclamation marks, "
            "no questions, no spam trigger words.\n"
            "Return JSON: {subjects: [string x 5], rationale: string}."
        ),
    ),
    PromptDef(
        key="email.qa_check",
        category="email",
        description="QA-score an email body for spamminess + personalization.",
        default_body=(
            "QA-score this cold email.\n"
            "Subject: {{subject}}\n"
            "Body: {{body}}\n"
            "Prospect: {{prospect_name}} ({{prospect_title}} at {{company}})\n"
            "Return JSON: {qaScore (0-100), qaDetails: {spamminess, personalization, "
            "clarity}, flagForManualReview: bool, reasons: [string]}."
        ),
    ),
    PromptDef(
        key="email.anti_pattern",
        category="email",
        description="Detect spammy / salesy / generic patterns in an email.",
        default_body=(
            "Scan the email body for anti-patterns (spammy phrasing, generic openers, "
            "missing personalization, multiple CTAs, buzzwords).\n"
            "Subject: {{subject}}\n"
            "Body: {{body}}\n"
            "Return JSON: {findings: [{pattern, severity, snippet, suggestion}], "
            "score (0-100), passed: bool}."
        ),
    ),
    PromptDef(
        key="email.compliance_check",
        category="email",
        description="CAN-SPAM + GDPR compliance check on an email body.",
        default_body=(
            "Check this email for CAN-SPAM + GDPR compliance.\n"
            "Body: {{body}}\n"
            "Sender: {{sender_name}} at {{sender_company}}\n"
            "Return JSON: {findings: [{rule, severity, snippet, fix}], "
            "compliant: bool, missingElements: [string]}."
        ),
    ),
    PromptDef(
        key="email.reply_categorize",
        category="email",
        description="Categorize an inbound reply (positive/negative/OOO/etc).",
        default_body=(
            "Categorize this inbound reply.\n"
            "Reply body: {{reply_body}}\n"
            "Sender: {{prospect_name}} ({{prospect_title}} at {{company}})\n"
            "Original send: {{original_subject}}\n"
            "Return JSON: {category: 'positive'|'negative'|'question'|'ooo'|"
            "'unsubscribe'|'neutral', confidence (0-1), suggested_action: string, "
            "key_quote: string}."
        ),
    ),
    PromptDef(
        key="email.auto_reply",
        category="email",
        description="Draft an auto-reply for a categorized inbound reply.",
        default_body=(
            "Draft an auto-reply (≤120 chars) to this inbound reply.\n"
            "Reply category: {{category}}\n"
            "Reply body: {{reply_body}}\n"
            "Prospect: {{prospect_name}} at {{company}}\n"
            "Sender context: {{sender_role}}\n"
            "If positive → propose a time. If question → answer in 2 sentences. "
            "If OOO → acknowledge and ask for the reschedule.\n"
            "Return JSON: {body, confidence (0-1), autoPilotEligible: bool}."
        ),
    ),
    PromptDef(
        key="email.personalization",
        category="email",
        description="Extract 3 personalization hooks for a prospect.",
        default_body=(
            "Extract 3 personalization hooks for {{prospect_name}} "
            "({{prospect_title}} at {{company}}, domain {{domain}}).\n"
            "Known signals: {{signals}}\n"
            "Recent activity: {{recent_activity}}\n"
            "Return JSON: {hooks: [{type: 'company'|'role'|'industry'|'event', "
            "snippet: string, source: string, confidence: 0-1}]}."
        ),
    ),
    PromptDef(
        key="email.framework_recommend",
        category="email",
        description="Recommend a messaging framework (PAS, AIDA, etc) for an email.",
        default_body=(
            "Recommend a messaging framework for a touch to {{prospect_name}} "
            "({{prospect_title}} at {{company}}).\n"
            "Angle: {{angle}}\n"
            "ICP pain points: {{pain_points}}\n"
            "Goal: {{goal}}\n"
            "Return JSON: {framework: 'PAS'|'AIDA'|'BAB'|'4U'|'S+C', "
            "rationale: string, outline: [string]}."
        ),
    ),
    PromptDef(
        key="email.gtm_thesis",
        category="email",
        description="Generate a GTM thesis paragraph for a campaign.",
        default_body=(
            "Draft a 2-paragraph GTM thesis for a campaign targeting {{icp_persona}} "
            "at {{company_type}} companies.\n"
            "Offer: {{offer}}\n"
            "Proof metric: {{proof_metric}}\n"
            "Differentiator vs {{competitor}}: {{differentiator}}\n"
            "Return JSON: {thesis: string, keyPillars: [string x 3], "
            "riskyAssumptions: [string]}."
        ),
    ),
]


# ── ICP + prospecting (10) ──────────────────────────────────────────────────

_ICP_PROSPECTING_PROMPTS: list[PromptDef] = [
    PromptDef(
        key="icp.suggest",
        category="icp",
        description="Suggest an ICP refinement given existing customer traits.",
        default_body=(
            "Suggest an ICP refinement based on these inputs.\n"
            "Existing customers: {{customers}}\n"
            "Top objections: {{objections}}\n"
            "Pain points: {{pain_points}}\n"
            "Return JSON: {persona, companyType, industries: [string], "
            "seniorities: [string], suggestedValueProps: [string], "
            "confidence: 0-1, rationale: string}."
        ),
    ),
    PromptDef(
        key="icp.auto_discover",
        category="icp",
        description="Auto-discover an ICP from a seed prospect list.",
        default_body=(
            "Auto-discover an ICP from this seed prospect list.\n"
            "Prospects: {{prospects}}\n"
            "Winners (closed-won): {{winners}}\n"
            "Return JSON: {persona, companyType, topPainPoints: [string], "
            "topObjections: [string], valueProps: [string], senderRole: string, "
            "senderOffer: string, proofMetric: string}."
        ),
    ),
    PromptDef(
        key="prospect.brief",
        category="prospecting",
        description="Generate a one-page prospect brief before outreach.",
        default_body=(
            "Generate a brief for {{prospect_name}} ({{prospect_title}} at {{company}}).\n"
            "Domain: {{domain}}\n"
            "LinkedIn: {{linkedin_url}}\n"
            "Recent news: {{recent_news}}\n"
            "Return JSON: {summary, roleContext, companyContext, "
            "suggestedAngle, topQuestion, risk: string}."
        ),
    ),
    PromptDef(
        key="prospect.lookalike",
        category="prospecting",
        description="Find lookalike prospects based on a seed prospect.",
        default_body=(
            "Find lookalike prospects similar to this seed prospect.\n"
            "Seed: {{seed_name}} ({{seed_title}} at {{seed_company}}, {{seed_domain}})\n"
            "ICP: {{icp_persona}}\n"
            "Return JSON: {lookalikes: [{name, title, company, domain, "
            "fitScore: 0-100, reason: string}]}."
        ),
    ),
    PromptDef(
        key="prospect.ultimate_profile",
        category="prospecting",
        description="Build the 'ultimate profile' (deep-enriched prospect summary).",
        default_body=(
            "Build the ultimate profile for {{prospect_name}}.\n"
            "Known: title={{prospect_title}}, company={{company}}, "
            "domain={{domain}}, linkedin={{linkedin_url}}\n"
            "Recent signals: {{signals}}\n"
            "Return JSON: {bio, careerTrajectory: [string], techStack: [string], "
            "reportedMetrics: {string: string}, reportingLine: string, "
            "icpFitReason: string, recommendedAngle: string}."
        ),
    ),
    PromptDef(
        key="prospect.source",
        category="prospecting",
        description="Source new prospects matching an ICP via a search query plan.",
        default_body=(
            "Plan a prospecting search for ICP: {{icp_persona}} at "
            "{{company_type}} companies in {{geography}}.\n"
            "Available sources: {{sources}}\n"
            "Return JSON: {queries: [{source, query, expectedCount, filters}], "
            "dedupStrategy: string, exclusionRules: [string]}."
        ),
    ),
    PromptDef(
        key="prospect.nl_search",
        category="prospecting",
        description="Translate a natural-language search into a structured query.",
        default_body=(
            "Translate this NL prospect search into a structured query.\n"
            "User query: {{user_query}}\n"
            "Available fields: {{available_fields}}\n"
            "Return JSON: {filters: [{field, op, value}], sortBy: string, "
            "limit: int, explanation: string, disambiguationQuestions: [string]}."
        ),
    ),
    PromptDef(
        key="prospect.enrich",
        category="prospecting",
        description="Enrich a prospect record with missing fields.",
        default_body=(
            "Enrich this prospect.\n"
            "Known: name={{prospect_name}}, company={{company}}, domain={{domain}}\n"
            "Missing fields: {{missing_fields}}\n"
            "Return JSON: {title, seniority, linkedinUrl, email, emailConfidence: 0-1, "
            "isCatchAll: bool, firmographic: {industry, employeeCount, revenueRange, "
            "location}, signals: [string]}."
        ),
    ),
    PromptDef(
        key="prospect.score",
        category="prospecting",
        description="LLM-assisted prospect scoring (complements pure-Python scorer).",
        default_body=(
            "Score this prospect's ICP fit + intent.\n"
            "Prospect: {{prospect_name}} ({{prospect_title}} at {{company}})\n"
            "ICP: {{icp_persona}}\n"
            "Signals: {{signals}}\n"
            "Return JSON: {icpFitScore: 0-100, intentScore: 0-10, "
            "urgencyTier: 'P0'|'P1'|'P2', topReasons: [string], "
            "topRisks: [string], recommendedAngle: string}."
        ),
    ),
    PromptDef(
        key="prospect.signals",
        category="prospecting",
        description="Extract intent + hiring + funding signals for a prospect.",
        default_body=(
            "Extract intent signals for {{company}} (domain: {{domain}}).\n"
            "Recent news: {{recent_news}}\n"
            "Job posts: {{job_posts}}\n"
            "Return JSON: {signals: [{type: 'funding'|'hiring'|'product_launch'|"
            "'leadership_change'|'expansion', strength: 0-10, snippet, source, "
            "detectedAt}], intentStrength: 0-10, intentSource: string}."
        ),
    ),
]


# ── Analytics + content (10) ────────────────────────────────────────────────

_ANALYTICS_CONTENT_PROMPTS: list[PromptDef] = [
    PromptDef(
        key="analytics.diagnose",
        category="analytics",
        description="Diagnose why a campaign under- or over-performed.",
        default_body=(
            "Diagnose this campaign's performance.\n"
            "Campaign: {{campaign_name}}\n"
            "Metrics: sent={{sent}}, open_rate={{open_rate}}, "
            "reply_rate={{reply_rate}}, meetings={{meetings}}\n"
            "Return JSON: {health: 'green'|'yellow'|'red', topIssues: [string], "
            "topWins: [string], recommendedActions: [string], "
            "benchmarkDelta: {string: number}}."
        ),
    ),
    PromptDef(
        key="analytics.campaign_results",
        category="analytics",
        description="Summarize campaign results for a stakeholder report.",
        default_body=(
            "Summarize this campaign's results.\n"
            "Campaign: {{campaign_name}} ({{duration_days}} days)\n"
            "Metrics: {{metrics}}\n"
            "Audience: {{audience}}\n"
            "Return JSON: {headline, summary, topPerformingTouch: int, "
            "worstPerformingTouch: int, learnings: [string], nextSteps: [string]}."
        ),
    ),
    PromptDef(
        key="content.idea_generate",
        category="content",
        description="Generate content ideas for a persona + industry.",
        default_body=(
            "Generate 5 content ideas for {{persona}} in the {{industry}} industry.\n"
            "Themes to avoid: {{avoid_themes}}\n"
            "Return JSON: {ideas: [{title, format: 'blog'|'linkedin'|'thread'|"
            "'video', hook, outline: [string], targetKeyword: string}]}."
        ),
    ),
    PromptDef(
        key="content.linkedin_post",
        category="content",
        description="Draft a LinkedIn post for the sender's voice.",
        default_body=(
            "Draft a LinkedIn post in {{sender_name}}'s voice ({{sender_role}}).\n"
            "Topic: {{topic}}\n"
            "Proof metric to cite: {{proof_metric}}\n"
            "Max 1300 chars. Hook in first line. One emoji max. End with a question.\n"
            "Return JSON: {body, hookLine, suggestedHashtags: [string]}."
        ),
    ),
    PromptDef(
        key="content.weekly_digest",
        category="content",
        description="Generate the weekly digest body for a tenant.",
        default_body=(
            "Generate this week's digest for tenant {{tenant_name}}.\n"
            "Wins: {{wins}}\n"
            "Risks: {{risks}}\n"
            "Next-week focus: {{next_week_focus}}\n"
            "Return JSON: {headline, body, topPerformer: string, "
            "actionItems: [string], kpis: {string: number}}."
        ),
    ),
    PromptDef(
        key="meeting.prep",
        category="meeting",
        description="Generate a meeting-prep brief for an upcoming prospect call.",
        default_body=(
            "Generate a meeting-prep brief.\n"
            "Prospect: {{prospect_name}} ({{prospect_title}} at {{company}})\n"
            "Call type: {{call_type}}\n"
            "Scheduled at: {{scheduled_at}}\n"
            "Return JSON: {agenda: [string], discoveryQuestions: [string], "
            "objectionHandlers: [{objection, response}], nextStepsIfYes: [string], "
            "nextStepsIfNo: [string]}."
        ),
    ),
    PromptDef(
        key="deal.suggest",
        category="deal",
        description="Suggest the next best action on a stalled deal.",
        default_body=(
            "Suggest next actions for this deal.\n"
            "Deal: {{deal_name}} (stage: {{stage}}, value: {{value}})\n"
            "Last activity: {{last_activity}}\n"
            "Days in stage: {{days_in_stage}}\n"
            "Return JSON: {nextBestAction, confidence: 0-1, reasoning, "
            "alternativeActions: [string], riskFlags: [string]}."
        ),
    ),
    PromptDef(
        key="deal.health",
        category="deal",
        description="Compute deal-health score from activity signals.",
        default_body=(
            "Score this deal's health.\n"
            "Deal: {{deal_name}} (stage: {{stage}})\n"
            "Activity log: {{activity_log}}\n"
            "Stakeholders engaged: {{stakeholders}}\n"
            "Return JSON: {healthScore: 0-100, healthLabel: 'green'|'yellow'|'red', "
            "signals: [{signal, weight: number}], reasoning: string}."
        ),
    ),
    PromptDef(
        key="deal.next_step",
        category="deal",
        description="Draft the next-step message to move the deal forward.",
        default_body=(
            "Draft a next-step message to {{prospect_name}}.\n"
            "Deal stage: {{stage}}\n"
            "Last touch: {{last_touch}}\n"
            "Goal: {{goal}}\n"
            "Return JSON: {channel: 'email'|'linkedin'|'call', body, "
            "ctas: [string], expectedOutcome: string}."
        ),
    ),
    PromptDef(
        key="weekly.digest_summary",
        category="weekly",
        description="Roll-up summary of this week's outreach across all campaigns.",
        default_body=(
            "Summarize this week's outreach for tenant {{tenant_name}}.\n"
            "Campaigns active: {{active_campaigns}}\n"
            "Aggregate metrics: {{aggregate_metrics}}\n"
            "Top reply themes: {{reply_themes}}\n"
            "Return JSON: {headline, body, highlights: [string], "
            "concerns: [string], suggestedFocus: string}."
        ),
    ),
]


# ── Sequencing + optimization (8) ───────────────────────────────────────────

_SEQUENCE_OPTIMIZATION_PROMPTS: list[PromptDef] = [
    PromptDef(
        key="sequence.cadence_plan",
        category="sequence",
        description="Design a multi-touch cadence plan for an ICP.",
        default_body=(
            "Design a {{touch_count}}-touch cadence for ICP {{icp_persona}}.\n"
            "Channel mix: {{channels}}\n"
            "Goal: {{goal}}\n"
            "Return JSON: {touches: [{day, channel, angle, "
            "framework, objective: string}], rationale: string, "
            "expectedReplyRate: 0-1}."
        ),
    ),
    PromptDef(
        key="sequence.touch_angle",
        category="sequence",
        description="Pick the angle for a specific touch in a cadence.",
        default_body=(
            "Pick the angle for touch #{{touch_number}} of a {{touch_count}}-touch "
            "cadence to {{prospect_name}}.\n"
            "Previous angles: {{previous_angles}}\n"
            "ICP pains: {{pain_points}}\n"
            "Available signals: {{signals}}\n"
            "Return JSON: {angle: 'FirstTouch'|'NewEvidence'|'DifferentPain'|"
            "'IndustryInsight'|'DirectQuestion'|'Breakup', rationale: string, "
            "suggestedHook: string}."
        ),
    ),
    PromptDef(
        key="optimization.rule_suggest",
        category="optimization",
        description="Suggest an optimization rule given campaign patterns.",
        default_body=(
            "Suggest an optimization rule based on these patterns.\n"
            "Patterns: {{patterns}}\n"
            "Recent metrics: {{metrics}}\n"
            "Return JSON: {rules: [{name, trigger: {field, op, value}, action: "
            "{type, params}, priority: 0-10, rationale: string}]}."
        ),
    ),
    PromptDef(
        key="optimization.pause_recommendation",
        category="optimization",
        description="Recommend whether to pause a campaign.",
        default_body=(
            "Recommend whether to pause campaign {{campaign_name}}.\n"
            "Metrics: {{metrics}}\n"
            "Days running: {{days_running}}\n"
            "Recent trend: {{trend}}\n"
            "Return JSON: {recommendation: 'pause'|'continue'|'adjust', "
            "confidence: 0-1, reasoning: string, "
            "adjustmentsIfContinue: [string]}."
        ),
    ),
    PromptDef(
        key="optimization.scale_recommendation",
        category="optimization",
        description="Recommend whether to scale a winning campaign.",
        default_body=(
            "Recommend whether to scale campaign {{campaign_name}}.\n"
            "Metrics: {{metrics}}\n"
            "Capacity: {{capacity}}\n"
            "Budget headroom: {{budget_headroom}}\n"
            "Return JSON: {recommendation: 'scale'|'hold'|'wind_down', "
            "scaleFactor: 0.5-3.0, confidence: 0-1, reasoning: string, "
            "risks: [string]}."
        ),
    ),
    PromptDef(
        key="ab_test.hypothesis",
        category="ab_testing",
        description="Draft an A/B test hypothesis for a touch element.",
        default_body=(
            "Draft an A/B test hypothesis for {{element}} on touch #{{touch_number}}.\n"
            "Baseline: {{baseline}}\n"
            "Variant: {{variant}}\n"
            "Return JSON: {hypothesis, primaryMetric, secondaryMetrics: [string], "
            "minimumDetectableEffect: number, recommendedSampleSize: int, "
            "rationale: string}."
        ),
    ),
    PromptDef(
        key="ab_test.significance",
        category="ab_testing",
        description="Compute statistical significance of an A/B test result.",
        default_body=(
            "Compute significance for this A/B test.\n"
            "Variant A: conversions={{a_conversions}}, sample={{a_sample}}\n"
            "Variant B: conversions={{b_conversions}}, sample={{b_sample}}\n"
            "Return JSON: {pValue: 0-1, confidence: 0-1, winner: 'A'|'B'|'inconclusive', "
            "lift: number, recommendedAction: string, "
            "minimumSampleSizeMet: bool}."
        ),
    ),
    PromptDef(
        key="scheduler.priority",
        category="scheduler",
        description="Rank pending sends for the next scheduler tick.",
        default_body=(
            "Rank these pending sends for the next scheduler tick.\n"
            "Pending: {{pending_sends}}\n"
            "Capacity this tick: {{capacity}}\n"
            "Business hours: {{business_hours}} ({{timezone}})\n"
            "Return JSON: {ranked: [{sendId, priority: 0-100, reason: string}], "
            "skipped: [{sendId, reason: string}]}."
        ),
    ),
]


# ── Misc (4) ────────────────────────────────────────────────────────────────

_MISC_PROMPTS: list[PromptDef] = [
    PromptDef(
        key="domain.enrich",
        category="domain",
        description="Enrich company info from a domain.",
        default_body=(
            "Enrich company info for domain '{{domain}}'.\n"
            "Return JSON: {companyName, industry, employeeCount, "
            "revenueRange, techStack: [string], location, description, "
            "fundingStage, foundedYear}."
        ),
    ),
    PromptDef(
        key="domain.dns_suggest",
        category="domain",
        description="Suggest DNS records (SPF, DKIM, DMARC) for a sending domain.",
        default_body=(
            "Suggest DNS records for sending domain {{domain}}.\n"
            "Provider: {{provider}}\n"
            "Current records: {{current_records}}\n"
            "Return JSON: {records: [{type: 'TXT'|'CNAME'|'MX', host, value, "
            "ttl, purpose: string}], missingRecords: [string], "
            "deliverabilityRisk: 'low'|'medium'|'high', instructions: string}."
        ),
    ),
    PromptDef(
        key="competitor.radar_summary",
        category="competitor",
        description="Summarize a competitor radar for a prospect's company.",
        default_body=(
            "Summarize the competitor radar for {{company}} (domain: {{domain}}).\n"
            "Known competitors: {{competitors}}\n"
            "Return JSON: {competitors: [{name, domain, positioning, "
            "overlapScore: 0-100, strength: string, weakness: string}], "
            "overallPositioning: string, recommendedAngle: string}."
        ),
    ),
    PromptDef(
        key="job_change.alert",
        category="job_change",
        description="Generate a job-change alert + re-engagement recommendation.",
        default_body=(
            "Generate a job-change alert for {{prospect_name}}.\n"
            "Previous: {{previous_title}} at {{previous_company}}\n"
            "New: {{new_title}} at {{new_company}} ({{new_domain}})\n"
            "Original ICP fit: {{original_icp_fit}}\n"
            "Return JSON: {newIcpFitScore: 0-100, reEngagementRecommended: bool, "
            "suggestedAngle: string, messageDraft: string, "
            "risks: [string]}."
        ),
    ),
]


# ── Aggregate ───────────────────────────────────────────────────────────────

PROMPT_DEFS: list[PromptDef] = (
    _EMAIL_PROMPTS
    + _ICP_PROSPECTING_PROMPTS
    + _ANALYTICS_CONTENT_PROMPTS
    + _SEQUENCE_OPTIMIZATION_PROMPTS
    + _MISC_PROMPTS
)


def _post_check() -> None:
    """Sanity-check the prompt list at import time (cheap, dev-only)."""
    keys = [p.key for p in PROMPT_DEFS]
    if len(keys) != len(set(keys)):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        raise RuntimeError(f"prompt_defs has duplicate keys: {dupes}")
    expected = 47
    if len(PROMPT_DEFS) != expected:
        raise RuntimeError(
            f"prompt_defs expected {expected} prompts, got {len(PROMPT_DEFS)}"
        )


_post_check()


def to_template_kwargs(defn: PromptDef, sort_order: int) -> dict[str, Any]:
    """
    Convert a PromptDef into the kwargs dict used to construct a
    PromptTemplate row (matches the model field names exactly).
    """
    import json as _json

    return {
        "key": defn.key,
        "category": defn.category,
        "name": defn.resolved_name(),
        "description": defn.description,
        "template": defn.default_body,
        "isEditable": True,
        "defaultValue": defn.default_body,
        "variables": _json.dumps(defn.resolved_variables()),
        "sortOrder": sort_order,
    }


__all__ = ["PromptDef", "PROMPT_DEFS", "to_template_kwargs"]
