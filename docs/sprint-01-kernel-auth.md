# Sprint 1: Kernel + Auth

**Depends on**: Sprint 0
**Modules built**: `kernel/` (18 components), `modules/auth_admin/` (partial)

## Definition of Success
- `POST /api/v1/auth/login` returns a session cookie (dev mode)
- `GET /api/v1/users/me` returns the authenticated user's profile
- Unauthenticated requests to any endpoint return 401
- CSRF token is set on login, validated on all writes
- Permission resolver passes all unit tests (admin override, node grant inheritance, revoked grant, descendant inheritance)
- Rate limiter blocks after threshold
- All kernel unit tests pass

## Database Migration

Tables created: `fc_user`, `fc_node`, `fc_node_permission`, `fc_rate_limit`, `fc_system_config`, `fc_api_key`

## Key Components to Build

### kernel/auth/middleware.py
```
Extract user from session cookie (Redis lookup) or Bearer token (DB lookup).
Return 401 if neither present.
Attach user to request state for downstream handlers.
```

### kernel/auth/csrf.py
```
On login: generate random token, set as signed cookie + return in response body.
On POST/PUT/PATCH/DELETE: compare X-CSRF-Token header to cookie value.
Return 403 if mismatch or missing.
Exempt: /api/v1/auth/login, /api/v1/health
```

### kernel/auth/session.py
```
create_session(user) → generate UUID, store in Redis with TTL 8hr, set cookie
  Also store: last_validated_at = now(), user_uid, cac_dn

validate_session(cookie) → Redis lookup, return User or None
  ZT CONTINUOUS AUTH: if last_validated_at > 15 min ago:
    → re-check user is still active in fc_user (not deactivated)
    → re-check CAC revocation list (if COSMOS provides one)
    → update last_validated_at in Redis
    → if user deactivated or revoked: destroy session, return None
  This ensures a revoked CAC or deactivated user is caught within 15 min,
  not 8 hours.

destroy_session(cookie) → Redis delete, clear cookie
force_destroy_user_sessions(user_uid) → scan Redis for all sessions
  matching this user_uid, delete all. Used by: admin deactivate,
  anomaly detector auto-lock, grant revocation.
```

### kernel/permissions/resolver.py
```
resolve_role(user, node_uid):
  1. Check Redis cache
  2. Load user grants (all active, cached per-request)
  3. Get ancestor chain for node (CTE, cached per-request)
  4. Walk ancestors, find highest matching grant
  5. Compare to global_role, return the higher
  6. Cache in Redis 5min

can(user, action, node_uid):
  role = resolve_role(user, node_uid)
  return role_gte(role, REQUIRED_ROLES[action])
```

### kernel/permissions/hierarchy.py
```
ROLE_ORDER = ['viewer', 'contributor', 'subapprover', 'approver', 'signatory', 'admin']
role_gte(role_a, role_b) → True if role_a >= role_b in hierarchy
REQUIRED_ROLES = {read: viewer, contribute: contributor, approve: subapprover, sign: signatory, manage_node: approver, admin: admin}
```

### kernel/tree/ancestors.py
```
WITH RECURSIVE chain AS (
    SELECT node_uid, parent_node_uid FROM fc_node WHERE node_uid = :target
    UNION ALL
    SELECT n.node_uid, n.parent_node_uid FROM fc_node n JOIN chain c ON n.node_uid = c.parent_node_uid
)
SELECT node_uid FROM chain
```

### kernel/tree/descendants.py
```
WITH RECURSIVE tree AS (
    SELECT node_uid FROM fc_node WHERE node_uid = :root
    UNION ALL
    SELECT n.node_uid FROM fc_node n JOIN tree t ON n.parent_node_uid = t.node_uid
)
SELECT node_uid FROM tree
```

### kernel/rate_limiter.py
```
check_rate(identifier, action):
  key = f"rate:{action}:{identifier}"
  count = redis.incr(key)
  if count == 1: redis.expire(key, 3600)
  if count > config.get(f"security.rate_limit.{action}"): raise 429
```

### kernel/config.py
```
Settings class (Pydantic BaseSettings):
  DATABASE_URL, REDIS_URL, S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET
  SECRET_KEY, APP_ENV, CORS_ORIGINS
  Loaded from environment variables (docker-compose .env file)
```

### modules/auth_admin/router.py (dev-mode login)
```
POST /api/v1/auth/login — accept username/password (dev only), create session
POST /api/v1/auth/logout — destroy session
GET  /api/v1/users/me — return current user profile
```

## Unit Tests to Write
```
test_admin_can_do_everything
test_contributor_cannot_approve
test_node_grant_overrides_global_role
test_revoked_grant_not_honored
test_grant_on_parent_inherits_to_descendants
test_ancestor_chain_correct_for_deep_node
test_descendant_set_includes_all_children
test_rate_limiter_blocks_after_threshold
test_rate_limiter_resets_after_window
test_csrf_required_on_post
test_csrf_not_required_on_get
test_session_creation_and_retrieval
test_session_expiry
test_unauthenticated_returns_401
test_session_revalidation_catches_deactivated_user    ← ZT continuous auth
test_session_revalidation_within_15min_window          ← ZT continuous auth
test_force_destroy_kills_all_user_sessions             ← ZT auto-remediation
```

## Verification
```bash
# Login
curl -X POST https://artifact.jordanaallred.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' -c cookies.txt

# Get profile
curl https://artifact.jordanaallred.com/api/v1/users/me -b cookies.txt

# Unauthenticated should fail
curl https://artifact.jordanaallred.com/api/v1/users/me
# → 401

# Tests
docker compose exec web pytest kernel/ -v
```

## RMF Artifacts (started this sprint, updated each subsequent sprint)

### Authorization Boundary Diagram
```
Create: docs/rmf/boundary-diagram.md (Mermaid or draw.io)

┌─────────────────────────────────────────────────┐
│  COSMOS Authorization Boundary (IL-4/5)         │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ ECS Web  │  │ECS Worker│  │   ALB    │      │
│  │ (Fargate)│  │ (Fargate)│  │          │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │              │             │             │
│  ┌────┴──────────────┴─────┐ ┌────┴─────┐      │
│  │   RDS PostgreSQL        │ │ S3 Bucket│      │
│  └─────────────────────────┘ └──────────┘      │
│  ┌─────────────────────────┐                    │
│  │   ElastiCache Redis     │                    │
│  └─────────────────────────┘                    │
│                                                 │
│  External connections (outbound only):          │
│  → OpenAI/Anthropic API (user-provided keys)    │
│  → COSMOS SAML IdP (CAC authentication)         │
└─────────────────────────────────────────────────┘

Inbound: HTTPS (443) via ALB only
Internal: All traffic within VPC, no public subnets for DB/Redis/S3
```

### Data Flow Diagram
```
Create: docs/rmf/data-flow.md

User (CAC) → COSMOS CNAP → ALB (TLS termination)
  → FastAPI (session validation)
    → PostgreSQL (fact data, user data, audit log)
    → Redis (session cache, permission cache, rate limits)
    → S3 (uploaded documents, generated exports, snapshots)
    → External LLM API (user's own key, encrypted at rest)
      ← LLM response (filtered before display)
    ← HTML response to user

Data classification: CUI when on COSMOS, UNCLASSIFIED on VPS (synthetic data only)
Data at rest: RDS encryption (AES-256), S3 SSE, Redis in-transit encryption
Data in transit: TLS 1.2+ everywhere
PII stored: display_name, email, EDIPI, CAC DN (all in fc_user)
PII not stored: passwords (CAC-only in prod), full IP addresses (hashed only)
```

Update both diagrams at the end of every sprint as new components/data flows are added.
