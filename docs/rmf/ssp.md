# System Security Plan (SSP) — artiFACT

## 1. System Identification

- **Name**: artiFACT
- **Type**: Major Application
- **Categorization**: MODERATE (C-M, I-M, A-L)
- **Impact Level**: IL-4/5 (CUI)
- **Hosting**: COSMOS (NIWC Pacific, AWS GovCloud)
- **Authorization boundary**: Inherits COSMOS CNAP/ZT boundary
- **See**: [Boundary Diagram](boundary-diagram.md)

## 2. System Description

- **Purpose**: Taxonomy-driven atomic fact corpus platform for DoD program documentation
- **Users**: DoD program managers, engineers, approvers, signatories
- **Data**: Unclassified program documentation decomposed into atomic facts (CUI)
- **Authentication**: CAC via COSMOS SAML (M365 federated identity)
- **Dev-mode authentication**: Username/password (disabled when APP_ENV=production)

## 3. System Architecture

- **Web framework**: FastAPI (Python 3.12+), async, server-rendered HTML via Jinja2
- **Database**: PostgreSQL 16 (RDS on COSMOS)
- **Cache/session store**: Redis 7
- **Object storage**: S3 (MinIO on VPS, S3 on COSMOS)
- **Background tasks**: Celery with Redis broker
- **Reverse proxy**: Nginx with TLS termination
- **See**: [Architecture Document](../artifact-v2-architecture.md) (sections 2-3)
- **See**: [Data Flow Diagram](data-flow.md)

## 4. Security Controls

- **See**: [Control Implementations](control-implementations.md)
- **Inherited from COSMOS**: AC-2, AU-2, AU-3, IA-2, SC-7, SC-8, SC-28, PE-*, MP-*
- **Implemented by artiFACT**: AC-3, AC-6, AU-12, CM-7, IA-8, SI-10, SC-28 (application layer)

## 5. Continuous Monitoring

- CloudWatch alarms (COSMOS), Docker health checks (VPS)
- Grafana dashboards for API latency, error rates, queue depth
- SBOM generated per release (CycloneDX format)
- `pip-audit` in CI pipeline (known vulnerability scan)
- OWASP ZAP baseline scan in CI pipeline
- RegScale integration (when on COSMOS)
- Structured JSON logs forwarded to CloudWatch -> LANT CSSP SIEM

## 6. Data Flow Summary

1. User authenticates via CAC -> COSMOS SAML -> session cookie (Redis)
2. User creates/edits atomic facts -> PostgreSQL (versioned, append-only audit log)
3. Approver/signatory reviews and signs facts -> state machine transitions
4. Export: facts -> factsheet (JSON/CSV/TXT) or AI-generated DOCX
5. Sync: external systems poll delta feed via API key (Bearer token)
6. AI Chat: user's own API key -> external LLM, facts loaded from PostgreSQL as context

## 7. Boundary Diagram Reference

See [boundary-diagram.md](boundary-diagram.md) for the authorization boundary diagram showing COSMOS inheritance and artiFACT-specific components.
