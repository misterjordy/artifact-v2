"""CRUD operations for fc_document_template."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import NotFound
from artiFACT.kernel.models import FcDocumentTemplate, FcUser


async def list_templates(db: AsyncSession, active_only: bool = True) -> list[FcDocumentTemplate]:
    """List all templates, optionally filtered to active only."""
    stmt = select(FcDocumentTemplate).order_by(FcDocumentTemplate.name)
    if active_only:
        stmt = stmt.where(FcDocumentTemplate.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_template(db: AsyncSession, template_uid: uuid.UUID) -> FcDocumentTemplate:
    """Get a single template by UID."""
    tpl = await db.get(FcDocumentTemplate, template_uid)
    if not tpl:
        raise NotFound("Template not found", code="TEMPLATE_NOT_FOUND")
    return tpl


async def create_template(
    db: AsyncSession,
    name: str,
    abbreviation: str,
    sections: list[dict],
    actor: FcUser,
    description: str | None = None,
) -> FcDocumentTemplate:
    """Create a new document template."""
    tpl = FcDocumentTemplate(
        name=name,
        abbreviation=abbreviation,
        description=description,
        sections=sections,
        created_by_uid=actor.user_uid,
    )
    db.add(tpl)
    await db.flush()
    return tpl


async def update_template(
    db: AsyncSession,
    template_uid: uuid.UUID,
    updates: dict,
) -> FcDocumentTemplate:
    """Update an existing template."""
    tpl = await get_template(db, template_uid)
    for key, val in updates.items():
        if val is not None:
            setattr(tpl, key, val)
    await db.flush()
    await db.refresh(tpl)
    return tpl


async def delete_template(db: AsyncSession, template_uid: uuid.UUID) -> None:
    """Soft-delete a template by marking it inactive."""
    tpl = await get_template(db, template_uid)
    tpl.is_active = False
    await db.flush()
