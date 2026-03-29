"""Taxonomy module unit tests."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artiFACT.kernel.exceptions import Conflict
from artiFACT.kernel.models import FcNode, FcUser
from artiFACT.modules.auth_admin.service import hash_password
from artiFACT.modules.taxonomy.service import (
    TREE_CACHE_KEY,
    create_node,
    move_node,
)
from artiFACT.modules.taxonomy.tree_serializer import (
    build_nested_tree,
    get_breadcrumb,
)
from artiFACT.modules.taxonomy.validators import (
    validate_max_depth,
    validate_not_circular,
    validate_title_unique,
)


def _make_user(role: str = "admin") -> FcUser:
    return FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"{role}-user",
        display_name=f"{role.title()} User",
        email=f"{role}@test.com",
        global_role=role,
        is_active=True,
        password_hash=hash_password(role),
    )


def _make_node(
    title: str = "Node",
    parent_uid: uuid.UUID | None = None,
    depth: int = 0,
    node_uid: uuid.UUID | None = None,
) -> FcNode:
    return FcNode(
        node_uid=node_uid or uuid.uuid4(),
        parent_node_uid=parent_uid,
        title=title,
        slug=title.lower().replace(" ", "-"),
        node_depth=depth,
        sort_order=0,
        is_archived=False,
        created_at=datetime.now(timezone.utc),
    )


# ── test_create_root_node ──────────────────────────────────────────


@pytest.mark.asyncio
@patch("artiFACT.modules.taxonomy.service.get_redis")
@patch("artiFACT.modules.taxonomy.service.publish")
@patch("artiFACT.modules.taxonomy.service.validate_title_unique")
async def test_create_root_node(mock_unique, mock_publish, mock_get_redis) -> None:
    """Creating a root node (no parent) should set depth=0."""
    mock_unique.return_value = None
    mock_publish.return_value = None
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    db = AsyncMock()
    actor = _make_user()

    node = await create_node(db, "Program A", None, 0, actor)

    assert node.title == "Program A"
    assert node.node_depth == 0
    assert node.parent_node_uid is None
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


# ── test_create_child_node_sets_depth ──────────────────────────────


@pytest.mark.asyncio
@patch("artiFACT.modules.taxonomy.service.get_redis")
@patch("artiFACT.modules.taxonomy.service.publish")
@patch("artiFACT.modules.taxonomy.service.validate_title_unique")
async def test_create_child_node_sets_depth(mock_unique, mock_publish, mock_get_redis) -> None:
    """Creating a child node should set depth = parent.depth + 1."""
    mock_unique.return_value = None
    mock_publish.return_value = None
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    parent = _make_node("Parent", depth=2)

    # Mock db.execute to return the parent when looked up
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = parent
    db = AsyncMock()
    db.execute.return_value = mock_result

    actor = _make_user()
    node = await create_node(db, "Child", parent.node_uid, 0, actor)

    assert node.node_depth == 3
    assert node.parent_node_uid == parent.node_uid


# ── test_move_node_recomputes_all_descendant_depths ─────────────────


@pytest.mark.asyncio
@patch("artiFACT.modules.taxonomy.service.get_redis")
@patch("artiFACT.modules.taxonomy.service.publish")
@patch("artiFACT.modules.taxonomy.service.get_descendants")
@patch("artiFACT.modules.taxonomy.service.validate_not_circular")
async def test_move_node_recomputes_all_descendant_depths(
    mock_circular, mock_descendants, mock_publish, mock_get_redis
) -> None:
    """Moving a node should recompute depth for the node and all descendants."""
    mock_circular.return_value = None
    mock_publish.return_value = None
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    node_uid = uuid.uuid4()
    child_uid = uuid.uuid4()
    grandchild_uid = uuid.uuid4()

    node_to_move = _make_node("Move Me", depth=1, node_uid=node_uid)
    new_parent = _make_node("New Parent", depth=3)

    # get_descendants returns the node itself + its children
    mock_descendants.return_value = [node_uid, child_uid, grandchild_uid]

    # First execute returns the node to move, second returns new parent
    mock_result_node = MagicMock()
    mock_result_node.scalar_one_or_none.return_value = node_to_move
    mock_result_parent = MagicMock()
    mock_result_parent.scalar_one_or_none.return_value = new_parent

    db = AsyncMock()
    db.execute.side_effect = [mock_result_node, mock_result_parent, None]

    actor = _make_user()
    result = await move_node(db, node_uid, new_parent.node_uid, actor)

    assert result.node_depth == 4  # new_parent.depth(3) + 1
    # db.execute should have been called 3 times: get node, get parent, update descendants
    assert db.execute.call_count == 3


# ── test_circular_reparent_rejected ────────────────────────────────


@pytest.mark.asyncio
async def test_circular_reparent_rejected() -> None:
    """Moving a node under its own descendant should raise Conflict (409)."""
    root_uid = uuid.uuid4()
    child_uid = uuid.uuid4()
    grandchild_uid = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.all.return_value = [
        (root_uid,),
        (child_uid,),
        (grandchild_uid,),
    ]
    db = AsyncMock()
    db.execute.return_value = mock_result

    with pytest.raises(Conflict, match="circular"):
        await validate_not_circular(db, root_uid, grandchild_uid)


# ── test_title_unique_among_siblings ───────────────────────────────


@pytest.mark.asyncio
async def test_title_unique_among_siblings() -> None:
    """Creating a node with a duplicate sibling title should raise Conflict."""
    existing = _make_node("Duplicate")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing

    db = AsyncMock()
    db.execute.return_value = mock_result

    parent_uid = uuid.uuid4()
    with pytest.raises(Conflict, match="sibling"):
        await validate_title_unique(db, "Duplicate", parent_uid)


# ── test_max_depth_enforced ────────────────────────────────────────


def test_max_depth_enforced() -> None:
    """Depth > 5 should raise Conflict."""
    # Depth 5 is OK
    validate_max_depth(5)

    # Depth 6 is rejected
    with pytest.raises(Conflict, match="depth"):
        validate_max_depth(6)


# ── test_tree_cache_invalidated_on_create ──────────────────────────


@pytest.mark.asyncio
@patch("artiFACT.modules.taxonomy.service.get_redis")
@patch("artiFACT.modules.taxonomy.service.publish")
@patch("artiFACT.modules.taxonomy.service.validate_title_unique")
async def test_tree_cache_invalidated_on_create(mock_unique, mock_publish, mock_get_redis) -> None:
    """Creating a node should call Redis delete on the tree cache key."""
    mock_unique.return_value = None
    mock_publish.return_value = None
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    db = AsyncMock()
    actor = _make_user()

    await create_node(db, "New Node", None, 0, actor)

    mock_redis.delete.assert_awaited_with(TREE_CACHE_KEY)


# ── test_nested_tree_structure_correct ─────────────────────────────


def test_nested_tree_structure_correct() -> None:
    """build_nested_tree should produce a correct recursive structure."""
    root = _make_node("Root", depth=0)
    child_a = _make_node("A", parent_uid=root.node_uid, depth=1)
    child_b = _make_node("B", parent_uid=root.node_uid, depth=1)
    grandchild = _make_node("A1", parent_uid=child_a.node_uid, depth=2)

    nested = build_nested_tree([root, child_a, child_b, grandchild])

    assert len(nested) == 1  # one root
    assert nested[0]["title"] == "Root"
    assert len(nested[0]["children"]) == 2
    titles = {c["title"] for c in nested[0]["children"]}
    assert titles == {"A", "B"}
    # Grandchild under A
    a_node = next(c for c in nested[0]["children"] if c["title"] == "A")
    assert len(a_node["children"]) == 1
    assert a_node["children"][0]["title"] == "A1"


# ── test_breadcrumb_path_correct ───────────────────────────────────


def test_breadcrumb_path_correct() -> None:
    """get_breadcrumb should return [root, ..., node] path."""
    root = _make_node("Root", depth=0)
    child = _make_node("Child", parent_uid=root.node_uid, depth=1)
    grandchild = _make_node("Grandchild", parent_uid=child.node_uid, depth=2)

    breadcrumb = get_breadcrumb([root, child, grandchild], grandchild.node_uid)

    assert len(breadcrumb) == 3
    assert breadcrumb[0].title == "Root"
    assert breadcrumb[1].title == "Child"
    assert breadcrumb[2].title == "Grandchild"
