---
title: SOC2 Compliance Runbook
last_updated: 2025-01-20
severity: SEV-2
owner: OUTRENA Security Team
related_runbooks: [05-incident-response, 08-disaster-recovery, 11-secrets-management]
---

# SOC2 Compliance Runbook

Operationalises the OUTRENA SOC2 Type II program against the AICPA Trust Service
Criteria (TSC). Each control below maps to a specific implementation file or
procedure. Audit evidence is collected quarterly — see
[§Evidence Collection Checklist](#evidence-collection-checklist) for the auditor
artefact list.

This runbook closes the SOC2 infrastructure gaps identified in SURVEY-INFRA
(part 1). All resources referenced here were added in SAAS-INFRA — file paths
point to the production codebase.

## Prerequisites

- Operator has read access to AWS CloudTrail + CloudWatch Logs in the prod
  account (or Azure Activity Log + Log Analytics workspace in the prod
  subscription).
- Operator has access to the SOC2 evidence repository (a separate
  `outrena-soc2-evidence` GitHub repo, access controlled by @security-team).
- Operator is on the @security-team or @sre-team GitHub team.

## Trust Service Criteria Mapping

Each SOC2 TSC maps to one or more implementation artefacts in the OUTRENA
repo. "Implementation" column lists where the control is technically enforced;
"evidence" column lists what the auditor receives quarterly.

### CC1 — Control Environment (governance)

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC1.1 — Board establishes accountability | `.github/CODEOWNERS` (team ownership); `runbooks/00-README.md` (on-call schedule) | CODEOWNERS export + on-call roster screenshot |
| CC1.4 — Tone at the top | `runbooks/00-README.md` severity ack SLAs; @security-team chartered in HR system | HR charter doc |
| CC1.5 — Enforces accountability | GitHub branch protection (main + develop require CODEOWNERS review + CI green) | Branch-protection rule export from GitHub API |

### CC2 — Communication + Information

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC2.1 — Internal communication | Slack `#incident-*` channels; PagerDuty `OUTRENA-SRE-Lead` escalation policy | PagerDuty policy export |
| CC2.2 — External communication | `runbooks/05-incident-response.md` §customer-communication template; status page at `status.outrena.com` | Status-page incident history |
| CC2.3 — Communication to affected parties | breach-notification procedure in runbook 05 §data-breach | Runbook 05 export |

### CC3 — Risk Assessment

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC3.1 — Risk identification | Quarterly threat-model review (`docs/threat-model.md`); SURVEY-INFRA report (worklog) | Threat-model doc + SURVEY-INFRA excerpt |
| CC3.4 — Risk mitigation | `terraform/aws/cloudtrail.tf`, `secrets_rotation.tf`, `.github/workflows/security.yml` (this SAAS-INFRA) | Terraform plan diff + CI security job log |

### CC4 — Monitoring Activities

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC4.1 — Ongoing monitoring | `terraform/aws/cloudtrail.tf` (CloudTrail + 6 SOC2 alarms); `terraform/azure/activity_log.tf` (4 activity-log alerts) | CloudTrail log export (quarterly) + CloudWatch alarm screenshots |
| CC4.2 — Deficiency evaluation | `monitoring/alert-runbook.md` (per-alert triage); SOC2 alarm → @security-team on-call | Alert-runbook export + SNS subscription confirmation |

### CC5 — Control Activities

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC5.1 — Selection + development | All controls in Terraform (IaC) — code-reviewed via PR | PR merge history |
| CC5.2 — Deployed + operated | Terraform apply logs (CI/CD); `runbooks/01-tenant-provisioning.md` (deploy procedure) | CI/CD workflow run history |
| CC5.3 — Segregation of duties | `.github/CODEOWNERS` enforces 2-person review on `/terraform/`, `/.github/`, `/runbooks/` | CODEOWNERS file + PR approval history |

### CC6 — Logical + Physical Access

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC6.1 — Logical access controls | `terraform/aws/secrets_rotation.tf` (auto-rotation); `terraform/azure/key_vault_rotation.tf` (Function App rotation); `runbooks/11-secrets-management.md` | Secrets Manager rotation history; IAM access review CSV (quarterly) |
| CC6.2 — User authentication | Keycloak (outrena-frontend IdP); MFA enforced via Keycloak realm settings | Keycloak realm export showing OTP policy |
| CC6.3 — Role-based access | Backend 4-role hierarchy: REP / MANAGER / TENANT_ADMIN / SUPER_ADMIN (`app/schemas/auth.py:29-33`) | Role-permission matrix doc |
| CC6.6 — Network access controls | `terraform/aws/security_groups.tf` (8 SGs, default-deny); `terraform/azure/nsg.tf`; `k8s/outrena/templates/networkpolicy.yaml` | Terraform state export of SG rules |
| CC6.7 — Restricted physical access | AWS + Azure data centre physical security (inherited from cloud provider) | AWS SOC2 report + Azure SOC2 report (vendor-supplied) |
| CC6.8 — System component inventory | `terraform/` (all infra codified); `k8s/outrena/Chart.yaml` (K8s inventory); `outrena-backend/pyproject.toml` (deps) | Terraform state file + Helm release list |

### CC7 — System Operations

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC7.1 — Inventory + infrastructure changes | `terraform/aws/cloudtrail.tf` §aws_config (records all supported resources, 6-hour snapshots) | AWS Config snapshot + change history CSV |
| CC7.2 — Monitoring | CloudTrail 365d (`terraform/aws/cloudtrail.tf`); Azure Activity Log 7y (`terraform/azure/activity_log.tf`) | CloudTrail log group retention screenshot + Activity Log diagnostic setting |
| CC7.3 — Incident response | `runbooks/05-incident-response.md` (376 lines); SOC2 alarms → SNS `aws_sns_topic.security_alerts` | Runbook 05 export + SNS topic config |
| CC7.4 — Recovery (backups) | `runbooks/08-disaster-recovery.md` (RPO 5min / RTO 1hr); RDS PITR 35d; quarterly DR drill | Runbook 08 export + DR drill report |

### CC8 — Change Management

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC8.1 — Authorised changes | GitHub branch protection on main + develop; CODEOWNERS review required; CI must pass | Branch-protection export + PR approval log |
| CC8.2 — Tested changes | `.github/workflows/ci.yml` (lint + type + unit + integration + terraform validate + Trivy); `.github/workflows/security.yml` (SAST + dep + secret + IaC + container + SBOM + license) | CI workflow run history (last 90d) |
| CC8.3 — Documented changes | Conventional commit messages; PR descriptions; `runbooks/03-rollback.md` (rollback procedure) | Git log + rollback runbook export |

### CC9 — Risk Mitigation

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| CC9.1 — Vendor mgmt | Sub-processor list (see §Sub-processor Management below); DPA on file | DPA copies + sub-processor list export |
| CC9.2 — Business continuity | `runbooks/08-disaster-recovery.md` (cross-region failover); Route 53 / Traffic Manager weighted cutover | Runbook 08 export + DR drill report |

### A1 — Availability (3-tier cloud)

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| A1.1 — Capacity planning | `terraform/aws/rds.tf` (Multi-AZ); `terraform/azure/postgres.tf` (zone-redundant HA); `runbooks/07-scaling.md` | Terraform state + scaling runbook |
| A1.2 — Environmental protections | Multi-AZ RDS; 3-AZ VPC; Azure zone-redundant Container Apps Env | Terraform plan diff |
| A1.3 — Recovery infrastructure | RDS PITR 35d (`terraform/aws/envs/prod/prod.tfvars:rds_backup_retention_days=35`); S3 versioning + CRR | Runbook 08 + terraform state |

### C1 — Confidentiality

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| C1.1 — Confidential info identified | `outrena-backend/.env.example` documents secret names; `runbooks/11-secrets-management.md` secret inventory | .env.example + runbook 11 |
| C1.2 — Confidential info protected | RDS KMS (`terraform/aws/rds.tf`); S3 SSE-KMS (`terraform/aws/s3.tf`); Redis at-rest (`terraform/aws/elasticache.tf`); Fernet for LLM keys (`outrena-backend/.env.example:ENCRYPTION_KEY`) | KMS key list + rotation config |

### L1 — Processing Integrity

| Criterion | Implementation | Evidence |
|-----------|----------------|----------|
| L1.1 — Data processing authorised | Tenant middleware (`app/middleware/tenant_middleware.py`); per-tenant schema isolation | Integration test report (`tests/integration/test_isolation.py`) |

### PI1 — Privacy (optional — not currently scoped)

PI1 is **out of scope** for the current SOC2 audit. Privacy controls will be
added when OUTRENA expands the audit scope to include PI1 (planned: FY2026).

## Audit Log Retention + Access

### AWS CloudTrail

- **Retention:** 365 days hot in CloudWatch Logs (`terraform/aws/cloudtrail.tf`
  `aws_cloudwatch_log_group.cloudtrail.retention_in_days = 365`). S3 bucket
  `aws_s3_bucket.cloudtrail_logs` retains 365d with lifecycle
  (STANDARD 90d → GLACIER 180d → expire 365d).
- **SOC2 7-year retention:** quarterly exports to a separate archive bucket
  (operator-driven, see §Evidence Collection Checklist below).
- **Access:** CloudTrail logs are queryable via CloudWatch Logs Insights.
  Operators with the `SecurityAuditor` IAM role can run read-only queries.
  Write access is restricted to the CloudTrail service principal (enforced by
  the bucket policy in `terraform/aws/cloudtrail.tf`).

```bash
# Query CloudTrail for all root-account activity in the last 7 days.
aws logs start-query \
  --log-group-name "/aws/cloudtrail/outrena-prod" \
  --start-time $(date -d '7 days ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, eventName, userIdentity.arn, sourceIPAddress | filter userIdentity.type = "root" | sort @timestamp desc'
```

### Azure Activity Log

- **Retention:** 730 days hot in the security Log Analytics workspace
  (`terraform/azure/activity_log.tf`
  `azurerm_log_analytics_workspace.security.retention_in_days = 730`).
  Storage account `azurerm_storage_account.activity_log` retains 7 years
  (hot 90d → cool 180d → archive 1y → delete 7y).
- **Access:** KQL queries against the security workspace. Operators with the
  `Log Analytics Reader` RBAC role can query.

```bash
# Query Activity Log for all role-assignment changes in the last 30 days.
az monitor log-analytics query \
  --workspace "$(terraform -chdir=terraform/azure output -raw log_analytics_security_workspace_id)" \
  --analytics-query 'AzureActivity | where OperationNameValue == "Microsoft.Authorization/roleAssignments/write" | project TimeGenerated, Caller, ResourceId | take 100'
```

### Application audit log

- **Table:** `platform_audit_log` (per-tenant schema; defined in
  `outrena-backend/alembic/versions/0002_initial_tenant.py`).
- **Retention:** 7 years (`AUDIT_LOG_RETENTION_DAYS=2555` in
  `outrena-backend/.env.example`). Daily cron `scripts/audit-log-retention.py`
  (placeholder — to be implemented) purges records older than the retention
  threshold.
- **Access:** only the SUPER_ADMIN role can read the audit log via the
  `/platform/audit-log` endpoint (`app/api/routes/platform.py`).

## Change Management Process

Every change to OUTRENA production goes through:

1. **Pull request** opened against `main` or `develop` branch.
2. **CODEOWNERS review** — `.github/CODEOWNERS` enforces 2-person review:
   - `/terraform/` → @devops-team
   - `/.github/` → @security-team + @devops-team (BOTH must approve)
   - `/runbooks/` → @sre-team
   - `/outrena-backend/` → @backend-team
3. **CI must pass** (`.github/workflows/ci.yml`):
   - Backend: ruff + mypy + pytest unit + pytest integration
   - Frontend: typecheck + lint + build
   - Terraform: `fmt -check -recursive` + `validate` (AWS + Azure)
   - Trivy filesystem scan (HIGH+CRITICAL)
   - audit_env.py (JWT bypass guard + duplicate-key check)
4. **Security workflow must pass** (`.github/workflows/security.yml`):
   - SAST (CodeQL)
   - Dependency scan (pip-audit + npm audit)
   - Secret scan (gitleaks)
   - IaC scan (checkov)
   - Container scan (Trivy image)
   - SBOM generation
5. **Branch protection** (configured in GitHub repo settings — documented in
   `runbooks/00-README.md`):
   - Require CODEOWNERS review
   - Require status checks: CI + Security workflows
   - Require linear history
   - Dismiss stale reviews on push
6. **Production deploy** is gated by a separate manual approval workflow:
   - `.github/workflows/cd-prod-aws.yml` (4 environment gates: prod → 25 → 50 → 100)
   - `.github/workflows/cd-prod-azure.yml` (same 4 gates)
   - Canary soak at 5% for 1h before promoting to 25%
7. **Rollback** is documented in `runbooks/03-rollback.md` + automated via
   `.github/workflows/rollback.yml`.

## Access Reviews

### Quarterly access review

Every quarter, @security-team reviews:

1. **AWS IAM users + roles** in the prod account:
   ```bash
   aws iam list-users --query 'Users[*].UserName' --output table
   aws iam list-roles --query 'Roles[?starts_with(RoleName, `outrena`)].RoleName' --output table
   ```
2. **Azure RBAC role assignments** at the subscription scope:
   ```bash
   az role assignment list --scope /subscriptions/<sub-id> \
     --query '[?roleDefinitionName==`Owner` || roleDefinitionName==`Contributor`].{user:principalName, role:roleDefinitionName}' -o table
   ```
3. **Keycloak realm admins**:
   ```bash
   # List realm-admin role assignments in the outrena realm.
   curl -sS -H "Authorization: Bearer $KEYCLOAK_TOKEN" \
     "https://auth.outrena.com/admin/realms/outrena/role-mappings/realm-admin/composite"
   ```
4. **GitHub team membership** for `@security-team`, `@devops-team`, `@sre-team`.
5. **3rd-party access** (Stripe dashboard, MailBridge admin console, LLM
   provider dashboards).

### Revocation procedure

To revoke access:

- **AWS IAM user:** `aws iam delete-user --user-name <name>` (after deleting
  access keys + detaching policies).
- **Azure principal:** `az role assignment delete --ids <id>` for each
  assignment; `az ad user delete --id <upn>` for the user.
- **Keycloak user:** deactivate via Admin API
  (`PUT /admin/realms/outrena/users/<id>` with `enabled=false`) — do NOT
  delete (preserves audit trail).
- **GitHub team:** remove user from team via `gh api -X DELETE
  orgs/outrena/teams/<team-slug>/memberships/<username>`.
- **Slack:** deactivate user via Slack admin.
- **3rd-party:** revoke in vendor console + notify vendor in writing.

All revocations must be logged in the SOC2 evidence repository with a ticket
reference + timestamp.

## Incident Response Cross-Reference

Full IR procedure is in `runbooks/05-incident-response.md`. SOC2-specific
additions:

- **SOC2 alarms** (added in SAAS-INFRA) route to a separate SNS topic
  `aws_sns_topic.security_alerts` (AWS) + action group
  `azurerm_monitor_action_group.security` (Azure) — these page the
  @security-team on-call, distinct from the ops alerts that page @sre-team.
- **SEV-1 security incidents** (root login, IAM policy change, console login
  without MFA) trigger the security-incident workflow in
  `runbooks/05-incident-response.md` §data-breach — this includes customer
  notification within 72h per GDPR Article 33.
- **Post-incident review** for SEV-1 security incidents includes a SOC2
  control-failure analysis — was the alarm timely? was the response within
  SLA? are controls adequate?

## Backup + DR Cross-Reference

Full DR procedure is in `runbooks/08-disaster-recovery.md`. SOC2 CC7.4 +
A1.3 evidence:

- **RPO 5min / RTO 1hr** — documented in runbook 08 §RPO-RTO-Targets.
- **Quarterly DR drill** — runbook 08 §DR-Drill. Evidence: drill report
  with restore-time + data-integrity verification.
- **Backup encryption** — all backups encrypted with customer-managed KMS
  keys (RDS KMS key for RDS snapshots; S3 KMS key for S3 versioning).

## Vulnerability Management

### Scanning

The `.github/workflows/security.yml` workflow runs the following scans on every
PR + nightly:

| Scan | Tool | Fail threshold |
|------|------|----------------|
| SAST | CodeQL (Python + TypeScript) | HIGH+ |
| Dependency (Python) | pip-audit | HIGH+ |
| Dependency (JavaScript) | npm audit | HIGH+ |
| Secret | gitleaks (full history) | any finding |
| IaC | checkov (terraform/) | HIGH+CRITICAL |
| Container | Trivy image (backend + frontend) | CRITICAL |
| License | pip-licenses + license-checker | warn-only |

### Patch SLAs

| Severity | SLA | Escalation |
|----------|-----|------------|
| CRITICAL | 24 hours | @security-team paged immediately; rollback if not patched in 24h |
| HIGH | 7 days | @devops-team ticket; weekly review |
| MEDIUM | 30 days | Backlog ticket; monthly review |
| LOW | Next release | Backlog ticket |

Dependabot PRs for security advisories get the `security` label and bypass the
grouping (so they're reviewed immediately, not batched).

## Data Retention Policy

| Data class | Retention | Mechanism | File reference |
|------------|-----------|-----------|----------------|
| User content (prospects, sequences, deals) | Until tenant requests deletion + 30d grace | Soft-delete flag + daily cron | `app/services/prospect_service.py` (delete()) |
| Audit logs (CloudTrail) | 7 years (1y hot + 6y archive) | S3 lifecycle + quarterly archive export | `terraform/aws/cloudtrail.tf` |
| Audit logs (Azure Activity Log) | 7 years (730d workspace + 2555d archive) | Storage management policy | `terraform/azure/activity_log.tf` |
| Audit logs (platform_audit_log table) | 7 years | Daily cron (scripts/audit-log-retention.py — TODO) | `outrena-backend/.env.example:AUDIT_LOG_RETENTION_DAYS=2555` |
| RDS automated backups | 35 days | `terraform/aws/envs/prod/prod.tfvars:rds_backup_retention_days=35` | `terraform/aws/rds.tf:161` |
| RDS Performance Insights | 7 days | `terraform/aws/rds.tf:177` | (free tier) |
| S3 CSV uploads | 365 days (lifecycle) | `terraform/aws/s3.tf:117-147` | STANDARD_IA 30d → GLACIER 90d → expire 365d |
| S3 collateral (sales PDFs) | indefinite (legal hold) | `terraform/aws/s3.tf:194-223` (no `expiration` block) | Lifecycle comment |
| ElastiCache snapshots | 7 days | `terraform/aws/elasticache.tf:112-113` | (Redis is cache, not source of truth) |
| CloudWatch Logs (app) | 90 days prod | `terraform/aws/envs/prod/prod.tfvars:log_retention_days=90` | `terraform/aws/cloudwatch.tf` |

### User data deletion

When a tenant requests data deletion:

1. Tenant admin opens a support ticket requesting deletion.
2. @security-team verifies the requester's identity + tenant ownership.
3. Operator runs the tenant-deletion script (to be implemented):
   ```bash
   # Soft-delete: sets deleted_at on the tenant row; daily cron hard-deletes
   # after 30d grace period (in case of accidental deletion).
   python scripts/delete-tenant-data.py --tenant-id <id> --confirm
   ```
4. Tenant data is purged from:
   - All per-tenant Postgres schemas (`tenant_<slug>`)
   - S3 CSV uploads for that tenant (lifecycle expires within 30d)
   - ElastiCache Redis keys (immediate flush of tenant-scoped keys)
   - Keycloak realm (deleted + exported to archive for audit trail)
5. Audit log entry retained for 7 years (not deleted) — confirms the deletion
   happened + who authorised it.

## Sub-Processor Management

Sub-processors with access to OUTRENA customer data:

| Sub-processor | Purpose | DPA reference | Last reviewed |
|---------------|---------|---------------|---------------|
| AWS | Primary cloud (US-East-1) | `aws-dpa-2024.pdf` (legal folder) | 2024-Q4 |
| Azure | Secondary cloud (EU-West) | `azure-dpa-2024.pdf` | 2024-Q4 |
| Stripe | Payment processing | `stripe-dpa.pdf` | 2024-Q4 |
| Keycloak (self-hosted) | Identity provider | N/A (self-hosted) | N/A |
| OpenAI / ZAI (LLM provider) | LLM inference | `llm-dpa.pdf` | 2024-Q4 |

### Adding a new sub-processor

1. Open a PR to add the sub-processor to the table above.
2. @security-team + @legal-team review (CODEOWNERS enforced).
3. DPA executed + filed in the legal folder.
4. Customer notification email sent 30 days before the sub-processor goes live
   (per GDPR Article 28).
5. Sub-processor added to the SOC2 evidence repository.

## Evidence Collection Checklist

Quarterly, the @security-team collects the following artefacts and uploads them
to the `outrena-soc2-evidence` repo under `evidence/<YYYY>-Q<N>/`:

### Per-quarter (every 3 months)

- [ ] **CloudTrail log export** — 90-day slice of CloudTrail logs, exported
      from the CloudWatch Logs group to S3 archive bucket:
      ```bash
      aws logs create-export-task \
        --log-group-name "/aws/cloudtrail/outrena-prod" \
        --from $(date -d '90 days ago' +%s) \
        --to $(date +%s) \
        --destination outrena-prod-cloudtrail-archive \
        --destination-prefix "evidence/$(date +%Y-Q%q)"
      ```
- [ ] **Azure Activity Log export** — 90-day slice, exported from the security
      workspace to the archive storage account.
- [ ] **Access review CSV** — output of the quarterly access review (see
      §Access Reviews above).
- [ ] **Patch compliance report** — Dependabot PR merge history + Trivy scan
      results from the last 90 days (downloaded from GitHub Security tab).
- [ ] **Backup restore test** — DR drill report from `runbooks/08-disaster-recovery.md`
      §DR-Drill.
- [ ] **Vulnerability scan report** — CodeQL + Trivy + pip-audit + npm audit +
      gitleaks + checkov from the last nightly run.
- [ ] **SBOM archive** — CycloneDX SBOMs (backend + frontend) from the last
      release, generated by `scripts/generate-sbom.sh`.
- [ ] **Secret rotation audit** — output of `aws secretsmanager list-secrets`
      (showing LastRotatedDate for each) + Azure Key Vault secret versions.
- [ ] **SOC2 alarm history** — CloudWatch metric alarm history for the 6 SOC2
      alarms in `terraform/aws/cloudtrail.tf` (unauthorized API calls, root
      login, IAM changes, SG changes, S3 policy changes, console-no-MFA).
- [ ] **CODEOWNERS + branch-protection** — export of `.github/CODEOWNERS` +
      branch protection rules from GitHub API.
- [ ] **CI/CD workflow run history** — last 90 days of CI + Security workflow
      runs (success rate + mean time to fix failures).

### Per-year (every 12 months)

- [ ] **Annual policy review** — confirm this runbook + runbook 05 + runbook 08
      + runbook 11 are still accurate; update `last_updated` dates.
- [ ] **DR drill summary** — annual cross-region failover test (beyond the
      quarterly RDS restore test).
- [ ] **Vendor SOC2 reports** — refresh AWS + Azure + Stripe SOC2 Type II
      reports from vendor portals.
- [ ] **Penetration test** — annual third-party pentest report.

## Cross-References

- `runbooks/05-incident-response.md` — IR procedure (SEV-1/2/3).
- `runbooks/08-disaster-recovery.md` — backup/restore + DR drill.
- `runbooks/09-secrets-management.md` — original secrets inventory + rotation.
- `runbooks/11-secrets-management.md` — SaaS-layer secrets management (this SAAS-INFRA addition).
- `monitoring/alert-runbook.md` — per-alert triage.
- `.github/CODEOWNERS` — code-owner review enforcement.
- `.github/dependabot.yml` — automated dependency PRs.
- `.github/workflows/security.yml` — CI security pipeline.
- `terraform/aws/cloudtrail.tf` — CloudTrail + Config + SOC2 alarms.
- `terraform/aws/secrets_rotation.tf` — Secrets Manager rotation.
- `terraform/azure/activity_log.tf` — Azure Activity Log + alerts.
- `terraform/azure/key_vault_rotation.tf` — Key Vault rotation Function App.
- `scripts/rotate-secrets.sh` — manual rotation trigger script.
- `scripts/generate-sbom.sh` — SBOM generation script.

## Open Items (TODO — out of scope for SAAS-INFRA)

- `scripts/audit-log-retention.py` — daily cron to purge `platform_audit_log`
  rows older than `AUDIT_LOG_RETENTION_DAYS`. Currently a placeholder reference
  in `.env.example`; needs implementation.
- `scripts/delete-tenant-data.py` — tenant data deletion script referenced in
  §User data deletion above. Needs implementation.
- App-layer column-level encryption for LLM API keys (currently plaintext
  `String` columns in `app/models/config_models.py:44`). Use the
  `ENCRYPTION_KEY` Fernet key added in SAAS-INFRA — see SURVEY-INFRA gap A8.
- Implement `AuditLog` SQLAlchemy model (referenced as `platform_audit_log`
  but not currently a model in `app/models/`).
