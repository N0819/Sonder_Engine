"""The light field (`world/spatial_light_field.py`): light as a quantity on
the sight grid, read through the four words every caller already has.

Two contracts under test. FAIL-OPEN: a scene whose rooms carry neither a
size tier nor anchors -- every scene the existing light fixtures draw --
composes byte-identically with the field code present, pinned by running
the same composition with the field's readers switched off and comparing.
GEOMETRY: where a room has a grid and a body a cell, the answer comes from
the lamp's rays -- decayed, shaped, shadowed, bounced, floored, quantised
LAST -- and the synthetic cases of `docs/design/DESIGN_LIGHT_FIELD.md`
§ 9.3 each hold: rings round a source, a cone against its side, a candle
behind a counter, a ceiling light over it, a doorway wedge, bounce in the
corners. Plus glare, the flicker hash, the schema round trip through the
merge, and the commit-time notice for a source that fails.

Every import goes through the `world.spatial` facade; the sibling is named
only where a test PATCHES it, which the facade rule permits.
"""

from __future__ import annotations

import copy
import json
import time as _time

import pytest

from agents import composer
from world import spatial
from world.spatial import (
    BEAT_KEY, BOUNCE, BOUNCE_PASSES_CAP, BOUNCE_REACH, BRIGHT_T,
    CONE_GAIN, CONE_HALF_ANGLE, CONE_PENUMBRA, DARK_THRESHOLD, DIM_T, FAIL_RATE,
    FLICKER_RATE, FLOOR_SPILL, GLARE_CELLS, GLARE_POWER, LIGHT_LEVELS, LIGHT_SHAPES,
    LIT_T, POWER, SIGHT_LEVELS, STEADINESS, _LIGHT_SIGHT, _ENTITY_DEFAULT_FIELDS,
    _ENTITY_STRUCTURAL_FIELDS, body_cell, compute_light_field, effective_light,
    emitted_level, failing_sources_out, fails_on, field_rows, flickers_on,
    glare_between, light_at, light_field, light_geometry_exists,
    merge_scene_with_diff, quantise, reach_radius, sight_level,
    spatial_rel_between, visual_level_between,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _room(name, *, size="medium", light="dark", exposure="enclosed",
          anchors=None, adjacent=None):
    room = {"name": name, "desc": "", "light": light, "exposure": exposure,
            "adjacent": list(adjacent or [])}
    if size:
        room["size"] = size
    if anchors is not None:
        room["anchors"] = anchors
    return room


def _scene(rooms, positions, *, entities=None, stations=None,
           orientation=None, contained=None, poses=None):
    return {"rooms": rooms, "positions": dict(positions),
            "entities": dict(entities or {}), "stations": dict(stations or {}),
            "orientation": dict(orientation or {}),
            "contained": dict(contained or {}), "poses": dict(poses or {})}


def lamp_room(level="lit", **fields):
    """A medium, dark, enclosed room with one source standing free at its
    centre (no station -> the room's centre, cell (3, 3))."""
    ent = {"name": "the lamp", "light_source": level, "portable": True}
    ent.update(fields)
    return _scene({"r": _room("the Hall", anchors={"table": {"desc": "a table"}})},
                  {"lamp": "r"}, entities={"lamp": ent})


CENTRE = (3, 3)


# ---------------------------------------------------------------------------
# § 9.3 -- one lit all_round source: the level at each ring
# ---------------------------------------------------------------------------

def test_a_lit_source_decays_by_inverse_square_and_quantises_last():
    lf = light_field(lamp_room("lit"), "r")
    assert [s["id"] for s in lf.sources] == ["lamp"]
    assert lf.sources[0]["cell"] == CENTRE
    # Direct light alone: P/(1+d^2) on the north ray.
    direct = lf.per_source["lamp"]
    assert direct[CENTRE] == pytest.approx(6.0)
    assert direct[(3, 2)] == pytest.approx(3.0)
    assert direct[(3, 1)] == pytest.approx(1.2)
    assert direct[(3, 0)] == pytest.approx(0.6)
    # Quantised LAST, after bounce and floor: lit at the lamp and one pace
    # out, dim beyond, dark only in the far corner.
    assert lf.level(CENTRE) == "lit"
    assert lf.level((3, 2)) == "lit"
    assert lf.level((3, 1)) == "dim"
    assert lf.level((3, 0)) == "dim"
    assert lf.level((0, 0)) == "dark"
    assert all(word in LIGHT_LEVELS for row in field_rows(lf, "r") for word in row)


def test_reach_ends_where_a_source_alone_falls_dark():
    assert reach_radius(POWER["dim"]) == 2
    assert reach_radius(POWER["lit"]) == 4
    assert reach_radius(POWER["bright"]) == 6
    assert reach_radius(0.0) == 0


def test_two_sources_sum_where_one_would_only_be_the_brighter():
    """Two candles ARE brighter than one -- the thing the max-of-levels model
    could never say."""
    one = lamp_room("dim")
    two = copy.deepcopy(one)
    two["entities"]["lamp2"] = dict(two["entities"]["lamp"], name="the other lamp")
    two["positions"]["lamp2"] = "r"
    a = light_field(one, "r")
    b = light_field(two, "r")
    assert b.intensity[CENTRE] > a.intensity[CENTRE]
    assert b.direct[CENTRE] == pytest.approx(2 * a.direct[CENTRE])


# ---------------------------------------------------------------------------
# § 9.3 -- a lit cone: inside the cone against beside it
# ---------------------------------------------------------------------------

def test_a_cone_lights_what_it_points_at_and_not_what_stands_beside_it():
    sc = lamp_room("lit", light_shape="cone", state={"pointed_at": "n"})
    lf = light_field(sc, "r")
    src = lf.sources[0]
    assert src["shape"] == "cone" and src["axis"] == 0.0
    direct = lf.per_source["lamp"]
    # Straight up the axis: the all_round decay, concentrated by CONE_GAIN
    # -- a beam puts the same light into fewer cells (2026-09-07; before
    # this a cone could only mask, and a hand lamp graded a body three paces
    # off as dim).
    assert direct[(3, 1)] == pytest.approx(1.2 * CONE_GAIN)
    # Ninety degrees off the axis, beyond the penumbra: nothing direct.
    assert direct.get((5, 3), 0.0) == 0.0
    assert direct.get((3, 5), 0.0) == 0.0
    # The penumbra is a linear ramp, not a step: 45 degrees off (the cell
    # diagonally ahead) is between full and nothing.
    diag = direct[(4, 2)]
    assert 0.0 < diag < (6.0 / 3.0) * CONE_GAIN
    assert diag == pytest.approx(
        (6.0 / 3.0) * CONE_GAIN * (1 - (45 - CONE_HALF_ANGLE) / CONE_PENUMBRA))
    assert lf.level((3, 1)) in ("dim", "lit")
    assert lf.intensity[(3, 1)] > lf.intensity[(5, 3)]


def test_a_cone_with_no_axis_is_all_round_for_the_beat():
    """No `pointed_at`, no holder, no facing: the wider answer."""
    lf = light_field(lamp_room("lit", light_shape="cone"), "r")
    assert lf.sources[0]["axis"] is None
    assert lf.per_source["lamp"][(5, 3)] == pytest.approx(6.0 / 5.0)


def test_a_carried_cone_points_where_its_holder_faces():
    sc = _scene({"r": _room("the Hall", anchors={"table": {"desc": "a table"}})},
                {"Q": "r", "torch": "r"},
                entities={"torch": {"name": "the torch", "light_source": "lit",
                                    "portable": True, "light_shape": "cone"}},
                stations={"Q": {"at": "table"}},
                orientation={"Q": {"facing": "e"}},
                contained={"torch": {"in": "Q", "mode": "held"}})
    lf = light_field(sc, "r")
    src = lf.sources[0]
    assert src["holder"] == "Q"
    assert src["cell"] == body_cell(sc, "Q")
    assert src["axis"] == 90.0
    # Carried: the source sits at the holder's eye height.
    assert src["height"] == 2.0


def test_an_aim_the_engine_cannot_read_is_all_round_not_the_chest():
    """`pointed_at` written as a phrase -- "north along riser 10" -- resolves
    to nothing. The fallback used to take the holder's FACING, so a lamp the
    player had aimed at a creature for four beats (chat 117, 59-62) lit a
    cone ninety degrees away from it, cone factor 0.0, and the body it was
    pointed at stayed "an indistinct figure". An aim that was written but
    cannot be read is not "wherever the chest points"; it leaves the cone
    all-round -- the docstring's own wider answer -- so the lamp lights what
    it can reach rather than nothing it was pointed at. Only a lamp with NO
    aim written follows its holder's body."""
    base = dict(
        rooms={"r": _room("the Hall", anchors={"table": {"desc": "a table"}})},
        positions={"Q": "r", "torch": "r"},
        stations={"Q": {"at": "table"}},
        orientation={"Q": {"facing": "e"}},
        contained={"torch": {"in": "Q", "mode": "held"}})
    torch = {"name": "the torch", "light_source": "lit",
             "portable": True, "light_shape": "cone"}

    unreadable = _scene(entities={"torch": {
        **torch, "state": {"pointed_at": "north along the riser"}}}, **base)
    assert light_field(unreadable, "r").sources[0]["axis"] is None

    unaimed = _scene(entities={"torch": {**torch, "state": {}}}, **base)
    assert light_field(unaimed, "r").sources[0]["axis"] == 90.0


def test_a_cone_concentrates_what_an_all_round_lamp_only_spreads():
    """A beam puts the lamp's light into fewer cells, so each is brighter.
    `cone_factor` is <= 1, so before `CONE_GAIN` a cone could only MASK: a
    `bright` source reached `lit` to 2.4 paces whatever its shape, and a
    halogen held on a body three paces off graded it dim -> conduct (chat
    117 beats 65/68/70, on-axis). On-axis, an aimed cone now carries `lit`
    further than the same lamp all round; off-axis it still lights nothing.
    """
    assert CONE_GAIN > 1.0
    scene = lamp_room("bright", light_shape="cone",
                      state={"pointed_at": "n"})
    lf = light_field(scene, "r")
    src = lf.sources[0]
    assert src["axis"] == 0.0
    # Three paces up the axis (the descent's distance; the medium grid is
    # six cells a side, so north is the direction with three paces in it).
    # Two paces behind the lamp: nothing.
    on_axis = lf.per_source["lamp"].get((CENTRE[0], CENTRE[1] - 3), 0.0)
    behind = lf.per_source["lamp"].get((CENTRE[0], CENTRE[1] + 2), 0.0)
    assert on_axis == pytest.approx(POWER["bright"] * CONE_GAIN / 10.0)
    assert on_axis >= LIT_T
    assert behind == 0.0
    # And the same lamp all round at the same three paces is not lit.
    spread = light_field(lamp_room("bright"), "r")
    assert spread.per_source["lamp"][(CENTRE[0], CENTRE[1] - 3)] < LIT_T


def test_pointed_at_an_anchor_resolves_through_its_cell():
    sc = lamp_room("lit", light_shape="cone", state={"pointed_at": "table"})
    lf = light_field(sc, "r")
    assert lf.sources[0]["axis"] is not None


# ---------------------------------------------------------------------------
# § 9.3 -- a candle behind a waist-high counter, then a ceiling light
# ---------------------------------------------------------------------------

def counter_room(source_height):
    """A waist-high counter runs along the north wall one pace off it. The
    candle stands at the counter on the room side; H stands at it on the
    wall side (`cover`)."""
    return _scene(
        {"r": _room("the Shop", anchors={
            "counter": {"desc": "the counter", "dir": "n", "footprint": "run",
                        "height": "waist"}})},
        {"candle": "r", "H": "r", "P": "r"},
        entities={"candle": {"name": "the candle", "light_source": "lit",
                             "light_height": source_height}},
        stations={"candle": {"at": "counter"}, "H": {"at": "counter", "cover": True},
                  "P": {"at": "counter"}})


def test_a_candle_on_the_floor_is_shadowed_by_the_counter():
    sc = counter_room("floor")
    lf = light_field(sc, "r")
    h_cell = body_cell(sc, "H")
    assert h_cell[1] == 0                      # on the wall side of the counter
    direct = lf.per_source["candle"]
    assert direct.get(h_cell, 0.0) == 0.0      # the counter cuts the ray
    # The cell straight across the counter from H, on the room side, is lit
    # by the same candle at the same distance from it or less.
    front = (h_cell[0], 2)
    assert direct.get(front, 0.0) > 0.0
    assert lf.intensity[front] > lf.intensity[h_cell]
    assert lf.level(h_cell) in ("dark", "dim")
    # And the body reads its own cell.
    assert light_at(sc, "H") == lf.level(h_cell)


def test_a_ceiling_light_casts_no_shadow_over_the_counter():
    sc = counter_room("full")
    lf = light_field(sc, "r")
    h_cell = body_cell(sc, "H")
    assert lf.per_source["candle"].get(h_cell, 0.0) > 0.0
    floor_sc = counter_room("floor")
    assert lf.intensity[h_cell] > light_field(floor_sc, "r").intensity[h_cell]


def test_a_fixture_defaults_to_full_and_a_free_portable_thing_to_head():
    fixture = lamp_room("lit")
    del fixture["entities"]["lamp"]["portable"]
    assert light_field(fixture, "r").sources[0]["height"] == 3.0
    assert light_field(lamp_room("lit"), "r").sources[0]["height"] == 2.0


# ---------------------------------------------------------------------------
# § 9.3 -- a lit kitchen and a dark cellar joined by a one-pace door
# ---------------------------------------------------------------------------

def kitchen_and_cellar(*, source=True):
    rooms = {
        "k": _room("the Kitchen", light="lit",
                   adjacent=[{"to": "c", "barrier": "open", "dir": "s"}]),
        "c": _room("the Cellar", light="dark",
                   adjacent=[{"to": "k", "barrier": "open", "dir": "n"}]),
    }
    entities = {}
    positions = {"P": "c"}
    if source:
        entities["stove"] = {"name": "the stove", "light_source": "bright"}
        positions["stove"] = "k"
    return _scene(rooms, positions, entities=entities)


def test_spill_is_a_wedge_through_the_doorway_and_dark_beside_the_frame():
    """The STOVE's rays: computed with the floor's spill off, so the wedge is
    the stove's alone. What the kitchen's lit floor adds through the same
    doorway is the next test's."""
    sc = kitchen_and_cellar()
    lf = compute_light_field(sc, "c", spill=False)
    assert "k" in lf.field.offsets
    stove = lf.sources[0]
    direct = lf.per_source["stove"]
    cellar_cells = lf.room_cells("c")
    lit_cellar = [c for c in cellar_cells if direct.get(c, 0.0) > 0.0]
    assert lit_cellar, "the stove's rays reach through the door"
    # The wedge opens from the door: the door cell on the cellar side is
    # lit, and the cells beside the doorframe against the wall are not.
    [wall] = lf.field.walls
    door_x = int(round((wall["aperture"][0] + wall["aperture"][1]) / 2))
    first_row = min(c[1] for c in cellar_cells)
    assert direct.get((door_x, first_row), 0.0) > 0.0
    beside = [(door_x - 1, first_row), (door_x + 1, first_row)]
    beside = [c for c in beside if c in lf.field.inside]
    # THE WEDGE IS EXACTLY THE SET OF CELLS WHOSE STRAIGHT RAY THREADS THE
    # GAP (`_wall_verdict`). A cell against the wall beside the frame is
    # lit only when the stove stands far enough off-axis on the OTHER side
    # for its ray to cross the wall line inside the one-pace aperture; the
    # cell on the stove's own side never is. (The door's seeded offset
    # differs between the two rooms, so which side that is varies.)
    assert beside
    for cell in beside:
        threads = spatial._wall_verdict(lf.field, stove["cell"], cell)
        assert (direct.get(cell, 0.0) > 0.0) == threads, (cell, threads)
    dark_beside = [c for c in beside if direct.get(c, 0.0) == 0.0]
    assert dark_beside, "the near side of the frame is always in the wall's shadow"
    # Nothing arrives round the corner by bounce either.
    assert all(lf.level(c) == "dark" for c in dark_beside)
    # The far corner of the cellar is dark whatever comes through the door.
    far = max(cellar_cells, key=lambda c: (c[1], -abs(c[0] - door_x)))
    assert lf.level(far) == "dark"
    assert lf.floor["k"] == POWER["lit"] and lf.floor["c"] == POWER["dark"]
    assert stove["room"] == "k"


def _door_geometry(lf, room):
    """(the aperture cell, the taking room's cell inside the door, the far
    corner) for a field with one wall."""
    [wall] = lf.field.walls
    ap = spatial.wall_aperture_cells(wall)[0]
    cells = lf.room_cells(room)
    first = min(c[1] for c in cells)
    door = (ap[0], first)
    far = max(cells, key=lambda c: (c[1], abs(c[0] - ap[0])))
    return ap, door, far


def test_the_kitchen_floor_spills_through_the_doorway_and_no_further_than_dim():
    """THE OWNER'S RULING (2026-09-04, the note's open question 1): the
    ambient floor spills. Without a source, the lit kitchen's floor is
    emitted from the doorway's aperture cell at FLOOR_SPILL of its power and
    lands on the cellar: `dim` at the door cell and the two beside the
    frame, `dark` at two paces and in the far corner, the room's median
    still dark. A `bright` floor reaches dim three paces in and still never
    `lit` at the door -- the room-level rule it replaces never lifted
    borrowed light past dim, and 0.25 is the largest FLOOR_SPILL that keeps
    that true (0.33 puts the door cell at 3.23, lit). The table beside the
    constant is this test."""
    sc = kitchen_and_cellar(source=False)
    lf = light_field(sc, "c")
    ap, door, far = _door_geometry(lf, "c")
    assert FLOOR_SPILL == 0.25
    assert lf.spill and set(lf.spill_from) == {"k"}
    assert lf.spill[door] == pytest.approx(FLOOR_SPILL * POWER["lit"] / 2.0)
    assert lf.level(door) == "dim"
    for beside in ((door[0] - 1, door[1]), (door[0] + 1, door[1])):
        if beside in lf.field.inside:
            assert lf.level(beside) == "dim"
    assert lf.level((door[0], door[1] + 1)) == "dark"
    assert lf.level(far) == "dark"
    assert effective_light(sc, "c") == "dark"          # the median: a small lit doorway
    assert effective_light(sc, "k") == "lit"
    # Nothing arrives in the kitchen from its own floor (the giver's cells
    # already have their floor), so its cells beside the door are its floor.
    assert all(lf.field.inside.get(c) == "c" for c in lf.spill)
    # A bright neighbour: dim to three paces, never lit at the door.
    sc["rooms"]["k"]["light"] = "bright"
    lf = light_field(sc, "c")
    ap, door, far = _door_geometry(lf, "c")
    assert [lf.level((door[0], door[1] + k)) for k in range(3)] == ["dim"] * 3
    assert lf.level(far) == "dark"


def test_floor_spill_at_zero_reproduces_the_field_as_first_built(monkeypatch):
    sc = kitchen_and_cellar(source=False)
    import world.spatial_light_field as sibling   # patched, not called
    monkeypatch.setattr(sibling, "FLOOR_SPILL", 0.0)
    lf = compute_light_field(sc, "c")
    assert lf.spill == {} and lf.spill_from == {}
    assert all(word == "dark" for row in field_rows(lf, "c") for word in row)
    assert compute_light_field(sc, "c", spill=False).intensity == lf.intensity


def test_light_crosses_glass_and_not_a_shut_door():
    """`light_passes`: a window places the neighbour on the LIGHT composite
    (sight's `observer_field` leaves it unplaced, because a grid cannot be
    walked into through glass), so the lit room's floor spills through it
    and a lamp behind it lights this room; a closed door places nothing,
    and the field is the room alone."""
    for barrier, placed in (("window", True), ("bars", True), ("open_door", True),
                            ("closed_door", False), ("membrane", False),
                            ("wall", False)):
        sc = kitchen_and_cellar(source=False)
        for room, edge in (("k", 0), ("c", 0)):
            sc["rooms"][room]["adjacent"][edge]["barrier"] = barrier
        lf = light_field(sc, "c")
        assert ("k" in lf.field.offsets) is placed, barrier
        assert bool(lf.spill) is placed, barrier
        assert ("k" in spatial.observer_field(sc, "P").offsets) is (
            barrier == "open_door"), barrier
    assert spatial.light_passes({}, "c", {"barrier": "window"}) == 1.0
    assert spatial.light_passes({}, "c", {"barrier": "closed_door"}) is None


def test_the_room_reads_its_median_cell():
    """One candle in a dark room does not make the room `lit`."""
    sc = lamp_room("lit")
    lf = light_field(sc, "r")
    assert effective_light(sc, "r") == quantise(lf.room_median("r"))
    assert effective_light(sc, "r") == "dim"
    assert lf.level(CENTRE) == "lit"


# ---------------------------------------------------------------------------
# § 9.3 -- bounce on against off: the corners
# ---------------------------------------------------------------------------

def test_bounce_fills_the_corners_and_never_exceeds_a_quarter_of_the_fall():
    sc = lamp_room("bright")
    del sc["entities"]["lamp"]["portable"]   # a fixture, `full`
    on = compute_light_field(sc, "r")
    off = compute_light_field(sc, "r", bounce=False)
    corner = (0, 0)
    assert on.intensity[corner] > off.intensity[corner]
    assert on.bounced and sum(on.bounced.values()) <= BOUNCE["enclosed"] * sum(
        off.direct.values()) * (1 + BOUNCE["enclosed"] + BOUNCE["enclosed"] ** 2
                                + BOUNCE["enclosed"] ** 3) + 1e-9
    # A bright fixture fills a medium enclosed room: no cell darker than dim.
    assert all(word != "dark" for row in field_rows(on, "r") for word in row)


def test_an_open_room_bounces_least():
    enclosed = lamp_room("lit")
    open_air = copy.deepcopy(enclosed)
    open_air["rooms"]["r"]["exposure"] = "open"
    a = compute_light_field(enclosed, "r")
    b = compute_light_field(open_air, "r")
    assert sum(a.bounced.values()) > sum(b.bounced.values())
    assert BOUNCE["enclosed"] > BOUNCE["sheltered"] > BOUNCE["open"]


def test_the_ambient_floor_is_a_floor_not_a_source():
    sc = lamp_room("lit")
    sc["rooms"]["r"]["light"] = "lit"
    lf = light_field(sc, "r")
    assert lf.floor["r"] == POWER["lit"]
    assert min(lf.intensity.values()) >= POWER["lit"]
    # The floor added nothing to bounce: the bounced field is what the lamp
    # alone produced.
    dark = light_field(lamp_room("lit"), "r")
    assert lf.bounced == dark.bounced


# ---------------------------------------------------------------------------
# Readers: the words are unchanged
# ---------------------------------------------------------------------------

def test_the_ladders_and_the_light_to_sight_table_are_untouched():
    assert LIGHT_LEVELS == ("dark", "dim", "lit", "bright")
    # The sight ladder gained `conduct` on 2026-09-05 (PQ2,
    # `docs/experiments/PLAY_2026_09_05C_quiet.md`): dim withholds detail,
    # not conduct, so the word an author means by "indoors, late afternoon"
    # stopped grading to the silhouette a barrier leaves. `shapes` is
    # untouched and is still what the caps, the crossings and the glare
    # answer; `dark` and the two lit words are exactly what they were.
    assert SIGHT_LEVELS == ("none", "shapes", "conduct", "full")
    assert _LIGHT_SIGHT == {"dark": "none", "dim": "conduct", "lit": "full",
                            "bright": "full"}
    assert LIGHT_SHAPES == ("all_round", "cone")
    assert STEADINESS == ("steady", "flickering", "failing")
    # A word's own power quantises back to the word, or the ambient floor of
    # a room would rename it: the note's LIT_T of 2.0 sat on POWER["dim"] and
    # made every dim room with a grid read lit.
    for word in ("dark", "dim", "lit", "bright"):
        assert quantise(POWER[word]) == word
    assert POWER["dark"] < DIM_T <= POWER["dim"] < LIT_T <= POWER["lit"] \
        < BRIGHT_T <= POWER["bright"]
    assert (DIM_T, LIT_T, BRIGHT_T) == (0.5, 2.5, 8.0) and DARK_THRESHOLD == DIM_T
    assert (BOUNCE_REACH, BOUNCE_PASSES_CAP, GLARE_CELLS) == (3, 4, 2)
    assert GLARE_POWER == POWER["lit"] and (FLICKER_RATE, FAIL_RATE) == (4, 12)


def test_light_at_speaks_the_ladder_and_reads_the_body_cell():
    sc = lamp_room("lit")
    sc["positions"]["P"] = "r"
    sc["stations"]["P"] = {"at": "table"}
    level = light_at(sc, "P")
    assert level in LIGHT_LEVELS
    lf = light_field(sc, "r")
    assert level == lf.level(body_cell(sc, "P"))


def test_a_body_without_a_station_reads_the_rooms_median(monkeypatch):
    """A body with no station is somewhere in the room, and 'somewhere' is
    the room's typical light -- the median cell `effective_light` already
    answers with. Until 2026-09-04 it kept the ROOM-LEVEL answer instead,
    so one room had two: chat 115's dim corridor with one lit fixture read
    `dim` as a room and `lit` for every unstationed body in it (the fixture
    'filling' the room under `light_radius`). Here: one lit lamp at the
    centre of a dark medium room; the room reads dim, and so does a body
    standing nowhere in particular in it, where the room-level model said
    lit."""
    sc = lamp_room("lit")
    sc["positions"]["P"] = "r"
    assert light_geometry_exists(sc, "r") and body_cell(sc, "P") is None
    assert light_at(sc, "P") == effective_light(sc, "r") == "dim"
    import world.spatial_light_field as sibling   # patched, not called
    monkeypatch.setattr(sibling, "field_light_at", lambda scene, name: None)
    assert light_at(sc, "P") == "lit"             # the room-level model, for the record


# ---------------------------------------------------------------------------
# The fail-open pin: no geometry, byte-identical composition
# ---------------------------------------------------------------------------

def _rooms(light_a="lit", light_b="lit", barrier="open"):
    """`tests/test_light_and_survival._rooms`, redrawn: two rooms with no
    size tier and no anchors."""
    return {
        "rooms": {
            "a": {"name": "A", "desc": "Room A.", "light": light_a,
                  "adjacent": [{"to": "b", "barrier": barrier,
                                "distance": "near"}]},
            "b": {"name": "B", "desc": "Room B.", "light": light_b,
                  "adjacent": []},
        },
        "positions": {"Watcher": "a", "Watched": "b", "Third": "a"},
        "entities": {},
    }


def _torch_rooms():
    sc = _rooms("dark", "dark")
    sc["entities"]["torch"] = {"name": "the torch", "light_source": "lit",
                               "portable": True}
    sc["positions"]["torch"] = "a"
    sc["contained"] = {"torch": {"in": "Third", "mode": "held"}}
    return sc


def _compose(sc):
    """Everything light decides, for every body and pair, plus the composed
    presence and environment percepts, as one JSON string."""
    bodies = [n for n in sc["positions"] if n not in (sc.get("entities") or {})]
    out = {"light_at": {n: light_at(sc, n) for n in bodies},
           "effective_light": {r: effective_light(sc, r) for r in sc["rooms"]},
           "pairs": {}}
    for a in bodies:
        for b in bodies:
            if a == b:
                continue
            rel = spatial_rel_between(sc, a, b)
            out["pairs"][f"{a}->{b}"] = {
                "rel": rel, "sight": sight_level(rel),
                "visual": visual_level_between(sc, a, b)}
        display = {n: n for n in bodies}
        percepts = composer.presence_percepts(
            sc, a, [{"name": n} for n in bodies if n != a], display)
        out["presence:" + a] = [(p.data, p.dedupe_key) for p in percepts]
        room = spatial.room_of(sc, a)
        env = composer.environment_percept(
            room, sc["rooms"][room]["name"], "", effective_light(sc, room))
        out["env:" + a] = (env.data, env.dedupe_key) if env else None
    return json.dumps(out, sort_keys=True, default=str)


NO_GEOMETRY_SCENES = [
    _rooms(), _rooms("dark", "lit"), _rooms("lit", "dark"),
    _rooms("dim", "dim"), _rooms("dark", "bright", "closed_door"),
    _rooms("dark", "lit", "window"), _torch_rooms(),
]


@pytest.mark.parametrize("sc", NO_GEOMETRY_SCENES)
def test_a_scene_without_geometry_composes_byte_identically(monkeypatch, sc):
    """THE PIN. With the field's three readers switched off (the module's
    answers replaced by 'no field'), every light verdict, every sight
    verdict, every presence percept and every environment percept for these
    scenes is the same string as with them on -- because none of these
    rooms carries a size tier or anchors, so the field does not exist and
    nothing here can have changed."""
    for room in sc["rooms"]:
        assert not light_geometry_exists(sc, room)
    live = _compose(sc)
    import world.spatial_light_field as sibling   # patched, not called
    monkeypatch.setattr(sibling, "field_light_at", lambda scene, name: None)
    monkeypatch.setattr(sibling, "field_effective_light", lambda scene, rid: None)
    monkeypatch.setattr(sibling, "glare_between", lambda scene, a, b: False)
    off = _compose(sc)
    assert live == off


def test_a_room_with_geometry_and_no_source_reads_its_own_light():
    """Geometry present, nothing burning: the floor is the room's light and
    the median is the floor, so the room-level word survives unchanged."""
    for light in ("dark", "dim", "lit", "bright"):
        sc = _scene({"r": _room("the Hall", light=light,
                                anchors={"table": {"desc": "a table"}})},
                    {"P": "r"}, stations={"P": {"at": "table"}})
        assert effective_light(sc, "r") == light
        assert light_at(sc, "P") == light


# ---------------------------------------------------------------------------
# Glare
# ---------------------------------------------------------------------------

def glare_scene(*, lit=True, facing=None, level="lit"):
    """P at the table, facing Q, who stands beside P holding a lamp: the
    light is in P's eyes and Q is behind it."""
    sc = _scene({"r": _room("the Hall", light="lit",
                            anchors={"table": {"desc": "a table"}})},
                {"P": "r", "Q": "r", "lamp": "r"},
                entities={"lamp": {"name": "the lamp", "light_source": level,
                                   "portable": True, "state": {"lit": lit}}},
                stations={"P": {"at": "table"}, "Q": {"near": ["P"]}},
                contained={"lamp": {"in": "Q", "mode": "held"}})
    p, q = body_cell(sc, "P"), body_cell(sc, "Q")
    sc["orientation"]["P"] = {"facing": facing or spatial.bearing_between(p, q)}
    return sc


def test_a_lamp_held_in_your_face_caps_sight_at_shapes():
    sc = glare_scene()
    assert glare_between(sc, "P", "Q")
    rel = spatial_rel_between(sc, "P", "Q")
    assert rel.get("glare") is True and sight_level(rel) == "shapes"
    assert visual_level_between(sc, "P", "Q") == "shapes"
    # The holder, looking out past their own lamp, is not dazzled by it.
    assert not glare_between(sc, "Q", "P")


def test_glare_needs_the_light_on_the_power_and_the_facing():
    assert not glare_between(glare_scene(lit=False), "P", "Q")
    assert visual_level_between(glare_scene(lit=False), "P", "Q") == "full"
    assert not glare_between(glare_scene(level="dim"), "P", "Q")
    # Facing away: the source is not in the front cone.
    sc = glare_scene()
    p, q = body_cell(sc, "P"), body_cell(sc, "Q")
    sc["orientation"]["P"] = {"facing": spatial.opposite_bearing(
        spatial.bearing_between(p, q))}
    assert not glare_between(sc, "P", "Q")
    # No station for the observer: no cell, no evidence, no glare.
    sc = glare_scene()
    del sc["stations"]["P"]
    assert not glare_between(sc, "P", "Q")


# ---------------------------------------------------------------------------
# Steadiness
# ---------------------------------------------------------------------------

def test_the_flicker_hash_is_deterministic_and_about_the_stated_rate():
    beats = range(4000)
    flick = [flickers_on(b, "lamp") for b in beats]
    fail = [fails_on(b, "lamp") for b in beats]
    assert flick == [flickers_on(b, "lamp") for b in beats]
    assert 0.20 < sum(flick) / len(flick) < 0.30      # 1 in 4
    assert 0.06 < sum(fail) / len(fail) < 0.11        # 1 in 12
    # Keyed on the source too: two sources in one room do not blink together.
    assert [flickers_on(b, "lamp") for b in beats] != [flickers_on(b, "torch") for b in beats]


def test_a_flickering_source_drops_one_level_on_its_beats_and_a_failing_one_goes_out():
    lamp = {"name": "the lamp", "light_source": "lit", "steadiness": "flickering"}
    beat_on = next(b for b in range(100) if flickers_on(b, "lamp"))
    beat_off = next(b for b in range(100) if not flickers_on(b, "lamp"))
    assert emitted_level(lamp, "lamp", beat_on) == "dim"
    assert emitted_level(lamp, "lamp", beat_off) == "lit"
    failing = dict(lamp, steadiness="failing")
    out = next(b for b in range(200) if fails_on(b, "lamp"))
    on = next(b for b in range(200) if not fails_on(b, "lamp"))
    assert emitted_level(failing, "lamp", out) is None
    assert emitted_level(failing, "lamp", on) == "lit"
    assert emitted_level(dict(lamp, state={"lit": False}), "lamp", beat_off) is None
    assert emitted_level({"name": "x"}, "x", 0) is None


def test_the_field_reads_the_beat_stamped_on_the_scene():
    sc = lamp_room("lit", steadiness="flickering")
    on = next(b for b in range(100) if flickers_on(b, "lamp"))
    off = next(b for b in range(100) if not flickers_on(b, "lamp"))
    sc[BEAT_KEY] = on
    assert light_field(sc, "r").sources[0]["level"] == "dim"
    sc[BEAT_KEY] = off
    assert light_field(sc, "r").sources[0]["level"] == "lit"
    # A reroll -- the same scene, the same beat -- sees the same light.
    assert light_field(copy.deepcopy(sc), "r").sources[0]["level"] == "lit"


def test_failing_sources_out_names_only_lit_failing_sources_on_their_beat():
    sc = lamp_room("lit", steadiness="failing")
    out = next(b for b in range(200) if fails_on(b, "lamp"))
    on = next(b for b in range(200) if not fails_on(b, "lamp"))
    assert failing_sources_out(sc, out) == [("lamp", "the lamp")]
    assert failing_sources_out(sc, on) == []
    sc["entities"]["lamp"]["state"] = {"lit": False}
    assert failing_sources_out(sc, out) == []
    assert failing_sources_out(lamp_room("lit"), out) == []


def test_the_commit_records_a_failed_source_out_and_tells_the_director(temp_db):
    """The seam is `engine_notices`, the channel every other engine fact the
    Director must answer next beat already rides; the switch is `state.lit`,
    the one a doused torch already uses; and the scene is stamped with the
    next beat's index for the field to read."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist import commit

    sc = lamp_room("lit", steadiness="failing")
    out = next(b for b in range(200) if fails_on(b, "lamp"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Lamp", "", _time.time()))
    temp_db.wset(chat_id, "scene", sc)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Lamp", persona_id=None,
                      lorebook_id=None, scenario="", created=_time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=out, player_input="",
                      created=_time.time()),
        cast=[], input="")
    ctx.director_resolve = {"state_diff": {"time": "a moment later"}}
    prepared = commit.prepare_scene_commit(ctx)
    merged = prepared["scene"]
    assert merged["entities"]["lamp"]["state"]["lit"] is False
    assert merged[BEAT_KEY] == out + 1
    # Staged on the context for commit's transaction: prepare writes nothing
    # durable (A66), and `commit_scene` files the list under the write lock.
    notices = list(ctx.engine_feedback)
    assert any("has gone out" in n and "the lamp" in n for n in notices), notices
    assert temp_db.wget(chat_id, "engine_notices", []) == []
    assert any("has gone out" in w for w in ctx.warnings)
    # The beat it does NOT fail: nothing is said, nothing is switched.
    on = next(b for b in range(200) if not fails_on(b, "lamp"))
    temp_db.wset(chat_id, "scene", lamp_room("lit", steadiness="failing"))
    temp_db.wset(chat_id, "engine_notices", [])
    ctx.turn.idx = on
    ctx.warnings.clear()
    ctx.engine_feedback.clear()
    prepared = commit.prepare_scene_commit(ctx)
    assert prepared["scene"]["entities"]["lamp"].get("state", {}).get("lit", True) is True
    assert ctx.engine_feedback == []


# ---------------------------------------------------------------------------
# Schema: the three fields survive the round trip and the merge
# ---------------------------------------------------------------------------

def test_the_schema_declares_the_fields_and_the_merge_keeps_them():
    from llm.schemas import SceneEntityDef
    declared = SceneEntityDef(
        name="the lamp", light_source="lit", light_shape="cone",
        light_height="waist", steadiness="flickering",
        state={"lit": True, "pointed_at": "n"}).model_dump()
    assert declared["light_shape"] == "cone"
    assert declared["light_height"] == "waist"
    assert declared["steadiness"] == "flickering"
    assert declared["state"]["pointed_at"] == "n"
    for field in ("light_shape", "light_height", "steadiness"):
        assert field in _ENTITY_DEFAULT_FIELDS and _ENTITY_DEFAULT_FIELDS[field] is None
        assert field in _ENTITY_STRUCTURAL_FIELDS
    scene = _scene({"r": _room("the Hall")}, {"lamp": "r"},
                   entities={"lamp": dict(declared)})
    # A re-echo that says nothing about the light fields keeps them.
    merged = merge_scene_with_diff(scene, {"entities": {"lamp": {
        "name": "the lamp", "state": {"lit": True}}}})
    lamp = merged["entities"]["lamp"]
    assert lamp["light_shape"] == "cone"
    assert lamp["light_height"] == "waist"
    assert lamp["steadiness"] == "flickering"
    assert lamp["state"]["pointed_at"] == "n"
    # A re-echo validated through the model (None-filled) keeps them too.
    echo = SceneEntityDef(name="the lamp").model_dump()
    merged = merge_scene_with_diff(scene, {"entities": {"lamp": echo}})
    assert merged["entities"]["lamp"]["light_shape"] == "cone"
    # And a declaration that changes one changes it.
    merged = merge_scene_with_diff(scene, {"entities": {"lamp": {
        "name": "the lamp", "light_shape": "all_round"}}})
    assert merged["entities"]["lamp"]["light_shape"] == "all_round"


def test_unknown_words_fall_to_the_wider_default():
    from world.spatial import normalize_light_shape, normalize_steadiness
    assert normalize_light_shape("spotlight") == "all_round"
    assert normalize_light_shape("Cone") == "cone"
    assert normalize_steadiness("guttering") == "steady"
    assert normalize_steadiness("FAILING") == "failing"


# ---------------------------------------------------------------------------
# PA3: the declared word is a floor, and a room whose fixtures are all out
# ---------------------------------------------------------------------------

def watch_room(*, lit=True, portable=False, exposure="enclosed",
               declared="bright"):
    """A room declared `bright` whose only source is one `bright` fixture --
    the lighthouse watch room, whose great lamp failed."""
    lamp = {"name": "the great lamp", "light_source": "bright",
            "state": {"lit": lit}}
    if portable:
        lamp["portable"] = True
    return _scene({"r": _room("the Watch Room", light=declared,
                              exposure=exposure,
                              anchors={"rail": {"desc": "the gallery rail"}})},
                  {"P": "r", "lamp": "r"}, entities={"lamp": lamp},
                  stations={"P": {"at": "rail"}})


def test_a_room_whose_only_fixture_is_out_reads_dark():
    """PA3. The declared word and the sources are two accounts of one fact;
    where the room HOLDS fixtures and every one of them is switched off, the
    word is the account that went stale. Live: the watch room read `bright`
    for nine beats after its only lamp failed and the commit correctly wrote
    `state.lit: false`, so the story's one secret -- a light going out --
    could not be seen (`PLAY_2026_09_05_lighthouse.md` § PA3)."""
    assert effective_light(watch_room(lit=True), "r") == "bright"
    assert light_at(watch_room(lit=True), "P") == "bright"
    assert effective_light(watch_room(lit=False), "r") == "dark"
    assert light_at(watch_room(lit=False), "P") == "dark"
    from world.spatial import ambient_floor_word
    assert ambient_floor_word(watch_room(lit=True), "r") == "bright"
    assert ambient_floor_word(watch_room(lit=False), "r") == "dark"


def test_the_floor_yields_only_to_the_rooms_own_fixtures():
    """Narrow three ways: no fixture at all keeps the word (F40's opposite
    instance -- a declared `lit` room must not go dark for want of an entity
    nobody wrote), a doused thing someone CARRIED in is not the room's
    account of itself, and outdoors the sky is the account."""
    for light in ("dark", "dim", "lit", "bright"):
        sc = _scene({"r": _room("the Hall", light=light,
                                anchors={"table": {"desc": "a table"}})},
                    {"P": "r"}, stations={"P": {"at": "table"}})
        assert effective_light(sc, "r") == light
        assert light_at(sc, "P") == light
    assert effective_light(watch_room(lit=False, portable=True), "r") == "bright"
    outdoors = watch_room(lit=False, exposure="open")
    assert effective_light(outdoors, "r") == "bright"
    # A `dark` room cannot be lowered further, and a lit fixture holds the
    # floor up however feebly it burns (F50's lone candle is untouched).
    assert effective_light(watch_room(lit=False, declared="dark"), "r") == "dark"


def test_a_doused_rooms_floor_no_longer_spills_next_door():
    """The floor that yielded gives nothing through the doorway either: one
    answer for what a room's own light is, read by both the floor and the
    spill."""
    def pair(lit):
        rooms = {
            "hall": _room("the Hall", light="bright", anchors={
                "rail": {"desc": "the gallery rail"}},
                adjacent=[{"to": "cell", "barrier": "open", "dir": "e"}]),
            "cell": _room("the Cell", light="dark", anchors={
                "cot": {"desc": "a cot"}},
                adjacent=[{"to": "hall", "barrier": "open", "dir": "w"}]),
        }
        return _scene(rooms, {"lamp": "hall"}, entities={"lamp": {
            "name": "the great lamp", "light_source": "bright",
            "state": {"lit": lit}}})
    lf = light_field(pair(True), "cell")
    assert lf.spill and max(lf.spill.values()) > 0.0
    dark = light_field(pair(False), "cell")
    assert not dark.spill
    assert effective_light(pair(False), "cell") == "dark"


# ---------------------------------------------------------------------------
# PC4: a flicker is a source wavering, not a source failing
# ---------------------------------------------------------------------------

def test_a_flickering_source_on_the_bottom_rung_still_gives_light():
    """A `dim` source on its flicker beats keeps the dimmest light it can
    give: going out is what `failing` means, and that files a notice where a
    flicker files nothing. Live: a candle lit in the player's own hand
    contributed no light at all on its flicker beats, and the room -- whose
    only source it was -- lost it entirely (`PLAY_2026_09_05_manor.md`
    § PC4)."""
    candle = {"name": "the tower candle", "light_source": "dim",
              "steadiness": "flickering", "portable": True}
    beats = [b for b in range(FLICKER_RATE * 8) if flickers_on(b, "candle")]
    assert beats                                   # the hash does pick some
    for beat in beats:
        assert emitted_level(candle, "candle", beat) == "dim"
    for beat in range(FLICKER_RATE * 8):
        sc = lamp_room("dim", steadiness="flickering")
        sc[BEAT_KEY] = beat
        assert [s["id"] for s in light_field(sc, "r").sources] == ["lamp"]
    # A `lit` source still drops to `dim`, and a failing one still goes out.
    lamp = {"name": "the lamp", "light_source": "lit",
            "steadiness": "flickering"}
    assert emitted_level(lamp, "lamp", beats[0]) == "dim"
    failing = {"name": "the lamp", "light_source": "dim",
               "steadiness": "failing"}
    out = next(b for b in range(FAIL_RATE * 40) if fails_on(b, "lamp"))
    assert emitted_level(failing, "lamp", out) is None
    # A source declared `dark` is not a light and a flicker does not make it
    # one.
    assert emitted_level({"name": "x", "light_source": "dark",
                          "steadiness": "flickering"}, "x", beats[0]) is None


# ---------------------------------------------------------------------------
# PA8: a thing is seen by the light that falls on it
# ---------------------------------------------------------------------------

def kitchen(*, lit=False):
    """A dark kitchen with a stove, a door onto the store, and a lamp that
    is out until it is lit."""
    rooms = {
        "kitchen": _room("the Kitchen", light="dark", anchors={
            "stove": {"desc": "the cast-iron stove", "dir": "n",
                      "height": "waist"},
            "table": {"desc": "the scrubbed table", "cell": [2, 3],
                      "height": "waist"}},
            adjacent=[{"to": "store", "barrier": "closed_door", "dir": "e"}]),
        "store": _room("the Store", light="dark", anchors={
            "sack": {"desc": "a sack of flour"}},
            adjacent=[{"to": "kitchen", "barrier": "closed_door", "dir": "w"}]),
    }
    return _scene(rooms, {"P": "kitchen", "lamp": "kitchen"},
                  entities={"lamp": {"name": "the lamp",
                                     "light_source": "lit",
                                     "state": {"lit": lit}}},
                  stations={"P": {"at": "table"}})


def test_a_dark_room_names_no_features_and_still_names_its_doorways():
    """PA8. A thing is seen by the light that falls on it, exactly as a body
    is. Live: after the player blew out the lamp her own view read "You can
    see The cast-iron stove ... within arm's reach ... It is dark here."
    (`PLAY_2026_09_05_lighthouse.md` § PA8)."""
    from world.spatial import feature_visibility
    dark = {r["anchor"]: r for r in feature_visibility(kitchen(), "P")}
    assert dark["stove"]["visible"] is False
    assert dark["stove"]["basis"] == "light"
    assert dark["door:store"]["visible"] is True   # a gap in the wall, not a thing
    # The one a body has its hands on is knowledge from a channel that does
    # not need light.
    assert dark["table"]["visible"] is True
    lit = {r["anchor"]: r for r in feature_visibility(kitchen(lit=True), "P")}
    assert lit["stove"]["visible"] is True
    assert lit["stove"]["basis"] == "open"


def test_where_light_falls_the_features_grade_as_they_always_did():
    """The gate SUBTRACTS and only ever subtracts: in a lit room every row
    is what it was before the light was consulted, and where there is no
    field to ask (`_unlit_cells` -> None) nothing is taken."""
    from world.spatial import _unlit_cells, feature_visibility
    sc = kitchen(lit=True)
    rows = {r["anchor"]: r for r in feature_visibility(sc, "P")}
    assert rows and all(row["visible"] for row in rows.values())
    assert all(row["basis"] != "light" for row in rows.values())
    assert _unlit_cells(sc, "no_such_room") is None
