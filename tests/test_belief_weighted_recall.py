"""Recall follows belief.

An inference memory was minted with the confidence the character declared the
moment they formed it, and nothing ever revisited it. Their mind_models kept
moving underneath -- theory_of_mind.apply_mind_model_updates blends a restated
belief up, partially explains away the competitor it displaces, decays the
unreinforced, and prunes below the floor -- so a character could hold one
belief and preferentially RECALL the one they had already abandoned.

reconcile_inference_confidence projects the reconciled credence back onto the
memories that expressed it; search_memories then ranks on it.
"""

from __future__ import annotations

import json
import time

import pytest

from memory import (
    _ABANDONED_BELIEF_FLOOR,
    reconcile_inference_confidence,
)
from theory_of_mind import apply_mind_model_updates, belief_credence


def _chat_and_char(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("T", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    return chat_id, char_id


def _inference(temp_db, chat_id, char_id, subject, claim, confidence,
               turn_idx=1):
    return temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
        "provenance,salience,content,gist,entities,confidence) "
        "VALUES(?,?,?,'inference','inference','inferred',?,?,?,?,?)",
        (chat_id, char_id, turn_idx, 0.45 + 0.3 * confidence,
         f"About {subject}: {claim}", claim, json.dumps([subject]), confidence))


def _confidence_of(temp_db, mid):
    return temp_db.q("SELECT confidence FROM memories WHERE id=?",
                     (mid,), one=True)["confidence"]


# ---- belief_credence ------------------------------------------------------

def test_credence_reads_the_live_hypothesis():
    state = apply_mind_model_updates(
        {}, [{"about_entity": "Vorne", "claim": "is hiding something",
              "kind": "stated_fact", "confidence": 0.8}], turn_idx=1)
    got = belief_credence(state, "Vorne", "is hiding something", turn_idx=1)
    assert got is not None and got > 0.5


def test_credence_is_none_for_a_claim_no_hypothesis_carries():
    state = apply_mind_model_updates(
        {}, [{"about_entity": "Vorne", "claim": "is hiding something",
              "kind": "stated_fact", "confidence": 0.8}], turn_idx=1)
    assert belief_credence(
        state, "Vorne", "wants to leave the city", turn_idx=1) is None
    # ...and an entity they have no model of at all.
    assert belief_credence(state, "Nobody", "anything", turn_idx=1) is None


def test_credence_decays_with_elapsed_turns():
    state = apply_mind_model_updates(
        {}, [{"about_entity": "Vorne", "claim": "is frightened right now",
              "kind": "emotion", "confidence": 0.8}], turn_idx=1)
    fresh = belief_credence(state, "Vorne", "is frightened right now", 1)
    later = belief_credence(state, "Vorne", "is frightened right now", 40)
    assert later < fresh


# ---- reconciliation -------------------------------------------------------

def test_a_held_belief_takes_its_hypothesis_confidence(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    mid = _inference(temp_db, chat_id, char_id, "Vorne",
                     "is hiding something", 0.30)
    state = apply_mind_model_updates(
        {}, [{"about_entity": "Vorne", "claim": "is hiding something",
              "kind": "stated_fact", "confidence": 0.9}], turn_idx=2)
    assert reconcile_inference_confidence(chat_id, char_id, state, 2) == 1
    assert _confidence_of(temp_db, mid) == pytest.approx(
        belief_credence(state, "Vorne", "is hiding something", 2), abs=1e-3)


def test_an_abandoned_belief_is_pushed_down_but_not_erased(temp_db):
    """A belief explained away is still a belief they once had -- 'I was sure
    of this and I was wrong' has to stay recallable."""
    chat_id, char_id = _chat_and_char(temp_db)
    mid = _inference(temp_db, chat_id, char_id, "Vorne",
                     "intends to betray the crew", 0.85)
    state = apply_mind_model_updates(
        {}, [{"about_entity": "Vorne", "claim": "is protecting his sister",
              "kind": "goal", "confidence": 0.9}], turn_idx=5)
    reconcile_inference_confidence(chat_id, char_id, state, 5)
    revised = _confidence_of(temp_db, mid)
    assert revised < 0.85
    assert revised >= _ABANDONED_BELIEF_FLOOR


def test_abandonment_never_lifts_an_already_low_memory(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    mid = _inference(temp_db, chat_id, char_id, "Vorne", "wears a red coat",
                     0.02)
    reconcile_inference_confidence(chat_id, char_id, {}, 3)
    assert _confidence_of(temp_db, mid) == pytest.approx(0.02, abs=1e-6)


def test_only_inference_rows_are_touched(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    other = temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
        "provenance,salience,content,gist,entities,confidence) "
        "VALUES(?,?,1,'episodic','episode','witnessed',0.5,?,?,?,1.0)",
        (chat_id, char_id, "Vorne crossed the room", "Vorne crossed the room",
         json.dumps(["Vorne"])))
    reconcile_inference_confidence(chat_id, char_id, {}, 3)
    assert _confidence_of(temp_db, other) == pytest.approx(1.0)


def test_reconciliation_is_scoped_to_one_character(temp_db):
    """Another mind's beliefs are not this mind's to revise."""
    chat_id, mara = _chat_and_char(temp_db)
    vorne = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Vorne", "{}", "{}", time.time()))
    theirs = _inference(temp_db, chat_id, vorne, "Mara",
                        "is lying about the letter", 0.9)
    reconcile_inference_confidence(chat_id, mara, {}, 3)
    assert _confidence_of(temp_db, theirs) == pytest.approx(0.9)


def test_reconciliation_never_consults_the_objective_record(temp_db):
    """The firewall property. A character revises from what they later
    PERCEIVED, never from being graded against what was actually true --
    reconciling against truth would collapse belief into truth, which is the
    one distinction this engine exists to keep.

    Enforced structurally: the function's only inputs are a chat/char id and
    that character's own state dict, so there is no channel through which the
    events row, the resolved event, or another mind's state could reach it.
    """
    import inspect
    import memory
    src = inspect.getsource(memory.reconcile_inference_confidence)
    for forbidden in ("resolved_event", "director_", "FROM events",
                      "dialogue_log", "ctx."):
        assert forbidden not in src, forbidden
    params = inspect.signature(memory.reconcile_inference_confidence).parameters
    assert list(params) == [
        "chat_id", "char_id", "state", "turn_idx", "elapsed_seconds"]


# ---- retrieval ------------------------------------------------------------

def test_recall_prefers_the_belief_the_character_still_holds(temp_db):
    """The point of the whole mechanism: two inferences about the same subject
    that a query matches equally, ranked by what the character believes now."""
    from memory import search_memories
    chat_id, char_id = _chat_and_char(temp_db)
    held = _inference(temp_db, chat_id, char_id, "Vorne",
                      "Vorne is protecting his sister", 0.9, turn_idx=1)
    abandoned = _inference(temp_db, chat_id, char_id, "Vorne",
                           "Vorne intends to betray the crew", 0.1, turn_idx=1)
    results = search_memories(chat_id, char_id, "Vorne", k=8,
                              chronological=False)
    order = [m["id"] for m in results]
    assert held in order and abandoned in order
    assert order.index(held) < order.index(abandoned)
    held_row = next(m for m in results if m["id"] == held)
    assert "belief the character still holds" in held_row["retrieval_reasons"]
