"""One grid for every sense (`spatial_fov.room_field`, 2026-09-04).

`observer_field` placed a neighbour beyond a doorway a body can walk into;
the sound field built `_acoustic_grid`, a second copy of that placement for
the wider predicate (a shut door's room is placed for sound), and the copy
had already drifted -- it still laid rooms out as tier squares after the
room-shapes work taught the original about L and round rooms. Now there is
ONE derivation and a placement PREDICATE: `sight_passes` (what a body walks
into: open, open_door), `light_passes` (what light crosses: every sight
barrier, glass and grilles included), `sound_passes` (whatever is not a
wall, at the aperture's pass).

Two contracts under test. BYTE-IDENTITY for sight: `observer_field` on every
scene shape the engine's tests draw -- squares, extents, an L, a round room,
diagonal doorways, far-declared edges, no geometry -- digests to exactly what
the pre-change module produced (the digests below were computed by running
`git show c3f274ea:world/spatial_fov.py` over the same scenes; the one added
wall key, `pass`, is left out of the digest and pinned separately). And the
WIDER predicates: sound places a shut door's room and a window's at their
passes, light places a window's and not a shut door's, and every composite
is the shape's cells, never the square's.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from world.spatial import (
    APERTURE_PASS, acoustic_grid, light_field, light_passes, observer_field,
    room_field, room_grid, sight_passes, sound_field, sound_passes,
    wall_aperture_cells, _placed_neighbours,
)


# ---------------------------------------------------------------------------
# The scenes: every placement shape the engine's tests draw
# ---------------------------------------------------------------------------

def _room(name, *, size=None, extent=None, shape=None, parts=None,
          anchors=None, adjacent=(), light="lit"):
    room = {"name": name, "desc": "", "light": light,
            "adjacent": list(adjacent), "anchors": dict(anchors or {})}
    if size:
        room["size"] = size
    if extent:
        room["extent"] = extent
    if shape:
        room["shape"] = shape
    if parts:
        room["parts"] = parts
    return room


def _scene(rooms, positions, stations=None):
    return {"rooms": rooms, "positions": dict(positions),
            "stations": dict(stations or {}), "orientation": {}, "poses": {},
            "entities": {}, "contained": {}}


def _pair(barrier, *, bearing="e", a_size="medium", b_size="medium",
          material=None, both=True):
    from world.spatial import opposite_bearing
    e1 = {"to": "b", "barrier": barrier, "dir": bearing}
    e2 = {"to": "a", "barrier": barrier, "dir": opposite_bearing(bearing)}
    if material:
        e1["material"] = e2["material"] = material
    return _scene({
        "a": _room("A", size=a_size, anchors={
            "c": {"desc": "a counter", "dir": "n", "footprint": "run",
                  "height": "waist"}}, adjacent=[e1]),
        "b": _room("B", size=b_size, anchors={
            "w": {"desc": "the far window", "dir": "e"},
            "shelf": {"desc": "a shelf", "dir": "s", "height": "waist"}},
            adjacent=[e2] if both else []),
    }, {"P": "a", "Q": "b"}, {"P": {"at": "c"}, "Q": {"at": "w"}})


def _hall():
    return _scene({"hall": _room("the Hall", size="large", anchors={
        "counter": {"desc": "the counter", "dir": "n", "footprint": "run",
                    "height": "waist"},
        "west": {"desc": "the west wall lamp", "dir": "w"},
        "east": {"desc": "the east window", "dir": "e"},
        "south": {"desc": "the south hearth", "dir": "s"}})},
        {"S": "hall", "L": "hall"}, {"S": {"at": "west"}, "L": {"at": "east"}})


def _wide_with_north_room():
    return _scene({
        "r": _room("R", extent={"w": 12, "d": 4}, anchors={
            "desk": {"desc": "a desk", "dir": "w", "height": "waist"}},
            adjacent=[{"to": "n_room", "barrier": "open_door", "dir": "n"}]),
        "n_room": _room("N", extent={"w": 4, "d": 4}),
    }, {"P": "r"}, {"P": {"at": "desk"}})


def _two_small_off_a_long_wall():
    return _scene({
        "r": _room("R", extent={"w": 24, "d": 4}, adjacent=[
            {"to": "a", "barrier": "open_door", "dir": "n"},
            {"to": "b", "barrier": "open_door", "dir": "n"}]),
        "a": _room("A", extent={"w": 2, "d": 2}),
        "b": _room("B", extent={"w": 2, "d": 2}),
    }, {"P": "r"})


def _round_with_neighbour(barrier="open_door"):
    return _scene({
        "r": _room("R", extent={"w": 6, "d": 6}, shape="round", anchors={
            "altar": {"desc": "an altar", "dir": "n", "height": "waist"}},
            adjacent=[{"to": "hall", "barrier": barrier, "dir": "e"}]),
        "hall": _room("H", size="small",
                      adjacent=[{"to": "r", "barrier": barrier, "dir": "w"}]),
    }, {"P": "r", "Q": "hall"}, {"P": {"at": "altar"}})


def _l_with_neighbour():
    return _scene({
        "r": _room("R", extent={"w": 8, "d": 8}, shape="l",
                   parts=[{"w": 8, "d": 3, "at": "nw"}, {"w": 3, "d": 8, "at": "ne"}],
                   anchors={"desk": {"desc": "a desk", "dir": "w", "height": "waist"},
                            "lamp": {"desc": "a lamp"}},
                   adjacent=[{"to": "s", "barrier": "open", "dir": "s"}]),
        "s": _room("S", size="small",
                   adjacent=[{"to": "r", "barrier": "open", "dir": "n"}]),
    }, {"P": "r", "Q": "s"}, {"P": {"at": "desk"}, "Q": {"near": ["P"]}})


def _no_geometry():
    return _scene({
        "a": {"name": "A", "desc": "Room A.", "light": "lit",
              "adjacent": [{"to": "b", "barrier": "open", "distance": "near"}]},
        "b": {"name": "B", "desc": "Room B.", "light": "dark", "adjacent": []},
    }, {"P": "a", "Q": "b"})


SCENES = {
    "open_door_pair": _pair("open_door"),
    "open_pair_north": _pair("open", bearing="n"),
    "closed_door_pair": _pair("closed_door"),
    "window_pair": _pair("window"),
    "bars_pair": _pair("bars"),
    "membrane_pair": _pair("membrane"),
    "wall_pair": _pair("wall"),
    "steel_door_pair": _pair("closed_door", material="steel"),
    "far_declared_only": _pair("open_door", both=False),
    "small_into_large": _pair("open_door", a_size="small", b_size="large"),
    "diagonal_pair": _pair("open_door", bearing="ne"),
    "hall": _hall(),
    "wide_with_north_room": _wide_with_north_room(),
    "two_small_off_a_long_wall": _two_small_off_a_long_wall(),
    "round_with_neighbour": _round_with_neighbour(),
    "round_behind_a_shut_door": _round_with_neighbour("closed_door"),
    "l_with_neighbour": _l_with_neighbour(),
    "no_geometry": _no_geometry(),
}

OBSERVERS = {name: "P" if "P" in sc["positions"] else "L"
             for name, sc in SCENES.items()}


def digest(field):
    """A canonical JSON digest of a `_Field`, over the contract as it stood
    before 2026-09-04: `inside`, `height`, `occluder`, `offsets`, `anchors`
    (id, cells, dir, height, opacity, footprint, implicit) and the walls'
    five keys. `pass` is deliberately left out; it is pinned on its own."""
    if field is None:
        return "none"
    body = {
        "inside": sorted((list(c), r) for c, r in field.inside.items()),
        "height": sorted((list(c), h) for c, h in field.height.items()),
        "occluder": sorted((list(c), a) for c, a in field.occluder.items()),
        "offsets": sorted((r, list(o)) for r, o in field.offsets.items()),
        "anchors": sorted(
            (room, aid, [list(c) for c in rec["cells"]], rec.get("dir"),
             rec.get("height"), rec.get("opacity"), rec.get("footprint"),
             bool(rec.get("implicit")))
            for room, placed in field.anchors.items()
            for aid, rec in placed.items()),
        "walls": sorted(
            json.dumps({k: w[k] for k in ("axis", "coord", "extent",
                                          "aperture", "to")}, sort_keys=True)
            for w in field.walls),
    }
    return hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()


#: `observer_field` digests computed by the PRE-CHANGE module
#: (`git show c3f274ea:world/spatial_fov.py`) over SCENES. A change here is
#: a change to what every sight caller sees, and must be argued for.
EXPECTED = {
    "bars_pair": "3796973826aa3c0a4a6211793cffc0f8c6278aa9",
    "closed_door_pair": "3796973826aa3c0a4a6211793cffc0f8c6278aa9",
    "diagonal_pair": "2e2eb8e469813172e41303c82c1138c4121be5f7",
    "far_declared_only": "c342947b51366ee97117f60f45c6db45d0b2a8bd",
    "hall": "0ae1c558ac6de0c157d99516f46204af5837ce1f",
    "l_with_neighbour": "aeace15bc3be46010d6b1f354568ebfb79f12c3c",
    "membrane_pair": "3796973826aa3c0a4a6211793cffc0f8c6278aa9",
    "no_geometry": "630197359f0cc6916dbe0f35a819c9c49251f6d2",
    "open_door_pair": "c342947b51366ee97117f60f45c6db45d0b2a8bd",
    "open_pair_north": "a758de50ca04096764c204e439902327ef4ed584",
    "round_behind_a_shut_door": "1bb832e9dc6c9940f0819fc17767a1fd8cfbfd85",
    "round_with_neighbour": "9666deb948172a79d2028d21af8b5c32d28cabee",
    "small_into_large": "c97ca61399d4dfbbd3b5da8c975fb9d3956fb088",
    "steel_door_pair": "3796973826aa3c0a4a6211793cffc0f8c6278aa9",
    "two_small_off_a_long_wall": "9af688f28380803d833cc5e381bcbec4888f1537",
    "wall_pair": "3796973826aa3c0a4a6211793cffc0f8c6278aa9",
    "wide_with_north_room": "9cb35b70c0ed5742c1bd10e013ce78de5bbb5716",
    "window_pair": "3796973826aa3c0a4a6211793cffc0f8c6278aa9",
}


# ---------------------------------------------------------------------------
# Sight: byte-identical
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(SCENES))
def test_sights_composite_is_what_it_was_on_every_scene(name):
    sc = SCENES[name]
    field = observer_field(sc, OBSERVERS[name])
    assert digest(field) == EXPECTED[name], name
    # The default predicate IS the sight rule, spelled either way.
    room = sc["positions"][OBSERVERS[name]]
    assert digest(room_field(sc, room)) == digest(
        room_field(sc, room, through=sight_passes))
    if field is not None:
        # The one added key, on every wall, under the sight rule.
        assert all(w["pass"] == 1.0 for w in field.walls)
        assert all(set(w) == {"axis", "coord", "extent", "aperture", "to",
                              "pass"} for w in field.walls)


def test_the_field_contract_is_unchanged():
    field = observer_field(SCENES["open_door_pair"], "P")
    for attr in ("inside", "height", "occluder", "offsets", "anchors", "walls"):
        assert hasattr(field, attr)
    assert field.cell_of("b", (0, 0)) == tuple(
        field.offsets["b"][i] + (0, 0)[i] for i in range(2))


def test_the_sight_predicate_walks_into_a_doorway_and_not_through_glass():
    for barrier, expected in (("open", 1.0), ("open_door", 1.0),
                              ("window", None), ("bars", None),
                              ("one_way_window", None), ("closed_door", None),
                              ("membrane", None), ("wall", None)):
        assert sight_passes({}, "a", {"barrier": barrier}) == expected, barrier


# ---------------------------------------------------------------------------
# Sound and light: the wider predicates on the same derivation
# ---------------------------------------------------------------------------

def test_sound_places_a_shut_door_and_a_window_at_their_passes():
    """The one thing `_acoustic_grid` was built for, now `room_field` under
    `sound_passes`: a shut door's room is placed (sight never places it), a
    window's too, each wall carrying the aperture's pass; a wall places
    nothing. On an open door the two composites are the same cells."""
    open_ = SCENES["open_door_pair"]
    sight = observer_field(open_, "Q")
    sound = sound_field(open_, "Q").grid
    assert digest(sight) == digest(sound)
    assert [w["pass"] for w in sound.walls] == [APERTURE_PASS["open_door"]]
    for name, barrier in (("closed_door_pair", "closed_door"),
                          ("window_pair", "window"), ("bars_pair", "bars"),
                          ("membrane_pair", "membrane")):
        sc = SCENES[name]
        assert sorted(observer_field(sc, "Q").offsets) == ["b"], name
        grid = sound_field(sc, "Q").grid
        assert sorted(grid.offsets) == ["a", "b"], name
        assert [w["pass"] for w in grid.walls] == [APERTURE_PASS[barrier]], name
    assert sorted(sound_field(SCENES["wall_pair"], "Q").grid.offsets) == ["b"]
    # The material shift the edge rules make, made here too.
    steel = sound_field(SCENES["steel_door_pair"], "Q").grid
    assert [w["pass"] for w in steel.walls] == [APERTURE_PASS["window"]]
    assert acoustic_grid(SCENES["closed_door_pair"], "b").offsets == \
        sound_field(SCENES["closed_door_pair"], "Q").grid.offsets


def test_sounds_composite_is_the_shape_not_the_square():
    """The drift the second copy had: a round room's composite for sound is
    the round room's cells, exactly as sight's is."""
    sc = SCENES["round_with_neighbour"]
    grid = room_grid(sc, "r")
    sight = observer_field(sc, "P")
    sound = room_field(sc, "r", through=sound_passes)
    assert {c for c, r in sound.inside.items() if r == "r"} == set(grid.cells)
    assert {c for c, r in sight.inside.items() if r == "r"} == set(grid.cells)
    assert len(grid.cells) < 36                 # a round room is not its box
    shut = SCENES["round_behind_a_shut_door"]
    assert sorted(observer_field(shut, "P").offsets) == ["r"]
    assert sorted(room_field(shut, "r", through=sound_passes).offsets) == ["hall", "r"]


def test_light_places_glass_and_not_a_shut_door():
    for barrier, placed in (("open_door", True), ("window", True),
                            ("bars", True), ("one_way_window", True),
                            ("closed_door", False), ("membrane", False),
                            ("wall", False)):
        assert (light_passes({}, "a", {"barrier": barrier}) == 1.0) is placed
    window = SCENES["window_pair"]
    window["rooms"]["b"]["light"] = "dark"
    lf = light_field(window, "b")
    assert sorted(lf.field.offsets) == ["a", "b"]
    assert sorted(observer_field(window, "Q").offsets) == ["b"]
    assert sorted(light_field(SCENES["closed_door_pair"], "b").field.offsets) == ["b"]
    # The own room's cells agree across all three composites.
    own = lambda f: {c for c, r in f.inside.items() if r == "b"}
    assert own(lf.field) == own(observer_field(window, "Q")) == own(
        sound_field(window, "Q").grid)


def test_placed_neighbours_reads_the_predicate_and_nothing_else():
    sc = SCENES["closed_door_pair"]
    assert _placed_neighbours(sc, "b", sight_passes) == []
    assert _placed_neighbours(sc, "b", sound_passes) == [
        ("a", "w", APERTURE_PASS["closed_door"])]
    assert _placed_neighbours(sc, "b", light_passes) == []
    assert _placed_neighbours(SCENES["window_pair"], "b", light_passes) == [
        ("a", "w", 1.0)]
    # A predicate answering 0 or None leaves the room alone.
    assert _placed_neighbours(sc, "b", lambda s, r, e: 0) == []


def test_aperture_cells_are_the_gap_on_the_wall_line():
    field = observer_field(SCENES["open_door_pair"], "P")
    (wall,) = field.walls
    cells = wall_aperture_cells(wall)
    assert len(cells) == 1
    (cell,) = cells
    assert cell[wall["axis"]] == wall["coord"]
    assert wall["aperture"][0] <= cell[1 - wall["axis"]] <= wall["aperture"][1]
    assert cell not in field.inside


def test_a_doorway_nobody_gave_a_bearing_to_is_not_hidden_by_the_cone():
    """A GUESS MAY NOT SUBTRACT.

    Sight is denied derived bearings on purpose (`derive=False`, so no view
    asserts a wall nobody declared), which leaves a doorway whose edge
    carries no `dir` placed by the hash that seeds any anchor along a wall.
    That is fine as somewhere to lay a thing out and worthless as evidence
    about where a body is looking -- and the cone was reading it as
    evidence.

    Measured, chat 117 turn 56: Aurel walked north up a 4x24 corridor at
    cell (2,1) facing north, with the doorway to the room he was walking
    TOWARD placed at (1,16) -- fifteen cells behind him -- because that edge
    carries an `axis` label and no `dir`. Three of the room's five features
    were culled and the way on was one of them, so the view reported the
    deck running into unbroken black while a door stood at the end of it.

    A doorway someone DID place stays ordinary geometry and is hidden
    behind a body like anything else; that is the other half of this test.
    """
    from world.spatial import feature_visibility

    rooms = {
        "run": {
            "name": "the long run", "size": "large", "exposure": "enclosed",
            "extent": {"w": 4, "d": 24}, "light": "lit",
            "adjacent": [
                # The way ON: no bearing anywhere, either side.
                {"to": "far", "barrier": "open_door"},
                # The way BACK: declared, and behind him.
                {"to": "back", "barrier": "open_door", "dir": "s"},
            ],
            "anchors": {"deck": {"desc": "the deck", "dir": "n",
                                 "height": "floor"}},
        },
        "far": {"name": "the far room", "adjacent": [{"to": "run"}]},
        "back": {"name": "the room behind",
                 "adjacent": [{"to": "run", "barrier": "open_door",
                               "dir": "n"}]},
    }
    scene = {"rooms": rooms, "positions": {"P": "run"}, "entities": {},
             "stations": {"P": {"at": "deck"}}, "poses": {},
             "orientation": {"P": {"facing": "n"}}}

    rows = {r["anchor"]: r for r in feature_visibility(scene, "P")}
    unbeared = rows["door:far"]
    assert unbeared["visible"] is True
    # ...and it claims no side, because "on your left" off a hash is the
    # false assertion this is avoiding.
    assert unbeared["side"] is None and unbeared["sector"] is None
    assert unbeared["peripheral"] is False
    # The declared doorway behind the body is still correctly hidden.
    assert rows["door:back"]["visible"] is False
    assert rows["door:back"]["basis"] == "cone"
