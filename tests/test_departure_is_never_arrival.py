"""Where a vehicle sets off from is never where it arrives, and under way it
is in no room until the story brings it in (the owner's ruling,
2026-09-25).

Chat 154 turn 4398: with no grammar and no reasoning, fresh drafts still
wrote the beach the TARDIS was leaving as its route (3 of 3 samples of
capture 3979), and once in twelve rerolls as its destination with an ETA of
5 s -- a timed arrival that would have docked it back on the beach -- while
its position stayed on the beach it had left for the whole journey, where
anyone standing there would have seen it.
"""

from __future__ import annotations

import copy

from world.spatial import merge_scene_with_diff, settle_departures


def _world(transit=None):
    tardis = {"name": "The TARDIS", "kind": "vehicle",
              "interior_rooms": ["console_room"], "state": {}}
    if transit is not None:
        tardis["state"]["transit"] = dict(transit)
    return {
        "rooms": {"beach": {"name": "Moonlit Beach", "adjacent": []},
                  "vortex": {"name": "The Vortex", "adjacent": []},
                  "shrine": {"name": "Shrine Forecourt", "adjacent": []},
                  "console_room": {"name": "Console Room", "parent_entity": "tardis",
                                   "adjacent": [{"to": "beach", "barrier": "open_door"}]}},
        "entities": {"tardis": tardis},
        "positions": {"tardis": "beach", "Hinami": "console_room"},
        "stations": {"tardis": {"at": "tideline", "near": []}},
    }


def _setting_off(before, **transit):
    merged = copy.deepcopy(before)
    merged["entities"]["tardis"]["state"]["transit"] = {"phase": "in_transit",
                                                         "hatch": "closed", **transit}
    return merged


def test_setting_off_the_place_left_is_neither_destination_nor_route():
    before = _world({"phase": "sealed", "hatch": "closed"})
    merged = _setting_off(before, destination_room="beach", eta_seconds=5, route_room="beach")
    assert settle_departures(before, merged)
    transit = merged["entities"]["tardis"]["state"]["transit"]
    # No destination, so no timed arrival carries it back; no route.
    assert transit == {"phase": "in_transit", "hatch": "closed", "departed_from": "beach"}
    # Under way with no route, it is in no room -- and has no station there.
    assert "tardis" not in merged["positions"] and "tardis" not in merged["stations"]
    assert merged["positions"]["Hinami"] == "console_room"
    # Idempotent: a second pass changes nothing.
    assert not settle_departures(before, merged)


def test_a_real_destination_is_kept_and_a_route_is_where_it_is():
    before = _world()
    merged = _setting_off(before, destination_room="shrine", eta_seconds=60,
                          route_room="vortex")
    settle_departures(before, merged)
    transit = merged["entities"]["tardis"]["state"]["transit"]
    assert transit["destination_room"] == "shrine" and transit["eta_seconds"] == 60
    assert merged["positions"]["tardis"] == "vortex"


def test_the_departure_holds_for_the_whole_journey():
    """A later step or beat copying the beach back in is still the place it
    left, and the vehicle already in no room stays there."""
    before = _world()
    first = _setting_off(before)
    settle_departures(before, first)
    later = copy.deepcopy(first)
    later["entities"]["tardis"]["state"]["transit"]["route_room"] = "beach"
    later["entities"]["tardis"]["state"]["transit"]["destination_room"] = "beach"
    settle_departures(first, later)
    transit = later["entities"]["tardis"]["state"]["transit"]
    assert "route_room" not in transit and "destination_room" not in transit
    assert "tardis" not in later["positions"]


def test_the_departure_survives_a_transit_written_again():
    """A beat's diff is merged more than once, and every later beat that
    touches the ship writes its whole `transit` again: replayed live, the
    committed TARDIS was roomless and had lost the place it left, so a later
    beat could have sent it straight back."""
    scene = _world()
    diff = {"entities": {"tardis": {"state": {"transit": {
        "phase": "in_transit", "hatch": "closed"}}}}}
    once = merge_scene_with_diff(scene, diff)
    twice = merge_scene_with_diff(once, diff)
    assert twice["entities"]["tardis"]["state"]["transit"]["departed_from"] == "beach"
    later = merge_scene_with_diff(twice, {"entities": {"tardis": {"state": {"transit": {
        "phase": "in_transit", "hatch": "closed", "destination_room": "beach"}}}}})
    transit = later["entities"]["tardis"]["state"]["transit"]
    assert transit["departed_from"] == "beach" and "destination_room" not in transit


def test_a_sealed_vehicle_has_not_left_and_is_bound_for_nowhere_it_stands():
    before = _world()
    merged = copy.deepcopy(before)
    merged["entities"]["tardis"]["state"]["transit"] = {
        "phase": "sealed", "hatch": "closed", "destination_room": "beach"}
    settle_departures(before, merged)
    assert "destination_room" not in merged["entities"]["tardis"]["state"]["transit"]
    assert merged["positions"]["tardis"] == "beach"


def test_docked_the_journey_is_over_and_a_destination_is_where_it_stands():
    before = _world({"phase": "in_transit", "hatch": "closed", "departed_from": "beach"})
    del before["positions"]["tardis"]
    merged = copy.deepcopy(before)
    merged["entities"]["tardis"]["state"]["transit"] = {
        "phase": "docked", "hatch": "closed", "departed_from": "beach",
        "destination_room": "shrine", "eta_seconds": 30}
    settle_departures(before, merged)
    assert merged["entities"]["tardis"]["state"]["transit"] == {
        "phase": "docked", "hatch": "closed"}
    assert merged["positions"]["tardis"] == "shrine"
    # A position the story wrote itself stands, wherever it is.
    merged = copy.deepcopy(before)
    merged["entities"]["tardis"]["state"]["transit"] = {"phase": "docked", "hatch": "open"}
    merged["positions"]["tardis"] = "beach"
    settle_departures(before, merged)
    assert merged["positions"]["tardis"] == "beach"


def test_the_merge_carries_it_and_the_door_opens_onto_nothing():
    scene = _world()
    diff = {"entities": {"tardis": {"state": {"transit": {
        "phase": "in_transit", "hatch": "closed", "destination_room": "beach",
        "eta_seconds": 5, "route_room": "beach"}}}}}
    merged = merge_scene_with_diff(scene, diff)
    transit = merged["entities"]["tardis"]["state"]["transit"]
    assert transit.get("departed_from") == "beach"
    assert not transit.get("destination_room") and not transit.get("route_room")
    assert "tardis" not in merged["positions"]
    assert not [e for e in merged["rooms"]["console_room"].get("adjacent") or []
                if e.get("to") == "beach"]
    # The world the beat started from is untouched.
    assert scene["positions"]["tardis"] == "beach"
