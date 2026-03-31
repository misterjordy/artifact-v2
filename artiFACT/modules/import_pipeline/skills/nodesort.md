# nodesort

Sort facts into a taxonomy. v1-proven format.

## system

Sort facts into a taxonomy. Return ONLY JSON: {"a":[[fact#,node#,confidence],...]}. Confidence is 0-1 indicating fit quality. Use 0 if no node fits.

## user

Nodes:
{taxonomy_text}

Facts:
{numbered_facts}

Assign each fact to the most specific matching node number.
{constraint_hint}
