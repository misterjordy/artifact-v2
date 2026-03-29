# Data Flow Diagram

**System**: artiFACT v2
**Classification**: UNCLASSIFIED
**Last updated**: Sprint 1 (2026-03-29)

## Primary Data Flow

```
User (CAC) → COSMOS CNAP → ALB (TLS termination)
  → FastAPI (session validation)
    → PostgreSQL (fact data, user data, audit log)
    → Redis (session cache, permission cache, rate limits)
    → S3 (uploaded documents, generated exports, snapshots)
    → External LLM API (user's own key, encrypted at rest)
      ← LLM response (filtered before display)
    ← HTML response to user
```

## Data Classification

- **CUI**: When deployed on COSMOS (production)
- **UNCLASSIFIED**: On VPS development environment (synthetic data only)

## Data at Rest

| Store | Encryption | Notes |
|-------|-----------|-------|
| RDS PostgreSQL | AES-256 (AWS managed) | All user data, fact data, audit logs |
| S3 | SSE (Server-Side Encryption) | Documents, exports, snapshots |
| Redis | In-transit encryption (TLS) | Ephemeral session/cache data |

## Data in Transit

- **TLS 1.2+** on all connections
- ALB → FastAPI: internal VPC, HTTP (TLS terminated at ALB)
- FastAPI → RDS: TLS required
- FastAPI → Redis: TLS in production
- FastAPI → S3: HTTPS
- FastAPI → LLM API: HTTPS (user-provided API keys)

## PII Inventory

| Field | Table | Purpose | Retention |
|-------|-------|---------|-----------|
| display_name | fc_user | User identification | Account lifetime |
| email | fc_user | Contact (optional) | Account lifetime |
| EDIPI | fc_user | DoD identifier | Account lifetime |
| CAC DN | fc_user | Authentication identity | Account lifetime |

## PII NOT Stored

- Passwords (CAC-only authentication in production)
- Full IP addresses (hashed only in audit logs)
- Browser fingerprints

## Sprint 1 Data Flows

1. **Login**: User → ALB → FastAPI → Redis (session create) → PostgreSQL (user lookup)
2. **Session validation**: Request → FastAPI → Redis (session check) → PostgreSQL (revalidation every 15min)
3. **Permission check**: Request → FastAPI → Redis (cache) → PostgreSQL (grants + ancestors CTE)
4. **Rate limiting**: Request → FastAPI → Redis (INCR + EXPIRE)
