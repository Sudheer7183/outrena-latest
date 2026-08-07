---
title: Data Subject Requests (DSR) Processing Runbook
last_updated: 2025-01-07
severity: SEV-2
owner: OUTRENA Data Protection Officer (DPO)
related_runbooks: [12-gdpr-compliance, 05-incident-response]
---

# Data Subject Requests (DSR) Processing Runbook

Step-by-step procedure for handling GDPR data-subject requests (Articles
15-22). The DPO (or a deputy) follows this runbook for every DSR
received via `POST /api/v1/gdpr/dsr` or via email to `DPO_EMAIL`.

## Prerequisites

- Operator is the OUTRENA DPO or a deputy on the @security-team.
- Operator has SUPER_ADMIN access to the OUTRENA platform.
- Operator has reviewed `runbooks/12-gdpr-compliance.md` §4 (DSR
  handling procedure overview) and `docs/ropa-outrena.md` (to know what
  data we hold).
- Operator has the email templates loaded in their mail client
  (§email-templates below).

## SLAs

| Milestone | SLA | Article | Tracking |
|-----------|-----|---------|----------|
| Acknowledge receipt | 3 days (`GDPR_DSR_ACKNOWLEDGE_DAYS`) | Art 12(3) | DPO sends acknowledgement email |
| Complete the request | 30 days (`GDPR_DSR_COMPLETION_DAYS`) | Art 12(3) | DSR `completed_at` timestamp |
| Notify extension | Before 30-day deadline | Art 12(3) | DPO emails the data subject with reason + new deadline (max +60 days) |

Extensions are permitted only for "complex requests" — the DPO MUST
document the complexity reason in the DSR `completion_notes` field.

## Identity Verification

Before processing ANY DSR, the DPO MUST verify the requester's identity
(Article 12(6)). Acceptable verification:

| Request channel | Verification required |
|-----------------|----------------------|
| Email to DPO_EMAIL from the data subject's email on file | Sufficient (the email itself is the proof). |
| Email to DPO_EMAIL from a different email | Reply to the on-file email + ask the requester to confirm from there. |
| Public DSR endpoint (POST /gdpr/dsr) | DPO emails the on-file email with a unique verification link (24h expiry). Requester clicks → identity verified. |
| Third-party request (agent acting for data subject) | Written authorisation from the data subject (scan + reply-to verification). |

**If identity cannot be verified within 7 days**, reject the DSR with
reason `"Could not verify identity within 7 days."` (POST /gdpr/dsrs/{id}/reject).

## Per-Right Procedures

### 1. Right of Access (Article 15)

**Request type**: `access`
**Trigger**: `POST /gdpr/dsr` body `{email, request_type:"access"}`

**Steps**:
1. Verify identity (§identity-verification).
2. Assign DSR to yourself: the DSR moves to `status=in_progress` when
   processing is triggered.
3. Trigger processing: `POST /api/v1/gdpr/dsrs/{id}/process` (TENANT_ADMIN).
   - The service calls `GdprService.process_access_request(dsr)` which
     sets `export_url=/api/v1/gdpr/export/{dsr_id}`.
4. Review the export bundle: `GET /api/v1/gdpr/export/{dsr_id}` (TENANT_ADMIN).
   - The bundle includes: prospect record, consent records + logs,
     sequence touches (email engagement), campaign memberships, deals,
     reply drafts, meeting prep briefs, meetings, call logs, job-change
     alerts, support tickets, DSR history.
5. Redact third-party PII if necessary (e.g. email bodies that quote
   other people — replace with `[redacted — third-party PII]`).
6. Complete the DSR: `POST /api/v1/gdpr/dsrs/{id}/complete` with
   `notes="Export bundle delivered via signed URL."`.
7. Send the completion email (§email-templates — access-completion)
   with a link to the export bundle. The link is the `export_url` field.

**Output**: JSON export bundle (also available as CSV via the script
`scripts/gdpr-data-export.py`).

### 2. Right to Portability (Article 20)

**Request type**: `portability`
**Trigger**: `POST /gdpr/dsr` body `{email, request_type:"portability"}`

Same procedure as Access (above), but:
- The export is JSON ONLY (no CSV).
- The export_url includes `?format=json`.
- The data subject is told they can import this JSON into another
  OUTRENA tenant or a competing platform.

The scope is narrower than Access — portability covers only data the
subject PROVIDED to OUTRENA (name, email, title, company, etc.), not
data OUTRENA derived (ICP scores, enrichment data, intent signals). The
DPO may need to manually filter the export bundle before delivery.

### 3. Right to Rectification (Article 16)

**Request type**: `rectification`
**Trigger**: `POST /gdpr/dsr` body `{email, request_type:"rectification", details:{corrections:{firstName:"Jane", ...}}}`

**Steps**:
1. Verify identity.
2. Trigger processing: `POST /api/v1/gdpr/dsrs/{id}/process`.
   - The service calls `GdprService.process_rectification_request(dsr,
     corrections)` which UPDATEs the Prospect row.
   - Only whitelisted fields can be rectified: `firstName`, `lastName`,
     `email`, `title`, `company`, `domain`.
   - PII fields are re-encrypted at rest via PiiService.
3. Complete the DSR with `notes="Prospect rectified: <fields>"`.
4. Send completion email (§email-templates — rectification-completion)
   confirming the fields that were updated.

**Edge case**: if the data subject requests rectification of a derived
field (e.g. `qaScore`, `icpFitScore`), reject with reason `"Derived
fields cannot be rectified — they are recomputed by the platform. The
underlying data has been verified as accurate."`.

### 4. Right to Erasure (Article 17)

**Request type**: `erasure`
**Trigger**: `POST /gdpr/dsr` body `{email, request_type:"erasure"}`

**Steps**:
1. Verify identity.
2. Confirm the data subject's grounds for erasure (Article 17(1)(a)-(f)).
   OUTRENA may refuse if processing is necessary for:
   - Compliance with a legal obligation (Art 17(3)(b) — tax records).
   - Establishment, exercise or defence of legal claims (Art 17(3)(e)).
   - Public interest (Art 17(3)(d) — unlikely for OUTRENA).
3. Trigger processing: `POST /api/v1/gdpr/dsrs/{id}/process`.
   - The service calls `GdprService.process_erasure_request(dsr)` which:
     - Sets `Prospect.firstName='[anonymized]'`, `lastName='[anonymized]'`,
       `email='[anonymized]'`, `linkedinUrl=NULL`, `notes=NULL`.
     - Sets `Prospect.deleted_at=now()`, `anonymized=true`,
       `consent_status='withdrawn'`.
   - The row is RETAINED for FK integrity (campaigns, sequences, deals
     reference it) and for aggregate stats rendered anonymous (Art 17(3)(e)).
4. Complete the DSR with `notes="Prospect anonymised. PII purged; row
   retained for aggregate stats per Art 17(3)(e)."`.
5. Send completion email (§email-templates — erasure-completion).

**Edge case — also delete from sub-processors**: if the data subject
asks for erasure from "all systems", the DPO must additionally:
- Email OpenAI / Anthropic to request deletion of the prospect's data
  from their training logs (per the sub-processor DPAs).
- Stripe customer records are retained for 7 years (tax-law obligation,
  Art 17(3)(b)) — explain this in the completion email.
- AWS / Azure backups: the prospect's data exists in RDS PITR backups
  for 35 days; explain this in the completion email.

### 5. Right to Restriction (Article 18)

**Request type**: `restriction`
**Trigger**: `POST /gdpr/dsr` body `{email, request_type:"restriction"}`

**Steps**:
1. Verify identity.
2. Confirm the data subject's grounds for restriction (Art 18(1)(a)-(d)).
3. Trigger processing: `POST /api/v1/gdpr/dsrs/{id}/process`.
   - The service calls `GdprService.process_restriction_request(dsr)`
     which sets `Prospect.consent_status='withdrawn'`,
     `suppressed=true`, `suppressionReason='gdpr_restriction'`.
   - The scheduler (scheduler_service) skips suppressed prospects for
     all outbound actions.
4. Complete the DSR with `notes="Processing restricted. Outbound
   actions blocked; data retained."`.
5. Send completion email (§email-templates — restriction-completion).

**Note**: restriction does NOT anonymise the data — the row is retained
in full. The data subject can later request erasure (Article 17) or
consent renewal (Article 7) to lift the restriction.

### 6. Right to Object (Article 21)

**Request type**: `objection`
**Trigger**: `POST /gdpr/dsr` body `{email, request_type:"objection"}`

**Steps**:
1. Verify identity.
2. Determine the processing the subject objects to:
   - Direct marketing (Art 21(2)) — MUST stop immediately, no
     balancing test.
   - Other processing (Art 21(1)) — DPO conducts a balancing test:
     do OUTRENA's legitimate interests override the subject's rights?
     Document the test result in the DSR `completion_notes`.
3. Trigger processing: `POST /api/v1/gdpr/dsrs/{id}/process`.
   - The service calls `GdprService.process_objection_request(dsr)`
     which suppresses the prospect (same as restriction).
4. Complete the DSR with `notes="Prospect suppressed (objection).
   Outbound marketing stopped."`.
5. Send completion email (§email-templates — objection-completion).

## Email Templates

All templates use `{{data_subject_name}}`, `{{dpo_email}}`, `{{export_url}}`,
`{{fields}}`, `{{reason}}`, and `{{new_deadline}}` placeholders.

### dsr-acknowledgement

```
Subject: Your data subject request — received

Dear {{data_subject_name}},

We have received your data subject request submitted on {{submitted_at}}.

OUTRENA will process your request and respond within 30 days, as required
by Article 12(3) of the General Data Protection Regulation (GDPR). If we
need more time (up to an additional 60 days), we will let you know within
the first 30 days with the reason for the extension.

If you have any questions in the meantime, please reply to this email or
contact our Data Protection Officer at {{dpo_email}}.

Reference: DSR-{{dsr_id}}

Kind regards,
OUTRENA Data Protection Team
```

### access-completion

```
Subject: Your data subject request — access completed

Dear {{data_subject_name}},

Your data subject access request (DSR-{{dsr_id}}) has been completed.

A copy of the personal data OUTRENA holds about you is available at the
following link (valid for 7 days):

  {{export_url}}

The export is in JSON format and includes:
  - Your prospect profile
  - Consent records and history
  - Email engagement events (opens, clicks, replies, bounces)
  - Campaign memberships and sequence touches
  - Deals, reply drafts, meeting prep briefs, meetings, call logs
  - Job-change alerts
  - Support ticket history
  - Prior DSR history

If you have any questions about the data in this export, please reply to
this email or contact our Data Protection Officer at {{dpo_email}}.

Kind regards,
OUTRENA Data Protection Team
```

### portability-completion

```
Subject: Your data subject request — portability completed

Dear {{data_subject_name}},

Your data portability request (DSR-{{dsr_id}}) has been completed.

A machine-readable JSON export of the personal data you provided to
OUTRENA is available at the following link (valid for 7 days):

  {{export_url}}

This export contains only data you provided to OUTRENA (name, email,
title, company, domain). It does not include data OUTRENA derived
(scores, intent signals, enrichment data). The JSON is structured for
import into another OUTRENA tenant or a competing platform.

If you have any questions, please reply to this email or contact our
Data Protection Officer at {{dpo_email}}.

Kind regards,
OUTRENA Data Protection Team
```

### rectification-completion

```
Subject: Your data subject request — rectification completed

Dear {{data_subject_name}},

Your data rectification request (DSR-{{dsr_id}}) has been completed.

The following fields have been updated:
{{fields}}

All other fields were verified as accurate and remain unchanged. If you
believe any other field is inaccurate, please reply with the specific
corrections and we will process a follow-up rectification request.

Kind regards,
OUTRENA Data Protection Team
```

### erasure-completion

```
Subject: Your data subject request — erasure completed

Dear {{data_subject_name}},

Your right-to-erasure request (DSR-{{dsr_id}}) has been completed.

OUTRENA has anonymised your personal data in our production database.
Specifically:
  - Your name, email, LinkedIn URL, and notes have been replaced with
    "[anonymized]".
  - Your prospect record has been soft-deleted (no longer appears in
    lists, exports, or outreach queues).
  - Your consent has been marked as withdrawn.

Please note the following exemptions under Article 17(3) of the GDPR:
  - Aggregate statistics derived from your data prior to erasure are
    retained (Art 17(3)(e)) — these are anonymous and cannot identify you.
  - Tax-related billing records (if you were a paying customer) are
    retained for 7 years (Art 17(3)(b)) — required by US tax law.
  - Your data may exist in database backups for up to 35 days (the RDS
    PITR retention window) — these backups are access-controlled and
    will be overwritten in due course.
  - We have notified our sub-processors (OpenAI, Anthropic) of your
    erasure request; they will delete your data from their training
    logs per their respective DPAs.

If you have any questions, please contact our Data Protection Officer
at {{dpo_email}}.

Kind regards,
OUTRENA Data Protection Team
```

### restriction-completion

```
Subject: Your data subject request — restriction completed

Dear {{data_subject_name}},

Your data restriction request (DSR-{{dsr_id}}) has been completed.

OUTRENA has restricted processing of your personal data:
  - All outbound marketing actions (email, LinkedIn) have been blocked.
  - Your data is retained but is no longer actively processed.

You may lift this restriction at any time by contacting us at
{{dpo_email}}. You may also request full erasure (Article 17) at any
time.

Kind regards,
OUTRENA Data Protection Team
```

### objection-completion

```
Subject: Your data subject request — objection completed

Dear {{data_subject_name}},

Your objection request (DSR-{{dsr_id}}) has been completed.

OUTRENA has stopped processing your personal data for direct marketing
purposes, effective immediately. Your prospect record has been
suppressed; you will not receive any further outreach from OUTRENA or
our customers via the platform.

You may request full erasure (Article 17) at any time by replying to
this email.

Kind regards,
OUTRENA Data Protection Team
```

### rejection

```
Subject: Your data subject request — unable to complete

Dear {{data_subject_name}},

We have reviewed your data subject request (DSR-{{dsr_id}}) and are
unable to complete it for the following reason:

  {{reason}}

If you believe this decision is incorrect, you have the right to:
  - Lodge a complaint with your local supervisory authority
    (Article 77 of the GDPR).
  - Seek a judicial remedy against OUTRENA (Article 79).

If you would like to provide additional information that may allow us
to reconsider, please reply to this email.

Kind regards,
OUTRENA Data Protection Team
```

### identity-verification

```
Subject: Please verify your identity for DSR-{{dsr_id}}

Dear data subject,

We have received a data subject request associated with this email
address. Before we can process your request, we need to verify your
identity.

Please click the following link to confirm you submitted this request.
The link expires in 24 hours.

  {{verification_link}}

If you did not submit this request, please ignore this email — no
action will be taken.

Kind regards,
OUTRENA Data Protection Team
```

### breach-notification-to-subjects

```
Subject: Security incident notification — your OUTRENA data

Dear {{data_subject_name}},

OUTRENA is writing to notify you of a security incident that may have
affected your personal data. We are notifying you without undue delay
in accordance with Article 34 of the General Data Protection Regulation
(GDPR), as the incident is likely to result in a high risk to your
rights and freedoms.

What happened:
  {{breach_description}}

When it happened:
  Discovered on {{discovered_at}}; occurred between {{breach_start}} and
  {{breach_end}}.

What data was involved:
  {{data_categories}}

What we are doing:
  - We have secured the affected systems and engaged our incident
    response team.
  - We have notified the relevant supervisory authority (Article 33).
  - We are providing [credit monitoring / identity-theft protection /
    other remediation] for affected data subjects.

What you can do:
  - [Specific recommendations — e.g. change your password, monitor your
    bank statements, etc.]

If you have any questions, please contact our Data Protection Officer
at {{dpo_email}}.

Kind regards,
OUTRENA Data Protection Team
```

## CLI: scripts/gdpr-data-export.py

For ad-hoc exports outside the DSR workflow (e.g. customer onboarding
audits, regulator requests), use the CLI:

```bash
python scripts/gdpr-data-export.py \
  --email user@example.com \
  --tenant-slug acme \
  --output /tmp/export.json
```

The script writes both JSON and CSV (side-by-side). It uses the same
`GdprService.export_user_data` method as the DSR endpoint, so the
output is identical.

See `scripts/gdpr-data-export.py --help` for the full options.

## Edge Cases

### Request from a non-customer

The data subject was never a Prospect in any tenant. The DSR is
recorded with `tenant_slug='__unknown__'`. The DPO:

1. Searches all tenant schemas for the email (manual SQL:
   `SELECT slug FROM public.tenants t WHERE EXISTS (SELECT 1 FROM
   tenant_{slug_replace_dashes_with_underscores}."Prospect" p WHERE
   lower(p.email) = 'subject@example.com')`).
2. If no match, completes the DSR with `notes="No data found for this
   email in any tenant."` and sends the access-completion email with
   an empty export.

### Request for third-party data

A requester asks for data about someone else (e.g. an employee asks
about their manager's data). REJECT with reason `"Identity could not
be verified — request is for third-party data without written
authorisation."`. The requester must provide written authorisation
from the data subject.

### Fraudulent request

The requester cannot verify identity after 7 days. REJECT with reason
`"Could not verify identity within 7 days."`. Log the attempt in
`public.platform_audit_log` (the DSR submission itself was already
logged by the audit middleware).

### Manifestly unfounded or excessive

The requester has submitted 10+ DSRs in the past 30 days with no new
information. The DPO may:
- Charge a "reasonable fee" for the request (Art 12(5)).
- Refuse to act on the request (Art 12(5)).

Document the unfounded/excessive reasoning in the DSR `rejection_reason`.

### Data subject is deceased

GDPR does not apply to deceased persons (Recital 27). Reject with
reason `"GDPR does not apply to data of deceased persons. Please
contact our legal team at legal@outrena.io for next-of-kin data
requests."`.

## See Also

- `runbooks/12-gdpr-compliance.md` — parent GDPR compliance runbook
- `runbooks/05-incident-response.md` — breach notification procedure
- `docs/ropa-outrena.md` — what data we hold (for the access export)
- `app/api/v1/gdpr.py` — DSR + consent + retention endpoints
- `app/services/gdpr_service.py` — DSR processors
- `scripts/gdpr-data-export.py` — CLI export tool
