"""Tests for session-based chat: CRUD, retriever, smart/efficient modes, prompt builder."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.ai_provider import AIProvider
from artiFACT.kernel.models import (
    FcChatMessage,
    FcChatSession,
    FcFact,
    FcFactVersion,
    FcNode,
    FcUser,
)
from artiFACT.modules.ai_chat.prompt_builder import build_system_prompt
from artiFACT.modules.ai_chat.retriever import (
    estimate_scope_tokens,
    load_all_facts,
    retrieve_facts,
)
from artiFACT.modules.ai_chat.service import chat_with_session
from artiFACT.modules.ai_chat.session_manager import (
    MAX_ACTIVE_SESSIONS,
    close_session,
    create_session,
    get_active_sessions,
    get_messages,
    get_session,
    save_message,
)
from artiFACT.modules.auth_admin.ai_key_manager import save_ai_key


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def user_with_key(db: AsyncSession, contributor_user: FcUser) -> FcUser:
    """Contributor user with an OpenAI key saved."""
    await save_ai_key(db, contributor_user.user_uid, "openai", "sk-test-chat-1234")
    return contributor_user


@pytest_asyncio.fixture
async def program_with_facts(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
) -> tuple[FcNode, FcNode, list[str]]:
    """Root program with child node containing published facts."""
    sentences = [
        "The propulsion system uses a solid rocket motor.",
        "The guidance system relies on GPS/INS integration.",
        "The warhead weighs 500 pounds.",
        "The hydraulic actuators control the fin surfaces.",
        "The datalink operates at L-band frequency.",
    ]
    for sentence in sentences:
        fact = FcFact(
            fact_uid=uuid.uuid4(),
            node_uid=child_node.node_uid,
            created_by_uid=admin_user.user_uid,
        )
        db.add(fact)
        await db.flush()
        ver = FcFactVersion(
            version_uid=uuid.uuid4(),
            fact_uid=fact.fact_uid,
            state="published",
            display_sentence=sentence,
            created_by_uid=admin_user.user_uid,
        )
        db.add(ver)
        await db.flush()
        fact.current_published_version_uid = ver.version_uid
        await db.flush()
    return root_node, child_node, sentences


@pytest_asyncio.fixture
async def large_program(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
) -> tuple[FcNode, int]:
    """Program with many facts for threshold/estimation tests."""
    count = 200
    for i in range(count):
        fact = FcFact(
            fact_uid=uuid.uuid4(),
            node_uid=child_node.node_uid,
            created_by_uid=admin_user.user_uid,
        )
        db.add(fact)
        await db.flush()
        ver = FcFactVersion(
            version_uid=uuid.uuid4(),
            fact_uid=fact.fact_uid,
            state="published",
            display_sentence=f"Generic fact number {i} about system configuration.",
            created_by_uid=admin_user.user_uid,
        )
        db.add(ver)
        await db.flush()
        fact.current_published_version_uid = ver.version_uid
        await db.flush()
    return root_node, count


@pytest_asyncio.fixture
async def signed_facts(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
) -> tuple[FcNode, list[str]]:
    """Node with a mix of published-only and signed facts."""
    pub_sentence = "Only published, not signed."
    signed_sentence = "This fact is signed."

    # Published-only fact
    f1 = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
    )
    db.add(f1)
    await db.flush()
    v1 = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=f1.fact_uid,
        state="published",
        display_sentence=pub_sentence,
        created_by_uid=admin_user.user_uid,
    )
    db.add(v1)
    await db.flush()
    f1.current_published_version_uid = v1.version_uid
    await db.flush()

    # Signed fact
    f2 = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
    )
    db.add(f2)
    await db.flush()
    v2 = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=f2.fact_uid,
        state="signed",
        display_sentence=signed_sentence,
        created_by_uid=admin_user.user_uid,
    )
    db.add(v2)
    await db.flush()
    f2.current_signed_version_uid = v2.version_uid
    f2.current_published_version_uid = v2.version_uid
    await db.flush()

    return root_node, [pub_sentence, signed_sentence]


# ── Session CRUD ─────────────────────────────────────────────────────


class TestSessionCRUD:
    @pytest.mark.asyncio
    async def test_create_session(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        assert session.chat_uid is not None
        assert session.user_uid == contributor_user.user_uid
        assert session.mode == "efficient"
        assert session.fact_filter == "published"
        assert session.is_active is True

    @pytest.mark.asyncio
    async def test_get_active_sessions(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        s1 = await create_session(db, contributor_user.user_uid, root_node.node_uid)
        s2 = await create_session(db, contributor_user.user_uid, root_node.node_uid)
        # Close one
        await close_session(db, s1.chat_uid, contributor_user.user_uid)

        active = await get_active_sessions(db, contributor_user.user_uid)
        assert len(active) == 1
        assert active[0].chat_uid == s2.chat_uid

    @pytest.mark.asyncio
    async def test_close_session_deletes_messages(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        for i in range(5):
            await save_message(db, session.chat_uid, "user", f"msg {i}")

        await close_session(db, session.chat_uid, contributor_user.user_uid)

        msgs = await get_messages(db, session.chat_uid)
        assert len(msgs) == 0

        # Session record still exists with token totals preserved
        refreshed = await db.get(FcChatSession, session.chat_uid)
        assert refreshed is not None
        assert refreshed.is_active is False

    @pytest.mark.asyncio
    async def test_close_session_requires_owner(
        self, db: AsyncSession, contributor_user: FcUser, viewer_user: FcUser,
        root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        from artiFACT.kernel.exceptions import NotFound

        with pytest.raises(NotFound):
            await close_session(db, session.chat_uid, viewer_user.user_uid)


# ── Messages ─────────────────────────────────────────────────────────


class TestMessages:
    @pytest.mark.asyncio
    async def test_save_message_updates_session(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        await save_message(
            db, session.chat_uid, "user", "Hello",
            input_tokens=10, output_tokens=0,
        )
        await db.refresh(session)
        assert session.last_message_at is not None
        assert session.total_input_tokens == 10

    @pytest.mark.asyncio
    async def test_get_messages_ordered(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        await save_message(db, session.chat_uid, "user", "First")
        await save_message(db, session.chat_uid, "assistant", "Second")
        await save_message(db, session.chat_uid, "user", "Third")
        await save_message(db, session.chat_uid, "assistant", "Fourth")

        msgs = await get_messages(db, session.chat_uid)
        assert len(msgs) == 4
        assert [m.content for m in msgs] == ["First", "Second", "Third", "Fourth"]

    @pytest.mark.asyncio
    async def test_messages_survive_page_reload(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        """Messages persist in PostgreSQL — simulated by re-querying."""
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        await save_message(db, session.chat_uid, "user", "Msg 1")
        await save_message(db, session.chat_uid, "assistant", "Reply 1")
        await save_message(db, session.chat_uid, "user", "Msg 2")

        # Simulate "page reload" by re-fetching from DB
        msgs = await get_messages(db, session.chat_uid)
        assert len(msgs) == 3
        assert msgs[0].content == "Msg 1"
        assert msgs[1].content == "Reply 1"
        assert msgs[2].content == "Msg 2"


# ── Retriever ────────────────────────────────────────────────────────


class TestRetriever:
    @pytest.mark.asyncio
    async def test_retrieve_facts_returns_scored_results(
        self, db: AsyncSession, program_with_facts: tuple
    ) -> None:
        root, child, sentences = program_with_facts
        from artiFACT.kernel.tree.descendants import get_descendants

        scope = await get_descendants(db, root.node_uid)
        results = await retrieve_facts(db, "propulsion rocket motor", scope)
        assert len(results) > 0
        all_sentences = [r.display_sentence for r in results]
        assert any("propulsion" in s.lower() for s in all_sentences)

    @pytest.mark.asyncio
    async def test_load_all_facts_returns_everything(
        self, db: AsyncSession, program_with_facts: tuple
    ) -> None:
        root, child, sentences = program_with_facts
        from artiFACT.kernel.tree.descendants import get_descendants

        scope = await get_descendants(db, root.node_uid)
        results = await load_all_facts(db, scope)
        assert len(results) == len(sentences)

    @pytest.mark.asyncio
    async def test_estimate_scope_tokens(
        self, db: AsyncSession, program_with_facts: tuple
    ) -> None:
        root, _, sentences = program_with_facts
        est = await estimate_scope_tokens(db, root.node_uid, None, "published")
        assert est["fact_count"] == len(sentences)
        assert est["estimated_tokens"] == len(sentences) * 15
        assert est["warning"] is False

    @pytest.mark.asyncio
    async def test_estimate_warns_above_2000_tokens(
        self, db: AsyncSession, large_program: tuple
    ) -> None:
        root, count = large_program
        est = await estimate_scope_tokens(db, root.node_uid, None, "published")
        assert est["fact_count"] == count
        assert est["warning"] is True


# ── Unified Pipeline ─────────────────────────────────────────────────


class TestUnifiedPipeline:
    @pytest.mark.asyncio
    async def test_full_corpus_loads_all_facts(
        self, db: AsyncSession, user_with_key: FcUser,
        program_with_facts: tuple, contributor_permission: None
    ) -> None:
        root, child, sentences = program_with_facts
        session = await create_session(
            db, user_with_key.user_uid, root.node_uid,
        )

        async def _mock_stream(self, key_row, messages, **kwargs):
            system = messages[0]["content"]
            for s in sentences:
                assert s in system, f"Missing fact in full_corpus mode: {s}"

            async def _gen():
                yield "Test response."
            return _gen()

        with patch.object(AIProvider, "stream_for_key", new=_mock_stream):
            collected: list[str] = []
            async for chunk in chat_with_session(
                db, session.chat_uid, "Tell me about the system.", user_with_key,
                full_corpus=True,
            ):
                collected.append(chunk)
        assert len(collected) > 0

    @pytest.mark.asyncio
    async def test_bm25_retrieval_includes_relevant_fact(
        self, db: AsyncSession, user_with_key: FcUser,
        program_with_facts: tuple, contributor_permission: None
    ) -> None:
        root, child, sentences = program_with_facts
        session = await create_session(
            db, user_with_key.user_uid, root.node_uid,
        )

        system_prompts: list[str] = []

        async def _mock_stream(self, key_row, messages, **kwargs):
            system_prompts.append(messages[0]["content"])

            async def _gen():
                yield "Propulsion info."
            return _gen()

        with patch.object(AIProvider, "stream_for_key", new=_mock_stream):
            async for _ in chat_with_session(
                db, session.chat_uid, "What is the propulsion system?", user_with_key,
            ):
                pass

        assert len(system_prompts) == 1
        prompt = system_prompts[0]
        assert "propulsion" in prompt.lower()

    @pytest.mark.asyncio
    async def test_search_command_uses_extracted_query(
        self, db: AsyncSession, user_with_key: FcUser,
        program_with_facts: tuple, contributor_permission: None
    ) -> None:
        root, child, sentences = program_with_facts
        session = await create_session(
            db, user_with_key.user_uid, root.node_uid,
        )

        system_prompts: list[str] = []

        async def _mock_stream(self, key_row, messages, **kwargs):
            system_prompts.append(messages[0]["content"])

            async def _gen():
                yield "Hydraulics info."
            return _gen()

        with patch.object(AIProvider, "stream_for_key", new=_mock_stream):
            async for _ in chat_with_session(
                db, session.chat_uid, "search for hydraulics", user_with_key,
            ):
                pass

        assert len(system_prompts) == 1
        prompt = system_prompts[0]
        assert "hydraulic" in prompt.lower()


# ── Fact filter ──────────────────────────────────────────────────────


class TestFactFilter:
    @pytest.mark.asyncio
    async def test_load_all_published_facts(
        self, db: AsyncSession, signed_facts: tuple
    ) -> None:
        root, sentences = signed_facts
        from artiFACT.kernel.tree.descendants import get_descendants

        scope = await get_descendants(db, root.node_uid)
        facts = await load_all_facts(db, scope)
        fact_sentences = [f.display_sentence for f in facts]
        # load_all_facts returns published facts via current_published_version_uid
        assert len(fact_sentences) == 2


# ── Send message saves both roles ────────────────────────────────────


class TestChatWithSession:
    @pytest.mark.asyncio
    async def test_send_message_saves_both_roles(
        self, db: AsyncSession, user_with_key: FcUser,
        program_with_facts: tuple, contributor_permission: None
    ) -> None:
        root, child, sentences = program_with_facts
        session = await create_session(
            db, user_with_key.user_uid, root.node_uid
        )

        async def _mock_stream(self, key_row, messages, **kwargs):
            async def _gen():
                yield "The answer."
            return _gen()

        with patch.object(AIProvider, "stream_for_key", new=_mock_stream):
            async for _ in chat_with_session(
                db, session.chat_uid, "What is the program?", user_with_key,
            ):
                pass

        msgs = await get_messages(db, session.chat_uid)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        assert msgs[1].content == "The answer."

        # Session token totals updated
        refreshed = await db.get(FcChatSession, session.chat_uid)
        assert refreshed.last_message_at is not None
        assert refreshed.total_input_tokens > 0

    @pytest.mark.asyncio
    async def test_send_message_streams_sse(
        self, db: AsyncSession, user_with_key: FcUser,
        program_with_facts: tuple, contributor_permission: None
    ) -> None:
        root, child, sentences = program_with_facts
        session = await create_session(
            db, user_with_key.user_uid, root.node_uid
        )

        async def _mock_stream(self, key_row, messages, **kwargs):
            async def _gen():
                yield "Hello "
                yield "world."
            return _gen()

        with patch.object(AIProvider, "stream_for_key", new=_mock_stream):
            collected: list[str] = []
            async for chunk in chat_with_session(
                db, session.chat_uid, "Hi", user_with_key,
            ):
                collected.append(chunk)

        all_text = "".join(collected)
        assert "text/event-stream" not in all_text  # it's the raw SSE data
        assert "chunk" in all_text
        assert '"done": true' in all_text or '"done":true' in all_text


# ── Prompt builder (new tests) ───────────────────────────────────────


class TestPromptBuilderNew:
    def test_system_prompt_no_token_cap(self) -> None:
        facts = [f"Fact {i}." for i in range(300)]
        prompt, loaded = build_system_prompt(facts)
        assert loaded == 300
        assert "Fact 299." in prompt

    def test_system_prompt_includes_program_name(self) -> None:
        prompt, _ = build_system_prompt(["Fact."], program_name="SNIPE-B")
        assert "SNIPE-B" in prompt

    def test_partial_load_prompt_includes_coverage_note(self) -> None:
        prompt, _ = build_system_prompt(
            ["Fact."], total_facts_in_scope=100
        )
        assert "most relevant facts" in prompt

    def test_playground_definitions_removed(self) -> None:
        prompt, _ = build_system_prompt(["Fact."])
        assert "SPECIAL DEFINITIONS" not in prompt

    def test_system_prompt_concise(self) -> None:
        """System prompt instructions should be ~80 tokens, not ~400."""
        prompt, _ = build_system_prompt([])
        # The instructions portion (before FACTS) should be concise
        from artiFACT.modules.ai_chat.prompt_builder import count_tokens

        # Prompt with no facts — just instructions
        assert count_tokens(prompt) < 200


# ── Max 5 sessions limit ───────────────────────────────────────────


class TestSessionLimit:
    @pytest.mark.asyncio
    async def test_create_session_enforces_max_limit(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        for _ in range(MAX_ACTIVE_SESSIONS):
            await create_session(db, contributor_user.user_uid, root_node.node_uid)

        from artiFACT.kernel.exceptions import Conflict

        with pytest.raises(Conflict):
            await create_session(db, contributor_user.user_uid, root_node.node_uid)

    @pytest.mark.asyncio
    async def test_closed_session_frees_slot(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        sessions = []
        for _ in range(MAX_ACTIVE_SESSIONS):
            sessions.append(
                await create_session(db, contributor_user.user_uid, root_node.node_uid)
            )
        # Close one — should free a slot
        await close_session(db, sessions[0].chat_uid, contributor_user.user_uid)
        new_session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        assert new_session.chat_uid is not None


# ── Conversation history cap ───────────────────────────────────────


class TestConversationHistoryCap:
    @pytest.mark.asyncio
    async def test_history_capped_at_20_messages(
        self, db: AsyncSession, user_with_key: FcUser,
        program_with_facts: tuple, contributor_permission: None
    ) -> None:
        root, child, sentences = program_with_facts
        session = await create_session(
            db, user_with_key.user_uid, root.node_uid,
        )

        # Seed 30 messages (15 user + 15 assistant)
        for i in range(15):
            await save_message(db, session.chat_uid, "user", f"Question {i}")
            await save_message(db, session.chat_uid, "assistant", f"Answer {i}")

        captured_messages: list[list[dict]] = []

        async def _mock_stream(self, key_row, messages, **kwargs):
            captured_messages.append(messages)

            async def _gen():
                yield "Response."
            return _gen()

        with patch.object(AIProvider, "stream_for_key", new=_mock_stream):
            async for _ in chat_with_session(
                db, session.chat_uid, "Final question", user_with_key,
            ):
                pass

        assert len(captured_messages) == 1
        ai_messages = captured_messages[0]
        # First is system prompt, rest are conversation messages
        conversation = [m for m in ai_messages if m["role"] != "system"]
        # 30 prior + 1 new user = 31, but capped at last 20 prior + new user
        # The 20 cap is on prior messages; the new user message is included in prior
        # since save_message is called before building conversation
        assert len(conversation) <= 21  # 20 capped prior + at most 1 edge case

    @pytest.mark.asyncio
    async def test_all_messages_still_persisted(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        """Even though only 20 are sent to AI, all messages are kept in DB."""
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        for i in range(25):
            await save_message(db, session.chat_uid, "user", f"Message {i}")

        msgs = await get_messages(db, session.chat_uid)
        assert len(msgs) == 25  # all persisted


# ── Token accumulation ─────────────────────────────────────────────


class TestTokenAccumulation:
    @pytest.mark.asyncio
    async def test_tokens_accumulate_across_messages(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        await save_message(
            db, session.chat_uid, "user", "q1", input_tokens=100, output_tokens=0
        )
        await save_message(
            db, session.chat_uid, "assistant", "a1", input_tokens=0, output_tokens=200
        )
        await save_message(
            db, session.chat_uid, "user", "q2", input_tokens=150, output_tokens=0
        )
        await save_message(
            db, session.chat_uid, "assistant", "a2", input_tokens=0, output_tokens=300
        )
        await db.refresh(session)
        assert session.total_input_tokens == 250
        assert session.total_output_tokens == 500

    @pytest.mark.asyncio
    async def test_close_preserves_token_totals(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        await save_message(
            db, session.chat_uid, "user", "q", input_tokens=50, output_tokens=0
        )
        await save_message(
            db, session.chat_uid, "assistant", "a", input_tokens=0, output_tokens=75
        )
        await close_session(db, session.chat_uid, contributor_user.user_uid)

        refreshed = await db.get(FcChatSession, session.chat_uid)
        assert refreshed.total_input_tokens == 50
        assert refreshed.total_output_tokens == 75
        assert refreshed.is_active is False


# ── SSE streaming response format ──────────────────────────────────


class TestStreamingFormat:
    @pytest.mark.asyncio
    async def test_stream_contains_chunk_and_done_events(
        self, db: AsyncSession, user_with_key: FcUser,
        program_with_facts: tuple, contributor_permission: None
    ) -> None:
        root, child, sentences = program_with_facts
        session = await create_session(
            db, user_with_key.user_uid, root.node_uid
        )

        async def _mock_stream(self, key_row, messages, **kwargs):
            async def _gen():
                yield "Part 1 "
                yield "Part 2."
            return _gen()

        with patch.object(AIProvider, "stream_for_key", new=_mock_stream):
            chunks = []
            async for chunk in chat_with_session(
                db, session.chat_uid, "Test", user_with_key,
            ):
                chunks.append(chunk)

        all_text = "".join(chunks)
        # Should have chunk events and a done event
        assert '"chunk":' in all_text or '"chunk": ' in all_text
        assert '"done":' in all_text or '"done": ' in all_text
        # Should have session_total_tokens in done event
        assert "session_total_tokens" in all_text
