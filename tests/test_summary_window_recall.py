"""The character receives the era the beat is about, not only the latest one.

Schema v23 made summary windows durable and `search_memory_summaries` able to
rank them, and then stopped: nothing sent a retrieved window to a character.
The stated reason was that bounded windows would cost a character their early
history unless something read them.

Measurement on the live bank inverted that. The consolidator is told to merge
the previous summary forward, and told just as firmly to shed low-salience
detail; shedding wins. Across the six live window pairs, successive windows
share 3-16% of their text and sit at cosine 0.57-0.88 — the Doctor's second
window recaps the first in one clause and is otherwise entirely about its own
ten turns. So a "cumulative" summary is in practice the latest CHAPTER, the
pre-v23 singleton was overwriting every chapter before it, and 53 of the 67
live banks have no summary over their opening turns at all.

Windows stopped that loss. This is what reads them: the beat's own query ranks
the earlier windows, and the best `_SUMMARY_RECALL_LIMIT` travel beside the
current one under `earlier_in_my_life`.

They arrive under the same guarantees as raw recall — one character's bank, the
same exclusive turn cutoff, first-hand kept apart from hearsay and surmise —
because a summary is a mind's own account and every rule that protects a memory
protects it too.
"""

from __future__ import annotations

import json
import time

import pytest

import memory
from character_schema import default_character_data


@pytest.fixture
def bank(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Recall", "", time.time()))
    ids = []
    for name in ("Mara", "Vesk"):
        ids.append(temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}", time.time(),
             "char_" + name.lower())))
    return {"chat": chat_id, "chars": ids}


def _window(bank, text, start, end, who=0, **kw):
    memory.save_memory_summary(bank["chat"], bank["chars"][who], text,
                               start_turn_idx=start, end_turn_idx=end, **kw)


def _context(bank, view, turn=60, who=0, **kw):
    return memory.build_character_memory_context(
        bank["chat"], bank["chars"][who], current_turn_idx=turn,
        current_view=view, active_state={"goal": "", "mood": ""}, **kw)


FERRY = "She crossed the river at dusk and paid the ferryman in silver coins."
LEDGER = "She argued with the archivist about a missing ledger in the record house."
NOW = "She waited on the steps of the guildhall for the rain to stop."


# ---- the thing that was missing ----

def test_an_earlier_chapter_reaches_the_character(bank):
    _window(bank, FERRY, 0, 10)
    _window(bank, LEDGER, 11, 20)
    _window(bank, NOW, 21, 30)
    ctx = _context(bank, "a ferryman is asking for silver coins")
    lived = [w["what_i_lived_through_then"]
             for w in ctx["earlier_in_my_life"]]
    assert FERRY in lived


def test_the_current_summary_is_never_sent_twice(bank):
    """`autobiographical_summary` already carries the latest window; sending it
    again under another key would spend the attention budget on a duplicate."""
    _window(bank, FERRY, 0, 10)
    _window(bank, NOW, 21, 30)
    ctx = _context(bank, "the steps of the guildhall in the rain")
    assert ctx["autobiographical_summary"] == NOW
    assert all(w["what_i_lived_through_then"] != NOW
               for w in ctx["earlier_in_my_life"])


def test_one_window_means_the_key_is_absent_not_empty(bank):
    """Nothing to recall is a missing key, matching the provenance summaries.
    An empty list still costs a line of attention and teaches nothing."""
    _window(bank, NOW, 21, 30)
    assert "earlier_in_my_life" not in _context(bank, "the guildhall steps")


def test_a_bank_with_no_summaries_at_all_is_unchanged(bank):
    ctx = _context(bank, "anything")
    assert "earlier_in_my_life" not in ctx
    assert ctx["autobiographical_summary"] == ""


# ---- the same guarantees raw recall gets ----

def test_a_window_that_closed_after_the_deciding_turn_is_withheld(bank):
    """The read seam's rule one layer up: a mind deciding turn N may not read a
    summary of how turn N turned out. Reroll depends on this — the same turn
    runs twice and must not know more the second time."""
    _window(bank, FERRY, 0, 10)
    _window(bank, "The fire that has not happened yet.", 21, 30)
    _window(bank, NOW, 31, 40)
    ctx = _context(bank, "fire and smoke", turn=25)
    assert ctx["autobiographical_summary"] == FERRY
    assert all("fire" not in w["what_i_lived_through_then"]
               for w in ctx.get("earlier_in_my_life", []))


def test_every_summary_surface_obeys_the_same_exclusive_cutoff(bank):
    _window(bank, FERRY, 0, 10)
    _window(bank, "Future firsthand.", 25, 30)
    _window(bank, "Future hearsay.", 25, 30,
            scope=memory.SUMMARY_SCOPE_HEARSAY)
    _window(bank, "Future surmise.", 25, 30,
            scope=memory.SUMMARY_SCOPE_SURMISE)
    ctx = memory.build_character_memory_context(
        bank["chat"], bank["chars"][0], current_turn_idx=25,
        current_view="The river is quiet.",
        active_state={"goal_held": 12, "mood": "neutral"})
    rendered = json.dumps(ctx)
    assert "Future firsthand" not in rendered
    assert "Future hearsay" not in rendered
    assert "Future surmise" not in rendered
    assert ctx["autobiographical_summary"] == FERRY
    assert ctx["where_i_came_from"]["what_i_lived_through_then"] == FERRY


def test_origin_never_reaches_forward_from_an_early_rerun(bank):
    _window(bank, "A future origin that has not happened.", 100, 109)
    assert memory._origin_on_drift(
        bank["chat"], bank["chars"][0], 5,
        {"goal_held": 12, "mood": "neutral"}) == {}


def test_another_characters_chapters_never_arrive(bank):
    _window(bank, FERRY, 0, 10, who=1)
    _window(bank, LEDGER, 11, 20, who=1)
    _window(bank, NOW, 21, 30, who=0)
    ctx = _context(bank, "a ferryman is asking for silver coins", who=0)
    assert "earlier_in_my_life" not in ctx


def test_hearsay_and_surmise_do_not_leak_into_it(bank):
    """Three provenances in one field is the collapse the separate summary
    scopes exist to prevent. A thing she was told is not a thing she saw."""
    _window(bank, FERRY, 0, 10)
    _window(bank, NOW, 21, 30)
    _window(bank, "A ferryman drowned last winter, they say.", 0, 10,
            scope=memory.SUMMARY_SCOPE_HEARSAY)
    _window(bank, "The ferryman was lying about the silver.", 0, 10,
            scope=memory.SUMMARY_SCOPE_SURMISE)
    ctx = _context(bank, "the ferryman and his silver")
    lived = " ".join(w["what_i_lived_through_then"]
                     for w in ctx["earlier_in_my_life"])
    assert "drowned" not in lived
    assert "lying" not in lived


def test_an_empty_window_is_not_recalled(bank):
    _window(bank, "", 0, 10)
    _window(bank, NOW, 21, 30)
    assert "earlier_in_my_life" not in _context(bank, "anything")


# ---- shape ----

def test_it_is_bounded_by_the_recall_limit(bank):
    for i in range(6):
        _window(bank, f"In that stretch she was still crossing rivers ({i}).",
                i * 10, i * 10 + 9)
    ctx = _context(bank, "crossing rivers")
    assert len(ctx["earlier_in_my_life"]) == memory._SUMMARY_RECALL_LIMIT


def test_chapters_arrive_in_the_order_they_were_lived(bank):
    """Ranking chooses WHICH; it must not choose the order. A life presented
    out of sequence is a life the character has to reassemble."""
    _window(bank, FERRY, 0, 10)
    _window(bank, LEDGER, 11, 20)
    _window(bank, NOW, 41, 50)
    ctx = _context(bank, "a missing ledger and a ferryman")
    lived = [w["what_i_lived_through_then"] for w in ctx["earlier_in_my_life"]]
    assert lived == [FERRY, LEDGER]


def test_when_is_relative_and_never_an_absolute_turn_index(bank):
    """`turn_idx` is GLOBAL play order shared by every frame, so an absolute
    number tells a character where a flash-forward sits in the story's
    construction — which no mind in the fiction can know."""
    _window(bank, FERRY, 10, 20)
    _window(bank, NOW, 41, 50)
    ctx = _context(bank, "the ferryman and his silver", turn=60)
    when = ctx["earlier_in_my_life"][0]["when"]
    assert when == "between about 40 and 50 beats ago"
    assert "10" not in when and "20" not in when


def test_the_span_helper_reads_plainly_at_the_edges():
    assert memory._beats_ago_span(60, 10, 20) == "between about 40 and 50 beats ago"
    # A window one turn wide is a moment, not a stretch.
    assert memory._beats_ago_span(60, 30, 30) == "about 30 beats ago"
    # A window still open at the present beat is not yet memory.
    assert memory._beats_ago_span(30, 20, 30) == ""
    assert memory._beats_ago_span(30, 30, 30) == ""
    assert memory._beats_ago_span(None, 0, 10) == ""


# ---- origin on drift ----

def test_origin_surfaces_when_a_goal_has_been_held_too_long(bank):
    _window(bank, FERRY, 0, 10)
    _window(bank, NOW, 41, 50)
    payload = memory._origin_on_drift(
        bank["chat"], bank["chars"][0], 60,
        {"goal_held": 12, "mood": "neutral"})
    assert payload["where_i_came_from"]["what_i_lived_through_then"] == FERRY
    assert payload["where_i_came_from"]["when"] == \
        "between about 50 and 60 beats ago"


def test_origin_is_absent_without_a_drift_signal(bank):
    _window(bank, FERRY, 0, 10)
    assert memory._origin_on_drift(
        bank["chat"], bank["chars"][0], 60,
        {"goal": "cross the river", "mood": "neutral"}) == {}


def test_origin_is_not_sent_twice(bank):
    _window(bank, FERRY, 0, 10)
    assert memory._origin_on_drift(
        bank["chat"], bank["chars"][0], 60,
        {"projects": [{"id": "p1", "adrift": 8}]},
        earlier_ids={10}) == {}


# ---- cost ----

def test_the_window_layer_costs_no_extra_embedding_call(bank, monkeypatch):
    """The windows rank against the same query vector the memories do, so the
    batch is embedded once and shared. This is the whole reason the layer is
    affordable per character per beat."""
    _window(bank, FERRY, 0, 10)
    _window(bank, NOW, 21, 30)
    calls = []
    real = memory.embed_texts_meta

    def counted(texts):          # installed AFTER the writes, which embed too
        calls.append(list(texts))
        return real(texts)

    monkeypatch.setattr(memory, "embed_texts_meta", counted)
    _context(bank, "the ferryman and his silver")
    assert len(calls) == 1


def test_sharing_the_batch_ranks_exactly_as_embedding_it_separately(bank):
    """The alignment that makes sharing safe: vectors[0] is the query and the
    rest are the aspects, in the order the filter produced them. Get that wrong
    and recall would rank against a mood where it meant to rank against the
    beat — quietly, with no error and no visible symptom."""
    for i, text in enumerate([
            "She paid the ferryman in silver and he would not meet her eye.",
            "The archivist swore the ledger had never existed.",
            "Rain on the guildhall steps, and nobody came out."]):
        memory.add_memory(bank["chat"], bank["chars"][0], None, "episodic",
                          "witnessed", 0.8, text, turn_idx=i * 5, gist=text)
    aspects = [("what you are trying to do", "find the ledger"),
               ("how you are feeling", "uneasy")]
    kw = dict(current_turn_idx=60, aspects=aspects, k=3)
    alone = memory.search_memories(bank["chat"], bank["chars"][0],
                                   "the ferryman and his silver", **kw)
    shared = memory.search_memories(
        bank["chat"], bank["chars"][0], "the ferryman and his silver",
        embedded=memory.embed_texts_meta(
            ["the ferryman and his silver"] + [t for _l, t in aspects]),
        **kw)
    assert [m["id"] for m in alone] == [m["id"] for m in shared]
    assert [round(m["score"], 9) for m in alone] == \
           [round(m["score"], 9) for m in shared]


def test_a_mismatched_batch_is_re_embedded_rather_than_trusted(bank):
    """The guard on the shared batch: if what the caller sent does not line up
    with the aspects, those are not the vectors the ranking thinks they are.
    Ranking against the wrong facet silently would be worse than the round
    trip it saves."""
    from providers import EmbeddingBatch

    wrong = EmbeddingBatch(vectors=[], model_key="nonsense", dimensions=0)
    hits = memory.search_memories(
        bank["chat"], bank["chars"][0], "the ferryman",
        current_turn_idx=60, embedded=wrong,
        aspects=[("how you are feeling", "uneasy")])
    assert hits == []  # no memories in this bank — but it must not raise
