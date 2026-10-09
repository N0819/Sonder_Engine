"""A new fixture keeps the wall the designer chose; code chooses only where
along it (`world/spatial_pack.py`, `director_rooms._pack`).

The owner's ruling of 2026-10-08: a model decides what a room holds and which
wall each thing stands against; code decides where along that wall, so no
two things share a cell at one height. Measured on the 31 in-beat first drafts
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


def test_two_heights_share_a_cell_and_nothing_moves():
    draft, _seen, record = _design([
        {"calls": [_gallery({
            "bartop": {"desc": "a bartop", "dir": "n", "footprint": "run",
                       "height": "waist"},
            "shelf": {"desc": "a bottle shelf", "dir": "n", "footprint": "run",
                      "height": "head"}})]},
        {"calls": [{"tool": "submit", "args": {}}]}])
    anchors = draft["rooms"]["gallery"]["anchors"]
    assert "offset" not in anchors["bartop"] and "offset" not in anchors["shelf"]
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
