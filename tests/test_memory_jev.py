"""The decision model picks what a mind remembers (mind/memory_jev.py).

Recall used to keep the top 24 of a fused ranking of the beat's words. It is
now a net of the rows the mind may see, graded by Jev for how each bears on
this moment and on what the mind is trying to do, best first. Blind-graded
before landing (docs/experiments/JEV_MEMORY_PROBE_2026_09_26.md): 1.84 against
1.14 on a 0-3 scale. These pin the shape: the grade decides, the state is the
mind's, the author's preview pays for nothing, a silent decision model leaves
the net's own order, the recent buffer is never spent, a reworded belief is
kept once, and the affect pass reads the pick best first.
"""

from __future__ import annotations

import time

import pytest

from llm import decisions
from mind import affect_pass, memory

KEY = "brass key"
#: Words for rows that share nothing but chance: rows built from one template
#: are one belief reworded to the near-duplicate cut, and it keeps one.
_WORDS = ("anchor bramble cinder dovetail ember falcon garnet harbour ivory juniper kettle "
          "lantern meadow nettle orchard pebble quarry rafter saffron thistle umber velvet "
          "willow yarrow zephyr acorn bellows copper drizzle ferry gable hollow inkwell jetty "
          "keel loam mortar oxbow pewter quill rook sluice tallow vane wicker").split()


def _row_text(i):
    import random
    rng = random.Random(i)
    words = " ".join(rng.sample(_WORDS, 7))
    return f"Mara hid the {KEY} beneath {words}." if i % 10 == 3 else f"Mara noticed {words}."


@pytest.fixture
def _bank(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("T", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    for i in range(40):
        memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.5, _row_text(i),
                          turn_idx=i)
    return chat_id, char_id


def _grade_by_key(asked):
    """Jev, as a test: the key rows bear strongly, the rest not at all."""
    def answer(state, questions):
        asked.append((state, questions))
        out = {}
        for qkey, q in questions.items():
            strong = KEY in q["instructions"]
            out[qkey] = {"type": "choice", "choice": "strong" if strong else "none",
                         "probabilities": ({"strong": 0.9, "clear": 0.1} if strong
                                           else {"none": 0.9, "slight": 0.1})}
        return out
    return answer


PERSON = {"name": "Mara", "drive": "to keep the harbour's secrets",
          "values": ["loyalty over comfort"]}


def _context(chat_id, char_id, turn=50, **kw):
    return memory.build_character_memory_context(
        chat_id, char_id, current_turn_idx=turn, current_view="the harbour at night",
        active_state={"goal": "find the key", "mood": "uneasy"}, **kw)


def test_recall_is_the_decision_models_pick(_bank, monkeypatch):
    chat_id, char_id = _bank
    asked = []
    monkeypatch.setattr(decisions, "OVERRIDE", _grade_by_key(asked))
    ctx = _context(chat_id, char_id, person=PERSON)
    picked = ctx["recalled_old_memories"]
    internal = ctx["_internal"]
    # Every key row came back, and the pick's own order leads with them.
    key_refs = {m["memory_ref"] for m in picked if KEY in (m.get("details") or m.get("gist") or "")}
    assert len(key_refs) == 4
    assert set(internal["recalled_by_grade"][:4]) == key_refs
    assert internal["picker"]["asked"] == 2 * internal["picker"]["net"]
    assert internal["picker"]["answered"] == internal["picker"]["net"]
    # The payload stays chronological.
    turns = [m.get("when") for m in picked]
    assert len(turns) == len(picked)
    # Both questions were asked of every row of the net.
    names = {k.split("__")[0] for k in asked[0][1]}
    assert names == {"memory_situation", "memory_useful"}


def test_the_state_is_the_minds_own(_bank, monkeypatch):
    chat_id, char_id = _bank
    asked = []
    monkeypatch.setattr(decisions, "OVERRIDE", _grade_by_key(asked))
    _context(chat_id, char_id, person=PERSON)
    state = asked[0][0]
    assert state.startswith("YOU ARE Mara.")
    assert "WHAT YOU PERCEIVE RIGHT NOW:\nthe harbour at night" in state
    assert "HOW YOU FEEL RIGHT NOW: uneasy" in state
    assert "WHAT YOU ARE TRYING TO DO: find the key" in state
    assert "WHAT DRIVES YOU: to keep the harbour's secrets" in state
    assert "WHAT YOU VALUE: loyalty over comfort" in state
    question = next(iter(asked[0][1].values()))["instructions"]
    assert "MEMORY (" in question and "beats ago" in question


def test_the_authors_preview_pays_for_no_call(_bank, monkeypatch):
    chat_id, char_id = _bank

    def refuse(state, questions):
        raise AssertionError("the preview must not call the decision model")

    monkeypatch.setattr(decisions, "OVERRIDE", refuse)
    ctx = _context(chat_id, char_id)
    assert ctx["recalled_old_memories"]
    assert ctx["_internal"]["picker"]["unasked"].startswith("no mind named")


def test_a_silent_decision_model_leaves_the_nets_order(_bank, monkeypatch):
    chat_id, char_id = _bank

    def down(state, questions):
        raise decisions.DecisionError("unreachable")

    monkeypatch.setattr(decisions, "OVERRIDE", down)
    ctx = _context(chat_id, char_id, person=PERSON)
    assert len(ctx["recalled_old_memories"]) == memory._RECALL_LIMIT
    assert "DecisionError" in ctx["_internal"]["picker"]["unasked"]


def test_the_recent_buffer_is_never_spent_on_recall(_bank, monkeypatch):
    chat_id, char_id = _bank
    monkeypatch.setattr(decisions, "OVERRIDE", _grade_by_key([]))
    ctx = _context(chat_id, char_id, turn=40, person=PERSON)
    recent = {m["memory_ref"] for m in ctx["recent_memories"]}
    recalled = {m["memory_ref"] for m in ctx["recalled_old_memories"]}
    assert recent and not (recent & recalled)


def test_a_reworded_belief_is_kept_once(temp_db, monkeypatch):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("T", "", time.time()))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                         ("Mara", "{}", "{}", time.time()))
    for i in range(3):
        memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.5,
                          f"Mara hid the {KEY} under the loose stone.", turn_idx=i)
    memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.5,
                      "Gulls fought over a fish head on the quay.", turn_idx=5)
    monkeypatch.setattr(decisions, "OVERRIDE", _grade_by_key([]))
    record = {}
    from llm.providers import embed_texts_meta
    embedded = embed_texts_meta(["the harbour"])
    out = memory.jev_memory_packet(chat_id, char_id, "the harbour", current_turn_idx=50,
                                       embedded=embedded, limit=24, person=PERSON,
                                       view="the harbour", record=record)
    texts = [m["content"] for m in out]
    assert texts.count(f"Mara hid the {KEY} under the loose stone.") == 1
    assert record["near_duplicates_dropped"] == 2


def test_the_latest_recall_primes_the_net(_bank):
    chat_id, char_id = _bank
    from core.db import q
    ids = [r["id"] for r in q("SELECT id FROM memories WHERE chat_id=? AND char_id=? "
                              "ORDER BY turn_idx LIMIT 3", (chat_id, char_id))]
    for i, mid in enumerate(ids):
        q("UPDATE memories SET last_accessed_turn=? WHERE id=?", (48 if i < 2 else 30, mid))
    from llm.providers import embed_texts_meta
    _mems, _net, lanes, _v = memory.memory_net(
        chat_id, char_id, "the harbour", current_turn_idx=50,
        embedded=embed_texts_meta(["the harbour"]))
    assert set(lanes["primed"]) == set(ids[:2])


def test_the_affect_pass_reads_the_pick_best_first():
    context = {"recalled_old_memories": [
        {"memory_ref": "old", "details": "the oldest row"},
        {"memory_ref": "mid", "details": "a middling row"},
        {"memory_ref": "best", "details": "the row that bears most"}],
        "_internal": {"recalled_by_grade": ["best", "mid", "old"]}}
    assert [m["ref"] for m in affect_pass.memories_from(context)] == ["best", "mid", "old"]
