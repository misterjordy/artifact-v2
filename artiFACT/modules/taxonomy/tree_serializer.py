"""Tree serialization: nested dict, breadcrumb path, flat list."""

import uuid
from typing import Any

from artiFACT.kernel.models import FcNode
from artiFACT.kernel.schemas import NodeOut


def _node_to_dict(node: FcNode) -> dict[str, Any]:
    """Convert an FcNode ORM object to a serializable dict."""
    return NodeOut.model_validate(node).model_dump(mode="json")


def build_nested_tree(flat_nodes: list[FcNode]) -> list[dict[str, Any]]:
    """Build a recursive nested tree structure from a flat list of nodes.

    Returns a list of root-level dicts, each with a 'children' key.
    """
    node_map: dict[uuid.UUID, dict[str, Any]] = {}
    for node in flat_nodes:
        entry = _node_to_dict(node)
        entry["children"] = []
        node_map[node.node_uid] = entry

    roots: list[dict[str, Any]] = []
    for node in flat_nodes:
        entry = node_map[node.node_uid]
        if node.parent_node_uid is not None and node.parent_node_uid in node_map:
            node_map[node.parent_node_uid]["children"].append(entry)
        else:
            roots.append(entry)

    return roots


def get_breadcrumb(flat_nodes: list[FcNode], node_uid: uuid.UUID) -> list[NodeOut]:
    """Return the path from root down to the given node (inclusive)."""
    node_map: dict[uuid.UUID, FcNode] = {n.node_uid: n for n in flat_nodes}
    path: list[NodeOut] = []
    current_uid: uuid.UUID | None = node_uid
    while current_uid is not None and current_uid in node_map:
        node = node_map[current_uid]
        path.append(NodeOut.model_validate(node))
        current_uid = node.parent_node_uid
    path.reverse()
    return path


def build_flat_tree(flat_nodes: list[FcNode]) -> list[dict[str, Any]]:
    """Return a flat list with an indent_level field for rendering."""
    result: list[dict[str, Any]] = []
    for node in flat_nodes:
        entry = _node_to_dict(node)
        entry["indent_level"] = node.node_depth
        result.append(entry)
    return result
