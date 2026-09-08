"""One communication-act vocabulary, read by every site.

Review 2026-09-07 finding B14: the set of typed communicative acts that leave
their addressee owing an answer was spelled out twice -- in
`agents/character._unanswered_question_note` (the player's still-unanswered
question) and in `agents.common._asks_player` (is the interaction loop still
waiting on the player?) -- and the act->verb rendering table was spelled out
twice more, present tense in `agents.common.communication_surface` and past
tense in `persist/commit_memory._own_sequence_memory`.  Four copies of
two facts, each free to disagree with its twin.  These tests hold each fact to
one source.
"""

import inspect

import pytest

from agents.common import (
    COMMUNICATION_ACT_VERBS,
    COMMUNICATION_ACTS_AWAITING_REPLY,
    _asks_player,
    communication_act,
    communication_awaits_reply,
    communication_surface,
    communication_verb,
)


def _comm(act, content="where the road goes", **extra):
    return {"type": "communication", "act": act, "content": content, **extra}


class TestOneAwaitingReplyVocabulary:
    def test_neither_predicate_site_keeps_a_private_copy(self):
        from agents import character

        for owner in (_asks_player, character._unanswered_question_note):
            assert '"request"' not in inspect.getsource(owner), (
                f"{owner.__name__} re-spells the awaiting-a-reply vocabulary "
                "instead of reading COMMUNICATION_ACTS_AWAITING_REPLY")

    @pytest.mark.parametrize("act", sorted(COMMUNICATION_ACTS_AWAITING_REPLY))
    def test_an_act_put_to_its_addressee_awaits_a_reply(self, act):
        assert communication_awaits_reply(_comm(act))

    @pytest.mark.parametrize("act", ["tell", "explain", "warn", "say", ""])
    def test_an_act_that_only_tells_does_not(self, act):
        assert not communication_awaits_reply(_comm(act))

    def test_the_act_is_read_the_same_way_everywhere(self):
        """A model writing `"Ask "` means the act one writing `"ask"` means.

        `communication_surface` collapsed whitespace and casefolded; the two
        awaiting-a-reply predicates did neither, so one event was rendered as
        a question and treated as a statement.
        """
        messy = _comm("  Ask\n")
        assert communication_act(messy) == "ask"
        assert communication_awaits_reply(messy)
        assert communication_surface(messy) == "asks where the road goes"

    def test_the_interaction_loop_waits_on_a_case_varied_ask(self):
        result = {"sequence": [_comm("Ask", targets=["the player"])]}
        assert _asks_player(result, {}) is True

    def test_the_interaction_loop_does_not_wait_on_a_telling(self):
        result = {"sequence": [_comm("tell", targets=["the player"])]}
        assert _asks_player(result, {}) is False


class TestOneActVerbTable:
    def test_the_past_tense_site_reads_the_shared_table(self):
        from persist import commit

        source = inspect.getsource(commit._own_sequence_memory)
        assert '"reassure"' not in source, (
            "commit_memory carries a second act->verb table instead of "
            "reading COMMUNICATION_ACT_VERBS")

    @pytest.mark.parametrize("act", sorted(COMMUNICATION_ACT_VERBS))
    def test_every_known_act_renders_in_both_tenses(self, act):
        present = communication_verb(_comm(act))
        past = communication_verb(_comm(act), "past", fallback="communicated")
        assert present and past
        assert past != "communicated"

    def test_question_survives_into_the_speakers_own_memory(self):
        """The measured divergence: the past table never knew `question`.

        Perception rendered the act as "asks ...", and the mind that performed
        it remembered "I communicated ...".
        """
        event = _comm("question")
        assert communication_surface(event) == "asks where the road goes"
        assert communication_verb(event, "past",
                                  fallback="communicated") == "asked"

    def test_an_unknown_act_keeps_each_surfaces_own_fallback(self):
        """The TABLE is shared; the fallback is legitimately surface-local."""
        event = _comm("banter")
        assert communication_verb(event) == "banters"
        assert communication_verb(event, "past",
                                  fallback="communicated") == "communicated"

    def test_first_person_memory_renders_a_question_as_asked(self):
        from persist.commit import _own_sequence_memory

        content, _gist = _own_sequence_memory(
            [_comm("question", content="where the road goes")])
        assert content == "I asked where the road goes."
