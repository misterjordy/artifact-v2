# Sprint 8: Import Pipeline

**Depends on**: Sprint 7 (AI provider), Sprint 3 (facts core)
**Module**: `modules/import_pipeline/` (9 + 5 extractor components)

## Definition of Success
- Upload accepts DOCX/PPTX/PDF/TXT with size validation
- Files stored in S3 (MinIO on VPS)
- Analysis runs as Celery background task (not blocking web — regression: v1 I-PERF-01)
- SSE streams progress to client
- Staged facts displayed for review with accept/reject per-fact
- Propose creates facts (all-or-nothing transaction — regression: v1 I-MAINT-02)
- Duplicate detection flags similar existing facts
- CSRF on ALL endpoints (regression: v1 I-SEC-01, I-SEC-02)
- Rate limited on upload and analyze (regression: v1 I-SEC-03)

## Components
### upload_handler.py — Validate type + size, hash, S3 upload, create session
### extractors/{docx,pptx,pdf,text}_extractor.py — One per file type
### analyzer.py — Celery task: chunk → AI extract → progress SSE
### deduplicator.py — Jaccard similarity (ONE copy — regression: v1 I-ARCH-03)
### stager.py — Write staged JSON to S3
### proposer.py — Staged → real facts in transaction
### location_recommender.py — AI node placement (ONE copy — regression: v1 I-LOW-04)

## Database Migration
Table: `fc_import_session`

## Key Tests
```
test_csrf_required_on_propose     (v1 I-SEC-01)
test_csrf_required_on_upload      (v1 I-SEC-02)
test_rate_limited_on_analyze      (v1 I-SEC-03)
test_analysis_runs_as_background_task_not_blocking
test_propose_all_or_nothing_transaction
test_duplicate_detection_flags_similar
test_file_size_limit_enforced
test_unsupported_file_type_rejected
```
