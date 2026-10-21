"""Something under way toward a destination arrives when its way is done,
whether or not anyone wrote down a time.

The control probe story (2026-10-21, chat 2, idx 4-9): the boatman cast off
from the lighthouse landing in the Mary Ann, bound for the mainland through
the channel. The resolve's encoder wrote `{in_transit, destination_room:
the_mainland, route_room: the_channel}` and no `eta_seconds` -- the transit
card names the field and never asks for it, and no stored journey with a
destination has carried one since the prose encoder -- and the timed arrival
(`world.mechanics`, pass (b)) scheduled on a written eta and nothing else. So
nothing was scheduled, and the boat sat in the channel from idx 5 to idx 9:
77.7 story hours on a crossing the room author measured at thirteen
kilometres, in a `{value, unit}` record no reader parsed.

The scene below is that beat's shape: the channel's two edges as the room
author wrote them, the planned stub of the mainland (which also hangs a door
with no distance off the landing behind the boat), the boat's own inside, and
the clocks of the departure beat (1993 s) and the next one, "That evening"
(13581 s).
"""

from __future__ import annotations

import copy
import json

import pytest

from world.mechanics import PRICED_ARRIVAL_KEY, mechanics_sweep
from world.spatial import (edge_metres, merge_scene_with_diff,
                           normalize_edge_distance, room_span, spatial_rel)

DEPARTURE_BEAT_END = 1993.0      # chat 2 idx 4's clock at commit
THAT_EVENING = 13581.0           # idx 5's clock at commit

UNDER_WAY = {"phase": "in_transit", "destination_room": "the_mainland",
             "route_room": "the_channel", "departed_from": "rock_landing"}


def _crossing(transit=None):
    return {
        "rooms": {
            "rock_landing": {
                "name": "The Landing", "exposure": "open",
                "extent": {"w": 12, "d": 8},
                "adjacent": [
                    {"to": "the_stair", "barrier": "open", "vertical": "up",
                     "way": "ladder", "dir": "n"},
                    # The planned stub's frontier door: no distance said.
                    {"to": "the_mainland", "barrier": "open_door",
                     "axis": "the mainland"}]},
            "the_stair": {"name": "The Steps",
                          "adjacent": [{"to": "rock_landing", "barrier": "open"}]},
            "the_channel": {
                "name": "the channel", "size": "large", "floor": "water",
                "exposure": "open", "extent": {"w": 10.0, "d": 7.0},
                "adjacent": [
                    {"to": "rock_landing", "barrier": "open", "dir": "w",
                     "distance": {"value": 1.5, "unit": "km"}},
                    {"to": "the_mainland", "barrier": "open", "dir": "e",
                     "distance": {"value": 13, "unit": "km"}},
                    {"to": "skerry", "barrier": "open", "dir": "s",
                     "distance": "3 km"}]},
            "skerry": {"name": "The Skerry", "exposure": "open",
                       "adjacent": [{"to": "the_channel", "barrier": "open"}]},
            "the_mainland": {
                "name": "The Mainland", "planned": True, "purpose": "",
                "adjacent": [{"to": "rock_landing", "barrier": "open_door"}]},
            "mary_ann_interior": {
                "name": "The Mary Ann", "parent_entity": "mary_ann",
                "dock_exit": True,
                "adjacent": [{"to": "the_channel", "distance": "near",
                              "barrier": "closed_door"}]},
        },
        "entities": {"mary_ann": {
            "name": "The Mary Ann", "kind": "vehicle", "container": True,
            "interior_rooms": ["mary_ann_interior"],
            "state": {"engine": "running",
                      "transit": dict(transit if transit is not None else UNDER_WAY)}}},
        "positions": {"mary_ann": "the_channel",
                      "Tam the deckhand": "mary_ann_interior"},
    }


def _sweep(scene, elapsed, pending=(), turn_id=11, turn_idx=4):
    return mechanics_sweep(scene, {"elapsed_seconds": elapsed}, None,
                           list(pending), chat_id=2, turn_id=turn_id,
                           turn_idx=turn_idx)


def _scheduled(ops):
    return [op[1] for op in ops if op[0] == "schedule"]


def _statuses(ops):
    return {op[1]: op[2] for op in ops if op[0] == "status"}


def _transit(scene):
    return scene["entities"]["mary_ann"]["state"]["transit"]


# ---------------------------------------------------------------------------
# The probe's crossing arrives at its priced time
# ---------------------------------------------------------------------------

def test_the_crossing_is_timed_by_the_way_the_world_measured():
    scene = _crossing()
    _, ops, _, counts = _sweep(scene, DEPARTURE_BEAT_END)

    rows = _scheduled(ops)
    assert len(rows) == 1 and counts["fired"] == 0
    row = rows[0]
    assert row["kind"] == "transit_arrival" and row["location_id"] == "the_channel"
    payload = json.loads(row["payload"])
    assert payload["entity_id"] == "mary_ann"
    assert payload["destination_room"] == "the_mainland"
    # The channel's own thirteen kilometres to the mainland, plus the span of
    # the channel it is crossing, at the charter's walking pace -- never the
    # door the mainland's stub hangs off the landing the boat has left.
    from world.charter_move import WALK_PACES_PER_SECOND
    way = 13000.0 + room_span(scene, "the_channel")
    assert row["due_at"] == pytest.approx(DEPARTURE_BEAT_END + way / WALK_PACES_PER_SECOND)
    assert payload[PRICED_ARRIVAL_KEY] == pytest.approx(way / WALK_PACES_PER_SECOND, abs=0.1)
    assert 2.5 * 3600 < row["due_at"] - DEPARTURE_BEAT_END < 3.0 * 3600


def test_the_crossing_comes_in_on_the_beat_its_way_is_done():
    scene = _crossing()
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    row = _scheduled(ops)[0]

    # Not before its time, and not timed twice.
    _, ops, _, counts = _sweep(scene, 5000.0, [row], turn_id=12, turn_idx=5)
    assert counts["fired"] == 0 and not _scheduled(ops)
    assert scene["positions"]["mary_ann"] == "the_channel"

    # "That evening": the clock is past the crossing, and she has come in.
    _, ops, notices, counts = _sweep(scene, THAT_EVENING, [row], turn_id=12,
                                     turn_idx=5)
    assert counts["fired"] == 1 and _statuses(ops) == {row["event_id"]: "fired"}
    assert scene["positions"]["mary_ann"] == "the_mainland"
    transit = _transit(scene)
    assert transit["phase"] == "docked"
    assert "destination_room" not in transit and "departed_from" not in transit
    # Whoever is in her rooms came with her, and her door opens on the quay.
    assert scene["positions"]["Tam the deckhand"] == "mary_ann_interior"
    assert spatial_rel(scene, "mary_ann_interior", "the_mainland")["barrier"] \
        != "separated"
    assert spatial_rel(scene, "mary_ann_interior", "the_channel")["barrier"] \
        == "separated"
    assert notices and "the_mainland" in notices[0]


# ---------------------------------------------------------------------------
# A written eta wins
# ---------------------------------------------------------------------------

def test_a_written_eta_stands_over_the_price():
    scene = _crossing(dict(UNDER_WAY, eta_seconds=1800))
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    rows = _scheduled(ops)
    assert len(rows) == 1
    assert rows[0]["due_at"] == DEPARTURE_BEAT_END + 1800
    # A written time's row is the shape it always was.
    assert json.loads(rows[0]["payload"]) == {
        "entity_id": "mary_ann", "destination_room": "the_mainland",
        "frame_id": None}


def test_a_time_written_after_the_price_replaces_it_once():
    scene = _crossing()
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    priced = _scheduled(ops)[0]

    # Next beat the prose says half an hour more, and the encoder writes it.
    _transit(scene)["eta_seconds"] = 1800
    _, ops, _, _ = _sweep(scene, 3000.0, [priced], turn_id=12, turn_idx=5)
    assert _statuses(ops) == {priced["event_id"]: "cancelled"}
    written = _scheduled(ops)
    assert len(written) == 1 and written[0]["due_at"] == 4800.0
    assert PRICED_ARRIVAL_KEY not in json.loads(written[0]["payload"])

    # Restated the beat after, the written time does not slip.
    _, ops, _, _ = _sweep(scene, 3300.0, [written[0]], turn_id=13, turn_idx=6)
    assert not _scheduled(ops) and not _statuses(ops)


# ---------------------------------------------------------------------------
# A place the world does not hold
# ---------------------------------------------------------------------------

def test_a_journey_to_a_place_the_world_does_not_hold_comes_in_off_the_map():
    from agents.mapping import _transit_destination_needs
    from world.charter_move import WALK_EDGE_PACES, WALK_PACES_PER_SECOND

    bound = dict(UNDER_WAY, destination_room="harrow_street")
    scene = _crossing(bound)
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    row = _scheduled(ops)[0]
    # No edge reaches a place the world does not hold: one way that covers
    # ground nobody measured, `far`, from the channel it is crossing.
    way = room_span(scene, "the_channel") + WALK_EDGE_PACES["far"]
    assert row["due_at"] == pytest.approx(DEPARTURE_BEAT_END + way / WALK_PACES_PER_SECOND)

    _, ops, notices, counts = _sweep(scene, row["due_at"], [row], turn_id=12,
                                     turn_idx=5)
    assert counts["fired"] == 1
    # Off the map at the place's name: in no room, docked AT it.
    assert "mary_ann" not in scene["positions"]
    transit = _transit(scene)
    assert transit["phase"] == "docked"
    assert transit["destination_room"] == "harrow_street"
    assert "route_room" not in transit and "departed_from" not in transit
    # Its doorway opens onto nothing -- not the water it finished crossing --
    # and whoever is in its rooms is with it.
    assert not [e for e in scene["rooms"]["mary_ann_interior"]["adjacent"]
                if e.get("to") == "the_channel"]
    assert scene["positions"]["Tam the deckhand"] == "mary_ann_interior"
    assert notices and "harrow_street" in notices[0] and "off the map" in notices[0]
    # It is not timed again...
    _, ops, _, _ = _sweep(scene, row["due_at"] + 600.0, turn_id=13, turn_idx=6)
    assert not _scheduled(ops)
    # ...the place is asked for...
    needs = _transit_destination_needs(scene, lambda spelling: None,
                                       turn_idx=6, frame_id=None)
    assert [(n["reason"], n["subject"]) for n in needs] == [
        ("transit_destination_unplanned", "harrow_street")]

    # ...and the beat the place is built, it stands there.
    built = merge_scene_with_diff(copy.deepcopy(scene), {"rooms": {
        "harrow_street": {"name": "Harrow Street", "desc": "A wet street.",
                          "adjacent": []}}})
    assert built["positions"]["mary_ann"] == "harrow_street"
    assert spatial_rel(built, "mary_ann_interior", "harrow_street")["barrier"] \
        != "separated"


# ---------------------------------------------------------------------------
# A journey already at its end is not timed again
# ---------------------------------------------------------------------------

def test_a_vessel_already_where_it_is_bound_is_not_timed():
    """Chat 153 idx 26 (the owner's database): the TARDIS written `arriving`
    at the moonlit beach while it already stood there. Its way is done; the
    prose docks it."""
    scene = {
        "rooms": {"moonlit_beach": {"name": "Moonlit Beach", "adjacent": []},
                  "tardis_console_room": {
                      "name": "Console Room", "parent_entity": "tardis",
                      "adjacent": [{"to": "moonlit_beach", "barrier": "closed_door"}]}},
        "entities": {"tardis": {
            "name": "The TARDIS", "kind": "object",
            "interior_rooms": ["tardis_console_room"],
            "state": {"transit": {"phase": "arriving", "hatch": "closed",
                                  "destination_room": "moonlit_beach"}}}},
        "positions": {"tardis": "moonlit_beach",
                      "The Doctor": "tardis_console_room"},
    }
    _, ops, _, counts = _sweep(scene, 967.0)
    assert not _scheduled(ops) and counts["fired"] == 0


def test_an_arrived_vessel_is_not_timed_again():
    scene = _crossing()
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    row = _scheduled(ops)[0]
    _sweep(scene, THAT_EVENING, [row], turn_id=12, turn_idx=5)
    assert _transit(scene)["phase"] == "docked"
    _, ops, _, _ = _sweep(scene, THAT_EVENING + 3600.0, turn_id=13, turn_idx=6)
    assert not _scheduled(ops) and not _statuses(ops)


def test_only_a_journey_under_way_toward_a_place_is_priced():
    """Sealed and not yet away, it has not begun one; bound for nowhere (the
    TARDIS's own shape, chats 154-161), there is no way to price -- it stays
    under way until the prose brings it in, as the transit card says."""
    for transit in ({"phase": "sealed", "destination_room": "the_mainland"},
                    {"phase": "in_transit", "route_room": "the_channel",
                     "departed_from": "rock_landing"}):
        _, ops, _, _ = _sweep(_crossing(transit), DEPARTURE_BEAT_END)
        assert not _scheduled(ops), transit


# ---------------------------------------------------------------------------
# A journey that turns for another place
# ---------------------------------------------------------------------------

def test_a_vessel_that_turns_for_another_place_is_timed_for_that_one():
    scene = _crossing()
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    first = _scheduled(ops)[0]

    _transit(scene)["destination_room"] = "skerry"
    _, ops, _, _ = _sweep(scene, 3000.0, [first], turn_id=12, turn_idx=5)
    assert _statuses(ops) == {first["event_id"]: "cancelled"}
    turned = _scheduled(ops)
    assert len(turned) == 1
    assert json.loads(turned[0]["payload"])["destination_room"] == "skerry"


def test_an_arrival_that_falls_due_for_an_end_given_up_does_not_land():
    scene = _crossing()
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    first = _scheduled(ops)[0]
    _transit(scene)["destination_room"] = "skerry"

    _, ops, _, counts = _sweep(scene, THAT_EVENING, [first], turn_id=12,
                               turn_idx=5)
    assert counts["fired"] == 0
    assert _statuses(ops) == {first["event_id"]: "cancelled"}
    assert scene["positions"]["mary_ann"] == "the_channel"
    assert [json.loads(r["payload"])["destination_room"]
            for r in _scheduled(ops)] == ["skerry"]


def test_silence_about_the_end_still_lands_where_the_journey_was_bound():
    """Review B1: a later write that leaves the destination out is silence
    about it, and the arrival lands where it was booked."""
    scene = _crossing()
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    first = _scheduled(ops)[0]
    _transit(scene).pop("destination_room")
    _, _, _, counts = _sweep(scene, THAT_EVENING, [first], turn_id=12,
                             turn_idx=5)
    assert counts["fired"] == 1
    assert scene["positions"]["mary_ann"] == "the_mainland"


# ---------------------------------------------------------------------------
# The measurement the room author wrote
# ---------------------------------------------------------------------------

def test_a_measurement_written_as_a_value_and_a_unit_is_read_as_one():
    assert edge_metres({"value": 13, "unit": "km"}) == 13000.0
    assert edge_metres({"to": "the_mainland",
                        "distance": {"value": 1.5, "unit": "km"}}) == 1500.0
    assert normalize_edge_distance({"value": 13, "unit": "km"}) == "remote"
    assert normalize_edge_distance({"value": 3, "unit": "m"}) == "adjacent"
    # A record with no number in it is no measurement, as before.
    assert edge_metres({"value": "a long way", "unit": "km"}) is None
    assert normalize_edge_distance({"value": True, "unit": "km"}) == "near"
    assert normalize_edge_distance({"value": 13, "unit": "leagues"}) == "near"
