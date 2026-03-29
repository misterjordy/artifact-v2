# Sprint 9: Export + Sync + Document Templates

**Depends on**: Sprint 7 (AI provider), Sprint 3 (facts core)
**Module**: `modules/export/` (7 + 2 template components)

## Definition of Success
- ALL export routes require auth (regression: v1 D-SEC-01 / SEC-04)
- Factsheet: TXT, JSON, NDJSON, CSV formats
- DOCX generation as background task with SSE progress
- Files in S3 with signed URL (24hr expiry, user-bound — regression: v1 D-SEC-02)
- Two-pass section assignment (regression: v1 D-LOW-01 bias)
- Document templates stored in DB (admin-managed, semantic prompts, no node mapping)
- "Views" feature: pick a template → see which facts AI would assign per section (prefilter only)
- `GET /api/v1/sync/full` returns complete data dump
- `GET /api/v1/sync/changes?cursor={seq}` returns delta feed with entity snapshots
- Delta feed uses monotonic `seq` cursor (BIGINT), not timestamps
- Advana service account can authenticate via API key and pull data
- All export tests pass

## Components
### factsheet.py — Streaming export, four formats, no internal UUIDs in output
### docgen/orchestrator.py — Celery task: prefilter → synthesize → build DOCX → S3
### docgen/prefilter.py — AI affinity scoring across ALL sections simultaneously
### docgen/synthesizer.py — Streaming AI synthesis per section
### docgen/docx_builder.py — python-docx assembly with template styles
If any fact version in the document has `classification` containing "CUI" (or any CUI variant: CUI//SP-CTI, CUI//SP-EXPT, etc.), the generated DOCX automatically includes:
- Header on every page: "CUI" or "CONTROLLED // [category]"
- Footer on every page: matching CUI banner + distribution statement
- Cover page classification marking
Classification is read from `fc_fact_version.classification` — if ANY included fact is CUI, the entire document is marked CUI. If all facts are UNCLASSIFIED, no CUI banners are injected.
### download_manager.py — S3 presigned URL, verify user = generator
### sync.py — Full dump + delta feed endpoints
### template_manager.py — CRUD for fc_document_template (admin)
### views.py — Run prefilter only (no synthesis) to show fact→section assignment preview

## Database Migration
Table: `fc_document_template`

## Seed Data: artiFACT Documents Its Own Self

artiFACT ships with a pre-loaded "artiFACT" program in its own taxonomy containing atomic facts about itself — architecture decisions, security controls, capabilities, user roles, data flows. This corpus is the source material for generating artiFACT's own compliance documentation.

### Pre-seeded taxonomy
```
artiFACT (trunk)
├── System Overview
├── Architecture & Design
├── Security Controls
├── Data & Privacy
├── User Roles & Permissions
├── AI Integration
├── Operations & Sustainment
└── Compliance & Authorization
```

### Pre-seeded document templates
```
ConOps (Concept of Operations):
  sections:
    - {key: purpose, title: "1. Purpose", prompt: "Describe the system's purpose and the operational need it addresses", guidance: "Focus on: what problem does the system solve, who uses it, why existing tools are insufficient"}
    - {key: system_overview, title: "2. System Overview", prompt: "Describe the system at a high level — what it does, how users interact with it", guidance: "Focus on: capabilities, user experience, key workflows"}
    - {key: operational_context, title: "3. Operational Context", prompt: "Describe where and how the system operates within the DON enterprise", guidance: "Focus on: hosting environment, network access, organizational relationships"}
    - {key: user_roles, title: "4. User Roles and Responsibilities", prompt: "Describe who uses the system and what each role can do", guidance: "Focus on: role hierarchy, permission model, typical user workflows"}
    - {key: data_flows, title: "5. Data Flows", prompt: "Describe how data moves through the system", guidance: "Focus on: data sources, processing, storage, outputs, external integrations"}
    - {key: security, title: "6. Security Considerations", prompt: "Describe the security posture and compliance framework", guidance: "Focus on: Zero Trust, CAC auth, encryption, CUI handling, ATO status"}

SDD (System Design Document):
  sections:
    - {key: architecture, title: "1. Architecture Overview", prompt: "Describe the system architecture, technology stack, and design patterns", guidance: "Focus on: modular monolith, bounded contexts, API-first, container deployment"}
    - {key: data_design, title: "2. Data Design", prompt: "Describe the database schema, data model, and storage strategy", guidance: "Focus on: PostgreSQL tables, relationships, JSONB patterns, S3 usage"}
    - {key: interface_design, title: "3. Interface Design", prompt: "Describe the API design, authentication, and external integrations", guidance: "Focus on: REST endpoints, OpenAPI spec, Advana sync, SAML/CAC"}
    - {key: security_design, title: "4. Security Design", prompt: "Describe the security architecture in detail", guidance: "Focus on: RBAC, CSRF, encryption, ZT pillars, FIPS, audit logging"}
    - {key: deployment, title: "5. Deployment Architecture", prompt: "Describe how the system is deployed, scaled, and maintained", guidance: "Focus on: Docker, ECS Fargate, RDS, Redis, CI/CD pipeline, blue/green"}
    - {key: testing, title: "6. Test Strategy", prompt: "Describe the testing approach", guidance: "Focus on: test pyramid, coverage targets, CI enforcement, E2E tests"}
```

### How it works
1. During Sprint 3, seed the artiFACT program with ~50-100 atomic facts about itself (pulled from the architecture doc, master reference, and sprint files).
2. During Sprint 9, seed the ConOps and SDD templates above.
3. When someone asks "where's the ConOps?": open artiFACT → select artiFACT program → select ConOps template → click Generate → download DOCX.
4. The generated document is always current because the source facts are maintained in the same system that generates the document.
5. When the architecture changes, update the relevant facts → regenerate → new document reflects the change.

This is the artiFACT thesis in action: the system that replaces documents with atomic facts can generate its own documents from its own atomic facts.

## Advana Delta Feed Design
```
GET /api/v1/sync/changes?cursor=0&limit=500

1. Query: SELECT * FROM fc_event_log WHERE seq > :cursor ORDER BY seq ASC LIMIT :limit
2. For each event, load current snapshot of the referenced entity:
   - entity_type='fact' → join fc_fact + fc_fact_version (current published)
   - entity_type='node' → fc_node
   - entity_type='signature' → fc_signature
   - entity_type='feedback' → fc_feedback
3. Return changes array with seq, change_type, entity snapshot
4. Return cursor = max(seq) from results, has_more = (count == limit)
5. Retired/deleted entities appear with is_retired=true (tombstones, not disappearing)

Service account auth: Authorization: Bearer af_svc_...
Scoped API key with scopes: ["read", "sync"]
Rate limit: 1000 req/hr (separate from interactive users)
```

## Key Tests
```
test_export_requires_auth          (v1 D-SEC-01)
test_download_url_user_bound       (v1 D-SEC-02)
test_two_pass_section_assignment   (v1 D-LOW-01)
test_docgen_runs_as_background_task
test_all_four_formats_valid
test_presigned_url_expires
test_delta_feed_cursor_monotonic
test_delta_feed_returns_entity_snapshots
test_delta_feed_includes_tombstones_for_retired
test_full_dump_includes_all_entity_types
test_full_dump_returns_cursor_for_subsequent_delta
test_document_template_crud
test_views_prefilter_returns_fact_section_assignments
test_service_account_api_key_works
```
