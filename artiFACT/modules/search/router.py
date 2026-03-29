"""Search API endpoints and HTMX partial."""

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.modules.search.acronym_miner import mine_acronyms
from artiFACT.modules.search.service import search_facts

router = APIRouter(prefix="/api/v1", tags=["search"])

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_jinja = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)

partials_router = APIRouter(tags=["search-partials"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Full-text search across published/signed facts."""
    results = await search_facts(db, q, limit=limit)
    return {
        "data": [r.model_dump(mode="json") for r in results],
        "total": len(results),
    }


@router.get("/search/acronyms")
async def acronyms(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> dict:
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
    results = await search_facts(db, q)
    html = _jinja.get_template("partials/search_results.html").render(
        query=q, results=[r.model_dump() for r in results]
    )
    return HTMLResponse(html)
