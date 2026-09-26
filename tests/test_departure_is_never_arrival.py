"""Where a vehicle sets off from is never where it arrives (the owner's
ruling, 2026-09-25), and under way it is in the space it moves through --
its route room -- or, when nothing has named one, in no room, until the
story brings it in.

Chat 154 turn 4398: with no grammar and no reasoning, fresh drafts still
wrote the beach the TARDIS was leaving as its route (3 of 3 samples of
capture 3979), and once in twelve rerolls as its destination with an ETA of
5 s -- a timed arrival that would have docked it back on the beach -- while
its position stayed on the beach it had left for the whole journey, where
anyone standing there would have seen it.

No room was the floor that ruling allowed, and the three branches of that
departure (chats 154, 156 and 157, the same evening) measured it as a place
to stand rather than a floor: 154 built a room for the space the ship
crossed and held together for the beats after; 157 named none, and the next
beat wrote it docked in no room at all.
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
                  "sky": {"name": "Open Sky", "adjacent": []},
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


def _transit(**fields):
    return {"entities": {"tardis": {"state": {"transit": fields}}}}


def _exits(scene, room="console_room"):
    return [edge.get("to") for edge in scene["rooms"][room].get("adjacent") or []]


def test_under_way_it_stays_in_the_space_it_moves_through():
    """A route room is where the ship IS, and a later beat's transit that does
    not mention it is silence, not a move into nowhere: `state` merges key by
    key (`_merge_entity`), so every write of `transit` replaces it whole, and
    chat 157 turn 4482 wrote `{"phase": "in_transit"}` and nothing else. The
    place it left is carried the same way; naming another space moves it."""
    set_off = merge_scene_with_diff(_world(), _transit(
        phase="in_transit", hatch="closed", route_room="vortex"))
    assert set_off["positions"]["tardis"] == "vortex"
    later = merge_scene_with_diff(set_off, _transit(phase="in_transit"))
    transit = later["entities"]["tardis"]["state"]["transit"]
    assert transit["route_room"] == "vortex" and transit["departed_from"] == "beach"
    assert later["positions"]["tardis"] == "vortex"
    assert _exits(later) == ["vortex"]
    onward = merge_scene_with_diff(later, _transit(phase="in_transit", route_room="sky"))
    assert onward["positions"]["tardis"] == "sky" and _exits(onward) == ["sky"]
    assert onward["entities"]["tardis"]["state"]["transit"]["departed_from"] == "beach"


def test_nothing_arrives_nowhere():
    """Chat 157 turn 4481: under way in no room, the ship was written
    `{"phase": "docked"}` -- the Director's prose had read a ship in flight
    as "a ship that has not landed clean" -- with no position, destination
    or route. Docking cleared `departed_from`, so turn 4482 set it off again
    with nothing remembering the beach, and a later beat could have landed
    it back there. An arrival is AT somewhere; one that names nowhere leaves
    the journey as it was."""
    before = _world({"phase": "in_transit", "hatch": "closed", "departed_from": "beach"})
    del before["positions"]["tardis"]
    del before["stations"]["tardis"]
    merged = copy.deepcopy(before)
    merged["entities"]["tardis"]["state"]["transit"] = {"phase": "docked"}
    assert settle_departures(before, merged)
    assert merged["entities"]["tardis"]["state"]["transit"] == {
        "phase": "in_transit", "departed_from": "beach"}
    assert "tardis" not in merged["positions"]
    assert not settle_departures(before, merged)
    # Through the merge, the door stays shut on nothing, and the beach is
    # still the one place it cannot land.
    landed = merge_scene_with_diff(before, _transit(phase="docked"))
    assert landed["entities"]["tardis"]["state"]["transit"]["phase"] == "in_transit"
    assert _exits(landed) == []
    back = merge_scene_with_diff(landed, _transit(phase="arriving", destination_room="beach"))
    assert "destination_room" not in back["entities"]["tardis"]["state"]["transit"]


def test_docked_in_the_space_it_was_crossing_is_an_arrival_there():
    """Stopping where it is -- a boat dropping anchor at sea, a ship holding
    still in the space it was crossing -- is an arrival, in its route room,
    with its door onto that space."""
    before = _world({"phase": "in_transit", "hatch": "closed",
                     "departed_from": "beach", "route_room": "vortex"})
    before["positions"]["tardis"] = "vortex"
    stopped = merge_scene_with_diff(before, _transit(phase="docked", hatch="open"))
    transit = stopped["entities"]["tardis"]["state"]["transit"]
    assert transit["phase"] == "docked" and "departed_from" not in transit
    assert stopped["positions"]["tardis"] == "vortex"
    [door] = stopped["rooms"]["console_room"]["adjacent"]
    assert door["to"] == "vortex" and door["barrier"] == "open_door"


def test_a_route_the_world_does_not_hold_is_no_door_until_it_is_built():
    """A route naming no room -- words, or a `new:` place nothing has built
    yet -- is not a place: the ship is in no room, and its doorway opens onto
    nothing rather than onto a room that does not exist (the rewrite drew
    `{"to": "the vortex"}` from the console room). The words are kept, so a
    later step or beat that builds the room stands the ship in it."""
    for words in ("new:the time vortex", "time_vortex"):
        away = merge_scene_with_diff(_world(), _transit(
            phase="in_transit", hatch="closed", route_room=words))
        assert "tardis" not in away["positions"]
        assert _exits(away) == []
        assert away["entities"]["tardis"]["state"]["transit"]["route_room"] == words
    built = merge_scene_with_diff(away, {"rooms": {"time_vortex": {
        "name": "The Time Vortex", "adjacent": []}}})
    assert built["positions"]["tardis"] == "time_vortex"
    assert _exits(built) == ["time_vortex"]


def test_a_passage_record_never_holds_a_moving_rooms_door():
    """Chats 156 and 157 (2026-09-25): an edit to the TARDIS's doorway in the
    World Browser minted a passage record for it while it stood on the beach
    (`web/world_routes._ensure_passage`), and `sync_scene_passages` -- which
    runs after the dock rewrite -- minted the beach edge back on every merge.
    In 157 the ship was in no room with a shut door onto the beach; in 156
    its doors led to the sea and the beach at once. The doorway is derived
    from where the ship IS, and a record keyed by two rooms it once joined
    cannot follow it; what the doorway itself is -- its name, what it is made
    of, how wide, where along the wall -- goes with the door."""
    scene = _world()
    pid = "beach|console_room"
    scene["passages"] = {pid: {"rooms": ["console_room", "beach"], "barrier": "open_door",
                               "name": "the police-box doors", "material": "wood",
                               "width": 1}}
    scene["rooms"]["console_room"]["adjacent"][0].update(
        {"passage": pid, "dir": "s", "offset": 0.6})
    scene["rooms"]["beach"]["adjacent"].append(
        {"to": "console_room", "barrier": "open_door", "passage": pid,
         "dir": "n", "offset": 0.6})
    away = merge_scene_with_diff(scene, _transit(
        phase="in_transit", hatch="closed", route_room="vortex"))
    assert not away.get("passages")
    assert _exits(away) == ["vortex"] and "console_room" not in _exits(away, "beach")
    [door] = away["rooms"]["console_room"]["adjacent"]
    assert door["barrier"] == "closed_door" and "passage" not in door
    assert (door["name"], door["material"], door["width"], door["dir"], door["offset"]) \
        == ("the police-box doors", "wood", 1, "s", 0.6)
    # In no room, no doorway at all -- the beach's included.
    nowhere = merge_scene_with_diff(scene, _transit(phase="in_transit", hatch="closed"))
    assert not nowhere.get("passages")
    assert _exits(nowhere) == [] and "console_room" not in _exits(nowhere, "beach")
    # Landing somewhere new, the same door opens there, still itself.
    landed = merge_scene_with_diff(away, {**_transit(phase="docked", hatch="open"),
                                          "positions": {"tardis": "shrine"}})
    [door] = landed["rooms"]["console_room"]["adjacent"]
    assert door["to"] == "shrine" and door["barrier"] == "open_door"
    assert door["name"] == "the police-box doors" and door["offset"] == 0.6
