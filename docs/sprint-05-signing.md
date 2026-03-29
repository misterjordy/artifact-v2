# Sprint 5: Signing

**Depends on**: Sprint 4 (queue)
**Module**: `modules/signing/` (5 components)

## Definition of Success
- `POST /api/v1/signatures/node/{uid}` signs all published facts under node
- Permission uses resolved role, not global_role (regression: v1 B-AUTH-01)
- Batch UPDATE in one query inside transaction (not per-fact loop)
- Signature record with fact count created
- Sign pane in queue shows only user's scoped nodes

## Components
### batch_signer.py — One UPDATE ... WHERE version_uid IN (...) inside transaction
### service.py — Permission check via kernel/permissions.can('sign', node_uid)
### expiration.py — Optional expires_at on signatures

## Database Migration
Table: `fc_signature`

## Key Tests
```
test_sign_uses_resolved_role_not_global     (v1 B-AUTH-01)
test_batch_update_one_query_not_loop        (v1 B-PERF-03)
test_sign_wrapped_in_transaction
test_signature_record_has_correct_count
test_sign_pane_scoped_to_user_nodes
```
