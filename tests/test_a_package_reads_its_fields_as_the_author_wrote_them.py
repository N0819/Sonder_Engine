"""What a package's fields MEAN, read the way the author wrote them (audit
2026-11-01, agents_narration_planner F2, F3, F9, F14).

* A bare string in a list-valued field is ONE item, never its letters:
  `frontier: "yard"` minted the axes y, a, r, d, `aliases: "Old Tom"` six
  one-letter aliases, and `advance_on: "fire"` four triggers. `_plan_geometry`'s
  `over` had been fixed for exactly this; the class had not.
* A clock whose due is no number validated clean and never fired.
* `due_turns` counted the chat's turn rows, so a live bubble's beats brought a
  player-frame clock due early.
* A ruin that lands at publish was never retired in `room_registry`.
"""
from __future__ import annotations

import json
import time

import pytest

from story.plot_packages import (OPERATION_FIELDS, as_list, draft_operation,
                                 edit_package, fire_due_clocks, get_package,
                                 new_package, normalize_package,
                                 preview_package, publish_package,
                                 validate_package)


def _story(db, *, turns=3):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Fields", "A port at dusk.", time.time()))

    def room(name, *exits):
        return {"name": name, "desc": name + ".",
                "adjacent": [{"to": e, "barrier": "open_door"} for e in exits]}
    db.wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": room("Quay", "warehouse"), "warehouse": room("Warehouse", "quay")},
        "positions": {"Wren": "quay"}, "entities": {}, "attire": {}})
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    ids = [db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, i, "", time.time()))
           for i in range(turns)]
    return cid, ids


def _publish(cid, uid):
    validate_package(cid, uid)
    return publish_package(cid, uid, expected_revision=get_package(cid, uid)["revision"])


# ---------------------------------------------------------------------------
# F3 -- a bare word is one item
# ---------------------------------------------------------------------------

def test_the_one_coercion_reads_a_word_as_one_item_and_noise_as_none():
    assert as_list("yard") == ["yard"]
    assert as_list({"to": "yard"}) == [{"to": "yard"}]
    assert as_list(["a", "b"]) == ["a", "b"]
    assert as_list(("a",)) == ["a"]
    assert as_list(None) == [] and as_list("") == [] and as_list(3) == []
    assert as_list(True) == []


def _single_letters(values):
    return [v for v in values if isinstance(v, str) and len(v) == 1]


#: Every list-valued field the operation table declares (a field whose text
#: opens with `[`), each written the way a model writes one item: a bare
#: string for a list of words, a bare object for a list of objects. The guard
#: below holds this table to the declared one, so a list field added later
#: must be added here, and so is held to the same rule.
LIST_FIELD_CASES = {
    ("plan_creature", "hunts"): (
        {"name": "rat king", "lair": "cellar", "hunts": "cellar"}, "cellar"),
    ("plan_creature", "prey"): (
        {"name": "rat king", "lair": "cellar", "prey": "stock"}, "stock"),
    ("plan_creature", "active_phases"): (
        {"name": "night thing", "lair": "cellar", "active_phases": "night"},
        "night"),
    ("plan_entity", "aliases"): (
        {"name": "Tom Harrow", "aliases": "Old Tom"}, "Old Tom"),
    ("plan_entity", "known_by"): (
        {"name": "Tom Harrow", "known_by": "player"}, "player"),
    ("file_lore", "knowledge_locations"): (
        {"subject_id": "quay", "content": "The quay floods.",
         "knowledge_tag": "common", "knowledge_locations": "quay"}, "quay"),
    ("file_lore", "circles"): (
        {"subject_id": "quay", "content": "The quay floods.",
         "circles": "smugglers"}, "smugglers"),
    ("set_vistas", "vistas"): (
        {"vistas": {"name": "the Grey Fells", "bearing": "n",
                    "distance_km": 30, "height_m": 900}}, None),
    ("presimulate", "charters"): ({"hours": 2, "charters": "hall"}, "hall"),
    ("charter_ops", "ops"): (
        {"charter": "hall", "ops": {"op": "errand", "body": "w1", "to": "quay"}},
        None),
    ("incident", "harms"): (
        {"room": "quay", "summary": "a crate falls",
         "harms": {"charter": "hall", "body": "w1", "outcome": "hurt"}}, None),
    ("director_note", "rooms"): (
        {"text": "The bill is the creditor's.", "rooms": "quay"}, "quay"),
}


def test_the_cases_are_every_declared_list_field():
    declared = {(kind, field.rstrip("?"))
                for kind, fields in OPERATION_FIELDS.items()
                for field, text in fields.items()
                if str(text).lstrip().startswith("[")}
    assert set(LIST_FIELD_CASES) == declared


@pytest.mark.parametrize("kind, field", sorted(LIST_FIELD_CASES))
def test_one_item_written_bare_is_one_item(kind, field):
    from story.plot_packages import OPERATIONS
    op, word = LIST_FIELD_CASES[(kind, field)]
    shaped = OPERATIONS[kind]["shape"](dict(op))
    items = shaped[field]
    assert isinstance(items, list) and len(items) == 1, items
    assert not _single_letters(items), items
    if word is not None:
        assert items == [word]


def test_a_planned_rooms_lists_read_a_bare_item_as_one():
    """`frontier: "yard"` minted the axes y, a, r, d, and `"the quay road"`
    was refused because one of its letters, 'e', is a direction -- a refusal
    naming a letter the model never wrote."""
    from story.plot_packages import OPERATIONS
    shaped = OPERATIONS["plan_rooms"]["shape"]({
        "structure": {"key": "harbour"}, "rooms": {"shed": {
            "name": "Shed", "frontier": "the quay road",
            "adjacent": {"to": "quay"}, "over": "cellar"}}})
    shed = shaped["rooms"]["shed"]
    assert shed["frontier"] == ["the quay road"]
    assert shed["adjacent"] == [{"to": "quay"}]
    assert shed["over"] == ["cellar"]


def test_a_region_events_lists_read_a_bare_word_as_one_item():
    from world.region_events import normalize_region_event
    event = normalize_region_event({
        "label": "a fire", "footprint": {"rooms": "quay", "structures": "harbour"},
        "effects": {"artifacts": "charred timbers"}})
    assert event["footprint"]["rooms"] == ["quay"]
    assert event["footprint"]["structures"] == ["harbour"]
    assert event["effects"]["artifacts"] == ["charred timbers"]


def test_a_clock_waiting_on_one_event_kind_written_bare_waits_on_that_kind():
    pkg = normalize_package({"uid": "plot:x", "title": "x", "clocks": [
        {"id": "clock_f", "label": "fire", "advance_on": "fire"}]})
    assert pkg["clocks"][0]["advance_on"] == [{"event_kind": "fire"}]


# ---------------------------------------------------------------------------
# F9 -- a due that is no number says so
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("due", [{"due_turns": "three"},
                                 {"due_story_hours": "at dawn"},
                                 {"due_turns": -2},
                                 {"due_story_hours": float("nan")}])
def test_a_clock_whose_due_is_no_number_does_not_validate(temp_db, due):
    cid, _ = _story(temp_db)
    pkg = new_package(cid, title="Never", premise="p")
    edit_package(cid, pkg["uid"], {"clocks": [dict(
        {"id": "clock_n", "label": "never"}, **due)]})
    draft_operation(cid, pkg["uid"], {
        "op": "scheduled_consequence", "clock": "clock_n", "summary": "bells"})
    errors = preview_package(cid, pkg["uid"])["errors"]
    assert any("clock_n" in e and "number" in e for e in errors), errors


def test_an_authored_clock_cannot_carry_the_engines_own_marks(temp_db):
    """`fired_turn: 0` on a draft clock made a clock that never fires, and
    `filled: N` one that fires at once."""
    cid, _ = _story(temp_db)
    pkg = new_package(cid, title="Marks", premise="p")
    edit_package(cid, pkg["uid"], {"clocks": [
        {"id": "clock_m", "label": "m", "due_turns": 1, "fired_turn": 0,
         "refused_turn": 1, "fired_elapsed": 9.0, "ticked_turn_idx": 4,
         "advance_on": ["fire"], "segments": 3, "filled": 3}]})
    clock = get_package(cid, pkg["uid"])["clocks"][0]
    for mark in ("fired_turn", "refused_turn", "fired_elapsed", "ticked_turn_idx"):
        assert mark not in clock, clock
    assert clock["filled"] == 0 and clock["segments"] == 3


def test_a_published_clock_whose_due_is_no_number_is_refused_on_the_record(temp_db):
    """A clock stored before the validation existed: it can never fire, and
    it says so once instead of asking the same question every beat."""
    cid, turn_ids = _story(temp_db)
    pkg = new_package(cid, title="Old", premise="p")
    edit_package(cid, pkg["uid"], {"clocks": [
        {"id": "clock_o", "label": "old", "due_turns": 1}]})
    draft_operation(cid, pkg["uid"], {
        "op": "scheduled_consequence", "clock": "clock_o", "summary": "bells"})
    _publish(cid, pkg["uid"])
    from story import plot_packages as pp
    stored = pp.packages(cid)
    stored[pkg["uid"]]["clocks"][0]["due_turns"] = "three"
    pp.save_packages(cid, stored)
    out = fire_due_clocks(cid, 5, turn_id=turn_ids[-1])
    assert out["fired"] == []
    clock = get_package(cid, pkg["uid"])["clocks"][0]
    assert clock["refused_turn"] == 5
    history = get_package(cid, pkg["uid"])["provenance"]["history"]
    assert any(h["action"] == "clock_refused" and "number" in h["note"]
               for h in history)
    fire_due_clocks(cid, 6, turn_id=turn_ids[-1])
    assert sum(1 for h in get_package(cid, pkg["uid"])["provenance"]["history"]
               if h["action"] == "clock_refused") == 1


# ---------------------------------------------------------------------------
# F14 -- a clock counts its own frame's beats
# ---------------------------------------------------------------------------

def test_a_bubbles_beats_do_not_bring_a_player_clock_due(temp_db):
    cid, turn_ids = _story(temp_db)
    pkg = new_package(cid, title="Three beats", premise="p")
    edit_package(cid, pkg["uid"], {"clocks": [
        {"id": "clock_3", "label": "three", "due_turns": 3}]})
    draft_operation(cid, pkg["uid"], {
        "op": "scheduled_consequence", "clock": "clock_3", "summary": "bells"})
    out = _publish(cid, pkg["uid"])
    published = out["published_turn"]
    bubble = temp_db.qi("INSERT INTO frames(chat_id,label,created) VALUES(?,?,?)",
                        (cid, "away", time.time()))
    for i in range(1, 5):
        temp_db.qi("INSERT INTO turns(chat_id,idx,frame_id,player_input,created) "
                   "VALUES(?,?,?,?,?)", (cid, published + i, bubble, "", time.time()))
    player_beat = published + 5
    temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
               (cid, player_beat, "", time.time()))
    assert fire_due_clocks(cid, player_beat)["fired"] == []
    for later in (player_beat + 1, player_beat + 2):
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                   "VALUES(?,?,?,?)", (cid, later, "", time.time()))
    assert fire_due_clocks(cid, player_beat + 1)["fired"] == []
    assert fire_due_clocks(cid, player_beat + 2)["fired"] == [
        (pkg["uid"], "clock_3")]


# ---------------------------------------------------------------------------
# F2 -- a ruin that lands at publish is retired
# ---------------------------------------------------------------------------

def test_a_ruin_published_at_once_retires_the_room(temp_db):
    cid, turn_ids = _story(temp_db)
    temp_db.qi("INSERT INTO room_registry(chat_id,room_uid,name) VALUES(?,?,?)",
               (cid, "warehouse", "Warehouse"))
    pkg = new_package(cid, title="The quake", premise="p",
                      authority={"may_schedule_harm": True})
    draft_operation(cid, pkg["uid"], {
        "op": "region_event", "label": "the quake",
        "footprint": {"rooms": ["warehouse"]},
        "profile": {"mode": "at_once", "intensity": 1.0},
        "effects": {"destroy": True, "harm": {"outcome": "hurt", "fraction": 0.0}}})
    _publish(cid, pkg["uid"])
    row = temp_db.q("SELECT retired_turn_id FROM room_registry WHERE chat_id=? "
                    "AND room_uid='warehouse'", (cid,), one=True)
    assert row["retired_turn_id"] == turn_ids[-1]
    stated = json.loads(temp_db.q(
        "SELECT payload FROM world_conditions WHERE chat_id=? AND "
        "subject_id='warehouse' AND active=1", (cid,), one=True)["payload"])
    assert stated["state"] == "ruined"
