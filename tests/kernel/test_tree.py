"""Tree traversal (ancestor/descendant CTE) unit tests."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from artiFACT.kernel.tree.ancestors import get_ancestors
from artiFACT.kernel.tree.descendants import get_descendants


@pytest.mark.asyncio
async def test_ancestor_chain_correct_for_deep_node() -> None:
    """Ancestor CTE should return the full chain from a deep node to root."""
    root_uid = uuid.uuid4()
    child_uid = uuid.uuid4()
    grandchild_uid = uuid.uuid4()

    # Mock the DB execute to return the CTE result
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (grandchild_uid,),
        (child_uid,),
        (root_uid,),
    ]
    db = AsyncMock()
    db.execute.return_value = mock_result

    ancestors = await get_ancestors(db, grandchild_uid)
    assert len(ancestors) == 3
    assert grandchild_uid in ancestors
    assert child_uid in ancestors
    assert root_uid in ancestors


@pytest.mark.asyncio
async def test_descendant_set_includes_all_children() -> None:
    """Descendant CTE should return root and all its descendants."""
    root_uid = uuid.uuid4()
    child_a_uid = uuid.uuid4()
    child_b_uid = uuid.uuid4()
    grandchild_uid = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.all.return_value = [
        (root_uid,),
        (child_a_uid,),
        (child_b_uid,),
        (grandchild_uid,),
    ]
    db = AsyncMock()
    db.execute.return_value = mock_result

    descendants = await get_descendants(db, root_uid)
    assert len(descendants) == 4
    assert root_uid in descendants
    assert child_a_uid in descendants
    assert child_b_uid in descendants
    assert grandchild_uid in descendants
