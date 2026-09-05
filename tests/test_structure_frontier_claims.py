"""A frontier is a space HELD OPEN, not a space spent.

Until 2026-09-05 a `frontier` axis was deleted from the holder's plan the
moment it minted a stub, and nothing anywhere recorded that the minted room
was a placeholder. So a later plan wanting that place had no way to say
"that one" and built a rival beside it. Measured on the Harrowmere replay
(2026-09-03): the axis "upland road" off the gate minted `bridge_road_2`
beside the real Bridge Road, and the Director, shown a stub called "bridge
road", minted `upland_road` next to it; `slate_lane_2`, `market_square_2`
and `market_square_3` were the same class, and **those were every duplicate
room of that run**.

The rule these tests hold to: *a minted stub is the space the plan reserved,
standing in until a plan claims it; claiming renames the room and never
mints a second one.*
"""

from __future__ import annotations

import json
import time

import pytest

from world.structure import (
    apply_frontier_mutations, claim_frontier_spaces, frontier_spaces,
    mint_frontier, plant_structure, planned_room_spellings,
    prepare_frontier_expansion, structure_warnings)


#: The replay's own structure grammar, verbatim from its `world` row.
HARROWMERE = {"key": "harrowmere", "max_planned": 100, "grammar": [
    {"kind": "road", "names": ["upland road", "bridge road"],
     "purposes": ["approach", "crossing"]},
    {"kind": "lane", "names": ["stone lane", "slate lane"],
     "purposes": ["dwelling"]},
]}


def _chat(temp_db, name="Frontier"):
    return temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        (name, "", time.time()))


def _plant(temp_db, cid, frontier=("upland road",)):
    """One planned room holding one frontier space open."""
    plant_structure(cid, HARROWMERE, {"gate": {
        "name": "Upland Gate", "purpose": "gatehouse", "adjacent": [],
        "frontier": list(frontier)}})
    return {"rooms": {"gate": {"name": "Upland Gate", "adjacent": []}},
            "positions": {"Player": "gate"}}


def _expand(temp_db, cid, scene):
    scene, mutations = prepare_frontier_expansion(cid, scene)
    with temp_db.transaction():
        apply_frontier_mutations(cid, None, mutations)
    return scene


def _row(temp_db, cid, uid):
    return temp_db.q("SELECT name,aliases,payload FROM room_registry WHERE "
                     "chat_id=? AND room_uid=?", (cid, uid), one=True)


def _planned(temp_db, cid, uid):
    return json.loads(_row(temp_db, cid, uid)["payload"])["planned"]


# -- 1. the axis is not lost when it mints ------------------------------------

def test_a_stub_remembers_the_axis_it_stands_for(temp_db):
    """The fact the engine already had and threw away."""
    cid = _chat(temp_db)
    scene = _expand(temp_db, cid, _plant(temp_db, cid))
    stub = next(uid for uid in scene["rooms"] if uid != "gate")

    spec = _planned(temp_db, cid, stub)
    assert spec["provisional"] is True
    assert spec["frontier_of"] == {"room": "gate", "axis": "upland road"}
    # And the HOLDER records that the axis is standing rather than spent.
    assert _planned(temp_db, cid, "gate")["frontier_standing"] == {
        "upland road": stub}
    assert _planned(temp_db, cid, "gate")["frontier"] == []


def test_the_room_can_see_the_open_spaces(temp_db):
    """A planner that cannot see the slot plans beside it."""
    cid = _chat(temp_db)
    scene = _plant(temp_db, cid)

    open_now = frontier_spaces(cid)
    assert open_now == [{"room": "gate", "room_name": "Upland Gate",
                         "structure": "harrowmere", "axis": "upland road",
                         "state": "open"}]

    scene = _expand(temp_db, cid, scene)
    stub = next(uid for uid in scene["rooms"] if uid != "gate")
    standing = frontier_spaces(cid)
    assert [(r["room"], r["axis"], r["state"], r.get("stub", "")) for r in
            standing] == [
        # The gate's space now has a stub standing in it ...
        ("gate", "upland road", "provisional", stub),
        # ... and the stub holds the next space open, one ring further out.
        (stub, "upland road", "open", "")]


# -- 2 and 3. a claim renames in place, and the old name survives -------------

def test_an_unvisited_stub_claimed_by_a_later_plan_is_the_same_room(temp_db):
    cid = _chat(temp_db)
    scene = _expand(temp_db, cid, _plant(temp_db, cid))
    stub = next(uid for uid in scene["rooms"] if uid != "gate")
    was = _row(temp_db, cid, stub)["name"]

    rooms, plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Weavers' Guildhall", "purpose": "guild business",
        "adjacent": [], "frontier": [],
        "claims": {"room": "gate", "axis": "upland road"}}}, scene=scene)
    assert errors == []
    # THE SAME ROOM: rekeyed onto the stub's uid, never a second one.
    assert set(rooms) == {stub}
    plant_structure(cid, HARROWMERE, rooms, claims=plan)

    row = _row(temp_db, cid, stub)
    assert row["name"] == "Weavers' Guildhall"
    assert was in json.loads(row["aliases"])
    assert _planned(temp_db, cid, stub)["purpose"] == "guild business"
    # The stub's way back to the gate survived a claim that did not name it.
    assert [e["to"] for e in _planned(temp_db, cid, stub)["adjacent"]] == ["gate"]
    # And no longer provisional, so the space is filled.
    assert "provisional" not in _planned(temp_db, cid, stub)
    assert frontier_spaces(cid) == []


def test_the_old_name_still_resolves_to_the_room_after_the_claim(temp_db):
    """The alias is the whole point: a Director still saying the old name
    must reach the room, or the rename mints the very duplicate the claim
    exists to close."""
    cid = _chat(temp_db)
    scene = _expand(temp_db, cid, _plant(temp_db, cid))
    stub = next(uid for uid in scene["rooms"] if uid != "gate")
    was = _row(temp_db, cid, stub)["name"]

    rooms, plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Weavers' Guildhall", "adjacent": [],
        "claims": {"room": "gate", "axis": "upland road"}}}, scene=scene)
    plant_structure(cid, HARROWMERE, rooms, claims=plan)

    spellings = planned_room_spellings(cid)
    from world.spatial import normalize_room_id
    assert spellings[normalize_room_id(was)] == stub
    assert spellings[normalize_room_id("Weavers' Guildhall")] == stub


# -- 4. a room somebody has been in keeps its name ----------------------------

def test_a_visited_stub_keeps_its_name_and_takes_the_rest(temp_db):
    cid = _chat(temp_db)
    scene = _expand(temp_db, cid, _plant(temp_db, cid))
    stub = next(uid for uid in scene["rooms"] if uid != "gate")
    was = _row(temp_db, cid, stub)["name"]
    # The story has been in it: the Director furnished it, which is the beat
    # a room stops being nobody's.
    scene["rooms"][stub]["desc"] = "A rutted track between drystone walls."

    rooms, plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Weavers' Guildhall", "purpose": "guild business",
        "extent": {"w": 8, "d": 12}, "frontier": ["mill lane"],
        "adjacent": [], "claims": {"room": "gate", "axis": "upland road"}}},
        scene=scene)
    assert errors == []
    plant_structure(cid, HARROWMERE, rooms, claims=plan)

    row = _row(temp_db, cid, stub)
    assert row["name"] == was, "a name is what the player knows the place by"
    assert "Weavers' Guildhall" in json.loads(row["aliases"])
    spec = _planned(temp_db, cid, stub)
    assert spec["purpose"] == "guild business"
    assert spec["extent"] == {"w": 8, "d": 12}
    assert spec["frontier"] == ["mill lane"]
    record, = plan["claims"]
    assert (record["kept_name"], record["renamed"]) == (True, False)


def test_a_stub_a_body_stands_in_right_now_keeps_its_name(temp_db):
    cid = _chat(temp_db)
    scene = _expand(temp_db, cid, _plant(temp_db, cid))
    stub = next(uid for uid in scene["rooms"] if uid != "gate")
    was = _row(temp_db, cid, stub)["name"]
    scene["positions"]["Player"] = stub

    rooms, plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Weavers' Guildhall", "adjacent": [],
        "claims": {"room": "gate", "axis": "upland road"}}}, scene=scene)
    plant_structure(cid, HARROWMERE, rooms, claims=plan)

    assert _row(temp_db, cid, stub)["name"] == was


# -- first claim wins ---------------------------------------------------------

def test_a_second_claim_on_a_filled_space_is_refused_naming_the_holder(temp_db):
    cid = _chat(temp_db)
    scene = _expand(temp_db, cid, _plant(temp_db, cid))
    stub = next(uid for uid in scene["rooms"] if uid != "gate")

    rooms, plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Weavers' Guildhall", "adjacent": [],
        "claims": {"room": "gate", "axis": "upland road"}}}, scene=scene)
    assert errors == []
    plant_structure(cid, HARROWMERE, rooms, claims=plan)

    _rooms, _plan, errors = claim_frontier_spaces(cid, {"almshouse": {
        "name": "Almshouse", "adjacent": [],
        "claims": {"room": "gate", "axis": "upland road"}}}, scene=scene)
    assert len(errors) == 1
    assert "gate" in errors[0] and stub in errors[0]
    assert "cannot be two things" in errors[0]


def test_two_rooms_of_one_plan_cannot_claim_the_same_space(temp_db):
    cid = _chat(temp_db)
    scene = _expand(temp_db, cid, _plant(temp_db, cid))
    claim = {"room": "gate", "axis": "upland road"}
    _rooms, _plan, errors = claim_frontier_spaces(cid, {
        "almshouse": {"name": "Almshouse", "adjacent": [], "claims": claim},
        "guildhall": {"name": "Guildhall", "adjacent": [], "claims": claim},
    }, scene=scene)
    assert len(errors) == 1 and "cannot be two things" in errors[0]


def test_a_claim_on_a_space_that_does_not_exist_says_what_the_room_holds(temp_db):
    cid = _chat(temp_db)
    scene = _plant(temp_db, cid)
    _rooms, _plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Guildhall", "adjacent": [],
        "claims": {"room": "gate", "axis": "the sea"}}}, scene=scene)
    assert len(errors) == 1
    assert "'upland road'" in errors[0]

    _rooms, _plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Guildhall", "adjacent": [],
        "claims": {"room": "nowhere", "axis": "upland road"}}}, scene=scene)
    assert len(errors) == 1 and "holds no plan" in errors[0]


def test_a_claim_on_a_space_nothing_has_minted_into_fills_it_directly(temp_db):
    """Nobody has stood at the gate, so no stub stands there -- and the
    plan's own room fills the space with no rename at all."""
    cid = _chat(temp_db)
    _plant(temp_db, cid)

    rooms, plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Weavers' Guildhall", "purpose": "guild business",
        "adjacent": [], "frontier": [],
        "claims": {"room": "gate", "axis": "upland road"}}}, scene={})
    assert errors == [] and set(rooms) == {"guildhall"}
    plant_structure(cid, HARROWMERE, rooms, claims=plan)

    gate = _planned(temp_db, cid, "gate")
    assert gate["frontier"] == []
    assert gate["frontier_standing"] == {"upland road": "guildhall"}
    assert [e["to"] for e in gate["adjacent"]] == ["guildhall"]
    assert [e["to"] for e in _planned(temp_db, cid, "guildhall")["adjacent"]] \
        == ["gate"]
    assert frontier_spaces(cid) == []


def test_a_claim_carries_the_operations_own_edges_with_it(temp_db):
    """The claiming room's key is discarded; every edge inside the same plan
    that names it follows the claim onto the room's real uid."""
    cid = _chat(temp_db)
    scene = _expand(temp_db, cid, _plant(temp_db, cid))
    stub = next(uid for uid in scene["rooms"] if uid != "gate")

    rooms, _plan, errors = claim_frontier_spaces(cid, {
        "guildhall": {"name": "Guildhall", "adjacent": [],
                      "claims": {"room": "gate", "axis": "upland road"}},
        "yard": {"name": "Guild Yard",
                 "adjacent": [{"to": "guildhall", "barrier": "open_door"}]},
    }, scene=scene)
    assert errors == [] and set(rooms) == {stub, "yard"}
    assert [e["to"] for e in rooms["yard"]["adjacent"]] == [stub]


# -- 5. the frontier keeps moving ---------------------------------------------

def test_a_stub_inherits_an_onward_axis_and_a_bearing_does_not(temp_db):
    _uid, spec = mint_frontier(HARROWMERE, "gate", "upland road", "1:h", [])
    assert spec["frontier"] == ["upland road"]
    # A bearing is not the name of a place, so it cannot be the name of what
    # lies beyond the place it named (ONE RULE, ONE OWNER: frontier_refusal).
    _uid, spec = mint_frontier(HARROWMERE, "square", "north", "1:h", [])
    assert spec["frontier"] == []


def test_twenty_beats_of_walking_open_a_bounded_number_of_rooms(temp_db):
    """MEASURE THE FRONTIER. One body walks the road it is handed, one room
    per beat, for twenty beats. The chain advances one stub per beat and
    stops the moment the walking does -- nothing mints ahead of a body."""
    cid = _chat(temp_db)
    scene = _plant(temp_db, cid)
    here = "gate"
    seen = [here]
    for _beat in range(20):
        scene["positions"]["Player"] = here
        scene = _expand(temp_db, cid, scene)
        onward = [e["to"] for e in scene["rooms"][here].get("adjacent") or ()
                  if e.get("to") not in seen]
        if not onward:
            break
        here = onward[0]
        seen.append(here)

    assert len(seen) == 21, "one room per beat walked, and not one more"
    assert len(scene["rooms"]) == 21
    # Every segment of one axis is that axis's name with an ordinal, so the
    # Director never sees two rooms spelled alike.
    names = [scene["rooms"][uid]["name"] for uid in seen[1:]]
    assert names[0] == "Upland Road"
    assert names[1] == "Upland Road 2"
    assert len(set(names)) == len(names)


def test_the_chain_stops_at_the_structures_max_planned(temp_db):
    """The cap that already bounds this is the only cap: `max_planned`."""
    cid = _chat(temp_db)
    plant_structure(cid, dict(HARROWMERE, max_planned=4), {"gate": {
        "name": "Upland Gate", "adjacent": [], "frontier": ["upland road"]}})
    scene = {"rooms": {"gate": {"name": "Upland Gate", "adjacent": []}},
             "positions": {"Player": "gate"}}
    here = "gate"
    seen = [here]
    for _beat in range(20):
        scene["positions"]["Player"] = here
        scene = _expand(temp_db, cid, scene)
        onward = [e["to"] for e in scene["rooms"][here].get("adjacent") or ()
                  if e.get("to") not in seen]
        if not onward:
            break
        here = onward[0]
        seen.append(here)
    assert len(scene["rooms"]) == 4
    # And the axis it could not mint is RETAINED, never silently dropped.
    assert frontier_spaces(cid)[-1]["state"] == "open"


# -- unchanged behaviour ------------------------------------------------------

def test_an_axis_naming_an_existing_room_still_draws_an_edge_and_mints_nothing(
        temp_db):
    cid = _chat(temp_db)
    plant_structure(cid, HARROWMERE, {
        "square": {"name": "Market Square", "adjacent": [], "frontier": []},
        "lane": {"name": "Stone Lane", "adjacent": [],
                 "frontier": ["market square"]}})
    scene = {"rooms": {"lane": {"name": "Stone Lane", "adjacent": []},
                       "square": {"name": "Market Square", "adjacent": []}},
             "positions": {"Player": "lane"}}
    scene = _expand(temp_db, cid, scene)

    assert set(scene["rooms"]) == {"lane", "square"}
    assert {e["to"] for e in scene["rooms"]["lane"]["adjacent"]} == {"square"}
    # The space is FILLED by a real plan, so it is not a space any more.
    assert frontier_spaces(cid) == []
    assert _planned(temp_db, cid, "lane")["frontier_standing"] == {
        "market square": "square"}


def test_a_refused_frontier_is_still_retained_and_reported(temp_db):
    cid = _chat(temp_db)
    plant_structure(cid, HARROWMERE, {"gate": {
        "name": "Upland Gate", "adjacent": [],
        "frontier": ["the village street of Ambry beyond the gate"]}})
    scene = {"rooms": {"gate": {"name": "Upland Gate", "adjacent": []}},
             "positions": {"Player": "gate"}}
    scene = _expand(temp_db, cid, scene)

    assert set(scene["rooms"]) == {"gate"}
    spec = _planned(temp_db, cid, "gate")
    assert spec["frontier"] == ["the village street of Ambry beyond the gate"]
    space, = frontier_spaces(cid)
    assert space["state"] == "open" and "describes what lies" in space["unmintable"]
    assert any("describes what lies" in w for w in structure_warnings(
        HARROWMERE, {"gate": spec}))


def test_a_structure_with_no_frontiers_is_untouched(temp_db):
    """Byte-identical: a plan that reserves nothing is planted, read and
    expanded exactly as it was before a space could be claimed."""
    cid = _chat(temp_db)
    plant_structure(cid, HARROWMERE, {
        "square": {"name": "Market Square", "purpose": "trade",
                   "adjacent": [{"to": "lane", "barrier": "open_door"}]},
        "lane": {"name": "Stone Lane", "purpose": "dwelling",
                 "adjacent": [{"to": "square", "barrier": "open_door"}]}})
    before = {uid: dict(_row(temp_db, cid, uid)) for uid in ("square", "lane")}
    scene = {"rooms": {"square": {"name": "Market Square", "adjacent": []}},
             "positions": {"Player": "square"}}

    scene, mutations = prepare_frontier_expansion(cid, scene)
    assert mutations == []
    assert frontier_spaces(cid) == []
    assert {uid: dict(_row(temp_db, cid, uid))
            for uid in ("square", "lane")} == before
    for uid in ("square", "lane"):
        spec = _planned(temp_db, cid, uid)
        assert "provisional" not in spec and "frontier_standing" not in spec
        assert "frontier_of" not in spec


@pytest.mark.parametrize("shape", [
    {"room": "gate"}, {"axis": "upland road"}, "gate", {"room": "", "axis": ""}])
def test_a_claim_names_both_ids_or_it_is_refused(shape):
    from story.plot_packages import _plan_claim
    with pytest.raises(ValueError):
        _plan_claim("guildhall", shape)


# -- the whole way through, as the Room actually reaches it -------------------

def _package_story(temp_db):
    """A story standing at a gate whose frontier has already minted a stub."""
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Claims", "A gate at dusk.", time.time()))
    plant_structure(cid, HARROWMERE, {"gate": {
        "name": "Upland Gate", "purpose": "gatehouse", "adjacent": [],
        "frontier": ["upland road"]}})
    scene = {"location": "Gate", "entities": {}, "attire": {},
             "rooms": {"gate": {"name": "Upland Gate", "desc": "Two towers.",
                                "adjacent": []}},
             "positions": {"Wren Ashby": "gate"}}
    scene, mutations = prepare_frontier_expansion(cid, scene)
    with temp_db.transaction():
        apply_frontier_mutations(cid, None, mutations)
    stub = next(uid for uid in scene["rooms"] if uid != "gate")
    temp_db.wset(cid, "scene", scene)
    for idx in range(3):
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                   "VALUES(?,?,?,?)", (cid, idx, "", time.time()))
    return cid, stub


def test_a_published_package_claims_the_space_instead_of_planting_beside_it(
        temp_db):
    """The whole seam: the Room reads the open space out of its own room
    tools, plans a room that CLAIMS it, and what publishes is the same room
    under a new name -- not a rival beside it."""
    from story.plot_packages import (draft_operation, get_package,
                                     new_package, preview_package,
                                     publish_package, validate_package)
    from story.room_tools import _t_inspect_structures

    cid, stub = _package_story(temp_db)
    spaces = _t_inspect_structures(cid, None)["frontiers"]
    space = next(row for row in spaces if row["state"] == "provisional")
    assert (space["room"], space["axis"], space["stub"]) == (
        "gate", "upland road", stub)

    pkg = new_package(cid, title="The Guild", premise="Weavers move in.")
    draft_operation(cid, pkg["uid"], {
        "op": "plan_rooms", "structure": {"key": "harrowmere"},
        "rooms": {"guildhall": {
            "name": "Weavers' Guildhall", "purpose": "guild business",
            "extent": {"w": 10, "d": 14},
            "claims": {"room": space["room"], "axis": space["axis"]}}}})
    preview = preview_package(cid, pkg["uid"])
    claimed, = [c for c in preview["changes"] if c.get("claimed")][0]["claimed"]
    assert claimed["room"] == stub and claimed["outcome"] == "renamed"
    assert preview["errors"] == []

    validate_package(cid, pkg["uid"])
    publish_package(cid, pkg["uid"],
                    expected_revision=get_package(cid, pkg["uid"])["revision"])

    rooms = {row["room_uid"] for row in temp_db.q(
        "SELECT room_uid FROM room_registry WHERE chat_id=?", (cid,))}
    assert rooms == {"gate", stub}, "no second room beside the space"
    assert _row(temp_db, cid, stub)["name"] == "Weavers' Guildhall"
    assert _planned(temp_db, cid, stub)["extent"] == {"w": 10, "d": 14}


def test_a_claim_the_registry_renamed_reaches_the_live_scene(temp_db):
    """A registry-only rename would be written back by the next commit: the
    registry's name is projected FROM the scene. While a room is still the
    plan's prose-free stub the plan owns its name, so the fringe carries the
    claim into the live scene the beat after it lands."""
    from world.structure import materialize_planned_fringe

    cid, stub = _package_story(temp_db)
    scene = temp_db.wget(cid, "scene")
    rooms, plan, errors = claim_frontier_spaces(cid, {"guildhall": {
        "name": "Weavers' Guildhall", "purpose": "guild business",
        "adjacent": [], "claims": {"room": "gate", "axis": "upland road"}}},
        scene=scene)
    assert errors == []
    plant_structure(cid, HARROWMERE, rooms, claims=plan)

    scene, _added = materialize_planned_fringe(cid, scene)
    assert scene["rooms"][stub]["name"] == "Weavers' Guildhall"
    assert scene["rooms"][stub]["purpose"] == "guild business"
    # And a room the story has described is its own: the plan does not
    # rewrite what a beat has already said.
    scene["rooms"][stub]["desc"] = "Looms behind shutters."
    scene["rooms"][stub]["name"] = "The Weaving Hall"
    scene, _added = materialize_planned_fringe(cid, scene)
    assert scene["rooms"][stub]["name"] == "The Weaving Hall"


def test_a_claim_that_cannot_be_honoured_plants_nothing(temp_db):
    """The world can move between the preview that passed a claim and the
    publish that applies it. A room planted beside the space it meant to
    fill is the entire defect, so a refused claim plants nothing at all."""
    from story.plot_packages import _apply_plan_rooms, _shape_plan_rooms

    cid, stub = _package_story(temp_db)
    op = dict(_shape_plan_rooms({
        "structure": {"key": "harrowmere"},
        "rooms": {"guildhall": {
            "name": "Weavers' Guildhall",
            "claims": {"room": "gate", "axis": "upland road"}}}}),
        op="plan_rooms")
    # Somebody else fills the space first.
    rooms, plan, _e = claim_frontier_spaces(cid, {"almshouse": {
        "name": "Almshouse", "adjacent": [],
        "claims": {"room": "gate", "axis": "upland road"}}}, scene={})
    plant_structure(cid, HARROWMERE, rooms, claims=plan)

    out = _apply_plan_rooms(cid, None, op, 0)
    assert out["rooms"] == [] and out["refused"]
    assert {row["room_uid"] for row in temp_db.q(
        "SELECT room_uid FROM room_registry WHERE chat_id=?", (cid,))} \
        == {"gate", stub}
