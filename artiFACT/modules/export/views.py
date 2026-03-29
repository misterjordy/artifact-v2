"""Views feature: run prefilter only to preview fact→section assignments."""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.modules.export.docgen.prefilter import (
    assign_facts_to_sections,
    score_facts_for_section,
)
from artiFACT.modules.export.factsheet import load_facts_for_export
from artiFACT.modules.export.template_manager import get_template


async def preview_assignments(
    db: AsyncSession,
    node_uids: list[uuid.UUID],
    template_uid: uuid.UUID,
    actor: FcUser,
    ai_call: object | None = None,
) -> dict:
    """Run prefilter only (no synthesis) to show which facts would go where.

    Returns template info + section assignments.
    """
    has_access = False
    for uid in node_uids:
        if await can(actor, "read", uid, db):
            has_access = True
            break
    if not has_access:
        raise Forbidden("No read access to any of the requested nodes")

    template = await get_template(db, template_uid)
    sections = template.sections

    facts = await load_facts_for_export(db, node_uids, ["published", "signed"])

    if ai_call is None:
        async def _default_ai_call(prompt: str) -> str:
            scores = {}
            for i in range(len(facts)):
                scores[str(i)] = 0.5
            return json.dumps({"scores": scores})
        ai_call = _default_ai_call

    affinity_scores = {}
    for section in sections:
        scores = await score_facts_for_section(ai_call, facts, section, sections)
        affinity_scores[section["key"]] = scores

    assignments = assign_facts_to_sections(affinity_scores, facts)

    result_assignments = []
    for section in sections:
        result_assignments.append({
            "section_key": section["key"],
            "section_title": section["title"],
            "facts": assignments.get(section["key"], []),
        })

    return {
        "template_uid": str(template.template_uid),
        "template_name": template.name,
        "assignments": result_assignments,
    }
