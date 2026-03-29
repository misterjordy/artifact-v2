# Sprint 13: Polish + Harden

**Depends on**: All previous sprints
**Scope**: Cross-cutting security, error handling, test coverage, performance

## Definition of Success
- Security headers on all responses (CSP, X-Frame-Options, HSTS, X-Content-Type-Options)
- Rate limits tuned per endpoint
- Custom 401, 403, 404, 500 error pages (styled, not raw JSON in browser)
- All 56 unit test files pass
- All integration tests pass
- All E2E tests pass
- `ruff check` and `mypy` clean (zero errors)
- Coverage ≥ 80%
- OpenAPI spec at `/api/v1/openapi.json` complete and valid
- Load test: 50 concurrent users, p95 < 2s

## Deliverables

### Security Headers Middleware
```
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

### Rate Limit Tuning
```
auth/login:       10/min per IP (brute force protection)
facts/create:     30/hr per user
facts/edit:       60/hr per user
ai/chat:          150/hr per user
ai/search:        60/hr per user
import/upload:    10/hr per user
import/analyze:   10/hr per user
export/factsheet: 30/hr per user
export/document:  9/hr per user
feedback/submit:  1/min per IP
```

### Error Pages
```
templates/errors/401.html — "Authentication required" with login link
templates/errors/403.html — "Access denied" with explanation
templates/errors/404.html — "Page not found" with search + home link
templates/errors/500.html — "Something went wrong" with support contact
```

### Load Test Script
```python
# tests/load/locustfile.py (using Locust — FOSS)
class ArtifactUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.client.post("/api/v1/auth/login", json={...})

    @task(5)
    def browse_tree(self):
        self.client.get("/api/v1/nodes")

    @task(3)
    def browse_facts(self):
        self.client.get(f"/api/v1/facts?node_uid={random_node}")

    @task(2)
    def search(self):
        self.client.get(f"/api/v1/search?q={random_term}")

    @task(1)
    def queue_check(self):
        self.client.get("/api/v1/queue/counts")
```

### OWASP ZAP Dynamic Application Security Test
```yaml
# Add to .gitlab-ci.yml
zap-scan:
  stage: test
  image: ghcr.io/zaproxy/zaproxy:stable
  script:
    - zap-baseline.py -t https://artifact.jordanaallred.com -r zap-report.html -l WARN
  artifacts:
    paths: [zap-report.html]
  allow_failure: true  # Don't block deploy on first run — review findings, then enforce
```
Baseline scan covers: XSS, SQL injection, CSRF, missing headers, cookie flags, clickjacking, directory traversal, information disclosure. Review the HTML report and fix any HIGH/MEDIUM findings before enforcing `allow_failure: false`.
```

### OpenAPI Validation
```bash
# Dump spec and validate
curl https://artifact.jordanaallred.com/api/v1/openapi.json > openapi.json
npx @apidevtools/swagger-cli validate openapi.json
```

### Coverage Report
```bash
docker compose exec web pytest --cov=artiFACT --cov-report=html --cov-fail-under=80
# Open htmlcov/index.html to see per-file coverage
```

## Checklist
```
[ ] Security headers middleware added and verified
[ ] All rate limits configured in fc_system_config
[ ] Error pages styled and rendering correctly
[ ] ruff check . — zero errors
[ ] ruff format --check . — zero changes needed
[ ] mypy artiFACT/ --strict — zero errors
[ ] pytest — all tests pass
[ ] pytest --cov — coverage ≥ 80%
[ ] OpenAPI spec validates
[ ] Locust load test: 50 users, p95 < 2s
[ ] Manual walkthrough: create user → create node → create fact → approve → sign → export
[ ] SSP skeleton complete
[ ] Control implementation statements drafted
[ ] Incident response runbook written
[ ] SBOM archived with release
[ ] ZT: Read-access logging active for export, AI chat, bulk browse
[ ] ZT: Anomaly detector configured and tested
[ ] ZT: Auto-session-expire on anomaly trigger verified
[ ] ZT: Structured log forwarding configured (for COSMOS SIEM/CSSP)
```

## Zero Trust Compliance (Pillars 5, 6, 7)

### Read-Access Logging (ZT Pillar 5 — Data)
```
Create: kernel/access_logger.py

Log to fc_event_log with entity_type='access' for these actions:
  - export/factsheet    → log user_uid, format, node filter, fact count returned
  - ai/chat             → log user_uid, topic/node selected, fact count loaded into prompt
  - sync/changes        → log api_key_uid, cursor, record count returned
  - sync/full           → log api_key_uid, total record count

DO NOT log:
  - Every page view (noise)
  - Every search query (noise)
  - Node tree browsing (noise)

Log only data-access patterns that would be relevant to an insider threat investigation:
  "Who exported what, who asked the AI about what, who pulled the delta feed."

Implementation: FastAPI middleware that fires AFTER the response, non-blocking (background task).
Should add <5ms latency to logged endpoints.
```

### Anomaly Detection (ZT Pillar 6 — Visibility & Analytics)
```
Create: modules/admin/anomaly_detector.py

Rules (configurable via fc_system_config):
  RULE 1: Export flood
    IF user performs > 10 exports in 30 minutes → flag
  RULE 2: AI corpus mining
    IF user makes > 50 AI chat requests in 1 hour → flag
  RULE 3: Off-hours bulk access
    IF user performs > 5 data-access events between 0000-0500 local → flag
  RULE 4: Scope escalation attempt
    IF user receives > 10 permission denied (403) responses in 10 minutes → flag

On flag:
  1. Log anomaly event to fc_event_log (entity_type='anomaly')
  2. Auto-expire ALL of the user's sessions in Redis (force re-CAC)
  3. Send alert to admin dashboard (real-time via SSE if admin is online)
  4. DO NOT auto-deactivate — admin reviews and decides

Implementation: Celery beat task runs every 5 minutes, scans recent events.
  Alternatively: inline check on the hot-path endpoints (export, AI chat)
  using Redis counters (same pattern as rate limiter, different thresholds).
```

### Auto-Session-Expire on Anomaly (ZT Pillar 7 — Automation & Orchestration)
```
When anomaly_detector flags a user:
  1. Call kernel/auth/session.py → force_destroy_user_sessions(user_uid)
     This scans Redis for all keys matching "session:*" with this user_uid
     and deletes them immediately.
  2. User's next request → session cookie invalid → 401 → must re-authenticate via CAC
  3. If CAC is still valid, user gets back in — but the anomaly is logged and admin is notified.
  4. If admin deactivated the user during the lockout, re-auth fails permanently.

This closes the gap between "8-hour session" and "continuous verification":
  Normal behavior: session re-validated every 15 min (Sprint 1)
  Anomalous behavior: session killed immediately, force re-auth
```

### Structured Log Forwarding (ZT Pillar 6 — Visibility & Analytics)
```
Create: kernel/log_forwarder.py

artiFACT emits structured JSON logs via structlog.
On COSMOS, forward these to CloudWatch Logs (already done by ECS).
COSMOS's LANT CSSP SIEM can ingest CloudWatch Logs.

Log format (every log line):
{
  "timestamp": "2026-03-28T15:30:00Z",
  "level": "info",
  "event": "fact.approved",
  "user_uid": "abc-123",
  "ip": "hashed",
  "session_id": "def-456",
  "entity_type": "version",
  "entity_uid": "ghi-789",
  "node_uid": "jkl-012",
  "request_id": "mno-345"      ← correlate all logs for a single request
}

On VPS (dev): logs go to stdout → docker compose logs
On COSMOS (prod): logs go to stdout → ECS → CloudWatch → SIEM

No special infrastructure needed — structlog + CloudWatch + ECS handles it.
Ask COSMOS team: "What format does LANT CSSP want logs in?"
If they want CEF or syslog, add a formatter in structlog config.
```

## ZT Tests
```
test_read_access_logged_on_export
test_read_access_logged_on_ai_chat
test_read_access_not_logged_on_page_view
test_anomaly_detector_flags_export_flood
test_anomaly_detector_flags_off_hours_bulk
test_anomaly_auto_expires_sessions
test_force_reauth_after_session_expire
test_structured_logs_have_request_id
test_structured_logs_have_user_uid
```

## RMF Compliance Artifacts

### System Security Plan (SSP) Skeleton
```
Create: docs/rmf/ssp.md

1. System Identification
   - Name: artiFACT
   - Type: Major Application
   - Categorization: MODERATE (C-M, I-M, A-L)
   - Impact Level: IL-4/5 (CUI)
   - Hosting: COSMOS (NIWC Pacific, AWS GovCloud)
   - Authorization boundary: Inherits COSMOS CNAP/ZT boundary
   - See: docs/rmf/boundary-diagram.md

2. System Description
   - Purpose: Taxonomy-driven atomic fact corpus platform
   - Users: DoD program managers, engineers, approvers, signatories
   - Data: Unclassified program documentation decomposed into atomic facts
   - Authentication: CAC via COSMOS SAML (M365 federated identity)

3. System Architecture
   - See: artifact-v2-architecture.md (sections 2-3)
   - See: docs/rmf/data-flow.md

4. Security Controls
   - See: docs/rmf/control-implementations.md
   - Inherited from COSMOS: AC-2, AU-2, AU-3, IA-2, SC-7, SC-8, SC-28, etc.
   - Implemented by artiFACT: AC-3, AC-6, AU-12, CM-7, IA-8, SI-10, etc.

5. Continuous Monitoring
   - CloudWatch alarms, Grafana dashboards
   - SBOM generated per release (CycloneDX)
   - pip-audit in CI (known vulnerability scan)
   - RegScale integration (when on COSMOS)
```

### Control Implementation Statements
```
Create: docs/rmf/control-implementations.md

AC-3 (Access Enforcement):
  artiFACT enforces role-based access control via kernel/permissions/resolver.py.
  Every API endpoint calls permissions.can(user, action, node_uid) before
  executing. Roles are hierarchical: viewer < contributor < subapprover <
  approver < signatory < admin. Per-node grants override global roles.
  Verified by: test_subapprover_cannot_reject_outside_scope,
  test_contributor_with_node_grant_can_approve, etc.

AC-6 (Least Privilege):
  Users receive 'viewer' role by default on first CAC login.
  Elevated roles require explicit admin grant.
  Per-node grants scope access to specific taxonomy branches.
  API keys support scoped permissions (read-only for machine clients).

AU-12 (Audit Generation):
  fc_event_log records every state-changing action with actor, timestamp,
  entity, and payload. Append-only design — no DELETE on event_log.
  Retention: 2 years in database, then archived to S3.
  Verified by: test_event_recorded_on_create, test_event_recorded_on_retire.

CM-7 (Least Functionality):
  Modules can be disabled via admin feature flags without code deployment.
  Only required services run (no SSH daemon in containers, no debug endpoints
  in production). Dev-mode login disabled when APP_ENV=production.

IA-8 (Identification and Authentication):
  All users authenticate via DoD CAC through COSMOS SAML/CNAP.
  No passwords stored. EDIPI used as unique identifier.
  Session tokens stored in Redis with 8-hour TTL.
  Machine clients use API keys (SHA-256 hashed, scoped).

SI-10 (Information Input Validation):
  All API inputs validated via Pydantic schemas (type, length, format).
  Content filter checks for profanity, junk, and injection patterns.
  AI input sanitized via Unicode NFKC normalization + regex patterns.
  CSRF tokens validated on all state-changing requests.
  SQL injection prevented by parameterized queries (SQLAlchemy).
  XSS prevented by Jinja2 autoescape=True.

SC-28 (Protection of Information at Rest):
  Database: RDS encryption (AES-256, AWS-managed key).
  S3: Server-side encryption enabled on all buckets.
  User AI keys: AES-256-GCM with master key in Secrets Manager.
  Session data: Redis in-transit encryption, no persistence to disk.
```

### Incident Response Runbook
```
Create: docs/runbook.md

=== SITE IS DOWN ===
1. SSH to VPS: ssh artifact-vps
2. Check containers: docker compose ps
   - If containers are stopped: docker compose up -d
   - If containers are restarting: docker compose logs -f web (check for crash loop)
3. Check nginx: sudo systemctl status nginx
   - If nginx is down: sudo systemctl restart nginx
4. Check disk: df -h (if >90%, clear docker images: docker system prune)
5. Check memory: free -h (if <200MB free, restart stack: docker compose restart)

=== SITE IS SLOW ===
1. docker compose logs -f web — look for slow query warnings
2. docker compose exec web python -c "import redis; r=redis.from_url('$REDIS_URL'); print(r.ping())"
3. docker compose exec postgres psql -U artifact -c "SELECT count(*) FROM pg_stat_activity"
4. If Postgres connections maxed: docker compose restart postgres

=== USER REPORTS SEEING WRONG DATA ===
1. Check permission cache: flush immediately
   docker compose exec web python -c "
   import redis; r=redis.from_url('$REDIS_URL');
   keys = r.keys('perm:*'); r.delete(*keys) if keys else None;
   print(f'Flushed {len(keys)} permission cache entries')"
2. Check user's grants: SELECT * FROM fc_node_permission WHERE user_uid = 'XXX'
3. Check event_log for recent changes: SELECT * FROM fc_event_log ORDER BY occurred_at DESC LIMIT 20

=== USER'S AI KEY LEAKED ===
1. The leaked key is the USER'S key (OpenAI/Anthropic), not ours
2. Tell user to rotate their key on the provider's website immediately
3. User saves new key in artiFACT Settings → old encrypted blob overwritten
4. If our MASTER encryption key is compromised (Secrets Manager):
   → Generate new master key in Secrets Manager
   → Run: python scripts/rotate_master_key.py --old-key-arn ARN --new-key-arn ARN
   → This decrypts all user keys with old master, re-encrypts with new master
   → Update ECS task definition with new Secrets Manager ARN
   → Redeploy

=== DATABASE CORRUPTED ===
On VPS:
  docker compose down
  docker compose exec postgres pg_restore -U artifact -d artifact_db backup_YYYYMMDD.sql
  docker compose up -d
  docker compose exec web alembic upgrade head

On COSMOS:
  Use RDS PITR: restore to last known good timestamp
  aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier artifact-prod \
    --target-db-instance-identifier artifact-prod-restored \
    --restore-time "2026-03-28T15:00:00Z"
  Update ECS environment to point to restored instance
  Verify data, then rename instances

=== HOW TO ROLL BACK A BAD DEPLOY ===
On VPS:
  git log --oneline -5          # find last good commit
  git checkout <good-sha>
  docker compose up --build -d

On COSMOS:
  # ECS auto-rolls-back if health checks fail
  # Manual: update task definition to previous image tag
  aws ecs update-service --cluster artifact --service web \
    --task-definition artifact-web:PREVIOUS_REVISION
```
