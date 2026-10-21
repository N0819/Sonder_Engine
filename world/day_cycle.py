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

#: WHERE ONE OF THE STORY'S DAYS TURNS INTO THE NEXT, as a fraction of the
#: day: where its night ends. The night belongs to the day before it -- "the
#: next morning" said at one in the morning is the one a few hours off, not
#: the one a day and a few hours off -- so a count of days (`seconds_until`'s
#: `days`) starts each day where `PHASES` ends the night. Derived from the
#: table rather than restated, so a table that moved the night would move it.
DAY_TURNS_AT = max(end for _name, _start, end in PHASES) % 1.0

#: THE RESOLUTION THE ENGINE PRICES A SPAN OF THE DAY TO, in seconds:
#: `seconds_until` rounds to it. A skip solved to where a part of the day
#: begins lands within half of it either side of that boundary, and the sum a
#: commit adds it into carries floating-point noise besides, so a reading this
#: close SHORT of where a part of the day begins is read as having reached it
#: (`phase_of_hour`). Measured (2026-10-21) on 17,545 skips to a part of the
#: day solved from random clocks (a 4-decimal anchor, a whole number of
#: elapsed seconds): 7,291 landed a fraction of a second short and the clock
#: read the part of the day before the one the beat was sent to; with this,
#: none. A tenth of a second is no time a story tells.
SPAN_RESOLUTION_SECONDS = 0.1

#: HOW FINELY A CLOCK'S ANCHOR IS STORED, in decimal places of an hour. Every
#: reader of where a stage begins takes the stored anchor plus the elapsed
#: seconds (`clock_hour`), and the commit reads its own phase from the anchor
#: as stored, so a clock re-anchored onto the start of a part of the day must
#: still read that part: a millionth of an hour is 0.0036 seconds, well
#: inside `SPAN_RESOLUTION_SECONDS`, where the four decimals it was stored to
#: until 2026-10-21 carried such a clock up to 0.18 seconds back across the
#: boundary.
ANCHOR_DECIMALS = 6

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

#: What the three dimming AXIS states meant when they were five sky words.
#: Read only for a record written before `cloud`/`air` existed, or by a caller
#: holding the name alone. Cloud and fog dim a lit room to dim and never
#: further -- a foggy dusk is not pitch black, and the darkness a storm brings
#: is the storm's own declaration to make.
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
    """The phase an hour of this world's day falls in, read at the
    resolution the engine prices spans to (`SPAN_RESOLUTION_SECONDS`): an
    hour within it short of where a part of the day begins has reached it."""
    return phase_at(day_fraction(
        float(hour) + SPAN_RESOLUTION_SECONDS / 3600.0, day_length))


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
    """What an outdoor room has to see by, from the sky alone.

    `sky` is the scene's whole weather record, or -- for a caller that has
    only the word -- the sky's name. WHAT DIMS A DAY IS AN AXIS (review
    2026-09-07 A88): a sky that shuts the day's own light out, or air you
    cannot see through. `DIMMING_SKIES` below is what those axes mean for the
    five names this engine used to be, and reading the name is now the
    fallback rather than the rule -- so a story under an ash-choked pall gets
    the dim its `cloud` states, where the word list gave it broad daylight.
    """
    level = SUN_LIGHT.get(str(phase or ""), "lit")
    if level == "dark":
        # THE NIGHT SKY HAS A MOON IN IT. `spatial_light.room_light` rules that
        # for an `open` room "the sky is that room's whole account" and an
        # authored `light` above it "is simply wrong -- the moonlit shore stays
        # dark at night". The rule is right; the account was short. Measured,
        # the owner's chat 151 (2026-09-20): a beach whose own weather read "a
        # clear black night sky strewn with stars, the full moon high", which
        # declared `light: "dim"`, composed `dark` in every view -- and a
        # planned police box standing on the sand was invisible to the two
        # people beside it, on a beach the story calls Moonlit.
        #
        # ONLY EVER BRIGHTER, and only to `dim`: moonlight is not daylight, so
        # no scene loses sight it had and a night never reads as a day. Cloud
        # and thick air still take it back -- a full moon behind a covered sky
        # lights nothing, which is the same axis test that dims a day one rung
        # below, asked here of the moon instead of the sun.
        from world.weather import moon_lights
        if isinstance(sky, dict) and moon_lights(sky) \
                and str(sky.get("cloud") or "") != "covered" \
                and str(sky.get("air") or "clear") == "clear":
            return "dim"
        return level
    if level != "lit":
        return level
    if isinstance(sky, dict):
        dims = (str(sky.get("cloud") or "") == "covered"
                or str(sky.get("air") or "clear") != "clear")
        if dims:
            return "dim"
        # A record predating the axes carries neither; fall through to the
        # name it does carry.
        if sky.get("cloud") or sky.get("air"):
            return level
        sky = sky.get("sky")
    if str(sky or "").strip().casefold() in DIMMING_SKIES:
        return "dim"
    return level


# ---------------------------------------------------------------------------
# Reading a label.
# ---------------------------------------------------------------------------

def clock_reading_hour(text, day_length=DAY_LENGTH_HOURS_DEFAULT):
    """The hour a clock reading inside `text` names, as a float in
    [0, `day_length`), or None when the text carries none this reader trusts.

    HOW LONG THE DAY IS HAS ONE ANSWER IN THIS ENGINE (`day_length_hours`),
    and the bound on a readable hour is that answer rather than a second
    statement of a Terran day: "27:30" is a time on a thirty-hour world and
    "25:30" is a time on none. (Review 2026-09-07 B9: this guard read
    `hour > 23` while both of its callers already carried the world's day
    length and re-checked the reading against it afterwards.)
    """
    text = str(text or "").casefold()
    length = max(1e-9, float(day_length))
    for match in CLOCK_READING.finditer(text):
        found = [g for g in match.groups() if g is not None]
        hour, minute = int(found[0]), int(found[1])
        if minute > 59:
            continue
        if hour < 12 and PM_MARKER.match(text[match.end():match.end() + 12]):
            hour += 12
        if hour >= length:
            continue
        return float(hour) + float(minute) / 60.0
    return None


def label_phase(label, day_length=DAY_LENGTH_HOURS_DEFAULT):
    """The phase a written time-of-day label names, or None.

    A clock reading is read first -- it is the more exact statement -- and
    placed on THIS world's day; a phase word is read second. On a world whose
    day is shorter than the reading (a 20-hour day, a "22:00" label) the
    reading is refused rather than wrapped by `clock_reading_hour`, because
    it cannot be a time on that clock.
    """
    text = str(label or "").casefold().strip()
    if not text:
        return None
    hour = clock_reading_hour(text, day_length)
    if hour is not None:
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
    hour = clock_reading_hour(text, day_length)
    if hour is not None:
        return hour
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
    return {"hour_of_day": display_hour(hour, length),
            "phase": phase_of_hour(hour, length),
            "day_length_hours": length}


def clock_hour(clock, style_guide=None):
    """``(hour, day_length)``: the hour of the day a stored clock record
    stands at, TO THE SECOND -- its anchor plus everything it has run, the
    arithmetic the commit's day cycle stamps the record from
    (`persist.commit_scene_state._advance_day_cycle`) -- or ``(None,
    day_length)`` when the record cannot be anchored.

    NOT THE RECORD'S `hour_of_day`. That is this reading rounded for showing
    (`display_hour`: a hundredth of an hour, 36 seconds), and a part of the
    day solved from it lands up to 18 seconds from where it was sent.
    Measured (the probe story, 2026-10-21, control chat 2 idx 8): the
    resolve's "until full dark" was solved from a stamped 13.55 against a
    clock standing at 13.5461, landed at 21:59:46, and the beat committed in
    the evening beside a stamp of 22.0 -- so the next beat's decision model,
    told the time of day from that stamp, was told it was night while the
    clock and the scene said evening. A record carrying a stamp and no anchor
    (written by hand, or before the day cycle) is read as stamped.

    ``style_guide`` None reads the day's length off the record (the commit
    stamps it there from the author's dial); a caller holding the story's
    style guide passes it, and the dial wins, as it does at the commit."""
    record = clock if isinstance(clock, dict) else {}
    if style_guide is None:
        style_guide = {"day_length_hours": record.get("day_length_hours")}
    anchor, length = clock_anchor(record, style_guide)
    if anchor is None:
        stamped = record.get("hour_of_day")
        if stamped is None or isinstance(stamped, bool):
            return None, length
        try:
            return float(stamped) % length, length
        except (TypeError, ValueError):
            return None, length
    try:
        elapsed = float(record.get("elapsed_seconds") or 0.0)
    except (TypeError, ValueError):
        elapsed = 0.0
    return hour_of_day(elapsed, anchor, length), length


def display_hour(hour, day_length=DAY_LENGTH_HOURS_DEFAULT):
    """An hour rounded for showing -- to a hundredth -- that still reads the
    part of the day the hour itself is in.

    THE STAMP AND THE PHASE BESIDE IT ARE ONE ANSWER. The nearest hundredth
    moves a reading up to 18 seconds, which carries it across a boundary:
    21.9961 is evening and rounds to 22.0, which reads night -- the clock
    record the probe story's beat left (2026-10-21, control chat 2 idx 8:
    `hour_of_day` 22.0 beside `phase` "evening"), and every reader that took
    a part of the day from the number disagreed with every reader that took
    the word. Where the nearest hundredth crosses, the hundredth on the
    hour's own side is shown."""
    length = max(1e-9, float(day_length))
    value = float(hour) % length
    phase = phase_of_hour(value, length)
    shown = round(value, 2)
    if phase_of_hour(shown, length) == phase:
        return shown
    for candidate in (math.floor(value * 100.0) / 100.0,
                      math.ceil(value * 100.0) / 100.0):
        if phase_of_hour(candidate, length) == phase:
            return round(candidate, 2)
    return round(value, 4)


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


#: The light a span may run until: the values of `SUN_LIGHT`, the ladder
#: the outdoor light already reads.
UNTIL_LIGHTS = ("dark", "dim", "lit")


def seconds_until(hour_now, *, light=None, hour=None, phase=None, days=0,
                  day_length=DAY_LENGTH_HOURS_DEFAULT):
    """How many story seconds until the sky's light next becomes `light`
    (one of `UNTIL_LIGHTS`), the clock next reads `hour`, or the day next
    reaches the part of it `phase` names, from `hour_now` -- or None when
    none of them names something this reader knows.

    A SPAN NAMED BY ITS END IS ARITHMETIC THE ENGINE OWNS. "We stay up
    talking until it is fully dark" names where the day gets to, not how
    long that takes, and only the clock and this module's own table know
    the answer: live, Larch Hill (2026-10-04), the encoder priced that wait
    at an hour, the clock stood at 16:48 in the afternoon, and the page
    said full dark. A light already reached is reached now (0); an hour is
    the next time the clock reads it, so `hour` equal to now is a full day
    away only when the caller says it is not now -- here, 0.

    A PART OF THE DAY IS READ THE SAME WAY, and by the one reader of
    written labels this module has (`clock_reading_hour`, `label_phase`),
    so a skip lands exactly where `_advance_day_cycle`'s landing rule would
    put it: on the reading a label carries, else at the START of the phase
    it names -- never a midpoint nobody stated, on `time_diff_duration`'s
    doctrine that under-ageing is recoverable and over-ageing is not. A part
    of the day the clock already stands in is reached now (0): "that
    evening" said in the evening passes nothing. Measured (the probe story,
    2026-10-20, chat 1 turn 5): "That evening ..." against a clock at 15:50
    moved it 44 seconds, and the keeper lit the lamp in the afternoon.

    A COUNT OF DAYS LANDS ON A PART OF THE DAY. `days` (a whole number, with
    `phase`) puts that part of the day that many of the story's days on: the
    day the clock stands in is day 0, each day turns where its night ends
    (`DAY_TURNS_AT`), and the span runs to where the part `phase` names
    begins -- or the reading it carries -- on the day counted. "Two days
    later ... all morning" said in the afternoon is the morning of the
    second day on: not the afternoon two days on, which a length of two
    days lands on, and not the morning of the third, which two whole days
    and then the next morning would be. Measured (the probe story,
    2026-10-21, control chat 2 idx 8): the part could say the two days or
    the morning, never both, and a beat set in the morning landed in the
    afternoon. With no count a part of the day is the next to begin, as
    above -- "the next morning" said in the evening -- and a count that is
    not a whole number of days is nothing this reader can solve (None)."""
    length = max(1e-9, float(day_length))
    now = float(hour_now) % length
    if hour is not None and not isinstance(hour, bool):
        try:
            target = float(hour) % length
        except (TypeError, ValueError):
            target = None
        if target is not None:
            return round(((target - now) % length) * 3600.0, 1)
    if str(phase or "").strip():
        if isinstance(days, bool) or not isinstance(days, int) or days < 0:
            return None
        reading = clock_reading_hour(phase, length)
        named = None if reading is not None else label_phase(phase, length)
        if reading is None and named is None:
            return None
        target = reading if reading is not None \
            else phase_bounds_hours(named, length)[0] % length
        if days:
            # Hours since the day the clock stands in turned, read at the
            # resolution `phase_of_hour` reads the part of the day at, so the
            # day counted from and the part of the day the clock reads agree
            # within that tenth of a second too.
            turn = DAY_TURNS_AT * length
            margin = SPAN_RESOLUTION_SECONDS / 3600.0
            since_turn = (now + margin - turn) % length - margin
            span = days * length + (target - turn) % length - since_turn
            return round(span * 3600.0, 1)
        if reading is not None:
            return round(((reading - now) % length) * 3600.0, 1)
        if phase_of_hour(now, length) == named:
            return 0.0
        return round(((target - now) % length) * 3600.0, 1)
    word = str(light or "").strip().casefold()
    if word not in UNTIL_LIGHTS:
        return None
    if SUN_LIGHT.get(phase_of_hour(now, length)) == word:
        return 0.0
    starts = sorted((start % 1.0) * length for _name, start, _end in PHASES)
    best = None
    for day in (0, 1, 2):
        for start in starts:
            at = start + day * length
            if at <= now:
                continue
            if SUN_LIGHT.get(phase_of_hour(at % length, length)) == word:
                best = at if best is None else min(best, at)
        if best is not None:
            break
    return None if best is None else round((best - now) * 3600.0, 1)
