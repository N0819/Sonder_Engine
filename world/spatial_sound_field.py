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
import math
from typing import Optional

from world.scene_memo import scene_memo, scene_read_parts
from world.spatial_barriers import normalize_barrier
from world.spatial_containment import container_of
from world.spatial_fov import (
    _Field,
    _HEIGHT_RANK,
    _door_cells,
    _observer_cell,
    _wall_verdict,
    body_cell,
    feature_visibility,
    grid_side,
    room_centre,
    room_field,
    room_has_geometry,
)
from world.spatial_geometry import door_anchor_id
from world.spatial_identity import PositionsIndex, room_of, room_of_record
from world.spatial_light_field import (
    _beat_hash, FAIL_RATE, FLICKER_RATE, normalize_steadiness, STEADINESS)
from world.spatial_senses import _material_shifted_barrier, _SOUND_WALK_BARRIERS


# ---------------------------------------------------------------------------
# The closed vocabularies
# ---------------------------------------------------------------------------

#: What a thing emits when running, or what a one-beat sound event is worth.
#: A schema the engine owns, not a device vocabulary: nothing here names a
#: generator, a waterfall, a radio or a crowd -- the objects hand's clause
#: states the class and the thing's name and description say what it is.
#:
#: `thunderous` and `catastrophic` were added 2026-09-05 with the decibel
#: denomination (`DESIGN_SOUND_DECIBELS.md` § 5): the old ladder topped out
#: at 12.5x a normal voice, so a cannon, a collapsing roof, a dragon and a
#: ship's horn had no rung and could reach no further than a shouting man.
#: Since the 2026-09-14 recalibration every rung is a real sound pressure
#: level (`SOUND_ONE_PACE_DB`), and which rungs clear `FAR_FIELD_ENTRY_DB`
#: is read off that table rather than stated here -- a running engine
#: does, a hearth fire does not -- which is what makes "an incredibly loud
#: noise travels very far" a property of the LADDER rather than of a
#: special case somewhere. An authored `db` number on an entity or an
#: event reaches anything the words do not.
SOUND_LEVELS = ("faint", "audible", "loud", "deafening", "thunderous",
                "catastrophic")

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
# DECIBELS: the denomination (DESIGN_SOUND_DECIBELS.md § 2A, 2026-09-05)
# ---------------------------------------------------------------------------
#
# The model is denominated in SOUND PRESSURE LEVELS. Every constant the owner
# sets is a dB number, every threshold is a dB MARGIN, every loss is a
# SUBTRACTION, and the far field (§ far field, below) is dB arithmetic end to
# end. What that buys is that the dynamic range stops being unwieldy: a
# whisper and a collapsing roof are 105 dB apart, one small number, where
# linearly they are a factor of thirty thousand million -- and a ladder
# that reaches an artillery piece stops needing fifteen-digit literals.
#
# POWERS STILL ADD IN POWER. Decibels are logarithms and logarithms do not
# sum; two incoherent sources at the same cell make a level of
# `db(p1 + p2)`, which is what real acoustics does too. So `noise_at` sums
# intensities and the WORD is decided in dB, against a dB margin. That is
# the whole of the conversion, and it is why it is exactly a rewriting: the
# comparison `signal >= FULL_SNR * noise` and the comparison
# `signal_db >= noise_db + FULL_SNR_DB` are the same inequality with a
# logarithm taken of both sides.
#
# THE REFERENCE IS ARBITRARY AND CANCELS. `DB_REF` sets where the ladder
# sits; every comparison in the model is a DIFFERENCE of two levels, so the
# reference falls out of all of them but two -- the absolute floor
# (`HEAR_FLOOR_DB`) and the far field's entry (`FAR_FIELD_ENTRY_DB`) -- and
# both are stated in the same denomination beside the ladder they gate.
#
# SINCE 2026-09-14 THE LADDERS ARE AUTHORED IN dB AND THE POWERS DERIVED,
# and the dB numbers are real ones: a sound pressure level in dB(A) at one
# pace, the distance every masking sentence in this module is written
# against ("could I hear someone beside me"). `DB_REF` is then only the
# power<->level conversion constant -- it says which linear power the
# number 40 dB names -- and has no calibration role: change it and every
# power moves together, every level stays, and nothing the model answers
# changes. It was 40 when the ladders were linear tables converted to
# levels, and it stays 40 so that the powers on disk, in traces and in the
# older tests remain the same numbers.

#: The power<->level conversion constant. See above: it no longer sets
#: where the ladder sits, because the ladder is authored in dB.
DB_REF = 40.0


def db_of_power(power) -> float:
    """A linear power as a level in dB. Silence is -inf, not an error: a
    source that is switched off has no level, and every comparison below
    handles -inf correctly by construction."""
    power = float(power or 0.0)
    if power <= 0.0:
        return float("-inf")
    return 10.0 * math.log10(power) + DB_REF


def power_of_db(db) -> float:
    """The inverse of `db_of_power`. Used where levels must be SUMMED --
    two sources at one cell -- because logarithms do not add."""
    db = float(db)
    if db == float("-inf"):
        return 0.0
    return 10.0 ** ((db - DB_REF) / 10.0)


def db_ratio(factor) -> float:
    """A bare RATIO in dB -- a gain, a loss, a threshold. No reference: this
    is the form every aperture factor, every occluder factor and both SNR
    thresholds take once the model is in logs."""
    factor = float(factor or 0.0)
    if factor <= 0.0:
        return float("-inf")
    return 10.0 * math.log10(factor)


def ratio_of_db(db) -> float:
    """The inverse of `db_ratio`, and the missing half of that pair.

    A GAIN IS A RATIO AND MUST NOT GO THROUGH `power_of_db`, which carries
    `DB_REF`: the two look interchangeable, differ by a factor of ten
    thousand, and the wrong one is silent. Caught before it shipped only by
    checking a one-hop answer against the composite field's own reading for
    the same pair -- 6.2e-07 where the field said 0.0191, which is a room
    that hears nothing ever and reports nothing."""
    db = float(db)
    if db == float("-inf"):
        return 0.0
    return 10.0 ** (db / 10.0)


#: The slack on every dB comparison, in dB. A LINEAR `>=` is inclusive and a
#: logarithm of both sides is not bit-exact, so an exactly-at-threshold pair
#: -- `signal == FULL_SNR * noise`, which synthetic fixtures do construct --
#: could round either way and answer a different WORD than the linear model
#: it replaces. MEASURED: over 800,000 exactly-at-threshold pairs across ten
#: decades of level, the largest disagreement the logarithm introduces is
#: 1.4e-14 dB. A pico-decibel is seventy times that and 2.3e-13 in power, so
#: the guarantee is exact and worth stating: THE dB PATH AND THE LINEAR PATH
#: GIVE THE SAME WORD FOR EVERY PAIR NOT WITHIN 1e-12 dB OF A THRESHOLD, and
#: an exact tie -- which synthetic fixtures do construct -- resolves the
#: inclusive way the linear `>=` resolved it.
_DB_EPS = 1e-12


def _at_least(level_db: float, threshold_db: float) -> bool:
    """`level_db >= threshold_db`, inclusive to `_DB_EPS`."""
    return level_db >= threshold_db - _DB_EPS


def spreading_loss_db(length: float) -> float:
    """`10*log10(1 + L^2)`: what a path of `length` costs a sound, in dB.
    The linear model's `1 / (1 + L^2)` written as the loss it is. Path
    length, never straight distance -- the whole difference from light."""
    length = float(length or 0.0)
    return 10.0 * math.log10(1.0 + length * length)


#: The spreading loss at a path of ONE cell: 3.01 dB. The yardstick every
#: masking rule is stated against ("could I hear someone beside me"), and
#: the distance every ladder below is authored at.
_ONE_PACE_LOSS_DB = spreading_loss_db(1.0)


def one_pace_power(db) -> float:
    """The power a source holds AT ITS OWN CELL so that it reads `db` one
    pace off. The flood charges a one-cell path `_ONE_PACE_LOSS_DB`, so a
    level authored at one pace -- which is where the world's tables measure
    a voice, a kettle and an engine -- sits that much higher at the cell.
    Every rung of `SPEECH_POWER` and `SOUND_POWER` is written through this,
    which is what lets `VOICE_ONE_PACE_DB` be exactly the number on the
    table and not the number less three."""
    return power_of_db(float(db) + _ONE_PACE_LOSS_DB)


# ---------------------------------------------------------------------------
# Constants the OWNER sets (DESIGN_SOUND_FIELD.md § 6, DESIGN_SOUND_DECIBELS.md
# § 5 and § 5c). Every one is named, owner-visible, and carries the table
# beside it, with the real-world basis of each number.
#
# THE dB TABLES ARE THE ONES WRITTEN DOWN AND THE POWERS ARE DERIVED FROM
# THEM (since 2026-09-14; it was the other way round while the ladders were
# converted linear tables, for tie-break exactness against arithmetic that
# had already shipped -- a reason that stopped applying the day the numbers
# were meant to change). A rung is a sound pressure level at ONE PACE, so a
# reader can check it against any decibel chart, and `one_pace_power` puts
# it on the cell.
#
# WHY THE OLD LADDERS WERE REPLACED RATHER THAN NUDGED. They were compressed:
# whisper->shout spanned 20.8 dB against 55 in the world (a factor of 0.36,
# measured in `DESIGN_SOUND_DECIBELS.md` § 5a), so every rung sat within a
# few decibels of its neighbours and a standing source and a voice could not
# be told apart by level. Played 2026-09-14 (two fresh stories, 22 turns;
# `PLAY_2026_09_14` in the session report): a hearth fire authored `audible`
# held the same power as a normal voice, so it masked a line spoken AT the
# hearth from five paces off (signal 0.08 against noise 1.83, `none`, and
# the page said "she offered no reply" four beats running); a launch engine
# authored `loud` shared its power with a loud voice, so a raised line one
# pace off on the deck was `none`; and a whisper at arm's reach beside that
# engine had no rung under conversation but the one the fire also sat on.
# Real levels put twenty decibels between a fire and a voice and ten between
# a voice and a shout, and the verdicts follow from the numbers instead of
# from a table tuned to them.
# ---------------------------------------------------------------------------

#: A speaking body's level ONE PACE OFF, by the line's volume word, in dB(A)
#: -- the figures any acoustics reference gives for speech at a metre.
#:
#:   mutter   38   speech under the breath: 35-45 dB(A) at a metre. The
#:                 owner's brief said ~45; 38 is taken because a mutter is
#:                 what the word means in a story -- an aside that reaches
#:                 the body beside you and not the room -- and the sentence
#:                 it has to satisfy is measured: across a large room's
#:                 width (a path of 5.8) in a still room (27 dB floor) it is
#:                 gone. At 45 it crossed that width `full`; at 40 it
#:                 crossed as a fragment that carried the numbers of the
#:                 secret it was muttered to keep ("...nation... seventeen...
#:                 nineteen...", `test_masked_floor_leaks`, the hole 1,364
#:                 live mutters rode). Under 39.4 it dies at the far wall;
#:                 38 is that with half a decibel of slack, and is `full` to
#:                 three paces, a fragment to four
#:   whisper  35   a whisper is 30-35 dB(A) at a metre; the upper figure,
#:                 because the engine's `whisper` is speech MADE for a
#:                 listener and the lower one is a breath. Five under a
#:                 mutter: the difference between breath and voice
#:   normal   60   conversational speech at a metre, the textbook 60 dB(A)
#:   loud     70   a raised voice, addressing a room: 65-75
#:   shout    82   shouting, 80-88 dB(A) at a metre; the middle of the
#:                 owner's stated 80-85
#:
#: The § 6 proposal (`mutter 1 | whisper 1.5 | normal 6 | loud 14 | shout
#: 30`, linear) and the 2026-09-04 table that replaced it (`0.6 | 1 | 12 |
#: 40 | 120`) are in `DESIGN_SOUND_FIELD.md` § 6a; the second gave the
#: ladder the ORDER a real voice has and not its span, which is the defect
#: the header of this section records.
SPEECH_ONE_PACE_DB = {"mutter": 38.0, "whisper": 35.0, "normal": 60.0,
                      "loud": 70.0, "shout": 82.0}

#: The same, as the power at the speaker's own cell -- what the flood
#: spreads. Derived, so it cannot drift from the table above.
SPEECH_POWER = {volume: one_pace_power(db)
                for volume, db in SPEECH_ONE_PACE_DB.items()}

#: The speech ladder as a level AT THE CELL -- the one-pace table plus the
#: one-pace loss: mutter 41.0 | whisper 38.0 | normal 63.0 | loud 73.0 |
#: shout 85.0. This is the number `sound_field_hear_level` adds a path's
#: gain to; `SPEECH_ONE_PACE_DB` is the number a reader compares to the
#: world.
SPEECH_DB = {volume: db_of_power(power)
             for volume, power in SPEECH_POWER.items()}

#: A running entity's level ONE PACE OFF, by `sound_source`, in dB(A).
#: Measured against the speech ladder because that is what a standing
#: noise IS to a story -- whether you can talk over it -- and in real
#: decibels the two ladders are comparable by construction.
#:
#:   faint         40   a ticking clock, a dripping tap, a candle's gutter:
#:                      35-45 dB(A); a quiet room is 30-40, so `faint` is
#:                      what you notice only when nothing else is happening
#:   audible       50   a hearth fire, a kettle coming up, a refrigerator:
#:                      45-55 dB(A) at a metre. Ten under a voice, so a
#:                      normal line beside it is `full`
#:   loud          80   an engine at idle, a mill, a busy workshop, a
#:                      vacuum cleaner: 75-85 dB(A) at a metre. The bottom
#:                      of the owner's stated 80-85, taken because the
#:                      composer's noise words are derived from the fragment
#:                      margin and 80 is where a raised voice one pace off
#:                      is still caught in pieces beside the machine
#:   deafening    100   a klaxon, a siren, a jackhammer, a chainsaw: 95-110
#:                      dB(A); a room you cannot use
#:   thunderous   120   thunder overhead, an artillery piece some way off,
#:                      the foot of a waterfall, a jet passing low: 115-125
#:   catastrophic 140   an explosion, a structure coming down, a jet engine
#:                      at close range: 135-150, the threshold of pain
#:
#: THE TOP TWO RUNGS MOVED, and it was forced rather than chosen. They were
#: declared 85 and 100 on 2026-09-05 as "23 and 38 dB over `deafening`",
#: on a ladder whose `deafening` was 61.8; on a real ladder `deafening` is
#: 100, so 85 and 100 would have put `thunderous` UNDER it and
#: `catastrophic` level with it. The ladder must be monotone -- `_one_level
#: _down` steps a failing source one rung down and would have made a
#: failing thunder LOUDER, and the far field's reach is asserted to grow
#: rung by rung -- so the two were re-authored at the real levels of the
#: things they name, which is also, to the decibel, their old offsets over
#: the new `deafening`. Their far-field reach grew with them (measured on a
#: 300-room chain of medium rooms and open doorways: 91 and 128 rooms
#: against the 29 and 51 the old levels reached); an explosion heard across
#: a whole scene is what an explosion is.
SOUND_ONE_PACE_DB = {"faint": 40.0, "audible": 50.0, "loud": 80.0,
                     "deafening": 100.0, "thunderous": 120.0,
                     "catastrophic": 140.0}

#: The same, as the power at the source's cell. Derived.
SOUND_POWER = {level: one_pace_power(db)
               for level, db in SOUND_ONE_PACE_DB.items()}

#: THE SAME FOUR WORDS MEAN SOMETHING ELSE ABOUT A ONE-OFF NOISE, and the
#: owner's 2026-09-06 ruling -- untie the noise ladder from the voice ladder
#: -- lands here rather than on `SOUND_POWER`.
#:
#: `SOUND_POWER` above is a STANDING EMISSION: a generator, a fan, a bell
#: rope pulled and left, a klaxon. What such a thing IS, to a story, is how
#: it sits against a voice -- whether you can talk over it, whether you have
#: to raise your voice, whether the room is unusable -- so measuring it
#: against the speech ladder is not the error, it is the definition.
#:
#: A `sensory_event` is an IMPACT. A crowbar on a bulkhead, a slammed hatch,
#: a dropped spanner, a detonation overhead: the sound is over before anyone
#: could talk over it, and what matters about it is HOW FAR IT WENT.
#: Measured against conversation on the compressed ladder it was absurd -- a
#: hammer blow on steel at 56.0 dB against a normal voice's 50.8, where the
#: real gap is nearer forty -- and 29 dB of range between `loud` and a
#: quiet room's 27.0 floor is what killed every noise inside the room that
#: made it. Measured on the descent story (chat 117): a `loud` clang in a
#: 20-pace plant room arrived at its own doorway at 30.0 dB, under the next
#: room's floor across any barrier at all, so a creature two rooms off could
#: never hear anything a player did whatever the geometry said.
#:
#:   emission (cell)  faint 43.0 | audible 53.0 | loud 83.0 | deafening 103.0
#:   impact   (cell)  faint 45.0 | audible 58.0 | loud 72.0 | deafening 80.0
#:
#: The impact ladder is UNTOUCHED by the 2026-09-14 recalibration: its four
#: lower rungs were authored in dB on 2026-09-06 at the source cell, not at
#: one pace, and are kept byte for byte. Two consequences are stated rather
#: than hidden. The emission ladder now sits ABOVE the impact ladder at
#: `loud` and `deafening` (an engine at 83 against a hammer blow at 72),
#: where on 2026-09-06 the relation was the reverse; nothing in the model
#: compares the two ladders to each other, so no verdict turns on it, and a
#: real impact ladder (a slammed door is 80-90 at a metre, a hammer on steel
#: over 100) is a separate recalibration registered in `docs/UNBUILT.md`.
#: And the two far rungs are shared, so they moved with `SOUND_POWER`.
#:
#: `loud` at 72 clears `FAR_FIELD_ENTRY_DB` (70), which is the point: a
#: hammer on a bulkhead walks the room graph and is heard across a level,
#: while `audible` 58 and `faint` 45 stay near-field things. An event whose
#: level is a bare number, or which carries an authored `db`, is unaffected.
EVENT_POWER = {"faint": power_of_db(45.0),
               "audible": power_of_db(58.0),
               "loud": power_of_db(72.0),
               "deafening": power_of_db(80.0),
               "thunderous": SOUND_POWER["thunderous"],
               "catastrophic": SOUND_POWER["catastrophic"]}

#: The impact ladder in dB at the cell -- faint 45.0 | audible 58.0 |
#: loud 72.0 | deafening 80.0 | thunderous 123.0 | catastrophic 143.0.
EVENT_DB = {level: db_of_power(power) for level, power in EVENT_POWER.items()}

#: The source ladder as a level AT THE CELL -- the one-pace table plus the
#: one-pace loss: faint 43.0 | audible 53.0 | loud 83.0 | deafening 103.0 |
#: thunderous 123.0 | catastrophic 143.0. Compared against
#: `FAR_FIELD_ENTRY_DB` at the cell, like the impact ladder.
SOUND_DB = {level: db_of_power(power) for level, power in SOUND_POWER.items()}

#: What crosses an aperture, by the barrier's class AFTER its material shift
#: (`_material_shifted_barrier`, so a paper screen and a vault door differ
#: exactly as they already do for the edge rules). A wall passes nothing and
#: is never an aperture; `separated` and `unknown` are not on a placed field
#: at all. Kept as § 6 proposed.
#:
#: REAL TRANSMISSION LOSSES SINCE 2026-09-14, on the same scale as the
#: emission ladders above: an open doorway ~2 dB, a grille the same, a hung
#: curtain ~5, a shut solid door ~25, closed glass ~28. Until then the table
#: was the compressed one calibrated against the old 20.8 dB voice span
#: (closed_door 6.02), and with real voices a shut door passed a normal line
#: `full` into the next room -- measured as
#: `tests/test_replay_defects_h.py`'s shut-door test failing the day the
#: ladders went real. Authored in dB and converted, so the pass factors
#: cannot drift from the losses they are.
#:
#:   open 0 | open_door 2 | bars 2 | membrane 5 | closed_door 25 |
#:   window 28 | one_way_window 28 | wall (no aperture)
APERTURE_DB = {"open": 0.0, "open_door": 2.0, "bars": 2.0, "membrane": 5.0,
               "closed_door": 25.0, "window": 28.0, "one_way_window": 28.0}
APERTURE_PASS = {**{barrier: 10.0 ** (-loss / 10.0)
                    for barrier, loss in APERTURE_DB.items()},
                 "wall": 0.0}

#: The same table as LOSSES in dB -- which is what an aperture factor is
#: once the model is in logs: a subtraction. `wall` is
#: not in it, because on the NEAR field a wall is not an aperture at all:
#: `sound_passes` refuses to place a neighbour beyond one, so there is no
#: cell path through a wall to charge a loss to. A wall's finite
#: transmission is the FAR field's business (`BARRIER_LOSS_DB` below), which
#: runs on rooms rather than cells and does not need a doorway to cross.
APERTURE_LOSS_DB = {barrier: -db_ratio(factor)
                    for barrier, factor in APERTURE_PASS.items()
                    if factor > 0.0}

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
#: The same, as a loss: 0.46 dB per occupied cell crossed.
OCCLUDER_LOSS_DB = -db_ratio(OCCLUDER_PASS)

#: The noise floor every cell of a room carries, by the room's exposure
#: (`weather.room_exposure`); the weather's audible level is added on top
#: (WEATHER_NOISE / WIND_NOISE). The floor is NOISE, never a source: it masks
#: and does not spread.
#:
#:   § 6 proposed   enclosed 0.3 | sheltered 0.6 | open 1.0
#:   set 2026-09-04 enclosed 0.05 | sheltered 0.1 | open 0.2
#:   set here       enclosed 0.05 | sheltered 0.1 | open 0.1
#:                  = 27.0 | 30.0 | 30.0 dB
#:
#: `open` moved 0.2 -> 0.1 on 2026-09-05, the owner ACCEPTING the
#: recommendation registered as `docs/UNBUILT.md` § 1.120: outdoors an
#: ordinary voice was `full` only inside about five paces, and 3.3 in light
#: rain, so two people walking together on an open road could not converse.
#: OPEN AIR IS NOT ITSELF A NOISE. What is noisy outdoors is the weather,
#: which is counted separately below, and 0.2 was four times a quiet room
#: for no source the world holds. Level with `sheltered` for the same
#: reason: the difference between a porch and a yard is what the sky can
#: reach them with, not what the air does on a still day.
#:
#: With FULL_SNR 2 the proposal put `full` at 0.6 in a quiet room, where a
#: normal voice at § 6's power is 0.23 five cells away -- `none`, below even
#: the floor. Two people at opposite walls of a medium room could not have
#: heard each other. The floor is set so a quiet enclosed room asks 0.1 for
#: `full`, which a normal voice clears to ten paces and a whisper to two.
AMBIENT = {"enclosed": 0.05, "sheltered": 0.1, "open": 0.1}

#: HOW MUCH QUIETER THAN ORDINARY A PLACE IS, when the room says so. The
#: declared word `quiet` on a room scales `AMBIENT[exposure]`, and it only
#: ever goes DOWN.
#:
#: One constant answered for a furnished parlour, a working plant room and
#: forty years of condemned concrete alike, and § 1.140 measured what that
#: cost: at the containment annex, through a shut door, 18 cells down the
#: spine, a `loud` pry bar on a bulkhead seam arrived at 24.9 dB against a
#: 27.0 dB floor -- SNR -2.1 where a `fragment` asks -0.97. A silent room
#: ought to be a place where a small sound carries; it was the thing that
#: swallowed a large one.
#:
#:   hushed  x1/4   -6 dB   an enclosed room reads 21.0
#:   dead    x1/16  -12 dB  an enclosed room reads 15.0
#:
#: SIX DECIBELS A RUNG, the same step the rest of this module is built on.
#:
#: DOWN ONLY, AND THE COMPLEMENT IS THE WHOLE ARGUMENT: what a place MAKES
#: that carries is a SOURCE, and the engine already has two ways to say it
#: -- `sound_source` on an entity standing in the room (the objects hand's
#: channel, the sibling of `light_source`) and `rooms[rid]["sound"]`, the
#: standing noise a PLACE makes, which a plan writes so an unfurnished room
#: can announce itself before it is seen. Both travel, both are heard from
#: the next room, and both already mask a listener standing beside them,
#: because `noise_at` counts every other source as noise. So a third word
#: meaning "loud" would be a second representation of a fact the scene
#: already holds, free to disagree with it. What no channel could say is
#: that a place makes NOTHING -- an absence has no source to hang on -- and
#: that is exactly and only what this word is for.
#:
#: A room that declares nothing is byte for byte what it was: an absent
#: word is not a claim, the same fail-open `normalize_light` takes.
QUIET_SCALE = {"hushed": 0.25, "dead": 0.0625}

#: The word's aliases -- what a model reaches for when it means the two
#: rungs above. Anything else is not a quiet word and the room keeps its
#: ordinary floor, because a word outside the set is a word the engine
#: cannot price and a guess here is a room that hears wrong forever.
_QUIET_ALIASES = {
    "silent": "dead", "deathly_quiet": "dead", "airless": "dead",
    "soundless": "dead", "tomb": "dead", "tomblike": "dead",
    "dead_quiet": "dead", "still": "hushed", "muffled": "hushed",
    "quiet": "hushed", "hush": "hushed", "subdued": "hushed",
}


def normalize_quiet(value) -> str:
    """The declared quiet word, or `""` for a room that declares none.

    Fail-CLOSED, against `normalize_light`'s fail-open, and the difference
    is which way the miss points: an unreadable light word means the room
    is ordinarily lit, which is a scene unchanged, while an unreadable
    quiet word would mean a room the engine has silently made deaf or
    sharp-eared for the rest of the story."""
    word = str(value or "").strip().casefold().replace(" ", "_")
    word = _QUIET_ALIASES.get(word, word)
    return word if word in QUIET_SCALE else ""


def room_quiet(scene, room_id) -> str:
    """The quiet a room declares of its own, or `""`."""
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return ""
    return normalize_quiet(room.get("quiet"))

#: What makes a room a DUCT: it is long, narrow and roofed, so the walls stop
#: a sound going anywhere except along it, and it carries far further than
#: the same sound in the open. Set as the ratio of a room's long side to its
#: short one, over its own measured `extent`.
#:
#:   set here   3.0 -- a room three times longer than it is wide is a passage
#:
#: A spine, a corridor, a gallery, a culvert, a tunnel and a nave all clear
#: it and none of them is named here; a hall, a cell, a parlour and a yard
#: do not.
DUCT_ASPECT = 3.0

#: What a pace costs a sound INSIDE a duct, against 1 in an ordinary room.
#: `spreading_loss_db` is `10*log10(1 + L^2)`, free-field inverse square:
#: right for a hall, where a sound goes off in every direction and only a
#: shrinking share of it reaches you, and wrong for a corridor, where there
#: is nowhere else for it to go. The exact law is cylindrical near the source
#: and plane further along; this is the first-order constant that stands for
#: both, and it is the owner's like every other constant here.
#:
#:   set here   0.5 -- a duct is half as long to a sound as it is to a body
#:
#: On the beat it was set for, 18 paces of vaulted service spine: 25.1 dB of
#: spreading loss becomes 19.1, and the pry bar the annex could not hear at
#: all arrives `full`. Charged only on a step WITHIN one room. A step across
#: a wall band is one step in either direction and keeps its own cost, which
#: is what makes a path's length the same measured from either end (the
#: reciprocity `_LENGTH_EPS` and `spread`'s tie-break exist to hold).
DUCT_STEP = 0.5

#: The same floors in dB -- enclosed 27.0 | sheltered 30.0 | open 33.0.
#: (`DESIGN_SOUND_DECIBELS.md` § 5 said 14 / 17 / 20: the right 3 dB steps
#: against a different reference than its own source ladder. The steps are
#: what the model behaves by; see `SPEECH_DB`.)
AMBIENT_DB = {exposure: db_of_power(power)
              for exposure, power in AMBIENT.items()}

#: The weather as noise: precipitation the room can hear
#: (`weather_for_room(...)["audible"]`, scaled by its `gain` -- muffled rain
#: through a wall is quieter than rain on you), by the sky's intensity word,
#: and wind that reaches the room by its wind word. NOT in § 6, which said
#: only "(+ weather)"; these are the two numbers that sentence needed.
#:
#:   set 2026-09-04 light 0.3 | moderate 0.6 | heavy 1.0
#:   set here       light 0.1 | moderate 0.25 | heavy 0.5
#:                  = 30.0 | 34.0 | 37.0 dB
#:
#: Moved 2026-09-05 with `AMBIENT["open"]`, the same accepted
#: recommendation (`docs/UNBUILT.md` § 1.120). RAIN YOU CAN TALK THROUGH
#: UNTIL IT IS HEAVY: light rain is the commonest weather there is, and at
#: 0.3 it more than doubled an open room's floor by itself and took ordinary
#: speech to 3.3 paces. `WIND_NOISE` is deliberately NOT moved -- wind you
#: have to raise your voice over is what wind is, and the run that found
#: this measured rain.
WEATHER_NOISE = {"light": 0.1, "moderate": 0.25, "heavy": 0.5}
WIND_NOISE = {"wind": 0.3, "gale": 1.0}

#: Both as levels. They are ADDED to the exposure floor, and levels do not
#: add -- `_ambient_floor` sums the powers and the dB view is taken of the
#: total, which is the one place the conversion has to be careful and the
#: one place real acoustics agrees with it exactly.
WEATHER_NOISE_DB = {word: db_of_power(power)
                    for word, power in WEATHER_NOISE.items()}
WIND_NOISE_DB = {word: db_of_power(power)
                 for word, power in WIND_NOISE.items()}

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
#: voice at five cells; set with AMBIENT on 2026-09-04 so a whisper's
#: fragment survives to four cells and dies at five.
#:
#: 27.0 dB, and unmoved by the 2026-09-14 recalibration. It is NOT the
#: ear's threshold in the physiological sense (that is 0 dB SPL by
#: definition); it is the floor of an ordinary quiet room, which is what it
#: was set to, and `quantise_hearing_db` explains why the two are one
#: number here: YOU CANNOT HEAR BELOW THE ROOM YOU ARE STANDING IN, so the
#: absolute limit the model needs is the quietest room it prices, and a
#: room declared quieter (`QUIET_SCALE`) lowers it with the room.
HEAR_FLOOR = 0.05
#: `full` when signal >= FULL_SNR * noise. Kept as § 6 proposed: +3 dB over
#: the noise. Real speech-in-noise data puts near-complete sentence
#: intelligibility for a familiar voice at a signal-to-noise ratio of 0 to
#: +5 dB in steady noise; +3 is the middle of that band.
FULL_SNR = 2.0
#: `fragment` when signal >= FRAGMENT_SNR * noise (and >= HEAR_FLOOR).
#:
#: MOVED 2026-09-14 from 0.8 (-0.97 dB) to 1/16 (-12.04 dB), WITH THE
#: LADDERS, because it was the number that made the deck's verdict wrong
#: whatever the ladders said. At -1 dB, "caught in pieces" ended where the
#: voice was four fifths of the room, and no real listener is that deaf: the
#: speech reception threshold (half the sentences understood) sits near -5
#: to -8 dB SNR in steady noise for normal hearing, intelligibility falls to
#: a few words by about -12, and against a masker that does not share
#: speech's spectrum -- an engine, wind, water -- the effective margin is
#: several decibels better again. So a voice is FOLLOWED at +3 over the
#: room and CAUGHT IN PIECES down to a sixteenth of it, two rungs of the
#: six-decibel step the rest of this module is built on. Measured on the
#: 4x3 deck with a real 80 dB engine: a raised line one pace off is
#: `fragment` from every cell of the deck (-3 to -10 dB), where at -1 dB
#: it was `none` from every cell; a normal line at arm's reach is a
#: `fragment` three paces from the machine and `none` at two, which is the
#: distance at which people on a launch stop talking and start shouting.
FRAGMENT_SNR = 0.0625

#: The three in dB. The two ratios become MARGINS over the noise -- `full`
#: at +3.01 dB, `fragment` at -12.04 dB -- which is the form they were
#: always in and the form that says what they mean: a voice is followed when
#: it is twice the room, and caught in pieces when it is a sixteenth of it.
#: The absolute floor is a LEVEL and so is the one number the reference does
#: not cancel out of.
FULL_SNR_DB = db_ratio(FULL_SNR)
FRAGMENT_SNR_DB = db_ratio(FRAGMENT_SNR)
HEAR_FLOOR_DB = db_of_power(HEAR_FLOOR)

#: THE NOISE LADDER the composer speaks (2026-09-04, the owner's rule b: the
#: sentence grades by a closed set, never a number). Three words for what
#: the noise at a cell does to a NORMAL VOICE ONE PACE OFF -- the yardstick
#: a body has for a room's loudness, "could I hear someone beside me" --
#: derived from the two SNR thresholds above, not set beside them:
#:
#:   quiet    a normal voice one pace off is `full`      noise <= 60 - FULL_SNR_DB      (57.0 dB)
#:   din      ... is a `fragment`                        noise <= 60 - FRAGMENT_SNR_DB  (72.0 dB)
#:   drowned  ... is `none`                              above that
#:
#: where 60 is `SPEECH_ONE_PACE_DB["normal"]`. In the world: a hearth fire
#: (50 at a pace) leaves the hearth `quiet`; an engine (80) is `drowned`
#: at the machine and a `din` within three paces of it. Move FULL_SNR or
#: FRAGMENT_SNR and the words move with them.
NOISE_WORDS = ("quiet", "din", "drowned")
#: A normal voice ONE PACE OFF as a power: the cell power over the one-pace
#: loss, which is exactly `one_pace_power(60)` unwound.
VOICE_ONE_PACE = SPEECH_POWER["normal"] / 2.0
#: The same yardstick as a level: 60.0 dB, a normal voice at one pace, and
#: the same number as `SPEECH_ONE_PACE_DB["normal"]` by construction.
VOICE_ONE_PACE_DB = db_of_power(VOICE_ONE_PACE)


def noise_word(noise: float) -> str:
    """One of NOISE_WORDS for a noise floor, by what it does to a normal
    voice one pace off. In dB the three words are one margin read twice."""
    return noise_word_db(db_of_power(noise))


def noise_word_db(noise_db: float) -> str:
    """`noise_word` for a floor already in dB."""
    if _at_least(VOICE_ONE_PACE_DB, noise_db + FULL_SNR_DB):
        return "quiet"
    if _at_least(VOICE_ONE_PACE_DB, noise_db + FRAGMENT_SNR_DB):
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


def word_for_level(level_db) -> str:
    """The volume word nearest a level AT THE CELL (`SPEECH_DB`'s terms):
    what a pitched line counts as wherever a reader wants the word --
    the edge ladder, a view, a memory."""
    try:
        level = float(level_db)
    except (TypeError, ValueError):
        return "normal"
    return min(SPEECH_DB, key=lambda w: (abs(SPEECH_DB[w] - level), w))


def _body_key(scene, name):
    """The positions key `name` denotes, by key or entity name, or None."""
    positions = (scene or {}).get("positions") or {}
    want = str(name or "").strip().casefold()
    if not want:
        return None
    for key in positions:
        if str(key).strip().casefold() == want:
            return key
    for eid, ent in ((scene or {}).get("entities") or {}).items():
        if isinstance(ent, dict) and str(ent.get("name") or "").strip().casefold() == want:
            if eid in positions:
                return eid
    return None


def pitched_level_db(scene, speaker, addressee) -> float:
    """The level AT THE CELL a line pitched to `addressee` is spoken at: the
    lowest that arrives `full` at the addressee's cell -- their noise floor
    plus `FULL_SNR_DB`, less the path's gain -- clamped to the ladder's
    span (a whisper at the least, a shout at the most: nobody pitches a
    line across a hall by wanting to). The owner's ask (2026-09-15): a
    line's loudness follows its intent, "low, so that only his table would
    hear" reaching the table and nobody at the far wall. Where the pair has
    no field, or the addressee cannot be placed, the line is a normal one.
    """
    lo, hi = SPEECH_DB["whisper"], SPEECH_DB["shout"]
    who = _body_key(scene, addressee)
    said = _body_key(scene, speaker)
    if not who or not said:
        return SPEECH_DB["normal"]
    from world.spatial_senses import spatial_rel_between
    rel = spatial_rel_between(scene, who, said)
    signal, noise = rel.get("signal"), rel.get("noise")
    if signal is None or noise is None or float(signal) <= 0.0:
        return SPEECH_DB["normal"]
    level = db_of_power(noise) + FULL_SNR_DB - db_ratio(signal)
    return max(lo, min(hi, level))


def sound_field_hear_level(volume, signal_gain, noise, level_db=None) -> str:
    """Quantise, LAST (§ 4.5): `full` at FULL_SNR, `fragment` at
    FRAGMENT_SNR and above HEAR_FLOOR, else `none`. `signal_gain` is the
    fraction of the speaker's power arriving at the listener's cell (what
    `spatial_rel_between` stamps as `rel["signal"]`); the volume word turns
    it into a signal here, because the relation is built before the line is
    read.

    In dB the two terms are ADDED rather than multiplied: the speaker's
    level at one pace, plus the path's gain -- a negative number, the
    aperture losses and the spreading loss the flood accumulated. That is
    the whole of what "an aperture factor becomes a subtraction" means."""
    volume = str(volume or "normal").strip().casefold()
    if level_db is None:
        level_db = SPEECH_DB.get(volume, SPEECH_DB["normal"])
    return quantise_hearing_db(float(level_db) + db_ratio(signal_gain),
                               db_of_power(noise))


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
    if noise is not None and quantise_hearing_db(
            SPEECH_DB[volume] - _ONE_PACE_LOSS_DB,
            db_of_power(noise)) == "none":
        return None
    return "fragment"


def quantise_hearing(signal: float, noise: float) -> str:
    """Quantise, LAST, from two LINEAR powers. The reference path, kept in
    step with the dB path below so the conversion property has something to
    prove (`tests/test_sound_field.py`)."""
    if noise <= 0:
        return "full" if signal >= HEAR_FLOOR else "none"
    if signal >= FULL_SNR * noise:
        return "full"
    if signal >= FRAGMENT_SNR * noise and signal >= min(HEAR_FLOOR, noise):
        return "fragment"
    return "none"


def quantise_hearing_db(signal_db: float, noise_db: float) -> str:
    """Quantise, LAST, from two LEVELS. THE PRODUCTION PATH.

    The same inequality with a logarithm taken of both sides: `full` at
    `FULL_SNR_DB` over the noise, `fragment` at `FRAGMENT_SNR_DB` over it
    AND at or above the absolute floor, else `none`.

    THE FLOOR GATES `fragment` AND NOT `full`, exactly as the linear model
    does. It reads like an oversight and is not one worth changing here: a
    signal under `HEAR_FLOOR` that still stands `FULL_SNR` over its room is
    a room quieter than the floor, and the model's answer is that you follow
    it. Whether that is right is the constants' question; whether this
    function answers it the same way as the one it replaces is this
    function's, and the order below is the answer. A silent room
    (`noise_db` -inf) keeps its own arm for the same reason.

    YOU CANNOT HEAR BELOW THE ROOM YOU ARE STANDING IN, which is why the
    absolute floor is taken against the room's noise rather than alone.
    `HEAR_FLOOR` was "set with AMBIENT" (its own comment) and landed on
    0.05, exactly `AMBIENT["enclosed"]` -- so in every ordinary indoor room
    the two gates sit within a decibel of each other and the absolute one is
    the higher, which is fine while nothing can be quieter than an ordinary
    room. `quiet` made something quieter, and left alone this line would
    have held a `dead` room to a floor 12 dB above its own noise: the room
    would declare itself a tomb and hear exactly what a furnished parlour
    hears, and the declared word would be inert with no error anywhere.
    Taking the lower of the two says the calibration was of an ORDINARY
    quiet room, and where a room is quieter than that, the room is the
    limit. A room that declares no quiet has a floor at or above
    `HEAR_FLOOR` and takes `HEAR_FLOOR`, byte for byte as before.
    """
    if noise_db == float("-inf"):
        return "full" if _at_least(signal_db, HEAR_FLOOR_DB) else "none"
    if _at_least(signal_db, noise_db + FULL_SNR_DB):
        return "full"
    if _at_least(signal_db, noise_db + FRAGMENT_SNR_DB) \
            and _at_least(signal_db, min(HEAR_FLOOR_DB, noise_db)):
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
    return room_field(scene, room_id, through=sound_passes, derive=True)


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


def spread(field: _Field, origin, *, step_scale=None) -> dict:
    """{cell: (path length, pass)} for every cell the flood reaches from
    `origin`: Dijkstra over the field's cells. A side step costs 1, a
    diagonal DIAGONAL_COST.

    `step_scale` is `{room_id: what a pace inside that room costs}` -- the
    duct rule (`DUCT_STEP`), and absent it every step costs what it always
    did, so every caller that does not pass one is byte-identical. It is
    charged on a step WITHIN one room only; the step across a wall band is
    one step from either side and keeps its cost, which is what keeps a
    path the same length measured from either end.

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
                nd = dist + cost * (step_scale or {}).get(here, 1.0)
                nf = factor
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


def loss_db_at(spread_map: dict, cell) -> float:
    """The same number as a LOSS in dB: the aperture and occluder losses the
    path crossed, plus `spreading_loss_db` of its length. +inf where the
    flood never arrived.

    The flood itself still accumulates a multiplicative factor, and this is
    the ONE place the decibel work is a view rather than the arithmetic. The
    reason is bit-identity: `spread` breaks ties between two equally short
    paths on the larger FACTOR, and a sum of dB losses and a product of
    factors do not order identically in the last bits -- which is exactly
    the class of defect the 2026-09-05 reciprocity repair was (`_LENGTH_EPS`
    and its note). A product of factors IS a sum of losses, so nothing
    behavioural rides on which side of the logarithm the accumulation
    happens; only the tie-break does, and it stays where it was measured."""
    gain = gain_at(spread_map, cell)
    return -db_ratio(gain) if gain > 0.0 else float("inf")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def event_db(event) -> float:
    """A one-beat sound's LEVEL in dB, from the event record.

    Read in one order, loudest evidence first: an authored `db` number (the
    escape hatch for anything the words do not reach -- a cannon, a
    calving glacier, a god); then a `level` word off `SOUND_LEVELS`, which
    is what the event channel asks for; then the older `intensity`, which
    `sensory_events` has always carried as a level word, a speech volume, or
    a number in [0, 1] read as a fraction of `deafening`'s POWER (kept
    exactly, fraction and all, because opening turns have written it);
    then `audible`, which is what a sound nobody graded is worth.
    """
    raw = event.get("db")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    for key in ("level", "intensity"):
        raw = event.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return db_of_power(
                EVENT_POWER["deafening"] * max(0.0, min(1.0, float(raw))))
        word = str(raw or "").strip().casefold()
        # `EVENT_DB`, the impact ladder: this function is only ever asked
        # about a one-beat sound. A speech volume written here is still
        # speech (`SPEECH_DB`) -- a level word a body could have SAID is
        # that body's loudness, not a hammer's.
        if word in EVENT_DB:
            return EVENT_DB[word]
        if word in SPEECH_DB:
            return SPEECH_DB[word]
    return EVENT_DB["audible"]


def _event_power(event) -> float:
    """`event_db` as a power, for the near field's flood -- which multiplies
    rather than adds. Written out rather than `power_of_db(event_db(...))`
    so a level word yields the EXACT literal the flood was measured on: the
    round trip through a logarithm returns 12.000000000000007, and this
    number is one end of a tie-break."""
    raw = event.get("db")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return power_of_db(float(raw))
    for key in ("level", "intensity"):
        raw = event.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return EVENT_POWER["deafening"] * max(0.0, min(1.0, float(raw)))
        word = str(raw or "").strip().casefold()
        # THE IMPACT LADDER, not the emission one (`EVENT_POWER`). A speech
        # volume written on an event still reads as speech: a level word a
        # body could have SAID is that body's loudness, not a hammer's.
        if word in EVENT_POWER:
            return EVENT_POWER[word]
        if word in SPEECH_POWER:
            return SPEECH_POWER[word]
    return EVENT_POWER["audible"]


def _is_sound_event(event) -> bool:
    for key in ("channel", "kind", "sense"):
        raw = str(event.get(key) or "").strip().casefold()
        if raw:
            from world.spatial_senses import _sense_channel
            return _sense_channel(raw) == "hearing"
    return False


#: WHAT THE WALLS GIVE BACK (the owner's ask, 2026-09-15: "quieter spaces
#: should allow for some pretty long reaching echoes like an abandoned
#: building"). A room's `surface` is the fraction of sound its surfaces
#: absorb: `bare` for stone, concrete, tile and an emptied room; `soft`
#: for cloth, crowd and snow; `furnished` the ordinary room. Sabine's
#: numbers, the owner's to move.
ABSORPTION = {"bare": 0.05, "furnished": 0.25, "soft": 0.5}
#: Only a BARE room adds its reverberant field to the direct one below: an
#: ordinary furnished room keeps today's spreading model byte for byte,
#: because applying the physics to every parlour would move every
#: calibration the owner has set. `soft` is accepted as the word for a room
#: that rings even less than that.
REVERBERANT_SURFACES = frozenset({"bare"})
#: The height a room is assumed to have, in metres, and a pace in metres.
ROOM_HEIGHT_M = 3.0
PACE_M = 0.75
#: When the ring is this much louder than the voice at the listener's cell,
#: the words smear: a `full` line grades `fragment`.
REVERB_SMEAR_DB = 6.0
#: A bare room this long (its longer side, in paces) gives a sharp sound
#: back as a second, separate sound -- about seventeen metres of extra
#: path, the fifty milliseconds an ear needs to hear two.
ECHO_SPAN_PACES = 12
#: The word the narrator is handed for a room's ring, by reverberation
#: time in seconds.
REVERB_WORDS = ((2.0, "cavernous"), (1.0, "ringing"), (0.6, "live"))
#: A body's tread at one pace, by pace: a walk is `faint` (40 dB), a run
#: `audible` (50). The owner's numbers.
TREAD_LEVEL = {"walk": "faint", "run": "audible"}
#: A TREAD IS IMPACT NOISE AND IS MADE IN THE FLOOR ITSELF: what the room
#: below hears is a property of the floor, not of the air above it --
#: boards overhead carry a footfall into the room beneath at a level a
#: voice through the same floor never reaches. The level heard in the room
#: below a walk, by the upper room's `floor` word (masonry for anything
#: else); a run is `TREAD_RUN_DB` louder. The owner's numbers.
FLOOR_IMPACT_DB = {"timber": 55.0, "board": 55.0, "plank": 55.0,
                   "stone": 40.0, "concrete": 40.0, "masonry": 40.0}
TREAD_RUN_DB = 8.0


def normalize_surface(value) -> str:
    word = str(value or "").strip().casefold()
    return word if word in ABSORPTION else ""


def room_surface(scene, room_id) -> str:
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    return normalize_surface((room or {}).get("surface")) if isinstance(room, dict) else ""


def room_reverberation(scene: dict, room_id) -> Optional[dict]:
    """How a bare room rings: `{rt60, gain, gain_db, word, echo}` from
    Sabine's rule over the room's extent and an assumed height, or None for
    a room that declares no reverberant surface.

    `rt60` is the reverberation time in seconds (0.161 V / A); `gain` is
    the reverberant field's level everywhere in the room relative to the
    ONE-PACE direct level the ladders are authored at
    (L_rev - L_1 = 8.5 + 10 log10(4 / R), R = A / (1 - a)), as a power
    ratio; `echo` says the room's longer side clears `ECHO_SPAN_PACES`.
    """
    surface = room_surface(scene, room_id)
    if surface not in REVERBERANT_SURFACES:
        return None
    from world.spatial_fov import room_grid
    grid = room_grid(scene, room_id)
    w = float(getattr(grid, "w", 0) or grid_side(scene, room_id)) * PACE_M
    d = float(getattr(grid, "d", 0) or grid_side(scene, room_id)) * PACE_M
    h = ROOM_HEIGHT_M
    alpha = ABSORPTION[surface]
    surface_m2 = 2.0 * (w * d + w * h + d * h)
    volume = w * d * h
    absorption = max(1e-6, alpha * surface_m2)
    rt60 = 0.161 * volume / absorption
    room_constant = absorption / max(1e-6, 1.0 - alpha)
    gain_db = 8.5 + 10.0 * math.log10(4.0 / room_constant)
    word = next((name for floor, name in REVERB_WORDS if rt60 >= floor), "")
    longest = max(getattr(grid, "w", 0) or 0, getattr(grid, "d", 0) or 0) \
        or grid_side(scene, room_id)
    return {"rt60": round(rt60, 2), "gain": ratio_of_db(gain_db),
            "gain_db": round(gain_db, 1), "word": word,
            "echo": float(longest) >= ECHO_SPAN_PACES}


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
    beat files (§ 5). WHO HEARS THEM IS THE DIRECTOR (E16): the notice reaches
    it next beat through the channel every other engine notice uses
    (`ctx.engine_feedback` -> `engine_notices`), and nothing mints a percept
    for a sound that stopped, so § 5's "silence where there was noise is
    heard" is heard on the page only if the Director answers the notice."""
    out = []
    notices = []
    rooms = scene.get("rooms") or {}
    entities = scene.get("entities") or {}
    if isinstance(entities, dict):
        # One folded read of `positions` for the whole sweep (B18).
        index = PositionsIndex(scene.get("positions") or {})
        for eid, entity in sorted(entities.items()):
            if not isinstance(entity, dict):
                continue
            level = normalize_sound_level(entity.get("sound_source"))
            if not level or not _running(entity):
                continue
            label = str(entity.get("name") or eid)
            room = room_of_record(scene, eid, entity, index=index)
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
                cell = room_centre(scene, room)
            out.append({"id": str(eid), "kind": "entity", "room": str(room),
                        "cell": cell, "power": power, "level": level,
                        "holder": holder, "beat": beat, "label": label})
    # A ROOM THAT IS HEARD DOING SOMETHING. `rooms[rid]["sound"]` is a
    # standing noise the PLACE makes -- water in a culvert, a plant still
    # turning over, wind through a grille -- and it is a room-level property
    # for the same reason `room_light` is one: it belongs to the space and
    # not to any thing in it, so a place the story has laid out but nobody
    # has furnished can still be heard. That is what lets a planned room
    # announce itself before it is seen (`plot_packages._plan_sound`).
    #
    # At the room's centre, like a crowd, because that is as fine as a fact
    # about a whole room gets.
    if isinstance(rooms, dict):
        for rid, room in sorted(rooms.items()):
            if not isinstance(room, dict):
                continue
            record = room.get("sound")
            if not isinstance(record, dict):
                continue
            level = normalize_sound_level(record.get("level"))
            if not level:
                continue
            # THE CARRYING LADDER (`EVENT_POWER`), not the emission one.
            # The two ladders differ in what they are measured AGAINST:
            # `SOUND_POWER` asks how a thing sits beside a voice -- whether
            # you can talk over the generator you share a room with -- and
            # `EVENT_POWER` asks how far a sound gets in the world. A room's
            # own voice is the second question by construction: the whole
            # reason to write one is that it is heard from somewhere else.
            # So `loud` and above clear `FAR_FIELD_ENTRY_DB` and announce
            # the place across a level, while `faint` and `audible` stay
            # near-field things you meet at the door -- which is the
            # gradient a story wants and neither ladder gave on its own.
            out.append({"id": "room:%s" % rid, "kind": "room",
                        "room": str(rid), "cell": room_centre(scene, rid),
                        "power": EVENT_POWER[level], "level": level,
                        "holder": None, "beat": "steady",
                        "detail": str(record.get("detail") or "")})
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
                    "cell": room_centre(scene, room),
                    "power": SOUND_POWER[level], "level": level,
                    "holder": None, "beat": "steady"})
    for idx, event in enumerate(events or []):
        if not isinstance(event, dict) or not _is_sound_event(event):
            continue
        room = str(event.get("source_room") or event.get("room")
                   or event.get("room_id") or "")
        if not room or room not in rooms:
            continue
        # A SOUND IS MADE WHERE ITS SOURCE STANDS. An event names its
        # `source`; where that is a body the scene places (a character, or
        # a charter body laid for the beat), the sound starts at that body's
        # cell, not at the room's centre. Measured (scratch play 2026-09-14,
        # chat 4 turn 18): a creature dragging itself at the well-house door
        # was priced from the yard's centre, seven cells from the listener
        # at the open back door, and fell under the floor there.
        source = str(event.get("source") or "").strip()
        cell = (body_cell(scene, source) if source and
                room_of(scene, source) == room else None)
        out.append({"id": "event:%d" % idx, "kind": "event", "room": room,
                    "cell": cell or room_centre(scene, room),
                    "power": _event_power(event), "level": None,
                    "holder": None, "beat": "steady"})
    for name, volume in sorted((speakers or {}).items()):
        room = room_of(scene, name)
        if not room or room not in rooms:
            continue
        cell = body_cell(scene, name) or room_centre(scene, room)
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


def is_duct(scene, room_id) -> bool:
    """Is this room a DUCT -- long, narrow and roofed, so a sound in it has
    nowhere to go but along it? Its own measured `extent` decides, at
    `DUCT_ASPECT`; a room the story has not measured is not one, because the
    size tiers are squares and a square is not a passage.

    Only an ENCLOSED room. What makes a corridor carry is its walls and its
    roof; a lane between two buildings under the open sky loses upward
    everything a tunnel keeps, and `exposure` is the word the engine already
    has for the difference."""
    from world import weather as _weather

    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return False
    if _weather.room_exposure(scene, room_id) != "enclosed":
        return False
    extent = room.get("extent")
    if not isinstance(extent, dict):
        return False
    try:
        w, d = float(extent.get("w") or 0), float(extent.get("d") or 0)
    except (TypeError, ValueError):
        return False
    if w <= 0 or d <= 0:
        return False
    return max(w, d) / min(w, d) >= DUCT_ASPECT


def duct_step_scale(scene, rooms) -> dict:
    """`{room_id: what a pace inside it costs a sound}` for the rooms a
    field placed -- `DUCT_STEP` in a duct and 1 everywhere else. Sparse: a
    field with no duct on it gets `{}` and floods exactly as it always
    did."""
    return {rid: DUCT_STEP for rid in (rooms or ()) if is_duct(scene, rid)}


def _still_night(scene, scoped) -> bool:
    """Dark sky over the room and no wind reaching it. The phase is the one
    the scene carries (`day_phase`, what the light field reads); a scene
    with none is not a night."""
    phase = str((scene or {}).get("day_phase") or "").strip()
    if not phase:
        return False
    from world.day_cycle import sun_light
    from world.weather import normalize_weather
    if sun_light(phase, normalize_weather((scene or {}).get("weather"))
                 or None) != "dark":
        return False
    scoped = scoped if isinstance(scoped, dict) else {}
    if scoped.get("wind_reaches") and str(scoped.get("wind") or "") in WIND_NOISE:
        return False
    return True


def _ambient_floor(scene, room_id) -> float:
    """AMBIENT[exposure] plus the weather the room can hear (§ 4.6)."""
    from world import weather as _weather
    exposure = _weather.room_exposure(scene, room_id)
    floor = AMBIENT.get(exposure, AMBIENT["enclosed"])
    # THE DECLARED QUIET SCALES THE PLACE'S OWN FLOOR AND NOTHING ELSE.
    # The weather below is added AFTER, because rain on a dead room is
    # still rain -- what the word says is that the room contributes no
    # noise of its own, not that the world has stopped reaching it.
    quiet = room_quiet(scene, room_id)
    if quiet:
        floor *= QUIET_SCALE[quiet]
    try:
        scoped = _weather.weather_for_room(scene, room_id)
    except Exception:
        scoped = {}
    # A STILL NIGHT IN THE OPEN IS HUSHED. `AMBIENT["open"]` is the open
    # air by day (§ 1.120: open air is not itself a noise; the weather is
    # counted separately), and a night with no wind on it is quieter than
    # any room with a fire and a clock -- about 25 dB(A) against a quiet
    # room's 30. Owner's retune 2026-09-14: a "faint" creature dragging
    # itself a few paces off in a dead fen night was refused at the day
    # floor, and a listener at an open door hears that. The same lever a
    # declared `quiet` uses (`QUIET_SCALE["hushed"]`, -6 dB), applied only
    # where the sky is dark and no wind reaches the room, so the day floors
    # and every pinned reach stand.
    if (not quiet and exposure != "enclosed"
            and _still_night(scene, scoped)):
        floor *= QUIET_SCALE["hushed"]
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
        # THE RING, ROOM BY ROOM: a bare room's reverberant field, as a gain
        # relative to the one-pace level, or None (`room_reverberation`).
        self.reverb = {room: room_reverberation(scene, room)
                       for room in grid.offsets}
        self._rev_spreads = {}
        # WHAT A PACE COSTS, ROOM BY ROOM. A duct carries a sound further
        # than the same length of hall (`DUCT_STEP`), and every other room
        # is unchanged, so a field with no duct on it floods byte for byte
        # as it did.
        self.step_scale = duct_step_scale(scene, grid.offsets)

    # -- geometry -----------------------------------------------------------

    def spread_from(self, cell) -> dict:
        if cell not in self._spreads:
            self._spreads[cell] = spread(self.grid, cell,
                                         step_scale=self.step_scale)
        return self._spreads[cell]

    def locate(self, name, room=None):
        """A body's cell on this field, or None when its room is not placed
        here. An unmeasured body stands at its room's centre -- the same
        approximation `_relative_sector` and `_observer_cell` make."""
        room = room or room_of(self.scene, name)
        if not room or room not in self.grid.offsets:
            return None
        cell = body_cell(self.scene, name) or room_centre(self.scene, room)
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
            # THE LOUDER OF THE TWO WAYS THE SOUND ARRIVES: straight, or off
            # the walls of a room that rings (`rev_gain`).
            return max(gain_at(field.spread_from(s), l),
                       field.rev_gain(str(s_room), l))
        return None

    # -- reverberation ------------------------------------------------------

    def rev_gain(self, source_room, cell) -> float:
        """The reverberant field a source in `source_room` puts at `cell`:
        the room's ring everywhere inside it, and beyond each of its
        openings the ring at the opening spread on as any sound is. Zero
        where the room does not ring."""
        rev = self.reverb.get(str(source_room))
        if not rev:
            return 0.0
        if self.grid.inside.get(cell) == str(source_room):
            return float(rev["gain"])
        if source_room not in self._rev_spreads:
            spreads = []
            for other in sorted(self.grid.offsets):
                if other == source_room:
                    continue
                cells, _bearing = _door_cells(self.scene, source_room, other)
                for door in cells or ():
                    at = self.grid.cell_of(source_room, door)
                    if at in self.grid.inside:
                        spreads.append(self.spread_from(at))
            self._rev_spreads[source_room] = spreads
        best = 0.0
        for spread_map in self._rev_spreads[source_room]:
            best = max(best, gain_at(spread_map, cell))
        return float(rev["gain"]) * best

    def gain_parts(self, speaker, listener, *, speaker_room=None,
                   listener_room=None):
        """(direct, reverberant) gains between two bodies, or None."""
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
            return gain_at(field.spread_from(s), l), field.rev_gain(str(s_room), l)
        return None

    # -- intensity ----------------------------------------------------------

    def intensity_at(self, source, cell) -> float:
        direct = gain_at(self.spread_from(source["at"]), cell)
        return source["power"] * max(direct, self.rev_gain(source["room"], cell))

    def noise_at(self, listener, *, exclude=(), room=None) -> Optional[float]:
        """The listener's NOISE (§ 4.4): every placed source's intensity at
        the listener's cell except those in `exclude` (ids, or the name of a
        body whose speech is the signal) AND except any source standing
        where an excluded one stands, plus the room's ambient floor.

        A SOUND IS NOT MASKED BY A SOUND ARRIVING FROM ITS OWN PLACE. Two
        noises made at one spot reach an ear as one louder noise from that
        spot; what an ear cannot do with them is tell them apart, and the
        model's word for that is `fragment` against `full`, not silence.
        Counting each as the other's noise says the opposite, and says it
        with force: a ratio test gives every source `1 / (N - 1)` of the
        din, so two equal sounds in one place are marginal and THREE ARE
        INAUDIBLE AT ANY VOLUME -- measured, three sources of power 100
        against an ambient of 0.05, all three `none`.

        It is not a corner. A beat's sound events are all placed at their
        room's centre (`sound_sources`), because a one-off noise says which
        room it was in and nothing finer, so every pair of events in one
        room lands on one cell by construction. Measured in the descent run
        (chat 117, turn 13): a pry bar on a door frame and a detonation
        overhead, both `loud`, both in the service spine, and the containment
        annex through the open door beside it heard neither -- while either
        one alone was `full` there.
        """
        cell = self.locate(listener, room)
        if cell is None:
            return None
        skip = {str(x).strip().casefold() for x in exclude if x}
        at_hand = {(source["room"], tuple(source["cell"]))
                   for source in self.sources
                   if source["id"].casefold() in skip
                   or source["id"].casefold().removeprefix("speech:") in skip}
        total = self.ambient.get(self.grid.inside[cell], AMBIENT["enclosed"])
        for source in self.sources:
            sid = source["id"].casefold()
            if sid in skip or sid.removeprefix("speech:") in skip:
                continue
            if (source["room"], tuple(source["cell"])) in at_hand:
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
        return quantise_hearing_db(db_of_power(signal), db_of_power(noise))

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
    """The key is the WHOLE READ SET (review B10). Two of these were guesses
    at what a sound field depends on rather than a record of it, and both
    were short:

    * `crossings` was read and unnamed. A body with a live threshold
      crossing and no station stands at the door anchor it came through
      (`effective_station`), and a source it carries is heard from there;
      measured, the pump moved from (3,3) to (4,3) when the crossing
      appeared, and the memo went on answering (3,3).
    * the entity table was projected down to the entities that SOUND, and
      the derivation reads every entity's names and aliases -- that is how a
      body touching a room feature gets seated at it (`_anchor_for_entity`).
      An entity that makes no noise still moves the noise: dropping the
      brazier's alias moved the same source from (1,2) to (3,3).

    So the scene goes in as the sub-blobs the derivation reads, entities
    entire. A field that neither sounds nor shines is not a smaller read
    set, only a smaller guess at one.

    AND THE READ SET IS STATED ONCE, in `scene_memo.SCENE_READS`, rather
    than spelled a third time here (the Section I residual of review C12).
    Spelled again, this one was short by "passages", "orientation", "poses"
    and the beat index -- and a hand-written list is short by whatever its
    author did not think of, which is the whole reason there is now one
    list. Measured on the passage key: two rooms one doorway apart, the
    doorway's barrier living on the passage record rather than on either
    edge, flipped to `wall` -- the cache went on answering a shout at
    `full` through it, pair gain 0.02117 where the right answer is no
    field-borne channel at all; flipped to `closed_door` the same gain
    should fall to 0.00529 and did not move. A passage's `width` is the
    same class: 1 pace against 8 moved the pair gain 0.02117 -> 0.02703
    and the door gain 0.06477 -> 0.1.
    """
    parts = [room_id, turn_idx, crowds, events, speakers,
             *scene_read_parts(scene)]
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _room_grid_exists(scene, room):
    """The grid gate, from the module that owns it. Imported per call rather
    than at module scope because `spatial_light_field` reads this module's
    ladders at import time."""
    from world.spatial_light_field import light_geometry_exists
    return light_geometry_exists(scene, room)


def sound_field(scene: dict, listener: str, *, room=None, turn_idx=None,
                crowds=None, events=None, speakers=None) -> Optional[SoundField]:
    """The sound field one listener hears the scene through, or None when
    the listener's room carries no geometry (§ 7's fail-open: no field, and
    every reader falls back to today's functions unchanged).

    Cached on everything it reads -- the rooms, positions, stations,
    contacts, containment, crossings, weather, the entities, the turn index
    and the extra sources -- so one stage pays the spreads once per
    listener. THE KEY DECIDES A HIT ALONE (`_cache_key`, review B10): the
    field is a pure function of it, so a scene that answers it identically
    gets the field already built, and no scene that answers it differently
    can be handed one.

    TWO LEVELS since review C12, for the reason `light_field` gives: the key
    `json.dumps`ed the scene on every lookup, hit or miss. The outer level
    is the read-pass memo (`world/scene_memo.py`) -- only the per-call
    extras (the turn index, crowds, events, speakers) are serialised into
    its key, and they are a handful of rows rather than the whole scene.
    The inner content cache below still catches a re-read scene."""
    room = room or room_of(scene, listener)
    # THE SAME GATE THE LIGHT FIELD USES. `room_has_geometry` is the FOV
    # layer's opt-in for the furniture sentence and asks whether an ANCHOR
    # carries an authored height -- a counter to shadow with. Measured across
    # the owner's 580 live rooms it answers TRUE FOR FOUR, so the near field
    # -- the spreading loss, the listener's noise floor, the masking rule,
    # the aperture losses -- was running for 0.7% of the world and everything
    # else fell back to the barrier-only edge model, which has no distance
    # within a room and no noise floor at all. That is not a narrower model,
    # it is a coarser one.
    #
    # Sound needs a GRID and somewhere to put the source, which a size tier
    # or an extent is; 336 of 580 rooms have one. The light field widened for
    # exactly this and said why ("light needs a grid and a place for the
    # source, not a counter to shadow with"), and the owner's ruling of
    # 2026-09-06 is that the most realistic sound travel is the point and a
    # room estimated from its size tier is an acceptable estimate.
    if not room or not _room_grid_exists(scene, room):
        return None
    extras = json.dumps([turn_idx, crowds, events, speakers],
                        sort_keys=True, default=str)
    return scene_memo(
        scene, ("sound_field", str(room), extras),
        lambda: _sound_field(scene, room, turn_idx, crowds, events, speakers))


def _sound_field(scene, room, turn_idx, crowds, events, speakers):
    """The field itself, content-cached across scene objects."""
    key = _cache_key(scene, room, turn_idx, crowds, events, speakers)
    cached = _SOUND_FIELD_CACHE.get(key)
    if cached is not None:
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


def far_path_gain(scene, listener_room, source_room):
    """The path gain from one ROOM to another over the room graph, or None
    where the question does not apply (same room, a room the scene does not
    hold). `0.0` is an ANSWER -- the rooms exist and no speech-scale sound
    gets from one to the other -- and is the answer `door_gain` could not
    give.

    THE ROOM GRAPH ANSWERS WHERE THE COMPOSITE FIELD CANNOT. A near field is
    a cell grid over the listener's room and the neighbours it can place; a
    pair further apart than that used to fall through to the edge model,
    whose word for it is `separated`, and from there to `door_gain` -- the
    best opening this room has, which is a CEILING and knows nothing about
    distance. Measured on synthetic chains of medium rooms joined by open
    doorways, `door_gain` returns 0.1131 at two hops, three hops, four and
    five, so `hear_level` answered `fragment` for a shout at every distance
    beyond adjacent, and the same for one four rooms further. The flood's
    loss over the same chain grows 22.1, 26.0, 29.0, 31.4, 33.4 dB.

    Live, chat 117 turn 49: Aurel shouted Sarah's name three rooms down a
    straight run of open doorways and her view carried no trace of it, while
    the flood put the same shout in her room at 31.6 dB over a 27.0 floor.
    She had stopped following instructions for four beats because the engine
    never delivered one, and she explained it in character -- "I filtered
    out vocalizations below alarm threshold" -- which is how a defect like
    this stays invisible.

    LOSS IS INDEPENDENT OF THE SOURCE LEVEL (spreading plus barriers, both
    subtractive in dB), so the probe level cancels and the gain this returns
    grades any volume. The probe is a shout because the flood terminates on
    AUDIBILITY: past where a shout dies, nothing anyone says is audible
    anyway, and the walk should stop rather than keep paying for rooms.

    Cost, measured 2026-09-06: 0.16 ms on the descent scene (22 rooms), 3.8
    ms on a 570-room chain -- the worst case the author's corpus could
    offer. Uncached deliberately; a memo keyed on the room graph is the
    answer if a big map ever measures badly.
    """
    rooms = (scene or {}).get("rooms") or {}
    listener_room, source_room = str(listener_room or ""), str(source_room or "")
    if not listener_room or not source_room or listener_room == source_room:
        return None
    if listener_room not in rooms or source_room not in rooms:
        return None
    # ADJACENT IS THE EDGE MODEL'S, AND STAYS ITS. This answers the case
    # that had no distance in it at all -- `separated`, one word for every
    # room beyond the next. Two rooms sharing an edge already have a barrier
    # to be graded by, tuned per barrier, and a wall between neighbours is a
    # thing the edge rules say something deliberate about; the flood would
    # overrule that with a coarser reading of the same single hop for no
    # gain, since there is no distance to be wrong about across one edge.
    from world.spatial_senses import rooms_adjacent
    if rooms_adjacent(scene, listener_room, source_room):
        return None
    probe = SPEECH_DB["shout"]
    rec = room_sound_flood(scene, source_room, probe).get(listener_room)
    if rec is None:
        # The flood terminates on audibility, so "no record" is two
        # different facts: the rooms are joined and a shout dies before it
        # arrives (0.0, an answer), or NO chain of edges joins them at all
        # -- another world, a ship in orbit -- and the question does not
        # apply (None). Answering 0.0 for the second stamped `signal` on a
        # pair the air has no relationship to, and the composer's device
        # rescue, which is gated on the air having no answer, was withdrawn
        # for exactly the hail it exists for.
        return 0.0 if _rooms_joined(scene, listener_room, source_room) else None
    return ratio_of_db(float(rec["db"]) - probe)


def _rooms_joined(scene, a, b) -> bool:
    """Is there ANY chain of declared edges between these rooms, whatever the
    barriers. Connectivity, not passability: a wall is a relationship."""
    from world.spatial_barriers import neighbor_map
    graph = neighbor_map(scene, None)
    seen = {str(a)}
    frontier = [str(a)]
    while frontier:
        nxt = []
        for room_id in frontier:
            for other in graph.get(room_id, ()):
                other = str(other)
                if other == str(b):
                    return True
                if other not in seen:
                    seen.add(other)
                    nxt.append(other)
        frontier = nxt
    return False


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
        # THE RING OVER THE VOICE. When the reverberant part arrives
        # `REVERB_SMEAR_DB` above the direct part, the words smear and the
        # direction is gone (`hear_level` grades it, `_bearing_through`
        # says where it seems to come from). An echo is the room's own:
        # a bare room long enough gives a sharp sound back.
        parts = sound.gain_parts(target, observer, speaker_room=target_room,
                                 listener_room=observer_room)
        if parts is not None:
            direct, rev = parts
            if rev > 0.0 and rev >= direct * ratio_of_db(REVERB_SMEAR_DB):
                rel["reverberant"] = True
        ring = room_reverberation(scene, o_room)
        if ring and ring.get("echo") and str(o_room) == str(t_room):
            rel["echo"] = True
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
    # THE ROOM GRAPH, BEFORE THE CEILING. `door_gain` is what this room's
    # best opening could deliver and says nothing about how far away the
    # speaker is; the flood says exactly that (`far_path_gain`). Stamped as
    # the signal so the FIELD branch of `hear_level` grades the pair -- the
    # masking rule, the door ceiling below and `_weaker_hearing` all keep
    # working unchanged, and the edge model's distance-blind `separated`
    # word stops being reached for a pair whose rooms the scene holds.
    #
    # It only ever SUBTRACTS at the boundary: at one hop, where both
    # readings exist, the composite field measured 0.0191 and the flood
    # 0.0062, because the flood charges whole room spans where the field
    # walks cells. The conservative one is the one that arrives late.
    far = far_path_gain(scene, o_room, t_room)
    if far is not None:
        rel["signal"] = far
        rel["noise"] = noise
        if door is not None and door > 0.0:
            rel["door_gain"] = door
        return rel
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
# THE EVENT CHANNEL: a sound that HAPPENS (docs/UNBUILT.md § 1.117)
# ---------------------------------------------------------------------------
#
# `sound_source` is a STANDING emission and `state.running` is the switch
# that holds it open. A thing that made a noise ONCE is not a thing that is
# making a noise, and until 2026-09-05 the engine had no word for the
# difference after the opening turn: a bell rung once either became a
# permanent source -- the lighthouse run's fog bell, nine beats of one story
# rewritten by a noise floor of 20.5 against a whisper's 0.34 -- or reached
# nobody at all. The objects hand's clause named the distinction correctly
# and then had nowhere to put the event.
#
# This is the somewhere. A beat's sounds live on the scene under the beat
# that made them and are gone the moment the beat is: no expiry rule, no
# device list, no guessing which kind of thing it was. The beat number IS
# the lifetime.

#: Where a beat's one-off sounds live on the scene, and the only place they
#: do. Beat-scoped by CONSTRUCTION: the record carries the beat that wrote
#: it and `beat_sensory_events` refuses any other, so a stale record cannot
#: outlive its beat even if nothing ever clears it.
SENSORY_EVENTS_KEY = "sensory_events"

#: How many one-beat sounds one beat may hold. A beat is a moment; a moment
#: with nine distinct noises in it is a model filling a list, not a world.
#: Named here because every cap in this engine is named.
MAX_SENSORY_EVENTS = 8


def tread_events(scene: dict, movers) -> list:
    """The beat's footfalls as one-beat sound events: for every body in
    `movers` ({name: pace}) a tread in its own room at `TREAD_LEVEL`, and
    one in every room it lies over with a floor between, at the floor's
    impact level (`FLOOR_IMPACT_DB`, plus `TREAD_RUN_DB` for a run). Events
    reach a listener the way every other beat sound does -- in the room,
    through the near field, and by the far flood -- and their `detail` is
    a sound fact that names nobody. Before 2026-09-15 a man climbing three
    storeys of stone stair made no sound anywhere.
    """
    from language_runtime import compositor_text
    from world.spatial_levels import floor_edges
    rooms = (scene or {}).get("rooms") or {}
    out = []
    for name, pace in sorted((movers or {}).items()):
        room = room_of(scene, name)
        if not room or room not in rooms:
            continue
        running = str(pace or "walk").strip().casefold() == "run"
        tread = compositor_text("sound_tread_run" if running else "sound_tread_walk")
        level = TREAD_LEVEL["run" if running else "walk"]
        out.append({"kind": "sound", "room": str(room), "level": level,
                    "source": str(name), "detail": tread, "tread": True})
        for edge in floor_edges(scene, room):
            if edge.get("vertical") != "down" or edge["to"] not in rooms:
                continue
            material = str((rooms.get(room) or {}).get("floor") or "").strip().casefold()
            level_db = FLOOR_IMPACT_DB.get(material, FLOOR_IMPACT_DB["stone"])
            if running:
                level_db += TREAD_RUN_DB
            out.append({"kind": "sound", "room": str(edge["to"]), "db": float(level_db),
                        "source": str(name), "tread": True,
                        "detail": compositor_text("sound_tread_overhead", tread=tread)})
    return out


def normalize_sensory_event(event, rooms=None) -> Optional[dict]:
    """One `state_diff.sensory_events` entry as the engine holds it, or None
    where it names no room the scene has.

    `{kind, room, level | db, source, detail}` -- the note's shape, and a
    closed set of keys. `kind` is the SENSE the event arrives on and defaults
    to hearing, which is what the channel is for; `level` is a word off
    `SOUND_LEVELS` and `db` the number for anything the words do not reach;
    `source` is what made it and `detail` what it was like. Nothing else
    survives, so a hand that writes prose into a key nobody reads writes it
    into nothing.
    """
    if not isinstance(event, dict):
        return None
    room = str(event.get("room") or event.get("room_id")
               or event.get("source_room") or "").strip()
    if not room or (rooms is not None and room not in rooms):
        return None
    out = {"kind": str(event.get("kind") or "sound").strip().casefold()[:32],
           "room": room,
           "source": " ".join(str(event.get("source") or "").split())[:80],
           "detail": " ".join(str(event.get("detail")
                                  or event.get("desc")
                                  or event.get("description") or "").split())[:200]}
    level = normalize_sound_level(event.get("level"))
    if level:
        out["level"] = level
    raw = event.get("db")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        out["db"] = float(raw)
    if "level" not in out and "db" not in out:
        raw = event.get("intensity")
        if raw not in (None, ""):
            out["intensity"] = raw
    if event.get("tread"):
        out["tread"] = True             # a footfall: its maker does not hear it as news
    # A BARE ROOM LONG ENOUGH GIVES A SHARP SOUND BACK (`room_reverberation`).
    if rooms is not None:
        ring = room_reverberation({"rooms": rooms}, room)
        if ring and ring.get("echo"):
            out["echo"] = True
    return out


def beat_sensory_events(scene: dict, turn_idx) -> list:
    """This beat's one-off sounds, and only this beat's. `[]` for any other
    beat, for a scene that holds none, and for a reader with no beat to ask
    about -- the field may only subtract on evidence it has."""
    record = (scene or {}).get(SENSORY_EVENTS_KEY)
    if not isinstance(record, dict) or turn_idx is None:
        return []
    try:
        beat = int(record.get("beat"))
    except (TypeError, ValueError):
        return []
    if beat != int(turn_idx):
        return []
    events = record.get("events")
    return [e for e in events if isinstance(e, dict)] \
        if isinstance(events, list) else []


# ---------------------------------------------------------------------------
# THE FAR FIELD (DESIGN_SOUND_DECIBELS.md § 2C, built 2026-09-05)
# ---------------------------------------------------------------------------
#
# The near field above is ONE HOP WIDE: `room_field` lays the listener's room
# and the neighbours placed beyond its own doorways, and nothing further. So
# until today a sound two rooms away was not quiet -- it was ABSENT, and no
# constant could change that. The far field is the answer, and it is a
# different model on purpose:
#
#   * the NEAR field is cells. It knows where the counter is, which doorway
#     the path went round, and who is standing behind what. It is the whole
#     answer inside the rooms it lays, and it stays that.
#   * the FAR field is ROOMS. Beyond the near field's edge there is no cell
#     path to walk, and a sound that has crossed two buildings does not need
#     one: what survives that far is a direction and a character, never a
#     placement. So it floods the room graph by Dijkstra on ACCUMULATED LOSS
#     in dB -- each room crossed costing the spreading loss of its own span,
#     each edge its barrier's transmission loss -- and answers only for the
#     rooms the near field could not reach.
#
# WHICH MEANS THE TWO NEVER ARGUE. The boundary is where authority hands
# over, not where two models disagree about a neighbour: every room on the
# listener's own composite is the near field's, and the far field is asked
# only about rooms beyond it. That is what "they agree at the boundary"
# has to mean between a cell model and a room model, and it is pinned.
#
# AND IT COSTS NOTHING ON A QUIET BEAT. Nothing under `FAR_FIELD_ENTRY_DB`
# enters it and no voice ever does (`far_field_sources` drops speech by
# kind), so a beat of conversation beside a hearth walks no graph at all:
# `distant_sounds` returns before it builds anything. A beat with a running
# engine or a klaxon in it (`loud` and up on the real ladder, since
# 2026-09-14) walks the room graph once per such source, which is a
# Dijkstra over a few dozen rooms on a cached graph.

#: What a solid partition passes. THE ONE GENUINELY NEW NUMBER
#: (`DESIGN_SOUND_DECIBELS.md` § 5): a wall used to pass NOTHING, which was
#: right for sight -- the table was borrowed from it -- and meant no
#: explosion, ever, was heard through one by anybody. A wall attenuates; it
#: does not abolish. 45 dB is the note's proposal and a real masonry wall.
#:
#: RESOLVED 2026-09-05, AND IT WAS A UNIT, NOT A JUDGEMENT. 45 was entered
#: as the real-world transmission loss of a masonry wall, and every other
#: number in this table was then on a DIFFERENT SCALE: the aperture losses
#: are derived from `APERTURE_PASS`, which was calibrated against the near
#: field's own sentences, and the speech ladder of the day had "the ratio a
#: real voice has" only in ORDER, not in span -- whisper->shout was 20.8 dB
#: against 58 in the world, a compression of 0.358, and every aperture sat
#: on that scale (window 10.0 against a real 28 scaled to 10.0, exactly;
#: open_door 0.5 against 0.7; membrane 3.0 against 1.8; closed_door 6.0
#: against 9.0). A real 45 dB wall, compressed, is 16, and that is what
#: shipped.
#:
#: THE 2026-09-14 RECALIBRATION MOVED THIS TABLE TOO, later the same day
#: (45 for a masonry wall, 50 for a floor, the apertures above at real
#: losses), because the mixed state it first left had a direction: the emission ladders are real levels and the aperture
#: and partition losses are the compressed ones calibrated against the old
#: ladder. Stated rather than hidden, because it has a direction: an
#: opening or a wall passes a real voice more readily than a real one would.
#: A closed door at 6.0 dB against a real solid door's 25 lets a normal line
#: three paces behind it through `full` (63 - 6 - 10 = 47 against the 27.0
#: floor), and a `thunderous` event crosses more walls at 16 than thunder
#: crosses at 45. Moving the losses to real transmission values is one
#: decision with a measured consequence for every doorway in every story,
#: and it is registered for the owner in `docs/UNBUILT.md` rather than taken
#: here; `tests/test_sound_field.py::test_every_barrier_in_the_table_is_on_
#: one_scale` pins the mixed state so the next edit meets it knowingly.
#:
#: WHAT 16 BOUGHT on the old ladder, measured through medium rooms against
#: the 27.0 dB floor: before, only `catastrophic` crossed one wall and
#: NOTHING crossed two, so a collapsing roof two rooms away was silent;
#: after, `thunderous` carried through two walls, `catastrophic` through
#: three, `deafening` crossed one and a `loud` event none. On the real
#: ladder the same wall passes more: an 83 dB engine is heard through one
#: wall of the next room (83 - 16 - 21.6 = 45.4 against 27.0) and a
#: `deafening` klaxon through two.
WALL_LOSS_DB = 45.0

#: A floor or a ceiling: an edge that goes up or down and is a wall rather
#: than a passage. A stairwell, a hatch or an open gallery is an APERTURE
#: and keeps its own loss -- a vertical passage's barrier already has one --
#: so this is only ever charged where the two rooms are stacked and nothing
#: joins them. On the same compressed scale as the wall above: a real 50 dB
#: concrete floor is 18 here, and it stays the heavier of the two.
FLOOR_CEILING_LOSS_DB = 50.0

#: What a barrier with nothing usable on it costs. A wall: the far field
#: fails toward LESS reach, which is the direction every guard here fails.
_UNKNOWN_BARRIER_LOSS_DB = WALL_LOSS_DB

#: The level a source must hold at its cell before the far field is built
#: at all. Set 2026-09-05 above the old `deafening` (61.8) so that only the
#: two far rungs reached it; on the real ladder (2026-09-14) it admits a
#: standing `loud` source (83 at the cell: an engine, a mill), `deafening`
#: and the two far rungs, and on the impact ladder `loud` (72) and up -- a
#: hearth fire (53) and a kettle stay near-field things you meet at the
#: door. A voice never enters, at any volume, and not because of this number
#: (a shout is 85 at its cell): `far_field_sources` refuses speech by kind.
#: That is not a performance guard bolted on: it is the same sentence as
#: "incredibly loud noises travel very far", read from the other end.
FAR_FIELD_ENTRY_DB = 70.0

#: How a sound from beyond the near field ARRIVES, by its margin over the
#: listening room's own noise floor. A closed set the engine owns, three
#: words, and deliberately NOT the hearing ladder: `full` on that ladder
#: means the words came through, and no distant sound ever carries words.
DISTANT_LEVELS = ("faint", "plain", "overwhelming")

#: The margin at which a distant sound stops being something you notice and
#: becomes something you cannot do anything else through. 20 dB is a
#: hundredfold over the room. The owner's, like every constant here.
OVERWHELMING_MARGIN_DB = 20.0


def _edge_loss_db(edge) -> float:
    """One edge's transmission loss in dB, after the material shift. An
    aperture costs what the near field's table charges it; a wall costs
    `WALL_LOSS_DB`, or `FLOOR_CEILING_LOSS_DB` where the edge also goes up
    or down and so is a floor rather than a partition."""
    from world.spatial_geometry import normalize_vertical
    shifted = _material_shifted_barrier(
        normalize_barrier(edge.get("barrier")), edge.get("material"))
    if shifted in APERTURE_LOSS_DB:
        return APERTURE_LOSS_DB[shifted]
    if normalize_vertical(edge.get("vertical")):
        return FLOOR_CEILING_LOSS_DB
    if shifted == "wall":
        return WALL_LOSS_DB
    return _UNKNOWN_BARRIER_LOSS_DB


def far_field_graph(scene: dict) -> dict:
    """`{room: {other: loss_db}}` -- the room graph a loud sound crosses,
    UNDIRECTED and with every edge on it.

    Undirected for the reason `one_opening_away` is: a doorway is one object
    and may be declared from either side, and a path has no direction. Where
    both sides declare it and disagree, the SMALLER loss wins -- the same
    permissive reading the opening floor takes, and the one that cannot
    silence a sound because of which room's author was more careful.

    Every edge, not only the ones sound walks: a wall is on this graph, at
    `WALL_LOSS_DB`, which is the whole point of the far field. The number
    is the constant's to state and is not repeated here (E26, 2026-09-07:
    this still read "45 dB" after the 2026-09-05 re-denomination to 16).

    CACHED ON THE SCENE OBJECT, because building it is the whole cost of a
    loud beat: `effective_adjacent` resolves passages scene-wide and costs
    about 8 ms a room, so a 600-room scene spent 543 ms here and 41 ms in
    the flood it feeds. The cache is held by identity, like the sound
    field's -- one beat's scene is one object, read many times and mutated
    by nobody while it is being read.
    """
    rooms = (scene or {}).get("rooms") or {}
    hit = _FAR_GRAPH_CACHE.get(id(scene))
    if hit is not None and hit[0] is scene and hit[1] is rooms:
        return hit[2]
    graph = _build_far_field_graph(scene, rooms)
    if len(_FAR_GRAPH_CACHE) >= _FAR_GRAPH_CACHE_MAX:
        _FAR_GRAPH_CACHE.clear()
    #: The scene is held, not just its id, so the id cannot be recycled onto
    #: another object while this entry stands.
    _FAR_GRAPH_CACHE[id(scene)] = (scene, rooms, graph)
    return graph


#: How many scenes' room graphs to remember. Small: the readers of one beat
#: share one scene object, and a stale entry is impossible rather than
#: unlikely (the entry is checked by identity of the scene AND of its rooms).
_FAR_GRAPH_CACHE: dict = {}
_FAR_GRAPH_CACHE_MAX = 8


def _build_far_field_graph(scene, rooms) -> dict:
    from world.spatial_barriers import effective_adjacent
    graph: dict = {room: {} for room in rooms}
    for room in sorted(rooms):
        for edge in effective_adjacent(scene, room) or ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            other = str(edge["to"])
            if other not in rooms or other == str(room):
                continue
            loss = _edge_loss_db(edge)
            for a, b in ((str(room), other), (other, str(room))):
                known = graph[a].get(b)
                if known is None or loss < known:
                    graph[a][b] = loss
        # A FLOOR IS AN EDGE TO A SOUND. Two rooms stacked with no stair
        # between them (`over`) share a floor the far field crosses at the
        # floor's loss -- a timber floor passes a shout and a heavy tread,
        # masonry passes almost nothing (`spatial_levels.floor_edges`).
        from world.spatial_levels import floor_edges
        for edge in floor_edges(scene, room):
            other = str(edge["to"])
            if other not in rooms:
                continue
            loss = edge.get("loss_db")
            loss = float(loss) if loss is not None else FLOOR_CEILING_LOSS_DB
            for a, b in ((str(room), other), (other, str(room))):
                known = graph[a].get(b)
                if known is None or loss < known:
                    graph[a][b] = loss
    return graph


def room_span(scene: dict, room_id) -> float:
    """How far a sound travels crossing this room, in paces: its `extent`
    where one is written, its size tier's side where none is. The engine's
    OWN conversion (`spatial_fov.grid_side` -> `room_grid`), not a second
    one -- 0 of 589 live rooms carried an extent when this was measured, so
    the tier is what the far field will actually run on, and the day extents
    are written the far field gets them for nothing.

    A DUCT IS SHORTER TO A SOUND THAN IT IS TO A BODY (`DUCT_STEP`, the same
    rule the near field's flood charges per pace). This is the room-graph
    scale of it: a corridor's whole length costs a sound half of what an
    open room's does, because the walls stop it going anywhere else. One
    derivation, two scales -- `is_duct` answers both.

    Why it matters more here than in the near field: the far field charges
    EVERY room on the path its whole span, source's own included, so a
    corridor between two places was the most expensive thing a sound could
    cross when it should be the cheapest. Measured on the descent story
    (chat 117): a `loud` 56 dB clang in a 20-pace plant room arrived at 30.0
    dB having crossed only its OWN room, which is under the 27 dB floor of
    the next room across any barrier at all -- so nothing between the
    adjacent room and a cannon was ever audible anywhere.
    """
    span = float(grid_side(scene, room_id))
    return span * DUCT_STEP if is_duct(scene, room_id) else span


#: Below this level nothing anywhere can hear a sound, whatever room it
#: reaches: the quietest floor THIS SCENE has, taken at the `fragment`
#: margin, or the absolute floor, whichever is higher. It is what makes the
#: flood terminate on AUDIBILITY and need no hop cap: loss only accumulates,
#: so once a room is under this, no room beyond it can be over it.
#:
#: It reads the scene because `quiet` broke the invariant it used to rest
#: on. The old cutoff was `AMBIENT["enclosed"]` and the comment said why --
#: "weather and sources only ever ADD to a floor" -- which stopped being
#: true the moment a room could declare itself quieter than the constant.
#: Left alone it would have cut the flood at 27 dB while a `dead` room four
#: hops out was listening at 15, and that room would have been deaf to
#: everything for the rest of the story with no warning anywhere. A scene
#: that declares no quiet takes exactly the old number, so nothing that
#: does not use the word can move.
def _gate_db(floor: float) -> float:
    """The lowest level a room with this noise floor can hear at all: the
    `fragment` margin over its own noise, or the absolute floor -- which is
    itself taken against the room, `quantise_hearing_db`'s rule -- whichever
    is higher. Written out because the flood's cutoff and the grader have to
    agree about it, and they used to agree only by both spelling
    `HEAR_FLOOR_DB`."""
    return max(db_of_power(floor) + FRAGMENT_SNR_DB,
               min(HEAR_FLOOR_DB, db_of_power(floor)))


def _inaudible_everywhere_db(scene=None) -> float:
    cut = _gate_db(AMBIENT["enclosed"])
    for room in ((scene or {}).get("rooms") or {}).values():
        if not isinstance(room, dict):
            continue
        word = normalize_quiet(room.get("quiet"))
        if word:
            cut = min(cut, _gate_db(AMBIENT["enclosed"] * QUIET_SCALE[word]))
    return cut


def ring_boost_db(scene: dict, room_id) -> float:
    """How much louder a room that rings hands its walls than the direct
    sound crossing it would be: the reverberant gain less the spreading
    the far field would otherwise charge for the room's span, never below
    nothing. The one term a bare room adds to the far field, applied at
    its entry and at the flood's start alike (`room_reverberation`)."""
    ring = room_reverberation(scene, room_id)
    if not ring:
        return 0.0
    return max(0.0, float(ring["gain_db"]) + spreading_loss_db(room_span(scene, room_id)))


def room_sound_flood(scene: dict, source_room, source_db: float) -> dict:
    """`{room_id: {"db", "length", "barrier_db", "via"}}` for every room a
    sound of `source_db` at one pace can still be heard in, `via` being the
    room it arrives FROM (the last hop, which is the direction a listener
    there would turn).

    Dijkstra minimising ACCUMULATED LOSS. A room's level is
    `source_db - barrier_db - spreading_loss_db(length)`, where `length` is
    the sum of the spans of every room on the path, source's own included,
    and `barrier_db` the sum of the edges' losses. Both terms only ever
    grow, so the priority is monotone and the flood may stop expanding a
    room the moment it falls under `_inaudible_everywhere_db(scene)`.

    NO HOP CAP, and none is wanted: the termination is AUDIBILITY, which is
    the physically meaningful bound and the one that makes the reach of a
    sound a property of how loud it is rather than of a constant. A
    `catastrophic` event crosses about fifty medium rooms of open doorways
    and stops; a `thunderous` one about thirty; a wall ends either in one
    hop. What bounds the cost is the arithmetic, not a counter.

    LABEL-CORRECTING rather than settle-once, because the loss is a sum of
    two terms that do not trade off monotonically -- a longer path through
    open doorways can beat a short one through a wall, and the room it beats
    it at may already have been popped. A room is re-expanded only on a
    strict improvement of more than `_DB_EPS`, which is what makes it
    terminate.
    """
    source_room = str(source_room or "")
    rooms = (scene or {}).get("rooms") or {}
    if not source_room or source_room not in rooms:
        return {}
    graph = far_field_graph(scene)
    cut = _inaudible_everywhere_db(scene)
    #: A room's span is derived from its shape, and deriving it lays the
    #: room's cells out. Measured on a 600-room grid: 543 ms without this
    #: memo and 41 ms with it, because a dense graph asks each room's span
    #: once per edge into it rather than once.
    spans: dict = {}

    def span(room_id) -> float:
        if room_id not in spans:
            spans[room_id] = room_span(scene, room_id)
        return spans[room_id]

    span0 = span(source_room)
    # A ROOM THAT RINGS HANDS ITS OPENINGS THE RING, not what is left of the
    # direct sound after crossing it (`room_reverberation`): the level at
    # the source room's walls is the reverberant one, and every room beyond
    # starts from that. `source_db` is raised by the difference, once.
    source_db += ring_boost_db(scene, source_room)
    best = {source_room: {"db": source_db - spreading_loss_db(span0),
                          "length": span0, "barrier_db": 0.0, "via": None}}
    heap = [(-best[source_room]["db"], source_room)]
    while heap:
        neg_db, room = heapq.heappop(heap)
        rec = best.get(room)
        if rec is None or rec["db"] < -neg_db - _DB_EPS:
            continue                    # stale: a louder way here was found
        if rec["db"] < cut:
            continue                    # inaudible here, and beyond it too
        for other in sorted(graph.get(room) or ()):
            barrier = rec["barrier_db"] + graph[room][other]
            length = rec["length"] + span(other)
            level = source_db - barrier - spreading_loss_db(length)
            if level < cut:
                continue
            known = best.get(other)
            if known is not None and known["db"] >= level - _DB_EPS:
                continue
            best[other] = {"db": level, "length": length,
                           "barrier_db": barrier, "via": room}
            heapq.heappush(heap, (-level, other))
    return best


def distant_level_word(level_db: float, floor_db: float) -> Optional[str]:
    """One of `DISTANT_LEVELS` for a sound arriving at `level_db` in a room
    whose noise floor is `floor_db`, or None where it does not arrive at
    all. The same two margins the hearing ladder is quantised by, plus one
    more for the sound there is no doing anything through."""
    # The same "you cannot hear below the room you are in" as
    # `quantise_hearing_db`; `floor_db` is that room's noise.
    if not _at_least(level_db, min(HEAR_FLOOR_DB, floor_db)):
        return None
    if _at_least(level_db, floor_db + OVERWHELMING_MARGIN_DB):
        return "overwhelming"
    if _at_least(level_db, floor_db + FULL_SNR_DB):
        return "plain"
    if _at_least(level_db, floor_db + FRAGMENT_SNR_DB):
        return "faint"
    return None


def far_field_sources(scene: dict, *, turn_idx=None, crowds=None,
                      events=None) -> list:
    """This beat's sources loud enough to enter the far field.

    `speakers` is not a parameter and never will be: A VOICE IS NOT A FAR
    FIELD SOURCE, AT ANY VOLUME. The threshold does not do it -- a real
    shout is 85 dB at its cell against an entry of 70, and until 2026-09-14
    it only happened to (60.8) -- and what this refuses is not a loudness.
    It is the claim that a body two streets away heard a sentence. So
    speech is excluded by CONSTRUCTION, at the only door it could come
    through, and no setting of the constants can open it.
    """
    out = []
    sources, _notices = sound_sources(scene, turn_idx=turn_idx, crowds=crowds,
                                      events=events)
    for source in sources:
        if source.get("kind") == "speech":
            continue                    # never, at any volume. See above.
        level_db = db_of_power(source.get("power"))
        # A ROOM THAT RINGS MAKES A SMALL SOUND A LOUD ONE at its walls
        # (`ring_boost_db`): the entry is judged on what leaves the room.
        if level_db + ring_boost_db(scene, source["room"]) < FAR_FIELD_ENTRY_DB:
            continue
        out.append({**source, "db": level_db})
    return out


def _public_character(source, events) -> str:
    """What a distant listener may be told the sound WAS LIKE -- and nothing
    else. A one-beat event's own `detail`, which is prose the objects hand
    wrote for exactly this: what the noise sounded like.

    A RUNNING ENTITY CONTRIBUTES NOTHING HERE, deliberately. The engine has
    a public description of the THING (`desc`) and none of its SOUND, and
    handing a body three rooms away "a rusted iron bell on an iron bracket"
    would tell them what an object they cannot see LOOKS like. That is a
    sight fact arriving on a hearing channel, which is the same defect as
    seeing through a wall with extra steps. Such a source delivers its
    direction and its level, and the composer says so.
    """
    # A ROOM'S OWN NOISE CARRIES ITS `detail` for the same reason an event's
    # does: it is prose written ABOUT THE SOUND, which is what a body beyond
    # the room is entitled to. The refusal below is about a THING, whose
    # description is a sight fact arriving on a hearing channel.
    if source.get("kind") == "room":
        return " ".join(str(source.get("detail") or "").split())[:200]
    if source.get("kind") != "event":
        return ""
    try:
        idx = int(str(source.get("id", "")).split(":")[1])
    except (IndexError, ValueError):
        return ""
    event = (events or [])[idx] if 0 <= idx < len(events or []) else None
    if not isinstance(event, dict):
        return ""
    return " ".join(str(event.get("detail") or "").split())[:160]


def distant_sounds(scene: dict, listener: str, *, room=None, turn_idx=None,
                   crowds=None, events=None, near_rooms=()) -> list:
    """Every sound from beyond the near field this listener can hear.

    `[{kind: "sound", level, db, character, bearing}]`, loudest first. A
    BEARING AND A CHARACTER, NEVER A SENTENCE AND NEVER A PLACE.

    `near_rooms` is what the listener's own composite already places
    (`SoundField.grid.offsets`): those rooms are the near field's and are
    skipped here, so no listener is ever answered twice about one sound.
    The listener's own room is skipped for the same reason -- a sound where
    it happened is `ambient_percepts`' business.

    WHAT THIS FUNCTION CANNOT RETURN is as much of its contract as what it
    can, and it is a FLOOR rather than a clause -- no configuration, no
    constant and no caller can open any of these:

      * no speech, at any volume (`far_field_sources` refuses the kind);
      * no speaker and no source name (only an event's `detail`, which is
        what the sound was LIKE);
      * NO ROOM. The flood knows which neighbour the sound arrived from and
        that room id never leaves this function: it is turned into a bearing
        HERE, against the listener's own facing and their own room's edge,
        and the bearing dict carries no room id and no room name. A bearing
        is a direction; a direction is not a location; and the difference is
        the whole of what a body two streets away is entitled to.

    The bearing is why this takes a listener rather than a room: which way
    "through the doorway on your left" is depends on which way they are
    facing, and that is the observer's own fact.
    """
    listener_room = str(room or room_of(scene, listener) or "")
    if not listener_room:
        return []
    sources = far_field_sources(scene, turn_idx=turn_idx, crowds=crowds,
                               events=events)
    if not sources:
        return []                       # the ordinary beat: nothing walked
    from world.spatial_senses import sound_bearing_via
    skip = {str(r) for r in near_rooms or ()} | {listener_room}
    floor_db = db_of_power(_ambient_floor(scene, listener_room))
    out = []
    for source in sources:
        if str(source.get("room") or "") in skip:
            continue                    # the near field's, or this room's own
        reached = room_sound_flood(scene, source["room"], source["db"])
        rec = reached.get(listener_room)
        if rec is None:
            continue
        word = distant_level_word(rec["db"], floor_db)
        if word is None:
            continue
        out.append({"kind": "sound", "level": word,
                    "db": round(rec["db"], 1),
                    "character": _public_character(source, events),
                    "bearing": sound_bearing_via(scene, listener, rec["via"],
                                                 room=listener_room)})
    out.sort(key=lambda r: (-r["db"], r["level"]))
    return out


# ---------------------------------------------------------------------------
# The shape of the sound, for the composer (DESIGN_SOUND_FIELD.md § 4b)
# ---------------------------------------------------------------------------

#: The source kinds that STAND in a room, as against the ones that belong to
#: the beat. An `entity` running, a `crowd` at rest and the `room`'s own floor
#: are its tone -- they were there before the beat and are there after it; an
#: `event` is a one-beat sound and a `speech` is a line, and `sound_shape`
#: already refuses to name either as the room's shape for that reason (D3
#: rework, 2026-09-08: a one-beat crash minted a soundscape key and the next
#: quiet beat was then heard as that sound STOPPING).
STANDING_SOURCE_KINDS = frozenset({"entity", "crowd", "room"})


def room_holds_a_standing_source(scene: dict, room) -> bool:
    """Does this room hold a thing that makes a STANDING sound -- running or
    not?

    The question the `ceased` verdict is really asking, and it is about the
    room rather than about this beat: a generator switched off is still a
    generator standing in the room, so its silence is news; a one-beat crash
    leaves nothing behind, so there was never a sound of this room's to
    stop. Declared `sound_source` on an entity placed here, or a crowd at
    rest here -- the two kinds that were sounding before the beat and can go
    on sounding after it.
    """
    from world.spatial_identity import room_of_record

    rid = str(room or "")
    if not rid or not isinstance(scene, dict):
        return False
    for eid, entity in (scene.get("entities") or {}).items():
        if not isinstance(entity, dict) or not entity.get("sound_source"):
            continue
        if room_of_record(scene, eid, entity) == rid:
            return True
    for crowd in (scene.get("crowds") or ()):
        if isinstance(crowd, dict) and str(crowd.get("room") or "") == rid:
            return True
    return False


def _cell_noise(field, room, cell) -> float:
    """The noise floor at one CELL of `room` on this field: the room's
    ambient floor plus every placed source's intensity there.
    `SoundField.noise_at` is the same sum for a BODY -- it locates the
    body's cell first -- and this is the cell asked directly, which is what
    a room-wide sweep needs. One arithmetic, so `sound_shape`'s grading and
    `room_noise_word`'s sweep cannot disagree."""
    total = field.ambient.get(room, AMBIENT["enclosed"])
    for source in field.sources:
        total += field.intensity_at(source, cell)
    return total


def room_noise_word(scene: dict, room: str, *, sound=None) -> Optional[str]:
    """The ONE noise word the whole ROOM carries, or None when its cells do
    not agree on one -- an UNEVEN room, which is `sound_shape` rule (a)
    read from the other side -- and None as well when no field reaches the
    room (no geometry, no cells of its own, a field laid on another room).

    NOT AN OBSERVER'S QUESTION, deliberately (review 2026-09-07 D3, and its
    rework). An even room has nothing to say about WHERE the sound is, so
    `sound_shape` answers None and the shape's own `self` word goes with it
    -- but the question an even room does answer, whether it went even by
    falling quiet or by filling up, is a property of the room's cells and of
    nothing else. Asking a body instead gets a different answer for a body
    the scene cannot place: `SoundField.locate` stands an unmeasured body at
    the room's CENTRE, so a huge dark hall with a generator running at one
    wall grades `quiet` at the middle while the shape refuses to speak for
    want of anything to grade, and "the noise has stopped" reaches a page
    the generator is still running on (measured: a huge hall, a `loud`
    source at the shelf, an unstationed observer). The room's own cells
    cannot say that, and they hold for a measured and an unmeasured
    observer alike.
    """
    if not room:
        return None
    # `sound_field` reads its listener only to resolve a room, and the room
    # is the argument here -- there is no body in this question at all.
    field = sound if sound is not None else sound_field(scene, room,
                                                        room=room)
    if field is None or field.room != room:
        return None
    cells = [c for c, r in field.grid.inside.items() if r == room]
    if not cells:
        return None
    words = {noise_word(_cell_noise(field, room, c)) for c in cells}
    return words.pop() if len(words) == 1 else None


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
        return _cell_noise(field, room, cell)

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
