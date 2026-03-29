"""Tests for safety/output_filter: bulk dump detection."""

import pytest

from artiFACT.modules.ai_chat.safety.output_filter import check_output


class TestOutputFilter:
    def test_safe_response_passes(self) -> None:
        facts = ["The sky is blue.", "Water is wet.", "Fire is hot."]
        response = "Based on the corpus, the sky is blue and water is wet."
        is_safe, filtered = check_output(response, facts)
        assert is_safe
        assert filtered == response

    def test_output_filter_catches_bulk_dump(self) -> None:
        """Bulk dump of facts triggers replacement response."""
        facts = [f"Fact number {i} is important." for i in range(20)]
        # Response that dumps all facts verbatim
        response = "\n".join(f"- {f}" for f in facts)
        is_safe, filtered = check_output(response, facts)
        assert not is_safe
        assert "specific questions" in filtered

    def test_few_verbatim_facts_ok(self) -> None:
        facts = [f"Fact {i}." for i in range(20)]
        # Only 2 verbatim matches
        response = "Fact 0. Fact 1. The rest is my summary."
        is_safe, filtered = check_output(response, facts)
        assert is_safe

    def test_empty_facts_always_safe(self) -> None:
        is_safe, filtered = check_output("Any response text", [])
        assert is_safe
