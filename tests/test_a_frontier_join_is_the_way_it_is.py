"""A frontier stub's join says the place lies that way; it does not say a door
opens onto it (`world/spatial_barriers.frontier_joins`).

THE CASE: the lighthouse probe story (control story, chat 2; its live replay,
chat 3 turn 25). The boatman's destination, `the_mainland`, is a frontier
stub the plan holds open (`provisional`, `frontier_of` the rock's landing),
minted off the landing's axis "the mainland" -- and the mint joined the two
by an OPEN DOOR WITH NO DISTANCE, while the open water between them,
`the_channel` (`floor: water`), measures 1.5 km to the landing and 13 km to
the mainland. At the far end of a skip that left him on the mainland, the
boatman's own view read "You are in The Mainland. Through the open doorway is
The Landing", a shout on the landing reached him through it in full, and
before lane B2 the skip walked him home across the sea in ten minutes. B2
refused the join inside the skip alone; sight, sound, an ordinary walk,
routing and the map all still read a doorway.

THE RULE: until the place is built, the join is read as what it is, from
typed fields alone -- across a MEDIUM where a medium room joins both ends
(the water a vessel crosses: the medium's own measured ways are the way), an
UNMEASURED FAR WAY otherwise -- and never as a doorway to see, hear or walk
through, nor one drawn on the map. A built place's join (claimed by a plan,
or described by a beat) stands as written, and an ordinary planned room is
untouched.
"""

from __future__ import annotations

import copy
import json
import time

from agents.director import _edge_to, _still_crossing, declared_walk_leg
from agents.perception import _visible_openings
from agents import composer
from web.world_routes import map_view
from world.charter_move import WALK_EDGE_PACES, WALK_PACES_PER_SECOND, edge_seconds
from world.spatial import (FRONTIER_FAR, FRONTIER_MEDIUM, SPEECH_DB, beam_sent_into,
                           corridor_sightlines, effective_adjacent,
                           effective_anchors, effective_light, frontier_joins,
                           frontier_way, hear_level, light_passes, nearby_rooms,
                           normalize_edge_distance, passable_neighbors,
                           passable_path, passable_route_exists, room_sound_flood,
                           sight_passes, sound_passes, spatial_rel,
                           spatial_rel_between, visible_adjacent_rooms,
                           visual_level_between)
from world.structure import (apply_frontier_mutations, claim_frontier_spaces,
                             lay_held_open_marks, materialize_planned_fringe,
                             plant_structure, prepare_frontier_expansion,
                             settle_developed_stubs, skeleton_rooms, solved_scene)

LANDING, MAINLAND, CHANNEL, STAIR = "rock_landing", "the_mainland", "the_channel", "the_stair"
PELL, RHONA = "Pell Hardacre", "Rhona Carrick"
HELD = {"provisional": True, "frontier_of": {"room": LANDING, "axis": "the mainland"}}


def _lighthouse(*, held_open=True):
    """The far end of the skip as the live replay committed it (chat 3,
    checkpoint 9), cut to the rooms the join touches: the join exactly as
    the mint and `_settle_stub_barriers` left it on both sides, the channel
    with its own two measured ways, the boatman on the mainland stub and a
    keeper on the landing. `held_open` lays the marks the registry's
    `provisional` row puts on the live stub (`structure.held_open_marks`)."""
    mainland = {"name": "The Mainland", "planned": True, "purpose": "", "level": 0,
                "adjacent": [{"to": LANDING, "barrier": "open_door"}]}
    if held_open:
        mainland.update(copy.deepcopy(HELD))
    return {
        "rooms": {
            LANDING: {
                "name": "The Landing", "exposure": "open", "floor": "stone",
                "extent": {"w": 12, "d": 8}, "shape": "rectangle", "level": 0,
                "desc": "A low shelf of wet black rock at the foot of the crag.",
                "adjacent": [
                    {"to": STAIR, "vertical": "up", "way": "ladder", "dir": "n",
                     "barrier": "open"},
                    {"to": MAINLAND, "barrier": "open_door", "axis": "the mainland"}]},
            STAIR: {"name": "The Steps", "exposure": "open", "level": 1,
                    "desc": "Stone steps cut up the crag to the tower door.",
                    "adjacent": []},
            MAINLAND: mainland,
            CHANNEL: {
                "name": "the channel", "floor": "water", "exposure": "open", "level": 0,
                "desc": "The sound between the rock and the mainland, open water.",
                "adjacent": [
                    {"to": LANDING, "barrier": "open", "dir": "w",
                     "distance": {"value": 1.5, "unit": "km"}},
                    {"to": MAINLAND, "barrier": "open", "dir": "e",
                     "distance": {"value": 13, "unit": "km"}}]},
        },
        "positions": {PELL: MAINLAND, RHONA: LANDING},
        "entities": {},
    }


def _built_by_a_beat(scene):
    """The stub as a beat that walked into it leaves it: described, and the
    plan's flags taken off (`settle_developed_stubs`)."""
    scene["rooms"][MAINLAND]["desc"] = "A stone quay under a row of grey houses."
    settle_developed_stubs(scene)
    return scene


def _openings_text(scene, observer, room):
    rows = _visible_openings(scene, observer, room)
    return composer._render_openings(rows, here=scene["rooms"][room]["name"])


def _map_exits(scene, room):
    for comp in map_view(scene, []).get("components") or []:
        for row in comp.get("rooms") or []:
            if row["id"] == room:
                return {e["to"]: e["barrier"] for e in row.get("exits") or []}
    return {}


# -- 1. the lighthouse: a join across the water is no doorway ----------------

def test_the_lighthouse_join_is_read_across_the_channel():
    scene = _lighthouse()
    assert frontier_joins(scene) == {frozenset((MAINLAND, LANDING)): FRONTIER_MEDIUM}
    rel = spatial_rel(scene, MAINLAND, LANDING)
    # The relation is the channel's: its longer way, 13 km -- no air.
    assert rel["frontier_join"] == FRONTIER_MEDIUM and rel["across"] == CHANNEL
    assert rel["distance"] == "remote"


def test_the_boatman_does_not_see_the_landing_through_a_doorway():
    scene = _lighthouse()
    text = _openings_text(scene, PELL, MAINLAND)
    assert "doorway" not in text and "The Landing" not in text
    # What he does see from the shore is the water before him.
    assert "the channel" in text
    assert LANDING not in [r["room_id"] for r in visible_adjacent_rooms(scene, MAINLAND)]
    assert MAINLAND not in [r["room_id"] for r in visible_adjacent_rooms(scene, LANDING)]
    # No doorway stands in either room's wall ...
    assert "door:" + LANDING not in effective_anchors(scene, MAINLAND)
    assert "door:" + MAINLAND not in effective_anchors(scene, LANDING)
    # ... and nobody on the landing is in his sight.
    assert visual_level_between(scene, PELL, RHONA) == "none"


def test_a_shout_on_the_landing_does_not_reach_the_mainland():
    scene = _lighthouse()
    shout = SPEECH_DB["shout"]
    assert MAINLAND not in room_sound_flood(scene, LANDING, shout)
    assert hear_level(spatial_rel_between(scene, PELL, RHONA), "shout") == "none"
    # Nor his, from the shore, on the landing, whose field is laid out.
    assert hear_level(spatial_rel_between(scene, RHONA, PELL), "shout") == "none"


def test_no_walk_steps_from_the_mainland_onto_the_landing():
    scene = _lighthouse()
    assert LANDING not in passable_neighbors(scene).get(MAINLAND, set())
    # The only way between them is the channel's: the medium's own ways.
    assert passable_path(scene, MAINLAND, LANDING) == [CHANNEL, LANDING]
    assert MAINLAND not in {str(e["to"]) for e in effective_adjacent(scene, LANDING)}


def test_a_payload_still_holds_the_place_that_lies_that_way():
    """Relevance is not a way: a stage's payload trims to the rooms a beat may
    be about, and the place a boat is bound for, held open past the landing,
    is one of them however far across the water it lies (`nearby_rooms`)."""
    scene = _lighthouse()
    assert MAINLAND in nearby_rooms(scene, [LANDING], hops=1)
    assert LANDING in nearby_rooms(scene, [MAINLAND], hops=1)


def test_the_map_draws_no_door_between_the_landing_and_the_mainland():
    scene = _lighthouse()
    assert MAINLAND not in _map_exits(scene, LANDING)
    assert LANDING not in _map_exits(scene, MAINLAND)


def test_the_landing_seen_from_its_steps_has_one_way_on():
    """Looking down the ladder at the landing, its ways on are the channel's
    and nothing else: the join to the mainland is no way out of it."""
    scene = _lighthouse()
    seen = {r["room_id"]: r for r in visible_adjacent_rooms(scene, STAIR)}
    assert seen[LANDING]["onward_exits"] == 1


def test_the_space_a_vessel_crosses_under_way_is_a_medium_too():
    """Typed fields only: the channel's `floor: water`, or -- where no floor
    says so -- a vessel under way naming it as its route."""
    scene = _lighthouse()
    scene["rooms"][CHANNEL].pop("floor")
    assert frontier_joins(scene) == {frozenset((MAINLAND, LANDING)): FRONTIER_FAR}
    scene["entities"]["mary_ann"] = {
        "name": "The Mary Ann", "kind": "vehicle",
        "state": {"transit": {"phase": "in_transit", "route_room": CHANNEL,
                              "destination_room": MAINLAND,
                              "departed_from": LANDING}}}
    assert frontier_joins(scene) == {frozenset((MAINLAND, LANDING)): FRONTIER_MEDIUM}


# -- 2. a join that crosses no medium is an unmeasured far way ---------------

BYRE, PASTURE, YARD = "hallow_farm_byre", "the_home_pasture", "hallow_farm_yard"
ASH, PROBE = "Ash Penrose", "Probe Listener"


def _farm(*, held_open=True):
    """The house probe story (chat 2): the byre's axis "the home pasture"
    minted a stub joined to it by the mint's open door, and nothing else
    stands between them."""
    pasture = {"name": "The Home Pasture", "planned": True, "purpose": "", "level": 0,
               "adjacent": [{"to": BYRE, "barrier": "open_door"}]}
    if held_open:
        pasture.update({"provisional": True,
                        "frontier_of": {"room": BYRE, "axis": "the home pasture"}})
    return {
        "rooms": {
            BYRE: {"name": "the byre", "exposure": "sheltered", "floor": "stone",
                   "extent": {"w": 3, "d": 4}, "shape": "rectangle", "level": 0,
                   "desc": "A low stone outbuilding east of the yard.",
                   "adjacent": [
                       {"to": YARD, "barrier": "open_door", "distance": "adjacent",
                        "dir": "w", "name": "the byre door"},
                       {"to": PASTURE, "barrier": "open_door", "axis": "the home pasture"}]},
            YARD: {"name": "the yard", "exposure": "open", "level": 0,
                   "desc": "A muddy yard between the house and the byre.", "adjacent": []},
            PASTURE: pasture,
        },
        "positions": {ASH: BYRE, PROBE: PASTURE},
        "entities": {},
    }


def test_the_far_join_is_walked_as_a_far_way_not_a_doorway():
    scene = _farm()
    assert frontier_joins(scene) == {frozenset((BYRE, PASTURE)): FRONTIER_FAR}
    # The place lies that way: a body may still set off for it ...
    assert passable_route_exists(scene, BYRE, PASTURE)
    assert declared_walk_leg(scene, BYRE, PASTURE)[0] == PASTURE
    # ... but it is a long way, priced as one and crossed in a long edge's beats.
    edge = _edge_to(scene["rooms"], BYRE, PASTURE, scene)
    assert normalize_edge_distance(edge.get("distance")) == "far"
    assert _still_crossing(normalize_edge_distance(edge.get("distance")), 1)
    assert edge_seconds(scene, BYRE, PASTURE) >= WALK_EDGE_PACES["far"] / WALK_PACES_PER_SECOND
    rel = spatial_rel(scene, PASTURE, BYRE)
    assert (rel["barrier"], rel["distance"], rel["frontier_join"]) == ("open", "far", FRONTIER_FAR)


def test_the_far_join_tells_its_holder_the_way_goes_on():
    """A FAR join is a way: the place lies that way, and the room it leaves
    from says so -- the Room's frontier is a space held open for exploring,
    and a player who is not told a way goes on there never sets off. It is
    never a door seen through: the stub is named, nothing past the join is
    described, and the sentence is the pack's own onward wording."""
    scene = _farm()
    rows = [r for r in _visible_openings(scene, ASH, BYRE) if r.get("room_name") == "The Home Pasture"]
    assert [r["state"] for r in rows] == ["onward"]
    assert not rows[0].get("room_notes") and not rows[0].get("features")
    text = _openings_text(scene, ASH, BYRE)
    assert "From here the way goes on to The Home Pasture." in text
    assert "is The Home Pasture" not in text
    # And from the stub, the way goes on back.
    assert _openings_text(scene, PROBE, PASTURE) == "From here the way goes on to the byre."


def test_a_far_join_up_or_down_says_which_way_it_goes_on():
    """A frontier that continues a shaft or a stair goes on UP or DOWN (the
    owner's chat 160: `shaft_above` off the elevator shaft, `vertical: up`)."""
    scene = _farm()
    scene["rooms"][BYRE]["adjacent"][1]["vertical"] = "up"
    scene["rooms"][PASTURE]["adjacent"][0]["vertical"] = "down"
    assert "Up from here is The Home Pasture." in _openings_text(scene, ASH, BYRE)


def test_a_way_that_goes_on_is_no_boundary_counted_beside_the_others():
    """The onward line names no boundary, so it takes no ordinal from one:
    the byre's plain opening onto the yard is still "the opening", not "the
    second opening", whichever of its ways the room lists first."""
    scene = _farm()
    scene["rooms"][BYRE]["adjacent"] = [
        {"to": PASTURE, "barrier": "open_door", "axis": "the home pasture"},
        {"to": YARD, "barrier": "open"}]
    text = _openings_text(scene, ASH, BYRE)
    assert "Through the opening is the yard." in text
    assert "second" not in text


def test_a_join_across_the_water_says_no_way_goes_on():
    """Across a medium the join is no way at all: the landing's view tells of
    the channel, and never that a way goes on to the mainland."""
    scene = _lighthouse()
    text = _openings_text(scene, RHONA, LANDING)
    assert "The Mainland" not in text
    assert "the channel" in text


def test_the_far_join_is_not_seen_or_heard_through_as_a_doorway():
    scene = _farm()
    assert "is the byre" not in _openings_text(scene, PROBE, PASTURE)
    assert PASTURE not in [r["room_id"] for r in visible_adjacent_rooms(scene, BYRE)]
    assert "door:" + PASTURE not in effective_anchors(scene, BYRE)
    assert visual_level_between(scene, PROBE, ASH) == "none"
    # A far way's sound: a voice is not heard as through an open door; what
    # carries is the far field's price of the ground between.
    rel = spatial_rel_between(scene, PROBE, ASH)
    assert rel.get("far_loss_db") is not None
    assert hear_level(dict(rel), "normal") != "full"
    # And the map draws an opening that covers ground, never a door.
    assert _map_exits(scene, BYRE)[PASTURE] == "open"


def test_no_light_crosses_the_far_join():
    """A stub dark of its own takes no spill from a lit room beyond the join,
    and a beam pointed at it from there is not sent into it -- read at the
    rooms' own level, the byre laid out by no light field."""
    scene = _farm()
    for field in ("extent", "shape"):
        scene["rooms"][BYRE].pop(field)
    scene["rooms"][BYRE].update(exposure="enclosed", light="lit")
    scene["rooms"][PASTURE]["light"] = "dark"
    assert effective_light(scene, PASTURE) == "dark"
    scene["rooms"][BYRE]["light"] = "dark"
    scene["positions"]["torch"] = BYRE
    scene["entities"]["torch"] = {"name": "the torch", "light_source": "lit",
                                  "portable": True, "light_shape": "cone",
                                  "state": {"pointed_at": PASTURE}}
    scene["contained"] = {"torch": {"in": ASH, "mode": "held"}}
    assert not beam_sent_into(scene, PASTURE, BYRE)


def _farm_in_a_line():
    """The farm beared west to east -- yard, byre, the pasture's stub -- with a
    built meadow a hand joined to the stub beyond it, so a line of sight has
    somewhere to run on to on either side of the join."""
    scene = _farm()
    scene["rooms"][YARD]["adjacent"] = [{"to": BYRE, "barrier": "open", "dir": "e"}]
    scene["rooms"][BYRE]["adjacent"] = [
        {"to": YARD, "barrier": "open", "dir": "w"},
        {"to": PASTURE, "barrier": "open_door", "dir": "e", "axis": "the home pasture"}]
    scene["rooms"][PASTURE]["adjacent"] = [
        {"to": BYRE, "barrier": "open_door", "dir": "w"},
        {"to": "meadow", "barrier": "open", "dir": "e"}]
    scene["rooms"]["meadow"] = {"name": "the long meadow", "level": 0,
                                "desc": "Rough grass running down to a stream.",
                                "adjacent": [{"to": PASTURE, "barrier": "open", "dir": "w"}]}
    return scene


def test_no_line_of_sight_runs_down_the_far_join():
    """Beared, with a built room beyond it, a corridor line still neither
    starts down the join nor runs on through it: the place lies that way,
    unbuilt."""
    scene = _farm_in_a_line()
    assert all(line.get("dir") != "e" for line in corridor_sightlines(scene, BYRE))
    assert all(line.get("distance", 0) < 2 or line.get("dir") != "e"
               for line in corridor_sightlines(scene, YARD))
    # No grid is laid through it, for sight, light or sound.
    edge = frontier_way(scene["rooms"][BYRE]["adjacent"][1])
    assert sight_passes(scene, BYRE, edge) is None
    assert light_passes(scene, BYRE, edge) is None
    assert sound_passes(scene, BYRE, edge) is None


# -- 3. a built place's join stands -------------------------------------------

def test_a_claimed_place_keeps_the_join_as_written():
    """A plan that claims the space rewrites the row without `provisional`
    -- keeping `frontier_of`, the axis it was minted for -- and the join is
    what it says: the held-open mark, not the provenance, is what reads it as
    the way it really is."""
    scene = _lighthouse(held_open=False)
    scene["rooms"][MAINLAND]["frontier_of"] = dict(HELD["frontier_of"])
    assert frontier_joins(scene) == {}
    assert LANDING in [r["room_id"] for r in visible_adjacent_rooms(scene, MAINLAND)]
    assert "door:" + LANDING in effective_anchors(scene, MAINLAND)
    assert "open doorway" in _openings_text(scene, PELL, MAINLAND)
    assert hear_level(spatial_rel_between(scene, PELL, RHONA), "shout") == "full"
    assert passable_path(scene, MAINLAND, LANDING) == [LANDING]
    assert _map_exits(scene, LANDING)[MAINLAND] == "open_door"


def test_a_place_described_this_beat_is_built_before_its_flags_come_off():
    """Within the beat that describes it the merge has written its prose and
    the commit has not yet settled it: a room with prose is built."""
    scene = _lighthouse()
    scene["rooms"][MAINLAND]["desc"] = "A stone quay under a row of grey houses."
    assert scene["rooms"][MAINLAND]["provisional"] is True
    assert frontier_joins(scene) == {}
    assert passable_path(scene, MAINLAND, LANDING) == [LANDING]


def test_a_place_a_beat_described_keeps_the_join_as_written():
    scene = _built_by_a_beat(_lighthouse())
    assert "provisional" not in scene["rooms"][MAINLAND]
    assert frontier_joins(scene) == {}
    assert LANDING in [r["room_id"] for r in visible_adjacent_rooms(scene, MAINLAND)]
    assert passable_path(scene, MAINLAND, LANDING) == [LANDING]
    assert _map_exits(scene, MAINLAND)[LANDING] == "open_door"


# -- 4. an ordinary planned room is untouched ----------------------------------

def test_an_ordinary_planned_room_is_read_exactly_as_before():
    """A prose-free planned bedroom is the plan's room, not a space held open:
    no mark, no rewrite -- the very edge the scene holds."""
    scene = {"rooms": {
        "tower_hall": {"name": "The Hall", "desc": "A round stone hall.",
                       "adjacent": [{"to": "bedroom", "barrier": "open_door"}]},
        "bedroom": {"name": "The Keeper's Room", "planned": True,
                    "purpose": "where the keeper sleeps",
                    "adjacent": [{"to": "tower_hall", "barrier": "open_door"}]}},
        "positions": {"Keeper": "bedroom", "Visitor": "tower_hall"}, "entities": {}}
    assert frontier_joins(scene) == {}
    own = effective_adjacent(scene, "bedroom")
    assert own[0] is scene["rooms"]["bedroom"]["adjacent"][0]
    assert "door:tower_hall" in effective_anchors(scene, "bedroom")
    assert "tower_hall" in [r["room_id"] for r in visible_adjacent_rooms(scene, "bedroom")]
    assert passable_path(scene, "bedroom", "tower_hall") == ["tower_hall"]
    assert hear_level(spatial_rel_between(scene, "Keeper", "Visitor"), "normal") == "full"
    assert "frontier_join" not in spatial_rel(scene, "bedroom", "tower_hall")


# -- 5. one reading of the medium ---------------------------------------------

def test_the_skip_reads_the_medium_the_spatial_layer_reads():
    """One owner for what a vessel crosses: the skip's executor reads the
    spatial layer's `MEDIUM_FLOORS` and `medium_rooms`, never a copy."""
    import world.spatial as spatial
    from world import skip_itinerary as itin
    assert itin.MEDIUM_FLOORS is spatial.MEDIUM_FLOORS
    assert itin.media is spatial.medium_rooms
    assert itin.media(_lighthouse()) == {CHANNEL}


# -- 6. the live stub carries the marks the registry holds ---------------------

GRAMMAR = {"key": "the_lamp_tower", "max_planned": 50, "grammar": []}


def _chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Frontier join", "", time.time()))


def _minted(temp_db, cid):
    """The landing planted with its axis, the boatman standing on it, and the
    frontier expansion run as a commit runs it."""
    plant_structure(cid, GRAMMAR, {LANDING: {
        "name": "The Landing", "purpose": "where the relief boat ties up",
        "adjacent": [], "frontier": ["the mainland"]}})
    scene = {"rooms": {LANDING: {"name": "The Landing", "desc": "Wet black rock.",
                                 "adjacent": []}},
             "positions": {PELL: LANDING}, "entities": {}}
    scene, mutations = prepare_frontier_expansion(cid, scene)
    with temp_db.transaction():
        apply_frontier_mutations(cid, None, mutations)
    return scene


def test_a_minted_stub_says_it_is_held_open_from_the_beat_it_is_minted(temp_db):
    cid = _chat(temp_db)
    scene = _minted(temp_db, cid)
    assert scene["rooms"][MAINLAND]["provisional"] is True
    assert scene["rooms"][MAINLAND]["frontier_of"] == {"room": LANDING, "axis": "the mainland"}
    assert frontier_joins(scene) == {frozenset((MAINLAND, LANDING)): FRONTIER_FAR}
    # The fringe keeps the marks, and the skeleton carries them too.
    scene, _ = materialize_planned_fringe(cid, scene)
    assert scene["rooms"][MAINLAND]["provisional"] is True
    assert skeleton_rooms(cid, GRAMMAR["key"])["rooms"][MAINLAND]["provisional"] is True


def test_the_commit_heals_a_scene_stored_without_the_marks(temp_db):
    """The fringe the commit runs lays the marks the registry holds onto the
    stored blob, and takes them off one a plan has claimed."""
    cid = _chat(temp_db)
    scene = _minted(temp_db, cid)
    for field in ("provisional", "frontier_of"):
        scene["rooms"][MAINLAND].pop(field)
    scene, _ = materialize_planned_fringe(cid, scene)
    assert scene["rooms"][MAINLAND]["provisional"] is True
    rooms, plan, errors = claim_frontier_spaces(cid, {"quay": {
        "name": "Harrow Quay", "purpose": "the mainland's harbour wall",
        "adjacent": [], "frontier": [],
        "claims": {"room": LANDING, "axis": "the mainland"}}}, scene=scene)
    plant_structure(cid, GRAMMAR, rooms, claims=plan)
    scene, _ = materialize_planned_fringe(cid, scene)
    assert "provisional" not in scene["rooms"][MAINLAND]


def test_a_stub_the_fringe_lays_says_so(temp_db):
    """The fringe's stub (`_planned_stub`), which the layout tier's preview
    reads too (`solved_scene`)."""
    spec = {"name": "The Mainland", "purpose": "", "structure": GRAMMAR["key"],
            "adjacent": [{"to": LANDING, "barrier": "open"}],
            "provisional": True, "frontier_of": {"room": LANDING, "axis": "the mainland"}}
    rooms = solved_scene({MAINLAND: ("The Mainland", spec)})["rooms"]
    assert rooms[MAINLAND]["provisional"] is True
    assert rooms[MAINLAND]["frontier_of"] == {"room": LANDING, "axis": "the mainland"}


def test_a_scene_stored_without_the_marks_is_read_with_them(temp_db):
    """A stub minted before the marks existed: the beat that reads it lays
    them from the registry (`story.scene.get_scene` -> `lay_held_open_marks`)."""
    cid = _chat(temp_db)
    scene = _minted(temp_db, cid)
    for field in ("provisional", "frontier_of"):
        scene["rooms"][MAINLAND].pop(field)
    assert frontier_joins(scene) == {}
    assert lay_held_open_marks(cid, scene) == [MAINLAND]
    assert frontier_joins(scene) == {frozenset((MAINLAND, LANDING)): FRONTIER_FAR}


def test_a_claim_takes_the_marks_off_and_the_join_stands(temp_db):
    cid = _chat(temp_db)
    scene = _minted(temp_db, cid)
    rooms, plan, errors = claim_frontier_spaces(cid, {"quay": {
        "name": "Harrow Quay", "purpose": "the mainland's harbour wall",
        "adjacent": [], "frontier": [],
        "claims": {"room": LANDING, "axis": "the mainland"}}}, scene=scene)
    assert errors == []
    plant_structure(cid, GRAMMAR, rooms, claims=plan)
    assert lay_held_open_marks(cid, scene) == []
    assert "provisional" not in scene["rooms"][MAINLAND]
    assert frontier_joins(scene) == {}


def test_a_described_stub_takes_the_marks_off(temp_db):
    cid = _chat(temp_db)
    scene = _minted(temp_db, cid)
    scene["rooms"][MAINLAND]["desc"] = "A stone quay under a row of grey houses."
    assert settle_developed_stubs(scene) == [MAINLAND]
    assert "provisional" not in scene["rooms"][MAINLAND]
    # And a read after it does not lay them back on a built room.
    assert lay_held_open_marks(cid, scene) == []
    assert frontier_joins(scene) == {}


def test_the_beat_reads_the_marks_from_the_registry(temp_db):
    """`story.scene.get_scene` lays them, so the beat that first reads a
    scene stored without them already reads the join as the way it is."""
    from core.db import wset
    from story.scene import get_scene
    cid = _chat(temp_db)
    scene = _minted(temp_db, cid)
    for field in ("provisional", "frontier_of"):
        scene["rooms"][MAINLAND].pop(field)
    wset(cid, "scene", scene)
    read = get_scene(cid)
    assert read["rooms"][MAINLAND]["provisional"] is True
    assert frontier_joins(read) == {frozenset((MAINLAND, LANDING)): FRONTIER_FAR}


def test_the_commit_merges_onto_the_marks_the_beat_read(temp_db):
    """The commit's merge base is the scene its readers saw (`compose_beat_
    scene`, beside `apply_solved_plans`): the place-memory and hearing
    domains read the composed scene before the fringe runs."""
    from core.db import wset
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist.commit import compose_beat_scene
    cid = _chat(temp_db)
    scene = _minted(temp_db, cid)
    for field in ("provisional", "frontier_of"):
        scene["rooms"][MAINLAND].pop(field)
    wset(cid, "scene", scene)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "wait", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Frontier join", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=1, player_input="wait",
                      created=time.time(), frame_id=None),
        cast=[], input="wait")
    ctx.director_resolve = {"resolved_event": "Nothing moves.",
                            "dialogue_log": [], "state_diff": {}}
    composed = compose_beat_scene(ctx)
    assert composed.scene["rooms"][MAINLAND]["provisional"] is True
    assert frontier_joins(composed.scene) == {
        frozenset((MAINLAND, LANDING)): FRONTIER_FAR}


def test_the_marks_survive_the_scene_as_json(temp_db):
    """A checkpoint, an archive and a branch store the scene as JSON."""
    cid = _chat(temp_db)
    scene = json.loads(json.dumps(_minted(temp_db, cid)))
    assert frontier_joins(scene) == {frozenset((MAINLAND, LANDING)): FRONTIER_FAR}
