"""The runaway-output guard reached the streaming path only.

`OutputGuard` is fed by `_guarded_sink`, and that sink exists only when a
caller has armed `token_sink` -- which `agents/runtime.py` does for pipeline
steps and nothing else does. So every caller that runs OUTSIDE a turn got its
response unchecked: the Writers' Room (Planner, Charter Planner, Dramaturge,
bible fold), and any other non-streamed call. The room is the one that made it
visible, because raising its response cap to 20k tokens gives a degenerating
model far more room to run.

Guarded where the text is finished rather than where it streams, so one check
covers both provider shapes and every caller of either. `DegenerateOutput` is
already a retryable `LLMError`, so the existing retry machinery handles it and
no call site needed a new branch.
"""
import pytest

from llm.providers import DegenerateOutput, guard_response


class TestTheGuardOverAFinishedResponse:
    def test_ordinary_prose_passes(self):
        assert guard_response("The harbour was cold and the boat was late.") \
            == "The harbour was cold and the boat was late."

    def test_a_short_response_is_never_judged(self):
        """The streaming guard ignores anything under 160 characters, and a
        finished short answer must not be held to a stricter bar than the same
        answer arriving in pieces."""
        assert guard_response("ok") == "ok"

    def test_runaway_whitespace_is_refused(self):
        with pytest.raises(DegenerateOutput):
            guard_response("A line." + " " * 900 + "more")

    def test_a_repeating_block_is_refused(self):
        with pytest.raises(DegenerateOutput):
            guard_response("The lamp gutters in the draught. " * 400)

    def test_none_and_empty_are_returned_unchanged(self):
        assert guard_response(None) is None
        assert guard_response("") == ""


class TestItIsWiredIntoBothProviderShapes:
    def test_the_openai_shaped_return_is_guarded(self):
        import inspect

        from llm import providers
        src = inspect.getsource(providers._chat_complete_once)
        # Both non-streaming returns -- the Anthropic block join and the
        # OpenAI-shaped message content -- hand their text through the guard;
        # the streaming legs keep their own per-attempt guard.
        assert src.count("guard_response(") == 2

    def test_the_room_inherits_it_without_its_own_branch(self):
        import inspect

        from agents import dramaturge, story_planner
        for module in (story_planner, dramaturge):
            src = inspect.getsource(module._call)
            assert "OutputGuard" not in src
            assert "guard_response" not in src


class TestTheRoomsCapsAreOneNumber:
    def test_every_room_response_cap_is_twenty_thousand_tokens(self):
        from agents.dramaturge import DRAMATURGE_MAX_TOKENS
        from agents.story_planner import (CHARTER_PLANNER_MAX_TOKENS,
                                          PLANNER_MAX_TOKENS)
        from story.room_bible import BIBLE_FOLD_MAX_TOKENS

        assert {PLANNER_MAX_TOKENS, CHARTER_PLANNER_MAX_TOKENS,
                DRAMATURGE_MAX_TOKENS, BIBLE_FOLD_MAX_TOKENS} == {20_000}

    def test_nothing_downstream_truncates_what_the_cap_allows(self):
        """A response cap raised while the store that holds the answer keeps
        its old ceiling is a raise that does nothing and says nothing."""
        from agents.story_planner import PLANNER_REPLY_CHARS
        from story.room_conversation import ROOM_REPLY_CHARS

        assert PLANNER_REPLY_CHARS <= ROOM_REPLY_CHARS

    def test_a_players_brief_keeps_its_own_smaller_ceiling(self):
        """The two were one constant and are two questions: what the room may
        say back is not an argument about pasted documents."""
        from story.room_conversation import (ROLE_MESSAGE_CHARS,
                                             ROOM_MESSAGE_CHARS,
                                             ROOM_REPLY_CHARS)

        assert ROOM_MESSAGE_CHARS < ROOM_REPLY_CHARS
        assert ROLE_MESSAGE_CHARS["player"] == ROOM_MESSAGE_CHARS
        assert ROLE_MESSAGE_CHARS["planner"] == ROOM_REPLY_CHARS

    def test_a_long_room_reply_survives_the_store(self, temp_db):
        import time

        from story.room_conversation import add_message
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Room", "", time.time()))
        long_reply = "The harbour plan, in detail. " * 500  # ~14k chars

        row = add_message(cid, None, "planner", long_reply)

        assert len(row["text"]) == len(long_reply.strip())
