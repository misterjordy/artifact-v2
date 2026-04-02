"""Tests for prompt_builder: no token cap, mode-aware coverage notes."""

from artiFACT.modules.ai_chat.prompt_builder import build_system_prompt, count_tokens


class TestCountTokens:
    def test_counts_simple_text(self) -> None:
        tokens = count_tokens("Hello world")
        assert tokens > 0

    def test_empty_string(self) -> None:
        assert count_tokens("") == 0


class TestBuildSystemPrompt:
    def test_returns_two_tuple(self) -> None:
        prompt, loaded = build_system_prompt(["Fact one.", "Fact two."])
        assert isinstance(prompt, str)
        assert loaded == 2

    def test_no_token_cap_all_facts_included(self) -> None:
        """All facts should appear in prompt — no truncation."""
        facts = [f"This is fact number {i} with extra detail for padding." for i in range(300)]
        prompt, loaded = build_system_prompt(facts)
        assert loaded == 300
        for i in range(300):
            assert f"This is fact number {i}" in prompt

    def test_reports_loaded_count(self) -> None:
        facts = ["Fact A.", "Fact B.", "Fact C."]
        prompt, loaded = build_system_prompt(facts)
        assert loaded == 3
        assert "3 of 3" in prompt

    def test_empty_facts(self) -> None:
        prompt, loaded = build_system_prompt([])
        assert loaded == 0
        assert "0 of 0" in prompt

    def test_system_prompt_includes_program_name(self) -> None:
        prompt, _ = build_system_prompt(["Fact."], program_name="Boatwing H-12")
        assert "Boatwing H-12" in prompt

    def test_partial_load_includes_coverage_note(self) -> None:
        prompt, _ = build_system_prompt(
            ["Fact."], total_facts_in_scope=100
        )
        assert "most relevant facts" in prompt

    def test_full_load_no_coverage_note(self) -> None:
        prompt, _ = build_system_prompt(
            ["Fact."], total_facts_in_scope=1
        )
        assert "most relevant facts" not in prompt

    def test_accepts_dict_facts(self) -> None:
        facts = [{"sentence": "Fact A."}, {"sentence": "Fact B."}]
        prompt, loaded = build_system_prompt(facts)
        assert loaded == 2
        assert "Fact A." in prompt
        assert "Fact B." in prompt

    def test_playground_definitions_removed(self) -> None:
        """System prompt should NOT contain old playground joke text."""
        prompt, _ = build_system_prompt(["Fact."])
        assert "SPECIAL DEFINITIONS" not in prompt
        assert "Boatwing" not in prompt  # no hardcoded joke
