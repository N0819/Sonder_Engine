"""A new fixture keeps the wall the designer chose; code chooses only where
along it (`world/spatial_pack.py`, `director_rooms._pack`).

The owner's ruling of 2026-10-08: a model decides what a room holds and which
wall each thing stands against; code decides where along that wall, so no
two things share a cell at one height -- and, since 2026-10-13, no two things
standing on the floor share one at any height. Measured on the 31 in-beat first drafts
of the 2026-10-08 play database: 16 came out of their first step clean
through the engine's own loop before this; the inn's seven rerolls of one
beat (chat 165, turn 3) spent their steps moving tables off benches. Code
never moves a fixture to another wall -- the layout lab's fallback did that
to 7 of 53 fixtures on the owner's preferred shrine -- and when a wall cannot
hold what the prose put on it, it says by how much and where each would fit.
"""

from __future__ import annotations

from agents import director_rooms


HALL = {"rooms": {"hall": {"name": "Hall", "desc": "A hall.",
                           "extent": {"w": 6, "d": 4}}},
        "positions": {}}


def _design(steps, scene=HALL, owed=("gallery",)):
    """Run the real loop on scripted steps; return the draft and what each
    step was shown."""
    steps = iter(steps)
    seen = []

    def call(system, payload):
        seen.append(payload)
        return next(steps, {"calls": []})

    record = {}
    draft = director_rooms.design_rooms(None, scene, {}, "sheet", list(owed),
                                        call, record)
    return draft, seen, record


def _gallery(anchors, **extra):
    room = {"name": "Gallery", "desc": "A long gallery.", "extent": {"w": 6, "d": 4},
            "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "s"}],
            "anchors": anchors}
    room.update(extra)
    return {"tool": "draft_room", "args": {"room_id": "gallery", "room": room}}


def test_a_new_fixture_whose_place_is_taken_moves_along_its_own_wall():
    """A four-pace counter on a six-pace north wall takes paces 1-4 from its
    seed, and a stool's seed lands on one of them: the counter keeps its
    seed (it takes more of the wall), the stool moves to the nearest free
    place along the SAME wall."""
    draft, _seen, record = _design([
        {"calls": [_gallery({
            "counter": {"desc": "an oak counter", "dir": "n", "footprint": "run",
                        "height": "waist"},
            "stool": {"desc": "a stool", "dir": "n", "footprint": "point",
                      "height": "waist"}})]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    anchors = draft["rooms"]["gallery"]["anchors"]
    assert "offset" not in anchors["counter"], "a fixture whose place is free keeps it"
    assert anchors["stool"]["dir"] == "n"
    assert anchors["stool"]["offset"] in (0.0, 1.0)
    assert record["final_check"]["clean"] is True


def _seeded_onto(taken, fixture, names):
    """The first of `names` whose seed lays `fixture` on the gallery's north
    wall over any of `taken`'s cells."""
    from world.spatial import anchor_cells
    for name in names:
        room = _gallery({name: dict(fixture)})["args"]["room"]
        cells = anchor_cells({"rooms": {"gallery": room}, "positions": {}},
                             "gallery", raw=True)[name]["cells"]
        if {tuple(c) for c in cells} & taken:
            return name
    raise AssertionError("no seed lands there")


def test_a_thing_hung_over_another_shares_its_cells_and_nothing_moves():
    """The ruling of 2026-10-08, "a cell is taken at one height", kept for
    what is off the floor (2026-10-13): a bottle shelf hung over the bartop
    shares its cells, and neither moves."""
    from world.spatial import anchor_cells
    bartop = {"desc": "a bartop", "dir": "n", "footprint": "run", "height": "waist"}
    room = _gallery({"bartop": dict(bartop)})["args"]["room"]
    under = {tuple(c) for c in anchor_cells({"rooms": {"gallery": room}, "positions": {}},
                                            "gallery", raw=True)["bartop"]["cells"]}
    shelf = {"desc": "a bottle shelf", "dir": "n", "footprint": "point",
             "height": "head", "mount": "hung"}
    name = _seeded_onto(under, shelf, [f"shelf_{i}" for i in range(80)])
    draft, _seen, record = _design([
        {"calls": [_gallery({"bartop": dict(bartop), name: dict(shelf)})]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    anchors = draft["rooms"]["gallery"]["anchors"]
    assert "offset" not in anchors["bartop"] and "offset" not in anchors[name]
    assert record["final_check"]["clean"] is True


def test_two_things_standing_on_the_floor_never_share_a_cell_whatever_their_heights():
    """The owner, 2026-10-13, reading Home 11's map ("stop overlapping
    furnitures"): a cupboard standing against the wall a bartop stands on is
    a second thing on that floor, so it takes the nearest free place along
    its own wall, though the two are of different heights. Until then a cell
    was taken at one height for everything, and a futon lay under a trunk."""
    from world.spatial import anchor_cells
    bartop = {"desc": "a bartop", "dir": "n", "footprint": "run", "height": "waist"}
    room = _gallery({"bartop": dict(bartop)})["args"]["room"]
    under = {tuple(c) for c in anchor_cells({"rooms": {"gallery": room}, "positions": {}},
                                            "gallery", raw=True)["bartop"]["cells"]}
    cupboard = {"desc": "a tall cupboard", "dir": "n", "footprint": "point", "height": "full"}
    name = _seeded_onto(under, cupboard, [f"cupboard_{i}" for i in range(80)])
    draft, _seen, record = _design([
        {"calls": [_gallery({"bartop": dict(bartop), name: dict(cupboard)})]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    anchors = draft["rooms"]["gallery"]["anchors"]
    assert "offset" not in anchors["bartop"], "the one that takes more of the wall keeps its seed"
    assert anchors[name]["dir"] == "n" and "offset" in anchors[name]
    placed = anchor_cells({"rooms": {"gallery": draft["rooms"]["gallery"]}, "positions": {}},
                          "gallery", raw=True)
    assert not {tuple(c) for c in placed[name]["cells"]} & under
    assert record["final_check"]["clean"] is True


def test_fixtures_drafted_together_are_laid_end_to_end_when_a_seed_leaves_no_room():
    """The inn's six-pace west wall held a two-pace long table and a
    four-pace barrel rack exactly; the table's seed left no four paces
    anywhere, so both are laid along the wall, each still on it."""
    draft, _seen, record = _design([
        {"calls": [_gallery({
            "long_table": {"desc": "a long table", "dir": "w", "footprint": "large",
                           "height": "waist"},
            "barrel_rack": {"desc": "a rack of barrels", "dir": "w", "footprint": "run",
                            "height": "waist"}}, extent={"w": 4, "d": 6})]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    anchors = draft["rooms"]["gallery"]["anchors"]
    assert anchors["long_table"]["dir"] == "w" and anchors["barrel_rack"]["dir"] == "w"
    assert record["final_check"]["clean"] is True, record["final_check"]


def test_a_fixture_shown_on_a_plan_is_never_moved_for_a_later_one():
    """The stool is drawn on the first step's plan where its seed put it;
    the counter drafted a step later finds no four paces round it and is
    reported, never fitted by moving the stool."""
    draft, seen, _record = _design([
        {"calls": [_gallery({"stool": {"desc": "a stool", "dir": "n",
                                       "footprint": "point", "height": "waist"}})]},
        {"calls": [{"tool": "draft_room", "args": {"room_id": "gallery", "room": {
            "anchors": {"counter": {"desc": "an oak counter", "dir": "n",
                                    "footprint": "run", "height": "waist"}}}}}]},
        {"calls": []}])
    anchors = draft["rooms"]["gallery"]["anchors"]
    assert "offset" not in anchors["stool"]
    assert anchors["counter"]["dir"] == "n"
    check = [e for e in seen[2]["transcript"] if e["tool"] == "check"][-1]["result"]
    (line,) = check["crowded_walls"]
    assert "north wall" in line and "counter" in line and "yours to choose" in line


def test_a_standing_fixture_and_a_place_the_designer_wrote_are_never_moved():
    scene = {"rooms": {
        "hall": dict(HALL["rooms"]["hall"]),
        "gallery": {"name": "Gallery", "desc": "A long gallery.",
                    "extent": {"w": 6, "d": 4},
                    "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "s"}],
                    "anchors": {"counter": {"desc": "an oak counter", "dir": "n",
                                            "footprint": "run", "height": "waist"}}}},
        "positions": {}}
    draft, _seen, record = _design([
        {"calls": [{"tool": "draft_room", "args": {"room_id": "gallery", "room": {
            "anchors": {
                "stool": {"desc": "a stool", "dir": "n", "footprint": "point",
                          "height": "waist"},
                "bench": {"desc": "a bench", "dir": "n", "footprint": "point",
                          "height": "waist", "offset": 0.5}}}}}]},
        {"calls": []}], scene=scene, owed=("gallery",))
    anchors = draft["rooms"]["gallery"]["anchors"]
    assert "counter" not in anchors, "the standing counter is the world's, not the draft's"
    assert anchors["stool"]["offset"] in (0.0, 1.0)
    assert anchors["bench"]["offset"] == 0.5, "the designer's own place wins"
    assert any("bench" in pair for pair in record["final_check"]["fixtures_overlapping"])


def test_a_corner_fixture_goes_to_the_nearest_cell_of_its_corner_walls():
    draft, _seen, record = _design([
        {"calls": [_gallery({
            "crate": {"desc": "a crate", "dir": "ne", "footprint": "point",
                      "height": "floor"},
            "sack": {"desc": "a sack of meal", "dir": "ne", "footprint": "point",
                     "height": "floor"}})]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    anchors = draft["rooms"]["gallery"]["anchors"]
    moved = [aid for aid in ("crate", "sack") if "cell" in anchors[aid]]
    assert len(moved) == 1
    x, y = anchors[moved[0]]["cell"]
    assert (x, y) in ((4, 0), (5, 1)), "the nearest cell of the north or east wall"
    assert anchors[moved[0]]["dir"] == "ne"
    assert record["final_check"]["clean"] is True


def test_fixtures_laid_end_to_end_keep_clear_of_what_hangs_at_their_own_height():
    """A stuck tall counter's group took in the table standing beside it, and
    every member was checked at the COUNTER's height: the table was laid on
    the waist-high chest hung there, and the packer wrote that overlap
    itself (review of 2026-10-13)."""
    draft, _seen, record = _design([
        {"calls": [_gallery({
            "counter": {"desc": "a tall counter", "dir": "n", "footprint": "small",
                        "height": "full"},
            "table": {"desc": "a long table", "dir": "n", "footprint": "run",
                      "height": "waist"},
            "chest": {"desc": "a spice chest hung on the wall", "dir": "n",
                      "footprint": "point", "height": "waist", "mount": "hung"}})]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    assert record["final_check"]["fixtures_overlapping"] == []
    assert record["final_check"]["clean"] is True


def test_a_wall_too_short_for_what_stands_on_it_is_told_to_the_designer():
    """Six paces of things standing on a four-pace wall, at three heights:
    the check counted one height at a time, called the room clean, and the
    map drew a bench across a counter and a cabinet (review of 2026-10-13).
    Two things standing on the floor share no cell at any height, and the
    wall's line counts every one of them."""
    draft, _seen, record = _design([
        {"calls": [_gallery({
            "counter": {"desc": "an oak counter", "dir": "n", "footprint": "run",
                        "height": "waist"},
            "bench": {"desc": "a low bench", "dir": "n", "footprint": "small",
                      "height": "floor"},
            "cabinet": {"desc": "a tall cabinet", "dir": "n", "footprint": "small",
                        "height": "full"}}, extent={"w": 4, "d": 3})]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    check = record["final_check"]
    assert check["clean"] is False
    assert check.get("fixtures_stuck"), check
    assert any("standing on the floor its fixtures take" in line
               for line in check.get("crowded_walls") or ()), check


# ---------------------------------------------------------------------------
# The second review of 2026-10-13
# ---------------------------------------------------------------------------

def _gallery_draft(anchors, **extra):
    room = dict(_gallery(anchors, **extra)["args"]["room"])
    return {"rooms": {"gallery": room}, "remove_rooms": [], "remove_adjacent": []}


def test_a_window_is_no_thing_standing_on_the_floor():
    """Every bearing in a room's `windows` is a pseudo-anchor of head
    height; read as standing, it clashed with the chest beneath it."""
    draft = _gallery_draft({"chest": {"desc": "a chest", "dir": "n", "cell": [2, 0],
                                      "footprint": "point", "height": "waist"}},
                           windows=[{"id": "w1", "dir": "n", "cell": [2, 0]}])
    result = director_rooms._check(HALL, draft, ["gallery"])
    assert not [o for o in result["fixtures_overlapping"] if "window" in o], result


def test_the_designers_plan_marks_two_things_standing_on_one_cell():
    draft = _gallery_draft({
        "chest": {"desc": "a chest", "cell": [1, 1], "footprint": "point", "height": "waist"},
        "cabinet": {"desc": "a cabinet", "cell": [1, 1], "footprint": "point", "height": "full"}})
    merged = director_rooms._merged(HALL, draft)
    view = director_rooms.render_room(merged, "gallery")
    assert view["map"][1][1] == "!"
    assert any("both stand on the floor" in line for line in view["legend"])


def test_a_wall_line_counts_what_blocks_it_whatever_wall_it_names():
    """The second review's three walls: a bed against the east wall taking
    the north wall's cells, a solver's wardrobe with no wall, a shelf hung
    at the stuck thing's height -- each was missing from the line -- and a
    wall the designer itself overfilled got overlaps and no line."""
    def lines(anchors, w, d):
        result = director_rooms._check(HALL, _gallery_draft(anchors, extent={"w": w, "d": d}),
                                       ["gallery"])
        return [x for x in result.get("crowded_walls") or () if "the north wall" in x]
    bed = lines({"bed": {"desc": "a bed", "dir": "e", "footprint": "large", "height": "waist",
                         "offset": 0.0},
                 "wardrobe": {"desc": "a wardrobe", "dir": "n", "footprint": "small",
                              "height": "full"}}, 3, 5)
    assert bed and all("bed" in x for x in bed), bed
    pinned = lines({"wardrobe": {"desc": "a wardrobe", "cell": [0, 0], "extent": {"w": 2, "d": 1},
                                 "height": "full"},
                    "chest": {"desc": "a chest", "dir": "n", "footprint": "small",
                              "height": "waist"}}, 3, 5)
    assert pinned and all("wardrobe" in x for x in pinned), pinned
    hung = lines({"shelf": {"desc": "a shelf", "dir": "n", "footprint": "small", "height": "waist",
                            "mount": "hung", "offset": 0.0},
                  "bench": {"desc": "a bench", "dir": "n", "footprint": "small", "height": "floor",
                            "offset": 1.0},
                  "counter": {"desc": "a counter", "dir": "n", "footprint": "small",
                              "height": "waist"}}, 4, 3)
    assert hung and all("shelf" in x for x in hung), hung
    # a wall the designer itself overfilled, every place its own: each
    # overlap is named, a step of this design's to settle
    result = director_rooms._check(HALL, _gallery_draft(
        {f"thing_{i}": {"desc": "a thing", "dir": "n", "footprint": "small", "height": h,
                        "offset": o}
         for i, (h, o) in enumerate((("floor", 0.0), ("waist", 0.5), ("full", 1.0)))},
        extent={"w": 4, "d": 3}), ["gallery"])
    assert result["clean"] is False
    assert any("standing on the floor" in o for o in result["fixtures_overlapping"]), result


def test_one_line_for_a_wall_counted_at_a_height_and_standing():
    """A wall overfull at one height whose stuck fixture is counted with
    everything standing there gets the standing line alone."""
    draft = _gallery_draft({
        "rack": {"desc": "a rack", "dir": "w", "footprint": "large", "height": "waist"},
        "chest": {"desc": "a chest", "dir": "w", "footprint": "large", "height": "waist"},
        "stool": {"desc": "a tall stool", "dir": "w", "footprint": "point", "height": "head"}},
        extent={"w": 8, "d": 3})
    result = director_rooms._check(HALL, draft, ["gallery"])
    west = [line for line in result.get("crowded_walls") or () if "the west wall" in line]
    assert len(west) == 1 and "standing on the floor" in west[0], west


def test_fixtures_the_world_already_holds_are_no_overlap_of_this_design():
    """Two fixtures nobody placed, whose raw seeds share a cell at two
    heights, stand apart on the map; a re-draft that touches neither is
    clean (a raw seed's phantom overlap held the designer)."""
    from world.spatial import anchor_cells
    base = {"desc": "a chest", "dir": "n", "footprint": "point", "height": "waist"}
    tall = {"desc": "a cabinet", "dir": "n", "footprint": "point", "height": "full"}
    names = [f"thing_{i}" for i in range(80)]
    seeds = {}
    for name in names:
        room = {"name": "Gallery", "desc": "A gallery.", "extent": {"w": 6, "d": 4},
                "anchors": {name: dict(base)}, "adjacent": []}
        seeds[name] = {tuple(c) for c in anchor_cells({"rooms": {"gallery": room}, "positions": {}},
                                                      "gallery", raw=True)[name]["cells"]}
    a, b = next((x, y) for i, x in enumerate(names) for y in names[i + 1:] if seeds[x] & seeds[y])
    world = {"rooms": dict(HALL["rooms"], gallery={
        "name": "Gallery", "desc": "A gallery.", "extent": {"w": 6, "d": 4},
        "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "s"}],
        "anchors": {a: dict(base), b: dict(tall)}}), "positions": {}}
    result = director_rooms._check(world, {"rooms": {"gallery": {"desc": "The gallery, dusted."}},
                                           "remove_rooms": [], "remove_adjacent": []}, ["gallery"])
    assert not [o for o in result["fixtures_overlapping"] if "standing on the floor" in o], result


# ---------------------------------------------------------------------------
# The third review of 2026-10-13
# ---------------------------------------------------------------------------

def test_a_fixture_only_re_described_owns_no_overlap_the_world_held():
    world = {"rooms": dict(HALL["rooms"], gallery={
        "name": "Gallery", "desc": "A gallery.", "extent": {"w": 6, "d": 4},
        "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "s"}],
        "anchors": {"chest": {"desc": "a chest", "cell": [1, 0], "footprint": "point",
                              "height": "waist"},
                    "cabinet": {"desc": "a cabinet", "cell": [1, 0], "footprint": "point",
                                "height": "full"}}}), "positions": {}}
    draft = {"rooms": {"gallery": {"anchors": {"chest": {"desc": "a cedar chest"}}}},
             "remove_rooms": [], "remove_adjacent": []}
    result = director_rooms._check(world, draft, ["gallery"])
    assert not [o for o in result["fixtures_overlapping"] if "standing on the floor" in o], result
    draft["rooms"]["gallery"]["anchors"]["chest"]["cell"] = [1, 0]
    result = director_rooms._check(world, draft, ["gallery"])
    assert [o for o in result["fixtures_overlapping"] if "standing on the floor" in o], result


def test_every_standing_overlap_the_check_names_the_plan_marks():
    draft = _gallery_draft({
        "chest": {"desc": "a chest", "dir": "n", "offset": 0.0, "footprint": "small",
                  "height": "waist"},
        "cabinet": {"desc": "a cabinet", "dir": "n", "offset": 0.0, "footprint": "small",
                    "height": "full"},
        "stool": {"desc": "a stool", "dir": "n", "footprint": "point", "height": "floor"}})
    result = director_rooms._check(HALL, draft, ["gallery"])
    named = [o for o in result["fixtures_overlapping"] if "standing on the floor" in o]
    assert named
    merged = director_rooms._merged(HALL, draft)
    view = director_rooms.render_room(merged, "gallery")
    for line in named:
        cell = eval(line.split(" share ")[1].split(",")[0] + "," + line.split(" share ")[1].split(",")[1])
        assert view["map"][cell[1]][cell[0]] == "!", (line, view["map"])


def test_a_wall_line_names_a_blocker_of_its_own_height_on_another_wall():
    draft = _gallery_draft({
        "bed": {"desc": "a bed", "dir": "e", "footprint": "large", "height": "full", "offset": 0.0},
        "wardrobe": {"desc": "a wardrobe", "dir": "n", "footprint": "small", "height": "full"}},
        extent={"w": 3, "d": 5})
    result = director_rooms._check(HALL, draft, ["gallery"])
    north = [x for x in result.get("crowded_walls") or () if "the north wall" in x]
    assert north and all("bed" in x for x in north), result.get("crowded_walls")


def test_a_wall_line_counts_paces_along_the_wall_never_a_band_of_cells():
    draft = _gallery_draft({
        "table": {"desc": "a table", "dir": "n", "footprint": "large", "height": "waist",
                  "offset": 0.0},
        "chest": {"desc": "a chest", "dir": "n", "footprint": "large", "height": "floor"}},
        extent={"w": 3, "d": 4})
    result = director_rooms._check(HALL, draft, ["gallery"])
    north = [x for x in result.get("crowded_walls") or () if "the north wall" in x]
    assert north, result
    import re
    for line in north:
        took = int(re.search(r"its fixtures take (\d+)", line).group(1))
        assert took <= 4, line


# ---------------------------------------------------------------------------
# The fourth review of 2026-10-13: the check, the plan and the packer read
# every fixture where the map stands it
# ---------------------------------------------------------------------------

def _plan_marks(world, draft, room):
    view = director_rooms.render_room(director_rooms._merged(world, draft), room)
    return view["map"]


def _standing_named(result):
    return [o for o in result["fixtures_overlapping"] if "standing on the floor" in o]


def test_a_fixture_written_onto_one_nobody_placed_is_named_and_marked():
    """A world fixture nobody placed is still where the map stands it: a
    cabinet the designer writes onto a chest whose wall has no other place
    for it, and a chest written onto a bench the map had to stand beside its
    seed, were both called clean and both committed (fourth review)."""
    nook = {"rooms": dict(HALL["rooms"], nook={
        "name": "Nook", "desc": "A nook.", "extent": {"w": 3, "d": 2},
        "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "w"}],
        "anchors": {"chest": {"desc": "a sea chest", "dir": "e", "footprint": "small",
                              "height": "waist"}}}), "positions": {}}
    draft = {"rooms": {"nook": {"anchors": {"cabinet": {
        "desc": "a tall cabinet", "cell": [2, 0], "footprint": "point", "height": "full"}}}},
        "remove_rooms": [], "remove_adjacent": []}
    result = director_rooms._check(nook, draft, ["nook"])
    assert result["clean"] is False and _standing_named(result), result
    assert _plan_marks(nook, draft, "nook")[0][2] == "!"
    gallery = {"rooms": dict(HALL["rooms"], gallery={
        "name": "Gallery", "desc": "A gallery.", "extent": {"w": 4, "d": 3},
        "adjacent": [{"to": "hall", "barrier": "door", "dir": "s"}],
        "anchors": {"bench": {"desc": "a low bench", "dir": "n", "footprint": "small",
                              "height": "floor"}}}), "positions": {}}
    draft = {"rooms": {"gallery": {"anchors": {"chest": {
        "desc": "an iron-bound chest", "dir": "n", "offset": 0.5, "footprint": "small",
        "height": "waist"}}}}, "remove_rooms": [], "remove_adjacent": []}
    result = director_rooms._check(gallery, draft, ["gallery"])
    named = _standing_named(result)
    assert result["clean"] is False and named, result
    for line in named:
        x, y = (int(v) for v in line.split(" share (")[1].split(")")[0].split(", "))
        assert _plan_marks(gallery, draft, "gallery")[y][x] == "!", line


def test_a_corner_fixture_is_where_the_check_reads_it():
    """A corner is a place somebody chose, which read-time placement never
    moves; read as a seed, a cabinet written onto a corner stove was called
    clean (fourth review)."""
    world = {"rooms": dict(HALL["rooms"], gallery={
        "name": "Gallery", "desc": "A gallery.", "extent": {"w": 4, "d": 3},
        "adjacent": [{"to": "hall", "barrier": "door", "dir": "s"}],
        "anchors": {"stove": {"desc": "an iron stove", "dir": "ne", "footprint": "point",
                              "height": "waist"}}}), "positions": {}}
    for cabinet in ({"desc": "a tall cabinet", "cell": [3, 0], "footprint": "point",
                     "height": "full"},
                    {"desc": "a tall cabinet", "dir": "n", "offset": 1.0, "footprint": "small",
                     "height": "full"}):
        draft = {"rooms": {"gallery": {"anchors": {"cabinet": cabinet}}},
                 "remove_rooms": [], "remove_adjacent": []}
        result = director_rooms._check(world, draft, ["gallery"])
        assert result["clean"] is False and _standing_named(result), (cabinet, result)
        assert _plan_marks(world, draft, "gallery")[0][3] == "!"


def test_taking_a_fixture_off_what_it_stood_on_is_writing_its_place():
    """`mount` decides whether a thing stands on the floor: a lamp the draft
    takes off its table stands on the table's cell, and a draft that changed
    only that was never read as placing it (fourth review)."""
    world = {"rooms": dict(HALL["rooms"], gallery={
        "name": "Gallery", "desc": "A gallery.", "extent": {"w": 5, "d": 4},
        "adjacent": [{"to": "hall", "barrier": "door", "dir": "s"}],
        "anchors": {"table": {"desc": "a table", "cell": [1, 1], "footprint": "small",
                              "height": "waist"},
                    "lamp": {"desc": "a lamp on the table", "cell": [1, 1],
                             "footprint": "point", "height": "head", "mount": "on table"}}}),
             "positions": {}}
    assert director_rooms._check(world, {"rooms": {"gallery": {"desc": "The gallery."}},
                                         "remove_rooms": [], "remove_adjacent": []},
                                 ["gallery"])["clean"] is True
    draft = {"rooms": {"gallery": {"anchors": {"lamp": {"desc": "a tall standing lamp",
                                                        "mount": "floor"}}}},
             "remove_rooms": [], "remove_adjacent": []}
    result = director_rooms._check(world, draft, ["gallery"])
    assert result["clean"] is False and _standing_named(result), result


def test_a_seed_kept_in_a_doorways_way_is_named_where_the_map_stands_it():
    """No place along its wall clear of a doorway and of what stands there:
    the packer keeps the seed and writes nothing, the map -- giving up a
    shared cell before a doorway -- stands it on the counter, and the check
    names that pair where the plan draws it, for the designer to move one
    (third, fourth and fifth reviews of 2026-10-13: read by its seed it was
    called clean; pinned in front of the door by code, it was frozen into a
    filed design). A place the designer writes stands where it was put."""
    world = {"rooms": dict(HALL["rooms"]), "positions": {}}
    room = {"name": "Store", "desc": "A store.", "extent": {"w": 3, "d": 4},
            "adjacent": [{"to": "hall", "barrier": "door", "dir": "e"}],
            "anchors": {"m0": {"desc": "a long shelf-counter", "footprint": "run",
                               "height": "waist", "dir": "n"},
                        "m2": {"desc": "a heap of sacks", "footprint": "large",
                               "height": "floor", "dir": "w"}}}
    draft = {"rooms": {"r": room}, "remove_rooms": [], "remove_adjacent": []}
    placed = {}
    director_rooms._pack(world, draft, placed)
    director_rooms._pack(world, draft, placed, settle=True)
    assert not {"offset", "cell"} & set(room["anchors"]["m2"]), room["anchors"]["m2"]
    result = director_rooms._check(world, draft, ["r"], settled=set(placed))
    named = _standing_named(result)
    assert result["clean"] is False and named, result
    for line in named:
        x, y = (int(v) for v in line.split(" share (")[1].split(")")[0].split(", "))
        assert _plan_marks(world, draft, "r")[y][x] == "!", line
    room["anchors"]["m2"]["offset"] = 0.5
    assert director_rooms._check(world, draft, ["r"], settled=set(placed))["clean"] is True


def test_a_wall_the_designer_overfilled_by_its_own_places_gets_its_line():
    """Six paces of things standing on a four-pace wall, every place the
    designer's own, at three heights: the overlaps were named and the wall's
    line was lost (fourth review; the second review's line)."""
    draft = _gallery_draft({
        "counter": {"desc": "a counter", "dir": "n", "footprint": "run", "height": "waist",
                    "offset": 0.0},
        "bench": {"desc": "a bench", "dir": "n", "footprint": "small", "height": "floor",
                  "offset": 0.5},
        "cabinet": {"desc": "a cabinet", "dir": "n", "footprint": "small", "height": "full",
                    "offset": 1.0}}, extent={"w": 4, "d": 3})
    placed = {}
    director_rooms._pack(HALL, draft, placed, settle=True)
    result = director_rooms._check(HALL, draft, ["gallery"], settled=set(placed))
    north = [x for x in result.get("crowded_walls") or () if "the north wall" in x]
    assert north and "standing on the floor its fixtures take 6" in north[0], result


def test_a_seed_the_map_never_drew_leaves_nothing_stuck():
    """A world fixture's seed the map never drew: the packer, reading the
    seed, left a new chest no place on a wall the map had room on, and a
    clean design was refused as stuck (chat 173's shrine hall; fourth
    review). Stuck is the map's word: standing clear and moving nothing, the
    chest is not stuck. The room's own ids are kept, since a seed is drawn
    from them."""
    world = {"rooms": {
        "shrine_hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 4, "d": 4},
                        "exposure": "enclosed", "adjacent": [
                            {"to": "court", "barrier": "closed_door", "dir": "s", "offset": 0.6667},
                            {"to": "side", "barrier": "closed_door", "dir": "e", "offset": 0.6667},
                            {"to": "loft", "barrier": "open", "width": 4, "dir": "n",
                             "offset": 0.6667}],
                        "anchors": {"offering_place": {"desc": "an offering place",
                                                       "footprint": "large", "height": "floor"},
                                    "kami_shrine": {"desc": "a shrine", "cell": [3, 0],
                                                    "extent": {"w": 1, "d": 2},
                                                    "footprint": "small", "height": "waist",
                                                    "dir": "n"}}},
        **{rid: {"name": rid, "desc": "Beyond.", "extent": {"w": 4, "d": 4}, "adjacent": []}
           for rid in ("court", "side", "loft")}}, "positions": {}}
    from world.spatial import anchor_cells
    live = anchor_cells(world, "shrine_hall")["offering_place"]["cells"]
    raw = anchor_cells(world, "shrine_hall", raw=True)["offering_place"]["cells"]
    assert live != raw, "the case needs a seed the map does not draw"
    draft = {"rooms": {"shrine_hall": {"anchors": {"chest": {
        "desc": "a cedar chest", "dir": "n", "footprint": "small", "height": "waist"}}}},
        "remove_rooms": [], "remove_adjacent": []}
    placed = {}
    director_rooms._pack(world, draft, placed, settle=True)
    director_rooms._pack(world, draft, placed)
    result = director_rooms._check(world, draft, ["shrine_hall"], settled=set(placed))
    assert not result.get("fixtures_stuck") and result["clean"] is True, result


def test_every_wall_line_counts_each_thing_where_the_map_stands_it():
    """Two walls too full in one room: the second line counted by seeds once
    the first had named a stuck fixture, and missed a floor-high thing the
    map stood on its wall (fourth review)."""
    world = {"rooms": dict(HALL["rooms"], r={
        "name": "R", "desc": "a room", "extent": {"w": 5, "d": 3},
        "adjacent": [{"to": "hall", "barrier": "door", "dir": "n"}],
        "anchors": {"o0": {"desc": "x", "footprint": "point", "height": "head", "dir": "w"},
                    "o1": {"desc": "x", "footprint": "large", "height": "waist", "dir": "sw"},
                    "o2": {"desc": "x", "footprint": "run", "height": "full", "dir": "ne",
                           "cell": [3, 0]}}}), "positions": {}}
    draft = {"rooms": {"r": {"anchors": {
        "m0": {"desc": "x", "footprint": "large", "height": "floor", "dir": "n"},
        "m1": {"desc": "x", "footprint": "point", "height": "head", "dir": "e",
               "offset": 0.55}}}}, "remove_rooms": [], "remove_adjacent": []}
    placed = {}
    director_rooms._pack(world, draft, placed, settle=True)
    director_rooms._pack(world, draft, placed)
    result = director_rooms._check(world, draft, ["r"], settled=set(placed))
    lines = result.get("crowded_walls") or []
    assert any("the north wall" in x and "no place along it holds m0" in x for x in lines), lines
    west = [x for x in lines if "the west wall" in x]
    assert west and "m0 2" in west[0], lines


# ---------------------------------------------------------------------------
# The fifth review of 2026-10-13
# ---------------------------------------------------------------------------

def test_a_world_fixture_code_placed_gives_way_to_a_new_ones_place():
    """A world fixture nobody placed stands aside for a place written: read
    as fixed where the map stood it, the desk left a new cabinet no place on
    a wall the map had room on, and 30 of 4,080 one-fixture drafts on the
    play db's rooms were refused with an overlap committed (chat 22's ready
    room; fifth review). The room's own ids are kept, since a seed is drawn
    from them."""
    world = {"rooms": {
        "room_ready_room": {"name": "Ready Room", "desc": "A ready room.", "size": "small",
                            "adjacent": [{"to": "room_bridge", "barrier": "open_door",
                                          "distance": "near", "dir": "s"}],
                            "anchors": {"desk": {"desc": "a desk", "dir": None},
                                        "sofa": {"desc": "a small sofa", "dir": None},
                                        "replicator": {"desc": "a replicator", "dir": None},
                                        "viewport": {"desc": "a window on the stars",
                                                     "dir": "n"}}},
        "room_bridge": {"name": "Bridge", "desc": "A bridge.", "adjacent": []}},
        "positions": {}}
    from world.spatial import anchor_cells
    assert anchor_cells(world, "room_ready_room")["desk"]["cells"] != \
        anchor_cells(world, "room_ready_room", raw=True)["desk"]["cells"]
    draft = {"rooms": {"room_ready_room": {"anchors": {"cabinet": {
        "desc": "a cabinet", "dir": "n", "footprint": "large", "height": "waist"}}}},
        "remove_rooms": [], "remove_adjacent": []}
    placed = {}
    director_rooms._pack(world, draft, placed, settle=True)
    director_rooms._pack(world, draft, placed)
    result = director_rooms._check(world, draft, ["room_ready_room"], settled=set(placed))
    assert result["clean"] is True and not result.get("fixtures_stuck"), result


def test_a_same_height_pair_the_world_already_held_is_the_worlds():
    """Read-time placement stood a tokonoma whose seed lay in a stair's
    doorway on the closet beside it, at one height; every design of that
    hall was refused for it, a re-description included (chat 172's main
    hall; fifth review). A pair of two things the draft placed nowhere is
    the world's; one the draft placed is the draft's."""
    stub = {"desc": "Beyond.", "adjacent": []}
    world = {"rooms": {
        "main_hall": {"name": "Main Hall", "desc": "A hall.", "extent": {"w": 8, "d": 5},
                      "shape": "rectangle", "adjacent": [
                          {"to": "genkan", "dir": "s", "offset": 0.5714, "barrier": "open"},
                          {"to": "kitchen", "dir": "e", "offset": 1.0, "barrier": "open"},
                          {"to": "washroom", "dir": "e", "offset": 0.25, "barrier": "open"},
                          {"to": "cellar_stair", "barrier": "closed_door", "dir": "n",
                           "offset": 0.8571},
                          {"to": "upper_stair", "barrier": "closed_door", "dir": "n",
                           "offset": 0.4286}],
                      "anchors": {
                          "chabudai_table": {"desc": "a low table", "cell": [3, 1],
                                             "extent": {"w": 2, "d": 2}, "footprint": "large",
                                             "height": "floor"},
                          "hibachi_brazier": {"desc": "a brazier", "footprint": "small",
                                              "height": "waist"},
                          "zabuton_cushions": {"desc": "cushions", "cell": [4, 3],
                                               "extent": {"w": 1, "d": 1}, "footprint": "point",
                                               "height": "floor"},
                          "oshiiire": {"desc": "a closet", "cell": [0, 0], "extent": {"w": 2, "d": 4},
                                       "footprint": "large", "height": "full", "dir": "w"},
                          "painted_screens": {"desc": "screens", "cell": [6, 1],
                                              "extent": {"w": 1, "d": 2}, "footprint": "small",
                                              "height": "head"},
                          "tokonoma": {"desc": "an alcove", "footprint": "small",
                                       "height": "full", "dir": "n"}}},
        **{rid: dict(stub, name=rid) for rid in ("genkan", "kitchen", "washroom",
                                                 "cellar_stair", "upper_stair")}},
        "positions": {}}
    from world.spatial import anchor_cells
    live = anchor_cells(world, "main_hall")
    assert set(map(tuple, live["tokonoma"]["cells"])) & set(map(tuple, live["oshiiire"]["cells"]))
    result = director_rooms._check(world, {"rooms": {"main_hall": {"desc": "The hall, swept."}},
                                           "remove_rooms": [], "remove_adjacent": []},
                                   ["main_hall"])
    assert result["clean"] is True, result
    touched = {"rooms": {"main_hall": {"anchors": {"tokonoma": {"cell": [1, 0]}}}},
               "remove_rooms": [], "remove_adjacent": []}
    result = director_rooms._check(world, touched, ["main_hall"])
    assert any("at height full" in o for o in result["fixtures_overlapping"]), result


def test_a_fixture_the_map_stands_clear_moving_nothing_is_not_stuck():
    """The packer's reading of the room left no place for a hung lamp the
    map stood clear, moving nothing; the design was refused as stuck
    (random room 625 of 1,500; fifth review). One the map stands clear only
    by moving another stays stuck."""
    world = {"rooms": dict(HALL["rooms"], r={
        "name": "R", "desc": "a room", "extent": {"w": 6, "d": 5},
        "adjacent": [{"to": "hall", "barrier": "door", "dir": "s"}],
        "anchors": {"o0": {"desc": "x", "footprint": "point", "height": "head", "dir": "nw"},
                    "o1": {"desc": "x", "footprint": "large", "height": "floor", "dir": "s"},
                    "o2": {"desc": "x", "footprint": "point", "height": "waist", "dir": "w"},
                    "o3": {"desc": "x", "footprint": "run", "height": "full", "dir": "s",
                           "offset": 0.61}}}), "positions": {}}
    draft = {"rooms": {"r": {"anchors": {
        "m0": {"desc": "x", "footprint": "point", "height": "head", "dir": "s"},
        "m1": {"desc": "x", "footprint": "small", "height": "floor", "dir": "se"},
        "m2": {"desc": "x", "footprint": "run", "height": "head"},
        "m3": {"desc": "x", "footprint": "large", "height": "head", "dir": "n"}}}},
        "remove_rooms": [], "remove_adjacent": []}
    placed = {}
    director_rooms._pack(world, draft, placed, settle=True)
    director_rooms._pack(world, draft, placed)
    result = director_rooms._check(world, draft, ["r"], settled=set(placed))
    assert "r.m0" not in (result.get("fixtures_stuck") or []), result
