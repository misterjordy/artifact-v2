# Sprint 14: COSMOS Port

**Depends on**: Sprint 13 (hardened platform), COSMOS billing resolved
**Scope**: Move from A2 VPS to COSMOS AWS GovCloud IL-4/5

## Definition of Success
- `terraform apply` creates all COSMOS infrastructure (RDS, ECS, ElastiCache, S3, ALB)
- Docker images pushed to ECR, ECS Fargate runs them
- CAC login works end-to-end (SAML assertion → artiFACT session)
- v1 data migrated to v2 PostgreSQL with zero data loss
- All integration tests pass against COSMOS environment
- `artifact.cosmos.navy.mil` serves the production app
- Blue/green deploy tested: push a change, zero downtime

## Pre-Requisites
```
[ ] COSMOS product account created and funded
[ ] A record: artifact.cosmos.navy.mil → ALB DNS
[ ] COSMOS SAML metadata URL obtained from COSMOS team
[ ] ECR repository created
[ ] Terraform state bucket created in S3
```

## ⚠️ MUST CHANGE BEFORE PROD — DO NOT SKIP

**FIPS 140 Cryptography**: The dev VPS uses standard OpenSSL. COSMOS prod MUST use FIPS-validated OpenSSL. Add to Dockerfile:
```dockerfile
ENV OPENSSL_FIPS=1
# Verify: python -c "import ssl; print(ssl.OPENSSL_VERSION)"
# Must show "fips" in the version string
```
Test that AI key encryption and session signing still work after enabling FIPS mode.

**Iron Bank Base Images**: The dev VPS uses `python:3.12-slim` from Docker Hub. COSMOS prod MUST use the DISA STIG-hardened image from Platform One's Iron Bank:
```dockerfile
# DEV (Docker Hub — fine for VPS)
FROM python:3.12-slim

# PROD (Iron Bank — required for COSMOS)
FROM registry1.dso.mil/ironbank/opensource/python/python:3.12
```
You'll need a Platform One account to pull from Iron Bank. The image is pre-hardened and vulnerability-scanned. Test the full stack with the Iron Bank image before go-live — some system packages may differ.

**Amazon Bedrock Provider**: Add `bedrock` as a provider option in `kernel/ai/provider.py`. On COSMOS, users should use Bedrock (IL-4/5 authorized within GovCloud boundary — CUI never leaves). On VPS dev, use commercial OpenAI/Anthropic with synthetic data only.
```python
# kernel/ai/provider.py — add alongside openai/anthropic/azure clients
elif provider == 'bedrock':
    return await self._call_bedrock(messages, model='anthropic.claude-sonnet-4-20250514-v1:0', ...)
```

## Step-by-Step

### 1. Terraform Infrastructure
```
terraform/environments/prod/main.tf:
  module "vpc"   — VPC + subnets in GovCloud region (us-gov-west-1)
  module "rds"   — PostgreSQL 16, db.t3.small, Multi-AZ, 35-day backups
  module "redis" — ElastiCache cache.t3.micro
  module "s3"    — Buckets: uploads, exports, snapshots (versioning enabled)
  module "ecr"   — Container registry
  module "ecs"   — Fargate cluster, 2 web tasks + 1 worker task
  module "alb"   — Application Load Balancer + TLS cert

terraform init
terraform plan -out=plan.tfplan
# Review plan carefully
terraform apply plan.tfplan
```

### 2. Push Docker Images
```bash
# Build production images (no --reload, no dev deps)
docker build -t artifact-web -f docker/Dockerfile --target production .
docker build -t artifact-worker -f docker/Dockerfile.worker --target production .

# Tag for ECR
docker tag artifact-web $ECR_URI/artifact-web:v1.0.0
docker tag artifact-worker $ECR_URI/artifact-worker:v1.0.0

# Push
docker push $ECR_URI/artifact-web:v1.0.0
docker push $ECR_URI/artifact-worker:v1.0.0
```

### 3. Configure Environment Variables
```
ECS Task Definition environment:
  DATABASE_URL=postgresql+asyncpg://artifact:PASSWORD@RDS_ENDPOINT:5432/artifact_prod
  REDIS_URL=redis://REDIS_ENDPOINT:6379
  S3_ENDPOINT=https://s3.us-gov-west-1.amazonaws.com
  S3_BUCKET=artifact-prod
  SECRET_KEY=<generated 64-char random>
  APP_ENV=production
  SAML_ENTITY_ID=https://artifact.cosmos.navy.mil
  SAML_ACS_URL=https://artifact.cosmos.navy.mil/api/v1/auth/saml/callback
  SAML_METADATA_URL=<from COSMOS team>
  AI_KEY_MASTER=<from Secrets Manager ARN>
```

### 4. Run Migrations
```bash
# Via ECS exec (requires enable-execute-command on task)
aws ecs execute-command --cluster artifact --task TASK_ID \
  --container web --interactive --command "alembic upgrade head"
```

### 5. CAC Integration
```
modules/auth_admin/cac_mapper.py:
  In production (APP_ENV=production):
    Parse SAML assertion from COSMOS identity provider
    Extract EDIPI, DN, email, display_name
    Map to fc_user record (create on first login)
    Create session in Redis
    Redirect to app

  Dev-mode login (APP_ENV=development):
    Username/password form (existing Sprint 1 flow)
    Disabled in production
```

### 6. Migrate v1 Data
```bash
# On a machine with access to both databases:

# Export v1
mysqldump -u techstat_factadmin -p techstat_factcorpus > v1_dump.sql

# Run migration script
python scripts/migrate_v1_to_v2.py \
  --source v1_dump.sql \
  --target postgresql://artifact:PASSWORD@RDS_ENDPOINT:5432/artifact_prod

# Validation output:
#   Migrated 719 facts (719 expected) ✓
#   Migrated 744 versions (744 expected) ✓
#   Migrated 218 nodes (218 expected) ✓
#   Backfilled 763 created_by_uid values ✓
#   Backfilled published_at on auto-published versions ✓
#   All facts have non-NULL created_by_uid ✓
#   All published versions have non-NULL published_at ✓
```

### 7. Verify Production
```bash
# Health check
curl https://artifact.cosmos.navy.mil/api/v1/health

# CAC login (in browser with CAC reader)
# Navigate to https://artifact.cosmos.navy.mil
# → COSMOS SAML redirect → CAC PIN prompt → authenticated

# Run integration tests against prod
pytest tests/integration/ --base-url=https://artifact.cosmos.navy.mil
```

### 8. Blue/Green Deploy Test
```bash
# Make a trivial change (e.g., bump version string)
# Push to ECR with new tag
docker tag artifact-web $ECR_URI/artifact-web:v1.0.1
docker push $ECR_URI/artifact-web:v1.0.1

# Update ECS service
aws ecs update-service --cluster artifact --service web \
  --force-new-deployment --task-definition artifact-web:LATEST

# Watch: old tasks drain, new tasks start, health checks pass
aws ecs describe-services --cluster artifact --services web \
  --query 'services[0].deployments'

# Verify zero downtime: run curl in a loop during deploy
while true; do curl -s -o /dev/null -w "%{http_code}\n" https://artifact.cosmos.navy.mil/api/v1/health; sleep 1; done
# Should see 200 200 200 200 200 continuously
```

### 9. Post-Launch
```
[ ] Monitor CloudWatch for 48 hours
[ ] Verify CAC login with multiple users (different branches, different roles)
[ ] Run full E2E test suite
[ ] Set up CloudWatch alarms (error rate > 1%, p95 > 2s, queue depth > 50)
[ ] Configure RDS automated snapshots verified
[ ] Document runbook: deploy, rollback, scale up, scale down
[ ] Cancel A2 VPS after 30 days of stable production
```

## Rollback Plan
```
IF deployment fails:
  ECS automatically keeps old tasks running (health check failure → no traffic shift)
  
IF data migration has issues:
  RDS PITR: restore to any second before migration started
  
IF CAC integration fails:
  Set APP_ENV=development temporarily to enable password login
  Debug SAML assertion parsing
  Re-enable CAC when fixed
```
