---
title: GDPR Compliance Runbook
last_updated: 2025-01-07
severity: SEV-1
owner: OUTRENA Data Protection Officer (DPO)
related_runbooks: [05-incident-response, 08-disaster-recovery, 10-soc2-compliance, 11-secrets-management, 13-data-subject-requests]
---

# GDPR Compliance Runbook

Operationalises the OUTRENA General Data Protection Regulation (GDPR)
compliance program against EU Regulation 2016/679. Each section maps to a
specific GDPR article or chapter and lists the implementation artefacts
(files, endpoints, procedures) that satisfy it.

This runbook closes the GDPR gaps identified in SURVEY-GDPR (worklog
entry SAAS2-GDPR-BE). All referenced code was added by SAAS2-GDPR-BE.

## Prerequisites

- Operator is the OUTRENA DPO or a deputy on the @security-team.
- Operator has SUPER_ADMIN access to the OUTRENA platform (for /gdpr/platform/*
  and /retention/* endpoints) and read access to the production DB.
- Operator has access to the breach-notification template (runbook
  05-incident-response §data-breach) and to the DPO mailbox
  (dpo@outrena.io — see env var DPO_EMAIL).
- Operator has reviewed `docs/ropa-outrena.md` (Record of Processing
  Activities — Article 30) and `docs/dpia-outrena.md` (Data Protection
  Impact Assessment — Article 35).

## 1. Scope + Applicability

### Who is a data subject?

A natural person who can be identified, directly or indirectly, by PII
OUTRENA processes. OUTRENA processes PII for the following data-subject
categories:

| Category | PII processed | Source |
|----------|---------------|--------|
| Prospects (B2B leads) | First name, last name, email, title, company, domain, LinkedIn URL | CSV import, prospecting integrations (Apollo, Clay, LinkedIn Sales Nav) |
| Tenant users (platform users) | First name, last name, email, role | Keycloak (identity provider) |
| Support ticket authors | User ID, message body, attachments | In-app support form |
| Contact-form submitters | Name, email, company, message | Public landing page (/api/v1/public/contact) |
| DSR submitters | Email, request details | Public DSR endpoint (/api/v1/gdpr/dsr) |

### What data do we process?

See `docs/ropa-outrena.md` for the full Article 30 register. Summary:

- **Prospect PII**: name, email, title, company, domain, LinkedIn URL.
  Stored encrypted at rest (PiiService / Fernet via ENCRYPTION_KEY) in
  the tenant schema `Prospect` table.
- **Email engagement**: opens, clicks, bounces (Sequence table in tenant
  schema; per-touch fields).
- **LLM processing**: prospect data is sent to LLM providers (OpenAI,
  Anthropic, ZAI) for email generation, ICP scoring, meeting prep
  briefs. LLM API keys are encrypted at rest in `LlmConfig.apiKey`.
- **Audit log**: every mutation + every PII read (Article 30) is
  recorded in `public.platform_audit_log` (7-year retention).
- **Billing**: Stripe customer ID + invoice history (public.subscriptions
  + Stripe); OUTRENA does NOT store full card numbers (PCI out of scope).

### Territorial scope

OUTRENA is based in the United States. All production data is stored in
AWS us-east-1 + Azure eastus (see terraform/aws + terraform/azure). EU
data subjects' PII is therefore subject to cross-border transfer rules
(see §9 below).

## 2. Lawful Bases (Article 6)

OUTRENA relies on the following lawful bases for each processing activity:

| Processing activity | Lawful basis | Article 6(1)(?) | Notes |
|---------------------|--------------|-----------------|-------|
| B2B prospecting outreach | Legitimate interest | (f) | Default for all Prospect rows (`lawful_basis='legitimate_interest'`). LIA on file in `docs/dpia-outrena.md`. |
| Marketing email to prospects who opted in | Consent | (a) | `lawful_basis='consent'` + `consent_status='granted'`. Recorded in `consents` table. |
| Sending platform transactional emails (welcome, password reset) | Contract | (b) | Necessary to deliver the service the user signed up for. |
| Billing + invoicing | Legal obligation | (c) | Tax-record retention (7 years). |
| Security monitoring + audit logging | Legitimate interest | (f) | Securing the platform against abuse. |
| DSR processing | Legal obligation | (c) | GDPR Article 12(3) — must respond to requests. |

When `lawful_basis='consent'`, the prospect's `consent_status` field
MUST be `granted` before any outbound action (email send, LinkedIn
outreach). The pre-flight check lives in
`ProspectService.check_consent()` — callers MUST invoke it before any
outbound action and BLOCK if it returns False.

## 3. Data Subject Rights (Articles 15-22)

OUTRENA supports the six GDPR data subject rights. Each right is
implemented via a specific endpoint in `app/api/v1/gdpr.py` and a
processor in `app/services/gdpr_service.py`. SLA: 30 days from receipt
to completion (Article 12(3)).

| Right | Article | Endpoint | Processor | SLA |
|-------|---------|----------|-----------|-----|
| Access | 15 | POST /gdpr/dsr (request_type=access) → GET /gdpr/export/{dsr_id} | `GdprService.process_access_request` | 30 days |
| Portability | 20 | POST /gdpr/dsr (request_type=portability) → GET /gdpr/export/{dsr_id}?format=json | `GdprService.process_portability_request` | 30 days |
| Rectification | 16 | POST /gdpr/dsr (request_type=rectification) | `GdprService.process_rectification_request` | 30 days |
| Erasure | 17 | POST /gdpr/dsr (request_type=erasure) | `GdprService.process_erasure_request` | 30 days |
| Restriction | 18 | POST /gdpr/dsr (request_type=restriction) | `GdprService.process_restriction_request` | 30 days |
| Objection | 21 | POST /gdpr/dsr (request_type=objection) | `GdprService.process_objection_request` | 30 days |

Detailed per-right procedures are in `runbooks/13-data-subject-requests.md`.

## 4. DSR Handling Procedure

```
┌──────────────────────────────────────────────────────────────────────┐
│ Day 0  — data subject submits DSR via POST /api/v1/gdpr/dsr          │
│         (no auth required; status=pending; DSR row created in        │
│         public.data_subject_requests)                                │
├──────────────────────────────────────────────────────────────────────┤
│ Day 1  — DPO receives Slack alert (#gdpr-dsr channel via SNS)        │
│         DPO acknowledges receipt via email template                  │
│         (runbook 13 §email-templates — acknowledgement)              │
│         SLA: acknowledgement within 3 days (GDPR_DSR_ACKNOWLEDGE_DAYS)│
├──────────────────────────────────────────────────────────────────────┤
│ Day 2  — DPO verifies data subject identity (runbook 13 §identity)   │
│         DPO assigns DSR to themselves (POST /gdpr/dsrs/{id}/process) │
├──────────────────────────────────────────────────────────────────────┤
│ Day 3  — DPO triggers processing (POST /gdpr/dsrs/{id}/process)      │
│         Dispatcher routes to the right processor (access / erasure / │
│         portability / rectification / objection / restriction)       │
├──────────────────────────────────────────────────────────────────────┤
│ Day 4  — DPO reviews the export bundle (GET /gdpr/export/{id})       │
│         DPO redacts third-party PII if necessary (e.g. email         │
│         bodies that quote other people)                              │
├──────────────────────────────────────────────────────────────────────┤
│ Day 5  — DPO marks the DSR complete (POST /gdpr/dsrs/{id}/complete)  │
│         DPO sends the completion email (runbook 13 §email-templates) │
│         with a link to the export bundle                             │
├──────────────────────────────────────────────────────────────────────┤
│ Day 30 — SLA deadline. If still open, escalate to DPO lead.          │
└──────────────────────────────────────────────────────────────────────┘
```

SLA tracking: the DSR `created_at` timestamp is the start of the SLA
clock. The DPO dashboard (GET /gdpr/platform/dsrs) shows open DSRs
sorted by age; any DSR older than 25 days without `assigned_to` set
triggers a P1 PagerDuty alert (configured in the DPO dashboard cron).

## 5. Consent Management (Article 7)

### Recording consent

Consent is recorded via `POST /api/v1/gdpr/consent/grant` (any
authenticated user) or `POST /api/v1/prospects/{id}/consent/grant`
(tied to a specific prospect). The `consents` table captures:

- `prospect_id` (FK to Prospect)
- `email` (denormalised for cross-prospect lookups)
- `lawful_basis` (consent / legitimate_interest / contract / ...)
- `consent_status` (granted / withdrawn / pending)
- `consent_text` (the EXACT text the data subject agreed to — for audit)
- `ip_address` + `user_agent` (provenance — Article 7(1))
- `granted_at` + `withdrawn_at`

Every grant / withdrawal / renewal is appended to the immutable
`consent_logs` table (action + details JSON + timestamp). Consent
history is NEVER overwritten in place.

### Withdrawing consent

`POST /api/v1/gdpr/consent/withdraw` (any auth user) or
`POST /api/v1/prospects/{id}/consent/withdraw`. Withdrawal:

1. Sets `consents.consent_status='withdrawn'` + `withdrawn_at=now()`.
2. Appends a `ConsentLog(action='withdrawn')` entry.
3. Sets `Prospect.consent_status='withdrawn'` + `suppressed=true` +
   `suppressionReason='consent_withdrawn'` + `suppressedAt=now()`.
4. The scheduler (scheduler_service) checks `suppressed=true` before
   every outbound email — suppressed prospects are skipped.

### Renewing consent

If a previously-withdrawn consent is re-granted, the same `consents` row
is updated (`consent_status='granted'`, `granted_at=now()`,
`withdrawn_at=NULL`) and a new `ConsentLog(action='renewed')` entry is
appended. The full history is preserved in `consent_logs`.

## 6. Data Retention Schedule (Article 5(1)(e))

Retention is enforced by `app/services/retention_service.py` and the
policies are stored in `public.retention_policies` (seeded by migration
0007). The schedule:

| Data type | Retention period | Action after period | Scope | Policy name |
|-----------|------------------|---------------------|-------|-------------|
| Inactive prospects | 2 years (730d) | Anonymise (PII → `[anonymized]`; row kept for stats) | Tenant | prospects_inactive |
| Consent logs | 3 years (1095d) | Hard-delete | Tenant | consent_logs |
| Email engagement events | 1 year (365d) | Hard-delete | Tenant | email_events |
| Audit logs | 7 years (2555d) | Hard-delete | Public | audit_logs |
| Resolved support tickets | 1 year (365d) | Anonymise | Tenant | support_tickets_resolved |

### Enforcement

- Manual: `POST /api/v1/retention/enforce` (SUPER_ADMIN) runs across all
  active tenants. Returns per-tenant affected counts.
- Per-tenant: `POST /api/v1/gdpr/retention/enforce` (TENANT_ADMIN) runs
  only the caller's tenant.
- Automated (recommended): a Celery beat task should run
  `RetentionService.enforce_all_policies(slug)` for every active tenant
  nightly. (Out of scope for SAAS2-GDPR-BE — wiring the Celery task is
  owned by the scheduler agent.)

### Status (dry-run)

`GET /api/v1/retention/status` (SUPER_ADMIN) or
`GET /api/v1/gdpr/retention-status` (TENANT_ADMIN) returns the count of
rows that WOULD be affected by each policy if enforcement ran now. Use
this to spot-check before triggering enforcement.

### Overriding a policy

`PUT /api/v1/retention/policies/{name}` lets the DPO override
`days` / `action` / `description` for any policy without a code deploy.
The override is persisted in `public.retention_policies` and takes
precedence over the in-memory defaults in `RetentionService.RETENTION_POLICIES`.

## 7. Data Protection by Design (Article 25)

### PII encryption at rest

PII fields on Prospect (`firstName`, `lastName`, `email`) are encrypted
at rest with Fernet (symmetric authenticated encryption) via
`app/services/pii_service.py`. The encryption key is
`ENCRYPTION_KEY` (env var; generate with `python -c "from
cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).

- On WRITE (create/update): PiiService encrypts PII before persisting.
- On READ (get/list): PiiService decrypts PII before returning.
- Transparent to existing code — no schema change required (columns
  stay VARCHAR).
- Dev fallback: if `ENCRYPTION_KEY` is empty, PiiService passes values
  through unchanged (with a logged warning). Production MUST set the key
  (the `audit_env.py` pre-deploy script enforces this).

### Access controls

- 4-role hierarchy: REP → MANAGER → TENANT_ADMIN → SUPER_ADMIN.
- DSR processing + retention enforcement require TENANT_ADMIN or higher.
- Cross-tenant operations (platform DSR list, retention across tenants)
  require SUPER_ADMIN.
- Per-feature permission keys (RBAC) — see `public.permissions` table.

### Audit logging (Article 30)

- Mutations (POST/PUT/PATCH/DELETE) are logged automatically by
  `app/middleware/audit_middleware.py`.
- GET reads of PII-bearing paths (`/api/v1/prospects`, `/api/v1/users`,
  `/api/v1/gdpr/export`, `/api/v1/gdpr/consent`, `/api/v1/support/tickets`)
  are also logged (action=`GET <path>`). Governed by
  `AUDIT_LOG_PII_READS` env var (default true; set false to disable).
- Audit log rows are stored in `public.platform_audit_log` (7-year
  retention per SOC2).

## 8. Breach Notification (Article 33-34)

### 72-hour procedure (Article 33 — supervisory authority)

Personal-data breach notification to the supervisory authority MUST
happen within 72 hours of becoming aware of the breach.

```
Hour 0   — On-call engineer declares SEV-1 (runbook 05-incident-response).
Hour 0   — PagerDuty page to @security-team + DPO.
Hour 1   — DPO confirms the incident involves personal data
           (PII exposure, unauthorised access, loss).
Hour 2   — DPO drafts the breach notification (template:
           runbook 05 §data-breach-notification-template).
           Fields required by Article 33(3):
             - Nature of the breach
             - DPO contact (DPO_EMAIL env var)
             - Likely consequences
             - Measures taken or proposed
Hour 4   — DPO files the notification with the lead supervisory
           authority (Ireland DPC for EU — OUTRENA's lead EU authority).
Hour 72  — HARD DEADLINE. If the notification has not been filed,
           escalate to OUTRENA CEO + outside counsel.
```

### Affected-data-subject notification (Article 34)

If the breach is "likely to result in a high risk to the rights and
freedoms of natural persons", the data subjects MUST be notified "without
undue delay" (no fixed hour deadline, but "as soon as possible"). The
DPO decides whether Article 34 applies based on the breach severity
matrix in runbook 05 §data-breach-severity-matrix.

### Communication channels

- Supervisory authority: via the DPC online breach notification form
  (https://www.dataprotection.ie/en/organisations/know-your-obligations/breach-notification).
- Data subjects: via email to the affected emails (runbook 13
  §email-templates — breach-notification-to-subjects).
- Internal: Slack #incident-{sev}, PagerDuty, status page
  (status.outrena.com) for customer-impacting incidents.

## 9. Cross-Border Transfers (Chapter V)

### Current state

All production data is stored in:
- AWS us-east-1 (RDS Postgres, ElastiCache Redis, S3 collateral).
- Azure eastus (Postgres Flexible Server, Redis, App Gateway).

EU data subjects' PII therefore undergoes a cross-border transfer from
the EU to the United States. The legal mechanism is **Standard
Contractual Clauses (SCCs)** — OUTRENA signed the EU Commission's 2021
SCCs with each sub-processor (AWS, Azure, Stripe, Keycloak host, LLM
providers).

### Sub-processor list (Article 28)

See `docs/ropa-outrena.md` §sub-processors for the full list. Summary:

| Sub-processor | Purpose | DPA reference | SCCs |
|---------------|---------|---------------|------|
| AWS | Hosting (RDS, S3, ElastiCache) | https://aws.amazon.com/compliance/eu-us-privacy-shield-faq/ | Yes (2021 SCCs) |
| Azure | Hosting (Postgres, Redis, App Gateway) | https://www.microsoft.com/licensing/docs/view/Microsoft-Products-and-Services-Data-Protection | Yes (2021 SCCs) |
| Stripe | Billing (subscriptions, invoices) | https://stripe.com/privacy | Yes (2021 SCCs) |
| Keycloak (self-hosted on AWS) | Identity provider | N/A (self-hosted) | N/A |
| OpenAI | LLM provider (email generation, ICP scoring) | https://openai.com/policies/privacy-policy | Yes (2021 SCCs) |
| Anthropic | LLM provider (Claude) | https://www.anthropic.com/legal/privacy | Yes (2021 SCCs) |
| ZAI (in-house) | LLM provider (default — no API key required) | N/A (in-house) | N/A |

### Future state (EU data residency)

Customer demand may require an EU region (eu-west-1 on AWS,
eu-west-europe on Azure). The terraform modules support this via the
`region` variable — see terraform/aws/envs/prod/prod.tfvars and
terraform/azure/envs/prod/prod.tfvars. When an EU region is stood up,
EU customers' tenants will be provisioned in EU schemas (separate
public.tenants rows with `region='eu'` column — schema change required).

## 10. Sub-processors

See §9 table above. The full Article 28 DPA register is in
`docs/ropa-outrena.md` §sub-processors. New sub-processors require:

1. DPA signed by OUTRENA + the sub-processor (Article 28(3)).
2. SCCs if the sub-processor is outside the EU/EEA.
3. Update to `docs/ropa-outrena.md` §sub-processors.
4. Update to the public privacy policy (`PrivacyPage.tsx` — frontend).
5. 30-day advance notice to data subjects (Article 28(2) — via email
   to all tenant admins + DPO blog post).

## 11. DPO Contact + Responsibilities

**DPO email**: `DPO_EMAIL` env var (default `dpo@outrena.io`).
**DPO role**: SUPER_ADMIN on the OUTRENA platform.
**DPO responsibilities** (Article 39):

1. Monitor GDPR compliance across OUTRENA.
2. Advise on Data Protection Impact Assessments (DPIAs — Article 35).
3. Cooperate with + act as contact point for supervisory authorities.
4. Be the contact point for data subjects exercising their rights
   (DSR submissions route to the DPO mailbox).
5. Report to OUTRENA highest management level (CEO).

The DPO is involved "in a proper manner, at an early stage" in all
issues relating to the protection of personal data (Article 38(1)).

## 12. ROPA reference

The full Article 30 Record of Processing Activities is in
`docs/ropa-outrena.md`. It enumerates every processing activity
(prospect data, user data, email tracking, LLM processing, analytics,
billing, support, audit logs, backups) with purpose, lawful basis,
data categories, recipients, retention, and transfer mechanism.

## 13. DPIA reference

The Article 35 Data Protection Impact Assessment is in
`docs/dpia-outrena.md`. It covers:

- Processing description (B2B sales outreach platform)
- Necessity + proportionality assessment
- Risk assessment (PII exposure, unauthorised access, data leakage)
- Mitigations (encryption, access controls, audit, retention)
- DPO sign-off section
- Annual review schedule

A new DPIA is required when:
- A new processing activity is introduced that is "likely to result in
  a high risk to the rights and freedoms of natural persons" (Article
  35(1)).
- An existing processing activity is materially changed (new data
  category, new sub-processor, new transfer mechanism).

## 14. Quarterly Compliance Checklist

The DPO runs this checklist at the start of each quarter. Each item
must be PASS or have an open JIRA ticket with a target close date.

### Article 30 — Records of processing

- [ ] `docs/ropa-outrena.md` reviewed + updated with any new processing
      activities from the last quarter.
- [ ] `public.platform_audit_log` last 90 days spot-checked for PII
      reads (GET /api/v1/prospects) — verify every read has a
      legitimate business purpose.

### Article 32 — Security of processing

- [ ] ENCRYPTION_KEY rotated (runbook 11-secrets-management §rotation).
- [ ] All tenant schemas have `Prospect.deleted_at` index (verifiable
      via `scripts/verify_schema_health.py`).
- [ ] No SUPER_ADMIN tokens older than 90 days (Keycloak token revocation).

### Articles 15-22 — Data subject rights

- [ ] All DSRs from the previous quarter are `completed` or `rejected`
      with a documented reason (GET /gdpr/platform/dsrs?status=pending
      returns 0 rows).
- [ ] Average DSR completion time < 14 days (SQL:
      `SELECT AVG(completed_at - created_at) FROM public.data_subject_requests
       WHERE status='completed' AND created_at > now() - interval '90 days'`).

### Article 33-34 — Breach notification

- [ ] Tabletop exercise run (runbook 05 §tabletop) — 1 hour scenario.
- [ ] Breach-notification template (runbook 05 §data-breach) reviewed
      + updated with any regulatory changes.

### Article 5(1)(e) — Retention

- [ ] `POST /api/v1/retention/enforce` run (SUPER_ADMIN) — verify
      per-tenant counts match the dry-run from `GET /retention/status`.
- [ ] No retention policy overrides in `public.retention_policies` that
      exceed regulatory minimums (e.g. audit_logs < 7y is non-compliant).

### Sub-processor management (Article 28)

- [ ] Every sub-processor's DPA is current (no expirations in the next
      90 days).
- [ ] Privacy page (`PrivacyPage.tsx`) sub-processor list matches
      `docs/ropa-outrena.md` §sub-processors.

### DPIA + ROPA

- [ ] `docs/dpia-outrena.md` annual review signed off by the DPO.
- [ ] No new processing activities introduced without a DPIA update.

## See Also

- `runbooks/13-data-subject-requests.md` — detailed DSR processing runbook
- `runbooks/05-incident-response.md` — breach-notification procedure
- `runbooks/10-soc2-compliance.md` — SOC2 audit-log retention overlap
- `docs/ropa-outrena.md` — Article 30 register
- `docs/dpia-outrena.md` — Article 35 DPIA
- `app/api/v1/gdpr.py` — GDPR router
- `app/api/v1/retention.py` — retention router
- `app/services/gdpr_service.py` — DSR + consent + export service
- `app/services/pii_service.py` — PII encryption
- `app/services/retention_service.py` — retention enforcement
- `app/middleware/audit_middleware.py` — PII-read audit logging
