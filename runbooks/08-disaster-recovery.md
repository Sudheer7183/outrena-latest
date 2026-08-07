---
title: Disaster Recovery + Backup/Restore Runbook
last_updated: 2025-01-15
severity: SEV-1
owner: OUTRENA SRE
---

# Disaster Recovery + Backup/Restore Runbook

Backup inventory, restore procedures, and cross-region failover for the OUTRENA
platform. Implements the DR plan referenced in migration doc §16.

## Prerequisites

- Operator has prod AWS + Azure admin access.
- For restores: a quiet maintenance window OR a SEV-1 (restore during a SEV-1 is the
  primary use case).
- DR drill scheduled quarterly (see `DR Drill` section).

## RPO / RTO Targets

| Resource | RPO | RTO | Mechanism |
|----------|-----|-----|-----------|
| RDS Postgres | 5 min (PITR) | 1 hr | Automated backups + PITR |
| ElastiCache Redis | 1 hr (snapshot) | 15 min | Daily snapshot (best-effort; Redis is a cache, not a source of truth) |
| S3 (CSV uploads, collateral) | 0 (versioning + CRR) | 15 min | S3 versioning + cross-region replication |
| Keycloak realm config | 24 hr | 30 min | Daily realm export |
| ECS / Container Apps (code) | 0 (in ECR/ACR + git) | 10 min | Re-deploy from registry |
| Terraform state | 0 (S3 + versioning) | 15 min | Terraform state in versioned S3 bucket |
| Secrets (Secrets Manager / Key Vault) | 0 (managed service) | 5 min | Secrets Manager / Key Vault SLA |

Overall platform RPO: **5 min** (dominated by RDS PITR). RTO: **1 hr**.

## Backup Inventory

### RDS automated backups

- **Retention:** 35 days.
- **PITR:** enabled; can restore to any 5-min point in the retention window.
- **Snapshots:** automated daily; retained 35 days.
- **Manual snapshots:** taken before each migration (see `02-schema-migration.md`).
- Terraform: `terraform/aws/rds.tf` — `backup_retention_period=35`,
  `storage_autoscaling=true`.

```bash
# List recent snapshots.
aws rds describe-db-snapshots --db-instance-identifier outrena-prod \
  --snapshot-type automated --query 'DBSnapshots[*].{id:DBSnapshotIdentifier,created:SnapshotCreateTime}' \
  --output table

# List manual snapshots (pre-migration).
aws rds describe-db-snapshots --db-instance-identifier outrena-prod \
  --snapshot-type manual --query 'DBSnapshots[*].{id:DBSnapshotIdentifier,created:SnapshotCreateTime}' \
  --output table
```

### ElastiCache snapshots

- **Retention:** 7 days.
- **Frequency:** daily (04:00 UTC).
- Terraform: `terraform/aws/elasticache.tf` — `snapshot_retention_limit=7`,
  `snapshot_window="04:00-05:00"`.

### S3 versioning + cross-region replication

- **Versioning:** enabled on all prod buckets (`csv-uploads`, `collateral`,
  `terraform-state`, `backups`).
- **CRR:** `csv-uploads` + `collateral` replicate to the DR region
  (`us-west-2` for AWS prod in `us-east-1`).
- **Lifecycle:** STANDARD → STANDARD_IA (30d) → GLACIER (90d) → DEEP_ARCHIVE (365d).

### Keycloak realm export

- **Frequency:** daily cron (03:00 UTC).
- **Script:** `scripts/export_keycloak_realm.sh`.
- **Output:** `s3://outrena-backups/keycloak/realm-export-<YYYYMMDD>.json`.
- **Retention:** 90 days.

```bash
# Manual export (ad-hoc, e.g. before a Keycloak upgrade).
scripts/export_keycloak_realm.sh --output /tmp/realm-export.json
aws s3 cp /tmp/realm-export.json \
  s3://outrena-backups/keycloak/realm-export-manual-$(date +%Y%m%d%H%M).json
```

## Restore Procedures

### RDS point-in-time recovery

> **⚠️ Warning:** PITR restores to a **new** RDS instance. You cannot overwrite the
> existing instance. Plan a cutover (rename DNS / update connection string).

```bash
# 1. Pick a restore point (UTC, within last 35 days).
RESTORE_TIME="2025-01-14 10:30:00"
NEW_INSTANCE_ID="outrena-prod-restored-$(date +%Y%m%d%H%M)"

# 2. Restore to a new instance.
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier outrena-prod \
  --target-db-instance-identifier $NEW_INSTANCE_ID \
  --restore-time "$RESTORE_TIME" \
  --db-instance-class db.r6g.2xlarge \
  --publicly-accessible false \
  --vpc-security-group-ids <sg-id>

# 3. Wait for the new instance to become available (10-30 min).
aws rds wait db-instance-available --db-instance-identifier $NEW_INSTANCE_ID

# 4. Test connectivity from a bastion.
psql -h <new-endpoint> -U outrena_app -d outrena -c "SELECT count(*) FROM public.tenants;"

# 5. Verify schema health.
python scripts/verify_schema_health.py --all-tenants \
  --database-url "postgresql://outrena_app:***@<new-endpoint>/outrena"

# 6. Promote: update the connection string in Secrets Manager + restart backend tasks.
aws secretsmanager update-secret \
  --secret-id /outrena/prod/database-url \
  --secret-string "postgresql://outrena_app:***@<new-endpoint>/outrena"
aws ecs update-service --cluster outrena-prod --service outrena-backend \
  --force-new-deployment

# 7. Once traffic is on the new instance, rename or decommission the old.
aws rds rename-db-instance --db-instance-identifier outrena-prod \
  --new-db-instance-identifier outrena-prod-old
aws rds rename-db-instance --db-instance-identifier $NEW_INSTANCE_ID \
  --new-db-instance-identifier outrena-prod
# Keep the old instance for 7 days, then delete.
```

### RDS snapshot restore (manual snapshot)

```bash
# 1. Pick a manual snapshot (typically pre-migration).
SNAPSHOT_ID="outrena-prod-pre-migration-20250114"

# 2. Restore.
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier outrena-prod-restored \
  --db-snapshot-identifier $SNAPSHOT_ID \
  --db-instance-class db.r6g.2xlarge \
  --vpc-security-group-ids <sg-id>

# 3-7. Same as PITR (above).
```

### S3 version restore

```bash
# 1. List versions of an object.
aws s3api list-object-versions --bucket outrena-csv-uploads \
  --prefix tenants/acme-corp/uploads/2025/01/14/some-file.csv \
  --query 'Versions[*].{id:VersionId,lastModified:LastModified,isLatest:IsLatest,deleted:IsDeleteMarker}' \
  --output table

# 2. Restore a specific version (copy over the current).
aws s3api get-object --bucket outrena-csv-uploads \
  --key tenants/acme-corp/uploads/2025/01/14/some-file.csv \
  --version-id <version-id> /tmp/restored-file.csv

aws s3 cp /tmp/restored-file.csv \
  s3://outrena-csv-uploads/tenants/acme-corp/uploads/2025/01/14/some-file.csv

# 3. For a deleted object, just remove the delete marker.
aws s3api delete-object --bucket outrena-csv-uploads \
  --key tenants/acme-corp/uploads/2025/01/14/some-file.csv \
  --version-id <delete-marker-version-id>
```

### Keycloak realm import

```bash
# 1. Download the latest realm export.
aws s3 cp s3://outrena-backups/keycloak/realm-export-20250114.json /tmp/realm-export.json

# 2. Import into Keycloak (only if the realm is missing or corrupt).
# Via Admin CLI:
/opt/keycloak/bin/kcadm.sh config credentials --server https://auth.outrena.com \
  --realm master --user admin --password "$KEYCLOAK_ADMIN_PASSWORD"
/opt/keycloak/bin/kcadm.sh create realms -f /tmp/realm-export.json

# Or via the admin UI: Import → select file → Import. Choose "Skip if exists" for a
# partial restore, "Overwrite" for a full restore.
```

> **⚠️ Warning:** Realm import overwrites clients + groups. If only one client is
> broken, prefer importing a single client JSON via the UI rather than the full realm.

### ElastiCache restore

```bash
# Restore from a snapshot to a new cluster.
aws elasticache create-cache-cluster \
  --cache-cluster-id outrena-prod-restored \
  --cache-node-type cache.r6g.2xlarge \
  --engine redis \
  --snapshot-arn arn:aws:elasticache:us-east-1:123456789012:snapshot:outrena-prod-20250114 \
  --num-cache-nodes 1 \
  --cache-subnet-group-name outrena-prod \
  --security-group-ids <sg-id>

# Cutover: update the Redis endpoint env var + restart backend tasks.
```

## Cross-Region Failover

The DR region is **us-west-2** (prod primary is us-east-1). Cross-region failover uses
Route 53 failover routing.

### Trigger criteria

Failover to DR is a SEV-1 decision. Trigger if:

- us-east-1 is fully unavailable (RDS, ECS, ALB all down) AND
- AWS status page confirms a regional outage AND
- Estimated recovery >1 hr.

If only one service (e.g. RDS) is down, prefer the in-region restore procedures above.

### Procedure

```bash
# 1. Confirm DR region is healthy (RDS + ECS + ALB in us-west-2).
aws rds describe-db-instances --db-instance-identifier outrena-dr --region us-west-2 \
  --query 'DBInstances[0].DBInstanceStatus'
aws ecs describe-services --cluster outrena-dr --services outrena-backend --region us-west-2 \
  --query 'services[0].status'

# 2. Verify the DR RDS has fresh data (within RPO).
# (Last replicated transaction timestamp — check the CRR / DMS replication lag metric.)
aws cloudwatch get-metric-statistics --namespace AWS/DMS --metric-name CDCLatencySource \
  --dimensions Name=ReplicationInstanceIdentifier,Value=outrena-dr-repl \
  --start-time $(date -u -d '15 min ago' +%FT%TZ) --end-time $(date -u +%FT%TZ) \
  --period 60 --statistics Average

# 3. Flip Route 53 to DR.
aws route53 change-resource-record-sets --hosted-zone-id <HZ_ID> \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.outrena.com.",
        "Type": "CNAME",
        "TTL": 60,
        "ResourceRecords": [{"Value": "outrena-dr-alb.us-west-2.elb.amazonaws.com"}]
      }
    }]
  }'

# 4. Wait for DNS propagation (60 s TTL).
dig +short api.outrena.com
# Expected: outrena-dr-alb.us-west-2.elb.amazonaws.com

# 5. Verify traffic is serving from DR.
curl -fsS https://api.outrena.com/health/ready | jq '.region'
# Expected: "us-west-2"

# 6. Notify customers (if customer-visible) + page SRE lead + product eng lead.
```

### Failback to primary

Once us-east-1 is healthy:

```bash
# 1. Reverse the data replication: DMS from DR (us-west-2) back to primary (us-east-1).
# 2. Verify replication lag is 0.
# 3. Flip Route 53 back to us-east-1.
aws route53 change-resource-record-sets --hosted-zone-id <HZ_ID> \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.outrena.com.",
        "Type": "CNAME",
        "TTL": 60,
        "ResourceRecords": [{"Value": "outrena-prod-alb.us-east-1.elb.amazonaws.com"}]
      }
    }]
  }'

# 4. Verify + monitor 24 hr.
```

## DR Drill (Quarterly)

A full DR drill is run in **staging** quarterly (Q1: Jan, Q2: Apr, Q3: Jul, Q4: Oct).
Owner: SRE lead.

### Drill procedure

1. Pick a snapshot from the last 24 hr.
2. Restore RDS to a fresh staging instance. Measure restore time (target <30 min).
3. Restore one S3 object from a version. Measure (target <5 min).
4. Restore Keycloak realm export into a fresh Keycloak instance. Measure (target <15
   min).
5. Failover staging to DR (test the Route 53 flip; immediately flip back).
6. Run the E2E suite against the restored stack. Must pass.
7. Write a drill report: timings, gaps, action items. File under
   `migration/dr-drills/<YYYY-MM>.md`.
8. Action items tracked as GitHub Issues labeled `dr-drill`.

### Drill pass criteria

- RDS restore: <30 min.
- S3 restore: <5 min.
- Keycloak restore: <15 min.
- E2E suite: green.
- Total simulated RTO: <1 hr.

If any criterion fails, the drill is a fail. File an action item to fix the gap before
the next quarter's drill.

## Verification

After any restore:

```bash
# 1. Schema health on all tenants.
python scripts/verify_schema_health.py --all-tenants

# 2. Tenant count matches backup.
psql -c "SELECT count(*) FROM public.tenants WHERE status='active';"
# Compare to backup-time count (recorded in the snapshot metadata).

# 3. End-to-end: login, create contact, send test sequence.

# 4. Grafana outrena-overview — no alerts firing.

# 5. Tenant-isolation check: cross-tenant 403 rate stable.
```

## Rollback

A restore is itself a rollback mechanism — there is no rollback of a restore. If a
restore is bad, restore from an earlier snapshot.

For failover: the rollback is failback (see above).

## Escalation

| Symptom | Escalate To | When |
|---------|-------------|------|
| RDS restore stuck >1 hr | DBA + AWS support | SEV-1 |
| Restore produces corrupt data | SRE lead + DBA + page AWS support | SEV-1 immediately |
| Cross-region failover DNS stuck >10 min | SRE lead + page AWS support | SEV-1 |
| DR region also down | SRE lead + VP Engineering + customer success | SEV-1; consider status.outrena.com notice |
| DR drill fails any criterion | SRE lead — schedule remediation | Within 1 business day |
| Backup itself is missing/corrupt | SRE lead + DBA | SEV-2; this is a pre-SEV-1 risk |

## Related

- `02-schema-migration.md` — pre-migration snapshots.
- `03-rollback.md` — rollback vs. restore decision.
- `09-secrets-management.md` — secrets are not in scope for DR (managed services).
- Migration doc §16 (rollback plan, DR targets).
