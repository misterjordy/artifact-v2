"""Seed data for Sprint 9: artiFACT taxonomy + ConOps/SDD templates."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from artiFACT.kernel.config import settings
from artiFACT.kernel.models import FcDocumentTemplate, FcNode

ARTIFACT_TAXONOMY = [
    "System Overview",
    "Architecture & Design",
    "Security Controls",
    "Data & Privacy",
    "User Roles & Permissions",
    "AI Integration",
    "Operations & Sustainment",
    "Compliance & Authorization",
]

CONOPS_SECTIONS = [
    {
        "key": "purpose",
        "title": "1. Purpose",
        "prompt": "Describe the system's purpose and the operational need it addresses",
        "guidance": "Focus on: what problem does the system solve, who uses it, why existing tools are insufficient",
    },
    {
        "key": "system_overview",
        "title": "2. System Overview",
        "prompt": "Describe the system at a high level — what it does, how users interact with it",
        "guidance": "Focus on: capabilities, user experience, key workflows",
    },
    {
        "key": "operational_context",
        "title": "3. Operational Context",
        "prompt": "Describe where and how the system operates within the DON enterprise",
        "guidance": "Focus on: hosting environment, network access, organizational relationships",
    },
    {
        "key": "user_roles",
        "title": "4. User Roles and Responsibilities",
        "prompt": "Describe who uses the system and what each role can do",
        "guidance": "Focus on: role hierarchy, permission model, typical user workflows",
    },
    {
        "key": "data_flows",
        "title": "5. Data Flows",
        "prompt": "Describe how data moves through the system",
        "guidance": "Focus on: data sources, processing, storage, outputs, external integrations",
    },
    {
        "key": "security",
        "title": "6. Security Considerations",
        "prompt": "Describe the security posture and compliance framework",
        "guidance": "Focus on: Zero Trust, CAC auth, encryption, CUI handling, ATO status",
    },
]

SDD_SECTIONS = [
    {
        "key": "architecture",
        "title": "1. Architecture Overview",
        "prompt": "Describe the system architecture, technology stack, and design patterns",
        "guidance": "Focus on: modular monolith, bounded contexts, API-first, container deployment",
    },
    {
        "key": "data_design",
        "title": "2. Data Design",
        "prompt": "Describe the database schema, data model, and storage strategy",
        "guidance": "Focus on: PostgreSQL tables, relationships, JSONB patterns, S3 usage",
    },
    {
        "key": "interface_design",
        "title": "3. Interface Design",
        "prompt": "Describe the API design, authentication, and external integrations",
        "guidance": "Focus on: REST endpoints, OpenAPI spec, Advana sync, SAML/CAC",
    },
    {
        "key": "security_design",
        "title": "4. Security Design",
        "prompt": "Describe the security architecture in detail",
        "guidance": "Focus on: RBAC, CSRF, encryption, ZT pillars, FIPS, audit logging",
    },
    {
        "key": "deployment",
        "title": "5. Deployment Architecture",
        "prompt": "Describe how the system is deployed, scaled, and maintained",
        "guidance": "Focus on: Docker, ECS Fargate, RDS, Redis, CI/CD pipeline, blue/green",
    },
    {
        "key": "testing",
        "title": "6. Test Strategy",
        "prompt": "Describe the testing approach",
        "guidance": "Focus on: test pyramid, coverage targets, CI enforcement, E2E tests",
    },
]


async def seed_templates(db: AsyncSession) -> None:
    """Seed ConOps and SDD document templates if they don't exist."""
    # Check if already seeded
    result = await db.execute(
        select(FcDocumentTemplate).where(FcDocumentTemplate.abbreviation == "ConOps")
    )
    if result.scalar_one_or_none():
        print("Templates already seeded, skipping.")
        return

    conops = FcDocumentTemplate(
        name="Concept of Operations",
        abbreviation="ConOps",
        description="Describes the system's purpose, users, and operational context.",
        sections=CONOPS_SECTIONS,
    )
    sdd = FcDocumentTemplate(
        name="System Design Document",
        abbreviation="SDD",
        description="Describes the system architecture, data design, and deployment strategy.",
        sections=SDD_SECTIONS,
    )
    db.add_all([conops, sdd])
    await db.flush()
    print(f"Seeded ConOps template: {conops.template_uid}")
    print(f"Seeded SDD template: {sdd.template_uid}")


async def seed_taxonomy(db: AsyncSession) -> None:
    """Seed the artiFACT program taxonomy if it doesn't exist."""
    result = await db.execute(
        select(FcNode).where(FcNode.title == "artiFACT", FcNode.node_depth == 0)
    )
    if result.scalar_one_or_none():
        print("artiFACT taxonomy already seeded, skipping.")
        return

    trunk = FcNode(
        title="artiFACT",
        slug="artifact",
        node_depth=0,
        sort_order=0,
    )
    db.add(trunk)
    await db.flush()
    print(f"Seeded trunk: {trunk.node_uid}")

    for i, branch_name in enumerate(ARTIFACT_TAXONOMY):
        slug = branch_name.lower().replace(" & ", "-").replace(" ", "-")
        branch = FcNode(
            parent_node_uid=trunk.node_uid,
            title=branch_name,
            slug=slug,
            node_depth=1,
            sort_order=i,
        )
        db.add(branch)
    await db.flush()
    print(f"Seeded {len(ARTIFACT_TAXONOMY)} taxonomy branches.")


async def run_seed() -> None:
    """Run all Sprint 9 seed operations."""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        async with db.begin():
            await seed_taxonomy(db)
            await seed_templates(db)
        await db.commit()

    await engine.dispose()
    print("Sprint 9 seed complete.")


if __name__ == "__main__":
    asyncio.run(run_seed())
