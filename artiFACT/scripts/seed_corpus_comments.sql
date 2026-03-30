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

-- ACCESS CONTROL MODEL
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '88bb115b-1031-48c2-b0a7-e3b621366b19', 'comment',
  'Cascading grants eliminate the need to assign permissions on every leaf node individually. An approver on "System Identity" automatically has approval rights on all child nodes beneath it.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '88bb115b-1031-48c2-b0a7-e3b621366b19' AND body LIKE 'Cascading grants eliminate%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f3ca2767-6ce5-4f26-9680-a51c62c629fe', 'comment',
  'Directly reading global_role from the user record would bypass node-level permissions entirely. All access decisions go through the kernel "can" function, which considers node context, role hierarchy, and grant cascading.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f3ca2767-6ce5-4f26-9680-a51c62c629fe' AND body LIKE 'Directly reading global_role%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '42947740-591c-4386-a23b-ceda9b3740d7', 'comment',
  'The "can" function is the single entry point for all permission checks — it takes (user, node, action) and returns a boolean. Centralizing this logic prevents scattered role checks throughout the codebase.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '42947740-591c-4386-a23b-ceda9b3740d7' AND body LIKE 'The "can" function is the single%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'cf13eeb3-71f8-45e6-9109-8f8e0c902c61', 'comment',
  'Each role inherits all capabilities of the roles below it: signatory can do everything an approver can, an approver can do everything a subapprover can, and so on down to viewer.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'cf13eeb3-71f8-45e6-9109-8f8e0c902c61' AND body LIKE 'Each role inherits all%');

-- ============================================================================
-- AI SAFETY CONTROLS
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f9221072-9a05-4db7-bb2e-c41ce3fc4f48', 'comment',
  'fc_ai_usage logs every AI API call with provider, model, token count, and estimated cost. This enables per-user cost attribution under the BYOK model and anomaly detection for unusual usage patterns.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f9221072-9a05-4db7-bb2e-c41ce3fc4f48' AND body LIKE 'fc_ai_usage logs every%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a8c94915-3585-4bf7-9f41-f7efad6e997a', 'comment',
  'Bulk fact dumps are a data exfiltration vector. If a user prompts the AI to "list all facts," the output filter detects the pattern and blocks it before the response reaches the client.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a8c94915-3585-4bf7-9f41-f7efad6e997a' AND body LIKE 'Bulk fact dumps are%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '1708281d-13a8-48f2-b59b-8e78c3199363', 'comment',
  'Per-user rate limiting prevents any single account from monopolizing AI resources or running denial-of-service against the LLM provider. Limits are configurable via fc_system_config.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '1708281d-13a8-48f2-b59b-8e78c3199363' AND body LIKE 'Per-user rate limiting prevents%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f05212be-4e6c-40ac-a660-a46c19264e84', 'comment',
  'Tracking provider and model per request enables cost allocation, performance comparison between models, and the ability to identify if a specific model version causes quality regressions.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f05212be-4e6c-40ac-a660-a46c19264e84' AND body LIKE 'Tracking provider and model%');

-- ============================================================================
-- APPROVAL WORKFLOW
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bd9b2718-b66a-49d9-9fcb-f6896c69525e', 'comment',
  'Publishing sets published_at and transitions the version state to "published." The fact entity''s published_version_uid pointer updates atomically in the same transaction.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bd9b2718-b66a-49d9-9fcb-f6896c69525e' AND body LIKE 'Publishing sets published_at%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '65ecb46e-6e5b-46e4-826d-f60d7f521439', 'comment',
  'Contributors are the lowest role that can create content. Their proposals must be reviewed and approved before becoming part of the published corpus — enforcing four-eyes review on all fact content.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '65ecb46e-6e5b-46e4-826d-f60d7f521439' AND body LIKE 'Contributors are the lowest%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '320723c0-9cc6-4908-91d4-89d838a2142f', 'comment',
  '"Revise language" is a convenience action: the approver edits the text and publishes the corrected version in one step, rather than rejecting and waiting for the contributor to resubmit.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '320723c0-9cc6-4908-91d4-89d838a2142f' AND body LIKE '"Revise language" is a convenience%');

-- ============================================================================
-- ATO & RMF
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f94ff83a-9822-4f56-aef8-fa29eff69aec', 'comment',
  'OWASP ZAP = Open Web Application Security Project Zed Attack Proxy. It runs automated penetration testing against the live application, probing for SQL injection, XSS, and other OWASP Top 10 vulnerabilities.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f94ff83a-9822-4f56-aef8-fa29eff69aec' AND body LIKE 'OWASP ZAP = Open Web%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6e9c856f-223d-43e9-97dc-094e082adf62', 'comment',
  'SBOM = Software Bill of Materials. A machine-readable inventory of every dependency. Required by Executive Order 14028 for federal software and submitted as RMF evidence.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6e9c856f-223d-43e9-97dc-094e082adf62' AND body LIKE 'SBOM = Software Bill%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7f102ab4-76c1-4156-8d6f-014d45f58414', 'comment',
  'Maintaining control implementation statements in the codebase keeps them versioned alongside the actual code. When a security control changes, the documentation updates in the same commit.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7f102ab4-76c1-4156-8d6f-014d45f58414' AND body LIKE 'Maintaining control implementation%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '559693d4-b3b1-47dd-a224-c611bbe4f7e1', 'comment',
  '80% overall coverage with 95% on the kernel ensures the most critical shared code is thoroughly tested. The kernel handles auth, permissions, encryption, and events — a bug there affects every module.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '559693d4-b3b1-47dd-a224-c611bbe4f7e1' AND body LIKE '80% overall coverage%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '81131d74-46f7-41c7-8e11-fc6867988f7e', 'comment',
  'An incident response runbook in the codebase means it''s version-controlled, peer-reviewed, and always co-located with the system it describes. Required for NIST 800-53 IR controls.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '81131d74-46f7-41c7-8e11-fc6867988f7e' AND body LIKE 'An incident response runbook%');

-- ============================================================================
-- AUDIT & ACCOUNTABILITY
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'cf44d5d2-1244-4524-9338-6c1cf45c4a60', 'comment',
  'Every state change — fact created, approved, signed, retired, permission granted — creates an immutable event record. This provides the evidence trail required by NIST 800-53 AU controls and powers the undo system.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'cf44d5d2-1244-4524-9338-6c1cf45c4a60' AND body LIKE 'Every state change%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '479b0d4b-79cf-47f7-a328-f8c1762e70fd', 'comment',
  'The seq column is a monotonic BIGINT that only increases. Advana stores the last seq it pulled and asks for everything after it — more reliable than timestamps because no two events share the same seq.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '479b0d4b-79cf-47f7-a328-f8c1762e70fd' AND body LIKE 'The seq column is a monotonic%');

-- ============================================================================
-- AUTHENTICATION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c4ad0118-81ff-4055-9fac-3aaaae4f07c1', 'comment',
  'Bearer tokens are for machine-to-machine integrations (e.g., Advana sync). Human users authenticate via CAC/SAML session cookies. Two distinct authentication paths serve distinct use cases.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c4ad0118-81ff-4055-9fac-3aaaae4f07c1' AND body LIKE 'Bearer tokens are for machine%');

-- ============================================================================
-- BACKEND
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f52399c9-8fe6-406f-9de7-2d9ea1760965', 'comment',
  'Alembic is the standard database migration tool for SQLAlchemy. Each migration is a versioned Python script that can upgrade or downgrade the schema, providing a reproducible history of all database changes.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f52399c9-8fe6-406f-9de7-2d9ea1760965' AND body LIKE 'Alembic is the standard%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '87f105c3-1853-4c98-a941-fe4950b89563', 'comment',
  'Celery is a distributed task queue for Python. Long-running operations like document generation, import analysis, and data retention cleanup run in Celery workers so the web server remains responsive.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '87f105c3-1853-4c98-a941-fe4950b89563' AND body LIKE 'Celery is a distributed%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7a768755-ea96-4818-933c-470851fccda5', 'comment',
  'FastAPI is a modern Python web framework built on Starlette and Pydantic. It provides automatic OpenAPI spec generation, async support, and type-based request validation out of the box.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7a768755-ea96-4818-933c-470851fccda5' AND body LIKE 'FastAPI is a modern Python%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'aa86fd8b-45b2-4fa9-b442-9cd219555f14', 'comment',
  'mypy is Python''s static type checker. Strict mode requires type annotations on every function parameter and return value, catching type errors at build time rather than at runtime in production.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'aa86fd8b-45b2-4fa9-b442-9cd219555f14' AND body LIKE 'mypy is Python''s static%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '75fa0db8-3ed3-4418-8c15-f6b00e381f76', 'comment',
  'Redis serves dual duty as both a cache/session store and the message broker for Celery task distribution. Using one Redis instance for both eliminates a separate RabbitMQ dependency.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '75fa0db8-3ed3-4418-8c15-f6b00e381f76' AND body LIKE 'Redis serves dual duty%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9f5f0d1e-e926-4bbe-955c-ad16827189f4', 'comment',
  'ruff is a Python linter and formatter written in Rust — orders of magnitude faster than Black or flake8. Consistent formatting eliminates style debates in code reviews.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9f5f0d1e-e926-4bbe-955c-ad16827189f4' AND body LIKE 'ruff is a Python linter%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7583b76b-351b-4a1e-9793-78ff6f46b6e0', 'comment',
  'structlog produces JSON-formatted log entries with structured key-value fields. This makes logs machine-parseable for CloudWatch queries and Grafana dashboards without regex parsing.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7583b76b-351b-4a1e-9793-78ff6f46b6e0' AND body LIKE 'structlog produces JSON%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd50c7f8c-e95b-416b-b243-432c5009686f', 'comment',
  'Python 3.12 provides performance improvements, better error messages, and native support for the type syntax used throughout the codebase.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd50c7f8c-e95b-416b-b243-432c5009686f' AND body LIKE 'Python 3.12 provides%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '1d16f01f-82ac-4a75-94eb-91b88e874abe', 'comment',
  'Uvicorn is an ASGI (Asynchronous Server Gateway Interface) server. ASGI is the async successor to WSGI, enabling concurrent request handling without threads — critical for SSE streaming and background task coordination.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '1d16f01f-82ac-4a75-94eb-91b88e874abe' AND body LIKE 'Uvicorn is an ASGI%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8a00c2ca-5929-4a7a-b4a3-32c23f5fb5fe', 'comment',
  'The 300-line file limit forces decomposition into focused, single-responsibility modules. It is a hard rule enforced by ruff in CI — no exceptions.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8a00c2ca-5929-4a7a-b4a3-32c23f5fb5fe' AND body LIKE 'The 300-line file limit%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '3145e58c-369e-43cb-9e74-a7ef78f5a745', 'comment',
  'The 50-line function limit ensures every function does one thing and is easily testable. Functions approaching the limit are a signal to extract helper functions.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '3145e58c-369e-43cb-9e74-a7ef78f5a745' AND body LIKE 'The 50-line function limit%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '70590092-40f9-4ee4-bbe2-bd8316afcccc', 'comment',
  'Full type signatures enable mypy to catch type mismatches at build time. Combined with strict mode, this eliminates an entire class of runtime errors before code reaches production.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '70590092-40f9-4ee4-bbe2-bd8316afcccc' AND body LIKE 'Full type signatures enable%');

-- ============================================================================
-- BACKUP & RECOVERY
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c259d58b-0f83-48f3-908a-741df66f57b7', 'comment',
  '35-day retention means the database can be restored to any second in the past 5 weeks. Combined with Multi-AZ failover, this provides both high availability and disaster recovery.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c259d58b-0f83-48f3-908a-741df66f57b7' AND body LIKE '35-day retention means%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '36f332e2-67e2-4c18-a2dd-ffcded98714e', 'comment',
  'S3 versioning keeps prior versions of every object. If an export file is accidentally overwritten or deleted, the previous version can be recovered within 30 days.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '36f332e2-67e2-4c18-a2dd-ffcded98714e' AND body LIKE 'S3 versioning keeps%');

-- ============================================================================
-- BOUNDED CONTEXTS
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '23144672-34f0-4156-97a9-52da03447f8a', 'comment',
  'These 13 contexts map to the core business capabilities of artiFACT: managing taxonomies, facts, auth, audit, queues, signing, import, export, AI chat, search, feedback, presentation, and administration.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '23144672-34f0-4156-97a9-52da03447f8a' AND body LIKE 'These 13 contexts map%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '1d917643-8a06-4f4c-adb2-5993d296a1d0', 'comment',
  'Bounded contexts are a Domain-Driven Design concept: each context owns its own business logic and data access patterns. Modules interact through the kernel event bus and shared database models only.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '1d917643-8a06-4f4c-adb2-5993d296a1d0' AND body LIKE 'Bounded contexts are a Domain%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b1204ad8-7f65-4786-a5c1-a78d9f2be3a8', 'comment',
  '108 components across 13 contexts averages about 8 components per context. Each component is a focused Python module handling one responsibility (e.g., service.py, schemas.py, router.py).',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b1204ad8-7f65-4786-a5c1-a78d9f2be3a8' AND body LIKE '108 components across%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7942ced6-7aca-47e9-b6e0-f00623543fb3', 'comment',
  'Top-level directories make the module structure visible at a glance. No hunting through nested packages — "ls" at the project root shows all 13 contexts immediately.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7942ced6-7aca-47e9-b6e0-f00623543fb3' AND body LIKE 'Top-level directories make%');

-- ============================================================================
-- BUDGET & SUSTAINMENT
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '3de56c53-b4a0-4d63-96a3-e86f079e98ca', 'comment',
  '$2,100/year covers the COSMOS hosting consumption charge. Compare this to typical DoD SaaS contracts that run $500K–$2M/year. The system runs unattended between deployments.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '3de56c53-b4a0-4d63-96a3-e86f079e98ca' AND body LIKE '$2,100/year covers%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'adc47c1e-ed49-4e47-ada1-bd1310f7e8cf', 'comment',
  'Amazon Bedrock is a managed AI service in AWS GovCloud. It provides access to foundation models (Claude, Titan) at IL-4/IL-5 without managing GPU infrastructure.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'adc47c1e-ed49-4e47-ada1-bd1310f7e8cf' AND body LIKE 'Amazon Bedrock is a managed%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bf79c0f5-a266-48d5-92ac-3c8bb284866a', 'comment',
  'All core workflows — create, edit, approve, sign, export — function without any AI provider. Bedrock powers optional features like chat, import analysis, and document generation.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bf79c0f5-a266-48d5-92ac-3c8bb284866a' AND body LIKE 'All core workflows%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6b7710ac-69f1-4563-a40e-66dd3141b8b1', 'comment',
  'COSMOS = Cloud One SIPR/NIPR Management and Operations Services. Consumption-based hosting means artiFACT pays only for what it uses — no reserved instances, no long-term commitments.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6b7710ac-69f1-4563-a40e-66dd3141b8b1' AND body LIKE 'COSMOS = Cloud One SIPR%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '26b663b5-cd1b-4988-8af4-f11aee2c7234', 'comment',
  'Each organization configures their own Bedrock access via BYOK (Bring Your Own Key). artiFACT never holds a centralized AI budget — cost attribution is automatic.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '26b663b5-cd1b-4988-8af4-f11aee2c7234' AND body LIKE 'Each organization configures%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e8a4c016-a980-46a3-b1ff-d8ab87c07e15', 'comment',
  'The system runs unattended between deployments. No contractor staff needed to keep the lights on — automated backups, health checks, and log forwarding handle operations.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e8a4c016-a980-46a3-b1ff-d8ab87c07e15' AND body LIKE 'The system runs unattended%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '91f13ecf-ea33-4d7f-87ee-904e91bb08d0', 'comment',
  'Zero license fees because the entire stack is FOSS (Free and Open Source Software) — Python, PostgreSQL, Redis, FastAPI, HTMX, Alpine.js, Tailwind CSS.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '91f13ecf-ea33-4d7f-87ee-904e91bb08d0' AND body LIKE 'Zero license fees because%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '086df2b6-8865-463b-a7da-410e55977056', 'comment',
  'No vendor dependency means the government can operate, modify, or fork the system indefinitely without commercial agreements, renewals, or license negotiations.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '086df2b6-8865-463b-a7da-410e55977056' AND body LIKE 'No vendor dependency means%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '20cae7f0-c6db-4bba-9789-754bfb2126bc', 'comment',
  'Government-owned source code eliminates IP disputes, contractor lock-in, and the risk of losing access when a contract ends. Any government employee can maintain the system.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '20cae7f0-c6db-4bba-9789-754bfb2126bc' AND body LIKE 'Government-owned source code%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9f7526e1-5983-465a-981c-582b93ee6996', 'comment',
  'AI cost depends on usage volume — light users (occasional chat) trend toward $5/month; heavy users (frequent document generation) trend toward $50/month. Each organization pays their own Bedrock bill.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9f7526e1-5983-465a-981c-582b93ee6996' AND body LIKE 'AI cost depends on usage%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7d0435c6-7eb6-41b2-9efa-027e91ef8d9b', 'comment',
  'Automated health checks, log forwarding, backups, and container restarts mean no human intervention is needed for day-to-day operations. Deployments happen only when new features ship.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7d0435c6-7eb6-41b2-9efa-027e91ef8d9b' AND body LIKE 'Automated health checks%');

-- ============================================================================
-- BYOK ARCHITECTURE
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b607ead8-32fa-4d00-9605-915822aec32b', 'comment',
  'Amazon Bedrock in AWS GovCloud is authorized for IL-4/IL-5 data processing. Production will use Bedrock instead of direct API calls to commercial providers.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b607ead8-32fa-4d00-9605-915822aec32b' AND body LIKE 'Amazon Bedrock in AWS GovCloud%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '02b8e32b-ea36-4d69-8cf1-edd3003bbfe3', 'comment',
  'API keys are encrypted with AES-256-GCM before storage. The encryption master key lives in AWS Secrets Manager — the plaintext key never touches disk or application code.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '02b8e32b-ea36-4d69-8cf1-edd3003bbfe3' AND body LIKE 'API keys are encrypted with%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '1a4d75d8-cdb8-4ae7-aedf-662c74a9e63f', 'comment',
  'Keys are decrypted server-side only at the moment of an AI API call, then immediately discarded from memory. The browser never sees the plaintext key — all AI requests proxy through the backend.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '1a4d75d8-cdb8-4ae7-aedf-662c74a9e63f' AND body LIKE 'Keys are decrypted server-side%');

-- ============================================================================
-- CHAT & CORPUS GROUNDING
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b20a557e-86ae-4a30-b0e6-cac9ffae2dec', 'comment',
  'Permission-scoped fact loading ensures the AI cannot leak facts a user doesn''t have access to. The corpus grounding respects the same node-level permissions as the browse UI.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b20a557e-86ae-4a30-b0e6-cac9ffae2dec' AND body LIKE 'Permission-scoped fact loading%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'cc412af0-61fc-4dc1-8426-775203dc62fa', 'comment',
  'Reporting the actual fact count to the client provides transparency: users know exactly how many facts ground the AI''s response and can judge the completeness of the context.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'cc412af0-61fc-4dc1-8426-775203dc62fa' AND body LIKE 'Reporting the actual fact count%');

-- ============================================================================
-- CI/CD PIPELINE
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '16efbec7-276b-4a19-a70a-17ba2ad03577', 'comment',
  '80% overall with 95% on the kernel is enforced in CI. The pipeline fails if coverage drops below these thresholds — no code merges without meeting the coverage bar.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '16efbec7-276b-4a19-a70a-17ba2ad03577' AND body LIKE '80% overall with 95%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7511722b-d240-466a-8ce0-bd0d047ba0f3', 'comment',
  'The kernel handles auth, permissions, encryption, and events — a bug there affects every module. 95% coverage ensures the most critical shared code is thoroughly tested.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7511722b-d240-466a-8ce0-bd0d047ba0f3' AND body LIKE 'The kernel handles auth%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9c2d7bc1-1304-44f2-a378-7677c2472fa0', 'comment',
  'mypy strict mode catches type errors before runtime. Combined with full type annotations on every function, this eliminates an entire class of bugs at build time.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9c2d7bc1-1304-44f2-a378-7677c2472fa0' AND body LIKE 'mypy strict mode catches%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ae7cd82e-c2f9-4359-9127-75ad49032f95', 'comment',
  'pip-audit checks every Python dependency against the OSV (Open Source Vulnerabilities) database. A known-vulnerable dependency fails the build — no manual security review needed.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ae7cd82e-c2f9-4359-9127-75ad49032f95' AND body LIKE 'pip-audit checks every%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9fa1f6e1-503e-4355-b26e-4507bc45f78b', 'comment',
  'pytest runs the full test suite including unit, integration, and API tests. All tests execute inside Docker containers matching the production environment.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9fa1f6e1-503e-4355-b26e-4507bc45f78b' AND body LIKE 'pytest runs the full test%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c4607063-1832-4536-94b2-e98423a334ec', 'comment',
  'ruff check is a Python linter written in Rust that replaces flake8, isort, and dozens of other tools. It enforces code quality rules at build time.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c4607063-1832-4536-94b2-e98423a334ec' AND body LIKE 'ruff check is a Python linter%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '166715eb-c110-4ee6-bce2-bc3a62c12e3f', 'comment',
  'SBOM = Software Bill of Materials. Required by Executive Order 14028 for all federal software. The CI pipeline generates it automatically on every build.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '166715eb-c110-4ee6-bce2-bc3a62c12e3f' AND body LIKE 'SBOM = Software Bill of Materials. Required%');

-- ============================================================================
-- COLLIBRA REGISTRATION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7060766a-6644-4721-a8f8-ae4e3d8b9606', 'comment',
  'Every fact in the corpus is human-reviewed and approved before publication. This means Collibra can rate artiFACT''s data quality as "high" — it''s not raw data or AI-generated content.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7060766a-6644-4721-a8f8-ae4e3d8b9606' AND body LIKE 'Every fact in the corpus%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '54744197-996d-4d3d-8fc6-9889df4173d8', 'comment',
  'OpenAPI 3.0 is the industry standard for describing REST APIs. The spec is auto-generated from FastAPI route definitions, so documentation never drifts from implementation.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '54744197-996d-4d3d-8fc6-9889df4173d8' AND body LIKE 'OpenAPI 3.0 is the industry%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '4ec44aa1-198e-4c7a-a468-fc2d0abefe8e', 'comment',
  'The delta feed API streams changes as they occur. Advana can poll for new data as frequently as needed — near-real-time freshness without batch ETL processes.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '4ec44aa1-198e-4c7a-a468-fc2d0abefe8e' AND body LIKE 'The delta feed API streams%');

-- ============================================================================
-- CONTAINER ARCHITECTURE
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '953ae6b1-0175-4991-bca1-c123bc96b53e', 'comment',
  'Certbot handles automatic TLS certificate provisioning and renewal via Let''s Encrypt. Used in development and staging; production TLS terminates at the ALB.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '953ae6b1-0175-4991-bca1-c123bc96b53e' AND body LIKE 'Certbot handles automatic%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f2aa7dfe-be16-40e3-8fdc-4ff5a8e2c057', 'comment',
  'MinIO is an S3-compatible object store. In development, it stands in for AWS S3 so file upload/download code works identically in both environments without conditionals.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f2aa7dfe-be16-40e3-8fdc-4ff5a8e2c057' AND body LIKE 'MinIO is an S3-compatible%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a5aca14e-5b02-4e7f-b3ed-b09854ea569d', 'comment',
  'Nginx serves as the reverse proxy in development — handling TLS termination, static file serving, and request routing to the web container. Production replaces it with the ALB.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a5aca14e-5b02-4e7f-b3ed-b09854ea569d' AND body LIKE 'Nginx serves as the reverse%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'db5b8ee3-77b0-4292-9c59-a4aa39014891', 'comment',
  'PostgreSQL 16 runs as a container in development with the same major version as production RDS. This ensures SQL compatibility between environments.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'db5b8ee3-77b0-4292-9c59-a4aa39014891' AND body LIKE 'PostgreSQL 16 runs as a container%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6e9ca751-0702-48fd-bacf-c256bd8ba9ba', 'comment',
  'The Redis container provides caching, session storage, rate limiting, and the Celery message broker — matching the production ElastiCache configuration.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6e9ca751-0702-48fd-bacf-c256bd8ba9ba' AND body LIKE 'The Redis container provides%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6a2e2a62-fbf8-4d66-bb65-7978fa2dbcf4', 'comment',
  'The web container runs Uvicorn serving the FastAPI application. In development it runs with --reload for hot code reloading; in production it runs multiple workers behind the ALB.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6a2e2a62-fbf8-4d66-bb65-7978fa2dbcf4' AND body LIKE 'The web container runs Uvicorn%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2717350a-9a72-4d49-8ec1-44ce1ab7ba95', 'comment',
  'The worker container runs Celery processes for background tasks — document generation, import analysis, data retention cleanup. Separate from the web container so long-running tasks don''t block HTTP requests.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2717350a-9a72-4d49-8ec1-44ce1ab7ba95' AND body LIKE 'The worker container runs Celery%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd1f6bfab-d8a6-4d45-b061-91d55a699693', 'comment',
  'Celery workers process queued tasks asynchronously. Document generation can take 30+ seconds — running it in a worker prevents the web server from timing out.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd1f6bfab-d8a6-4d45-b061-91d55a699693' AND body LIKE 'Celery workers process queued%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '46ac6a3c-4a7c-4397-9091-afaa0635001b', 'comment',
  'Uvicorn --reload watches for file changes and restarts the server automatically. Developers save a file and see the change immediately without manually restarting the container.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '46ac6a3c-4a7c-4397-9091-afaa0635001b' AND body LIKE 'Uvicorn --reload watches%');

-- ============================================================================
-- CORE TABLES
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '5e249a89-e7ae-4be4-81f3-08dd0dc3d475', 'comment',
  'fc_fact maintains pointers to the current (latest), published (approved), and signed versions. This enables instant lookups without scanning the version history.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '5e249a89-e7ae-4be4-81f3-08dd0dc3d475' AND body LIKE 'fc_fact maintains pointers%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7526a457-275e-4b10-8a35-84c7281566a6', 'comment',
  'The display_sentence is the human-readable fact text. metadata_tags enable faceted filtering. classification tracks CUI status per fact. State drives the approval workflow.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7526a457-275e-4b10-8a35-84c7281566a6' AND body LIKE 'The display_sentence is the human%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6cd0165e-39e0-4721-aa8d-14dde603cb33', 'comment',
  'Each version is an immutable snapshot. Editing a fact creates a new version rather than modifying the existing one — the complete history of every change is preserved.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6cd0165e-39e0-4721-aa8d-14dde603cb33' AND body LIKE 'Each version is an immutable%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'cf5e9e89-46a5-4c9a-936d-52087c1b4459', 'comment',
  'parent_node_uid creates the tree structure. node_depth enables efficient ancestor queries. sort_order controls the display sequence within a parent node.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'cf5e9e89-46a5-4c9a-936d-52087c1b4459' AND body LIKE 'parent_node_uid creates the tree%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bcc14e37-b82d-43f7-94af-5bd70a8bf71e', 'comment',
  'fc_node is the backbone of artiFACT''s data model. The hierarchical taxonomy organizes facts into a tree — programs contain branches, branches contain leaves, leaves contain facts.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bcc14e37-b82d-43f7-94af-5bd70a8bf71e' AND body LIKE 'fc_node is the backbone%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a32f3063-cde0-4ff7-bb66-44b3b051e05e', 'comment',
  'Five granular roles enable least-privilege access. A viewer can browse; a contributor can propose; a subapprover helps review; an approver publishes; a signatory provides official attestation.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a32f3063-cde0-4ff7-bb66-44b3b051e05e' AND body LIKE 'Five granular roles enable%');

-- ============================================================================
-- COSMOS DEPLOYMENT
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6633ca66-5270-40db-b01f-e12fdc7f39f2', 'comment',
  'ECR = Elastic Container Registry. AWS''s Docker image registry. Container images are pushed to ECR by CI/CD and pulled by ECS Fargate at deployment time.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6633ca66-5270-40db-b01f-e12fdc7f39f2' AND body LIKE 'ECR = Elastic Container%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bdef4e5c-46db-4d68-9295-79cb38422221', 'comment',
  'cache.t3.micro is the smallest ElastiCache instance type — sufficient for artiFACT''s session, cache, and Celery broker workload. Keeps costs minimal while providing sub-millisecond latency.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bdef4e5c-46db-4d68-9295-79cb38422221' AND body LIKE 'cache.t3.micro is the smallest%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '83672fe5-6245-45e8-84e0-c9956ac2e0c4', 'comment',
  '2 web tasks provide high availability — if one task fails, the other continues serving requests while ECS replaces the failed task automatically.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '83672fe5-6245-45e8-84e0-c9956ac2e0c4' AND body LIKE '2 web tasks provide%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '88c61f86-864f-4045-bf5a-5e74b71f8f61', 'comment',
  'db.t3.small is a burstable instance type — sufficient for artiFACT''s workload with the ability to burst CPU for peak loads. PostgreSQL 16 matches the development container version exactly.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '88c61f86-864f-4045-bf5a-5e74b71f8f61' AND body LIKE 'db.t3.small is a burstable%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '99848fd4-73a8-4c6e-9f1a-b2d8d5bcfdd8', 'comment',
  'S3 buckets are organized by function: exports (generated documents), snapshots (admin-triggered pg_dump backups), and uploads (document import files).',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '99848fd4-73a8-4c6e-9f1a-b2d8d5bcfdd8' AND body LIKE 'S3 buckets are organized%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2ebdbc7b-e254-4fd7-80b3-9448297bb5e2', 'comment',
  'AWS Secrets Manager provides hardware-backed storage with IAM-controlled access, automatic rotation, and audit logging. Database credentials are never in config files or environment variables.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2ebdbc7b-e254-4fd7-80b3-9448297bb5e2' AND body LIKE 'AWS Secrets Manager provides hardware%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '04672929-df81-4f2f-9cd8-21f280f563e5', 'comment',
  'The encryption master key encrypts all user AI API keys (BYOK). Storing it in Secrets Manager means the key is fetched at runtime and held only in memory — never written to disk.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '04672929-df81-4f2f-9cd8-21f280f563e5' AND body LIKE 'The encryption master key encrypts%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f3f98cf2-0d21-4383-b9ff-9511dbc5917d', 'comment',
  'S3 versioning keeps previous versions of every object. Combined with 30-day retention on deleted objects, this provides a safety net against accidental overwrites or deletions.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f3f98cf2-0d21-4383-b9ff-9511dbc5917d' AND body LIKE 'S3 versioning keeps previous%');

-- ============================================================================
-- CUI HANDLING
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '05aa3997-3305-4c0e-912f-41304b18f0ed', 'comment',
  'Bedrock processes fact text for AI features but receives no user PII — no names, emails, EDIPIs, or CAC DNs are included in AI prompts. Only fact content is sent.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '05aa3997-3305-4c0e-912f-41304b18f0ed' AND body LIKE 'Bedrock processes fact text%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'eaafec60-cc67-41e5-aaf0-588b4b1aa2eb', 'comment',
  'CUI = Controlled Unclassified Information (32 CFR Part 2002). CUI banners appear automatically when any fact included in a view or document carries CUI classification — no manual marking needed.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'eaafec60-cc67-41e5-aaf0-588b4b1aa2eb' AND body LIKE 'CUI = Controlled Unclassified%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '51c4bc5e-5b27-4038-b2a4-3380d2386363', 'comment',
  'Per-fact classification enables granular CUI tracking. A node can contain both unclassified and CUI facts — the system knows exactly which facts carry marking requirements.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '51c4bc5e-5b27-4038-b2a4-3380d2386363' AND body LIKE 'Per-fact classification enables%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '264bf514-609b-4de7-b55d-d92a261e1f95', 'comment',
  'DOCX cover page markings comply with DoDI 5200.48 requirements for CUI document marking. The highest classification of any included fact determines the document-level marking.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '264bf514-609b-4de7-b55d-d92a261e1f95' AND body LIKE 'DOCX cover page markings comply%');

-- ============================================================================
-- CUI TRAINING
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '5efa23b3-a0d6-4719-8997-55a60a69c31c', 'comment',
  'DoD CUI awareness training is mandated by DoDI 5200.48. This is a personnel requirement, not an application feature — each user''s command is responsible for tracking compliance.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '5efa23b3-a0d6-4719-8997-55a60a69c31c' AND body LIKE 'DoD CUI awareness training%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'baedc986-23a6-4271-a4f0-db67131179a4', 'comment',
  'The login splash screen serves as a procedural control — users certify CUI awareness before accessing the system. This is a standard DoD information system access banner.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'baedc986-23a6-4271-a4f0-db67131179a4' AND body LIKE 'The login splash screen serves%');

-- ============================================================================
-- DATA EXPORT & PORTABILITY
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '515715ac-a943-4939-95c9-540289c4ad8f', 'comment',
  'The sync/full endpoint is artiFACT''s data portability guarantee. It dumps the complete corpus as structured JSON — facts, versions, signatures, audit events, user records — for migration or archival.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '515715ac-a943-4939-95c9-540289c4ad8f' AND body LIKE 'The sync/full endpoint is%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2dbbde22-f116-4095-9586-5e60e7491adc', 'comment',
  'Signed S3 URLs grant temporary access to a specific file without requiring the user to have AWS credentials. 24 hours is long enough to download but short enough to prevent link sharing.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2dbbde22-f116-4095-9586-5e60e7491adc' AND body LIKE 'Signed S3 URLs grant temporary%');

-- ============================================================================
-- DATA LAYER
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bcf6a8ea-1291-4ac7-80b0-da91287a7754', 'comment',
  'gen_random_uuid() generates UUID v4 values at the database level, ensuring globally unique identifiers regardless of which application instance creates the row.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bcf6a8ea-1291-4ac7-80b0-da91287a7754' AND body LIKE 'gen_random_uuid() generates%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8c13833c-d1c1-4cd6-a138-d4070b5717b8', 'comment',
  'TIMESTAMPTZ DEFAULT now() means every row automatically records its creation time in UTC. No application code needed to set the timestamp — it cannot be forgotten or faked.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8c13833c-d1c1-4cd6-a138-d4070b5717b8' AND body LIKE 'TIMESTAMPTZ DEFAULT now()%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '24b57b2d-7c9e-496f-ab4b-86d1305e7962', 'comment',
  'MinIO provides an S3-compatible API for local development. Code that uses the S3 SDK works identically against MinIO and AWS S3 — no environment-specific conditionals.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '24b57b2d-7c9e-496f-ab4b-86d1305e7962' AND body LIKE 'MinIO provides an S3-compatible%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '70427747-705e-46cd-a342-7f5713b4de01', 'comment',
  'PostgreSQL 16 provides advanced features used throughout artiFACT: JSONB columns, tsvector full-text search, gen_random_uuid(), CTEs, and window functions.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '70427747-705e-46cd-a342-7f5713b4de01' AND body LIKE 'PostgreSQL 16 provides advanced%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9cab2a55-dc5a-413a-9030-dce9930acffd', 'comment',
  'Redis session storage enables horizontal scaling — any web task can serve any user''s request because the session lives in Redis, not in the web process''s memory.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9cab2a55-dc5a-413a-9030-dce9930acffd' AND body LIKE 'Redis session storage enables%');

-- ============================================================================
-- DATA RETENTION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '116800ea-e6a4-4aa9-a772-9d13203cd906', 'comment',
  'Six-year audit trail retention aligns with NARA GRS 3.2 Item 031 for system access and security audit trails. Celery beat automates the cleanup after the retention period.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '116800ea-e6a4-4aa9-a772-9d13203cd906' AND body LIKE 'Six-year audit trail%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '44fe786d-ea59-49f5-aaa3-7bb89e6292c5', 'comment',
  'Three-year retention per NARA GRS 5.2 Item 020. Old fact versions are kept 3 years after being superseded, then eligible for automated cleanup.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '44fe786d-ea59-49f5-aaa3-7bb89e6292c5' AND body LIKE 'Three-year retention per%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9bd67fc3-5b6e-4b28-b68e-ed60aa5fad91', 'comment',
  'Per NARA GRS 3.1 Item 010, superseded configuration records have no retention requirement. When an admin updates a feature flag, the old value can be deleted immediately.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9bd67fc3-5b6e-4b28-b68e-ed60aa5fad91' AND body LIKE 'Per NARA GRS 3.1%');

-- ============================================================================
-- DITPR REGISTRATION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '33a35a17-85d7-4ea5-8066-da4863c5647d', 'comment',
  'DITPR = DoD IT Portfolio Repository. The authoritative registry of all DoD information systems, required by DoDI 8510.01 for any system seeking an Authority to Operate.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '33a35a17-85d7-4ea5-8066-da4863c5647d' AND body LIKE 'DITPR = DoD IT Portfolio%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '424768b5-72ba-4803-a6a6-89d23525fa34', 'comment',
  'CUI = Controlled Unclassified Information. The classification level determines which security controls apply and which hosting environments are authorized.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '424768b5-72ba-4803-a6a6-89d23525fa34' AND body LIKE 'CUI = Controlled Unclassified. The classification%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9f8d4f40-20bc-41e9-8266-50208dae78a7', 'comment',
  'AWS GovCloud is an isolated AWS region designed for sensitive government workloads. It meets FedRAMP High and DoD IL-4/IL-5 requirements.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9f8d4f40-20bc-41e9-8266-50208dae78a7' AND body LIKE 'AWS GovCloud is an isolated%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'aebdddc3-e2df-468f-9ab7-98c65caa87f1', 'comment',
  'COSMOS NIWC Pacific = Cloud One SIPR/NIPR Management and Operations Services at Naval Information Warfare Center Pacific. A managed DoD cloud platform providing shared infrastructure and ATO boundary.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'aebdddc3-e2df-468f-9ab7-98c65caa87f1' AND body LIKE 'COSMOS NIWC Pacific = Cloud One%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e3379b50-61ce-476d-bb9f-8b62fc30d773', 'comment',
  'IL-4 = Impact Level 4. Covers Controlled Unclassified Information in commercial cloud environments. Defined by the DoD Cloud Computing Security Requirements Guide.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e3379b50-61ce-476d-bb9f-8b62fc30d773' AND body LIKE 'IL-4 = Impact Level 4%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7643474b-fa95-4860-a230-434f61b22cff', 'comment',
  'IL-5 = Impact Level 5. Covers CUI in DoD cloud and higher-sensitivity unclassified data. Requires dedicated government infrastructure like AWS GovCloud.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7643474b-fa95-4860-a230-434f61b22cff' AND body LIKE 'IL-5 = Impact Level 5%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e31cc86c-ae6b-4b55-b679-d0382095a190', 'comment',
  '"Major Application" is a DITPR classification for IT systems that require an independent ATO assessment. It triggers specific documentation and oversight requirements.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e31cc86c-ae6b-4b55-b679-d0382095a190' AND body LIKE '"Major Application" is a DITPR%');

-- ============================================================================
-- DOCUMENT GENERATION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8d430272-da49-4982-bec3-d8aa80d27746', 'comment',
  'SSE = Server-Sent Events. Progress updates stream to the browser in real time as each document section is generated — users see live status without polling.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8d430272-da49-4982-bec3-d8aa80d27746' AND body LIKE 'SSE = Server-Sent Events. Progress%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '91176e8c-6a24-4594-a48e-9a1950ed40ad', 'comment',
  'Running generation as a Celery background task prevents HTTP timeouts. The web server returns immediately while the worker processes the AI calls, which can take 30+ seconds.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '91176e8c-6a24-4594-a48e-9a1950ed40ad' AND body LIKE 'Running generation as a Celery%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ab856f59-b598-4516-b66d-6ce77ae0bf3e', 'comment',
  'Prefilter scores every published fact against all template sections simultaneously using the LLM. This determines which facts belong in which document sections before any prose is generated.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ab856f59-b598-4516-b66d-6ce77ae0bf3e' AND body LIKE 'Prefilter scores every published%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'af1fb8b8-cf98-4cf3-8c2c-ec13706cd05a', 'comment',
  'The synthesizer takes the prefilter''s fact-to-section assignments and generates coherent prose. Separating this from prefilter lets users review which facts map to which sections before spending AI tokens.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'af1fb8b8-cf98-4cf3-8c2c-ec13706cd05a' AND body LIKE 'The synthesizer takes the prefilter%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c71bd3bb-70c1-41ad-a5b5-7ea5b1d26f76', 'comment',
  'CUI markings in generated documents are applied automatically based on the classification of included facts. Headers, footers, and cover pages carry the appropriate markings per DoDI 5200.48.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c71bd3bb-70c1-41ad-a5b5-7ea5b1d26f76' AND body LIKE 'CUI markings in generated documents%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2a24b953-cc28-47a5-8b3a-ce9adef9adcf', 'comment',
  'Views show users which facts the AI would assign to each template section without generating prose. This preview saves AI token costs and lets users refine the corpus before committing to full generation.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2a24b953-cc28-47a5-8b3a-ce9adef9adcf' AND body LIKE 'Views show users which facts%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'fbddcc30-2b95-4df5-80f8-4f7d7034dd87', 'comment',
  'The views feature is like a dry run: it shows the fact-to-section mapping from prefilter without running synthesis. Users can identify missing facts or misassignments before incurring AI costs.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'fbddcc30-2b95-4df5-80f8-4f7d7034dd87' AND body LIKE 'The views feature is like%');

-- ============================================================================
-- ENCRYPTION & DATA PROTECTION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '4d3acaef-ddd9-4e54-94ef-22f6c10ae806', 'comment',
  'Amazon Bedrock in AWS GovCloud is authorized at IL-4/IL-5 for processing CUI data. AI operations stay within the authorization boundary.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '4d3acaef-ddd9-4e54-94ef-22f6c10ae806' AND body LIKE 'Amazon Bedrock in AWS GovCloud is authorized%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'fffba7b3-355d-410d-b219-39f5f1ff3202', 'comment',
  'AES-256 encryption at rest is a baseline requirement for CUI data per CNSS Policy 15. RDS provides this transparently — no application-level encryption needed for database rows.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'fffba7b3-355d-410d-b219-39f5f1ff3202' AND body LIKE 'AES-256 encryption at rest%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6ffc2ff3-a7d7-40f3-b62d-2266266dbcff', 'comment',
  'TLS 1.2+ encrypts all data in transit between clients, services, and databases. Older TLS versions are disabled as required by NIST SP 800-52 Rev 2.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6ffc2ff3-a7d7-40f3-b62d-2266266dbcff' AND body LIKE 'TLS 1.2+ encrypts%');

-- ============================================================================
-- EXTERNAL DATA SHARING
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '34c6803f-3ad6-44f4-a9e6-2b1bc3e84212', 'comment',
  'Service accounts authenticate with scoped API keys — not user sessions. Each key has explicit permissions (read, sync) and can be revoked independently.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '34c6803f-3ad6-44f4-a9e6-2b1bc3e84212' AND body LIKE 'Service accounts authenticate with scoped%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'dfe56c4e-9e56-4b79-9202-a7ea472fc50c', 'comment',
  'The sync API includes display names and roles for attribution (who approved what) but excludes EDIPI and email to follow minimum necessary disclosure principles.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'dfe56c4e-9e56-4b79-9202-a7ea472fc50c' AND body LIKE 'The sync API includes display%');

-- ============================================================================
-- EXTERNAL INTEGRATIONS
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b3e66269-be45-4940-9f54-115680be7f2c', 'comment',
  'Apigee is Google''s API gateway product used by Advana/Jupiter. It auto-discovers artiFACT''s OpenAPI spec for routing, authentication, and rate limiting at the gateway level.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b3e66269-be45-4940-9f54-115680be7f2c' AND body LIKE 'Apigee is Google''s API%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '5af6a5e3-eba9-4f16-9652-363142be23a5', 'comment',
  'The delta feed endpoint returns only events newer than the consumer''s cursor position. Advana polls this to stay current without re-downloading the entire corpus each time.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '5af6a5e3-eba9-4f16-9652-363142be23a5' AND body LIKE 'The delta feed endpoint returns%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'df97d3fd-4acf-4552-945f-e46f22b77033', 'comment',
  'A monotonic seq cursor only increases — no two events share the same value. Unlike timestamps, it guarantees strict ordering without clock skew issues.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'df97d3fd-4acf-4552-945f-e46f22b77033' AND body LIKE 'A monotonic seq cursor only%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '675c7c1b-838c-4fa4-8d30-5178e6930950', 'comment',
  'BIGINT seq avoids the problems of timestamp-based cursors: clock skew, sub-millisecond event collisions, and timezone ambiguity. Each event gets a unique, ordered integer.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '675c7c1b-838c-4fa4-8d30-5178e6930950' AND body LIKE 'BIGINT seq avoids the problems%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e3cef7a9-2df5-4442-96d6-b6ebac72d552', 'comment',
  'OpenAPI 3.0 spec auto-generation means the API documentation updates every time a route changes. External consumers always have an accurate, machine-readable contract.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e3cef7a9-2df5-4442-96d6-b6ebac72d552' AND body LIKE 'OpenAPI 3.0 spec auto-generation%');

-- ============================================================================
-- FACT LIFECYCLE
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'fb03e7db-b8e5-4614-b1b0-e5e8e40d573e', 'comment',
  'The initial version starts in "proposed" state and enters the approval queue. Contributors cannot bypass the review process — all new content requires approver sign-off.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'fb03e7db-b8e5-4614-b1b0-e5e8e40d573e' AND body LIKE 'The initial version starts%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b29ab142-6f60-44d8-b5c8-db7d5073053e', 'comment',
  'Approvers can bypass the proposal queue when creating facts directly. This streamlines bulk data entry during initial corpus population.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b29ab142-6f60-44d8-b5c8-db7d5073053e' AND body LIKE 'Approvers can bypass%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '7ae97163-37ab-4ba4-bad2-e1cfb2c88427', 'comment',
  'Retiring a fact removes it from the active corpus without deleting it. The fact and its history remain in the database for retention compliance and audit purposes.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '7ae97163-37ab-4ba4-bad2-e1cfb2c88427' AND body LIKE 'Retiring a fact removes%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '1448979e-1abc-447f-aec2-4ae7821a11cc', 'comment',
  'Signing is an official attestation by a signatory that the published fact is accurate and authoritative. It''s the highest level of endorsement in the approval hierarchy.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '1448979e-1abc-447f-aec2-4ae7821a11cc' AND body LIKE 'Signing is an official attestation%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '34c70629-282c-462a-8f39-7dddbefa6b8f', 'comment',
  'Unretiring restores a fact to the active corpus. Only an approver or higher can unretire, ensuring retired facts don''t accidentally re-enter the corpus without review.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '34c70629-282c-462a-8f39-7dddbefa6b8f' AND body LIKE 'Unretiring restores a fact%');

-- ============================================================================
-- FRONTEND
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b56c3bb0-7b97-4eb1-abbd-8b49beaee305', 'comment',
  'Alpine.js is a lightweight JavaScript framework (~15KB) for client-side interactivity. It handles dropdowns, modals, and form validation without the complexity of React or Vue.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b56c3bb0-7b97-4eb1-abbd-8b49beaee305' AND body LIKE 'Alpine.js is a lightweight%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c04e71e3-ea3d-47ee-8f95-49264b87e7d7', 'comment',
  'HTMX enables dynamic updates by swapping HTML fragments from the server. No JSON API layer needed — the server renders the final HTML and HTMX puts it on the page.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c04e71e3-ea3d-47ee-8f95-49264b87e7d7' AND body LIKE 'HTMX enables dynamic updates%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c6f0cb86-7200-4058-8dcf-f9fff84ff45a', 'comment',
  'Jinja2 autoescape converts special characters like < and > into safe HTML entities automatically. This prevents XSS (Cross-Site Scripting) attacks without requiring developers to remember to escape each value.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c6f0cb86-7200-4058-8dcf-f9fff84ff45a' AND body LIKE 'Jinja2 autoescape converts%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '3d1b2e5a-a928-49bf-89fa-fa5982185521', 'comment',
  'Tailwind CSS CDN means zero build step for styles. Utility classes are applied directly in HTML templates — no separate CSS files to maintain or compile.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '3d1b2e5a-a928-49bf-89fa-fa5982185521' AND body LIKE 'Tailwind CSS CDN means%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '88d8689b-7e6d-4437-b1ff-ac22dc7807a5', 'comment',
  'Zero build step means no webpack, no npm, no node_modules. The frontend ships as plain HTML templates, CDN-loaded CSS/JS, and Jinja2 server-side rendering.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '88d8689b-7e6d-4437-b1ff-ac22dc7807a5' AND body LIKE 'Zero build step means%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '21a3889b-951d-457d-93be-062ec543dd5d', 'comment',
  'Server-rendered HTML via Jinja2 means the server does all the work — the browser receives complete HTML pages. No client-side JavaScript framework required for rendering.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '21a3889b-951d-457d-93be-062ec543dd5d' AND body LIKE 'Server-rendered HTML via Jinja2%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'de34c60c-f506-4319-9f24-230197ae6e39', 'comment',
  'Zero npm eliminates the node_modules dependency tree — often 500MB+ of transitive dependencies with potential supply chain vulnerabilities. The frontend uses only CDN-loaded libraries.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'de34c60c-f506-4319-9f24-230197ae6e39' AND body LIKE 'Zero npm eliminates%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd9a23046-aae1-4549-a006-baed5ab9bbee', 'comment',
  'Webpack is a JavaScript module bundler typically required for React/Vue apps. artiFACT''s server-rendered architecture eliminates the need for any JavaScript build pipeline.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd9a23046-aae1-4549-a006-baed5ab9bbee' AND body LIKE 'Webpack is a JavaScript module%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '053fc9c3-fdc8-47ad-9fb1-034aadb1c8c2', 'comment',
  'CSS variables in theme.css enable runtime theme switching without reloading. Three modes support different user preferences and accessibility needs.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '053fc9c3-fdc8-47ad-9fb1-034aadb1c8c2' AND body LIKE 'CSS variables in theme.css%');

-- ============================================================================
-- GRACEFUL DEGRADATION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a435c91c-64df-4081-b7e0-0c03e924f347', 'comment',
  'Returning -1 signals to the UI that the actual count is unavailable. The UI renders a dash instead of a number, rather than showing a stale cached value or erroring out.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a435c91c-64df-4081-b7e0-0c03e924f347' AND body LIKE 'Returning -1 signals to the UI%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'fcf86c00-835a-4f97-98b6-3d0df748c1b6', 'comment',
  'Logging a warning when Redis is down (rather than blocking requests) is intentional fail-open behavior. Rate limiting is defense-in-depth, not a primary security control.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'fcf86c00-835a-4f97-98b6-3d0df748c1b6' AND body LIKE 'Logging a warning when Redis%');

-- ============================================================================
-- IMPORT ANALYSIS
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'fe256e51-be16-458a-a33d-7bc765fc7dbe', 'comment',
  'Running analysis as a Celery background task prevents HTTP timeouts. AI-powered document parsing can take minutes for large files — the user sees real-time progress via SSE.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'fe256e51-be16-458a-a33d-7bc765fc7dbe' AND body LIKE 'Running analysis as a Celery%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a5a6a13d-49ca-44d3-9a2f-3674f5885e84', 'comment',
  'AI-extracted facts are staged, not auto-published. A human reviews each one before it enters the proposal queue — maintaining the same four-eyes review standard as manually created facts.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a5a6a13d-49ca-44d3-9a2f-3674f5885e84' AND body LIKE 'AI-extracted facts are staged%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c5b2d155-1001-437b-8425-5d361db6394a', 'comment',
  'Document import is the on-ramp from traditional Word-based acquisition documentation. Users upload existing artifacts and the AI extracts atomic facts for review and approval.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c5b2d155-1001-437b-8425-5d361db6394a' AND body LIKE 'Document import is the on-ramp%');

-- ============================================================================
-- INFRASTRUCTURE
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '75269965-ae22-4dd2-8492-69ec6aa87f58', 'comment',
  'Docker Compose defines the complete local development stack: web, worker, postgres, redis, minio, nginx, and certbot. One command (docker compose up) starts everything.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '75269965-ae22-4dd2-8492-69ec6aa87f58' AND body LIKE 'Docker Compose defines the complete%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2837434c-41a3-45b6-84cc-986c515430ad', 'comment',
  'Terraform = Infrastructure as Code tool. Every cloud resource (ECS tasks, RDS instances, S3 buckets, IAM roles) is defined in declarative .tf files. The production environment can be recreated from scratch.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2837434c-41a3-45b6-84cc-986c515430ad' AND body LIKE 'Terraform = Infrastructure as Code%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '012dab6d-9820-41f0-9f5c-5c9492775ad1', 'comment',
  'AWS GovCloud is an isolated AWS region designed for sensitive government workloads. It meets FedRAMP High and DoD IL-4/IL-5 requirements for CUI data handling.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '012dab6d-9820-41f0-9f5c-5c9492775ad1' AND body LIKE 'AWS GovCloud is an isolated AWS region designed for sensitive%');

-- ============================================================================
-- KERNEL SERVICES
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ee2ea09a-7d61-4f77-9e3b-136314a25cc0', 'comment',
  'The kernel is the only code that can be imported across module boundaries. Shared concerns like auth, permissions, events, and database sessions live here to prevent cross-module coupling.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ee2ea09a-7d61-4f77-9e3b-136314a25cc0' AND body LIKE 'The kernel is the only code%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '10afc299-caee-4f2c-986b-86f18d708524', 'comment',
  'No inter-module imports is the fundamental architectural constraint. If module A needs data from module B, it reads the shared database — never imports B''s internal code.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '10afc299-caee-4f2c-986b-86f18d708524' AND body LIKE 'No inter-module imports is%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd8d34456-e384-4bb6-a2e3-14730abdf4fd', 'comment',
  'Making the kernel the sole shared import creates a clear dependency graph: modules depend on kernel, kernel depends on nothing. This prevents circular dependencies and keeps modules independently testable.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd8d34456-e384-4bb6-a2e3-14730abdf4fd' AND body LIKE 'Making the kernel the sole%');

-- ============================================================================
-- MODULE COMMUNICATION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'd1711fe3-5822-4d26-8c78-9d50675a5fd0', 'comment',
  'Reading through the database prevents tight coupling. Module A doesn''t need to know module B''s internal API — it queries the shared data model via SQLAlchemy.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'd1711fe3-5822-4d26-8c78-9d50675a5fd0' AND body LIKE 'Reading through the database prevents%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e20728ec-c4f4-4d09-be92-e6ba7a2a48aa', 'comment',
  'Writes go through the event bus so that side effects (audit logging, cache invalidation, badge updates) happen automatically. The writing module doesn''t need to know who reacts to its events.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e20728ec-c4f4-4d09-be92-e6ba7a2a48aa' AND body LIKE 'Writes go through the event bus%');

-- ============================================================================
-- MONITORING & LOGGING
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'eb848ba3-01ca-4623-a816-4228646f8c28', 'comment',
  'Health check endpoints verify that the application can actually reach its dependencies — not just that the process is running. A healthy response means database, Redis, and S3 are all reachable.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'eb848ba3-01ca-4623-a816-4228646f8c28' AND body LIKE 'Health check endpoints verify%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '5cb93f93-8dd7-4217-8708-ecddc1cb0b11', 'comment',
  'CloudWatch is AWS''s centralized logging service. Structured JSON logs from structlog are machine-parseable, enabling queries like "show all errors in the signing module in the last hour."',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '5cb93f93-8dd7-4217-8708-ecddc1cb0b11' AND body LIKE 'CloudWatch is AWS''s centralized%');

-- ============================================================================
-- OWASP ZAP RESULTS
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2e001cd1-ead5-4de2-9cc1-b11867279874', 'comment',
  'HIGH findings indicate vulnerabilities that could be exploited remotely with significant impact. These are deployment blockers — no exceptions.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2e001cd1-ead5-4de2-9cc1-b11867279874' AND body LIKE 'HIGH findings indicate%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '059e7c91-d105-4910-bcc9-1bf5dafa0c3b', 'comment',
  'MEDIUM findings are tracked and remediated on a risk-based timeline. They indicate real vulnerabilities but with limited exploitability or impact.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '059e7c91-d105-4910-bcc9-1bf5dafa0c3b' AND body LIKE 'MEDIUM findings are tracked%');

-- ============================================================================
-- PERMISSION MODEL
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '10d555d1-24c6-4861-99c1-a3224668e422', 'comment',
  'Grant cascading means a permission on a parent node automatically applies to all children. Granting "approver" on "Architecture & Design" gives approval rights on every child node beneath it.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '10d555d1-24c6-4861-99c1-a3224668e422' AND body LIKE 'Grant cascading means%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '4434269f-3306-4d6e-bb45-a58eeb416f8c', 'comment',
  'Ancestor-walking permission resolution means the system checks the current node, then its parent, then grandparent, up to root. The first matching grant determines the user''s effective role.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '4434269f-3306-4d6e-bb45-a58eeb416f8c' AND body LIKE 'Ancestor-walking permission%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f71ca48f-40cb-48b4-a463-572b126187fe', 'comment',
  'Cache invalidation on grant events ensures new permissions take effect promptly. Without this, a newly granted user would wait up to 5 minutes (the cache TTL) before their access works.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f71ca48f-40cb-48b4-a463-572b126187fe' AND body LIKE 'Cache invalidation on grant events%');

-- ============================================================================
-- PII INVENTORY
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '06469fe5-7089-4c74-b522-de90af6bf3d8', 'comment',
  'Admin-only user list visibility follows least-privilege principles. Non-admins see display names only on approval and signature records where attribution is operationally necessary.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '06469fe5-7089-4c74-b522-de90af6bf3d8' AND body LIKE 'Admin-only user list visibility%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'c4cee7e2-25a3-45d0-839c-b2fdfd5d6a2c', 'comment',
  'EDIPI = Electronic Data Interchange Personal Identifier. Concealing it from other users prevents cross-system identity correlation without authorization.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'c4cee7e2-25a3-45d0-839c-b2fdfd5d6a2c' AND body LIKE 'EDIPI = Electronic Data Interchange%');

-- ============================================================================
-- PILLAR 1 — USER IDENTITY
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '181b52ff-0e51-44f9-a12c-dc8105d0c12d', 'comment',
  'Anomaly detection triggers (export floods, off-hours bulk access, scope escalation) force the user to re-authenticate via CAC. This ensures a compromised session cannot continue operating.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '181b52ff-0e51-44f9-a12c-dc8105d0c12d' AND body LIKE 'Anomaly detection triggers (export%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'bdf5ae3a-53d3-4cb2-a0b1-9011e5fdc06a', 'comment',
  'CAC = Common Access Card. SAML = Security Assertion Markup Language. COSMOS handles the CAC validation and passes the verified identity to artiFACT via a signed SAML assertion.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'bdf5ae3a-53d3-4cb2-a0b1-9011e5fdc06a' AND body LIKE 'CAC = Common Access Card. SAML%');

-- ============================================================================
-- PILLAR 5 — DATA
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f00aad31-652b-495c-a3f4-7ca45ae11b99', 'comment',
  'AES-256-GCM provides both encryption (confidentiality) and authentication (tamper detection) in one operation. The 256-bit key length meets CNSS Policy 15 requirements.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f00aad31-652b-495c-a3f4-7ca45ae11b99' AND body LIKE 'AES-256-GCM provides both encryption%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '0c20a340-bb82-4aaa-b646-f8e1c1d1a2b2', 'comment',
  'These three classification levels cover all data artiFACT handles. UNCLASSIFIED is the default. CUI requires safeguarding per 32 CFR Part 2002. CONFIDENTIAL is the lowest classification level.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '0c20a340-bb82-4aaa-b646-f8e1c1d1a2b2' AND body LIKE 'These three classification levels%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a15c5d20-7604-44ca-93c7-c5232f76b698', 'comment',
  'AWS Secrets Manager provides hardware-backed storage, automatic rotation, and IAM-controlled access. The master key is fetched at runtime and held only in memory.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a15c5d20-7604-44ca-93c7-c5232f76b698' AND body LIKE 'AWS Secrets Manager provides hardware-backed storage, automatic%');

-- ============================================================================
-- PILLAR 6 — VISIBILITY
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '4295666d-e7ff-47c2-a5db-da1420a66170', 'comment',
  'AI corpus mining is a data exfiltration technique where a user uses iterative AI queries to gradually extract the entire fact corpus. The anomaly detector tracks query patterns to detect this.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '4295666d-e7ff-47c2-a5db-da1420a66170' AND body LIKE 'AI corpus mining is a data%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'eb73e000-05d3-4fdf-a23a-4217ef35d2b8', 'comment',
  'structlog produces structured JSON log entries with key-value fields. Machine-parseable logs enable CloudWatch Insights queries and Grafana dashboards without regex-based parsing.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'eb73e000-05d3-4fdf-a23a-4217ef35d2b8' AND body LIKE 'structlog produces structured%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e0be3ff2-7845-4de1-a41f-38a90bf5e46d', 'comment',
  'CloudWatch is AWS''s centralized log aggregation and monitoring service. Forwarding logs there enables alerting, querying, and long-term retention outside the application.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e0be3ff2-7845-4de1-a41f-38a90bf5e46d' AND body LIKE 'CloudWatch is AWS''s centralized log aggregation%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6d99ba90-0a05-4865-a561-56b72f4d13b2', 'comment',
  'Grafana is an open-source visualization platform. Dashboards for active users, AI cost, error rates, latency, and request rates provide real-time operational visibility.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6d99ba90-0a05-4865-a561-56b72f4d13b2' AND body LIKE 'Grafana is an open-source visualization%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '44e24826-7b6d-45a7-b9db-e009c3fe86c4', 'comment',
  'fc_event_log is the immutable audit trail. Every create, update, delete, approve, sign, and permission change is recorded with actor, entity, and timestamp.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '44e24826-7b6d-45a7-b9db-e009c3fe86c4' AND body LIKE 'fc_event_log is the immutable%');

-- ============================================================================
-- PROGRAM OVERVIEW
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2618e9a4-cae7-4266-a62c-06354a5394a0', 'comment',
  'Traditional acquisition documents contain overlapping content — the same fact about a system''s architecture might appear in 10 different artifacts. artiFACT stores it once and assembles it into any required format.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2618e9a4-cae7-4266-a62c-06354a5394a0' AND body LIKE 'Traditional acquisition documents contain%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '505a99e8-7709-41c5-b8c0-34622d9878a5', 'comment',
  'A taxonomy is a hierarchical classification system. artiFACT organizes facts into a tree structure — programs at the top, branches for topic areas, leaves for specific subjects.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '505a99e8-7709-41c5-b8c0-34622d9878a5' AND body LIKE 'A taxonomy is a hierarchical%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a1a216c2-8f66-4891-aae6-cca15283a34d', 'comment',
  '71 engineering artifacts include documents like the System Engineering Plan, Test and Evaluation Master Plan, Software Development Plan, and dozens more. Many contain 30%+ overlapping content.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a1a216c2-8f66-4891-aae6-cca15283a34d' AND body LIKE '71 engineering artifacts include%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a4761bfe-b381-4a6c-bbe7-bc2a2b015549', 'comment',
  'On-demand generation from the current corpus guarantees every document reflects the latest approved facts. No stale versions, no manual sync between documents.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a4761bfe-b381-4a6c-bbe7-bc2a2b015549' AND body LIKE 'On-demand generation from%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8db83027-cd0b-4a06-a1db-6cdd0160b355', 'comment',
  'AI-assisted document generation uses a two-pass approach: prefilter assigns facts to template sections, then synthesis generates prose. Users preview assignments before spending AI tokens.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8db83027-cd0b-4a06-a1db-6cdd0160b355' AND body LIKE 'AI-assisted document generation uses%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e0b788d5-8835-42c8-9854-e1857812e476', 'comment',
  '30%+ duplication means updating a single fact requires finding and updating it in dozens of documents. artiFACT eliminates this by storing each fact exactly once.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e0b788d5-8835-42c8-9854-e1857812e476' AND body LIKE '30%+ duplication means%');

-- ============================================================================
-- RECORDS RETENTION
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'e7c1cd5e-9c81-48d5-b2e2-fde7c7449a9c', 'comment',
  'NARA = National Archives and Records Administration. GRS = General Records Schedule. 5.2/020 covers transitory records superseded by new versions — 3-year retention after supersession.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'e7c1cd5e-9c81-48d5-b2e2-fde7c7449a9c' AND body LIKE 'NARA = National Archives%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'b1554486-d0ce-4ac8-91e9-188efd634f29', 'comment',
  'NARA GRS 5.7/010 covers miscellaneous communications including user feedback. Destroy 1 year after resolution — Celery beat automates the cleanup.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'b1554486-d0ce-4ac8-91e9-188efd634f29' AND body LIKE 'NARA GRS 5.7/010%');

-- ============================================================================
-- REST CONVENTIONS
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '0d341d37-0eda-47a1-8ed7-52b454ecc76e', 'comment',
  'The /api/v1 prefix enables API versioning. If a breaking change is needed, a /api/v2 can be introduced while v1 continues serving existing clients.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '0d341d37-0eda-47a1-8ed7-52b454ecc76e' AND body LIKE 'The /api/v1 prefix enables%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '99e987f3-24d0-4d02-971b-47efa68299bf', 'comment',
  'CSRF = Cross-Site Request Forgery. The X-CSRF-Token header proves the request came from artiFACT''s own pages, not a malicious third-party site.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '99e987f3-24d0-4d02-971b-47efa68299bf' AND body LIKE 'CSRF = Cross-Site Request Forgery. The X-CSRF%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '8d5fcb46-82be-4d87-9038-a31971d5c654', 'comment',
  'A consistent error format means client code has one pattern for handling all errors — parse detail, message, and error_code regardless of which endpoint returned the error.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '8d5fcb46-82be-4d87-9038-a31971d5c654' AND body LIKE 'A consistent error format means%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '67163a8e-8638-4def-a27a-db22498d7071', 'comment',
  'Consistent response envelopes (data, total, offset, limit) enable generic pagination handling on the client. Every list endpoint returns the same structure.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '67163a8e-8638-4def-a27a-db22498d7071' AND body LIKE 'Consistent response envelopes%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'aaeac141-8486-4be5-897f-2984df960ba0', 'comment',
  'RESTful nouns (e.g., /api/v1/facts, /api/v1/nodes) follow HTTP semantics: GET reads, POST creates, PUT updates, DELETE removes. No verb-based endpoints like /api/v1/createFact.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'aaeac141-8486-4be5-897f-2984df960ba0' AND body LIKE 'RESTful nouns (e.g.%');

-- ============================================================================
-- ROLE HIERARCHY
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '07b3df87-dab8-430b-b22d-b77cfaf57d25', 'comment',
  'Role inheritance means a signatory automatically has all approver, subapprover, contributor, and viewer capabilities. No need to grant multiple roles — one grant covers everything below it.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '07b3df87-dab8-430b-b22d-b77cfaf57d25' AND body LIKE 'Role inheritance means%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '500270a8-60e7-437b-b5ae-dbf1b95cd3ce', 'comment',
  'Five node-level roles provide fine-grained access control. A signatory can attest, an approver can publish, a subapprover helps review, a contributor can propose, and a viewer can read.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '500270a8-60e7-437b-b5ae-dbf1b95cd3ce' AND body LIKE 'Five node-level roles provide%');

-- ============================================================================
-- SIGNING WORKFLOW
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '9020467b-7d4e-4cf0-94a5-e497bfe0e466', 'comment',
  'Signature expiration supports scenarios where facts require periodic re-attestation. If a signature expires, the signatory must re-sign to confirm the facts are still accurate.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '9020467b-7d4e-4cf0-94a5-e497bfe0e466' AND body LIKE 'Signature expiration supports%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '2661e54d-31a4-4013-be51-382b96197a78', 'comment',
  'Recording fact_count at signing time provides an audit trail of exactly how many facts were attested. If facts are later added, the signature''s scope is clear.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '2661e54d-31a4-4013-be51-382b96197a78' AND body LIKE 'Recording fact_count at signing%');

-- ============================================================================
-- STAKEHOLDERS
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '59687c22-3a6c-4b0d-b482-9b42e265e73c', 'comment',
  'Advana = Advanced Analytics platform. DoD''s enterprise data and analytics environment. It consumes artiFACT data via the delta feed for cross-program analytics.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '59687c22-3a6c-4b0d-b482-9b42e265e73c' AND body LIKE 'Advana = Advanced Analytics%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'cb3ae221-3097-441b-a514-0a8ef9f0ccbc', 'comment',
  'Commercial internet accessibility (via COSMOS CNAP) means users don''t need to be on a military network. Any CAC-enabled browser on a CNAP-enrolled device can reach artiFACT.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'cb3ae221-3097-441b-a514-0a8ef9f0ccbc' AND body LIKE 'Commercial internet accessibility%');

-- ============================================================================
-- SYSTEM TABLES
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'cadb2c7a-1125-481e-9289-e49b662d8b44', 'comment',
  'fc_ai_usage enables per-user cost attribution under the BYOK model. Each organization can see exactly how much their users spend on AI features.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'cadb2c7a-1125-481e-9289-e49b662d8b44' AND body LIKE 'fc_ai_usage enables per-user%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '5211302f-3573-41da-99af-1b338c468e3e', 'comment',
  'Semantic document templates define the structure of acquisition documents — sections with prompts and guidance. The AI uses these to map facts to the correct document sections.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '5211302f-3573-41da-99af-1b338c468e3e' AND body LIKE 'Semantic document templates%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '87e6b9d7-3316-4d64-b5ab-ec029bc0bdff', 'comment',
  'JSONB feature flags enable runtime capability toggling. An admin can disable AI chat, document generation, or any feature instantly without redeploying the application.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '87e6b9d7-3316-4d64-b5ab-ec029bc0bdff' AND body LIKE 'JSONB feature flags enable%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '78bc3f69-7822-47d6-8517-c69ea7f11361', 'comment',
  'Rate limit configuration in fc_system_config allows admins to adjust per-user request limits without code changes. Stored as JSONB for flexible schema.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '78bc3f69-7822-47d6-8517-c69ea7f11361' AND body LIKE 'Rate limit configuration in%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '0564d389-12cf-44bc-b210-1f17824b3099', 'comment',
  'Per-user preferences (theme, default node, notification settings) are stored as flexible JSONB. New preferences can be added without schema migrations.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '0564d389-12cf-44bc-b210-1f17824b3099' AND body LIKE 'Per-user preferences (theme%');

-- ============================================================================
-- WORKFLOW TABLES
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '04bfd3be-7d39-431c-8dd9-4a279c49e802', 'comment',
  'Challenges are formal disagreements with a fact''s content. The challenge/resolution workflow provides a structured review process — not just comments, but tracked disputes with resolution states.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '04bfd3be-7d39-431c-8dd9-4a279c49e802' AND body LIKE 'Challenges are formal%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '5da4a079-bb19-4d71-a7fe-8384abdb3e2d', 'comment',
  'Threaded comments on fact versions enable contextual discussion. parent_comment_uid creates reply chains so conversations stay organized and traceable.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '5da4a079-bb19-4d71-a7fe-8384abdb3e2d' AND body LIKE 'Threaded comments on fact versions%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'f20610be-db97-40df-b843-26713eeacd4e', 'comment',
  'fc_import_session tracks the lifecycle of a document upload: file received, AI analysis in progress, facts extracted, human review pending. SSE streams progress to the user in real time.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'f20610be-db97-40df-b843-26713eeacd4e' AND body LIKE 'fc_import_session tracks the lifecycle%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'ba4c5ee4-f8b2-4d23-9b9c-50e3922285bd', 'comment',
  'fc_signature records batch signing operations per taxonomy node. A signatory signs all published facts under a node in one operation — the record captures who signed, when, and the fact count.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'ba4c5ee4-f8b2-4d23-9b9c-50e3922285bd' AND body LIKE 'fc_signature records batch signing%');

-- ============================================================================
-- MISSION NEED
-- ============================================================================

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '6d45c558-cb08-479f-a545-80e74d8f3b90', 'comment',
  'These 71 artifacts span the full acquisition lifecycle: requirements, design, test, deployment, sustainment, and retirement. Many share 30%+ overlapping content.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '6d45c558-cb08-479f-a545-80e74d8f3b90' AND body LIKE 'These 71 artifacts span%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), '63e43513-a15c-44cf-a5c6-b9f7f63088bf', 'comment',
  'DON = Department of the Navy (Navy + Marine Corps). "Authoritative atomic data" means each fact is the single approved source — no conflicting versions in different documents.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = '63e43513-a15c-44cf-a5c6-b9f7f63088bf' AND body LIKE 'DON = Department of the Navy%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'a0627887-d874-4fe3-8e07-1a832acefef1', 'comment',
  'This is the core problem artiFACT solves. A single fact change triggers a manual hunt through dozens of documents — error-prone, time-consuming, and often incomplete.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'a0627887-d874-4fe3-8e07-1a832acefef1' AND body LIKE 'This is the core problem%');

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
SELECT gen_random_uuid(), 'eb19452d-1e0b-4f6a-be40-c7d1573d1156', 'comment',
  'artiFACT''s import feature lets users upload existing Word documents and extract facts from them. Teams can transition gradually without disrupting current workflows.',
  'a0000001-0000-4000-8000-000000000001', now()
WHERE NOT EXISTS (SELECT 1 FROM fc_fact_comment WHERE version_uid = 'eb19452d-1e0b-4f6a-be40-c7d1573d1156' AND body LIKE 'artiFACT''s import feature%');

COMMIT;
