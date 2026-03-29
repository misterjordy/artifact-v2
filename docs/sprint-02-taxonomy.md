# Sprint 2: Taxonomy

**Depends on**: Sprint 1 (kernel + auth)
**Module**: `modules/taxonomy/` (5 components)

## Definition of Success
- `GET /api/v1/nodes` returns the full tree in flat and nested JSON
- `POST /api/v1/nodes` creates a node with correct `node_depth`
- `PUT /api/v1/nodes/{uid}` renames, reorders
- `POST /api/v1/nodes/{uid}/move` reparents and recomputes depth for all descendants
- Circular reparent is rejected with 409
- Tree response cached in Redis, invalidated on change
- Browser renders collapsible tree in left pane (HTMX partial)
- All taxonomy unit tests pass

## Database Migration
Table created: `fc_node` (if not already in Sprint 1 migration)

## Components

### service.py
```
create_node(db, title, parent_uid, sort_order, actor):
  validate parent exists, compute depth, check depth <= 5
  check title unique among siblings
  create node, flush, invalidate cache, emit event

move_node(db, node_uid, new_parent_uid, actor):
  prevent circular reference (new_parent cannot be a descendant)
  compute depth delta
  update node + all descendants' node_depth
  invalidate cache, emit event

archive_node(db, node_uid, actor):
  check no active facts under node or descendants
  set is_archived = True
```

### validators.py
```
validate_title_unique(db, title, parent_uid) → raise Conflict if duplicate sibling
validate_max_depth(depth) → raise Conflict if > 5
validate_not_circular(db, node_uid, new_parent_uid) → raise Conflict if circular
```

### tree_serializer.py
```
build_nested_tree(flat_nodes) → recursive dict structure
get_breadcrumb(flat_nodes, node_uid) → [root, ..., node] path
build_flat_tree(flat_nodes) → flat list with indent_level field
```

### router.py
```
GET  /api/v1/nodes           → full tree (check Redis cache first)
GET  /api/v1/nodes/{uid}     → single node + breadcrumb + children
POST /api/v1/nodes           → create (requires manage_node on parent)
PUT  /api/v1/nodes/{uid}     → update title/sort_order
POST /api/v1/nodes/{uid}/move → reparent
POST /api/v1/nodes/{uid}/archive → soft archive
```

### HTML Template: left pane tree
```
HTMX partial: GET /partials/tree
Collapsible nodes using Alpine.js x-show
+fact / +node hover actions per row
Click node → hx-get="/partials/browse/{node_uid}" → swap center pane
```

## Tests
```
test_create_root_node
test_create_child_node_sets_depth
test_move_node_recomputes_all_descendant_depths
test_circular_reparent_rejected
test_title_unique_among_siblings
test_max_depth_enforced
test_tree_cache_invalidated_on_create
test_nested_tree_structure_correct
test_breadcrumb_path_correct
```

## Verification
```bash
# Create root
curl -X POST .../api/v1/nodes -d '{"title":"Program A"}' -b cookies.txt -H "X-CSRF-Token: $TOKEN"

# Create child
curl -X POST .../api/v1/nodes -d '{"title":"Interfaces","parent_node_uid":"..."}' ...

# Get tree
curl .../api/v1/nodes -b cookies.txt | python -m json.tool
```
