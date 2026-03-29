"""Tests for prompt_builder: token counting, no byte truncation (v1 A-SEC-01)."""

from artiFACT.modules.ai_chat.prompt_builder import build_system_prompt, count_tokens


class TestCountTokens:
    def test_counts_simple_text(self) -> None:
        tokens = count_tokens("Hello world")
        assert tokens > 0

    def test_empty_string(self) -> None:
        assert count_tokens("") == 0


class TestBuildSystemPrompt:
    def test_returns_three_tuple(self) -> None:
        prompt, loaded, total = build_system_prompt(["Fact one.", "Fact two."])
        assert isinstance(prompt, str)
        assert loaded == 2
        assert total == 2

    def test_prompt_never_truncated_mid_sentence(self) -> None:
        """Regression: v1 A-SEC-01 — byte truncation split sentences."""
        # Create facts that are large enough to exceed budget
        long_facts = [f"This is fact number {i} with extra detail for padding." for i in range(500)]
        prompt, loaded, total = build_system_prompt(long_facts, max_tokens=2000)

        # Not all facts should be loaded (we exceeded budget)
        assert loaded < total
        assert total == 500

        # Every included fact should be complete (no truncation mid-sentence)
        for i in range(loaded):
            assert f"- This is fact number {i} with extra detail for padding." in prompt

        # The next fact should NOT be in the prompt (it was cut at boundary)
        if loaded < total:
            assert f"- This is fact number {loaded}" not in prompt

    def test_respects_token_budget(self) -> None:
        facts = [f"Fact {i}." for i in range(100)]
        prompt, loaded, total = build_system_prompt(facts, max_tokens=1000)
        assert count_tokens(prompt) <= 1000

    def test_reports_loaded_and_total(self) -> None:
        facts = ["Fact A.", "Fact B.", "Fact C."]
        prompt, loaded, total = build_system_prompt(facts, max_tokens=6000)
        assert loaded == 3
        assert total == 3
        assert "3 loaded of 3 total" in prompt

    def test_empty_facts(self) -> None:
        prompt, loaded, total = build_system_prompt([])
        assert loaded == 0
        assert total == 0
        assert "0 loaded" in prompt
