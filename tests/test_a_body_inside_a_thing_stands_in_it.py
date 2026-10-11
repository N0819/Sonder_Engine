"""A BODY INSIDE A THING STANDS IN THE THING, AND GOES WHERE IT GOES.

The Cwm Du run's ride (O26), replayed after its fix wave (chat 167 turn 4629,
2026-10-10). The decision model now brought the inside rule, and the encoder
still minted the shaft cage with `interior_rooms: []` and no position at all,
posed the player "inside" against the landing the cage hung at, and set the
cage off up the shaft with nobody in it.

A thing big enough to be inside is a room (`encoder/entities__inside`), and
the only producer of that room was the encoder remembering to author it.
For a body's own inside the engine already derives the room from the ledger
(`materialize_enclosure_interiors`), and stopped at gate 3 for things because
a thing's minted inside took an open doorway -- an occupant the ledger hid
became visible from the room outside. This is that gate's other half: the
inside is minted SHUT, through the thing's own enclosure, and only the
thing's own hatch opens it. The owner's ruling (2026-10-11): build the
interior in code, with one encoder instruction naming the thing.
"""

from __future__ import annotations

import copy

from world.spatial import merge_scene_with_diff, sighted_level

PEOPLE = ("Nell Hartley", "Ffion Rees", "Onsetter")


def _pit():
    return {"location": "Cwm Du", "time": "night", "attire": {}, "overlays": {},
            "rooms": {"pit_bottom": {"name": "Pit Bottom", "desc": "", "adjacent": []},
                      "pithead_yard": {"name": "Pithead Yard", "desc": "", "adjacent": []}},
            "positions": {name: "pit_bottom" for name in PEOPLE},
            "entities": {name: {"name": name, "kind": "person"} for name in PEOPLE}}


def _board(cage_state=None, riders=("Nell Hartley", "Ffion Rees"), **cage):
    """The replay's shape: a cage minted with no place and no inside."""
    record = {"name": "shaft cage", "kind": "vehicle", "container": True,
              "interior_rooms": [], **cage}
    if cage_state is not None:
        record["state"] = cage_state
    return merge_scene_with_diff(_pit(), {
        "entities": {"pit_cage": record},
        "containment": {who: {"in": "pit_cage", "mode": "inside"} for who in riders}})


def _inside(scene):
    return [rid for rid, room in scene["rooms"].items()
            if isinstance(room, dict) and room.get("parent_entity") == "pit_cage"]


class TestTheRiderStandsInside:
    def test_a_thing_with_no_inside_and_no_place_gets_both(self):
        scene = _board({"hatch": "open"})
        assert scene["positions"]["pit_cage"] == "pit_bottom"     # where she got in
        assert _inside(scene) == ["pit_cage_interior"]
        assert scene["entities"]["pit_cage"]["interior_rooms"] == ["pit_cage_interior"]
        assert scene["positions"]["Nell Hartley"] == "pit_cage_interior"
        assert scene["positions"]["Ffion Rees"] == "pit_cage_interior"
        # one truth: the room form, not the ledger, says where she is
        assert scene.get("contained") in ({}, None)

    def test_the_two_inside_see_and_hear_each_other(self):
        scene = _board()
        assert sighted_level(scene, "Nell Hartley", "Ffion Rees") == "full"

    def test_she_goes_where_it_goes(self):
        scene = _board({"hatch": "open"})
        under_way = merge_scene_with_diff(copy.deepcopy(scene), {"entities": {"pit_cage": {
            "state": {"hatch": "open", "transit": {"phase": "in_transit",
                                                   "destination_room": "pithead_yard"}}}}})
        assert under_way["positions"]["Nell Hartley"] == "pit_cage_interior"
        arrived = merge_scene_with_diff(copy.deepcopy(under_way), {
            "entities": {"pit_cage": {"state": {"transit": {"phase": "docked"}}}},
            "positions": {"pit_cage": "pithead_yard"}})
        assert arrived["positions"]["Nell Hartley"] == "pit_cage_interior"
        assert [e["to"] for e in arrived["rooms"]["pit_cage_interior"]["adjacent"]] \
            == ["pithead_yard"]


class TestTheWayInIsShutUnlessTheThingOpensIt:
    def _barrier(self, scene):
        return [e["barrier"] for e in scene["rooms"]["pit_cage_interior"]["adjacent"]]

    def test_an_open_hatch_shows_its_riders(self):
        scene = _board({"hatch": "open"})
        assert self._barrier(scene) == ["open_door"]
        assert sighted_level(scene, "Onsetter", "Nell Hartley") == "full"

    def test_a_hatch_nobody_mentioned_stays_shut(self):
        """The non-body enclosure default gate 3 was waiting on: before it, a
        thing's minted inside took an open doorway from the dock rewrite."""
        scene = _board()
        assert self._barrier(scene) == ["closed_door"]
        assert sighted_level(scene, "Onsetter", "Nell Hartley") == "none"

    def test_the_things_own_enclosure_shapes_the_shut_way_in(self):
        scene = _board(enclosure="barred")
        assert self._barrier(scene) == ["bars"]


class TestWhatStaysTheLedgers:
    def test_a_thing_carried_inside_another_is_no_room(self):
        scene = merge_scene_with_diff(_pit(), {
            "entities": {"jar": {"name": "stone jar", "kind": "container"},
                         "coin": {"name": "copper coin", "kind": "object"}},
            "positions": {"jar": "pit_bottom"},
            "containment": {"coin": {"in": "jar", "mode": "inside"}}})
        assert not [r for r, v in scene["rooms"].items()
                    if isinstance(v, dict) and v.get("parent_entity") == "jar"]
        assert scene["contained"]["coin"]["in"] == "jar"

    def test_inside_a_body_is_the_bodys_own_inside_as_before(self):
        """`inside` a BODY was already canonicalised to that body's interior
        (`canonical_enclosure_mode`, against the holder) and minted by the body
        branch -- dark, its way in the body's own. The thing branch never
        takes it."""
        scene = _pit()
        scene["attire"] = {"Ffion Rees": {}}
        merged = merge_scene_with_diff(scene, {"containment": {
            "Nell Hartley": {"in": "Ffion Rees", "mode": "inside"}}})
        inside = merged["positions"]["Nell Hartley"]
        assert merged["rooms"][inside]["parent_entity"] == "Ffion Rees"
        assert merged["rooms"][inside]["light"] == "dark"


def test_the_stored_lift_shape_follows_its_doorway(tmp_path):
    """Chat 160's freight elevator, the one stored scene of this shape: the
    occupant positioned in the car's interior AND contained `inside` the car.
    The record is the redundant half now; the car's own hatch decides who
    sees in, and she stays in the car."""
    scene = _pit()
    scene["entities"]["freight_elevator"] = {"name": "Freight Elevator", "kind": "vehicle",
                                             "state": {"hatch": "open"}}
    scene["positions"]["freight_elevator"] = "pit_bottom"
    scene["rooms"]["elevator_car"] = {"name": "Elevator Car", "desc": "",
                                      "parent_entity": "freight_elevator",
                                      "adjacent": [{"to": "pit_bottom", "barrier": "open_door"}]}
    scene["positions"]["Nell Hartley"] = "elevator_car"
    scene["contained"] = {"Nell Hartley": {"in": "freight_elevator", "mode": "inside"}}
    merged = merge_scene_with_diff(scene, {})
    assert merged["positions"]["Nell Hartley"] == "elevator_car"
    assert merged.get("contained") in ({}, None)
    assert sighted_level(merged, "Onsetter", "Nell Hartley") == "full"


def test_the_cards_name_the_thing_in_both_packs():
    from pathlib import Path
    for language in ("en", "ja"):
        card = Path(f"language_packs/{language}/cards/system_prompts/encoder/"
                    "entities__inside.txt").read_text(encoding="utf-8")
        assert "`inside`" in card and "containment" in card, language
        assert "interior_rooms" in card, language       # authoring it stays allowed


# ---- the encoder's own spelling of getting in: a pose ----------------------

CAGE = {"pit_cage": {"name": "shaft cage", "kind": "vehicle", "state": {"hatch": "open"}}}


def _posed(relative_to, support=None):
    return {"Nell Hartley": {"posture": "standing", "support": support or relative_to,
                             "relative_to": relative_to, "relation": "inside",
                             "constraint": "", "detail": "standing in the cage"}}


class TestAPoseNamingTheThingPutsHerInIt:
    """The 4629 replays posed her `inside` twice, once with the inside rule
    and its containment channel in hand. Where the pose names the thing, that
    is containment, canonicalised against the holder (`contain_posed_inside`)."""

    def test_a_pose_inside_the_thing_this_beat_stands_her_in_it(self):
        scene = merge_scene_with_diff(_pit(), {"entities": CAGE,
                                               "poses": _posed("pit_cage")})
        assert scene["positions"]["Nell Hartley"] == "pit_cage_interior"
        assert scene["positions"]["pit_cage"] == "pit_bottom"

    def test_a_pose_against_an_anchor_or_a_body_is_an_arrangement(self):
        # against an anchor, with no placeless thing minted this beat to be
        # inside (the cage stands where it was put): an arrangement
        scene = merge_scene_with_diff(_pit(), {"entities": CAGE,
                                               "positions": {"pit_cage": "pit_bottom"},
                                               "poses": _posed("cage_landing")})
        assert scene["positions"]["Nell Hartley"] == "pit_bottom"
        scene = merge_scene_with_diff(_pit(), {"poses": _posed("Ffion Rees")})
        assert scene["positions"]["Nell Hartley"] == "pit_bottom"
        assert not (scene.get("contained") or {}).get("Nell Hartley")

    def test_a_standing_pose_never_pulls_her_back_in(self):
        """A pose outlives the moment it described: read every merge, it would
        drag a body that has stepped out back into the thing."""
        aboard = merge_scene_with_diff(_pit(), {"entities": CAGE,
                                                "poses": _posed("pit_cage")})
        out = merge_scene_with_diff(copy.deepcopy(aboard),
                                    {"positions": {"Nell Hartley": "pit_bottom"}})
        assert out["positions"]["Nell Hartley"] == "pit_bottom"
        again = merge_scene_with_diff(copy.deepcopy(out), {})
        assert again["positions"]["Nell Hartley"] == "pit_bottom"


def test_the_poses_card_says_a_body_inside_is_containment_in_both_packs():
    from pathlib import Path
    for language in ("en", "ja"):
        card = Path(f"language_packs/{language}/cards/system_prompts/encoder/"
                    "poses.txt").read_text(encoding="utf-8")
        assert card.count("containment") >= 2, language


class TestTheBeatsOwnSpellingOfGettingIn:
    """Replayed twice with the inside rule in hand, the encoder posed her
    `inside` against the LANDING and, in the same event, minted the cage with
    no place. That pair is the encoder's own spelling of getting in."""

    def _board(self, entities, pose_against="cage_landing"):
        pit = _pit()
        pit["rooms"]["pit_bottom"]["anchors"] = {"cage_landing": {}}
        return merge_scene_with_diff(pit, {
            "entities": entities,
            "poses": {"Nell Hartley": {"posture": "standing", "support": pose_against,
                                       "relative_to": pose_against, "relation": "inside",
                                       "constraint": "", "detail": "standing inside the cage"}}})

    def test_posed_inside_as_the_beat_mints_one_placeless_thing(self):
        scene = self._board({"cage": {"name": "shaft cage", "kind": "vehicle",
                                      "container": True, "state": {"hatch": "open"}}})
        assert scene["positions"]["Nell Hartley"] == "cage_interior"
        assert scene["positions"]["cage"] == "pit_bottom"
        risen = merge_scene_with_diff(copy.deepcopy(scene), {"positions": {"cage": "pithead_yard"}})
        assert risen["positions"]["Nell Hartley"] == "cage_interior"
        assert [e["to"] for e in risen["rooms"]["cage_interior"]["adjacent"]] == ["pithead_yard"]

    def test_two_placeless_things_are_a_guess_and_no_answer(self):
        scene = self._board({
            "cage": {"name": "shaft cage", "kind": "vehicle", "container": True},
            "tub": {"name": "coal tub", "kind": "container", "container": True}})
        assert scene["positions"]["Nell Hartley"] == "pit_bottom"

    def test_a_placed_thing_or_a_thing_no_one_gets_into_is_no_answer(self):
        placed = self._board({"cage": {"name": "shaft cage", "kind": "vehicle"}})
        placed2 = merge_scene_with_diff(_pit(), {
            "entities": {"cage": {"name": "shaft cage", "kind": "vehicle"}},
            "positions": {"cage": "pithead_yard"},
            "poses": {"Nell Hartley": {"relation": "inside", "relative_to": "cage_landing",
                                       "support": "cage_landing"}}})
        assert placed2["positions"]["Nell Hartley"] == "pit_bottom"
        coin = self._board({"coin": {"name": "copper coin", "kind": "object"}})
        assert coin["positions"]["Nell Hartley"] == "pit_bottom"
        assert placed["positions"]["Nell Hartley"] == "cage_interior"   # control
