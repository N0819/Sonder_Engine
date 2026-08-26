"""A goal the world has invalidated must be closable by the world.

Live bug (chat 88, char 72, intention i6): formed turn 46, reading "Begin oral
route mouth play -- taste ... before progressing to swallowing". The station it
names was left behind at turn 54; the committed contact ledger reads
target_interior "mouth" for turns 49-53, "throat" at 54, "esophagus" 55-58 and
"stomach" 59-67. Thirteen turns after the precondition ended, i6 was still
`status: "active"` and every want that character generated carried
`serves: "i6"`. The engine DETECTED it four separate times -- commit warnings
on turns 54, 55, 58 and 64, "progress claimed on a beat that repeated an
earlier move" -- and nothing acted on any of them, because `_advance_intent`
stalls only AT the ceiling and i6 sat at progress 0.6. The one op that closes a
goal the world has sealed, `nonviable`, can only be emitted by the character,
who cannot see the contradiction: its perception says one station, its
intention says another, and nothing compared the two. At turn 64 the model
tried to repair itself by restating the intent text on a `progress` op; renames
on progress are ignored, so the stored text never changed and no warning said
so.

Corpus survey (engine.db read-only, all 329 intentions in the live corpus's 75
state rows, replaying the real floor against every committed scene): the rule
closes exactly two, and both are this intention -- chat 88 i6 at turn 55 and
its sibling branch chat 89 i6 at turn 55, each one beat after that branch's
occupant left the named station, and each still `active` at that chat's last
beat. It is silent on the same intention text in branch chats 86/87, which
ended while the named station was still live; on i3's two-barren-then-satisfied
arc; and on the two authored standing intentions idle for the whole 67-turn
run.

The story nouns of the live case are evidence, never the rule: everything below
is written in the engine's vocabulary -- a standing interior relation, the
station it stands at, and an aim that names one the world has left.
"""

from __future__ import annotations

import re

import pytest

from mind.affect import (WORLD_DRIFT_SETTLE, apply_intent_ops,
                         settle_intent_world_anchors, steering_intent_ids)
from persist.commit import _intent_names_term, _interior_relations_of

AIM = ("draw Nix slowly through the antechamber, savoring the crossing, "
       "before the descent")


def _names(text, term):
    """The affect-level tests' own matcher: word boundary plus possessive guard."""
    text = str(text or "").casefold()
    term = str(term or "").strip().casefold()
    if not text or not term:
        return False
    for m in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text):
        if re.search(r"(?:\b(?:her|his|their|your|my|its)\s+|['’]s\s+)$",
                     text[:m.start()]):
            continue
        return True
    return False


def _aim(**over):
    row = {"id": "i6", "intent": AIM, "status": "active", "formed_turn": 0,
           "last_progress_turn": 0, "progress": 0.6}
    row.update(over)
    return [row]


def _view(station, other="Nix", source="ledger"):
    return [{"other": other, "station": station, "source": source}]


def _always_ok(op):
    return True


# ---- the class ------------------------------------------------------------

def test_the_world_closes_an_intention_whose_station_it_left_behind():
    intents, warns = settle_intent_world_anchors(
        _aim(), _view("antechamber"), 1, _names)
    assert intents[0]["status"] == "active"
    assert intents[0]["world_anchor"]["station"] == "antechamber"
    assert not warns

    intents, warns = settle_intent_world_anchors(
        intents, _view("gallery"), 2, _names)
    assert intents[0]["status"] == "active"
    assert intents[0]["world_drift"] == 1
    assert not warns

    intents, warns = settle_intent_world_anchors(
        intents, _view("gallery"), 3, _names)
    row = intents[0]
    assert row["status"] == "blocked"
    assert row["blocked_turn"] == 3
    assert row["last_progress_turn"] == 3
    assert "antechamber" in row["blocked_why"] and "gallery" in row["blocked_why"]
    assert row["world_closed"]["turn"] == 3
    assert len([w for w in warns if "closed by the world" in w]) == 1


def test_the_closing_beat_steers_at_full_weight_then_stops():
    intents, _ = settle_intent_world_anchors(_aim(), _view("antechamber"), 1, _names)
    intents, _ = settle_intent_world_anchors(intents, _view("gallery"), 2, _names)
    intents, _ = settle_intent_world_anchors(intents, _view("gallery"), 3, _names)
    assert "i6" in steering_intent_ids(intents, 3)
    assert "i6" not in steering_intent_ids(intents, 4)


def test_a_slow_intention_at_its_bound_station_never_closes():
    intents = _aim()
    for turn in range(1, 31):
        intents, warns = settle_intent_world_anchors(
            intents, _view("antechamber"), turn, _names)
        assert not warns
    assert intents[0]["status"] == "active"
    assert "world_drift" not in intents[0]


def test_absence_of_the_relation_is_not_evidence():
    intents, _ = settle_intent_world_anchors(_aim(), _view("antechamber"), 1, _names)
    intents, _ = settle_intent_world_anchors(intents, _view("gallery"), 2, _names)
    assert intents[0]["world_drift"] == 1

    intents, warns = settle_intent_world_anchors(intents, [], 3, _names)
    assert "world_drift" not in intents[0]
    assert intents[0]["status"] == "active"
    assert not warns

    intents, _ = settle_intent_world_anchors(intents, _view("gallery"), 4, _names)
    assert intents[0]["status"] == "active"
    intents, warns = settle_intent_world_anchors(intents, _view("gallery"), 5, _names)
    assert intents[0]["status"] == "blocked"
    assert any("closed by the world" in w for w in warns)


def test_an_intention_naming_the_current_station_rebinds_instead_of_closing():
    both = _aim(intent="carry Nix through the antechamber and on into the gallery")
    intents, _ = settle_intent_world_anchors(both, _view("antechamber"), 1, _names)
    assert intents[0]["world_anchor"]["station"] == "antechamber"
    for turn in (2, 3, 4):
        intents, warns = settle_intent_world_anchors(
            intents, _view("gallery"), turn, _names)
        assert not warns
    assert intents[0]["status"] == "active"
    assert intents[0]["world_anchor"]["station"] == "gallery"
    assert "world_drift" not in intents[0]


def test_a_grind_past_the_closure_buys_no_progress():
    intents, _ = settle_intent_world_anchors(
        _aim(progress=0.4), _view("antechamber"), 1, _names)
    intents, _ = settle_intent_world_anchors(intents, _view("gallery"), 2, _names)
    intents, _ = settle_intent_world_anchors(intents, _view("gallery"), 3, _names)
    assert intents[0]["status"] == "blocked"
    assert intents[0]["world_closed"]["progress"] == pytest.approx(0.4)

    intents, _ = apply_intent_ops(intents, [{"op": "progress", "id": "i6"}],
                                  4, _always_ok)
    assert intents[0]["status"] == "active"
    assert intents[0]["progress"] == pytest.approx(0.6)

    intents, warns = settle_intent_world_anchors(
        intents, _view("gallery"), 5, _names)
    assert intents[0]["status"] == "blocked"
    assert intents[0]["progress"] == pytest.approx(0.4)
    assert intents[0]["last_progress_turn"] == 4
    assert any("re-closed by the world" in w for w in warns)
    assert not any("settled beat" in w for w in warns)


def test_a_returned_world_reopens_the_bookkeeping():
    intents, _ = settle_intent_world_anchors(_aim(), _view("antechamber"), 1, _names)
    intents, _ = settle_intent_world_anchors(intents, _view("gallery"), 2, _names)
    intents, _ = settle_intent_world_anchors(intents, _view("gallery"), 3, _names)
    assert intents[0]["status"] == "blocked"

    intents, _ = apply_intent_ops(intents, [{"op": "progress", "id": "i6"}],
                                  4, _always_ok)
    intents, warns = settle_intent_world_anchors(
        intents, _view("antechamber"), 5, _names)
    assert intents[0]["status"] == "active"
    assert "world_drift" not in intents[0]
    assert "world_closed" not in intents[0]
    assert not warns


def test_closed_rows_and_junk_pass_through_untouched():
    rows = [{"id": "i1", "intent": AIM, "status": "satisfied", "progress": 1.0},
            {"id": "i2", "intent": AIM, "status": "dormant", "progress": 0.4},
            {"id": "i3", "intent": AIM, "status": "blocked", "progress": 0.2},
            "not a dict"]
    out, warns = settle_intent_world_anchors(rows, _view("gallery"), 9, _names)
    assert out == rows
    assert not warns


def test_a_never_anchored_intention_is_out_of_reach():
    """Lexical binding fails toward silence: an aim naming neither the party
    nor the station never anchors, and keeps exactly today's behaviour."""
    rows = [{"id": "i9", "intent": "keep going", "status": "active",
             "progress": 0.5}]
    for turn in range(1, 10):
        rows, warns = settle_intent_world_anchors(
            rows, _view("gallery"), turn, _names)
        assert not warns
    assert rows[0]["status"] == "active"
    assert "world_anchor" not in rows[0]


# ---- representation change is not world movement --------------------------

def test_a_representation_change_rebinds_rather_than_drifting():
    """The chat-88-shaped anchor, met by the same place under a new name.

    `world_anchor` persists in chat_chars.state, so a chat carrying an anchor
    bound to a free-text ledger station will, the beat after its interior is
    materialized as rooms, see a room DISPLAY NAME in the same slot.
    settle_intent_world_anchors is handed two strings and cannot recover WHY
    one of them changed -- so the provenance is stamped on the anchor, and a
    changed source discards the binding instead of drifting against a stale
    one. The goal stays open, which is the one error direction this floor
    refuses to get wrong.
    """
    intents, _ = settle_intent_world_anchors(
        _aim(), _view("antechamber", source="ledger"), 1, _names)
    assert intents[0]["world_anchor"]["source"] == "ledger"
    intents, _ = settle_intent_world_anchors(
        intents, _view("gallery", source="ledger"), 2, _names)
    assert intents[0]["world_drift"] == 1

    # the interior materializes as rooms: same standing relation, new vocabulary
    for turn in (3, 4, 5):
        intents, warns = settle_intent_world_anchors(
            intents, _view("Grand Gallery", source="room"), turn, _names)
        assert not warns
    assert intents[0]["status"] == "active"
    assert "world_drift" not in intents[0]
    assert "world_anchor" not in intents[0]


def test_the_floor_rebuilds_its_anchor_in_the_new_vocabulary():
    aim = _aim(intent="draw Nix slowly through the Grand Gallery, then deeper")
    intents, _ = settle_intent_world_anchors(
        aim, _view("antechamber", source="ledger"), 1, _names)
    assert "world_anchor" not in intents[0]
    intents, _ = settle_intent_world_anchors(
        intents, _view("Grand Gallery", source="room"), 2, _names)
    assert intents[0]["world_anchor"] == {"other": "Nix",
                                          "station": "Grand Gallery",
                                          "source": "room", "turn": 2}
    intents, _ = settle_intent_world_anchors(
        intents, _view("Deep Cistern", source="room"), 3, _names)
    intents, warns = settle_intent_world_anchors(
        intents, _view("Deep Cistern", source="room"), 4, _names)
    assert intents[0]["status"] == "blocked"
    assert any("closed by the world" in w for w in warns)


# ---- the caller's two halves ---------------------------------------------

def test_only_the_container_side_is_in_reach():
    scene = {"contacts": [
        {"relation": "interior", "actor": "Nix", "target": "Vessel Warden",
         "target_interior": "hold"},
        {"relation": "surface", "actor": "Nix", "target": "Vessel Warden",
         "target_interior": "hull"},
        {"relation": "interior", "actor": "Nix", "target": "Vessel Warden",
         "target_interior": ""},
    ]}
    assert _interior_relations_of(scene, "Vessel Warden") == [
        {"other": "Nix", "station": "hold", "source": "ledger"}]
    # the contained body may legitimately strive against the passage
    assert _interior_relations_of(scene, "Nix") == []
    assert _interior_relations_of({}, "Vessel Warden") == []
    assert _interior_relations_of(scene, "") == []


def test_a_station_that_is_a_room_of_this_container_is_stamped_room():
    scene = {
        "rooms": {"hold_a": {"name": "Cargo Hold",
                             "parent_entity": "Vessel Warden"},
                  "dock": {"name": "Dock"}},
        "contacts": [{"relation": "interior", "actor": "Nix",
                      "target": "Vessel Warden",
                      "target_interior": "Cargo Hold"}],
    }
    assert _interior_relations_of(scene, "Vessel Warden") == [
        {"other": "Nix", "station": "Cargo Hold", "source": "room"}]
    scene["rooms"]["hold_a"]["parent_entity"] = "Someone Else"
    assert _interior_relations_of(scene, "Vessel Warden")[0]["source"] == "ledger"


def test_the_matcher_refuses_a_possessed_station_and_matches_kana():
    assert _intent_names_term("begin the approach through the antechamber",
                              "antechamber")
    assert not _intent_names_term("kiss her antechamber", "antechamber")
    assert not _intent_names_term("kiss Nix's antechamber", "antechamber")
    assert not _intent_names_term("kiss Nix’s antechamber", "antechamber")
    # a party recorded under a display name, called by given name in the aim
    assert _intent_names_term("walk Mira out of the hold", "Mira Vashenko")
    # a word boundary cannot see the end of a kana name; name_boundary_pattern can
    assert _intent_names_term("ヒナミに近づく",
                              "ヒナミ")
    assert not _intent_names_term("", "antechamber")
    assert not _intent_names_term("begin the approach", "")


# ---- restated text on a moving op -----------------------------------------

def test_restated_text_on_a_progress_op_warns_and_is_not_applied():
    rows = _aim()
    out, warns = apply_intent_ops(
        rows, [{"op": "progress", "id": "i6",
                "intent": "continue the descent, past the antechamber"}],
        7, _always_ok)
    assert out[0]["intent"] == AIM
    assert any("restated text" in w for w in warns)


def test_an_unchanged_text_on_a_progress_op_says_nothing():
    rows = _aim()
    out, warns = apply_intent_ops(
        rows, [{"op": "progress", "id": "i6", "intent": AIM}], 7, _always_ok)
    assert not any("restated text" in w for w in warns)
    assert out[0]["progress"] == pytest.approx(0.8)


# ---- the floor is actually wired, in the right order ----------------------

def test_the_commit_calls_the_floor_between_the_ops_and_the_steering():
    """A floor nothing calls is the defect it was written to close.

    The precedent is `test_project_tier_reachable`'s reader test: the source
    survives the module split, so pin the source. Order is the substance here
    -- AFTER `apply_intent_ops`, so the floor has the last word over a
    grind-revival; BEFORE `steering_intent_ids` and the project boundary
    review, so the collapse steers its own beat once and the task-closed
    review invites the successor on the beat the goal actually closed.
    """
    import inspect

    from persist import commit

    src = inspect.getsource(commit.prepare_memory_commit)
    ops = src.index("affect.apply_intent_ops(")
    floor = src.index("affect.settle_intent_world_anchors(")
    steering = src.index("affect.steering_intent_ids(")
    boundary = src.index("affect.project_boundary(")
    assert ops < floor < steering < boundary
    assert "_interior_relations_of(sc, cname)" in src
    assert "_intent_names_term" in src
