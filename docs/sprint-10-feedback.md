# Sprint 10: Feedback

**Depends on**: Sprint 1 (kernel)
**Module**: `modules/feedback/` (5 components)

## Definition of Success
- `POST /api/v1/feedback` works without auth (rate limited by IP)
- Admin kanban view grouped by category + status
- Admin can move, comment, edit, close items
- CSRF uses consistent header (kernel middleware — regression: v1 F-SEC-01)
- All feedback tests pass

## Components
### service.py — Submit (anonymous), rate limited by IP hash
### kanban.py — Admin queries: group by category, count aggregations
### categories.py — CRUD for categories (stored in fc_system_config)

## Database Migration
Table: `fc_feedback` (feedback history stored in `fc_event_log` with `entity_type='feedback'` — no separate fc_feedback_event table)

## Key Tests
```
test_anonymous_submit_works
test_rate_limited_by_ip
test_csrf_header_consistent_with_app   (v1 F-SEC-01)
test_admin_can_move_between_categories
test_admin_can_close_feedback
```
