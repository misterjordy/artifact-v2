# Sprint 6: Search

**Depends on**: Sprint 3 (facts core)
**Module**: `modules/search/` (4 components)

## Definition of Success
- `GET /api/v1/search?q=system+owner` returns ranked results with breadcrumbs
- Uses PostgreSQL tsvector (no N+1 CTEs per result — regression: v1 B-PERF-02)
- Breadcrumbs from cached in-memory tree
- `GET /api/v1/search/acronyms` queries correct columns (regression: v1 B-BUG-01)
- Search works for all authenticated users
- Results render in center pane via HTMX swap

## Components
### service.py — tsvector @@ plainto_tsquery with ts_rank, breadcrumbs from tree cache
### acronym_miner.py — Regex against fc_fact_version.display_sentence (correct table)

## Key Tests
```
test_search_returns_ranked_results
test_breadcrumbs_resolved_from_cache_not_N_queries     (v1 B-PERF-02)
test_acronym_query_uses_correct_table_and_columns      (v1 B-BUG-01)
test_search_accessible_to_all_authenticated_users
```
