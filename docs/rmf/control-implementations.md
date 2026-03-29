# Control Implementation Statements — artiFACT

## AC-3 (Access Enforcement)

artiFACT enforces role-based access control via `kernel/permissions/resolver.py`.
Every API endpoint calls `permissions.can(user, action, node_uid)` before executing.
Roles are hierarchical: viewer < contributor < subapprover < approver < signatory < admin.
Per-node grants override global roles and are scoped to specific taxonomy branches.

**Verified by**: `test_subapprover_cannot_reject_outside_scope`, `test_contributor_with_node_grant_can_approve`, `test_unauthenticated_blocked_on_all_endpoints`

## AC-6 (Least Privilege)

Users receive `viewer` role by default on first CAC login.
Elevated roles require explicit admin grant via the grants API.
Per-node grants scope access to specific taxonomy branches.
API keys support scoped permissions (read-only for machine clients).

**Verified by**: `test_viewer_cannot_create_facts`, `test_contributor_cannot_approve`

## AU-12 (Audit Generation)

`fc_event_log` records every state-changing action with actor, timestamp, entity, and payload.
Append-only design — no DELETE on event_log table.
Retention: 2 years in database, then archived to S3.
Read-access logging (ZT Pillar 5) records export, AI chat, and sync access events.

**Verified by**: `test_event_recorded_on_create`, `test_event_recorded_on_retire`, `test_read_access_logged_on_export`

## CM-7 (Least Functionality)

Modules can be disabled via admin feature flags without code deployment.
Only required services run (no SSH daemon in containers, no debug endpoints in production).
Dev-mode login disabled when `APP_ENV=production`.

## IA-8 (Identification and Authentication)

All users authenticate via DoD CAC through COSMOS SAML/CNAP.
No passwords stored in production. EDIPI used as unique identifier.
Session tokens stored in Redis with 8-hour TTL, re-validated every 15 minutes.
Machine clients use API keys (SHA-256 hashed, scoped).

**Verified by**: `test_session_validates_user`, `test_expired_api_key_rejected`

## SI-10 (Information Input Validation)

All API inputs validated via Pydantic schemas (type, length, format).
Content filter checks for profanity, junk, and injection patterns.
AI input sanitized via Unicode NFKC normalization + regex patterns.
CSRF tokens validated on all state-changing requests.
SQL injection prevented by parameterized queries (SQLAlchemy).
XSS prevented by Jinja2 `autoescape=True`.

**Verified by**: `test_csrf_required_on_all_writes`, `test_input_filter_blocks_injection`

## SC-28 (Protection of Information at Rest)

- **Database**: RDS encryption (AES-256, AWS-managed key) on COSMOS
- **S3**: Server-side encryption enabled on all buckets
- **User AI keys**: AES-256-GCM with master key in Secrets Manager
- **Session data**: Redis in-transit encryption, no persistence to disk

## Zero Trust Controls

### ZT Pillar 5 — Data Access Logging
`kernel/access_logger.py` logs data-exfiltration-relevant access patterns:
export, AI chat, sync delta, sync full. Non-blocking background logging.

### ZT Pillar 6 — Anomaly Detection
`modules/admin/anomaly_detector.py` detects: export flood (>10/30min),
AI corpus mining (>50/hr), scope escalation (>10 403s/10min), off-hours bulk access.

### ZT Pillar 7 — Automated Response
On anomaly trigger: all user sessions destroyed (force re-CAC), event logged,
admin alerted via real-time pub/sub. User is NOT auto-deactivated — admin reviews.
