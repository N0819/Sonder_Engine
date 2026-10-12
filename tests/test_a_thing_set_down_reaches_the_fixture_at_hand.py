"""A thing set down at a fixture reaches it; a hand-off to nothing keeps it.

Saltmarsh Crossing (2026-10-11, chat 170 turn idx 8): the encoder wrote
`{"op": "transfer", "object_id": "office_letter", "from_id": "Agnes Holloway",
"to_id": "desk"}`. The harbour office she stood in keeps a fixture whose id is
exactly `desk`, and `resolve_placement_target` never looked at a room's
fixtures, so the op was refused and the letter stayed where the opening had
minted it -- loose on the far bank -- while every page had it on the desk.

Two rules, and their limits:

- a destination naming a fixture of the room the hand-off happens in resolves
  to that room, AT that fixture. Only that room: three rooms of that story
  keep a `desk`, and the one set down at is the one at hand;
- a destination naming nothing keeps the thing with the body the op says it
  left -- a loose thing goes into that hand, a thing the body already has
  stays as it has it, a thing someone else holds stays with them -- and the
  Director is told, where before it was told the thing "stayed where it was"
  and a loose thing never moved again.
"""
from __future__ import annotations

import copy

from world.spatial import derive_inventory_placements, resolve_placement_target


def _scene(**over):
    """A harbour office with a desk, a grain office with another, and a clerk
    standing in the first with a letter lying at her feet."""
    scene = {
        "rooms": {
            "harbour_office": {"name": "Harbour office", "adjacent": ["quay"],
                               "anchors": {"desk": {"desc": "a slant-topped desk"},
                                           "Chart Table": {"desc": "charts"}}},
            "grain_office": {"name": "Grain office", "adjacent": ["quay"],
                             "anchors": {"desk": {"desc": "a counting-house desk"},
                                         "tally_desk": {"desc": "chalked tallies"}}},
            "quay": {"name": "Quay", "adjacent": ["harbour_office", "grain_office"]},
        },
        "positions": {"Agnes Holloway": "harbour_office",
                      "Bethan Marsh": "harbour_office",
                      "office_letter": "harbour_office"},
        "entities": {
            "agnes": {"name": "Agnes Holloway", "kind": "person", "aliases": []},
            "bethan": {"name": "Bethan Marsh", "kind": "person", "aliases": []},
            "office_letter": {"name": "office letter", "kind": "letter",
                              "portable": True},
        },
        "attire": {"Agnes Holloway": {"torso": [{"item": "wool coat"}]},
                   "Bethan Marsh": {"torso": [{"item": "oilskin"}]}},
        "scales": {}, "contained": {}, "stations": {},
    }
    scene.update(over)
    return scene


def _set_down(scene, to_id, from_id="Agnes Holloway"):
    report = []
    derive_inventory_placements(scene, [{
        "op": "transfer", "object_id": "office_letter", "from_id": from_id,
        "to_id": to_id}], report=report)
    return report


class TestAFixtureOfTheRoomAtHand:
    def test_the_saltmarsh_letter_lands_on_the_harbour_office_desk(self):
        scene = _scene(contained={"office_letter": {"in": "agnes", "mode": "held"}})
        report = _set_down(scene, "desk")
        assert scene["positions"]["office_letter"] == "harbour_office"
        assert scene["stations"]["office_letter"]["at"] == "desk"
        assert "office_letter" not in scene["contained"], "set down, not carried"
        assert report == [], report

    def test_the_desk_reached_is_the_one_in_her_room(self):
        """The same id in the grain office is not the desk she stands at."""
        scene = _scene(positions={"Agnes Holloway": "grain_office",
                                  "Bethan Marsh": "harbour_office",
                                  "office_letter": "grain_office"})
        _set_down(scene, "desk")
        assert scene["positions"]["office_letter"] == "grain_office"
        assert scene["stations"]["office_letter"]["at"] == "desk"

    def test_a_fixture_is_named_by_its_id_in_any_case_or_spacing(self):
        scene = _scene()
        _set_down(scene, "chart table")
        assert scene["stations"]["office_letter"]["at"] == "Chart Table"

    def test_a_fixture_of_another_room_is_out_of_reach(self):
        """`tally_desk` is the grain office's; from the harbour office it
        names nothing, and the letter stays in her hand."""
        scene = _scene()
        assert resolve_placement_target(scene, "tally_desk",
                                        here="harbour_office") == (None, None)
        report = _set_down(scene, "tally_desk")
        assert scene["contained"]["office_letter"] == {"in": "agnes", "mode": "held"}
        assert "office_letter" not in scene["stations"]
        assert any("stays with 'Agnes Holloway'" in note for note in report), report

    def test_without_a_room_at_hand_no_fixture_is_searched(self):
        assert resolve_placement_target(_scene(), "desk") == (None, None)

    def test_a_room_a_body_and_a_thing_still_come_first(self):
        """A fixture is the last reading: nothing that resolved before reads
        differently now."""
        scene = _scene()
        scene["rooms"]["harbour_office"]["anchors"]["quay"] = {"desc": "a painted quay"}
        assert resolve_placement_target(scene, "quay", here="harbour_office") == (
            "room", "quay")
        scene["rooms"]["harbour_office"]["anchors"]["Bethan Marsh"] = {"desc": "her stool"}
        assert resolve_placement_target(scene, "Bethan Marsh", here="harbour_office") == (
            "carrier", "bethan")
        scene["entities"]["desk"] = {"name": "desk", "kind": "furniture"}
        scene["positions"]["desk"] = "quay"
        assert resolve_placement_target(scene, "desk", here="harbour_office") == (
            "anchor", "desk")

    def test_a_station_the_beat_declares_is_kept(self):
        """A station written this beat for the thing outranks the fixture its
        transfer named, as it outranks every other derived one."""
        scene = _scene()
        derive_inventory_placements(scene, [{
            "op": "transfer", "object_id": "office_letter",
            "from_id": "Agnes Holloway", "to_id": "desk"}],
            stations={"office_letter": {"at": "Chart Table"}}, report=[])
        assert scene["positions"]["office_letter"] == "harbour_office"
        assert scene.get("stations", {}).get("office_letter", {}).get("at") != "desk"


class TestAHandOffToNothingKeepsTheThingWithItsHolder:
    def test_a_loose_thing_goes_into_the_hand_the_op_names(self):
        scene = _scene()
        report = _set_down(scene, "the pigeonholes")
        assert scene["contained"]["office_letter"] == {"in": "agnes", "mode": "held"}
        (note,) = report
        assert "'the pigeonholes' names no room, no body, no fixture" in note
        assert "stays with 'Agnes Holloway'" in note

    def test_a_thing_she_already_has_stays_as_she_has_it(self):
        """Pocketed stays pocketed: the floor never invents the act of taking
        it out, and a garment it leaves worn is attire's to take off."""
        scene = _scene(contained={"office_letter": {"in": "agnes", "mode": "pocket"}})
        report = _set_down(scene, "the pigeonholes")
        assert scene["contained"]["office_letter"] == {"in": "agnes", "mode": "pocket"}
        assert "stays with 'Agnes Holloway'" in report[0]

    def test_a_thing_another_body_holds_stays_with_them(self):
        scene = _scene(contained={"office_letter": {"in": "bethan", "mode": "held"}})
        before = copy.deepcopy(scene)
        report = _set_down(scene, "the pigeonholes")
        assert scene["contained"] == before["contained"]
        assert "stayed where it was" in report[0]

    def test_a_hand_off_from_no_body_moves_nothing(self):
        """From a room, or from nobody: there is no hand to keep it in."""
        for giver in ("harbour_office", "", "the night clerk"):
            scene = _scene()
            before = copy.deepcopy(scene)
            report = _set_down(scene, "the pigeonholes", from_id=giver)
            assert scene["contained"] == before["contained"], giver
            assert scene["positions"] == before["positions"], giver
            if giver:
                assert "stayed where it was" in report[0], giver
