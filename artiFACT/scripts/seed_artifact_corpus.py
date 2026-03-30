"""Seed the artiFACT self-documenting compliance corpus.

Creates the artiFACT program taxonomy as a root node, 200+ atomic facts,
document templates, and admin-only permissions. Idempotent — safe to run
multiple times.

Run: docker compose exec web python -m artiFACT.scripts.seed_artifact_corpus
"""

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from artiFACT.kernel.config import settings
from artiFACT.kernel.models import (
    FcDocumentTemplate,
    FcEventLog,
    FcFact,
    FcFactVersion,
    FcNode,
    FcNodePermission,
)

log = structlog.get_logger()

JALLRED_UID = uuid.UUID("a0000001-0000-4000-8000-000000000001")
SEED_TIME = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Taxonomy definition: (path, depth, sort_order)
# artiFACT is a ROOT node (depth 0, no parent) — same level as Special Projects.
# Path components separated by " > ".
# ---------------------------------------------------------------------------
TAXONOMY: list[tuple[str, int, int]] = [
    # Root
    ("artiFACT", 0, 2),
    # Twigs (depth 1)
    ("artiFACT > System Identity", 1, 1),
    ("artiFACT > Architecture & Design", 1, 2),
    ("artiFACT > Security & Compliance", 1, 3),
    ("artiFACT > Data & Privacy", 1, 4),
    ("artiFACT > User Roles & Workflows", 1, 5),
    ("artiFACT > AI Integration", 1, 6),
    ("artiFACT > Operations & Deployment", 1, 7),
    ("artiFACT > Diagrams", 1, 8),
    ("artiFACT > Compliance Artifacts", 1, 9),
    # Leaves under System Identity (depth 2)
    ("artiFACT > System Identity > Program Overview", 2, 1),
    ("artiFACT > System Identity > Mission Need", 2, 2),
    ("artiFACT > System Identity > Stakeholders", 2, 3),
    ("artiFACT > System Identity > Budget & Sustainment", 2, 4),
    # Leaves under Architecture & Design (depth 2)
    ("artiFACT > Architecture & Design > Technology Stack", 2, 1),
    ("artiFACT > Architecture & Design > Module Architecture", 2, 2),
    ("artiFACT > Architecture & Design > Data Model", 2, 3),
    ("artiFACT > Architecture & Design > API Design", 2, 4),
    # Veins under Technology Stack (depth 3)
    ("artiFACT > Architecture & Design > Technology Stack > Backend", 3, 1),
    ("artiFACT > Architecture & Design > Technology Stack > Frontend", 3, 2),
    ("artiFACT > Architecture & Design > Technology Stack > Data Layer", 3, 3),
    ("artiFACT > Architecture & Design > Technology Stack > Infrastructure", 3, 4),
    # Veins under Module Architecture (depth 3)
    ("artiFACT > Architecture & Design > Module Architecture > Bounded Contexts", 3, 1),
    ("artiFACT > Architecture & Design > Module Architecture > Kernel Services", 3, 2),
    ("artiFACT > Architecture & Design > Module Architecture > Module Communication", 3, 3),
    # Veins under Data Model (depth 3)
    ("artiFACT > Architecture & Design > Data Model > Core Tables", 3, 1),
    ("artiFACT > Architecture & Design > Data Model > Workflow Tables", 3, 2),
    ("artiFACT > Architecture & Design > Data Model > System Tables", 3, 3),
    # Veins under API Design (depth 3)
    ("artiFACT > Architecture & Design > API Design > REST Conventions", 3, 1),
    ("artiFACT > Architecture & Design > API Design > Authentication", 3, 2),
    ("artiFACT > Architecture & Design > API Design > External Integrations", 3, 3),
    # Leaves under Security & Compliance (depth 2)
    ("artiFACT > Security & Compliance > Zero Trust Implementation", 2, 1),
    ("artiFACT > Security & Compliance > Encryption & Data Protection", 2, 2),
    ("artiFACT > Security & Compliance > Access Control Model", 2, 3),
    ("artiFACT > Security & Compliance > Audit & Accountability", 2, 4),
    ("artiFACT > Security & Compliance > CUI Handling", 2, 5),
    ("artiFACT > Security & Compliance > ATO & RMF", 2, 6),
    # Veins under Zero Trust (depth 3)
    ("artiFACT > Security & Compliance > Zero Trust Implementation > Pillar 1 \u2014 User Identity", 3, 1),
    ("artiFACT > Security & Compliance > Zero Trust Implementation > Pillar 2 \u2014 Device", 3, 2),
    ("artiFACT > Security & Compliance > Zero Trust Implementation > Pillar 3 \u2014 Network", 3, 3),
    ("artiFACT > Security & Compliance > Zero Trust Implementation > Pillar 4 \u2014 Application", 3, 4),
    ("artiFACT > Security & Compliance > Zero Trust Implementation > Pillar 5 \u2014 Data", 3, 5),
    ("artiFACT > Security & Compliance > Zero Trust Implementation > Pillar 6 \u2014 Visibility", 3, 6),
    ("artiFACT > Security & Compliance > Zero Trust Implementation > Pillar 7 \u2014 Automation", 3, 7),
    # Leaves under Data & Privacy (depth 2)
    ("artiFACT > Data & Privacy > PII Inventory", 2, 1),
    ("artiFACT > Data & Privacy > Data Retention", 2, 2),
    ("artiFACT > Data & Privacy > Data Export & Portability", 2, 3),
    ("artiFACT > Data & Privacy > External Data Sharing", 2, 4),
    # Leaves under User Roles & Workflows (depth 2)
    ("artiFACT > User Roles & Workflows > Role Hierarchy", 2, 1),
    ("artiFACT > User Roles & Workflows > Permission Model", 2, 2),
    ("artiFACT > User Roles & Workflows > Fact Lifecycle", 2, 3),
    ("artiFACT > User Roles & Workflows > Approval Workflow", 2, 4),
    ("artiFACT > User Roles & Workflows > Signing Workflow", 2, 5),
    # Leaves under AI Integration (depth 2)
    ("artiFACT > AI Integration > BYOK Architecture", 2, 1),
    ("artiFACT > AI Integration > Chat & Corpus Grounding", 2, 2),
    ("artiFACT > AI Integration > Import Analysis", 2, 3),
    ("artiFACT > AI Integration > Document Generation", 2, 4),
    ("artiFACT > AI Integration > AI Safety Controls", 2, 5),
    # Leaves under Operations & Deployment (depth 2)
    ("artiFACT > Operations & Deployment > Container Architecture", 2, 1),
    ("artiFACT > Operations & Deployment > COSMOS Deployment", 2, 2),
    ("artiFACT > Operations & Deployment > Graceful Degradation", 2, 3),
    ("artiFACT > Operations & Deployment > Monitoring & Logging", 2, 4),
    ("artiFACT > Operations & Deployment > Backup & Recovery", 2, 5),
    ("artiFACT > Operations & Deployment > CI/CD Pipeline", 2, 6),
    # Leaves under Diagrams (depth 2)
    ("artiFACT > Diagrams > System Context", 2, 1),
    ("artiFACT > Diagrams > Data Flow", 2, 2),
    ("artiFACT > Diagrams > Deployment Architecture", 2, 3),
    ("artiFACT > Diagrams > Module Dependency", 2, 4),
    ("artiFACT > Diagrams > Fact State Machine", 2, 5),
    ("artiFACT > Diagrams > Authentication Flow", 2, 6),
    ("artiFACT > Diagrams > Network Topology", 2, 7),
    # Leaves under Compliance Artifacts (depth 2)
    ("artiFACT > Compliance Artifacts > DITPR Registration", 2, 1),
    ("artiFACT > Compliance Artifacts > Records Retention", 2, 2),
    ("artiFACT > Compliance Artifacts > Collibra Registration", 2, 3),
    ("artiFACT > Compliance Artifacts > CUI Training", 2, 4),
    ("artiFACT > Compliance Artifacts > OWASP ZAP Results", 2, 5),
]


def _slug(title: str) -> str:
    """Convert a title to a URL-safe slug."""
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ---------------------------------------------------------------------------
# Atomic facts: (node_path_leaf, display_sentence)
# Each fact is ONE atomic statement — no compound clauses.
# ---------------------------------------------------------------------------
FACTS: list[tuple[str, str]] = [
    # === System Identity > Program Overview ===
    ("Program Overview", "artiFACT is a taxonomy-driven atomic fact corpus platform"),
    ("Program Overview", "artiFACT manages DoD software acquisition engineering documentation"),
    ("Program Overview", "artiFACT decomposes traditional acquisition documents into atomic facts"),
    ("Program Overview", "Each fact is version-controlled and signable"),
    ("Program Overview", "Facts are organized in a hierarchical taxonomy"),
    ("Program Overview", "artiFACT replaces 71 engineering artifacts with a single source of truth"),
    ("Program Overview", "Those 71 artifacts carry over 30 percent duplicative content"),
    ("Program Overview", "Documents are generated on demand from the current corpus"),
    ("Program Overview", "Documents are not maintained as static files"),
    ("Program Overview", "artiFACT treats individual factual statements as first-class entities"),
    ("Program Overview", "Each fact entity has version control"),
    ("Program Overview", "Each fact entity has approval workflows"),
    ("Program Overview", "Each fact entity has digital signatures"),
    ("Program Overview", "Each fact entity has classification markings"),
    ("Program Overview", "The system provides AI-assisted document generation"),
    ("Program Overview", "artiFACT follows the DoD Software Acquisition Pathway"),
    ("Program Overview", "artiFACT operates under the Adaptive Acquisition Framework"),
    ("Program Overview", "artiFACT is developed internally by a NAVWAR program office"),
    ("Program Overview", "Development uses existing government labor"),
    ("Program Overview", "There is no contract vehicle"),
    ("Program Overview", "There is no ACAT designation"),
    ("Program Overview", "No milestone decision authority is required"),
    ("Program Overview", "artiFACT is not a program of record"),
    ("Program Overview", "artiFACT is an internal productivity tool for program offices"),
    ("Program Overview", "The codebase includes an architecture document"),
    ("Program Overview", "The codebase includes a master reference with style guides and pseudocode"),
    ("Program Overview", "The codebase includes 15 sprint files with definitions of success"),
    ("Program Overview", "The codebase includes an OpenAPI spec"),

    # === System Identity > Mission Need ===
    ("Mission Need", "A typical DoD acquisition program has 71 engineering artifacts"),
    ("Mission Need", "Those 71 artifacts carry over 30 percent duplicative content"),
    ("Mission Need", "When a single fact changes a human must manually find every document containing that fact"),
    ("Mission Need", "A human must then manually update each of those documents"),
    ("Mission Need", "artiFACT stores each fact once in one place"),
    ("Mission Need", "Each stored fact has version control"),
    ("Mission Need", "Each stored fact has approval workflows"),
    ("Mission Need", "The system addresses the DON need for authoritative atomic data"),
    ("Mission Need", "Atomic data can be programmatically assembled into any required document format"),
    ("Mission Need", "Duplicative content across acquisition documents costs thousands of engineering hours across the DON"),
    ("Mission Need", "artiFACT supplements existing workflows rather than replacing them"),
    ("Mission Need", "Users can continue using Word documents while gradually building their corpus"),

    # === System Identity > Stakeholders ===
    ("Stakeholders", "The system is developed for NAVWAR"),
    ("Stakeholders", "The target users are DON program managers"),
    ("Stakeholders", "The target users include engineers"),
    ("Stakeholders", "The target users include acquisition professionals"),
    ("Stakeholders", "COSMOS NIWC Pacific provides the cloud hosting infrastructure"),
    ("Stakeholders", "Advana Jupiter is the downstream data consumer"),
    ("Stakeholders", "Advana consumes data via the delta feed API"),
    ("Stakeholders", "The program manager is Jordan Allred"),
    ("Stakeholders", "The Jupiter team registers artiFACT as a data source in their Apigee gateway"),
    ("Stakeholders", "artiFACT is accessible from any CAC-enabled browser"),
    ("Stakeholders", "artiFACT is accessible on commercial internet"),
    ("Stakeholders", "artiFACT is accessible on DODIN"),

    # === System Identity > Budget & Sustainment ===
    ("Budget & Sustainment", "Annual sustainment cost is approximately 2100 dollars"),
    ("Budget & Sustainment", "Hosting is provided by COSMOS on a consumption basis"),
    ("Budget & Sustainment", "COSMOS hosting requires no commitment"),
    ("Budget & Sustainment", "There are zero license fees"),
    ("Budget & Sustainment", "AI costs are per user"),
    ("Budget & Sustainment", "Each users organization pays for their own Bedrock usage"),
    ("Budget & Sustainment", "Typical AI cost is 5 to 50 dollars per month per user"),
    ("Budget & Sustainment", "No contractor support is required for daily operations"),
    ("Budget & Sustainment", "The system runs unattended between deployments"),
    ("Budget & Sustainment", "The entire stack is FOSS"),
    ("Budget & Sustainment", "There is no vendor dependency"),
    ("Budget & Sustainment", "There is no SaaS subscription"),
    ("Budget & Sustainment", "There is no commercial support contract"),
    ("Budget & Sustainment", "The source code is government-owned"),
    ("Budget & Sustainment", "Amazon Bedrock is used for AI features"),
    ("Budget & Sustainment", "Bedrock is not required for core operations"),
    ("Budget & Sustainment", "If funding is cut all data can be exported via the sync full endpoint"),
    ("Budget & Sustainment", "Total recovery time after funding restoration is approximately one day"),

    # === Architecture & Design > Technology Stack > Backend ===
    ("Backend", "The backend uses Python 3.12"),
    ("Backend", "FastAPI is the web framework"),
    ("Backend", "Uvicorn serves as the ASGI server"),
    ("Backend", "Celery handles background task processing"),
    ("Backend", "Redis serves as the Celery message broker"),
    ("Backend", "Alembic manages database schema migrations"),
    ("Backend", "structlog provides structured JSON logging"),
    ("Backend", "ruff format enforces code formatting"),
    ("Backend", "Line length is set to 100 characters"),
    ("Backend", "mypy runs in strict mode for type checking"),
    ("Backend", "Every function has a type signature for parameters and return values"),
    ("Backend", "No file exceeds 300 lines"),
    ("Backend", "No function exceeds 50 lines"),

    # === Architecture & Design > Technology Stack > Frontend ===
    ("Frontend", "The frontend uses server-rendered HTML via Jinja2"),
    ("Frontend", "Jinja2 autoescape is enabled"),
    ("Frontend", "HTMX provides dynamic updates without page reloads"),
    ("Frontend", "Alpine.js provides client-side interactivity"),
    ("Frontend", "Tailwind CSS CDN provides utility-first styling"),
    ("Frontend", "The frontend requires zero build step"),
    ("Frontend", "CSS variables in theme.css provide three theme modes"),
    ("Frontend", "The three theme modes are eyecare dark and default"),
    ("Frontend", "There is zero npm"),
    ("Frontend", "There is zero webpack"),

    # === Architecture & Design > Technology Stack > Data Layer ===
    ("Data Layer", "PostgreSQL 16 is the primary database"),
    ("Data Layer", "Redis provides caching"),
    ("Data Layer", "Redis provides session storage"),
    ("Data Layer", "Redis provides rate limiting"),
    ("Data Layer", "MinIO provides S3-compatible object storage"),
    ("Data Layer", "MinIO stores file uploads and exports"),
    ("Data Layer", "All JSON columns use JSONB not JSON or TEXT"),
    ("Data Layer", "All UID columns use native UUID type not CHAR 36"),
    ("Data Layer", "All timestamp columns use TIMESTAMPTZ not TIMESTAMP"),
    ("Data Layer", "Every table has a UUID primary key generated by gen_random_uuid"),
    ("Data Layer", "Every table has created_at TIMESTAMPTZ DEFAULT now"),

    # === Architecture & Design > Technology Stack > Infrastructure ===
    ("Infrastructure", "Docker containers orchestrate all services"),
    ("Infrastructure", "Docker Compose manages the local development stack"),
    ("Infrastructure", "ECS Fargate is the production orchestrator on COSMOS"),
    ("Infrastructure", "Terraform manages infrastructure as code"),
    ("Infrastructure", "The production target is AWS GovCloud"),
    ("Infrastructure", "The production impact level is IL-4 and IL-5"),
    ("Infrastructure", "Production uses Iron Bank base images for container security"),

    # === Architecture & Design > Module Architecture > Bounded Contexts ===
    ("Bounded Contexts", "The system is a modular monolith"),
    ("Bounded Contexts", "The system has 13 bounded contexts"),
    ("Bounded Contexts", "Each bounded context is a top-level directory"),
    ("Bounded Contexts", "Each bounded context has a strict public interface of router.py and schemas.py"),
    ("Bounded Contexts", "No component inside one context ever imports from inside another context"),
    ("Bounded Contexts", "The 13 contexts are taxonomy facts auth_admin audit queue signing import_pipeline export ai_chat search feedback presentation and admin"),
    ("Bounded Contexts", "The system contains approximately 108 internal components"),
    ("Bounded Contexts", "Each bounded context contains internal components averaging 50 to 200 lines"),
    ("Bounded Contexts", "The largest components are approximately 400 lines"),

    # === Architecture & Design > Module Architecture > Kernel Services ===
    ("Kernel Services", "The kernel is the only shared import allowed across modules"),
    ("Kernel Services", "Kernel provides database sessions"),
    ("Kernel Services", "Kernel provides authentication middleware"),
    ("Kernel Services", "Kernel provides the permissions resolver"),
    ("Kernel Services", "Kernel provides the event bus"),
    ("Kernel Services", "Kernel provides rate limiting"),
    ("Kernel Services", "Kernel provides content filtering"),
    ("Kernel Services", "Kernel provides pagination"),
    ("Kernel Services", "Kernel provides background task infrastructure"),
    ("Kernel Services", "All shared code lives in the kernel"),
    ("Kernel Services", "Modules never import from each other"),
    ("Kernel Services", "The kernel contains approximately 12 components"),
    ("Kernel Services", "Kernel components are organized into auth permissions tree ai and utility submodules"),

    # === Architecture & Design > Module Architecture > Module Communication ===
    ("Module Communication", "Cross-module reads go through the database"),
    ("Module Communication", "Cross-module reads use shared SQLAlchemy models in the kernel"),
    ("Module Communication", "Cross-module writes go through the kernel event bus"),
    ("Module Communication", "The event bus uses publish and subscribe"),
    ("Module Communication", "The event bus enables audit recording"),
    ("Module Communication", "The event bus enables badge invalidation"),
    ("Module Communication", "The event bus enables cache invalidation"),
    ("Module Communication", "The event bus enables workflow transitions"),

    # === Architecture & Design > Data Model > Core Tables ===
    ("Core Tables", "fc_user stores user identity"),
    ("Core Tables", "fc_user columns include CAC DN EDIPI display name email and global role"),
    ("Core Tables", "fc_node stores the hierarchical taxonomy"),
    ("Core Tables", "fc_node columns include parent_node_uid node_depth and sort_order"),
    ("Core Tables", "fc_fact stores the fact entity"),
    ("Core Tables", "fc_fact has pointers to current published and signed versions"),
    ("Core Tables", "fc_fact_version stores each version of a fact"),
    ("Core Tables", "fc_fact_version columns include state display_sentence metadata_tags and classification"),
    ("Core Tables", "fc_fact_version has a generated tsvector for full-text search"),
    ("Core Tables", "fc_node_permission grants per-node roles"),
    ("Core Tables", "Available node roles are signatory approver subapprover contributor and viewer"),
    ("Core Tables", "Foreign keys use ON DELETE RESTRICT for core entities"),

    # === Architecture & Design > Data Model > Workflow Tables ===
    ("Workflow Tables", "fc_event_log captures every mutation"),
    ("Workflow Tables", "fc_event_log columns include entity_type entity_uid event_type and payload"),
    ("Workflow Tables", "fc_event_log has a monotonic seq column for the Advana delta feed"),
    ("Workflow Tables", "fc_signature records batch signing operations per node"),
    ("Workflow Tables", "fc_import_session tracks document upload and AI analysis progress"),
    ("Workflow Tables", "fc_fact_comment supports threaded comments on fact versions"),
    ("Workflow Tables", "fc_fact_comment supports challenges and resolutions"),

    # === Architecture & Design > Data Model > System Tables ===
    ("System Tables", "fc_system_config stores feature flags as key-value JSONB"),
    ("System Tables", "fc_system_config stores rate limit configuration as key-value JSONB"),
    ("System Tables", "fc_document_template stores semantic document templates"),
    ("System Tables", "Each template has ordered sections containing key title prompt and guidance"),
    ("System Tables", "fc_ai_usage tracks token counts per user per AI action"),
    ("System Tables", "fc_ai_usage tracks estimated costs per user per AI action"),
    ("System Tables", "fc_user_preference stores per-user settings as key-value JSONB"),

    # === Architecture & Design > API Design > REST Conventions ===
    ("REST Conventions", "All endpoints are under the api v1 prefix"),
    ("REST Conventions", "The API uses RESTful nouns not verbs"),
    ("REST Conventions", "Pagination uses offset and limit query parameters"),
    ("REST Conventions", "Default pagination limit is 50"),
    ("REST Conventions", "Maximum pagination limit is 200"),
    ("REST Conventions", "Responses follow the format data array total offset limit"),
    ("REST Conventions", "Error responses follow the format detail message code error_code"),
    ("REST Conventions", "CSRF validation is required on all POST PUT PATCH DELETE requests"),
    ("REST Conventions", "CSRF tokens are passed via the X-CSRF-Token header"),

    # === Architecture & Design > API Design > Authentication ===
    ("artiFACT > Architecture & Design > API Design > Authentication", "Browser authentication uses session cookies stored in Redis"),
    ("artiFACT > Architecture & Design > API Design > Authentication", "API authentication uses Authorization Bearer tokens"),
    ("artiFACT > Architecture & Design > API Design > Authentication", "Bearer tokens are for machine-to-machine access"),
    ("artiFACT > Architecture & Design > API Design > Authentication", "Sessions are re-validated every 15 minutes"),
    ("artiFACT > Architecture & Design > API Design > Authentication", "Session re-validation interval aligns with Zero Trust Pillar 1"),
    ("artiFACT > Architecture & Design > API Design > Authentication", "Production authentication uses CAC via COSMOS SAML"),
    ("artiFACT > Architecture & Design > API Design > Authentication", "EDIPI is extracted from the SAML assertion"),

    # === Architecture & Design > API Design > External Integrations ===
    ("External Integrations", "The Advana delta feed endpoint is GET api v1 sync changes"),
    ("External Integrations", "The delta feed uses a monotonic seq cursor"),
    ("External Integrations", "The full data dump endpoint is GET api v1 sync full"),
    ("External Integrations", "The delta feed uses BIGINT seq not timestamps"),
    ("External Integrations", "BIGINT seq provides cursor consistency"),
    ("External Integrations", "Service accounts authenticate via scoped API keys"),
    ("External Integrations", "API key scopes include read and sync permissions"),
    ("External Integrations", "The OpenAPI 3.0 spec is auto-generated at api v1 openapi.json"),
    ("External Integrations", "artiFACT feeds data to Jupiter Advana via a standard REST API"),
    ("External Integrations", "Advana Apigee gateway discovers the OpenAPI spec automatically"),

    # === Security & Compliance > Zero Trust > Pillar 1 — User Identity ===
    ("Pillar 1 \u2014 User Identity", "CAC multi-factor authentication is provided via COSMOS SAML"),
    ("Pillar 1 \u2014 User Identity", "Sessions are re-validated every 15 minutes"),
    ("Pillar 1 \u2014 User Identity", "Anomaly detection triggers force re-authentication"),
    ("Pillar 1 \u2014 User Identity", "Force re-authentication works by expiring all user sessions"),
    ("Pillar 1 \u2014 User Identity", "Per-node RBAC enforces least privilege at the taxonomy level"),
    ("Pillar 1 \u2014 User Identity", "API keys provide non-person entity authentication"),

    # === Security & Compliance > Zero Trust > Pillar 2 — Device ===
    ("Pillar 2 \u2014 Device", "Device posture assessment is inherited from COSMOS"),
    ("Pillar 2 \u2014 Device", "COSMOS uses Netskope and CNAP for device posture"),
    ("Pillar 2 \u2014 Device", "artiFACT does not independently verify device posture"),

    # === Security & Compliance > Zero Trust > Pillar 3 — Network ===
    ("Pillar 3 \u2014 Network", "CNAP zero trust network access is inherited from COSMOS"),
    ("Pillar 3 \u2014 Network", "Production uses private VPC subnets"),
    ("Pillar 3 \u2014 Network", "Production uses ALB-only ingress"),
    ("Pillar 3 \u2014 Network", "No VPN is required for access"),

    # === Security & Compliance > Zero Trust > Pillar 4 — Application ===
    ("Pillar 4 \u2014 Application", "All containers run as non-root appuser"),
    ("Pillar 4 \u2014 Application", "Authentication is required on every request via global middleware"),
    ("Pillar 4 \u2014 Application", "CSRF is validated on all state-changing HTTP methods"),
    ("Pillar 4 \u2014 Application", "Pydantic validates all API input"),
    ("Pillar 4 \u2014 Application", "Jinja2 autoescape prevents XSS"),
    ("Pillar 4 \u2014 Application", "SBOM generation runs in the CI pipeline"),
    ("Pillar 4 \u2014 Application", "pip-audit runs in the CI pipeline"),
    ("Pillar 4 \u2014 Application", "Production uses Iron Bank base images"),

    # === Security & Compliance > Zero Trust > Pillar 5 — Data ===
    ("Pillar 5 \u2014 Data", "Each fact version has a classification field"),
    ("Pillar 5 \u2014 Data", "Supported classification values are UNCLASSIFIED CUI and CONFIDENTIAL"),
    ("Pillar 5 \u2014 Data", "AI keys are encrypted with AES-256-GCM"),
    ("Pillar 5 \u2014 Data", "The encryption master key is stored in AWS Secrets Manager"),
    ("Pillar 5 \u2014 Data", "CUI markings are auto-injected in generated documents"),
    ("Pillar 5 \u2014 Data", "CUI injection triggers when any included fact has CUI classification"),
    ("Pillar 5 \u2014 Data", "Read-access logging tracks exports"),
    ("Pillar 5 \u2014 Data", "Read-access logging tracks AI chat queries"),
    ("Pillar 5 \u2014 Data", "Read-access logging tracks sync feed pulls"),

    # === Security & Compliance > Zero Trust > Pillar 6 — Visibility ===
    ("Pillar 6 \u2014 Visibility", "Structured JSON logs are produced via structlog"),
    ("Pillar 6 \u2014 Visibility", "Logs forward to CloudWatch"),
    ("Pillar 6 \u2014 Visibility", "Logs forward to CSSP SIEM"),
    ("Pillar 6 \u2014 Visibility", "fc_event_log records every mutation"),
    ("Pillar 6 \u2014 Visibility", "Each event records actor entity and timestamp"),
    ("Pillar 6 \u2014 Visibility", "Read-access events are logged for export endpoints"),
    ("Pillar 6 \u2014 Visibility", "Read-access events are logged for AI endpoints"),
    ("Pillar 6 \u2014 Visibility", "Read-access events are logged for sync endpoints"),
    ("Pillar 6 \u2014 Visibility", "Anomaly detection monitors for export floods"),
    ("Pillar 6 \u2014 Visibility", "Anomaly detection monitors for AI corpus mining"),
    ("Pillar 6 \u2014 Visibility", "Anomaly detection monitors for off-hours bulk access"),
    ("Pillar 6 \u2014 Visibility", "Anomaly detection monitors for scope escalation attempts"),
    ("Pillar 6 \u2014 Visibility", "Grafana dashboards visualize request rate"),
    ("Pillar 6 \u2014 Visibility", "Grafana dashboards visualize latency"),
    ("Pillar 6 \u2014 Visibility", "Grafana dashboards visualize error rate"),
    ("Pillar 6 \u2014 Visibility", "Grafana dashboards visualize active user count"),
    ("Pillar 6 \u2014 Visibility", "Grafana dashboards visualize AI cost"),

    # === Security & Compliance > Zero Trust > Pillar 7 — Automation ===
    ("Pillar 7 \u2014 Automation", "The CI CD pipeline runs linting"),
    ("Pillar 7 \u2014 Automation", "The CI CD pipeline runs type checking"),
    ("Pillar 7 \u2014 Automation", "The CI CD pipeline runs tests"),
    ("Pillar 7 \u2014 Automation", "The CI CD pipeline runs SBOM generation"),
    ("Pillar 7 \u2014 Automation", "The CI CD pipeline runs security scanning"),
    ("Pillar 7 \u2014 Automation", "Feature flags allow runtime toggling of capabilities without deployment"),
    ("Pillar 7 \u2014 Automation", "Auto-session-expire triggers on anomalous behavior patterns"),
    ("Pillar 7 \u2014 Automation", "Auto-CUI-marking runs during document generation"),
    ("Pillar 7 \u2014 Automation", "Celery beat handles scheduled data retention tasks"),

    # === Security & Compliance > Encryption & Data Protection ===
    ("Encryption & Data Protection", "All data at rest is encrypted using RDS AES-256"),
    ("Encryption & Data Protection", "S3 objects use server-side encryption"),
    ("Encryption & Data Protection", "AI API keys are encrypted with AES-256-GCM"),
    ("Encryption & Data Protection", "The AES-256-GCM master key is stored in AWS Secrets Manager"),
    ("Encryption & Data Protection", "All data in transit uses TLS 1.2 or higher"),
    ("Encryption & Data Protection", "AI processing uses Amazon Bedrock in AWS GovCloud"),
    ("Encryption & Data Protection", "Amazon Bedrock operates at IL-4 and IL-5"),
    ("Encryption & Data Protection", "CUI never leaves the authorization boundary"),

    # === Security & Compliance > Access Control Model ===
    ("Access Control Model", "The permission resolver uses a single kernel function called can"),
    ("Access Control Model", "The can function checks user role node and action"),
    ("Access Control Model", "Permissions are never checked by reading global_role directly"),
    ("Access Control Model", "The only exception is admin nav visibility"),
    ("Access Control Model", "The role hierarchy is signatory then approver then subapprover then contributor then viewer"),
    ("Access Control Model", "Permissions cascade down the taxonomy tree"),
    ("Access Control Model", "A grant on a parent applies to all descendants"),
    ("Access Control Model", "Permission resolution is cached in Redis"),
    ("Access Control Model", "Permission cache TTL is 300 seconds"),

    # === Security & Compliance > Audit & Accountability ===
    ("Audit & Accountability", "Every mutation emits an event captured in fc_event_log"),
    ("Audit & Accountability", "Events include entity_type and entity_uid"),
    ("Audit & Accountability", "Events include event_type and payload"),
    ("Audit & Accountability", "Events include actor_uid and occurred_at"),
    ("Audit & Accountability", "The event log uses a monotonic BIGINT seq column"),
    ("Audit & Accountability", "The seq column serves as the Advana delta feed cursor"),
    ("Audit & Accountability", "Reversible events include server-computed reverse_payload"),
    ("Audit & Accountability", "No public endpoint exists to inject arbitrary undo payloads"),

    # === Security & Compliance > CUI Handling ===
    ("CUI Handling", "Per-fact classification fields enable granular CUI tracking"),
    ("CUI Handling", "Generated documents include CUI banners in headers"),
    ("CUI Handling", "Generated documents include CUI banners in footers"),
    ("CUI Handling", "CUI banners appear when any included fact has CUI classification"),
    ("CUI Handling", "The classification field supports UNCLASSIFIED"),
    ("CUI Handling", "The classification field supports CUI with category markings"),
    ("CUI Handling", "The classification field supports CONFIDENTIAL"),
    ("CUI Handling", "AI API calls via Bedrock do not transmit PII"),
    ("CUI Handling", "Generated DOCX includes cover page classification marking"),

    # === Security & Compliance > ATO & RMF ===
    ("ATO & RMF", "artiFACT operates under the COSMOS authorization boundary"),
    ("ATO & RMF", "COSMOS has an existing ATO through NIWC Pacific"),
    ("ATO & RMF", "The target is continuous ATO"),
    ("ATO & RMF", "Continuous ATO leverages the DevSecOps pipeline"),
    ("ATO & RMF", "The SSP skeleton is maintained in the codebase"),
    ("ATO & RMF", "Control implementation statements are maintained in the codebase"),
    ("ATO & RMF", "The incident response runbook is maintained in the codebase"),
    ("ATO & RMF", "Application-level security is tested via OWASP ZAP"),
    ("ATO & RMF", "Application-level security is tested via pip-audit"),
    ("ATO & RMF", "Application-level security is tested via SBOM"),
    ("ATO & RMF", "Test coverage exceeds 80 percent"),
    ("ATO & RMF", "COSMOS provides Wiz for infrastructure scanning"),
    ("ATO & RMF", "COSMOS provides RegScale for RMF artifact management"),

    # === Data & Privacy > PII Inventory ===
    ("PII Inventory", "artiFACT collects display name"),
    ("PII Inventory", "artiFACT collects email address"),
    ("PII Inventory", "artiFACT collects EDIPI"),
    ("PII Inventory", "artiFACT collects CAC Distinguished Name"),
    ("PII Inventory", "All PII is derived from the COSMOS SAML assertion at login"),
    ("PII Inventory", "No PII is collected via user input forms"),
    ("PII Inventory", "No SSNs are stored"),
    ("PII Inventory", "No financial data is stored"),
    ("PII Inventory", "No medical data is stored"),
    ("PII Inventory", "No biometrics are stored"),
    ("PII Inventory", "Admins can view the user list with name email and role"),
    ("PII Inventory", "Non-admin users see display names only on approval and signature records"),
    ("PII Inventory", "No user can see another users EDIPI"),

    # === Data & Privacy > Data Retention ===
    ("Data Retention", "Fact versions follow NARA GRS 5.2 Item 020"),
    ("Data Retention", "Fact version retention is 3 years after superseded"),
    ("Data Retention", "Approval decisions follow NARA GRS 5.2 Item 020"),
    ("Data Retention", "The audit trail follows NARA GRS 3.2 Item 031"),
    ("Data Retention", "Audit trail retention is 6 years"),
    ("Data Retention", "Signature records follow NARA GRS 5.2 Item 020"),
    ("Data Retention", "Signature retention is 3 years after superseded"),
    ("Data Retention", "User feedback follows NARA GRS 5.7 Item 010"),
    ("Data Retention", "Feedback retention is 1 year after resolved"),
    ("Data Retention", "Import sessions are retained for 90 days after completion"),
    ("Data Retention", "System config follows NARA GRS 3.1 Item 010"),
    ("Data Retention", "System config is deleted when superseded"),

    # === Data & Privacy > Data Export & Portability ===
    ("Data Export & Portability", "GET api v1 sync full returns every node and fact version as JSON"),
    ("Data Export & Portability", "GET api v1 sync full returns every signature and user record as JSON"),
    ("Data Export & Portability", "GET api v1 sync full returns every audit event as JSON"),
    ("Data Export & Portability", "Fact exports are available in TXT format"),
    ("Data Export & Portability", "Fact exports are available in JSON format"),
    ("Data Export & Portability", "Fact exports are available in NDJSON format"),
    ("Data Export & Portability", "Fact exports are available in CSV format"),
    ("Data Export & Portability", "Generated DOCX documents are downloadable with signed S3 URLs"),
    ("Data Export & Portability", "Signed S3 URLs expire after 24 hours"),
    ("Data Export & Portability", "There is zero data lock-in"),

    # === Data & Privacy > External Data Sharing ===
    ("External Data Sharing", "The Advana sync API includes display names and roles"),
    ("External Data Sharing", "The Advana sync API does not include EDIPI"),
    ("External Data Sharing", "Sync API access requires an authenticated service account"),
    ("External Data Sharing", "No PII is shared with commercial services"),
    ("External Data Sharing", "AI API calls via Bedrock do not include PII"),

    # === User Roles & Workflows > Role Hierarchy ===
    ("Role Hierarchy", "The global roles are admin and viewer"),
    ("Role Hierarchy", "Node-level roles are signatory approver subapprover contributor and viewer"),
    ("Role Hierarchy", "Signatory is the highest node-level role"),
    ("Role Hierarchy", "Viewer is the lowest node-level role"),
    ("Role Hierarchy", "A higher role inherits all capabilities of lower roles on the same node"),

    # === User Roles & Workflows > Permission Model ===
    ("Permission Model", "Permissions are granted per-node via fc_node_permission"),
    ("Permission Model", "Grants cascade to all descendant nodes in the taxonomy"),
    ("Permission Model", "Permission resolution checks the node and all ancestors up to root"),
    ("Permission Model", "Revoked permissions use a revoked_at timestamp"),
    ("Permission Model", "Re-grant is possible after revocation"),
    ("Permission Model", "The permission cache is invalidated on grant events"),
    ("Permission Model", "The permission cache is invalidated on revoke events"),

    # === User Roles & Workflows > Fact Lifecycle ===
    ("Fact Lifecycle", "A fact is created with an initial version in proposed state"),
    ("Fact Lifecycle", "Approvers can create facts directly in published state"),
    ("Fact Lifecycle", "Published facts can be signed by a signatory"),
    ("Fact Lifecycle", "Facts can be retired"),
    ("Fact Lifecycle", "Retiring a fact sets is_retired true and retired_at timestamp"),
    ("Fact Lifecycle", "Retired facts can be unretired by an approver"),

    # === User Roles & Workflows > Approval Workflow ===
    ("Approval Workflow", "Contributors propose facts which enter the approval queue"),
    ("Approval Workflow", "Approvers see proposals scoped to their granted nodes"),
    ("Approval Workflow", "Approve publishes the version and sets published_at"),
    ("Approval Workflow", "Reject marks the version as rejected"),
    ("Approval Workflow", "Rejection can include an optional note"),
    ("Approval Workflow", "Revise language rejects the original version"),
    ("Approval Workflow", "Revise language publishes a revised version atomically"),

    # === User Roles & Workflows > Signing Workflow ===
    ("Signing Workflow", "A signatory can sign all published facts under a node in a single batch"),
    ("Signing Workflow", "Signing runs as one UPDATE WHERE IN query inside a transaction"),
    ("Signing Workflow", "A signature record is created with fact count"),
    ("Signing Workflow", "A signature record can have an optional expiration"),
    ("Signing Workflow", "Signatures apply to the current published versions at signing time"),

    # === AI Integration > BYOK Architecture ===
    ("BYOK Architecture", "Users provide their own AI API keys"),
    ("BYOK Architecture", "AI API keys are encrypted with AES-256-GCM"),
    ("BYOK Architecture", "Encrypted keys are stored in fc_user_ai_key"),
    ("BYOK Architecture", "The backend proxies all AI requests"),
    ("BYOK Architecture", "Keys are never exposed to the browser"),
    ("BYOK Architecture", "Supported providers include OpenAI"),
    ("BYOK Architecture", "Supported providers include Anthropic"),
    ("BYOK Architecture", "Amazon Bedrock is planned for production"),
    ("BYOK Architecture", "Each user organization pays for their own AI usage"),

    # === AI Integration > Chat & Corpus Grounding ===
    ("Chat & Corpus Grounding", "AI chat loads published facts into the system prompt"),
    ("Chat & Corpus Grounding", "Only facts from the users accessible nodes are loaded"),
    ("Chat & Corpus Grounding", "Token counting ensures the prompt fits the model context window"),
    ("Chat & Corpus Grounding", "The actual loaded fact count is reported to the client"),
    ("Chat & Corpus Grounding", "Output filtering catches attempts at bulk fact dumps"),

    # === AI Integration > Import Analysis ===
    ("Import Analysis", "Users can upload DOCX documents for AI-powered fact extraction"),
    ("Import Analysis", "Users can upload PDF documents for AI-powered fact extraction"),
    ("Import Analysis", "Users can upload TXT documents for AI-powered fact extraction"),
    ("Import Analysis", "Analysis runs as a Celery background task"),
    ("Import Analysis", "Progress is streamed via SSE"),
    ("Import Analysis", "Extracted facts are staged for human review before proposal"),
    ("Import Analysis", "Duplicate detection uses Jaccard similarity against existing facts"),

    # === AI Integration > Document Generation ===
    ("Document Generation", "Document generation uses a two-pass approach"),
    ("Document Generation", "The first pass is prefilter"),
    ("Document Generation", "The second pass is synthesis"),
    ("Document Generation", "The prefilter scores every published fact against all template sections simultaneously"),
    ("Document Generation", "The synthesizer generates prose for each section from the matched facts"),
    ("Document Generation", "The DOCX builder assembles the document with template styles"),
    ("Document Generation", "The DOCX builder applies CUI markings when applicable"),
    ("Document Generation", "Generation runs as a Celery background task"),
    ("Document Generation", "Generation progress is streamed via SSE"),
    ("Document Generation", "A views feature lets users run prefilter only"),
    ("Document Generation", "The views feature shows which facts AI would assign per section"),

    # === AI Integration > AI Safety Controls ===
    ("AI Safety Controls", "Input sanitization includes Unicode NFKC normalization"),
    ("AI Safety Controls", "Output filtering detects bulk fact dumps"),
    ("AI Safety Controls", "Output filtering detects prompt injection attempts"),
    ("AI Safety Controls", "Rate limiting is applied per user"),
    ("AI Safety Controls", "AI usage is tracked in fc_ai_usage"),
    ("AI Safety Controls", "Tracked AI usage fields include provider and model"),
    ("AI Safety Controls", "Tracked AI usage fields include token count and estimated cost"),

    # === Operations & Deployment > Container Architecture ===
    ("Container Architecture", "The Docker Compose stack includes a web container"),
    ("Container Architecture", "The Docker Compose stack includes a worker container"),
    ("Container Architecture", "The Docker Compose stack includes a postgres container"),
    ("Container Architecture", "The Docker Compose stack includes a redis container"),
    ("Container Architecture", "The Docker Compose stack includes a minio container"),
    ("Container Architecture", "The Docker Compose stack includes an nginx container"),
    ("Container Architecture", "The Docker Compose stack includes a certbot container"),
    ("Container Architecture", "All containers run as non-root appuser"),
    ("Container Architecture", "Uvicorn runs with reload in development"),
    ("Container Architecture", "The worker container runs Celery for background tasks"),

    # === Operations & Deployment > COSMOS Deployment ===
    ("COSMOS Deployment", "Production uses ECS Fargate"),
    ("COSMOS Deployment", "Production runs 2 web tasks"),
    ("COSMOS Deployment", "Production runs 1 worker task"),
    ("COSMOS Deployment", "RDS PostgreSQL 16 runs as db.t3.small"),
    ("COSMOS Deployment", "RDS uses Multi-AZ"),
    ("COSMOS Deployment", "RDS has 35-day automated backups"),
    ("COSMOS Deployment", "ElastiCache Redis runs as cache.t3.micro"),
    ("COSMOS Deployment", "S3 buckets store uploads"),
    ("COSMOS Deployment", "S3 buckets store exports"),
    ("COSMOS Deployment", "S3 buckets store snapshots"),
    ("COSMOS Deployment", "S3 versioning is enabled"),
    ("COSMOS Deployment", "Terraform manages all infrastructure as code"),
    ("COSMOS Deployment", "ECR stores Docker container images"),
    ("COSMOS Deployment", "Secrets Manager stores database credentials"),
    ("COSMOS Deployment", "Secrets Manager stores the encryption master key"),

    # === Operations & Deployment > Graceful Degradation ===
    ("Graceful Degradation", "When Redis is down the permission resolver falls back to direct PostgreSQL queries"),
    ("Graceful Degradation", "When Redis is down the rate limiter skips limiting"),
    ("Graceful Degradation", "When Redis is down the rate limiter logs a warning"),
    ("Graceful Degradation", "When Redis is down the session store falls back to signed JWT cookies"),
    ("Graceful Degradation", "When Redis is down the badge counter returns negative one"),
    ("Graceful Degradation", "When Redis is down the UI shows a dash instead of a count"),
    ("Graceful Degradation", "When S3 is down browse and edit features remain functional"),
    ("Graceful Degradation", "When S3 is down sign and queue features remain functional"),
    ("Graceful Degradation", "When the external LLM API is down all non-AI features remain functional"),
    ("Graceful Degradation", "When PostgreSQL is down everything fails"),
    ("Graceful Degradation", "PostgreSQL is the source of truth"),

    # === Operations & Deployment > Monitoring & Logging ===
    ("Monitoring & Logging", "Structured JSON logs via structlog forward to CloudWatch"),
    ("Monitoring & Logging", "Every mutation is recorded in fc_event_log"),
    ("Monitoring & Logging", "Read-access events are logged for data-exfiltration-relevant endpoints"),
    ("Monitoring & Logging", "Health check endpoints report database connectivity status"),
    ("Monitoring & Logging", "Health check endpoints report Redis connectivity status"),
    ("Monitoring & Logging", "Health check endpoints report S3 connectivity status"),

    # === Operations & Deployment > Backup & Recovery ===
    ("Backup & Recovery", "Production RDS uses Multi-AZ"),
    ("Backup & Recovery", "RDS has automated backups with 35-day retention"),
    ("Backup & Recovery", "Point-in-time recovery is available to any second in the last 35 days"),
    ("Backup & Recovery", "S3 versioning retains deleted objects for 30 days"),
    ("Backup & Recovery", "Admin-triggered pg_dump uploads snapshots to S3"),

    # === Operations & Deployment > CI/CD Pipeline ===
    ("CI/CD Pipeline", "The CI pipeline runs ruff format"),
    ("CI/CD Pipeline", "The CI pipeline runs ruff check"),
    ("CI/CD Pipeline", "The CI pipeline runs mypy in strict mode"),
    ("CI/CD Pipeline", "The CI pipeline runs pytest"),
    ("CI/CD Pipeline", "The CI pipeline runs SBOM generation"),
    ("CI/CD Pipeline", "The CI pipeline runs pip-audit"),
    ("CI/CD Pipeline", "OWASP ZAP provides dynamic application security testing"),
    ("CI/CD Pipeline", "Coverage target is 80 percent overall"),
    ("CI/CD Pipeline", "Coverage target is 95 percent on kernel"),
    ("CI/CD Pipeline", "Deployment uses blue-green strategy via ECS task definition updates"),

    # === Diagrams > System Context ===
    ("System Context", "DIAGRAM:MERMAID:C4Context artiFACT is the central system bounded by the COSMOS authorization boundary"),
    ("System Context", "DIAGRAM:MERMAID:C4Context Users access artiFACT via CAC-enabled browser through COSMOS CNAP"),
    ("System Context", "DIAGRAM:MERMAID:C4Context artiFACT sends delta feed data to Advana Jupiter via REST API"),
    ("System Context", "DIAGRAM:MERMAID:C4Context artiFACT sends AI requests to Amazon Bedrock in AWS GovCloud"),
    ("System Context", "DIAGRAM:MERMAID:C4Context COSMOS provides SAML identity provider for CAC authentication"),
    ("System Context", "DIAGRAM:MERMAID:C4Context CloudWatch receives structured logs from artiFACT"),
    ("System Context", "DIAGRAM:MERMAID:C4Context CSSP SIEM receives forwarded logs from CloudWatch"),

    # === Diagrams > Data Flow ===
    ("Data Flow", "DIAGRAM:MERMAID:flowchart User submits fact via browser which sends POST to FastAPI backend"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart FastAPI validates input via Pydantic and checks permissions via kernel resolver"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart FastAPI writes validated fact to PostgreSQL"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Event bus publishes fact.created event"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Audit recorder captures fact.created event to fc_event_log"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Approver reviews proposal in queue and approves it"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Approval transitions the fact version state to published"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Document generation reads published facts from PostgreSQL"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Document generation sends facts to Bedrock for synthesis"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Document generation writes completed DOCX to S3"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Advana pulls delta feed from sync endpoint using monotonic seq cursor"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Import pipeline uploads document to S3"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Celery worker extracts facts from uploaded document via Bedrock"),
    ("Data Flow", "DIAGRAM:MERMAID:flowchart Extracted facts are staged for human review"),

    # === Diagrams > Deployment Architecture ===
    ("Deployment Architecture", "DIAGRAM:MERMAID:architecture Production runs on ECS Fargate with ALB ingress in AWS GovCloud us-gov-west-1"),
    ("Deployment Architecture", "DIAGRAM:MERMAID:architecture Two web task containers serve HTTP behind the ALB"),
    ("Deployment Architecture", "DIAGRAM:MERMAID:architecture One worker task container runs Celery for background jobs"),
    ("Deployment Architecture", "DIAGRAM:MERMAID:architecture RDS PostgreSQL 16 Multi-AZ serves as the primary database"),
    ("Deployment Architecture", "DIAGRAM:MERMAID:architecture ElastiCache Redis serves as cache session store and message broker"),
    ("Deployment Architecture", "DIAGRAM:MERMAID:architecture S3 buckets store uploads exports and snapshots"),
    ("Deployment Architecture", "DIAGRAM:MERMAID:architecture ECR stores Docker container images"),
    ("Deployment Architecture", "DIAGRAM:MERMAID:architecture Secrets Manager stores database credentials and encryption master key"),

    # === Diagrams > Module Dependency ===
    ("Module Dependency", "DIAGRAM:MERMAID:flowchart All 13 modules depend on kernel for shared services"),
    ("Module Dependency", "DIAGRAM:MERMAID:flowchart Modules never import from each other only through kernel"),
    ("Module Dependency", "DIAGRAM:MERMAID:flowchart Queue module reads fc_fact_version via database"),
    ("Module Dependency", "DIAGRAM:MERMAID:flowchart Queue module publishes approval events via kernel event bus"),
    ("Module Dependency", "DIAGRAM:MERMAID:flowchart Facts module subscribes to approval events and updates version state"),
    ("Module Dependency", "DIAGRAM:MERMAID:flowchart Export module reads published facts from database"),
    ("Module Dependency", "DIAGRAM:MERMAID:flowchart Export module sends facts to AI provider via kernel"),
    ("Module Dependency", "DIAGRAM:MERMAID:flowchart Search module queries fc_fact_version tsvector index directly"),

    # === Diagrams > Fact State Machine ===
    ("Fact State Machine", "DIAGRAM:MERMAID:stateDiagram proposed transitions to published via approve action"),
    ("Fact State Machine", "DIAGRAM:MERMAID:stateDiagram proposed transitions to rejected via reject action"),
    ("Fact State Machine", "DIAGRAM:MERMAID:stateDiagram proposed transitions to withdrawn via withdraw action"),
    ("Fact State Machine", "DIAGRAM:MERMAID:stateDiagram published transitions to signed via sign action"),
    ("Fact State Machine", "DIAGRAM:MERMAID:stateDiagram signed cannot transition back to proposed"),
    ("Fact State Machine", "DIAGRAM:MERMAID:stateDiagram retired is a terminal state on the fact entity not the version"),

    # === Diagrams > Authentication Flow ===
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram User presents CAC to browser"),
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram Browser redirects to COSMOS SAML IDP"),
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram COSMOS IDP validates CAC certificate"),
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram COSMOS IDP returns SAML assertion to artiFACT"),
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram artiFACT cac_mapper extracts EDIPI and DN from assertion"),
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram artiFACT creates or updates fc_user record from assertion"),
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram artiFACT creates session in Redis with 15-minute re-validation interval"),
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram On each request middleware checks session validity"),
    ("Authentication Flow", "DIAGRAM:MERMAID:sequenceDiagram Middleware re-validates session if interval has elapsed"),

    # === Diagrams > Network Topology ===
    ("Network Topology", "DIAGRAM:MERMAID:architecture COSMOS CNAP provides zero trust network access from user browser to ALB"),
    ("Network Topology", "DIAGRAM:MERMAID:architecture ALB terminates TLS and forwards to ECS tasks in private subnet"),
    ("Network Topology", "DIAGRAM:MERMAID:architecture ECS tasks connect to RDS in private subnet"),
    ("Network Topology", "DIAGRAM:MERMAID:architecture ECS tasks connect to ElastiCache in private subnet"),
    ("Network Topology", "DIAGRAM:MERMAID:architecture ECS tasks connect to S3 via VPC endpoint"),
    ("Network Topology", "DIAGRAM:MERMAID:architecture No direct internet access from ECS tasks"),

    # === Compliance Artifacts > DITPR Registration ===
    ("DITPR Registration", "artiFACT must be registered in the DoD IT Portfolio Repository"),
    ("DITPR Registration", "DITPR is located at ditpr.osd.mil"),
    ("DITPR Registration", "The system type is Major Application"),
    ("DITPR Registration", "The classification is UNCLASSIFIED CUI"),
    ("DITPR Registration", "The impact level is IL-4"),
    ("DITPR Registration", "The impact level is IL-5"),
    ("DITPR Registration", "The hosting environment is COSMOS NIWC Pacific Cloud Service Center"),
    ("DITPR Registration", "The cloud service provider is AWS GovCloud"),

    # === Compliance Artifacts > Records Retention ===
    ("Records Retention", "Fact versions follow NARA GRS 5.2 Item 020 with 3-year retention"),
    ("Records Retention", "Approval decisions follow NARA GRS 5.2 Item 020 with 3-year retention"),
    ("Records Retention", "The full audit trail follows NARA GRS 3.2 Item 031 with 6-year retention"),
    ("Records Retention", "Signature records follow NARA GRS 5.2 Item 020 with 3-year retention"),
    ("Records Retention", "User feedback follows NARA GRS 5.7 Item 010 with 1-year retention after resolved"),
    ("Records Retention", "Import sessions are retained 90 days after completion"),
    ("Records Retention", "System configuration follows NARA GRS 3.1 Item 010 deleted when superseded"),

    # === Compliance Artifacts > Collibra Registration ===
    ("Collibra Registration", "artiFACT will be registered as a data source in Advana Collibra data catalog"),
    ("Collibra Registration", "The data refresh frequency is near-real-time via delta feed API"),
    ("Collibra Registration", "The data format is JSON via REST API"),
    ("Collibra Registration", "The API spec follows OpenAPI 3.0"),
    ("Collibra Registration", "The data quality score is high"),
    ("Collibra Registration", "Quality is high because every fact is human-reviewed and approved"),

    # === Compliance Artifacts > CUI Training ===
    ("CUI Training", "All artiFACT users must have current DoD CUI awareness training"),
    ("CUI Training", "CUI training compliance is enforced administratively by user commands"),
    ("CUI Training", "CUI training is not enforced by the application"),
    ("CUI Training", "The login splash screen includes a certification statement"),

    # === Compliance Artifacts > OWASP ZAP Results ===
    ("OWASP ZAP Results", "OWASP ZAP dynamic application security testing runs in the CI pipeline"),
    ("OWASP ZAP Results", "HIGH findings must be resolved before deployment"),
    ("OWASP ZAP Results", "MEDIUM findings must be resolved before deployment"),
    ("OWASP ZAP Results", "The ZAP report is attached to the RMF evidence package"),
]

# ---------------------------------------------------------------------------
# Document templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "name": "Concept of Operations",
        "abbreviation": "ConOps",
        "description": "Describes the system purpose, operational context, user roles, data flows, and security posture",
        "sections": [
            {"key": "purpose", "title": "1. Purpose", "prompt": "Describe the system's purpose and the operational need it addresses", "guidance": "Focus on: what problem does the system solve, who uses it, why existing tools are insufficient"},
            {"key": "system_overview", "title": "2. System Overview", "prompt": "Describe the system at a high level — what it does, how users interact with it", "guidance": "Focus on: capabilities, user experience, key workflows"},
            {"key": "operational_context", "title": "3. Operational Context", "prompt": "Describe where and how the system operates within the DON enterprise", "guidance": "Focus on: hosting environment, network access, organizational relationships"},
            {"key": "user_roles", "title": "4. User Roles and Responsibilities", "prompt": "Describe who uses the system and what each role can do", "guidance": "Focus on: role hierarchy, permission model, typical user workflows"},
            {"key": "data_flows", "title": "5. Data Flows", "prompt": "Describe how data moves through the system", "guidance": "Focus on: data sources, processing, storage, outputs, external integrations"},
            {"key": "security", "title": "6. Security Considerations", "prompt": "Describe the security posture and compliance framework", "guidance": "Focus on: Zero Trust, CAC auth, encryption, CUI handling, ATO status"},
        ],
    },
    {
        "name": "System Design Document",
        "abbreviation": "SDD",
        "description": "Describes the system architecture, data design, interfaces, security design, deployment, and test strategy",
        "sections": [
            {"key": "architecture", "title": "1. Architecture Overview", "prompt": "Describe the system architecture, technology stack, and design patterns", "guidance": "Focus on: modular monolith, bounded contexts, API-first, container deployment"},
            {"key": "data_design", "title": "2. Data Design", "prompt": "Describe the database schema, data model, and storage strategy", "guidance": "Focus on: PostgreSQL tables, relationships, JSONB patterns, S3 usage"},
            {"key": "interface_design", "title": "3. Interface Design", "prompt": "Describe the API design, authentication, and external integrations", "guidance": "Focus on: REST endpoints, OpenAPI spec, Advana sync, SAML/CAC"},
            {"key": "security_design", "title": "4. Security Design", "prompt": "Describe the security architecture in detail", "guidance": "Focus on: RBAC, CSRF, encryption, ZT pillars, FIPS, audit logging"},
            {"key": "deployment", "title": "5. Deployment Architecture", "prompt": "Describe how the system is deployed, scaled, and maintained", "guidance": "Focus on: Docker, ECS Fargate, RDS, Redis, CI/CD pipeline, blue/green"},
            {"key": "testing", "title": "6. Test Strategy", "prompt": "Describe the testing approach", "guidance": "Focus on: test pyramid, coverage targets, CI enforcement, E2E tests"},
        ],
    },
    {
        "name": "System Security Plan",
        "abbreviation": "SSP",
        "description": "Describes system identification, security controls, Zero Trust compliance, data protection, incident response, and continuous monitoring",
        "sections": [
            {"key": "system_id", "title": "1. System Identification", "prompt": "Describe the system name, owner, classification, impact level, and authorization boundary", "guidance": "Focus on: DITPR ID, COSMOS boundary, IL-4/5, CUI handling"},
            {"key": "system_description", "title": "2. System Description", "prompt": "Describe the system purpose, architecture, and key capabilities", "guidance": "Focus on: mission need, technology stack, user base"},
            {"key": "security_controls", "title": "3. Security Controls", "prompt": "Describe the implemented security controls mapped to NIST 800-53", "guidance": "Focus on: AC, AU, IA, SC, SI control families with specific implementations"},
            {"key": "zt_compliance", "title": "4. Zero Trust Compliance", "prompt": "Describe how the system addresses each DoD ZT pillar", "guidance": "Focus on: all 7 pillars, inherited vs implemented controls"},
            {"key": "data_protection", "title": "5. Data Protection", "prompt": "Describe encryption, CUI handling, PII protections, and data retention", "guidance": "Focus on: AES-256, TLS, classification markings, NARA schedules"},
            {"key": "incident_response", "title": "6. Incident Response", "prompt": "Describe the incident response procedures and automated remediation", "guidance": "Focus on: anomaly detection, auto-session-expire, log forwarding, escalation"},
            {"key": "continuous_monitoring", "title": "7. Continuous Monitoring", "prompt": "Describe the ongoing security assessment approach", "guidance": "Focus on: CI/CD scanning, SBOM, ZAP, Wiz, cATO pipeline"},
        ],
    },
    {
        "name": "Test and Evaluation Master Plan",
        "abbreviation": "TEMP",
        "description": "Describes the overall test strategy, infrastructure, unit testing, integration testing, security testing, and acceptance criteria",
        "sections": [
            {"key": "test_overview", "title": "1. Test Overview", "prompt": "Describe the overall test strategy and objectives", "guidance": "Focus on: test pyramid, coverage targets, CI enforcement"},
            {"key": "test_infrastructure", "title": "2. Test Infrastructure", "prompt": "Describe the test environment and tooling", "guidance": "Focus on: Docker PostgreSQL, pytest, conftest fixtures, no SQLite"},
            {"key": "unit_tests", "title": "3. Unit Testing", "prompt": "Describe the unit test approach for each module", "guidance": "Focus on: per-component tests, mocking rules, what NOT to mock"},
            {"key": "integration_tests", "title": "4. Integration Testing", "prompt": "Describe the integration test approach", "guidance": "Focus on: real DB, real Redis, HTTP client tests, security regression"},
            {"key": "security_testing", "title": "5. Security Testing", "prompt": "Describe the security testing approach", "guidance": "Focus on: OWASP ZAP, pip-audit, SBOM, permission enforcement tests"},
            {"key": "acceptance_criteria", "title": "6. Acceptance Criteria", "prompt": "Describe the acceptance criteria for each sprint", "guidance": "Focus on: Definition of Success bullets, pass/fail criteria"},
        ],
    },
    {
        "name": "Systems Engineering Plan",
        "abbreviation": "SEP",
        "description": "Describes the SE approach, technical baseline, interface management, risk management, and configuration management",
        "sections": [
            {"key": "se_approach", "title": "1. SE Approach", "prompt": "Describe the systems engineering methodology and governance", "guidance": "Focus on: modular monolith, sprint-based development, bounded contexts"},
            {"key": "technical_baseline", "title": "2. Technical Baseline", "prompt": "Describe the current technical architecture and design decisions", "guidance": "Focus on: technology choices, schema decisions, API design"},
            {"key": "interfaces", "title": "3. Interface Management", "prompt": "Describe internal and external interfaces", "guidance": "Focus on: module boundaries, kernel services, Advana API, SAML"},
            {"key": "risk_management", "title": "4. Technical Risk Management", "prompt": "Describe identified technical risks and mitigations", "guidance": "Focus on: graceful degradation, vendor independence, FOSS stack"},
            {"key": "configuration_mgmt", "title": "5. Configuration Management", "prompt": "Describe version control, branching, deployment strategy", "guidance": "Focus on: git, squash merge, semver, Docker images, blue-green"},
        ],
    },
]


def _resolve_node_title(fact_path: str) -> str:
    """Extract the leaf node title from a fact path."""
    if " > " in fact_path:
        return fact_path.rsplit(" > ", 1)[-1]
    return fact_path


def _build_node_title_to_path() -> dict[str, str]:
    """Build a mapping from leaf title to full path for unique resolution."""
    title_to_paths: dict[str, list[str]] = {}
    for path, _, _ in TAXONOMY:
        leaf = path.rsplit(" > ", 1)[-1] if " > " in path else path
        title_to_paths.setdefault(leaf, []).append(path)
    result: dict[str, str] = {}
    for title, paths in title_to_paths.items():
        if len(paths) == 1:
            result[title] = paths[0]
    return result


def _resolve_fact_to_path(fact_path: str, title_map: dict[str, str]) -> str | None:
    """Resolve a fact's node reference to a full taxonomy path."""
    if " > " in fact_path:
        leaf = fact_path.rsplit(" > ", 1)[-1]
        for path, _, _ in TAXONOMY:
            if path.endswith(fact_path) or path == fact_path:
                return path
        return title_map.get(leaf)
    return title_map.get(fact_path)


async def _seed_taxonomy(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Create taxonomy nodes. artiFACT is a root node (no parent).

    Returns path -> node_uid mapping.
    """
    path_to_uid: dict[str, uuid.UUID] = {}
    sorted_tax = sorted(TAXONOMY, key=lambda t: t[1])

    for path, depth, sort_order in sorted_tax:
        leaf_title = path.rsplit(" > ", 1)[-1] if " > " in path else path

        if " > " in path:
            parent_path = path.rsplit(" > ", 1)[0]
            parent_uid = path_to_uid.get(parent_path)
            if parent_uid is None:
                log.error("parent_not_found", path=path, parent=parent_path)
                continue
        else:
            # artiFACT is a root node — no parent
            parent_uid = None

        # Check if exists
        if parent_uid is not None:
            result = await db.execute(
                select(FcNode).where(
                    FcNode.title == leaf_title,
                    FcNode.parent_node_uid == parent_uid,
                )
            )
        else:
            result = await db.execute(
                select(FcNode).where(
                    FcNode.title == leaf_title,
                    FcNode.parent_node_uid.is_(None),
                    FcNode.node_depth == depth,
                )
            )
        existing = result.scalar_one_or_none()
        if existing:
            path_to_uid[path] = existing.node_uid
            log.info("node_exists", title=leaf_title, depth=depth)
            continue

        node_uid = uuid.uuid4()
        node = FcNode(
            node_uid=node_uid,
            parent_node_uid=parent_uid,
            title=leaf_title,
            slug=_slug(leaf_title),
            node_depth=depth,
            sort_order=sort_order,
            is_archived=False,
            created_by_uid=JALLRED_UID,
        )
        db.add(node)
        path_to_uid[path] = node_uid
        log.info("node_created", title=leaf_title, depth=depth)

    await db.flush()
    return path_to_uid


async def _seed_permission(db: AsyncSession, artifact_node_uid: uuid.UUID) -> None:
    """Grant signatory permission to jallred on the artiFACT node."""
    result = await db.execute(
        select(FcNodePermission).where(
            FcNodePermission.user_uid == JALLRED_UID,
            FcNodePermission.node_uid == artifact_node_uid,
            FcNodePermission.revoked_at.is_(None),
        )
    )
    if result.scalar_one_or_none():
        log.info("permission_exists", user="jallred", node="artiFACT")
        return

    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=JALLRED_UID,
        node_uid=artifact_node_uid,
        role="signatory",
        granted_by_uid=JALLRED_UID,
    )
    db.add(perm)
    await db.flush()
    log.info("permission_created", user="jallred", node="artiFACT", role="signatory")


async def _seed_facts(db: AsyncSession, path_to_uid: dict[str, uuid.UUID]) -> int:
    """Create facts and published versions. Returns count created."""
    title_map = _build_node_title_to_path()
    created = 0
    event_time = SEED_TIME

    for fact_ref, sentence in FACTS:
        full_path = _resolve_fact_to_path(fact_ref, title_map)
        if full_path is None:
            log.warning("fact_node_not_found", ref=fact_ref, sentence=sentence[:60])
            continue

        node_uid = path_to_uid.get(full_path)
        if node_uid is None:
            log.warning("fact_node_uid_missing", path=full_path, sentence=sentence[:60])
            continue

        # Idempotent: skip if sentence already exists
        result = await db.execute(
            select(FcFactVersion).where(FcFactVersion.display_sentence == sentence)
        )
        if result.scalar_one_or_none():
            continue

        fact_uid = uuid.uuid4()
        version_uid = uuid.uuid4()
        event_time = event_time + timedelta(seconds=1)

        fact = FcFact(
            fact_uid=fact_uid,
            node_uid=node_uid,
            current_published_version_uid=None,
            is_retired=False,
            created_at=event_time,
            created_by_uid=JALLRED_UID,
        )
        db.add(fact)
        await db.flush()

        version = FcFactVersion(
            version_uid=version_uid,
            fact_uid=fact_uid,
            state="published",
            display_sentence=sentence,
            metadata_tags=[],
            classification="UNCLASSIFIED",
            created_at=event_time,
            created_by_uid=JALLRED_UID,
            published_at=event_time,
        )
        db.add(version)
        await db.flush()

        fact.current_published_version_uid = version_uid
        await db.flush()

        db.add(FcEventLog(
            event_uid=uuid.uuid4(),
            entity_type="version",
            entity_uid=version_uid,
            event_type="fact.created",
            payload={"state": "proposed", "fact_uid": str(fact_uid)},
            actor_uid=JALLRED_UID,
            occurred_at=event_time,
        ))
        db.add(FcEventLog(
            event_uid=uuid.uuid4(),
            entity_type="version",
            entity_uid=version_uid,
            event_type="fact.published",
            payload={"state": "published", "fact_uid": str(fact_uid)},
            actor_uid=JALLRED_UID,
            occurred_at=event_time + timedelta(seconds=0.5),
        ))
        created += 1

    await db.flush()
    return created


async def _seed_templates(db: AsyncSession) -> int:
    """Create document templates. Returns count created."""
    created = 0
    for tmpl_data in TEMPLATES:
        result = await db.execute(
            select(FcDocumentTemplate).where(
                FcDocumentTemplate.abbreviation == tmpl_data["abbreviation"]
            )
        )
        if result.scalar_one_or_none():
            log.info("template_exists", abbr=tmpl_data["abbreviation"])
            continue

        tmpl = FcDocumentTemplate(
            template_uid=uuid.uuid4(),
            name=tmpl_data["name"],
            abbreviation=tmpl_data["abbreviation"],
            description=tmpl_data["description"],
            sections=tmpl_data["sections"],
            is_active=True,
            created_by_uid=JALLRED_UID,
        )
        db.add(tmpl)
        created += 1
        log.info("template_created", name=tmpl_data["name"])

    await db.flush()
    return created


async def run_seed() -> None:
    """Main seed entry point."""
    log.info("artifact_corpus_seed_starting")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as db:
        async with db.begin():
            path_to_uid = await _seed_taxonomy(db)

            artifact_uid = path_to_uid.get("artiFACT")
            if artifact_uid is None:
                log.error("artifact_node_not_created")
                return

            await _seed_permission(db, artifact_uid)

            fact_count = await _seed_facts(db, path_to_uid)
            log.info("facts_created", count=fact_count)

            tmpl_count = await _seed_templates(db)
            log.info("templates_created", count=tmpl_count)

    await engine.dispose()

    log.info(
        "artifact_corpus_seed_complete",
        nodes=len(TAXONOMY),
        facts_defined=len(FACTS),
        facts_created=fact_count,
        templates=tmpl_count,
    )


if __name__ == "__main__":
    asyncio.run(run_seed())
