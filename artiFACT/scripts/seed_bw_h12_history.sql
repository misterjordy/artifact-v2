-- ═══════════════════════════════════════════════════════════════════════
-- Rich seed data for Boatwing & SNIPE-B Program Fundamentals
-- Adds Office characters, permissions, version histories, challenges,
-- comments, and rejection events.
-- Run AFTER golden_snapshot.sql.  Idempotent (ON CONFLICT DO NOTHING).
-- ═══════════════════════════════════════════════════════════════════════

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════
-- 1. USERS
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO fc_user (user_uid, cac_dn, display_name, global_role, is_active, password_hash)
VALUES
  ('a0000005-0000-4000-8000-000000000005', 'mscott',   'Michael Scott',   'viewer', true,
   '02866863221c58e5976d4236add34db53607dda561c8710d500de291b17f2941'),
  ('a0000006-0000-4000-8000-000000000006', 'mpalmer',  'Meredith Palmer', 'viewer', true,
   '02866863221c58e5976d4236add34db53607dda561c8710d500de291b17f2941'),
  ('a0000007-0000-4000-8000-000000000007', 'jhalpert', 'Jim Halpert',     'viewer', true,
   '02866863221c58e5976d4236add34db53607dda561c8710d500de291b17f2941'),
  ('a0000008-0000-4000-8000-000000000008', 'cbratton', 'Creed Bratton',   'viewer', true,
   '02866863221c58e5976d4236add34db53607dda561c8710d500de291b17f2941')
ON CONFLICT (user_uid) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════
-- 2. PERMISSIONS
-- ═══════════════════════════════════════════════════════════════════════
-- Existing in snapshot:
--   Oscar  (a03) → approver  on BW root (6fb855e0) + SNIPE-B root (1d6fc401)
--   Pam    (a04) → contributor on BW root + SNIPE-B root
--   DWall  (a02) → signatory on Special Projects (fbdfa1f8) — inherits down
--   Jordan (a01) → admin

-- BW D&C node (9091c8af) — leaf-level for the Office crew
INSERT INTO fc_node_permission (permission_uid, user_uid, node_uid, role, granted_by_uid)
VALUES
  ('b0000001-0000-4000-8000-000000000001', 'a0000006-0000-4000-8000-000000000006',
   '9091c8af-25ce-4e9c-b500-d9ada7434ce2', 'contributor', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000002-0000-4000-8000-000000000002', 'a0000008-0000-4000-8000-000000000008',
   '9091c8af-25ce-4e9c-b500-d9ada7434ce2', 'contributor', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000003-0000-4000-8000-000000000003', 'a0000007-0000-4000-8000-000000000007',
   '9091c8af-25ce-4e9c-b500-d9ada7434ce2', 'approver', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000004-0000-4000-8000-000000000004', 'a0000005-0000-4000-8000-000000000005',
   '9091c8af-25ce-4e9c-b500-d9ada7434ce2', 'approver', 'a0000001-0000-4000-8000-000000000001')
ON CONFLICT (permission_uid) DO NOTHING;

-- Give Office crew access to BW root so they can work on Program Status & Phase too
INSERT INTO fc_node_permission (permission_uid, user_uid, node_uid, role, granted_by_uid)
VALUES
  ('b0000010-0000-4000-8000-000000000010', 'a0000005-0000-4000-8000-000000000005',
   '6fb855e0-cbf9-47a0-98cb-99f3a15fade0', 'approver', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000011-0000-4000-8000-000000000011', 'a0000007-0000-4000-8000-000000000007',
   '6fb855e0-cbf9-47a0-98cb-99f3a15fade0', 'approver', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000012-0000-4000-8000-000000000012', 'a0000006-0000-4000-8000-000000000006',
   '6fb855e0-cbf9-47a0-98cb-99f3a15fade0', 'contributor', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000013-0000-4000-8000-000000000013', 'a0000008-0000-4000-8000-000000000008',
   '6fb855e0-cbf9-47a0-98cb-99f3a15fade0', 'contributor', 'a0000001-0000-4000-8000-000000000001')
ON CONFLICT (permission_uid) DO NOTHING;

-- Give Office crew access to SNIPE-B root
INSERT INTO fc_node_permission (permission_uid, user_uid, node_uid, role, granted_by_uid)
VALUES
  ('b0000020-0000-4000-8000-000000000020', 'a0000005-0000-4000-8000-000000000005',
   '1d6fc401-13b1-46ee-9e44-76add93385b5', 'approver', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000021-0000-4000-8000-000000000021', 'a0000007-0000-4000-8000-000000000007',
   '1d6fc401-13b1-46ee-9e44-76add93385b5', 'approver', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000022-0000-4000-8000-000000000022', 'a0000006-0000-4000-8000-000000000006',
   '1d6fc401-13b1-46ee-9e44-76add93385b5', 'contributor', 'a0000001-0000-4000-8000-000000000001'),
  ('b0000023-0000-4000-8000-000000000023', 'a0000008-0000-4000-8000-000000000008',
   '1d6fc401-13b1-46ee-9e44-76add93385b5', 'contributor', 'a0000001-0000-4000-8000-000000000001')
ON CONFLICT (permission_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 3. BW-H12 ABBREVIATION FACT (f98acbf6) — FIX & ENRICH
-- ═══════════════════════════════════════════════════════════════════════
-- V1 (57978e4b) published "Program abbreviation is BW-H12" by Jordan
-- V2 (f076b01b) rejected  "Program abbreviation is BW-H12 or BWH12" by Meredith
-- V3 (59296b15) rejected  "Program abbreviation is BW H12" by Meredith
-- V4 (785d8958) proposed  "Program abbreviation is BWH12" by Creed

-- Diversify authorship
UPDATE fc_fact_version SET created_by_uid = 'a0000006-0000-4000-8000-000000000006'
WHERE version_uid IN ('f076b01b-1203-4e1f-8947-a777d12dde81', '59296b15-1628-4fcc-9a2f-08b123cadcc9');

UPDATE fc_fact_version SET created_by_uid = 'a0000008-0000-4000-8000-000000000008'
WHERE version_uid = '785d8958-cdf0-4b73-a603-59112d14ca6b';

-- Rejection events
INSERT INTO fc_event_log (event_uid, entity_type, entity_uid, event_type, payload, actor_uid, note, occurred_at, reversible)
VALUES
  ('c0000001-0000-4000-8000-000000000001', 'version',
   'f076b01b-1203-4e1f-8947-a777d12dde81', 'version.rejected',
   '{"version_uid": "f076b01b-1203-4e1f-8947-a777d12dde81", "fact_uid": "f98acbf6-b080-4219-8159-36aef750b206"}',
   'a0000007-0000-4000-8000-000000000007',
   'The official program designation is BW-H12 with a hyphen. See NAVAIR directive 2024-0312.',
   '2026-03-12 11:17:32+00', false),
  ('c0000002-0000-4000-8000-000000000002', 'version',
   '59296b15-1628-4fcc-9a2f-08b123cadcc9', 'version.rejected',
   '{"version_uid": "59296b15-1628-4fcc-9a2f-08b123cadcc9", "fact_uid": "f98acbf6-b080-4219-8159-36aef750b206"}',
   'a0000005-0000-4000-8000-000000000005',
   'The hyphen is required per MIL-STD-881F. Dropping it changes the identifier.',
   '2026-03-12 11:23:16+00', false)
ON CONFLICT (event_uid) DO NOTHING;

-- Clean up old bad comments
DELETE FROM fc_fact_comment WHERE comment_uid IN (
  'd0000001-0000-4000-8000-000000000001',
  'd0000002-0000-4000-8000-000000000002',
  'd0000003-0000-4000-8000-000000000003',
  'd0000004-0000-4000-8000-000000000004',
  'd0000005-0000-4000-8000-000000000005',
  'd0000006-0000-4000-8000-000000000006',
  'd0000007-0000-4000-8000-000000000007'
);

-- Coherent comment thread on V1 (published)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d0000001-0000-4000-8000-000000000001',
   '57978e4b-4421-49b2-95be-1037097a64b6', 'comment',
   'Verified against the Program Management Agreement (PMA-299). BW-H12 is correct.',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-10 14:22:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Comment on V2 (rejected) — regular comments, not challenges
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d0000002-0000-4000-8000-000000000002',
   'f076b01b-1203-4e1f-8947-a777d12dde81', 'comment',
   'Where did you see "BWH12" without the hyphen? That''s not in any official documentation I can find.',
   'a0000007-0000-4000-8000-000000000007',
   '2026-03-12 11:17:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

INSERT INTO fc_fact_comment (comment_uid, version_uid, parent_comment_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d0000003-0000-4000-8000-000000000003',
   'f076b01b-1203-4e1f-8947-a777d12dde81',
   'd0000002-0000-4000-8000-000000000002',
   'comment',
   'I saw it on a briefing slide from last Tuesday. Might have been a typo.',
   'a0000006-0000-4000-8000-000000000006',
   '2026-03-12 11:17:15+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Comment on V3 (rejected)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d0000004-0000-4000-8000-000000000004',
   '59296b15-1628-4fcc-9a2f-08b123cadcc9', 'comment',
   'Removing the hyphen changes the identifier entirely. "BW H12" would be parsed as two separate tokens by DITPR.',
   'a0000004-0000-4000-8000-000000000004',
   '2026-03-12 11:22:45+00')
ON CONFLICT (comment_uid) DO NOTHING;

INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d0000005-0000-4000-8000-000000000005',
   '59296b15-1628-4fcc-9a2f-08b123cadcc9', 'comment',
   'Confirmed with PM office: the canonical form is "BW-H12" with hyphen. All variants without it are incorrect.',
   'a0000002-0000-4000-8000-000000000002',
   '2026-03-12 11:23:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 4. BW ACQUISITION CATEGORY (0105dae6) — REJECTED CHALLENGE
-- ═══════════════════════════════════════════════════════════════════════
-- Current published: cc267687 "Acquisition category is ACAT I"
-- V2 (387c372a) rejected "ACAT II" by Pam — already fixed in snapshot cleanup
-- V3 (28b28e22) rejected "BCAT II" — nonsense proposal

-- Pam challenges published "Acquisition category is ACAT I" (cc267687)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, proposed_sentence,
                             created_by_uid, created_at, resolution_state, resolution_note,
                             resolved_by_uid, resolved_at)
VALUES
  ('d1000001-0000-4000-8000-000000000001',
   'cc267687-2944-4ac5-a068-c2b01f3d0edf', 'challenge',
   'Per the latest DAB memo (DAB-2026-0287), the program has been recategorized to ACAT IC due to cost restructuring under the latest FYDP.',
   'Acquisition category is ACAT IC',
   'a0000004-0000-4000-8000-000000000004',
   '2026-03-18 09:30:00+00',
   'rejected',
   'The DAB memo was draft-only and was superseded by the final ADM determination. ACAT I stands per the signed Acquisition Decision Memorandum.',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-18 14:15:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Jim comments on the published version supporting Oscar's rejection
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d1000002-0000-4000-8000-000000000001',
   'cc267687-2944-4ac5-a068-c2b01f3d0edf', 'comment',
   'Pam, the draft memo was circulated but never signed. The ADM registry is the authoritative source.',
   'a0000007-0000-4000-8000-000000000007',
   '2026-03-18 15:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Rejection event for V3 "BCAT II"
INSERT INTO fc_event_log (event_uid, entity_type, entity_uid, event_type, payload, actor_uid, note, occurred_at, reversible)
VALUES
  ('c0000010-0000-4000-8000-000000000010', 'version',
   '28b28e22-6a2b-4553-82d2-93971fb85980', 'version.rejected',
   '{"version_uid": "28b28e22-6a2b-4553-82d2-93971fb85980", "fact_uid": "0105dae6-00f8-4a23-97cb-662d85bd4257"}',
   'a0000003-0000-4000-8000-000000000003',
   '"BCAT" is not a valid acquisition category. Categories are ACAT I, IA, IC, II, III, or IV per DoDI 5000.85.',
   '2026-03-12 08:05:00+00', false)
ON CONFLICT (event_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 5. BW PRODUCT TYPE (36e80f7f) — APPROVED CHALLENGE → NEW VERSION
-- ═══════════════════════════════════════════════════════════════════════
-- Current published: e3ab677f "Product type is maritime-aerial hybrid platform"

-- Jim challenges the current published version
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, proposed_sentence,
                             created_by_uid, created_at, resolution_state,
                             resolved_by_uid, resolved_at)
VALUES
  ('d2000001-0000-4000-8000-000000000001',
   'e3ab677f-4c2f-4084-a1da-01b80c8f1e94', 'challenge',
   'The "unmanned" qualifier is required per DoD Directive 3000.09 for autonomous systems classification. Omitting it creates ambiguity in the JCIDS process.',
   'Product type is maritime-aerial unmanned hybrid platform',
   'a0000007-0000-4000-8000-000000000007',
   '2026-03-20 10:00:00+00',
   'approved',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-20 14:30:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- The approved challenge creates a new published version
INSERT INTO fc_fact_version (version_uid, fact_uid, state, display_sentence, metadata_tags,
                             classification, supersedes_version_uid, created_by_uid,
                             created_at, published_at)
VALUES
  ('e4000001-0000-4000-8000-000000000001',
   '36e80f7f-9fea-4337-a630-c010935fb88c', 'published',
   'Product type is maritime-aerial unmanned hybrid platform',
   '["#BoatWithWings", "#BoatyMcFlyFace"]',
   'UNCLASSIFIED',
   'e3ab677f-4c2f-4084-a1da-01b80c8f1e94',
   'a0000007-0000-4000-8000-000000000007',
   '2026-03-20 14:30:00+00', '2026-03-20 14:30:00+00')
ON CONFLICT (version_uid) DO NOTHING;

UPDATE fc_fact SET current_published_version_uid = 'e4000001-0000-4000-8000-000000000001'
WHERE fact_uid = '36e80f7f-9fea-4337-a630-c010935fb88c';

-- Pam comments on the new version
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d2000002-0000-4000-8000-000000000001',
   'e4000001-0000-4000-8000-000000000001', 'comment',
   'Good catch. This aligns with the updated CDD language from the February review.',
   'a0000004-0000-4000-8000-000000000004',
   '2026-03-20 15:12:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 6. BW PROGRAM STATUS — "Program is in EMD phase" (09d2fa8d)
-- ═══════════════════════════════════════════════════════════════════════
-- Current published: edafbf98 "Program is in Engineering and Manufacturing Development phase"

-- Meredith proposes a change → rejected by Jim for being too specific
INSERT INTO fc_fact_version (version_uid, fact_uid, state, display_sentence, metadata_tags,
                             classification, supersedes_version_uid, created_by_uid,
                             created_at, published_at)
VALUES
  ('e5000001-0000-4000-8000-000000000001',
   '09d2fa8d-791a-4c91-b857-666874f5687f', 'rejected',
   'Program is in Engineering and Manufacturing Development phase, Block 2 upgrade cycle',
   '[]', 'UNCLASSIFIED',
   'edafbf98-8fcf-44ca-ae5b-5c171f71b969',
   'a0000006-0000-4000-8000-000000000006',
   '2026-03-17 08:45:00+00', NULL)
ON CONFLICT (version_uid) DO NOTHING;

INSERT INTO fc_event_log (event_uid, entity_type, entity_uid, event_type, payload, actor_uid, note, occurred_at, reversible)
VALUES
  ('c0000020-0000-4000-8000-000000000020', 'version',
   'e5000001-0000-4000-8000-000000000001', 'version.rejected',
   '{"version_uid": "e5000001-0000-4000-8000-000000000001"}',
   'a0000007-0000-4000-8000-000000000007',
   'Block 2 is a sub-program milestone, not part of the acquisition phase designation. Keep the phase statement general.',
   '2026-03-17 10:20:00+00', false)
ON CONFLICT (event_uid) DO NOTHING;

-- Comment on the published version
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d3000001-0000-4000-8000-000000000001',
   'edafbf98-8fcf-44ca-ae5b-5c171f71b969', 'comment',
   'This should be updated when the program transitions to LRIP. Oscar, are we still tracking a Q3 gate review?',
   'a0000005-0000-4000-8000-000000000005',
   '2026-03-22 11:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

INSERT INTO fc_fact_comment (comment_uid, version_uid, parent_comment_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d3000002-0000-4000-8000-000000000001',
   'edafbf98-8fcf-44ca-ae5b-5c171f71b969',
   'd3000001-0000-4000-8000-000000000001',
   'comment',
   'Yes, the Milestone C decision review is on the calendar for September. I''ll update the fact when we get the signed memo.',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-22 11:45:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 7. BW GOVERNING DIRECTIVE (2bcac1bd) — CHALLENGE PENDING
-- ═══════════════════════════════════════════════════════════════════════
-- Current published: 3bc1dd43 "Governing directive is DoDI 5000.85"

-- Creed challenges with a pending challenge (shows in queue)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, proposed_sentence,
                             created_by_uid, created_at)
VALUES
  ('d4000001-0000-4000-8000-000000000001',
   '3bc1dd43-5053-42c4-a619-e26970ed3b44', 'challenge',
   'DoDI 5000.85 was updated and reissued as DoDI 5000.85T on 15 Feb 2026. The transitional directive applies until the permanent replacement is signed.',
   'Governing directive is DoDI 5000.85T (transitional)',
   'a0000008-0000-4000-8000-000000000008',
   '2026-03-28 16:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 8. SNIPE-B CLASSIFICATION (187d9ed7) — COMMENTS + PENDING CHALLENGE
-- ═══════════════════════════════════════════════════════════════════════
-- Current published: 48e94a07 "Program is classified as an autonomous nonlethal enemy nuisance system"

-- Comments on a rejected version (951f26fb "lethal non-standard autonomous")
INSERT INTO fc_event_log (event_uid, entity_type, entity_uid, event_type, payload, actor_uid, note, occurred_at, reversible)
VALUES
  ('c0000030-0000-4000-8000-000000000030', 'version',
   '951f26fb-4929-457d-bd7a-e4661d68a533', 'version.rejected',
   '{"version_uid": "951f26fb-4929-457d-bd7a-e4661d68a533"}',
   'a0000003-0000-4000-8000-000000000003',
   'Word order matters for JCIDS taxonomy. "Autonomous" must precede the lethality descriptor per the SNIPE-B CDD.',
   '2026-03-15 10:30:00+00', false)
ON CONFLICT (event_uid) DO NOTHING;

-- Rejection event for the other rejected version (a0ba85cd "unclassified as a non-standard...")
INSERT INTO fc_event_log (event_uid, entity_type, entity_uid, event_type, payload, actor_uid, note, occurred_at, reversible)
VALUES
  ('c0000031-0000-4000-8000-000000000031', 'version',
   'a0ba85cd-6f5a-4eaa-adfc-198a02b85d56', 'version.rejected',
   '{"version_uid": "a0ba85cd-6f5a-4eaa-adfc-198a02b85d56"}',
   'a0000007-0000-4000-8000-000000000007',
   '"Unclassified" is a security marking, not a program classification. These are different concepts.',
   '2026-03-14 09:00:00+00', false)
ON CONFLICT (event_uid) DO NOTHING;

-- Comment thread on current published (48e94a07)
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d5000001-0000-4000-8000-000000000001',
   '48e94a07-bc1d-498b-921d-7547399c7dc7', 'comment',
   'The "nonlethal enemy nuisance" classification was confirmed in the latest OUSD(A&S) review. This is the authoritative wording.',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-20 13:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

INSERT INTO fc_fact_comment (comment_uid, version_uid, parent_comment_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d5000002-0000-4000-8000-000000000001',
   '48e94a07-bc1d-498b-921d-7547399c7dc7',
   'd5000001-0000-4000-8000-000000000001',
   'comment',
   'Does "nonlethal" here mean compliant with the DoD Non-Lethal Weapons Policy (DoDD 3000.03E) or is it a colloquial descriptor?',
   'a0000004-0000-4000-8000-000000000004',
   '2026-03-20 14:15:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

INSERT INTO fc_fact_comment (comment_uid, version_uid, parent_comment_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d5000003-0000-4000-8000-000000000001',
   '48e94a07-bc1d-498b-921d-7547399c7dc7',
   'd5000002-0000-4000-8000-000000000001',
   'comment',
   'It''s the formal classification per the CDD. SNIPE-B is specifically categorized under the non-lethal effects taxonomy despite its kinetic delivery mechanism.',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-20 14:45:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Meredith files a pending challenge on the current published
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, proposed_sentence,
                             created_by_uid, created_at)
VALUES
  ('d5000004-0000-4000-8000-000000000001',
   '48e94a07-bc1d-498b-921d-7547399c7dc7', 'challenge',
   'OUSD(A&S) issued updated guidance on 25 Mar 2026 removing "enemy nuisance" from the approved taxonomy. The replacement term is "autonomous precision non-lethal system".',
   'Program is classified as an autonomous precision non-lethal system',
   'a0000006-0000-4000-8000-000000000006',
   '2026-03-28 09:30:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 9. SNIPE-B PROGRAM STATUS — "active with significant unresolved questions" (f8139c60)
-- ═══════════════════════════════════════════════════════════════════════
-- Current published: 6cb235d6

-- Michael proposes removing "significant unresolved questions"
INSERT INTO fc_fact_version (version_uid, fact_uid, state, display_sentence, metadata_tags,
                             classification, supersedes_version_uid, created_by_uid,
                             created_at, published_at)
VALUES
  ('e6000001-0000-4000-8000-000000000001',
   'f8139c60-00c2-496d-a3db-f5cdce82e63b', 'rejected',
   'Program status is active',
   '[]', 'UNCLASSIFIED',
   '6cb235d6-7b1c-4515-a586-20f79a056dbd',
   'a0000005-0000-4000-8000-000000000005',
   '2026-03-16 09:00:00+00', NULL)
ON CONFLICT (version_uid) DO NOTHING;

INSERT INTO fc_event_log (event_uid, entity_type, entity_uid, event_type, payload, actor_uid, note, occurred_at, reversible)
VALUES
  ('c0000040-0000-4000-8000-000000000040', 'version',
   'e6000001-0000-4000-8000-000000000001', 'version.rejected',
   '{"version_uid": "e6000001-0000-4000-8000-000000000001"}',
   'a0000003-0000-4000-8000-000000000003',
   'The "significant unresolved questions" qualifier is required per the latest DAES assessment. Removing it would misrepresent the program health status.',
   '2026-03-16 11:30:00+00', false)
ON CONFLICT (event_uid) DO NOTHING;

-- Michael tries again with better wording → Jim approves
INSERT INTO fc_fact_version (version_uid, fact_uid, state, display_sentence, metadata_tags,
                             classification, supersedes_version_uid, change_summary,
                             created_by_uid, created_at, published_at)
VALUES
  ('e6000002-0000-4000-8000-000000000001',
   'f8139c60-00c2-496d-a3db-f5cdce82e63b', 'published',
   'Program status is active with unresolved technical questions pending EMD Phase II review',
   '[]', 'UNCLASSIFIED',
   '6cb235d6-7b1c-4515-a586-20f79a056dbd',
   'Refined qualifier to specify nature and timeline of unresolved items per DAES feedback',
   'a0000005-0000-4000-8000-000000000005',
   '2026-03-18 08:00:00+00', '2026-03-18 10:15:00+00')
ON CONFLICT (version_uid) DO NOTHING;

UPDATE fc_fact SET current_published_version_uid = 'e6000002-0000-4000-8000-000000000001'
WHERE fact_uid = 'f8139c60-00c2-496d-a3db-f5cdce82e63b';

-- Comment on the new published version
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d6000001-0000-4000-8000-000000000001',
   'e6000002-0000-4000-8000-000000000001', 'comment',
   'Much better. This accurately reflects the DAES finding without the vagueness of "significant".',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-18 10:30:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Jim challenges the new version to add a DAES reference
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, proposed_sentence,
                             created_by_uid, created_at, resolution_state,
                             resolved_by_uid, resolved_at)
VALUES
  ('d6000002-0000-4000-8000-000000000001',
   'e6000002-0000-4000-8000-000000000001', 'challenge',
   'We should cite the specific DAES assessment for traceability. Without it, the "unresolved technical questions" claim has no anchor.',
   'Program status is active with unresolved technical questions per DAES-2026-Q1 pending EMD Phase II review',
   'a0000007-0000-4000-8000-000000000007',
   '2026-03-22 09:00:00+00',
   'approved',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-22 11:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Approved challenge creates new version
INSERT INTO fc_fact_version (version_uid, fact_uid, state, display_sentence, metadata_tags,
                             classification, supersedes_version_uid, created_by_uid,
                             created_at, published_at)
VALUES
  ('e6000003-0000-4000-8000-000000000001',
   'f8139c60-00c2-496d-a3db-f5cdce82e63b', 'published',
   'Program status is active with unresolved technical questions per DAES-2026-Q1 pending EMD Phase II review',
   '[]', 'UNCLASSIFIED',
   'e6000002-0000-4000-8000-000000000001',
   'a0000007-0000-4000-8000-000000000007',
   '2026-03-22 11:00:00+00', '2026-03-22 11:00:00+00')
ON CONFLICT (version_uid) DO NOTHING;

UPDATE fc_fact SET current_published_version_uid = 'e6000003-0000-4000-8000-000000000001'
WHERE fact_uid = 'f8139c60-00c2-496d-a3db-f5cdce82e63b';

-- Pam comments on the final version
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d6000003-0000-4000-8000-000000000001',
   'e6000003-0000-4000-8000-000000000001', 'comment',
   'Traceability to the DAES reference is exactly right. This is how facts should be sourced.',
   'a0000004-0000-4000-8000-000000000004',
   '2026-03-22 12:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 10. SNIPE-B ACQUISITION CATEGORY (5f5ab0dc) — REJECT → FIX → APPROVE
-- ═══════════════════════════════════════════════════════════════════════
-- V1 (6009074c) published "Acquisition category is ACAT III"
-- V2 (f0aed3a6) rejected  "Acquisition category is ACAT II" by Creed (fixed in snapshot)
-- V3 (e7000002) published "ACAT III per SAR..." by Meredith (added below)

-- Creed comments on his own rejected version
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d7000001-0000-4000-8000-000000000001',
   'f0aed3a6-8b7b-4eba-ad7a-586e55cec767', 'comment',
   'I thought the SAR still showed ACAT II. My bad — I was looking at the FY25 report, not the current one.',
   'a0000008-0000-4000-8000-000000000008',
   '2026-03-10 10:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Meredith proposes a better update with SAR citation → approved by Oscar
INSERT INTO fc_fact_version (version_uid, fact_uid, state, display_sentence, metadata_tags,
                             classification, supersedes_version_uid, change_summary,
                             created_by_uid, created_at, published_at)
VALUES
  ('e7000002-0000-4000-8000-000000000001',
   '5f5ab0dc-b0dd-484c-957a-e7fb8144e26b', 'published',
   'Acquisition category is ACAT III per SAR-SNIPE-2026-Q1 unit cost determination',
   '[]', 'UNCLASSIFIED',
   '6009074c-1c25-490e-bfe5-eaae4ffcdbf1',
   'Added SAR reference for traceability per approver feedback',
   'a0000006-0000-4000-8000-000000000006',
   '2026-03-17 09:00:00+00', '2026-03-17 11:00:00+00')
ON CONFLICT (version_uid) DO NOTHING;

UPDATE fc_fact SET current_published_version_uid = 'e7000002-0000-4000-8000-000000000001'
WHERE fact_uid = '5f5ab0dc-b0dd-484c-957a-e7fb8144e26b';

-- Oscar comments on the approved version
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d7000002-0000-4000-8000-000000000001',
   'e7000002-0000-4000-8000-000000000001', 'comment',
   'Good. Including the SAR reference makes this auditable. This is the pattern we should follow for all cost-derived classifications.',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-17 11:15:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 11. SNIPE-B GOVERNING DIRECTIVE (b15979bd) — SIGNED + CHALLENGE
-- ═══════════════════════════════════════════════════════════════════════
-- Current published: 1fc6625e "Governing directive is DoDI 5000.85"

-- David Wallace signs this version
UPDATE fc_fact_version SET state = 'signed', signed_at = '2026-03-19 16:00:00+00'
WHERE version_uid = '1fc6625e-a701-4ec4-8736-874a8cbabcd5';

UPDATE fc_fact SET current_signed_version_uid = '1fc6625e-a701-4ec4-8736-874a8cbabcd5'
WHERE fact_uid = 'b15979bd-9b0a-4a49-ad11-1e330de4fbd9';

-- Pam comments on the signed version
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d8000001-0000-4000-8000-000000000001',
   '1fc6625e-a701-4ec4-8736-874a8cbabcd5', 'comment',
   'This was signed by David Wallace on 19 March. Should we update to reference the transitional DoDI 5000.85T?',
   'a0000004-0000-4000-8000-000000000004',
   '2026-03-25 10:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

INSERT INTO fc_fact_comment (comment_uid, version_uid, parent_comment_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d8000002-0000-4000-8000-000000000001',
   '1fc6625e-a701-4ec4-8736-874a8cbabcd5',
   'd8000001-0000-4000-8000-000000000001',
   'comment',
   'Hold off until the transitional directive is formally issued. We don''t want to update a signed fact based on pre-decisional guidance.',
   'a0000003-0000-4000-8000-000000000003',
   '2026-03-25 10:30:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════
-- 12. SNIPE-B "Program is in EMD" (157b2de2) — REJECTED CHALLENGE
-- ═══════════════════════════════════════════════════════════════════════
-- Current published: a953cf6c "Program is in engineering and manufacturing development"

-- Creed challenges to add more detail
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, proposed_sentence,
                             created_by_uid, created_at, resolution_state, resolution_note,
                             resolved_by_uid, resolved_at)
VALUES
  ('d9000001-0000-4000-8000-000000000001',
   'a953cf6c-5289-4def-b155-9a7f69891813', 'challenge',
   'This is too vague. The program has passed Milestone B and is specifically in the detailed design sub-phase of EMD.',
   'Program is in the detailed design sub-phase of engineering and manufacturing development',
   'a0000008-0000-4000-8000-000000000008',
   '2026-03-19 14:00:00+00',
   'rejected',
   'Sub-phase status changes frequently and would require constant updates. The top-level phase is the appropriate granularity for this taxonomy node. Track sub-phases in Program Status and Phase instead.',
   'a0000007-0000-4000-8000-000000000007',
   '2026-03-19 16:00:00+00')
ON CONFLICT (comment_uid) DO NOTHING;

-- Comment on the published version acknowledging the rejection
INSERT INTO fc_fact_comment (comment_uid, version_uid, comment_type, body, created_by_uid, created_at)
VALUES
  ('d9000002-0000-4000-8000-000000000001',
   'a953cf6c-5289-4def-b155-9a7f69891813', 'comment',
   'Fair point. I''ll propose the sub-phase detail under Program Status and Phase instead.',
   'a0000008-0000-4000-8000-000000000008',
   '2026-03-19 16:30:00+00')
ON CONFLICT (comment_uid) DO NOTHING;


COMMIT;
