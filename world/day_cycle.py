"""The day: an hour derived from the clock, a phase derived from the hour.

WHAT WAS MISSING. The engine kept an exact story clock (`simulation_clock.
elapsed_seconds`) and a standing time-of-day LABEL (`scene.time_of_day`,
free text the Director declared once), and nothing joined them. The label
was written at the opening and again only when a beat explicitly declared a
new one, so a story that ran 64.9 hours across forty beats read "mid-morning"
on every one of them (the Harrowmere playtest, 2026-09-02): the number moved
and the word did not, and every reader in the tree -- the Director's payload,
a background voice's block, the ambience bucket, the clock's own display --
reads the word.

THE SHAPE. One ANCHOR, set when a readable time is first declared: the hour
of the day the clock stood at when `elapsed_seconds` was zero. From then on
the hour is arithmetic -- ``(anchor + elapsed / 3600) % day_length`` -- and
the phase is a lookup over a closed table of FRACTIONS of the day, so a
world with a thirty-hour day scales every phase with it rather than keeping
a Terran dawn at 06:00 on a planet whose sun is elsewhere. Nothing is
integrated, nothing ticks: the same "recompute from the clock at contact,
commit only branches" rule `world/routines.py` states, applied to the sky.

A label the Director declares is still authority: it RE-ANCHORS the clock
when it names a phase the derived hour is not in (a time skip the Director
expressed as "the next morning" rather than as seconds), it is left standing
verbatim while the clock is still inside the phase it names (an author's
"before dawn" is not rewritten to "pre-dawn" on the beat it was written),
and a label this table cannot read -- a stardate with no clock reading in it
-- stands untouched because the cycle cannot say it is wrong. The cycle
engages only once something readable has anchored it; a story that has never
said what time it is keeps saying nothing, which is the fail-open every
other gate in the engine uses.

PURE. No I/O, no model, no clock of its own: a caller hands in the stored
clock record and the author's style guide and gets numbers and names back.
"""

from __future__ import annotations

import math
import re

#: A Terran day. The one default; the author's style guide overrides it per
#: story (`day_length_hours`), because a fiction may take place on a world
#: whose sun keeps other hours.
DAY_LENGTH_HOURS_DEFAULT = 24.0

#: The phases of a day as FRACTIONS of it, in order, each with the fraction
#: it starts at and the fraction it ends at. Night wraps past the day's end,
#: which is why it is the one entry whose end exceeds 1.0. Closed and owned
#: by the engine: a phase name is a token every reader below agrees on
#: (`dressing.backdrops.time_bucket` buckets every one of them), so this is
#: a schema, not a guess at English. On a 24-hour day the boundaries fall at
#: 22:00, 04:30, 06:00, 07:00, 11:00, 13:30, 18:00 and 19:30.
PHASES = (
    ("night", 22.0 / 24.0, 28.5 / 24.0),
    ("pre-dawn", 4.5 / 24.0, 6.0 / 24.0),
    ("dawn", 6.0 / 24.0, 7.0 / 24.0),
    ("morning", 7.0 / 24.0, 11.0 / 24.0),
    ("midday", 11.0 / 24.0, 13.5 / 24.0),
    ("afternoon", 13.5 / 24.0, 18.0 / 24.0),
    ("dusk", 18.0 / 24.0, 19.5 / 24.0),
    ("evening", 19.5 / 24.0, 22.0 / 24.0),
)
PHASE_NAMES = tuple(name for name, _start, _end in PHASES)

#: What the sun gives an outdoor room to see by in each phase, on the light
#: ladder `world/spatial_light.LIGHT_LEVELS` reads. Dark from the end of
#: evening to first light, dim at the two edges, lit through the day. Never
#: "bright": glare is a declaration a room makes about itself, not a
#: property of noon everywhere.
SUN_LIGHT = {
    "night": "dark", "pre-dawn": "dark", "dawn": "dim",
    "morning": "lit", "midday": "lit", "afternoon": "lit",
    "dusk": "dim", "evening": "dark",
}

#: Skies that take one step off the daylight. Fog and cloud dim a lit room
#: to dim and never further -- a foggy dusk is not pitch black, and the
#: darkness a storm brings is the storm's own declaration to make.
DIMMING_SKIES = frozenset({"overcast", "storm", "fog"})

#: The phases a charter body spends in its berth rather than on an errand
#: -- nobody walks to the market at three in the morning -- and the phases
#: it goes out for its own sake, to a commons, rather than to the place its
#: needs are fed from. Read by `world/charter_move.errands`.
RESTING_PHASES = frozenset({"night", "pre-dawn"})
SOCIAL_PHASES = frozenset({"dusk", "evening"})

#: A clock reading inside a label. The three alternatives each capture
#: exactly (hour, minute); the guards are the ones the corpus earned
#: (`dressing/backdrops.py` carried this regex first, and its comment): a
#: colon form may not follow a sign, or a countdown ("-01:45:00") reads as
#: quarter to two; a bare four-digit form needs a leading zero ("0830") or a
#: unit ("1430 hours"), or every year in every opening ("Late night, 2026")
#: becomes twenty past eight; and the minute must be a real minute, which
#: is what stops "1893" reading as 18:93.
CLOCK_READING = re.compile(
    r"(?<![-+\d])(\d{1,2}):(\d{2})"
    r"|(?<![-+\d])0(\d)(\d{2})(?!\d)"
    r"|(?<![-+\d])(\d{2})(\d{2})(?=\s*(?:hours|hrs|h\b))"
)
PM_MARKER = re.compile(r"^[^a-z0-9]{0,3}(?:\d{1,2}\s*)?p\.?\s?m\.?")

#: Which phase a written label names. Categories, not vocabulary: each row
#: is the handful of ways English names one part of the day, checked in an
#: order that lets a longer phrase win over the word inside it ("before
#: dawn" is not dawn, "nightfall" is not night). Extending a row widens what
#: the cycle can READ; a label outside every row is not wrong, it is simply
#: one the cycle leaves standing. `dressing.backdrops.time_bucket` keeps its
#: own coarser four-bucket table for the scenery caches and reads every
#: phase name here.
_PHASE_WORDS = (
    ("pre-dawn", ("pre-dawn", "predawn", "pre dawn", "small hours",
                  "before dawn", "before first light", "before sunrise")),
    ("dusk", ("dusk", "sunset", "sundown", "twilight", "gloaming")),
    ("evening", ("evening", "nightfall")),
    ("dawn", ("dawn", "sunrise", "daybreak", "first light", "sunup")),
    ("night", ("night", "midnight", "after dark", "nocturn")),
    ("afternoon", ("afternoon",)),
    ("midday", ("midday", "noon")),
    ("morning", ("morning",)),
)


# ---------------------------------------------------------------------------
# Arithmetic.
# ---------------------------------------------------------------------------

def day_length_hours(style_guide=None) -> float:
    """The story's day, in hours: the author's dial or the Terran default."""
    raw = (style_guide or {}).get("day_length_hours") \
        if isinstance(style_guide, dict) else None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DAY_LENGTH_HOURS_DEFAULT
    if not math.isfinite(value) or value <= 0.0:
        return DAY_LENGTH_HOURS_DEFAULT
    return value


def hour_of_day(elapsed_seconds, anchor_hour, day_length=DAY_LENGTH_HOURS_DEFAULT) -> float:
    """Where the sun stands: the anchor plus everything the clock has run."""
    length = max(1e-9, float(day_length))
    return (float(anchor_hour) + float(elapsed_seconds or 0.0) / 3600.0) % length


def day_fraction(hour, day_length=DAY_LENGTH_HOURS_DEFAULT) -> float:
    length = max(1e-9, float(day_length))
    return (float(hour) % length) / length


def phase_at(fraction) -> str:
    """The phase a fraction of the day falls in. Total: every fraction in
    [0, 1) is inside exactly one span, and the wrap is night's."""
    f = float(fraction) % 1.0
    for name, start, end in PHASES:
        if start <= f < end or start <= f + 1.0 < end:
            return name
    return "night"


def phase_of_hour(hour, day_length=DAY_LENGTH_HOURS_DEFAULT) -> str:
    return phase_at(day_fraction(hour, day_length))


def phase_midpoint_hour(phase, day_length=DAY_LENGTH_HOURS_DEFAULT):
    """The hour a bare phase word anchors to: the middle of its span. None
    for a word that is not a phase."""
    length = max(1e-9, float(day_length))
    for name, start, end in PHASES:
        if name == phase:
            return (((start + end) / 2.0) % 1.0) * length
    return None


def phase_bounds_hours(phase, day_length=DAY_LENGTH_HOURS_DEFAULT):
    """``(start_hour, end_hour)`` of a phase on this world's day, or None.
    Night's end exceeds the day length, as its fraction does."""
    length = max(1e-9, float(day_length))
    for name, start, end in PHASES:
        if name == phase:
            return start * length, end * length
    return None


def sun_light(phase, sky=None) -> str:
    """What an outdoor room has to see by, from the sky alone."""
    level = SUN_LIGHT.get(str(phase or ""), "lit")
    if level == "lit" and str(sky or "").strip().casefold() in DIMMING_SKIES:
        return "dim"
    return level


# ---------------------------------------------------------------------------
# Reading a label.
# ---------------------------------------------------------------------------

def clock_reading_hour(text):
    """The hour a clock reading inside `text` names, as a float in [0, 24),
    or None when the text carries none this reader trusts."""
    text = str(text or "").casefold()
    for match in CLOCK_READING.finditer(text):
        found = [g for g in match.groups() if g is not None]
        hour, minute = int(found[0]), int(found[1])
        if hour > 23 or minute > 59:
            continue
        if hour < 12 and PM_MARKER.match(text[match.end():match.end() + 12]):
            hour += 12
        return float(hour) + float(minute) / 60.0
    return None


def label_phase(label, day_length=DAY_LENGTH_HOURS_DEFAULT):
    """The phase a written time-of-day label names, or None.

    A clock reading is read first -- it is the more exact statement -- and
    placed on THIS world's day; a phase word is read second. On a world whose
    day is shorter than the reading (a 20-hour day, a "22:00" label) the
    reading is refused rather than wrapped, because it cannot be a time on
    that clock.
    """
    text = str(label or "").casefold().strip()
    if not text:
        return None
    hour = clock_reading_hour(text)
    if hour is not None:
        if hour >= float(day_length):
            return None
        return phase_of_hour(hour, day_length)
    for name, words in _PHASE_WORDS:
        if any(word in text for word in words):
            return name
    return None


def label_hour(label, day_length=DAY_LENGTH_HOURS_DEFAULT):
    """The hour a label anchors the clock to: the reading itself when it
    carries one, the middle of the phase it names otherwise, None when it
    names neither."""
    text = str(label or "").casefold().strip()
    if not text:
        return None
    hour = clock_reading_hour(text)
    if hour is not None:
        return hour if hour < float(day_length) else None
    phase = label_phase(text, day_length)
    return phase_midpoint_hour(phase, day_length) if phase else None


# ---------------------------------------------------------------------------
# The clock record.
# ---------------------------------------------------------------------------

def anchor_from_hour(hour, elapsed_seconds, day_length=DAY_LENGTH_HOURS_DEFAULT) -> float:
    """The anchor that puts the clock at `hour` when it reads `elapsed`."""
    length = max(1e-9, float(day_length))
    return (float(hour) - float(elapsed_seconds or 0.0) / 3600.0) % length


def clock_anchor(clock, style_guide=None):
    """``(anchor_hour, day_length)`` for a stored clock record.

    The stored anchor wins. A clock that has none but carries a readable
    label (the greeting path seeds `display` before turn 0 runs) anchors on
    that label at its own elapsed; failing that, the author's `opening_hour`
    dial. None for the anchor means the cycle has nothing to stand on and
    every reader keeps today's behaviour.
    """
    length = day_length_hours(style_guide)
    record = clock if isinstance(clock, dict) else {}
    raw = record.get("anchor_hour")
    if raw is not None:
        try:
            return float(raw) % length, length
        except (TypeError, ValueError):
            pass
    try:
        elapsed = float(record.get("elapsed_seconds") or 0.0)
    except (TypeError, ValueError):
        elapsed = 0.0
    hour = label_hour(record.get("display"), length)
    if hour is None and isinstance(style_guide, dict):
        raw = style_guide.get("opening_hour")
        try:
            hour = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            hour = None
        if hour is not None and not (0.0 <= hour < length):
            hour = None
    if hour is None:
        return None, length
    return anchor_from_hour(hour, elapsed, length), length


def describe(clock, style_guide=None):
    """``{"hour_of_day", "phase", "day_length_hours"}`` for a clock record, or
    None when the record cannot be anchored."""
    anchor, length = clock_anchor(clock, style_guide)
    if anchor is None:
        return None
    try:
        elapsed = float((clock or {}).get("elapsed_seconds") or 0.0)
    except (TypeError, ValueError, AttributeError):
        elapsed = 0.0
    hour = hour_of_day(elapsed, anchor, length)
    return {"hour_of_day": round(hour, 2), "phase": phase_of_hour(hour, length),
            "day_length_hours": length}


# ---------------------------------------------------------------------------
# The charter's own copy of the day.
# ---------------------------------------------------------------------------

def charter_phase(charter, at_hours):
    """The phase a charter's clock stands in at `at_hours`, or None for an
    institution that was never told when its day begins.

    A charter counts its own hours from zero (`clock_hours`); the story tells
    it once (`day_anchor_hours`: the story's hour of the day at charter hour
    zero) and it carries the rest itself, so a presimulated month and an
    in-play window read the same table.
    """
    record = charter if isinstance(charter, dict) else {}
    anchor = record.get("day_anchor_hours")
    if anchor is None:
        return None
    try:
        anchor = float(anchor)
        length = float(record.get("day_length_hours") or DAY_LENGTH_HOURS_DEFAULT)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(length) or length <= 0.0:
        length = DAY_LENGTH_HOURS_DEFAULT
    return phase_of_hour((anchor + float(at_hours or 0.0)) % length, length)


def charter_hour(charter, at_hours):
    """The story hour of the day at charter hour `at_hours`, or None."""
    record = charter if isinstance(charter, dict) else {}
    anchor = record.get("day_anchor_hours")
    if anchor is None:
        return None
    try:
        anchor = float(anchor)
        length = float(record.get("day_length_hours") or DAY_LENGTH_HOURS_DEFAULT)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(length) or length <= 0.0:
        length = DAY_LENGTH_HOURS_DEFAULT
    return (anchor + float(at_hours or 0.0)) % length
