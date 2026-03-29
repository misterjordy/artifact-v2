"""Seed script for Sprint 3: artiFACT self-documenting program + playground programs."""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.db import async_session
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── artiFACT self-documenting facts ──────────────────────────────────────

ARTIFACT_CHILDREN = {
    "System Overview": [
        "artiFACT is a web-based fact management system for DoD acquisition programs.",
        "The system enables programs to capture, version, and govern atomic facts.",
        "artiFACT replaces manual document authoring with structured fact-based generation.",
        "The platform supports multiple concurrent programs in a single deployment.",
        "Users authenticate via CAC (Common Access Card) with SAML 2.0 integration.",
        "The system is designed for IL-4 (Impact Level 4) deployment environments.",
        "artiFACT provides REST APIs for integration with Advana and Jupiter platforms.",
    ],
    "Architecture & Design": [
        "artiFACT uses a three-tier architecture: FastAPI backend, PostgreSQL database, Redis cache.",
        "The backend is built with Python 3.12+ and FastAPI with async/await throughout.",
        "SQLAlchemy 2.0 with asyncpg provides the async ORM and database access layer.",
        "The frontend uses server-rendered HTML with HTMX for dynamic updates.",
        "Alpine.js provides client-side interactivity without a build step.",
        "Tailwind CSS via CDN provides utility-first styling with CSS variable theming.",
        "The codebase follows a modular architecture with kernel and module boundaries.",
        "Each module has router, service, schemas, and tests as separate components.",
        "The event bus enables decoupled communication between modules.",
        "Redis provides session management, permission caching, and rate limiting.",
    ],
    "Security Controls": [
        "All state-changing requests require CSRF token validation via X-CSRF-Token header.",
        "Sessions are stored in Redis with 8-hour TTL and 15-minute re-validation windows.",
        "API keys use SHA-256 hashing and support scoped access with expiration.",
        "AI provider keys are encrypted at rest using AES-256-GCM before database storage.",
        "Rate limiting uses Redis INCR with EXPIRE to prevent abuse without table growth.",
        "The undo system computes reverse_payload server-side only — never from client input.",
        "No public endpoint accepts arbitrary reverse_payload to prevent injection attacks.",
        "Jinja2 templates use autoescape=True by default to prevent XSS vulnerabilities.",
    ],
    "Data & Privacy": [
        "All database tables use UUID primary keys generated server-side.",
        "Timestamps use TIMESTAMPTZ to ensure timezone-aware storage.",
        "JSON columns use JSONB type for efficient indexing and querying.",
        "Fact versions are immutable — edits create new versions with supersedes links.",
        "Soft-delete patterns use is_retired/is_archived flags with partial indexes.",
        "The event log provides a complete audit trail of all system mutations.",
        "Full-text search uses PostgreSQL tsvector with GIN indexing.",
    ],
    "User Roles & Permissions": [
        "The system implements a six-tier role hierarchy: viewer, contributor, subapprover, approver, signatory, admin.",
        "Permissions cascade through the taxonomy tree from parent to child nodes.",
        "Node-level permission grants override global roles when more permissive.",
        "Permission resolution checks Redis cache before querying the database.",
        "Contributors can create facts in proposed state within their assigned nodes.",
        "Approvers can publish, retire, and reassign facts within their scope.",
        "Signatories can digitally sign published fact versions.",
        "Admins have unrestricted access across all nodes and operations.",
    ],
    "AI Integration": [
        "artiFACT integrates with OpenAI, Anthropic, Azure OpenAI, and AWS Bedrock.",
        "Each user manages their own AI API keys encrypted with AES-256-GCM.",
        "AI usage is tracked per-user with input/output token counts and cost estimates.",
        "Document generation uses AI to match facts to document section templates.",
        "AI chat provides contextual assistance for fact creation and editing.",
        "The import analyzer uses AI to extract atomic facts from uploaded documents.",
    ],
    "Operations & Sustainment": [
        "Docker Compose provides the local development environment with all services.",
        "Health check endpoints verify service availability at /api/v1/health.",
        "Structured logging via structlog provides consistent log formatting.",
        "Celery with Redis broker handles background task processing.",
        "MinIO provides S3-compatible object storage for document uploads.",
        "Database migrations use Alembic for version-controlled schema changes.",
    ],
    "Compliance & Authorization": [
        "artiFACT is designed to support FedRAMP Moderate authorization requirements.",
        "Audit logs capture who did what, when, and provide undo capability.",
        "The delta feed API enables Advana integration via Apigee data mesh.",
        "Classification markings are tracked at the fact version level.",
        "The system supports NIST 800-53 control family requirements for access control.",
    ],
}

BOATWING_FACTS = {
    "System Overview": [
        "Boatwing is a maritime vessel tracking and maintenance scheduling system.",
        "The system tracks fleet readiness status across multiple naval installations.",
        "Boatwing integrates with NAVSEA maintenance databases for work order management.",
    ],
    "Compliance": [
        "Boatwing operates at IL-5 within the Navy Marine Corps Intranet (NMCI).",
        "All maintenance records are retained for 7 years per SECNAV instruction.",
    ],
}

SNIPEB_FACTS = {
    "System Overview": [
        "SNIPE-B is a ballistics calculation and environmental sensing platform.",
        "The system provides real-time wind and atmospheric data to fire control systems.",
        "SNIPE-B supports both standalone and networked operational modes.",
    ],
    "Architecture": [
        "SNIPE-B uses an embedded Linux runtime with real-time scheduling.",
        "Sensor data is transmitted via MIL-STD-1553 data bus to fire control.",
    ],
}


async def _seed_program(
    db: AsyncSession,
    program_name: str,
    children_facts: dict[str, list[str]],
    admin: FcUser,
) -> None:
    """Create a program root node, children, and seed facts."""
    slug = program_name.lower().replace(" ", "-").replace("&", "and")
    root = FcNode(
        node_uid=uuid.uuid4(),
        title=program_name,
        slug=slug,
        node_depth=0,
        created_by_uid=admin.user_uid,
    )
    db.add(root)
    await db.flush()
    print(f"  Created root: {program_name} ({root.node_uid})")

    for child_title, sentences in children_facts.items():
        child_slug = child_title.lower().replace(" ", "-").replace("&", "and")
        child = FcNode(
            node_uid=uuid.uuid4(),
            parent_node_uid=root.node_uid,
            title=child_title,
            slug=child_slug,
            node_depth=1,
            created_by_uid=admin.user_uid,
        )
        db.add(child)
        await db.flush()

        for sentence in sentences:
            fact = FcFact(
                fact_uid=uuid.uuid4(),
                node_uid=child.node_uid,
                created_by_uid=admin.user_uid,
            )
            db.add(fact)
            await db.flush()

            version = FcFactVersion(
                version_uid=uuid.uuid4(),
                fact_uid=fact.fact_uid,
                display_sentence=sentence,
                state="published",
                created_by_uid=admin.user_uid,
                published_at=_utcnow(),
                classification="UNCLASSIFIED",
            )
            fact.current_published_version_uid = version.version_uid
            db.add(version)

        await db.flush()
        print(f"    {child_title}: {len(sentences)} facts")


async def seed() -> None:
    """Run the full seed operation."""
    async with async_session() as db:
        async with db.begin():
            # Find or create admin user
            result = await db.execute(select(FcUser).where(FcUser.global_role == "admin").limit(1))
            admin = result.scalar_one_or_none()
            if not admin:
                admin = FcUser(
                    user_uid=uuid.uuid4(),
                    cac_dn="CN=Seed Admin",
                    display_name="Seed Admin",
                    global_role="admin",
                )
                db.add(admin)
                await db.flush()
                print(f"Created admin user: {admin.display_name}")

            print("\nSeeding artiFACT self-documenting program...")
            await _seed_program(db, "artiFACT", ARTIFACT_CHILDREN, admin)

            print("\nSeeding Boatwing playground program...")
            await _seed_program(db, "Boatwing", BOATWING_FACTS, admin)

            print("\nSeeding SNIPE-B playground program...")
            await _seed_program(db, "SNIPE-B", SNIPEB_FACTS, admin)

        total = sum(len(v) for v in ARTIFACT_CHILDREN.values())
        total += sum(len(v) for v in BOATWING_FACTS.values())
        total += sum(len(v) for v in SNIPEB_FACTS.values())
        print(f"\nDone. Total facts seeded: {total}")


if __name__ == "__main__":
    asyncio.run(seed())
