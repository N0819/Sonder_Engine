# spatial_light_field.py
"""Light as a quantity on the sight grid, derived and never stored.

`world/spatial_light.py` is a ROOM-level model: a room has one word on the
ladder `dark | dim | lit | bright`, a source lights the room it stands in,
and a body is lifted to the source's level when it holds it or stands near
it. That model has no DIRECTION (a flashlight lights a room as a lantern
does), no DISTANCE beyond `near`, no SHADOW (a body behind the counter is
as lit as the body in front of it, though the FOV layer knows the counter
is there), and a one-step, one-hop spill.

This module runs sight backwards. `world/spatial_fov.py` already derives a
per-room grid, anchors as occluders with a height rank, body cells from
stations, a facing, a recursive `shadowcast`, and the wall between two
placed rooms as a LINE with the doorway as a gap in it. Light is the same
rays from the lamp instead of the eye:

    every cell of the composite field holds a scalar, SUMMED from every
    source whose rays reach it, decayed by distance, shaped by the source's
    cone, shadowed by anything at or above the source's height, filled in by
    bounce, floored by the room's ambient, and QUANTISED TO THE LADDER LAST

-- so every reader that exists today (`light_at`, `effective_light`,
`sight_level`, the composer's darkness sentences, the Director's dark-room
check) keeps its four words and gets them from geometry instead of from the
room. The design is `docs/design/DESIGN_LIGHT_FIELD.md`; every constant in
§ 6 of that note is a named module constant below with the table beside it.

FAIL-OPEN, the same way `observer_field` is. Where the scene carries no
geometry -- a room with neither a size tier nor anchors, a body without a
station -- the field does not exist for that reader and it falls back to
the room-level function unchanged, so an existing scene composes
byte-identically (`tests/test_light_field.py` pins this against the
existing light fixtures). Pure, total, no I/O, no model.

A SOURCE IS A CLASS, NOT A DEVICE. Beside the existing `light_source` (the
ladder word the source EMITS) an entity may carry:

    light_shape   all_round | cone          how the emission is distributed
    light_height  floor | waist | head | full  where the source sits (the
                                            anchor height vocabulary)
    steadiness    steady | flickering | failing
    state.pointed_at  <entity or anchor id> | <bearing>   a cone's axis

Four closed sets the engine OWNS and reads (`LIGHT_LEVELS`, `LIGHT_SHAPES`,
`HEIGHTS`, `STEADINESS`): a schema in CLAUDE.md's sense, not a vocabulary
table. Nothing here names a lantern, a torch, a phone or a spell.

Measured before this was written (2026-09-04, 104 live scenes, 589 rooms,
823 entities, chat 111 excluded): 2 entities carry `light_source` (one
`dim`, one `lit`), 0 are portable, 0 have a station or a holder record;
321/589 rooms carry a size or anchors (where this field exists), 2/589 an
authored geometry field; both rooms holding a source carry a size or
anchors, neither an authored height. So today the field bites on ambient
and spill far more than on sources, and the corpus is not the argument for
the constants -- the synthetic table in the note's § 9.3 is.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Optional

from world.spatial_barriers import _SIGHT_BARRIERS, normalize_barrier
from world.spatial_containment import container_of
from world.spatial_fov import (
    _FRONT_SECTORS,
    _HEIGHT_RANK,
    _centre,
    _cone_sector,
    _line,
    _observer_cell,
    _on_wall_line,
    _sector_verdict,
    _visible_set,
    _wall_verdict,
    HEIGHTS,
    body_cell,
    eye_rank,
    feature_visibility,
    grid_side,
    height_rank,
    normalize_height,
    room_field,
    shadowcast,
    wall_aperture_cells,
)
from world.spatial_geometry import door_anchor_id, effective_facing
from world.spatial_identity import _ci_get, room_of
from world.spatial_light import (
    LIGHT_LEVELS, _light_radius, normalize_light, room_light)
from world.spatial_orientation import _BEARING_DEG, normalize_bearing, relative_bearing


# ---------------------------------------------------------------------------
# The closed vocabularies
# ---------------------------------------------------------------------------

LIGHT_SHAPES = ("all_round", "cone")
DEFAULT_LIGHT_SHAPE = "all_round"

STEADINESS = ("steady", "flickering", "failing")
DEFAULT_STEADINESS = "steady"

#: The heights a source may sit at are the anchor heights (`spatial_fov.
#: HEIGHTS`), re-exported so a reader of this module sees the whole schema.
LIGHT_HEIGHTS = HEIGHTS


def normalize_light_shape(value) -> str:
    v = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    return v if v in LIGHT_SHAPES else DEFAULT_LIGHT_SHAPE


def normalize_steadiness(value) -> str:
    v = str(value or "").strip().casefold()
    return v if v in STEADINESS else DEFAULT_STEADINESS


# ---------------------------------------------------------------------------
# CONSTANTS THE OWNER SETS (DESIGN_LIGHT_FIELD.md § 6). Every one is a
# STARTING POINT, chosen so that a `lit` source in a `medium` (6-cell) room
# reads `lit` to about two cells, `dim` to about four, and reaches the far
# wall as `dark`, and so that a `bright` fixture at `full` height fills a
# medium room to `lit` once bounce is applied. The synthetic table in the
# note's § 9.3 is what these produce; the owner may move any of them after
# reading it. None is buried anywhere else.
#
#     POWER          dark 0 | dim 2 | lit 6 | bright 18   ladder units at d=0
#     DIM_T / LIT_T / BRIGHT_T   0.5 / 2.5 / 8.0          quantisation
#                                (LIT_T was proposed at 2.0; see below)
#     DARK_THRESHOLD  = DIM_T                              reach and bounce stop
#     CONE_HALF_ANGLE 30 deg     CONE_PENUMBRA 20 deg
#     BOUNCE          enclosed 0.25 | sheltered 0.12 | open 0.05
#     BOUNCE_REACH    3 cells    BOUNCE_PASSES_CAP 4
#     GLARE_POWER     = POWER[lit]   GLARE_CELLS 2
#     FLICKER_RATE    1 beat in 4    FAIL_RATE 1 beat in 12
# ---------------------------------------------------------------------------

#: Power in "ladder units at one cell": a source of power P lights the cell
#: it stands in to intensity P, and a room's ambient floor is the power of
#: its own word.
POWER = {"dark": 0.0, "dim": 2.0, "lit": 6.0, "bright": 18.0}

#: Quantisation thresholds, applied LAST: bright if I >= BRIGHT_T, lit if
#: I >= LIT_T, dim if I >= DIM_T, else dark. THE THRESHOLDS MUST LIE STRICTLY
#: BETWEEN THE POWERS, so that a word's own power quantises back to the word
#: (`tests/test_light_field.py` pins the round trip): the floor of a `dim`
#: room is POWER["dim"], and if that sat on LIT_T every dim room with a grid
#: read `lit` to every stationed body in it. The note proposed LIT_T = 2.0,
#: exactly POWER["dim"]; the first run of the fail-open pin found the dim
#: room reading lit, and 2.5 is the smallest move that separates them. The
#: owner may set it elsewhere above 2.0.
DIM_T = 0.5
LIT_T = 2.5
BRIGHT_T = 8.0

#: Where a source's reach ends and where bounce stops adding: the intensity
#: below which a cell is dark.
DARK_THRESHOLD = DIM_T

#: A cone is full inside CONE_HALF_ANGLE of its axis and falls linearly to
#: nothing over CONE_PENUMBRA degrees beyond it. Bearings are the eight
#: compass points, so a word-given axis is quantised to 45 degrees; the
#: penumbra exists to hide that quantisation, which is why it is a constant
#: and not a nicety.
CONE_HALF_ANGLE = 30.0
CONE_PENUMBRA = 20.0

#: Indirect fill, by the room's `exposure` (`world/weather.room_exposure`):
#: the whole of a ceiling and a floor in one coefficient. `enclosed` returns
#: light from walls, ceiling and floor; `sheltered` has a roof and no walls;
#: `open` has the ground alone.
BOUNCE = {"enclosed": 0.25, "sheltered": 0.12, "open": 0.05}

#: How far one bounce carries, in cells, and a SAFETY ceiling on passes that
#: is expected never to bind: with BOUNCE <= 0.25 and inverse-square decay
#: the second pass already adds under a tenth of the first.
BOUNCE_REACH = 3
BOUNCE_PASSES_CAP = 4

#: Glare: a source of at least this power, inside the observer's front cone
#: at no more than this many cells, with the target on the far side of it,
#: caps sight at `shapes`. The flashlight in your face -- and the all-round
#: lantern held up between two faces, decided 2026-09-04: glare is about
#: POWER IN THE EYES, not about the source's shape; a cone decides only
#: whether the power reaches the eye at all (`per_source` at the observer's
#: cell), so a cone pointed away dazzles nobody and a lantern does.
GLARE_POWER = POWER["lit"]
GLARE_CELLS = 2

#: THE AMBIENT FLOOR SPILLS THROUGH DOORWAYS (the owner agreed, 2026-09-04;
#: the note's open question 1). Each aperture cell of a wall between two
#: placed rooms emits the GIVING room's floor into the TAKING room at height
#: `full`, power FLOOR_SPILL * POWER[floor word] * the aperture's pass,
#: inverse-square from the aperture cell, summed over the aperture's cells
#: (a wide door spills more), quantised last with everything else. Through
#: whatever passes light -- an open doorway, a window (glass passes light
#: and not bodies, so the light composite places it where sight's does not,
#: `light_passes`) -- never through a wall or a closed door. 0 reproduces
#: the field as first built (no spill).
#:
#: Tuned so a dark medium room with an open door onto a `lit` room reads
#: `dim` at the door cell and `dark` in the far corner, and so no floor's
#: spill alone reads `lit` at the door (the room-level rule it replaces
#: never lifted borrowed light past dim). Measured on the synthetic pair
#: (`tests/test_light_field.py`, the door cell d=1 from the aperture,
#: bounce on):
#:
#:   FLOOR_SPILL   lit neighbour: d=1 / d=2 / far corner   bright neighbour: d=1 / d=2 / d=3
#:   0.00          dark / dark / dark                       dark / dark / dark
#:   0.20          dim  / dark / dark                       dim  / dim  / dark
#:   0.25          dim  / dark / dark                       dim  / dim  / dim
#:   0.33          dim  / dark / dark                       lit  / dim  / dim
#:   0.50          dim  / dim  / dark                       lit  / dim  / dim
#:
#: (intensities at 0.25: lit 0.79 / 0.35 / 0.02, bright 2.43 / 1.11 / 0.58;
#: the cells beside the doorframe read dim from 0.25 up, as a doorway's glow
#: does.) 0.25 is the largest value at which a bright floor's spill still
#: reads dim at the door. On the owner's corpus it returns chats 73 and
#: 74's "Hotel back office" (small, dark, an open edge onto the lit lobby)
#: to `dim` in the three cells at its doorway -- the two rooms the field
#: alone had made dark, § 9.4 of the note -- while the room's median stays
#: dark, as a small dark room with one lit doorway is.
FLOOR_SPILL = 0.25

#: Steadiness, as "one beat in N": a `flickering` source drops one level on
#: beats where hash(beat, source) % FLICKER_RATE == 0; a `failing` source
#: goes out where hash(beat, source) % FAIL_RATE == 0. A hash, not a draw,
#: so a reroll of the beat sees the same light as the beat it replaces.
FLICKER_RATE = 4
FAIL_RATE = 12

#: The scene key the commit stamps with the index of the beat about to be
#: played (`persist/commit_scene_state.prepare_scene_commit`), so the two
#: hashes above can be computed from the scene alone at read time. Absent
#: -- the opening turn, an old story -- reads as beat 0.
BEAT_KEY = "beat_idx"


# ---------------------------------------------------------------------------
# Where the field exists
# ---------------------------------------------------------------------------

def light_geometry_exists(scene: dict, room_id) -> bool:
    """Does this room carry the geometry the field is computed over?

    The note's § 7 states the gate: a room with neither a size tier nor
    anchors has no grid worth lighting, and every reader for it keeps the
    room-level answer. A room that has either has asked to be lit from
    somewhere. (Deliberately WIDER than `room_has_geometry`, the FOV layer's
    opt-in for the furniture sentence, which needs an authored height:
    light needs a grid and a place for the source, not a counter to shadow
    with -- 321/589 live rooms against 2/589.)
    """
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return False
    if str(room.get("size") or "").strip():
        return True
    anchors = room.get("anchors")
    return bool(anchors) if isinstance(anchors, (dict, list, tuple)) else False


def beat_index(scene: dict) -> int:
    try:
        return int((scene or {}).get(BEAT_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def light_passes(scene, room_id, edge):
    """The light field's placement predicate for `spatial_fov.room_field`:
    1.0 for every barrier sight crosses (`_SIGHT_BARRIERS` -- an open
    doorway, a window, a grille, a one-way pane), None for a wall, a closed
    door or a curtain. WIDER than `sight_passes`, which leaves glass and
    grilles unplaced because a grid cannot be walked into through them; a
    lamp behind a window lights this room all the same, and so does the lit
    room's floor through it. One grid derivation, three predicates
    (`spatial_fov._placed_neighbours`)."""
    barrier = normalize_barrier(edge.get("barrier"))
    return 1.0 if barrier in _SIGHT_BARRIERS else None


# ---------------------------------------------------------------------------
# Steadiness
# ---------------------------------------------------------------------------

def _beat_hash(beat, source_id) -> int:
    joined = "light\x1f%s\x1f%s" % (int(beat), str(source_id))
    return int(hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8], 16)


def flickers_on(beat, source_id) -> bool:
    """Is this the beat a `flickering` source drops one level?"""
    return _beat_hash(beat, source_id) % FLICKER_RATE == 0


def fails_on(beat, source_id) -> bool:
    """Is this the beat a `failing` source goes out?"""
    return _beat_hash(beat, source_id) % FAIL_RATE == 0


def _lit(entity: dict) -> bool:
    state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
    return state.get("lit", True) not in (False, 0, "off", "false", "no",
                                          "doused", "out")


def _one_level_down(level: str) -> str:
    """One rung down the ladder, and NEVER past the dimmest light a source
    can still give.

    FLICKERING IS A SOURCE WAVERING, NOT A SOURCE FAILING. Going out is what
    `failing` means, and it files a notice the Director answers (§ 5); a
    flicker files nothing, so a flicker that reached `dark` put a source out
    with nothing anywhere to say so. Measured live: a `dim` candle lit in
    the player's own hand contributed no light at all on its flicker beats,
    and the room -- whose only source it was -- read its declared floor with
    the candle absent from `light_sources` entirely
    (`PLAY_2026_09_05_manor.md` § PC4). A source declared `dark` is not a
    light and stays where it is."""
    i = LIGHT_LEVELS.index(level) if level in LIGHT_LEVELS else 2
    return LIGHT_LEVELS[i - 1] if i > 1 else level


def emitted_level(entity: dict, source_id, beat) -> Optional[str]:
    """The ladder word a source emits THIS beat, or None when it gives no
    light: unlit, `failing` and out on this beat, or `dark`. A `flickering`
    source is one level down on its flicker beats."""
    if not isinstance(entity, dict) or not entity.get("light_source"):
        return None
    if not _lit(entity):
        return None
    steadiness = normalize_steadiness(entity.get("steadiness"))
    if steadiness == "failing" and fails_on(beat, source_id):
        return None
    level = normalize_light(entity.get("light_source"))
    if steadiness == "flickering" and flickers_on(beat, source_id):
        level = _one_level_down(level)
    return None if level == "dark" else level


def _room_fixtures(scene: dict, room_id) -> list:
    """Every ROOM-FILLING light source standing in `room_id`, lit or not --
    the room's own account of what lights it. Positioned by id or by name,
    the way `spatial_light.source_light` reads them; filling by
    `_light_radius`, so a hearth, a sconce or a ceiling fixture counts and a
    hand torch does not. What someone carried in is not the room's account
    of itself, and a stranger walking into a lit hall with a dead lantern in
    their fist must not put the hall out."""
    entities = (scene or {}).get("entities") or {}
    positions = (scene or {}).get("positions") or {}
    if not isinstance(entities, dict) or not room_id:
        return []
    out = []
    for eid, entity in entities.items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        where = _ci_get(positions, eid)
        if where is None:
            where = _ci_get(positions, str(entity.get("name") or ""))
        if where == room_id and _light_radius(entity) == "room":
            out.append(entity)
    return out


def ambient_floor_word(scene: dict, room_id) -> str:
    """The light a room gives its own cells as a FLOOR (§ 4 step 6): the
    declared word `room_light` answers, unless the room's own sources
    contradict it.

    THE DECLARED WORD AND THE SOURCES ARE TWO ACCOUNTS OF ONE FACT, and
    until 2026-09-05 neither was allowed to correct the other, so the lie
    ran in whichever direction the story moved. Where a room HOLDS sources
    and every one of them is switched off, the sources are the account that
    changed and the word is the one that went stale: a room whose lamps are
    all out is dark, whatever word it was minted with. Measured live: the
    lighthouse watch room read `bright` for nine beats after its only lamp
    failed and the commit correctly wrote `state.lit: false`, so the story's
    one secret -- a light going out -- could not be seen at all
    (`PLAY_2026_09_05_lighthouse.md` § PA3).

    Narrow deliberately, three ways, because a floor that yields too easily
    is F40 again from the other side:

      * a room with no FIXTURE has said nothing about its light and keeps
        its word -- a windowless room declared `lit` by whoever minted it
        does not go dark for want of an entity nobody wrote, and a doused
        hand torch carried into it is not the room's account of itself
        (`_room_fixtures`);
      * a source that is LIT holds the floor up however feebly it burns, so
        F50's lone candle in a `dim` parlour is untouched, and only the
        SWITCH counts: a `flickering` source between its beats and a
        `failing` one that has not yet been recorded out are still lit;
      * only an `enclosed` room's word yields. Outdoors the sky is the
        account and the lamps are not (`room_light` already lets the sun
        overrule the declared word there); whether a declared word should
        ever outrank the sources outdoors, and whether the floor should hold
        for `dim`, are the owner's -- registered in `docs/UNBUILT.md`.
    """
    declared = room_light(scene, room_id)
    if declared == "dark" or _exposure_of(scene, room_id) != "enclosed":
        return declared
    sources = _room_fixtures(scene, room_id)
    if not sources or any(_lit(entity) for entity in sources):
        return declared
    return "dark"


def failing_sources_out(scene: dict, beat) -> list:
    """`[(entity_id, label)]` for every lit `failing` source the hash puts
    out on `beat`. The commit reads this to record `state.lit: false` and
    file the notice the Director answers next beat; the field reads the
    same hash at perception time, so the two agree without a write."""
    out = []
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        if not _lit(entity):
            continue
        if normalize_steadiness(entity.get("steadiness")) != "failing":
            continue
        if fails_on(beat, eid):
            out.append((str(eid), str(entity.get("name") or eid)))
    return out


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def _holder_of(scene: dict, eid, entity) -> Optional[str]:
    """The body carrying this source, if the containment ledger says one
    does: the innermost container that is positioned in a room."""
    for key in (eid, entity.get("name")):
        if not key:
            continue
        holder = container_of(scene, str(key))
        if holder and room_of(scene, holder):
            return str(holder)
    return None


def _angle_deg(a: tuple, b: tuple) -> Optional[float]:
    """Compass angle from cell a to cell b in degrees (n = 0, e = 90), the
    same convention as `_BEARING_DEG`; None when they coincide."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return None
    return math.degrees(math.atan2(dx, -dy)) % 360.0


def _angle_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _resolve_pointed_at(scene, field, room_id, origin, pointed):
    """A `state.pointed_at` value as an axis in degrees: a bearing word
    through `_BEARING_DEG`, an entity through its cell, an anchor through
    its placed cell. None when it resolves to nothing."""
    if pointed is None:
        return None
    if isinstance(pointed, (int, float)) and not isinstance(pointed, bool):
        return float(pointed) % 360.0
    text = str(pointed or "").strip()
    if not text:
        return None
    bearing = normalize_bearing(text)
    if bearing in _BEARING_DEG:
        return float(_BEARING_DEG[bearing])
    # An entity or body in a placed room.
    t_room = room_of(scene, text)
    if t_room and t_room in field.offsets:
        cell = body_cell(scene, text)
        if cell:
            return _angle_deg(origin, field.cell_of(t_room, cell))
    # An anchor of the source's own room.
    placed = (field.anchors.get(room_id) or {}).get(text)
    if placed and placed.get("cells"):
        cells = placed["cells"]
        target = min(cells, key=lambda c: (c[0] - origin[0]) ** 2
                     + (c[1] - origin[1]) ** 2)
        return _angle_deg(origin, field.cell_of(room_id, target))
    return None


def light_sources(scene: dict, field, beat) -> list:
    """Every source that lights a cell of this field on this beat:

      {id, label, room, cell (field frame), power, height (rank), shape,
       axis (degrees or None), holder}

    A source's cell is its holder's when a body carries it, else its own
    station's, else -- unmeasured -- the centre of its room, the same
    approximation `_observer_cell` makes for an unplaced observer: a lamp
    somewhere in the room is not nowhere. Its height is the declared
    `light_height`, else the holder's eye rank when carried, `head` when
    standing free and portable, `full` when it is a fixture of the room.
    A cone with neither `pointed_at` nor a facing to follow is all_round
    for the beat: the wider answer.
    """
    out = []
    entities = (scene or {}).get("entities") or {}
    if not isinstance(entities, dict):
        return out
    for eid, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        level = emitted_level(entity, eid, beat)
        if level is None:
            continue
        power = POWER.get(level, 0.0)
        if power <= 0.0:
            continue
        room_id = room_of(scene, str(eid))
        if room_id is None and entity.get("name"):
            room_id = room_of(scene, str(entity["name"]))
        if room_id is None or room_id not in field.offsets:
            continue
        holder = _holder_of(scene, eid, entity)
        cell = None
        if holder and room_of(scene, holder) == room_id:
            cell = body_cell(scene, holder)
        if cell is None:
            cell = body_cell(scene, str(eid))
        if cell is None and entity.get("name"):
            cell = body_cell(scene, str(entity["name"]))
        if cell is None:
            cell = _centre(grid_side(scene, room_id))
        origin = field.cell_of(room_id, cell)
        declared = str(entity.get("light_height") or "").strip()
        if declared and normalize_height(declared) == declared.casefold():
            height = height_rank(declared)
        elif holder:
            height = eye_rank(scene, holder)
        elif entity.get("portable"):
            height = _HEIGHT_RANK["head"]
        else:
            height = _HEIGHT_RANK["full"]
        shape = normalize_light_shape(entity.get("light_shape"))
        axis = None
        if shape == "cone":
            state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
            axis = _resolve_pointed_at(scene, field, room_id, origin,
                                       state.get("pointed_at"))
            if axis is None:
                facing = None
                if holder:
                    facing = effective_facing(scene, holder)
                if not facing:
                    facing = effective_facing(scene, str(eid)) or (
                        effective_facing(scene, str(entity["name"]))
                        if entity.get("name") else None)
                if facing in _BEARING_DEG:
                    axis = float(_BEARING_DEG[facing])
        out.append({
            "id": str(eid), "label": str(entity.get("name") or eid),
            "room": room_id, "cell": origin, "power": float(power),
            "height": float(height), "shape": shape, "axis": axis,
            "holder": holder, "level": level,
        })
    out.sort(key=lambda s: s["id"])
    return out


# ---------------------------------------------------------------------------
# Casting
# ---------------------------------------------------------------------------

def reach_radius(power: float) -> int:
    """The distance at which a source alone falls below dark: past it the
    source contributes nothing, so nothing is cast."""
    if power <= DARK_THRESHOLD:
        return 0
    return int(math.ceil(math.sqrt(power / DARK_THRESHOLD)))


def _cast(field, origin: tuple, radius: int, source_rank: float,
          memo: Optional[dict] = None) -> set:
    """Every cell of the field a source at `origin` with height
    `source_rank` reaches within `radius`: shadowcast with `blocked` = the
    cell's occluder rank is at or above the source's height (an anchor at
    `floor` height blocks no line, as it blocks no sight line), or the cell
    is outside the field, or the straight ray crosses a wall line outside
    its doorway (`_wall_verdict`)."""
    key = (origin, radius, source_rank)
    if memo is not None and key in memo:
        return memo[key]

    def blocked(x, y):
        if (x, y) not in field.inside:
            # A cell on a wall line is the wall's business, judged on the
            # straight ray below, not a solid the cast stops at -- the same
            # reasoning `_visible_set` gives.
            return not _on_wall_line(field, (x, y))
        h = field.height.get((x, y))
        return h is not None and h > _HEIGHT_RANK["floor"] and h >= source_rank

    reached = set()
    for cell in shadowcast(origin, radius, blocked):
        if cell not in field.inside:
            continue
        if cell != origin and not _wall_verdict(field, origin, cell):
            continue
        reached.add(cell)
    if memo is not None:
        memo[key] = reached
    return reached


def cone_factor(angle: Optional[float], axis: Optional[float]) -> float:
    """1 inside CONE_HALF_ANGLE of the axis, falling linearly to 0 over
    CONE_PENUMBRA beyond it; 1 when there is no axis (all_round) or no
    angle (the source's own cell)."""
    if axis is None or angle is None:
        return 1.0
    gap = _angle_gap(angle, axis)
    if gap <= CONE_HALF_ANGLE:
        return 1.0
    if gap >= CONE_HALF_ANGLE + CONE_PENUMBRA:
        return 0.0
    return 1.0 - (gap - CONE_HALF_ANGLE) / CONE_PENUMBRA


def quantise(intensity: float) -> str:
    if intensity >= BRIGHT_T:
        return "bright"
    if intensity >= LIT_T:
        return "lit"
    if intensity >= DIM_T:
        return "dim"
    return "dark"


# ---------------------------------------------------------------------------
# The field
# ---------------------------------------------------------------------------

class LightField:
    """One room's light, over the composite field that room's observers
    see over: per-cell intensity before and after bounce and floor, the
    per-source contributions (glare reads them), and the sources."""

    def __init__(self, room_id, field):
        self.room_id = room_id
        self.field = field
        self.sources = []
        self.direct = {}        # cell -> summed direct intensity (spill included)
        self.per_source = {}    # source id -> {cell -> intensity}
        self.spill = {}         # cell -> intensity arriving as a floor's spill
        self.spill_from = {}    # giving room id -> {cells of the taking room lit}
        self.bounced = {}       # cell -> intensity added by bounce
        self.floor = {}         # room_id -> ambient floor power
        self.intensity = {}     # cell -> final intensity (bounce + floor)

    def level(self, cell) -> str:
        return quantise(self.intensity.get(cell, 0.0))

    def room_cells(self, room_id) -> list:
        return sorted(c for c, r in self.field.inside.items() if r == room_id)

    def room_median(self, room_id) -> float:
        """The MEDIAN cell intensity of a room -- its typical light, not its
        brightest corner or its darkest (`median_low`, so the answer is a
        cell's own intensity)."""
        values = sorted(self.intensity.get(c, 0.0) for c in self.room_cells(room_id))
        if not values:
            return 0.0
        return values[(len(values) - 1) // 2]

    def room_level(self, room_id) -> str:
        return quantise(self.room_median(room_id))


def _exposure_of(scene, room_id) -> str:
    from world.weather import room_exposure
    exposure = room_exposure(scene, room_id)
    return exposure if exposure in BOUNCE else "enclosed"


def _bounce(scene, lf: LightField, memo: dict, *, enabled=True) -> None:
    """Indirect fill on the SUMMED direct field, once, not per source: each
    pass, every cell above DARK_THRESHOLD re-emits BOUNCE[exposure] of its
    intensity all-round to the cells it reaches within BOUNCE_REACH at
    inverse-square decay; passes repeat until the largest addition falls
    below DARK_THRESHOLD or BOUNCE_PASSES_CAP is hit.

    The re-emission is BOUNCE[exposure] * I IN TOTAL, shared among the
    reached cells in proportion to 1/(1+d^2) -- not that much to EACH cell.
    Read the other way the first prototype returned about six times the
    light that fell (the inverse-square weights over a 3-cell disc sum to
    ~6), a single `lit` lamp made a medium room `bright` to its corners,
    and every pass added more than the last. Sharing the quarter is what
    makes the note's own expectation true: a pass returns at most a quarter
    of what fell, and the second adds under a tenth of the first.

    Indirect light arrives off the ceiling and the walls, so it clears
    anything short of them: a bounce ray is stopped by a `full`-height
    occluder and by a wall, and by nothing lower -- which is what fills the
    corner behind the counter in a lit room. The ambient FLOOR is not in
    the field bounce runs on (it is applied after): a floor casts nothing
    and does not spill, so it must not be re-emitted through a doorway.
    """
    lf.bounced = {}
    if not enabled:
        return
    coef = {rid: BOUNCE[_exposure_of(scene, rid)] for rid in lf.field.offsets}
    current = dict(lf.direct)
    for _pass in range(BOUNCE_PASSES_CAP):
        added = {}
        for cell, intensity in current.items():
            if intensity < DARK_THRESHOLD:
                continue
            emit = coef.get(lf.field.inside.get(cell), BOUNCE["enclosed"]) * intensity
            if emit <= 0.0:
                continue
            weights = {}
            for target in _cast(lf.field, cell, BOUNCE_REACH,
                                _HEIGHT_RANK["full"], memo):
                if target == cell:
                    continue
                d2 = (target[0] - cell[0]) ** 2 + (target[1] - cell[1]) ** 2
                if d2 > BOUNCE_REACH * BOUNCE_REACH:
                    continue
                weights[target] = 1.0 / (1.0 + d2)
            norm = sum(weights.values())
            if norm <= 0.0:
                continue
            for target, weight in weights.items():
                added[target] = added.get(target, 0.0) + emit * weight / norm
        if not added:
            break
        for cell, value in added.items():
            lf.bounced[cell] = lf.bounced.get(cell, 0.0) + value
        if max(added.values()) < DARK_THRESHOLD:
            break
        current = added


def _spill(scene, lf: LightField, memo: dict, *, spill=True) -> None:
    """The ambient floor through the doorways (FLOOR_SPILL, the table beside
    it). For each wall between two placed rooms and each direction across
    it, the GIVING room's floor power times FLOOR_SPILL times the aperture's
    pass is emitted from every aperture cell at `full` height -- shadowed by
    nothing lower than a wall, as a doorway's glow is -- and lands on the
    TAKING room's cells alone at inverse-square from the aperture cell. The
    giving room already has its floor; adding the spill to its own cells
    would lift the cells beside its own door above its floor for no reason
    the world has. Records `lf.spill` (per cell) and `lf.spill_from` (per
    giving room, the taking cells it reached) so the composer can name the
    opening the light comes through."""
    lf.spill = {}
    lf.spill_from = {}
    if not spill or FLOOR_SPILL <= 0.0:
        return
    field = lf.field
    done = set()
    for wall in field.walls:
        other = wall["to"]
        if other not in field.offsets:
            continue
        for giver, taker in ((lf.room_id, other), (other, lf.room_id)):
            power = (FLOOR_SPILL * POWER.get(ambient_floor_word(scene, giver), 0.0)
                     * float(wall.get("pass", 1.0)))
            if power <= 0.0:
                continue
            radius = reach_radius(power)
            if radius <= 0:
                continue
            reached = lf.spill_from.setdefault(giver, set())
            for ap in wall_aperture_cells(wall):
                # A diagonal doorway is a gap in two wall lines that meet at
                # one band cell; that cell emits once.
                if (giver, ap) in done:
                    continue
                done.add((giver, ap))
                for cell in _cast(field, ap, radius, _HEIGHT_RANK["full"], memo):
                    if field.inside.get(cell) != taker:
                        continue
                    d2 = (cell[0] - ap[0]) ** 2 + (cell[1] - ap[1]) ** 2
                    intensity = power / (1.0 + d2)
                    lf.spill[cell] = lf.spill.get(cell, 0.0) + intensity
                    lf.direct[cell] = lf.direct.get(cell, 0.0) + intensity
                    reached.add(cell)


def compute_light_field(scene: dict, room_id, *, beat=None,
                        bounce=True, spill=True) -> Optional[LightField]:
    """The light field over `room_id`'s composite field, uncached. None
    when the room has no geometry to compute over (§ 7: fail-open)."""
    if not light_geometry_exists(scene, room_id):
        return None
    field = room_field(scene, room_id, through=light_passes)
    if field is None:
        return None
    if beat is None:
        beat = beat_index(scene)
    lf = LightField(room_id, field)
    memo = {}
    lf.sources = light_sources(scene, field, beat)
    # 1-5. Power, reach, decay, shape, sum.
    for src in lf.sources:
        radius = reach_radius(src["power"])
        contrib = {}
        for cell in _cast(field, src["cell"], radius, src["height"], memo):
            d2 = (cell[0] - src["cell"][0]) ** 2 + (cell[1] - src["cell"][1]) ** 2
            intensity = src["power"] / (1.0 + d2)
            if src["axis"] is not None:
                intensity *= cone_factor(_angle_deg(src["cell"], cell), src["axis"])
            if intensity <= 0.0:
                continue
            contrib[cell] = intensity
            lf.direct[cell] = lf.direct.get(cell, 0.0) + intensity
        lf.per_source[src["id"]] = contrib
    # 6a. The ambient floor's SPILL through every aperture (FLOOR_SPILL): the
    # giving room's floor, emitted from the aperture cells at `full` height
    # into the taking room's cells only, summed like any other direct light
    # so bounce fills behind the doorframe as it does behind a counter.
    _spill(scene, lf, memo, spill=spill)
    # 7. Bounce, on the summed direct field.
    _bounce(scene, lf, memo, enabled=bounce)
    # 6. Ambient floor -- a FLOOR, never a source: applied to the room's
    # own cells only, after bounce, so it casts nothing and spills nowhere.
    for rid in field.offsets:
        lf.floor[rid] = POWER.get(ambient_floor_word(scene, rid), 0.0)
    for cell, rid in field.inside.items():
        total = lf.direct.get(cell, 0.0) + lf.bounced.get(cell, 0.0)
        lf.intensity[cell] = max(total, lf.floor.get(rid, 0.0))
    return lf


# The field is computed once per (scene inputs, room) and reused across
# every reader in the turn -- `light_at` runs once per body per observer
# pair. Keyed on everything the derivation reads, so the memo cannot go
# stale; bounded the way `_ANCHOR_CACHE` is.
_FIELD_CACHE: dict = {}
_FIELD_CACHE_MAX = 64


def _cache_key(scene: dict, room_id) -> str:
    sc = scene or {}
    sources = {}
    for eid, ent in (sc.get("entities") or {}).items():
        if isinstance(ent, dict) and ent.get("light_source"):
            sources[str(eid)] = ent
    return json.dumps([
        str(room_id), sc.get("rooms"), sources, sc.get("positions"),
        sc.get("stations"), sc.get("orientation"), sc.get("poses"),
        sc.get("contacts"), sc.get("contained"), sc.get("crossings"),
        sc.get("day_phase"), sc.get("weather"), sc.get(BEAT_KEY),
    ], sort_keys=True, default=str)


def light_field(scene: dict, room_id) -> Optional[LightField]:
    """The cached light field over `room_id`, or None when the room has no
    geometry. Every reader below goes through this."""
    if not light_geometry_exists(scene, room_id):
        return None
    key = _cache_key(scene, room_id)
    cached = _FIELD_CACHE.get(key)
    if cached is not None:
        return cached
    lf = compute_light_field(scene, room_id)
    if lf is None:
        return None
    if len(_FIELD_CACHE) >= _FIELD_CACHE_MAX:
        _FIELD_CACHE.clear()
    _FIELD_CACHE[key] = lf
    return lf


def observer_light_field(scene: dict, observer: str) -> Optional[LightField]:
    """The field over the observer's own room -- the composite their sight
    runs over (`observer_field`)."""
    room_id = room_of(scene, observer)
    return light_field(scene, room_id) if room_id else None


# ---------------------------------------------------------------------------
# Readers (§ 4b). Each answers None when the field does not exist for the
# question, and the room-level function in `spatial_light` keeps its answer.
# ---------------------------------------------------------------------------

def field_light_at(scene: dict, name: str) -> Optional[str]:
    """The quantised level of the body's cell in its own field, or None
    when the body's room has no geometry.

    A BODY WITHOUT A CELL READS THE ROOM'S MEDIAN (2026-09-04). It used to
    keep the room-level `light_at` answer, which reads `light_radius` and
    proximity and knows nothing of the grid -- so one room had two answers:
    chat 115's 'Sublevel Four Shelter Approach' (declared dim, one `lit`
    fixture at its centre, every body unstationed) read `dim` as a room
    (`effective_light`, the field's median) while every body in it read
    `lit` (room-level, the fixture filling the room). A body with no station
    is somewhere in the room, and the room's typical light is the one
    statistic the field already answers for 'somewhere'. Same class as an
    unstationed SOURCE standing at the room's centre: the field's own
    approximation, not the room-level model's."""
    room_id = room_of(scene, name)
    if not room_id or not light_geometry_exists(scene, room_id):
        return None
    lf = light_field(scene, room_id)
    if lf is None:
        return None
    cell = body_cell(scene, name)
    if cell is None:
        return lf.room_level(room_id)
    return lf.level(lf.field.cell_of(room_id, cell))


def field_effective_light(scene: dict, room_id) -> Optional[str]:
    """The level of the room's MEDIAN cell intensity, so a room reads as
    its typical light and one candle does not make it `lit`. None when
    the room has no geometry."""
    lf = light_field(scene, room_id)
    if lf is None:
        return None
    return lf.room_level(room_id)


def glare_between(scene: dict, observer: str, target: str) -> bool:
    """Is the observer's sight of the target capped by GLARE: a source of
    power >= GLARE_POWER, lighting the observer's cell, inside the
    observer's front cone at <= GLARE_CELLS cells, with the target on the
    far side of it -- the source's cell lies on the straight line to the
    target, or IS the target's cell (the target holds it).

    Needs the observer's facing and both cells; without them there is no
    evidence and the answer is False, the wider answer.
    """
    o_room = room_of(scene, observer)
    t_room = room_of(scene, target)
    if not o_room or not t_room or not light_geometry_exists(scene, o_room):
        return False
    facing = effective_facing(scene, observer)
    if facing not in _BEARING_DEG:
        return False
    lf = light_field(scene, o_room)
    if lf is None or t_room not in lf.field.offsets:
        return False
    o_cell = body_cell(scene, observer)
    t_cell = body_cell(scene, target)
    if o_cell is None or t_cell is None:
        return False
    origin = lf.field.cell_of(o_room, o_cell)
    goal = lf.field.cell_of(t_room, t_cell)
    if origin == goal:
        return False
    between = set(_line(origin, goal)) | {goal}
    for src in lf.sources:
        if src["power"] < GLARE_POWER or src["cell"] == origin:
            continue
        if src["cell"] not in between:
            continue
        d = math.hypot(src["cell"][0] - origin[0], src["cell"][1] - origin[1])
        if d > GLARE_CELLS:
            continue
        angle = _angle_deg(origin, src["cell"])
        if angle is None:
            continue
        sector = relative_bearing(facing, _bearing_word(angle))
        if sector not in _FRONT_SECTORS:
            continue
        # The light has to be in the observer's eyes: a cone pointed away,
        # or a source the counter shadows the observer from, dazzles nobody.
        if lf.per_source.get(src["id"], {}).get(origin, 0.0) <= 0.0:
            continue
        return True
    return False


def _bearing_word(angle: float) -> str:
    from world.spatial_orientation import _BEARINGS
    return _BEARINGS[int(round(angle / 45.0)) % 8]


# ---------------------------------------------------------------------------
# The shape of the light, for the composer (§ 4b, last bullet)
# ---------------------------------------------------------------------------

def light_shape(scene: dict, observer: str, *, sweep=False) -> Optional[dict]:
    """Where the light falls, as the composer's closed-vocabulary input, or
    None when there is nothing to add. The owner's five rules (2026-09-04),
    shared word for word with `spatial_sound_field.sound_shape`:

      a. speak only when the room is UNEVEN -- the observer's own room's
         cells do not all quantise to one word. Even, None, and the
         composer's flat sentence stands byte-identically.
      b. grade by ANCHOR, not by cell -- the VISIBLE anchors of the room
         (`feature_visibility`: cone and line already subtracted) grouped by
         the level at each anchor's nearest cell (the mapping
         `neighbour_feature_visibility` uses), bright to dark. Four words,
         no number, no cell, no sector name leaves this function.
      c. name the source only when it is IN VIEW -- a source in this room
         the observer's eyes reach (the cone's rear arc and the line of
         occluders subtract exactly as they do for furniture); light from a
         placed neighbour, whether a source there or the neighbour's floor
         spilling, is named by the OPENING it comes through when that
         opening is in view; anything else is not mentioned.
      d. say where the observer stands in it -- the level at their own
         measured cell; no cell, no claim.
      e. subtract, never add -- every item is an anchor description the
         eyes already reach or the label of a source they already see.

    Returns {"groups": [{"level": word, "items": [desc, ...]}, ...],
             "sources": [label, ...], "openings": [desc, ...],
             "self": word | None}.
    """
    room_id = room_of(scene, observer)
    if not room_id:
        return None
    lf = light_field(scene, room_id)
    if lf is None:
        return None
    cells = lf.room_cells(room_id)
    if not cells or len({lf.level(c) for c in cells}) <= 1:
        return None                         # rule (a): even; the flat sentence stands
    field = lf.field
    origin, how = _observer_cell(scene, observer)
    facing = None if sweep else effective_facing(scene, observer)
    eye = eye_rank(scene, observer)
    rows = feature_visibility(scene, observer, sweep=bool(sweep))
    placed = field.anchors.get(room_id) or {}
    groups = {}
    visible_doors = set()
    for row in rows:
        if not row.get("visible"):
            continue
        if row.get("implicit"):
            visible_doors.add(row["anchor"])
            continue
        rec = placed.get(row["anchor"]) or {}
        anchor_cells = rec.get("cells") or ()
        if not anchor_cells:
            continue
        target = min(anchor_cells, key=lambda c: (c[0] - origin[0]) ** 2
                     + (c[1] - origin[1]) ** 2)
        groups.setdefault(lf.level(target), []).append(row["desc"])
    # Rule (c): sources in view, else the opening their light comes through.
    sources = []
    openings = []
    seen_cache = {}

    def in_view(cell, top):
        if how == "measured":
            key = top
            if key not in seen_cache:
                seen_cache[key] = _visible_set(field, origin, eye, top)
            if cell not in seen_cache[key]:
                return False
        if facing:
            dist = math.hypot(cell[0] - origin[0], cell[1] - origin[1])
            if _sector_verdict(_cone_sector(facing, origin, cell)) == "rear" \
                    and dist > 1.5:
                return False
        return _wall_verdict(field, origin, cell)

    for src in lf.sources:
        if src["room"] == room_id:
            if src["cell"] != origin and not in_view(src["cell"], src["height"]):
                continue
            if src["label"] not in sources:
                sources.append(src["label"])
            continue
        # Beyond a doorway: named by the opening, when the opening is seen
        # and the light actually reaches this room.
        if not any(field.inside.get(c) == room_id and v > 0.0
                   for c, v in lf.per_source.get(src["id"], {}).items()):
            continue
        door = door_anchor_id(src["room"])
        if door in visible_doors:
            desc = str((placed.get(door) or {}).get("desc") or "").strip()
            if desc and desc not in openings:
                openings.append(desc)
    for giver, reached in lf.spill_from.items():
        if giver == room_id or not any(field.inside.get(c) == room_id
                                       for c in reached):
            continue
        door = door_anchor_id(giver)
        if door in visible_doors:
            desc = str((placed.get(door) or {}).get("desc") or "").strip()
            if desc and desc not in openings:
                openings.append(desc)
    ordered = [{"level": word, "items": groups[word]}
               for word in reversed(LIGHT_LEVELS) if groups.get(word)]
    self_word = lf.level(origin) if how == "measured" else None
    if not ordered and self_word is None:
        return None
    return {"groups": ordered, "sources": sources, "openings": openings,
            "self": self_word}


# ---------------------------------------------------------------------------
# What the field looks like, for tests and the measurement scripts
# ---------------------------------------------------------------------------

def field_rows(lf: LightField, room_id, *, what="level") -> list:
    """The room's grid as rows of words (or intensities), north at the top,
    for a test to read against a drawing."""
    if lf is None:
        return []
    ox, oy = lf.field.offsets.get(room_id, (0, 0))
    cells = lf.room_cells(room_id)
    if not cells:
        return []
    xs = sorted({c[0] for c in cells})
    ys = sorted({c[1] for c in cells})
    rows = []
    for y in ys:
        row = []
        for x in xs:
            if what == "level":
                row.append(lf.level((x, y)))
            else:
                row.append(round(lf.intensity.get((x, y), 0.0), 2))
        rows.append(row)
    return rows
