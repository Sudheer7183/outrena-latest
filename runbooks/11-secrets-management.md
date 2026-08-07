---
title: Secrets Management Runbook (SaaS layer)
last_updated: 2025-01-20
severity: SEV-2
owner: OUTRENA Security Team
related_runbooks: [09-secrets-management, 10-soc2-compliance, 05-incident-response]
---

# Secrets Management Runbook (SaaS layer)

SaaS-layer secrets management for OUTRENA. Extends `runbooks/09-secrets-management.md`
with the SaaS-platform secret hierarchy, automated rotation infrastructure
(added in SAAS-INFRA), emergency procedures, and the Fernet encryption-key
handling protocol.

All resources referenced here were added in SAAS-INFRA. File paths point to
the production codebase.

## Prerequisites

- Operator has read + write access to AWS Secrets Manager / Azure Key Vault
  for the prod account.
- Operator has access to the rotation Lambda logs (CloudWatch Logs group
  `/aws/lambda/outrena-<env>-secret-rotation`).
- Operator is on @security-team or @sre-team.

## Secret Hierarchy

OUTRENA uses a 3-tier secret hierarchy depending on environment:

```
                     ┌──────────────────────────────────────┐
                     │   Tier 1 — Dev (.env file)           │
                     │   outrena-backend/.env               │
                     │   (gitignored, plaintext on disk)    │
                     └─────────────────┬────────────────────┘
                                       │ (promotion)
                     ┌─────────────────▼────────────────────┐
                     │   Tier 2 — Prod secrets store        │
                     │   AWS: Secrets Manager               │
                     │   Azure: Key Vault                   │
                     │   (encrypted at rest with KMS)       │
                     └─────────────────┬────────────────────┘
                                       │ (runtime fetch)
                     ┌─────────────────▼────────────────────┐
                     │   Tier 3 — App secret_service.py     │
                     │   (caches in memory, never logs)     │
                     │   (forwards to ECS / Container Apps) │
                     └──────────────────────────────────────┘
```

### Backend env-var → secrets-store mapping

The `SECRET_BACKEND` env var (`outrena-backend/.env.example`) controls which
tier the app reads from:

| `SECRET_BACKEND` | Source | Use case |
|------------------|--------|----------|
| `env` (default) | `outrena-backend/.env` file | Dev / unit tests |
| `aws` | AWS Secrets Manager (cross-account via task role) | Prod AWS |
| `azure` | Azure Key Vault (via managed identity) | Prod Azure |

In prod, ECS task definitions (`terraform/aws/ecs_*.tf`) and Container Apps
(`terraform/azure/container_apps.tf`) inject secrets via the platform-native
`secrets=[{name, valueFrom}]` block — the app sees them as regular env vars
without ever touching the secrets store directly.

## Secrets Inventory (SaaS layer)

Extends the table in `runbooks/09-secrets-management.md` with the SaaS-layer
secrets added in SAAS-INFRA:

| Secret | Store | Rotation cadence | Rotation method | Used by |
|--------|-------|------------------|-----------------|---------|
| RDS master password | AWS SM + Azure KV | 90 days | AWS Lambda (RDS template) | RDS, ops scripts |
| DATABASE_URL (app role) | AWS SM + Azure KV | 90 days | AWS Lambda (RDS template) | backend, worker |
| Redis AUTH token | AWS SM | 30 days | AWS Lambda (generic) | backend, worker |
| Keycloak admin password | AWS SM + Azure KV | 90 days | Azure Function + manual AWS | Keycloak realm admin |
| Keycloak DB role password | AWS SM | 90 days | AWS Lambda (RDS template) | Keycloak Container App |
| MailBridge URL | AWS SM + Azure KV | operator-only (no-op marker) | manual (upstream rotates) | backend webhook handler |
| **Stripe secret key** (NEW) | AWS SM + Azure KV | 90 days | manual (Stripe dashboard) | backend payment service |
| **Stripe webhook secret** (NEW) | AWS SM + Azure KV | 90 days | manual (Stripe dashboard) | backend webhook handler |
| **Stripe publishable key** (NEW) | AWS SM + Azure KV | n/a (public) | n/a | frontend |
| **ENCRYPTION_KEY (Fernet)** (NEW) | AWS SM + Azure KV | NEVER without re-encryption plan | manual (see §"ENCRYPTION_KEY rotation") | backend column-level encryption |
| JWT signing key (deprecated) | AWS SM | 365 days | manual (or on compromise) | auth service (Keycloak now signs) |
| LLM API keys (per-tenant) | DB column (encrypted with ENCRYPTION_KEY) | 90 days | tenant settings UI | LLM gateway |

## Rotation Schedule (Summary)

| Secret class | Cadence | Mechanism |
|--------------|---------|-----------|
| App-level secrets (Stripe, Redis AUTH) | 30 days | `terraform/aws/secrets_rotation.tf` Lambda + `terraform/azure/key_vault_rotation.tf` Function |
| RDS secrets (master, DATABASE_URL, Keycloak DB) | 90 days | AWS-provided `SecretsManagerRDSPostgreSQLRotationSingleUser` Lambda template |
| Keycloak admin password | 90 days | Azure Function (Azure side); manual via Keycloak Admin API (AWS side) |
| Keycloak client secrets (per-tenant) | 90 days | Tenant settings UI (per-tenant) |
| JWT signing key | 365 days | Manual (currently deprecated — Keycloak signs JWTs) |
| TLS certificates | auto (ACM) / 12 months (Azure KV) | ACM auto-renew; Azure App Gateway annual upload |
| ENCRYPTION_KEY (Fernet) | NEVER without re-encryption plan | Manual — see §"ENCRYPTION_KEY rotation" below |

## How to Rotate Manually

### AWS — trigger immediate rotation

Use `scripts/rotate-secrets.sh` (added in SAAS-INFRA):

```bash
# Rotate a single secret.
scripts/rotate-secrets.sh --provider aws --secret-name outrena-prod-rds-master

# Rotate all OUTRENA-managed secrets (emergency).
scripts/rotate-secrets.sh --provider aws --all

# Dry-run (print the command, don't execute).
scripts/rotate-secrets.sh --provider aws --secret-name outrena-prod-keycloak-admin --dry-run
```

Or call the AWS CLI directly:

```bash
aws secretsmanager rotate-secret --secret-id outrena-prod-rds-master --region us-east-1

# Verify.
aws secretsmanager describe-secret --secret-id outrena-prod-rds-master \
  --query 'LastRotatedDate'
```

### Azure — trigger immediate rotation

The Azure rotation Function App is invoked via the Azure CLI:

```bash
# Rotate a single secret.
scripts/rotate-secrets.sh --provider azure --secret-name db-admin-password

# Rotate all Key Vault secrets.
scripts/rotate-secrets.sh --provider azure --all

# Or invoke the Function directly.
az functionapp invoke \
  --resource-group outrena-prod-rg \
  --name outrena-prd-rotation-fn \
  --function-name rotate_secrets \
  --data '{"secret_name":"db-admin-password"}'
```

### AWS Rotation Lambda deployment (one-time setup)

The RDS rotation Lambda in `terraform/aws/secrets_rotation.tf` delegates to
the AWS-provided `SecretsManagerRDSPostgreSQLRotationSingleUser` template.
The template ships as a Serverless Application Repository (SAR) app — deploy
it once per region:

```bash
# 1. Deploy the SAR app via CloudFormation.
aws serverlessrepo create-cloud-formation-change-set \
  --application-id arn:aws:serverlessrepo:us-east-1:297356227824:applications/SecretsManagerRDSPostgreSQLRotationSingleUser \
  --stack-name outrena-prod-rds-rotation-template \
  --capabilities CAPABILITY_IAM,CAPABILITY_RESOURCE_POLICY

# 2. Wait for the change set to be created, then execute it.
aws cloudformation execute-change-set \
  --change-set-name <change-set-id>

# 3. Once deployed, the SAR app exports a Lambda Layer ARN — attach it to the
#    aws_lambda_function.secret_rotation_rds resource in
#    terraform/aws/secrets_rotation.tf (uncomment the `layers = [...]` line).
#    Then run `terraform apply`.
```

### Azure Function deploy (one-time setup)

The rotation Function App in `terraform/azure/key_vault_rotation.tf` defines
the binding metadata but the actual Python source is deployed via zip deploy:

```bash
# 1. Package the function source (the __init__.py + function.json are inline
#    in the Terraform azurerm_function_app_function resource; you can either
#    extract them or maintain a parallel function_app_source/ directory).
mkdir -p /tmp/rotation-fn/rotate_secrets
cat > /tmp/rotation-fn/rotate_secrets/__init__.py <<'EOF'
# Copy the __init__.py content from terraform/azure/key_vault_rotation.tf
# (the `file { name = "__init__.py" ... }` block).
EOF
cat > /tmp/rotation-fn/rotate_secrets/function.json <<'EOF'
# Copy the function.json content from the same resource.
EOF
cat > /tmp/rotation-fn/host.json <<'EOF'
{"version":"2.0","logging":{"logLevel":{"default":"Information"}}}
EOF
cat > /tmp/rotation-fn/requirements.txt <<'EOF'
azure-functions
azure-identity
azure-keyvault-secrets
EOF
cd /tmp/rotation-fn && zip -r /tmp/rotation-fn.zip .

# 2. Deploy the zip to the Function App.
az functionapp deployment source config-zip \
  --resource-group outrena-prod-rg \
  --name outrena-prd-rotation-fn \
  --src /tmp/rotation-fn.zip

# 3. Verify the function shows up.
az functionapp function show \
  --resource-group outrena-prod-rg \
  --name outrena-prd-rotation-fn \
  --function-name rotate_secrets
```

## How to Add a New Secret

To add a new secret to the OUTRENA stack:

1. **Create the secret in the secrets store:**
   ```bash
   # AWS — add to terraform/aws/secrets.tf (or a new file).
   resource "aws_secretsmanager_secret" "stripe_secret_key" {
     name                    = "${local.name_prefix}-stripe-secret-key"
     description             = "OUTRENA Stripe secret API key"
     kms_key_id              = aws_kms_key.rds.arn
     recovery_window_in_days = 30
     tags = { Name = "${local.name_prefix}-stripe-secret-key-secret" }
   }

   resource "aws_secretsmanager_secret_version" "stripe_secret_key" {
     secret_id = aws_secretsmanager_secret.stripe_secret_key.id
     secret_string = jsonencode({ STRIPE_SECRET_KEY = var.stripe_secret_key })
   }

   # Azure — add to terraform/azure/key_vault.tf.
   resource "azurerm_key_vault_secret" "stripe_secret_key" {
     name         = "stripe-secret-key"
     value        = var.stripe_secret_key
     key_vault_id = azurerm_key_vault.main.id
     tags         = local.default_tags
   }
   ```

2. **Add the env var to `outrena-backend/.env.example`** with a comment
   describing its purpose + where it's stored in prod.

3. **Inject the secret into the ECS task definition:**
   ```hcl
   # terraform/aws/ecs_backend.tf — add to the `secrets` block.
   { name = "STRIPE_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.stripe_secret_key.arn}:STRIPE_SECRET_KEY::" }
   ```

4. **Grant the backend task role read access to the new secret:**
   ```hcl
   # terraform/aws/iam.tf — add the secret ARN to the ecs_execution_secrets policy.
   aws_secretsmanager_secret.stripe_secret_key.arn,
   ```

5. **Add a rotation rule** (if applicable) in `terraform/aws/secrets_rotation.tf`:
   ```hcl
   resource "aws_secretsmanager_secret_rotation" "stripe_secret_key" {
     secret_id           = aws_secretsmanager_secret.stripe_secret_key.id
     rotation_lambda_arn = aws_lambda_function.secret_rotation_generic.arn
     rotation_rules { automatically_after_days = 90 }
     rotate_immediately = false
     depends_on = [aws_lambda_permission.secret_rotation_generic]
   }
   ```

6. **Update the inventory table** in `runbooks/09-secrets-management.md` AND
   this runbook (§Secrets Inventory).

7. **Test:** deploy to staging, verify the backend can read the secret via
   `aws secretsmanager get-secret-value`.

## Emergency Secret Rotation (Compromise Procedure)

Use this procedure when a secret is known or suspected to be compromised.

### SLA: 4 hours from detection

| Step | Owner | Time |
|------|-------|------|
| 1. Confirm compromise | @security-team on-call | 0-30 min |
| 2. Revoke + rotate the compromised secret | @devops-team on-call | 30-90 min |
| 3. Audit access logs for misuse | @security-team | 30-120 min |
| 4. Notify affected tenants (if PII exposure) | @security-team + @legal | 60-240 min |
| 5. Post-incident review | @security-team + @sre-team | within 7 days |

### Step 1 — Confirm compromise

- Triggered by: gitleaks finding, alert from `aws_cloudwatch_metric_alarm.console_login_no_mfa`
  or `root_login`, customer report, or operator discovery.
- Confirm: is the secret value actually exposed (not just a false positive)?
- If yes: declare SEV-1 per `runbooks/05-incident-response.md`.

### Step 2 — Revoke + rotate

```bash
# 2a. Rotate the compromised secret immediately.
scripts/rotate-secrets.sh --provider aws --secret-name <compromised-secret>

# 2b. For RDS master password — the rotation Lambda updates RDS too. Verify:
aws rds describe-db-instances --db-instance-identifier outrena-prod-postgres \
  --query 'DBInstances[0].MasterUserPassword'  # should be empty (rotated)

# 2c. For Keycloak admin — also invalidate active sessions:
curl -sS -X POST "https://auth.outrena.com/admin/realms/outrena/logout-all" \
  -H "Authorization: Bearer $KEYCLOAK_TOKEN"

# 2d. For Stripe — rotate via Stripe dashboard (cannot be done via API).

# 2e. For ENCRYPTION_KEY (Fernet) — DO NOT rotate immediately. See
#     §"ENCRYPTION_KEY rotation" below for the re-encryption plan.
```

### Step 3 — Audit access logs

```bash
# AWS — query CloudTrail for any API call that used the compromised secret.
aws logs start-query \
  --log-group-name "/aws/cloudtrail/outrena-prod" \
  --start-time $(date -d '30 days ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, eventName, userIdentity.arn, sourceIPAddress | filter userIdentity.sessionContext.sessionIssuer.arn = "<compromised-role-arn>" | sort @timestamp desc'

# Azure — query Activity Log for actions by the compromised principal.
az monitor log-analytics query \
  --workspace <security-workspace-id> \
  --analytics-query 'AzureActivity | where Caller == "<compromised-principal>" | project TimeGenerated, OperationNameValue, ResourceId | take 1000'
```

### Step 4 — Notify affected tenants

If PII was exposed, follow `runbooks/05-incident-response.md` §data-breach —
customer notification within 72h per GDPR Article 33.

### Step 5 — Post-incident review

Within 7 days, write a blameless postmortem (template in runbook 05) covering:
- How was the compromise detected?
- What was the blast radius?
- Was the response within SLA?
- What controls should be added to prevent recurrence?

## Secret Scanning

### CI scanning

Gitleaks runs on every PR + nightly in `.github/workflows/security.yml` §secret-scan:

- **Full history scan** — gitleaks scans all commits, not just the diff.
- **SARIF upload** — findings appear in the GitHub Security tab.
- **Push protection** — GitHub repo settings should also enable "secret
  scanning + push protection" (documented in `runbooks/00-README.md`).

### Responding to a gitleaks finding

1. **DO NOT** push a "fix" commit that just removes the secret — the secret is
   already in git history and a fix commit doesn't rotate it.
2. **Rotate the secret immediately** per §Emergency Secret Rotation above.
3. **Remove the secret from git history** (optional, only if the secret was
   pushed to a public branch):
   ```bash
   # Use git-filter-repo (preferred over git-filter-branch).
   pip install git-filter-repo
   git filter-repo --replace-text <(echo "<compromised-secret>==>REDACTED")
   git push --force-with-lease
   ```
4. **Force-push** requires coordination — see `runbooks/00-README.md`
   §force-push-policy (force-push is blocked on main + develop by default).

## Encryption-at-Rest

| Resource | Mechanism | Key | File reference |
|----------|-----------|-----|----------------|
| RDS Postgres | KMS-encrypted storage | `aws_kms_key.rds` (customer-managed, annual rotation) | `terraform/aws/rds.tf:148` |
| ElastiCache Redis | KMS-encrypted at-rest + transit | `aws_kms_key.redis` | `terraform/aws/elasticache.tf:102-103` |
| S3 (csv + collateral + cloudtrail logs) | SSE-KMS | `aws_kms_key.s3` + `aws_kms_key.cloudtrail` | `terraform/aws/s3.tf` + `terraform/aws/cloudtrail.tf` |
| ECR images | KMS-encrypted | `aws_kms_key.s3` | `terraform/aws/ecr.tf:73-76` |
| CloudWatch Logs (app + cloudtrail + secret_rotation) | KMS-encrypted | `aws_kms_key.rds` + `aws_kms_key.cloudtrail` | `terraform/aws/cloudwatch.tf` + `terraform/aws/cloudtrail.tf` |
| Secrets Manager secrets | KMS-encrypted | `aws_kms_key.rds` + `aws_kms_key.redis` | `terraform/aws/{rds,secrets,elasticache}.tf` |
| Azure Postgres | encrypted at rest (default) | platform-managed | `terraform/azure/postgres.tf` |
| Azure Storage | min_tls=TLS1_2, https only | platform-managed | `terraform/azure/storage.tf:31-34` |
| Azure Key Vault | soft-delete 7d + purge protection | platform-managed | `terraform/azure/key_vault.tf:48-49` |
| LLM API keys (DB column) | Fernet symmetric encryption | `ENCRYPTION_KEY` env var | `outrena-backend/.env.example` |
| PII columns (TODO) | Fernet | `ENCRYPTION_KEY` env var | (not yet implemented — see §Open Items) |

## Encryption-in-Transit

| Connection | Mechanism | File reference |
|------------|-----------|----------------|
| Client → ALB (AWS) | TLS 1.3 + 1.2 (`ELBSecurityPolicy-TLS13-1-2-2021-06`) | `terraform/aws/alb.tf:146` |
| HTTP → HTTPS redirect | ALB listener rule (301) | `terraform/aws/alb.tf:163-185` |
| ALB → ECS tasks | TLS termination at ALB; plaintext inside VPC (acceptable per §13.2) | `terraform/aws/alb.tf` |
| ECS → RDS Postgres | TLS (server-side) — RDS forces TLS via `rds.force_ssl=1` parameter | `terraform/aws/rds.tf` |
| ECS → Redis | `transit_encryption_enabled=true` + AUTH token (`rediss://`) | `terraform/aws/elasticache.tf:104-109` |
| ECS → S3 / Secrets Manager | AWS SDK uses HTTPS by default | (no config) |
| S3 bucket policy | Deny non-SSL transport (`aws:SecureTransport=false`) | `terraform/aws/s3.tf:347-375` |
| Client → App Gateway (Azure) | TLS via Key Vault cert | `terraform/azure/app_gateway.tf:155-161` |
| Container Apps → Postgres | TLS (server-side, `public_network_access_enabled=false`) | `terraform/azure/postgres.tf` |
| Container Apps → Redis | `rediss://` (TLS) | `terraform/azure/key_vault.tf:139-165` |
| K8s ingress | cert-manager + letsencrypt-prod ClusterIssuer | `k8s/outrena/values.yaml:275` |
| nginx security headers | HSTS + X-Frame-Options + X-Content-Type-Options | `nginx/nginx.conf:60-64` |

## Least-Privilege

### AWS IAM

- **Per-service task roles:** each ECS service (backend / frontend / worker /
  keycloak) has its own task role with only the permissions it needs
  (`terraform/aws/iam.tf`). No shared roles.
- **No static AWS access keys:** all AWS access is via ECS task role
  (Fargate) or OIDC (GitHub Actions). `.gitignore` excludes `.env` /
  `.env.local` / `~/.aws/credentials`.
- **OIDC for CI/CD:** `.github/workflows/cd-*.yml` use `permissions.id-token:
  write` + `aws-actions/configure-aws-credentials@v4` with `role-to-assume`
  (no static `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` secrets).
- **KMS key policies:** each KMS key has a restrictive policy granting only
  the relevant service principal (RDS / S3 / CloudTrail / CloudWatch Logs).
  See `terraform/aws/{rds,s3,cloudtrail}.tf` `data "aws_iam_policy_document"
  "kms_*"`.

### Azure RBAC

- **Per-Container-App managed identities:** each Container App has its own
  user-assigned identity with `Key Vault Secrets User` role on the Key Vault
  (`terraform/azure/managed_identities.tf`). No shared service principals.
- **Key Vault RBAC mode:** `enable_rbac_authorization = true` — no access
  policies (which would be too coarse-grained).
- **Network ACLs on Key Vault:** `default_action = "Deny"` — only the App,
  Idp, and Data subnets can hit the data plane
  (`terraform/azure/key_vault.tf:57-69`).
- **OIDC for CI/CD:** `terraform/azure/versions.tf` backend uses `use_oidc =
  true`; GitHub Actions uses `azure/login@v1` with OIDC federation.

### JIT access

- **Production AWS console access** is via SSO (Azure AD federated) with
  time-bound (1-hour) sessions. No long-lived IAM users with console access.
- **Production Azure portal access** is via PIM (Privileged Identity
  Management) — Owner role requires explicit activation with MFA + approval.
- **Bastion / SSM access** to private resources is via AWS Systems Manager
  Session Manager (no SSH keys on bastions).

## ENCRYPTION_KEY (Fernet) Rotation

The `ENCRYPTION_KEY` env var is a Fernet symmetric key used for column-level
encryption of LLM API keys + (TODO) PII columns in the database.

**NEVER rotate `ENCRYPTION_KEY` without a re-encryption plan.**

### Why rotation is hard

Fernet keys encrypt data at rest in the database. If you change the key,
all existing ciphertext becomes undecryptable. You must:

1. Add the new key to the keyring (Fernet supports multi-key rotation — the
   `cryptography.fernet.MultiFernet` class decrypts with any key in the
   keyring, encrypts with the first).
2. Run a re-encryption script that reads every encrypted row, decrypts with
   the old key, re-encrypts with the new key, and writes back.
3. After re-encryption is complete + verified, remove the old key from the
   keyring.

### Rotation procedure (planned — not yet implemented)

```bash
# 1. Generate the new key.
NEW_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Store both old + new keys in the secrets store as a comma-separated list
#    (MultiFernet format: "new_key,old_key").
aws secretsmanager update-secret \
  --secret-id outrena-prod-encryption-key \
  --secret-string "$NEW_KEY,$OLD_KEY"

# 3. Deploy the backend — it reads the new keyring and can decrypt both old
#    and new ciphertext.

# 4. Run the re-encryption script (TODO: scripts/re-encrypt-llm-keys.py).
#    This reads every LLM API key, re-encrypts with the new key, writes back.

# 5. Verify re-encryption: pick a sample tenant, confirm their LLM key still
#    works (the backend decrypts + uses it to call the LLM gateway).

# 6. Remove the old key from the keyring.
aws secretsmanager update-secret \
  --secret-id outrena-prod-encryption-key \
  --secret-string "$NEW_KEY"

# 7. Deploy the backend again — it now uses only the new key.
```

Until the re-encryption script is implemented (§Open Items), the
`ENCRYPTION_KEY` MUST NOT be rotated.

## Open Items (TODO — out of scope for SAAS-INFRA)

- **`scripts/re-encrypt-llm-keys.py`** — re-encryption script for
  ENCRYPTION_KEY rotation. Required before ENCRYPTION_KEY can be rotated.
- **App-layer column-level encryption for LLM API keys** — currently stored
  as plaintext `String` columns in `app/models/config_models.py:44`. Use the
  `ENCRYPTION_KEY` Fernet key (now documented in `.env.example`) to encrypt
  on write + decrypt on read. SURVEY-INFRA gap A8.
- **`scripts/audit-log-retention.py`** — daily cron for `platform_audit_log`
  retention. See runbook 10 §Open Items.
- **`AuditLog` SQLAlchemy model** — referenced as `platform_audit_log` table
  but not currently a model in `app/models/`. See runbook 10 §Open Items.
- **`platform_audit_log` retention** — the table itself needs creating
  (Alembic migration) + the retention cron implemented.
