"""Taxonomy API endpoints and HTMX partials."""

import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.auth.session import get_redis
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcUser
from artiFACT.kernel.permissions.resolver import can
from artiFACT.kernel.schemas import NodeOut
from artiFACT.modules.taxonomy.schemas import (
    NodeCreate,
    NodeDetail,
    NodeMove,
    NodeUpdate,
    TreeOut,
)
from artiFACT.modules.taxonomy.service import (
    TREE_CACHE_KEY,
    archive_node,
    create_node,
    get_all_nodes,
    get_node_with_children,
    move_node,
    update_node,
)
from artiFACT.modules.taxonomy.tree_serializer import (
    build_flat_tree,
    build_nested_tree,
    get_breadcrumb,
)

router = APIRouter(prefix="/api/v1", tags=["taxonomy"])
partials_router = APIRouter(tags=["taxonomy-partials"])


@router.get("/nodes")
async def list_nodes(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> TreeOut:
    """Return the full taxonomy tree in flat and nested JSON. Cached in Redis."""
    r = await get_redis()
    cached = await r.get(TREE_CACHE_KEY)
    if cached:
        data = json.loads(cached)
        return TreeOut(**data)

    nodes = await get_all_nodes(db)
    flat = [NodeOut.model_validate(n) for n in nodes]
    nested = build_nested_tree(nodes)

    tree = TreeOut(flat=flat, nested=nested)
    await r.setex(TREE_CACHE_KEY, 300, tree.model_dump_json())
    return tree


@router.get("/nodes/{node_uid}")
async def get_node(
    node_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> NodeDetail:
    """Return a single node with breadcrumb path and direct children."""
    node, children = await get_node_with_children(db, node_uid)
    all_nodes = await get_all_nodes(db)
    breadcrumb = get_breadcrumb(all_nodes, node_uid)
    return NodeDetail(
        **NodeOut.model_validate(node).model_dump(),
        breadcrumb=breadcrumb,
        children=[NodeOut.model_validate(c) for c in children],
    )


@router.post("/nodes", status_code=201)
async def create(
    body: NodeCreate,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> NodeOut:
    """Create a new taxonomy node. Requires manage_node on parent."""
    if body.parent_node_uid is not None:
        if not await can(user, "manage_node", body.parent_node_uid, db):
            raise Forbidden("Insufficient permissions to manage this node")
    else:
        # Creating a root node requires admin
        if user.global_role != "admin":
            raise Forbidden("Only admins can create root nodes")

    node = await create_node(db, body.title, body.parent_node_uid, body.sort_order, user)
    await db.commit()
    return NodeOut.model_validate(node)


@router.put("/nodes/{node_uid}")
async def update(
    node_uid: uuid.UUID,
    body: NodeUpdate,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> NodeOut:
    """Update a node's title and/or sort_order."""
    if not await can(user, "manage_node", node_uid, db):
        raise Forbidden("Insufficient permissions to manage this node")

    node = await update_node(db, node_uid, body.title, body.sort_order, user)
    await db.commit()
    return NodeOut.model_validate(node)


@router.post("/nodes/{node_uid}/move")
async def move(
    node_uid: uuid.UUID,
    body: NodeMove,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> NodeOut:
    """Reparent a node and recompute depths."""
    if not await can(user, "manage_node", node_uid, db):
        raise Forbidden("Insufficient permissions to manage this node")

    node = await move_node(db, node_uid, body.new_parent_uid, user)
    await db.commit()
    return NodeOut.model_validate(node)


@router.post("/nodes/{node_uid}/archive")
async def archive(
    node_uid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> NodeOut:
    """Soft-archive a node."""
    if not await can(user, "manage_node", node_uid, db):
        raise Forbidden("Insufficient permissions to manage this node")

    node = await archive_node(db, node_uid, user)
    await db.commit()
    return NodeOut.model_validate(node)


@partials_router.get("/partials/tree", response_class=HTMLResponse)
async def tree_partial(
    db: AsyncSession = Depends(get_db),
    user: FcUser = Depends(get_current_user),
) -> str:
    """HTMX partial: collapsible tree for the left pane."""
    nodes = await get_all_nodes(db)
    nested = build_nested_tree(nodes)

    def render_node(node: dict, level: int = 0) -> str:
        indent = level * 16
        uid = node["node_uid"]
        title = node["title"]
        children = node.get("children", [])
        has_children = len(children) > 0

        html = f'<div class="tree-row" style="padding-left:{indent}px" x-data="{{open: true}}">\n'
        html += '  <div class="tree-row-inner">\n'

        if has_children:
            html += f'    <button class="tree-toggle" @click="open = !open" aria-label="Toggle">'
            html += '<span x-text="open ? \'\\u25BE\' : \'\\u25B8\'"></span></button>\n'
        else:
            html += '    <span class="tree-toggle-spacer"></span>\n'

        html += f'    <a class="tree-link" hx-get="/partials/browse/{uid}" '
        html += f'hx-target="#center-pane" hx-swap="innerHTML">{title}</a>\n'

        html += f'    <span class="tree-actions">'
        html += f'<button class="btn-icon" title="Add node" '
        html += f'hx-get="/partials/node-form?parent={uid}" '
        html += f'hx-target="#modal" hx-swap="innerHTML">+node</button> '
        html += f'<button class="btn-icon" title="Add fact" '
        html += f'hx-get="/partials/fact-form?node={uid}" '
        html += f'hx-target="#modal" hx-swap="innerHTML">+fact</button>'
        html += '</span>\n'

        html += '  </div>\n'

        if has_children:
            html += f'  <div x-show="open">\n'
            for child in children:
                html += render_node(child, level + 1)
            html += '  </div>\n'

        html += '</div>\n'
        return html

    body = ""
    for root in nested:
        body += render_node(root)

    return body
