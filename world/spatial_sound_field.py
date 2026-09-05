# spatial_sound_field.py
"""Loudness as a quantity on the sight grid: the sound field.

`docs/design/DESIGN_SOUND_FIELD.md`, built 2026-09-04 as a sibling of
`world/spatial_fov.py` behind the `world/spatial.py` facade. Derived, never
stored, no model anywhere.

The rule in one sentence: sound is a scalar on every cell of a listener's
field, spread from each source along the SHORTEST ACOUSTIC PATH -- cell to
cell, through apertures in the wall lines with a drop per barrier, never
through the wall itself, round whatever stands inside a room at the cost of
the extra path -- decayed by path length, summed into a SIGNAL for the source
being listened to and a NOISE for everything else plus the room's ambient,
and quantised to the existing `none | fragment | full` ladder LAST, so every
reader keeps its three words and gets them from geometry instead of from the
edge.

This is a FLOOD, not a raycast, and that is the whole difference from light:
a voice round a corner through an open door arrives at reduced level, a
voice behind a counter arrives at the level of the path round the counter,
and a straight-line model would have made the first silent and the second
inaudible. So the spread is Dijkstra over cells, and it is exact for the
quantity we want: a path on one composite field crosses at most one wall (the
neighbours are placed beyond the observer's own walls and never touch each
other), so the gain `pass / (1 + L^2)` is maximised by minimising `L` through
that wall's aperture.

THE FIELD MAY ONLY EXIST ON EVIDENCE. It exists for a pair only when the
listener's room carries geometry (`room_has_geometry`, the same opt-in the
sight layer uses -- an anchor with a footprint, a height or an opacity), the
listener and the source both resolve to a cell on the listener's composite
field, and no containment relation stands between them (a voice inside a
body is conducted through a mass the grid has no cell for; those cases keep
`hear_level`'s present answers). Everywhere else `spatial_rel_between` stamps
nothing and every reader falls back to today's functions byte-identically --
the `observer_field` precedent, pinned in `tests/test_sound_field.py`.

Measured before this was written (2026-09-04, 104 live scene rows, 589
rooms, read-only): 2 rooms carry anchor geometry, in one scene; 1 of them is
occupied, by 2 bodies, one of whom has spoken. 10,093 spoken lines across 91
chats: normal 84.8%, mutter 11.0%, loud 2.0%, whisper 1.8%, shout 0.4%. So
the field bites on almost nothing in the existing corpus and everything the
spatial hand writes geometry for from here.
"""

from __future__ import annotations

import hashlib
import heapq
import json
from typing import Optional

from world.spatial_barriers import normalize_barrier
from world.spatial_containment import container_of
from world.spatial_fov import (
    _Field,
    _HEIGHT_RANK,
    _centre,
    _door_cells,
    _observer_cell,
    _wall_verdict,
    body_cell,
    feature_visibility,
    grid_side,
    room_field,
    room_has_geometry,
)
from world.spatial_geometry import door_anchor_id
from world.spatial_identity import _ci_get, room_of
from world.spatial_light_field import (
    _beat_hash, FAIL_RATE, FLICKER_RATE, normalize_steadiness, STEADINESS)
from world.spatial_senses import _material_shifted_barrier, _SOUND_WALK_BARRIERS


# ---------------------------------------------------------------------------
# The closed vocabularies
# ---------------------------------------------------------------------------

#: What a thing emits when running. A schema the engine owns, not a device
#: vocabulary: nothing here names a generator, a waterfall, a radio or a
#: crowd -- the objects hand's clause states the class and the thing's name
#: and description say what it is.
SOUND_LEVELS = ("faint", "audible", "loud", "deafening")

#: Whether a source can be relied on: `STEADINESS`, `normalize_steadiness`,
#: `FLICKER_RATE`, `FAIL_RATE` and the beat hash are the LIGHT field's,
#: imported above rather than defined twice (unified at the 2026-09-04
#: merge): a generator that cuts out is the same class as a lamp that goes
#: out, and when they are one entity they fail on the same beat -- one hash,
#: two senses (`DESIGN_SOUND_FIELD.md` § 5).

#: The speech volumes the social hand writes on a spoken line
#: (`schemas.SpeechVolume`). Read here, declared there.
SPEECH_VOLUMES = ("mutter", "whisper", "normal", "loud", "shout")


# ---------------------------------------------------------------------------
# Constants the OWNER sets (DESIGN_SOUND_FIELD.md § 6). Every one is named,
# owner-visible, and carries the table beside it. The § 6 proposal is
# recorded where a value differs from it, with the measured reason.
# ---------------------------------------------------------------------------

#: Power of a speaking body at its own cell, by the line's volume word.
#:
#:   § 6 proposed   mutter 1 | whisper 1.5 | normal 6 | loud 14 | shout 30
#:   set here       mutter 0.6 | whisper 1 | normal 12 | loud 40 | shout 120
#:
#: Why the proposal was not kept: measured against § 6's OWN sentences with
#: inverse-square decay, a 4:1 normal-to-whisper ratio cannot both carry a
#: normal voice across a medium room as `full` (path 7 corner to corner ->
#: 6/50 = 0.12) and fade a whisper to a fragment at three cells (1.5/10 =
#: 0.15 sits ABOVE it). The sentences need the ratio a real voice has -- a
#: whisper is tens of decibels under conversation, not a quarter of it -- so
#: the ladder is widened and the § 9.3 table in the note is computed on these.
SPEECH_POWER = {"mutter": 0.6, "whisper": 1.0, "normal": 12.0,
                "loud": 40.0, "shout": 120.0}

#: Power of a running entity at its own cell, by `sound_source`. Tied to the
#: speech ladder rung for rung -- `audible` IS a normal voice, `loud` IS a
#: loud one -- so "a loud generator masks a normal voice" means exactly what
#: it says in numbers.
#:
#:   § 6 proposed   faint 2 | audible 6 | loud 14 | deafening 40
#:   set here       faint 1 | audible 12 | loud 40 | deafening 150
SOUND_POWER = {"faint": 1.0, "audible": 12.0, "loud": 40.0,
               "deafening": 150.0}

#: What crosses an aperture, by the barrier's class AFTER its material shift
#: (`_material_shifted_barrier`, so a paper screen and a vault door differ
#: exactly as they already do for the edge rules). A wall passes nothing and
#: is never an aperture; `separated` and `unknown` are not on a placed field
#: at all. Kept as § 6 proposed.
#:
#:   open 1.0 | open_door 0.9 | bars 0.9 | membrane 0.5 | closed_door 0.25 |
#:   window 0.1 | one_way_window 0.1 | wall 0
APERTURE_PASS = {"open": 1.0, "open_door": 0.9, "bars": 0.9,
                 "membrane": 0.5, "closed_door": 0.25, "window": 0.1,
                 "one_way_window": 0.1, "wall": 0.0}

#: Path cost of a diagonal step; a side step costs 1. Kept as § 6 proposed.
DIAGONAL_COST = 1.4

#: What a NON-PARTITION occluder costs the sound that crosses its cell -- a
#: counter, a table, a sofa back, a shelf: things a voice goes over rather
#: than round. NOT in § 6, which had no such term because the flood went
#: round everything from the waist up; it is the number the PE1 repair
#: needed, and it is the owner's like every other constant here.
#:
#:   set here   0.9 per occupied cell crossed
#:
#: Chosen against the case that found the defect: a counter run and a table
#: between two bodies four paces apart in a quiet enclosed room leave a
#: normal voice `full` (0.9^2 * 12 / 17 = 0.57, against the 0.10 `full`
#: asks there), while a line of three such things costs about a quarter of
#: the signal. Near 1 for a second reason: the flood minimises PATH LENGTH,
#: so a factor much below 1 would make the shortest path the wrong answer
#: (a detour round the counter can carry more than a crossing through it),
#: and the Dijkstra would have to optimise the gain itself.
OCCLUDER_PASS = 0.9

#: The noise floor every cell of a room carries, by the room's exposure
#: (`weather.room_exposure`); the weather's audible level is added on top
#: (WEATHER_NOISE / WIND_NOISE). The floor is NOISE, never a source: it masks
#: and does not spread.
#:
#:   § 6 proposed   enclosed 0.3 | sheltered 0.6 | open 1.0
#:   set here       enclosed 0.05 | sheltered 0.1 | open 0.2
#:
#: With FULL_SNR 2 the proposal put `full` at 0.6 in a quiet room, where a
#: normal voice at § 6's power is 0.23 five cells away -- `none`, below even
#: the floor. Two people at opposite walls of a medium room could not have
#: heard each other. The floor is set so a quiet enclosed room asks 0.1 for
#: `full`, which a normal voice clears to ten paces and a whisper to two.
AMBIENT = {"enclosed": 0.05, "sheltered": 0.1, "open": 0.2}

#: The weather as noise: precipitation the room can hear
#: (`weather_for_room(...)["audible"]`, scaled by its `gain` -- muffled rain
#: through a wall is quieter than rain on you), by the sky's intensity word,
#: and wind that reaches the room by its wind word. NOT in § 6, which said
#: only "(+ weather)"; these are the two numbers that sentence needed.
WEATHER_NOISE = {"light": 0.3, "moderate": 0.6, "heavy": 1.0}
WIND_NOISE = {"wind": 0.3, "gale": 1.0}

#: A crowd's level by its BAND -- the count vocabulary `world/crowds.py`
#: owns. § 3 asked for `audible` when open and `loud` when the crowd's `mood`
#: is a raised one; `mood` is free prose (24 characters, any words), and
#: reading it for loudness would be exactly the word list CLAUDE.md forbids,
#: failing in whichever direction its missing word points. The band is a
#: closed set the engine already grades density by, so a throng is loud and
#: a handful is faint without anyone enumerating English. Whether mood should
#: ALSO raise the level is the note's open question, unchanged.
CROWD_SOUND = {"a handful": "faint", "a dozen or so": "audible",
               "a few dozen": "audible", "a throng": "loud"}

#: The absolute floor under `fragment`: a signal quieter than this is not
#: heard however quiet the room. § 6 proposed 0.3, which sat above a normal
#: voice at five cells; set with AMBIENT so a whisper's fragment survives to
#: four cells and dies at five.
HEAR_FLOOR = 0.05
#: `full` when signal >= FULL_SNR * noise. Kept as § 6 proposed.
FULL_SNR = 2.0
#: `fragment` when signal >= FRAGMENT_SNR * noise (and >= HEAR_FLOOR). Kept.
FRAGMENT_SNR = 0.8

#: THE NOISE LADDER the composer speaks (2026-09-04, the owner's rule b: the
#: sentence grades by a closed set, never a number). Three words for what
#: the noise at a cell does to a NORMAL VOICE ONE PACE OFF -- the yardstick
#: a body has for a room's loudness, "could I hear someone beside me" --
#: derived from the two SNR thresholds above, not set beside them:
#:
#:   quiet    a normal voice one pace off is `full`      noise <= 6.0 / FULL_SNR     (3.0)
#:   din      ... is a `fragment`                        noise <= 6.0 / FRAGMENT_SNR (7.5)
#:   drowned  ... is `none`                              above that
#:
#: where 6.0 is SPEECH_POWER["normal"] at a path of one cell, 12 / (1 + 1).
#: Move FULL_SNR or FRAGMENT_SNR and the words move with them.
NOISE_WORDS = ("quiet", "din", "drowned")
VOICE_ONE_PACE = SPEECH_POWER["normal"] / 2.0


def noise_word(noise: float) -> str:
    """One of NOISE_WORDS for a noise floor, by what it does to a normal
    voice one pace off."""
    noise = float(noise or 0.0)
    if VOICE_ONE_PACE >= FULL_SNR * noise:
        return "quiet"
    if VOICE_ONE_PACE >= FRAGMENT_SNR * noise:
        return "din"
    return "drowned"

#: Steadiness rates: see the light field's FLICKER_RATE / FAIL_RATE, imported
#: above -- one hash, two senses, one pair of rates.

#: SOUND IS STOPPED ONLY BY WHAT REACHES THE CEILING. An occluder at or
#: above this rank is a PARTITION -- it parts the room acoustically and the
#: flood goes round its cell. Everything lower is furniture: sound goes over
#: and around it, losing `OCCLUDER_PASS` for the crossing and no path length
#: at all.
#:
#: This was `_HEIGHT_RANK["waist"]` until 2026-09-05, which made a counter a
#: wall. Measured live: an 8x6 kitchen with a waist counter along one wall
#: and a waist table beside it, two bodies four paces apart in it, a normal
#: voice -- signal 0.0067 against noise 0.32, `none`, because the flood had
#: to walk 12 cells round the end of the counter for a four-cell straight
#: line. Neither of the two people standing in the room received either the
#: lie or its correction, and nothing anywhere warned that a line had
#: reached nobody (`PLAY_2026_09_05_flat.md` § PE1).
#:
#: The LIGHT field is not the same mistake and is deliberately left alone: a
#: light ray is cast, not flooded, so a head-high shelf must shadow a
#: waist-high candle and must not shadow a ceiling fixture -- `_cast`'s
#: `blocked` compares the occluder against the SOURCE's height, which is the
#: right rule for a line and the wrong one for a flood.
_PARTITION_RANK = _HEIGHT_RANK["full"]

#: Occluder ranks at or above this are what the flood pays `OCCLUDER_PASS`
#: to cross: a counter, a table, a sofa back, a head-high shelf.
#: Floor-height things (a rug, a hearth on the wall line) cost nothing.
_ROUND_RANK = _HEIGHT_RANK["waist"]

#: `state.running` values that mean the thing is switched off. The same set
#: `spatial_light` reads for `state.lit`, plus the words a machine stops with.
_OFF = (False, 0, "off", "false", "no", "stopped", "silent", "dead")

#: How many composite fields to remember. One perception stage asks for the
#: same (scene, listener) field once per source; the derivation is pure, so a
#: cache keyed on everything it reads cannot go stale.
_SOUND_FIELD_CACHE: dict = {}
_FIELD_CACHE_MAX = 64


# ---------------------------------------------------------------------------
# Vocabulary readers
# ---------------------------------------------------------------------------

def normalize_sound_level(value) -> Optional[str]:
    v = str(value or "").strip().casefold()
    return v if v in SOUND_LEVELS else None


def _running(entity) -> bool:
    state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
    running = state.get("running", True)
    if isinstance(running, str):
        running = running.strip().casefold()
    return running not in _OFF


def steadiness_this_beat(steadiness, turn_idx, source_id) -> str:
    """`steady` | `dropped` | `out` for one source on one beat.

    `steady` sources are always steady. A `flickering` source is `dropped`
    (one level quieter) when the beat hash lands on FLICKER_RATE; a `failing`
    source is `out` (silent, and a notice is filed) when it lands on
    FAIL_RATE, and `dropped` on the flicker beats between. No turn index --
    a reader outside a turn -- is a steady beat: the field may only subtract
    on evidence it has.
    """
    kind = normalize_steadiness(steadiness)
    if kind == "steady" or turn_idx is None:
        return "steady"
    h = _beat_hash(turn_idx, source_id)
    if kind == "failing" and h % FAIL_RATE == 0:
        return "out"
    if h % FLICKER_RATE == 0:
        return "dropped"
    return "steady"


def _power_of_level(level, beat) -> float:
    if beat == "out":
        return 0.0
    if beat == "dropped":
        # A DROP IS A SOURCE WAVERING, NOT A SOURCE STOPPING, and it never
        # reaches past the quietest sound the thing can still make: going
        # silent is what `failing` means, and that files a notice the
        # Director answers (§ 5) where a flicker files nothing. The light
        # field's `_one_level_down` is the same clamp on the same ladder --
        # a `faint` generator dropping to no sound at all was the light
        # field's snuffed candle in the other sense
        # (`PLAY_2026_09_05_manor.md` § PC4).
        level = SOUND_LEVELS[max(0, SOUND_LEVELS.index(level) - 1)]
    return SOUND_POWER[level]


def sound_field_hear_level(volume, signal_gain, noise) -> str:
    """Quantise, LAST (§ 4.5): `full` at FULL_SNR, `fragment` at
    FRAGMENT_SNR and above HEAR_FLOOR, else `none`. `signal_gain` is the
    fraction of the speaker's power arriving at the listener's cell (what
    `spatial_rel_between` stamps as `rel["signal"]`); the volume word turns
    it into a signal here, because the relation is built before the line is
    read."""
    volume = str(volume or "normal").strip().casefold()
    power = SPEECH_POWER.get(volume, SPEECH_POWER["normal"])
    return quantise_hearing(power * float(signal_gain or 0.0), float(noise or 0.0))


#: The volumes a voice is RAISED at -- the two the bounded loudness walk
#: already treats as carrying past the room they are made in
#: (`spatial_senses.sound_walk_level`). Read here, declared there.
RAISED_VOLUMES = ("loud", "shout")


def one_opening_away(scene: dict, a_room, b_room) -> bool:
    """Are these two rooms joined by ONE passable opening -- an edge sound
    walks through (`_SOUND_WALK_BARRIERS`, after the material shift, so a
    paper door is the opening it acoustically is)?

    Undirected, because a doorway is one object and may be declared from
    either side: an edge from either room counts. That is also what keeps
    the floor below reciprocal.
    """
    from world.spatial_barriers import effective_adjacent
    a_room, b_room = str(a_room or ""), str(b_room or "")
    if not a_room or not b_room or a_room == b_room:
        return False
    for here, there in ((a_room, b_room), (b_room, a_room)):
        for edge in effective_adjacent(scene, here) or ():
            if not isinstance(edge, dict) or str(edge.get("to") or "") != there:
                continue
            shifted = _material_shifted_barrier(
                normalize_barrier(edge.get("barrier")), edge.get("material"))
            if shifted in _SOUND_WALK_BARRIERS:
                return True
    return False


def open_edge_floor(volume, rel: dict) -> Optional[str]:
    """`fragment` where a RAISED VOICE CARRIES THROUGH AN OPENING, else None.

    One passable edge away, a loud voice or a shout is at worst a fragment.
    The edge model always said so -- `open`/`open_door`/`bars` deliver a
    shout `full` -- and the field, which knows the path and the noise, can
    say `none` for the same shout across the same archway once the walk is
    long enough. That is a real loss of REACH rather than a stricter
    hearing model: when both perception passes came to read the field
    (2026-09-05, § PC3), a shout across one open archway could reach nobody
    at all. The floor is the half of that repair the field owes.

    Capped by the masking rule everything else is capped by (§ PA5): where
    the noise at the listener's own cell would refuse the same voice ONE
    PACE OFF, nothing from the next room survives either -- an opening
    carries a voice into a room, not through the bell ringing in it. The
    yardstick is the one `NOISE_WORDS` already uses, `P / 2` at a path of
    one cell.
    """
    if not isinstance(rel, dict) or not rel.get("open_edge"):
        return None
    volume = str(volume or "").strip().casefold()
    if volume not in RAISED_VOLUMES:
        return None
    noise = rel.get("noise")
    if noise is not None and quantise_hearing(
            SPEECH_POWER[volume] / 2.0, float(noise)) == "none":
        return None
    return "fragment"


def quantise_hearing(signal: float, noise: float) -> str:
    if noise <= 0:
        return "full" if signal >= HEAR_FLOOR else "none"
    if signal >= FULL_SNR * noise:
        return "full"
    if signal >= FRAGMENT_SNR * noise and signal >= HEAR_FLOOR:
        return "fragment"
    return "none"


# ---------------------------------------------------------------------------
# The composite grid a sound runs over
# ---------------------------------------------------------------------------

def _aperture_pass(scene, room_id, edge) -> float:
    barrier = normalize_barrier(edge.get("barrier"))
    shifted = _material_shifted_barrier(barrier, edge.get("material"))
    return float(APERTURE_PASS.get(shifted, 0.0))


def sound_passes(scene, room_id, edge):
    """The sound field's placement predicate for `spatial_fov.room_field`:
    the aperture's pass for any barrier that is not a wall -- an open
    doorway, a curtain, a shut door, a window, a grille -- and None for a
    wall, which is never an aperture. Sight places what a body walks into;
    sound places whatever a wall lets through. ONE grid derivation serves
    both since 2026-09-04: `_acoustic_grid` was a second copy of the
    placement loop, and it still laid rooms out as tier squares after the
    room-shapes work had taught `room_field` about L and round rooms."""
    factor = _aperture_pass(scene, room_id, edge)
    return factor if factor > 0 else None


def acoustic_grid(scene, room_id) -> Optional[_Field]:
    """The listener's composite for sound: `room_field` under
    `sound_passes`, every wall record carrying its aperture's `pass`."""
    if not room_id:
        return None
    return room_field(scene, room_id, through=sound_passes)


def _crossing_pass(field, a, b) -> float:
    """The product of the aperture factors of every wall the straight step
    from `a` to `b` crosses through its aperture; 0 when it strikes a wall
    outside one, or crosses no wall at all (two cells in different rooms
    with nothing declared between them are not neighbours)."""
    if not _wall_verdict(field, a, b):
        return 0.0
    factor = 0.0
    for wall in field.walls:
        axis = wall["axis"]
        o, t = a[axis], b[axis]
        c = wall["coord"]
        if (o - c) * (t - c) >= 0:
            continue
        k = (c - o) / float(t - o)
        along = a[1 - axis] + k * (b[1 - axis] - a[1 - axis])
        if not (wall["extent"][0] <= along <= wall["extent"][1]):
            continue
        factor = wall["pass"] if factor == 0.0 else factor * wall["pass"]
    return factor


#: Two ways round a table are the SAME length, and a float sum does not
#: always say so: 1 + 1 + 1.4 + 1.4 and 1.4 + 1.4 + 1 + 1 differ in the last
#: bit, and a strict comparison then keeps whichever path the heap happened
#: to reach first -- which is not the same path from the two ends, and made
#: the gain between one pair differ by exactly one OCCLUDER_PASS depending
#: on who was asking. Path lengths are compared to this tolerance so that
#: "same length, louder way" is decidable. It is arithmetic, not a constant
#: the owner sets.
_LENGTH_EPS = 1e-9

_STEPS = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
          (1, 1, DIAGONAL_COST), (1, -1, DIAGONAL_COST),
          (-1, 1, DIAGONAL_COST), (-1, -1, DIAGONAL_COST))


def spread(field: _Field, origin) -> dict:
    """{cell: (path length, pass)} for every cell the flood reaches from
    `origin`: Dijkstra over the field's cells. A side step costs 1, a
    diagonal DIAGONAL_COST.

    SOUND GOES OVER AND AROUND WHAT IS NOT A PARTITION. A cell holding an
    occluder that reaches the ceiling (`_PARTITION_RANK`) is REACHED but
    never passed through -- the flood steps onto the partition's cell and
    goes round it, so a body standing at it hears and the cells behind it
    are reached by the path round the end. (Until 2026-09-04 such a cell was
    not entered at all, and a listener whose station resolved onto another
    anchor's cell -- a body at the hearth where the seeded shelf also landed
    -- heard NOTHING at any volume: signal 0, a shout beside them `none`.)
    Anything lower is furniture: the flood crosses its cell for
    OCCLUDER_PASS and no extra path at all, because a counter between two
    people costs a conversation a little of its edge and not its existence.
    Until 2026-09-05 the round-it rule ran from the WAIST up, and an
    ordinary kitchen counter parted a room as a wall does (§ PE1, the
    constant's own note). A step into another room
    leaps the wall band -- the wall is a line of no thickness -- and is
    allowed only where `_wall_verdict` puts the segment inside an aperture,
    carrying that aperture's `pass`. Deterministic: a tie breaks on the
    cell."""
    inside = field.inside
    if origin not in inside:
        return {}
    heights = field.height

    def furniture(cell) -> float:
        """OCCLUDER_PASS for a cell holding something short of a partition,
        1.0 otherwise. EVERY such cell on the path counts, both ends
        included -- a path pays for what it stands in as well as for what it
        crosses -- because a path has no direction and a factor charged only
        on arrival would make the two ends of one path disagree."""
        return (OCCLUDER_PASS
                if _ROUND_RANK <= heights.get(cell, -1.0) < _PARTITION_RANK
                else 1.0)

    start = furniture(origin)
    best = {origin: (0.0, start)}
    heap = [(0.0, origin, start)]
    while heap:
        dist, cell, factor = heapq.heappop(heap)
        known = best.get(cell)
        if known is not None and (known[0] < dist - _LENGTH_EPS
                                  or (known[0] <= dist + _LENGTH_EPS
                                      and known[1] > factor)):
            continue                    # stale: a shorter or a louder way here
        if cell != origin and heights.get(cell, -1.0) >= _PARTITION_RANK:
            continue                    # reached, not passed through
        x, y = cell
        here = inside[cell]
        for dx, dy, cost in _STEPS:
            nxt = (x + dx, y + dy)
            if nxt in inside:
                if inside[nxt] != here:
                    continue            # rooms never touch; the band is between
                nd, nf = dist + cost, factor
            else:
                # Across the band: the cell two steps on, in another room.
                nxt = (x + 2 * dx, y + 2 * dy)
                if nxt not in inside or inside[nxt] == here:
                    continue
                pf = _crossing_pass(field, cell, nxt)
                if pf <= 0:
                    continue
                nd, nf = dist + cost, factor * pf
            # Furniture in the way: crossed, not gone round (`OCCLUDER_PASS`).
            nf *= furniture(nxt)
            known = best.get(nxt)
            # The BEST path, not the first of its length: at equal length the
            # larger factor wins, so an equally short way round the shut door
            # or over nothing is not lost to whichever the heap reached
            # first. Path reversal keeps both terms, so this is what makes
            # the flood's answer the same in either direction.
            if known is None or nd < known[0] - _LENGTH_EPS \
                    or (nd <= known[0] + _LENGTH_EPS and nf > known[1]):
                best[nxt] = (nd, nf)
                heapq.heappush(heap, (nd, nxt, nf))
    return best


def gain_at(spread_map: dict, cell) -> float:
    """`pass / (1 + L^2)` at one cell of a spread; 0 where the flood never
    arrived. Path length, not straight distance -- the whole difference from
    light (§ 4.3)."""
    rec = spread_map.get(cell)
    if rec is None:
        return 0.0
    length, factor = rec
    return factor / (1.0 + length * length)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def _event_power(event) -> float:
    """A one-beat source's power from its `intensity`: a sound level word,
    a speech volume word, a number in [0, 1] as a fraction of `deafening`,
    or `audible` when it says nothing usable."""
    raw = event.get("intensity")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return SOUND_POWER["deafening"] * max(0.0, min(1.0, float(raw)))
    word = str(raw or "").strip().casefold()
    if word in SOUND_POWER:
        return SOUND_POWER[word]
    if word in SPEECH_POWER:
        return SPEECH_POWER[word]
    return SOUND_POWER["audible"]


def _is_sound_event(event) -> bool:
    for key in ("channel", "kind", "sense"):
        raw = str(event.get(key) or "").strip().casefold()
        if raw:
            from world.spatial_senses import _sense_channel
            return _sense_channel(raw) == "hearing"
    return False


def sound_sources(scene: dict, *, turn_idx=None, crowds=None, events=None,
                  speakers=None) -> tuple:
    """(sources, notices). Each source: {id, kind, room, cell, power, level,
    holder}, `cell` room-local. Kinds: `entity` (a running `sound_source`,
    at its cell -- its holder's cell when a body carries it, so a machine in
    your hands is heard at your own cell before anything else, § 4.7),
    `crowd` (at its room's centre, level by band), `event` (a one-beat sound
    event with a `source_room`, at that room's centre), `speech` (a body in
    `speakers` {name: volume}, at its cell -- for genuinely simultaneous
    voices; the reader path grades one line at a time).

    `notices` are the engine notices a `failing` source that went quiet this
    beat files (§ 5): silence where there was noise is heard, and the
    Director reads it next beat through the channel every other engine
    notice uses (`ctx.engine_feedback` -> `engine_notices`)."""
    out = []
    notices = []
    positions = scene.get("positions") or {}
    rooms = scene.get("rooms") or {}
    entities = scene.get("entities") or {}
    if isinstance(entities, dict):
        for eid, entity in sorted(entities.items()):
            if not isinstance(entity, dict):
                continue
            level = normalize_sound_level(entity.get("sound_source"))
            if not level or not _running(entity):
                continue
            label = str(entity.get("name") or eid)
            room = _ci_get(positions, eid)
            if room is None:
                room = _ci_get(positions, label)
            if not room or room not in rooms:
                continue
            beat = steadiness_this_beat(entity.get("steadiness"), turn_idx,
                                        eid)
            power = _power_of_level(level, beat)
            if beat == "out":
                notices.append(
                    "%s in %s has stopped: a failing sound source went "
                    "quiet this beat, and the silence is heard where the "
                    "sound was" % (label, (rooms.get(room) or {}).get("name")
                                   or room))
            holder = container_of(scene, eid) or container_of(scene, label)
            cell = None
            if holder:
                cell = body_cell(scene, holder)
            if cell is None:
                cell = body_cell(scene, eid) or body_cell(scene, label)
            if cell is None:
                cell = _centre(grid_side(scene, room))
            out.append({"id": str(eid), "kind": "entity", "room": str(room),
                        "cell": cell, "power": power, "level": level,
                        "holder": holder, "beat": beat, "label": label})
    for crowd in crowds or []:
        if not isinstance(crowd, dict):
            continue
        room = str(crowd.get("room_uid") or "")
        if not room or room not in rooms:
            continue
        from world.crowds import normalize_band
        level = CROWD_SOUND.get(normalize_band(crowd.get("band")), "audible")
        out.append({"id": "crowd:%s" % (crowd.get("uid") or room),
                    "kind": "crowd", "room": room,
                    "cell": _centre(grid_side(scene, room)),
                    "power": SOUND_POWER[level], "level": level,
                    "holder": None, "beat": "steady"})
    for idx, event in enumerate(events or []):
        if not isinstance(event, dict) or not _is_sound_event(event):
            continue
        room = str(event.get("source_room") or event.get("room")
                   or event.get("room_id") or "")
        if not room or room not in rooms:
            continue
        out.append({"id": "event:%d" % idx, "kind": "event", "room": room,
                    "cell": _centre(grid_side(scene, room)),
                    "power": _event_power(event), "level": None,
                    "holder": None, "beat": "steady"})
    for name, volume in sorted((speakers or {}).items()):
        room = room_of(scene, name)
        if not room or room not in rooms:
            continue
        cell = body_cell(scene, name) or _centre(grid_side(scene, room))
        vol = str(volume or "normal").strip().casefold()
        out.append({"id": "speech:%s" % name, "kind": "speech",
                    "room": str(room), "cell": cell,
                    "power": SPEECH_POWER.get(vol, SPEECH_POWER["normal"]),
                    "level": vol, "holder": None, "beat": "steady"})
    return out, notices


def sound_notices(scene: dict, turn_idx) -> list:
    """The notices this beat's failing sources carry on the field
    (`SoundField.notices`), scene-wide -- a failure is a fact about the
    source, not about who is listening. The notice the DIRECTOR reads is
    filed once, at commit, by `persist/commit_scene_state.py`'s failed-source
    block, which reads `failing_sound_sources_out` beside the light field's
    `failing_sources_out` and writes the switch as well: one notice per
    thing, whichever senses it fails in."""
    _sources, notices = sound_sources(scene, turn_idx=turn_idx)
    return notices


def failing_sound_sources_out(scene: dict, beat) -> list:
    """`[(entity_id, label)]` for every running `failing` sound source the
    beat hash puts out on `beat` -- the sound field's half of the commit's
    failed-source block (the light field's is `failing_sources_out`). The
    same hash `steadiness_this_beat` reads at perception time, so the two
    agree without a write; a thing that both lights and hums lands in both
    lists on the same beat and the commit files ONE notice for it."""
    out = []
    entities = (scene or {}).get("entities") or {}
    if not isinstance(entities, dict):
        return out
    for eid, entity in sorted(entities.items()):
        if not isinstance(entity, dict):
            continue
        if not normalize_sound_level(entity.get("sound_source")):
            continue
        if not _running(entity):
            continue
        if steadiness_this_beat(entity.get("steadiness"), beat, eid) != "out":
            continue
        out.append((str(eid), str(entity.get("name") or eid)))
    return out


def _ambient_floor(scene, room_id) -> float:
    """AMBIENT[exposure] plus the weather the room can hear (§ 4.6)."""
    from world import weather as _weather
    floor = AMBIENT.get(_weather.room_exposure(scene, room_id),
                        AMBIENT["enclosed"])
    try:
        scoped = _weather.weather_for_room(scene, room_id)
    except Exception:
        scoped = {}
    if scoped:
        if scoped.get("audible"):
            floor += WEATHER_NOISE.get(str(scoped.get("intensity") or ""),
                                       0.0) * float(scoped.get("gain") or 0.0)
        if scoped.get("wind_reaches"):
            floor += WIND_NOISE.get(str(scoped.get("wind") or ""), 0.0)
    return floor


# ---------------------------------------------------------------------------
# The field
# ---------------------------------------------------------------------------

class SoundField:
    """One listener's sound field: the composite grid, every source placed
    on it with its spread, and the ambient floor per room. Built by
    `sound_field`; read by `gain_between`, `noise_at`, `level_of`."""

    def __init__(self, scene, room_id, grid, sources, notices, turn_idx):
        self.scene = scene
        self.room = room_id
        self.grid = grid
        self.turn_idx = turn_idx
        self.notices = list(notices)
        self.sources = []
        self._spreads = {}
        #: The sources as `sound_sources` gave them, before placement on
        #: THIS grid, so a field for another room can be laid from the same
        #: beat's sources (`_field_for`).
        self._raw_sources = list(sources)
        self._siblings = {}
        for source in sources:
            if source["room"] not in grid.offsets:
                continue
            placed = dict(source)
            placed["at"] = grid.cell_of(source["room"], source["cell"])
            if placed["at"] not in grid.inside:
                continue
            self.sources.append(placed)
        self.ambient = {room: _ambient_floor(scene, room)
                        for room in grid.offsets}

    # -- geometry -----------------------------------------------------------

    def spread_from(self, cell) -> dict:
        if cell not in self._spreads:
            self._spreads[cell] = spread(self.grid, cell)
        return self._spreads[cell]

    def locate(self, name, room=None):
        """A body's cell on this field, or None when its room is not placed
        here. An unmeasured body stands at its room's centre -- the same
        approximation `_relative_sector` and `_observer_cell` make."""
        room = room or room_of(self.scene, name)
        if not room or room not in self.grid.offsets:
            return None
        cell = body_cell(self.scene, name) or _centre(
            grid_side(self.scene, room))
        at = self.grid.cell_of(room, cell)
        return at if at in self.grid.inside else None

    def _field_for(self, room_id):
        """This beat's field laid on another room, or None when that room
        carries no geometry. The same scene and the same sources; only the
        composite differs."""
        if not room_id:
            return None
        if room_id == self.room:
            return self
        if room_id in self._siblings:
            return self._siblings[room_id]
        field = None
        if room_has_geometry(self.scene, room_id):
            grid = acoustic_grid(self.scene, room_id)
            if grid is not None:
                field = SoundField(self.scene, room_id, grid,
                                   self._raw_sources, self.notices,
                                   self.turn_idx)
        self._siblings[room_id] = field
        return field

    def gain_between(self, speaker, listener, *, speaker_room=None,
                     listener_room=None) -> Optional[float]:
        """The fraction of a unit source at the speaker's cell that arrives
        at the listener's cell, or None when the pair is on no field.

        A PATH BETWEEN TWO CELLS HAS NO DIRECTION: the gain one way is the
        gain the other, so a pair gets ONE number and it is computed on ONE
        field. Which field is decided by the PAIR and not by whoever is
        asking -- the two rooms sorted, first that can place both bodies --
        because every composite is laid from one room outward
        (`room_field`), and two composites of the same two rooms are two
        different layouts: different offsets, different aperture spans,
        different path lengths through them. Read per listener, that made
        hearing one-way. Measured live: a courtyard and a gate across one
        open arch, one beat, one pair -- the warden's own field answered
        0.0309 for the shout and the shouter's answered 0.0, so the warden
        heard and replied while the player's view carried no hearing
        observation at all and the narrator wrote "no reply comes" over a
        reply the world had already produced
        (`PLAY_2026_09_05_caravanserai.md` § PB2).

        The NOISE stays the listener's own (`noise_at`, on the listener's
        field): a noise floor is a property of where a body stands, which is
        the one thing about the pair that is not shared.
        """
        s_room = speaker_room or room_of(self.scene, speaker)
        l_room = listener_room or room_of(self.scene, listener)
        if not s_room or not l_room:
            return None
        for room_id in sorted({str(s_room), str(l_room)}):
            field = self._field_for(room_id)
            if field is None:
                continue
            s = field.locate(speaker, s_room)
            l = field.locate(listener, l_room)
            if s is None or l is None:
                continue
            return gain_at(field.spread_from(s), l)
        return None

    # -- intensity ----------------------------------------------------------

    def intensity_at(self, source, cell) -> float:
        return source["power"] * gain_at(self.spread_from(source["at"]), cell)

    def noise_at(self, listener, *, exclude=(), room=None) -> Optional[float]:
        """The listener's NOISE (§ 4.4): every placed source's intensity at
        the listener's cell except those in `exclude` (ids, or the name of a
        body whose speech is the signal), plus the room's ambient floor."""
        cell = self.locate(listener, room)
        if cell is None:
            return None
        skip = {str(x).strip().casefold() for x in exclude if x}
        total = self.ambient.get(self.grid.inside[cell], AMBIENT["enclosed"])
        for source in self.sources:
            sid = source["id"].casefold()
            if sid in skip or sid.removeprefix("speech:") in skip:
                continue
            total += self.intensity_at(source, cell)
        return total

    def signal_at(self, listener, source_id, *, room=None) -> Optional[float]:
        cell = self.locate(listener, room)
        if cell is None:
            return None
        for source in self.sources:
            if source["id"] == source_id:
                return self.intensity_at(source, cell)
        return 0.0

    def level_of(self, listener, source_id, *, room=None) -> str:
        """`none | fragment | full` for one placed source (an entity, a
        crowd, an event, or `speech:<name>`) as this listener hears it."""
        signal = self.signal_at(listener, source_id, room=room)
        noise = self.noise_at(listener, exclude=(source_id,), room=room)
        if signal is None or noise is None:
            return "none"
        return quantise_hearing(signal, noise)

    def door_gain(self, listener, *, room=None) -> Optional[float]:
        """The largest gain from any of the listener's own room's doorways
        to the listener's cell -- what a unit source standing in the best
        opening of this room would deliver to their ear. None when the
        listener is off the field or the room has no opening placed.

        This is the SIGNAL half of the masking rule for a voice the field
        cannot place: wherever it came from, it entered this room through
        one of these openings and crossed the rest of the room as any other
        sound does, so no path from beyond can deliver more than a voice
        standing in the doorway. The barrier and the hops on the far side
        are the edge model's business and only ever subtract further.
        """
        cell = self.locate(listener, room)
        if cell is None:
            return None
        room = room or room_of(self.scene, listener)
        best = None
        for other in sorted(self.grid.offsets):
            if other == room:
                continue
            cells, _bearing = _door_cells(self.scene, room, other)
            for door in cells or ():
                at = self.grid.cell_of(room, door)
                if at not in self.grid.inside:
                    continue
                gain = gain_at(self.spread_from(at), cell)
                if best is None or gain > best:
                    best = gain
        return best

    def speech_level(self, speaker, volume, listener, *, speaker_room=None,
                     listener_room=None) -> Optional[str]:
        """One line's level for one listener, the speaker not otherwise a
        placed source. None when the pair is not on the field."""
        gain = self.gain_between(speaker, listener, speaker_room=speaker_room,
                                 listener_room=listener_room)
        if gain is None:
            return None
        noise = self.noise_at(listener, exclude=(speaker,), room=listener_room)
        if noise is None:
            # The pair's gain came off the pair's own field (`gain_between`);
            # the noise can only come off the LISTENER's, and without it
            # there is nothing to quantise against.
            return None
        level = sound_field_hear_level(volume, gain, noise)
        if level == "none" and one_opening_away(
                self.scene, listener_room or room_of(self.scene, listener),
                speaker_room or room_of(self.scene, speaker)):
            # A raised voice carries through an opening (§ PC3), the same
            # floor `hear_level` applies to a stamped relation.
            level = open_edge_floor(
                volume, {"open_edge": True, "noise": noise}) or level
        return level


def _cache_key(scene, room_id, turn_idx, crowds, events, speakers) -> str:
    entities = scene.get("entities") or {}
    sound_entities = {}
    if isinstance(entities, dict):
        for eid, entity in entities.items():
            if isinstance(entity, dict) and entity.get("sound_source"):
                sound_entities[eid] = {
                    "name": entity.get("name"),
                    "sound_source": entity.get("sound_source"),
                    "steadiness": entity.get("steadiness"),
                    "state": entity.get("state"),
                }
    parts = [room_id, turn_idx, crowds, events, speakers,
             scene.get("rooms"), scene.get("positions"), scene.get("stations"),
             scene.get("contacts"), scene.get("contained"),
             scene.get("weather"), scene.get("day_phase"), sound_entities]
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def sound_field(scene: dict, listener: str, *, room=None, turn_idx=None,
                crowds=None, events=None, speakers=None) -> Optional[SoundField]:
    """The sound field one listener hears the scene through, or None when
    the listener's room carries no geometry (§ 7's fail-open: no field, and
    every reader falls back to today's functions unchanged).

    Cached on everything it reads -- the rooms, positions, stations,
    contacts, containment, weather, the sound entities, the turn index and
    the extra sources -- so one stage pays the spreads once per listener."""
    room = room or room_of(scene, listener)
    if not room or not room_has_geometry(scene, room):
        return None
    key = _cache_key(scene, room, turn_idx, crowds, events, speakers)
    cached = _SOUND_FIELD_CACHE.get(key)
    if cached is not None and cached.scene is scene:
        return cached
    grid = acoustic_grid(scene, room)
    if grid is None:
        return None
    sources, notices = sound_sources(scene, turn_idx=turn_idx, crowds=crowds,
                                     events=events, speakers=speakers)
    field = SoundField(scene, room, grid, sources, notices, turn_idx)
    if len(_SOUND_FIELD_CACHE) >= _FIELD_CACHE_MAX:
        _SOUND_FIELD_CACHE.clear()
    _SOUND_FIELD_CACHE[key] = field
    return field


#: Relation flags under which the medium is a body, not air, and the field
#: has no cell for it: those pairs keep `hear_level`'s present answers (§ 4a).
_CONDUCTED = ("inside_source", "enclosed_from_source", "source_enclosed",
              "concealed")


def stamp_sound_relation(scene: dict, rel: dict, observer: str, target: str,
                         *, sound=None, observer_room=None,
                         target_room=None) -> dict:
    """Add `signal` (the path gain from the target's cell to the observer's,
    per unit of the target's power) and `noise` (the observer's noise floor
    with the target excluded) to a body-to-body relation, when the observer's
    field exists and both bodies stand on it. Otherwise the relation is
    returned exactly as given -- not a key added, not a value changed -- which
    is what keeps every scene without geometry byte-identical.

    `sound` is a precomputed `SoundField` for the observer (a perception
    stage builds one per perceiver with the beat's crowds, events and turn
    index); absent, a field is derived from the scene alone."""
    if any(rel.get(flag) for flag in _CONDUCTED):
        return rel
    if sound is None:
        sound = sound_field(scene, observer, room=observer_room)
    if sound is None:
        return rel
    noise = sound.noise_at(observer, exclude=(target,), room=observer_room)
    if noise is None:
        return rel
    o_room = observer_room or room_of(scene, observer)
    t_room = target_room or room_of(scene, target)
    if one_opening_away(scene, o_room, t_room):
        # A RAISED VOICE CARRIES THROUGH AN OPENING (`open_edge_floor`): the
        # rooms, not the path, decide that this pair has one, so it is
        # recorded here where the rooms are known.
        rel["open_edge"] = True
    gain = sound.gain_between(target, observer, speaker_room=target_room,
                              listener_room=observer_room)
    if gain is not None:
        rel["signal"] = gain
        rel["noise"] = noise
        return rel
    # NOISE MASKS A VOICE BY WHAT REACHES THE LISTENER, WHEREVER THE VOICE
    # CAME FROM. One masking rule, on every path: a listener's noise floor
    # is a property of where the LISTENER stands, not of how far away the
    # speaker is, so it must grade a voice from beyond the field exactly as
    # it grades one from across the room. Where the field cannot place the
    # speaker at all -- another room's room, more hops than a composite
    # covers -- it can still say what a voice entering by this room's own
    # best opening would deliver to this ear (`door_gain`), and that is a
    # CEILING the edge model's answer may not exceed. Measured live: a fog
    # bell in the watch room graded an ordinary voice IN the room to `none`
    # (signal 0.34, noise 20.5) while a shout from three rooms away arrived
    # whole, because the edge model had no idea there was a bell
    # (`PLAY_2026_09_05_lighthouse.md` § PA5).
    door = sound.door_gain(observer, room=observer_room)
    if door is None or door <= 0.0:
        return rel
    rel["door_gain"] = door
    rel["noise"] = noise
    return rel


def heard_events(scene: dict, listener: str, events, *, room=None,
                 turn_idx=None, crowds=None) -> list:
    """Sound events from OTHER rooms this listener hears through the field
    (§ 4b): [(event, level)] for each event with a `source_room` not the
    listener's own that grades above `none`. Empty without a field. Own-room
    events are the composer's business already (`ambient_percepts`)."""
    if not events:
        return []
    room = room or room_of(scene, listener)
    field = sound_field(scene, listener, room=room, turn_idx=turn_idx,
                        crowds=crowds, events=events)
    if field is None:
        return []
    out = []
    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        source_room = str(event.get("source_room") or event.get("room")
                          or event.get("room_id") or "")
        if not source_room or source_room == str(room):
            continue
        level = field.level_of(listener, "event:%d" % idx, room=room)
        if level != "none":
            out.append((event, level))
    return out


# ---------------------------------------------------------------------------
# The shape of the sound, for the composer (DESIGN_SOUND_FIELD.md § 4b)
# ---------------------------------------------------------------------------

def sound_shape(scene: dict, observer: str, *, sound=None, room=None,
                sweep=False) -> Optional[dict]:
    """Where the sound is, as the composer's closed-vocabulary input, or None
    when there is nothing to say. The owner's five rules (2026-09-04), the
    same five the light field's `light_shape` follows:

      a. speak only when the room is UNEVEN -- the noise word is not the
         same at every cell of the listener's own room; even, None, and
         whatever the composer says today stands byte-identically;
      b. grade by ANCHOR, not by cell -- the VISIBLE anchors of the room
         (`feature_visibility`, cone and line already subtracted) grouped by
         the noise word at the anchor's nearest cell (the mapping
         `neighbour_feature_visibility` uses), loud to quiet; no number,
         cell or sector name leaves this function;
      c. name the source only when the observer has a channel to it -- a
         running entity in this room the observer HEARS is named by its
         label; one in a placed neighbour is named by the OPENING it comes
         through, when that opening is in view; a source neither heard nor
         in view is not mentioned;
      d. say where the observer stands in it -- the noise word at their own
         measured cell; no cell, no claim;
      e. subtract, never add -- every item here is an anchor description the
         observer's eyes already reach or a label of a thing they already
         hear.

    Returns {"groups": [{"level": word, "items": [desc, ...]}, ...],
             "sources": [label, ...], "openings": [desc, ...],
             "self": word | None}.

    `sound` is the observer's precomputed field for the beat (crowds and the
    turn index included); absent, one is derived from the scene alone.
    """
    room = room or room_of(scene, observer)
    if not room:
        return None
    field = sound if sound is not None else sound_field(scene, observer, room=room)
    if field is None or field.room != room:
        return None
    grid = field.grid
    own_cells = [c for c, r in grid.inside.items() if r == room]
    if not own_cells:
        return None

    def noise_at_cell(cell):
        total = field.ambient.get(room, AMBIENT["enclosed"])
        for source in field.sources:
            total += field.intensity_at(source, cell)
        return total

    words = {noise_word(noise_at_cell(c)) for c in own_cells}
    if len(words) <= 1:
        return None                         # rule (a): even; nothing to add
    origin, how = _observer_cell(scene, observer)
    rows = feature_visibility(scene, observer, sweep=bool(sweep))
    placed = grid.anchors.get(room) or {}
    groups = {}
    visible_doors = set()
    for row in rows:
        if not row.get("visible"):
            continue
        if row.get("implicit"):
            visible_doors.add(row["anchor"])
            continue
        rec = placed.get(row["anchor"]) or {}
        cells = rec.get("cells") or ()
        if not cells:
            continue
        target = min(cells, key=lambda c: (c[0] - origin[0]) ** 2
                     + (c[1] - origin[1]) ** 2)
        groups.setdefault(noise_word(noise_at_cell(target)), []).append(
            row["desc"])
    sources = []
    openings = []
    for source in field.sources:
        if source.get("kind") not in ("entity", "crowd"):
            continue                        # a line and a one-beat event are the beat's, not the room's
        if field.level_of(observer, source["id"], room=room) == "none":
            continue                        # rule (c): not heard, not named
        if source["room"] == room:
            label = str(source.get("label") or "").strip()
            if label and label not in sources:
                sources.append(label)
            continue
        door = door_anchor_id(source["room"])
        if door in visible_doors:
            desc = str((placed.get(door) or {}).get("desc") or "").strip()
            if desc and desc not in openings:
                openings.append(desc)
    ordered = [{"level": word, "items": groups[word]}
               for word in reversed(NOISE_WORDS) if groups.get(word)]
    self_word = noise_word(noise_at_cell(origin)) if how == "measured" else None
    if not ordered and self_word is None:
        return None
    return {"groups": ordered, "sources": sources, "openings": openings,
            "self": self_word}
