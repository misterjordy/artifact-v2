# nodesort

Sort facts into a taxonomy tree. Prefer leaf nodes over branches.

## system

Sort facts into a taxonomy. The tree is indented — children under parents. ALWAYS pick the deepest (leaf) node that fits. Never pick a parent if a child matches. Return ONLY JSON: {"a":[[fact#,node#,confidence],...]}. Use 0 if no node fits.

## user

Nodes:
{taxonomy_text}

Facts:
{numbered_facts}

Assign each fact to the most specific matching node number.
{constraint_hint}
