---
title: Secrets Management + Rotation Runbook
last_updated: 2025-01-15
severity: SEV-2
owner: OUTRENA SRE
---

# Secrets Management + Rotation Runbook

Inventory of all OUTRENA secrets, how to rotate each, how to verify rotation, and how
to audit access. All secrets live in AWS Secrets Manager (prod AWS) or Azure Key Vault
(prod Azure); none are stored in plaintext or in git.

## Prerequisites

- Operator has Secrets Manager / Key Vault read + write access for the prod account.
- For ECS env var rotations: GitHub Actions prod workflow trigger permission.
- For LLM API key rotations: tenant admin access (via the platform UI).
- Quarterly rotation schedule tracked in the SRE wiki.

## Secrets Inventory

| Secret | Store | Rotation Cadence | Rotation Method | Used By |
|--------|-------|------------------|-----------------|---------|
| RDS master password | AWS Secrets Manager + Azure Key Vault | Quarterly | Rotation Lambda (automatic) | RDS, ECS tasks (read replica) |
| Keycloak admin password | AWS Secrets Manager + Azure Key Vault | Quarterly | Manual | Keycloak realm admin, CI/CD |
| MailBridge webhook URL | AWS Secrets Manager | When MailBridge rotates | Manual | Backend webhook handler |
| MailBridge signing secret | AWS Secrets Manager | When MailBridge rotates | Manual | Backend signature verifier |
| LLM API keys (per-tenant) | DB encrypted column (per-tenant settings) | Per tenant policy (default 90 days) | Tenant settings UI | LLM gateway |
| Backend JWT signing key | AWS Secrets Manager | Annually (or on compromise) | Manual | Auth service (deprecated — Keycloak now signs) |
| Slack webhook URLs | GitHub Actions secrets | On team change | Manual | CI/CD workflows |
| TLS cert (ACM) | AWS ACM | Auto-renew (ACM) | Automatic | ALB, CloudFront |
| TLS cert (Azure App Gateway) | Azure Key Vault | Annually | Manual upload | App Gateway |
| GitHub Actions deploy token | GitHub | Annually | GitHub UI | CI/CD |
| PagerDuty integration keys | GitHub Actions secrets | On team change | Manual | Alert routing |

## How to Rotate Each

### RDS master password

Rotation is **automatic** via a Secrets Manager rotation Lambda. The Lambda runs every
90 days and on-demand.

**Trigger manually:**

```bash
aws secretsmanager rotate-secret --secret-id /outrena/prod/rds-master-password
# Rotation completes in ~30 s. The Lambda updates the RDS password + the secret value
# in one atomic operation. No app restart required (ECS tasks read the secret at task
# start; new tasks pick up the new password on next deploy).

# Verify.
aws secretsmanager describe-secret --secret-id /outrena/prod/rds-master-password \
  --query 'RotatedDate'
```

> **⚠️ Warning:** The RDS master password is only used for administrative access
> (migrations, snapshots). Application access uses the `outrena_app` role whose
> password is **not** rotated by this Lambda — that one is in a separate secret
> (`/outrena/prod/db-app-password`) and is rotated manually.

### Keycloak admin password

Manual rotation. Requires Keycloak admin UI access.

```bash
# 1. Generate a new password.
NEW_PASSWORD=$(openssl rand -base64 32)

# 2. Update Keycloak via Admin API.
curl -sS -X PUT "https://auth.outrena.com/admin/realms/master/users/<admin-user-id>/reset-password" \
  -H "Authorization: Bearer $CURRENT_KEYCLOAK_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"password\",\"value\":\"$NEW_PASSWORD\",\"temporary\":false}"

# 3. Update Secrets Manager + Key Vault.
aws secretsmanager update-secret --secret-id /outrena/prod/keycloak-admin-password \
  --secret-string "$NEW_PASSWORD"
az keyvault secret set --vault-name kv-outrena-prod \
  --name keycloak-admin-password --value "$NEW_PASSWORD"

# 4. Update CI/CD (GitHub Actions secret).
gh secret set KEYCLOAK_ADMIN_PASSWORD --body "$NEW_PASSWORD" --env prod

# 5. Restart CI runners (they cache the password) — or just trigger a re-deploy.
# 6. Verify.
curl -sS -X POST "https://auth.outrena.com/realms/master/protocol/openid-connect/token" \
  -d "grant_type=password" -d "client_id=admin-cli" \
  -d "username=admin" -d "password=$NEW_PASSWORD" | jq '.access_token | length'
# Expected: non-zero.
```

### MailBridge webhook URL + signing secret

MailBridge rotates these on their schedule (annually or on incident) and notifies
OUTRENA ops 7 days in advance. Rotation is manual.

```bash
# 1. MailBridge provides the new URL + signing secret via secure channel (1Password
#    shared vault).
NEW_URL="<from MailBridge>"
NEW_SECRET="<from MailBridge>"

# 2. Update Secrets Manager.
aws secretsmanager update-secret --secret-id /outrena/prod/mailbridge-webhook-url \
  --secret-string "$NEW_URL"
aws secretsmanager update-secret --secret-id /outrena/prod/mailbridge-signing-secret \
  --secret-string "$NEW_SECRET"

# 3. Restart backend tasks (the webhook handler reads the secret at startup).
aws ecs update-service --cluster outrena-prod --service outrena-backend \
  --force-new-deployment

# 4. Verify with MailBridge's test endpoint.
curl -fsS -X POST https://api.outrena.com/internal/mailbridge/test-auth \
  -H "X-MailBridge-Signature: $(echo -n 'test' | openssl dgst -sha256 -hmac "$NEW_SECRET" | awk '{print $2}')" \
  -H "Content-Type: application/json" -d '{"test":true}'
# Expected: 200 OK.
```

### LLM API keys (per-tenant)

Rotated via the tenant settings UI by the tenant admin (or OUTRENA customer success on
their behalf). Stored encrypted in the per-tenant schema's `settings` table.

```text
1. Log in to https://<tenant-slug>.outrena.com as admin.
2. Settings → Integrations → LLM Provider.
3. Click "Rotate API Key".
4. Paste new key → Save.
5. Backend tests the key with a 1-token completion. Success → key active.
6. Old key is purged from the DB + audit-logged.
```

> **⚠️ Warning:** If a tenant's LLM key is compromised, rotate immediately via the UI.
> Do NOT wait for the 90-day cadence. Audit log records who rotated + when.

### Backend JWT signing key

Largely deprecated — Keycloak now signs all JWTs. The backend JWT signing key is only
used for internal service-to-service tokens. Rotate annually:

```bash
# 1. Generate new key.
NEW_KEY=$(openssl rand -hex 32)
aws secretsmanager update-secret --secret-id /outrena/prod/backend-jwt-key \
  --secret-string "$NEW_KEY"

# 2. Restart backend tasks (forces re-read).
aws ecs update-service --cluster outrena-prod --service outrena-backend \
  --force-new-deployment

# 3. Restart scheduler + worker too (they validate internal JWTs).
aws ecs update-service --cluster outrena-prod --service outrena-scheduler --force-new-deployment
aws ecs update-service --cluster outrena-prod --service outrena-worker --force-new-deployment

# 4. Verify an internal service-to-service call.
curl -fsS -H "Authorization: Bearer $(./scripts/mint_internal_token.sh)" \
  https://api.outrena.com/internal/health | jq .
```

### Slack webhook URLs

```bash
# 1. Slack → Apps → Incoming Webhooks → rotate.
# 2. Update GitHub Actions secrets.
gh secret set SLACK_WEBHOOK_URL        --body "<new-url>" --env prod
gh secret set SLACK_INCIDENT_WEBHOOK_URL --body "<new-url>" --env prod

# 3. Trigger a test deploy to verify the new webhook.
gh workflow run cd-prod-aws.yml -f ref=main -f environment=staging
# Check #deploys + #on-call-incidents receive the notification.
```

### TLS cert — ACM (AWS)

Auto-renews 60 days before expiry. No action required. Verify:

```bash
aws acm list-certificates --query 'CertificateSummaryList[*].{domain:DomainName,arn:CertificateArn}' --output table
aws acm describe-certificate --certificate-arn <arn> \
  --query 'Certificate.{domain:DomainName,status:Status,notAfter:NotAfter,renewal:RenewalSummary}'
# Status=ISSUED, RenewalSummary.Status=SUCCESS (or null if not yet in renewal window).
```

### TLS cert — Azure App Gateway (manual upload)

Azure App Gateway uses a cert stored in Key Vault. Renewal is manual.

```bash
# 1. Obtain the renewed cert (from the cert authority, e.g. DigiCert or Let's Encrypt).
# 2. Convert to PFX (with private key).
openssl pkcs12 -export -out /tmp/outrena.pfx -inkey private.key -in cert.pem
# 3. Upload to Key Vault.
az keyvault certificate import --vault-name kv-outrena-prod \
  --name outrena-tls-2025 --file /tmp/outrena.pfx

# 4. Update App Gateway to reference the new cert (Terraform).
cd terraform/azure
terraform plan  -var tls_cert_keyvault_id=outrena-tls-2025 -out=tfplan
terraform apply tfplan

# 5. Verify.
curl -vI https://app.outrena.com 2>&1 | grep -E "expire|subject"
```

### GitHub Actions deploy token

Rotate via GitHub UI (Settings → Developer settings → Personal access tokens). Update
the org-level secret `GH_DEPLOY_TOKEN` in GitHub Actions.

## How to Verify Rotation Succeeded

For each secret, after rotation:

1. **Backend tasks re-deployed** and `/health/ready` returns 200.
2. **End-to-end test** that exercises the secret:
   - RDS password: query via `psql`.
   - Keycloak admin: mint a token via Admin API.
   - MailBridge: hit the test-auth endpoint.
   - LLM API key: send a 1-token completion.
   - JWT key: mint + validate an internal token.
   - Slack webhook: trigger a test deploy.
   - TLS cert: `curl -vI` + check expiry.
3. **Audit log entry** recording who rotated + when.

## Audit — Who Accessed Which Secret When

### AWS CloudTrail

```bash
# All Secrets Manager API calls in the last 24 hr.
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventSource,AttributeValue=secretsmanager.amazonaws.com \
  --start-time $(date -u -d '24 hours ago' +%FT%TZ) \
  --end-time $(date -u +%FT%TZ) \
  --query 'Events[*].{time:EventTime,user:Username,action:EventName,resource:ResourceName}' \
  --output table

# Filter to a specific secret.
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=/outrena/prod/rds-master-password \
  --start-time $(date -u -d '7 days ago' +%FT%TZ) \
  --end-time $(date -u +%FT%TZ) --output table
```

### Azure Key Vault diagnostic logs

```bash
# Enable diagnostic settings on the Key Vault (one-time).
az monitor diagnostic-settings create \
  --name kv-audit --resource <kv-id> \
  --workspace <la-workspace-id> \
  --metrics All --logs '[{"category":"AuditEvent","enabled":true}]'

# Query the audit log.
az monitor log-analytics query \
  --workspace <la-workspace-id> \
  --analytics-query "AzureDiagnostics
    | where ResourceType == 'VAULTS'
    | where OperationName in ('SecretGet','SecretList','SecretSet','SecretUpdate')
    | project TimeGenerated, caller_s, identity_claim_http_schemas_xmlsoap_org_ws_2005_05_identity_claims_name_s, OperationName, id_s
    | order by TimeGenerated desc
    | limit 100"
```

### Quarterly audit review

The SRE lead reviews all secret-access events quarterly. Red flags:
- A human user (not a service role) accessing RDS master password.
- Access from an IP outside the corporate CIDR or VPN.
- Access at unusual hours (3 AM local for the named user).
- Bulk secret reads (>10 in a minute) — possible exfiltration.

Findings are documented in `migration/audits/<YYYY-Qn>.md`.

## Rollback

Secrets rotation has no rollback per se — once a secret is rotated, the old value is
gone (by design, for security). If rotation breaks the system:

1. Identify which secret is the cause (check the audit log for the most recent
   rotation).
2. If the old secret is still valid (e.g. MailBridge hasn't disabled the old signing
   secret yet), revert the Secrets Manager value to the old secret + restart tasks.
3. If the old secret is gone, generate a new secret + update the upstream provider
   (MailBridge, Keycloak, etc.) to accept it.

For TLS cert rotation: the old cert is retained in Key Vault / ACM for 90 days;
revert is `terraform apply -var tls_cert_keyvault_id=<old-cert-name>`.

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| Rotation Lambda fails for RDS password | DBA + SRE lead | Within 1 hr |
| After rotation, backend cannot connect to RDS | SRE lead — likely old tasks still running | Immediately |
| Suspicious secret access (audit log red flag) | Security lead + legal | Within 1 business day |
| Secret value leaked to git / Slack / log | Security lead + legal — page immediately | SEV-1 |
| Keycloak admin password lost (no one has it) | Identity lead + Keycloak vendor | SEV-1; requires realm reset |
| TLS cert expired before renewal | SRE lead + cert authority | SEV-1; site is down |

## Related

- `06-keycloak-jwks-rotation.md` — JWKS is a separate (automatic) rotation concern.
- `11-mailbridge-integration.md` — MailBridge webhook + signing secret in context.
- `08-disaster-recovery.md` — Keycloak realm export (daily) is a backup of secrets
  stored in Keycloak.
- Migration doc §14 Risk #1 (secrets exposure).
