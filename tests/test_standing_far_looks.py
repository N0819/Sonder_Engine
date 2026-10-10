"""A place that already stands takes a far look, and what somebody else
wrote stands (`plot_packages.set_far_looks`, `landscape.
standing_looks_wanted`, `room_sketch.looks_offered`).

The owner's go-ahead, 2026-10-09 ("far looks everywhere"): the far-looks
round gave a planned place a far look the far layer says in place of "open
ground" or "a building", but only places a plan wrote since 2026-10-08 had
one -- a room the Director minted in a beat, and every place of an older
story, read by their ground. Measured before (the stored scenes, a
stranger's eye): chat 166's bodies were told 113 far places and 0 by a
look; its 34 rooms held 20 declared places and none had one; Kirinoura's
7 declared places none.

So: a Room operation of its own that writes a far look onto a place that
already stands (`plan_rooms` refuses a described room as a retcon) under
its own grant, by the seed-only rule -- it fills a place that reads by its
ground, or replaces its own unchanged word, and a look the plan seeded, a
beat or the opening wrote, or a host wrote or cleared stands; a bounded pass
in the planting sketch that is handed the nearest places wanting one; a
drafted town's room shape that carries one through the closure; and a room
author that gives one to an outdoor place nobody planned. Hand-made scenes;
the places and words are illustrations, not the rule.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import wset
from tests.test_far_looks import _chat, _commit_beat, _places, _valley


# --------------------------------------------------------------------------
# The rule: what the Room may write over, and what stands
# --------------------------------------------------------------------------

def _town():
    """A harbour seen from an inn's doorway: the quay and the square open,
    a covered market sheltered, the inn and a chandlery on the square, a
    cellar under the inn that declares no exposure, and the inside of a boat
    moored at the quay. Each room joins the next by an open way."""
    def room(name, exposure=None, **more):
        out = {"name": name, "desc": "%s, as the story has seen it." % name,
               "adjacent": []}
        if exposure:
            out["exposure"] = exposure
        out.update(more)
        return out
    rooms = {
        "inn": room("The Inn", "enclosed"),
        "inn_kitchen": room("The Inn Kitchen", "enclosed"),
        "square": room("The Square", "open"),
        "market": room("The Market", "sheltered"),
        "quay": room("The Quay", "open"),
        "chandlery": room("The Chandlery", "enclosed"),
        "cellar": room("The Cellar"),
        "hold": room("The Hold", "enclosed", parent_entity="boat"),
    }
    def join(a, b, **edge):
        rooms[a]["adjacent"].append({"to": b, "barrier": "open", **edge})
    join("inn", "square", dir="s")
    join("inn", "inn_kitchen", dir="n", barrier="open_door")
    join("square", "market", dir="e")
    join("square", "chandlery", dir="w")
    join("market", "quay", dir="e")
    join("inn", "cellar", vertical="down")
    return {"rooms": rooms, "positions": {"Ada": "inn"}, "stations": {},
            "entities": {"boat": {"name": "the boat", "kind": "vehicle",
                                  "interior_rooms": ["hold"]}},
            "day_phase": "afternoon", "weather": {"air": "clear"}}


def test_a_place_reads_by_its_ground_until_the_room_writes_and_then_by_its_own_word():
    from world.landscape import WRITTEN_LOOKS_KEY, room_look_writable
    sc = _town()
    assert room_look_writable(sc, "quay") == (True, "none")
    sc["rooms"]["quay"]["far_look"] = "a stone quay with mooring posts"
    sc[WRITTEN_LOOKS_KEY] = {"quay": "a stone quay with mooring posts"}
    # Its own word, unchanged since: the Room may say it again.
    assert room_look_writable(sc, "quay") == (True, "own")


def test_a_look_somebody_else_wrote_or_cleared_stands():
    """THE SEED-ONLY RULE (`structure.PLAN_SEEDED_FIELDS`): the Room's look
    never goes back over a beat's change, the plan's word, the opening's or
    a host's edit or clear."""
    from world.landscape import LOOK_WRITE_REASONS, WRITTEN_LOOKS_KEY, room_look_writable
    from world.structure import LAID_LOOKS_KEY
    sc = _town()
    # A look nobody recorded -- the plan's, a beat's, the opening's.
    sc["rooms"]["square"]["far_look"] = "a cobbled square"
    assert room_look_writable(sc, "square") == (False, "standing")
    # The Room wrote one, and a beat changed it since.
    sc["rooms"]["quay"]["far_look"] = "a burned-out quay"
    sc[WRITTEN_LOOKS_KEY] = {"quay": "a stone quay with mooring posts"}
    assert room_look_writable(sc, "quay") == (False, "changed")
    # A host wrote or cleared it by hand.
    sc[WRITTEN_LOOKS_KEY]["market"] = ""
    assert room_look_writable(sc, "market") == (False, "host")
    # The plan laid one and somebody cleared it.
    sc[LAID_LOOKS_KEY] = {"chandlery": "a narrow tarred shop"}
    assert room_look_writable(sc, "chandlery") == (False, "cleared")
    # No far eye sees a room that declares no exposure, or the inside of a
    # body; a room the scene does not hold is no standing place.
    assert room_look_writable(sc, "cellar") == (False, "undeclared")
    assert room_look_writable(sc, "hold") == (False, "inside")
    assert room_look_writable(sc, "nowhere") == (False, "absent")
    for rid in sc["rooms"]:
        assert room_look_writable(sc, rid)[1] in LOOK_WRITE_REASONS


def test_a_part_of_the_map_follows_the_same_rule():
    from world.landscape import region_look_writable
    assert region_look_writable({"name": "Fen"}) == (True, "none")
    assert region_look_writable({"name": "Fen", "far_look": "reed flats",
                                 "far_look_written": "reed flats"}) == (True, "own")
    assert region_look_writable({"name": "Fen", "far_look": "reed flats",
                                 "far_look_laid": "reed flats"}) == (False, "standing")
    assert region_look_writable({"name": "Fen", "far_look_laid": "reed flats"}) == \
        (False, "cleared")
    assert region_look_writable({"name": "Fen", "far_look_written": ""}) == (False, "host")


# --------------------------------------------------------------------------
# The operation
# --------------------------------------------------------------------------

def _story_with(db, scene):
    cid = _chat(db)
    wset(cid, "scene", scene)
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "", time.time()))
    return cid


def _publish(cid, ops, *, created_by="writers_room"):
    """Draft, validate and publish one package of ``ops``; the preview."""
    from story.plot_packages import (draft_operation, new_package,
                                     preview_package, publish_package,
                                     validate_package)
    pkg = new_package(cid, title="Seen from afar", created_by=created_by)
    for op in ops:
        draft_operation(cid, pkg["uid"], op)
    preview = preview_package(cid, pkg["uid"])
    verdict = validate_package(cid, pkg["uid"])
    if verdict["ok"]:
        publish_package(cid, pkg["uid"], expected_revision=verdict["at_revision"])
    return preview, verdict


def test_a_described_room_takes_a_far_look_where_a_plan_would_be_a_retcon(temp_db):
    """`plan_rooms` refuses a room the story has described ("a retcon, not a
    plan"), so a room the Director minted, or one an older story furnished,
    could take no look from the Room at all. `set_far_looks` writes how it
    reads from far off and nothing else, and the far layer says it."""
    from story.plot_packages import _preview_plan_rooms, _shape_plan_rooms, _world_snapshot
    from world.landscape import WRITTEN_LOOKS_KEY
    cid = _story_with(temp_db, _valley())
    world = _world_snapshot(cid)
    refused = _preview_plan_rooms(cid, None, _shape_plan_rooms({
        "structure": {"key": "vale", "name": "Vale"},
        "rooms": {"meadow": {"name": "The Meadow", "far_look": "a long hay meadow"}}}),
        world)
    assert any("retcon" in e for e in refused["errors"])
    preview, verdict = _publish(cid, [{"op": "set_far_looks",
                                       "rooms": {"meadow": "a long hay meadow"}}])
    assert verdict["ok"] and not preview["errors"], preview
    assert preview["changes"][0]["rooms"] == {"meadow": "a long hay meadow"}
    scene = temp_db.wget(cid, "scene")
    assert scene["rooms"]["meadow"]["far_look"] == "a long hay meadow"
    assert scene[WRITTEN_LOOKS_KEY] == {"meadow": "a long hay meadow"}
    # The far layer says it in place of the ground.
    line = [p for p in _places(scene) if p["room"] == "meadow"][0]
    assert line["look"] == "a long hay meadow"


def test_the_operation_keeps_what_somebody_else_wrote_and_says_so(temp_db):
    sc = _valley()
    sc["rooms"]["orchard"]["far_look"] = "rows of apple trees"      # a beat's
    sc["rooms"]["mill"]["exposure"] = ""                              # undeclared
    cid = _story_with(temp_db, sc)
    preview, verdict = _publish(cid, [{"op": "set_far_looks", "rooms": {
        "orchard": "a stand of pear trees", "mill": "a squat stone mill",
        "meadow": "a long hay meadow"}}])
    assert verdict["ok"], preview
    change = preview["changes"][0]
    assert change["rooms"] == {"meadow": "a long hay meadow"}
    assert change["kept"] == {"orchard": "standing", "mill": "undeclared"}
    assert any("'orchard' keeps the far look it has" in w for w in preview["warnings"])
    assert any("'mill' takes no far look: it declares no exposure" in w
               for w in preview["warnings"])
    rooms = temp_db.wget(cid, "scene")["rooms"]
    assert rooms["orchard"]["far_look"] == "rows of apple trees"
    assert "far_look" not in rooms["mill"]
    # Its own word, unchanged, it may say again; a beat's change since stands.
    _publish(cid, [{"op": "set_far_looks", "rooms": {"meadow": "a mown hay meadow"}}])
    assert temp_db.wget(cid, "scene")["rooms"]["meadow"]["far_look"] == "a mown hay meadow"
    scene = temp_db.wget(cid, "scene")
    scene["rooms"]["meadow"]["far_look"] = "a blackened field of stubble"
    temp_db.wset(cid, "scene", scene)
    preview, _ = _publish(cid, [{"op": "set_far_looks",
                                 "rooms": {"meadow": "a mown hay meadow"}}])
    assert preview["changes"][0]["kept"] == {"meadow": "changed"}
    assert temp_db.wget(cid, "scene")["rooms"]["meadow"]["far_look"] == \
        "a blackened field of stubble"


def test_the_inside_of_a_body_and_a_room_nobody_holds_are_refused(temp_db):
    sc = _town()
    cid = _story_with(temp_db, sc)
    preview, verdict = _publish(cid, [{"op": "set_far_looks", "rooms": {
        "hold": "a dark hold", "nowhere_at_all": "a field"}}])
    assert not verdict["ok"]
    assert any("'hold' is the inside of a body" in e for e in preview["errors"])
    assert any("'nowhere_at_all' exists nowhere" in e for e in preview["errors"])
    from story.plot_packages import OPERATIONS
    with pytest.raises(ValueError):
        OPERATIONS["set_far_looks"]["shape"]({"rooms": {"quay": "   "}})
    with pytest.raises(ValueError):
        OPERATIONS["set_far_looks"]["shape"]({})


def test_a_planned_stub_takes_its_look_into_its_plan_and_the_fringe_agrees(temp_db):
    """A stub's look is the plan's (`PLAN_SEEDED_FIELDS`): the operation
    writes the stub AND seeds the plan, so the fringe's record of what the
    stub took agrees, a stub in another frame or not yet in the scene reads
    it, and a plan that later says something new is laid as before."""
    from tests.test_far_looks import _plan_meadow
    from world.structure import LAID_LOOKS_KEY, registry_rows
    cid = _chat(temp_db)
    _plan_meadow(cid, "")
    temp_db.wset(cid, "scene", {
        "rooms": {"yard": {"name": "The Yard", "desc": "A yard.", "exposure": "open",
                           "adjacent": [{"to": "meadow", "barrier": "open"}]}},
        "positions": {"Ada": "yard"}, "entities": {}})
    sc = _commit_beat(temp_db, cid, 1, {})
    assert sc["rooms"]["meadow"].get("planned") and "far_look" not in sc["rooms"]["meadow"]
    preview, verdict = _publish(cid, [{"op": "set_far_looks",
                                       "rooms": {"meadow": "a long hay meadow"}}])
    assert verdict["ok"], preview
    assert registry_rows(cid)["meadow"]["planned"]["far_look"] == "a long hay meadow"
    sc = _commit_beat(temp_db, cid, 2, {})
    assert sc["rooms"]["meadow"]["far_look"] == "a long hay meadow"
    assert sc[LAID_LOOKS_KEY] == {"meadow": "a long hay meadow"}
    # A beat burns it; the next commit keeps the burn.
    sc = _commit_beat(temp_db, cid, 3, {"rooms": {"meadow": {
        "name": "The Meadow", "far_look": "a blackened field of stubble"}}})
    sc = _commit_beat(temp_db, cid, 4, {})
    assert sc["rooms"]["meadow"]["far_look"] == "a blackened field of stubble"
    # A planned room the scene does not hold yet takes it into its plan.
    from world.structure import plant_structure
    plant_structure(cid, {"key": "fen", "max_planned": 8},
                    {"staithe": {"name": "Staithe", "purpose": "boats", "exposure": "open"}})
    preview, verdict = _publish(cid, [{"op": "set_far_looks",
                                       "rooms": {"staithe": "a timber staithe on stilts"}}])
    assert verdict["ok"], preview
    assert registry_rows(cid)["staithe"]["planned"]["far_look"] == "a timber staithe on stilts"


def test_a_plans_look_the_host_cleared_is_not_written_back(temp_db):
    from tests.test_far_looks import _plan_meadow
    cid = _chat(temp_db)
    _plan_meadow(cid, "a long hay meadow")
    temp_db.wset(cid, "scene", {
        "rooms": {"yard": {"name": "The Yard", "desc": "A yard.", "exposure": "open",
                           "adjacent": [{"to": "meadow", "barrier": "open"}]}},
        "positions": {"Ada": "yard"}, "entities": {}})
    sc = _commit_beat(temp_db, cid, 1, {})
    sc["rooms"]["meadow"].pop("far_look")          # the host clears it
    temp_db.wset(cid, "scene", sc)
    preview, _ = _publish(cid, [{"op": "set_far_looks",
                                 "rooms": {"meadow": "a mown hay meadow"}}])
    assert preview["changes"][0]["kept"] == {"meadow": "cleared"}
    assert "far_look" not in temp_db.wget(cid, "scene")["rooms"]["meadow"]


def test_a_part_of_the_map_takes_a_look_and_a_hosts_or_a_plans_word_stands(temp_db):
    from story.plot_packages import _apply_plan_rooms, _shape_plan_rooms
    from world.regions import region_registry, set_region_far_look
    cid = _story_with(temp_db, _valley())
    _apply_plan_rooms(cid, None, _shape_plan_rooms({
        "structure": {"key": "vale", "name": "The Vale"},
        "rooms": {"barn": {"name": "Barn", "exposure": "enclosed"}}}), 0)
    preview, verdict = _publish(cid, [{"op": "set_far_looks",
                                       "regions": {"vale": "hedged fields and copses"}}])
    assert verdict["ok"], preview
    entry = region_registry(cid, None)["vale"]
    assert entry["far_look"] == entry["far_look_written"] == "hedged fields and copses"
    # The host edits it: a host's word, and the Room never writes over it.
    set_region_far_look(cid, None, "vale", "a burned waste")
    preview, _ = _publish(cid, [{"op": "set_far_looks",
                                 "regions": {"vale": "hedged fields and copses"}}])
    assert preview["changes"][0]["kept"] == {"vale": "host"}
    assert region_registry(cid, None)["vale"]["far_look"] == "a burned waste"
    # A region the plan laid a look on keeps the plan's word.
    _apply_plan_rooms(cid, None, _shape_plan_rooms({
        "structure": {"key": "fen", "name": "The Fen", "far_look": "a grey flat of reed"},
        "rooms": {"staithe": {"name": "Staithe", "exposure": "open"}}}), 1)
    preview, _ = _publish(cid, [{"op": "set_far_looks", "regions": {"fen": "salt marsh"}}])
    assert preview["changes"][0]["kept"] == {"fen": "standing"}
    preview, verdict = _publish(cid, [{"op": "set_far_looks",
                                       "regions": {"nowhere": "salt marsh"}}])
    assert not verdict["ok"] and any("exists nowhere" in e for e in preview["errors"])


def test_a_plans_new_word_for_a_part_of_the_map_replaces_the_rooms_own_look(temp_db):
    """REVIEW F4 (2026-10-09): the Room's look on a part of the map that read
    by its ground only filled a silence, as its look on a planned stub fills
    the stub's plan; a later plan that says the whole of it anew replaces it,
    as a re-plan replaces the stub's. Kept behind the Room's word, the
    plan's look was recorded as laid and never landed, though its own
    preview said it would -- and restating the plan could never lay it.
    A host's word still stands."""
    from story.plot_packages import (_apply_plan_rooms, _preview_plan_rooms,
                                     _shape_plan_rooms, _world_snapshot)
    from world.regions import region_registry, set_region_far_look
    cid = _story_with(temp_db, _valley())
    _apply_plan_rooms(cid, None, _shape_plan_rooms({
        "structure": {"key": "vale", "name": "The Vale"},
        "rooms": {"barn": {"name": "Barn", "exposure": "enclosed"}}}), 0)
    _publish(cid, [{"op": "set_far_looks", "regions": {"vale": "hedged fields and copses"}}])
    replan = _shape_plan_rooms({
        "structure": {"key": "vale", "name": "The Vale",
                      "far_look": "terraced vineyards to the skyline"},
        "rooms": {"byre": {"name": "Byre", "exposure": "enclosed"}}})
    preview = _preview_plan_rooms(cid, None, replan, _world_snapshot(cid))
    said = [c for c in preview["changes"] if c.get("region_far_look")]
    assert said and said[0]["region_far_look"] == "terraced vineyards to the skyline"
    _apply_plan_rooms(cid, None, replan, 1)
    entry = region_registry(cid, None)["vale"]
    assert entry["far_look"] == "terraced vineyards to the skyline"
    # The plan's word now stands against the Room's operation.
    preview, _ = _publish(cid, [{"op": "set_far_looks",
                                 "regions": {"vale": "hedged fields and copses"}}])
    assert preview["changes"][0]["kept"] == {"vale": "changed"}
    # A host's edit is not the Room's word: a plan's first look leaves it.
    cid = _story_with(temp_db, _valley())
    _apply_plan_rooms(cid, None, _shape_plan_rooms({
        "structure": {"key": "vale", "name": "The Vale"},
        "rooms": {"barn": {"name": "Barn", "exposure": "enclosed"}}}), 0)
    set_region_far_look(cid, None, "vale", "a burned waste")
    _apply_plan_rooms(cid, None, replan, 1)
    assert region_registry(cid, None)["vale"]["far_look"] == "a burned waste"


def test_writing_a_look_on_what_stands_is_its_own_grant(temp_db):
    """A package an agent drafted lands only under a grant that covers it:
    `set_far_looks` is a capability of its own (it plans nothing), and the
    total grant covers it as it covers every kind."""
    from story.mandates import MANDATE_CAPABILITIES, grant_mandate
    from story.plot_packages import package_requirements
    assert "set_far_looks" in MANDATE_CAPABILITIES
    assert "set_far_looks" in package_requirements(
        {"operations": [{"op": "set_far_looks", "rooms": {"meadow": "a meadow"}}]})
    cid = _story_with(temp_db, _valley())
    grant_mandate(cid, None, text="Plan rooms.", capabilities=["plan_rooms"])
    _, verdict = _publish(cid, [{"op": "set_far_looks", "rooms": {"meadow": "a meadow"}}],
                          created_by="story_planner")
    assert not verdict["ok"]
    assert any("set_far_looks" in e for e in verdict["errors"]), verdict
    grant_mandate(cid, None, text="Do anything.", capabilities=["everything"])
    _, verdict = _publish(cid, [{"op": "set_far_looks", "rooms": {"meadow": "a meadow"}}],
                          created_by="story_planner")
    assert verdict["ok"], verdict


def test_a_far_look_on_a_far_place_raises_no_reach_warning(temp_db):
    """A far look is for a place seen from far off: a place far from where
    the story stands is its point, never a plan the story cannot reach."""
    sc = _valley()
    cid = _story_with(temp_db, sc)
    from story.plot_packages import _reach_warning, _world_snapshot, operation_rooms
    world = dict(_world_snapshot(cid), occupied={"yard"})
    op = {"op": "set_far_looks", "rooms": {"far_hill": "a bare green hill"}}
    # The room it names is declared, so a room's slice lists the operation...
    assert operation_rooms(op) == {"far_hill"}
    # ...and the reach warning, which is about plans, does not read it.
    assert _reach_warning(cid, world, {"operations": [op]}) is None
    planted = {"op": "director_note", "text": "The hill is where the beacon was.",
               "rooms": ["far_hill"]}
    assert _reach_warning(cid, world, {"operations": [planted]}) is not None


# --------------------------------------------------------------------------
# What wants a look: the standing places near the story
# --------------------------------------------------------------------------

def test_the_places_near_the_story_that_read_by_their_ground_are_found_nearest_first():
    """Declared ground and the buildings on it, within the far layer's reach
    of where the story stands, not only what an eye sees this beat: Ada is
    indoors and looks out on nothing, and the square she steps into should
    not read as "open ground" for want of the beat she stood inside."""
    from world.landscape import standing_looks_wanted
    sc = _town()
    sc["rooms"]["market"]["far_look"] = "a long market roof on posts"
    wanted = standing_looks_wanted(sc, ["inn"], regions={})
    places = [(p["room"], p["ground"], p["hops"]) for p in wanted["places"]]
    # The inn is one building with its kitchen; the market has its look; the
    # cellar declares nothing; the hold is the inside of a body.
    assert places == [("inn", "building", 0), ("square", "open", 1),
                      ("chandlery", "building", 2), ("quay", "open", 3)]
    assert wanted["places"][0]["members"] == ["inn", "inn_kitchen"]
    # A building any of whose rooms carries a look is said by it.
    sc["rooms"]["inn_kitchen"]["far_look"] = "a low whitewashed inn"
    assert "inn" not in [p["room"] for p in standing_looks_wanted(sc, ["inn"])["places"]]
    # A building no open ground fronts is seen from nowhere far.
    lone = _town()
    lone["rooms"]["square"]["exposure"] = "enclosed"
    found = [p["room"] for p in standing_looks_wanted(lone, ["quay"])["places"]]
    assert "chandlery" not in found and "inn" not in found


def _two_level():
    """A shop on a street whose upper room opens onto a terrace a storey
    higher, a lane below the street and a hill beyond the terrace: one
    building, read from the street side as both its rooms and from the
    terrace side as its upper room alone (`building_of` takes in no room
    below a front's floor)."""
    def room(name, exposure, level, *edges, **more):
        return {"name": name, "desc": "%s." % name, "exposure": exposure,
                "level": level, "adjacent": list(edges), **more}
    rooms = {
        "lane": room("The Lane", "open", 0, {"to": "street", "barrier": "open", "dir": "n"}),
        "street": room("The Street", "open", 0,
                       {"to": "shop", "barrier": "open_door", "dir": "n"}),
        "shop": room("The Shop", "enclosed", 0,
                     {"to": "upper", "barrier": "open", "vertical": "up", "way": "stair",
                      "dir": "n"}),
        "upper": room("The Upper Room", "enclosed", 1,
                      {"to": "terrace", "barrier": "open_door", "dir": "n"}),
        "terrace": room("The Terrace", "open", 1,
                        {"to": "hill", "barrier": "open", "dir": "n"}),
        "hill": room("The Hill", "open", 1),
    }
    # Each two rooms from the building: the far layer never answers the
    # rooms beside a body, which its own sight covers.
    return {"rooms": rooms, "positions": {"Ada": "lane", "Bram": "hill"},
            "stations": {}, "entities": {}, "day_phase": "afternoon",
            "weather": {"air": "clear"}}


def _building_look(sc, who):
    """The look of the one building `who` is shown far off, "" for none."""
    from world.landscape import far_places
    from world.scene_memo import scene_read_pass
    with scene_read_pass(sc):
        found = [p for p in far_places(sc, who, known={}) if p["ground"] == "building"]
    assert len(found) == 1, found
    return found[0]["look"]


def test_a_building_is_offered_from_each_front_the_far_layer_reads_it_from():
    """REVIEW F3 (2026-10-09): the pass claimed a building by the first
    front its walk reached and wrote the look there, while the far layer
    builds the mass from whichever front the viewer's walk reaches -- and a
    mass holds no room below its front's floor. A look on the street front
    never reached the terrace side, which read as "a building" for good.
    Offered per front: each side that reads by its ground is offered, and a
    look on it is read from that side."""
    from world.landscape import standing_looks_wanted
    sc = _two_level()
    wanted = {p["room"]: p for p in standing_looks_wanted(sc, ["lane"])["places"]
              if p["ground"] == "building"}
    assert sorted(wanted) == ["shop", "upper"]
    assert wanted["shop"]["members"] == ["shop", "upper"]
    assert wanted["upper"]["members"] == ["upper"]
    # Only the street front looked: the terrace side still reads by its
    # ground, and is still offered.
    sc["rooms"]["shop"]["far_look"] = "a narrow two-storey shop of tarred board"
    assert _building_look(sc, "Ada") == "a narrow two-storey shop of tarred board"
    assert _building_look(sc, "Bram") == ""
    again = [p["room"] for p in standing_looks_wanted(sc, ["lane"])["places"]]
    assert "upper" in again and "shop" not in again
    # Both looked: each side reads its own, and nothing more is wanted.
    sc["rooms"]["upper"]["far_look"] = "a tarred upper storey under a slate roof"
    assert _building_look(sc, "Ada") == "a narrow two-storey shop of tarred board"
    assert _building_look(sc, "Bram") == "a tarred upper storey under a slate roof"
    assert not [p for p in standing_looks_wanted(sc, ["lane"])["places"]
                if p["ground"] == "building"]


def test_ground_that_opens_onto_one_room_alone_shows_that_room_to_no_far_eye():
    """A far walk reaches ground from a room beside it, and a body beside
    the room the ground opens onto has that room in its near field, which
    the far layer never answers: a balcony or a landing off one room alone
    is no way in. Measured on the live play db: a watchtower's top cabin
    fronting its own balcony was offered in three scenes, and no stored
    view (56 walks) read a look there. Ground that touches another room
    too -- a walkway on to the next roof -- is a front as before."""
    from world.landscape import standing_looks_wanted
    def room(name, exposure, level, *edges):
        return {"name": name, "desc": "%s." % name, "exposure": exposure,
                "level": level, "adjacent": list(edges)}
    sc = {"rooms": {
        "square": room("The Square", "open", 0, {"to": "lane", "barrier": "open", "dir": "n"}),
        "lane": room("The Lane", "open", 0, {"to": "tower", "barrier": "open_door", "dir": "n"}),
        "tower": room("The Tower Floor", "enclosed", 0,
                      {"to": "cabin", "barrier": "open", "vertical": "up", "dir": "n"}),
        "cabin": room("The Cabin", "enclosed", 1,
                      {"to": "balcony", "barrier": "closed_door", "dir": "e"}),
        "balcony": room("The Balcony", "open", 1)},
        "positions": {"Ada": "square"}, "entities": {}}
    found = {p["room"]: p for p in standing_looks_wanted(sc, ["square"])["places"]}
    assert found["tower"]["members"] == ["cabin", "tower"]
    assert "cabin" not in found and "balcony" in found
    sc["rooms"]["walkway"] = room("The Walkway", "open", 1,
                                  {"to": "balcony", "barrier": "open", "dir": "w"})
    found = {p["room"]: p for p in standing_looks_wanted(sc, ["square"])["places"]}
    assert found["cabin"]["members"] == ["cabin"]


def test_two_doors_onto_one_street_are_one_building_offered_once():
    """A mass whose other front is already offered is not offered again:
    that front's look is the first its view reads."""
    from world.landscape import standing_looks_wanted
    sc = _two_level()
    sc["rooms"]["back"] = {"name": "The Back Shop", "desc": ".", "exposure": "enclosed",
                           "level": 0, "adjacent": [
                               {"to": "street", "barrier": "open_door", "dir": "s"},
                               {"to": "shop", "barrier": "open", "dir": "w"}]}
    fronts = [p["room"] for p in standing_looks_wanted(sc, ["lane"])["places"]
              if p["ground"] == "building"]
    assert fronts.count("back") + fronts.count("shop") == 1 and "upper" in fronts


def test_a_look_on_one_side_never_takes_the_place_of_a_look_somebody_wrote_on_another():
    """THE SEED-ONLY RULE, from every side: the street front reads its mass
    in order -- the front, then each room in from it -- and says the first
    look it meets. Where the plan wrote one on a back room the stair to the
    upper room comes before, a look written on the upper room would be read
    from the street in place of the plan's word, so the upper room is not
    offered."""
    from world.landscape import standing_looks_wanted
    sc = _two_level()
    sc["rooms"]["store"] = {"name": "The Store", "desc": ".", "exposure": "enclosed",
                            "level": 0, "far_look": "a squat stone store",
                            "adjacent": [{"to": "shop", "barrier": "open", "dir": "e"}]}
    assert _building_look(sc, "Ada") == "a squat stone store"
    assert "upper" not in [p["room"] for p in standing_looks_wanted(sc, ["lane"])["places"]]
    # Where the plan's room comes first, the upper room's look changes
    # nothing the street reads, and it is offered.
    sc["rooms"]["shop"]["adjacent"].insert(0, {"to": "store", "barrier": "open", "dir": "w"})
    assert "upper" in [p["room"] for p in standing_looks_wanted(sc, ["lane"])["places"]]


def _buildings_wanted(sc, starts):
    from world.landscape import standing_looks_wanted
    return [p for p in standing_looks_wanted(sc, starts)["places"] if p["ground"] == "building"]


def test_a_building_is_offered_from_each_front_whichever_side_the_story_stands_on():
    """RE-REVIEW N1 (2026-10-09): F3's per-front claim skipped a front whose
    mass held a front already offered -- which only reads right from the
    side whose mass is the larger. With the story on the hill the terrace
    front is reached first, and the street front, whose mass takes the
    upper room in, was never offered: the street read the look made for the
    one-storey terrace side in place of a two-storey mass, and with bodies
    on both sides at equal hops the room ids' alphabetical order decided
    which. Two fronts are one view only when they build one mass."""
    for starts in (["hill"], ["lane"], ["lane", "hill"]):
        sc = _two_level()
        wanted = {p["room"]: p["members"] for p in _buildings_wanted(sc, starts)}
        assert wanted == {"shop": ["shop", "upper"], "upper": ["upper"]}, (starts, wanted)
        for rid in wanted:
            sc["rooms"][rid]["far_look"] = "the look written for the %s" % rid
        assert _building_look(sc, "Ada") == "the look written for the shop"
        assert _building_look(sc, "Bram") == "the look written for the upper"
    # Whatever the street front is called, the ids never decide it.
    sc = json.loads(json.dumps(_two_level()).replace('"shop"', '"zshop"'))
    assert sorted(p["room"] for p in _buildings_wanted(sc, ["lane", "hill"])) == \
        ["upper", "zshop"]


def test_a_side_reading_the_look_made_for_another_side_is_offered_its_own(temp_db):
    """RE-REVIEW N1, its remainder: a pass may give one side of a building
    its look and not the other -- the cap cuts the farther front, or the
    answer leaves it out. The street side then reads the terrace front's
    look, the first in its mass's order: made for a one-storey side, said of
    a two-storey mass. And a mass any room of which carried a look was never
    offered again. That look is the Room's own word on another front whose
    own view does not take the street front in, so the street front stays
    wanted, and the sketch is shown the look it reads now; once it has its
    own, each side reads its own."""
    from pathlib import Path
    from story.room_sketch import _looks_payload, looks_offered
    from world.landscape import standing_looks_wanted
    cid = _story_with(temp_db, _two_level())
    _publish(cid, [{"op": "set_far_looks",
                    "rooms": {"upper": "a low tarred cabin on a terrace"}}])
    scene = temp_db.wget(cid, "scene")
    assert _building_look(scene, "Ada") == "a low tarred cabin on a terrace"
    wanted = standing_looks_wanted(scene, ["lane", "hill"])
    assert [(p["room"], p.get("reads_look_of")) for p in wanted["places"]
            if p["ground"] == "building"] == [("shop", "upper")]
    section, _kinds, _named = _looks_payload(cid, None, scene, looks_offered(wanted))
    shop = [p for p in section["places"] if p["id"] == "shop"][0]
    assert shop["another_sides_look"] == "a low tarred cabin on a terrace"
    assert shop["height"] == "two"
    root = Path(__file__).resolve().parents[1] / "language_packs"
    for lang in ("en", "ja"):
        card = (root / lang / "cards/system_prompts/prompts/room_sketch.txt").read_text("utf-8")
        assert '"another_sides_look"' in card, lang
    # Given its own, each side reads its own, and nothing more is wanted.
    _publish(cid, [{"op": "set_far_looks",
                    "rooms": {"shop": "a narrow two-storey shop of tarred board"}}])
    scene = temp_db.wget(cid, "scene")
    assert _building_look(scene, "Ada") == "a narrow two-storey shop of tarred board"
    assert _building_look(scene, "Bram") == "a low tarred cabin on a terrace"
    assert _buildings_wanted(scene, ["lane", "hill"]) == []


def test_a_look_made_for_the_same_view_or_by_somebody_else_keeps_a_side_unoffered():
    """The guard on the remainder: only the Room's OWN word, made for a
    front whose own view leaves this side out, is a look made for another
    side. A look a beat, the plan or a host wrote on the other side stands
    as what this side reads (the seed-only rule); a look the Room wrote on a
    room no far walk enters by -- a garret under the roof -- is the whole
    building's, made for no one side; and a look the Room wrote on another
    door of the same mass was made for this very view."""
    from world.landscape import WRITTEN_LOOKS_KEY
    sc = _two_level()
    sc["rooms"]["upper"]["far_look"] = "a low tarred cabin on a terrace"       # a beat's
    assert _buildings_wanted(sc, ["lane", "hill"]) == []
    sc = _two_level()
    sc["rooms"]["upper"]["adjacent"].append({"to": "garret", "barrier": "open",
                                             "vertical": "up", "way": "ladder", "dir": "n"})
    sc["rooms"]["garret"] = {"name": "The Garret", "desc": ".", "exposure": "enclosed",
                             "level": 2, "far_look": "a tall tarred house", "adjacent": []}
    sc[WRITTEN_LOOKS_KEY] = {"garret": "a tall tarred house"}                    # the Room's
    assert _building_look(sc, "Ada") == _building_look(sc, "Bram") == "a tall tarred house"
    assert _buildings_wanted(sc, ["lane", "hill"]) == []
    sc = _two_level()
    sc["rooms"]["back"] = {"name": "The Back Shop", "desc": ".", "exposure": "enclosed",
                           "level": 0, "far_look": "a narrow two-storey shop",
                           "adjacent": [{"to": "street", "barrier": "open_door", "dir": "s"},
                                        {"to": "shop", "barrier": "open", "dir": "w"}]}
    sc[WRITTEN_LOOKS_KEY] = {"back": "a narrow two-storey shop"}                # the Room's
    assert [p["room"] for p in _buildings_wanted(sc, ["lane"])
            if p["room"] in ("shop", "back")] == []


def test_the_full_loop_is_told_a_buildings_inside_never_shows_from_far_off():
    """RE-REVIEW N2 (2026-10-09): F5 handed the sketch a building's text as
    its inside, but the full loop -- given the same places, and reading a
    building's front room through its tools, whose description is that same
    inside ("Crates to the rafters") -- writes by set_far_looks' field text
    and its card, which said a look agrees with what the story has said of
    the place and never that what it says within a building is its inside.
    One rule for both tiers."""
    from pathlib import Path
    from story.plot_packages import OPERATION_FIELDS
    assert "nothing of an inside shows from far off" in \
        OPERATION_FIELDS["set_far_looks"]["rooms?"]
    root = Path(__file__).resolve().parents[1] / "language_packs"
    en = (root / "en/cards/system_prompts/prompts/story_planner.txt").read_text("utf-8")
    ja = (root / "ja/cards/system_prompts/prompts/story_planner.txt").read_text("utf-8")
    assert "nothing of an inside shows from far off" in en
    assert "内側のものは何ひとつ遠くからは見えません" in ja


def test_a_part_of_the_map_is_wanted_where_its_ground_reads_by_ground():
    from world.landscape import REGIONS_UNREAD, standing_looks_wanted
    sc = _town()
    for rid in ("square", "quay", "market"):
        sc["rooms"][rid]["region"] = "harbour"
    wanted = standing_looks_wanted(sc, ["inn"], regions={"harbour": {"name": "The Harbour"}})
    assert [(r["region"], r["hops"]) for r in wanted["regions"]] == [("harbour", 1)]
    assert set(wanted["regions"][0]["rooms"]) == {"square", "quay", "market"}
    # One with a look of its own, or whose look somebody wrote, is not.
    assert standing_looks_wanted(sc, ["inn"], regions={"harbour": {
        "name": "The Harbour", "far_look_written": ""}})["regions"] == []
    # A registry the stage could not read offers none.
    assert standing_looks_wanted(sc, ["inn"], regions=REGIONS_UNREAD)["regions"] == []


def test_a_pass_offers_at_most_the_named_number_parts_of_the_map_first():
    from story.room_sketch import SKETCH_LOOKS_CAP, looks_offered
    wanted = {"places": [{"room": "p%d" % n, "ground": "open", "hops": n}
                         for n in range(SKETCH_LOOKS_CAP + 5)],
              "regions": [{"region": "harbour", "hops": 1, "rooms": ["p1"]}]}
    offered = looks_offered(wanted)
    assert [r["region"] for r in offered["regions"]] == ["harbour"]
    assert len(offered["places"]) + len(offered["regions"]) == SKETCH_LOOKS_CAP
    assert offered["places"][0]["room"] == "p0"


# --------------------------------------------------------------------------
# The bounded pass: the frontier reports, the fill asks under the grant
# --------------------------------------------------------------------------

from tests.test_planting_ahead_is_one_sketch import (  # noqa: E402,F401  (fixtures)
    PLANTING, _beat, _fill, _grant, _loops, _packages, _sketches, _story, scripted)
from story import room_frontier as rf  # noqa: E402
from agents import story_planner as sp  # noqa: E402


def _harbour(db):
    """The sketch tests' port, the quay open and the warehouse a building
    on it, planned ahead enough that nothing is short but looks. A lane
    runs up from the quay, declaring no sky: somewhere a far eye looks
    across the quay from, so the warehouse is a front a far eye can see."""
    rooms = {
        "harbour_lane": {"name": "Harbour Lane", "desc": "A lane up from the water.",
                         "adjacent": [{"to": "quay", "barrier": "open"}]},
        "quay": {"name": "Quay", "desc": "Wet stone and rope.", "exposure": "open",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}],
                 "anchors": {"crane": {"desc": "a tall iron crane", "dir": "n",
                                       "height": "full", "footprint": "large"}}},
        "warehouse": {"name": "Warehouse", "desc": "Crates to the rafters.",
                      "exposure": "enclosed",
                      "adjacent": [{"to": "quay", "barrier": "open_door"},
                                   {"to": "loft", "barrier": "open"}]},
        "loft": {"name": "Loft", "desc": "Sacking and dust.", "exposure": "enclosed",
                 "adjacent": [{"to": "warehouse", "barrier": "open"}]},
    }
    cid = _story(db, rooms=rooms)
    from world.structure import plant_structure
    from world.planned_entities import add_planned_entity
    plant_structure(cid, {"key": "port", "max_planned": 8}, {
        "ropewalk": {"name": "Ropewalk", "purpose": "rope", "exposure": "open",
                     "far_look": "a long open rope-ground",
                     "adjacent": [{"to": "quay", "barrier": "open"}]},
        "netloft": {"name": "Net Loft", "purpose": "nets", "exposure": "enclosed",
                    "far_look": "a tarred net loft on piles",
                    "adjacent": [{"to": "quay", "barrier": "open_door"}]}})
    for name in ("Orrin Vane", "Bel Harrow"):
        add_planned_entity(cid, {"kind": "person", "name": name,
                                 "brief": {"purpose": "work", "where": "quay"}})
    return cid


def test_the_frontier_reports_places_wanting_looks_and_the_fill_asks_only_under_its_grant(temp_db):
    cid = _harbour(temp_db)
    report = rf.frontier_report(cid, None)
    assert report["rooms_short"] == 0 and report["identities_short"] == 0, report
    looks = report["looks_wanted"]
    assert [p["room"] for p in looks["places"]] == ["quay", "warehouse"]
    # Without the grant they are nobody's question: no fill, the same
    # question as before, and no ask on the status row on their account.
    _grant(cid, *PLANTING)
    assert not sp._looks_asked(cid, None, report)
    assert rf.fill_signature(report, ["m"]) == rf.fill_signature(
        {k: v for k, v in report.items() if k != "looks_wanted"}, ["m"])
    assert sp.schedule_room_work(_beat(temp_db, cid, 2)) is None
    _grant(cid, "set_far_looks")
    assert sp._looks_asked(cid, None, report)
    assert sp._signature(cid, None, report, ["m"]) != rf.fill_signature(report, ["m"])


def test_a_pass_gives_the_standing_places_their_looks_in_one_package(temp_db, scripted):
    """The sketch is handed the nearest places that read by their ground --
    what each is, what the story has said of it, and what the far layer
    already says standing on it -- and its looks land as ONE `set_far_looks`;
    the question then rides planting's back-off."""
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks")

    def answer(payload):
        offered = payload["looks"]
        assert payload["granted"]["looks"] is True
        quay = [p for p in offered["places"] if p["id"] == "quay"][0]
        assert quay["ground"] == "open" and quay["the_story_says"] == "Wet stone and rope."
        assert quay["said_beside_it"] == ["a tall iron crane"]
        house = [p for p in offered["places"] if p["id"] == "warehouse"][0]
        assert house["ground"] == "building" and house["rooms_within"] == ["Loft"]
        return {"looks": [{"place": "quay", "far_look": "a stone quay black with tar"},
                          {"place": "warehouse", "far_look": "a tall warehouse of grey board"}],
                "title": "The quay from afar", "reply": "Two looks.", "escalate": None}
    script = scripted(sketch=answer)
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "sketch" and len(_sketches(script)) == 1
    published = _packages(cid, "published")
    assert [p["operations"] for p in published] == [["set_far_looks"]]
    rooms = temp_db.wget(cid, "scene")["rooms"]
    assert rooms["quay"]["far_look"] == "a stone quay black with tar"
    assert rooms["warehouse"]["far_look"] == "a tall warehouse of grey board"
    assert "looks_wanted" not in rf.frontier_report(cid, None)
    # Nothing wants a look and nothing is short: the next commit asks nothing.
    assert _fill(temp_db, cid, 3) is None


def test_a_buildings_inside_is_handed_to_the_sketch_as_its_inside(temp_db):
    """REVIEW F5 (2026-10-09): for a building the sketch was handed its
    front room's text as "what the story says" and told the look must agree
    with it -- but that text is what a body INSIDE meets ("Crates to the
    rafters"), and a far look is told to every far eye, which the far
    layer's floor stops only at names. So a building's text and the names
    of its rooms ride as its inside, the card says nothing of an inside
    shows from far off, and what does show rides beside them: how high its
    mass stands, the word its look is said in place of."""
    from story import room_sketch
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks")
    _context, payload = room_sketch.sketch_payload(cid, None, rf.frontier_report(cid, None))
    house = [p for p in payload["looks"]["places"] if p["id"] == "warehouse"][0]
    assert "the_story_says" not in house and "said_beside_it" not in house
    assert house["said_within"] == "Crates to the rafters."
    assert house["rooms_within"] == ["Loft"]
    assert house["height"] == "one"
    quay = [p for p in payload["looks"]["places"] if p["id"] == "quay"][0]
    assert quay["the_story_says"] == "Wet stone and rope." and "said_within" not in quay
    # The height is the far layer's own word for the mass.
    from world.landscape import building_height, building_of
    sc = _two_level()
    assert building_height(building_of(sc, "shop")[1]) == "two"
    assert building_height(building_of(sc, "upper")[1]) == "one"
    # Both packs say an inside never shows from far off.
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "language_packs"
    en = (root / "en/cards/system_prompts/prompts/room_sketch.txt").read_text("utf-8")
    ja = (root / "ja/cards/system_prompts/prompts/room_sketch.txt").read_text("utf-8")
    assert "nothing of an inside shows from far off" in en
    assert "内側のものは何ひとつ遠くからは見えません" in ja


def test_the_planner_is_shown_the_nearest_few_wanting_a_look_and_only_under_the_grant(temp_db):
    """The whole frontier rides every step of every Planner reply: the
    places wanting a look ride it as the fill's task names them -- the
    nearest `SKETCH_LOOKS_CAP`, ids and ground -- and not at all where the
    grants do not let the Room write one."""
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING)

    def frontier():
        return sp._payload(cid, None, text="hello", task=None, transcript=[], step=1,
                           calls_left=5, seconds_left=30.0, turn_idx=2)["frontier"]
    assert "looks_wanted" not in frontier()
    _grant(cid, "set_far_looks")
    assert frontier()["looks_wanted"] == {
        "regions": [], "places": [{"room": "quay", "ground": "open"},
                                  {"room": "warehouse", "ground": "building"}]}


LOOKS_ANSWER = {"looks": [{"place": "quay", "far_look": "a stone quay black with tar"}],
                "reply": "One look.", "escalate": None}


def test_a_pass_that_only_describes_what_stands_spends_none_of_plantings_hour(temp_db, scripted):
    """Planting ahead is held to the hour's fills (`mandates.
    FILLS_PER_STORY_HOUR`); a pass that only gave standing places their far
    looks planted nothing, and counted there it would spend the hour the
    world's growth runs on -- the Brackwater run's slow clock held the whole
    thirty-beat story inside one story hour. A number the player stated is
    the total of every fill, so there it counts."""
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks")
    scripted(sketch=LOOKS_ANSWER)
    job = _fill(temp_db, cid, 2)
    assert job.result["published"] and rf.fills_this_hour(cid, None, 2) == 0
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks", limits={"fills_per_hour": 6})
    job = _fill(temp_db, cid, 2)
    assert job.result["published"] and rf.fills_this_hour(cid, None, 2) == 1


def test_a_pass_that_lands_nothing_backs_off_like_planting(temp_db, scripted):
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks")
    script = scripted(sketch={"looks": [], "reply": "Nothing I can see whole yet."})
    assert _fill(temp_db, cid, 2) is not None
    assert _fill(temp_db, cid, 3) is None                       # unchanged: waits
    assert len(_sketches(script)) == 1
    assert _fill(temp_db, cid, 2 + rf.fill_wait_beats(1)) is not None


def test_a_look_for_a_place_not_offered_is_left_out_and_the_offered_looks_land(
        temp_db, scripted):
    """REVIEW F2 (2026-10-09): one look for a valid place the sketch was not
    offered -- the warehouse's own loft, which the operation itself would
    write -- refused the whole answer, threw the two offered looks away and
    handed a one-call question to the full loop (about seventeen calls a
    fill on the Brackwater run). A far look plans nothing and nothing leans
    on it, so the look not offered is left out and said, and the rest land."""
    from world.structure import registry_rows
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks")
    script = scripted(sketch={"looks": [
        {"place": "quay", "far_look": "a stone quay black with tar"},
        {"place": "warehouse", "far_look": "a tall warehouse of grey board"},
        {"place": "loft", "far_look": "a loft under a slate roof"},
        {"place": "ropewalk", "far_look": "a rope-ground"}],
        "reply": "Two looks.", "escalate": None})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "sketch" and _loops(script) == []
    assert [p["operations"] for p in _packages(cid, "published")] == [["set_far_looks"]]
    rooms = temp_db.wget(cid, "scene")["rooms"]
    assert rooms["quay"]["far_look"] == "a stone quay black with tar"
    assert rooms["warehouse"]["far_look"] == "a tall warehouse of grey board"
    assert "far_look" not in rooms["loft"]
    # A planned place nobody offered keeps the plan's own word.
    assert registry_rows(cid)["ropewalk"]["planned"]["far_look"] == "a long open rope-ground"
    [note] = [n for n in job.result["notes"] if "not offered" in n]
    assert "'loft'" in note and "'ropewalk'" in note


def test_a_sketch_may_give_its_looks_as_a_map_and_name_a_place_as_it_was_shown(
        temp_db, scripted):
    """The card's shape is a list of {place, far_look}; a map {place: look},
    the operation's own {rooms, regions} that the Planner's sheet shows, and
    a place named as the payload named it say the same thing, and are read
    as it (review F2: a map was refused as unreadable). A look that cannot
    be read is left out and said; the rest of the answer stands."""
    def harbour():
        cid = _harbour(temp_db)
        scene = temp_db.wget(cid, "scene")
        scene["rooms"]["quay"]["name"] = "The Old Quay"
        temp_db.wset(cid, "scene", scene)
        _grant(cid, *PLANTING, "set_far_looks")
        return cid

    cid = harbour()
    scripted(sketch={"looks": {"the old quay": "a stone quay black with tar",
                               "warehouse": "a tall warehouse of grey board"},
                     "reply": "Two looks."})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "sketch", job.result
    rooms = temp_db.wget(cid, "scene")["rooms"]
    assert rooms["quay"]["far_look"] == "a stone quay black with tar"
    assert rooms["warehouse"]["far_look"] == "a tall warehouse of grey board"

    cid = harbour()
    scripted(sketch={"looks": {"rooms": {"quay": "a stone quay black with tar"},
                               "regions": {}}, "reply": "One look."})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "sketch", job.result
    assert temp_db.wget(cid, "scene")["rooms"]["quay"]["far_look"] == \
        "a stone quay black with tar"

    cid = harbour()
    scripted(sketch={"looks": ["a stone quay", {"place": "quay", "far_look": {"text": 1}},
                               {"place": "warehouse",
                                "far_look": "a tall warehouse of grey board"}],
                     "reply": "One look."})
    job = _fill(temp_db, cid, 2)
    assert job.result["tier"] == "sketch", job.result
    rooms = temp_db.wget(cid, "scene")["rooms"]
    assert "far_look" not in rooms["quay"]
    assert rooms["warehouse"]["far_look"] == "a tall warehouse of grey board"
    assert any("could not be read" in n for n in job.result["notes"])


def _loop_files(*ops):
    """The full loop's steps that file ``ops`` as one package and publish it."""
    def uid(payload):
        for entry in reversed(payload.get("transcript") or []):
            result = entry.get("result") or {}
            if isinstance(result, dict) and result.get("uid"):
                return result["uid"]
        return None
    steps = [{"calls": [{"tool": "new_package", "args": {"title": "Seen from afar"}}]}]
    steps += [lambda p, op=op: {"calls": [{"tool": "draft_operation", "args": {
        "uid": uid(p), "operation": op}}]} for op in ops]
    steps += [lambda p: {"calls": [{"tool": "validate_package", "args": {"uid": uid(p)}}]},
              lambda p: {"calls": [{"tool": "publish_package", "args": {
                  "uid": uid(p), "expected_revision": 1 + len(ops)}}]},
              {"reply": "Filed."}]
    return steps


ESCALATED = {"escalate": "the quay wants more than a sketch can say"}
LOOK_OP = {"op": "set_far_looks", "rooms": {"quay": "a stone quay black with tar"}}


def test_a_looks_only_pass_the_full_loop_files_spends_none_of_plantings_hour(
        temp_db, scripted):
    """REVIEW F2, the loop tier: a sketch that hands its question on reaches
    the full loop, and a pass whose every package there only gave far looks
    was counted against planting's hour as the sketch's was not -- on a slow
    clock, every planting the story would get. One rule for both tiers, read
    off the packages as filed: a looks-only pass is not counted, unless the
    player stated a number (the total of every fill); a pass that planted
    beside its looks is."""
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks")
    scripted(*_loop_files(LOOK_OP), sketch=ESCALATED)
    out = sp.run_fill(cid, None, base_turn=2)
    assert out["tier"] == "escalated" and out["published"], out
    assert temp_db.wget(cid, "scene")["rooms"]["quay"]["far_look"] == \
        "a stone quay black with tar"
    assert rf.fills_this_hour(cid, None, 2) == 0
    # A number the player stated is the total of every fill.
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks", limits={"fills_per_hour": 6})
    scripted(*_loop_files(LOOK_OP), sketch=ESCALATED)
    out = sp.run_fill(cid, None, base_turn=2)
    assert out["published"] and rf.fills_this_hour(cid, None, 2) == 1
    # A package that planted beside its looks counts on planting's line.
    cid = _harbour(temp_db)
    _grant(cid, *PLANTING, "set_far_looks")
    scripted(*_loop_files(LOOK_OP, {
        "op": "plan_entity", "kind": "person", "name": "Tam Rook",
        "role": "net-mender", "brief": {"purpose": "nets", "where": "quay"}}),
        sketch=ESCALATED)
    out = sp.run_fill(cid, None, base_turn=2)
    assert out["published"] and rf.fills_this_hour(cid, None, 2) == 1


# --------------------------------------------------------------------------
# A drafted town carries its looks; the room author gives one to a new place
# --------------------------------------------------------------------------

def test_a_drafted_towns_far_look_survives_every_hop_from_plan_to_stub(temp_db):
    """THE RAIL, as `test_a_fixture_survives_the_whole_rail` walks it for
    fixtures: `plant_structure` keeps a drafted room's look, but the
    closure's room rebuild is an allowlist and dropped it, so a town the
    Room drafted would have stood with none however the plan specification
    asked."""
    from world.charter_generate import close_plan
    from world.structure import plant_structure, skeleton_rooms
    plan = {"name": "Brackwater", "structure": {"key": "brackwater", "max_planned": 8},
            "rooms": {"walk": {"name": "The Walk", "purpose": "the town's spine",
                               "exposure": "open", "far_look": "a plank  walk on piles",
                               "adjacent": [{"to": "store", "barrier": "open_door"}]},
                      "store": {"name": "The Store", "purpose": "work",
                                "exposure": "enclosed",
                                "far_look": "a squat store of tarred board",
                                "adjacent": [{"to": "walk", "barrier": "open_door"}]}},
            "charters": [{"key": "store", "name": "The Store",
                          "posts": {"keeper": {"place": "store"}},
                          "populations": [{"post": "keeper", "count": 1}]}]}
    closed = close_plan(plan)
    assert closed["rooms"]["walk"]["far_look"] == "a plank walk on piles"
    assert "far_look_cut_from" not in closed["rooms"]["walk"]
    cid = _chat(temp_db)
    plant_structure(cid, closed["structure"], closed["rooms"])
    stub = skeleton_rooms(cid, "brackwater")["rooms"]["store"]
    assert stub["far_look"] == "a squat store of tarred board"


def test_a_split_dwellings_sibling_reads_from_afar_as_the_dwelling_it_is_more_of():
    """A sibling is the same kind of room, measured the same: a row of one
    kind of house is said once with its count, never as one house and four
    buildings. An annex is not the same kind and waits for the Director."""
    from world.charter_generate import _spread_berths
    rooms = {"row": {"name": "The Row", "purpose": "homes", "exposure": "enclosed",
                     "far_look": "a narrow tarred house",
                     "adjacent": [{"to": "walk", "barrier": "open_door"}]},
             "walk": {"name": "The Walk", "exposure": "open", "adjacent": []}}
    bodies = {"b%d" % n: {"berth": "row", "place": "walk"} for n in range(12)}
    minted = _spread_berths(rooms, [("port", bodies, [])], ceiling=8)
    sibling = minted["row"]["rooms"][0]
    assert minted["row"]["mode"] == "siblings"
    assert rooms[sibling]["far_look"] == "a narrow tarred house"
    rooms = {"inn": {"name": "The Inn", "exposure": "enclosed", "far_look": "a low inn",
                     "adjacent": []}}
    bodies = {"b%d" % n: {"berth": "inn", "place": "inn"} for n in range(12)}
    minted = _spread_berths(rooms, [("inn", bodies, ["inn"])], ceiling=8)
    annex = minted["inn"]["rooms"][0]
    assert minted["inn"]["mode"] == "annexes" and "far_look" not in rooms[annex]


def test_the_location_designer_is_told_which_rooms_seen_from_outside_lack_a_look():
    from story.location_design import rooms_with_no_far_look
    rooms = {"walk": {"exposure": "open"},
             "row": {"exposure": "enclosed", "adjacent": [{"to": "walk"}]},
             "back": {"exposure": "enclosed", "adjacent": [{"to": "row"}]},
             "yard": {"exposure": "open", "far_look": "a muddy yard"},
             "loose": {"name": "no exposure"}}
    assert rooms_with_no_far_look(rooms) == ["row", "walk"]


def test_the_cards_ask_for_looks_on_what_stands_in_both_packs():
    from pathlib import Path
    from story.plot_packages import OPERATION_FIELDS
    from world.charter_generate import _PLAN_SYSTEM
    root = Path(__file__).resolve().parents[1] / "language_packs"
    for lang in ("en", "ja"):
        sketch = (root / lang / "cards/system_prompts/prompts/room_sketch.txt").read_text("utf-8")
        assert '"looks": [{"place": "<an id from looks>", "far_look": ' \
               '"<how it reads from far off>"}]' in sketch, lang
        assert '"said_beside_it"' in sketch and '"looks"' in sketch, lang
        for key in ('"said_within"', '"rooms_within"', '"height"'):
            assert key in sketch, (lang, key)
        planner = (root / lang / "cards/system_prompts/prompts/story_planner.txt").read_text("utf-8")
        assert '"looks_wanted"' in planner and "set_far_looks" in planner, lang
        author = (root / lang / "cards/system_prompts/prose_contract/room_author.txt"
                  ).read_text("utf-8")
        assert author.count("`far_look`") >= 2, lang
    assert "rooms?" in OPERATION_FIELDS["set_far_looks"]
    assert "regions?" in OPERATION_FIELDS["set_far_looks"]
    assert "far_look," in _PLAN_SYSTEM and "also gives its far_look" in _PLAN_SYSTEM


def test_every_field_the_sketch_card_names_rides_the_payload(temp_db):
    """A rule about a field is inert unless the call receives it: every key
    the card names in a place or a part of the map is in the payload. (The
    look of another side, which rides only a side of a building that reads
    one, is pinned where that side is built: test_a_side_reading_the_look_
    made_for_another_side_is_offered_its_own.)"""
    from story import room_sketch
    cid = _harbour(temp_db)
    scene = temp_db.wget(cid, "scene")
    scene["rooms"]["quay"]["region"] = "port"       # the planted structure's
    temp_db.wset(cid, "scene", scene)
    _grant(cid, *PLANTING, "set_far_looks")
    report = rf.frontier_report(cid, None)
    _context, payload = room_sketch.sketch_payload(cid, None, report)
    looks = payload["looks"]
    keys = set().union(*(p.keys() for p in looks["places"]))
    assert {"id", "name", "ground", "the_story_says", "said_beside_it",
            "said_within", "rooms_within", "height", "part_of_the_map"} <= keys, keys
    assert {"places_in_it", "id", "name"} <= set(looks["regions"][0]), looks["regions"]
    assert looks["most"] == room_sketch.SKETCH_LOOKS_CAP


# --------------------------------------------------------------------------
# The host's word, the ledgers, the archive
# --------------------------------------------------------------------------

from tests.test_world_routes import client, story  # noqa: E402,F401  (fixtures)


def test_the_world_browser_marks_a_hosts_far_look_as_the_hosts(client, story, temp_db):
    from world.landscape import WRITTEN_LOOKS_KEY, room_look_writable
    cid = story["chat_id"]
    r = client.patch(f"/api/chats/{cid}/rooms/garden", json={"far_look": ""})
    assert r.status_code == 200, r.text
    scene = temp_db.wget(cid, "scene")
    assert scene[WRITTEN_LOOKS_KEY]["garden"] == ""
    if "exposure" in scene["rooms"]["garden"]:
        assert room_look_writable(scene, "garden") == (False, "host")


def test_an_entity_fold_leaves_the_record_of_written_looks_keyed_by_room(temp_db):
    """The Room's record is keyed by ROOM, like the plan's beside it: a mint
    folded as `well` -> `village_well` would have re-keyed it, and the
    host's clear on the room `well` read as never made."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist.commit import _fold_duplicate_mints
    from world.landscape import WRITTEN_LOOKS_KEY
    cid = _chat(temp_db)
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Far", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=1, player_input="", created=time.time()),
        cast=[], input="")
    well = {"name": "the well", "exposure": "open", "desc": "A stone well-head."}
    keeper = {"name": "the village well", "aliases": ["well"]}
    prev = {"rooms": {"well": dict(well)}, "entities": {"village_well": dict(keeper)},
            WRITTEN_LOOKS_KEY: {"well": ""}}
    diff = {"entities": {"well": {"name": "well"}}}
    sc = {"rooms": {"well": dict(well)}, "positions": {},
          "entities": {"village_well": dict(keeper), "well": {"name": "well"}},
          WRITTEN_LOOKS_KEY: {"well": ""}}
    assert _fold_duplicate_mints(ctx, cid, sc, prev, diff) == [("well", "village_well")]
    assert sc[WRITTEN_LOOKS_KEY] == {"well": ""}


def test_a_written_look_travels_through_the_archive_and_the_checkpoint(temp_db):
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app
    from world.landscape import WRITTEN_LOOKS_KEY
    from world.regions import region_registry
    cid = _story_with(temp_db, _valley())
    from story.plot_packages import _apply_plan_rooms, _shape_plan_rooms
    _apply_plan_rooms(cid, None, _shape_plan_rooms({
        "structure": {"key": "vale", "name": "The Vale"},
        "rooms": {"barn": {"name": "Barn", "exposure": "enclosed"}}}), 0)
    _publish(cid, [{"op": "set_far_looks", "rooms": {"meadow": "a long hay meadow"},
                    "regions": {"vale": "hedged fields"}}])
    ensure_checkpoint(cid, 0)
    temp_db.wset(cid, "scene", {"rooms": {}, "positions": {}, "entities": {}})
    restore_checkpoint(cid, 0)
    scene = json.loads(json.dumps(temp_db.wget(cid, "scene")))
    assert scene[WRITTEN_LOOKS_KEY] == {"meadow": "a long hay meadow"}
    assert region_registry(cid, None)["vale"]["far_look_written"] == "hedged fields"
    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(cid)})
    icid = imported["id"] if isinstance(imported, dict) else imported
    scene = temp_db.wget(icid, "scene")
    scene = json.loads(scene) if isinstance(scene, str) else scene
    assert scene[WRITTEN_LOOKS_KEY] == {"meadow": "a long hay meadow"}
    assert region_registry(icid, None)["vale"]["far_look_written"] == "hedged fields"



def _two_street_doors():
    """`_two_level` with a second street door, `side`, which the shop lists
    before its stair to the terrace room."""
    sc = _two_level()
    shop = sc["rooms"]["shop"]
    shop["adjacent"].insert(0, {"to": "side", "barrier": "open", "dir": "e"})
    sc["rooms"]["side"] = {"name": "The Side Shop", "desc": ".", "exposure": "enclosed",
                           "level": 0, "adjacent": []}
    sc["rooms"]["street"]["adjacent"].append({"to": "side", "barrier": "open_door", "dir": "n"})
    return sc


def test_a_door_reading_a_look_made_for_another_side_is_offered_its_own():
    """(review B1) After a pass gave only the terrace side its look, two
    street doors of one mass, each reaching the other before the stair, read
    the terrace's one-storey word for the two-storey mass -- and neither was
    ever offered, because the check protected a look made for another side.
    That look is not the street side's: a door reading it is offered, and its
    look lands."""
    from world.landscape import WRITTEN_LOOKS_KEY, standing_looks_wanted
    sc = _two_street_doors()
    sc["rooms"]["upper"]["far_look"] = "a low tarred cabin on a terrace"
    sc[WRITTEN_LOOKS_KEY] = {"upper": "a low tarred cabin on a terrace"}
    assert _building_look(sc, "Ada") == "a low tarred cabin on a terrace"
    wanted = [(p["room"], p.get("reads_look_of"))
              for p in standing_looks_wanted(sc, ["lane", "hill"])["places"]
              if p["ground"] == "building"]
    assert wanted and all(read == "upper" for _rid, read in wanted), wanted
    rid = wanted[0][0]
    sc["rooms"][rid]["far_look"] = "a narrow two-storey shop of tarred board"
    sc[WRITTEN_LOOKS_KEY][rid] = "a narrow two-storey shop of tarred board"
    assert _building_look(sc, "Ada") == "a narrow two-storey shop of tarred board"
    assert _building_look(sc, "Bram") == "a low tarred cabin on a terrace"
