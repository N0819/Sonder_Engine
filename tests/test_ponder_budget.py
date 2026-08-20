"""A deliberate act of remembering gets the attention the mind currently has.

The ponder lane asked for a fixed 4 rows while passive recall asked for
`recall_limit` -- 16 when the mind is relaxed, narrowed to 8 and then 4 as
absorption rises. So a character that had DECIDED to interrogate its own memory
was always served as though it were maximally absorbed, which is the one state
it is demonstrably not in.

Measured before the change, on 470 questions nobody on this project wrote
(LongMemEval, ranks taken from the k=16 payload): k=4 answers 287 of them and
k=16 answers 396. The cap cost 28% of everything answerable, and the loss fell
hardest on precisely the question shapes a ponder tends to have -- preferences
lost 47% of answerable, multi-session 34%, temporal reasoning 32% -- while
questions whose evidence sits in one row barely noticed. The curve has no knee
at 4; 4 is the bottom of it.

The payload objection is real and was measured rather than waved away: a ponder
fires on roughly 1 turn in 332 across the live corpus, so this spends about a
thousand extra tokens on 0.3% of beats.

What these tests pin is the RELATIONSHIP, not the number. If `_RECALL_LIMIT`
moves, ponder should move with it; if absorption narrows recall, ponder narrows
too.
"""

from __future__ import annotations

import time

import pytest

from mind import memory
from tests.helpers import patch_seam


@pytest.fixture
def _bank(temp_db):
    """One character with more rows than any ponder budget would return."""
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("T", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    for i in range(40):
        memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.5,
                          f"The lantern on the {i}th night by the harbour wall.",
                          turn_idx=i)
    return chat_id, char_id


PONDER = "what do I know about the lantern"


def _ponder_k(monkeypatch, chat_id, char_id, absorption):
    """The k the ponder lane actually asks for, captured at the seam."""
    seen = {}
    real = memory.search_memories

    def spy(cid, chid, query, **kw):
        # By the QUERY, not by include_archived: passive recall passes that
        # flag too, so a flag-based spy reads whichever call ran last and
        # only happens to be right because ponder runs second.
        if query == PONDER:
            seen["k"] = kw.get("k")
        return real(cid, chid, query, **kw)

    patch_seam(monkeypatch, "mind.memory_context", "search_memories", spy)
    memory.build_character_memory_context(
        chat_id, char_id, current_turn_idx=50, current_view="the harbour",
        active_state={}, absorption=absorption,
        ponder_query=PONDER)
    return seen.get("k")


class TestPonderTracksAttention:
    def test_a_relaxed_mind_ponders_at_the_full_recall_budget(
            self, _bank, monkeypatch):
        chat_id, char_id = _bank
        assert _ponder_k(monkeypatch, chat_id, char_id, 0.0) == memory._RECALL_LIMIT

    def test_a_partly_absorbed_mind_ponders_narrower(self, _bank, monkeypatch):
        chat_id, char_id = _bank
        k = _ponder_k(monkeypatch, chat_id, char_id, 0.5)
        assert k == 8, "absorption 0.35-0.7 narrows recall to 8"

    def test_a_fully_absorbed_mind_keeps_the_old_floor(self, _bank, monkeypatch):
        """The change must not make an absorbed mind ponder MORE. Four was
        always right for this case; it was only ever wrong as a ceiling."""
        chat_id, char_id = _bank
        assert _ponder_k(monkeypatch, chat_id, char_id, 0.9) == 4

    def test_the_budget_is_never_below_four(self, _bank, monkeypatch):
        """A caller passing a tiny recall_limit must not silence the lane
        entirely -- a ponder that returns nothing is worse than a small one,
        because the character asked."""
        chat_id, char_id = _bank
        seen = {}
        real = memory.search_memories

        def spy(cid, chid, query, **kw):
            if query == "the lantern":
                seen["k"] = kw.get("k")
            return real(cid, chid, query, **kw)

        patch_seam(monkeypatch, "mind.memory_context", "search_memories", spy)
        memory.build_character_memory_context(
            chat_id, char_id, current_turn_idx=50, current_view="the harbour",
            active_state={}, recall_limit=1, ponder_query="the lantern")
        assert seen.get("k") == 4


class TestPonderStillDelivers:
    def test_a_ponder_returns_rows_and_they_are_labelled(self, _bank,
                                                         monkeypatch):
        chat_id, char_id = _bank
        ctx = memory.build_character_memory_context(
            chat_id, char_id, current_turn_idx=50, current_view="the harbour",
            active_state={}, ponder_query="what do I know about the lantern")
        # Pondered rows are not a separate key: they merge into recall and
        # carry `deliberate_ponder` in `retrieval_origin`, which is how the
        # character tells what it ASKED for from what merely surfaced.
        #
        # A LIST, not a string: a row can arrive through both lanes on the
        # same beat, and the payload says so rather than picking one.
        def origins(item):
            got = item.get("retrieval_origin")
            return got if isinstance(got, list) else [got] if got else []

        tagged = [item for value in ctx.values() if isinstance(value, list)
                  for item in value if isinstance(item, dict)
                  and "deliberate_ponder" in origins(item)]
        assert tagged, "the deliberate lane must deliver rows it marks as its own"

    def test_no_ponder_query_costs_nothing(self, _bank, monkeypatch):
        """The lane is opt-in: with no pending query it must not retrieve."""
        calls = []
        real = memory.search_memories

        def spy(cid, chid, query, **kw):
            calls.append(query)
            return real(cid, chid, query, **kw)

        patch_seam(monkeypatch, "mind.memory_context", "search_memories", spy)
        memory.build_character_memory_context(
            chat_id=_bank[0], char_id=_bank[1], current_turn_idx=50,
            current_view="the harbour", active_state={})
        # Exactly one retrieval -- passive recall -- and no second call.
        assert len(calls) == 1, (
            "no ponder query must mean no second retrieval, got %r" % (calls,))
