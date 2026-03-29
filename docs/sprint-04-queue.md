# Sprint 4: Queue + Approval

**Depends on**: Sprint 3 (facts core)
**Module**: `modules/queue/` (7 components)

## Definition of Success
- Proposed facts appear in queue scoped to user's approvable nodes
- Subapprover on Node A CANNOT see/act on proposals from Node B
- Approve publishes (transaction), reject rejects with note
- "Revise language": reject original + publish revised (atomic)
- Badge count in nav updates within 60s
- All scope enforcement tests pass (regression: v1 Q-SEC-01/02)

## Database Migration
No new tables. Reads fc_fact_version (proposed), fc_event_log (move proposals).

## Components

### scope_resolver.py — `get_approvable_nodes(db, user)` → {node_uid: role}
### proposal_query.py — One query per pane: proposals, moves, unsigned
### service.py — approve/reject with scope check + transaction
### revision.py — Revise language: reject + create revised + publish (atomic)
### badge_counter.py — Redis-cached count, invalidated on approve/reject events

## Key Regression Tests
```
test_subapprover_cannot_reject_outside_scope     (v1 Q-SEC-01)
test_subapprover_cannot_approve_outside_scope     (v1 Q-SEC-01)
test_move_reject_requires_scope_check             (v1 Q-SEC-02)
test_contributor_with_node_grant_can_approve       (v1 Q-AUTH-02)
test_approve_wrapped_in_transaction                (v1 Q-MAINT-04)
test_badge_count_accurate_after_approve
test_revision_atomic_reject_plus_publish
```
