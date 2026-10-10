"""A vessel moving within the room it set off from stays in that room.

The owner's ruling of 2026-10-09 (D2), on scratch story 166 turn 4600 (F92):
the Grebe, docked in the down-channel, "noses into the reed and stops" --
written `arriving` with the channel as its route, then `docked` -- and the
2026-09-25 rule dropped a route naming the room it set off from, so the boat
was in no room for the seven beats after; and rowing it back to the stage
through the same channel (turn 4605) severed the deck's last doorway, so the
two people aboard stood `separated` and `far` from the water they crossed.

Kept from that ruling: setting off records `departed_from`; a destination is
never the place it left; leaving a room names the space it moves through,
and a route naming a space the world does not hold yet is no room until it
is built. Changed, as the ruling is worded: a journey that names NO OTHER
SPACE -- no route, or one naming the place it left, no position in another
room, no destination elsewhere, and no other space crossed yet -- has its
route at `departed_from` and stays there. A journey bound for somewhere else
is leaving, and is not that case: it is in the space it moves through when
one is named, and in no room when none is (a lift called away to another
floor, review N4). A position the step gives it in another room is the
space it moves in (review F6), never the room it is bound for (review N5).
And an open boat moving is open to the room it moves in, nearing its landing
too (review F7): the transit's own `hatch: open` opens the doorway onto the
room the vessel stands in, where it used to be a shut door whatever the
hatch.
"""

from __future__ import annotations

import copy

from world.spatial import merge_scene_with_diff, settle_departures, spatial_rel

CHANNEL, STAGE, DECK = "the_down_channel", "landing_stage", "grebe_board"


def _channel(transit=None, *, grebe_at=CHANNEL):
    grebe = {"name": "the Grebe", "kind": "vehicle", "interior_rooms": [DECK],
             "state": {"transit": dict(transit or {"phase": "docked", "hatch": "open"})}}
    scene = {
        "rooms": {
            STAGE: {"name": "the landing stage",
                    "adjacent": [{"to": CHANNEL, "barrier": "open"}]},
            CHANNEL: {"name": "the down-channel",
                      "anchors": {"reed_edge": {"desc": "the reed's edge"}},
                      "adjacent": [{"to": STAGE, "barrier": "open"}]},
            DECK: {"name": "the Grebe's deck", "parent_entity": "the_grebe",
                   "adjacent": [{"to": CHANNEL, "barrier": "open_door"}]},
        },
        "entities": {"the_grebe": grebe},
        "positions": {"Tamsin Coyle": DECK, "Hester Gale": DECK},
        "stations": {"the_grebe": {"at": "reed_edge", "near": []}},
    }
    if grebe_at:
        scene["positions"]["the_grebe"] = grebe_at
    return scene


def _write(**transit):
    return {"entities": {"the_grebe": {"state": {"transit": transit}}}}


def _transit(scene):
    return scene["entities"]["the_grebe"]["state"]["transit"]


def _door(scene):
    return {edge["to"]: edge["barrier"]
            for edge in scene["rooms"][DECK].get("adjacent") or []}


def test_a_vessel_naming_no_other_space_stays_in_the_room_it_set_off_from():
    """Turn 4600's first step, both ways the encoder writes it: the channel
    as the route, and no route at all."""
    for write in (_write(phase="arriving", hatch="open", route_room=CHANNEL),
                  _write(phase="arriving", hatch="open")):
        moved = merge_scene_with_diff(_channel(), write)
        assert moved["positions"]["the_grebe"] == CHANNEL
        assert _transit(moved)["departed_from"] == CHANNEL
        assert _transit(moved)["route_room"] == CHANNEL
        assert moved["stations"]["the_grebe"] == {"at": "reed_edge", "near": []}
        # Open to the water it is in: the passengers see out and reach out.
        assert _door(moved) == {CHANNEL: "open_door"}
        assert spatial_rel(moved, DECK, CHANNEL)["barrier"] == "open_door"


def test_stopping_where_it_moves_is_docking_there():
    """Turn 4600's second step: "noses into the reed and stops"."""
    moving = merge_scene_with_diff(_channel(), _write(
        phase="arriving", hatch="open", route_room=CHANNEL))
    stopped = merge_scene_with_diff(moving, _write(
        phase="docked", hatch="open", route_room=CHANNEL))
    assert stopped["positions"]["the_grebe"] == CHANNEL
    assert _transit(stopped)["phase"] == "docked"
    assert "departed_from" not in _transit(stopped)
    assert _door(stopped) == {CHANNEL: "open_door"}


def test_leaving_names_the_space_it_moves_through():
    """Turn 4598: the Grebe leaves the stage naming the channel as the space
    it moves through, and is in the channel."""
    out = merge_scene_with_diff(_channel(grebe_at=STAGE), _write(
        phase="in_transit", hatch="open", route_room=CHANNEL))
    assert out["positions"]["the_grebe"] == CHANNEL
    assert (_transit(out)["departed_from"], _transit(out)["route_room"]) == (STAGE, CHANNEL)


def test_a_journey_bound_elsewhere_is_not_one_within_the_room_it_left():
    """Review N4, and the ruling as worded: a journey that names a
    destination elsewhere is LEAVING the room it set off from, so it is in
    the space it moves through when one is named, and in no room when none
    is -- the 2026-09-25 rule, which drops a route naming the room it left.
    Round 2 stood such a journey in the room it left whenever no other space
    was named: a turbolift bound from the deck-14 corridor for deck 10 stood
    in that corridor behind a shut door for the whole ride (chat 34 turn
    740), and the shelter elevator descending for three minutes stood in
    the hallway at the top (chat 23 turn 436). Turn 4605 is the same shape --
    the Grebe bound back for the stage, naming only the channel it lay in as
    its route -- and reads the same way: in no room until it docks."""
    for write in (_write(phase="in_transit", hatch="closed", destination_room=STAGE,
                         eta_seconds=235),
                  _write(phase="in_transit", hatch="open", route_room=CHANNEL,
                         destination_room=STAGE)):
        away = merge_scene_with_diff(_channel(), write)
        assert "the_grebe" not in away["positions"]
        assert _transit(away)["destination_room"] == STAGE
        assert _transit(away)["departed_from"] == CHANNEL
        assert "route_room" not in _transit(away)
        assert CHANNEL not in _door(away)


def test_a_boat_the_old_floor_left_in_no_room_is_back_where_it_set_off():
    """The committed scene of turn 4600 onward: in no room, `arriving`,
    `departed_from` the channel. Any merge puts it back where it set off --
    turn 4604 wrote the same transit again and nothing else."""
    lost = _channel({"phase": "arriving", "hatch": "open",
                     "departed_from": CHANNEL}, grebe_at=None)
    found = merge_scene_with_diff(lost, _write(phase="arriving", hatch="open"))
    assert found["positions"]["the_grebe"] == CHANNEL
    assert _transit(found)["route_room"] == CHANNEL
    assert _door(found) == {CHANNEL: "open_door"}


def test_the_place_it_left_is_still_never_its_destination():
    before = _channel()
    merged = copy.deepcopy(before)
    merged["entities"]["the_grebe"]["state"]["transit"] = {
        "phase": "in_transit", "hatch": "open", "destination_room": CHANNEL,
        "eta_seconds": 30}
    settle_departures(before, merged)
    assert "destination_room" not in _transit(merged)
    assert "eta_seconds" not in _transit(merged)
    assert merged["positions"]["the_grebe"] == CHANNEL


def test_naming_the_place_it_left_keeps_the_space_it_was_crossing():
    """A ship already in the space it crosses is not sent back by a write
    that names where it left as its route: that is silence, like no route."""
    crossing = _channel({"phase": "in_transit", "hatch": "closed",
                         "departed_from": STAGE, "route_room": CHANNEL})
    later = merge_scene_with_diff(crossing, _write(
        phase="in_transit", hatch="closed", route_room=STAGE))
    assert _transit(later)["route_room"] == CHANNEL
    assert later["positions"]["the_grebe"] == CHANNEL


def test_a_hatch_shut_or_unsaid_under_way_is_a_shut_door():
    """Only the transit's own word opens the way while it moves, and only
    onto the room it stands in: a lift or a ship that leaves its hatch out
    of the write is shut, and one nearing a destination it has not reached,
    hatch shut or unsaid, faces it through a closed door."""
    for write in (_write(phase="in_transit", hatch="closed"),
                  _write(phase="in_transit")):
        assert _door(merge_scene_with_diff(_channel(), write)) == {CHANNEL: "closed_door"}
    sealed = merge_scene_with_diff(_channel(), _write(phase="sealed", hatch="open"))
    assert "open_door" not in _door(sealed).values()
    for write in (_write(phase="arriving", hatch="closed", destination_room=STAGE),
                  _write(phase="arriving", destination_room=STAGE)):
        assert _door(merge_scene_with_diff(_channel(), write)) == {STAGE: "closed_door"}


def test_an_open_boat_nearing_its_landing_is_still_on_the_water():
    """Review F7: the transit card's own "nearing the end is arriving",
    written for an open boat in the channel bound for the stage, cut the
    deck off from the channel it floats on and stood a shut door between it
    and the stage -- F92's symptom on the last leg of every boat journey. It
    stays open to the water it is on; the stage ahead is seen across it."""
    # Under way in the channel, out of the mere upstream and bound for the
    # stage: the channel is the space it crosses.
    crossing = {"phase": "in_transit", "hatch": "open", "departed_from": "the_mere",
                "route_room": CHANNEL, "destination_room": STAGE}

    def upstream():
        scene = _channel(crossing)
        scene["rooms"]["the_mere"] = {"name": "the mere", "adjacent": [
            {"to": CHANNEL, "barrier": "open"}]}
        scene["rooms"][CHANNEL]["adjacent"].append({"to": "the_mere", "barrier": "open"})
        return scene

    for write in (_write(phase="arriving", hatch="open", destination_room=STAGE),
                  _write(phase="arriving", hatch="open", destination_room=STAGE,
                         route_room=CHANNEL)):
        nearing = merge_scene_with_diff(upstream(), write)
        assert nearing["positions"]["the_grebe"] == CHANNEL
        assert _door(nearing) == {CHANNEL: "open_door"}
        assert spatial_rel(nearing, DECK, CHANNEL)["barrier"] == "open_door"
        assert _transit(nearing)["destination_room"] == STAGE
    landed = merge_scene_with_diff(nearing, {
        **_write(phase="docked", hatch="open", destination_room=STAGE)})
    assert landed["positions"]["the_grebe"] == STAGE
    assert _door(landed) == {STAGE: "open_door"}


def test_a_position_the_step_gives_it_is_the_space_it_moves_in():
    """Review F6: docked at the stage, the Grebe is rowed into the channel --
    the write gives it the channel as its position and sets off naming no
    route, or the stage. The step put it in the channel, so that is the
    space it moves through; D2 had pulled it back onto the stage, deck open
    to the stage, while the beat rowed it away."""
    for transit in ({"phase": "in_transit", "hatch": "open"},
                    {"phase": "in_transit", "hatch": "open", "route_room": STAGE}):
        out = merge_scene_with_diff(_channel(grebe_at=STAGE), {
            "positions": {"the_grebe": CHANNEL},
            "entities": {"the_grebe": {"state": {"transit": transit}}}})
        assert out["positions"]["the_grebe"] == CHANNEL
        assert (_transit(out)["departed_from"], _transit(out)["route_room"]) == (STAGE, CHANNEL)
        assert _door(out) == {CHANNEL: "open_door"}
    # A position that only repeats where it stood names no other space: it
    # moves within that room (D2).
    stays = merge_scene_with_diff(_channel(grebe_at=STAGE), {
        "positions": {"the_grebe": STAGE},
        "entities": {"the_grebe": {"state": {"transit": {"phase": "in_transit",
                                                         "hatch": "open"}}}}})
    assert stays["positions"]["the_grebe"] == STAGE
    assert _transit(stays)["route_room"] == STAGE


def test_a_position_at_where_it_is_bound_is_not_where_it_is():
    """Review N5: a ferry docked at Port A, written under way for Port B
    half an hour out with its position at Port B. Round 2 took that position
    as the space it moved through and stood the ferry at its far port for
    the whole crossing, its deck open onto the quay while it was arriving.
    A journey under way has not reached where it is bound: bound elsewhere
    and naming no space, it is in no room, and the far port is behind a shut
    door it cannot be walked through."""
    from world.spatial import passable_route_exists

    def ports(hatch):
        return {
            "rooms": {
                "port_a": {"name": "Port A", "adjacent": [{"to": "the_strait", "barrier": "open"}]},
                "the_strait": {"name": "the strait", "adjacent": [
                    {"to": "port_a", "barrier": "open"}, {"to": "port_b", "barrier": "open"}]},
                "port_b": {"name": "Port B", "adjacent": [{"to": "the_strait", "barrier": "open"}]},
                "ferry_deck": {"name": "the ferry's deck", "parent_entity": "the_ferry",
                               "adjacent": [{"to": "port_a", "barrier": "open_door"}]},
            },
            "entities": {"the_ferry": {"name": "the ferry", "kind": "vehicle",
                                       "interior_rooms": ["ferry_deck"],
                                       "state": {"transit": {"phase": "docked", "hatch": hatch}}}},
            "positions": {"the_ferry": "port_a", "Ana": "ferry_deck"},
        }

    for phase, hatch in (("in_transit", "closed"), ("arriving", "open")):
        out = merge_scene_with_diff(ports(hatch), {
            "positions": {"the_ferry": "port_b"},
            "entities": {"the_ferry": {"state": {"transit": {
                "phase": phase, "hatch": hatch, "destination_room": "port_b",
                "eta_seconds": 1800}}}}})
        transit = out["entities"]["the_ferry"]["state"]["transit"]
        assert "the_ferry" not in out["positions"], (phase, out["positions"])
        assert transit.get("route_room") in (None, "")
        assert transit["destination_room"] == "port_b"
        assert not passable_route_exists(out, "ferry_deck", "port_b", body="Ana")


def test_the_encoder_is_told_a_journey_within_one_place_stays_in_it():
    """The card that had said only "never the place it set off from" now
    names the other kind of journey too, en and ja, and says it once:
    leaving never names the place left as the space, and a thing moving
    within the place it is in stays there whether it names that place or
    none (review F10: the draft also said "that place is the space it moves
    through", which a model following both lines could not reconcile)."""
    from llm import prompts
    en = prompts.unified_specialist_prompt(["entities"], parts=["entities__transit"])
    ja = prompts.unified_specialist_prompt(["entities"], "ja", parts=["entities__transit"])
    assert ("leaving the place it stood in, never the place it set off from, "
            "which is behind it the moment it is under way.") in en
    assert ("A thing moving within the place it is already in has left nothing "
            "behind and stays there, whether it names that place as the space "
            "it moves through or names none.") in en
    assert "that place is the space it moves through" not in en
    assert "立っていた場所を離れるなら、出発した場所は決して書きません。" in ja
    assert "すでにいる場所の中で動くものは、何も後ろにせず、そこにとどまります。" in ja
    assert "その場所を通り抜けている空間として名指しても、何も名指さなくても同じです。" in ja
    assert "その場所こそが通り抜けている空間であり" not in ja


def _lift_scene():
    return {
        "rooms": {
            "deck14_corridor": {"name": "deck 14 corridor", "adjacent": []},
            "deck10_corridor": {"name": "deck 10 corridor", "adjacent": []},
            "lift_car": {"name": "the lift car", "parent_entity": "the_lift",
                         "adjacent": [{"to": "deck14_corridor", "barrier": "open_door"}]},
        },
        "entities": {"the_lift": {"name": "the turbolift", "kind": "vehicle",
                                  "interior_rooms": ["lift_car"],
                                  "state": {"transit": {"phase": "docked", "hatch": "open"}}}},
        "positions": {"the_lift": "deck14_corridor", "Ana": "lift_car"},
    }


def test_a_journey_bound_elsewhere_stays_bound_elsewhere_through_a_write_that_omits_it():
    """(review B1) Every write replaces a vessel's transit whole, so a lift
    bound for deck 10, written `{"phase": "docked", "hatch": "open"}` on the
    next beat -- the shape chat 33 turn 696 stored -- read as a journey
    naming no other space: D2 stood it back in the corridor it left with its
    door open onto it, and a bare `docked` then docked it there. Bound
    elsewhere it stays until it arrives."""
    from world.spatial import merge_scene_with_diff

    def write(**transit):
        return {"entities": {"the_lift": {"state": {"transit": transit}}}}

    def doors(scene):
        return {e["to"]: e["barrier"] for e in scene["rooms"]["lift_car"].get("adjacent") or []}
    away = merge_scene_with_diff(_lift_scene(), write(
        phase="in_transit", hatch="closed", destination_room="deck10_corridor", eta_seconds=235))
    assert "the_lift" not in away["positions"]
    for later in (write(phase="docked", hatch="open"),
                  write(phase="arriving", hatch="open", destination_room=None),
                  write(phase="in_transit", hatch="open", destination_room=None)):
        out = merge_scene_with_diff(away, later)
        assert out["positions"].get("the_lift") != "deck14_corridor", (later, out["positions"])
        assert "deck14_corridor" not in doors(out), (later, doors(out))
