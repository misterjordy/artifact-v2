# nodesort

Sort facts into a taxonomy tree. Prefer leaf nodes over branches.

## system

Sort facts into a taxonomy. The tree is indented — children under parents. RULES: (1) ALWAYS pick the deepest (leaf) node that fits. A leaf is a node with no children indented below it. (2) NEVER pick a branch (parent) when one of its children is relevant. "Program Overview" under "System Identity" is BETTER than "System Identity" itself. (3) If truly no leaf fits, use the nearest branch. Use 0 only if nothing in the tree fits at all. Return ONLY JSON: {"a":[[fact#,node#],...]}. Use 0 if no node fits.

## user

Nodes:
{taxonomy_text}

Facts:
{numbered_facts}

Assign each fact to the single most specific (deepest) matching node.
{constraint_hint}
