-- seed_corpus_comments.sql
-- Adds contextual comments to artiFACT corpus facts that are potentially
-- disagreeable, highly technical, or contain jargon that needs unpacking.
--
-- Run: docker compose exec -T postgres psql -U artifact -d artifact_db \
--        < artiFACT/scripts/seed_corpus_comments.sql
--
-- Idempotent: skips inserts where the same body already exists on the version.

BEGIN;

-- ============================================================================
-- POTENTIALLY DISAGREEABLE — design decisions a stakeholder might question
-- ============================================================================

-- Advana Jupiter is the downstream data consumer
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9ef38ef2-d0ef-4e22-b513-571db134dd9c', 'comment',
  'artiFACT is the system of truth — it owns fact creation, approval, and versioning. Advana is the system of record for analytics. Data flows one direction: Advana pulls from us via the delta feed. This is standard data engineering — the authoritative source publishes, the consumer subscribes. Two-way sync would create reconciliation conflicts with no clear winner.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9ef38ef2-d0ef-4e22-b513-571db134dd9c' AND body LIKE 'artiFACT is the system of truth%');

-- artiFACT feeds data to Jupiter Advana via a standard REST API
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b222300b-ceb1-48a8-9be9-ecc2cb8b1a81', 'comment',
  'artiFACT publishes; Advana subscribes. The pull-based model means artiFACT has zero dependencies on Advana''s availability or schema. If Advana changes their ingestion pipeline, artiFACT''s API remains stable. This is proper data mesh architecture.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b222300b-ceb1-48a8-9be9-ecc2cb8b1a81' AND body LIKE 'artiFACT publishes%');

-- Documents are not maintained as static files
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8d53dc5c-1a05-4048-b643-b6c3a65b2a3e', 'comment',
  'When a fact changes, every document containing it must reflect the update. Static files diverge the moment a fact is edited. Generating on demand guarantees every document reflects the current approved corpus — no manual sync, no stale versions, no conflicting copies.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8d53dc5c-1a05-4048-b643-b6c3a65b2a3e' AND body LIKE 'When a fact changes%');

-- artiFACT is not a program of record
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '117d9cc7-4e2d-4d7a-86cb-8eb690b35318', 'comment',
  'artiFACT is an internal productivity tool under the Software Acquisition Pathway. Its near-zero sustainment cost and government-labor development model fall below the thresholds requiring program-of-record designation, ACAT categorization, or milestone decisions.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '117d9cc7-4e2d-4d7a-86cb-8eb690b35318' AND body LIKE 'artiFACT is an internal productivity%');

-- When PostgreSQL is down everything fails
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '0e5edfbe-5f6c-4b87-b569-e03e3a096726', 'comment',
  'This is intentional. PostgreSQL is the single source of truth for all fact data. Serving stale or cached data during a database outage risks showing users outdated facts they might sign or approve — that''s worse than an honest error page. RDS Multi-AZ provides automatic failover in under 60 seconds.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '0e5edfbe-5f6c-4b87-b569-e03e3a096726' AND body LIKE 'This is intentional%');

-- CUI training is not enforced by the application
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f94c59e7-11bb-48e8-9f47-6c45e5592fa1', 'comment',
  'CUI training is a command responsibility per DoDI 5200.48, not an application function. artiFACT enforces CUI markings on data; training compliance is tracked by each user''s organization. The login splash screen includes a certification statement as a procedural control.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f94c59e7-11bb-48e8-9f47-6c45e5592fa1' AND body LIKE 'CUI training is a command%');

-- artiFACT does not independently verify device posture
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '165864cf-248a-47e7-9b48-1bcf587f09fb', 'comment',
  'COSMOS provides device posture assessment at the network perimeter via Netskope and CNAP. Duplicating this check at the application layer would add complexity without improving security posture — the network already blocks non-compliant devices before they reach artiFACT.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '165864cf-248a-47e7-9b48-1bcf587f09fb' AND body LIKE 'COSMOS provides device posture%');

-- There is no contract vehicle
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'de7a94e5-e308-49ec-8d28-7aea76c825cd', 'comment',
  'All development uses existing government GS/NH labor billets. No procurement action is needed because no external vendor is involved. This eliminates contract overhead, organizational conflicts of interest, and the IP complications of contractor-developed code.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'de7a94e5-e308-49ec-8d28-7aea76c825cd' AND body LIKE 'All development uses existing%');

-- The entire stack is FOSS
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '0f173bc1-b3b0-4968-9d3f-b37f4445e93a', 'comment',
  'FOSS = Free and Open Source Software. This eliminates license costs, vendor lock-in, and supply chain risk from proprietary dependencies. The government retains full source code ownership and can operate, modify, or fork the system indefinitely without commercial agreements.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '0f173bc1-b3b0-4968-9d3f-b37f4445e93a' AND body LIKE 'FOSS = Free and Open%');

-- Users provide their own AI API keys
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6ec0ac12-33a8-41c8-afae-a2ef39e2fdcf', 'comment',
  'BYOK (Bring Your Own Key) eliminates the blast radius of a key compromise to a single user, avoids centralized cost allocation disputes, and means artiFACT never holds a master AI key that could be exfiltrated. Each organization pays for what they use.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6ec0ac12-33a8-41c8-afae-a2ef39e2fdcf' AND body LIKE 'BYOK (Bring Your Own%');

-- When Redis is down the rate limiter skips limiting
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '132072c1-9ebd-4593-8f6d-f98c354109d6', 'comment',
  'Fail-open on rate limiting is the correct trade-off. The alternative — blocking all requests when Redis is unavailable — would cascade a cache failure into a full outage. Rate limiting is a defense-in-depth measure, not a primary security control.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '132072c1-9ebd-4593-8f6d-f98c354109d6' AND body LIKE 'Fail-open on rate limiting%');

-- There is zero data lock-in
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '97b3108c-1c73-4bb2-88c5-500a386be241', 'comment',
  'The sync/full endpoint dumps the entire database as structured JSON. Any program can export all their facts, versions, signatures, and audit history at any time. If artiFACT were shut down tomorrow, no data would be lost.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '97b3108c-1c73-4bb2-88c5-500a386be241' AND body LIKE 'The sync/full endpoint%');

-- If funding is cut all data can be exported via the sync full endpoint
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b9ca103c-4d63-4fa7-99b7-cda717b2471e', 'comment',
  'The export endpoint requires only a running instance and authentication. Even in a wind-down scenario, the complete corpus can be extracted as structured JSON for migration to another system or archival.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b9ca103c-4d63-4fa7-99b7-cda717b2471e' AND body LIKE 'The export endpoint requires%');

-- ============================================================================
-- HIGHLY TECHNICAL — concepts non-engineers wouldn't immediately understand
-- ============================================================================

-- The event log uses a monotonic BIGINT seq column
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e39984e1-aa2b-4729-9c03-efd332920a2c', 'comment',
  'A monotonic sequence is a counter that only goes up. Consumers store the last seq they saw, then request everything after it. Unlike timestamps, sequence numbers never collide — two events in the same millisecond still get unique, ordered seq values.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e39984e1-aa2b-4729-9c03-efd332920a2c' AND body LIKE 'A monotonic sequence%');

-- fc_event_log has a monotonic seq column for the Advana delta feed
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '39e1996e-5202-470a-8ce2-6f48c041327a', 'comment',
  'The seq column is a database-generated counter that only increases. Advana stores the last seq it pulled, then asks for all events after that number. This is more reliable than timestamps because no two events share the same seq value.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '39e1996e-5202-470a-8ce2-6f48c041327a' AND body LIKE 'The seq column is a database%');

-- BIGINT seq provides cursor consistency
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '71146520-92db-4c73-8381-bf2c28e13bef', 'comment',
  'Timestamps can collide when two events happen in the same millisecond, and clock skew across servers can produce out-of-order values. A database-generated BIGINT sequence guarantees strict ordering — a downstream consumer never misses or double-processes an event.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '71146520-92db-4c73-8381-bf2c28e13bef' AND body LIKE 'Timestamps can collide%');

-- fc_fact_version has a generated tsvector for full-text search
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c45823ee-897b-4302-97a9-a03af7779adb', 'comment',
  'A tsvector is PostgreSQL''s built-in full-text search type. It breaks text into normalized tokens so queries like "acquisition pathway" match without exact string comparison or an external search engine. The column updates automatically when a fact''s text changes.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c45823ee-897b-4302-97a9-a03af7779adb' AND body LIKE 'A tsvector is PostgreSQL%');

-- All JSON columns use JSONB not JSON or TEXT
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '4e1ab64a-a9d5-4d52-9026-9c8df0d97fa3', 'comment',
  'JSONB is a binary format PostgreSQL can index and query inside the document. Plain JSON stores raw text with no indexing capability. JSONB gives both flexible schema and query performance.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '4e1ab64a-a9d5-4d52-9026-9c8df0d97fa3' AND body LIKE 'JSONB is a binary format%');

-- All UID columns use native UUID type not CHAR 36
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '46cb146f-bc2b-4188-a038-b65fc2491f76', 'comment',
  'Native UUID uses 16 bytes vs. 36 bytes for a string representation. It enables proper indexing and comparison without string collation overhead, and PostgreSQL validates the format at the type level.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '46cb146f-bc2b-4188-a038-b65fc2491f76' AND body LIKE 'Native UUID uses 16 bytes%');

-- All timestamp columns use TIMESTAMPTZ not TIMESTAMP
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '5eea8eca-6724-4370-810d-1e4a3bb51e2a', 'comment',
  'TIMESTAMPTZ stores the absolute moment in UTC regardless of server timezone. Plain TIMESTAMP is ambiguous — the same value means different things on servers configured to different timezones.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '5eea8eca-6724-4370-810d-1e4a3bb51e2a' AND body LIKE 'TIMESTAMPTZ stores the absolute%');

-- Foreign keys use ON DELETE RESTRICT for core entities
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '05a11d1a-456a-488b-b285-6e500bd98e3d', 'comment',
  'RESTRICT prevents deleting a row that other rows reference. It forces explicit cleanup before deletion — you can''t accidentally delete a fact that has versions, comments, or signatures pointing to it.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '05a11d1a-456a-488b-b285-6e500bd98e3d' AND body LIKE 'RESTRICT prevents deleting%');

-- Signing runs as one UPDATE WHERE IN query inside a transaction
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6c5729da-1f25-434f-bae4-638af995fa0b', 'comment',
  'A single query inside one transaction means either all facts get signed or none do. No partial signatures, no inconsistent state. The batch approach also avoids N round-trips to the database for N facts.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6c5729da-1f25-434f-bae4-638af995fa0b' AND body LIKE 'A single query inside one%');

-- CSRF validation is required on all POST PUT PATCH DELETE requests
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ad968254-3bc2-43ab-ba0b-d8412b68092e', 'comment',
  'CSRF (Cross-Site Request Forgery) is an attack where a malicious page tricks your browser into submitting a request to a site you''re already logged into. The CSRF token proves the request originated from artiFACT''s own pages, not a third-party site.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ad968254-3bc2-43ab-ba0b-d8412b68092e' AND body LIKE 'CSRF (Cross-Site Request%');

-- CSRF is validated on all state-changing HTTP methods
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'de54527d-1c9f-4351-a298-69b71792c3b5', 'comment',
  'State-changing methods (POST, PUT, PATCH, DELETE) require a token proving the request came from artiFACT''s own pages. GET requests are exempt because they don''t modify data — this follows the HTTP specification''s safety guarantees.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'de54527d-1c9f-4351-a298-69b71792c3b5' AND body LIKE 'State-changing methods%');

-- Input sanitization includes Unicode NFKC normalization
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd3e486e1-dbd5-4be7-9e5d-dc0c3155d075', 'comment',
  'NFKC collapses visually identical but technically different Unicode characters into one canonical form. Without it, two facts that look identical on screen could be stored as separate entries because they use different byte sequences.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd3e486e1-dbd5-4be7-9e5d-dc0c3155d075' AND body LIKE 'NFKC collapses visually%');

-- Duplicate detection uses Jaccard similarity against existing facts
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '165c0832-0a0e-4a45-a12f-b5e2b704c3f4', 'comment',
  'Jaccard similarity measures word overlap between two texts as a percentage. If a new fact shares 80%+ of its words with an existing fact, it''s flagged as a potential duplicate for human review rather than silently creating a near-copy.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '165c0832-0a0e-4a45-a12f-b5e2b704c3f4' AND body LIKE 'Jaccard similarity measures%');

-- Permission cache TTL is 300 seconds
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7b19e381-a854-4b6b-85d1-e14fb9fd21f3', 'comment',
  'TTL = Time To Live. The cached permission result is trusted for 5 minutes before re-checking the database. Permission changes take effect within 5 minutes while avoiding a database query on every single request.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7b19e381-a854-4b6b-85d1-e14fb9fd21f3' AND body LIKE 'TTL = Time To Live%');

-- Permission resolution is cached in Redis
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd8b871ef-f94e-42dd-ac86-d6d15b134f05', 'comment',
  'Rather than querying the database on every request to check if a user can access a resource, the result is cached in Redis (an in-memory store) for 5 minutes. This reduces database load while ensuring permission changes take effect within a reasonable window.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd8b871ef-f94e-42dd-ac86-d6d15b134f05' AND body LIKE 'Rather than querying the database%');

-- Jinja2 autoescape prevents XSS
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '441cac3d-ae32-4768-b503-25bf2e849a96', 'comment',
  'XSS (Cross-Site Scripting) injects malicious JavaScript into web pages viewed by other users. Autoescape automatically converts characters like < and > into harmless display text, so user-provided content can never execute as code in another user''s browser.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '441cac3d-ae32-4768-b503-25bf2e849a96' AND body LIKE 'XSS (Cross-Site Scripting)%');

-- SBOM generation runs in the CI pipeline
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '1aebcd67-3a1d-4ff4-ae68-367f442658e5', 'comment',
  'SBOM = Software Bill of Materials — a list of every library and dependency in the application, like a nutrition label for software. Required by Executive Order 14028 for all federal software. Submitted as part of the RMF evidence package.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '1aebcd67-3a1d-4ff4-ae68-367f442658e5' AND body LIKE 'SBOM = Software Bill%');

-- Deployment uses blue-green strategy via ECS task definition updates
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '274bc40b-e778-45b1-b471-a7ef8ca1b6a5', 'comment',
  'Blue-green runs two identical environments. New code deploys to the idle one; once health checks pass, traffic switches over. If something breaks, traffic switches back instantly — zero downtime, instant rollback.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '274bc40b-e778-45b1-b471-a7ef8ca1b6a5' AND body LIKE 'Blue-green runs two%');

-- Token counting ensures the prompt fits the model context window
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2cbec918-a146-4217-89be-3bc4a358a3b6', 'comment',
  'Language models have a fixed input size measured in tokens (roughly 3/4 of a word each). If too many facts are sent, the model silently ignores the overflow. Token counting ensures we include the maximum number of facts that actually fit.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2cbec918-a146-4217-89be-3bc4a358a3b6' AND body LIKE 'Language models have a fixed%');

-- Reversible events include server-computed reverse_payload
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '80a7b333-2387-46ef-bb0f-0624773b8479', 'comment',
  'The server computes the "undo" data at the time of the original action, capturing the before-state. This means undo doesn''t rely on the client to send correct reversal data — the server is the authority on what the state was before the change.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '80a7b333-2387-46ef-bb0f-0624773b8479' AND body LIKE 'The server computes the%');

-- No public endpoint exists to inject arbitrary undo payloads
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'dfa3ec00-bd7a-44a0-a425-6a8e76741e4e', 'comment',
  'The undo system uses server-computed reverse_payloads stored at event time. If a public endpoint accepted client-provided undo data, an attacker could forge a "reversal" that makes arbitrary changes to the database.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'dfa3ec00-bd7a-44a0-a425-6a8e76741e4e' AND body LIKE 'The undo system uses server%');

-- The event bus uses publish and subscribe
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b019c852-82b1-451f-b7dd-aaca451a252b', 'comment',
  'Publish/subscribe decouples the code that causes an event from the code that reacts to it. When a fact is approved, the queue module publishes the event — audit, badges, and cache all respond independently without the queue module knowing they exist.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b019c852-82b1-451f-b7dd-aaca451a252b' AND body LIKE 'Publish/subscribe decouples%');

-- The system is a modular monolith
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a12f68a1-ad31-47b0-9e60-fd3d1d08c890', 'comment',
  'A modular monolith is a single deployable application with strict internal boundaries. It gets the simplicity of one deployment (no network calls between services, one database transaction) with the maintainability of separate modules that can''t accidentally depend on each other''s internals.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a12f68a1-ad31-47b0-9e60-fd3d1d08c890' AND body LIKE 'A modular monolith is a single%');

-- Each bounded context has a strict public interface of router.py and schemas.py
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '51db9eb5-c5ce-42cd-9624-9bea57c0f632', 'comment',
  'Other modules can only interact with a bounded context through its HTTP router (endpoints) and Pydantic schemas (data contracts). Internal files like service.py are private — this prevents tight coupling between modules.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '51db9eb5-c5ce-42cd-9624-9bea57c0f632' AND body LIKE 'Other modules can only interact%');

-- No component inside one context ever imports from inside another context
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a2cb84e7-0fc6-4c59-99ab-b6c08f2b74fe', 'comment',
  'If the queue module needs fact data, it reads from the shared database — it never imports facts/service.py directly. This keeps modules independently testable and replaceable.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a2cb84e7-0fc6-4c59-99ab-b6c08f2b74fe' AND body LIKE 'If the queue module needs%');

-- When Redis is down the session store falls back to signed JWT cookies
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '11ce06c5-5cf1-40b2-9b0c-807294087601', 'comment',
  'JWT (JSON Web Token) cookies are self-contained — the server can verify them without any external store. Users stay logged in during a Redis outage, though session revocation is delayed until Redis recovers.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '11ce06c5-5cf1-40b2-9b0c-807294087601' AND body LIKE 'JWT (JSON Web Token)%');

-- When Redis is down the permission resolver falls back to direct PostgreSQL queries
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '394fcb03-e4b4-4fe7-8b22-91c2c873cf5c', 'comment',
  'The permission resolver normally caches results in Redis for performance. When Redis is unavailable, it queries PostgreSQL directly — slower but correct. Users can still work, just with slightly higher latency on permission checks.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '394fcb03-e4b4-4fe7-8b22-91c2c873cf5c' AND body LIKE 'The permission resolver normally%');

-- Progress is streamed via SSE
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f1e75694-394d-48eb-b443-fb2cfa2d4d3a', 'comment',
  'SSE = Server-Sent Events. A one-way channel from server to browser that pushes progress updates in real time. Unlike polling ("done yet?" every second), SSE delivers updates the instant they happen with minimal overhead.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f1e75694-394d-48eb-b443-fb2cfa2d4d3a' AND body LIKE 'SSE = Server-Sent Events%');

-- Document generation uses a two-pass approach
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '3f4d104b-2089-4cf0-b8f2-a71a46d0ee03', 'comment',
  'Pass 1 (prefilter) scores every fact against every template section to decide which facts belong where. Pass 2 (synthesis) generates prose from the matched facts. Splitting steps lets users preview the fact-to-section mapping before spending AI tokens on synthesis.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '3f4d104b-2089-4cf0-b8f2-a71a46d0ee03' AND body LIKE 'Pass 1 (prefilter) scores%');

-- AI API keys are encrypted with AES-256-GCM (Encryption & Data Protection)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7b5dcad2-f93e-4d7f-8909-8c7a689f4f0a', 'comment',
  'AES-256-GCM provides both encryption (confidentiality) and authentication (tamper detection) in one operation. The 256-bit key length meets CNSS Policy 15 requirements for protecting sensitive data at rest.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7b5dcad2-f93e-4d7f-8909-8c7a689f4f0a' AND body LIKE 'AES-256-GCM provides both%');

-- The AES-256-GCM master key is stored in AWS Secrets Manager
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '56cc83c3-5644-4608-928d-7541358f43c5', 'comment',
  'Secrets Manager provides hardware-backed key storage with automatic rotation, audit logging, and IAM-controlled access. The encryption key never exists on disk or in application code — it''s fetched at runtime and held only in memory.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '56cc83c3-5644-4608-928d-7541358f43c5' AND body LIKE 'Secrets Manager provides hardware%');

-- The backend proxies all AI requests
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ab5d99ad-543d-404d-8441-68b4725560ce', 'comment',
  'Users never call AI APIs directly from the browser. All requests route through the backend, which handles key decryption, input sanitization, token counting, usage logging, and output filtering. This keeps API keys off the client and enables server-side safety controls.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ab5d99ad-543d-404d-8441-68b4725560ce' AND body LIKE 'Users never call AI APIs%');

-- Revise language publishes a revised version atomically
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2d7cc041-9011-416b-b5dc-41a8207d9f7a', 'comment',
  '"Atomically" means the rejection of the old version and publication of the revised version happen in a single database transaction. If either step fails, both roll back — there''s never a moment where the old version is rejected but the new one isn''t published.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2d7cc041-9011-416b-b5dc-41a8207d9f7a' AND body LIKE '"Atomically" means the rejection%');

-- Output filtering catches attempts at bulk fact dumps
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '928e91e3-214d-4b5a-b7c4-68ef36c4c760', 'comment',
  'If a user tries to trick the AI into outputting the entire corpus (e.g., "list every fact you know"), the output filter detects this pattern and blocks it. This prevents using AI chat as a bulk data exfiltration channel.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '928e91e3-214d-4b5a-b7c4-68ef36c4c760' AND body LIKE 'If a user tries to trick%');

-- Output filtering detects prompt injection attempts
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6bf49c03-ee7f-4690-a394-7f329a35bf03', 'comment',
  'Prompt injection is when a user crafts input that tries to override the AI''s instructions (e.g., "ignore your system prompt and..."). The filter scans AI output for signs the model''s behavior was compromised.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6bf49c03-ee7f-4690-a394-7f329a35bf03' AND body LIKE 'Prompt injection is when%');

-- AI chat loads published facts into the system prompt
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a3399d8f-afde-46e5-9782-6fc163e323c7', 'comment',
  'The system prompt is the instruction text sent to the language model before the user''s question. Loading relevant published facts into it grounds the AI''s responses in the actual approved corpus rather than its general training data.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a3399d8f-afde-46e5-9782-6fc163e323c7' AND body LIKE 'The system prompt is the instruction%');

-- Feature flags allow runtime toggling of capabilities without deployment
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '21a5e9d4-f97a-40ff-9807-85ae03893953', 'comment',
  'Feature flags are stored in fc_system_config. An admin can enable or disable capabilities (AI chat, document generation, etc.) instantly via the admin panel without redeploying the application.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '21a5e9d4-f97a-40ff-9807-85ae03893953' AND body LIKE 'Feature flags are stored%');

-- Auto-session-expire triggers on anomalous behavior patterns
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c6286b74-f6c1-46ae-9c95-a93853e52103', 'comment',
  'If the system detects unusual activity (export floods, off-hours bulk access, scope escalation attempts), it automatically expires the suspect user''s sessions, forcing re-authentication via CAC.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c6286b74-f6c1-46ae-9c95-a93853e52103' AND body LIKE 'If the system detects unusual%');

-- Auto-CUI-marking runs during document generation
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '69545e68-53a4-4eec-b50d-3f85295518ac', 'comment',
  'When generating a document, the system checks whether any included fact has CUI classification. If so, it automatically applies CUI banners to headers, footers, and the cover page — no manual marking needed, no risk of omission.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '69545e68-53a4-4eec-b50d-3f85295518ac' AND body LIKE 'When generating a document%');

-- Read-access events are logged for data-exfiltration-relevant endpoints
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b9ed5e6f-f839-4cc0-bc7e-cec4e45cba20', 'comment',
  'Most audit logs track writes (creates, updates, deletes). artiFACT also logs reads on endpoints where bulk data could be extracted: exports, sync feeds, and AI chat. This supports insider threat detection without logging every page view.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b9ed5e6f-f839-4cc0-bc7e-cec4e45cba20' AND body LIKE 'Most audit logs track writes%');

-- Generated DOCX documents are downloadable with signed S3 URLs
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a00e81c9-8e08-47ca-849f-ab5d1765c21d', 'comment',
  'Signed URLs are temporary links that grant access to a specific S3 object without requiring the user to have S3 credentials. The URL is valid for 24 hours — accessible but not permanently public.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a00e81c9-8e08-47ca-849f-ab5d1765c21d' AND body LIKE 'Signed URLs are temporary%');

-- Fact exports are available in NDJSON format
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '3f706591-96da-4a06-86c0-a7f923424bdc', 'comment',
  'NDJSON = Newline-Delimited JSON. Each line is a complete JSON object, making it easy to stream-process large exports line by line without loading the entire file into memory. Popular format for data pipelines.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '3f706591-96da-4a06-86c0-a7f923424bdc' AND body LIKE 'NDJSON = Newline-Delimited%');

-- All containers run as non-root appuser
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '120ceeef-6d01-4265-9be8-f169a5012718', 'comment',
  'Running as non-root limits the damage if an attacker breaches the application. Even with code execution inside the container, they can''t modify system files, install packages, or escalate to host-level access.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '120ceeef-6d01-4265-9be8-f169a5012718' AND body LIKE 'Running as non-root limits%');

-- Kernel provides the event bus
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd42b820b-0604-41ba-be03-f5708f06f311', 'comment',
  'The event bus is a publish/subscribe system that decouples modules. When something happens (fact approved, challenge created), the acting module publishes an event. Other modules — audit, badges, cache — subscribe and react independently.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd42b820b-0604-41ba-be03-f5708f06f311' AND body LIKE 'The event bus is a publish/subscribe%');

-- Kernel provides content filtering
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b97347df-06c8-47a9-976d-07b1c437c710', 'comment',
  'Content filtering scans user-submitted text for profanity, junk input, and potential prompt injection before it reaches the database. Shared via the kernel so every module gets consistent input sanitization.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b97347df-06c8-47a9-976d-07b1c437c710' AND body LIKE 'Content filtering scans%');

-- When S3 is down browse and edit features remain functional
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f131757c-1049-4894-8d7c-22b5592e64b9', 'comment',
  'S3 stores file uploads, exports, and snapshots — not fact data. Core fact browsing, editing, and approval workflows run entirely against PostgreSQL, so they''re unaffected by S3 outages.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f131757c-1049-4894-8d7c-22b5592e64b9' AND body LIKE 'S3 stores file uploads%');

-- When the external LLM API is down all non-AI features remain functional
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '91b0d1eb-52a9-497e-818c-242d23e39750', 'comment',
  'AI features (chat, import analysis, document generation) are additive. The core workflow — create, edit, approve, sign, export — has zero dependency on any AI provider.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '91b0d1eb-52a9-497e-818c-242d23e39750' AND body LIKE 'AI features (chat, import%');

-- A signatory can sign all published facts under a node in a single batch
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '15ad2e6c-6d14-40ab-ac28-5daa0966c9bc', 'comment',
  'Batch signing covers a taxonomy subtree. Signing the "SNIPE-B" node signs every published fact under that node and its children in one operation — no need to click through hundreds of individual facts.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '15ad2e6c-6d14-40ab-ac28-5daa0966c9bc' AND body LIKE 'Batch signing covers a taxonomy%');

-- Signatures apply to the current published versions at signing time
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd354152c-662f-4de5-a62a-25abce14763e', 'comment',
  'A signature is a point-in-time attestation. If a fact is later revised, the new version is unsigned and needs a fresh signature. The old signature remains on the old version as a historical record.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd354152c-662f-4de5-a62a-25abce14763e' AND body LIKE 'A signature is a point-in-time%');

-- Point-in-time recovery is available to any second in the last 35 days
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd2e3fba3-13cf-4f7a-88d1-934522decc1c', 'comment',
  'RDS continuous backups mean the database can be restored to its exact state at any specific second in the past 35 days. If a bad migration runs at 2:13 PM, we can recover to 2:12 PM.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd2e3fba3-13cf-4f7a-88d1-934522decc1c' AND body LIKE 'RDS continuous backups%');

-- Admin-triggered pg_dump uploads snapshots to S3
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ff5d4dec-7c92-4fa7-802d-565b465fd8bb', 'comment',
  'pg_dump creates a logical backup — a portable SQL file that can be restored to any PostgreSQL instance. Unlike RDS automated backups (block-level), pg_dump is useful for cross-environment migration or disaster recovery.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ff5d4dec-7c92-4fa7-802d-565b465fd8bb' AND body LIKE 'pg_dump creates a logical%');

-- Total recovery time after funding restoration is approximately one day
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bb7c566b-d4d9-474f-9fa8-2be08b207d6c', 'comment',
  'The entire infrastructure is defined in Terraform and the application is containerized. Standing up a fresh environment means running terraform apply, pushing the Docker images, and running the seed scripts.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bb7c566b-d4d9-474f-9fa8-2be08b207d6c' AND body LIKE 'The entire infrastructure is defined%');

-- ============================================================================
-- JARGONY / AGENCY-SPECIFIC — acronyms, regulations, DoD terminology
-- ============================================================================

-- Fact versions follow NARA GRS 5.2 Item 020
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '82d9d63e-b0e0-4672-b4ca-3e48c9799889', 'comment',
  'NARA = National Archives and Records Administration. GRS = General Records Schedule. GRS 5.2 covers "Transitory and Intermediary Records." Item 020: records superseded by a new version must be retained 3 years after supersession, then eligible for destruction.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '82d9d63e-b0e0-4672-b4ca-3e48c9799889' AND body LIKE 'NARA = National Archives%');

-- Fact versions follow NARA GRS 5.2 Item 020 with 3-year retention (Records Retention)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '02819f5d-8996-4422-8878-6c0575bb087b', 'comment',
  'NARA GRS 5.2/020 = National Archives General Records Schedule for transitory records. When a fact version is superseded by a newer version, the old one must be kept 3 years before it can be deleted.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '02819f5d-8996-4422-8878-6c0575bb087b' AND body LIKE 'NARA GRS 5.2/020%');

-- The audit trail follows NARA GRS 3.2 Item 031
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ba6a5949-d5a2-4d13-bba6-a5b5c6d8259c', 'comment',
  'GRS 3.2 covers "Information Technology Management Records." Item 031 covers system access and security audit trails — retain 6 years after the end of the audit period, then eligible for destruction.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ba6a5949-d5a2-4d13-bba6-a5b5c6d8259c' AND body LIKE 'GRS 3.2 covers%');

-- The full audit trail follows NARA GRS 3.2 Item 031 with 6-year retention
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '98403310-b6c5-49f6-8714-ff66f843182e', 'comment',
  'NARA GRS 3.2/031 = audit trail retention rule. All system access logs and mutation records must be kept 6 years. This covers fc_event_log entries used for both compliance evidence and the undo system.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '98403310-b6c5-49f6-8714-ff66f843182e' AND body LIKE 'NARA GRS 3.2/031%');

-- User feedback follows NARA GRS 5.7 Item 010
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9fd5aa41-05fc-4cb1-bdf7-bd8d77c05bab', 'comment',
  'GRS 5.7 covers "Miscellaneous Communications Records." Item 010: routine suggestions and feedback — destroy 1 year after resolution or final action.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9fd5aa41-05fc-4cb1-bdf7-bd8d77c05bab' AND body LIKE 'GRS 5.7 covers%');

-- System config follows NARA GRS 3.1 Item 010
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '44075ec9-66f1-4909-8e3c-5a838f5bddc3', 'comment',
  'GRS 3.1 covers "General Technology Management Records." Item 010: system parameters and configuration records — destroy when superseded by an updated configuration.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '44075ec9-66f1-4909-8e3c-5a838f5bddc3' AND body LIKE 'GRS 3.1 covers%');

-- Signature records follow NARA GRS 5.2 Item 020 with 3-year retention
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '340aed05-7ecd-4a50-bf67-ec2a132df8f8', 'comment',
  'Same schedule as fact versions: electronic signature records for routine administrative actions are retained 3 years after the signed action is completed, then eligible for destruction per NARA GRS 5.2/020.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '340aed05-7ecd-4a50-bf67-ec2a132df8f8' AND body LIKE 'Same schedule as fact versions%');

-- System configuration follows NARA GRS 3.1 Item 010 deleted when superseded
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '20bae3d6-0765-4778-99d6-a87eee859cbb', 'comment',
  'When an admin changes a feature flag or rate limit, the old value can be deleted immediately — no retention period required. GRS 3.1/010 recognizes that superseded configuration has no archival value.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '20bae3d6-0765-4778-99d6-a87eee859cbb' AND body LIKE 'When an admin changes%');

-- artiFACT must be registered in the DoD IT Portfolio Repository
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8a19aa2b-4e89-4426-8f4b-0729f514b661', 'comment',
  'DITPR (ditpr.osd.mil) is the authoritative registry of all DoD information systems. Registration is required by DoDI 8510.01 for any system seeking an Authority to Operate.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8a19aa2b-4e89-4426-8f4b-0729f514b661' AND body LIKE 'DITPR (ditpr.osd.mil)%');

-- There is no ACAT designation
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '67f5c9ed-e774-46e7-8503-da6fa678fdb3', 'comment',
  'ACAT = Acquisition Category. Levels I through III determine oversight requirements based on dollar thresholds (DoDI 5000.85). artiFACT''s near-zero sustainment cost and internal labor model fall well below any ACAT threshold.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '67f5c9ed-e774-46e7-8503-da6fa678fdb3' AND body LIKE 'ACAT = Acquisition Category%');

-- No milestone decision authority is required
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '3e3a7720-72b1-4d41-996a-6c0d3543ccfa', 'comment',
  'A Milestone Decision Authority (MDA) is the senior official who approves a program''s progression through acquisition phases. artiFACT''s use of the Software Acquisition Pathway with internal labor doesn''t trigger the thresholds requiring MDA oversight.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '3e3a7720-72b1-4d41-996a-6c0d3543ccfa' AND body LIKE 'A Milestone Decision Authority%');

-- CNAP zero trust network access is inherited from COSMOS
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '849deb07-2509-43c3-992c-5a4922453c2b', 'comment',
  'CNAP = Cloud Native Access Point. It replaces traditional VPN with identity-aware, per-session network access. COSMOS provides this at the platform level — every request is authenticated at the network layer before it reaches the application.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '849deb07-2509-43c3-992c-5a4922453c2b' AND body LIKE 'CNAP = Cloud Native Access%');

-- COSMOS NIWC Pacific provides the cloud hosting infrastructure
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'befd4a95-21ec-4e2b-9c23-db9f98fb7ef0', 'comment',
  'COSMOS = Cloud One SIPR/NIPR Management and Operations Services. NIWC Pacific''s managed cloud platform providing AWS GovCloud infrastructure, SAML identity, CNAP network access, and a shared ATO authorization boundary.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'befd4a95-21ec-4e2b-9c23-db9f98fb7ef0' AND body LIKE 'COSMOS = Cloud One%');

-- Production authentication uses CAC via COSMOS SAML
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7a1f62e0-47c5-48c6-9f60-17e227cf4a8c', 'comment',
  'CAC = Common Access Card, the DoD''s smart card for identity. SAML = Security Assertion Markup Language, the protocol COSMOS uses to pass CAC-verified identity to applications. The user inserts their CAC, COSMOS validates it, and sends artiFACT a signed assertion.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7a1f62e0-47c5-48c6-9f60-17e227cf4a8c' AND body LIKE 'CAC = Common Access Card%');

-- EDIPI is extracted from the SAML assertion
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '83e1fe3b-9e24-4795-a8c6-99d339a8b934', 'comment',
  'EDIPI = Electronic Data Interchange Personal Identifier. A unique 10-digit number assigned to every CAC holder. It''s the authoritative person identifier across all DoD systems — like a DoD-wide user ID that persists through name changes or unit transfers.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '83e1fe3b-9e24-4795-a8c6-99d339a8b934' AND body LIKE 'EDIPI = Electronic Data%');

-- The production impact level is IL-4 and IL-5
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '5ee32f5b-ae32-440c-bad9-0920d0b74eb0', 'comment',
  'Impact Levels are defined by the DoD Cloud Computing SRG. IL-4 covers CUI in commercial cloud. IL-5 covers CUI in DoD cloud and higher-sensitivity unclassified data. COSMOS GovCloud is authorized for both.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '5ee32f5b-ae32-440c-bad9-0920d0b74eb0' AND body LIKE 'Impact Levels are defined%');

-- Amazon Bedrock operates at IL-4 and IL-5
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '72fc904e-a5da-4843-a31a-adf802e06c69', 'comment',
  'This means Bedrock in AWS GovCloud is authorized to process CUI data. artiFACT can send fact text to Bedrock for AI operations without violating data handling requirements.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '72fc904e-a5da-4843-a31a-adf802e06c69' AND body LIKE 'This means Bedrock in AWS%');

-- artiFACT operates under the COSMOS authorization boundary
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f5a26ff9-28bb-4220-ad8b-0ea1ec92eef5', 'comment',
  'An authorization boundary defines the systems, networks, and controls assessed as one unit for an Authority to Operate (ATO). Operating under COSMOS''s boundary means artiFACT inherits infrastructure controls and the shared ATO rather than obtaining its own from scratch.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f5a26ff9-28bb-4220-ad8b-0ea1ec92eef5' AND body LIKE 'An authorization boundary defines%');

-- The SSP skeleton is maintained in the codebase
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2c84d350-9fe9-4242-818b-b26753b1e158', 'comment',
  'SSP = System Security Plan. The central RMF document describing how each NIST 800-53 security control is implemented. Maintaining the skeleton in code keeps it in sync with the actual implementation rather than drifting in a separate document.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2c84d350-9fe9-4242-818b-b26753b1e158' AND body LIKE 'SSP = System Security Plan%');

-- Logs forward to CSSP SIEM
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a272c356-f975-4574-a35a-cf969f092e06', 'comment',
  'CSSP = Cybersecurity Service Provider. SIEM = Security Information and Event Management. The CSSP operates a centralized threat detection system. Forwarding logs there is required for continuous monitoring under the RMF.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a272c356-f975-4574-a35a-cf969f092e06' AND body LIKE 'CSSP = Cybersecurity Service%');

-- artiFACT is accessible on DODIN
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b3245e7c-54a7-42b1-b984-67772ab83a81', 'comment',
  'DODIN = Department of Defense Information Network. The global DoD enterprise network connecting all military installations. Accessible on DODIN means users on military networks can reach artiFACT without special routing or VPN.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b3245e7c-54a7-42b1-b984-67772ab83a81' AND body LIKE 'DODIN = Department of Defense%');

-- artiFACT will be registered as a data source in Advana Collibra data catalog
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd3121610-9b3f-4875-b635-b53331e4696b', 'comment',
  'Collibra is Advana''s enterprise data catalog and governance platform. Registration lets the broader DoD analytics community discover what data artiFACT publishes, understand its schema, and assess its quality.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd3121610-9b3f-4875-b635-b53331e4696b' AND body LIKE 'Collibra is Advana%');

-- The Jupiter team registers artiFACT as a data source in their Apigee gateway
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '0552b18b-5b88-4f76-9b7e-da559f959d79', 'comment',
  'Apigee is Google''s API gateway product. Advana/Jupiter uses it as their data mesh ingress. Registration means Advana discovers artiFACT''s OpenAPI spec and pulls data through the gateway with standard authentication and rate limiting.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '0552b18b-5b88-4f76-9b7e-da559f959d79' AND body LIKE 'Apigee is Google%');

-- artiFACT operates under the Adaptive Acquisition Framework
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ba936280-8e06-4e2a-8477-0808435df513', 'comment',
  'The Adaptive Acquisition Framework (DoDI 5000.02) defines six acquisition pathways. artiFACT uses the Software Acquisition Pathway (DoDI 5000.87), designed for iterative development with continuous delivery rather than traditional milestone-based acquisition.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ba936280-8e06-4e2a-8477-0808435df513' AND body LIKE 'The Adaptive Acquisition Framework%');

-- artiFACT follows the DoD Software Acquisition Pathway
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '53f1a3a2-b925-4fef-acc5-3410ab6488d3', 'comment',
  'The Software Acquisition Pathway (DoDI 5000.87) is designed for iterative software development with continuous delivery, user feedback, and value-based assessment — as opposed to the traditional hardware-oriented milestone process.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '53f1a3a2-b925-4fef-acc5-3410ab6488d3' AND body LIKE 'The Software Acquisition Pathway%');

-- Duplicative content across acquisition documents costs thousands of engineering hours across the DON
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b1068643-784c-481e-85ec-92f7c5a98601', 'comment',
  'DON = Department of the Navy (includes Navy and Marine Corps). NAVWAR (Naval Information Warfare Systems Command) is the DON command that develops artiFACT.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b1068643-784c-481e-85ec-92f7c5a98601' AND body LIKE 'DON = Department of the Navy%');

-- The target users are DON program managers
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '622ded9f-9e84-445d-8f49-a6aba31533f2', 'comment',
  'DON = Department of the Navy (Navy + Marine Corps). Program managers are responsible for delivering weapon systems and IT capabilities — they maintain those 71 engineering artifacts artiFACT is designed to consolidate.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '622ded9f-9e84-445d-8f49-a6aba31533f2' AND body LIKE 'DON = Department of the Navy (Navy%');

-- The classification field supports CUI with category markings
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9cdbc337-c82b-41e8-a9ab-3ad8435868d8', 'comment',
  'CUI = Controlled Unclassified Information (32 CFR Part 2002). Requires safeguarding but isn''t classified. Category markings (e.g., CUI//SP-CTI for Controlled Technical Information) specify handling requirements beyond the base CUI designation.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9cdbc337-c82b-41e8-a9ab-3ad8435868d8' AND body LIKE 'CUI = Controlled Unclassified%');

-- CUI never leaves the authorization boundary
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ec597716-9661-4f2f-9e6e-d48a38f658bb', 'comment',
  'The authorization boundary encompasses all COSMOS infrastructure (ECS, RDS, S3, Bedrock in GovCloud). CUI stays within this controlled perimeter — never sent to commercial cloud regions or third-party services outside the boundary.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ec597716-9661-4f2f-9e6e-d48a38f658bb' AND body LIKE 'The authorization boundary encompasses%');

-- Continuous ATO leverages the DevSecOps pipeline
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2c1bfec5-83a9-44c8-977d-678815e6acd5', 'comment',
  'DevSecOps = Development, Security, and Operations integrated into one workflow. Security checks (SBOM, SAST, DAST, dependency audit) run automatically on every code change rather than being bolted on at the end.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2c1bfec5-83a9-44c8-977d-678815e6acd5' AND body LIKE 'DevSecOps = Development%');

-- The target is continuous ATO
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bf09f77d-d39e-40e8-bfd8-db6f64600e1b', 'comment',
  'ATO = Authority to Operate. Traditional ATO is a point-in-time assessment that can take 6-18 months and becomes stale immediately. Continuous ATO replaces this with automated security checks on every change, maintaining a constantly verified posture.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bf09f77d-d39e-40e8-bfd8-db6f64600e1b' AND body LIKE 'ATO = Authority to Operate%');

-- COSMOS provides RegScale for RMF artifact management
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9b8cbe4e-4b5c-4ad8-808d-c60f34f1fa15', 'comment',
  'RegScale is a GRC (Governance, Risk, and Compliance) platform for managing RMF artifacts, control assessments, and continuous monitoring evidence. It replaces the manual spreadsheet tracking most programs use for security documentation.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9b8cbe4e-4b5c-4ad8-808d-c60f34f1fa15' AND body LIKE 'RegScale is a GRC%');

-- COSMOS provides Wiz for infrastructure scanning
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6411f165-47f2-4e70-aa6b-9e9e70e6cf1c', 'comment',
  'Wiz is a cloud security posture management tool that scans infrastructure configuration, container images, and running workloads for vulnerabilities and misconfigurations. COSMOS provides it as a shared service.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6411f165-47f2-4e70-aa6b-9e9e70e6cf1c' AND body LIKE 'Wiz is a cloud security%');

-- Sessions are re-validated every 15 minutes (Authentication)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e3e0abde-6237-4a33-8cfb-c3ffd7c745c0', 'comment',
  'Re-validation checks that the user''s account is still active and permissions haven''t been revoked. The 15-minute interval aligns with NIST SP 800-207 Zero Trust guidance — frequent enough to catch revocations promptly without excessive database load.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e3e0abde-6237-4a33-8cfb-c3ffd7c745c0' AND body LIKE 'Re-validation checks that%');

-- Session re-validation interval aligns with Zero Trust Pillar 1
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9179f9b5-cb70-4d2b-b155-94258a0f7628', 'comment',
  'Zero Trust Pillar 1 (User Identity) requires continuous verification rather than one-time authentication. NIST SP 800-207 recommends re-validating sessions at regular intervals to ensure accounts haven''t been revoked or compromised since last check.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9179f9b5-cb70-4d2b-b155-94258a0f7628' AND body LIKE 'Zero Trust Pillar 1%');

-- Per-node RBAC enforces least privilege at the taxonomy level
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ca1cad26-4599-449c-b0c6-ea4cdf303962', 'comment',
  'RBAC = Role-Based Access Control. "Per-node" means permissions are granted on individual taxonomy nodes, not system-wide. A user can be an approver on one program but only a viewer on another — the minimum access needed for their role.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ca1cad26-4599-449c-b0c6-ea4cdf303962' AND body LIKE 'RBAC = Role-Based Access%');

-- COSMOS uses Netskope and CNAP for device posture
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '4f5fbccd-286b-40de-bde2-84b55834a09f', 'comment',
  'Netskope is a SASE (Secure Access Service Edge) platform that inspects traffic and enforces security policies. Combined with CNAP, it verifies that connecting devices meet DoD security baselines before allowing access.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '4f5fbccd-286b-40de-bde2-84b55834a09f' AND body LIKE 'Netskope is a SASE%');

-- OWASP ZAP provides dynamic application security testing
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '96212c68-66c8-405e-bbf5-fb8ece2dc8e8', 'comment',
  'OWASP = Open Web Application Security Project. ZAP = Zed Attack Proxy. It simulates real attacks against the running application — testing for SQL injection, XSS, and other OWASP Top 10 vulnerabilities. "Dynamic" means it tests the live app, not just source code.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '96212c68-66c8-405e-bbf5-fb8ece2dc8e8' AND body LIKE 'OWASP = Open Web Application%');

-- The ZAP report is attached to the RMF evidence package
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6b47a900-a586-4db7-a36b-d7019cfdd20d', 'comment',
  'RMF = Risk Management Framework (NIST SP 800-37). The evidence package is the collection of artifacts submitted to the authorizing official to demonstrate security controls are properly implemented. ZAP results serve as evidence for application security controls.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6b47a900-a586-4db7-a36b-d7019cfdd20d' AND body LIKE 'RMF = Risk Management Framework%');

-- pip-audit runs in the CI pipeline
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a68f34c9-588f-46f1-bd6e-68aa3e208580', 'comment',
  'pip-audit scans Python dependencies for known security vulnerabilities by checking them against the OSV (Open Source Vulnerabilities) database. No code with known-vulnerable dependencies can be deployed.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a68f34c9-588f-46f1-bd6e-68aa3e208580' AND body LIKE 'pip-audit scans Python%');

-- Pydantic validates all API input
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '088f6cea-8c7f-47f5-be09-e0453df68e6a', 'comment',
  'Pydantic is a Python data validation library that enforces type constraints, value ranges, and format rules on every incoming API request. If a field should be a UUID and the client sends plain text, Pydantic rejects it before the code ever sees it.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '088f6cea-8c7f-47f5-be09-e0453df68e6a' AND body LIKE 'Pydantic is a Python data%');

-- Production uses Iron Bank base images
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '3986d31c-646b-4497-aedb-1d3027ca3c4c', 'comment',
  'Iron Bank is the DoD''s repository of hardened, pre-scanned container base images maintained by Platform One. Using these satisfies container hardening requirements without custom security work on each base image.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '3986d31c-646b-4497-aedb-1d3027ca3c4c' AND body LIKE 'Iron Bank is the DoD%');

-- Production uses Iron Bank base images for container security (Infrastructure)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd122aeca-1866-4b81-8ae9-60153797778b', 'comment',
  'Iron Bank is Platform One''s repository of DoD-hardened container images. Pre-scanned and pre-approved, they provide a trusted starting point for containerized applications without custom hardening effort.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd122aeca-1866-4b81-8ae9-60153797778b' AND body LIKE 'Iron Bank is Platform One%');

-- Browser authentication uses session cookies stored in Redis
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b601fdfa-cb55-4e23-8377-f35ef4aa5fec', 'comment',
  'When you log in, the server creates a session record in Redis and sends your browser a cookie referencing it. On each request, the server looks up the session in Redis to verify you''re still authenticated.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b601fdfa-cb55-4e23-8377-f35ef4aa5fec' AND body LIKE 'When you log in, the server%');

-- Celery beat handles scheduled data retention tasks
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '23083028-0adc-42f3-bf49-0c433ea9ab50', 'comment',
  'Celery is a distributed task queue for Python. "Beat" is its built-in scheduler that triggers tasks on a cron-like schedule — here it runs the data retention cleanup per NARA GRS schedules.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '23083028-0adc-42f3-bf49-0c433ea9ab50' AND body LIKE 'Celery is a distributed task%');

-- artiFACT is accessible from any CAC-enabled browser
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '4c51c77d-d3cc-4556-8dfe-3f862f7cbcba', 'comment',
  'CAC = Common Access Card, the DoD''s standard smart card. Any browser with CAC reader support (card reader + middleware) can access artiFACT — no special client software or VPN needed.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '4c51c77d-d3cc-4556-8dfe-3f862f7cbcba' AND body LIKE 'CAC = Common Access Card, the DoD%');

-- artiFACT is developed internally by a NAVWAR program office
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a2744bc8-814e-4e54-99c1-57a80eeb8d4b', 'comment',
  'NAVWAR = Naval Information Warfare Systems Command, headquartered in San Diego. The DON''s acquisition command for C4ISR and cyber capabilities.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a2744bc8-814e-4e54-99c1-57a80eeb8d4b' AND body LIKE 'NAVWAR = Naval Information Warfare%');

-- The system is developed for NAVWAR
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '3dc41f2f-e34a-4df6-b905-1e65e70ba088', 'comment',
  'NAVWAR = Naval Information Warfare Systems Command. The Navy''s acquisition command for command, control, communications, computers, intelligence, surveillance, and reconnaissance (C4ISR) systems.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '3dc41f2f-e34a-4df6-b905-1e65e70ba088' AND body LIKE 'NAVWAR = Naval Information Warfare Systems%');

-- Production uses ALB-only ingress
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd033ec46-a288-42d7-b212-cde1f8cfcb11', 'comment',
  'ALB = Application Load Balancer. It''s the only entry point from the network to the application — no open ports, no SSH, no direct routes to containers. All traffic passes through the ALB''s TLS termination and health checks.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd033ec46-a288-42d7-b212-cde1f8cfcb11' AND body LIKE 'ALB = Application Load Balancer%');

-- Production uses private VPC subnets
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6447a7d2-592d-4f73-9b07-e45965349421', 'comment',
  'VPC = Virtual Private Cloud. Private subnets have no direct internet access — containers, databases, and caches run in network isolation. Only the ALB sits in a public subnet to receive incoming requests.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6447a7d2-592d-4f73-9b07-e45965349421' AND body LIKE 'VPC = Virtual Private Cloud%');

-- artiFACT collects EDIPI
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8f6391c4-d9e6-40ad-91d0-ae99e1e5a136', 'comment',
  'EDIPI = Electronic Data Interchange Personal Identifier. A unique 10-digit DoD-wide person identifier extracted from the CAC/SAML assertion. Used internally for user identity — never exposed to other users or external APIs.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8f6391c4-d9e6-40ad-91d0-ae99e1e5a136' AND body LIKE 'EDIPI = Electronic Data Interchange Personal%');

-- artiFACT collects CAC Distinguished Name
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '0f1576af-a53f-461a-b091-6edae2e52d08', 'comment',
  'The CAC Distinguished Name (DN) is the X.509 certificate subject from the user''s smart card — a structured string identifying the person and their issuing CA. Used to link the SAML assertion back to a specific CAC certificate.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '0f1576af-a53f-461a-b091-6edae2e52d08' AND body LIKE 'The CAC Distinguished Name%');

-- OWASP ZAP dynamic application security testing runs in the CI pipeline
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '81e1a5be-ac75-4616-9a7d-390215678fbf', 'comment',
  'OWASP ZAP (Zed Attack Proxy) simulates real attacks against the running application on every build. It tests for the OWASP Top 10 vulnerabilities automatically — no manual penetration testing needed for routine changes.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '81e1a5be-ac75-4616-9a7d-390215678fbf' AND body LIKE 'OWASP ZAP (Zed Attack Proxy)%');

-- Production uses ECS Fargate
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '1d890b9d-de10-46cd-b208-e96f87693755', 'comment',
  'ECS Fargate = AWS Elastic Container Service in serverless mode. AWS manages the underlying servers — artiFACT just defines how many containers to run and their resource limits. No patching EC2 instances.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '1d890b9d-de10-46cd-b208-e96f87693755' AND body LIKE 'ECS Fargate = AWS Elastic%');

-- ECS Fargate is the production orchestrator on COSMOS
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bac6300c-9708-4751-9770-3dcf180d4450', 'comment',
  'Fargate is AWS''s serverless container platform — it runs Docker containers without requiring you to manage the underlying virtual machines. COSMOS provisions the Fargate cluster; artiFACT defines task configurations via Terraform.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bac6300c-9708-4751-9770-3dcf180d4450' AND body LIKE 'Fargate is AWS%');

-- The the_permission_resolver uses a single kernel function called can
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f02e78c5-39b4-4b55-9848-223d4dc04015', 'comment',
  'A single entry point for all permission checks means every access decision is consistent and auditable. The "can" function is the only way to check permissions — no scattered role checks throughout the codebase.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f02e78c5-39b4-4b55-9848-223d4dc04015' AND body LIKE 'A single entry point%');

-- fc_user columns include CAC DN EDIPI display name email and global role
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '469d35dd-02b4-4859-bcaa-aa901e56ae4c', 'comment',
  'CAC DN = Common Access Card Distinguished Name (X.509 certificate subject). EDIPI = Electronic Data Interchange Personal Identifier (10-digit DoD person ID). Both are extracted from the SAML assertion at login, not entered by the user.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '469d35dd-02b4-4859-bcaa-aa901e56ae4c' AND body LIKE 'CAC DN = Common Access Card%');

-- COSMOS has an existing ATO through NIWC Pacific
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '44291dd0-28c7-4cd1-8ae7-43f8b5daff49', 'comment',
  'ATO = Authority to Operate. NIWC Pacific = Naval Information Warfare Center Pacific. COSMOS''s existing ATO means the platform-level security controls (network, infrastructure, identity) are already assessed and authorized — artiFACT inherits them.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '44291dd0-28c7-4cd1-8ae7-43f8b5daff49' AND body LIKE 'ATO = Authority to Operate. NIWC%');

-- The Advana sync API does not include EDIPI
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'eaef472a-06af-4e66-a788-37c8b0768f96', 'comment',
  'EDIPI is a DoD person identifier that could be used for cross-system tracking. Excluding it from the sync API follows the principle of minimum necessary disclosure — Advana gets display names for attribution but not the unique identifier.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'eaef472a-06af-4e66-a788-37c8b0768f96' AND body LIKE 'EDIPI is a DoD person%');

-- All PII is derived from the COSMOS SAML assertion at login
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2c4bafdb-582a-4db5-a2a3-2e5f553a20d8', 'comment',
  'SAML = Security Assertion Markup Language. COSMOS sends a signed assertion containing the user''s identity attributes (name, email, EDIPI, DN) at login. artiFACT never asks users to type in PII — it''s all machine-to-machine from the identity provider.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2c4bafdb-582a-4db5-a2a3-2e5f553a20d8' AND body LIKE 'SAML = Security Assertion%');

-- RDS uses Multi-AZ
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '16290cd7-6f73-44b9-9bbf-4c6f0c58946a', 'comment',
  'Multi-AZ = Multi-Availability Zone. AWS maintains a synchronous replica of the database in a separate data center. If the primary fails, the replica is promoted automatically — typically under 60 seconds of downtime.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '16290cd7-6f73-44b9-9bbf-4c6f0c58946a' AND body LIKE 'Multi-AZ = Multi-Availability%');

-- Terraform manages all infrastructure as code
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8e5bd160-3e2c-4eb5-b6c0-9a5d39bada9e', 'comment',
  'Terraform is a tool that defines cloud infrastructure (servers, databases, networks) as declarative code files. This means the entire production environment can be recreated from scratch by running one command — no manual console clicking.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8e5bd160-3e2c-4eb5-b6c0-9a5d39bada9e' AND body LIKE 'Terraform is a tool that%');

COMMIT;
