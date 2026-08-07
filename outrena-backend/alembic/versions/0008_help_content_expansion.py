"""Help-guide content expansion (AUDIT-HELP-1 / FIX-HELP-1).

Revision ID: 0008
Revises: 0007
Create Date: 2025-01-08 00:00:00

This migration expands the help-guide content from the 0003 stub seed
(5 sections / 6 single-sentence stub articles) to 14 sections / 60
substantive articles (with 6 screenshot placeholders wired for
/key articles) covering:

  - All 31 legacy HTML guide topics (Getting Started, ICP Profiles,
    Prospects, Pipeline, Email Studio, Sequences, Analytics, Deals,
    Compliance/Suppression, Reply Inbox, LinkedIn Hub, Content Ideas,
    Weekly Digest, Templates, Alumni Tracker, A/B Split Testing, System
    Parameters, Prompt Management, User Management, LLM Models, Autopilot,
    Exclusion Rules, Meeting Prep, Collaterals, Prospecting Flows, Flow
    Templates, Flow Webhooks, Rate Limits, Flow Autopilot Queue, Flow
    Analytics, Flow A/B Tests) — reorganised into 14 React-SaaS-aligned
    sections that match the sidebar nav-config group structure.

  - All 10 NEW SaaS topics:
      * Dual-Path Integration  → integrations section
      * Per-User Capabilities  → deliverability + campaigns-sequences
      * Manager Dashboard      → optimization section
      * Usage/Cost Tracking    → compliance-gdpr section
      * GDPR (DSR/Consent/Retention) → compliance-gdpr section
      * Global LLM Config      → platform-admin section
      * Billing depth          → billing-rbac section
      * RBAC depth             → billing-rbac section
      * Platform Admin depth   → platform-admin section
      * In-app Support         → support-help section

  - Role-gated sections per the ROLE_HIERARCHY ladder:
      REP          → 8 sections (getting-started, icp-prospects,
                     campaigns-sequences, deliverability, integrations,
                     flows-autopilot, linkedin-alumni, support-help)
      MANAGER      → + pipeline, optimization
      TENANT_ADMIN → + admin-setup, billing-rbac, compliance-gdpr
      SUPER_ADMIN  → + platform-admin

Idempotent: re-running this migration upserts sections (ON CONFLICT
slug DO UPDATE) and upserts articles by (section_id, slug) — existing
rows are UPDATED in place, no duplicates inserted. Role-gate rows are
ON CONFLICT (section_id, min_role) DO NOTHING.

Branches on schema: PUBLIC-only (help content lives in the public
schema). Tenant-schema migrations are no-ops.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import text

# ── revision identifiers ────────────────────────────────────────────────────
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers (mirror 0003/0007 conventions) ──────────────────────────────────


def _s() -> str:
    """Return the active schema for this migration step."""
    ctx = context.get_context()
    if ctx is None:
        return "public"
    return getattr(ctx, "version_table_schema", None) or "public"


def _table_exists(bind, schema: str, name: str) -> bool:
    result = bind.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": name},
    )
    return result.fetchone() is not None


# ── Section catalog ─────────────────────────────────────────────────────────
# (slug, title, description, sort_order, min_role or None)
#
# `min_role` controls the help_section_roles gate row. A None value means
# the section is open to every authenticated user (REP+). Setting it to
# "MANAGER"/"TENANT_ADMIN"/"SUPER_ADMIN" creates a gate row that hides
# the section from lower roles per the ROLE_HIERARCHY ladder.

_HELP_SECTIONS: list[tuple[str, str, str, int, str | None]] = [
    # ── REP-gated (no row = open to every authenticated user) ───────────────
    (
        "getting-started",
        "Getting Started",
        "Your first 30 minutes: sign-in, LLM setup, ICP, first campaign, reply inbox.",
        0,
        None,
    ),
    (
        "icp-prospects",
        "ICP Profiles & Prospects",
        "Define ideal customer profiles, source and import prospects, scoring, suppression.",
        1,
        None,
    ),
    (
        "campaigns-sequences",
        "Campaigns & Sequences",
        "Build campaigns, 7-touch sequences, frameworks, per-user campaign ownership.",
        2,
        None,
    ),
    (
        "deliverability",
        "Deliverability & Sending",
        "Domains, SPF/DKIM/DMARC, MailBridge, per-user sender identities and quotas.",
        3,
        None,
    ),
    (
        "integrations",
        "Integrations (Dual-Path)",
        "Apollo, ZoomInfo, Clearbit, Hunter — platform-managed vs tenant-managed.",
        4,
        None,
    ),
    (
        "flows-autopilot",
        "Prospecting Flows & Autopilot",
        "Build flows, schedule runs, autopilot queue, rate limits, scheduler status.",
        5,
        None,
    ),
    (
        "linkedin-alumni",
        "LinkedIn Hub & Alumni Tracker",
        "LinkedIn engagement, inbox, job-change alerts, alumni tracking.",
        6,
        None,
    ),
    (
        "support-help",
        "In-app Support & Help Guide",
        "Open support tickets, browse help articles, search, deep-link to articles.",
        7,
        None,
    ),
    # ── MANAGER-gated ───────────────────────────────────────────────────────
    (
        "pipeline",
        "Pipeline & Meetings",
        "Deals Kanban, meetings, call logs, meeting prep, deal-health monitoring.",
        10,
        "MANAGER",
    ),
    (
        "optimization",
        "Optimization & Analytics",
        "A/B testing, optimization rules, weekly digest, manager dashboard cross-user view.",
        11,
        "MANAGER",
    ),
    # ── TENANT_ADMIN-gated ─────────────────────────────────────────────────
    (
        "admin-setup",
        "Admin Setup",
        "LLM config, prompt management, system parameters, exclusion rules, collaterals, "
        "templates, source config, signal monitors, domain enrichment.",
        20,
        "TENANT_ADMIN",
    ),
    (
        "billing-rbac",
        "Billing & RBAC",
        "Subscriptions, billing, roles, permissions, user management.",
        21,
        "TENANT_ADMIN",
    ),
    (
        "compliance-gdpr",
        "Compliance & GDPR",
        "DSR registry, consent logs, retention policies, usage/cost tracking, SOC2.",
        22,
        "TENANT_ADMIN",
    ),
    # ── SUPER_ADMIN-gated ──────────────────────────────────────────────────
    (
        "platform-admin",
        "Platform Admin",
        "Platform dashboard, tenant signups, global LLM config, audit log, integrations.",
        30,
        "SUPER_ADMIN",
    ),
]


# ── Article catalog ─────────────────────────────────────────────────────────
# (section_slug, slug, title, body_markdown, sort_order)
#
# Bodies are GitHub-flavoured Markdown (rendered client-side via
# react-markdown + remark-gfm). Each article follows the template:
#   # Title (optional — frontend already renders the title separately)
#   Intro paragraph
#   ## Steps (numbered list)
#   ## Tips (optional)
#   ## See also (cross-links using /help/<section>/<article> deep-link URLs)

_HELP_ARTICLES: list[tuple[str, str, str, str, int]] = [

    # ════════════════════════════════════════════════════════════════════════
    # getting-started (4 articles)
    # ════════════════════════════════════════════════════════════════════════
    (
        "getting-started", "welcome", "Welcome to OUTRENA",
        "OUTRENA is the AI-Powered Outreach Operating System — a unified "
        "platform for ICP-driven prospecting, multi-touch sequences, reply "
        "handling, and pipeline analytics. This guide walks you through your "
        "first 30 minutes.\n\n"
        "![OUTRENA dashboard overview](/help-screenshots/getting-started-welcome.png)\n\n"
        "## Steps\n\n"
        "1. Sign in at **/login** with your work email. Your role (REP, "
        "MANAGER, TENANT_ADMIN, SUPER_ADMIN) is set by your tenant admin.\n"
        "2. Open the **Dashboard** (sidebar top) for a daily snapshot: queue "
        "depth, reply rate, today's tasks.\n"
        "3. Open the **Help Guide** (sidebar top) — you are here — for "
        "context-aware articles on every feature.\n\n"
        "## Tips\n\n"
        "- Roles are hierarchical: TENANT_ADMIN sees everything MANAGER sees, "
        "plus Setup/Admin pages.\n"
        "- Your tenant admin must configure at least one LLM model before "
        "Autopilot or Email Studio will work.\n\n"
        "## See also\n\n"
        "- [Connecting an LLM Model](/help/admin-setup/connecting-llm)\n"
        "- [Your First ICP Profile](/help/icp-prospects/first-icp)\n"
        "- [Creating Your First Campaign](/help/campaigns-sequences/first-campaign)",
        0,
    ),
    (
        "getting-started", "quick-start", "5-Minute Quick Start",
        "Get a campaign sending in under five minutes once your tenant admin "
        "has connected an LLM and a sending domain.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → ICP Profiles** and click **Auto-discover** "
        "against your top 3 customers.\n"
        "2. Go to **Prospecting → Autopilot**, pick the ICP, set a daily "
        "cap, and start the queue.\n"
        "3. Once prospects arrive, open **Outreach → Campaigns** and click "
        "**Create Campaign** with the new prospects.\n"
        "4. In **Outreach → Email Studio** review and approve the "
        "AI-generated sequences.\n"
        "5. Schedule send from **Outreach → Sequences** and monitor replies "
        "in the **Reply Inbox**.\n\n"
        "## Tips\n\n"
        "- If QA fails on an email, the threshold is set in **Setup → System "
        "Parameters** (default 7/10).\n"
        "- Sending won't start until your domain passes SPF/DKIM/DMARC — "
        "check via **Setup → Domains → Check DNS**.\n\n"
        "## See also\n\n"
        "- [Managing Domains](/help/deliverability/managing-domains)\n"
        "- [Email Studio QA Workflow](/help/campaigns-sequences/email-studio)",
        1,
    ),
    (
        "getting-started", "first-campaign", "Creating Your First Campaign",
        "A campaign is the unit of outreach work in OUTRENA. It bundles "
        "prospects, a GTM thesis, a framework, an LLM config, and a sending "
        "domain — then orchestrates sequences at scale.\n\n"
        "## Steps\n\n"
        "1. Click **Campaigns** in the sidebar.\n"
        "2. Click **Create Campaign** (top-right).\n"
        "3. Fill in the campaign name, description, and framework.\n"
        "4. Select an ICP profile, LLM config, and sending domain.\n"
        "5. (Optional) Link collaterals from the shared library.\n"
        "6. Click **Create**.\n\n"
        "## Tips\n\n"
        "- Campaigns are owned by the creating user. Managers can see all "
        "campaigns via the **Manager Dashboard**.\n"
        "- The integration mode (platform_managed vs tenant_managed) "
        "affects LLM and integration costs. See [Dual-Path Integrations]"
        "(/help/integrations/dual-path).\n\n"
        "## See also\n\n"
        "- [Managing Sequences](/help/campaigns-sequences/managing-sequences)\n"
        "- [ICP Profiles](/help/icp-prospects/icp-profiles)",
        2,
    ),
    (
        "getting-started", "navigation", "Sidebar Navigation Map",
        "The OUTRENA sidebar groups every feature into six top-level "
        "sections. Role-based filtering hides sections you cannot access.\n\n"
        "## Sidebar groups\n\n"
        "1. **Overview** — Dashboard, Manager Dashboard (MANAGER+), Help Guide.\n"
        "2. **Prospecting** — Autopilot, ICP Profiles, Prospects, Sourcing, "
        "LinkedIn, Job Change, Competitors, Lead Score, Flows, Domain Enrich.\n"
        "3. **Outreach** — Campaigns, Email Studio, Sequences, Reply Inbox, "
        "Collaterals, Meeting Prep, Exclusion Rules, Templates.\n"
        "4. **Pipeline** — Deals Kanban, Meetings, Call Logs.\n"
        "5. **Optimize** — Analytics, A/B Testing, Content Ideas, Weekly "
        "Digest, Optimization Rules.\n"
        "6. **Setup & Admin** (TENANT_ADMIN+) — LLM Models, Prompts, System "
        "Parameters, Integrations, Domains, MailBridge, Rate Limits, "
        "Scheduler, Billing, User Management, Roles, Permissions, Audit Logs, "
        "GDPR Center, Usage & Cost.\n"
        "7. **Platform Admin** (SUPER_ADMIN) — separate console at "
        "/platform-admin.\n\n"
        "## See also\n\n"
        "- [Role Hierarchy](/help/billing-rbac/role-hierarchy)\n"
        "- [Manager Dashboard](/help/optimization/manager-dashboard)",
        3,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # icp-prospects (4 articles)
    # ════════════════════════════════════════════════════════════════════════
    (
        "icp-prospects", "icp-profiles", "ICP Profiles",
        "An Ideal Customer Profile (ICP) defines the firmographic, "
        "technographic, and intent signals that score and source prospects. "
        "ICPs drive every downstream workflow: Autopilot sourcing, lead "
        "scoring, campaign filtering, sequence personalization.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → ICP Profiles**.\n"
        "2. Click **Auto-discover** and pick 1-3 of your best customers — "
        "OUTRENA extracts their common signals into a draft ICP.\n"
        "3. Edit the ICP: industry, company size, geography, tech stack, "
        "intent keywords, negative signals.\n"
        "4. Set weights for each signal (1-5) — these drive the lead score.\n"
        "5. Click **Save**. The ICP is now selectable in Autopilot, "
        "Campaigns, and Flows.\n\n"
        "## Tips\n\n"
        "- One ICP per GTM motion. Don't mix SMB and Enterprise in one "
        "profile — the signals conflict.\n"
        "- Negative signals (e.g. \"uses Salesforce\" if you're a HubSpot "
        "shop) are as valuable as positive ones.\n\n"
        "## See also\n\n"
        "- [Importing Prospects via CSV](/help/icp-prospects/csv-import)\n"
        "- [Lead Scoring](/help/icp-prospects/lead-scoring)",
        0,
    ),
    (
        "icp-prospects", "first-icp", "Your First ICP Profile",
        "Walk through a concrete ICP setup so you can start sourcing "
        "qualified prospects in under five minutes.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → ICP Profiles** and click **New ICP**.\n"
        "2. Name it (e.g. \"Mid-market SaaS - US\").\n"
        "3. Add firmographics: industry = SaaS, headcount 50-500, region US.\n"
        "4. Add tech stack: include HubSpot, exclude Salesforce.\n"
        "5. Add intent keywords: \"outreach automation\", \"SDR tooling\".\n"
        "6. Click **Auto-discover from customers** and pick 2 reference "
        "accounts to enrich the profile.\n"
        "7. Click **Save** then **Activate**.\n\n"
        "## Tips\n\n"
        "- Activate an ICP only after testing it against 5-10 known "
        "good-fit accounts — verify the score distribution.\n\n"
        "## See also\n\n"
        "- [ICP Profiles](/help/icp-prospects/icp-profiles)\n"
        "- [Autopilot Pipeline](/help/flows-autopilot/autopilot)",
        1,
    ),
    (
        "icp-prospects", "csv-import", "Importing Prospects via CSV",
        "Bulk-import prospects from a CSV when you already have a list "
        "(e.g. exported from your CRM, a conference attendee list, or an "
        "Apollo export). OUTRENA enriches and scores each row.\n\n"
        "![CSV import dialog](/help-screenshots/icp-prospects-csv-import.png)\n\n"
        "## Steps\n\n"
        "1. Open **Prospects** in the sidebar.\n"
        "2. Click **Import CSV** (top-right).\n"
        "3. Upload the CSV (required columns: `email`; recommended: "
        "`first_name`, `last_name`, `company`, `title`, `linkedin_url`).\n"
        "4. Select an ICP profile to score the imports against.\n"
        "5. (Optional) Apply a suppression list to skip existing prospects.\n"
        "6. Click **Start Import**. Progress is shown in the import drawer.\n\n"
        "## Tips\n\n"
        "- Duplicates are auto-merged on email.\n"
        "- GDPR consent status defaults to `pending` for CSV imports — "
        "obtain consent before sending. See [Consent Management]"
        "(/help/compliance-gdpr/consent-management).\n\n"
        "## See also\n\n"
        "- [Suppression Lists](/help/icp-prospects/suppression)\n"
        "- [GDPR Consent Management](/help/compliance-gdpr/consent-management)",
        2,
    ),
    (
        "icp-prospects", "suppression", "Suppression Lists",
        "Suppression lists prevent OUTRENA from contacting prospects you "
        "shouldn't reach — unsubscribes, existing customers, competitors, "
        "or accounts owned by another rep.\n\n"
        "## Steps\n\n"
        "1. Open **Prospects** and click the **Suppression** tab.\n"
        "2. Click **Add Suppression Rule**.\n"
        "3. Choose the rule type: email pattern, domain, company name, or "
        "CSV upload.\n"
        "4. Enter the values (one per line) and a reason for audit.\n"
        "5. Click **Save**. Future imports and Autopilot runs will skip "
        "matching prospects.\n\n"
        "## Tips\n\n"
        "- Suppression rules are tenant-wide by default; tenant admins can "
        "scope them to a single campaign.\n"
        "- Reply Inbox auto-suppression (\"unsubscribe\" intent) is separate "
        "and managed in **Setup → System Parameters**.\n\n"
        "## See also\n\n"
        "- [Exclusion Rules](/help/admin-setup/exclusion-rules)\n"
        "- [System Parameters](/help/admin-setup/system-parameters)",
        3,
    ),
    (
        "icp-prospects", "lead-scoring", "Lead Scoring",
        "Every prospect gets a 0-100 score derived from the ICP weights, "
        "intent signals, and engagement history. Scores drive Autopilot "
        "queue priority and campaign filtering.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → Lead Score**.\n"
        "2. Filter by ICP, score band, or activity window.\n"
        "3. Click any prospect to see the score breakdown — which signals "
        "contributed and by how much.\n"
        "4. To re-weight, edit the ICP profile — scores recompute "
        "automatically on the next Autopilot tick.\n\n"
        "## Tips\n\n"
        "- The score is recomputed nightly. Manual enrichment (e.g. adding "
        "a LinkedIn URL) triggers an immediate re-score.\n"
        "- Use score bands in Campaign filters (e.g. score >= 70) to "
        "concentrate effort on best-fit accounts.\n\n"
        "## See also\n\n"
        "- [ICP Profiles](/help/icp-prospects/icp-profiles)\n"
        "- [Autopilot Pipeline](/help/flows-autopilot/autopilot)",
        4,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # campaigns-sequences (5 articles incl. Per-User Campaign Ownership)
    # ════════════════════════════════════════════════════════════════════════
    (
        "campaigns-sequences", "first-campaign", "Creating a Campaign",
        "Campaigns organize your outreach to a specific audience. Each "
        "campaign has an owner (a REP or MANAGER), an ICP profile, an LLM "
        "config, and a sending domain.\n\n"
        "![Creating a campaign](/help-screenshots/campaigns-sequences-first-campaign.png)\n\n"
        "## Steps\n\n"
        "1. Click **Campaigns** in the sidebar.\n"
        "2. Click the **Create Campaign** button (top-right).\n"
        "3. Fill in the campaign name, description, and framework.\n"
        "4. Select an ICP profile, LLM config, and sending domain.\n"
        "5. (Optional) Link collaterals from the shared library.\n"
        "6. Click **Create**.\n\n"
        "## Tips\n\n"
        "- Campaigns are owned by the creating user. Managers can see all "
        "campaigns via the **Manager Dashboard**.\n"
        "- The integration mode (platform_managed vs tenant_managed) "
        "affects LLM and integration costs. See [Dual-Path Integrations]"
        "(/help/integrations/dual-path).\n\n"
        "## See also\n\n"
        "- [Managing Sequences](/help/campaigns-sequences/managing-sequences)\n"
        "- [ICP Profiles](/help/icp-prospects/icp-profiles)",
        0,
    ),
    (
        "campaigns-sequences", "managing-sequences", "Managing 7-Touch Sequences",
        "Sequences are multi-touch outreach plans (Email + LinkedIn) "
        "generated per prospect with framework-aware angles and QA-scored "
        "copy. OUTRENA supports the 7-touch sequence pattern by default.\n\n"
        "## Steps\n\n"
        "1. Open **Outreach → Sequences**.\n"
        "2. Pick a campaign to view its sequence tree.\n"
        "3. Each touch shows: angle, channel, day offset, draft, QA score.\n"
        "4. Edit any draft inline; click **Regenerate** to ask the LLM for "
        "a new angle.\n"
        "5. Approve touches individually or in bulk.\n"
        "6. Click **Schedule Send** — OUTRENA queues sends per your "
        "domain's daily cap.\n\n"
        "## Tips\n\n"
        "- QA-scored below threshold (default 7/10) touches are flagged for "
        "manual review before sending.\n"
        "- Per-user sending quotas apply — see [Per-User Sender Identities]"
        "(/help/deliverability/per-user-sender-identities).\n\n"
        "## See also\n\n"
        "- [Email Studio QA Workflow](/help/campaigns-sequences/email-studio)\n"
        "- [Per-User Campaign Ownership](/help/campaigns-sequences/per-user-campaign-ownership)",
        1,
    ),
    (
        "campaigns-sequences", "email-studio", "Email Studio QA Workflow",
        "Email Studio is where every AI-generated email is reviewed, "
        "edited, QA-scored, and approved before it enters a sequence. "
        "REP users own their queue; MANAGER+ can review anyone's queue via "
        "the cross-user view.\n\n"
        "![Email Studio review pane](/help-screenshots/campaigns-sequences-email-studio.png)\n\n"
        "## Steps\n\n"
        "1. Open **Outreach → Email Studio**.\n"
        "2. The left rail shows drafts grouped by status: Pending Review, "
        "QA Failed, QA Passed, Approved.\n"
        "3. Click a draft to see the prospect context, the framework angle "
        "used, and the QA score breakdown.\n"
        "4. Edit the body, then click **Re-run QA** to re-score.\n"
        "5. Approve with **Mark as Approved** (or use the keyboard shortcut "
        "`A`).\n"
        "6. Approved emails enter the sequence queue at their scheduled "
        "send day.\n\n"
        "## Tips\n\n"
        "- The QA threshold is set in **Setup → System Parameters** (key: "
        "`email_qa_threshold`). Default 7/10.\n"
        "- MANAGER+ users see a **Reviewer** filter at the top — pick any "
        "rep to triage their queue.\n\n"
        "## See also\n\n"
        "- [Managing 7-Touch Sequences](/help/campaigns-sequences/managing-sequences)\n"
        "- [Manager Dashboard](/help/optimization/manager-dashboard)",
        2,
    ),
    (
        "campaigns-sequences", "reply-inbox", "Reply Inbox & Auto-Pilot",
        "Reply Inbox ingests every inbound reply, classifies intent "
        "(positive, negative, OOO, unsubscribe, neutral), and routes "
        "high-priority replies for human review. Auto-Pilot can handle "
        "positive replies hands-off.\n\n"
        "## Steps\n\n"
        "1. Open **Outreach → Reply Inbox**.\n"
        "2. Filter by intent, campaign, or assignee.\n"
        "3. Click a reply to see the full thread, the AI-suggested "
        "response, and the prospect score.\n"
        "4. Edit the suggestion, then click **Send** — or **Auto-Pilot** "
        "to let the LLM send context-aware follow-ups automatically.\n"
        "5. Mark positive replies as **Booked** to log them in the Deals "
        "Kanban.\n\n"
        "## Tips\n\n"
        "- Auto-Pilot is opt-in per reply OR globally per campaign. Be "
        "conservative — false-positive auto-replies damage reputation.\n"
        "- Unsubscribe intent auto-suppresses the prospect across the "
        "tenant. See [Suppression Lists](/help/icp-prospects/suppression).\n\n"
        "## See also\n\n"
        "- [Suppression Lists](/help/icp-prospects/suppression)\n"
        "- [Deals Kanban](/help/pipeline/deals-kanban)",
        3,
    ),
    (
        "campaigns-sequences", "per-user-campaign-ownership",
        "Per-User Campaign Ownership",
        "Campaigns are owned by the creating user — a REP or MANAGER. "
        "This is a SaaS2 multi-tenant feature: each rep has their own "
        "pipeline, their own sending quota, and their own analytics. "
        "Managers see a cross-user rollup via the Manager Dashboard.\n\n"
        "## How it works\n\n"
        "1. When a REP clicks **Create Campaign**, the `owner_id` is set "
        "to their user ID. Only they (and MANAGER+ users in their tenant) "
        "can edit it.\n"
        "2. Sending uses the owner's per-user sender identity (see "
        "[Per-User Sender Identities](/help/deliverability/per-user-sender-identities)).\n"
        "3. Analytics (reply rate, meetings booked, pipeline value) are "
        "attributed to the owner; the Manager Dashboard aggregates across "
        "the team.\n"
        "4. Daily send quota is enforced per user — see [Usage & Cost "
        "Tracking](/help/compliance-gdpr/usage-cost-tracking).\n\n"
        "## Tips\n\n"
        "- REP users can transfer ownership to a teammate via the "
        "**Campaign → Reassign** action (requires MANAGER+ to approve).\n"
        "- When a REP leaves, the tenant admin should bulk-reassign their "
        "campaigns before deactivating the user.\n\n"
        "## See also\n\n"
        "- [Per-User Sender Identities](/help/deliverability/per-user-sender-identities)\n"
        "- [Manager Dashboard](/help/optimization/manager-dashboard)",
        4,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # deliverability (4 articles incl. Per-User Sender Identities)
    # ════════════════════════════════════════════════════════════════════════
    (
        "deliverability", "managing-domains", "Managing Sending Domains",
        "Sending domains are the foundation of deliverability. OUTRENA "
        "manages SPF, DKIM, and DMARC via the **Setup → Domains** page. "
        "Sequences will not start on a domain until all three pass.\n\n"
        "![Domains list with DNS check](/help-screenshots/deliverability-managing-domains.png)\n\n"
        "## Steps\n\n"
        "1. Open **Setup → Domains** (TENANT_ADMIN+).\n"
        "2. Click **Add Domain** and enter the apex or subdomain.\n"
        "3. OUTRENA generates the DNS records (SPF, DKIM, DMARC, MX for "
        "MailBridge).\n"
        "4. Publish the records in your DNS provider.\n"
        "5. Click **Check DNS** — re-runs every 15 min until all pass.\n"
        "6. Once green, the domain is selectable in Campaign create.\n\n"
        "## Tips\n\n"
        "- Use a subdomain (e.g. `mail.yourcompany.com`) so a deliverability "
        "issue doesn't affect your primary domain's reputation.\n"
        "- DMARC policy should start at `p=none` (monitor) and graduate to "
        "`p=quarantine` after 2 weeks of clean reports.\n\n"
        "## See also\n\n"
        "- [Per-User Sender Identities](/help/deliverability/per-user-sender-identities)\n"
        "- [MailBridge Configuration](/help/deliverability/mailbridge)",
        0,
    ),
    (
        "deliverability", "dns-records", "SPF / DKIM / DMARC Explained",
        "These three DNS records prove to receiving mail servers that "
        "OUTRENA is authorized to send on your behalf. All three must "
        "pass before sequences start.\n\n"
        "## What each does\n\n"
        "1. **SPF** (Sender Policy Framework) — a TXT record listing the "
        "IPs/servers allowed to send from your domain. Receivers check "
        "the SPF record of the `Return-Path` domain.\n"
        "2. **DKIM** (DomainKeys Identified Mail) — a public-key signature "
        "embedded in the email header. Receivers fetch the public key from "
        "your DNS to verify the signature.\n"
        "3. **DMARC** (Domain-based Message Authentication) — a policy "
        "record that tells receivers what to do if SPF/DKIM fail "
        "(none / quarantine / reject) and where to send aggregate reports.\n\n"
        "## Tips\n\n"
        "- OUTRENA generates all three records for you on the **Setup → "
        "Domains** page. Copy them verbatim into your DNS provider.\n"
        "- DNS propagation can take up to 48h. Use **Check DNS** to "
        "re-verify; the status badge updates every 15 minutes.\n\n"
        "## See also\n\n"
        "- [Managing Sending Domains](/help/deliverability/managing-domains)\n"
        "- [MailBridge Configuration](/help/deliverability/mailbridge)",
        1,
    ),
    (
        "deliverability", "mailbridge", "MailBridge Configuration",
        "MailBridge is OUTRENA's inbound + outbound email relay. It "
        "handles bounce parsing, unsubscribe detection, reply threading, "
        "and per-user sender identity routing.\n\n"
        "## Steps\n\n"
        "1. Open **Setup → MailBridge** (TENANT_ADMIN+).\n"
        "2. Verify your inbound MX records are published (per domain).\n"
        "3. Set the bounce threshold — after N bounces on a domain, "
        "sequences auto-pause.\n"
        "4. Configure the spam-complaint threshold — recipients marking "
        "you as spam trigger automatic suppression.\n"
        "5. (Optional) Set a custom Reply-To domain.\n\n"
        "## Tips\n\n"
        "- MailBridge logs every inbound event — viewable in **Reply "
        "Inbox → Activity**.\n"
        "- If bounces spike, check your ICP targeting — usually a sign "
        "of stale data, not a MailBridge issue.\n\n"
        "## See also\n\n"
        "- [Per-User Sender Identities](/help/deliverability/per-user-sender-identities)\n"
        "- [Reply Inbox & Auto-Pilot](/help/campaigns-sequences/reply-inbox)",
        2,
    ),
    (
        "deliverability", "per-user-sender-identities",
        "Per-User Sender Identities and Quotas",
        "A SaaS2 feature: every user gets their own sender identity "
        "(name + email + reply-to) and a daily send quota. Campaigns "
        "owned by a user send from that user's identity.\n\n"
        "## Steps (user self-service)\n\n"
        "1. Open **Setup → Sender Identities** (any authenticated user).\n"
        "2. Click **Add Identity** and enter your name, from-email, "
        "reply-to-email.\n"
        "3. Verify the email via the OTP code OUTRENA sends.\n"
        "4. Click **Set Default** to make this your primary sender "
        "identity.\n"
        "5. View your daily/hourly quota at the top of the page.\n\n"
        "## Steps (tenant admin override)\n\n"
        "1. Open **Admin → User Management**.\n"
        "2. Pick a user. Click **Sender Identities**.\n"
        "3. Add, verify, or revoke identities on the user's behalf.\n"
        "4. Adjust the user's daily send quota (default: 200/day).\n\n"
        "## Tips\n\n"
        "- Quota is enforced per user, not per campaign. Sharing a "
        "campaign across owners combines their quotas.\n"
        "- Quota overages show up in [Usage & Cost Tracking]"
        "(/help/compliance-gdpr/usage-cost-tracking).\n\n"
        "## See also\n\n"
        "- [Per-User Campaign Ownership](/help/campaigns-sequences/per-user-campaign-ownership)\n"
        "- [Rate Limits](/help/flows-autopilot/rate-limits)",
        3,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # integrations (3 articles incl. Dual-Path)
    # ════════════════════════════════════════════════════════════════════════
    (
        "integrations", "dual-path",
        "Platform-managed vs Tenant-managed Integrations",
        "OUTRENA's dual-path integration model (SaaS2) lets each tenant "
        "choose: use the platform-managed integration (OUTRENA's API keys, "
        "billed through usage) or bring their own tenant-managed keys "
        "(billed directly by the provider, more control).\n\n"
        "## Steps\n\n"
        "1. Open **Setup → Integration Config** (TENANT_ADMIN+).\n"
        "2. For each integration (Apollo, ZoomInfo, Clearbit, Hunter, LLM "
        "providers) pick a mode:\n"
        "   - **platform_managed** — use OUTRENA's keys. Costs roll up to "
        "   your monthly usage bill.\n"
        "   - **tenant_managed** — paste your own API key. Costs bill "
        "   directly from the provider.\n"
        "3. Click **Test Connection** to verify.\n"
        "4. Click **Save**. The mode is applied immediately to all new "
        "Autopilot/Flow runs.\n\n"
        "## Tips\n\n"
        "- Switching modes mid-campaign affects only NEW runs; in-flight "
        "runs finish on the prior mode.\n"
        "- Tenant-managed keys are encrypted at rest with the tenant's "
        "KMS key. See [GDPR Compliance](/help/compliance-gdpr/dsr-registry).\n\n"
        "## See also\n\n"
        "- [Usage & Cost Tracking](/help/compliance-gdpr/usage-cost-tracking)\n"
        "- [Global LLM Configuration](/help/platform-admin/global-llm-config)",
        0,
    ),
    (
        "integrations", "apollo-zoominfo",
        "Apollo & ZoomInfo Source Connectors",
        "Apollo and ZoomInfo are OUTRENA's two primary prospect-source "
        "connectors. They enrich prospects with email, phone, title, and "
        "intent data.\n\n"
        "## Steps\n\n"
        "1. Open **Setup → Integration Config**.\n"
        "2. Find the Apollo (or ZoomInfo) row and pick a mode.\n"
        "3. For tenant_managed: paste your API key.\n"
        "4. Click **Test** — OUTRENA runs a sample enrichment.\n"
        "5. Once verified, open **Prospecting → Sourcing** to configure "
        "credit-budget caps (per-day, per-month).\n\n"
        "## Tips\n\n"
        "- Apollo credits are cheaper than ZoomInfo but coverage is "
        "thinner in EMEA. Use ZoomInfo for EU prospects.\n"
        "- Set a monthly credit cap to avoid surprise bills in "
        "platform_managed mode.\n\n"
        "## See also\n\n"
        "- [Dual-Path Integrations](/help/integrations/dual-path)\n"
        "- [Usage & Cost Tracking](/help/compliance-gdpr/usage-cost-tracking)",
        1,
    ),
    (
        "integrations", "clearbit-hunter",
        "Clearbit & Hunter for Email Enrichment",
        "Clearbit enriches company + contact firmographics; Hunter "
        "resolves email addresses from a domain. Both run automatically "
        "on every new prospect.\n\n"
        "## Steps\n\n"
        "1. Open **Setup → Integration Config**.\n"
        "2. Configure Clearbit and Hunter (each can be platform_managed "
        "or tenant_managed).\n"
        "3. Test both connectors.\n"
        "4. Open **Setup → System Parameters** and enable "
        "`auto_enrich_on_import` (default: true).\n"
        "5. New prospects (CSV import or Autopilot) get enriched within "
        "60 seconds of landing in the database.\n\n"
        "## Tips\n\n"
        "- Hunter's confidence score <50 is auto-suppressed from sequences. "
        "Adjust the threshold in System Parameters.\n"
        "- Clearbit company-data refreshes quarterly — no need to "
        "re-enrich manually.\n\n"
        "## See also\n\n"
        "- [Dual-Path Integrations](/help/integrations/dual-path)\n"
        "- [System Parameters](/help/admin-setup/system-parameters)",
        2,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # flows-autopilot (4 articles)
    # ════════════════════════════════════════════════════════════════════════
    (
        "flows-autopilot", "flows-builder", "Prospecting Flows Builder",
        "A Flow is a no-code prospecting pipeline: source → filter → "
        "enrich → score → route-to-campaign. Build once, schedule "
        "recurring runs, and let Autopilot source net-new prospects "
        "hands-off.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → Flows**.\n"
        "2. Click **New Flow** and name it.\n"
        "3. Add a **Source** step: pick Apollo/ZoomInfo/CSV/File upload.\n"
        "4. Add **Filter** steps: ICP match, score band, suppression, "
        "geography.\n"
        "5. Add **Enrich** steps: Clearbit, Hunter, LinkedIn URL lookup.\n"
        "6. Add a **Route** step: send to a campaign or to the prospect "
        "database for manual triage.\n"
        "7. Save and click **Run Now** (or schedule).\n\n"
        "## Tips\n\n"
        "- Each step has a runtime cost shown in the editor. Watch the "
        "total before scheduling.\n"
        "- Use the **Dry Run** button (top-right) to execute the flow "
        "with a 10-row sample.\n\n"
        "## See also\n\n"
        "- [Flow Templates](/help/flows-autopilot/flow-templates)\n"
        "- [Autopilot Pipeline](/help/flows-autopilot/autopilot)",
        0,
    ),
    (
        "flows-autopilot", "flow-templates", "Flow Templates",
        "Flow templates are pre-built prospecting pipelines for common "
        "GTM motions. They give you a working starting point instead of "
        "building from scratch.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → Flows** and click the **Templates** tab.\n"
        "2. Browse the catalog: \"Net-new ABM\", \"Re-engage dormant\", "
        "\"Job-change watchers\", \"Competitor customers\".\n"
        "3. Click **Use Template**.\n"
        "4. Customize the steps (sources, filters, routes) for your "
        "tenant.\n"
        "5. Save as a new flow.\n\n"
        "## Tips\n\n"
        "- Templates are versioned — when OUTRENA ships a new version, "
        "you'll see an \"Update available\" badge.\n"
        "- Custom flows you build can be saved as templates for your "
        "team (MANAGER+ only).\n\n"
        "## See also\n\n"
        "- [Prospecting Flows Builder](/help/flows-autopilot/flows-builder)\n"
        "- [Flow Webhooks](/help/flows-autopilot/flow-webhooks)",
        1,
    ),
    (
        "flows-autopilot", "flow-webhooks", "Flow Webhooks",
        "Flow webhooks fire HTTP POSTs to your external systems when a "
        "flow step emits an event (new prospect, score threshold crossed, "
        "routed to campaign). Useful for syncing OUTRENA to your CRM or "
        "data warehouse.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → Flows → Webhooks** tab.\n"
        "2. Click **Add Webhook**.\n"
        "3. Pick the flow + the event type.\n"
        "4. Enter the destination URL and (optionally) a secret for "
        "HMAC signing.\n"
        "5. Save. OUTRENA sends a test event on save.\n\n"
        "## Tips\n\n"
        "- Webhook delivery is at-least-once; design your receiver to be "
        "idempotent on the `event_id` field.\n"
        "- Failed deliveries retry with exponential backoff for 24h, "
        "then drop. View the delivery log per webhook.\n\n"
        "## See also\n\n"
        "- [Prospecting Flows Builder](/help/flows-autopilot/flows-builder)\n"
        "- [Autopilot Pipeline](/help/flows-autopilot/autopilot)",
        2,
    ),
    (
        "flows-autopilot", "autopilot", "Autopilot Pipeline",
        "Autopilot is the legacy always-on prospecting pipeline. It "
        "sources net-new prospects against an ICP on a schedule, "
        "enriches + scores them, and routes them into your prospect "
        "database. New tenants should prefer the Flows Builder — Autopilot "
        "is preserved for backward compatibility.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → Autopilot**.\n"
        "2. Pick an ICP profile.\n"
        "3. Set the daily cap (default 50).\n"
        "4. Set the source mix (Apollo %, ZoomInfo %, etc.).\n"
        "5. Click **Start**. The queue runs every 15 minutes.\n"
        "6. View the run log at the bottom — each run shows count "
        "sourced, enriched, suppressed.\n\n"
        "## Tips\n\n"
        "- Autopilot pauses automatically when your monthly credit cap "
        "is hit. See [Usage & Cost Tracking]"
        "(/help/compliance-gdpr/usage-cost-tracking).\n"
        "- For more control (multi-step filtering, webhooks), migrate "
        "to a Flow — see [Prospecting Flows Builder]"
        "(/help/flows-autopilot/flows-builder).\n\n"
        "## See also\n\n"
        "- [ICP Profiles](/help/icp-prospects/icp-profiles)\n"
        "- [Prospecting Flows Builder](/help/flows-autopilot/flows-builder)",
        3,
    ),
    (
        "flows-autopilot", "rate-limits", "Rate Limits & Scheduler",
        "Rate limits prevent a single tenant from saturating the shared "
        "LLM/integration infrastructure. The Scheduler controls when "
        "background jobs (Autopilot ticks, Flow runs, reply-auto-pilot) "
        "execute.\n\n"
        "## Steps\n\n"
        "1. Open **Setup → Rate Limits** (TENANT_ADMIN+).\n"
        "2. Adjust per-minute/per-hour caps for: LLM calls, enrichment "
        "calls, email sends, webhook deliveries.\n"
        "3. Open **Setup → Scheduler** to see the current tick cadence "
        "(default: 15 min for Autopilot, 5 min for reply-auto-pilot).\n"
        "4. (Diagnostic only) Click **Manual Tick** to force-run a job "
        "out of schedule.\n\n"
        "## Tips\n\n"
        "- If your tenant hits a rate limit, the Scheduler shows a "
        "yellow badge next to the throttled job.\n"
        "- Rate limits are global per tenant; per-user quotas are "
        "separate (see [Per-User Sender Identities]"
        "(/help/deliverability/per-user-sender-identities)).\n\n"
        "## See also\n\n"
        "- [Per-User Sender Identities](/help/deliverability/per-user-sender-identities)\n"
        "- [Usage & Cost Tracking](/help/compliance-gdpr/usage-cost-tracking)",
        4,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # linkedin-alumni (3 articles)
    # ════════════════════════════════════════════════════════════════════════
    (
        "linkedin-alumni", "linkedin-engagement", "LinkedIn Engagement Hub",
        "The LinkedIn Hub syncs your connected LinkedIn account's "
        "engagement activity — connection accepts, replies, profile "
        "views — into OUTRENA so the LLM can personalize sequences.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → LinkedIn**.\n"
        "2. Click **Connect Account** and authorize via the OAuth popup.\n"
        "3. Set the daily connection-request cap (default 20).\n"
        "4. Pick which campaigns can use LinkedIn touches.\n"
        "5. View the engagement feed at the bottom — each item shows the "
        "prospect, the action, and the suggested next step.\n\n"
        "## Tips\n\n"
        "- LinkedIn's official API limits are strict. OUTRENA throttles "
        "to 80/week by default.\n"
        "- Disconnect via the same page — sequences with LinkedIn touches "
        "will pause until you reconnect.\n\n"
        "## See also\n\n"
        "- [Managing 7-Touch Sequences](/help/campaigns-sequences/managing-sequences)\n"
        "- [Alumni Tracker](/help/linkedin-alumni/alumni-tracker)",
        0,
    ),
    (
        "linkedin-alumni", "job-change", "Job-Change Alerts",
        "Job-change alerts fire when a tracked prospect changes employer. "
        "These are high-signal events — a prospect who moved into a "
        "decision-maker role at a target account is a hot lead.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → Job Change**.\n"
        "2. By default, every prospect in your database is tracked. Filter "
        "to a specific campaign or ICP if desired.\n"
        "3. Each alert shows: old employer, new employer, new title, "
        "alert date.\n"
        "4. Click **Create Campaign** to spin up a re-engagement campaign "
        "pre-populated with the alert list.\n\n"
        "## Tips\n\n"
        "- Job-change data refreshes nightly. Manual refresh available "
        "via the **Refresh Now** button.\n"
        "- Connect a Slack webhook in **Setup → System Parameters** to "
        "pipe alerts into a channel.\n\n"
        "## See also\n\n"
        "- [Alumni Tracker](/help/linkedin-alumni/alumni-tracker)\n"
        "- [Creating a Campaign](/help/campaigns-sequences/first-campaign)",
        1,
    ),
    (
        "linkedin-alumni", "alumni-tracker", "Alumni Tracker",
        "The Alumni Tracker monitors your customers' ex-employees — when "
        "they land at a new company, they're a warm intro to a new "
        "account. Pair this with the Job-Change Alerts for a 360° view.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → LinkedIn → Alumni** tab.\n"
        "2. Add the companies whose alumni you want to track (your "
        "customers and your competitors).\n"
        "3. Set the role filter (e.g. VP+ Eng, Director+ Sales).\n"
        "4. View the alumni feed; each row shows the alum, current "
        "employer, current title, and a **warmth** score.\n"
        "5. Click **Add to Prospects** to push the alum into your "
        "prospect database with the source = \"alumni_tracker\".\n\n"
        "## Tips\n\n"
        "- The warmth score combines: how recently they left, whether "
        "they're still in your ICP, and their engagement history.\n"
        "- Alumni Tracker uses 1 LinkedIn API credit per tracked company "
        "per day. See [Usage & Cost Tracking]"
        "(/help/compliance-gdpr/usage-cost-tracking).\n\n"
        "## See also\n\n"
        "- [Job-Change Alerts](/help/linkedin-alumni/job-change)\n"
        "- [Usage & Cost Tracking](/help/compliance-gdpr/usage-cost-tracking)",
        2,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # pipeline (4 articles, MANAGER+)
    # ════════════════════════════════════════════════════════════════════════
    (
        "pipeline", "deals-kanban", "Deals Kanban",
        "The Deals Kanban is your tenant's pipeline view: deals move "
        "left-to-right through stages (Qualified → Discovery → Demo → "
        "Proposal → Negotiation → Closed-Won). Each deal has AI-suggested "
        "next steps and a deal-health score.\n\n"
        "## Steps\n\n"
        "1. Open **Pipeline → Deals**.\n"
        "2. Filter by owner, campaign, or stage.\n"
        "3. Drag a deal card to advance the stage.\n"
        "4. Click a card to see: activity timeline, AI-suggested next "
        "step, deal-health score, value, expected close date.\n"
        "5. Use the **Bulk Edit** bar to reassign or close multiple "
        "deals at once.\n\n"
        "## Tips\n\n"
        "- Deal-health turns yellow when no activity for 7 days, red "
        "after 14. Use this to triage stalled deals.\n"
        "- MANAGER+ users see all reps' deals. REP users see only "
        "their own (or campaigns they own).\n\n"
        "## See also\n\n"
        "- [Meeting Prep](/help/pipeline/meeting-prep)\n"
        "- [Manager Dashboard](/help/optimization/manager-dashboard)",
        0,
    ),
    (
        "pipeline", "meetings", "Meetings & Call Logs",
        "Meetings and call logs are the source of truth for pipeline "
        "activity. The LLM ingests transcripts (auto-generated from "
        "Zoom/Teams recordings) to update the deal record and surface "
        "next steps.\n\n"
        "## Steps\n\n"
        "1. Open **Pipeline → Meetings** to see upcoming + past "
        "meetings.\n"
        "2. After a meeting, the transcript auto-attaches if your "
        "calendar provider is connected.\n"
        "3. Click a meeting to see: AI summary, action items, sentiment, "
        "next-step recommendation.\n"
        "4. Open **Pipeline → Call Logs** to log ad-hoc calls manually.\n\n"
        "## Tips\n\n"
        "- Action items auto-sync to your CRM (if connected via "
        "Integration Config).\n"
        "- MANAGER+ can filter meetings by rep for 1:1 prep.\n\n"
        "## See also\n\n"
        "- [Meeting Prep](/help/pipeline/meeting-prep)\n"
        "- [Deals Kanban](/help/pipeline/deals-kanban)",
        1,
    ),
    (
        "pipeline", "meeting-prep", "Meeting Prep & AI Briefs",
        "Before every meeting, OUTRENA generates a one-page brief: "
        "prospect background, prior touchpoints, recent company news, "
        "and 3 suggested talking points.\n\n"
        "## Steps\n\n"
        "1. Open **Outreach → Meeting Prep**.\n"
        "2. Search for the prospect or pick from today's calendar.\n"
        "3. Click **Generate Brief** (takes ~10 seconds).\n"
        "4. Review the brief: prospect bio, company news, talking points, "
        "objection handlers.\n"
        "5. Click **Email to me** to send a copy before the meeting.\n\n"
        "## Tips\n\n"
        "- Briefs use the prospect's LinkedIn activity + your sequence "
        "history + Clearbit news. Quality scales with data freshness.\n"
        "- For MANAGER+ users running deal reviews, the brief can be "
        "shared with the deal owner as a coaching artifact.\n\n"
        "## See also\n\n"
        "- [Deals Kanban](/help/pipeline/deals-kanban)\n"
        "- [Collaterals Library](/help/admin-setup/collaterals)",
        2,
    ),
    (
        "pipeline", "call-logs", "Call Logs & Outcome Tracking",
        "Call logs capture ad-hoc phone calls (sales dialer, mobile, "
        "VoIP). Pair each call with an outcome (connected, voicemail, "
        "callback scheduled) so the LLM can recommend the next touch.\n\n"
        "## Steps\n\n"
        "1. Open **Pipeline → Call Logs**.\n"
        "2. Click **Log Call**.\n"
        "3. Pick the prospect, enter the duration, outcome, and notes.\n"
        "4. (Optional) Upload a recording — OUTRENA transcribes and "
        "extracts action items.\n"
        "5. Save. The call appears in the prospect's activity feed.\n\n"
        "## Tips\n\n"
        "- Outcomes drive the next-step recommendation in the Deals "
        "Kanban. \"Voicemail\" → 3-day follow-up; \"Connected\" → log "
        "meeting.\n"
        "- MANAGER+ can filter call logs by rep for coaching reviews.\n\n"
        "## See also\n\n"
        "- [Meetings & Call Logs](/help/pipeline/meetings)\n"
        "- [Deals Kanban](/help/pipeline/deals-kanban)",
        3,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # optimization (4 articles incl. Manager Dashboard, MANAGER+)
    # ════════════════════════════════════════════════════════════════════════
    (
        "optimization", "ab-testing", "A/B Split Testing",
        "A/B tests compare two (or more) variants of an email subject, "
        "body, send-time, or framework. OUTRENA auto-detects statistical "
        "significance and recommends a winner.\n\n"
        "## Steps\n\n"
        "1. Open **Optimize → A/B Testing**.\n"
        "2. Click **New Test** and pick the dimension (subject, body, "
        "send-time, framework).\n"
        "3. Define variants A and B (the LLM can draft B from A).\n"
        "4. Set the sample size and success metric (open rate, reply "
        "rate, meeting-booked rate).\n"
        "5. Start the test. OUTRENA splits the audience 50/50 and "
        "monitors for significance.\n"
        "6. Once a winner is declared, click **Promote** to apply the "
        "winning variant to the full campaign.\n\n"
        "## Tips\n\n"
        "- Tests need ~100 sends per variant to reach significance. "
        "Don't call winners early.\n"
        "- Multi-variant tests (3+ variants) need proportionally more "
        "traffic.\n\n"
        "## See also\n\n"
        "- [Optimization Rules](/help/optimization/optimization-rules)\n"
        "- [Weekly Digest](/help/optimization/weekly-digest)",
        0,
    ),
    (
        "optimization", "optimization-rules", "Optimization Rules",
        "Optimization rules are tenant-wide automations: if a condition "
        "fires, take an action. Examples: \"if reply rate < 5% on a "
        "campaign for 7 days, auto-pause and notify owner\", \"if QA "
        "score < 6 on a domain, route to manual review\".\n\n"
        "## Steps\n\n"
        "1. Open **Optimize → Optimization Rules**.\n"
        "2. Click **New Rule**.\n"
        "3. Define the trigger (metric, threshold, time window).\n"
        "4. Define the action (pause campaign, notify owner, route to "
        "review, scale-up send volume).\n"
        "5. Save. The rule runs every hour.\n\n"
        "## Tips\n\n"
        "- Rules fire on the hourly tick, not in real-time. Critical "
        "issues (DNS failure, billing past-due) bypass rules.\n"
        "- MANAGER+ can clone rules across tenants via the API (useful "
        "for multi-tenant operators).\n\n"
        "## See also\n\n"
        "- [A/B Split Testing](/help/optimization/ab-testing)\n"
        "- [Weekly Digest](/help/optimization/weekly-digest)",
        1,
    ),
    (
        "optimization", "weekly-digest", "Weekly Digest",
        "The Weekly Digest is an automated Monday-morning email summarizing "
        "last week's outreach performance, top campaigns, and "
        "recommendations. Configure cadence and recipients on this page.\n\n"
        "## Steps\n\n"
        "1. Open **Optimize → Weekly Digest**.\n"
        "2. Pick the day-of-week and time for delivery (default: Monday "
        "08:00 in the tenant's timezone).\n"
        "3. Add recipients (defaults to all MANAGER+ users).\n"
        "4. Choose sections to include: top campaigns, reply-rate trend, "
        "A/B test results, deal-pipeline movement, anomaly alerts.\n"
        "5. Click **Send Test** to preview the email.\n\n"
        "## Tips\n\n"
        "- The digest uses the same data as the Manager Dashboard — "
        "consider linking to it for drill-down.\n"
        "- Anomaly alerts (e.g. reply rate dropped 50% WoW) are "
        "highlighted at the top.\n\n"
        "## See also\n\n"
        "- [Manager Dashboard](/help/optimization/manager-dashboard)\n"
        "- [Optimization Rules](/help/optimization/optimization-rules)",
        2,
    ),
    (
        "optimization", "manager-dashboard",
        "Manager Dashboard: Cross-User View",
        "The Manager Dashboard is a SaaS2 feature: a single page where "
        "MANAGER+ users see every rep's campaigns, sequences, reply "
        "rates, and pipeline value — without needing to switch users.\n\n"
        "## Steps\n\n"
        "1. Open **Manager Dashboard** (sidebar top, MANAGER+).\n"
        "2. Filter by rep, campaign, or date range.\n"
        "3. Top row: team-wide KPIs (active campaigns, replies today, "
        "meetings booked, pipeline value).\n"
        "4. Middle row: per-rep leaderboard with drill-down links.\n"
        "5. Bottom row: anomaly alerts from Optimization Rules.\n"
        "6. Click any rep's name to see their per-user dashboard.\n\n"
        "## Tips\n\n"
        "- Per-user campaign ownership ([see article]"
        "(/help/campaigns-sequences/per-user-campaign-ownership)) is what "
        "makes this view possible — every campaign has a single owner.\n"
        "- The Manager Dashboard respects per-user sender identity "
        "quotas; if a rep is throttled, their column shows a yellow "
        "badge.\n\n"
        "## See also\n\n"
        "- [Per-User Campaign Ownership](/help/campaigns-sequences/per-user-campaign-ownership)\n"
        "- [Weekly Digest](/help/optimization/weekly-digest)",
        3,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # admin-setup (6 articles, TENANT_ADMIN+)
    # ════════════════════════════════════════════════════════════════════════
    (
        "admin-setup", "connecting-llm", "Connecting an LLM Model",
        "Connecting at least one LLM is the prerequisite for Autopilot, "
        "Email Studio, Reply Drafts, Meeting Prep — everything that "
        "generates text. The built-in ZAI (GLM-4) provider needs no API "
        "key; just enable it.\n\n"
        "![Adding an LLM model](/help-screenshots/admin-setup-connecting-llm.png)\n\n"
        "## Steps\n\n"
        "1. Open **Setup → LLM Models** (TENANT_ADMIN+).\n"
        "2. Click **Add Model**.\n"
        "3. Pick a provider: ZAI (built-in), OpenAI, Anthropic, Google, "
        "DeepSeek, Groq, or self-hosted Ollama.\n"
        "4. Enter the API key (encrypted at rest). For Ollama, enter the "
        "base URL.\n"
        "5. Pick a model name (e.g. `gpt-4o`, `claude-3-5-sonnet`).\n"
        "6. Set a tier (fast / balanced / quality) — sequences pick the "
        "tier, OUTRENA picks the cheapest model in that tier.\n"
        "7. Click **Test** then **Save**.\n"
        "8. Mark one model as **Default**.\n\n"
        "## Tips\n\n"
        "- Mix tiers: cheap-fast model for QA, premium model for "
        "generation. This cuts LLM cost 40-60%.\n"
        "- In dual-path mode, each LLM provider can be platform_managed "
        "or tenant_managed. See [Dual-Path Integrations]"
        "(/help/integrations/dual-path).\n\n"
        "## See also\n\n"
        "- [Prompt Management](/help/admin-setup/prompt-management)\n"
        "- [Dual-Path Integrations](/help/integrations/dual-path)",
        0,
    ),
    (
        "admin-setup", "prompt-management", "Prompt Management",
        "OUTRENA ships ~47 prompt templates covering every generation "
        "task: email body, subject line, reply classification, meeting "
        "brief, etc. Tenant admins can clone and customize any template.\n\n"
        "## Steps\n\n"
        "1. Open **Setup → Prompts** (TENANT_ADMIN+).\n"
        "2. Browse by category (email, reply, meeting, scoring, etc.).\n"
        "3. Click any template to view the prompt source with variables "
        "(`{{prospect.first_name}}`, `{{campaign.framework}}`, etc.).\n"
        "4. Click **Clone** to make a custom copy.\n"
        "5. Edit the prompt body. Use **Test** to run it against a "
        "sample prospect.\n"
        "6. Click **Activate** to swap the system template for your "
        "custom version.\n\n"
        "## Tips\n\n"
        "- Activated custom prompts are tagged in the prompt log so you "
        "can A/B test variants.\n"
        "- Use the LLM tier field on each prompt to control which model "
        "runs it.\n\n"
        "## See also\n\n"
        "- [Connecting an LLM Model](/help/admin-setup/connecting-llm)\n"
        "- [System Parameters](/help/admin-setup/system-parameters)",
        1,
    ),
    (
        "admin-setup", "system-parameters", "System Parameters",
        "System Parameters is the tenant-wide key/value config store. "
        "It holds the QA threshold, Autopilot cadence, Auto-Pilot "
        "reply-handling rules, default unsubscribe language, and more.\n\n"
        "## Steps\n\n"
        "1. Open **Setup → System Parameters** (TENANT_ADMIN+).\n"
        "2. Browse by group: Email QA, Autopilot, Reply Auto-Pilot, "
        "Consent, Deliverability, Webhooks.\n"
        "3. Click any row to edit. Hover the info icon for a description.\n"
        "4. Save. Changes apply immediately to new runs; in-flight runs "
        "finish on the prior value.\n\n"
        "## Tips\n\n"
        "- The `email_qa_threshold` (default 7) is the most-tuned "
        "parameter — lower it during ramp-up, raise it for premium "
        "campaigns.\n"
        "- Parameter changes are audit-logged. View the log in "
        "**Admin → Audit Logs**.\n\n"
        "## See also\n\n"
        "- [Email Studio QA Workflow](/help/campaigns-sequences/email-studio)\n"
        "- [Audit Logs](/help/billing-rbac/audit-logs)",
        2,
    ),
    (
        "admin-setup", "exclusion-rules", "Exclusion Rules",
        "Exclusion rules prevent specific prospects from being added to "
        "any campaign. Unlike [Suppression Lists]"
        "(/help/icp-prospects/suppression) which act on email/domain "
        "patterns, exclusion rules act on prospect attributes (title, "
        "industry, geography).\n\n"
        "## Steps\n\n"
        "1. Open **Outreach → Exclusion Rules** (TENANT_ADMIN+).\n"
        "2. Click **New Rule**.\n"
        "3. Pick the attribute (e.g. `title` contains \"intern\").\n"
        "4. Set the action: skip in Autopilot, skip in Campaigns, or "
        "skip in both.\n"
        "5. Save. The rule runs on every prospect touchpoint.\n\n"
        "## Tips\n\n"
        "- Use exclusion rules to enforce GDPR lawful-basis filters "
        "(e.g. exclude `consent_status = 'denied'`).\n"
        "- Rules can be scoped to a single campaign or applied tenant-wide.\n\n"
        "## See also\n\n"
        "- [Suppression Lists](/help/icp-prospects/suppression)\n"
        "- [GDPR Consent Management](/help/compliance-gdpr/consent-management)",
        3,
    ),
    (
        "admin-setup", "collaterals", "Collaterals Library & Brand Voice",
        "Collaterals are reusable content assets — case studies, "
        "one-pagers, battle cards, ROI calculators — that the LLM "
        "weaves into sequences. The Brand Voice setting tunes the LLM "
        "to write in your house style.\n\n"
        "## Steps\n\n"
        "1. Open **Outreach → Collaterals** (TENANT_ADMIN+).\n"
        "2. Click **Upload** to add a PDF/DOCX/MD file.\n"
        "3. Tag each collateral: use case, ICP, stage.\n"
        "4. Switch to the **Brand Voice** tab. Paste 3-5 example emails "
        "in your house style.\n"
        "5. Click **Train**. OUTRENA builds a voice profile.\n"
        "6. In Campaign create, link collaterals — the LLM will cite "
        "them.\n\n"
        "## Tips\n\n"
        "- Brand Voice training works best with emails from a single "
        "author. Avoid mixing styles.\n"
        "- Collaterals are vector-indexed; the LLM retrieves the most "
        "relevant chunks per prospect.\n\n"
        "## See also\n\n"
        "- [Meeting Prep](/help/pipeline/meeting-prep)\n"
        "- [Creating a Campaign](/help/campaigns-sequences/first-campaign)",
        4,
    ),
    (
        "admin-setup", "domain-enrichment", "Domain Enrichment & Signal Monitors",
        "Domain Enrichment monitors target-company websites for changes "
        "(new product launches, leadership updates, press releases) and "
        "feeds them as intent signals into the prospect score. Signal "
        "Monitors let you define custom webhook-driven signals.\n\n"
        "## Steps\n\n"
        "1. Open **Prospecting → Domain Enrich** (TENANT_ADMIN+).\n"
        "2. Add the domains you want to monitor (or import from an ICP).\n"
        "3. Set the monitor cadence (default: daily).\n"
        "4. Switch to the **Signal Monitors** tab to add custom signals "
        "(e.g. G2 reviews, Crunchbase funding, LinkedIn posts).\n"
        "5. Each signal type has a config form — fill it out and click "
        "**Activate**.\n\n"
        "## Tips\n\n"
        "- Signal Monitor events appear in the prospect's activity feed "
        "and bump the lead score.\n"
        "- Custom signals via webhook: POST to `/api/v1/signals/ingest` "
        "with your tenant API key.\n\n"
        "## See also\n\n"
        "- [Lead Scoring](/help/icp-prospects/lead-scoring)\n"
        "- [ICP Profiles](/help/icp-prospects/icp-profiles)",
        5,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # billing-rbac (4 articles, TENANT_ADMIN+)
    # ════════════════════════════════════════════════════════════════════════
    (
        "billing-rbac", "managing-subscription", "Managing Your Subscription",
        "OUTRENA bills per-seat + per-usage. The Billing page shows your "
        "current plan, seat count, monthly usage, and lets you upgrade "
        "or downgrade.\n\n"
        "## Steps\n\n"
        "1. Open **Setup → Billing** (TENANT_ADMIN+).\n"
        "2. View the current plan, renewal date, and seat count.\n"
        "3. Click **Change Plan** to upgrade or downgrade. Proration is "
        "calculated instantly.\n"
        "4. Click **Manage Seats** to add/remove users. Removing a user "
        "deactivates their Keycloak account immediately.\n"
        "5. View the **Invoice History** tab for past invoices + "
        "receipts.\n"
        "6. Update the payment method under **Billing → Payment**.\n\n"
        "## Tips\n\n"
        "- Usage overages (LLM calls, integration credits) are billed "
        "monthly in arrears. See [Usage & Cost Tracking]"
        "(/help/compliance-gdpr/usage-cost-tracking).\n"
        "- Downgrades take effect at the next renewal; upgrades take "
        "effect immediately.\n\n"
        "## See also\n\n"
        "- [Usage & Cost Tracking](/help/compliance-gdpr/usage-cost-tracking)\n"
        "- [User Management](/help/billing-rbac/user-management)",
        0,
    ),
    (
        "billing-rbac", "role-hierarchy", "Role Hierarchy & Permissions",
        "OUTRENA's RBAC model has 4 system roles (REP, MANAGER, "
        "TENANT_ADMIN, SUPER_ADMIN) plus custom roles you can define. "
        "Roles are hierarchical — higher roles inherit lower-role "
        "permissions.\n\n"
        "## System roles\n\n"
        "- **REP** — runs outreach, manages own campaigns, sequences, "
        "reply inbox.\n"
        "- **MANAGER** — REP + sees all reps' campaigns (Manager "
        "Dashboard), manages templates and optimization rules.\n"
        "- **TENANT_ADMIN** — MANAGER + manages users, LLM, prompts, "
        "system params, integrations, domains, billing, RBAC, GDPR.\n"
        "- **SUPER_ADMIN** — platform operator (OUTRENA staff); sees "
        "all tenants via the Platform Admin console.\n\n"
        "## Steps (create a custom role)\n\n"
        "1. Open **Admin → Roles** (TENANT_ADMIN+).\n"
        "2. Click **New Role**.\n"
        "3. Pick a base role to inherit from.\n"
        "4. Toggle individual permissions on/off (see [Permissions]"
        "(/help/billing-rbac/permissions-matrix)).\n"
        "5. Save. Assign the role to users via **User Management**.\n\n"
        "## Tips\n\n"
        "- Custom roles can't exceed the permissions of their base role.\n"
        "- SUPER_ADMIN is platform-managed — tenant admins cannot create "
        "or assign it.\n\n"
        "## See also\n\n"
        "- [Permissions Matrix](/help/billing-rbac/permissions-matrix)\n"
        "- [User Management](/help/billing-rbac/user-management)",
        1,
    ),
    (
        "billing-rbac", "permissions-matrix", "Permissions Matrix",
        "The Permissions Matrix page lists every feature permission in "
        "OUTRENA and which roles grant it. Useful for auditing access "
        "and designing custom roles.\n\n"
        "## Steps\n\n"
        "1. Open **Admin → Permissions** (TENANT_ADMIN+).\n"
        "2. Filter by feature group (Prospecting, Outreach, Pipeline, "
        "Setup, Admin, Platform).\n"
        "3. The matrix shows: permission key, description, which system "
        "roles have it.\n"
        "4. Click any permission to see which custom roles reference it.\n"
        "5. (Read-only) — to change which roles have a permission, edit "
        "the role in **Admin → Roles**.\n\n"
        "## Tips\n\n"
        "- New features add new permissions; the audit log captures "
        "every permission-grant change.\n"
        "- Permissions are enforced server-side; the frontend only "
        "hides UI for usability, not for security.\n\n"
        "## See also\n\n"
        "- [Role Hierarchy](/help/billing-rbac/role-hierarchy)\n"
        "- [Audit Logs](/help/billing-rbac/audit-logs)",
        2,
    ),
    (
        "billing-rbac", "user-management", "User Management & Invites",
        "User Management is the tenant admin's console for inviting, "
        "deactivating, and role-assigning users. Backed by Keycloak.\n\n"
        "## Steps\n\n"
        "1. Open **Admin → User Management** (TENANT_ADMIN+).\n"
        "2. View all users in your tenant — name, email, role, last "
        "login, status (active/disabled).\n"
        "3. Click **Invite User** and enter email + role.\n"
        "4. The invitee receives a Keycloak account-creation email.\n"
        "5. To change a role: click the user → **Change Role**.\n"
        "6. To deactivate: click **Disable**. Their campaigns are "
        "auto-reassigned to their manager.\n\n"
        "## Tips\n\n"
        "- Disabled users' campaigns transfer to their direct manager "
        "(or to the first TENANT_ADMIN if no manager).\n"
        "- Per-user sender identities persist for 30 days post-disable "
        "in case of re-enable.\n\n"
        "## See also\n\n"
        "- [Per-User Sender Identities](/help/deliverability/per-user-sender-identities)\n"
        "- [Role Hierarchy](/help/billing-rbac/role-hierarchy)",
        3,
    ),
    (
        "billing-rbac", "audit-logs", "Audit Logs",
        "Every privileged action — user create/disable, role change, "
        "LLM key update, billing change, GDPR export — is logged with "
        "actor, target, timestamp, and diff. TENANT_ADMIN can view; "
        "SUPER_ADMIN can view cross-tenant.\n\n"
        "## Steps\n\n"
        "1. Open **Admin → Audit Logs** (TENANT_ADMIN+).\n"
        "2. Filter by actor, action, target, or date range.\n"
        "3. Click any row to see the full diff (before/after values).\n"
        "4. Export to CSV via the **Export** button.\n\n"
        "## Tips\n\n"
        "- Audit logs are retained 7 years per SOC2 policy.\n"
        "- For platform-wide events (tenant signup, plan change), see "
        "the Platform Admin audit log.\n\n"
        "## See also\n\n"
        "- [User Management](/help/billing-rbac/user-management)\n"
        "- [Role Hierarchy](/help/billing-rbac/role-hierarchy)",
        4,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # platform-admin (4 articles incl. Global LLM Config, SUPER_ADMIN)
    # ════════════════════════════════════════════════════════════════════════
    (
        "platform-admin", "tenant-signup", "Tenant Signup Approvals",
        "Self-serve tenant signups land in an approval queue. "
        "SUPER_ADMIN users approve or reject each request; approved "
        "tenants are provisioned instantly.\n\n"
        "## Steps\n\n"
        "1. Open **Platform Admin → Approvals** (SUPER_ADMIN).\n"
        "2. View the pending queue: tenant name, subdomain, owner email, "
        "plan requested.\n"
        "3. Click any row to review the request details + run a "
        "background check on the email domain.\n"
        "4. Click **Approve** — the tenant is provisioned and a welcome "
        "email sent.\n"
        "5. Or **Reject** with a reason — the requester is notified.\n\n"
        "## Tips\n\n"
        "- Auto-approval can be enabled per-plan in Platform Settings "
        "for low-risk tiers.\n"
        "- Approval actions are logged in the platform audit log.\n\n"
        "## See also\n\n"
        "- [Platform Dashboard](/help/platform-admin/platform-dashboard)\n"
        "- [Platform Audit Log](/help/platform-admin/audit-log)",
        0,
    ),
    (
        "platform-admin", "platform-dashboard", "Platform Admin Dashboard",
        "The Platform Admin Dashboard is SUPER_ADMIN's home base: "
        "tenant count, MRR, active users, system health, recent "
        "incidents.\n\n"
        "## Steps\n\n"
        "1. Open **Platform Admin → Dashboard** (SUPER_ADMIN).\n"
        "2. Top row: KPIs — total tenants, MRR, active users (7d), "
        "platform uptime.\n"
        "3. Middle row: tenant growth chart + plan distribution.\n"
        "4. Bottom row: recent signups (pending approval), recent "
        "incidents, top tenants by usage.\n"
        "5. Click any tenant name to drill into the tenant detail page.\n\n"
        "## Tips\n\n"
        "- The dashboard refreshes every 60 seconds.\n"
        "- For deep-dive analytics, use the **Platform → Usage** page.\n\n"
        "## See also\n\n"
        "- [Tenant Signup Approvals](/help/platform-admin/tenant-signup)\n"
        "- [Platform Usage & Cost](/help/platform-admin/platform-usage)",
        1,
    ),
    (
        "platform-admin", "global-llm-config", "Global LLM Configuration",
        "Global LLM Configs are the platform-level default LLM keys "
        "used when a tenant is in `platform_managed` mode. SUPER_ADMIN "
        "manages these; tenant admins see them as read-only.\n\n"
        "## Steps\n\n"
        "1. Open **Platform Admin → LLM Configs** (SUPER_ADMIN).\n"
        "2. Click **Add Global Config**.\n"
        "3. Pick a provider (OpenAI, Anthropic, Google, DeepSeek, Groq, "
        "ZAI, Ollama).\n"
        "4. Enter the API key (encrypted with the platform KMS key).\n"
        "5. Set the cost-per-1K-tokens (input + output) — used for "
        "tenant usage billing.\n"
        "6. Set rate limits (RPM, TPM).\n"
        "7. Save. The config is now available to all tenants in "
        "`platform_managed` mode.\n\n"
        "## Tips\n\n"
        "- Rotate keys quarterly — the rotation is seamless, no tenant "
        "downtime.\n"
        "- Cost-per-1K-tokens feeds the [Cost Table]"
        "(/help/compliance-gdpr/usage-cost-tracking) used for tenant "
        "usage billing.\n\n"
        "## See also\n\n"
        "- [Dual-Path Integrations](/help/integrations/dual-path)\n"
        "- [Usage & Cost Tracking](/help/compliance-gdpr/usage-cost-tracking)",
        2,
    ),
    (
        "platform-admin", "platform-usage", "Platform Usage & Cost Table",
        "The Platform Usage page rolls up per-tenant usage (LLM tokens, "
        "integration credits, email sends) for SUPER_ADMIN. The Cost "
        "Table defines the per-unit price for each usage type.\n\n"
        "## Steps\n\n"
        "1. Open **Platform Admin → Usage** (SUPER_ADMIN).\n"
        "2. Filter by tenant, provider, or date range.\n"
        "3. The table shows: tenant, usage type, units consumed, "
        "effective cost (units × cost-table price).\n"
        "4. Switch to the **Cost Table** tab to edit per-unit prices.\n"
        "5. Click **Export** for a CSV suitable for invoicing.\n\n"
        "## Tips\n\n"
        "- Cost-table changes apply to NEW usage only; historical rows "
        "retain their original price.\n"
        "- The usage data feeds each tenant's [Usage & Cost Tracking]"
        "(/help/compliance-gdpr/usage-cost-tracking) page.\n\n"
        "## See also\n\n"
        "- [Global LLM Configuration](/help/platform-admin/global-llm-config)\n"
        "- [Usage & Cost Tracking](/help/compliance-gdpr/usage-cost-tracking)",
        3,
    ),
    (
        "platform-admin", "audit-log", "Platform Audit Log",
        "The Platform Audit Log captures every SUPER_ADMIN action "
        "(tenant approval, key rotation, cost-table change, manual "
        "tenant suspension) plus cross-tenant system events.\n\n"
        "## Steps\n\n"
        "1. Open **Platform Admin → Audit Logs** (SUPER_ADMIN).\n"
        "2. Filter by actor, action, tenant, or date range.\n"
        "3. Click any row to see the full event diff.\n"
        "4. Export to CSV for compliance reviews.\n\n"
        "## Tips\n\n"
        "- Retained 7 years per SOC2.\n"
        "- Tamper-evident: each row is hash-chained to the prior row.\n\n"
        "## See also\n\n"
        "- [Tenant Signup Approvals](/help/platform-admin/tenant-signup)\n"
        "- [Platform Dashboard](/help/platform-admin/platform-dashboard)",
        4,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # compliance-gdpr (5 articles incl. Usage/Cost, GDPR DSR/Consent/Retention)
    # ════════════════════════════════════════════════════════════════════════
    (
        "compliance-gdpr", "dsr-registry", "Data Subject Requests (DSR)",
        "GDPR Articles 15-22 give EU residents the right to access, "
        "rectify, erase, restrict, port, and object to their personal "
        "data. The DSR Registry tracks every request end-to-end.\n\n"
        "## Steps\n\n"
        "1. Open **Admin → GDPR Center** (TENANT_ADMIN+).\n"
        "2. The DSR Registry shows every request: type, email, status, "
        "SLA due date.\n"
        "3. Requests can be submitted via the public form at "
        "`/p/gdpr-rights` or created manually by the tenant admin.\n"
        "4. Click a request to process it:\n"
        "   - **Access** — generates a JSON export of all prospect data.\n"
        "   - **Erasure** — soft-deletes the prospect (anonymized=true).\n"
        "   - **Portability** — generates a machine-readable export.\n"
        "   - **Restriction** — flags the prospect, halts processing.\n"
        "5. Complete the request by uploading the export URL + notes, "
        "then click **Mark Complete**.\n\n"
        "## Tips\n\n"
        "- SLA is 30 days per GDPR. OUTRENA shows a red badge if a "
        "request is at risk of breaching SLA.\n"
        "- All DSR actions are audit-logged.\n\n"
        "## See also\n\n"
        "- [Consent Management](/help/compliance-gdpr/consent-management)\n"
        "- [Retention Policies](/help/compliance-gdpr/retention-policies)",
        0,
    ),
    (
        "compliance-gdpr", "consent-management", "Consent Management",
        "Consent is the lawful basis most B2B SaaS use for outreach. "
        "OUTRENA tracks consent per prospect with a full audit trail "
        "of when/how consent was obtained, modified, or withdrawn.\n\n"
        "## Steps\n\n"
        "1. Open **Admin → GDPR Center → Consent** tab.\n"
        "2. View the consent dashboard: total prospects by status "
        "(granted / pending / withdrawn / denied).\n"
        "3. Each prospect's consent log shows: timestamp, channel "
        "(form, email, CSV import, API), lawful basis, IP, user agent.\n"
        "4. To bulk-update consent (e.g. after a re-permission "
        "campaign), use the API: `POST /api/v1/gdpr/consent/bulk`.\n"
        "5. Exclusion rules can be configured to auto-exclude "
        "`consent_status != 'granted'` — see [Exclusion Rules]"
        "(/help/admin-setup/exclusion-rules).\n\n"
        "## Tips\n\n"
        "- Default lawful basis for CSV imports is "
        "`legitimate_interest` (Article 6(1)(f)). Switch to `consent` "
        "if your jurisdiction requires it.\n"
        "- Withdrawal triggers an immediate soft-delete (anonymized=true) "
        "on the next retention tick.\n\n"
        "## See also\n\n"
        "- [Data Subject Requests](/help/compliance-gdpr/dsr-registry)\n"
        "- [Retention Policies](/help/compliance-gdpr/retention-policies)",
        1,
    ),
    (
        "compliance-gdpr", "retention-policies", "Retention Policies",
        "Retention policies define how long OUTRENA keeps each data "
        "type. Default policies match SOC2 + GDPR expectations; tenant "
        "admins can tighten but not loosen them.\n\n"
        "## Default policies\n\n"
        "- **Prospects (inactive 2y)** → anonymize\n"
        "- **Consent logs (3y)** → hard delete\n"
        "- **Email events (1y)** → hard delete\n"
        "- **Audit logs (7y)** → hard delete (SOC2)\n"
        "- **Support tickets resolved (1y)** → anonymize\n\n"
        "## Steps\n\n"
        "1. Open **Admin → GDPR Center → Retention** tab.\n"
        "2. View the active policies.\n"
        "3. Click any policy to tighten the retention window (e.g. "
        "reduce audit log retention from 7y to 5y — never increase "
        "beyond the SOC2-mandated max).\n"
        "4. Click **Run Now** to execute the policy immediately "
        "(otherwise runs nightly).\n"
        "5. View the **Run History** tab for past executions.\n\n"
        "## Tips\n\n"
        "- Anonymized prospects retain their aggregate metrics (reply "
        "rate, deal value) but lose all PII.\n"
        "- Hard-deleted rows are gone forever — no recovery.\n\n"
        "## See also\n\n"
        "- [Data Subject Requests](/help/compliance-gdpr/dsr-registry)\n"
        "- [Consent Management](/help/compliance-gdpr/consent-management)",
        2,
    ),
    (
        "compliance-gdpr", "usage-cost-tracking", "Usage and Cost Tracking",
        "The Usage page is REP-friendly (sees own usage), the tenant "
        "rollup is MANAGER+, and SUPER_ADMIN sees the platform-wide "
        "view. Costs derive from the Cost Table maintained by "
        "SUPER_ADMIN.\n\n"
        "## Steps (REP — own usage)\n\n"
        "1. Open **Usage** (any authenticated user).\n"
        "2. View your 30-day usage: LLM tokens, integration credits, "
        "email sends, daily quota consumed.\n"
        "3. Filter by usage type or date range.\n"
        "4. Compare to your quota — overages are flagged in red.\n\n"
        "## Steps (MANAGER+ — tenant rollup)\n\n"
        "1. Open **Usage** and switch to the **Team** tab.\n"
        "2. View per-rep usage + the team total.\n"
        "3. Click any rep to drill into their per-user dashboard.\n\n"
        "## Steps (TENANT_ADMIN — billing)\n\n"
        "1. Open **Setup → Billing → Usage**.\n"
        "2. View month-to-date spend broken down by usage type.\n"
        "3. Project end-of-month bill based on current burn rate.\n\n"
        "## Tips\n\n"
        "- Cost-per-unit comes from the platform Cost Table — see "
        "[Platform Usage & Cost Table]"
        "(/help/platform-admin/platform-usage).\n"
        "- Switch to tenant_managed mode for any integration to "
        "bypass OUTRENA's usage billing — see [Dual-Path Integrations]"
        "(/help/integrations/dual-path).\n\n"
        "## See also\n\n"
        "- [Per-User Sender Identities](/help/deliverability/per-user-sender-identities)\n"
        "- [Managing Your Subscription](/help/billing-rbac/managing-subscription)",
        3,
    ),
    (
        "compliance-gdpr", "soc2-overview", "SOC2 + Audit Trail Overview",
        "OUTRENA's compliance posture: SOC2 Type II audited annually. "
        "Every privileged action is logged to a tamper-evident audit "
        "trail. This article summarizes the controls relevant to "
        "tenant admins.\n\n"
        "## Controls in scope\n\n"
        "1. **Access control** — RBAC + per-tenant schema isolation.\n"
        "2. **Audit logging** — every privileged action; 7-year retention.\n"
        "3. **Encryption** — at rest (AES-256) + in transit (TLS 1.3).\n"
        "4. **Data retention** — automated per the Retention Policies.\n"
        "5. **Incident response** — PagerDuty integration, 1-hour SLA.\n"
        "6. **Change management** — every code change PR-reviewed + "
        "audit-logged deploys.\n\n"
        "## Steps (request a compliance report)\n\n"
        "1. Open **Admin → GDPR Center → Compliance** tab.\n"
        "2. Click **Request SOC2 Report**.\n"
        "3. Fill in the recipient email + NDA acknowledgement.\n"
        "4. SUPER_ADMIN will receive the request and email the report "
        "within 5 business days.\n\n"
        "## Tips\n\n"
        "- The DPA is available publicly at `/p/dpa`.\n"
        "- For custom compliance questions, open a support ticket with "
        "the `compliance` tag.\n\n"
        "## See also\n\n"
        "- [Audit Logs](/help/billing-rbac/audit-logs)\n"
        "- [Data Subject Requests](/help/compliance-gdpr/dsr-registry)",
        4,
    ),

    # ════════════════════════════════════════════════════════════════════════
    # support-help (3 articles)
    # ════════════════════════════════════════════════════════════════════════
    (
        "support-help", "open-ticket", "Opening a Support Ticket",
        "In-app support tickets route directly to OUTRENA's support "
        "team. Response SLA is 4 business hours; critical issues "
        "(sending-down, billing) get 1-hour SLA.\n\n"
        "## Steps\n\n"
        "1. Open **Support** (any authenticated user).\n"
        "2. Click **New Ticket**.\n"
        "3. Pick a category: billing, deliverability, bug, feature "
        "request, compliance.\n"
        "4. Set a severity: P0 (sending-down), P1 (degraded), P2 "
        "(question), P3 (feature request).\n"
        "5. Describe the issue. Attach screenshots if relevant.\n"
        "6. Click **Submit**. You'll receive an email confirmation.\n\n"
        "## Tips\n\n"
        "- P0 tickets page OUTRENA's on-call engineer directly.\n"
        "- Tickets can be linked to a specific campaign/prospect for "
        "faster context.\n\n"
        "## See also\n\n"
        "- [Using the Help Guide](/help/support-help/using-help-guide)\n"
        "- [Audit Logs](/help/billing-rbac/audit-logs)",
        0,
    ),
    (
        "support-help", "using-help-guide", "Using the Help Guide",
        "The Help Guide is context-aware: every section is "
        "role-filtered so you only see content relevant to your role. "
        "Deep-link URLs make it easy to share articles with teammates.\n\n"
        "## Steps\n\n"
        "1. Open **Help Guide** (sidebar top).\n"
        "2. Browse sections in the left rail, or use the **Search** "
        "box at the top.\n"
        "3. Click a section to load its articles.\n"
        "4. Click any article to expand it. The URL updates to "
        "`/help-guide/<section>/<article>` — copy-paste to share.\n"
        "5. Cross-links inside articles (e.g. \"See also: Managing "
        "Domains\") jump to the linked article.\n\n"
        "## Tips\n\n"
        "- Bookmark commonly-used articles in your browser.\n"
        "- If you can't find an answer, open a [Support Ticket]"
        "(/help/support-help/open-ticket).\n\n"
        "## See also\n\n"
        "- [Opening a Support Ticket](/help/support-help/open-ticket)\n"
        "- [Role Hierarchy](/help/billing-rbac/role-hierarchy)",
        1,
    ),
    (
        "support-help", "contact-support", "Other Ways to Contact Support",
        "Beyond in-app tickets, OUTRENA offers email, chat, and "
        "status-page channels for different urgency levels.\n\n"
        "## Channels\n\n"
        "1. **In-app ticket** — `/support` page (best for tracked "
        "issues with screenshots).\n"
        "2. **Email** — `support@outrena.com` (best for general "
        "questions).\n"
        "3. **Slack Connect** — for tenants on Enterprise plans, a "
        "dedicated Slack channel with the CSM.\n"
        "4. **Status page** — `status.outrena.com` for platform-wide "
        "incidents.\n"
        "5. **On-call** — P0 issues page OUTRENA's on-call engineer "
        "(via in-app ticket with severity=P0).\n\n"
        "## Tips\n\n"
        "- For billing disputes, always open an in-app ticket with "
        "category=billing — it routes to the billing team.\n"
        "- Feature requests are tracked publicly on the OUTRENA "
        "roadmap (linked from the Help Guide footer).\n\n"
        "## See also\n\n"
        "- [Opening a Support Ticket](/help/support-help/open-ticket)\n"
        "- [Using the Help Guide](/help/support-help/using-help-guide)",
        2,
    ),
]


# ── upgrade / downgrade ─────────────────────────────────────────────────────


def upgrade() -> None:
    schema = _s()
    # Help content lives exclusively in the public schema. Tenant-schema
    # migrations for 0008 are no-ops (no tenant-scoped help tables).
    if schema == "public":
        _upgrade_public()


def downgrade() -> None:
    schema = _s()
    if schema == "public":
        _downgrade_public()


# ── PUBLIC schema upgrade ────────────────────────────────────────────────────


def _upgrade_public() -> None:
    bind = op.get_bind()

    # Idempotency guard: the help_sections table must already exist
    # (created by 0003). If somehow it doesn't, bail out — operator
    # must run 0003 first.
    if not _table_exists(bind, "public", "help_sections"):
        raise RuntimeError(
            "public.help_sections table missing — run 0003_saas_platform "
            "before 0008_help_content_expansion."
        )

    _seed_help_sections(bind)
    _seed_help_section_roles(bind)
    _seed_help_articles(bind)


def _downgrade_public() -> None:
    """Downgrade: leave content in place.

    Removing 60 articles on downgrade is destructive (a tenant admin may
    have edited them via the admin UI). We log and no-op instead. To
    fully revert to the 0003 seed, manually `DELETE FROM help_articles`
    and re-run 0003's `_seed_help_content`.
    """
    op.get_bind().execute(
        text(
            "SELECT '0008_help_content_expansion downgrade: no-op "
            "(content left in place)' AS msg"
        )
    )


# ── Seeders (all idempotent) ─────────────────────────────────────────────────


def _seed_help_sections(bind) -> None:
    """Upsert sections by slug."""
    for slug, title, desc, sort, _min_role in _HELP_SECTIONS:
        bind.execute(
            text(
                "INSERT INTO public.help_sections "
                "(slug, title, description, sort_order) "
                "VALUES (:slug, :title, :desc, :sort) "
                "ON CONFLICT (slug) DO UPDATE SET "
                "  title = EXCLUDED.title, "
                "  description = EXCLUDED.description, "
                "  sort_order = EXCLUDED.sort_order"
            ),
            {"slug": slug, "title": title, "desc": desc, "sort": sort},
        )


def _seed_help_section_roles(bind) -> None:
    """Insert role-gate rows for sections with min_role != None.

    Idempotent: ON CONFLICT (section_id, min_role) DO NOTHING. To remove
    a gate (e.g. tenant admin lowers a section's min_role), a future
    migration must explicitly DELETE the row.
    """
    for slug, _title, _desc, _sort, min_role in _HELP_SECTIONS:
        if min_role is None:
            continue
        row = bind.execute(
            text("SELECT id FROM public.help_sections WHERE slug = :slug"),
            {"slug": slug},
        ).fetchone()
        if row is None:
            continue
        bind.execute(
            text(
                "INSERT INTO public.help_section_roles "
                "(section_id, min_role) VALUES (:sid, :role) "
                "ON CONFLICT (section_id, min_role) DO NOTHING"
            ),
            {"sid": row.id, "role": min_role},
        )


def _seed_help_articles(bind) -> None:
    """Upsert articles by (section_id, slug)."""
    # Pre-fetch section IDs to avoid N+1 queries.
    section_id_map: dict[str, int] = {
        row.slug: row.id
        for row in bind.execute(
            text("SELECT id, slug FROM public.help_sections")
        ).fetchall()
    }
    for sec_slug, art_slug, title, body, sort in _HELP_ARTICLES:
        sid = section_id_map.get(sec_slug)
        if sid is None:
            continue
        existing = bind.execute(
            text(
                "SELECT id FROM public.help_articles "
                "WHERE section_id = :sid AND slug = :slug"
            ),
            {"sid": sid, "slug": art_slug},
        ).fetchone()
        if existing is None:
            bind.execute(
                text(
                    "INSERT INTO public.help_articles "
                    "(section_id, slug, title, body, sort_order) "
                    "VALUES (:sid, :slug, :title, :body, :sort)"
                ),
                {
                    "sid": sid,
                    "slug": art_slug,
                    "title": title,
                    "body": body,
                    "sort": sort,
                },
            )
        else:
            bind.execute(
                text(
                    "UPDATE public.help_articles "
                    "SET title = :title, body = :body, sort_order = :sort "
                    "WHERE id = :id"
                ),
                {
                    "title": title,
                    "body": body,
                    "sort": sort,
                    "id": existing.id,
                },
            )


__all__ = ["revision", "down_revision", "upgrade", "downgrade"]
