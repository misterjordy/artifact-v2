"""Server-rendered HTML pages: login and browse."""

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Cookie, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.auth.session import get_session_data, is_auto_approve_active, validate_session
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcFact, FcFactVersion, FcImportSession, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.kernel.schemas import NodeOut
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.facts.history import get_fact_history
from artiFACT.modules.facts.service import create_fact
from artiFACT.modules.queue.badge_counter import get_badge_count
from artiFACT.modules.queue.scope_resolver import get_approvable_nodes
from artiFACT.modules.taxonomy.service import create_node
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
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> HTMLResponse:
    """Queue view with tabs for proposals, moves, unsigned."""
    approvable = await get_approvable_nodes(db, user)
    badge_total = await get_badge_count(db, user.user_uid, list(approvable.keys()))
    html = _jinja.get_template("queue.html").render(
        user=user, badge_total=badge_total, active_nav="queue",
        playground_mode=(playground_mode == "true"),
    )
    return HTMLResponse(html)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    user: FcUser = Depends(get_current_user),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> HTMLResponse:
    """AI key settings page."""
    html = _jinja.get_template("settings.html").render(
        user=user, active_nav="settings", playground_mode=(playground_mode == "true"),
    )
    return HTMLResponse(html)


@router.get("/partials/settings", response_class=HTMLResponse)
async def settings_partial(
    user: FcUser = Depends(get_current_user),
) -> HTMLResponse:
    """HTMX partial: settings for the right slideout pane."""
    html = _jinja.get_template("partials/settings_pane.html").render(user=user)
    return HTMLResponse(html)


@router.get("/partials/undo-actions", response_class=HTMLResponse)
async def undo_actions_partial(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
) -> HTMLResponse:
    """HTMX partial: undo actions list for the right pane."""
    from artiFACT.modules.audit.undo_actions import get_undo_actions_for_template

    actions, total = await get_undo_actions_for_template(
        db, user, days=30, limit=limit, offset=offset,
    )
    has_more = (offset + limit) < total
    next_offset = offset + limit
    html = _jinja.get_template("partials/undo_actions.html").render(
        actions=actions, has_more=has_more, next_offset=next_offset,
        is_append=(offset > 0),
    )
    return HTMLResponse(html)


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(
    user: FcUser = Depends(get_current_user),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> HTMLResponse:
    """AI chat page."""
    html = _jinja.get_template("chat.html").render(
        user=user, active_nav="chat", playground_mode=(playground_mode == "true"),
    )
    return HTMLResponse(html)


@router.get("/import", response_class=HTMLResponse)
async def import_page(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> HTMLResponse:
    """Document import page with tree sidebar and program selector."""
    # Get root-level program nodes the user can contribute to
    all_nodes = (
        await db.execute(
            select(FcNode)
            .where(FcNode.is_archived.is_(False), FcNode.node_depth == 0)
            .order_by(FcNode.sort_order, FcNode.title)
        )
    ).scalars().all()

    programs = []
    for node in all_nodes:
        if user.global_role == "admin" or await can(user, "contribute", node.node_uid, db):
            programs.append({"node_uid": str(node.node_uid), "title": node.title})

    # Detect active import session (resume on page load)
    active_result = await db.execute(
        select(FcImportSession)
        .where(
            FcImportSession.created_by_uid == user.user_uid,
            FcImportSession.status.in_(["analyzing", "staged"]),
        )
        .order_by(FcImportSession.created_at.desc())
        .limit(1)
    )
    active_session = active_result.scalar_one_or_none()

    active_session_data = None
    if active_session:
        active_session_data = {
            "session_uid": str(active_session.session_uid),
            "status": active_session.status,
            "source_filename": active_session.source_filename,
            "input_type": active_session.input_type,
        }

    html = _jinja.get_template("import.html").render(
        user=user,
        active_nav="import",
        playground_mode=(playground_mode == "true"),
        programs=programs,
        today=date.today().isoformat(),
        active_session=active_session_data,
    )
    return HTMLResponse(html)


@router.get("/export", response_class=HTMLResponse)
async def export_page(
    user: FcUser = Depends(get_current_user),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> HTMLResponse:
    """Export and document generation page."""
    html = _jinja.get_template("export.html").render(
        user=user, active_nav="export", playground_mode=(playground_mode == "true"),
    )
    return HTMLResponse(html)


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
    user: FcUser = Depends(get_current_user),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> HTMLResponse:
    """Admin dashboard page (admin-only)."""
    if user.global_role != "admin":
        raise Forbidden("Admin access required")
    html = _jinja.get_template("admin.html").render(
        user=user, active_nav="admin", playground_mode=(playground_mode == "true"),
    )
    return HTMLResponse(html)


@router.get("/acronyms", response_class=HTMLResponse)
async def acronyms_page(
    user: FcUser = Depends(get_current_user),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> HTMLResponse:
    """Acronym management page."""
    html = _jinja.get_template("acronyms.html").render(
        user=user, active_nav="acronyms", playground_mode=(playground_mode == "true"),
    )
    return HTMLResponse(html)


@router.get("/browse", response_class=HTMLResponse)
async def browse_page(
    user: FcUser = Depends(get_current_user),
    playground_mode: str | None = Cookie(None, alias="playground_mode"),
) -> HTMLResponse:
    """Main browse view with tree in left pane."""
    html = _jinja.get_template("browse.html").render(
        user=user, active_nav="browse", playground_mode=(playground_mode == "true"),
    )
    return HTMLResponse(html)


def _dfs_descendants(all_nodes: list, root_uid: uuid.UUID) -> list:
    """Return all descendants of root_uid in depth-first pre-order (matching tree render)."""
    children_map: dict[uuid.UUID, list] = {}
    for n in all_nodes:
        pid = n.parent_node_uid
        if pid is not None:
            children_map.setdefault(pid, []).append(n)
    # children already sorted by (sort_order, title) from the query
    result: list = []
    stack = list(reversed(children_map.get(root_uid, [])))
    while stack:
        node = stack.pop()
        result.append(node)
        for child in reversed(children_map.get(node.node_uid, [])):
            stack.append(child)
    return result


def _relative_path(all_nodes: list, root_uid: uuid.UUID, target_uid: uuid.UUID) -> str:
    """Build a slash-separated path from root's child down to target node."""
    uid_to_node = {n.node_uid: n for n in all_nodes}
    parts: list[str] = []
    current = uid_to_node.get(target_uid)
    while current and current.node_uid != root_uid:
        parts.append(current.title)
        current = uid_to_node.get(current.parent_node_uid)
    parts.reverse()
    return " / ".join(parts)


async def _get_facts_for_node(db: AsyncSession, node_uid: uuid.UUID) -> list[dict[str, Any]]:
    """Load published facts for a node. Proposed-only facts live in the queue, not here."""
    stmt = (
        select(FcFact)
        .where(
            FcFact.node_uid == node_uid,
            FcFact.is_retired.is_(False),
            FcFact.current_published_version_uid.isnot(None),
        )
        .order_by(FcFact.created_at.asc())
    )
    result = await db.execute(stmt)
    facts = result.scalars().all()

    items = []
    for fact in facts:
        ver = await db.get(FcFactVersion, fact.current_published_version_uid)
        if not ver:
            continue
        items.append(
            {
                "fact_uid": str(fact.fact_uid),
                "version_uid": str(ver.version_uid),
                "sentence": ver.display_sentence,
                "state": ver.state,
                "classification": ver.classification or "UNCLASSIFIED",
                "smart_tags": ver.smart_tags or [],
                "smart_tags_manual": ver.smart_tags_manual or [],
            }
        )
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
        select(FcNode)
        .where(FcNode.is_archived.is_(False))
        .order_by(FcNode.node_depth, FcNode.sort_order, FcNode.title)
    )
    all_nodes = list(all_nodes_result.scalars().all())
    breadcrumb = get_breadcrumb(all_nodes, node_uid)

    facts = await _get_facts_for_node(db, node_uid)

    # Walk all descendants in DFS pre-order (matches left-pane tree order)
    descendant_nodes = _dfs_descendants(all_nodes, node_uid)

    children_with_facts = []
    for desc_node in descendant_nodes:
        desc_facts = await _get_facts_for_node(db, desc_node.node_uid)
        if desc_facts:
            rel_path = _relative_path(all_nodes, node_uid, desc_node.node_uid)
            children_with_facts.append(
                {
                    "node": NodeOut.model_validate(desc_node),
                    "facts": desc_facts,
                    "rel_path": rel_path,
                }
            )

    can_contribute = await can(user, "contribute", node_uid, db)
    can_manage = await can(user, "manage_node", node_uid, db)

    html = _jinja.get_template("partials/browse_node.html").render(
        node=NodeOut.model_validate(node),
        breadcrumb=[NodeOut.model_validate(n) for n in breadcrumb]
        if isinstance(breadcrumb[0], FcNode) and breadcrumb
        else breadcrumb,
        facts=facts,
        children_with_facts=children_with_facts,
        can_contribute=can_contribute,
        can_manage=can_manage,
    )
    return HTMLResponse(html)


@router.get("/partials/fact-history/{fact_uid}", response_class=HTMLResponse)
async def fact_history_partial(
    fact_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> HTMLResponse:
    """HTMX partial: fact version history timeline for the right pane."""
    data = await get_fact_history(db, fact_uid, user)
    approvable = await get_approvable_nodes(db, user)
    can_approve = data["node_uid"] in approvable
    can_contribute = await can(user, "contribute", data["node_uid"], db)
    html = _jinja.get_template("partials/fact_history.html").render(
        **data, can_approve=can_approve, can_contribute=can_contribute,
    )
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Form partials: GET (render form) + POST (handle submission)
# ---------------------------------------------------------------------------

@router.get("/partials/node-form", response_class=HTMLResponse)
async def node_form_get(
    parent: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> HTMLResponse:
    """Render the add-node form partial."""
    node = await db.get(FcNode, parent)
    parent_title = node.title if node else "Unknown"
    html = _jinja.get_template("partials/node_form.html").render(
        parent_node_uid=str(parent),
        parent_title=parent_title,
        error=None,
        title_value="",
    )
    return HTMLResponse(html)


@router.post("/partials/node-form", response_class=HTMLResponse)
async def node_form_post(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    title: str = Form(""),
    parent_node_uid: str = Form(""),
) -> HTMLResponse:
    """Handle add-node form submission."""
    title = title.strip()
    parent_uid = uuid.UUID(parent_node_uid) if parent_node_uid else None

    if not title:
        parent_node = await db.get(FcNode, parent_uid) if parent_uid else None
        html = _jinja.get_template("partials/node_form.html").render(
            parent_node_uid=parent_node_uid,
            parent_title=parent_node.title if parent_node else "",
            error="Title is required.",
            title_value=title,
        )
        return HTMLResponse(html)

    try:
        if parent_uid is not None:
            if not await can(user, "manage_node", parent_uid, db):
                raise Forbidden("You do not have permission to add nodes here.")
        else:
            if user.global_role != "admin":
                raise Forbidden("Only admins can create root nodes.")

        await create_node(db, title, parent_uid, 0, user)
        await db.commit()
    except Exception as exc:
        parent_node = await db.get(FcNode, parent_uid) if parent_uid else None
        html = _jinja.get_template("partials/node_form.html").render(
            parent_node_uid=parent_node_uid,
            parent_title=parent_node.title if parent_node else "",
            error=str(exc),
            title_value=title,
        )
        return HTMLResponse(html)

    # Success: clear modal, refresh tree
    resp = HTMLResponse("")
    resp.headers["HX-Trigger-After-Settle"] = json.dumps(
        {"closeModal": True, "refreshTree": True}
    )
    return resp


@router.get("/partials/fact-form", response_class=HTMLResponse)
async def fact_form_get(
    node: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> HTMLResponse:
    """Render the add-fact form partial."""
    if not await can(user, "contribute", node, db):
        raise Forbidden("You do not have permission to add facts here.")
    node_obj = await db.get(FcNode, node)
    node_title = node_obj.title if node_obj else "Unknown"
    html = _jinja.get_template("partials/fact_form.html").render(
        node_uid=str(node),
        node_title=node_title,
        error=None,
        sentence_value="",
        effective_date_value=date.today().isoformat(),
        classification_value="UNCLASSIFIED",
    )
    return HTMLResponse(html)


@router.post("/partials/fact-form", response_class=HTMLResponse)
async def fact_form_post(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
    session_id: str | None = Cookie(None, alias="session_id"),
    node_uid: str = Form(""),
    sentence: str = Form(""),
    effective_date: str = Form(""),
    classification: str = Form("UNCLASSIFIED"),
) -> HTMLResponse:
    """Handle add-fact form submission."""
    sentence = sentence.strip()
    effective_date = effective_date.strip() or date.today().isoformat()
    nuid = uuid.UUID(node_uid)

    if not sentence or len(sentence) < 10:
        node_obj = await db.get(FcNode, nuid)
        html = _jinja.get_template("partials/fact_form.html").render(
            node_uid=node_uid,
            node_title=node_obj.title if node_obj else "",
            error="Sentence is required (minimum 10 characters).",
            sentence_value=sentence,
            effective_date_value=effective_date or "",
            classification_value=classification,
        )
        return HTMLResponse(html)

    session_data = await get_session_data(session_id) if session_id else None
    auto_approve = is_auto_approve_active(session_data)

    try:
        fact, version = await create_fact(
            db, nuid, sentence, user,
            effective_date=effective_date,
            classification=classification,
            auto_approve=auto_approve,
        )
        await flush_pending_events(db)
        await db.commit()
    except Exception as exc:
        node_obj = await db.get(FcNode, nuid)
        html = _jinja.get_template("partials/fact_form.html").render(
            node_uid=node_uid,
            node_title=node_obj.title if node_obj else "",
            error=str(exc),
            sentence_value=sentence,
            effective_date_value=effective_date or "",
            classification_value=classification,
        )
        return HTMLResponse(html)

    # Success: clear modal, refresh center pane
    resp = HTMLResponse("")
    resp.headers["HX-Trigger-After-Settle"] = json.dumps({
        "closeModal": True,
        "refreshTree": True,
        "refreshNode": {"nodeUid": node_uid},
    })
    return resp
