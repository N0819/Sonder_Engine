"""The Writers' Room can author geometry (F47), and a way up (PA7).

Measured 2026-09-05, in all five play runs: a planner asked in plain words
for a room "four paces wide and twenty long" had nowhere to put the
measurement, so it went into `purpose` prose and the room materialised
sizeless; asked for a loft above the watch room, it produced an edge with
`bearing: "up"` and `barrier: "wall"` -- the one word that said what it
meant sat in a field that holds compass points, and the way up sealed.

These pin the plan side of both: what `plan_rooms` accepts, that the values
it accepts are the ones the SCENE reads, and that an unreadable measurement
changes nothing. What the planted skeleton then carries into the live scene
is `world/structure.py`'s (see the report accompanying this commit).
"""

import pytest

from story.plot_packages import _plan_edge, _shape_plan_rooms


def _plan(rooms, key="lighthouse"):
    return _shape_plan_rooms({"structure": {"key": key}, "rooms": rooms})


def test_a_room_asked_for_in_paces_gets_an_extent_a_shape_and_an_exposure():
    """The caravanserai's "four paces wide and twenty long", as a field."""
    shaped = _plan({"stall_range": {
        "name": "Stall range", "purpose": "where the beasts are kept",
        "extent": {"w": 4, "d": 20}, "shape": "rectangle",
        "exposure": "sheltered"}})["rooms"]["stall_range"]
    assert shaped["extent"] == {"w": 4, "d": 20}
    assert shaped["shape"] == "rectangle"
    assert shaped["exposure"] == "sheltered"


def test_the_scene_reads_what_the_plan_wrote():
    """Not "a field exists" -- the room's own readers answer from it."""
    from world.spatial import effective_room_size, room_grid, size_from_extent
    from world.weather import room_exposure

    shaped = _plan({"lamp_room": {
        "name": "Lamp room", "extent": {"w": 12, "d": 12}, "shape": "round",
        "exposure": "open"}})["rooms"]["lamp_room"]
    scene = {"rooms": {"lamp_room": dict(shaped)}}

    grid = room_grid(scene, "lamp_room")
    assert (grid.w, grid.d) == (12, 12), (
        "the plan's paces must be the grid the scene reasons over, not a "
        "size word derived from a default")
    assert size_from_extent(shaped["extent"]) == effective_room_size(
        scene, "lamp_room")
    assert room_exposure(scene, "lamp_room") == "open"


def test_the_measurement_is_clamped_by_the_worlds_own_normalizer():
    """`plan_rooms` restates no vocabulary: the paces bounds are the
    engine's, so a plan cannot author a room the scene could not hold."""
    from world.spatial import EXTENT_MAX_PACES, EXTENT_MIN_PACES

    shaped = _plan({"yard": {"name": "Yard",
                             "extent": {"w": 900, "d": 1}}})["rooms"]["yard"]
    assert shaped["extent"] == {"w": EXTENT_MAX_PACES, "d": EXTENT_MIN_PACES}


@pytest.mark.parametrize("geometry", [
    {"extent": "enormous"},
    {"extent": {"w": 4}},
    {"extent": None},
    {"shape": "oval"},
    {"exposure": "draughty"},
])
def test_an_unreadable_measurement_leaves_todays_behaviour(geometry):
    """FAIL-OPEN, exactly as the rest of the record does. An "oval" room is
    not silently squared into a rectangle and a half-written extent is not
    guessed at: the field is absent and the scene's own default stands,
    which is the room as it would have been before any of this."""
    shaped = _plan({"cell": dict({"name": "Cell"}, **geometry)})["rooms"]["cell"]
    for field in ("extent", "shape", "exposure"):
        assert field not in shaped, (
            "an unreadable %s must be NO %s, never a guess" % (field, field))


def test_a_loft_above_the_watch_room_has_a_way_up():
    """PA7. The plan says `up`; the edge is vertical and it is passable."""
    from world.spatial import edge_passable, effective_adjacent

    shaped = _plan({
        "watch_room": {"name": "Watch room"},
        "loft": {"name": "Loft",
                 "adjacent": [{"to": "watch_room", "vertical": "up"}]},
    })["rooms"]
    edge = shaped["loft"]["adjacent"][0]
    assert edge["vertical"] == "up"
    assert edge_passable(edge, "loft"), (
        "a plan that named a way up must not plant a sealed edge")

    scene = {"rooms": {uid: dict(room) for uid, room in shaped.items()}}
    back = [e for e in effective_adjacent(scene, "watch_room")
            if e.get("to") == "loft"]
    assert back and back[0].get("vertical") == "down", (
        "the far side of a way up is a way down; the scene derives it")


def test_up_is_not_a_bearing():
    """The measured shape of PA7: the word arrived in the bearing field,
    because there was nowhere else to put it. It is moved, not dropped."""
    edge = _plan_edge({"to": "watch_room", "bearing": "up"})
    assert edge["vertical"] == "up"
    assert "bearing" not in edge

    edge = _plan_edge({"to": "cellar", "dir": "downstairs"})
    assert edge["vertical"] == "down"
    assert "dir" not in edge

    kept = _plan_edge({"to": "gate", "dir": "n"})
    assert kept["dir"] == "n" and "vertical" not in kept, (
        "a compass point is a compass point and stays one")


def test_the_preview_shows_what_the_plan_measured():
    """So a host reading the preview can see that a measurement survived --
    the manor run reported a stable yard back as fourteen by twelve after
    being asked for roughly ten by six."""
    from story.plot_packages import _preview_plan_rooms

    op = _plan({"yard": {"name": "Yard", "extent": {"w": 10, "d": 6}},
                "loft": {"name": "Loft",
                         "adjacent": [{"to": "yard", "vertical": "up"}]}})
    world = {"rooms": {}, "planned": {}, "described_rooms": set(),
             "containment": {}}
    preview = _preview_plan_rooms(1, None, op, world)
    change = preview["changes"][0]
    assert change["geometry"]["yard"]["extent"] == {"w": 10, "d": 6}
    assert change["vertical"] == ["loft -> yard (up)"]


def test_the_operation_shape_offers_the_fields():
    """A field a model is never told about is a field that does not exist:
    F47 recurred verbatim in five runs against an operation that already
    took `adjacent` and `frontier`."""
    from story.plot_packages import OPERATION_FIELDS

    rooms = OPERATION_FIELDS["plan_rooms"]["rooms"]
    for field in ("extent", "shape", "exposure", "vertical"):
        assert field in rooms
