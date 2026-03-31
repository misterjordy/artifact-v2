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
    FcFactComment,
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
    ("artiFACT > Program Definition", 1, 1),
    ("artiFACT > Architecture & Design", 1, 2),
    ("artiFACT > Security & Compliance", 1, 3),
    ("artiFACT > Data & Privacy", 1, 4),
    ("artiFACT > User Roles & Workflows", 1, 5),
    ("artiFACT > AI Integration", 1, 6),
    ("artiFACT > Operations & Deployment", 1, 7),
    ("artiFACT > Architecture Diagrams", 1, 8),
    ("artiFACT > Compliance Artifacts", 1, 9),
    # Leaves under Program Definition (depth 2)
    ("artiFACT > Program Definition > System Purpose & Capabilities", 2, 1),
    ("artiFACT > Program Definition > Problem Statement & Justification", 2, 2),
    ("artiFACT > Program Definition > Stakeholders", 2, 3),
    ("artiFACT > Program Definition > Budget & Sustainment", 2, 4),
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
    ("artiFACT > Data & Privacy > Bulk Data Export & Portability", 2, 3),
    ("artiFACT > Data & Privacy > External Data Sharing", 2, 4),
    # Leaves under User Roles & Workflows (depth 2)
    ("artiFACT > User Roles & Workflows > Role Hierarchy", 2, 1),
    ("artiFACT > User Roles & Workflows > Permission Model", 2, 2),
    ("artiFACT > User Roles & Workflows > Fact Lifecycle", 2, 3),
    ("artiFACT > User Roles & Workflows > Approval Workflow", 2, 4),
    ("artiFACT > User Roles & Workflows > Signing Workflow", 2, 5),
    # Leaves under AI Integration (depth 2)
    ("artiFACT > AI Integration > BYOK Architecture", 2, 1),
    ("artiFACT > AI Integration > AI Chat & Fact Retrieval", 2, 2),
    ("artiFACT > AI Integration > AI-Powered Document Import", 2, 3),
    ("artiFACT > AI Integration > Document Generation", 2, 4),
    ("artiFACT > AI Integration > AI Safety Controls", 2, 5),
    # Leaves under Operations & Deployment (depth 2)
    ("artiFACT > Operations & Deployment > Container Architecture", 2, 1),
    ("artiFACT > Operations & Deployment > COSMOS Deployment", 2, 2),
    ("artiFACT > Operations & Deployment > Fault Tolerance & Graceful Degradation", 2, 3),
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
    # === Program Definition > System Purpose & Capabilities ===
    ("System Purpose & Capabilities", "artiFACT is a taxonomy-driven atomic fact corpus platform"),
    ("System Purpose & Capabilities", "artiFACT manages DoD software acquisition engineering documentation"),
    ("System Purpose & Capabilities", "artiFACT decomposes traditional acquisition documents into atomic facts"),
    ("System Purpose & Capabilities", "Each fact is version-controlled and signable"),
    ("System Purpose & Capabilities", "Facts are organized in a hierarchical taxonomy"),
    ("System Purpose & Capabilities", "artiFACT replaces 71 engineering artifacts with a single source of truth"),
    ("System Purpose & Capabilities", "Those 71 artifacts carry over 30 percent duplicative content"),
    ("System Purpose & Capabilities", "Documents are generated on demand from the current corpus"),
    ("System Purpose & Capabilities", "Documents are not maintained as static files"),
    ("System Purpose & Capabilities", "artiFACT treats individual factual statements as first-class entities"),
    ("System Purpose & Capabilities", "Each fact entity has version control"),
    ("System Purpose & Capabilities", "Each fact entity has approval workflows"),
    ("System Purpose & Capabilities", "Each fact entity has digital signatures"),
    ("System Purpose & Capabilities", "Each fact entity has classification markings"),
    ("System Purpose & Capabilities", "The system provides AI-assisted document generation"),
    ("System Purpose & Capabilities", "artiFACT follows the DoD Software Acquisition Pathway"),
    ("System Purpose & Capabilities", "artiFACT operates under the Adaptive Acquisition Framework"),
    ("System Purpose & Capabilities", "artiFACT is developed internally by a NAVWAR program office"),
    ("System Purpose & Capabilities", "Development uses existing government labor"),
    ("System Purpose & Capabilities", "There is no contract vehicle"),
    ("System Purpose & Capabilities", "There is no ACAT designation"),
    ("System Purpose & Capabilities", "No milestone decision authority is required"),
    ("System Purpose & Capabilities", "artiFACT is not a program of record"),
    ("System Purpose & Capabilities", "artiFACT is an internal productivity tool for program offices"),
    ("System Purpose & Capabilities", "The codebase includes an architecture document"),
    ("System Purpose & Capabilities", "The codebase includes a master reference with style guides and pseudocode"),
    ("System Purpose & Capabilities", "The codebase includes 15 sprint files with definitions of success"),
    ("System Purpose & Capabilities", "The codebase includes an OpenAPI spec"),

    # === Program Definition > Problem Statement & Justification ===
    ("Problem Statement & Justification", "A typical DoD acquisition program has 71 engineering artifacts"),
    ("Problem Statement & Justification", "Those 71 artifacts carry over 30 percent duplicative content"),
    ("Problem Statement & Justification", "When a single fact changes a human must manually find every document containing that fact"),
    ("Problem Statement & Justification", "A human must then manually update each of those documents"),
    ("Problem Statement & Justification", "artiFACT stores each fact once in one place"),
    ("Problem Statement & Justification", "Each stored fact has version control"),
    ("Problem Statement & Justification", "Each stored fact has approval workflows"),
    ("Problem Statement & Justification", "The system addresses the DON need for authoritative atomic data"),
    ("Problem Statement & Justification", "Atomic data can be programmatically assembled into any required document format"),
    ("Problem Statement & Justification", "Duplicative content across acquisition documents costs thousands of engineering hours across the DON"),
    ("Problem Statement & Justification", "artiFACT supplements existing workflows rather than replacing them"),
    ("Problem Statement & Justification", "Users can continue using Word documents while gradually building their corpus"),

    # === Program Definition > Stakeholders & User Community ===
    ("Stakeholders & User Community", "The system is developed for NAVWAR"),
    ("Stakeholders & User Community", "The target users are DON program managers"),
    ("Stakeholders & User Community", "The target users include engineers"),
    ("Stakeholders & User Community", "The target users include acquisition professionals"),
    ("Stakeholders & User Community", "COSMOS NIWC Pacific provides the cloud hosting infrastructure"),
    ("Stakeholders & User Community", "Advana Jupiter is the downstream data consumer"),
    ("Stakeholders & User Community", "Advana consumes data via the delta feed API"),
    ("Stakeholders & User Community", "The program manager is Jordan Allred"),
    ("Stakeholders & User Community", "The Jupiter team registers artiFACT as a data source in their Apigee gateway"),
    ("Stakeholders & User Community", "artiFACT is accessible from any CAC-enabled browser"),
    ("Stakeholders & User Community", "artiFACT is accessible on commercial internet"),
    ("Stakeholders & User Community", "artiFACT is accessible on DODIN"),

    # === Program Definition > Cost Model & Sustainment ===
    ("Cost Model & Sustainment", "Annual sustainment cost is approximately 2100 dollars"),
    ("Cost Model & Sustainment", "Hosting is provided by COSMOS on a consumption basis"),
    ("Cost Model & Sustainment", "COSMOS hosting requires no commitment"),
    ("Cost Model & Sustainment", "There are zero license fees"),
    ("Cost Model & Sustainment", "AI costs are per user"),
    ("Cost Model & Sustainment", "Each users organization pays for their own Bedrock usage"),
    ("Cost Model & Sustainment", "Typical AI cost is 5 to 50 dollars per month per user"),
    ("Cost Model & Sustainment", "No contractor support is required for daily operations"),
    ("Cost Model & Sustainment", "The system runs unattended between deployments"),
    ("Cost Model & Sustainment", "The entire stack is FOSS"),
    ("Cost Model & Sustainment", "There is no vendor dependency"),
    ("Cost Model & Sustainment", "There is no SaaS subscription"),
    ("Cost Model & Sustainment", "There is no commercial support contract"),
    ("Cost Model & Sustainment", "The source code is government-owned"),
    ("Cost Model & Sustainment", "Amazon Bedrock is used for AI features"),
    ("Cost Model & Sustainment", "Bedrock is not required for core operations"),
    ("Cost Model & Sustainment", "If funding is cut all data can be exported via the sync full endpoint"),
    ("Cost Model & Sustainment", "Total recovery time after funding restoration is approximately one day"),

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
    ("Backend", "No file exceeds 500 lines"),
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

    # === Data & Privacy > Bulk Data Export & Portability ===
    ("Bulk Bulk Data Export & Portability", "GET api v1 sync full returns every node and fact version as JSON"),
    ("Bulk Bulk Data Export & Portability", "GET api v1 sync full returns every signature and user record as JSON"),
    ("Bulk Bulk Data Export & Portability", "GET api v1 sync full returns every audit event as JSON"),
    ("Bulk Bulk Data Export & Portability", "Fact exports are available in TXT format"),
    ("Bulk Bulk Data Export & Portability", "Fact exports are available in JSON format"),
    ("Bulk Bulk Data Export & Portability", "Fact exports are available in NDJSON format"),
    ("Bulk Bulk Data Export & Portability", "Fact exports are available in CSV format"),
    ("Bulk Bulk Data Export & Portability", "Generated DOCX documents are downloadable with signed S3 URLs"),
    ("Bulk Bulk Data Export & Portability", "Signed S3 URLs expire after 24 hours"),
    ("Bulk Bulk Data Export & Portability", "There is zero data lock-in"),

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

    # === AI Integration > AI Chat & Fact Retrieval ===
    ("AI Chat & Fact Retrieval", "AI chat loads published facts into the system prompt"),
    ("AI Chat & Fact Retrieval", "Only facts from the users accessible nodes are loaded"),
    ("AI Chat & Fact Retrieval", "Token counting ensures the prompt fits the model context window"),
    ("AI Chat & Fact Retrieval", "The actual loaded fact count is reported to the client"),
    ("AI Chat & Fact Retrieval", "Output filtering catches attempts at bulk fact dumps"),

    # === AI Integration > AI-Powered Document Import ===
    ("AI-Powered Document Import", "Users can upload DOCX documents for AI-powered fact extraction"),
    ("AI-Powered Document Import", "Users can upload PDF documents for AI-powered fact extraction"),
    ("AI-Powered Document Import", "Users can upload TXT documents for AI-powered fact extraction"),
    ("AI-Powered Document Import", "Analysis runs as a Celery background task"),
    ("AI-Powered Document Import", "Progress is streamed via SSE"),
    ("AI-Powered Document Import", "Extracted facts are staged for human review before proposal"),
    ("AI-Powered Document Import", "Duplicate detection uses Jaccard similarity against existing facts"),

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

    # === Operations & Deployment > Fault Tolerance & Graceful Degradation ===
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When Redis is down the permission resolver falls back to direct PostgreSQL queries"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When Redis is down the rate limiter skips limiting"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When Redis is down the rate limiter logs a warning"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When Redis is down the session store falls back to signed JWT cookies"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When Redis is down the badge counter returns negative one"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When Redis is down the UI shows a dash instead of a count"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When S3 is down browse and edit features remain functional"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When S3 is down sign and queue features remain functional"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When the external LLM API is down all non-AI features remain functional"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "When PostgreSQL is down everything fails"),
    ("Fault Tolerance & Fault Tolerance & Graceful Degradation", "PostgreSQL is the source of truth"),

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

    # === Architecture & Design > Data Model > Workflow Tables (challenge columns) ===
    ("Workflow Tables", "fc_fact_comment has a proposed_sentence column for challenge alternative wording"),
    ("Workflow Tables", "fc_fact_comment has a resolution_state column constrained to approved or rejected"),
    ("Workflow Tables", "fc_fact_comment has a resolution_note column for approver rationale"),
    ("Workflow Tables", "A partial index idx_comment_challenge_pending accelerates the pending challenges queue"),

    # === Architecture & Design > Data Model > Core Tables (version history) ===
    ("Core Tables", "fc_fact_version uses a supersedes_version_uid linked list to order version history"),
    ("Core Tables", "Version history is fetched with three batch queries assembled in Python to avoid N-plus-one"),

    # === User Roles & Workflows > Fact Lifecycle (challenges + history) ===
    ("Fact Lifecycle", "Users can challenge a published fact by proposing alternative wording"),
    ("Fact Lifecycle", "Challenges must be submitted within 30 days of publication"),
    ("Fact Lifecycle", "Approving a challenge creates a new published version rather than mutating the original"),

    # === User Roles & Workflows > Approval Workflow (challenge resolution) ===
    ("Approval Workflow", "Approvers resolve challenges by approving or rejecting the proposed alternative"),

    # === Program Definition > System Purpose & Capabilities (program boundaries + UI) ===
    ("System Purpose & Capabilities", "Root-level taxonomy nodes define program boundaries for data separation"),
    ("System Purpose & Capabilities", "The playground reset wipes only the Special Projects subtree and restores from a snapshot"),

    # === Security & Compliance > Audit & Accountability ===
    ("Audit & Accountability", "The audit recorder subscribes to 13 event types including challenge lifecycle events"),
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

# ---------------------------------------------------------------------------
# Contextual comments: (display_sentence, comment_body)
# Each comment is attached to the published version of the matching fact.
# Categories: disagreeable design decisions, highly technical concepts,
#             jargony/agency-specific terminology.
# ---------------------------------------------------------------------------
FACT_COMMENTS: list[tuple[str, str]] = [
    # === POTENTIALLY DISAGREEABLE ===
    (
        "Advana Jupiter is the downstream data consumer",
        "artiFACT is the system of truth \u2014 it owns fact creation, approval, and versioning."
        " Advana is the system of record for analytics. Data flows one direction: Advana pulls"
        " from us via the delta feed. This is standard data engineering \u2014 the authoritative"
        " source publishes, the consumer subscribes. Two-way sync would create reconciliation"
        " conflicts with no clear winner.",
    ),
    (
        "artiFACT feeds data to Jupiter Advana via a standard REST API",
        "artiFACT publishes; Advana subscribes. The pull-based model means artiFACT has zero"
        " dependencies on Advana's availability or schema. If Advana changes their ingestion"
        " pipeline, artiFACT's API remains stable. This is proper data mesh architecture.",
    ),
    (
        "Documents are not maintained as static files",
        "When a fact changes, every document containing it must reflect the update. Static files"
        " diverge the moment a fact is edited. Generating on demand guarantees every document"
        " reflects the current approved corpus \u2014 no manual sync, no stale versions, no"
        " conflicting copies.",
    ),
    (
        "artiFACT is not a program of record",
        "artiFACT is an internal productivity tool under the Software Acquisition Pathway. Its"
        " near-zero sustainment cost and government-labor development model fall below the"
        " thresholds requiring program-of-record designation, ACAT categorization, or milestone"
        " decisions.",
    ),
    (
        "When PostgreSQL is down everything fails",
        "This is intentional. PostgreSQL is the single source of truth for all fact data. Serving"
        " stale or cached data during a database outage risks showing users outdated facts they"
        " might sign or approve \u2014 that's worse than an honest error page. RDS Multi-AZ"
        " provides automatic failover in under 60 seconds.",
    ),
    (
        "CUI training is not enforced by the application",
        "CUI training is a command responsibility per DoDI 5200.48, not an application function."
        " artiFACT enforces CUI markings on data; training compliance is tracked by each user's"
        " organization. The login splash screen includes a certification statement as a"
        " procedural control.",
    ),
    (
        "artiFACT does not independently verify device posture",
        "COSMOS provides device posture assessment at the network perimeter via Netskope and"
        " CNAP. Duplicating this check at the application layer would add complexity without"
        " improving security posture \u2014 the network already blocks non-compliant devices"
        " before they reach artiFACT.",
    ),
    (
        "There is no contract vehicle",
        "All development uses existing government GS/NH labor billets. No procurement action is"
        " needed because no external vendor is involved. This eliminates contract overhead,"
        " organizational conflicts of interest, and the IP complications of"
        " contractor-developed code.",
    ),
    (
        "The entire stack is FOSS",
        "FOSS = Free and Open Source Software. This eliminates license costs, vendor lock-in,"
        " and supply chain risk from proprietary dependencies. The government retains full source"
        " code ownership and can operate, modify, or fork the system indefinitely without"
        " commercial agreements.",
    ),
    (
        "Users provide their own AI API keys",
        "BYOK (Bring Your Own Key) eliminates the blast radius of a key compromise to a single"
        " user, avoids centralized cost allocation disputes, and means artiFACT never holds a"
        " master AI key that could be exfiltrated. Each organization pays for what they use.",
    ),
    (
        "When Redis is down the rate limiter skips limiting",
        "Fail-open on rate limiting is the correct trade-off. The alternative \u2014 blocking all"
        " requests when Redis is unavailable \u2014 would cascade a cache failure into a full"
        " outage. Rate limiting is a defense-in-depth measure, not a primary security control.",
    ),
    (
        "There is zero data lock-in",
        "The sync/full endpoint dumps the entire database as structured JSON. Any program can"
        " export all their facts, versions, signatures, and audit history at any time. If"
        " artiFACT were shut down tomorrow, no data would be lost.",
    ),
    (
        "If funding is cut all data can be exported via the sync full endpoint",
        "The export endpoint requires only a running instance and authentication. Even in a"
        " wind-down scenario, the complete corpus can be extracted as structured JSON for"
        " migration to another system or archival.",
    ),

    # === HIGHLY TECHNICAL ===
    (
        "The event log uses a monotonic BIGINT seq column",
        "A monotonic sequence is a counter that only goes up. Consumers store the last seq they"
        " saw, then request everything after it. Unlike timestamps, sequence numbers never"
        " collide \u2014 two events in the same millisecond still get unique, ordered seq values.",
    ),
    (
        "fc_event_log has a monotonic seq column for the Advana delta feed",
        "The seq column is a database-generated counter that only increases. Advana stores the"
        " last seq it pulled, then asks for all events after that number. This is more reliable"
        " than timestamps because no two events share the same seq value.",
    ),
    (
        "BIGINT seq provides cursor consistency",
        "Timestamps can collide when two events happen in the same millisecond, and clock skew"
        " across servers can produce out-of-order values. A database-generated BIGINT sequence"
        " guarantees strict ordering \u2014 a downstream consumer never misses or double-processes"
        " an event.",
    ),
    (
        "fc_fact_version has a generated tsvector for full-text search",
        "A tsvector is PostgreSQL's built-in full-text search type. It breaks text into"
        " normalized tokens so queries like \"acquisition pathway\" match without exact string"
        " comparison or an external search engine. The column updates automatically when a"
        " fact's text changes.",
    ),
    (
        "All JSON columns use JSONB not JSON or TEXT",
        "JSONB is a binary format PostgreSQL can index and query inside the document. Plain JSON"
        " stores raw text with no indexing capability. JSONB gives both flexible schema and"
        " query performance.",
    ),
    (
        "All UID columns use native UUID type not CHAR 36",
        "Native UUID uses 16 bytes vs. 36 bytes for a string representation. It enables proper"
        " indexing and comparison without string collation overhead, and PostgreSQL validates the"
        " format at the type level.",
    ),
    (
        "All timestamp columns use TIMESTAMPTZ not TIMESTAMP",
        "TIMESTAMPTZ stores the absolute moment in UTC regardless of server timezone. Plain"
        " TIMESTAMP is ambiguous \u2014 the same value means different things on servers"
        " configured to different timezones.",
    ),
    (
        "Foreign keys use ON DELETE RESTRICT for core entities",
        "RESTRICT prevents deleting a row that other rows reference. It forces explicit cleanup"
        " before deletion \u2014 you can't accidentally delete a fact that has versions,"
        " comments, or signatures pointing to it.",
    ),
    (
        "Signing runs as one UPDATE WHERE IN query inside a transaction",
        "A single query inside one transaction means either all facts get signed or none do. No"
        " partial signatures, no inconsistent state. The batch approach also avoids N round-trips"
        " to the database for N facts.",
    ),
    (
        "CSRF validation is required on all POST PUT PATCH DELETE requests",
        "CSRF (Cross-Site Request Forgery) is an attack where a malicious page tricks your"
        " browser into submitting a request to a site you're already logged into. The CSRF token"
        " proves the request originated from artiFACT's own pages, not a third-party site.",
    ),
    (
        "CSRF is validated on all state-changing HTTP methods",
        "State-changing methods (POST, PUT, PATCH, DELETE) require a token proving the request"
        " came from artiFACT's own pages. GET requests are exempt because they don't modify"
        " data \u2014 this follows the HTTP specification's safety guarantees.",
    ),
    (
        "Input sanitization includes Unicode NFKC normalization",
        "NFKC collapses visually identical but technically different Unicode characters into one"
        " canonical form. Without it, two facts that look identical on screen could be stored as"
        " separate entries because they use different byte sequences.",
    ),
    (
        "Duplicate detection uses Jaccard similarity against existing facts",
        "Jaccard similarity measures word overlap between two texts as a percentage. If a new"
        " fact shares 80%+ of its words with an existing fact, it's flagged as a potential"
        " duplicate for human review rather than silently creating a near-copy.",
    ),
    (
        "Permission cache TTL is 300 seconds",
        "TTL = Time To Live. The cached permission result is trusted for 5 minutes before"
        " re-checking the database. Permission changes take effect within 5 minutes while"
        " avoiding a database query on every single request.",
    ),
    (
        "Permission resolution is cached in Redis",
        "Rather than querying the database on every request to check if a user can access a"
        " resource, the result is cached in Redis (an in-memory store) for 5 minutes. This"
        " reduces database load while ensuring permission changes take effect within a"
        " reasonable window.",
    ),
    (
        "Jinja2 autoescape prevents XSS",
        "XSS (Cross-Site Scripting) injects malicious JavaScript into web pages viewed by other"
        " users. Autoescape automatically converts characters like < and > into harmless display"
        " text, so user-provided content can never execute as code in another user's browser.",
    ),
    (
        "SBOM generation runs in the CI pipeline",
        "SBOM = Software Bill of Materials \u2014 a list of every library and dependency in the"
        " application, like a nutrition label for software. Required by Executive Order 14028"
        " for all federal software. Submitted as part of the RMF evidence package.",
    ),
    (
        "Deployment uses blue-green strategy via ECS task definition updates",
        "Blue-green runs two identical environments. New code deploys to the idle one; once"
        " health checks pass, traffic switches over. If something breaks, traffic switches back"
        " instantly \u2014 zero downtime, instant rollback.",
    ),
    (
        "Token counting ensures the prompt fits the model context window",
        "Language models have a fixed input size measured in tokens (roughly 3/4 of a word"
        " each). If too many facts are sent, the model silently ignores the overflow. Token"
        " counting ensures we include the maximum number of facts that actually fit.",
    ),
    (
        "Reversible events include server-computed reverse_payload",
        "The server computes the \"undo\" data at the time of the original action, capturing the"
        " before-state. This means undo doesn't rely on the client to send correct reversal"
        " data \u2014 the server is the authority on what the state was before the change.",
    ),
    (
        "No public endpoint exists to inject arbitrary undo payloads",
        "The undo system uses server-computed reverse_payloads stored at event time. If a public"
        " endpoint accepted client-provided undo data, an attacker could forge a \"reversal\""
        " that makes arbitrary changes to the database.",
    ),
    (
        "The event bus uses publish and subscribe",
        "Publish/subscribe decouples the code that causes an event from the code that reacts to"
        " it. When a fact is approved, the queue module publishes the event \u2014 audit, badges,"
        " and cache all respond independently without the queue module knowing they exist.",
    ),
    (
        "The system is a modular monolith",
        "A modular monolith is a single deployable application with strict internal boundaries."
        " It gets the simplicity of one deployment (no network calls between services, one"
        " database transaction) with the maintainability of separate modules that can't"
        " accidentally depend on each other's internals.",
    ),
    (
        "Each bounded context has a strict public interface of router.py and schemas.py",
        "Other modules can only interact with a bounded context through its HTTP router"
        " (endpoints) and Pydantic schemas (data contracts). Internal files like service.py are"
        " private \u2014 this prevents tight coupling between modules.",
    ),
    (
        "No component inside one context ever imports from inside another context",
        "If the queue module needs fact data, it reads from the shared database \u2014 it never"
        " imports facts/service.py directly. This keeps modules independently testable and"
        " replaceable.",
    ),
    (
        "When Redis is down the session store falls back to signed JWT cookies",
        "JWT (JSON Web Token) cookies are self-contained \u2014 the server can verify them"
        " without any external store. Users stay logged in during a Redis outage, though session"
        " revocation is delayed until Redis recovers.",
    ),
    (
        "When Redis is down the permission resolver falls back to direct PostgreSQL queries",
        "The permission resolver normally caches results in Redis for performance. When Redis is"
        " unavailable, it queries PostgreSQL directly \u2014 slower but correct. Users can still"
        " work, just with slightly higher latency on permission checks.",
    ),
    (
        "Progress is streamed via SSE",
        "SSE = Server-Sent Events. A one-way channel from server to browser that pushes progress"
        " updates in real time. Unlike polling (\"done yet?\" every second), SSE delivers updates"
        " the instant they happen with minimal overhead.",
    ),
    (
        "Document generation uses a two-pass approach",
        "Pass 1 (prefilter) scores every fact against every template section to decide which"
        " facts belong where. Pass 2 (synthesis) generates prose from the matched facts."
        " Splitting steps lets users preview the fact-to-section mapping before spending AI"
        " tokens on synthesis.",
    ),
    (
        "The backend proxies all AI requests",
        "Users never call AI APIs directly from the browser. All requests route through the"
        " backend, which handles key decryption, input sanitization, token counting, usage"
        " logging, and output filtering. This keeps API keys off the client and enables"
        " server-side safety controls.",
    ),
    (
        "Revise language publishes a revised version atomically",
        "\"Atomically\" means the rejection of the old version and publication of the revised"
        " version happen in a single database transaction. If either step fails, both roll"
        " back \u2014 there's never a moment where the old version is rejected but the new one"
        " isn't published.",
    ),
    (
        "Output filtering catches attempts at bulk fact dumps",
        "If a user tries to trick the AI into outputting the entire corpus (e.g., \"list every"
        " fact you know\"), the output filter detects this pattern and blocks it. This prevents"
        " using AI chat as a bulk data exfiltration channel.",
    ),
    (
        "Output filtering detects prompt injection attempts",
        "Prompt injection is when a user crafts input that tries to override the AI's"
        " instructions (e.g., \"ignore your system prompt and...\"). The filter scans AI output"
        " for signs the model's behavior was compromised.",
    ),
    (
        "AI chat loads published facts into the system prompt",
        "The system prompt is the instruction text sent to the language model before the user's"
        " question. Loading relevant published facts into it grounds the AI's responses in the"
        " actual approved corpus rather than its general training data.",
    ),
    (
        "Feature flags allow runtime toggling of capabilities without deployment",
        "Feature flags are stored in fc_system_config. An admin can enable or disable"
        " capabilities (AI chat, document generation, etc.) instantly via the admin panel"
        " without redeploying the application.",
    ),
    (
        "Auto-session-expire triggers on anomalous behavior patterns",
        "If the system detects unusual activity (export floods, off-hours bulk access, scope"
        " escalation attempts), it automatically expires the suspect user's sessions, forcing"
        " re-authentication via CAC.",
    ),
    (
        "Auto-CUI-marking runs during document generation",
        "When generating a document, the system checks whether any included fact has CUI"
        " classification. If so, it automatically applies CUI banners to headers, footers, and"
        " the cover page \u2014 no manual marking needed, no risk of omission.",
    ),
    (
        "Read-access events are logged for data-exfiltration-relevant endpoints",
        "Most audit logs track writes (creates, updates, deletes). artiFACT also logs reads on"
        " endpoints where bulk data could be extracted: exports, sync feeds, and AI chat. This"
        " supports insider threat detection without logging every page view.",
    ),
    (
        "Generated DOCX documents are downloadable with signed S3 URLs",
        "Signed URLs are temporary links that grant access to a specific S3 object without"
        " requiring the user to have S3 credentials. The URL is valid for 24 hours \u2014"
        " accessible but not permanently public.",
    ),
    (
        "Fact exports are available in NDJSON format",
        "NDJSON = Newline-Delimited JSON. Each line is a complete JSON object, making it easy"
        " to stream-process large exports line by line without loading the entire file into"
        " memory. Popular format for data pipelines.",
    ),
    (
        "All containers run as non-root appuser",
        "Running as non-root limits the damage if an attacker breaches the application. Even"
        " with code execution inside the container, they can't modify system files, install"
        " packages, or escalate to host-level access.",
    ),
    (
        "Kernel provides the event bus",
        "The event bus is a publish/subscribe system that decouples modules. When something"
        " happens (fact approved, challenge created), the acting module publishes an event."
        " Other modules \u2014 audit, badges, cache \u2014 subscribe and react independently.",
    ),
    (
        "Kernel provides content filtering",
        "Content filtering scans user-submitted text for profanity, junk input, and potential"
        " prompt injection before it reaches the database. Shared via the kernel so every module"
        " gets consistent input sanitization.",
    ),
    (
        "When S3 is down browse and edit features remain functional",
        "S3 stores file uploads, exports, and snapshots \u2014 not fact data. Core fact"
        " browsing, editing, and approval workflows run entirely against PostgreSQL, so they're"
        " unaffected by S3 outages.",
    ),
    (
        "When the external LLM API is down all non-AI features remain functional",
        "AI features (chat, import analysis, document generation) are additive. The core"
        " workflow \u2014 create, edit, approve, sign, export \u2014 has zero dependency on any"
        " AI provider.",
    ),
    (
        "A signatory can sign all published facts under a node in a single batch",
        "Batch signing covers a taxonomy subtree. Signing the \"SNIPE-B\" node signs every"
        " published fact under that node and its children in one operation \u2014 no need to"
        " click through hundreds of individual facts.",
    ),
    (
        "Signatures apply to the current published versions at signing time",
        "A signature is a point-in-time attestation. If a fact is later revised, the new version"
        " is unsigned and needs a fresh signature. The old signature remains on the old version"
        " as a historical record.",
    ),
    (
        "Point-in-time recovery is available to any second in the last 35 days",
        "RDS continuous backups mean the database can be restored to its exact state at any"
        " specific second in the past 35 days. If a bad migration runs at 2:13 PM, we can"
        " recover to 2:12 PM.",
    ),
    (
        "Admin-triggered pg_dump uploads snapshots to S3",
        "pg_dump creates a logical backup \u2014 a portable SQL file that can be restored to any"
        " PostgreSQL instance. Unlike RDS automated backups (block-level), pg_dump is useful for"
        " cross-environment migration or disaster recovery.",
    ),
    (
        "Total recovery time after funding restoration is approximately one day",
        "The entire infrastructure is defined in Terraform and the application is containerized."
        " Standing up a fresh environment means running terraform apply, pushing the Docker"
        " images, and running the seed scripts.",
    ),
    (
        "AI API keys are encrypted with AES-256-GCM",
        "AES-256-GCM provides both encryption (confidentiality) and authentication (tamper"
        " detection) in one operation. The 256-bit key length meets CNSS Policy 15 requirements"
        " for protecting sensitive data at rest.",
    ),
    (
        "The AES-256-GCM master key is stored in AWS Secrets Manager",
        "Secrets Manager provides hardware-backed key storage with automatic rotation, audit"
        " logging, and IAM-controlled access. The encryption key never exists on disk or in"
        " application code \u2014 it's fetched at runtime and held only in memory.",
    ),
    (
        "The permission resolver uses a single kernel function called can",
        "A single entry point for all permission checks means every access decision is"
        " consistent and auditable. The \"can\" function is the only way to check"
        " permissions \u2014 no scattered role checks throughout the codebase.",
    ),

    # === JARGONY / AGENCY-SPECIFIC ===
    (
        "Fact versions follow NARA GRS 5.2 Item 020",
        "NARA = National Archives and Records Administration. GRS = General Records Schedule."
        " GRS 5.2 covers \"Transitory and Intermediary Records.\" Item 020: records superseded"
        " by a new version must be retained 3 years after supersession, then eligible for"
        " destruction.",
    ),
    (
        "Fact versions follow NARA GRS 5.2 Item 020 with 3-year retention",
        "NARA GRS 5.2/020 = National Archives General Records Schedule for transitory records."
        " When a fact version is superseded by a newer version, the old one must be kept 3 years"
        " before it can be deleted.",
    ),
    (
        "The audit trail follows NARA GRS 3.2 Item 031",
        "GRS 3.2 covers \"Information Technology Management Records.\" Item 031 covers system"
        " access and security audit trails \u2014 retain 6 years after the end of the audit"
        " period, then eligible for destruction.",
    ),
    (
        "The full audit trail follows NARA GRS 3.2 Item 031 with 6-year retention",
        "NARA GRS 3.2/031 = audit trail retention rule. All system access logs and mutation"
        " records must be kept 6 years. This covers fc_event_log entries used for both"
        " compliance evidence and the undo system.",
    ),
    (
        "User feedback follows NARA GRS 5.7 Item 010",
        "GRS 5.7 covers \"Miscellaneous Communications Records.\" Item 010: routine suggestions"
        " and feedback \u2014 destroy 1 year after resolution or final action.",
    ),
    (
        "System config follows NARA GRS 3.1 Item 010",
        "GRS 3.1 covers \"General Technology Management Records.\" Item 010: system parameters"
        " and configuration records \u2014 destroy when superseded by an updated configuration.",
    ),
    (
        "Signature records follow NARA GRS 5.2 Item 020 with 3-year retention",
        "Same schedule as fact versions: electronic signature records for routine administrative"
        " actions are retained 3 years after the signed action is completed, then eligible for"
        " destruction per NARA GRS 5.2/020.",
    ),
    (
        "System configuration follows NARA GRS 3.1 Item 010 deleted when superseded",
        "When an admin changes a feature flag or rate limit, the old value can be deleted"
        " immediately \u2014 no retention period required. GRS 3.1/010 recognizes that"
        " superseded configuration has no archival value.",
    ),
    (
        "artiFACT must be registered in the DoD IT Portfolio Repository",
        "DITPR (ditpr.osd.mil) is the authoritative registry of all DoD information systems."
        " Registration is required by DoDI 8510.01 for any system seeking an Authority to"
        " Operate.",
    ),
    (
        "There is no ACAT designation",
        "ACAT = Acquisition Category. Levels I through III determine oversight requirements"
        " based on dollar thresholds (DoDI 5000.85). artiFACT's near-zero sustainment cost and"
        " internal labor model fall well below any ACAT threshold.",
    ),
    (
        "No milestone decision authority is required",
        "A Milestone Decision Authority (MDA) is the senior official who approves a program's"
        " progression through acquisition phases. artiFACT's use of the Software Acquisition"
        " Pathway with internal labor doesn't trigger the thresholds requiring MDA oversight.",
    ),
    (
        "CNAP zero trust network access is inherited from COSMOS",
        "CNAP = Cloud Native Access Point. It replaces traditional VPN with identity-aware,"
        " per-session network access. COSMOS provides this at the platform level \u2014 every"
        " request is authenticated at the network layer before it reaches the application.",
    ),
    (
        "COSMOS NIWC Pacific provides the cloud hosting infrastructure",
        "COSMOS = Cloud One SIPR/NIPR Management and Operations Services. NIWC Pacific's"
        " managed cloud platform providing AWS GovCloud infrastructure, SAML identity, CNAP"
        " network access, and a shared ATO authorization boundary.",
    ),
    (
        "Production authentication uses CAC via COSMOS SAML",
        "CAC = Common Access Card, the DoD's smart card for identity. SAML = Security Assertion"
        " Markup Language, the protocol COSMOS uses to pass CAC-verified identity to"
        " applications. The user inserts their CAC, COSMOS validates it, and sends artiFACT a"
        " signed assertion.",
    ),
    (
        "EDIPI is extracted from the SAML assertion",
        "EDIPI = Electronic Data Interchange Personal Identifier. A unique 10-digit number"
        " assigned to every CAC holder. It's the authoritative person identifier across all DoD"
        " systems \u2014 like a DoD-wide user ID that persists through name changes or unit"
        " transfers.",
    ),
    (
        "The production impact level is IL-4 and IL-5",
        "Impact Levels are defined by the DoD Cloud Computing SRG. IL-4 covers CUI in"
        " commercial cloud. IL-5 covers CUI in DoD cloud and higher-sensitivity unclassified"
        " data. COSMOS GovCloud is authorized for both.",
    ),
    (
        "Amazon Bedrock operates at IL-4 and IL-5",
        "This means Bedrock in AWS GovCloud is authorized to process CUI data. artiFACT can"
        " send fact text to Bedrock for AI operations without violating data handling"
        " requirements.",
    ),
    (
        "artiFACT operates under the COSMOS authorization boundary",
        "An authorization boundary defines the systems, networks, and controls assessed as one"
        " unit for an Authority to Operate (ATO). Operating under COSMOS's boundary means"
        " artiFACT inherits infrastructure controls and the shared ATO rather than obtaining its"
        " own from scratch.",
    ),
    (
        "The SSP skeleton is maintained in the codebase",
        "SSP = System Security Plan. The central RMF document describing how each NIST 800-53"
        " security control is implemented. Maintaining the skeleton in code keeps it in sync"
        " with the actual implementation rather than drifting in a separate document.",
    ),
    (
        "Logs forward to CSSP SIEM",
        "CSSP = Cybersecurity Service Provider. SIEM = Security Information and Event"
        " Management. The CSSP operates a centralized threat detection system. Forwarding logs"
        " there is required for continuous monitoring under the RMF.",
    ),
    (
        "artiFACT is accessible on DODIN",
        "DODIN = Department of Defense Information Network. The global DoD enterprise network"
        " connecting all military installations. Accessible on DODIN means users on military"
        " networks can reach artiFACT without special routing or VPN.",
    ),
    (
        "artiFACT will be registered as a data source in Advana Collibra data catalog",
        "Collibra is Advana's enterprise data catalog and governance platform. Registration lets"
        " the broader DoD analytics community discover what data artiFACT publishes, understand"
        " its schema, and assess its quality.",
    ),
    (
        "The Jupiter team registers artiFACT as a data source in their Apigee gateway",
        "Apigee is Google's API gateway product. Advana/Jupiter uses it as their data mesh"
        " ingress. Registration means Advana discovers artiFACT's OpenAPI spec and pulls data"
        " through the gateway with standard authentication and rate limiting.",
    ),
    (
        "artiFACT operates under the Adaptive Acquisition Framework",
        "The Adaptive Acquisition Framework (DoDI 5000.02) defines six acquisition pathways."
        " artiFACT uses the Software Acquisition Pathway (DoDI 5000.87), designed for iterative"
        " development with continuous delivery rather than traditional milestone-based"
        " acquisition.",
    ),
    (
        "artiFACT follows the DoD Software Acquisition Pathway",
        "The Software Acquisition Pathway (DoDI 5000.87) is designed for iterative software"
        " development with continuous delivery, user feedback, and value-based assessment \u2014"
        " as opposed to the traditional hardware-oriented milestone process.",
    ),
    (
        "Duplicative content across acquisition documents costs thousands of engineering"
        " hours across the DON",
        "DON = Department of the Navy (includes Navy and Marine Corps). NAVWAR (Naval"
        " Information Warfare Systems Command) is the DON command that develops artiFACT.",
    ),
    (
        "The target users are DON program managers",
        "DON = Department of the Navy (Navy + Marine Corps). Program managers are responsible"
        " for delivering weapon systems and IT capabilities \u2014 they maintain those 71"
        " engineering artifacts artiFACT is designed to consolidate.",
    ),
    (
        "The classification field supports CUI with category markings",
        "CUI = Controlled Unclassified Information (32 CFR Part 2002). Requires safeguarding"
        " but isn't classified. Category markings (e.g., CUI//SP-CTI for Controlled Technical"
        " Information) specify handling requirements beyond the base CUI designation.",
    ),
    (
        "CUI never leaves the authorization boundary",
        "The authorization boundary encompasses all COSMOS infrastructure (ECS, RDS, S3, Bedrock"
        " in GovCloud). CUI stays within this controlled perimeter \u2014 never sent to"
        " commercial cloud regions or third-party services outside the boundary.",
    ),
    (
        "Continuous ATO leverages the DevSecOps pipeline",
        "DevSecOps = Development, Security, and Operations integrated into one workflow."
        " Security checks (SBOM, SAST, DAST, dependency audit) run automatically on every code"
        " change rather than being bolted on at the end.",
    ),
    (
        "The target is continuous ATO",
        "ATO = Authority to Operate. Traditional ATO is a point-in-time assessment that can take"
        " 6-18 months and becomes stale immediately. Continuous ATO replaces this with automated"
        " security checks on every change, maintaining a constantly verified posture.",
    ),
    (
        "COSMOS provides RegScale for RMF artifact management",
        "RegScale is a GRC (Governance, Risk, and Compliance) platform for managing RMF"
        " artifacts, control assessments, and continuous monitoring evidence. It replaces the"
        " manual spreadsheet tracking most programs use for security documentation.",
    ),
    (
        "COSMOS provides Wiz for infrastructure scanning",
        "Wiz is a cloud security posture management tool that scans infrastructure"
        " configuration, container images, and running workloads for vulnerabilities and"
        " misconfigurations. COSMOS provides it as a shared service.",
    ),
    (
        "Sessions are re-validated every 15 minutes",
        "Re-validation checks that the user's account is still active and permissions haven't"
        " been revoked. The 15-minute interval aligns with NIST SP 800-207 Zero Trust"
        " guidance \u2014 frequent enough to catch revocations promptly without excessive"
        " database load.",
    ),
    (
        "Session re-validation interval aligns with Zero Trust Pillar 1",
        "Zero Trust Pillar 1 (User Identity) requires continuous verification rather than"
        " one-time authentication. NIST SP 800-207 recommends re-validating sessions at regular"
        " intervals to ensure accounts haven't been revoked or compromised since last check.",
    ),
    (
        "Per-node RBAC enforces least privilege at the taxonomy level",
        "RBAC = Role-Based Access Control. \"Per-node\" means permissions are granted on"
        " individual taxonomy nodes, not system-wide. A user can be an approver on one program"
        " but only a viewer on another \u2014 the minimum access needed for their role.",
    ),
    (
        "COSMOS uses Netskope and CNAP for device posture",
        "Netskope is a SASE (Secure Access Service Edge) platform that inspects traffic and"
        " enforces security policies. Combined with CNAP, it verifies that connecting devices"
        " meet DoD security baselines before allowing access.",
    ),
    (
        "OWASP ZAP provides dynamic application security testing",
        "OWASP = Open Web Application Security Project. ZAP = Zed Attack Proxy. It simulates"
        " real attacks against the running application \u2014 testing for SQL injection, XSS,"
        " and other OWASP Top 10 vulnerabilities. \"Dynamic\" means it tests the live app, not"
        " just source code.",
    ),
    (
        "The ZAP report is attached to the RMF evidence package",
        "RMF = Risk Management Framework (NIST SP 800-37). The evidence package is the"
        " collection of artifacts submitted to the authorizing official to demonstrate security"
        " controls are properly implemented. ZAP results serve as evidence for application"
        " security controls.",
    ),
    (
        "pip-audit runs in the CI pipeline",
        "pip-audit scans Python dependencies for known security vulnerabilities by checking them"
        " against the OSV (Open Source Vulnerabilities) database. No code with known-vulnerable"
        " dependencies can be deployed.",
    ),
    (
        "Pydantic validates all API input",
        "Pydantic is a Python data validation library that enforces type constraints, value"
        " ranges, and format rules on every incoming API request. If a field should be a UUID"
        " and the client sends plain text, Pydantic rejects it before the code ever sees it.",
    ),
    (
        "Production uses Iron Bank base images",
        "Iron Bank is the DoD's repository of hardened, pre-scanned container base images"
        " maintained by Platform One. Using these satisfies container hardening requirements"
        " without custom security work on each base image.",
    ),
    (
        "Production uses Iron Bank base images for container security",
        "Iron Bank is Platform One's repository of DoD-hardened container images. Pre-scanned"
        " and pre-approved, they provide a trusted starting point for containerized applications"
        " without custom hardening effort.",
    ),
    (
        "Browser authentication uses session cookies stored in Redis",
        "When you log in, the server creates a session record in Redis and sends your browser a"
        " cookie referencing it. On each request, the server looks up the session in Redis to"
        " verify you're still authenticated.",
    ),
    (
        "Celery beat handles scheduled data retention tasks",
        "Celery is a distributed task queue for Python. \"Beat\" is its built-in scheduler that"
        " triggers tasks on a cron-like schedule \u2014 here it runs the data retention cleanup"
        " per NARA GRS schedules.",
    ),
    (
        "artiFACT is accessible from any CAC-enabled browser",
        "CAC = Common Access Card, the DoD's standard smart card. Any browser with CAC reader"
        " support (card reader + middleware) can access artiFACT \u2014 no special client"
        " software or VPN needed.",
    ),
    (
        "artiFACT is developed internally by a NAVWAR program office",
        "NAVWAR = Naval Information Warfare Systems Command, headquartered in San Diego. The"
        " DON's acquisition command for C4ISR and cyber capabilities.",
    ),
    (
        "The system is developed for NAVWAR",
        "NAVWAR = Naval Information Warfare Systems Command. The Navy's acquisition command for"
        " command, control, communications, computers, intelligence, surveillance, and"
        " reconnaissance (C4ISR) systems.",
    ),
    (
        "Production uses ALB-only ingress",
        "ALB = Application Load Balancer. It's the only entry point from the network to the"
        " application \u2014 no open ports, no SSH, no direct routes to containers. All traffic"
        " passes through the ALB's TLS termination and health checks.",
    ),
    (
        "Production uses private VPC subnets",
        "VPC = Virtual Private Cloud. Private subnets have no direct internet access \u2014"
        " containers, databases, and caches run in network isolation. Only the ALB sits in a"
        " public subnet to receive incoming requests.",
    ),
    (
        "artiFACT collects EDIPI",
        "EDIPI = Electronic Data Interchange Personal Identifier. A unique 10-digit DoD-wide"
        " person identifier extracted from the CAC/SAML assertion. Used internally for user"
        " identity \u2014 never exposed to other users or external APIs.",
    ),
    (
        "artiFACT collects CAC Distinguished Name",
        "The CAC Distinguished Name (DN) is the X.509 certificate subject from the user's smart"
        " card \u2014 a structured string identifying the person and their issuing CA. Used to"
        " link the SAML assertion back to a specific CAC certificate.",
    ),
    (
        "OWASP ZAP dynamic application security testing runs in the CI pipeline",
        "OWASP ZAP (Zed Attack Proxy) simulates real attacks against the running application on"
        " every build. It tests for the OWASP Top 10 vulnerabilities automatically \u2014 no"
        " manual penetration testing needed for routine changes.",
    ),
    (
        "Production uses ECS Fargate",
        "ECS Fargate = AWS Elastic Container Service in serverless mode. AWS manages the"
        " underlying servers \u2014 artiFACT just defines how many containers to run and their"
        " resource limits. No patching EC2 instances.",
    ),
    (
        "ECS Fargate is the production orchestrator on COSMOS",
        "Fargate is AWS's serverless container platform \u2014 it runs Docker containers without"
        " requiring you to manage the underlying virtual machines. COSMOS provisions the Fargate"
        " cluster; artiFACT defines task configurations via Terraform.",
    ),
    (
        "fc_user columns include CAC DN EDIPI display name email and global role",
        "CAC DN = Common Access Card Distinguished Name (X.509 certificate subject). EDIPI ="
        " Electronic Data Interchange Personal Identifier (10-digit DoD person ID). Both are"
        " extracted from the SAML assertion at login, not entered by the user.",
    ),
    (
        "COSMOS has an existing ATO through NIWC Pacific",
        "ATO = Authority to Operate. NIWC Pacific = Naval Information Warfare Center Pacific."
        " COSMOS's existing ATO means the platform-level security controls (network,"
        " infrastructure, identity) are already assessed and authorized \u2014 artiFACT inherits"
        " them.",
    ),
    (
        "The Advana sync API does not include EDIPI",
        "EDIPI is a DoD person identifier that could be used for cross-system tracking."
        " Excluding it from the sync API follows the principle of minimum necessary"
        " disclosure \u2014 Advana gets display names for attribution but not the unique"
        " identifier.",
    ),
    (
        "All PII is derived from the COSMOS SAML assertion at login",
        "SAML = Security Assertion Markup Language. COSMOS sends a signed assertion containing"
        " the user's identity attributes (name, email, EDIPI, DN) at login. artiFACT never asks"
        " users to type in PII \u2014 it's all machine-to-machine from the identity provider.",
    ),
    (
        "RDS uses Multi-AZ",
        "Multi-AZ = Multi-Availability Zone. AWS maintains a synchronous replica of the database"
        " in a separate data center. If the primary fails, the replica is promoted"
        " automatically \u2014 typically under 60 seconds of downtime.",
    ),
    (
        "Terraform manages all infrastructure as code",
        "Terraform is a tool that defines cloud infrastructure (servers, databases, networks) as"
        " declarative code files. This means the entire production environment can be recreated"
        " from scratch by running one command \u2014 no manual console clicking.",
    ),

    # === PASS 2: AGGRESSIVE COVERAGE (60% target) ===

    # --- ACCESS CONTROL MODEL ---
    (
        "A grant on a parent applies to all descendants",
        "Cascading grants eliminate the need to assign permissions on every leaf node"
        " individually. An approver on \"System Identity\" automatically has approval rights"
        " on all child nodes beneath it.",
    ),
    (
        "Permissions are never checked by reading global_role directly",
        "Directly reading global_role from the user record would bypass node-level permissions"
        " entirely. All access decisions go through the kernel \"can\" function, which considers"
        " node context, role hierarchy, and grant cascading.",
    ),
    (
        "The can function checks user role node and action",
        "The \"can\" function is the single entry point for all permission checks \u2014 it takes"
        " (user, node, action) and returns a boolean. Centralizing this logic prevents scattered"
        " role checks throughout the codebase.",
    ),
    (
        "The role hierarchy is signatory then approver then subapprover then contributor"
        " then viewer",
        "Each role inherits all capabilities of the roles below it: signatory can do everything"
        " an approver can, an approver can do everything a subapprover can, and so on down to"
        " viewer.",
    ),

    # --- AI SAFETY CONTROLS ---
    (
        "AI usage is tracked in fc_ai_usage",
        "fc_ai_usage logs every AI API call with provider, model, token count, and estimated"
        " cost. This enables per-user cost attribution under the BYOK model and anomaly"
        " detection for unusual usage patterns.",
    ),
    (
        "Output filtering detects bulk fact dumps",
        "Bulk fact dumps are a data exfiltration vector. If a user prompts the AI to \"list all"
        " facts,\" the output filter detects the pattern and blocks it before the response"
        " reaches the client.",
    ),
    (
        "Rate limiting is applied per user",
        "Per-user rate limiting prevents any single account from monopolizing AI resources or"
        " running denial-of-service against the LLM provider. Limits are configurable via"
        " fc_system_config.",
    ),
    (
        "Tracked AI usage fields include provider and model",
        "Tracking provider and model per request enables cost allocation, performance comparison"
        " between models, and the ability to identify if a specific model version causes quality"
        " regressions.",
    ),

    # --- APPROVAL WORKFLOW ---
    (
        "Approve publishes the version and sets published_at",
        "Publishing sets published_at and transitions the version state to \"published.\" The"
        " fact entity's published_version_uid pointer updates atomically in the same"
        " transaction.",
    ),
    (
        "Contributors propose facts which enter the approval queue",
        "Contributors are the lowest role that can create content. Their proposals must be"
        " reviewed and approved before becoming part of the published corpus \u2014 enforcing"
        " four-eyes review on all fact content.",
    ),
    (
        "Revise language rejects the original version",
        "\"Revise language\" is a convenience action: the approver edits the text and publishes"
        " the corrected version in one step, rather than rejecting and waiting for the"
        " contributor to resubmit.",
    ),

    # --- ATO & RMF ---
    (
        "Application-level security is tested via OWASP ZAP",
        "OWASP ZAP = Open Web Application Security Project Zed Attack Proxy. It runs automated"
        " penetration testing against the live application, probing for SQL injection, XSS, and"
        " other OWASP Top 10 vulnerabilities.",
    ),
    (
        "Application-level security is tested via SBOM",
        "SBOM = Software Bill of Materials. A machine-readable inventory of every dependency."
        " Required by Executive Order 14028 for federal software and submitted as RMF evidence.",
    ),
    (
        "Control implementation statements are maintained in the codebase",
        "Maintaining control implementation statements in the codebase keeps them versioned"
        " alongside the actual code. When a security control changes, the documentation updates"
        " in the same commit.",
    ),
    (
        "Test coverage exceeds 80 percent",
        "80% overall coverage with 95% on the kernel ensures the most critical shared code is"
        " thoroughly tested. The kernel handles auth, permissions, encryption, and events \u2014"
        " a bug there affects every module.",
    ),
    (
        "The incident response runbook is maintained in the codebase",
        "An incident response runbook in the codebase means it's version-controlled,"
        " peer-reviewed, and always co-located with the system it describes. Required for NIST"
        " 800-53 IR controls.",
    ),

    # --- AUDIT & ACCOUNTABILITY ---
    (
        "Every mutation emits an event captured in fc_event_log",
        "Every state change \u2014 fact created, approved, signed, retired, permission"
        " granted \u2014 creates an immutable event record. This provides the evidence trail"
        " required by NIST 800-53 AU controls and powers the undo system.",
    ),
    (
        "The seq column serves as the Advana delta feed cursor",
        "The seq column is a monotonic BIGINT that only increases. Advana stores the last seq"
        " it pulled and asks for everything after it \u2014 more reliable than timestamps"
        " because no two events share the same seq.",
    ),

    # --- AUTHENTICATION ---
    (
        "API authentication uses Authorization Bearer tokens",
        "Bearer tokens are for machine-to-machine integrations (e.g., Advana sync). Human users"
        " authenticate via CAC/SAML session cookies. Two distinct authentication paths serve"
        " distinct use cases.",
    ),

    # --- BACKEND ---
    (
        "Alembic manages database schema migrations",
        "Alembic is the standard database migration tool for SQLAlchemy. Each migration is a"
        " versioned Python script that can upgrade or downgrade the schema, providing a"
        " reproducible history of all database changes.",
    ),
    (
        "Celery handles background task processing",
        "Celery is a distributed task queue for Python. Long-running operations like document"
        " generation, import analysis, and data retention cleanup run in Celery workers so the"
        " web server remains responsive.",
    ),
    (
        "FastAPI is the web framework",
        "FastAPI is a modern Python web framework built on Starlette and Pydantic. It provides"
        " automatic OpenAPI spec generation, async support, and type-based request validation"
        " out of the box.",
    ),
    (
        "mypy runs in strict mode for type checking",
        "mypy is Python's static type checker. Strict mode requires type annotations on every"
        " function parameter and return value, catching type errors at build time rather than at"
        " runtime in production.",
    ),
    (
        "Redis serves as the Celery message broker",
        "Redis serves dual duty as both a cache/session store and the message broker for Celery"
        " task distribution. Using one Redis instance for both eliminates a separate RabbitMQ"
        " dependency.",
    ),
    (
        "ruff format enforces code formatting",
        "ruff is a Python linter and formatter written in Rust \u2014 orders of magnitude faster"
        " than Black or flake8. Consistent formatting eliminates style debates in code reviews.",
    ),
    (
        "structlog provides structured JSON logging",
        "structlog produces JSON-formatted log entries with structured key-value fields. This"
        " makes logs machine-parseable for CloudWatch queries and Grafana dashboards without"
        " regex parsing.",
    ),
    (
        "The backend uses Python 3.12",
        "Python 3.12 provides performance improvements, better error messages, and native"
        " support for the type syntax used throughout the codebase.",
    ),
    (
        "Uvicorn serves as the ASGI server",
        "Uvicorn is an ASGI (Asynchronous Server Gateway Interface) server. ASGI is the async"
        " successor to WSGI, enabling concurrent request handling without threads \u2014"
        " critical for SSE streaming and background task coordination.",
    ),
    (
        "No file exceeds 500 lines",
        "The 500-line file limit forces decomposition into focused, single-responsibility"
        " modules. It is a hard rule enforced by ruff in CI \u2014 no exceptions.",
    ),
    (
        "No function exceeds 50 lines",
        "The 50-line function limit ensures every function does one thing and is easily"
        " testable. Functions approaching the limit are a signal to extract helper functions.",
    ),
    (
        "Every function has a type signature for parameters and return values",
        "Full type signatures enable mypy to catch type mismatches at build time. Combined with"
        " strict mode, this eliminates an entire class of runtime errors before code reaches"
        " production.",
    ),

    # --- BACKUP & RECOVERY ---
    (
        "RDS has automated backups with 35-day retention",
        "35-day retention means the database can be restored to any second in the past 5 weeks."
        " Combined with Multi-AZ failover, this provides both high availability and disaster"
        " recovery.",
    ),
    (
        "S3 versioning retains deleted objects for 30 days",
        "S3 versioning keeps prior versions of every object. If an export file is accidentally"
        " overwritten or deleted, the previous version can be recovered within 30 days.",
    ),

    # --- BOUNDED CONTEXTS ---
    (
        "The 13 contexts are taxonomy facts auth_admin audit queue signing import_pipeline"
        " export ai_chat search feedback presentation and admin",
        "These 13 contexts map to the core business capabilities of artiFACT: managing"
        " taxonomies, facts, auth, audit, queues, signing, import, export, AI chat, search,"
        " feedback, presentation, and administration.",
    ),
    (
        "The system has 13 bounded contexts",
        "Bounded contexts are a Domain-Driven Design concept: each context owns its own"
        " business logic and data access patterns. Modules interact through the kernel event"
        " bus and shared database models only.",
    ),
    (
        "The system contains approximately 108 internal components",
        "108 components across 13 contexts averages about 8 components per context. Each"
        " component is a focused Python module handling one responsibility (e.g., service.py,"
        " schemas.py, router.py).",
    ),
    (
        "Each bounded context is a top-level directory",
        "Top-level directories make the module structure visible at a glance. No hunting"
        " through nested packages \u2014 \"ls\" at the project root shows all 13 contexts"
        " immediately.",
    ),

    # --- BUDGET & SUSTAINMENT ---
    (
        "Annual sustainment cost is approximately 2100 dollars",
        "$2,100/year covers the COSMOS hosting consumption charge. Compare this to typical DoD"
        " SaaS contracts that run $500K\u2013$2M/year. The system runs unattended between"
        " deployments.",
    ),
    (
        "Amazon Bedrock is used for AI features",
        "Amazon Bedrock is a managed AI service in AWS GovCloud. It provides access to"
        " foundation models (Claude, Titan) at IL-4/IL-5 without managing GPU infrastructure.",
    ),
    (
        "Bedrock is not required for core operations",
        "All core workflows \u2014 create, edit, approve, sign, export \u2014 function without"
        " any AI provider. Bedrock powers optional features like chat, import analysis, and"
        " document generation.",
    ),
    (
        "COSMOS hosting requires no commitment",
        "COSMOS = Cloud One SIPR/NIPR Management and Operations Services. Consumption-based"
        " hosting means artiFACT pays only for what it uses \u2014 no reserved instances, no"
        " long-term commitments.",
    ),
    (
        "Each users organization pays for their own Bedrock usage",
        "Each organization configures their own Bedrock access via BYOK (Bring Your Own Key)."
        " artiFACT never holds a centralized AI budget \u2014 cost attribution is automatic.",
    ),
    (
        "No contractor support is required for daily operations",
        "The system runs unattended between deployments. No contractor staff needed to keep the"
        " lights on \u2014 automated backups, health checks, and log forwarding handle"
        " operations.",
    ),
    (
        "There are zero license fees",
        "Zero license fees because the entire stack is FOSS (Free and Open Source Software)"
        " \u2014 Python, PostgreSQL, Redis, FastAPI, HTMX, Alpine.js, Tailwind CSS.",
    ),
    (
        "There is no vendor dependency",
        "No vendor dependency means the government can operate, modify, or fork the system"
        " indefinitely without commercial agreements, renewals, or license negotiations.",
    ),
    (
        "The source code is government-owned",
        "Government-owned source code eliminates IP disputes, contractor lock-in, and the risk"
        " of losing access when a contract ends. Any government employee can maintain the"
        " system.",
    ),
    (
        "Typical AI cost is 5 to 50 dollars per month per user",
        "AI cost depends on usage volume \u2014 light users (occasional chat) trend toward"
        " $5/month; heavy users (frequent document generation) trend toward $50/month. Each"
        " organization pays their own Bedrock bill.",
    ),
    (
        "The system runs unattended between deployments",
        "Automated health checks, log forwarding, backups, and container restarts mean no human"
        " intervention is needed for day-to-day operations. Deployments happen only when new"
        " features ship.",
    ),

    # --- BYOK ARCHITECTURE ---
    (
        "Amazon Bedrock is planned for production",
        "Amazon Bedrock in AWS GovCloud is authorized for IL-4/IL-5 data processing. Production"
        " will use Bedrock instead of direct API calls to commercial providers.",
    ),
    (
        "Encrypted keys are stored in fc_user_ai_key",
        "API keys are encrypted with AES-256-GCM before storage. The encryption master key"
        " lives in AWS Secrets Manager \u2014 the plaintext key never touches disk or"
        " application code.",
    ),
    (
        "Keys are never exposed to the browser",
        "Keys are decrypted server-side only at the moment of an AI API call, then immediately"
        " discarded from memory. The browser never sees the plaintext key \u2014 all AI requests"
        " proxy through the backend.",
    ),

    # --- CHAT & CORPUS GROUNDING ---
    (
        "Only facts from the users accessible nodes are loaded",
        "Permission-scoped fact loading ensures the AI cannot leak facts a user doesn't have"
        " access to. The corpus grounding respects the same node-level permissions as the"
        " browse UI.",
    ),
    (
        "The actual loaded fact count is reported to the client",
        "Reporting the actual fact count to the client provides transparency: users know exactly"
        " how many facts ground the AI's response and can judge the completeness of the"
        " context.",
    ),

    # --- CI/CD PIPELINE ---
    (
        "Coverage target is 80 percent overall",
        "80% overall with 95% on the kernel is enforced in CI. The pipeline fails if coverage"
        " drops below these thresholds \u2014 no code merges without meeting the coverage bar.",
    ),
    (
        "Coverage target is 95 percent on kernel",
        "The kernel handles auth, permissions, encryption, and events \u2014 a bug there affects"
        " every module. 95% coverage ensures the most critical shared code is thoroughly"
        " tested.",
    ),
    (
        "The CI pipeline runs mypy in strict mode",
        "mypy strict mode catches type errors before runtime. Combined with full type"
        " annotations on every function, this eliminates an entire class of bugs at build time.",
    ),
    (
        "The CI pipeline runs pip-audit",
        "pip-audit checks every Python dependency against the OSV (Open Source Vulnerabilities)"
        " database. A known-vulnerable dependency fails the build \u2014 no manual security"
        " review needed.",
    ),
    (
        "The CI pipeline runs pytest",
        "pytest runs the full test suite including unit, integration, and API tests. All tests"
        " execute inside Docker containers matching the production environment.",
    ),
    (
        "The CI pipeline runs ruff check",
        "ruff check is a Python linter written in Rust that replaces flake8, isort, and dozens"
        " of other tools. It enforces code quality rules at build time.",
    ),
    (
        "The CI pipeline runs SBOM generation",
        "SBOM = Software Bill of Materials. Required by Executive Order 14028 for all federal"
        " software. The CI pipeline generates it automatically on every build.",
    ),

    # --- COLLIBRA REGISTRATION ---
    (
        "Quality is high because every fact is human-reviewed and approved",
        "Every fact in the corpus is human-reviewed and approved before publication. This means"
        " Collibra can rate artiFACT's data quality as \"high\" \u2014 it's not raw data or"
        " AI-generated content.",
    ),
    (
        "The API spec follows OpenAPI 3.0",
        "OpenAPI 3.0 is the industry standard for describing REST APIs. The spec is"
        " auto-generated from FastAPI route definitions, so documentation never drifts from"
        " implementation.",
    ),
    (
        "The data refresh frequency is near-real-time via delta feed API",
        "The delta feed API streams changes as they occur. Advana can poll for new data as"
        " frequently as needed \u2014 near-real-time freshness without batch ETL processes.",
    ),

    # --- CONTAINER ARCHITECTURE ---
    (
        "The Docker Compose stack includes a certbot container",
        "Certbot handles automatic TLS certificate provisioning and renewal via Let's Encrypt."
        " Used in development and staging; production TLS terminates at the ALB.",
    ),
    (
        "The Docker Compose stack includes a minio container",
        "MinIO is an S3-compatible object store. In development, it stands in for AWS S3 so"
        " file upload/download code works identically in both environments without conditionals.",
    ),
    (
        "The Docker Compose stack includes an nginx container",
        "Nginx serves as the reverse proxy in development \u2014 handling TLS termination,"
        " static file serving, and request routing to the web container. Production replaces it"
        " with the ALB.",
    ),
    (
        "The Docker Compose stack includes a postgres container",
        "PostgreSQL 16 runs as a container in development with the same major version as"
        " production RDS. This ensures SQL compatibility between environments.",
    ),
    (
        "The Docker Compose stack includes a redis container",
        "The Redis container provides caching, session storage, rate limiting, and the Celery"
        " message broker \u2014 matching the production ElastiCache configuration.",
    ),
    (
        "The Docker Compose stack includes a web container",
        "The web container runs Uvicorn serving the FastAPI application. In development it runs"
        " with --reload for hot code reloading; in production it runs multiple workers behind"
        " the ALB.",
    ),
    (
        "The Docker Compose stack includes a worker container",
        "The worker container runs Celery processes for background tasks \u2014 document"
        " generation, import analysis, data retention cleanup. Separate from the web container"
        " so long-running tasks don't block HTTP requests.",
    ),
    (
        "The worker container runs Celery for background tasks",
        "Celery workers process queued tasks asynchronously. Document generation can take 30+"
        " seconds \u2014 running it in a worker prevents the web server from timing out.",
    ),
    (
        "Uvicorn runs with reload in development",
        "Uvicorn --reload watches for file changes and restarts the server automatically."
        " Developers save a file and see the change immediately without manually restarting"
        " the container.",
    ),

    # --- CORE TABLES ---
    (
        "fc_fact has pointers to current published and signed versions",
        "fc_fact maintains pointers to the current (latest), published (approved), and signed"
        " versions. This enables instant lookups without scanning the version history.",
    ),
    (
        "fc_fact_version columns include state display_sentence metadata_tags and"
        " classification",
        "The display_sentence is the human-readable fact text. metadata_tags enable faceted"
        " filtering. classification tracks CUI status per fact. State drives the approval"
        " workflow.",
    ),
    (
        "fc_fact_version stores each version of a fact",
        "Each version is an immutable snapshot. Editing a fact creates a new version rather"
        " than modifying the existing one \u2014 the complete history of every change is"
        " preserved.",
    ),
    (
        "fc_node columns include parent_node_uid node_depth and sort_order",
        "parent_node_uid creates the tree structure. node_depth enables efficient ancestor"
        " queries. sort_order controls the display sequence within a parent node.",
    ),
    (
        "fc_node stores the hierarchical taxonomy",
        "fc_node is the backbone of artiFACT's data model. The hierarchical taxonomy organizes"
        " facts into a tree \u2014 programs contain branches, branches contain leaves, leaves"
        " contain facts.",
    ),
    (
        "Available node roles are signatory approver subapprover contributor and viewer",
        "Five granular roles enable least-privilege access. A viewer can browse; a contributor"
        " can propose; a subapprover helps review; an approver publishes; a signatory provides"
        " official attestation.",
    ),

    # --- COSMOS DEPLOYMENT ---
    (
        "ECR stores Docker container images",
        "ECR = Elastic Container Registry. AWS's Docker image registry. Container images are"
        " pushed to ECR by CI/CD and pulled by ECS Fargate at deployment time.",
    ),
    (
        "ElastiCache Redis runs as cache.t3.micro",
        "cache.t3.micro is the smallest ElastiCache instance type \u2014 sufficient for"
        " artiFACT's session, cache, and Celery broker workload. Keeps costs minimal while"
        " providing sub-millisecond latency.",
    ),
    (
        "Production runs 2 web tasks",
        "2 web tasks provide high availability \u2014 if one task fails, the other continues"
        " serving requests while ECS replaces the failed task automatically.",
    ),
    (
        "RDS PostgreSQL 16 runs as db.t3.small",
        "db.t3.small is a burstable instance type \u2014 sufficient for artiFACT's workload"
        " with the ability to burst CPU for peak loads. PostgreSQL 16 matches the development"
        " container version exactly.",
    ),
    (
        "S3 buckets store exports",
        "S3 buckets are organized by function: exports (generated documents), snapshots"
        " (admin-triggered pg_dump backups), and uploads (document import files).",
    ),
    (
        "Secrets Manager stores database credentials",
        "AWS Secrets Manager provides hardware-backed storage with IAM-controlled access,"
        " automatic rotation, and audit logging. Database credentials are never in config files"
        " or environment variables.",
    ),
    (
        "Secrets Manager stores the encryption master key",
        "The encryption master key encrypts all user AI API keys (BYOK). Storing it in Secrets"
        " Manager means the key is fetched at runtime and held only in memory \u2014 never"
        " written to disk.",
    ),
    (
        "S3 versioning is enabled",
        "S3 versioning keeps previous versions of every object. Combined with 30-day retention"
        " on deleted objects, this provides a safety net against accidental overwrites or"
        " deletions.",
    ),

    # --- CUI HANDLING ---
    (
        "AI API calls via Bedrock do not transmit PII",
        "Bedrock processes fact text for AI features but receives no user PII \u2014 no names,"
        " emails, EDIPIs, or CAC DNs are included in AI prompts. Only fact content is sent.",
    ),
    (
        "CUI banners appear when any included fact has CUI classification",
        "CUI = Controlled Unclassified Information (32 CFR Part 2002). CUI banners appear"
        " automatically when any fact included in a view or document carries CUI"
        " classification \u2014 no manual marking needed.",
    ),
    (
        "Per-fact classification fields enable granular CUI tracking",
        "Per-fact classification enables granular CUI tracking. A node can contain both"
        " unclassified and CUI facts \u2014 the system knows exactly which facts carry marking"
        " requirements.",
    ),
    (
        "Generated DOCX includes cover page classification marking",
        "DOCX cover page markings comply with DoDI 5200.48 requirements for CUI document"
        " marking. The highest classification of any included fact determines the"
        " document-level marking.",
    ),

    # --- CUI TRAINING ---
    (
        "All artiFACT users must have current DoD CUI awareness training",
        "DoD CUI awareness training is mandated by DoDI 5200.48. This is a personnel"
        " requirement, not an application feature \u2014 each user's command is responsible for"
        " tracking compliance.",
    ),
    (
        "The login splash screen includes a certification statement",
        "The login splash screen serves as a procedural control \u2014 users certify CUI"
        " awareness before accessing the system. This is a standard DoD information system"
        " access banner.",
    ),

    # --- DATA EXPORT & PORTABILITY ---
    (
        "GET api v1 sync full returns every audit event as JSON",
        "The sync/full endpoint is artiFACT's data portability guarantee. It dumps the complete"
        " corpus as structured JSON \u2014 facts, versions, signatures, audit events, user"
        " records \u2014 for migration or archival.",
    ),
    (
        "Signed S3 URLs expire after 24 hours",
        "Signed S3 URLs grant temporary access to a specific file without requiring the user to"
        " have AWS credentials. 24 hours is long enough to download but short enough to prevent"
        " link sharing.",
    ),

    # --- DATA LAYER ---
    (
        "Every table has a UUID primary key generated by gen_random_uuid",
        "gen_random_uuid() generates UUID v4 values at the database level, ensuring globally"
        " unique identifiers regardless of which application instance creates the row.",
    ),
    (
        "Every table has created_at TIMESTAMPTZ DEFAULT now",
        "TIMESTAMPTZ DEFAULT now() means every row automatically records its creation time in"
        " UTC. No application code needed to set the timestamp \u2014 it cannot be forgotten or"
        " faked.",
    ),
    (
        "MinIO provides S3-compatible object storage",
        "MinIO provides an S3-compatible API for local development. Code that uses the S3 SDK"
        " works identically against MinIO and AWS S3 \u2014 no environment-specific"
        " conditionals.",
    ),
    (
        "PostgreSQL 16 is the primary database",
        "PostgreSQL 16 provides advanced features used throughout artiFACT: JSONB columns,"
        " tsvector full-text search, gen_random_uuid(), CTEs, and window functions.",
    ),
    (
        "Redis provides session storage",
        "Redis session storage enables horizontal scaling \u2014 any web task can serve any"
        " user's request because the session lives in Redis, not in the web process's memory.",
    ),

    # --- DATA RETENTION ---
    (
        "Audit trail retention is 6 years",
        "Six-year audit trail retention aligns with NARA GRS 3.2 Item 031 for system access"
        " and security audit trails. Celery beat automates the cleanup after the retention"
        " period.",
    ),
    (
        "Fact version retention is 3 years after superseded",
        "Three-year retention per NARA GRS 5.2 Item 020. Old fact versions are kept 3 years"
        " after being superseded, then eligible for automated cleanup.",
    ),
    (
        "System config is deleted when superseded",
        "Per NARA GRS 3.1 Item 010, superseded configuration records have no retention"
        " requirement. When an admin updates a feature flag, the old value can be deleted"
        " immediately.",
    ),

    # --- DITPR REGISTRATION ---
    (
        "DITPR is located at ditpr.osd.mil",
        "DITPR = DoD IT Portfolio Repository. The authoritative registry of all DoD information"
        " systems, required by DoDI 8510.01 for any system seeking an Authority to Operate.",
    ),
    (
        "The classification is UNCLASSIFIED CUI",
        "CUI = Controlled Unclassified Information. The classification level determines which"
        " security controls apply and which hosting environments are authorized.",
    ),
    (
        "The cloud service provider is AWS GovCloud",
        "AWS GovCloud is an isolated AWS region designed for sensitive government workloads. It"
        " meets FedRAMP High and DoD IL-4/IL-5 requirements.",
    ),
    (
        "The hosting environment is COSMOS NIWC Pacific Cloud Service Center",
        "COSMOS NIWC Pacific = Cloud One SIPR/NIPR Management and Operations Services at Naval"
        " Information Warfare Center Pacific. A managed DoD cloud platform providing shared"
        " infrastructure and ATO boundary.",
    ),
    (
        "The impact level is IL-4",
        "IL-4 = Impact Level 4. Covers Controlled Unclassified Information in commercial cloud"
        " environments. Defined by the DoD Cloud Computing Security Requirements Guide.",
    ),
    (
        "The impact level is IL-5",
        "IL-5 = Impact Level 5. Covers CUI in DoD cloud and higher-sensitivity unclassified"
        " data. Requires dedicated government infrastructure like AWS GovCloud.",
    ),
    (
        "The system type is Major Application",
        "\"Major Application\" is a DITPR classification for IT systems that require an"
        " independent ATO assessment. It triggers specific documentation and oversight"
        " requirements.",
    ),

    # --- DOCUMENT GENERATION ---
    (
        "Generation progress is streamed via SSE",
        "SSE = Server-Sent Events. Progress updates stream to the browser in real time as each"
        " document section is generated \u2014 users see live status without polling.",
    ),
    (
        "Generation runs as a Celery background task",
        "Running generation as a Celery background task prevents HTTP timeouts. The web server"
        " returns immediately while the worker processes the AI calls, which can take 30+"
        " seconds.",
    ),
    (
        "The prefilter scores every published fact against all template sections simultaneously",
        "Prefilter scores every published fact against all template sections simultaneously"
        " using the LLM. This determines which facts belong in which document sections before"
        " any prose is generated.",
    ),
    (
        "The synthesizer generates prose for each section from the matched facts",
        "The synthesizer takes the prefilter's fact-to-section assignments and generates"
        " coherent prose. Separating this from prefilter lets users review which facts map to"
        " which sections before spending AI tokens.",
    ),
    (
        "The DOCX builder applies CUI markings when applicable",
        "CUI markings in generated documents are applied automatically based on the"
        " classification of included facts. Headers, footers, and cover pages carry the"
        " appropriate markings per DoDI 5200.48.",
    ),
    (
        "A views feature lets users run prefilter only",
        "Views show users which facts the AI would assign to each template section without"
        " generating prose. This preview saves AI token costs and lets users refine the corpus"
        " before committing to full generation.",
    ),
    (
        "The views feature shows which facts AI would assign per section",
        "The views feature is like a dry run: it shows the fact-to-section mapping from"
        " prefilter without running synthesis. Users can identify missing facts or"
        " misassignments before incurring AI costs.",
    ),

    # --- ENCRYPTION & DATA PROTECTION ---
    (
        "AI processing uses Amazon Bedrock in AWS GovCloud",
        "Amazon Bedrock in AWS GovCloud is authorized at IL-4/IL-5 for processing CUI data. AI"
        " operations stay within the authorization boundary.",
    ),
    (
        "All data at rest is encrypted using RDS AES-256",
        "AES-256 encryption at rest is a baseline requirement for CUI data per CNSS Policy 15."
        " RDS provides this transparently \u2014 no application-level encryption needed for"
        " database rows.",
    ),
    (
        "All data in transit uses TLS 1.2 or higher",
        "TLS 1.2+ encrypts all data in transit between clients, services, and databases. Older"
        " TLS versions are disabled as required by NIST SP 800-52 Rev 2.",
    ),

    # --- EXTERNAL DATA SHARING ---
    (
        "Sync API access requires an authenticated service account",
        "Service accounts authenticate with scoped API keys \u2014 not user sessions. Each key"
        " has explicit permissions (read, sync) and can be revoked independently.",
    ),
    (
        "The Advana sync API includes display names and roles",
        "The sync API includes display names and roles for attribution (who approved what) but"
        " excludes EDIPI and email to follow minimum necessary disclosure principles.",
    ),

    # --- EXTERNAL INTEGRATIONS ---
    (
        "Advana Apigee gateway discovers the OpenAPI spec automatically",
        "Apigee is Google's API gateway product used by Advana/Jupiter. It auto-discovers"
        " artiFACT's OpenAPI spec for routing, authentication, and rate limiting at the"
        " gateway level.",
    ),
    (
        "The Advana delta feed endpoint is GET api v1 sync changes",
        "The delta feed endpoint returns only events newer than the consumer's cursor position."
        " Advana polls this to stay current without re-downloading the entire corpus each time.",
    ),
    (
        "The delta feed uses a monotonic seq cursor",
        "A monotonic seq cursor only increases \u2014 no two events share the same value."
        " Unlike timestamps, it guarantees strict ordering without clock skew issues.",
    ),
    (
        "The delta feed uses BIGINT seq not timestamps",
        "BIGINT seq avoids the problems of timestamp-based cursors: clock skew,"
        " sub-millisecond event collisions, and timezone ambiguity. Each event gets a unique,"
        " ordered integer.",
    ),
    (
        "The OpenAPI 3.0 spec is auto-generated at api v1 openapi.json",
        "OpenAPI 3.0 spec auto-generation means the API documentation updates every time a"
        " route changes. External consumers always have an accurate, machine-readable"
        " contract.",
    ),

    # --- FACT LIFECYCLE ---
    (
        "A fact is created with an initial version in proposed state",
        "The initial version starts in \"proposed\" state and enters the approval queue."
        " Contributors cannot bypass the review process \u2014 all new content requires"
        " approver sign-off.",
    ),
    (
        "Approvers can create facts directly in published state",
        "Approvers can bypass the proposal queue when creating facts directly. This streamlines"
        " bulk data entry during initial corpus population.",
    ),
    (
        "Facts can be retired",
        "Retiring a fact removes it from the active corpus without deleting it. The fact and"
        " its history remain in the database for retention compliance and audit purposes.",
    ),
    (
        "Published facts can be signed by a signatory",
        "Signing is an official attestation by a signatory that the published fact is accurate"
        " and authoritative. It's the highest level of endorsement in the approval hierarchy.",
    ),
    (
        "Retired facts can be unretired by an approver",
        "Unretiring restores a fact to the active corpus. Only an approver or higher can"
        " unretire, ensuring retired facts don't accidentally re-enter the corpus without"
        " review.",
    ),

    # --- FRONTEND ---
    (
        "Alpine.js provides client-side interactivity",
        "Alpine.js is a lightweight JavaScript framework (~15KB) for client-side interactivity."
        " It handles dropdowns, modals, and form validation without the complexity of React or"
        " Vue.",
    ),
    (
        "HTMX provides dynamic updates without page reloads",
        "HTMX enables dynamic updates by swapping HTML fragments from the server. No JSON API"
        " layer needed \u2014 the server renders the final HTML and HTMX puts it on the page.",
    ),
    (
        "Jinja2 autoescape is enabled",
        "Jinja2 autoescape converts special characters like < and > into safe HTML entities"
        " automatically. This prevents XSS (Cross-Site Scripting) attacks without requiring"
        " developers to remember to escape each value.",
    ),
    (
        "Tailwind CSS CDN provides utility-first styling",
        "Tailwind CSS CDN means zero build step for styles. Utility classes are applied directly"
        " in HTML templates \u2014 no separate CSS files to maintain or compile.",
    ),
    (
        "The frontend requires zero build step",
        "Zero build step means no webpack, no npm, no node_modules. The frontend ships as plain"
        " HTML templates, CDN-loaded CSS/JS, and Jinja2 server-side rendering.",
    ),
    (
        "The frontend uses server-rendered HTML via Jinja2",
        "Server-rendered HTML via Jinja2 means the server does all the work \u2014 the browser"
        " receives complete HTML pages. No client-side JavaScript framework required for"
        " rendering.",
    ),
    (
        "There is zero npm",
        "Zero npm eliminates the node_modules dependency tree \u2014 often 500MB+ of transitive"
        " dependencies with potential supply chain vulnerabilities. The frontend uses only"
        " CDN-loaded libraries.",
    ),
    (
        "There is zero webpack",
        "Webpack is a JavaScript module bundler typically required for React/Vue apps."
        " artiFACT's server-rendered architecture eliminates the need for any JavaScript build"
        " pipeline.",
    ),
    (
        "CSS variables in theme.css provide three theme modes",
        "CSS variables in theme.css enable runtime theme switching without reloading. Three"
        " modes support different user preferences and accessibility needs.",
    ),

    # --- GRACEFUL DEGRADATION ---
    (
        "When Redis is down the badge counter returns negative one",
        "Returning -1 signals to the UI that the actual count is unavailable. The UI renders a"
        " dash instead of a number, rather than showing a stale cached value or erroring out.",
    ),
    (
        "When Redis is down the rate limiter logs a warning",
        "Logging a warning when Redis is down (rather than blocking requests) is intentional"
        " fail-open behavior. Rate limiting is defense-in-depth, not a primary security"
        " control.",
    ),

    # --- IMPORT ANALYSIS ---
    (
        "Analysis runs as a Celery background task",
        "Running analysis as a Celery background task prevents HTTP timeouts. AI-powered"
        " document parsing can take minutes for large files \u2014 the user sees real-time"
        " progress via SSE.",
    ),
    (
        "Extracted facts are staged for human review before proposal",
        "AI-extracted facts are staged, not auto-published. A human reviews each one before it"
        " enters the proposal queue \u2014 maintaining the same four-eyes review standard as"
        " manually created facts.",
    ),
    (
        "Users can upload DOCX documents for AI-powered fact extraction",
        "Document import is the on-ramp from traditional Word-based acquisition documentation."
        " Users upload existing artifacts and the AI extracts atomic facts for review and"
        " approval.",
    ),

    # --- INFRASTRUCTURE ---
    (
        "Docker Compose manages the local development stack",
        "Docker Compose defines the complete local development stack: web, worker, postgres,"
        " redis, minio, nginx, and certbot. One command (docker compose up) starts everything.",
    ),
    (
        "Terraform manages infrastructure as code",
        "Terraform = Infrastructure as Code tool. Every cloud resource (ECS tasks, RDS"
        " instances, S3 buckets, IAM roles) is defined in declarative .tf files. The production"
        " environment can be recreated from scratch.",
    ),
    (
        "The production target is AWS GovCloud",
        "AWS GovCloud is an isolated AWS region designed for sensitive government workloads. It"
        " meets FedRAMP High and DoD IL-4/IL-5 requirements for CUI data handling.",
    ),

    # --- KERNEL SERVICES ---
    (
        "All shared code lives in the kernel",
        "The kernel is the only code that can be imported across module boundaries. Shared"
        " concerns like auth, permissions, events, and database sessions live here to prevent"
        " cross-module coupling.",
    ),
    (
        "Modules never import from each other",
        "No inter-module imports is the fundamental architectural constraint. If module A needs"
        " data from module B, it reads the shared database \u2014 never imports B's internal"
        " code.",
    ),
    (
        "The kernel is the only shared import allowed across modules",
        "Making the kernel the sole shared import creates a clear dependency graph: modules"
        " depend on kernel, kernel depends on nothing. This prevents circular dependencies and"
        " keeps modules independently testable.",
    ),

    # --- MODULE COMMUNICATION ---
    (
        "Cross-module reads go through the database",
        "Reading through the database prevents tight coupling. Module A doesn't need to know"
        " module B's internal API \u2014 it queries the shared data model via SQLAlchemy.",
    ),
    (
        "Cross-module writes go through the kernel event bus",
        "Writes go through the event bus so that side effects (audit logging, cache"
        " invalidation, badge updates) happen automatically. The writing module doesn't need to"
        " know who reacts to its events.",
    ),

    # --- MONITORING & LOGGING ---
    (
        "Health check endpoints report database connectivity status",
        "Health check endpoints verify that the application can actually reach its"
        " dependencies \u2014 not just that the process is running. A healthy response means"
        " database, Redis, and S3 are all reachable.",
    ),
    (
        "Structured JSON logs via structlog forward to CloudWatch",
        "CloudWatch is AWS's centralized logging service. Structured JSON logs from structlog"
        " are machine-parseable, enabling queries like \"show all errors in the signing module"
        " in the last hour.\"",
    ),

    # --- OWASP ZAP RESULTS ---
    (
        "HIGH findings must be resolved before deployment",
        "HIGH findings indicate vulnerabilities that could be exploited remotely with"
        " significant impact. These are deployment blockers \u2014 no exceptions.",
    ),
    (
        "MEDIUM findings must be resolved before deployment",
        "MEDIUM findings are tracked and remediated on a risk-based timeline. They indicate"
        " real vulnerabilities but with limited exploitability or impact.",
    ),

    # --- PERMISSION MODEL ---
    (
        "Grants cascade to all descendant nodes in the taxonomy",
        "Grant cascading means a permission on a parent node automatically applies to all"
        " children. Granting \"approver\" on \"Architecture & Design\" gives approval rights on"
        " every child node beneath it.",
    ),
    (
        "Permission resolution checks the node and all ancestors up to root",
        "Ancestor-walking permission resolution means the system checks the current node, then"
        " its parent, then grandparent, up to root. The first matching grant determines the"
        " user's effective role.",
    ),
    (
        "The permission cache is invalidated on grant events",
        "Cache invalidation on grant events ensures new permissions take effect promptly."
        " Without this, a newly granted user would wait up to 5 minutes (the cache TTL) before"
        " their access works.",
    ),

    # --- PII INVENTORY ---
    (
        "Admins can view the user list with name email and role",
        "Admin-only user list visibility follows least-privilege principles. Non-admins see"
        " display names only on approval and signature records where attribution is"
        " operationally necessary.",
    ),
    (
        "No user can see another users EDIPI",
        "EDIPI = Electronic Data Interchange Personal Identifier. Concealing it from other"
        " users prevents cross-system identity correlation without authorization.",
    ),

    # --- PILLAR 1 — USER IDENTITY ---
    (
        "Anomaly detection triggers force re-authentication",
        "Anomaly detection triggers (export floods, off-hours bulk access, scope escalation)"
        " force the user to re-authenticate via CAC. This ensures a compromised session cannot"
        " continue operating.",
    ),
    (
        "CAC multi-factor authentication is provided via COSMOS SAML",
        "CAC = Common Access Card. SAML = Security Assertion Markup Language. COSMOS handles"
        " the CAC validation and passes the verified identity to artiFACT via a signed SAML"
        " assertion.",
    ),

    # --- PILLAR 5 — DATA ---
    (
        "AI keys are encrypted with AES-256-GCM",
        "AES-256-GCM provides both encryption (confidentiality) and authentication (tamper"
        " detection) in one operation. The 256-bit key length meets CNSS Policy 15"
        " requirements.",
    ),
    (
        "Supported classification values are UNCLASSIFIED CUI and CONFIDENTIAL",
        "These three classification levels cover all data artiFACT handles. UNCLASSIFIED is the"
        " default. CUI requires safeguarding per 32 CFR Part 2002. CONFIDENTIAL is the lowest"
        " classification level.",
    ),
    (
        "The encryption master key is stored in AWS Secrets Manager",
        "AWS Secrets Manager provides hardware-backed storage, automatic rotation, and"
        " IAM-controlled access. The master key is fetched at runtime and held only in memory.",
    ),

    # --- PILLAR 6 — VISIBILITY ---
    (
        "Anomaly detection monitors for AI corpus mining",
        "AI corpus mining is a data exfiltration technique where a user uses iterative AI"
        " queries to gradually extract the entire fact corpus. The anomaly detector tracks"
        " query patterns to detect this.",
    ),
    (
        "Structured JSON logs are produced via structlog",
        "structlog produces structured JSON log entries with key-value fields."
        " Machine-parseable logs enable CloudWatch Insights queries and Grafana dashboards"
        " without regex-based parsing.",
    ),
    (
        "Logs forward to CloudWatch",
        "CloudWatch is AWS's centralized log aggregation and monitoring service. Forwarding"
        " logs there enables alerting, querying, and long-term retention outside the"
        " application.",
    ),
    (
        "Grafana dashboards visualize active user count",
        "Grafana is an open-source visualization platform. Dashboards for active users, AI"
        " cost, error rates, latency, and request rates provide real-time operational"
        " visibility.",
    ),
    (
        "fc_event_log records every mutation",
        "fc_event_log is the immutable audit trail. Every create, update, delete, approve,"
        " sign, and permission change is recorded with actor, entity, and timestamp.",
    ),

    # --- PROGRAM OVERVIEW ---
    (
        "artiFACT decomposes traditional acquisition documents into atomic facts",
        "Traditional acquisition documents contain overlapping content \u2014 the same fact"
        " about a system's architecture might appear in 10 different artifacts. artiFACT stores"
        " it once and assembles it into any required format.",
    ),
    (
        "artiFACT is a taxonomy-driven atomic fact corpus platform",
        "A taxonomy is a hierarchical classification system. artiFACT organizes facts into a"
        " tree structure \u2014 programs at the top, branches for topic areas, leaves for"
        " specific subjects.",
    ),
    (
        "artiFACT replaces 71 engineering artifacts with a single source of truth",
        "71 engineering artifacts include documents like the System Engineering Plan, Test and"
        " Evaluation Master Plan, Software Development Plan, and dozens more. Many contain 30%+"
        " overlapping content.",
    ),
    (
        "Documents are generated on demand from the current corpus",
        "On-demand generation from the current corpus guarantees every document reflects the"
        " latest approved facts. No stale versions, no manual sync between documents.",
    ),
    (
        "The system provides AI-assisted document generation",
        "AI-assisted document generation uses a two-pass approach: prefilter assigns facts to"
        " template sections, then synthesis generates prose. Users preview assignments before"
        " spending AI tokens.",
    ),
    (
        "Those 71 artifacts carry over 30 percent duplicative content",
        "30%+ duplication means updating a single fact requires finding and updating it in"
        " dozens of documents. artiFACT eliminates this by storing each fact exactly once.",
    ),

    # --- RECORDS RETENTION ---
    (
        "Approval decisions follow NARA GRS 5.2 Item 020 with 3-year retention",
        "NARA = National Archives and Records Administration. GRS = General Records Schedule."
        " 5.2/020 covers transitory records superseded by new versions \u2014 3-year retention"
        " after supersession.",
    ),
    (
        "User feedback follows NARA GRS 5.7 Item 010 with 1-year retention after resolved",
        "NARA GRS 5.7/010 covers miscellaneous communications including user feedback. Destroy"
        " 1 year after resolution \u2014 Celery beat automates the cleanup.",
    ),

    # --- REST CONVENTIONS ---
    (
        "All endpoints are under the api v1 prefix",
        "The /api/v1 prefix enables API versioning. If a breaking change is needed, a /api/v2"
        " can be introduced while v1 continues serving existing clients.",
    ),
    (
        "CSRF tokens are passed via the X-CSRF-Token header",
        "CSRF = Cross-Site Request Forgery. The X-CSRF-Token header proves the request came"
        " from artiFACT's own pages, not a malicious third-party site.",
    ),
    (
        "Error responses follow the format detail message code error_code",
        "A consistent error format means client code has one pattern for handling all errors"
        " \u2014 parse detail, message, and error_code regardless of which endpoint returned"
        " the error.",
    ),
    (
        "Responses follow the format data array total offset limit",
        "Consistent response envelopes (data, total, offset, limit) enable generic pagination"
        " handling on the client. Every list endpoint returns the same structure.",
    ),
    (
        "The API uses RESTful nouns not verbs",
        "RESTful nouns (e.g., /api/v1/facts, /api/v1/nodes) follow HTTP semantics: GET reads,"
        " POST creates, PUT updates, DELETE removes. No verb-based endpoints like"
        " /api/v1/createFact.",
    ),

    # --- ROLE HIERARCHY ---
    (
        "A higher role inherits all capabilities of lower roles on the same node",
        "Role inheritance means a signatory automatically has all approver, subapprover,"
        " contributor, and viewer capabilities. No need to grant multiple roles \u2014 one"
        " grant covers everything below it.",
    ),
    (
        "Node-level roles are signatory approver subapprover contributor and viewer",
        "Five node-level roles provide fine-grained access control. A signatory can attest, an"
        " approver can publish, a subapprover helps review, a contributor can propose, and a"
        " viewer can read.",
    ),

    # --- SIGNING WORKFLOW ---
    (
        "A signature record can have an optional expiration",
        "Signature expiration supports scenarios where facts require periodic re-attestation."
        " If a signature expires, the signatory must re-sign to confirm the facts are still"
        " accurate.",
    ),
    (
        "A signature record is created with fact count",
        "Recording fact_count at signing time provides an audit trail of exactly how many facts"
        " were attested. If facts are later added, the signature's scope is clear.",
    ),

    # --- STAKEHOLDERS ---
    (
        "Advana consumes data via the delta feed API",
        "Advana = Advanced Analytics platform. DoD's enterprise data and analytics environment."
        " It consumes artiFACT data via the delta feed for cross-program analytics.",
    ),
    (
        "artiFACT is accessible on commercial internet",
        "Commercial internet accessibility (via COSMOS CNAP) means users don't need to be on a"
        " military network. Any CAC-enabled browser on a CNAP-enrolled device can reach"
        " artiFACT.",
    ),

    # --- SYSTEM TABLES ---
    (
        "fc_ai_usage tracks estimated costs per user per AI action",
        "fc_ai_usage enables per-user cost attribution under the BYOK model. Each organization"
        " can see exactly how much their users spend on AI features.",
    ),
    (
        "fc_document_template stores semantic document templates",
        "Semantic document templates define the structure of acquisition documents \u2014"
        " sections with prompts and guidance. The AI uses these to map facts to the correct"
        " document sections.",
    ),
    (
        "fc_system_config stores feature flags as key-value JSONB",
        "JSONB feature flags enable runtime capability toggling. An admin can disable AI chat,"
        " document generation, or any feature instantly without redeploying the application.",
    ),
    (
        "fc_system_config stores rate limit configuration as key-value JSONB",
        "Rate limit configuration in fc_system_config allows admins to adjust per-user request"
        " limits without code changes. Stored as JSONB for flexible schema.",
    ),
    (
        "fc_user_preference stores per-user settings as key-value JSONB",
        "Per-user preferences (theme, default node, notification settings) are stored as"
        " flexible JSONB. New preferences can be added without schema migrations.",
    ),

    # --- WORKFLOW TABLES ---
    (
        "fc_fact_comment supports challenges and resolutions",
        "Challenges are formal disagreements with a fact's content. The challenge/resolution"
        " workflow provides a structured review process \u2014 not just comments, but tracked"
        " disputes with resolution states.",
    ),
    (
        "fc_fact_comment supports threaded comments on fact versions",
        "Threaded comments on fact versions enable contextual discussion. parent_comment_uid"
        " creates reply chains so conversations stay organized and traceable.",
    ),
    (
        "fc_import_session tracks document upload and AI analysis progress",
        "fc_import_session tracks the lifecycle of a document upload: file received, AI analysis"
        " in progress, facts extracted, human review pending. SSE streams progress to the user"
        " in real time.",
    ),
    (
        "fc_signature records batch signing operations per node",
        "fc_signature records batch signing operations per taxonomy node. A signatory signs all"
        " published facts under a node in one operation \u2014 the record captures who signed,"
        " when, and the fact count.",
    ),

    # --- MISSION NEED ---
    (
        "A typical DoD acquisition program has 71 engineering artifacts",
        "These 71 artifacts span the full acquisition lifecycle: requirements, design, test,"
        " deployment, sustainment, and retirement. Many share 30%+ overlapping content.",
    ),
    (
        "The system addresses the DON need for authoritative atomic data",
        "DON = Department of the Navy (Navy + Marine Corps). \"Authoritative atomic data\" means"
        " each fact is the single approved source \u2014 no conflicting versions in different"
        " documents.",
    ),
    (
        "When a single fact changes a human must manually find every document containing"
        " that fact",
        "This is the core problem artiFACT solves. A single fact change triggers a manual hunt"
        " through dozens of documents \u2014 error-prone, time-consuming, and often incomplete.",
    ),
    (
        "Users can continue using Word documents while gradually building their corpus",
        "artiFACT's import feature lets users upload existing Word documents and extract facts"
        " from them. Teams can transition gradually without disrupting current workflows.",
    ),
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


async def _seed_corpus_comments(db: AsyncSession) -> int:
    """Create contextual comments on published fact versions. Returns count created."""
    created = 0

    for sentence, comment_body in FACT_COMMENTS:
        # Find the published version by sentence text
        result = await db.execute(
            select(FcFactVersion).where(FcFactVersion.display_sentence == sentence)
        )
        version = result.scalar_one_or_none()
        if version is None:
            log.warning("comment_version_not_found", sentence=sentence[:60])
            continue

        # Idempotent: skip if comment with same body already exists on this version
        result = await db.execute(
            select(FcFactComment).where(
                FcFactComment.version_uid == version.version_uid,
                FcFactComment.body == comment_body,
            )
        )
        if result.scalar_one_or_none():
            continue

        comment = FcFactComment(
            comment_uid=uuid.uuid4(),
            version_uid=version.version_uid,
            comment_type="comment",
            body=comment_body,
            created_by_uid=JALLRED_UID,
        )
        db.add(comment)
        created += 1

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

            comment_count = await _seed_corpus_comments(db)
            log.info("comments_created", count=comment_count)

    await engine.dispose()

    log.info(
        "artifact_corpus_seed_complete",
        nodes=len(TAXONOMY),
        facts_defined=len(FACTS),
        facts_created=fact_count,
        templates=tmpl_count,
        comments_defined=len(FACT_COMMENTS),
        comments_created=comment_count,
    )


if __name__ == "__main__":
    asyncio.run(run_seed())
