# Sprint 7: Per-User AI + Chat

**Depends on**: Sprint 3 (facts core), Sprint 1 (kernel AI provider)
**Modules**: `modules/ai_chat/` (7 + 3 safety), `modules/auth_admin/ai_key_manager.py`

## Definition of Success
- Settings page: CRUD for AI API keys (AES-256-GCM encrypted at rest)
- `POST /api/v1/ai/chat` streams corpus-grounded response using user's own key
- Token-counted prompt (never byte-truncated — regression: v1 A-SEC-01)
- Actual loaded fact count reported to client
- Context scoped to user's readable nodes (regression: v1 A-SEC-03)
- Unicode NFKC normalization in input filter
- Output filter catches bulk fact dumps
- Rate limited per user
- Works with OpenAI and Anthropic providers

## Components
### prompt_builder.py — Token-counted fact loading, stops at budget, reports loaded/total
### safety/input_filter.py — Regex + NFKC + confusable mapping (Layer 1)
### safety/system_hardening.py — Immutable system prompt rules (Layer 2)
### safety/output_filter.py — Full-sentence fingerprint matching (Layer 3)
### context_provider.py — Filter taxonomy to user-readable nodes only
### service.py — Orchestrate: load facts → build prompt → call AI → filter → stream

## Database Migration
Table: `fc_user_ai_key`

## Key Tests
```
test_prompt_never_truncated_mid_sentence     (v1 A-SEC-01)
test_context_scoped_to_readable_nodes        (v1 A-SEC-03)
test_unicode_normalization_catches_cyrillic  (v1 A-INJ-01)
test_no_key_returns_clear_error_message
test_rate_limited_per_user
test_streaming_response_works
test_output_filter_catches_bulk_dump
test_key_encrypted_at_rest
```
