# artiFACT v2 — Enterprise Platform Architecture

**Date**: 2026-03-28
**Author**: Architecture session with Jordan Allred
**Target environment**: COSMOS (NIWC Pacific, AWS GovCloud IL-4/5, CAC-authenticated)
**Classification**: UNCLASSIFIED

---

## 1. Design Principles

Every decision below follows from the 110 bugs found in v1 and the deployment target (COSMOS GovCloud).

**Narrow failure modes.** Each module is a self-contained unit with exactly one responsibility. A bug in the import pipeline cannot crash the approval queue. A broken AI call cannot corrupt the fact store.

**Zero shared mutable state between modules.** Modules communicate through the database and a thin internal event bus — never by importing each other's functions or sharing global variables.

**Free and open source everything.** The only cost is COSMOS infrastructure (AWS compute, storage, RDS). Every tool, library, framework, and dependency is FOSS.

**API-first.** Every capability is an HTTP endpoint with an OpenAPI spec. The UI is a consumer of the API, not a special citizen. Jupiter/Advana integration is a matter of handing them the spec and an API key.

---

## 2. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Runtime** | Python 3.12+ | COSMOS supports it natively, massive ecosystem, async support, strong typing |
| **Framework** | FastAPI 0.115+ | Auto-generates OpenAPI spec (critical for Advana), async, dependency injection, Pydantic validation, zero license cost |
| **Database** | PostgreSQL 16 (RDS) | Enterprise-grade, JSONB for flexible metadata, row-level security, recursive CTEs native, point-in-time recovery, read replicas |
| **Migrations** | Alembic | Industry standard for PostgreSQL schema versioning |
| **ORM** | SQLAlchemy 2.0 (Core, not ORM) | Explicit SQL with type safety — no magic, no N+1 surprises |
| **Cache** | ElastiCache Redis (or local Redis) | Session store, permission cache, rate limiting, queue badge counts |
| **Object store** | S3 (COSMOS-native) | Document uploads, generated DOCX, snapshots, audit exports |
| **Search** | PostgreSQL `tsvector` full-text | Good enough for <100K facts. Upgrade path to OpenSearch if needed |
| **Frontend** | HTMX + Alpine.js + Vanilla CSS | Zero build step, zero npm, zero webpack. Server-rendered HTML with progressive enhancement. Matches v1's "no framework" philosophy but with structure |
| **AI proxy** | Per-user API key, backend proxy | Keys stored encrypted in DB, backend makes all LLM calls — never expose keys to browser |
| **Auth** | CAC via COSMOS SAML/OIDC → FastAPI middleware | COSMOS handles certificate validation, artiFACT receives verified identity |
| **Containerization** | Docker | One Dockerfile per service, ECR for registry |
| **Orchestration** | ECS Fargate | Serverless containers — no EC2 instances to patch |
| **IaC** | Terraform (open source) | Reproducible infrastructure across build/test/prod |
| **CI/CD** | GitLab CI (COSMOS provides GitLab) or GitHub Actions | Pipeline-as-code, environment promotion |
| **Testing** | pytest + httpx (API), Playwright (E2E) | All FOSS |
| **Monitoring** | CloudWatch + Prometheus + Grafana | Grafana is FOSS; CloudWatch is included in COSMOS |
| **Secrets** | AWS Secrets Manager | For system secrets (DB creds, signing keys). User AI keys stored encrypted in PostgreSQL |

---

## 3. Module Architecture

### 3.1 Design Pattern: Modular Monolith

The system is decomposed into **13 bounded contexts** containing **~108 internal components** organized in 4 tiers. This is the "modular monolith" pattern used by Shopify, early Google, and Netflix (pre-microservices): bounded contexts have strict no-cross-import rules between them, while internal components can be tested, replaced, or extracted independently.

Each bounded context is a top-level directory with a strict public interface (`router.py` + `schemas.py`). No component inside one context ever imports from inside another context — they go through `kernel/`.

### 3.2 Module Communication Rules

1. **Modules NEVER import from each other.** `queue/` cannot `from modules.facts.service import ...`.
2. **Cross-module reads go through the database.** `queue/` reads `fc_fact_version` directly (it has read access to the table via SQLAlchemy models in the kernel).
3. **Cross-module writes go through the kernel event bus or internal service calls.** `queue/` calls `kernel.events.publish('fact.approved', {fact_uid, version_uid})` → `facts/` subscribes and updates the pointer. Or `queue/` calls a thin kernel-level function that encapsulates the write.
4. **The kernel is the ONLY shared import.** If you find yourself wanting to import from another module, the function belongs in the kernel.

### 3.3 Top-Level Directory Structure

```
artiFACT/
├── kernel/                  ← Shared kernel (the ONLY cross-module import)
│   ├── auth.py              ← CAC identity + RBAC resolution
│   ├── db.py                ← Database session factory
│   ├── models.py            ← SQLAlchemy table definitions (single source of truth)
│   ├── permissions.py       ← Role hierarchy, node-grant resolution, descendant CTE
│   ├── events.py            ← Internal event bus (publish/subscribe)
│   ├── crypto.py            ← Encryption helpers (for AI keys, etc.)
│   ├── config.py            ← Environment-based configuration
│   ├── exceptions.py        ← Shared exception types
│   └── schemas.py           ← Shared Pydantic models (FactOut, NodeOut, etc.)
│
├── modules/
│   ├── taxonomy/            ← TIER 1: Data foundation
│   │   ├── router.py        ← GET /api/v1/nodes, POST /api/v1/nodes, etc.
│   │   ├── service.py       ← Business logic
│   │   ├── schemas.py       ← Input/output Pydantic models
│   │   └── tests/
│   │
│   ├── facts/               ← TIER 1: Core fact CRUD + versioning
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── tests/
│   │
│   ├── auth_admin/          ← TIER 1: User management + RBAC grants
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── tests/
│   │
│   ├── queue/               ← TIER 2: Approval workflows
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── tests/
│   │
│   ├── signing/             ← TIER 2: Signature lifecycle
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── tests/
│   │
│   ├── import_pipeline/     ← TIER 2: Document ingestion
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── extractors.py    ← DOCX/PPTX/PDF/TXT extraction
│   │   ├── analyzer.py      ← AI-driven fact extraction + dedup
│   │   ├── schemas.py
│   │   └── tests/
│   │
│   ├── export/              ← TIER 2: Download + docgen
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── docgen.py        ← SEP/document generation
│   │   ├── schemas.py
│   │   └── tests/
│   │
│   ├── ai_chat/             ← TIER 2: Corpus-grounded AI Q&A
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── prompt_builder.py
│   │   ├── safety.py        ← Injection detection, output filtering
│   │   ├── schemas.py
│   │   └── tests/
│   │
│   ├── audit/               ← TIER 1: Event log + undo
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── tests/
│   │
│   ├── feedback/            ← TIER 3: User feedback collection
│   │   ├── router.py
│   │   ├── service.py

### 3.4 Sub-Module Breakdown

Each bounded context is broken into internal components averaging 50-200 lines. The largest (analyzer.py, orchestrator.py) might hit 400. Nothing approaches v1's 1,096-line factQueue.php or 2,233-line telemetry.php. When a component breaks, you send a 100-line file with one job — not a 1,000-line file where the bug could be anywhere.

#### KERNEL (shared infrastructure — 12 components)

```
kernel/
├── auth/
│   ├── middleware.py          ← FastAPI dependency: extract user from session/API key
│   ├── session.py             ← Session create/validate/destroy (Redis-backed)
│   ├── csrf.py                ← CSRF token generate/validate middleware
│   └── api_keys.py            ← Bearer token auth for machine clients (Advana)
│
├── permissions/
│   ├── resolver.py            ← resolve_role(user, node) — the ONE permission function
│   ├── grants.py              ← Read active grants for a user (cached in Redis)
│   ├── hierarchy.py           ← Role hierarchy (role_gte, REQUIRED_ROLES map)
│   └── cache.py               ← Permission cache read/write/invalidate
│
├── tree/
│   ├── ancestors.py           ← get_ancestors(node_uid) — single recursive CTE
│   ├── descendants.py         ← get_descendants(node_uid) — single recursive CTE
│   └── builder.py             ← Build full in-memory tree from one query (taxonomyTree pattern)
│
├── ai/
│   ├── provider.py            ← AIProvider class — the ONE LLM abstraction
│   ├── openai_client.py       ← OpenAI-specific HTTP calls
│   ├── anthropic_client.py    ← Anthropic-specific HTTP calls
│   ├── azure_client.py        ← Azure OpenAI-specific HTTP calls
│   └── token_counter.py       ← Token counting per provider (tiktoken for OpenAI, etc.)
│
├── crypto.py                  ← AES-256-GCM encrypt/decrypt for user AI keys
├── config.py                  ← Environment config loader (env vars → typed config)
├── db.py                      ← SQLAlchemy engine + async session factory
├── models.py                  ← ALL table definitions (single source of truth)
├── schemas.py                 ← Shared Pydantic types (UserOut, NodeOut, FactOut, etc.)
├── events.py                  ← Internal event bus (publish/subscribe)
├── exceptions.py              ← HTTPException subclasses (NotFound, Forbidden, Conflict)
├── rate_limiter.py            ← Rate limit check/log (Redis-backed)
├── content_filter.py          ← Profanity check, junk detection, duplicate check
├── pagination.py              ← Pagination params + response wrapper
└── background.py              ← Celery app + task decorator
```

---

#### 1. TAXONOMY (node/tree management — 5 components)

```
modules/taxonomy/
├── router.py                  ← PUBLIC INTERFACE: HTTP endpoints
│     GET  /api/v1/nodes                    ← Full tree (flat + nested formats)
│     GET  /api/v1/nodes/{uid}              ← Single node + breadcrumb
│     POST /api/v1/nodes                    ← Create node
│     PUT  /api/v1/nodes/{uid}              ← Update title, sort_order, parent
│     POST /api/v1/nodes/{uid}/move         ← Reparent (recomputes depth)
│     POST /api/v1/nodes/{uid}/archive      ← Soft archive
│
├── service.py                 ← Business logic: create, move, archive
│                                 Validates parent exists, computes node_depth,
│                                 generates slug, checks for circular reparent
│
├── validators.py              ← Input validation beyond Pydantic
│                                 Title uniqueness within siblings,
│                                 max depth check, circular reference detection
│
├── tree_serializer.py         ← Convert flat node list → nested JSON tree
│                                 Supports: full tree, subtree, breadcrumb path
│                                 Uses kernel/tree/builder.py for the query
│
├── schemas.py                 ← NodeCreate, NodeUpdate, NodeOut, TreeOut
│
└── tests/
    ├── test_create.py
    ├── test_move.py
    ├── test_tree_serializer.py
    └── test_validators.py
```

---

#### 2. FACTS (fact CRUD + versioning — 8 components)

```
modules/facts/
├── router.py                  ← PUBLIC INTERFACE
│     GET  /api/v1/facts                      ← List (filtered by node, state, user)
│     GET  /api/v1/facts/{uid}                ← Single fact + current version
│     GET  /api/v1/facts/{uid}/versions       ← Version history
│     POST /api/v1/facts                      ← Create (proposed or auto-published)
│     PUT  /api/v1/facts/{uid}                ← Edit (creates new version)
│     POST /api/v1/facts/{uid}/retire         ← Retire
│     POST /api/v1/facts/{uid}/unretire       ← Unretire (admin)
│     POST /api/v1/facts/{uid}/move           ← Reassign to different node
│
├── service.py                 ← Core business logic
│                                 State machine: proposed → published → signed
│                                 All transitions in ONE function with explicit guards
│                                 Every mutation wrapped in transaction
│                                 Every mutation emits event via kernel/events.py
│
├── state_machine.py           ← Fact version state transitions
│                                 ALLOWED_TRANSITIONS dict
│                                 transition(version, from_state, to_state, actor)
│                                 Enforces: proposed→published, proposed→rejected, etc.
│                                 Rejects: signed→proposed, retired→published, etc.
│
├── versioning.py              ← Version creation logic
│                                 create_version(fact, sentence, metadata, actor)
│                                 Always sets published_at when state=published
│                                 Always sets created_by_uid
│                                 Links supersedes_version_uid
│
├── validators.py              ← Content validation
│                                 Uses kernel/content_filter.py for profanity/junk
│                                 Duplicate detection within node (exact + fuzzy)
│                                 Sentence length bounds
│                                 Effective date format
│
├── reassign.py                ← Move fact to different node
│                                 Permission check on BOTH source and target
│                                 Option: direct move (approver) or propose move (contributor)
│                                 Uses kernel/tree/ancestors.py for branch validation
│
├── schemas.py                 ← FactCreate, FactUpdate, FactOut, VersionOut
│
├── bulk.py                    ← Batch operations
│                                 bulk_retire(fact_uids), bulk_move(fact_uids, target_node)
│                                 All-or-nothing transaction
│
└── tests/
    ├── test_create.py
    ├── test_state_machine.py
    ├── test_versioning.py
    ├── test_reassign.py
    ├── test_validators.py
    └── test_bulk.py
```

---

#### 3. AUTH_ADMIN (user management + RBAC grants — 7 components)

```
modules/auth_admin/
├── router.py                  ← PUBLIC INTERFACE
│     GET  /api/v1/users                     ← List users (admin)
│     GET  /api/v1/users/me                  ← Current user profile
│     GET  /api/v1/users/{uid}               ← User detail + grants
│     POST /api/v1/users/{uid}/role          ← Set global role (admin)
│     POST /api/v1/users/{uid}/deactivate    ← Deactivate (admin)
│     POST /api/v1/users/{uid}/reactivate    ← Reactivate (admin)
│     GET  /api/v1/grants                    ← List grants for a node (approver+)
│     POST /api/v1/grants                    ← Create/update grant
│     POST /api/v1/grants/{uid}/revoke       ← Revoke grant
│
├── service.py                 ← User CRUD, grant CRUD
│                                 Upsert pattern for grants (handles revoke + re-grant)
│                                 Invalidates permission cache on grant change
│
├── cac_mapper.py              ← Map SAML assertion → fc_user record
│                                 Extract EDIPI, DN, email from COSMOS SAML
│                                 Auto-create user on first login
│                                 Update last_login_at
│
├── ai_key_manager.py          ← CRUD for per-user AI API keys
│                                 Encrypt on store, decrypt on use
│                                 Validate key format per provider
│                                 Store only prefix for display ("sk-proj-BN...")
│
├── user_search.py             ← Search/filter users for admin panel
│                                 By name, role, last_login, active status
│                                 Pagination
│
├── schemas.py                 ← UserOut, GrantCreate, GrantOut, AIKeyCreate
│
└── tests/
    ├── test_cac_mapper.py
    ├── test_grants.py
    ├── test_ai_key_manager.py
    └── test_user_search.py
```

---

#### 4. AUDIT (event log + undo — 6 components)

```
modules/audit/
├── router.py                  ← PUBLIC INTERFACE
│     GET  /api/v1/audit/events              ← Event log (filtered by entity, type, actor, date)
│     GET  /api/v1/audit/events/{uid}        ← Single event detail
│     GET  /api/v1/audit/undo/stack          ← User's undoable actions
│     POST /api/v1/audit/undo/{event_uid}    ← Undo a specific action
│     POST /api/v1/audit/redo/{event_uid}    ← Redo an undone action
│     GET  /api/v1/audit/history/{entity_uid} ← Full timeline for an entity
│
├── service.py                 ← Record events, compute reverse payloads
│                                 record_event() — called by kernel/events.py subscribers
│                                 NEVER accepts reverse_payload from external input
│                                 Computes reverse_payload from current DB state at event time
│
├── recorder.py                ← Event bus subscriber
│                                 Listens for: fact.created, fact.published, fact.retired,
│                                              version.approved, version.rejected,
│                                              signature.created, node.moved, etc.
│                                 Maps each event type to a reverse_payload computation
│
├── undo_engine.py             ← Execute undo/redo operations
│                                 Reads reverse_payload from fc_event_log (server-computed)
│                                 Validates: user has permission on target entity NOW
│                                 Validates: entity is still in expected state (collision check)
│                                 Dispatches actual mutation THROUGH the owning module
│                                 (calls facts/service.py, NOT raw SQL)
│
├── collision_checker.py       ← Pre-check if undo is safe
│                                 Entity still exists?
│                                 State hasn't changed since the event?
│                                 Batch check for bulk undos (one query, not N)
│
├── schemas.py                 ← EventOut, UndoStackItem, UndoResult
│
└── tests/
    ├── test_recorder.py
    ├── test_undo_engine.py
    ├── test_collision_checker.py
    └── test_undo_permissions.py    ← Specifically tests that undo respects current permissions
```

---

#### 5. QUEUE (approval workflows — 7 components)

```
modules/queue/
├── router.py                  ← PUBLIC INTERFACE
│     GET  /api/v1/queue/proposals           ← Pending proposals for current user's scope
│     GET  /api/v1/queue/moves               ← Pending move proposals
│     GET  /api/v1/queue/unsigned             ← Facts awaiting signature
│     GET  /api/v1/queue/counts              ← Badge counts (cached in Redis)
│     POST /api/v1/queue/approve/{version_uid}
│     POST /api/v1/queue/reject/{version_uid}
│     POST /api/v1/queue/approve-move/{event_uid}
│     POST /api/v1/queue/reject-move/{event_uid}
│
├── service.py                 ← Approval/rejection logic
│                                 Every action verifies scope via kernel/permissions
│                                 Approve: calls facts/service via kernel event
│                                 Reject: calls facts/state_machine via kernel event
│                                 All wrapped in transactions
│
├── scope_resolver.py          ← Compute which nodes a user can approve
│                                 Uses kernel/permissions/resolver.py
│                                 Caches result per-request (static cache pattern)
│                                 Returns {node_uid: role} map, NOT just [node_uid]
│
├── proposal_query.py          ← Query builders for the three queue panes
│                                 get_proposals(node_uids) — proposed versions
│                                 get_move_proposals(node_uids) — from event_log payload
│                                 get_unsigned(node_uids) — published but not signed
│                                 Each is ONE query with JOINs, not N+1
│
├── revision.py                ← "Revise language" approval path
│                                 Reject original + create revised version + publish
│                                 All in one transaction
│
├── badge_counter.py           ← Queue badge count for nav
│                                 Cached in Redis with 60s TTL
│                                 Invalidated on approve/reject events
│                                 Called from layout on every page — must be <1ms
│
├── schemas.py                 ← ProposalOut, MoveProposalOut, ApproveRequest, RejectRequest
│
└── tests/
    ├── test_approve.py
    ├── test_reject.py
    ├── test_scope_resolver.py
    ├── test_revision.py
    ├── test_badge_counter.py
    └── test_scope_enforcement.py   ← Tests that subapprover can't approve outside scope
```

---

#### 6. SIGNING (signature lifecycle — 5 components)

```
modules/signing/
├── router.py                  ← PUBLIC INTERFACE
│     GET  /api/v1/signatures                ← List signatures (by node, signer, date)
│     POST /api/v1/signatures/node/{uid}     ← Sign all published facts under a node
│     POST /api/v1/signatures/fact/{uid}     ← Sign a single fact
│     GET  /api/v1/signatures/{uid}          ← Signature detail
│
├── service.py                 ← Sign logic
│                                 Permission: kernel/permissions.can('sign', node_uid)
│                                 Collects all published versions under node (one query)
│                                 Batch UPDATE in transaction (not per-fact loop)
│                                 Creates fc_signature record
│                                 Emits signature.created event
│
├── batch_signer.py            ← Batch version state update
│                                 UPDATE fc_fact_version SET state='signed', signed_at=now()
│                                 WHERE version_uid IN (...) — one query
│                                 UPDATE fc_fact SET current_signed_version_uid = ...
│                                 All in transaction
│
├── expiration.py              ← Signature expiration logic (optional)
│                                 Check if signature has expires_at
│                                 Background task to flag expired signatures
│
├── schemas.py                 ← SignRequest, SignatureOut
│
└── tests/
    ├── test_sign_node.py
    ├── test_sign_fact.py
    ├── test_batch_signer.py
    └── test_permission_check.py
```

---

#### 7. IMPORT_PIPELINE (document ingestion — 9 components)

```
modules/import_pipeline/
├── router.py                  ← PUBLIC INTERFACE
│     POST /api/v1/import/upload             ← Upload document → S3
│     POST /api/v1/import/analyze/{uid}      ← Trigger AI extraction (async task)
│     GET  /api/v1/import/sessions/{uid}     ← Session status
│     GET  /api/v1/import/sessions/{uid}/progress  ← SSE progress stream
│     GET  /api/v1/import/sessions/{uid}/staged     ← Staged facts for review
│     POST /api/v1/import/sessions/{uid}/propose    ← Accept staged → create facts
│     POST /api/v1/import/sessions/{uid}/discard    ← Discard staged
│     POST /api/v1/import/recommend-location        ← AI recommend node placement
│
├── upload_handler.py          ← File upload processing
│                                 Validate file type + size
│                                 Compute SHA-256 hash (dedup check)
│                                 Upload to S3 temp bucket
│                                 Create fc_import_session record
│
├── extractors/
│   ├── __init__.py            ← Dispatcher: pick extractor by file extension
│   ├── docx_extractor.py      ← python-docx extraction
│   ├── pptx_extractor.py      ← python-pptx extraction
│   ├── pdf_extractor.py       ← pdfminer.six extraction (pypdf fallback)
│   ├── text_extractor.py      ← Plain text / markdown passthrough
│   └── base.py                ← ExtractorBase ABC — extract(file_path) → str
│
├── analyzer.py                ← AI-powered fact extraction (Celery task)
│                                 Chunking strategy (section-aware)
│                                 Calls kernel/ai/provider.py (not direct curl)
│                                 Uses response_format='json_object'
│                                 Streams progress via Redis pub/sub → SSE
│
├── deduplicator.py            ← Jaccard similarity + exact match
│                                 tokenize() and jaccard() — ONE copy
│                                 Compare extracted facts against existing corpus
│                                 Flag duplicates with similarity score
│
├── stager.py                  ← Stage extracted facts for user review
│                                 Write staged facts JSON to S3
│                                 Update session status = 'staged'
│
├── proposer.py                ← Convert staged facts to real fc_fact records
│                                 Calls facts/service (via kernel event)
│                                 All-or-nothing transaction
│                                 Sets created_by_uid, published_at, etc.
│
├── location_recommender.py    ← AI-powered node placement suggestion
│                                 Builds numeric-indexed tree (75% token reduction)
│                                 ONE implementation (not duplicated in queue)
│                                 Called by both import and queue modules
│                                 Lives here but exposed via kernel if queue needs it
│
├── schemas.py                 ← UploadResponse, SessionOut, StagedFactOut, ProposeRequest
│
└── tests/
    ├── test_upload.py
    ├── test_extractors/
    │   ├── test_docx.py
    │   ├── test_pptx.py
    │   └── test_pdf.py
    ├── test_analyzer.py
    ├── test_deduplicator.py
    ├── test_stager.py
    └── test_proposer.py
```

---

#### 8. EXPORT (download + docgen — 7 components)

```
modules/export/
├── router.py                  ← PUBLIC INTERFACE (ALL routes require auth)
│     GET  /api/v1/export/factsheet          ← Download facts as TXT/JSON/CSV/NDJSON
│     POST /api/v1/export/document           ← Trigger SEP/DOCX generation (async task)
│     GET  /api/v1/export/document/{uid}/progress  ← SSE progress
│     GET  /api/v1/export/document/{uid}/download   ← Signed S3 URL
│     GET  /api/v1/export/templates           ← Available doc templates
│
├── factsheet.py               ← Flat fact export
│                                 Formats: txt, json, ndjson, csv
│                                 Filtered by node, state, date range
│                                 Omits internal UUIDs in public formats (uses sequence numbers)
│                                 Streams response for large exports
│
├── docgen/
│   ├── orchestrator.py        ← SEP generation orchestrator (Celery task)
│   │                             8 sections × (prefilter + synthesis)
│   │                             Calls kernel/ai/provider.py
│   │                             Progress via Redis → SSE
│   │
│   ├── prefilter.py           ← AI affinity scoring (which facts → which section)
│   │                             Two-pass: score all sections simultaneously, then assign
│   │                             Fixes v1's first-section-gets-first-pick bias
│   │
│   ├── synthesizer.py         ← AI text synthesis per section
│   │                             Streaming via kernel/ai/provider.py
│   │
│   ├── docx_builder.py        ← python-docx assembly
│   │                             Template-driven (header, footer, styles from template)
│   │                             Output to S3, return signed download URL
│   │
│   └── templates/             ← DOCX template files (styles, logos, headers)
│       ├── sep_standard.py
│       └── sep_brief.py
│
├── download_manager.py        ← S3 signed URL generation
│                                 Verifies requesting user = generating user
│                                 URLs expire in 1 hour
│                                 Files auto-deleted from S3 after 24 hours (lifecycle rule)
│
├── schemas.py                 ← ExportRequest, DocumentOut, DownloadURL
│
└── tests/
    ├── test_factsheet.py
    ├── test_prefilter.py
    ├── test_synthesizer.py
    ├── test_docx_builder.py
    └── test_download_manager.py
```

---

#### 9. AI_CHAT (corpus-grounded Q&A — 7 components)

```
modules/ai_chat/
├── router.py                  ← PUBLIC INTERFACE
│     POST /api/v1/ai/chat                   ← Send message (streaming response)
│     GET  /api/v1/ai/context                ← Available programs/topics (scoped to user)
│     POST /api/v1/ai/search                 ← AI-ranked semantic search
│     GET  /api/v1/ai/status                 ← User's key status + usage
│
├── service.py                 ← Chat orchestration
│                                 Load facts for topic → build prompt → call AI → filter output
│                                 Rate limited per user via kernel/rate_limiter.py
│
├── prompt_builder.py          ← System prompt construction
│                                 Token-counted fact loading (not byte truncation)
│                                 Reports actual loaded count to client
│                                 Easter eggs gated behind feature flag
│
├── safety/
│   ├── input_filter.py        ← Layer 1: Injection detection
│   │                             Regex patterns + Unicode NFKC normalization
│   │                             Confusable character mapping (Cyrillic а → Latin a)
│   │                             Flags but doesn't block (canary injection in Layer 2)
│   │
│   ├── system_hardening.py    ← Layer 2: Hardened system prompt rules
│   │                             Immutable instructions, canary phrases
│   │
│   └── output_filter.py       ← Layer 3: Response filtering
│                                 Fact fingerprint matching (full sentence, not 40-char prefix)
│                                 Bulk dump detection
│                                 PII leak detection
│
├── context_provider.py        ← Load available programs/topics
│                                 Scoped to user's readable nodes
│                                 (fixing v1 A-SEC-03: full taxonomy exposure)
│
├── schemas.py                 ← ChatMessage, ChatResponse, ContextOut
│
└── tests/
    ├── test_prompt_builder.py
    ├── test_input_filter.py
    ├── test_output_filter.py
    ├── test_context_scoping.py
    └── test_token_counting.py
```

---

#### 10. SEARCH (full-text + semantic — 4 components)

```
modules/search/
├── router.py                  ← PUBLIC INTERFACE
│     GET  /api/v1/search?q=...              ← Full-text search
│     GET  /api/v1/search/acronyms           ← Acronym lookup
│
├── service.py                 ← Search orchestration
│                                 PostgreSQL ts_rank + tsvector
│                                 Breadcrumbs resolved in-memory from cached tree
│                                 (not N+1 CTEs per result)
│
├── acronym_miner.py           ← Extract acronyms from corpus
│                                 Queries fc_fact_version (correct table, not v1's nonexistent columns)
│                                 Caches results in Redis (refresh on fact publish events)
│
├── schemas.py                 ← SearchResult, AcronymEntry
│
└── tests/
    ├── test_search.py
    └── test_acronym_miner.py
```

---

#### 11. FEEDBACK (user feedback — 5 components)

```
modules/feedback/
├── router.py                  ← PUBLIC INTERFACE
│     POST /api/v1/feedback                  ← Submit (anonymous allowed)
│     GET  /api/v1/feedback                  ← List (admin)
│     GET  /api/v1/feedback/{uid}/history    ← Event timeline
│     POST /api/v1/feedback/{uid}/status     ← Update status (admin)
│     POST /api/v1/feedback/{uid}/comment    ← Add comment (admin)
│     POST /api/v1/feedback/categories       ← Manage categories (admin)
│
├── service.py                 ← Feedback CRUD
│                                 Rate limited by IP for anonymous
│                                 CSRF uses consistent header (kernel/auth/csrf.py)
│
├── kanban.py                  ← Admin kanban board queries
│                                 Group by category + status
│                                 Count aggregations
│
├── categories.py              ← Category CRUD (stored in fc_system_config)
│                                 Protected categories: mobile, other, delivered
│
├── schemas.py                 ← FeedbackCreate, FeedbackOut, CategoryOut
│
└── tests/
    ├── test_submit.py
    ├── test_kanban.py
    └── test_categories.py
```

---

#### 12. PRESENTATION (briefing mode — 4 components)

```
modules/presentation/
├── router.py                  ← PUBLIC INTERFACE
│     GET  /api/v1/presentation/config       ← Slide data + beat timing
│     GET  /presentation/                    ← Full-screen presentation page
│
├── slide_data.py              ← Slide content definitions
│                                 Static data + dynamic queries (user count, fact count)
│                                 Beat timing map
│
├── static/
│   ├── presentation.js        ← Self-contained beat engine + VCR controls
│   ├── presentation.css       ← Scoped styles (--fp- variables)
│   └── audio/                 ← Narration MP3s + SFX
│       ├── 1-1.mp3
│       ├── 1-2.mp3
│       └── 0.mp3              ← Cymbal SFX
│
├── schemas.py                 ← SlideConfig, BeatTiming
│
└── tests/
    └── test_slide_data.py
```

---

#### 13. ADMIN (system dashboard — 8 components)

```
modules/admin/
├── router.py                  ← PUBLIC INTERFACE (admin-only)
│     GET  /api/v1/admin/dashboard           ← System health + metrics
│     GET  /api/v1/admin/modules             ← Module status
│     POST /api/v1/admin/modules/{name}/toggle
│     GET  /api/v1/admin/config              ← Feature flags + rate limits
│     POST /api/v1/admin/config/{key}        ← Update config
│     POST /api/v1/admin/snapshot            ← Trigger DB snapshot to S3
│     POST /api/v1/admin/cache/flush         ← Flush Redis caches
│     GET  /api/v1/admin/health              ← Detailed health check
│
├── dashboard.py               ← Aggregate metrics
│                                 User count, fact count, version count
│                                 Facts per state, per program
│                                 Activity in last 24h/7d/30d
│                                 Error rate from CloudWatch
│
├── module_health.py           ← Per-module health checks
│                                 DB connectivity, Redis connectivity, S3 access
│                                 Per-module: can it read its own tables?
│                                 Background task queue depth
│
├── config_manager.py          ← Feature flag CRUD
│                                 Read/write fc_system_config
│                                 Type validation per key
│                                 Audit log entry on every change
│
├── snapshot_manager.py        ← Database snapshot operations
│                                 Trigger pg_dump → S3 (Celery task)
│                                 List available snapshots
│                                 Restore from snapshot (with confirmation gate)
│
├── cache_manager.py           ← Redis cache operations
│                                 Stats: hit rate, key count, memory
│                                 Flush: all, permissions only, badges only
│
├── system_info.py             ← Version, deploy SHA, uptime, environment name
│                                 Python version, dependency versions
│
├── schemas.py                 ← DashboardOut, ModuleHealth, ConfigEntry, SnapshotOut
│
└── tests/
    ├── test_dashboard.py
    ├── test_module_health.py
    ├── test_config_manager.py
    └── test_snapshot_manager.py
```

---

#### Component Count Summary

| Bounded Context | Internal Components | Test Files |
|----------------|-------------------|------------|
| Kernel | 18 | (tested via module tests) |
| Taxonomy | 5 | 4 |
| Facts | 8 | 6 |
| Auth Admin | 7 | 4 |
| Audit | 6 | 4 |
| Queue | 7 | 6 |
| Signing | 5 | 4 |
| Import Pipeline | 9 + 5 extractors | 8 |
| Export | 7 + 2 templates | 5 |
| AI Chat | 7 + 3 safety | 5 |
| Search | 4 | 2 |
| Feedback | 5 | 3 |
| Presentation | 4 | 1 |
| Admin | 8 | 4 |
| **Total** | **~108 components** | **~56 test files** |

Each component averages 50-200 lines. The largest (analyzer.py, orchestrator.py) might hit 400. Nothing approaches v1's 1,096-line factQueue.php or 2,233-line telemetry.php. When you send me a broken component, I see a 100-line file with one job — not a 1,000-line file where the bug could be anywhere.

---

## 4. Data Schema

### 4.1 Entity-Relationship Overview

```
fc_user ──────────────── fc_node_permission ──── fc_node
   │                                                │
   │                                                │── (parent_node_uid → fc_node)
   │                                                │
   ├── fc_user_ai_key                               │
   │                                                │
   ├── fc_event_log ◄──────────────────────────── fc_fact
   │                                                │
   ├── fc_signature ────────────────────────────── │
   │                                                │
   └── fc_import_session                           fc_fact_version
                                                     │
                                                   fc_fact_comment
```

### 4.2 Table Definitions

All UIDs use `UUID` type (native PostgreSQL, not CHAR(36)). All timestamps are `TIMESTAMPTZ` (timezone-aware). All JSON columns use `JSONB` (indexable, queryable).

```sql
-- ═══════════════════════════════════════════════════════════
-- TIER 1: Core tables
-- ═══════════════════════════════════════════════════════════

CREATE TABLE fc_user (
    user_uid        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cac_dn          TEXT UNIQUE NOT NULL,           -- CAC distinguished name (from COSMOS SAML)
    edipi           VARCHAR(10) UNIQUE,              -- DoD EDIPI (Electronic Data Interchange Personal Identifier)
    display_name    VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    global_role     VARCHAR(20) NOT NULL DEFAULT 'viewer'
                    CHECK (global_role IN ('admin','signatory','approver','subapprover','contributor','viewer')),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);
CREATE INDEX idx_user_cac ON fc_user (cac_dn);
CREATE INDEX idx_user_edipi ON fc_user (edipi);

CREATE TABLE fc_user_ai_key (
    key_uid         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_uid        UUID NOT NULL REFERENCES fc_user(user_uid) ON DELETE CASCADE,
    provider        VARCHAR(20) NOT NULL CHECK (provider IN ('openai','anthropic','azure_openai','bedrock')),
    encrypted_key   BYTEA NOT NULL,                 -- AES-256-GCM encrypted
    key_prefix      VARCHAR(10),                    -- e.g., "sk-proj-BN..." for display
    model_override  VARCHAR(100),                   -- user can specify model
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ,
    UNIQUE (user_uid, provider)
);

CREATE TABLE fc_node (
    node_uid        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_node_uid UUID REFERENCES fc_node(node_uid) ON DELETE RESTRICT,
    title           VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL,
    node_depth      SMALLINT NOT NULL DEFAULT 0,     -- computed on write, avoids tree-walk queries
    sort_order      INT NOT NULL DEFAULT 0,
    is_archived     BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_uid  UUID REFERENCES fc_user(user_uid)
);
CREATE INDEX idx_node_parent ON fc_node (parent_node_uid);
CREATE INDEX idx_node_slug ON fc_node (slug);

CREATE TABLE fc_node_permission (
    permission_uid  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_uid        UUID NOT NULL REFERENCES fc_user(user_uid) ON DELETE CASCADE,
    node_uid        UUID NOT NULL REFERENCES fc_node(node_uid) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL
                    CHECK (role IN ('signatory','approver','subapprover','contributor','viewer')),
    granted_by_uid  UUID NOT NULL REFERENCES fc_user(user_uid),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at      TIMESTAMPTZ,
    UNIQUE (user_uid, node_uid, revoked_at)   -- allows re-grant after revocation (NULL != NULL in unique)
);
CREATE INDEX idx_perm_user ON fc_node_permission (user_uid) WHERE revoked_at IS NULL;
CREATE INDEX idx_perm_node ON fc_node_permission (node_uid) WHERE revoked_at IS NULL;

CREATE TABLE fc_fact (
    fact_uid                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_uid                       UUID NOT NULL REFERENCES fc_node(node_uid) ON DELETE RESTRICT,
    current_published_version_uid  UUID,             -- FK added after fc_fact_version created
    current_signed_version_uid     UUID,
    is_retired                     BOOLEAN NOT NULL DEFAULT false,
    created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_uid                 UUID REFERENCES fc_user(user_uid),
    retired_at                     TIMESTAMPTZ,
    retired_by_uid                 UUID REFERENCES fc_user(user_uid)
);
CREATE INDEX idx_fact_node ON fc_fact (node_uid) WHERE NOT is_retired;
CREATE INDEX idx_fact_published ON fc_fact (current_published_version_uid) WHERE current_published_version_uid IS NOT NULL;

CREATE TABLE fc_fact_version (
    version_uid              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fact_uid                 UUID NOT NULL REFERENCES fc_fact(fact_uid) ON DELETE RESTRICT,
    state                    VARCHAR(20) NOT NULL DEFAULT 'proposed'
                             CHECK (state IN ('proposed','challenged','accepted','rejected',
                                              'published','signed','withdrawn','retired')),
    display_sentence         TEXT NOT NULL,
    canonical_json           JSONB,
    metadata_tags            JSONB DEFAULT '[]'::jsonb,
    source_reference         JSONB,
    effective_date           DATE,
    last_verified_date       DATE,
    classification           VARCHAR(64) DEFAULT 'UNCLASSIFIED',
    applies_to               VARCHAR(255),
    change_summary           TEXT,
    supersedes_version_uid   UUID REFERENCES fc_fact_version(version_uid),
    created_by_uid           UUID REFERENCES fc_user(user_uid),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at             TIMESTAMPTZ,            -- set on ALL publish paths (fixing v1 S-BUG-01)
    signed_at                TIMESTAMPTZ,
    -- Full-text search vector
    search_vector            TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', display_sentence)) STORED
);
CREATE INDEX idx_version_fact ON fc_fact_version (fact_uid);
CREATE INDEX idx_version_state ON fc_fact_version (state);
CREATE INDEX idx_version_search ON fc_fact_version USING GIN (search_vector);
CREATE INDEX idx_version_created_by ON fc_fact_version (created_by_uid);

-- Deferred FK for circular reference
ALTER TABLE fc_fact ADD CONSTRAINT fk_fact_pub_version
    FOREIGN KEY (current_published_version_uid) REFERENCES fc_fact_version(version_uid);
ALTER TABLE fc_fact ADD CONSTRAINT fk_fact_signed_version
    FOREIGN KEY (current_signed_version_uid) REFERENCES fc_fact_version(version_uid);


-- ═══════════════════════════════════════════════════════════
-- TIER 1: Audit
-- ═══════════════════════════════════════════════════════════

CREATE TABLE fc_event_log (
    event_uid       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seq             BIGINT GENERATED ALWAYS AS IDENTITY,  -- monotonic cursor for Advana delta feed
    entity_type     VARCHAR(20) NOT NULL,            -- 'fact', 'version', 'node', 'signature', 'user', 'feedback'
    entity_uid      UUID NOT NULL,
    event_type      VARCHAR(64) NOT NULL,            -- 'proposed', 'approved', 'rejected', 'signed', etc.
    payload         JSONB,                           -- structured data (target_node_uid, etc.) — NOT freetext
    actor_uid       UUID REFERENCES fc_user(user_uid),
    note            TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- For undo: the reverse operation data, computed server-side only
    reversible      BOOLEAN NOT NULL DEFAULT false,
    reverse_payload JSONB                            -- only set by server-side audit service
);
CREATE UNIQUE INDEX idx_event_seq ON fc_event_log (seq);  -- cursor index for delta feed
CREATE INDEX idx_event_entity ON fc_event_log (entity_uid, entity_type);
CREATE INDEX idx_event_type ON fc_event_log (event_type, entity_type);
CREATE INDEX idx_event_actor ON fc_event_log (actor_uid, occurred_at DESC);
CREATE INDEX idx_event_occurred ON fc_event_log (occurred_at DESC);

-- User preferences (auto-approve toggle, UI settings, etc.)
CREATE TABLE fc_user_preference (
    user_uid        UUID NOT NULL REFERENCES fc_user(user_uid) ON DELETE CASCADE,
    key             VARCHAR(100) NOT NULL,
    value           JSONB NOT NULL,
    PRIMARY KEY (user_uid, key)
);

-- AI usage tracking (token counter, cost estimator)
CREATE TABLE fc_ai_usage (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_uid        UUID NOT NULL REFERENCES fc_user(user_uid),
    provider        VARCHAR(20) NOT NULL,
    model           VARCHAR(100),
    input_tokens    INT NOT NULL DEFAULT 0,
    output_tokens   INT NOT NULL DEFAULT 0,
    estimated_cost  NUMERIC(10,6) DEFAULT 0,
    action          VARCHAR(32) NOT NULL,            -- 'chat', 'import_analyze', 'docgen', 'recommend'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_usage_user ON fc_ai_usage (user_uid, created_at DESC);

-- Document templates (semantic section descriptions — AI matches facts at generation time)
CREATE TABLE fc_document_template (
    template_uid    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,           -- "Systems Engineering Plan"
    abbreviation    VARCHAR(20) NOT NULL,             -- "SEP"
    description     TEXT,
    sections        JSONB NOT NULL,                  -- ordered list of {key, title, prompt, guidance}
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_by_uid  UUID REFERENCES fc_user(user_uid),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- sections JSONB example:
-- [
--   {"key": "introduction", "title": "1. Introduction",
--    "prompt": "Provide an overview of the system, its mission, and the purpose of this document",
--    "guidance": "Focus on program identity, mission need, system overview"},
--   {"key": "system_summary", "title": "2. System Summary",
--    "prompt": "Describe the system architecture, interfaces, and key technical characteristics",
--    "guidance": "Focus on system design, interfaces, technical specs"},
--   ...
-- ]
-- NO node mapping. NO tag mapping. AI scores fact relevance at generation time.


-- ═══════════════════════════════════════════════════════════
-- TIER 2: Workflow tables
-- ═══════════════════════════════════════════════════════════

CREATE TABLE fc_signature (
    signature_uid   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_uid        UUID NOT NULL REFERENCES fc_node(node_uid),
    signed_by_uid   UUID NOT NULL REFERENCES fc_user(user_uid),
    signed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    fact_count      INT NOT NULL DEFAULT 0,
    note            TEXT,
    expires_at      TIMESTAMPTZ                     -- optional signature expiration
);
CREATE INDEX idx_sig_node ON fc_signature (node_uid);
CREATE INDEX idx_sig_signer ON fc_signature (signed_by_uid);

CREATE TABLE fc_import_session (
    session_uid        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_node_uid   UUID NOT NULL REFERENCES fc_node(node_uid),
    source_filename    VARCHAR(500) NOT NULL,
    source_hash        VARCHAR(64) NOT NULL,
    source_s3_key      VARCHAR(500),                -- S3 location of uploaded file
    granularity        VARCHAR(20) NOT NULL DEFAULT 'standard'
                       CHECK (granularity IN ('brief','standard','exhaustive')),
    effective_date     DATE NOT NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','analyzing','staged','proposed','approved','rejected','failed')),
    staged_facts_s3    VARCHAR(500),                -- S3 key for staged facts JSON
    error_message      TEXT,
    created_by_uid     UUID REFERENCES fc_user(user_uid),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at       TIMESTAMPTZ
);
CREATE INDEX idx_import_program ON fc_import_session (program_node_uid);
CREATE INDEX idx_import_hash ON fc_import_session (source_hash);

CREATE TABLE fc_fact_comment (
    comment_uid        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_uid        UUID NOT NULL REFERENCES fc_fact_version(version_uid),
    parent_comment_uid UUID REFERENCES fc_fact_comment(comment_uid),
    comment_type       VARCHAR(20) NOT NULL DEFAULT 'comment'
                       CHECK (comment_type IN ('comment','challenge','resolution')),
    body               TEXT NOT NULL,
    created_by_uid     UUID REFERENCES fc_user(user_uid),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at        TIMESTAMPTZ,
    resolved_by_uid    UUID REFERENCES fc_user(user_uid)
);
CREATE INDEX idx_comment_version ON fc_fact_comment (version_uid);


-- ═══════════════════════════════════════════════════════════
-- TIER 3: Peripheral tables
-- ═══════════════════════════════════════════════════════════

CREATE TABLE fc_feedback (
    feedback_uid    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category        VARCHAR(64) NOT NULL DEFAULT 'other',
    display_name    VARCHAR(64) NOT NULL,
    body            TEXT NOT NULL,
    source          VARCHAR(8) NOT NULL DEFAULT 'web',
    ip_hash         VARCHAR(64),
    status          VARCHAR(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','in_progress','delivered','deleted')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ,
    closed_by_uid   UUID REFERENCES fc_user(user_uid)
);
CREATE INDEX idx_feedback_status ON fc_feedback (status, created_at DESC);

-- NOTE: fc_feedback_event table removed — feedback history stored in fc_event_log
-- with entity_type = 'feedback'. One event log table for all audit trails.


-- ═══════════════════════════════════════════════════════════
-- System tables
-- ═══════════════════════════════════════════════════════════

-- NOTE: fc_rate_limit table removed — rate limiting handled entirely by Redis
-- (INCR + EXPIRE pattern, no table growth, no cleanup needed)

CREATE TABLE fc_system_config (
    key             VARCHAR(100) PRIMARY KEY,
    value           JSONB NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by_uid  UUID REFERENCES fc_user(user_uid)
);
```

### 4.3 Schema Design Decisions

**No `fc_undo_log` table.** Undo is computed from `fc_event_log.reverse_payload`, which is set server-side at event recording time. No public endpoint to inject arbitrary payloads. This eliminates v1's most dangerous vulnerability (U-SEC-01).

**No `fc_ownership` table.** Replaced entirely by `fc_node_permission` which proved to be the correct abstraction in v1.

**`node_depth` computed on write.** When a node is created or moved, `node_depth` is set by counting ancestors. This eliminates the N+1 depth-walk query in v1's `factCreate`.

**`UNIQUE (user_uid, node_uid, revoked_at)`.** PostgreSQL treats NULLs as distinct in unique constraints, so `(user_A, node_B, NULL)` can coexist with `(user_A, node_B, '2026-03-01')`. This fixes v1's inability to revoke and re-grant permissions.

**`published_at` set on ALL publish paths.** The schema comment explicitly documents this requirement. The `facts/` service enforces it in the single state-transition function.

**`search_vector` is a generated column.** PostgreSQL maintains the tsvector automatically — no trigger, no manual update. Always in sync.

**`reverse_payload` on events.** The audit module computes the undo data at event-creation time from the current state. This means the undo payload is always consistent with the state that existed when the action occurred.

**`fc_event_log.seq` is a BIGINT IDENTITY.** UUIDs are not monotonic and timestamps can have ties. The `seq` column provides a guaranteed-unique, gap-free, monotonic cursor for Advana's delta feed. Apigee passes `?cursor=47` and gets everything after seq 47.

**No `fc_rate_limit` table.** Rate limiting handled entirely by Redis (`INCR` + `EXPIRE`). No table growth, no cleanup cron, no stale data.

**No `fc_feedback_event` table.** Feedback history merged into `fc_event_log` as `entity_type = 'feedback'`. One audit trail for everything.

**`fc_document_template.sections` uses semantic prompts, not node mappings.** Section definitions describe WHAT the section is about (prompt + guidance text), not WHERE the facts live in the taxonomy. The AI scores each fact's relevance to each section at generation time. This means: taxonomy restructuring never breaks document generation, the same fact can appear in different document types for different reasons, and new document types are created via admin UI without code changes.

**`fc_user_preference` is a flexible key-value store.** Rather than adding a column to `fc_user` for every preference (auto-approve toggle, UI theme, default view, etc.), preferences are stored as key-value pairs. New preferences never require a schema migration.

**`fc_ai_usage` enables per-user cost visibility.** Every AI call logs input/output tokens and estimated cost. Users see their own spend in Settings. Admins see aggregate spend across all users. The `action` column distinguishes chat vs. import vs. docgen spending.

### 4.4 Advana/Jupiter API Compatibility

Advana uses Apigee (Google's API gateway) as its data mesh. artiFACT publishes a standard REST API with an OpenAPI 3.0 spec. Advana's Apigee instance discovers the spec and pulls data through it. artiFACT never pushes to Advana — Advana pulls from us.

**Standard entity endpoints** (auto-generated OpenAPI spec at `/api/v1/openapi.json`):

```
GET  /api/v1/nodes                          ← Full taxonomy tree
GET  /api/v1/nodes/{uid}/facts              ← Facts under a node
GET  /api/v1/facts?state=published          ← All published facts
GET  /api/v1/facts/{uid}/versions           ← Version history
GET  /api/v1/signatures                     ← Signature records
GET  /api/v1/audit/events                   ← Full audit trail
POST /api/v1/facts/search                   ← Full-text search
```

**Data sync endpoints** (for Advana integration and emergency data export):

```
GET  /api/v1/sync/full                      ← Full dump of all entities (emergency export)
GET  /api/v1/sync/changes?cursor={seq}      ← Delta feed (incremental sync)
```

**Delta feed design** — uses `fc_event_log.seq` (BIGINT IDENTITY, monotonic) as the cursor:

```
GET /api/v1/sync/changes?cursor=0&limit=500

Response:
{
  "changes": [
    {
      "seq": 1,                              // monotonic cursor — never reused, never gaps
      "occurred_at": "2026-03-28T15:30:00Z",
      "change_type": "version.approved",     // what happened
      "entity_type": "fact",
      "entity_uid": "def-456",
      "snapshot": {                           // current state of the entity AT THIS MOMENT
        "fact_uid": "def-456",
        "node_uid": "abc-123",
        "sentence": "System owner is Department of the Navy.",
        "state": "published",
        "published_at": "2026-03-28T15:30:00Z",
        "is_retired": false,
        ...
      }
    },
    ...
  ],
  "cursor": 47,                              // seq of last entry — pass as ?cursor= next call
  "has_more": true                            // false when caught up
}

Pagination: call repeatedly with cursor= until has_more=false.
Deduplication: if same entity changed 5 times since last cursor, ALL 5 changes
  returned (Advana sees the full history, not just the latest).
Tombstones: retired/deleted entities appear with is_retired=true and state=retired
  (they don't disappear from the feed).
Ordering: guaranteed monotonic by seq — no timestamp ties, no gaps.
```

**Full dump** — the "shutting down tomorrow" endpoint:

```
GET /api/v1/sync/full

Response:
{
  "exported_at": "2026-03-28T16:00:00Z",
  "schema_version": "2.0",
  "nodes": [...],           // all nodes with hierarchy
  "facts": [...],           // all facts with current version
  "versions": [...],        // all versions (full history)
  "signatures": [...],      // all signature records
  "users": [...],           // display_name + role (no PII beyond what Advana needs)
  "templates": [...],       // document templates
  "events": [...],          // full audit trail
  "cursor": 4821            // current max seq — Advana can start delta feed from here
}
```

**Authentication**: service account (`global_role = 'viewer'`) with a scoped API key (`scopes: ["read", "sync"]`). Authenticates via `Authorization: Bearer af_svc_...` header. Rate limited separately from interactive users (1000 req/hr vs 150 for humans). The API key is provisioned by an admin and given to the Advana integration team.

All endpoints return JSON with consistent pagination (`?cursor=` for sync, `?offset=&limit=` for browse), filtering (`?state=published&node_uid=...`), and sorting (`?sort=created_at&order=desc`).

---

## 5. Authentication and Authorization

### 5.1 CAC Authentication Flow

```
[User's browser]
    │
    │  CAC certificate presented
    ▼
[COSMOS Netskope / CNAP]
    │
    │  SAML assertion with CAC DN, EDIPI, email
    ▼
[artiFACT FastAPI middleware]
    │
    │  1. Extract EDIPI + DN from SAML assertion
    │  2. Lookup/create fc_user record
    │  3. Set session cookie (signed, httponly, secure, samesite=strict)
    │  4. Cache permissions in Redis (TTL 5 min)
    ▼
[artiFACT API handlers]
    │
    │  Every request: validate session → resolve permissions → proceed or 403
    ▼
[Response]
```

### 5.2 Permission Resolution (fixing all 4 global_role bugs)

```python
# kernel/permissions.py — the ONE place permissions are resolved

async def resolve_role(user: User, node_uid: UUID) -> str:
    """
    Returns the effective role for a user on a specific node.
    Checks: explicit grant on this node → inherited grant from ancestor → global_role.
    The HIGHEST role wins.
    """
    # 1. Check Redis cache first
    cache_key = f"perm:{user.user_uid}:{node_uid}"
    cached = await redis.get(cache_key)
    if cached:
        return cached

    # 2. Get all active grants for this user (ONE query, cached per-request)
    grants = await get_user_grants(user.user_uid)  # {node_uid: role}

    # 3. Get ancestor chain for this node (ONE CTE query, cached per-request)
    ancestors = await get_ancestors(node_uid)  # [node_uid, parent_uid, grandparent_uid, ...]

    # 4. Walk ancestors, find highest grant
    best_role = user.global_role
    for ancestor_uid in ancestors:
        if ancestor_uid in grants:
            if role_gte(grants[ancestor_uid], best_role):
                best_role = grants[ancestor_uid]

    # 5. Cache for 5 minutes
    await redis.set(cache_key, best_role, ex=300)
    return best_role


async def can(user: User, action: str, node_uid: UUID) -> bool:
    """Single entry point for all permission checks."""
    role = await resolve_role(user, node_uid)
    return role_gte(role, REQUIRED_ROLES[action])

# REQUIRED_ROLES maps action → minimum role
REQUIRED_ROLES = {
    'read':         'viewer',
    'contribute':   'contributor',
    'approve':      'subapprover',
    'sign':         'signatory',
    'manage_node':  'approver',
    'admin':        'admin',
}
```

Every module calls `kernel.permissions.can()`. No module ever reads `user.global_role` directly. This fixes Q-AUTH-02, I-SEC-05, F-AUTH-01, B-AUTH-01 — all four instances of the v1 global_role gate bug — permanently.

### 5.3 CSRF Protection

FastAPI middleware automatically validates a `X-CSRF-Token` header on every state-changing request (POST/PUT/PATCH/DELETE). The token is set as a signed cookie on login and injected into JS via a meta tag. ONE implementation, ZERO per-module variation. This eliminates all 5 CSRF bugs from v1.

### 5.4 API Key Authentication (for Advana/machine clients)

```sql
CREATE TABLE fc_api_key (
    key_uid         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_uid        UUID NOT NULL REFERENCES fc_user(user_uid) ON DELETE CASCADE,
    key_hash        VARCHAR(64) NOT NULL,           -- SHA-256 of the key
    key_prefix      VARCHAR(8) NOT NULL,            -- for display: "af_live_Ab..."
    label           VARCHAR(100),
    scopes          JSONB DEFAULT '["read"]'::jsonb, -- ['read'], ['read','write'], ['admin']
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ
);
```

Machine clients send `Authorization: Bearer af_live_AbCd...`. The middleware hashes the key, looks up `fc_api_key`, and authenticates as the associated user. Scopes limit what the key can do (read-only for Advana).

---

## 6. Per-User AI Integration (BYOK)

### 6.1 Key Storage

Users provide their own GenAI API keys through the settings page. Keys are encrypted at rest using AES-256-GCM with a master key stored in AWS Secrets Manager.

```python
# kernel/crypto.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

MASTER_KEY = get_secret('ARTIFACT_AI_KEY_MASTER')  # from Secrets Manager

def encrypt_api_key(plaintext: str) -> bytes:
    nonce = os.urandom(12)
    ct = AESGCM(MASTER_KEY).encrypt(nonce, plaintext.encode(), None)
    return nonce + ct  # 12-byte nonce + ciphertext

def decrypt_api_key(blob: bytes) -> str:
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(MASTER_KEY).decrypt(nonce, ct, None).decode()
```

### 6.2 Provider Abstraction

```python
# kernel/ai_provider.py

class AIProvider:
    """Single abstraction for all LLM calls. Fixes v1's 5 duplicated curl wrappers."""

    async def complete(
        self,
        user: User,
        messages: list[dict],
        *,
        response_format: str | None = None,    # 'json_object' or None
        stream: bool = False,
        timeout: int = 120,
        max_tokens: int = 4096,
    ) -> str | AsyncIterator[str]:
        key_record = await get_user_ai_key(user.user_uid)
        if not key_record:
            raise HTTPException(400, "No AI API key configured. Add one in Settings.")

        plaintext_key = decrypt_api_key(key_record.encrypted_key)
        provider = key_record.provider

        if provider == 'openai':
            return await self._call_openai(plaintext_key, messages, ...)
        elif provider == 'anthropic':
            return await self._call_anthropic(plaintext_key, messages, ...)
        elif provider == 'azure_openai':
            return await self._call_azure(plaintext_key, messages, ...)
        elif provider == 'bedrock':
            # No user key needed — uses IAM role on COSMOS ECS task
            # CUI stays within GovCloud boundary (IL-4/5 authorized)
            return await self._call_bedrock(messages, ...)
```

All modules (`ai_chat/`, `import_pipeline/`, `export/`, `queue/` recommend) call `AIProvider.complete()`. ONE implementation. Provider switching is a user-level setting, not a code change.

### 6.3 Token Counting (fixing v1 A-SEC-01)

```python
# ai_chat/prompt_builder.py

def build_system_prompt(facts: list[str], max_tokens: int = 6000) -> str:
    """Build system prompt with proper token counting, never byte truncation."""
    header = SYSTEM_INSTRUCTIONS  # ~500 tokens
    token_budget = max_tokens - count_tokens(header) - 200  # headroom

    included = []
    used = 0
    for fact in facts:
        fact_tokens = count_tokens(fact)
        if used + fact_tokens > token_budget:
            break
        included.append(fact)
        used += fact_tokens

    return header + "\n\nFACTS:\n" + "\n".join(included)

# Returns actual count loaded, not total available
# UI shows: "Loaded 47 of 150 facts (token limit)"
```

---

## 7. Background Task Architecture

Long-running operations (import analysis, DOCX generation) must not block web workers. v1 locked a PHP worker for up to 10 minutes per import.

### 7.1 Task Queue

Use **Celery** with **Redis** as the broker (all FOSS). A separate worker container runs tasks asynchronously.

```
[Web container]  →  Redis queue  →  [Worker container]
     │                                     │
     │  POST /api/v1/import/analyze        │  Runs AI calls, extraction
     │  Returns task_id immediately        │  Updates fc_import_session.status
     │                                     │  Sends SSE progress events
     ▼                                     ▼
[Client polls]                        [Task complete]
GET /api/v1/tasks/{task_id}           Sets status = 'staged'
```

### 7.2 SSE Progress

```python
# import_pipeline/router.py

@router.get("/import/sessions/{uid}/progress")
async def stream_progress(uid: UUID, user: User = Depends(get_current_user)):
    """SSE endpoint for real-time progress updates."""
    async def event_stream():
        async for event in subscribe(f"import:{uid}"):
            yield f"data: {event.json()}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 8. Build → Test → Prod Pipeline

### 8.1 Three Environments

| Environment | Purpose | COSMOS Account | Database | AI Keys |
|-------------|---------|----------------|----------|---------|
| **Build** (dev) | Active development, local testing | Developer's personal COSMOS product account | Local PostgreSQL (Docker) or small RDS | Developer's own keys |
| **Test** (staging) | Integration testing, demo, QA | Shared team COSMOS product account | RDS (separate instance, seeded with sanitized prod data) | Test keys with spending caps |
| **Prod** | Production | Dedicated COSMOS product account with IATT/ATO | RDS Multi-AZ with automated backups, PITR | User-provided keys |

### 8.2 Infrastructure as Code

Each environment is defined by a Terraform workspace:

```
terraform/
├── modules/
│   ├── vpc/main.tf            ← VPC, subnets, security groups
│   ├── rds/main.tf            ← PostgreSQL RDS + parameter groups
│   ├── ecs/main.tf            ← ECS cluster, task definitions, services
│   ├── s3/main.tf             ← Buckets for uploads, exports, backups
│   ├── redis/main.tf          ← ElastiCache Redis cluster
│   ├── ecr/main.tf            ← Container registry
│   └── alb/main.tf            ← Application Load Balancer
│
├── environments/
│   ├── build/
│   │   ├── main.tf            ← module calls with build-specific vars
│   │   └── terraform.tfvars   ← instance sizes: db.t3.micro, 1 task, etc.
│   ├── test/
│   │   ├── main.tf
│   │   └── terraform.tfvars   ← instance sizes: db.t3.small, 2 tasks
│   └── prod/
│       ├── main.tf
│       └── terraform.tfvars   ← instance sizes: db.r6g.large, Multi-AZ, 4 tasks, read replica
```

### 8.3 CI/CD Pipeline

```yaml
# .gitlab-ci.yml

stages:
  - lint
  - test
  - build
  - deploy-test
  - smoke-test
  - deploy-prod

lint:
  stage: lint
  script:
    - ruff check .                    # Python linting
    - mypy artiFACT/                  # Type checking
    - ruff format --check .           # Formatting

test:
  stage: test
  services:
    - postgres:16
    - redis:7
  variables:
    DATABASE_URL: "postgresql://test:test@postgres/artifact_test"
    REDIS_URL: "redis://redis:6379"
  script:
    - alembic upgrade head            # Run migrations
    - pytest --cov=artiFACT --cov-report=xml -x
    - coverage report --fail-under=80  # Enforce 80% coverage minimum

build:
  stage: build
  script:
    - docker build -t $ECR_REPO:$CI_COMMIT_SHA -f docker/Dockerfile .
    - docker build -t $ECR_REPO:$CI_COMMIT_SHA-worker -f docker/Dockerfile.worker .
    - docker push $ECR_REPO:$CI_COMMIT_SHA
    - docker push $ECR_REPO:$CI_COMMIT_SHA-worker

deploy-test:
  stage: deploy-test
  environment: test
  script:
    - cd terraform/environments/test
    - terraform init
    - terraform apply -auto-approve -var="image_tag=$CI_COMMIT_SHA"
    - alembic upgrade head            # Migrate test DB

smoke-test:
  stage: smoke-test
  script:
    - pytest tests/smoke/ --base-url=$TEST_URL

deploy-prod:
  stage: deploy-prod
  environment: prod
  when: manual                        # Requires human approval
  only:
    - main
  script:
    - cd terraform/environments/prod
    - terraform init
    - terraform plan -var="image_tag=$CI_COMMIT_SHA" -out=plan.tfplan
    - terraform apply plan.tfplan
    - alembic upgrade head            # Migrate prod DB
```

### 8.4 Promotion Flow

```
Developer pushes to feature branch
    │
    ▼
[CI: lint + test + build]
    │
    │  Passes → Docker image pushed to ECR
    ▼
Merge to main
    │
    ▼
[CI: deploy-test automatically]
    │
    │  Migrations run on test DB
    │  Smoke tests pass
    ▼
[Manual gate: deploy-prod]
    │
    │  Terraform plan reviewed
    │  Approved by PM or lead
    ▼
[CI: deploy-prod]
    │
    │  Blue/green deployment via ECS
    │  Migrations run on prod DB
    │  Health checks pass → traffic shifts
    ▼
Production live
```

### 8.5 Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "add fc_fact_comment.parent_comment_uid"

# Review the generated migration in migrations/versions/
# Edit if needed (autogenerate is a starting point, not gospel)

# Apply locally
alembic upgrade head

# Downgrade (for testing rollback)
alembic downgrade -1
```

Every migration is forward-compatible: additive changes (new columns with defaults, new tables, new indexes) deploy safely with zero downtime. Destructive changes (drop column, rename) use a two-phase approach: (1) stop writing to old column, (2) deploy, (3) next release drops the column.

### 8.6 Snapshots and Backup

**RDS automated backups**: PITR (point-in-time recovery) with 35-day retention in prod, 7-day in test.

**S3 versioning**: Enabled on all buckets. Deleted objects recoverable for 30 days.

**Schema-level snapshots** (for data seeding / demo reset):

```bash
# Export sanitized snapshot
pg_dump --no-owner --no-acl -Fc artifact_prod > snapshot_$(date +%Y%m%d).dump

# Restore to test
pg_restore --no-owner --clean --if-exists -d artifact_test snapshot_20260328.dump
```

---

## 9. Admin Strategy

### 9.1 Admin Roles

| Role | Capabilities |
|------|-------------|
| **System Admin** (`global_role = 'admin'`) | Full access to everything. User management, module toggles, system config, data export, snapshot triggers. Limited to 2-3 people. |
| **Program Admin** (per-node `approver` grant on a trunk) | Manages their program's taxonomy subtree, approves facts, grants permissions within their scope. Cannot see other programs' data in admin views. |
| **Help Desk** (new role: `support`) | Read-only access to all data + feedback management. Cannot approve, sign, or modify facts. |

### 9.2 Admin Module Endpoints

```
GET  /admin/dashboard              ← System health, user count, fact count, error rate
GET  /admin/users                  ← User list with role badges, last login, active grants
POST /admin/users/{uid}/role       ← Change global role
POST /admin/users/{uid}/deactivate ← Soft deactivate (preserves audit trail)
GET  /admin/modules                ← Module health status (DB connectivity, Redis, S3)
POST /admin/modules/{name}/toggle  ← Enable/disable a module (e.g., disable feedback)
GET  /admin/config                 ← System configuration (feature flags, rate limits)
POST /admin/config/{key}           ← Update config value
GET  /admin/audit                  ← Event log browser with filtering
GET  /admin/export/schema          ← Download current schema DDL
POST /admin/snapshot/trigger       ← Trigger a pg_dump to S3
GET  /admin/cache/stats            ← Redis hit rate, key count
POST /admin/cache/flush            ← Flush permission cache (after grant changes)
```

### 9.3 Feature Flags

```python
# Stored in fc_system_config, cached in Redis

FEATURE_FLAGS = {
    'module.feedback.enabled':      True,
    'module.presentation.enabled':  True,
    'module.ai_chat.enabled':       True,
    'module.import.enabled':        True,
    'module.export.enabled':        True,
    'ai.easter_eggs.enabled':       False,  # Off by default for formal evals
    'security.rate_limit.ai':       150,    # requests/hour/user
    'security.rate_limit.import':   10,     # imports/hour/user
    'security.rate_limit.export':   30,     # exports/hour/user
    'content.profanity_filter':     True,
    'content.max_document_chars':   50000,  # raised from v1's 12,500
}
```

### 9.4 Monitoring and Alerting

```python
# Every module exposes a health check

@router.get("/health")
async def health():
    checks = {
        "database": await check_db(),
        "redis": await check_redis(),
        "s3": await check_s3(),
    }
    status = "healthy" if all(checks.values()) else "degraded"
    return {"status": status, "checks": checks}
```

CloudWatch alarms fire on: error rate > 1%, response time p95 > 2s, task queue depth > 50, disk > 80%. Grafana dashboards visualize request rate, latency, error rate, active users, and AI cost per user.

---

## 10. Security Posture

Every v1 finding is addressed architecturally — not patched individually:

| v1 Pattern | v2 Fix |
|------------|--------|
| API key in plaintext | AWS Secrets Manager for system secrets, AES-256-GCM for user keys |
| No CSRF on 5 endpoints | Global CSRF middleware — all POST/PUT/PATCH/DELETE validated |
| global_role gate (4 modules) | Single `kernel.permissions.can()` — never read global_role directly |
| Descendant CTE duplicated 5× | Single `kernel.permissions.get_descendants()` |
| OpenAI wrapper duplicated 5× | Single `kernel.ai_provider.AIProvider` |
| No transactions on multi-step writes | FastAPI dependency that wraps handlers in transactions |
| esc() missing single-quote (4 copies) | Server-rendered HTML via Jinja2 with autoescape=True |
| Undo injection via public endpoint | No public undo/record — reverse_payload computed server-side only |
| Unauthenticated export | Global auth middleware — all routes require auth by default, opt-out for public |
| No CSP headers | Security headers middleware: CSP, X-Frame-Options, HSTS, X-Content-Type-Options |
| No continuous auth (v1 sessions never re-checked) | Session re-validation every 15 min + anomaly-triggered auto-expire |
| No read-access logging | Data-access events logged for export, AI chat, sync endpoints |
| No anomaly detection | Rule-based anomaly detector with auto-session-expire |
| Containers run as root | Non-root `appuser` in all Dockerfiles |

### 10.4 Zero Trust Compliance

The architecture maps to all seven DoD ZT Reference Architecture v2.0 pillars:

| Pillar | Owner | Implementation |
|--------|-------|---------------|
| **1. User** | artiFACT | CAC MFA via COSMOS SAML. Session re-validated every 15 min. Anomaly triggers force re-auth. Per-node RBAC with least privilege. API keys for NPEs. |
| **2. Device** | COSMOS | Netskope/CNAP handles device posture. artiFACT inherits. |
| **3. Network** | COSMOS | CNAP zero trust network access. Private VPC subnets. ALB-only ingress. No VPN. |
| **4. App/Workload** | artiFACT | Immutable non-root containers. Auth on every request. CSRF on all writes. Pydantic input validation. Jinja2 autoescape. SBOM + pip-audit in CI. Iron Bank images in prod. |
| **5. Data** | artiFACT | Classification field per fact. AES-256-GCM for AI keys. CUI markings auto-injected in docgen. Read-access logging on data-exfiltration-relevant endpoints. |
| **6. Visibility** | Shared | Structured JSON logs via structlog → CloudWatch → CSSP SIEM. fc_event_log for all mutations. Read-access log for exports/AI. Anomaly detection rules. Grafana dashboards. |
| **7. Automation** | artiFACT | CI/CD pipeline. Feature flags. Auto-session-expire on anomaly. Auto-CUI-marking on docgen. Celery beat for data retention. |

### 10.1 Graceful Degradation

Every external dependency has a fallback path. The app degrades but does not crash.

```
Redis down:
  Permission resolver → falls back to direct PostgreSQL query (slower, ~50ms vs ~1ms)
  Rate limiter → skips rate limiting, logs warning (allow rather than crash)
  Session store → falls back to signed JWT cookie (stateless, no revocation until Redis recovers)
  Badge counter → returns -1 (UI shows "—" instead of count)
  Tree cache → direct DB query per request

S3 (MinIO) down:
  Import upload → returns 503 "File storage temporarily unavailable"
  Export download → returns 503 with retry-after header
  Snapshot trigger → fails with clear admin error
  Browse / Edit / Sign / Queue → fully functional (no S3 dependency)
  AI Chat → fully functional (facts come from PostgreSQL, not S3)

External LLM API down:
  AI Chat → returns "AI service unavailable. Your facts are unaffected."
  Import analysis → task fails, session status = 'failed', user can retry
  Docgen → task fails, user can retry
  All non-AI features → fully functional

PostgreSQL down:
  Everything fails (this is the source of truth — no workaround)
  Health check returns {"status": "unhealthy", "checks": {"database": false}}
  CloudWatch alarm fires immediately
```

Implementation pattern:
```python
# kernel/cache.py
async def cached_or_query(cache_key: str, ttl: int, query_fn):
    """Try Redis first, fall back to DB query on Redis failure."""
    try:
        cached = await redis.get(cache_key)
        if cached:
            return deserialize(cached)
    except (ConnectionError, TimeoutError):
        structlog.get_logger().warning("redis_unavailable", key=cache_key)
        # Fall through to DB query
    
    result = await query_fn()
    
    try:
        await redis.set(cache_key, serialize(result), ex=ttl)
    except (ConnectionError, TimeoutError):
        pass  # Cache write failed — that's fine, DB is source of truth
    
    return result
```

### 10.2 Secrets Rotation

**User AI keys** (encrypted with master key in Secrets Manager):
```
Rotation trigger: suspected master key compromise, annual rotation policy, or admin-initiated

1. Generate new master key in AWS Secrets Manager (new version)
2. Run rotation script:
   python scripts/rotate_master_key.py \
     --old-key-arn arn:aws-us-gov:secretsmanager:...:old \
     --new-key-arn arn:aws-us-gov:secretsmanager:...:new
   
   Script logic:
     FOR each row IN fc_user_ai_key:
       plaintext = decrypt(row.encrypted_key, old_master_key)
       row.encrypted_key = encrypt(plaintext, new_master_key)
       db.commit()  # per-row commit so partial failure is recoverable
     
3. Update ECS task definition env var AI_KEY_MASTER to new ARN
4. Redeploy (blue/green, zero downtime)
5. Delete old key version from Secrets Manager after 7 days
```

**Database password**:
```
1. Generate new password
2. Update RDS master password: aws rds modify-db-instance --master-user-password NEW
3. Update ECS task definition DATABASE_URL with new password
4. Redeploy
```

**Session signing secret** (SECRET_KEY):
```
1. Generate new secret
2. Update ECS task definition
3. Redeploy
4. All existing sessions invalidated (users must re-login via CAC)
   This is acceptable — session TTL is 8 hours anyway
```

### 10.3 Data Retention

| Table | Retention | Mechanism |
|-------|-----------|-----------|
| `fc_event_log` | 2 years in DB, then archived to S3 | Nightly Celery beat task |
| `fc_feedback` + events | 1 year | Nightly task: archive closed items older than 1yr |
| `fc_import_session` | 90 days | Nightly task: delete completed/failed sessions |
| S3 `imports/` prefix | 30 days | S3 lifecycle rule |
| S3 `exports/` prefix | 24 hours | S3 lifecycle rule |
| S3 `snapshots/` prefix | 1 year | S3 lifecycle rule |
| Redis session keys | 8 hours | TTL on key |
| Redis permission cache | 5 minutes | TTL on key |
| Redis badge counts | 60 seconds | TTL on key |

Implementation:
```python
# kernel/background.py — Celery beat schedule
beat_schedule = {
    'archive-old-events': {
        'task': 'artiFACT.modules.audit.tasks.archive_old_events',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
    'purge-old-imports': {
        'task': 'artiFACT.modules.import_pipeline.tasks.purge_old_sessions',
        'schedule': crontab(hour=3, minute=30),
    },
    'archive-old-feedback': {
        'task': 'artiFACT.modules.feedback.tasks.archive_old_feedback',
        'schedule': crontab(hour=4, minute=0),
    },
}
```

---

## 11. Migration Path from v1

### Phase 1: Schema Migration (Week 1-2)
1. Stand up PostgreSQL in build environment
2. Run Alembic migrations to create v2 schema
3. Write a one-time Python script that reads the MySQL dump and inserts into PostgreSQL, mapping CHAR(36) UIDs to native UUID, fixing NULL `published_at_utc`, populating `node_depth`, generating `search_vector`

### Phase 2: Core Modules (Week 3-6)
1. `kernel/` — auth, permissions, models, events
2. `taxonomy/` — node CRUD + tree rendering
3. `facts/` — fact CRUD + versioning + state machine
4. `audit/` — event log + undo (server-side only)
5. `auth_admin/` — user management + grants

### Phase 3: Workflow Modules (Week 7-10)
1. `queue/` — approval workflows
2. `signing/` — signature lifecycle
3. `search/` — full-text search
4. `export/` — fact sheets + docgen (background worker)

### Phase 4: AI + Import (Week 11-14)
1. `ai_chat/` — corpus-grounded Q&A with BYOK
2. `import_pipeline/` — document ingestion with background worker

### Phase 5: Peripherals + Polish (Week 15-16)
1. `feedback/` — feedback collection
2. `presentation/` — briefing mode
3. `admin/` — system dashboard

### Phase 6: Production Deployment (Week 17-18)
1. Terraform apply to COSMOS prod account
2. Data migration from v1 MySQL
3. CAC integration testing
4. Load testing
5. Go live

---

## 12. Cost Estimate (COSMOS only)

| Resource | Spec | Estimated Monthly |
|----------|------|------------------|
| ECS Fargate (web) | 2 tasks × 0.5 vCPU × 1GB | ~$30 |
| ECS Fargate (worker) | 1 task × 0.25 vCPU × 0.5GB | ~$8 |
| RDS PostgreSQL | db.t3.small, 20GB, Multi-AZ (prod only) | ~$50 (single) / ~$100 (Multi-AZ) |
| ElastiCache Redis | cache.t3.micro | ~$12 |
| S3 | <10GB with versioning | ~$1 |
| ALB | Application Load Balancer | ~$20 |
| ECR | Container registry | ~$1 |
| CloudWatch | Logs + metrics | ~$5 |
| **Total (test)** | | **~$75/mo** |
| **Total (prod, Multi-AZ)** | | **~$175/mo** |

All software is $0. The only cost is COSMOS AWS consumption.
