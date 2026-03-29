# Sprint 3: Facts Core

**Depends on**: Sprint 2 (taxonomy)
**Modules**: `modules/facts/` (8 components), `modules/audit/` (6 components)

## Definition of Success
- `POST /api/v1/facts` creates fact + initial version
- Contributor creates → state=proposed; Approver creates → state=published with `published_at` set
- `PUT /api/v1/facts/{uid}` creates new version (supersedes previous)
- `POST /api/v1/facts/{uid}/retire` sets is_retired=true
- State machine rejects invalid transitions (signed→proposed, retired→published)
- `created_by_uid` set on both fc_fact and fc_fact_version (never NULL)
- Every mutation emits event captured by audit/recorder.py
- `GET /api/v1/facts/{uid}/versions` returns version history
- Browse page renders facts grouped by node
- All fact + audit unit tests pass

## Database Migration
Tables: `fc_fact`, `fc_fact_version`, `fc_event_log`, `fc_ai_usage`

## Seed Data
After tables are created and CRUD is working, seed the **artiFACT self-documenting program**: create the "artiFACT" root node with children (System Overview, Architecture & Design, Security Controls, Data & Privacy, User Roles & Permissions, AI Integration, Operations & Sustainment, Compliance & Authorization). Populate with ~50-100 atomic facts about artiFACT itself, pulled from the architecture doc and master reference. These facts become the source material for generating ConOps/SDD documents in Sprint 9. Also seed Boatwing and SNIPE-B as playground programs.

## Components — facts/

### state_machine.py
```
ALLOWED_TRANSITIONS = {
  proposed: [published, rejected, withdrawn],
  published: [signed, retired],
  signed: [retired],
  rejected: [], withdrawn: [], retired: []
}
transition(db, version, new_state, actor):
  validate transition allowed
  set published_at on publish, signed_at on sign
  emit event
```

### versioning.py
```
create_version(db, fact, sentence, metadata, actor):
  determine state: published if can(approve) else proposed
  ALWAYS set created_by_uid
  ALWAYS set published_at if state=published
  link supersedes_version_uid
```

### service.py
```
create_fact(db, node_uid, sentence, metadata, actor):
  check can(contribute, node_uid)
  validate content (profanity, length, duplicates)
  create fc_fact with created_by_uid
  create initial version via versioning.py
  emit fact.created event

edit_fact(db, fact_uid, sentence, metadata, actor):
  check can(contribute, fact.node_uid)
  create new version superseding current
  emit fact.edited event

retire_fact(db, fact_uid, actor):
  check can(approve, fact.node_uid)
  set is_retired=True, retired_at, retired_by_uid
  emit fact.retired event
```

### reassign.py
```
reassign(db, fact_uid, target_node_uid, actor):
  check can(approve, source_node) AND can(approve, target_node)
  update fact.node_uid
  emit fact.moved event
```

### validators.py
```
validate_sentence(text) → length, profanity, junk detection
validate_duplicate(db, sentence, node_uid) → Jaccard check against existing
validate_effective_date(date_str) → YYYY-MM-DD format
```

### bulk.py
```
bulk_retire(db, fact_uids, actor) → all-or-nothing transaction
bulk_move(db, fact_uids, target_node, actor) → all-or-nothing transaction
```

## Components — audit/

### recorder.py
```
Subscribe to all fact/version events
Compute reverse_payload from current state BEFORE mutation
Store in fc_event_log
```

### undo_engine.py
```
undo_event(db, event_uid, actor):
  verify event is reversible
  verify actor has CURRENT permission
  check collision (state unchanged)
  dispatch reverse through facts/service (NOT raw SQL)
  mark event as undone
```

### collision_checker.py
```
check_collision(db, event):
  load entity, verify state matches what was recorded
  raise Conflict if state has changed since event
```

## Tests
```
# State machine
test_proposed_to_published, test_signed_cannot_go_to_proposed
test_publish_always_sets_published_at (regression: v1 S-BUG-01)

# Create
test_create_sets_created_by (regression: v1 F-DATA-01)
test_contributor_creates_proposed, test_approver_creates_published
test_duplicate_rejected, test_profanity_rejected

# Audit
test_event_recorded_on_create, test_event_recorded_on_retire
test_undo_checks_current_permission (regression: v1 U-SEC-02)
test_no_public_undo_record_endpoint (regression: v1 U-SEC-01)
test_collision_detected_on_stale_undo

# Browse
test_browse_page_renders_facts_by_node
test_retired_facts_hidden_from_browse
```
