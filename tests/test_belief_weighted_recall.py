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

from mind.memory import (
    _ABANDONED_BELIEF_DECAY,
    _ABANDONED_BELIEF_FLOOR,
    _abandoned_confidence,
    reconcile_inference_confidence,
)
from mind.theory_of_mind import apply_mind_model_updates, belief_credence


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
    from mind import memory
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
    from mind.memory import search_memories
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


# ---- abandonment is one-shot, not compounding -----------------------------
#
# mind_models is a small working set (per-entity capacity, per-kind half-life
# decay, pruning at the floor) while the memory bank is an archive, so in any
# long chat most inference rows eventually have no stored hypothesis without
# the character ever concluding they were wrong. Measured live 2026-07-29:
# under a compounding x0.55-per-turn demotion, 76-80% of the whole inference
# bank in the two active chats reached the floor within 7-18 played turns, and
# late-turn top-8 retrieval returned 0-1 inference memories vs 13-15 at mint
# confidence. These tests pin the repaired semantics.


def test_abandonment_is_idempotent_across_repeated_passes(temp_db):
    """Reconciling the same abandoned row on five consecutive turns lands on
    the same number every time -- never a per-turn compounding decay."""
    chat_id, char_id = _chat_and_char(temp_db)
    mid = _inference(temp_db, chat_id, char_id, "Vorne",
                     "intends to betray the crew", 0.70)
    expected = _abandoned_confidence(0.45 + 0.3 * 0.70)
    assert expected == pytest.approx(0.70 * _ABANDONED_BELIEF_DECAY, abs=1e-6)
    assert reconcile_inference_confidence(chat_id, char_id, {}, 5) == 1
    first = _confidence_of(temp_db, mid)
    for turn in range(6, 10):
        reconcile_inference_confidence(chat_id, char_id, {}, turn)
    assert _confidence_of(temp_db, mid) == pytest.approx(first, abs=1e-6)
    assert first == pytest.approx(expected, abs=1e-3)
    assert first > _ABANDONED_BELIEF_FLOOR


def test_a_crushed_row_self_heals_on_the_next_pass(temp_db):
    """Rows previously compounded to the floor recover to the one-shot resting
    place from their (untouched) salience -- no migration required."""
    chat_id, char_id = _chat_and_char(temp_db)
    mid = _inference(temp_db, chat_id, char_id, "Vorne",
                     "intends to betray the crew", 0.70)
    temp_db.qi("UPDATE memories SET confidence=? WHERE id=?",
               (_ABANDONED_BELIEF_FLOOR, mid))
    reconcile_inference_confidence(chat_id, char_id, {}, 9)
    assert _confidence_of(temp_db, mid) == pytest.approx(
        0.70 * _ABANDONED_BELIEF_DECAY, abs=1e-3)


def test_a_held_belief_never_ranks_below_an_abandoned_one(temp_db):
    """Held >= abandoned, always -- including when the surviving hypothesis
    has half-life-decayed to near nothing. Staleness is not disbelief."""
    chat_id, char_id = _chat_and_char(temp_db)
    held = _inference(temp_db, chat_id, char_id, "Vorne",
                      "is frightened of the dark", 0.70, turn_idx=1)
    abandoned = _inference(temp_db, chat_id, char_id, "Vorne",
                           "intends to betray the crew", 0.70, turn_idx=1)
    # An emotion hypothesis formed at turn 1, reconciled at turn 60: its live
    # credence has decayed far below the abandoned resting place.
    state = apply_mind_model_updates(
        {}, [{"about_entity": "Vorne", "claim": "is frightened of the dark",
              "kind": "emotion", "confidence": 0.8}], turn_idx=1)
    live = belief_credence(state, "Vorne", "is frightened of the dark", 60)
    assert live is not None and live < _abandoned_confidence(0.45 + 0.3 * 0.70)
    reconcile_inference_confidence(chat_id, char_id, state, 60)
    held_conf = _confidence_of(temp_db, held)
    abandoned_conf = _confidence_of(temp_db, abandoned)
    assert held_conf >= abandoned_conf
    assert abandoned_conf == pytest.approx(0.70 * _ABANDONED_BELIEF_DECAY,
                                           abs=1e-3)


def test_a_genuinely_explained_away_belief_is_still_demoted(temp_db):
    """The fix must not disable the feature: a claim displaced by a live rival
    still rests well below its mint confidence, below the rival's credence."""
    chat_id, char_id = _chat_and_char(temp_db)
    mid = _inference(temp_db, chat_id, char_id, "Vorne",
                     "intends to betray the crew", 0.85)
    rival = _inference(temp_db, chat_id, char_id, "Vorne",
                       "is protecting his sister", 0.85)
    state = apply_mind_model_updates(
        {}, [{"about_entity": "Vorne", "claim": "is protecting his sister",
              "kind": "goal", "confidence": 0.9}], turn_idx=5)
    reconcile_inference_confidence(chat_id, char_id, state, 5)
    demoted = _confidence_of(temp_db, mid)
    assert demoted < 0.85
    assert demoted >= _ABANDONED_BELIEF_FLOOR
    assert demoted < _confidence_of(temp_db, rival)


def test_an_abandoned_inference_stays_retrievable_at_k8(temp_db):
    """The property the corpus actually lost: an inference no hypothesis
    carries any more, when it is the memory that best answers the query,
    must still surface in a k=8 recall against a bank of unrelated
    higher-confidence witnessed rows. At the compounding floor it did not."""
    from mind.memory import add_memory, search_memories
    chat_id, char_id = _chat_and_char(temp_db)
    fillers = [
        "The kettle boiled over on the old stove",
        "Rain drummed the tin roof through the night",
        "A grey cat slept on the warm windowsill",
        "The market stalls closed early before the storm",
        "Lantern oil ran low in the back cupboard",
        "The ferry horn sounded twice across the bay",
        "Fresh bread cooled on the long wooden counter",
        "A loose shutter banged against the north wall",
        "The well rope frayed near the iron ring",
        "Snow settled on the orchard past the fence",
    ]
    for i, text in enumerate(fillers):
        add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.7,
                   text, turn_idx=i + 1, confidence=1.0)
    mint = 0.7
    target = add_memory(
        chat_id, char_id, None, "inference", "inferred",
        0.45 + 0.3 * mint,
        "About the stranger: the limping courier is smuggling letters "
        "for the garrison captain",
        turn_idx=2, confidence=mint, category="inference")
    reconcile_inference_confidence(chat_id, char_id, {}, 20)
    assert _confidence_of(temp_db, target) == pytest.approx(
        mint * _ABANDONED_BELIEF_DECAY, abs=1e-3)
    results = search_memories(
        chat_id, char_id,
        "why would the limping courier be smuggling letters",
        k=8, current_turn_idx=20, chronological=False)
    assert target in [m["id"] for m in results]
