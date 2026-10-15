"""What an answer says of the ground, read against the plan.

A third review of design A6 (2026-10-14) found the grounds right about the
plan's joins and wrong about the answers beside them: a relation thrown away
for a thing joined to open ground alone, which then stood at the plot's far
corner; a thing by the entrance stood by the whole court instead; an
outbuilding with no end named stood centred before the entrance; the
entrance moved after the call had answered against it, and opened onto an
outbuilding; and the relate call was shown one front and laid against
another. Each test is the reviewer's plan, built from the suite's court and
farm.
"""
from __future__ import annotations

import copy

import pytest

from world import layout_bridge as lb
from world.layout_solver import SEED, _STEP, solve

from tests.test_the_floor_charges_what_failed import _building, _court_plan, _farm_plan, _lay, _lay_farm
from tests.test_the_grounds_hold_together import SCENE
from tests.test_the_grounds_keep_their_doors import _add


def _spec_of(plan, scene=SCENE, held=()):
    specs, sort, relate = plan
    b = _building(specs, scene, held)
    inv = lb.hold_inventory(b, copy.deepcopy(sort))
    return b, inv, lb.spec_from_answers(b, inv, copy.deepcopy(relate))


def _farm_spec_of(plan):
    from tests.test_a_building_stands_in_its_grounds import HELD_OPEN, SCENE as FARM
    return _spec_of(plan, FARM, HELD_OPEN)


def _held(spec, refused, places):
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    assert set(places) <= set(spec.get("ground_is") or {}), spec.get("ground_is")


def _seeds(spec):
    for k in range(4):
        yield k, solve(copy.deepcopy(spec), seed=SEED + k)


def _rect(layout, pid):
    return next(f["rect"] for f in layout.features if f["id"] == pid)


def _step(layout):
    door = next(d for d in layout.doors if d.get("b") == "entrance")
    sx, sy = _STEP[door["side"]]
    return door["cell"][0] + sx, door["cell"][1] + sy


def _gap(rect, cells):
    """Paces between a box and the nearest of `cells`, edge to edge."""
    return min(max(rect.x - x, x - (rect.x + rect.w - 1), 0) + max(rect.y - y, y - (rect.y + rect.d - 1), 0)
               for x, y in cells)


def _thing(joined, uid, answer, back="w", out="e", kind="feature", barrier=None):
    """A mutation: `uid`, a thing (or other `kind`) the plan joins to
    `joined` alone -- through a door, where `joined` is a room -- answered
    `answer`."""
    def mutate(specs, sort, relate):
        specs[joined][1]["adjacent"].append(dict({"to": uid, "dir": out},
                                                 **({"barrier": barrier} if barrier else {})))
        _add(specs, uid, f"the {uid.title()}", f"a {uid}", [{"to": joined, "dir": back}],
             exposure="open")
        sort["grounds"].append({"id": uid, "is": kind})
        relate["grounds"].append(dict(answer, id=uid))
    return mutate


# --------------------------------------------- things joined to open ground


@pytest.mark.parametrize("side", [None, "e"])
def test_a_thing_by_the_entrance_onto_open_ground_stands_at_the_door(side):
    """A lantern joined to the court the entrance opens onto, answered by
    the entrance: read as by the court, it stood nineteen paces off at the
    court's far edge. The ground at the entrance's step is kept clear
    (`layout_solver._grounds`' aprons), and the lantern stands just past it
    -- on the side answered, where it is."""
    answer = dict({"kind": "lantern", "by": "entrance"}, **({"side": side} if side else {}))
    plan = _court_plan(_thing("court", "lantern", answer))
    _b, spec, _layout, refused = _lay(*plan)
    _held(spec, refused, ["court", "lane", "shed", "lantern"])
    lantern = next(f for f in spec["grounds"]["features"] if f["id"] == "lantern")
    assert (lantern["by"], lantern["in"]) == ("entrance", "court")
    for k, layout in _seeds(spec):
        rect, step = _rect(layout, "lantern"), _step(layout)
        assert _gap(rect, [step]) <= 3, (k, rect, step)
        assert step not in rect.cells(), k
        if side == "e":
            assert rect.x + rect.w / 2 > step[0] + 0.5, (k, rect, step)


def test_a_thing_in_open_ground_stands_by_what_the_answer_names():
    """A bench the plan joins to the garden round the farm, answered by the
    kitchen: the kitchen is no place the plan joins it to, so the answer was
    thrown away, and the bench went to the plot's far corner a dozen paces
    north of the house. Standing by the kitchen keeps its join to the garden
    it stands in."""
    mutate = _thing("garden", "bench", {"kind": "bench", "by": "kitchen"})
    _b, spec, _layout, refused = _lay_farm(mutate)
    _held(spec, refused, ["garden", "bench"])
    bench = next(f for f in spec["grounds"]["features"] if f["id"] == "bench")
    assert (bench["by"], bench["in"]) == ("kitchen", "garden")
    for k, layout in _seeds(spec):
        rect = _rect(layout, "bench")
        assert _gap(rect, layout.floors[0]["kitchen"][0].cells()) <= 2, (k, rect)
        assert rect.cells() <= layout.areas["garden"], k


def test_posts_answered_to_flank_a_way_they_are_not_joined_to_stand_at_its_mouth():
    """Posts the plan joins to the court alone, answered to flank the lane at
    its near end: the lane is no place they are joined to, so the answer was
    thrown away, and the posts stood at the court's far east edge, sixteen
    paces from the lane. By the lane's near end they stand in the court at
    its mouth."""
    mutate = _thing("court", "posts", {"kind": "statue", "flank": "lane", "end": "near"},
                    back="n", out="s")
    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    _held(spec, refused, ["court", "lane", "shed", "posts"])
    for k, layout in _seeds(spec):
        rect = _rect(layout, "posts")
        assert _gap(rect, layout.ways["lane"]["rows"][0]) <= 2, (k, rect)
        assert rect.cells() <= layout.areas["court"], k


@pytest.mark.parametrize("answer", [{"kind": "lantern", "side": "n"},
                                    {"kind": "lantern", "by": "court", "side": "n"}])
def test_a_thing_in_open_ground_answered_a_side_its_ground_lacks_stands_in_its_ground(answer):
    """The court lies before the house; a lantern joined to it alone,
    answered north of the house -- or by the court, north of it -- stood
    behind the house where no court was, and was dropped. It stands in its
    court, on the side asked only where the court lies there."""
    _b, spec, _layout, refused = _lay(*_court_plan(_thing("court", "lantern", answer)))
    _held(spec, refused, ["court", "lantern"])
    for k, layout in _seeds(spec):
        assert _rect(layout, "lantern").cells() <= layout.areas["court"], k


def test_a_side_of_the_building_answered_of_a_thing_joined_to_a_way_is_that_side_of_the_way():
    """A lantern the plan joins to the path, answered north: read as north
    of the building it stood where no path was, and was dropped."""
    mutate = _thing("path", "lantern", {"kind": "lantern", "side": "n"})
    _b, spec, _layout, refused = _lay_farm(mutate)
    _held(spec, refused, ["path", "lantern"])
    lantern = next(f for f in spec["grounds"]["features"] if f["id"] == "lantern")
    assert (lantern["by"], lantern["side"]) == ("path", "n")


# ---------------------------------------------------------- outbuildings


def _privy_on_the_hall(answer_side):
    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"].append({"to": "privy", "dir": "s", "barrier": "closed_door"})
        _add(specs, "privy", "the Privy", "a privy", [{"to": "hall", "dir": "n"}])
        sort["grounds"].append({"id": "privy", "is": "outbuilding"})
        relate["grounds"].append({"id": "privy", "side": answer_side})
    return mutate


@pytest.mark.parametrize("answer_side,end", [("e", "e"), ("s", "w")])
def test_an_outbuilding_on_the_entrances_side_never_stands_before_it(answer_side, end):
    """A privy the plan joins to the hall's south wall -- the entrance's --
    with no end of that side named by the plan: centred there, it stood three
    paces before the entrance door, the walk wrapped round it, and the floor
    dropped it. It stands past a corner: toward the end the answer names
    across the plan's side, else the end of the house its room stands at
    (the hall, west of the side room)."""
    plan = _court_plan(_privy_on_the_hall(answer_side))
    _b, _inv, spec = _spec_of(plan)
    block = next(x for x in spec["blocks"] if x["id"] == "privy")
    assert (block["beside"]["side"], block.get("toward")) == ("s", end)
    _b, spec, _layout, refused = _lay(*plan)
    _held(spec, refused, ["court", "lane", "shed", "privy"])
    for k, layout in _seeds(spec):
        main, privy = layout.outlines["main"][0], layout.outlines["privy"][0]
        assert privy.x >= main.x + main.w or privy.x + privy.w <= main.x, (k, privy, main)


def test_an_outbuildings_end_reads_the_join_sides_the_answer_gave():
    """The farm's privy joined to the washroom's south wall, the plan saying
    nowhere which side of the hall the washroom lies; the answer says west.
    Read off the plan's own bearings alone, the washroom lay nowhere, and the
    privy stood before the entrance with the path bent round it -- or, past a
    corner, at the end of the house the washroom is not."""
    def mutate(specs, sort, relate):
        specs["washroom"][1]["adjacent"] = [e for e in specs["washroom"][1]["adjacent"]
                                            if e["to"] != "privy"]
        specs["washroom"][1]["adjacent"].append({"to": "privy", "dir": "s", "barrier": "closed_door"})
        specs["privy"][1]["adjacent"] = [{"to": "washroom", "dir": "n"}]
        for uid, other in (("hall", "washroom"), ("washroom", "hall")):
            for e in specs[uid][1]["adjacent"]:
                if e["to"] == other:
                    e.pop("dir", None)
        next(r for r in relate["rooms"] if r["id"] == "hall")["joins"] = [{"to": "washroom", "side": "w"}]
        # the privy answered on the plan's own side, which names no end
        next(g for g in relate["grounds"] if g["id"] == "privy")["side"] = "s"

    _b, _inv, spec = _farm_spec_of(_farm_plan(mutate))
    block = next(x for x in spec["blocks"] if x["id"] == "privy")
    assert (block["beside"]["side"], block.get("toward")) == ("s", "w")
    _b, spec, _layout, refused = _lay_farm(mutate)
    _held(spec, refused, ["path", "gate", "privy", "garden"])


# ------------------------------------------------------------- the entrance


def test_the_answer_never_moves_the_entrance_the_call_was_shown():
    """The hall opens onto the court and onto an approach on its north wall,
    which the answer says leaves from the entrance. Re-pointed after the call
    had answered against the court's front, the entrance turned north into
    the wall the answer had given the ladder, and the lane and the shed were
    dropped. The entrance stays the one the call was shown; the approach
    leaves from the hall's own door onto it."""
    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"].append({"to": "zapproach", "dir": "n", "barrier": "open_door"})
        _add(specs, "zapproach", "the Approach", "a gravel approach", [{"to": "hall", "dir": "s"}],
             exposure="open")
        sort["grounds"].append({"id": "zapproach", "is": "way"})
        relate["grounds"].append({"id": "zapproach", "from": "entrance"})

    _b, _inv, spec = _spec_of(_court_plan(mutate))
    assert "entrance_to" not in spec and spec["front"] == "s"
    assert next(w for w in spec["grounds"]["ways"] if w["id"] == "zapproach")["from"] == "door"
    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    _held(spec, refused, ["court", "lane", "shed", "zapproach"])


def test_the_relate_call_reads_the_front_of_the_entrance_it_is_shown():
    """A lantern the plan joins to the hall's east wall, its id sorting
    before the path's: the entrance moves off it onto the path, and the call
    was told so -- beside the old entrance's wall as the front, so any left
    or right it read off the lore was turned a quarter."""
    mutate = _thing("hall", "lantern", {"kind": "lantern"}, barrier="open_door")
    plan = _farm_plan(mutate)
    b, inv, spec = _farm_spec_of(plan)
    assert b["entrance"]["to"] == "lantern"           # as the plan alone chose it
    fixed = lb.relate_payload(b, inv)["fixed"]
    assert fixed["entrance"] == {"room": "hall", "opens_onto": "path"}
    assert fixed["front"] == spec["front"] == "s"


def test_the_entrance_never_opens_onto_a_building_apart():
    """A barn the plan joins to the hall's west wall, its id sorting before
    the court's: the entrance opened onto the barn, its walk was never laid
    from the entrance, and the barn was dropped on every seed."""
    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"].append({"to": "barn", "dir": "w", "barrier": "closed_door"})
        _add(specs, "barn", "the Barn", "a barn", [{"to": "hall", "dir": "e"}])
        sort["grounds"].append({"id": "barn", "is": "outbuilding"})
        relate["grounds"].append({"id": "barn", "side": "w"})

    b, _inv, spec = _spec_of(_court_plan(mutate))
    assert b["entrance"]["to"] == "barn"              # as the plan alone chose it
    assert spec["entrance_to"] == "court"
    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    _held(spec, refused, ["barn", "court", "lane", "shed"])


def test_a_place_taken_out_keeps_the_entrance_its_way_opening_through_it():
    """The hall opens onto the path and a yard. The path taken out of the
    ground, the entrance stays where the call was shown it, its way opening
    through the entrance door (`_door_already`): moved onto the yard, the
    entrance would face wherever the yard's own door had to, and on a plan
    whose ground lay on the far side the whole ground went (the fuzz's seed
    66, `test_the_floor_charges_what_failed`)."""
    mutate = _thing("hall", "yard", {"where": "w"}, back="e", out="w", kind="open",
                    barrier="closed_door")
    plan = _farm_plan(mutate)
    b, inv, _spec = _farm_spec_of(plan)
    assert b["entrance"]["to"] == "path"
    taken = lb.without_places(b, ["path"])
    assert lb.entrance_of(taken, inventory=inv)["to"] == "path"
    spec = lb.spec_from_answers(taken, inv, copy.deepcopy(plan[2]))
    assert "entrance_to" not in spec
    assert spec["door_to"]["path"] == "entrance"


def test_a_thing_in_open_ground_answered_across_a_way_stays_in_its_ground():
    """A gate the plan joins to the court alone, answered across the lane:
    across a way stands on that way's own line, out of the court -- kept for
    a thing joined to open ground alone, it would stand across the lane's
    mouth and cost the court its meeting with the lane. Across is held to
    the plan's joins; the gate stands in its court."""
    mutate = _thing("court", "gate", {"kind": "gate", "across": "lane", "end": "near"},
                    back="n", out="s")
    _b, _inv, spec = _spec_of(_court_plan(mutate))
    gate = next(f for f in spec["grounds"]["features"] if f["id"] == "gate")
    assert "across" not in gate and gate["in"] == "court"
    _b, spec, _layout, refused = _lay(*_court_plan(mutate))
    _held(spec, refused, ["court", "lane", "shed", "gate"])
