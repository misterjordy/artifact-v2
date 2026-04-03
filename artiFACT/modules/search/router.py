"""Search API endpoints and HTMX partial."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.modules.search.acronym_miner import mine_acronyms
from artiFACT.modules.search.service import search_facts, search_facts_flat

router = APIRouter(prefix="/api/v1", tags=["search"])

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_jinja = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)

partials_router = APIRouter(tags=["search-partials"])


@router.get("/search")
async def search(
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    program_uid: list[str] | None = Query(None),
) -> dict[str, Any]:
    """Full-text search across published/signed facts, grouped by program."""
    if not q.strip():
        return {"data": {"programs": [], "total": 0}}

    results = await search_facts(
        db, q, limit=limit, offset=offset, program_uids=program_uid,
    )
    return {"data": results}


@router.get("/search/acronyms")
async def acronyms(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return extracted acronyms from the fact corpus."""
    entries = await mine_acronyms(db)
    return {"data": entries, "total": len(entries)}


@partials_router.get("/partials/search", response_class=HTMLResponse)
async def search_partial(
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> HTMLResponse:
    """HTMX partial: search results rendered for center pane."""
    if not q.strip():
        return HTMLResponse(
            '<p class="text-sm text-[var(--color-text-muted)]">Enter a search term.</p>'
        )
    results = await search_facts_flat(db, q)
    html = _jinja.get_template("partials/search_results.html").render(
        query=q, results=[r.model_dump() for r in results]
    )
    return HTMLResponse(html)


@partials_router.get("/partials/search-results", response_class=HTMLResponse)
async def sidebar_search_results(
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    program_uid: list[str] | None = Query(None),
) -> HTMLResponse:
    """HTMX partial: search results for the sidebar taxonomy pane."""
    if not q.strip() or len(q.strip()) < 2:
        return HTMLResponse("")

    # Get programs the user can access
    programs_result = await db.execute(
        select(FcNode)
        .where(FcNode.node_depth == 0, FcNode.is_archived.is_(False))
        .order_by(FcNode.sort_order, FcNode.title)
    )
    all_programs = list(programs_result.scalars().all())
    accessible_programs = []
    for prog in all_programs:
        if await can(user, "read", prog.node_uid, db):
            accessible_programs.append(prog)

    accessible_uids = [str(p.node_uid) for p in accessible_programs]
    filter_uids = program_uid if program_uid else accessible_uids

    results = await search_facts_flat(db, q, program_uids=filter_uids)

    result_dicts = []
    for r in results:
        d = r.model_dump()
        d["breadcrumb"] = [b.title for b in r.breadcrumb]
        result_dicts.append(d)

    html = _jinja.get_template("partials/sidebar_search_results.html").render(
        query=q,
        results=result_dicts,
        programs=accessible_programs if len(accessible_programs) > 1 else [],
    )
    return HTMLResponse(html)
