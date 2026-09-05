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
    CONE_HALF_ANGLE, CONE_PENUMBRA, DARK_THRESHOLD, DIM_T, FAIL_RATE,
    FLICKER_RATE, GLARE_CELLS, GLARE_POWER, LIGHT_LEVELS, LIGHT_SHAPES,
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
    # Straight up the axis: full power at the same decay as all_round.
    assert direct[(3, 1)] == pytest.approx(1.2)
    # Ninety degrees off the axis, beyond the penumbra: nothing direct.
    assert direct.get((5, 3), 0.0) == 0.0
    assert direct.get((3, 5), 0.0) == 0.0
    # The penumbra is a linear ramp, not a step: 45 degrees off (the cell
    # diagonally ahead) is between full and nothing.
    diag = direct[(4, 2)]
    assert 0.0 < diag < 6.0 / 3.0
    assert diag == pytest.approx((6.0 / 3.0) * (1 - (45 - CONE_HALF_ANGLE) / CONE_PENUMBRA))
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
    sc = kitchen_and_cellar()
    lf = light_field(sc, "c")
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
    # The far corner of the cellar is dark; the floor of the kitchen does
    # not spill (a floor is not a source), only the stove does.
    far = max(cellar_cells, key=lambda c: (c[1], -abs(c[0] - door_x)))
    assert lf.level(far) == "dark"
    assert lf.floor["k"] == POWER["lit"] and lf.floor["c"] == POWER["dark"]
    assert stove["room"] == "k"


def test_without_a_source_the_kitchen_floor_does_not_spill():
    """The room-level rule lifted a dark room beside a lit one to dim; the
    field makes spill a consequence of the rays, and a floor casts none. The
    note's first open question for the owner (§ 4.6) is exactly this."""
    sc = kitchen_and_cellar(source=False)
    assert effective_light(sc, "c") == "dark"
    assert effective_light(sc, "k") == "lit"


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
    assert SIGHT_LEVELS == ("none", "shapes", "full")
    assert _LIGHT_SIGHT == {"dark": "none", "dim": "shapes", "lit": "full",
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


def test_a_body_without_a_station_keeps_the_room_level_answer(monkeypatch):
    """A body with no station is somewhere in the room, and 'somewhere' has
    no cell to read: the room-level `light_at` answers exactly as it does
    with the field switched off, though the room itself carries geometry."""
    sc = lamp_room("lit")
    sc["positions"]["P"] = "r"
    assert light_geometry_exists(sc, "r") and body_cell(sc, "P") is None
    with_field = light_at(sc, "P")
    import world.spatial_light_field as sibling   # patched, not called
    monkeypatch.setattr(sibling, "field_light_at", lambda scene, name: None)
    assert with_field == light_at(sc, "P")


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
    notices = temp_db.wget(chat_id, "engine_notices", [])
    assert any("has gone out" in n and "the lamp" in n for n in notices), notices
    assert any("has gone out" in w for w in ctx.warnings)
    # The beat it does NOT fail: nothing is said, nothing is switched.
    on = next(b for b in range(200) if not fails_on(b, "lamp"))
    temp_db.wset(chat_id, "scene", lamp_room("lit", steadiness="failing"))
    temp_db.wset(chat_id, "engine_notices", [])
    ctx.turn.idx = on
    ctx.warnings.clear()
    prepared = commit.prepare_scene_commit(ctx)
    assert prepared["scene"]["entities"]["lamp"].get("state", {}).get("lit", True) is True
    assert temp_db.wget(chat_id, "engine_notices", []) == []


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
