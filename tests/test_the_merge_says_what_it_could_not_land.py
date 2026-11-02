"""What the scene merge refuses, or cannot land, it says -- to the Director,
through the report the commit already routes (`crossing_report`).

Audit world_spatial_truth (2026-11-01): nothing in `merge_scene_with_diff`
wrote to any channel for these, so a beat's write vanished with no word:

* F19 (CONFIRMED SILENT-NOOP): the two edge shields build the refusal sentence
  ("kept the passage ... open: it was sealed from one side only") and their
  only live caller passed no list to receive it; the bearing shield had no
  list at all.
* F20 (CONFIRMED): `positions: {Ann: "attic"}` with no attic was accepted and
  Ann stood nowhere -- `separated / far` from everyone.
* F11 (CONFIRMED): `remove_rooms` on a room anything stands in was refused
  silently, and a successful one left every doorway into the vanished room
  (`spatial_rel(hall, cellar)` still `open_door / near`).
"""

from world.spatial import merge_scene_with_diff, spatial_rel


def _scene():
    return {
        "rooms": {
            "hall": {"name": "Hall", "adjacent": [
                {"to": "cellar", "barrier": "open_door", "dir": "n"},
                {"to": "yard", "barrier": "open_door", "dir": "e"}]},
            "cellar": {"name": "Cellar", "adjacent": [
                {"to": "hall", "barrier": "open_door", "dir": "s"}]},
            "yard": {"name": "Yard", "adjacent": [
                {"to": "hall", "barrier": "open_door", "dir": "w"}]},
        },
        "positions": {"Ann": "hall", "Bo": "hall"},
        "entities": {}, "attire": {"Ann": {}, "Bo": {}},
        "contained": {}, "contacts": [],
    }


def test_a_one_sided_seal_is_refused_and_said():
    report = []
    merged = merge_scene_with_diff(
        _scene(), {"rooms": {"cellar": {"adjacent": [
            {"to": "hall", "barrier": "wall"}]}}}, crossing_report=report)
    edge = [e for e in merged["rooms"]["cellar"]["adjacent"] if e["to"] == "hall"][0]
    assert edge["barrier"] == "open_door"
    assert any("one side only" in note for note in report)


def test_a_one_sided_rebearing_is_refused_and_said():
    report = []
    merged = merge_scene_with_diff(
        _scene(), {"rooms": {"hall": {"adjacent": [
            {"to": "cellar", "barrier": "open_door", "dir": "w"}]}}},
        crossing_report=report)
    edge = [e for e in merged["rooms"]["hall"]["adjacent"] if e["to"] == "cellar"][0]
    assert edge["dir"] == "n"
    assert any("cellar" in note and "bearing" in note for note in report)


def test_a_position_in_a_room_the_world_does_not_hold_is_said():
    report = []
    merged = merge_scene_with_diff(_scene(), {"positions": {"Ann": "attic"}},
                                   crossing_report=report)
    assert any("Ann" in note and "attic" in note for note in report)
    # Reported, not repaired: the Director decides what was meant.
    assert merged["positions"]["Ann"] == "attic"


def test_a_room_minted_in_the_same_beat_is_no_complaint():
    report = []
    merge_scene_with_diff(_scene(), {
        "rooms": {"attic": {"name": "Attic", "adjacent": [
            {"to": "hall", "barrier": "open_door"}]}},
        "positions": {"Ann": "attic"}}, crossing_report=report)
    assert not any("attic" in note for note in report)


def test_removing_a_room_takes_every_doorway_into_it():
    merged = merge_scene_with_diff(_scene(), {"remove_rooms": ["cellar"]})
    assert "cellar" not in merged["rooms"]
    assert all(e.get("to") != "cellar"
               for room in merged["rooms"].values()
               for e in room.get("adjacent") or [])
    assert spatial_rel(merged, "hall", "cellar")["barrier"] != "open_door"


def test_removing_an_occupied_room_is_refused_and_said():
    sc = _scene()
    sc["positions"]["crate"] = "cellar"
    sc["entities"]["crate"] = {"name": "crate", "kind": "object"}
    report = []
    merged = merge_scene_with_diff(sc, {"remove_rooms": ["cellar"]},
                                   crossing_report=report)
    assert "cellar" in merged["rooms"]
    assert any("cellar" in note for note in report)
