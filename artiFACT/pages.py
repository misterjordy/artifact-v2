"""Server-rendered HTML pages: login and browse."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.auth.session import validate_session
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.kernel.schemas import NodeOut
from artiFACT.modules.queue.badge_counter import get_badge_count
from artiFACT.modules.queue.scope_resolver import get_approvable_nodes
from artiFACT.modules.taxonomy.tree_serializer import get_breadcrumb

router = APIRouter(tags=["pages"])

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_jinja = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


@router.get("/", response_class=HTMLResponse, response_model=None)
async def login_page(
    db: AsyncSession = Depends(get_db),
    session_id: str | None = Cookie(None, alias="session_id"),
) -> HTMLResponse | RedirectResponse:
    """Show login form, or redirect to /browse if already authenticated."""
    if session_id:
        user = await validate_session(session_id, db)
        if user:
            return RedirectResponse("/browse", status_code=302)
    html = _jinja.get_template("login.html").render(active_nav="")
    return HTMLResponse(html)


@router.get("/queue", response_class=HTMLResponse)
async def queue_page(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> HTMLResponse:
    """Queue view with tabs for proposals, moves, unsigned."""
    approvable = await get_approvable_nodes(db, user)
    badge_total = await get_badge_count(db, user.user_uid, list(approvable.keys()))
    html = _jinja.get_template("queue.html").render(user=user, badge_total=badge_total, active_nav="queue")
    return HTMLResponse(html)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(user: FcUser = Depends(get_current_user)) -> HTMLResponse:
    """AI key settings page."""
    html = _jinja.get_template("settings.html").render(user=user, active_nav="settings")
    return HTMLResponse(html)


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(user: FcUser = Depends(get_current_user)) -> HTMLResponse:
    """AI chat page."""
    html = _jinja.get_template("chat.html").render(user=user, active_nav="chat")
    return HTMLResponse(html)


@router.get("/import", response_class=HTMLResponse)
async def import_page(user: FcUser = Depends(get_current_user)) -> HTMLResponse:
    """Document import page."""
    html = _jinja.get_template("import.html").render(user=user, active_nav="import")
    return HTMLResponse(html)


@router.get("/export", response_class=HTMLResponse)
async def export_page(user: FcUser = Depends(get_current_user)) -> HTMLResponse:
    """Export and document generation page."""
    html = _jinja.get_template("export.html").render(user=user, active_nav="export")
    return HTMLResponse(html)


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(user: FcUser = Depends(get_current_user)) -> HTMLResponse:
    """Admin dashboard page (admin-only)."""
    if user.global_role != "admin":
        raise Forbidden("Admin access required")
    html = _jinja.get_template("admin.html").render(user=user, active_nav="admin")
    return HTMLResponse(html)


@router.get("/browse", response_class=HTMLResponse)
async def browse_page(user: FcUser = Depends(get_current_user)) -> HTMLResponse:
    """Main browse view with tree in left pane."""
    html = _jinja.get_template("browse.html").render(user=user, active_nav="browse")
    return HTMLResponse(html)


async def _get_facts_for_node(
    db: AsyncSession, node_uid: uuid.UUID
) -> list[dict]:
    """Load non-retired facts for a node with their current version info."""
    stmt = (
        select(FcFact)
        .where(FcFact.node_uid == node_uid, FcFact.is_retired.is_(False))
        .order_by(FcFact.created_at.asc())
    )
    result = await db.execute(stmt)
    facts = result.scalars().all()

    items = []
    for fact in facts:
        sentence = ""
        state = "proposed"
        classification = "UNCLASSIFIED"
        if fact.current_published_version_uid:
            ver = await db.get(FcFactVersion, fact.current_published_version_uid)
            if ver:
                sentence = ver.display_sentence
                state = ver.state
                classification = ver.classification or "UNCLASSIFIED"
        else:
            ver_stmt = (
                select(FcFactVersion)
                .where(FcFactVersion.fact_uid == fact.fact_uid)
                .order_by(FcFactVersion.created_at.desc())
                .limit(1)
            )
            ver_result = await db.execute(ver_stmt)
            ver = ver_result.scalar_one_or_none()
            if ver:
                sentence = ver.display_sentence
                state = ver.state
                classification = ver.classification or "UNCLASSIFIED"
        items.append({
            "fact_uid": str(fact.fact_uid),
            "sentence": sentence,
            "state": state,
            "classification": classification,
        })
    return items


@router.get("/partials/browse/{node_uid}", response_class=HTMLResponse)
async def browse_node_partial(
    node_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> HTMLResponse:
    """HTMX partial: facts grouped by node."""
    node = await db.get(FcNode, node_uid)
    if not node:
        return HTMLResponse('<p class="text-sm text-red-500">Node not found.</p>')

    all_nodes_result = await db.execute(
        select(FcNode).where(FcNode.is_archived.is_(False))
        .order_by(FcNode.node_depth, FcNode.sort_order, FcNode.title)
    )
    all_nodes = list(all_nodes_result.scalars().all())
    breadcrumb = get_breadcrumb(all_nodes, node_uid)

    facts = await _get_facts_for_node(db, node_uid)

    children_stmt = (
        select(FcNode)
        .where(FcNode.parent_node_uid == node_uid, FcNode.is_archived.is_(False))
        .order_by(FcNode.sort_order, FcNode.title)
    )
    children_result = await db.execute(children_stmt)
    children = children_result.scalars().all()

    children_with_facts = []
    for child in children:
        child_facts = await _get_facts_for_node(db, child.node_uid)
        if child_facts:
            children_with_facts.append({
                "node": NodeOut.model_validate(child),
                "facts": child_facts,
            })

    html = _jinja.get_template("partials/browse_node.html").render(
        node=NodeOut.model_validate(node),
        breadcrumb=[NodeOut.model_validate(n) for n in breadcrumb]
        if isinstance(breadcrumb[0], FcNode) and breadcrumb else breadcrumb,
        facts=facts,
        children_with_facts=children_with_facts,
    )
    return HTMLResponse(html)
