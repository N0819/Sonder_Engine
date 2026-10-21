"""Under way a vessel is in the space it moves through -- never in the place
it is bound for -- and a vessel the world can place nowhere asks for that
space.

The control story (2026-10-20, chat 1, a lighthouse on a sea rock; idx 4 is
turn id 5): the relief boat `mary_ann`, moored at the `landing` with its
open well `mary_ann_well` as its inside, cast off "departing for the
harbour". The encoder wrote `state.transit = {phase: in_transit, hatch:
open, route_room: harrow_street, destination_room: harrow_street}` --
`harrow_street` being the mainland street a letter was addressed to, which
the room designer had built the beat before -- against its own card, which
calls the route "the space it moves through between its places". The merge
stood the boat in its route, so it stood in the street within the beat, its
well's doorway re-pointed from the landing to the street, a rock in the sea
behind it: the owner's "departure is never arrival" (2026-09-25) broken by
the one write that names the place gone to as the way there.

The scenes here are the checkpoint's shape cut to what the rule reads; the
transits are the encoder's recorded writes, interpret's and resolve's.
"""

from __future__ import annotations

import copy
import time

import pytest

import agents.mapping as mapping
from agents import director_prose
from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from world.spatial import merge_scene_with_diff

LANDING, STREET, WELL, BOAT = "landing", "harrow_street", "mary_ann_well", "mary_ann"

#: The encoder's two writes, as recorded (control.db, turn id 5): the
#: interpret stage named the street as the way, the resolve stage named it
#: as the way AND the end.
INTERPRET_WRITE = {"phase": "in_transit", "hatch": "open", "route_room": STREET}
RESOLVE_WRITE = {"phase": "in_transit", "hatch": "open", "route_room": STREET,
                 "destination_room": STREET}


def _rock(*, channel=False):
    """Checkpoint 4 (the world before idx 4), cut to the rule's inputs: the
    tower's rooms, the landing shelf, the street the designer joined to the
    tower's foot as `{open, far}`, and the boat moored with its well open
    onto the landing."""
    rooms = {
        LANDING: {"name": "The Landing", "size": "medium", "exposure": "open",
                  "adjacent": [{"to": "tower_foot", "barrier": "open",
                                "distance": "adjacent"}]},
        "tower_foot": {"name": "The Tower Foot", "size": "small",
                       "exposure": "enclosed",
                       "adjacent": [{"to": LANDING, "barrier": "open"},
                                    {"to": "lamp_room", "barrier": "open"}]},
        "lamp_room": {"name": "The Lamp Room", "exposure": "enclosed",
                      "adjacent": [{"to": "tower_foot", "barrier": "open"}]},
        STREET: {"name": "Harrow Street", "size": "medium", "exposure": "open",
                 "adjacent": [{"to": "tower_foot", "dir": "sw", "barrier": "open",
                               "distance": "far", "name": "the quay road"}]},
        WELL: {"name": "The Mary Ann's Well", "size": "small", "exposure": "open",
               "parent_entity": BOAT,
               "adjacent": [{"to": LANDING, "barrier": "open_door",
                             "distance": "near"}]},
    }
    if channel:
        rooms["the_channel"] = {
            "name": "The Channel", "size": "large", "exposure": "open",
            "adjacent": [{"to": LANDING, "barrier": "open"}]}
    return {
        "rooms": rooms,
        "entities": {BOAT: {"name": "The Mary Ann", "kind": "vehicle",
                            "interior_rooms": [WELL],
                            "state": {"transit": {"phase": "docked", "hatch": "open"},
                                      "engine": "off"}}},
        "positions": {"Rhona Carrick": "tower_foot", "Elias Thorne": "tower_foot",
                      "Pell Hardacre": "tower_foot", BOAT: LANDING},
    }


def _cast_off(scene, transit):
    return merge_scene_with_diff(scene, {
        "entities": {BOAT: {"state": {"transit": dict(transit),
                                      "engine": "running"}}},
        "positions": {"Pell Hardacre": WELL}})


def _well_opens_onto(scene):
    return {e["to"] for e in scene["rooms"][WELL].get("adjacent") or []
            if isinstance(e, dict) and e.get("to") != WELL}


def test_the_control_beat_puts_the_boat_on_no_street():
    """The resolve write merged over the world before the beat, and then
    over the world the interpret write had already made (a beat's diff is
    merged more than once): either way the boat is not in the street, and
    its well opens onto nothing -- the space it crosses has not been named.
    It keeps where it left and where it is bound, and its pilot is aboard.

    The same beat written as the card asks -- the water as the way, the
    street as the end -- stands the boat in the channel, its open well open
    onto the water it floats on and never onto the street: the rule takes
    nothing from it."""
    for before in (_rock(), _cast_off(_rock(), INTERPRET_WRITE)):
        after = _cast_off(before, RESOLVE_WRITE)
        transit = after["entities"][BOAT]["state"]["transit"]
        assert after["positions"].get(BOAT) != STREET
        assert BOAT not in after["positions"], "under way in no room until its water is built"
        assert "route_room" not in transit
        assert transit["destination_room"] == STREET
        assert transit["departed_from"] == LANDING
        assert _well_opens_onto(after) == set(), "no door onto a place not reached"
        assert after["positions"]["Pell Hardacre"] == WELL
    on_water = _cast_off(_rock(channel=True), dict(RESOLVE_WRITE, route_room="the_channel"))
    assert on_water["positions"][BOAT] == "the_channel"
    assert _well_opens_onto(on_water) == {"the_channel"}
    assert on_water["entities"][BOAT]["state"]["transit"]["destination_room"] == STREET


# ---- the vessel in no room asks for the space it moves through ------------

def _ctx(temp_db, scene, idx=5):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("The Lamp Room", "A rock lighthouse.", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, "go", time.time()))
    wset(cid, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="The Lamp Room", persona_id=None, lorebook_id=None,
                      scenario="A rock lighthouse.", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=idx, player_input="go",
                      created=time.time(), frame_id=None),
        cast=[], input="go")
    ctx.director_interpret = {"movement": None, "flow": {}}
    return ctx


@pytest.fixture
def no_retrieval(monkeypatch):
    monkeypatch.setattr(mapping, "search_lore", lambda weights, query, **kw: [])


def _needs(temp_db, scene, reason):
    out = mapping.compile_world_context(_ctx(temp_db, scene), nonce=0)
    return [n for n in out.get("planning_needs", []) if n.get("reason") == reason]


def test_a_vessel_in_no_room_asks_for_the_space_between(temp_db, no_retrieval):
    """No room is only the floor (the owner, 2026-09-25). The beat after the
    control beat compiles a world whose boat is under way in no room, and
    asks for the space it moves through, by its two ends, so that space is
    planned as reached from the landing and never as the street. Its end
    the world holds, so the journey's end is asked for by nobody.

    In its water, nothing is owed. And a vehicle with no inside -- a coach
    the story never boarded -- is a thing in no room, which strands nobody."""
    committed = _cast_off(_rock(), RESOLVE_WRITE)
    needs = _needs(temp_db, committed, "transit_route_unplanned")
    assert len(needs) == 1
    need = needs[0]
    assert need["kind"] == "room" and need["subject"] == "landing -> harrow_street"
    assert need["surface"]["vehicle"] == BOAT
    assert need["surface"]["departed_from"] == LANDING
    assert need["surface"]["destination_room"] == STREET
    assert not _needs(temp_db, committed, "transit_destination_unplanned")
    on_water = _cast_off(_rock(channel=True), dict(RESOLVE_WRITE, route_room="the_channel"))
    assert not _needs(temp_db, on_water, "transit_route_unplanned")
    coach = copy.deepcopy(committed)
    del coach["rooms"][WELL]
    coach["entities"][BOAT]["interior_rooms"] = []
    coach["positions"].pop("Pell Hardacre")
    assert not _needs(temp_db, coach, "transit_route_unplanned")


def test_a_route_still_to_be_built_is_asked_for_by_its_own_words(temp_db, no_retrieval):
    """A route written `new:<words>` that no author built leaves the boat in
    no room with the words on its transit; the need carries them."""
    scene = _cast_off(_rock(), {"phase": "in_transit", "hatch": "open",
                                "route_room": "new:the channel",
                                "destination_room": STREET})
    assert BOAT not in scene["positions"]
    needs = _needs(temp_db, scene, "transit_route_unplanned")
    assert [n["subject"] for n in needs] == ["the channel"]


# ---- a journey's end is a place the world holds ----------------------------

def _transit_event(transit):
    return {"event": "Pell turns the Mary Ann's bow west into the channel.",
            "transforms": [{"item": BOAT, "patch": {"entities": {BOAT: {
                "state": {"transit": dict(transit), "engine": "running"}}}}}]}


def test_a_journey_bound_for_a_place_still_to_be_built_sets_off_without_it():
    """The card: "never a place still to be built, which is left out". Every
    string the encoder writes is walked for `new:` places, so a destination
    written that way had the room author build it this beat beside the
    rooms the boat is leaving -- the same door as the street's. Left out, the
    boat is under way bound for nowhere named, its ETA with it; a held end, a
    route still to be built and an arrival are written as they came."""
    events = [_transit_event({"phase": "in_transit", "hatch": "open",
                              "route_room": "new:the channel",
                              "destination_room": "new:the harbour",
                              "eta_seconds": 1800})]
    warned = []
    kept = director_prose.journeys_end_where_the_world_is(events, warn=warned.append)
    transit = kept[0]["transforms"][0]["patch"]["entities"][BOAT]["state"]["transit"]
    assert transit == {"phase": "in_transit", "hatch": "open",
                       "route_room": "new:the channel"}
    assert director_prose.new_place_refs(kept) == ["the channel"]
    assert len(warned) == 1 and "new:the harbour" in warned[0]
    for transit in ({"phase": "in_transit", "destination_room": STREET},
                    {"phase": "docked", "destination_room": "new:the harbour"}):
        same = [_transit_event(transit)]
        assert director_prose.journeys_end_where_the_world_is(same) == same
