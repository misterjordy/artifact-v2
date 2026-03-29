# Authorization Boundary Diagram

**System**: artiFACT v2
**Classification**: UNCLASSIFIED
**Last updated**: Sprint 1 (2026-03-29)

## Boundary Diagram

```
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
```

## Network Boundaries

- **Inbound**: HTTPS (443) via ALB only
- **Internal**: All traffic within VPC, no public subnets for DB/Redis/S3
- **Outbound**: LLM API calls (user-provided keys), SAML IdP communication

## Components (Sprint 1)

| Component | Service | Port | Notes |
|-----------|---------|------|-------|
| FastAPI Web | ECS Fargate | 8000 | Behind ALB, non-root (appuser) |
| Celery Worker | ECS Fargate | N/A | Background task processing |
| PostgreSQL | RDS | 5432 | VPC-internal only, AES-256 at rest |
| Redis | ElastiCache | 6379 | Sessions, permissions cache, rate limits |
| S3 | AWS S3 | 443 | Document storage, SSE encryption |
| ALB | AWS ALB | 443 | TLS 1.2+ termination, WAF integration |

## Security Controls (Sprint 1)

- Session-based authentication with 8hr TTL
- Zero Trust continuous revalidation (15min window)
- CSRF protection on all state-changing requests
- Rate limiting via Redis (INCR + EXPIRE)
- RBAC with node-scoped grants + admin override
- Non-root container execution
