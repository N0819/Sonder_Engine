"""A deliberate act of remembering gets the attention the mind currently has.

The ponder lane asked for a fixed 4 rows while passive recall asked for
`recall_limit` -- 16 when the mind is relaxed, narrowed to 8 and then 4 as
absorption rises. So a character that had DECIDED to interrogate its own memory
was always served as though it were maximally absorbed, which is the one state
it is demonstrably not in.

Measured before the change, on 470 questions nobody on this project wrote
(LongMemEval, RUN at each k): k=4 answers 304 of them and k=16 answers 399.
The cap cost 24% of everything answerable, and the loss fell hardest on
precisely the question shapes a ponder tends to have -- preferences lost 40%
of answerable, multi-session 32%, temporal reasoning 30% -- while questions
whose evidence sits in one row lost 11%. The curve has no knee at 4; 4 is the
bottom of it: 304, 359, 382, 399 at k = 4, 8, 12, 16.

The first version of these numbers was derived from ONE k=16 run by asking
which targets ranked at or below k, and it understated every arm -- worst at
k=4, by 17 probes. Chronological-neighbour padding is computed relative to k,
so a real small-k run admits neighbours a strict top-k slice never contains
(UNBUILT 1.73). Derived ranks are not a substitute for running the arm.

The payload objection is real and was measured rather than waved away: a ponder
fires on roughly 1 turn in 332 across the live corpus, so this spends about a
thousand extra tokens on 0.3% of beats.

What these tests pin is the RELATIONSHIP, not the number. If `_RECALL_LIMIT`
moves, ponder should move with it; if absorption narrows recall, ponder narrows
too.

SINCE 2026-09-29 THE PONDER IS GRADED, and its size is the owner's five (the
owner: "Ponder pulls up 50 candidates using rrf for jev to sort on how well it
answers the ponder"; `memory_jev.jev_ponder_packet`). The LongMemEval numbers
above were retrieval by similarity alone, where more rows was the only way to
hold the answers; a decision model sorting fifty candidates keeps the answers
in its first few. What survives of the relationship: a ponder never keeps more
than the attention the mind has, and never fewer than the old floor of four --
`min(PONDER_LIMIT, max(4, recall_limit))`.
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


def _ponder_k(monkeypatch, chat_id, char_id, absorption=0.0, recall_limit=None, query=PONDER):
    """How many rows the ponder lane asks to keep, captured at the seam."""
    seen = {}
    real = memory.jev_ponder_packet

    def spy(cid, chid, q, **kw):
        if q == query:
            seen["k"] = kw.get("limit")
        return real(cid, chid, q, **kw)

    patch_seam(monkeypatch, "mind.memory_context", "jev_ponder_packet", spy)
    kwargs = {} if recall_limit is None else {"recall_limit": recall_limit}
    memory.build_character_memory_context(
        chat_id, char_id, current_turn_idx=50, current_view="the harbour",
        active_state={}, absorption=absorption, ponder_query=query, **kwargs)
    return seen.get("k")


class TestPonderTracksAttention:
    def test_a_relaxed_mind_ponders_the_owners_five(self, _bank, monkeypatch):
        chat_id, char_id = _bank
        assert _ponder_k(monkeypatch, chat_id, char_id, 0.0) == memory.PONDER_LIMIT == 5

    def test_a_partly_absorbed_mind_still_has_room_for_five(self, _bank, monkeypatch):
        chat_id, char_id = _bank
        assert _ponder_k(monkeypatch, chat_id, char_id, 0.5) == min(memory.PONDER_LIMIT, 8), (
            "absorption 0.35-0.7 narrows recall to 8, which five fits inside")

    def test_a_fully_absorbed_mind_keeps_the_old_floor(self, _bank, monkeypatch):
        """An absorbed mind's ponder is still small: recall narrows to 4,
        and the ponder with it."""
        chat_id, char_id = _bank
        assert _ponder_k(monkeypatch, chat_id, char_id, 0.9) == 4

    def test_the_budget_is_never_below_four(self, _bank, monkeypatch):
        """A caller passing a tiny recall_limit must not silence the lane
        entirely -- a ponder that returns nothing is worse than a small one,
        because the character asked."""
        chat_id, char_id = _bank
        assert _ponder_k(monkeypatch, chat_id, char_id, recall_limit=1, query="the lantern") == 4


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
        pondered = []
        patch_seam(monkeypatch, "mind.memory_context", "jev_ponder_packet",
                   lambda *a, **kw: pondered.append(a) or [])
        memory.build_character_memory_context(
            chat_id=_bank[0], char_id=_bank[1], current_turn_idx=50,
            current_view="the harbour", active_state={})
        assert pondered == [], "no ponder query must mean no ponder net"
        # No search at all: passive recall is the decision model's pick
        # (`mind/memory_jev.py`), and with no pending query nothing else runs.
        assert calls == [], (
            "no ponder query must mean no ponder retrieval, got %r" % (calls,))
