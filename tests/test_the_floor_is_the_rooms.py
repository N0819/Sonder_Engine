"""What covers a floor wall to wall is the room's floor, never a fixture.

The owner's shrine (chat 168, 2026-10-12): "i think tatami should be a floor
description rather than a fixture". The layout tier's first call was asked
to list every "floor covering" and had nowhere to put one but `fixtures`, so
the tatami of every room was laid as a thing in it and every view read
"Tatami mats within arm's reach". The call now answers each room's `floor`;
the bridge writes it as the plan's `floor` where the plan states none, the
hand furnishing a stub is told it, and the engine's sound reads tatami as
the timber floor it is laid on.
"""
from __future__ import annotations

import copy

from world import layout_bridge as lb

SPECS = {
    "hall": ("the Hall", {
        "purpose": "a hall", "structure": "town", "exposure": "enclosed",
        "adjacent": [{"to": "street", "dir": "s", "barrier": "closed_door"},
                     {"to": "loft", "vertical": "up", "way": "stair"}]}),
    "loft": ("the Loft", {
        "purpose": "a sleeping loft", "structure": "town", "floor": "plank",
        "adjacent": [{"to": "hall", "vertical": "down", "way": "stair"}]}),
    "street": ("the Street", {"purpose": "the street", "structure": "town", "exposure": "open",
                              "adjacent": [{"to": "hall", "dir": "n"}]}),
}
SORT = {"rooms": [
    {"id": "hall", "floor": "  Tatami ", "fixtures": [{"id": "hearth", "name": "the hearth"}]},
    {"id": "loft", "floor": "tatami", "fixtures": [{"id": "bed", "name": "a futon"}]}],
    "stairs": [{"from": "hall", "to": "loft", "enclosed": False}]}
RELATE = {"front": "s", "rooms": [
    {"id": "hall", "purpose": "hall", "fixtures": [{"id": "hearth", "kind": "hearth", "at": "n"}]},
    {"id": "loft", "purpose": "bedroom", "fixtures": [{"id": "bed", "kind": "futon", "at": "e"}]}],
    "stairs": [{"from": "hall", "to": "loft", "from_at": "n", "to_at": "n"}]}


def _scene():
    return {"rooms": {"hall": {"name": "the Hall", "planned": True, "adjacent": []},
                      "street": {"name": "the Street", "desc": "A street.",
                                 "adjacent": [{"to": "hall", "dir": "n"}]}},
            "positions": {}, "entities": {}}


def _solve(sort=SORT):
    (b,) = lb.plan_buildings(copy.deepcopy(SPECS), _scene())
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    spec = lb.spec_from_answers(b, inv, copy.deepcopy(RELATE))
    layout = lb.solve_spec(spec)
    return b, inv, lb.planned_layout(b, spec, layout, inventory=inv)[0]


def test_the_floor_the_first_call_reads_is_the_plans_where_it_states_none():
    _b, inv, solved = _solve()
    held = {r["id"]: r for r in inv["rooms"]}
    assert held["hall"]["floor"] == "tatami"
    assert solved["hall"]["geometry"]["floor"] == "tatami"
    # the plan's own word stands: the loft was planned on planks
    assert "floor" not in solved["loft"]["geometry"]
    # a floor is a word: anything else is none
    _b, inv, solved = _solve(dict(SORT, rooms=[dict(SORT["rooms"][0], floor={"made": "mats"}),
                                               SORT["rooms"][1]]))
    assert "floor" not in {r["id"]: r for r in inv["rooms"]}["hall"]
    assert "floor" not in solved["hall"]["geometry"]


def test_a_tatami_floor_carries_sound_as_the_timber_under_it():
    from world.spatial import floor_edges
    from world.spatial import FLOOR_IMPACT_DB, tread_events

    def house(floor):
        return {"rooms": {"bedroom": {"name": "Bedroom", "level": 1, "over": ["hall"],
                                      "floor": floor, "adjacent": []},
                          "hall": {"name": "Hall", "level": 0, "adjacent": []}},
                "positions": {"Hinami": "bedroom"}, "entities": {}}

    (edge,) = floor_edges(house("tatami"), "hall")
    (timber,) = floor_edges(house("timber"), "hall")
    (wood,) = floor_edges(house("wood"), "hall")
    assert edge["loss_db"] == timber["loss_db"] == wood["loss_db"] == 30.0
    below = [e for e in tread_events(house("tatami"), {"Hinami": "walk"}) if e["room"] == "hall"]
    assert below and below[0]["db"] == FLOOR_IMPACT_DB["timber"]


def test_the_hand_furnishing_a_stub_is_told_its_floor_and_its_windows(temp_db, monkeypatch):
    from world import structure
    spec = {"purpose": "a bedroom", "floor": "tatami",
            "windows": [{"id": "east_window", "dir": "e", "cell": [5, 2],
                         "name": "a window facing the moonrise"}]}
    monkeypatch.setattr(structure, "_planned_specs",
                        lambda cid: {"bedroom": ("the Bedroom", spec)})
    monkeypatch.setattr(structure, "is_planned_stub", lambda scene, rid, specs=None: True)
    scene = {"rooms": {"bedroom": {"name": "the Bedroom", "planned": True}}}
    brief = structure.planned_room_brief(1, scene, ["bedroom"])["bedroom"]
    assert brief["floor"] == "tatami"
    assert brief["windows"] == [{"dir": "e", "name": "a window facing the moonrise"}]
