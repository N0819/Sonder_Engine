"""A place CODE chooses for a fixture keeps the ways in and out clear.

The owner, reading Home 9 (chat 172, 2026-10-12): "a lot of oddities like
furniture being placed in front of doors" -- and every one of the eleven
there was a code placement: the layout solver kept a doorway's step clear but
not the pace inside it, and a fixture nobody placed was laid by its seed,
which by the ruling of 2026-09-16 reserved nothing, two pairs of them stacked
on one cell. The owner: go ahead. So a place code chooses -- the seed, the
packer, the solver -- keeps clear of every doorway's step and the pace inside
it and of every cell another fixture holds at its height, while a place a
story or a host makes stands where it was put ("an object in front of a door
is entirely spatially valid" still holds for those).
"""
from __future__ import annotations

import copy


def _scene(anchors, *, door=("closed_door", "s", 0.5), extent=(6, 5)):
    barrier, wall, offset = door
    hall = {"name": "Hall", "desc": "A hall.", "exposure": "enclosed",
            "extent": {"w": extent[0], "d": extent[1]}, "anchors": copy.deepcopy(anchors),
            "adjacent": [{"to": "yard", "barrier": barrier, "dir": wall, "offset": offset}]}
    yard = {"name": "Yard", "desc": "A yard.", "exposure": "enclosed", "extent": {"w": 6, "d": 6},
            "adjacent": []}
    return {"rooms": {"hall": hall, "yard": yard}, "positions": {}, "stations": {}, "entities": {}}


def _cells(rec):
    return {tuple(c) for c in rec["cells"]}


def _doorway(sc):
    from world.spatial import anchor_cells
    step = _cells(anchor_cells(sc, "hall")["door:yard"])
    return step, {(x, y - 1) for x, y in step}          # a south wall: the pace inside is north


def _seeded_into(sc, anchor, cells, names):
    """The first of `names` whose SEED alone (`raw`) puts `anchor` on any of
    `cells` -- found, never typed, so the test holds whatever the seeds are."""
    from world.spatial import anchor_cells
    for name in names:
        trial = copy.deepcopy(sc)
        trial["rooms"]["hall"]["anchors"] = {name: dict(anchor)}
        if _cells(anchor_cells(trial, "hall", raw=True)[name]) & cells:
            return name
    raise AssertionError("no seed lands there; widen the names")


def test_a_fixture_code_places_never_stands_in_a_doorway():
    from world.spatial import anchor_cells
    sc = _scene({})
    step, inner = _doorway(sc)
    chest = {"desc": "a chest", "dir": "s", "footprint": "point", "height": "waist"}
    against = _seeded_into(sc, chest, step, [f"chest_{i}" for i in range(80)])
    stool = {"desc": "a stool", "footprint": "point", "height": "waist"}
    loose = _seeded_into(sc, stool, step | inner, [f"stool_{i}" for i in range(400)])
    sc["rooms"]["hall"]["anchors"] = {against: chest, loose: stool}
    placed = anchor_cells(sc, "hall")
    for aid in (against, loose):
        assert not _cells(placed[aid]) & (step | inner), (aid, placed[aid]["cells"])
    assert placed[against]["dir"] == "s" and all(y == 4 for _x, y in placed[against]["cells"]), \
        "it keeps the wall it was given"
    raw = anchor_cells(sc, "hall", raw=True)
    assert _cells(raw[against]) & step, "the raw reading is the seed's arithmetic"


def test_a_place_a_story_or_a_host_made_stands_in_the_doorway():
    from world.spatial import anchor_cells
    sc = _scene({})
    step, _inner = _doorway(sc)
    (cell,) = step
    sc["rooms"]["hall"]["anchors"] = {"screen": {"desc": "a screen across the door",
                                                 "cell": list(cell), "height": "head"}}
    assert _cells(anchor_cells(sc, "hall")["screen"]) == {cell}


def test_two_fixtures_code_places_on_the_floor_share_no_cell_at_any_height():
    """What stands on the floor holds it at every height (the owner,
    2026-10-13, after Home 11 laid a futon under a trunk and a stove in a
    tub); only a thing off the floor -- hung, from the ceiling, on or in
    another fixture -- shares cells with what stands beneath it, the ruling
    of 2026-10-08 kept for those."""
    from world.spatial import anchor_cells
    sc = _scene({}, door=("closed_door", "n", 0.0))
    first = {"desc": "a bench", "dir": "s", "footprint": "point", "height": "waist"}
    names = [f"bench_{i}" for i in range(60)]
    raw = {}
    for name in names:
        trial = copy.deepcopy(sc)
        trial["rooms"]["hall"]["anchors"] = {name: dict(first)}
        raw[name] = _cells(anchor_cells(trial, "hall", raw=True)[name])
    a, b = next((x, y) for i, x in enumerate(names) for y in names[i + 1:] if raw[x] & raw[y])
    sc["rooms"]["hall"]["anchors"] = {a: dict(first), b: dict(first)}
    placed = anchor_cells(sc, "hall")
    assert not _cells(placed[a]) & _cells(placed[b])
    # standing on the floor at two heights, still two things on one floor
    sc["rooms"]["hall"]["anchors"] = {a: dict(first), b: dict(first, height="full")}
    placed = anchor_cells(sc, "hall")
    assert not _cells(placed[a]) & _cells(placed[b])
    # hung above it, it shares: a bench and the rack over it
    for mount in ("hung", "ceiling", f"on {a}"):
        sc["rooms"]["hall"]["anchors"] = {a: dict(first), b: dict(first, height="head", mount=mount)}
        placed = anchor_cells(sc, "hall")
        assert _cells(placed[a]) & _cells(placed[b]) == raw[a] & raw[b], mount


def test_a_place_code_chooses_holds_the_fixture_whole_where_one_can():
    """A place at the room's edge clips a fixture's footprint, and a
    clipped place, with fewer cells, always crowds less: a large table moved
    off a chest took the two cells of the last column beside it rather than
    the whole square one pace south (2026-10-13, found while the floor rule
    landed). Of the places that crowd nothing, one that holds the fixture
    whole is taken first (`spatial_fov.whole_cells`)."""
    from world.spatial import anchor_cells, room_grid
    sc = _scene({}, door=("closed_door", "n", 0.0), extent=(6, 6))
    grid = room_grid(sc, "hall")
    table = {"desc": "a large table", "footprint": "large", "height": "waist"}
    found = 0
    for i in range(400):
        name = f"table_{i}"
        trial = copy.deepcopy(sc)
        trial["rooms"]["hall"]["anchors"] = {name: dict(table)}
        seed = anchor_cells(trial, "hall", raw=True)[name]["cells"][0]
        if seed[0] != grid.w - 2 or seed[1] > grid.d - 3 or seed[1] < 2:
            continue
        found += 1
        trial["rooms"]["hall"]["anchors"]["chest"] = {
            "desc": "a chest", "cell": list(seed), "footprint": "point", "height": "waist"}
        placed = anchor_cells(trial, "hall")
        assert len(placed[name]["cells"]) == 4, (name, seed, placed[name]["cells"])
        assert tuple(seed) not in _cells(placed[name])
    assert found, "no seed lands there; widen the names"


def test_nothing_is_kept_clear_beneath_a_window():
    from world.spatial import anchor_cells
    sc = _scene({}, door=("window", "s", 0.5))
    pane = _cells(anchor_cells(sc, "hall")["door:yard"])
    chest = {"desc": "a chest", "dir": "s", "footprint": "point", "height": "waist"}
    name = _seeded_into(sc, chest, pane, [f"chest_{i}" for i in range(80)])
    sc["rooms"]["hall"]["anchors"] = {name: chest}
    assert _cells(anchor_cells(sc, "hall")[name]) & pane


def test_the_solver_keeps_the_pace_inside_a_doorway_clear():
    from world.layout_solver import _STEP, solve
    from test_layout_solver import TAVERN
    lay = solve(TAVERN)
    keep = set()
    for door in lay.doors:
        if "tap" not in (door["a"], door["b"]):
            continue
        (x, y), (dx, dy) = door["cell"], _STEP[door["side"]]
        keep |= {(x, y), (x - dx, y - dy)} if door["a"] == "tap" else {(x + dx, y + dy), (x + 2 * dx, y + 2 * dy)}
    for fx in lay.fixtures["tap"]:
        assert not fx["rect"].cells() & keep, fx["id"]


def test_the_designer_moves_a_new_fixture_out_of_a_doorway_along_its_wall():
    from agents import director_rooms
    from world.spatial import anchor_cells
    hall = {"rooms": {"hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 6, "d": 4}}},
            "positions": {}}
    gallery = {"name": "Gallery", "desc": "A long gallery.", "extent": {"w": 6, "d": 4},
               "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "s", "offset": 0.4}]}
    probe = copy.deepcopy(hall)
    probe["rooms"]["gallery"] = dict(gallery, anchors={})
    step = _cells(anchor_cells(probe, "gallery")["door:hall"])
    chest = {"desc": "a chest", "dir": "s", "footprint": "point", "height": "waist"}
    name = None
    for i in range(80):
        trial = copy.deepcopy(probe)
        trial["rooms"]["gallery"]["anchors"] = {f"chest_{i}": chest}
        if _cells(anchor_cells(trial, "gallery", raw=True)[f"chest_{i}"]) & step:
            name = f"chest_{i}"
            break
    assert name
    steps = iter([{"calls": [{"tool": "draft_room", "args": {"room_id": "gallery",
                                                              "room": dict(gallery, anchors={name: chest})}}]},
                  {"calls": [{"tool": "submit", "args": {}}]}])
    record = {}
    draft = director_rooms.design_rooms(None, hall, {}, "sheet", ["gallery"],
                                        lambda system, payload: next(steps, {"calls": []}), record)
    anchors = draft["rooms"]["gallery"]["anchors"]
    assert anchors[name]["dir"] == "s" and anchors[name].get("offset") is not None, \
        "pinned along its own wall, for good"
    merged = copy.deepcopy(hall)
    merged["rooms"]["gallery"] = draft["rooms"]["gallery"]
    assert not _cells(anchor_cells(merged, "gallery", raw=True)[name]) & step
    assert record["final_check"]["clean"] is True
