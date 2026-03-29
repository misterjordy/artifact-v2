# Sprint 12: Admin Dashboard

**Depends on**: Sprint 1 (auth), Sprint 3 (facts), Sprint 4 (queue)
**Module**: `modules/admin/` (8 components)

## Definition of Success
- Dashboard: user count, fact count, error rate, active users
- User management: list, search, change role, deactivate/reactivate
- Module health: per-module DB/Redis/S3 connectivity
- Feature flags: toggle any flag, changes immediate
- Cache: view stats, flush all or by category
- Snapshot: trigger pg_dump to S3, list snapshots
- All admin endpoints require `global_role = 'admin'`

## Components
### dashboard.py — Aggregate metrics (users, facts, queue, system)
### module_health.py — Per-module health checks (DB, Redis, S3 per module)
### config_manager.py — Feature flag CRUD from fc_system_config
### snapshot_manager.py — Celery task: pg_dump → S3
### cache_manager.py — Redis stats, selective flush
### system_info.py — Version, SHA, uptime, env name

## Key Tests
```
test_admin_required_on_all_endpoints
test_non_admin_gets_403
test_dashboard_returns_valid_metrics
test_feature_flag_toggle_takes_effect
test_snapshot_creates_file_in_s3
test_cache_flush_clears_permissions
```
