"""While a room is the plan's prose-free stub the plan owns its measurements
-- and so a measurement the plan stops stating comes off the stub, and a
doorway the story has settled is the one the plan's brief hands on.

THE AUDIT (2026-11-01, world_layout_bridge_structure F3, reproduced): a lot is
a fringe stub before it is expanded, minted with the lot's `extent` -- the
whole building's footprint. Expanded, the plan says its entry has no size
(the footprint moves onto the lot's record), but `materialize_planned_fringe`
only ever ADDED the plan's geometry: the stub kept 10 by 14, and the beat that
described the shop floor as 4 by 5 was refused, because a planned stub that
carries an extent holds it as "the plan's measurement". The fringe now
records what it laid from the plan (`PLAN_GEOMETRY_LAID_KEY`, as
`LAID_LOOKS_KEY` does for far looks) and takes a measurement back off while
the stub still holds the value the plan laid and the plan no longer states
it; a stub laid before the record existed reads the lot's own record of the
footprint it dropped. A value a beat wrote is never taken.

F9, reproduced: `planned_room_brief` read the plan's edges first and let the
first writer win, so a stub whose doorway the fringe had settled to the shut
`closed_door` the room beyond declares (`_settle_stub_barriers`, chat 117's
measured class) was briefed to its designer as `open_door` -- and a design
echoing the exit wrote it back onto the stub. The live stub's edge is read
first now; the plan's only where the stub holds none.

Hand-made plans; the names are illustrations, not the rule.
"""
from __future__ import annotations

import copy

import pytest

import world.structure as structure


@pytest.fixture
def plan(monkeypatch):
    specs = {}
    monkeypatch.setattr(structure, "_planned_specs", lambda cid: specs)
    return specs


LOT = {"name": "General Store", "purpose": "the village's general store",
       "structure": "village", "exposure": "enclosed", "extent": {"w": 10, "d": 14},
       "adjacent": [{"to": "street", "barrier": "closed_door", "dir": "n"}],
       "lot": {"storeys": 2}}
STREET = {"name": "Street", "purpose": "the village street", "structure": "village",
          "exposure": "open", "extent": {"w": 6, "d": 60},
          "adjacent": [{"to": "store", "barrier": "closed_door"}]}


def _village():
    return {"rooms": {"street": {"name": "Street", "desc": "A street.", "adjacent": []}},
            "positions": {"Hinami": "street"}}


def _expand(plan):
    from agents.director_lots import planned_rooms_of
    rows = {"store": {"name": "General Store", "planned": LOT},
            "street": {"name": "Street", "planned": STREET}}
    answer = {"rooms": [
        {"id": "shop", "name": "Shop", "level": 0, "entry": True, "purpose": "the shop floor",
         "joins": [{"to": "back", "side": "s", "barrier": "open_door"}]},
        {"id": "back", "name": "Back Room", "level": 0, "purpose": "storage",
         "joins": [{"to": "shop", "side": "n"}, {"to": "up", "vertical": "up"}]},
        {"id": "up", "name": "Living Room", "level": 1, "purpose": "family",
         "joins": [{"to": "back", "vertical": "down"}]}]}
    planted, _notes, _sleeps = planned_rooms_of("store", rows, answer, turn_idx=12)
    plan.clear()
    plan["street"] = ("Street", STREET)
    for uid, spec in planted.items():
        plan[uid] = (spec["name"], dict(spec, structure="village"))


def test_an_expanded_lot_s_entry_sheds_the_whole_building_s_footprint(plan):
    from world.spatial import _merge_room
    plan.update({"store": ("General Store", LOT), "street": ("Street", STREET)})
    scene = _village()
    structure.materialize_planned_fringe(1, scene)
    assert scene["rooms"]["store"]["extent"] == {"w": 10, "d": 14}
    _expand(plan)
    structure.materialize_planned_fringe(1, scene)
    stub = scene["rooms"]["store"]
    assert "extent" not in stub, "the plan no longer measures the entry"
    assert stub["purpose"] == "the shop floor"
    merged = _merge_room(stub, {"desc": "A small shop floor with a counter.",
                                "extent": {"w": 4, "d": 5}}, "store")
    assert merged["extent"] == {"w": 4, "d": 5}


def test_a_stub_laid_before_the_record_reads_the_lot_s_own_footprint(plan):
    """The stores the beat walked into before the job, and the tea house the
    tier refused twice, were stubbed before this record existed."""
    _expand(plan)
    scene = _village()
    scene["rooms"]["store"] = {"name": "General Store", "planned": True,
                               "purpose": "the village's general store",
                               "extent": {"w": 10, "d": 14}, "adjacent": []}
    structure.materialize_planned_fringe(1, scene)
    assert "extent" not in scene["rooms"]["store"]


def test_a_replan_that_drops_a_measurement_takes_it_off_and_nothing_else(plan):
    yard = {"name": "Yard", "structure": "farm", "exposure": "open",
            "sound": {"level": "faint", "detail": "hens"}, "extent": {"w": 8, "d": 8},
            "adjacent": [{"to": "lane", "barrier": "open"}]}
    plan.update({"yard": ("Yard", yard)})
    scene = {"rooms": {"lane": {"name": "Lane", "desc": "A lane.",
                                "adjacent": [{"to": "yard", "barrier": "open"}]}},
             "positions": {"Ann": "lane"}}
    structure.materialize_planned_fringe(1, scene)
    assert scene["rooms"]["yard"]["sound"] == {"level": "faint", "detail": "hens"}
    replanned = copy.deepcopy(yard)
    replanned.pop("sound")
    replanned.pop("extent")
    plan["yard"] = ("Yard", replanned)
    # a beat measured the yard meanwhile: that is the story's, not the plan's
    scene["rooms"]["yard"]["extent"] = {"w": 5, "d": 6}
    structure.materialize_planned_fringe(1, scene)
    stub = scene["rooms"]["yard"]
    assert "sound" not in stub
    assert stub["extent"] == {"w": 5, "d": 6}
    assert stub["exposure"] == "open"


def test_the_brief_hands_on_the_doorway_the_story_settled(plan, monkeypatch):
    import core.db
    monkeypatch.setattr(core.db, "wget_for_frame", lambda *a, **k: {})
    plan.update({
        "annex": ("Containment Annex", {"structure": "site", "purpose": "holding cells",
                                        "adjacent": [{"to": "spine", "barrier": "open_door",
                                                      "dir": "w"}]}),
        "spine": ("Service Spine", {"structure": "site", "purpose": "corridor",
                                    "adjacent": [{"to": "annex", "barrier": "open_door",
                                                  "dir": "e"}]})})
    scene = {"rooms": {
        "spine": {"name": "Service Spine", "desc": "A corridor.",
                  "adjacent": [{"to": "annex", "barrier": "closed_door",
                                "name": "the containment door", "dir": "e"}]},
        "annex": {"name": "Containment Annex", "planned": True,
                  "adjacent": [{"to": "spine", "barrier": "open_door", "dir": "w"}]}},
        "positions": {"Ann": "spine"}}
    structure._settle_stub_barriers(scene["rooms"])
    assert scene["rooms"]["annex"]["adjacent"][0]["barrier"] == "closed_door"
    brief = structure.planned_room_brief(1, scene, ["annex"])
    [exit_] = brief["annex"]["exits"]
    assert exit_["barrier"] == "closed_door"
    assert exit_["dir"] == "w"
