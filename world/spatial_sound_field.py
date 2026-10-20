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

SPEECH LEFT THE FIELD 2026-10-20 (`DESIGN_SOUND_FIELD.md` § 11, the hearing
rule in `spatial_senses.hear_level`): whether the words of a line arrive is a
table over what stands between two bodies, not signal against noise here.
This module still answers for SOUNDS -- where they reach, how loud at a cell,
what a room's noise is called -- and lends the rule four things: the far
field's loss for a voice rooms away (`far_path`, `far_speech_level`), the
open air's for one across open ground (`open_air_loss_db`), the paces breath
is private by (`_pair_paces`), and the one place noise decides a line, a
deafening source's reach (`masking_db_at`, `masked_level`).
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
    anchor_cells,
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
from world.spatial_senses import (EAR_VOLUME, _material_shifted_barrier,
                                  _SOUND_WALK_BARRIERS)


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
#: (`schemas.SpeechVolume`). Read here, declared there. `ear` -- a breath
#: with the lips at one ear -- since 2026-10-20 (`spatial_senses.EAR_VOLUME`).
SPEECH_VOLUMES = ("ear", "mutter", "whisper", "normal", "loud", "shout")


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
#:   ear      25   a whisper INTO an ear, the lips at it: 20-30 dB(A) at a
#:                 metre-equivalent (the owner, 2026-10-20: "whispering into
#:                 someone's ears is clearly a lot quieter than a normal
#:                 whisper"). It is heard at all only because the lips are
#:                 a few centimetres from that ear -- some 26 dB nearer than
#:                 a metre, so about 50 dB there, plainly -- while a body a
#:                 pace off meets it at a quiet room's own 27 dB, and half
#:                 a metre off a few decibels over it: breath, with no
#:                 voicing to follow. The hearing rule gives it to its
#:                 addressee as a whisper within reach is given, and to
#:                 nobody else by any path (`spatial_senses.EAR_VOLUME`);
#:                 this level is what a reader asking for a number is told
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
SPEECH_ONE_PACE_DB = {"ear": 25.0, "mutter": 38.0, "whisper": 35.0,
                      "normal": 60.0, "loud": 70.0, "shout": 82.0}

#: The same, as the power at the speaker's own cell -- what the flood
#: spreads. Derived, so it cannot drift from the table above.
SPEECH_POWER = {volume: one_pace_power(db)
                for volume, db in SPEECH_ONE_PACE_DB.items()}

#: The speech ladder as a level AT THE CELL -- the one-pace table plus the
#: one-pace loss: ear 28.0 | mutter 41.0 | whisper 38.0 | normal 63.0 |
#: loud 73.0 | shout 85.0. This is the number a budget subtracts a path's
#: loss from; `SPEECH_ONE_PACE_DB` is the number a reader compares to the
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
#:   loud          65   THE LOUDEST EVERYDAY LIFE GETS, in a home, a shop or
#:                      a street: a vacuum cleaner or a television turned up
#:                      is 65-75 dB(A) at a metre, and a kettle's whistle, a
#:                      radio turned up or a busy street sit in the same
#:                      band -- a noise people raise their voices over and
#:                      go on talking. The bottom of the band, for the two
#:                      readers a standing source still has: the noise words
#:                      read a source at its OWN cell, three decibels over a
#:                      pace, which is where a body standing at the thing is
#:                      placed, and a household thing must read a `din`
#:                      there at most (the owner, 2026-10-20: "Ordinary
#:                      household objects should probably be scaled back")
#:                      -- 68 at the cell, and 71 with a second such thing
#:                      beside it, under the 72 `drowned` begins at; and the
#:                      far field's entry (`FAR_FIELD_ENTRY_DB`, 70 at the
#:                      cell) keeps it a thing heard in its own room and the
#:                      next. It was 80 until 2026-10-20 ("an engine at
#:                      idle, a mill, a busy workshop, a vacuum cleaner:
#:                      75-85"), which put a kettle written `loud` at 83 by
#:                      the stove, `drowned` there and heard rooms away
#:                      (chat 176 turn 2). What stops conversation is the
#:                      next rung
#:   deafening    100   a klaxon, a siren, a jackhammer, a chainsaw, a bell
#:                      close up, machinery a voice cannot be raised over:
#:                      95-110 dB(A) -- the class that STOPS conversation (the
#:                      owner, 2026-10-20), and a room you cannot use
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
SOUND_ONE_PACE_DB = {"faint": 40.0, "audible": 50.0, "loud": 65.0,
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
#:   emission (cell)  faint 43.0 | audible 53.0 | loud 68.0 | deafening 103.0
#:   impact   (cell)  faint 45.0 | audible 58.0 | loud 72.0 | deafening 80.0
#:
#: The impact ladder is UNTOUCHED by the 2026-09-14 recalibration: its four
#: lower rungs were authored in dB on 2026-09-06 at the source cell, not at
#: one pace, and are kept byte for byte -- and untouched again on 2026-10-20,
#: when the emission `loud` came down to a household level (68 at the cell;
#: it was 83). Two consequences are stated rather than hidden. The emission
#: ladder sits ABOVE the impact ladder at `deafening` (103 against 80) and,
#: since 2026-10-20, under it at `loud` (a television turned up against a
#: hammer blow at 72); nothing in the model compares the two ladders to each
#: other, so no verdict turns on it, and a real impact ladder (a slammed
#: door is 80-90 at a metre, a hammer on steel over 100) is a separate
#: recalibration registered in `docs/UNBUILT.md`. And the two far rungs are
#: shared, so they moved with `SOUND_POWER`.
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
#: one-pace loss: faint 43.0 | audible 53.0 | loud 68.0 | deafening 103.0 |
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
#:
#: Since 2026-10-20 a voice in one room is not graded against this at all
#: (the hearing rule); it is the QUIET FLOOR a voice from rooms away or
#: across open ground is graded against (`quiet_floor`), and what a sound
#: is heard over, with the weather and the running things on top.
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
#: speech to 3.3 paces. `WIND_NOISE` was deliberately NOT moved then --
#: wind you have to raise your voice over is what wind is, and the run that
#: found this measured rain -- and was raised to real levels on 2026-10-20
#: (`WIND_NOISE_DB`, below).
#:
#: SINCE 2026-10-20 NO WEATHER MASKS A LINE (the hearing rule,
#: `spatial_senses.hear_level`): rain and wind are everyday noise a voice
#: rises over. These levels now shape only how a SOUND is heard (`noise_at`,
#: `level_of`), a distant sound's margin (`distant_level_word`) and the
#: room's noise words; a voice from rooms away is graded against the quiet
#: floor without them (`quiet_floor`).
WEATHER_NOISE = {"light": 0.1, "moderate": 0.25, "heavy": 0.5}

#: WIND AT THE EAR IS NOISE (2026-10-20, wave B2), in dB(A) at the ear of a
#: body the wind reaches (`weather_for_room`'s `wind_reaches`: under the sky
#: or a roof open at its sides, and a `wind` or a `gale`). Wind noise is the
#: turbulence the moving air makes round the head and the outer ear, and it
#: rises steeply with the wind's speed: roughly 50-70 dB(A) in a strong
#: wind, more in a gale -- a wind people stand in and talk by raising their
#: voices, and a gale they have to shout over at arm's length.
#:
#:   wind  60   a strong wind (the Beaufort scale's strong breeze to near
#:              gale: wires whistle, an umbrella is hard to hold): the middle
#:              of that range, and over `DIN_DB` -- a din at the ear, so a
#:              bystander beyond conversational reach catches pieces of a
#:              conversation a few paces off (§ 12.1's rule)
#:   gale  70   a gale (walking into it is hard): the top of the range
#:
#: Until 2026-10-20 these were 34.8 and 40.0 dB -- "wind you have to raise
#: your voice over is what wind is", and both sat under a quiet room's
#: talk. A breeze is not here: it reaches no ear as noise (`wind_reaches`).
#: The owner's rain ruling stands untouched (`WEATHER_NOISE`, 37 dB at its
#: heaviest, is never a din), and no wind reaches a line spoken TO a
#: listener, or within conversational reach: noise never stops people
#: talking to each other (`spatial_senses._bystander_in_a_din`).
WIND_NOISE_DB = {"wind": 60.0, "gale": 70.0}
#: The same as powers, which is what `_ambient_floor` adds. Derived.
WIND_NOISE = {word: power_of_db(level) for word, level in WIND_NOISE_DB.items()}

#: WIND BENDS A SOUND'S REACH (2026-10-20, wave B2; `wind_bend_db`). The
#: wind blows faster a few metres up than at the ground, so downwind the
#: speed of sound grows with height and upwind it falls: a sound travelling
#: WITH the wind is bent back down toward the ground and arrives louder at
#: range, and one travelling AGAINST it is bent up and away, leaving a
#: shadow near the ground that swallows it. Outdoor measurements put the
#: upwind shadow's excess attenuation at 10-20 dB (more at high
#: frequencies) once a path is long enough for a ray to curve off the
#: ground -- the shadow's edge stands some 100-200 m out for a source and a
#: listener a metre or two up in a moderate wind -- and the downwind gain at
#: 2-5 dB; across the wind little changes (Piercy, Embleton & Sutherland
#: 1977; Embleton 1996, "Tutorial on sound propagation outdoors").
#:
#: Outdoors only: a path both of whose ends are under the sky (a room's
#: `exposure` not `enclosed`). The wind's quarter is the weather's
#: `wind_from` (`weather.WIND_FROM_KEY`); a record that names none bends
#: nothing.
#:
#: A path shorter than this is not bent at all: a call across a street, and
#: across any one room the engine lays out (96 paces is 72 m), loses or
#: gains next to nothing -- the owner's ruling that a call carries across a
#: street holds by construction.
WIND_BEND_ONSET_M = 50.0
#: ...and by this length the bend has its full size: it grows with the
#: logarithm of the distance from the onset to here, where the shadow's
#: edge has been passed for any source and listener near the ground.
WIND_BEND_FULL_M = 400.0
#: The most the upwind shadow takes, by the wind's strength word -- the
#: lower half of the measured 10-20 dB for a wind, its middle for a gale,
#: and a few decibels for a breeze, whose gradient is gentle.
WIND_UPWIND_DB = {"breeze": 5.0, "wind": 10.0, "gale": 15.0}
#: The most the downwind side gains: 2-5 dB measured, by strength.
WIND_DOWNWIND_DB = {"breeze": 1.0, "wind": 3.0, "gale": 5.0}

#: Both as levels. They are ADDED to the exposure floor, and levels do not
#: add -- `_ambient_floor` sums the powers and the dB view is taken of the
#: total, which is the one place the conversion has to be careful and the
#: one place real acoustics agrees with it exactly.
WEATHER_NOISE_DB = {word: db_of_power(power)
                    for word, power in WEATHER_NOISE.items()}

#: A crowd's level by its BAND -- the count vocabulary `world/crowds.py`
#: owns. § 3 asked for `audible` when open and `loud` when the crowd's `mood`
#: is a raised one; `mood` is free prose (24 characters, any words), and
#: reading it for loudness would be exactly the word list CLAUDE.md forbids,
#: failing in whichever direction its missing word points. The band is a
#: closed set the engine already grades density by, so a throng is loud and
#: a handful is faint without anyone enumerating English. Whether mood should
#: ALSO raise the level is the note's open question, unchanged. This word is
#: what a crowd IS on the emission ladder -- what the noise words and the far
#: field's character read; how loud its TALK is, and so how far it carries and
#: whom it keeps from following a far table, is `CROWD_BABBLE_DB` below
#: (wave A, 2026-10-20), which fills the crowd's room: a few dozen people are
#: a din there and reach the far field, and a throng drowns its room.
CROWD_SOUND = {"a handful": "faint", "a dozen or so": "audible",
               "a few dozen": "audible", "a throng": "loud"}

#: WHAT A CROWD SOUNDS LIKE WHERE IT STANDS, in dB(A), by the same band --
#: the babble of its talk, which FILLS the room the crowd is in rather than
#: pouring out of its centre (2026-10-20, wave A; `SoundField.intensity_at`).
#: The word above stays what a crowd IS on the emission ladder (what the
#: noise words and the far field's character read); this is how loud its
#: talk is, and it is a real measurement rather than a rung:
#:
#:   a handful       55   two or three quiet conversations in a room
#:   a dozen or so   62   a full table or two; people lean in to talk
#:   a few dozen     68   a busy tavern or dining room
#:   a throng        75   a packed hall, a market at its height
#:
#: Basis: babble from N talkers sums incoherently, about 3 dB a doubling of
#: the people talking at once, and the talkers raise their voices against
#: one another as it climbs (the "cafeteria effect", Lombard escalation):
#: measured restaurants and canteens sit at 60-80 dB(A), a busy one around
#: 70, a packed bar or hall 75-85 (Lebo et al. 1994; Rindel 2012). Until
#: this table a crowd was a point source at its room's centre on the
#: emission ladder, so a few dozen people talking were a 50 dB hearth fire
#: -- quieter than one voice -- and no crowd short of a throng was ever a
#: din anywhere in the room it stood in.
CROWD_BABBLE_DB = {"a handful": 55.0, "a dozen or so": 62.0,
                   "a few dozen": 68.0, "a throng": 75.0}

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
#: `full` when signal >= FULL_SNR * noise, for a SOUND -- a thing running, a
#: crowd, a one-beat event, a distant noise: heard plainly at +3 dB over the
#: room. Kept as § 6 proposed. Real speech-in-noise data puts near-complete
#: sentence intelligibility for a familiar voice at a signal-to-noise ratio
#: of 0 to +5 dB in steady noise; +3 is the middle of that band.
#:
#: A VOICE'S OWN MARGIN IS `SPEECH_FULL_SNR` (2026-10-20), and this one
#: stays the sounds': `level_of`, `heard_events`, `distant_level_word`'s
#: `plain` and the noise words all read it, and moving it took the `faint`
#: rung out of the distant-sound ladder (a sound must stand over the room's
#: floor to be heard at all, and `plain` began at the floor itself).
FULL_SNR = 2.0
#: `full` for a SPOKEN LINE, wherever the hearing rule grades one by its
#: level -- rooms away against the listening room's quiet floor
#: (`far_speech_level`), under the open sky over distance (`open_air_loss_db`),
#: in a deafening source's reach (`masked_level`): 0 dB, a sentence followed
#: whole when it stands level with the noise it is heard in.
#:
#: 2026-10-20, with the hearing rule. Speech intelligibility is high at 0 dB
#: signal to noise in steady noise, half the sentences go near -5 dB, and
#: words are still caught to about -12 (`FRAGMENT_SNR`, shared): the +3 dB
#: the line had been held to asked a voice to be twice the room before a
#: sentence of it was followed, which no listener asks.
SPEECH_FULL_SNR = 1.0
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

#: The four in dB. The ratios become MARGINS over the noise -- a sound
#: `full` at +3.01 dB, a spoken line `full` at 0 dB, either `fragment` at
#: -12.04 dB -- which is the form they were always in and the form that
#: says what they mean: a sound is plain when it is twice the room, a line
#: is followed when it stands level with it, and both are caught in pieces
#: down to a sixteenth of it.
#: The absolute floor is a LEVEL and so is the one number the reference does
#: not cancel out of.
FULL_SNR_DB = db_ratio(FULL_SNR)
SPEECH_FULL_SNR_DB = db_ratio(SPEECH_FULL_SNR)
FRAGMENT_SNR_DB = db_ratio(FRAGMENT_SNR)
HEAR_FLOOR_DB = db_of_power(HEAR_FLOOR)

#: THE NOISE LADDER the composer speaks (2026-09-04, the owner's rule b: the
#: sentence grades by a closed set, never a number). Three words for how hard
#: the noise at a cell makes a NORMAL VOICE ONE PACE OFF work -- the
#: yardstick a body has for a room's loudness, "could I hear someone beside
#: me" -- derived from the two SNR thresholds above, not set beside them:
#:
#:   quiet    a normal voice one pace off is followed as it is   noise <= 60 - FULL_SNR_DB      (57.0 dB)
#:   din      ... only in pieces unless it is raised             noise <= 60 - FRAGMENT_SNR_DB  (72.0 dB)
#:   drowned  ... not at all unless it is shouted                above that
#:
#: where 60 is `SPEECH_ONE_PACE_DB["normal"]`. In the world: a hearth fire
#: (50 at a pace) leaves the hearth `quiet`; a household `loud` (65 at a
#: pace, 68 at its own cell: a television turned up, a kettle's whistle)
#: is a `din` at the thing and a few paces round it and never `drowned` --
#: the owner's 2026-10-20 ruling, which the `loud` rung is set to keep; a
#: `deafening` machine (100) is `drowned` across a room. Move FULL_SNR or
#: FRAGMENT_SNR and the words move with them.
#:
#: DESCRIPTION SINCE 2026-10-20, NEVER A VERDICT. The words say how far a
#: voice has to rise, and a voice does rise, without deciding to (the
#: Lombard effect, `lombard_level_db`): two people at an engine talk over
#: it, and the page says they are in its din. Whether the WORDS of a line
#: arrive is the hearing rule's (`spatial_senses.hear_level`), where noise
#: decides only in the reach of what the story made deafening
#: (`MASKING_LEVELS`). The thresholds are the sounds' (`FULL_SNR`), so the
#: words are byte for byte what they were.
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


#: WHAT NOISE MAY TAKE A VOICE AWAY: a source the story itself makes
#: `deafening` or louder, and a one-beat event the story says drowns
#: everything out (`sensory_events[].drowns`). The owner, 2026-10-20:
#: "NOISE NEVER MASKS SPEECH" but for these. Below them the classes are a
#: model's judgement of an everyday thing -- `loud` is the loudest of a
#: home, a shop or a street, a television turned up or a kettle's whistle,
#: 65-75 dB(A) in the world (re-anchored there 2026-10-20; it had been an
#: engine at idle as well) -- and
#: across that span a voice that shares the noise rises with it (Lombard,
#: +3 to +10 dB and up to a shout) while a sentence is still followed at 0 dB
#: and caught to -12: so in the world people talk in kitchens, workshops and
#: on launches, raising their voices. `deafening` (100 dB(A) at a pace: a
#: klaxon, a siren, a jackhammer) is the first class whose every member
#: stands above the ceiling a voice can be raised to -- a shout, 80-88 dB(A)
#: at a pace (`SPEECH_ONE_PACE_DB`; Pearsons, Bennett & Fidell 1977 found
#: speech levels climbing about 0.6 dB per dB of noise and levelling off
#: there) -- which is what noise that masks speech whatever the speaker
#: does is.
MASKING_LEVELS = ("deafening", "thunderous", "catastrophic")

#: WHAT A ROOM DOES TO A VOICE ACROSS IT, for the one budget that needs a
#: voice's level rather than its word (`masked_level`): the reverberant
#: field beyond the critical distance holds a voice 0-10 dB under its level
#: at a pace by the room's size (Sabine's room constant; furnished rooms
#: from a parlour to a hall). The middle of that, 6 dB. The masking noise
#: from a source in the same enclosed room is held to the same floor
#: (`_masking_noise_db`), since its sound fills the room the same way.
VOICE_ROOM_DROP_DB = 6.0
#: What an opening or a door radiates into the next room spreads over that
#: room's absorption: 10 log10(S / A), about -10 dB for a doorway of 2 m2
#: into a room with 20 m2 of absorption. The masking budget's coupling term.
ROOM_COUPLING_DB = 10.0
#: SEEING THE SPEAKER'S FACE is worth several decibels of signal to noise:
#: lips, jaw and face follow the voice, and a listener who watches recovers
#: words the noise took (Sumby & Pollack 1954; MacLeod & Summerfield 1987
#: measured about 11 dB for sentences, smaller at the easier end). Applied
#: where noise is what decides, in a deafening source's reach; the low end
#: of the measured range, because a story's light and angle are rarely the
#: laboratory's.
AV_BENEFIT_DB = 6.0

#: PRIVACY IN A DIN (2026-10-20, wave A; `din_level`, and the bystander cap
#: in `spatial_senses.hear_level`). The hearing rule of the same day let no
#: noise below `deafening` touch a line, so a bystander anywhere in a busy
#: tavern followed every word at the far table. In the world a din cuts
#: both ways: the people TALKING TO EACH OTHER raise their voices (Lombard)
#: and, a pace or two apart, follow one another; a bystander a few paces off
#: hears the same raised voice's DIRECT sound 10-15 dB down against the same
#: din, and catches pieces of it or only the fact that people are talking --
#: energetic masking plus informational masking, the cocktail-party effect
#: working against the eavesdropper (Bronkhorst 2000). The room's ring that
#: carries a voice across a quiet room (the rule's one-room row) is under
#: the din here, and reverberant speech is the smeared part a listener
#: cannot use, so what reaches a bystander is the voice falling off with
#: distance as in open air.
#:
#: A DIN is noise at the listener's own ear at or above the `din` rung of
#: the noise words (`noise_word_db`): where a normal voice one pace off is
#: no longer followed as it is. 57 dB(A) -- babble and music at 65-75 are
#: a din; rain (37 at its heaviest, `WEATHER_NOISE`) and a quiet house
#: (25-35) never are, so the owner's rain ruling holds by construction.
#: Derived from the words' own thresholds, so the view that tells a body
#: "you are in the din" and the rule that keeps a far table's talk from it
#: are one number.
DIN_DB = VOICE_ONE_PACE_DB - FULL_SNR_DB
#: WITHIN CONVERSATIONAL REACH, in paces of the field's own path between
#: the two bodies: the people around one table, or standing together -- a
#: pace or two apart, the distance people in a noisy room close to when they
#: talk (social distance begins about 1.2 m; in a din groups stand closer).
#: Noise never stops people talking TO EACH OTHER: the line's addressee, and
#: anyone this near the speaker, hear it as the rule's table says, din or
#: none. Beyond it, in a din, a listener is a bystander.
CONVERSATION_REACH_PACES = 2.0

#: TONE TRAVELS FARTHER THAN WORDS (2026-10-20, wave A; `voice_margin_db`,
#: `spatial_senses.voice_carries`). A listener detects a voice -- that
#: someone is speaking, how loudly, its pitch and its emotional colour,
#: anger, laughter, crying, a scream -- well below the level at which any
#: of its words come through: the speech DETECTION threshold sits some
#: 10-15 dB under the threshold at which words are recognised (ANSI S3.6
#: practice: SDT about 8-12 dB below SRT), and a wall or a door takes a
#: voice's consonants and leaves its low half, the vowels and the tune
#: (transmission loss rises about 6 dB an octave). So where a line's words
#: are lost, the voice itself still arrives this far under the last caught
#: word (`FRAGMENT_SNR_DB`): ten decibels, the near end of the range, so
#: the rung is never wider than the measurement.
TONE_BELOW_WORDS_DB = 10.0
#: The margin over the listener's floor or noise at which the fact of a
#: voice still arrives: -22.0 dB.
VOICE_TONE_SNR_DB = FRAGMENT_SNR_DB - TONE_BELOW_WORDS_DB

#: WHICH WAY THE SPEAKER FACES (2026-10-20, wave B2; `facing_loss_db`, the
#: `speaker_turned_away` stamp in `stamp_sound_relation`). A voice is
#: directional: the mouth radiates forward and the head shades what goes
#: behind it. Measured round talkers at a metre (Chu & Warnock 2002, NRC
#: "Detailed directivity of sound fields around human talkers"; Monson,
#: Hunter & Story 2012), the overall level directly behind is some 6-8 dB
#: under the level in front and 4-6 dB at the rear diagonals; the band the
#: consonants carry the words in (2-4 kHz) falls most, 10-15 dB directly
#: behind, and the vowels and the tune below 1 kHz barely 2-4.
#:
#: WHAT THE WORDS LOSE to a listener in the speaker's rear arc (behind and
#: the two rear diagonals, `spatial_geometry._REAR_SECTORS`): the consonant
#: band's loss averaged over that arc.
FACING_AWAY_WORDS_DB = 8.0
#: WHAT THE VOICE LOSES there -- its low half, which is what the tone rung
#: carries (`voice_margin_db`): the vowels and the tune are nearly
#: omnidirectional, so a voice turned away is still plainly a voice.
FACING_AWAY_VOICE_DB = 3.0

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
    the edge ladder, a view, a memory.

    Never `ear`, however low the level: a breath with the lips at one ear
    is an act, not a loudness a level rounds to, and it reaches one body
    only (`spatial_senses.EAR_VOLUME`). A level under a whisper is a
    whisper."""
    try:
        level = float(level_db)
    except (TypeError, ValueError):
        return "normal"
    return min((w for w in SPEECH_DB if w != EAR_VOLUME),
               key=lambda w: (abs(SPEECH_DB[w] - level), w))


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
    quietest voice the hearing rule carries to them whole
    (`spatial_senses.hear_level`), a whisper at the least and a shout at the
    most -- nobody pitches a line across a hall by wanting to. The owner's
    ask (2026-09-15): a line's loudness follows its intent, "low, so that
    only his table would hear" reaching the table and nobody at the far
    wall. Where no voice reaches them whole, or the pair cannot be placed,
    the line is a normal one.

    RESTATED 2026-10-20 with the rule. It solved a level against the noise
    and the cell path; the rule has no noise in it below a deafening source
    and no distance inside a room, so the answer is a WORD of the ladder --
    within reach, a whisper; anywhere else the room or an opening carries a
    voice, an ordinary one; through a shut door, raised -- returned as that
    word's level so every caller keeps reading a level.

    NEVER THE EAR (2026-10-20). A breath with the lips at one ear
    (`spatial_senses.EAR_VOLUME`) is quieter than a whisper, but it is not
    a level a voice is pitched at from where it stands: the speaker has to
    put their mouth to that ear, which is an act the prose states and the
    line's own volume says. And a pitched line is graded for every other
    listener at the level it comes to, which the ear rung -- the addressee
    and nobody else -- is not. So the quietest pitch is a whisper, and "low,
    so that only his table would hear" still reaches the table.
    """
    who = _body_key(scene, addressee)
    said = _body_key(scene, speaker)
    if not who or not said:
        return SPEECH_DB["normal"]
    from world.spatial_senses import hear_level, spatial_rel_between
    rel = spatial_rel_between(scene, who, said)
    for word in ("whisper", "mutter", "normal", "loud", "shout"):
        if hear_level(rel, word) == "full":
            return SPEECH_DB[word]
    return SPEECH_DB["normal"]


#: THE LOMBARD EFFECT. A speaker raises their voice with the noise around
#: them without deciding to -- about 0.6 dB of voice for every dB of noise
#: above roughly 45 dB, up to a shout (Pearsons, Bennett & Fidell 1977,
#: "Speech Levels in Various Noise Environments", EPA-600/1-77-025; onset
#: after Lazarus 1986). Conversational speech only: a whisper or a mutter is a
#: choice to be heard by few, a shout is already the top of the ladder, and a
#: pitched line is solved for its addressee. Measured: nothing in the engine
#: adapted a voice to its room, so a smith answering at arm's length over a
#: working forge was graded as if he had spoken into a quiet room (owner,
#: 2026-09-23: "doesn't make particular sense").
#:
#: Since 2026-10-20 it is read where noise decides, in a deafening source's
#: reach (`masked_level`); below that the rise is the reason everyday noise
#: takes nothing from a voice, and the declared volume is the speaker's
#: intent, never their level in the room.
LOMBARD_ONSET_DB = 45.0
LOMBARD_SLOPE = 0.6
LOMBARD_VOLUMES = ("normal", "loud")


def lombard_level_db(volume, source_noise) -> Optional[float]:
    """The level AT THE CELL a conversational line is actually spoken at,
    given the noise power where its SPEAKER stands; None where the rule does
    not apply (another volume, or no noise known). At or under the onset it
    is exactly the volume's own level, so a quiet room changes nothing."""
    volume = str(volume or "normal").strip().casefold()
    if volume not in LOMBARD_VOLUMES or source_noise is None:
        return None
    base = SPEECH_DB[volume]
    raise_db = LOMBARD_SLOPE * max(0.0, db_of_power(source_noise) - LOMBARD_ONSET_DB)
    return base + min(raise_db, SPEECH_DB["shout"] - base)


def far_speech_level(volume, loss_db, floor_db=None, *, muffled=False,
                     level_db=None) -> str:
    """A line from ROOMS AWAY: the speaker's level at their cell, less the
    room graph's loss to the listener's room (`stamp_sound_relation` stamps
    it), against the listening room's QUIET floor -- the place's own level,
    never its weather or the things running in it, which mask nothing. A
    voice that crossed a pane, a heavy door, a wall or a floor on the way
    (`muffled`, `FAR_CLEAR_EDGE_DB`) arrives as its low half, in pieces at
    best. Breath is held to the room's own level (`quantise_speech_db`)."""
    from world.spatial_senses import UNVOICED_VOLUMES
    word = str(volume or "normal").strip().casefold()
    level = float(level_db) if level_db is not None else \
        SPEECH_DB.get(word, SPEECH_DB["normal"])
    floor = AMBIENT_DB["enclosed"] if floor_db is None else float(floor_db)
    heard = quantise_speech_db(level - float(loss_db), floor,
                               voiced=word not in UNVOICED_VOLUMES)
    if muffled and heard == "full":
        return "fragment"
    return heard


def facing_loss_db(rel: dict, part: str = "words") -> float:
    """WHAT A SPEAKER TURNED AWAY TAKES from the voice's DIRECT sound, in dB:
    `FACING_AWAY_WORDS_DB` from its words (`part` "words") or
    `FACING_AWAY_VOICE_DB` from the voice's low half (`part` "voice", the
    tone rung's), where the relation says the listener stands in the
    speaker's rear arc (`speaker_turned_away`); nothing elsewhere.

    Read ONLY by the budgets whose voice is the direct sound -- under the
    open sky (`open_air_loss_db`), rooms away from a speaker under the sky
    (`far_loss_db`), and a bystander in a din (`_din_voice_db`). A room's
    ring carries a voice across the room, through an opening and to a door
    nobody stands at whichever way its speaker faces, so no budget built on
    the ring reads this."""
    if not isinstance(rel, dict) or not rel.get("speaker_turned_away"):
        return 0.0
    return FACING_AWAY_VOICE_DB if part == "voice" else FACING_AWAY_WORDS_DB


def _voice_path_loss_db(rel: dict, reach) -> float:
    """The masking budget's path: how far under its level at a pace a voice
    arrives, by what stands between the two bodies (the hearing rule's own
    classes; `spatial_senses.hear_level`). Within reach, nothing; across a
    room, its reverberant drop; into the next room, the opening or door it
    crosses and the spread on the far side; rooms away, the far field's own
    measured loss. The two direct-sound paths, rooms away and under the
    sky, lose what a speaker turned away takes (`facing_loss_db`)."""
    from world.spatial_senses import (DOOR_REACH_BARRIERS,
                                      _material_shifted_barrier)
    if rel.get("far_loss_db") is not None:
        return float(rel["far_loss_db"]) - _ONE_PACE_LOSS_DB \
            + facing_loss_db(rel)
    if rel.get("open_air_loss_db") is not None:
        return max(0.0, float(rel["open_air_loss_db"]) - _ONE_PACE_LOSS_DB) \
            + facing_loss_db(rel)
    if rel.get("same_room"):
        return 0.0 if reach == "within_reach" else VOICE_ROOM_DROP_DB
    barrier = _material_shifted_barrier(normalize_barrier(rel.get("barrier")),
                                        rel.get("material"))
    if barrier in DOOR_REACH_BARRIERS and rel.get("door_reach"):
        return APERTURE_LOSS_DB[barrier]
    if reach == "within_reach" and barrier in APERTURE_LOSS_DB:
        return APERTURE_LOSS_DB[barrier]
    if barrier in APERTURE_LOSS_DB:
        return VOICE_ROOM_DROP_DB + APERTURE_LOSS_DB[barrier] + ROOM_COUPLING_DB
    return VOICE_ROOM_DROP_DB + WALL_LOSS_DB + ROOM_COUPLING_DB


def masked_level(rel: dict, volume, *, reach=None, level_db=None,
                 seen=False) -> str:
    """WHAT A DEAFENING NOISE LEAVES OF A LINE: the cap the hearing rule
    applies where the relation carries `masking_db` -- noise the story made
    deafening, or an event it says drowns everything, at the listener's ear
    (`stamp_sound_relation`). The one place noise decides speech.

    The voice is spoken over the noise where its SPEAKER stands -- raised
    without deciding to, up to a shout (`lombard_level_db`) -- reaches the
    listener by the rule's own path (`_voice_path_loss_db`), and is graded
    against the listener's noise at the ordinary margins. A listener who
    sees the speaker's face gains `AV_BENEFIT_DB`. Within reach of a klaxon
    a voice at arm's length is caught in pieces and one across the room is
    lost; a whisper is lost everywhere in it."""
    from world.spatial_senses import UNVOICED_VOLUMES
    noise_db = rel.get("masking_db")
    if noise_db is None:
        return "full"
    word = _speech_word(volume)
    voice = _masked_voice_db(rel, word, reach=reach, level_db=level_db,
                             seen=seen)
    return quantise_speech_db(voice, float(noise_db),
                              voiced=word not in UNVOICED_VOLUMES)


def _speech_word(volume) -> str:
    """The speech ladder's word for a line's volume; anything else is an
    ordinary voice, as the rule grades it."""
    word = str(volume or "normal").strip().casefold()
    return word if word in SPEECH_DB else "normal"


def _masked_voice_db(rel, word, *, reach=None, level_db=None, seen=False):
    """`masked_level`'s voice at the listener's ear, in dB: spoken over the
    noise where its speaker stands, carried by the rule's own path."""
    speaker_noise = rel.get("speaker_masking_db")
    raised = lombard_level_db(word, power_of_db(speaker_noise)
                              if speaker_noise is not None else None)
    level = level_db if level_db is not None else SPEECH_DB[word]
    if raised is not None and level_db is None:
        level = raised
    voice = float(level) - _ONE_PACE_LOSS_DB - _voice_path_loss_db(rel, reach)
    if seen:
        voice += AV_BENEFIT_DB
    return voice


def _din_voice_db(rel, word, *, level_db=None, seen=False,
                  part="words") -> Optional[float]:
    """What reaches a BYSTANDER in a din of a line spoken a few paces off, in
    dB at their ear, or None where the relation carries no din or no paces.

    The voice is raised over the din where its SPEAKER stands
    (`lombard_level_db`, up to a shout), and the bystander has its DIRECT
    sound: the speaker's level at their cell less the free-field spreading
    over the field's own path between the two (`spreading_loss_db`, 6 dB a
    doubling), less the opening's own loss where the two are one opening
    apart. The ring that carries a voice across a quiet room is under the
    din, and reverberant speech is what a listener cannot use (`DIN_DB`'s
    note). A listener who watches the speaker's face gains
    `AV_BENEFIT_DB`; one behind a speaker turned away loses what the head
    shades of the direct sound (`facing_loss_db`, its words or -- `part`
    "voice", the tone rung's -- its low half)."""
    if rel.get("din_db") is None or rel.get("paces") is None:
        return None
    speaker_din = rel.get("speaker_din_db")
    raised = lombard_level_db(word, power_of_db(speaker_din)
                              if speaker_din is not None else None)
    level = level_db if level_db is not None else SPEECH_DB[word]
    if raised is not None and level_db is None:
        level = raised
    voice = float(level) - spreading_loss_db(max(1.0, float(rel["paces"])))
    if not rel.get("same_room"):
        from world.spatial_senses import _material_shifted_barrier
        barrier = _material_shifted_barrier(
            normalize_barrier(rel.get("barrier")), rel.get("material"))
        voice -= APERTURE_LOSS_DB.get(barrier, 0.0)
    if seen:
        voice += AV_BENEFIT_DB
    return voice - facing_loss_db(rel, part)


def din_level(rel: dict, volume, *, level_db=None, seen=False) -> str:
    """WHAT A DIN LEAVES A BYSTANDER OF A LINE: `full | fragment | none`, by
    `_din_voice_db` against the din at the bystander's ear at the speech
    margins (`quantise_speech_db`). `full` where the relation carries no din.

    Applied by `spatial_senses.hear_level` only to a listener the line was
    not addressed to and who stands beyond `CONVERSATION_REACH_PACES` of the
    speaker: noise never stops people talking to each other. In a tavern's
    babble (68 dB) a raised conversational voice is followed whole a pace or
    two off, caught in pieces from about three paces, and beyond about eight
    a bystander has only the fact that people are talking
    (`spatial_senses.voice_carries`)."""
    from world.spatial_senses import UNVOICED_VOLUMES
    word = _speech_word(volume)
    voice = _din_voice_db(rel, word, level_db=level_db, seen=seen)
    if voice is None:
        return "full"
    return quantise_speech_db(voice, float(rel["din_db"]),
                              voiced=word not in UNVOICED_VOLUMES)


def voice_margin_db(rel: dict, volume, *, reach=None, level_db=None,
                    seen=False, din=False) -> Optional[float]:
    """How far over (or under) what the listener hears it against a line's
    VOICE arrives, in dB -- the budget the tone rung reads
    (`spatial_senses.voice_carries`), from the same numbers the hearing
    rule's table is written against. None where no air carries a voice at
    all: no relation between the rooms, another world, a far path that
    nothing crosses.

    The path: rooms away, the far field's measured loss; under the sky, the
    open air's; otherwise the masking budget's own path classes
    (`_voice_path_loss_db`: the room's drop, the opening or door, the spread
    into the next room, a wall). Against the listening room's quiet floor
    (`floor_db` where stamped, a quiet room's 27 dB otherwise -- the
    table's own budget floor). Where noise the story made deafening reaches
    the listener (`masking_db`), or -- `din` -- a din reaches a bystander,
    the weaker of that budget and the path's. Behind a speaker turned away
    the direct-sound paths lose the voice's low half's few decibels
    (`facing_loss_db(rel, "voice")`), never the words' larger share: a
    voice turned away is still plainly a voice."""
    word = _speech_word(volume)
    level = float(level_db) if level_db is not None else SPEECH_DB[word]
    floor = float(rel["floor_db"]) if rel.get("floor_db") is not None \
        else AMBIENT_DB["enclosed"]
    if rel.get("far_loss_db") is not None:
        loss = float(rel["far_loss_db"])
        if math.isinf(loss):
            return None
        margins = [level - loss - facing_loss_db(rel, "voice") - floor]
    elif rel.get("open_air_loss_db") is not None:
        margins = [level - float(rel["open_air_loss_db"])
                   - facing_loss_db(rel, "voice") - floor]
    else:
        barrier = normalize_barrier(rel.get("barrier"))
        if not rel.get("same_room") and (barrier == "unknown"
                                         or rel.get("distance") == "remote"):
            return None
        margins = [level - _ONE_PACE_LOSS_DB
                   - _voice_path_loss_db(rel, reach) - floor]
    if rel.get("masking_db") is not None:
        margins.append(_masked_voice_db(rel, word, reach=reach,
                                        level_db=level_db, seen=seen)
                       - float(rel["masking_db"]))
    if din:
        voice = _din_voice_db(rel, word, level_db=level_db, seen=seen,
                              part="voice")
        if voice is not None:
            margins.append(voice - float(rel["din_db"]))
    return min(margins)


def quantise_hearing(signal: float, noise: float, *, voiced: bool = False) -> str:
    """Quantise, LAST, from two LINEAR powers. The reference path, kept in
    step with the dB path below so the conversion property has something to
    prove (`tests/test_sound_field.py`)."""
    if noise <= 0:
        return "full" if signal >= HEAR_FLOOR else "none"
    if signal >= FULL_SNR * noise:
        return "full"
    if signal >= FRAGMENT_SNR * noise and (
            voiced or signal >= min(HEAR_FLOOR, noise)):
        return "fragment"
    return "none"


def quantise_speech_db(signal_db: float, noise_db: float, *,
                       voiced: bool = True) -> str:
    """A SPOKEN LINE's word from two levels: `full` at `SPEECH_FULL_SNR_DB`
    over the noise, `fragment` at `FRAGMENT_SNR_DB` -- for breath, only at or
    above the room's own level, which a whisper cannot be heard under
    (`quantise_hearing_db` says why) -- else `none`. The one quantiser every
    speech budget reads: rooms away, under the open sky, in a deafening
    source's reach."""
    if noise_db == float("-inf"):
        return "full" if _at_least(signal_db, HEAR_FLOOR_DB) else "none"
    if _at_least(signal_db, noise_db + SPEECH_FULL_SNR_DB):
        return "full"
    if _at_least(signal_db, noise_db + FRAGMENT_SNR_DB) and (
            voiced or _at_least(signal_db, min(HEAR_FLOOR_DB, noise_db))):
        return "fragment"
    return "none"


def quantise_hearing_db(signal_db: float, noise_db: float, *,
                        voiced: bool = False) -> str:
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

    A VOICED LINE IS NOT HELD TO THE FLOOR (`voiced`; the speech budgets
    read `quantise_speech_db`, which keeps the same rule for every volume
    outside `spatial_senses.UNVOICED_VOLUMES`). The sentence above is true
    of a breath and false of a voice: `FRAGMENT_SNR` puts the words of a
    voice in pieces down to 12 dB UNDER the noise, and in any room whose
    noise sits near the floor
    this gate cancelled that whole band, so a normal line had to reach the
    room's own level before a single word of it arrived. The two numbers
    stopped agreeing on 2026-09-14, when the fragment margin moved from
    -1 dB to -12 dB and the floor did not: a quiet house became harder to
    overhear in than a noisy one. Measured on the mood test stories
    (2026-09-26): a boy pressed to a shut door, listening for every word,
    caught none of a normal conversation arriving 1.3 dB under a 27 dB
    room. A whisper and a mutter keep the floor, which is what their own
    calibration (the far wall of a large room, `SPEECH_ONE_PACE_DB`)
    stands on.
    """
    if noise_db == float("-inf"):
        return "full" if _at_least(signal_db, HEAR_FLOOR_DB) else "none"
    if _at_least(signal_db, noise_db + FULL_SNR_DB):
        return "full"
    if _at_least(signal_db, noise_db + FRAGMENT_SNR_DB) and (
            voiced or _at_least(signal_db, min(HEAR_FLOOR_DB, noise_db))):
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
#: THE RING NO LONGER SMEARS A LINE (2026-10-20, the hearing rule). From
#: 2026-09-15 a voice whose reverberant part outran its direct part at the
#: listener's cell -- by 15 dB of ring, then (2026-10-02) by its clarity
#: C50 under -5 dB -- was graded a fragment, which put the CELL PATH back
#: into whether a voice in the same room was heard, against the rule that
#: distance inside a room takes nothing from it. The reverberant field is
#: what CARRIES a voice across a room (`spatial_senses.hear_level`), and in
#: the world people follow one another in stone halls, with effort. The
#: smear fired on none of the 2,408 lines the owner's chats replayed. What a
#: room's ring still does is real and kept: it carries a sound further
#: (`ring_boost_db`), gives a sharp one back (`echo`) and takes away where a
#: sound came from (`spatial_senses._bearing_through`).
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
#: `wood` and `tatami` read as timber -- tatami as the timber under its mats
#: (`spatial_levels.FLOOR_LOSS_DB` says why); what the mats take off a tread
#: is the owner's number to set.
FLOOR_IMPACT_DB = {"timber": 55.0, "board": 55.0, "plank": 55.0, "wood": 55.0,
                   "tatami": 55.0,
                   "stone": 40.0, "concrete": 40.0, "masonry": 40.0}
TREAD_RUN_DB = 8.0

#: FOOTSTEPS AND THUDS COME THROUGH FLOORS (2026-10-20, wave A;
#: `tread_events`). Impact sound -- a footfall, a dropped weight, a slammed
#: door, a body falling -- is made IN the structure and travels through it
#: far better than airborne speech does: on a timber floor a footfall above
#: is plainly heard in the room below, a stone or earth floor carries much
#: less, and a soft step carries less again. The engine's three gaits, a
#: closed set on the walk's `pace` (`TREAD_GAITS`): `sneak` (a body moving
#: so as not to be heard), `walk`, `run`.
TREAD_GAITS = ("sneak", "walk", "run")
#: A STEP PLACED NOT TO BE HEARD -- weight eased down, heel to toe -- strikes
#: the floor with a small fraction of a walking step's force: measured
#: impact peaks fall by 10-20 dB between a firm walk and a slow, soft one
#: (footfall noise studies of light-weight floors, e.g. Jeon et al. 2004's
#: walking-vs-soft-walking LAmax). The middle of that. On a timber floor a
#: sneak above still comes through as a creak a quiet room below can hear
#: (40 dB); on stone it does not (25).
TREAD_SNEAK_DB = 15.0
#: WHAT A FLOOR CARRIES SIDEWAYS: a footfall reaches the room beside the
#: walker's on the same storey through the shared floor and the partition
#: -- flanking transmission -- some 10-20 dB under what reaches the room
#: directly below (ISO 12354-2's flanking paths for impact sound). The
#: middle of that: a walk on timber is heard next door (40 dB), a walk on
#: stone is not (25).
FOOTFALL_FLANKING_DB = 15.0


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

    ONLY AN ENCLOSED ROOM RINGS, for the reason only an enclosed room is a
    duct (`is_duct`): a ring is sound the walls AND THE ROOF keep, and a
    place open to the sky, or open at its sides, lets it go. Sabine's rule
    here assumes a ceiling (`ROOM_HEIGHT_M`) on every room, so a stone
    breakwater under a gale was priced as a stone hall: a 2.2 s
    "cavernous" ring about 4 dB over a voice at one pace, which smeared
    every normal line spoken a few paces apart on it (the homecoming test
    story, 2026-09-26: 22 lines caught in pieces in the open air). The
    owner, that day: "Sound gatings is entirely overzealous."
    """
    from world import weather as _weather

    surface = room_surface(scene, room_id)
    if surface not in REVERBERANT_SURFACES:
        return None
    if _weather.room_exposure(scene, room_id) != "enclosed":
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


def sound_sources(scene: dict, *, turn_idx=None, crowds=None, events=None) -> tuple:
    """(sources, notices). Each source: {id, kind, room, cell, power, level,
    holder}, `cell` room-local. Kinds: `entity` (a running `sound_source`,
    at its cell -- its holder's cell when a body carries it, so a machine in
    your hands is heard at your own cell before anything else, § 4.7),
    `crowd` (at its room's centre, level by band), `event` (a one-beat sound
    event with a `source_room`, at its maker's cell or its room's centre).
    There is no `speech` kind since 2026-10-20: a voice is graded by the
    hearing rule (`spatial_senses.hear_level`), and one voice never masks
    another -- the `speakers` parameter that placed simultaneous voices here
    had no caller in the engine.

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
            # A ROOM'S OWN VOICE ALREADY CARRIES ITS ECHO. The word is how
            # the place sounds to someone standing in it -- a drip in a
            # stone cell is written `faint` because that is what it is
            # there, ring and all -- so the ring must not be laid on top of
            # it a second time. The power is set so that direct and ring
            # together make the word at one pace, and the far field, which
            # hands a ringing room's walls its ring (`ring_boost_db`), then
            # starts from the word too. A THING's `sound_source` is not
            # scaled: it is the thing's, it goes where the thing goes, and
            # a bare room it is carried into rings with it. Measured on the
            # mood test stories (2026-09-26): a `faint` drip in a hushed
            # 4x3 stone infirmary stood at 58 dB where anyone stood --
            # louder than a mutter at arm's length -- and rain written into
            # a 3x3 stone stoop left it at 69 dB and drowned the rehearsal
            # room two doors away.
            power = EVENT_POWER[level]
            ring = room_reverberation(scene, rid)
            if ring:
                power = power / (1.0 + float(ring["gain"]))
            out.append({"id": "room:%s" % rid, "kind": "room",
                        "room": str(rid), "cell": room_centre(scene, rid),
                        "power": power, "level": level,
                        "holder": None, "beat": "steady",
                        "detail": str(record.get("detail") or "")})
    for crowd in crowds or []:
        if not isinstance(crowd, dict):
            continue
        room = str(crowd.get("room_uid") or "")
        if not room or room not in rooms:
            continue
        from world.crowds import normalize_band
        band = normalize_band(crowd.get("band"))
        level = CROWD_SOUND.get(band, "audible")
        # ITS TALK, AT ITS REAL LEVEL (`CROWD_BABBLE_DB`): the band's babble
        # at one pace, which `SoundField.intensity_at` also holds through the
        # whole room the crowd stands in. `level` stays the band's word.
        babble = CROWD_BABBLE_DB.get(band, CROWD_BABBLE_DB["a dozen or so"])
        out.append({"id": "crowd:%s" % (crowd.get("uid") or room),
                    "kind": "crowd", "room": room,
                    "cell": room_centre(scene, room),
                    "power": one_pace_power(babble), "level": level,
                    "babble_db": babble,
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
        if cell is None and source:
            # ...AND WHERE ITS SOURCE IS ONE OF THE ROOM'S OWN FIXTURES, AT
            # THE FIXTURE. A windlass's clank priced from the room's centre
            # put the man standing there "in the din" while the windlass
            # itself read faint (playerless Aldermill round 5, 2026-09-23,
            # idx 14). The middle cell of the fixture's own footprint.
            fixture = next((rec for aid, rec in anchor_cells(scene, room).items()
                            if str(aid).casefold() == source.casefold()), None)
            cells = list((fixture or {}).get("cells") or ())
            if cells:
                cell = tuple(cells[len(cells) // 2])
        if cell is None and source.startswith(DOOR_SOURCE_PREFIX):
            # ...AND WHERE IT IS ONE OF THE ROOM'S DOORWAYS, AT THE DOORWAY:
            # a door opened or shut sounds where it hangs (`door_events`).
            cells, _bearing = _door_cells(scene, room, source[len(DOOR_SOURCE_PREFIX):])
            if cells:
                cell = tuple(cells[len(cells) // 2])
        power = _event_power(event)
        drowns = event.get("drowns") is True
        if drowns:
            # A NOISE THE STORY SAYS DROWNS EVERYTHING is priced as a thing
            # that does: no quieter than `deafening` on the emission ladder,
            # whatever word the event carries. Its level still decides how
            # far it reaches (`SoundField.masking_db_at`).
            power = max(power, SOUND_POWER["deafening"])
        out.append({"id": "event:%d" % idx, "kind": "event", "room": room,
                    "cell": cell or room_centre(scene, room),
                    "power": power, "level": None, "drowns": drowns,
                    "holder": None, "beat": "steady"})
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
    `sound_field`; read by `noise_at`, `level_of` and `masking_db_at`."""

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

    # -- reverberation ------------------------------------------------------

    def rev_gain(self, source_room, cell) -> float:
        """The reverberant field a source in `source_room` puts at `cell`:
        the room's ring everywhere inside it, and beyond each of its
        openings the ring at the opening spread on as any sound is. Zero
        where the room does not ring."""
        rev = self.reverb.get(str(source_room))
        if not rev:
            return 0.0
        # ON THE SAME FOOTING AS EVERY OTHER GAIN HERE. `room_reverberation`
        # states the ring relative to the level ONE PACE off, and every gain
        # this field returns multiplies the level at the source's OWN cell,
        # which sits `_ONE_PACE_LOSS_DB` above it (`one_pace_power`). Applied
        # unscaled, every echo read 3.01 dB loud, so the smear rule's 15 dB
        # behaved as 12 and a bare room fragmented any line spoken more than
        # about two paces off, a shout included: a smith answering from 2.4
        # paces reached the woman he answered as fragments (playerless
        # Aldermill round 5, 2026-09-23, idx 19; signal +5 dB over the noise).
        ring = float(rev["gain"]) * ratio_of_db(-_ONE_PACE_LOSS_DB)
        if self.grid.inside.get(cell) == str(source_room):
            return ring
        return ring * self._door_gain(source_room, cell)

    def _door_gain(self, source_room, cell) -> float:
        """The best gain to `cell` from any doorway of `source_room` on this
        field: what a sound that fills that room carries on, beyond it, from
        the openings it leaves by."""
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
        return best

    # -- intensity ----------------------------------------------------------

    def intensity_at(self, source, cell) -> float:
        babble = source.get("babble_db")
        if source.get("kind") == "crowd" and babble is not None:
            # A CROWD FILLS THE ROOM IT STANDS IN (`CROWD_BABBLE_DB`): its
            # talk comes from every part of it, so anywhere in that room the
            # babble is its level there, and beyond the room it carries on
            # from the openings it leaves by. Priced as a point at the
            # room's centre, the far end of a tavern full of talk was as
            # quiet as an empty room and its middle a machine shop.
            fill = power_of_db(float(babble))
            if self.grid.inside.get(cell) == str(source["room"]):
                return fill
            return fill * self._door_gain(str(source["room"]), cell)
        direct = gain_at(self.spread_from(source["at"]), cell)
        return source["power"] * max(direct, self.rev_gain(source["room"], cell))

    def noise_at(self, listener, *, exclude=(), room=None) -> Optional[float]:
        """The listener's NOISE (§ 4.4): every placed source's intensity at
        the listener's cell except those in `exclude` (source ids) AND except
        any source standing where an excluded one stands, plus the room's
        ambient floor. What a SOUND -- a thing, a crowd, an event -- is heard
        over (`level_of`); since 2026-10-20 never what a voice is graded
        against, which is `masking_db_at`'s, and only for what the story made
        deafening.

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

        A BEAT'S ONE-OFF SOUNDS ARE MOMENTS, NOT A FLOOR (the owner,
        2026-09-25: "sounds should be allowed to be transient mid beat. there
        are types of sound after all."). A sound event -- a creak, a clank, a
        gasp, a shot (`sensory_events`) -- happens at some moment in the beat
        and is heard as itself (`level_of`); what a line, or any other sound,
        is heard over is what sounds THROUGHOUT it: standing sources, crowds,
        the room's own sound and its ambient floor. Counted as a floor, an
        instant sat on every line of the beat at full power. Measured on the
        owner's chat 155 turn 34: a listener's own single `audible` moan,
        placed at her own cell, read 58 dB in her ears and took a line
        murmured by a face inches from hers to nothing; a faint creak of the
        table she lay on still held it to a fragment. A noise that should
        drown speech for as long as it lasts is the engine's other type of
        sound, a standing source (`sound_source` with `state.running`). The
        same-place rule above still holds for standing sources; the
        event-on-event case it was measured on no longer arises.
        """
        cell = self.locate(listener, room)
        if cell is None:
            return None
        skip = {str(x).strip().casefold() for x in exclude if x}
        at_hand = {(source["room"], tuple(source["cell"]))
                   for source in self.sources
                   if source["id"].casefold() in skip}
        total = self.ambient.get(self.grid.inside[cell], AMBIENT["enclosed"])
        for source in self.sources:
            if source.get("kind") == "event":
                continue
            sid = source["id"].casefold()
            if sid in skip:
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
                return self.intensity_at(source, cell) \
                    * ratio_of_db(self._wind_db(source, cell))
        return 0.0

    def _wind_db(self, source, cell) -> float:
        """What the wind does to a source's sound on its way to `cell`
        (`wind_bend_db`), where the source and the listener both stand
        under the sky: by the field's own path and its bearing. A crowd's
        talk fills its room and is no point to bend from."""
        if source.get("kind") == "crowd" or not _scene_wind(self.scene)[1] \
                or not _outdoors(self.scene, source["room"],
                                 self.grid.inside.get(cell)):
            return 0.0
        metres, bearing = _field_path(self, cell, source["at"])
        if metres is None or not bearing:
            return 0.0
        return wind_bend_db(self.scene, bearing, metres)

    def level_of(self, listener, source_id, *, room=None) -> str:
        """`none | fragment | full` for one placed source (an entity, a
        crowd, an event, or `speech:<name>`) as this listener hears it."""
        signal = self.signal_at(listener, source_id, room=room)
        noise = self.noise_at(listener, exclude=(source_id,), room=room)
        if signal is None or noise is None:
            return "none"
        return quantise_hearing_db(db_of_power(signal), db_of_power(noise))

    def masking_db_at(self, listener, *, room=None) -> Optional[float]:
        """The noise that may take a voice away at this listener's ear, in dB
        -- the place's quiet floor and every source the story makes
        deafening or louder (`MASKING_LEVELS`) or says drowns everything (a
        `drowns` event) -- or None when nothing of that kind reaches them, so
        an ordinary room carries no masking at all. Off the field, None.

        A SOURCE FILLS THE ROOM IT STANDS IN: indoors, beyond a pace or two,
        its reverberant field holds it within a few decibels of its level at
        a pace (`VOICE_ROOM_DROP_DB`), so a listener in the same enclosed
        room is held to that level at least, wherever the cell flood puts
        them -- the same drop the voice it masks is held to."""
        from world import weather as _weather
        cell = self.locate(listener, room)
        if cell is None:
            return None
        here = self.grid.inside[cell]
        total = 0.0
        for source in self.sources:
            if not _masks(source):
                continue
            power = self.intensity_at(source, cell)
            if source["room"] == here and \
                    _weather.room_exposure(self.scene, here) == "enclosed":
                diffuse = power_of_db(db_of_power(source["power"])
                                      - _ONE_PACE_LOSS_DB - VOICE_ROOM_DROP_DB)
                power = max(power, diffuse)
            total += power
        if total <= 0.0:
            return None
        return db_of_power(total + quiet_floor(self.scene, here))


def open_air_loss_db(scene, sound, listener, speaker, room,
                     speaker_room=None) -> Optional[float]:
    """What the open air takes from a voice between two bodies in one room
    under the sky, or None where the rule has no distance to read: an
    enclosed room (its reverberant field holds a voice across it), or a
    body the scene does not place.

    OR IN TWO ROOMS UNDER THE SKY, one opening apart (`speaker_room`, wave
    B2): a square and the street beside it, a meadow and the pasture past
    its gap, are one stretch of open air with a line drawn across it, and
    the opening row's budget -- a room's ring radiating through a doorway
    into the next room's ring -- has nothing to stand on there. The field's
    path runs through the opening and charges it its own small loss.
    Measured: a normal voice 140 paces across two open fields was whole
    through the opening and in pieces across one field of the same length.
    The caller asks only for a pair the opening joins.

    UNDER THE SKY A VOICE FALLS 6 dB EVERY TIME THE DISTANCE DOUBLES: no
    ceiling and walls give it back, so the free-field law the cell flood
    already charges (`spreading_loss_db` over the path) is the physics
    rather than an approximation of it. Against an open place's quiet floor
    (`quiet_floor`, 30 dB) a normal voice is followed to 45 paces -- some
    34 m, nearly three times a street's width, so a call across a street
    carries in any weather -- and caught in pieces to 180; a raised voice
    is followed to 140, and on a still night every reach doubles.

    Both bodies must stand where the scene put them (`body_cell`): a body
    with no station stands at the room's centre on the field, which is a
    guess, and a guess must not take a voice away."""
    speaker_room = speaker_room or room
    if not _outdoors(scene, room, speaker_room):
        return None
    if body_cell(scene, listener) is None or body_cell(scene, speaker) is None:
        return None
    here = sound.locate(listener, room)
    there = sound.locate(speaker, speaker_room)
    if here is None or there is None:
        return None
    loss = loss_db_at(sound.spread_from(there), here)
    return None if math.isinf(loss) else loss


def _scene_wind(scene) -> tuple:
    """`(strength, quarter)` of the scene's wind -- the weather's `wind`
    word and its `wind_from` -- or ("", "") where the weather names none."""
    from world.weather import WIND_FROM_KEY, normalize_weather
    raw = (scene or {}).get("weather")
    if not isinstance(raw, dict) or not raw.get(WIND_FROM_KEY):
        return "", ""               # no quarter named: the common case, free
    weather = normalize_weather(raw)
    return (str(weather.get("wind") or ""),
            str(weather.get(WIND_FROM_KEY) or ""))


def wind_bend_db(scene, travel, metres) -> float:
    """WHAT THE WIND DOES TO A SOUND OUTDOORS, in dB: positive where it
    carries the sound (travelling downwind), negative where it swallows it
    (upwind), for a sound going `metres` with compass bearing `travel` --
    the way the sound goes, from its source to the ear. 0.0 where the
    weather names no wind or no quarter, the bearing is unknown, or the path
    is under `WIND_BEND_ONSET_M`.

    By the angle between the sound's way and the wind's: its cosine scales
    `WIND_DOWNWIND_DB` with the wind and `WIND_UPWIND_DB` against it, so a
    crosswind does nothing, and the size grows with the logarithm of the
    distance from the onset to `WIND_BEND_FULL_M`. The caller asks only for
    a path both of whose ends are under the sky."""
    from world.spatial_orientation import _BEARING_DEG, opposite_bearing
    strength, quarter = _scene_wind(scene)
    if strength not in WIND_UPWIND_DB or not quarter \
            or travel not in _BEARING_DEG:
        return 0.0
    try:
        metres = float(metres)
    except (TypeError, ValueError):
        return 0.0
    if not metres > WIND_BEND_ONSET_M:
        return 0.0
    ramp = min(1.0, math.log(metres / WIND_BEND_ONSET_M)
               / math.log(WIND_BEND_FULL_M / WIND_BEND_ONSET_M))
    downwind = opposite_bearing(quarter)
    along = math.cos(math.radians(_BEARING_DEG[travel]
                                  - _BEARING_DEG[downwind]))
    if abs(along) < 1e-9:
        return 0.0
    top = WIND_DOWNWIND_DB[strength] if along > 0 else WIND_UPWIND_DB[strength]
    return along * top * ramp


def _open_between(scene, rel, a, b) -> bool:
    """Are two NEIGHBOURING rooms both under the sky and joined by an
    opening (a doorless way, an open door or gate, a grille -- after the
    material shift): one stretch of open air with a line across it, which
    the open air's law reads (`open_air_loss_db`)."""
    from world.spatial_senses import OPEN_BARRIERS, rooms_adjacent
    if not a or not b or a == b or not rooms_adjacent(scene, a, b):
        return False
    barrier = _material_shifted_barrier(normalize_barrier(rel.get("barrier")),
                                        rel.get("material"))
    return barrier in OPEN_BARRIERS and _outdoors(scene, a, b)


def _outdoors(scene, *rooms) -> bool:
    """Is every one of these rooms under the sky -- `exposure` not
    `enclosed`, a roof open at its sides included?"""
    from world import weather as _weather
    return all(room and _weather.room_exposure(scene, room) != "enclosed"
               for room in rooms)


def _field_path(sound, here, there):
    """`(metres, bearing)` of the field's own path from the cell `there` to
    the cell `here` on one composite: the flood's length, in metres, and the
    compass bearing from one cell to the other. (None, None) off the
    field."""
    from world.spatial_fov import bearing_between
    if here is None or there is None:
        return None, None
    rec = sound.spread_from(there).get(here)
    if rec is None:
        return None, None
    return float(rec[0]) * PACE_M, bearing_between(tuple(there), tuple(here))


def _pair_paces(scene, sound, listener, speaker, l_room, s_room, rel):
    """How many paces of the field's own path stand between two bodies in
    one room or two rooms one opening apart, or None where the field does
    not place them both from what the scene says (`body_cell`: a body with
    no station stands at the room's centre on the field, a guess). The
    measure breath is private by (`spatial_senses.WHISPER_REACH_PACES`).

    The path, not a straight line, because a voice goes round what parts a
    room and through the opening between two -- the stage and the pit below
    it, whose wide opening no doorway cell stands for (the rival test story,
    2026-09-26: a whisper from the stage's lip to the conductor's stand a
    pace and a half below)."""
    from world.spatial_senses import OPEN_BARRIERS, _material_shifted_barrier
    if l_room != s_room:
        barrier = _material_shifted_barrier(
            normalize_barrier(rel.get("barrier")), rel.get("material"))
        if barrier not in OPEN_BARRIERS:
            return None
    if body_cell(scene, listener) is None or body_cell(scene, speaker) is None:
        return None
    here = sound.locate(listener, l_room)
    there = sound.locate(speaker, s_room)
    if here is None or there is None:
        return None
    rec = sound.spread_from(there).get(here)
    return None if rec is None else float(rec[0])


def _plan_line(scene, a, b, *, a_at=None) -> tuple:
    """`(metres, bearing)` of the straight line from `a` to body `b` on
    their site plan -- the ground between them and its compass bearing --
    or (None, None) where the two do not stand on one plan
    (`site_plan.plan_point`). `a` is a body, or, with `a_at` a
    `(room, cell)`, a point in a room (a sound's own cell)."""
    from world.site_plan import PACE_M as _PLAN_PACE_M, plan_point, room_site
    if a_at is not None:
        a_room, a_cell = a_at
        site_a = room_site(scene, a_room)
        pa = (site_a["x"] + a_cell[0] + 0.5, site_a["y"] + a_cell[1] + 0.5) \
            if site_a and a_cell is not None else None
    else:
        site_a = room_site(scene, room_of(scene, a))
        pa = plan_point(scene, a)
    site_b = room_site(scene, room_of(scene, b))
    if not site_a or not site_b or site_a["plan"] != site_b["plan"]:
        return None, None
    pb = plan_point(scene, b)
    if pa is None or pb is None:
        return None, None
    from world.spatial_fov import bearing_between
    metres = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) * _PLAN_PACE_M
    return metres, bearing_between((pa[0], pa[1]), (pb[0], pb[1]))


def _plan_bearing(scene, a, b) -> Optional[str]:
    """The compass bearing from body `a` to body `b` on their site plan, or
    None where the two do not stand on one plan (`_plan_line`)."""
    return _plan_line(scene, a, b)[1]


def _wind_on_the_path(scene, sound, listener, speaker, l_room, s_room,
                      far=None) -> float:
    """`wind_bend_db` for the path a voice takes from `speaker` to
    `listener`, where both ends stand under the sky (`_outdoors`): in one
    room, the field's own path and its bearing; rooms away, the straight
    line on the site plan where both stand on one, else the far field's
    path (`far`) and the way it arrives by -- the bearing from the room it
    comes through into the listener's. 0.0 indoors, or where nothing says
    which way the sound goes."""
    if not _scene_wind(scene)[1] or not _outdoors(scene, l_room, s_room):
        return 0.0                  # no quarter named, or a roof on the way
    from world.spatial_orientation import travel_bearing
    metres, bearing = _field_path(sound, sound.locate(listener, l_room),
                                  sound.locate(speaker, s_room))
    if bearing is None and l_room != s_room:
        metres, bearing = _plan_line(scene, speaker, listener)
        if bearing is None and far and far.get("via"):
            metres = float(far.get("length") or 0.0) * PACE_M
            bearing = travel_bearing(scene, str(far["via"]), l_room)
    if metres is None or not bearing:
        return 0.0
    return wind_bend_db(scene, bearing, metres)


def _first_hop(scene, from_room, to_room) -> Optional[str]:
    """The room next to `from_room` on the far field's path toward
    `to_room`: the way a sound from one leaves for the other. The flood is
    run from `to_room` -- the graph is undirected and a path's loss is the
    same both ways -- so the record it leaves at `from_room` names, as the
    room it arrived from, the first room the other way."""
    rec = room_sound_flood(scene, to_room, SPEECH_DB["shout"]).get(
        str(from_room))
    return str(rec["via"]) if rec and rec.get("via") else None


def _bearing_toward(scene, sound, listener, speaker, l_room, s_room
                    ) -> Optional[str]:
    """Which way, from the SPEAKER, the listener lies -- the direction the
    voice has to go to reach them: across the observer's own composite field
    for one room or a neighbour (`bearing_between` of the two cells); rooms
    away, on the site plan when both stand on one, else the way out of the
    speaker's room the far field's path leaves by (`_first_hop`). None where
    nothing says."""
    from world.spatial_fov import bearing_between
    here = sound.locate(listener, l_room) if sound is not None else None
    there = sound.locate(speaker, s_room) if sound is not None else None
    if here is not None and there is not None:
        return bearing_between(tuple(there), tuple(here))
    planned = _plan_bearing(scene, speaker, listener)
    if planned:
        return planned
    via = _first_hop(scene, s_room, l_room)
    if not via:
        return None
    from world.spatial_orientation import travel_bearing
    return travel_bearing(scene, s_room, via)


def _speaker_turned_away(scene, sound, listener, speaker, l_room, s_room,
                         rel) -> bool:
    """Does the listener stand in the SPEAKER's rear arc, where the head
    shades the voice's direct sound (`FACING_AWAY_WORDS_DB`) -- asked only
    where a budget reads that direct sound, and only on the engine's own
    record of which way the speaker faces (`effective_facing`)?

    Never within conversational reach (a standing contact, or
    `CONVERSATION_REACH_PACES` of the field's path): the one at the
    speaker's shoulder hears a turned head whole. Only where the voice's
    budget is its direct sound: under the open sky (`open_air_loss_db`), a
    din at the listener's ear (the ring is under it), or rooms away from a
    speaker standing under the sky. Everywhere else the room's ring carries
    the voice -- across the room, through an opening, to a door nobody
    stands at -- and the ring faces nowhere."""
    from world import weather as _weather
    from world.spatial_geometry import _REAR_SECTORS, effective_facing
    from world.spatial_orientation import relative_bearing
    if rel.get("reach") == "within_reach":
        return False
    paces = rel.get("paces")
    if paces is not None and float(paces) <= CONVERSATION_REACH_PACES:
        return False
    direct = (rel.get("open_air_loss_db") is not None
              or rel.get("din_db") is not None
              or (rel.get("far_loss_db") is not None
                  and _weather.room_exposure(scene, s_room) != "enclosed"))
    if not direct:
        return False
    facing = effective_facing(scene, speaker)
    if not facing:
        return False
    toward = _bearing_toward(scene, sound, listener, speaker, l_room, s_room)
    return relative_bearing(facing, toward) in _REAR_SECTORS


def _masks(source) -> bool:
    """Is this placed source one the hearing rule lets mask a voice: a
    standing thing at a `MASKING_LEVELS` word, or a beat's event that says
    it drowns everything."""
    if source.get("kind") == "event":
        return bool(source.get("drowns")) and float(source.get("power") or 0.0) > 0.0
    return source.get("level") in MASKING_LEVELS and \
        float(source.get("power") or 0.0) > 0.0


def quiet_floor(scene, room_id) -> float:
    """A room's QUIET FLOOR as a power: its exposure's ambient level, scaled
    by a declared quiet and a still night -- the place's own level, without
    the weather or anything running in it (`_ambient_floor` adds those for
    the field's description). What a voice from rooms away is graded
    against: rain and a fire do not mask speech, the room's own stillness
    is simply how low a sound can be and still be there."""
    from world import weather as _weather
    exposure = _weather.room_exposure(scene, room_id)
    floor = AMBIENT.get(exposure, AMBIENT["enclosed"])
    quiet = room_quiet(scene, room_id)
    if quiet:
        return floor * QUIET_SCALE[quiet]
    if exposure != "enclosed":
        try:
            scoped = _weather.weather_for_room(scene, room_id)
        except Exception:
            scoped = {}
        if _still_night(scene, scoped):
            floor *= QUIET_SCALE["hushed"]
    return floor


def _cache_key(scene, room_id, turn_idx, crowds, events) -> str:
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
    parts = [room_id, turn_idx, crowds, events, *scene_read_parts(scene)]
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _room_grid_exists(scene, room):
    """The grid gate, from the module that owns it. Imported per call rather
    than at module scope because `spatial_light_field` reads this module's
    ladders at import time."""
    from world.spatial_light_field import light_geometry_exists
    return light_geometry_exists(scene, room)


def sound_field(scene: dict, listener: str, *, room=None, turn_idx=None,
                crowds=None, events=None) -> Optional[SoundField]:
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
    extras = json.dumps([turn_idx, crowds, events],
                        sort_keys=True, default=str)
    return scene_memo(
        scene, ("sound_field", str(room), extras),
        lambda: _sound_field(scene, room, turn_idx, crowds, events))


def _sound_field(scene, room, turn_idx, crowds, events):
    """The field itself, content-cached across scene objects."""
    key = _cache_key(scene, room, turn_idx, crowds, events)
    cached = _SOUND_FIELD_CACHE.get(key)
    if cached is not None:
        return cached
    grid = acoustic_grid(scene, room)
    if grid is None:
        return None
    sources, notices = sound_sources(scene, turn_idx=turn_idx, crowds=crowds,
                                     events=events)
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
    path = far_path(scene, listener_room, source_room)
    if path is None:
        return None
    return ratio_of_db(-path["loss_db"])


#: The heaviest single edge a far path may cross and still carry a voice's
#: consonants: a shut ordinary door (`APERTURE_DB["closed_door"]`, 25), the
#: partition a raised voice and a shout cross whole in the next room
#: (`spatial_senses.hear_level`). A pane, a heavy door, a wall or a floor on
#: the way leaves a voice its low half -- a partition's loss rises about
#: 6 dB an octave -- so the line arrives in pieces at best
#: (`far_speech_level`), as one through the same pane next door does.
FAR_CLEAR_EDGE_DB = APERTURE_DB["closed_door"]


def far_path(scene, listener_room, source_room) -> Optional[dict]:
    """`{loss_db, muffled, length, via}` for a voice from `source_room`
    heard in `listener_room` over the room graph, or None where the question
    does not apply (same room, neighbours -- the hearing rule's own classes
    -- or rooms no chain of edges joins). `loss_db` is measured from the
    speaker's level at their cell; `inf` is an ANSWER: the rooms are joined
    and nothing a voice can do arrives. `length` is the path's paces and
    `via` the room it arrives from (`room_sound_flood`'s), which is what the
    wind reads the way of the sound by (`wind_bend_db`); both None for the
    `inf` answer."""
    rooms = (scene or {}).get("rooms") or {}
    listener_room, source_room = str(listener_room or ""), str(source_room or "")
    if not listener_room or not source_room or listener_room == source_room:
        return None
    if listener_room not in rooms or source_room not in rooms:
        return None
    from world.spatial_senses import rooms_adjacent
    if rooms_adjacent(scene, listener_room, source_room):
        return None
    probe = SPEECH_DB["shout"]
    rec = room_sound_flood(scene, source_room, probe).get(listener_room)
    if rec is None:
        # The flood terminates on audibility, so "no record" is two
        # different facts: the rooms are joined and a shout dies before it
        # arrives (an answer), or NO chain of edges joins them at all --
        # another world, a ship in orbit -- and the question does not apply
        # (None). Answering for the second stamped the air on a pair it has
        # no relationship to, and the composer's device rescue, which is
        # gated on the air having no answer, was withdrawn for exactly the
        # hail it exists for.
        if not _rooms_joined(scene, listener_room, source_room):
            return None
        return {"loss_db": math.inf, "muffled": True, "length": None,
                "via": None}
    return {"loss_db": probe - float(rec["db"]),
            "muffled": float(rec.get("max_edge_db") or 0.0) > FAR_CLEAR_EDGE_DB,
            "length": float(rec.get("length") or 0.0),
            "via": rec.get("via")}


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
    """What the hearing rule reads off the field, stamped on a body-to-body
    relation -- the observer listening, the target speaking -- when the
    observer's field exists and places them (`spatial_senses.hear_level`):

      * `air` -- the two rooms are one, neighbours, or joined by any chain
        of edges: the air has an answer for this pair, so being addressed by
        name is not a second channel (`composer.line_hear_level`);
      * `far_loss_db`, `far_muffled`, `floor_db` -- for rooms beyond the next
        one, what the room graph takes from the voice, whether a shut thing
        stood on the way, and the listening room's quiet floor
        (`far_speech_level`);
      * `masking_db`, `speaker_masking_db` -- only where something the story
        made deafening, or an event it says drowns everything, reaches the
        listener's ear (and the speaker's, for the rise of their voice):
        noise that decides speech for everyone (`masked_level`);
      * `din_db`, `speaker_din_db` -- where the field places both bodies
        and the noise at the listener's ear is a din (`DIN_DB`): what a
        BYSTANDER beyond conversational reach follows of the line
        (`din_level`, 2026-10-20 wave A) -- never its addressee.

    RESTATED 2026-10-20. It stamped the cell path's gain and the listener's
    whole noise floor -- a kettle, rain, a crowd -- and the verdict was their
    ratio, so the cells decided whether a voice in the same room was heard.
    A relation the field cannot speak for is returned exactly as given,
    which keeps every scene without geometry byte-identical, and the
    enclosure cases are never stamped: a voice through a body's mass is not
    on any grid.

    `sound` is a precomputed `SoundField` for the observer (a perception
    stage builds one per perceiver with the beat's crowds, events and turn
    index); absent, a field is derived from the scene alone."""
    if any(rel.get(flag) for flag in _CONDUCTED):
        return rel
    if sound is None:
        sound = sound_field(scene, observer, room=observer_room)
    if sound is None or sound.locate(observer, observer_room) is None:
        return rel
    from world.spatial_senses import rooms_adjacent
    o_room = str(observer_room or room_of(scene, observer) or "")
    t_room = str(target_room or room_of(scene, target) or "")
    if not o_room or not t_room:
        return rel
    far = far_path(scene, o_room, t_room)
    if far is not None:
        rel["air"] = True
        rel["far_loss_db"] = far["loss_db"]
        rel["far_muffled"] = far["muffled"]
        rel["floor_db"] = db_of_power(quiet_floor(scene, o_room))
    elif o_room == t_room or rooms_adjacent(scene, o_room, t_room) \
            or _rooms_joined(scene, o_room, t_room):
        rel["air"] = True
    if o_room == t_room or _open_between(scene, rel, o_room, t_room):
        loss = open_air_loss_db(scene, sound, observer, target, o_room,
                                speaker_room=t_room)
        if loss is not None:
            rel["open_air_loss_db"] = loss
            rel["floor_db"] = db_of_power(quiet_floor(scene, o_room))
    # THE WIND ON THE PATH (wave B2, `wind_bend_db`): outdoors, a voice
    # going with the wind is carried and one going against it swallowed.
    # Folded into the open air's loss, or the far field's, so every reader
    # of the budget has it; stamped as well, so `hearing_reason` can say so.
    if rel.get("open_air_loss_db") is not None or (
            rel.get("far_loss_db") is not None
            and not math.isinf(float(rel["far_loss_db"]))):
        bend = _wind_on_the_path(scene, sound, observer, target, o_room,
                                 t_room, far)
        if bend:
            rel["wind_bend_db"] = bend
            key = "open_air_loss_db" if rel.get("open_air_loss_db") \
                is not None else "far_loss_db"
            rel[key] = float(rel[key]) - bend
    paces = _pair_paces(scene, sound, observer, target, o_room, t_room, rel)
    if paces is not None:
        rel["paces"] = paces
        # A DIN AT THE LISTENER'S EAR (`DIN_DB`): what a bystander in it
        # follows of a conversation a few paces off is the din's to decide
        # (`din_level`, applied by `spatial_senses.hear_level` only to a
        # listener the line was not addressed to, beyond conversational
        # reach). Stamped only where the field places both bodies -- the
        # paces are the budget's distance -- and with the noise where the
        # SPEAKER stands, which their voice rises over.
        din = sound.noise_at(observer, room=o_room)
        if din is not None and _at_least(db_of_power(din), DIN_DB):
            rel["din_db"] = db_of_power(din)
            own = sound._field_for(t_room)
            spoken_over = own.noise_at(target, room=t_room) \
                if own is not None else None
            if spoken_over is not None:
                rel["speaker_din_db"] = db_of_power(spoken_over)
    if any(_masks(source) for source in sound.sources) or \
            any(_masks(source) for source in sound._raw_sources):
        masking = sound.masking_db_at(observer, room=o_room)
        if masking is not None:
            rel["masking_db"] = masking
            own = sound._field_for(t_room)
            spoken_over = own.masking_db_at(target, room=t_room) \
                if own is not None else None
            if spoken_over is not None:
                rel["speaker_masking_db"] = spoken_over
    # WHICH WAY THE SPEAKER FACES (wave B2): the listener in the speaker's
    # rear arc, where a budget reads the voice's direct sound
    # (`_speaker_turned_away`, `facing_loss_db`).
    if _speaker_turned_away(scene, sound, observer, target, o_room, t_room,
                            rel):
        rel["speaker_turned_away"] = True
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


# ---------------------------------------------------------------------------
# SOUND ARRIVES AFTER WHAT MADE IT (2026-10-20, wave B2; § 14.3)
# ---------------------------------------------------------------------------
#
# Light crosses any distance a story holds at once; sound crosses air at
# some 343 m/s. So a source SEEN far off is seen first and heard after --
# a distant gun's flash and then its bang, an axe falling across a valley
# and then its chock, lightning and then its thunder, three seconds a
# kilometre. Within a building the gap is a few hundredths of a second,
# under anything a body can tell. A rendering of ORDER within one beat, never
# a new beat: where a view holds both the sight of a thing and the sound it
# made, and the thing stands far enough off, the sight is told first and
# the sound after it (`perception`'s outcome pass, `composer.ambient_percepts`
# and `weather_percepts`).

#: How fast sound crosses air: 343 m/s, dry air at 20 C (331 at freezing).
SPEED_OF_SOUND_M_S = 343.0
#: THE GAP THAT READS AS "AND THEN": 0.3 s. The eye and the ear bind a sight
#: and a sound into one event across a window of roughly a tenth to a fifth
#: of a second (the audiovisual temporal binding window, about 100-200 ms
#: for a sharp event), and a third of a second is past it with room to
#: spare -- a gap a reader takes as a beat. At 343 m/s: about 103 m.
SOUND_AFTER_SIGHT_S = 0.3
SOUND_AFTER_SIGHT_M = SPEED_OF_SOUND_M_S * SOUND_AFTER_SIGHT_S
#: From this gap on the sound comes "seconds" after the sight rather than
#: "a moment" after it: 1.5 s, about half a kilometre.
SOUND_SECONDS_AFTER_S = 1.5
#: How far off the sky's flash is, for its thunder: lightning comes down
#: from a cloud base one to two kilometres up, so even a strike close by is
#: mostly that far away, and its thunder always comes seconds after the
#: flash. The middle of that.
LIGHTNING_M = 1500.0
#: The two words the delay is said by, a closed set the packs word.
SOUND_AFTER_WORDS = ("moment", "seconds")


def sound_delay_s(metres) -> float:
    """How long after a thing is seen its sound arrives, in seconds."""
    return max(0.0, float(metres)) / SPEED_OF_SOUND_M_S


def sound_after_sight(metres) -> Optional[str]:
    """One of `SOUND_AFTER_WORDS` -- how long after the sight of a thing
    `metres` off its sound arrives -- or None where the two are one moment
    (under `SOUND_AFTER_SIGHT_M`), or the distance is not known."""
    if metres is None:
        return None
    delay = sound_delay_s(metres)
    if not _at_least(delay, SOUND_AFTER_SIGHT_S):
        return None
    return "seconds" if _at_least(delay, SOUND_SECONDS_AFTER_S) else "moment"


def seen_source_metres(scene, observer, source) -> Optional[float]:
    """How far a body the observer sees stands from them, in metres: the
    straight line between their measured cells -- in one room, or across
    the observer's own composite field into a room it places beyond an
    opening, or on one site plan. None where either body is unplaced -- a
    guess never puts a sound after its sight."""
    o_room, s_room = room_of(scene, observer), room_of(scene, source)
    if not o_room or not s_room:
        return None
    if body_cell(scene, observer) is None or body_cell(scene, source) is None:
        return None
    field = sound_field(scene, observer, room=o_room)
    if field is not None:
        here, there = field.locate(observer, o_room), field.locate(source, s_room)
        if here is not None and there is not None:
            return math.hypot(here[0] - there[0], here[1] - there[1]) * PACE_M
    return _plan_line(scene, source, observer)[0]


# ---------------------------------------------------------------------------
# LOUD SOUND IS FELT (2026-10-20, wave B2; DESIGN_SOUND_FIELD.md § 14.4)
# ---------------------------------------------------------------------------
#
# A very loud low-frequency sound, and a heavy impact, are FELT as well as
# heard -- through the floor or the ground a body stands, sits or lies on,
# and in the chest: an explosion, a falling tree, a big drum, machinery a
# voice cannot be raised over. Often before the sound and beyond it: the
# structure carries a blow where the air between rooms has long since lost
# it, and a body that cannot hear feels it all the same. A percept on the
# TOUCH channel, from typed data only -- the beat's sound events on the
# impact ladder (`EVENT_DB`, or an authored `db`), a running thing or a
# place's own sound at `deafening` and above, and where the site plan stands
# the rooms -- naming no source and no direction: a body learns that
# something shook the floor, and how hard.

#: THE FELT THRESHOLD, as the level a sound holds ONE PACE from where it is
#: made: what is shaking the floor under a body standing at it. 100 dB(A),
#: the floor of the `deafening` class (machinery a voice cannot be raised
#: over, `SOUND_ONE_PACE_DB`): airborne low-frequency sound begins to be
#: felt in the body somewhere about 100-110 dB, and an impact heavy enough
#: to shake a floor -- a dropped load, a heavy door slammed, a beam coming
#: down -- is 90-110 dB(A) a metre off. So a `deafening` machine is felt by
#: a body at it, a `thunderous` sound or impact some seventy metres round,
#: and a `catastrophic` one across a town. A household thing never is, nor
#: a voice: a shout is 82.
FELT_DB = 100.0
#: WHAT THE STRUCTURE TAKES OVER DISTANCE: 3 dB a doubling of the paces from
#: the source, beyond its first pace -- the waves that carry a blow through
#: a floor slab or along the ground spread over a surface, not a sphere
#: (amplitude falling as one over the square root of the distance), where
#: airborne sound loses 6 dB a doubling. The material's own damping, which
#: shortens the longest reaches, is not counted.
FELT_SPREAD_DB_PER_DOUBLING = 3.0
#: WHAT A FLOOR TAKES between storeys: a floor is the medium vibration
#: travels by, not a barrier to it -- building-vibration practice takes some
#: 1-3 dB a floor -- so a blow overhead is felt in the room below nearly as
#: hard as above. (Airborne sound loses 50 through the same floor,
#: `FLOOR_CEILING_LOSS_DB`.)
FELT_STOREY_DB = 3.0
#: HOW HARD IT IS FELT, by the margin over `FELT_DB` -- a closed set the
#: engine owns. Ten decibels a rung, the steps in which vibration
#: perception is graded (barely perceptible, distinctly perceptible,
#: strongly perceptible: some 10 dB apart in vibration-assessment practice).
FELT_LEVELS = ("tremor", "shudder", "jolt")
FELT_SHUDDER_DB = 10.0
FELT_JOLT_DB = 20.0


def felt_word(margin_db) -> Optional[str]:
    """One of `FELT_LEVELS` for a vibration arriving `margin_db` over
    `FELT_DB`, or None under it."""
    if not _at_least(float(margin_db), 0.0):
        return None
    if _at_least(float(margin_db), FELT_JOLT_DB):
        return "jolt"
    if _at_least(float(margin_db), FELT_SHUDDER_DB):
        return "shudder"
    return "tremor"


def _structure_paces(scene, a, b) -> Optional[float]:
    """How far apart two rooms stand through the structure, in paces: the
    shortest chain of declared ways between them -- ANY way, a wall
    included, since a building carries a blow through its walls -- each
    hop the half-spans of the two rooms it joins (`room_span`). None where
    no chain joins them."""
    a, b = str(a or ""), str(b or "")
    if not a or not b:
        return None
    if a == b:
        return 0.0
    graph = far_field_graph(scene)
    spans: dict = {}

    def span(room_id):
        if room_id not in spans:
            spans[room_id] = room_span(scene, room_id)
        return spans[room_id]

    best = {a: 0.0}
    heap = [(0.0, a)]
    while heap:
        dist, room = heapq.heappop(heap)
        if room == b:
            return dist
        if dist > best.get(room, math.inf) + _DB_EPS:
            continue
        for other in sorted(graph.get(room) or ()):
            step = dist + (span(room) + span(other)) / 2.0
            if step < best.get(other, math.inf) - _DB_EPS:
                best[other] = step
                heapq.heappush(heap, (step, other))
    return None


def _felt_reach(scene, source, listener, l_room) -> Optional[tuple]:
    """`(paces, storeys)` between a source and a listener's body for the
    felt rule: in one room the straight line between the source's cell and
    the body's; on one site plan the straight line across the plan and the
    storeys between the two floors; else the structure's chain of rooms
    (`_structure_paces`) and the storeys their `level`s set apart."""
    from world.site_plan import STOREY_M, room_elevation_m, room_level
    s_room = str(source.get("room") or "")
    if s_room == str(l_room):
        here = body_cell(scene, listener) or room_centre(scene, l_room)
        there = source.get("cell") or room_centre(scene, s_room)
        return math.hypot(here[0] - there[0], here[1] - there[1]), 0
    metres, _bearing = _plan_line(scene, None, listener,
                                  a_at=(s_room, source.get("cell")))
    if metres is not None:
        storeys = round(abs(room_elevation_m(scene, s_room)
                            - room_elevation_m(scene, l_room)) / STOREY_M)
        return metres / PACE_M, int(storeys)
    paces = _structure_paces(scene, s_room, l_room)
    if paces is None:
        return None
    return paces, abs(room_level(scene, s_room) - room_level(scene, l_room))


def _felt_source_db(source, events) -> Optional[float]:
    """The level ONE PACE from where a source is made, for the felt rule:
    a beat's impact by its own event (the impact ladder, or its authored
    `db`, never the `drowns` pricing, which is about masking), a running
    thing or a place's own sound by its power at its cell. None for a
    footfall, which has its own way through the floor (`tread_events`), and
    for a crowd, whose talk is no blow."""
    kind = source.get("kind")
    if kind == "crowd":
        return None
    if kind == "event":
        try:
            event = (events or [])[int(str(source["id"]).split(":")[1])]
        except (IndexError, ValueError, KeyError):
            return None
        if not isinstance(event, dict) or event.get("tread"):
            return None
        return event_db(event) - _ONE_PACE_LOSS_DB
    return db_of_power(source.get("power")) - _ONE_PACE_LOSS_DB


def felt_through_ground(scene, room_id) -> bool:
    """Does a body in this room stand on the GROUND rather than a floor: a
    room under the open sky that declares no `floor` of its own (a deck, a
    boardwalk and a stage under the sky name theirs)."""
    from world import weather as _weather
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict) or str(room.get("floor") or "").strip():
        return False
    return _weather.room_exposure(scene, room_id) == "open"


def felt_vibrations(scene: dict, listener: str, *, room=None, events=None,
                    turn_idx=None) -> list:
    """WHAT THIS BODY FEELS THROUGH WHAT IT STANDS ON: `[{felt, standing,
    key, db}]`, hardest first -- `felt` one of `FELT_LEVELS`, `standing`
    True for a running thing or a place's own sound (a steady trembling)
    and False for one of the beat's events (a blow), `key` the source's id,
    `db` the margin over `FELT_DB`.

    A source is felt where its level a pace from where it is made, less the
    structure's spreading over the paces between it and the body
    (`FELT_SPREAD_DB_PER_DOUBLING`) and a floor's loss for every storey
    between them (`FELT_STOREY_DB`), stands at or over `FELT_DB`. NOT GATED
    BY HEARING: a body that cannot hear feels it all the same, and a wall
    the air could not cross is the structure that carries it. A body off
    the ground (`site_plan.body_altitude_m`, a flier) feels nothing through
    a floor it is not on."""
    from world.site_plan import REACH_ALTITUDE_M, body_altitude_m
    l_room = str(room or room_of(scene, listener) or "")
    rooms = (scene or {}).get("rooms") or {}
    if not l_room or l_room not in rooms:
        return []
    sources, _notices = sound_sources(scene, turn_idx=turn_idx, events=events)
    loud = []
    for source in sources:
        level = _felt_source_db(source, events)
        if level is not None and _at_least(level, FELT_DB):
            loud.append((source, level))
    if not loud:
        return []                      # the ordinary beat: nothing shakes
    if body_altitude_m(scene, listener) >= REACH_ALTITUDE_M:
        return []
    out = []
    for source, level in loud:
        reach = _felt_reach(scene, source, listener, l_room)
        if reach is None:
            continue
        paces, storeys = reach
        arrived = level - FELT_SPREAD_DB_PER_DOUBLING * math.log2(
            max(1.0, float(paces))) - FELT_STOREY_DB * storeys
        word = felt_word(arrived - FELT_DB)
        if word is None:
            continue
        out.append({"felt": word, "standing": source.get("kind") != "event",
                    "key": str(source.get("id") or ""),
                    "db": round(arrived - FELT_DB, 1)})
    out.sort(key=lambda r: -r["db"])
    return out


def tread_gait(pace) -> str:
    """One of `TREAD_GAITS` for a walk's `pace`; anything else is a walk."""
    word = str(pace or "walk").strip().casefold()
    return word if word in TREAD_GAITS else "walk"


def footfall_db(scene, room_id, gait) -> float:
    """What a footfall in `room_id` puts into the room under it, in dB: the
    room's own floor word (`FLOOR_IMPACT_DB`, masonry for a word it does not
    hold -- UNBUILT_WORLD § 1.209), a run's `TREAD_RUN_DB` over a walk, a
    sneak's `TREAD_SNEAK_DB` under it."""
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    material = str((room or {}).get("floor") or "").strip().casefold() \
        if isinstance(room, dict) else ""
    level = FLOOR_IMPACT_DB.get(material, FLOOR_IMPACT_DB["stone"])
    gait = tread_gait(gait)
    if gait == "run":
        level += TREAD_RUN_DB
    elif gait == "sneak":
        level -= TREAD_SNEAK_DB
    return float(level)


def _footfall_heard(scene, room_id, level_db) -> bool:
    """Is a footfall arriving at `level_db` heard at all in `room_id`: over
    the room's own floor -- the place and the weather it hears
    (`_ambient_floor`) -- at a sound's margins (`quantise_hearing_db`). A
    sound under the room it is heard in is not heard."""
    return quantise_hearing_db(
        level_db, db_of_power(_ambient_floor(scene, room_id))) != "none"


def _rooms_beside(scene, room_id, exclude=()) -> list:
    """The rooms on `room_id`'s storey a footfall in it reaches through the
    structure rather than the air: those its plan sets wall to wall with it
    (`site_plan.plan_rooms_beside`), and those a declared way that is not an
    opening joins it to on the same storey -- a shut door, a curtain, a
    wall, a pane. A room an opening joins hears the walker's own tread
    through the opening (the near field), so it is not one of these."""
    from world.site_plan import plan_rooms_beside
    from world.spatial_levels import room_level
    from world.spatial_orientation import normalize_vertical
    from world.spatial_routing import spatial_rel
    from world.spatial_senses import OPEN_BARRIERS
    rooms = (scene or {}).get("rooms") or {}
    here_level = room_level(scene, room_id)
    found = list(plan_rooms_beside(scene, room_id))
    for rid in sorted(rooms, key=str):
        edge = _declared_edge(scene, room_id, rid)
        if str(rid) == str(room_id) or str(rid) in found or edge is None:
            continue
        if normalize_vertical(edge.get("vertical")) \
                or room_level(scene, rid) != here_level:
            continue
        found.append(str(rid))
    out = []
    for rid in found:
        if rid in exclude or rid not in rooms:
            continue
        edge = _declared_edge(scene, room_id, rid)
        if edge is not None and normalize_vertical(edge.get("vertical")):
            continue
        rel = spatial_rel(scene, rid, room_id)
        barrier = _material_shifted_barrier(
            normalize_barrier(rel.get("barrier")), rel.get("material"))
        if barrier in OPEN_BARRIERS:
            continue
        out.append(rid)
    return out


def _declared_edge(scene, a, b) -> Optional[dict]:
    """The edge either room declares toward the other, or None."""
    rooms = (scene or {}).get("rooms") or {}
    for x, y in ((a, b), (b, a)):
        room = rooms.get(x)
        for edge in (room.get("adjacent") or ()) if isinstance(room, dict) else ():
            if isinstance(edge, dict) and str(edge.get("to") or "") == str(y):
                return edge
    return None


def tread_events(scene: dict, movers) -> list:
    """The beat's footfalls as one-beat sound events: for every body in
    `movers` ({name: pace}) a tread in its own room at `TREAD_LEVEL`, one in
    every room it lies over with a floor between, at the floor's impact
    level (`footfall_db`), and one in every room beside it on its storey a
    flanking path's `FOOTFALL_FLANKING_DB` under that. Events reach a
    listener the way every other beat sound does -- in the room, through
    the near field, and by the far flood -- and their `detail` is a sound
    fact that names nobody: the listener learns that someone moves overhead,
    never who. Before 2026-09-15 a man climbing three storeys of stone stair
    made no sound anywhere.

    FOOTSTEPS COME THROUGH FLOORS (2026-10-20, wave A, DESIGN_SOUND_FIELD
    § 12). The room under is the one the plan sets under the walker's room
    (`site_plan.plan_rooms_below`) as well as one the room declares it lies
    `over` (`spatial_levels.floor_edges`) -- only 4 of the 238 sited rooms
    in the owner's scenes declared one, so a body pacing a cottage's
    bedroom reached nobody in the kitchen under it -- and never a room a way
    joins it to: a stair carries a tread through the air. A tread a room
    could not hear over its own floor (`_footfall_heard`) is not filed
    there: a sneak on stone, a walk next door to a stone floor. A SNEAK
    (`TREAD_SNEAK_DB`) makes no tread in its own room -- not being heard
    there is what the gait is -- and a softer one through the floor.
    """
    from language_runtime import compositor_text
    from world.site_plan import plan_rooms_below
    from world.spatial_levels import floor_edges
    rooms = (scene or {}).get("rooms") or {}
    out = []
    for name, pace in sorted((movers or {}).items()):
        room = room_of(scene, name)
        if not room or room not in rooms:
            continue
        gait = tread_gait(pace)
        tread = compositor_text("sound_tread_" + gait)
        if gait in TREAD_LEVEL:
            out.append({"kind": "sound", "room": str(room),
                        "level": TREAD_LEVEL[gait], "source": str(name),
                        "detail": tread, "tread": True})
        impact = footfall_db(scene, room, gait)
        under = [str(e["to"]) for e in floor_edges(scene, room)
                 if e.get("vertical") == "down" and e["to"] in rooms]
        under += [rid for rid in plan_rooms_below(scene, room)
                  if rid not in under and rid in rooms
                  and _declared_edge(scene, room, rid) is None]
        for rid in under:
            if not _footfall_heard(scene, rid, impact):
                continue
            out.append({"kind": "sound", "room": rid, "db": impact,
                        "source": str(name), "tread": True,
                        "detail": compositor_text("sound_tread_overhead",
                                                  tread=tread)})
        beside = impact - FOOTFALL_FLANKING_DB
        for rid in _rooms_beside(scene, room, exclude=under):
            if not _footfall_heard(scene, rid, beside):
                continue
            from world.spatial_routing import spatial_rel
            from world.spatial_senses import _sound_barrier_phrases
            barrier = normalize_barrier(spatial_rel(scene, rid, room).get("barrier"))
            phrases = _sound_barrier_phrases()
            where = phrases.get(barrier) or phrases.get("wall") or ""
            out.append({"kind": "sound", "room": rid, "db": beside,
                        "source": str(name), "tread": True,
                        "detail": compositor_text("sound_tread_beside",
                                                  tread=tread, where=where)})
    return out


#: Where a door event sounds: the doorway of the event's room onto the room
#: this names (`door_events`, and the seeding rung in `sound_field`).
DOOR_SOURCE_PREFIX = "door:"
#: How loud a door is worked, at its doorway: the event ladder's quietest
#: word, a door opened or shut with care. A slam is the Director's to write
#: as a sound of its own; this is only the noise a doorway makes by changing.
DOOR_LEVEL = "faint"
#: The barriers a door stands in, open or shut. A way with no door in it
#: (`open`), a curtain (`membrane`) and a window are not doors being worked.
_DOOR_OPEN = {"open_door": True, "closed_door": False}


def door_events(prev_scene: dict, scene: dict) -> list:
    """Every doorway that went from shut to open, or open to shut, between
    `prev_scene` and `scene`, as one-beat sound events: one in each of the
    two rooms it joins, sounding at that room's side of the doorway, so a
    body in either room hears it as its own and one further off hears it
    through the field. Both carry the same `detail`, so a listener the two
    reach hears one door. Reads the two scenes' edges -- the typed barrier --
    and never prose; names nobody who worked it.

    A DOOR OPENED BEHIND YOU IS HEARD. Chat 168 turn 4591 (2026-10-12):
    Tamamo slid Hinami's shoji open a hand's width; the resolve's prose had
    "a soft rasp of paper and a dry tick of wood", no sound event was
    written, and the body lying three paces off with her back to the door
    was told nothing at all. A barrier changing state is a sound the
    doorway makes, whoever wrote the change."""
    from language_runtime import compositor_text
    from world.spatial_barriers import normalize_barrier
    rooms_now = (scene or {}).get("rooms") or {}
    rooms_then = (prev_scene or {}).get("rooms") or {}

    def _edge(rooms, rid, to):
        room = rooms.get(rid)
        for edge in (room or {}).get("adjacent") or () if isinstance(room, dict) else ():
            if isinstance(edge, dict) and str(edge.get("to") or "") == to:
                return edge
        return None

    out, seen = [], set()
    for rid, room in sorted(rooms_now.items()):
        if not isinstance(room, dict):
            continue
        for edge in room.get("adjacent") or ():
            if not isinstance(edge, dict):
                continue
            to = str(edge.get("to") or "")
            pair = tuple(sorted((str(rid), to)))
            if not to or to == str(rid) or to not in rooms_now or pair in seen:
                continue
            before = _edge(rooms_then, str(rid), to)
            if before is None:
                continue                      # a doorway the beat made is not one worked
            now = _DOOR_OPEN.get(normalize_barrier(edge.get("barrier")))
            then = _DOOR_OPEN.get(normalize_barrier(before.get("barrier")))
            if now is None or then is None or now == then:
                continue
            seen.add(pair)
            detail = compositor_text("sound_door_opens" if now else "sound_door_shuts")
            for here, there in ((str(rid), to), (to, str(rid))):
                out.append({"kind": "sound", "room": here, "level": DOOR_LEVEL,
                            "source": DOOR_SOURCE_PREFIX + there, "detail": detail})
    return out


def normalize_sensory_event(event, rooms=None) -> Optional[dict]:
    """One `state_diff.sensory_events` entry as the engine holds it, or None
    where it names no room the scene has.

    `{kind, room, level | db, source, detail, drowns}` -- the note's shape,
    and a closed set of keys. `kind` is the SENSE the event arrives on and defaults
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
    if event.get("drowns") is True:
        # THE STORY SAYS IT DROWNS EVERYTHING OUT, for as long as it lasts:
        # the one beat sound that may take a voice away (`MASKING_LEVELS`'
        # sibling, `masked_level`). Only a literal true: a word here is not
        # an instruction the engine can price.
        out["drowns"] = True
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
# `distant_sounds` returns before it builds anything. A beat with a
# running machine or a klaxon in it (`deafening` and up on the emission
# ladder since 2026-10-20, when `loud` came down to a household level; any
# `loud` impact) walks the room graph once per such source, which is a
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
#: standing `deafening` source and the two far rungs, and on the impact
#: ladder `loud` (72) and up -- a hearth fire (53) and a household `loud`
#: (68 at the cell since 2026-10-20: a television turned up, a kettle's
#: whistle) stay near-field things you meet at the door. Until 2026-10-20 a
#: standing `loud` was 83 at its cell and entered, so a kettle the opening
#: wrote `loud` was heard rooms away (chat 176 turn 2). A bare room's ring
#: can still lift a `loud` over the entry (`ring_boost_db`): a ringing hall
#: hands its doorways more than a furnished one, which is the physics. A voice never enters, at any volume, and not because of this number
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
#: ...AND LOUD IN ITS OWN RIGHT. Twenty over a dead room's floor is 35 dB,
#: a key dropped two storeys down, and "drowns everything" was said of it
#: (Hollin Mill turn 3, 2026-09-15). A sound nothing can be done through
#: arrives at least as loud as ordinary talk in the room: 50 dB at the
#: listener, which a `deafening` crash next door clears (56) and a key
#: two floors down does not (39). The owner's number.
OVERWHELMING_FLOOR_DB = 50.0


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

    Undirected because a doorway is one object and may be declared from
    either side, and a path has no direction. Where both sides declare it
    and disagree, the SMALLER loss wins -- the permissive reading, and the
    one that cannot silence a sound because of which room's author was more
    careful.

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
    """`{room_id: {"db", "length", "barrier_db", "via", "max_edge_db"}}` for every room a
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
                          "length": span0, "barrier_db": 0.0, "via": None,
                          "max_edge_db": 0.0}}
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
                           "barrier_db": barrier, "via": room,
                           # The heaviest single edge on the way: what a
                           # voice that came by it lost its consonants to
                           # (`far_path`).
                           "max_edge_db": max(rec["max_edge_db"],
                                              graph[room][other])}
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
    if _at_least(level_db, max(floor_db + OVERWHELMING_MARGIN_DB, OVERWHELMING_FLOOR_DB)):
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


def _wind_on_a_sound(scene, source, listener, l_room, rec) -> float:
    """`wind_bend_db` for a far-field sound reaching `listener`: the straight
    line from the sound's own cell to the listener on their site plan where
    both stand on one, else the flood's path (`rec["length"]`) and the way
    it arrives by (from `rec["via"]` into the listener's room). 0.0 unless
    both ends are under the sky (`_outdoors`)."""
    s_room = str(source.get("room") or "")
    if not _scene_wind(scene)[1] or not _outdoors(scene, s_room, l_room):
        return 0.0
    metres, bearing = _plan_line(scene, None, listener,
                                 a_at=(s_room, source.get("cell")))
    if bearing is None and rec.get("via"):
        from world.spatial_orientation import travel_bearing
        metres = float(rec.get("length") or 0.0) * PACE_M
        bearing = travel_bearing(scene, str(rec["via"]), l_room)
    if metres is None or not bearing:
        return 0.0
    return wind_bend_db(scene, bearing, metres)


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
        # THE WIND ON THE WAY (wave B2): outdoors at both ends, a bell
        # downwind carries a few decibels further and one upwind falls into
        # the shadow (`wind_bend_db`).
        level = float(rec["db"]) + _wind_on_a_sound(
            scene, source, listener, listener_room, rec)
        word = distant_level_word(level, floor_db)
        if word is None:
            continue
        out.append({"kind": "sound", "level": word,
                    "db": round(level, 1),
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


def room_still_sounding(scene: dict, room, *, sound=None) -> bool:
    """Is a standing source in this room still SOUNDING this beat -- running,
    at any level, and not out on a failing beat?

    The half of the `ceased` question `room_holds_a_standing_source` leaves
    open. A room goes even at `quiet` with a source standing in it two ways:
    the source stopped, or it fell below the voice it had been drowning and
    went on. The noise words measure what a sound does to a voice one pace
    off, so `quiet` says "you can talk over it", never "silent". Chat 157
    turn 4482: the Director's prose had the TARDIS's din "gentle into a hum"
    an hour from landing, the hand moved the console's `sound_source` from
    loud to audible with it still running, and the view said "The noise has
    stopped." -- which the page made "a silence so total your ears ring with
    it", the ship still in flight.

    Read from the field's own sources -- the one `room_noise_word` grades,
    built the same way when none is handed in -- so a switched-off source
    and a failing one that went out this beat answer False here, and a crowd
    the field carries answers True, exactly as they count in the grading.
    """
    rid = str(room or "")
    if not rid or not isinstance(scene, dict):
        return False
    field = sound if sound is not None else sound_field(scene, rid, room=rid)
    sources = getattr(field, "sources", None) or ()
    return any(isinstance(source, dict) and str(source.get("room") or "") == rid
               and source.get("kind") in ("entity", "crowd")
               and float(source.get("power") or 0.0) > 0.0
               for source in sources)


def _cell_noise(field, room, cell) -> float:
    """The room's STANDING noise at one CELL of `room` on this field: the
    room's ambient floor plus every standing source's intensity there
    (`STANDING_SOURCE_KINDS`). One arithmetic, so `sound_shape`'s grading
    and `room_noise_word`'s sweep cannot disagree.

    The room's tone, not the beat's: a one-beat event and a spoken line are
    reported as themselves, and counted here they graded a room by a single
    clank -- two windlass impacts made the whole weir read "in the din"
    around a waterwheel that makes no sound at all, and the sentence named
    no source because the shape refuses to name a one-beat one (playerless
    Aldermill round 5, 2026-09-23, idx 14). `SoundField.noise_at` is the
    MASKING floor for one body and counts everything, as masking must."""
    total = field.ambient.get(room, AMBIENT["enclosed"])
    for source in field.sources:
        if source.get("kind") not in STANDING_SOURCE_KINDS:
            continue
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
            # a doorway's pseudo-anchor, or a window's: only the first is a
            # door (`spatial_geometry.is_door_anchor`)
            if str(row["anchor"]).startswith("door:"):
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
