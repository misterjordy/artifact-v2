# Sprint 11: Presentation

**Depends on**: Sprint 3 (facts for dynamic stats)
**Module**: `modules/presentation/` (4 components)

## Definition of Success
- Presentation modal opens from nav icon
- Slides render with beat timing and narration
- VCR controls work (play, pause, step, mute)
- Tour mode uses canned responses, NOT real AI calls (regression: v1 P-COST-01)
- Mobile touch nav works
- Presentation forces dark theme regardless of app theme

## Components
### slide_data.py — Static slide content + dynamic stats queries
### static/presentation.js — Beat engine, VCR controls, mode toggle
### static/presentation.css — Scoped styles with --fp- variables

## Key Tests
```
test_tour_does_not_fire_real_ai_calls   (v1 P-COST-01)
test_dynamic_stats_query_returns_valid_counts
test_slide_data_all_slides_have_beats
```
