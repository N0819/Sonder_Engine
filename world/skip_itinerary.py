"""A mind's own account of a skipped stretch, laid on the clock and lived.

`docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md` § 4.4: when the writer passes
over time, each cast member is asked what they do for the duration
(`agents/skip_stage.py`), and their answer is run here, in pure code -- the
ruling of 2026-09-14, "pure code off screen, an LLM on screen": the question
is the mind declaring, and this module is what the world lets it do.

THREE PARTS, each a pure function of its inputs:

  * **The itinerary** (`expand_itinerary`, `default_day`): the answer's
    `routine` repeated for every day of the span, its `plan` laid over it in
    order, `at_the_end` over the last moments, every gap filled by the default
    day, and the whole clipped to the span. A plan that runs past its span --
    asked "until morning", the probe's farm daughter planned the whole of the
    next day -- ends where the span does.
  * **The places** (`resolve_exact`, `place_questions`, `read_place_answers`):
    each `where` the mind wrote, exactly against the places it knows, then
    through ONE decision-model request per mind over those same places plus
    "none of these", and failing both as an OFF-MAP LABEL -- a place the world
    does not hold, which invents no room.
  * **The executor** (`live_through`, `share_company`): the stretches run in
    time order. A walk between rooms takes its route's edge seconds out of the
    start of the stretch it walks to (`charter_move.edge_seconds`, the walk
    every charter body takes), over the ways a body WALKS (`Ways`: never a
    frontier stub's join, never across water or the space a vessel moves
    through); a body off the map comes back by where it left it; a body
    under way with a vessel goes where the vessel goes (`journey_under_way`),
    and a stretch spent on that way is the ride itself (`rides`);
    what a stretch uses is met by what the mind carries, what is within its
    reach where the stretch finds it, and what it can walk to and back for
    inside the stretch (`Reach`) -- only a thing a body can carry is ever
    missing (`Reach.can_carry`): a fixture, a store, a vessel is used where it
    stands -- and what is not fails it only where the decision model says it
    cannot be done without (`judge_without`; no answer never fails it); a
    stretch the
    world cannot carry out fails with a typed reason, and its row says what
    failed (`missing`, `meant`); two minds in the same room, or at the same off-map
    label, over overlapping time each receive the other's `doing` -- never
    the other's `why`, and named only as the observer knows them; each
    stretch carries the sky where the mind stood, the weather walked once per
    drift window (`weather.weather_course`).

Nothing here reads or writes the database: the stage hands in the scene, the
mind's known places, what it holds, the decision model's answers, the
frontier joins the plan holds open and the labels each observer may use, and
takes back the log and the far end. The shapes are fixed by the build spec
(`STRETCH`, `LOG`, the far end), with `missing` and `meant` on every LOG row
-- `missing` kept on a row told as far as it went without them, too.
"""

from __future__ import annotations

import re

# WHAT ONLY A VESSEL CROSSES HAS ONE READING, the spatial layer's
# (`spatial_transit.MEDIUM_FLOORS`, `medium_rooms`): a frontier stub's join is
# read by it too (`spatial_barriers.frontier_joins`), and two copies of one
# guard on the floor word could drift apart with nothing reporting it.
from world.spatial import MEDIUM_FLOORS, medium_rooms

#: THE TRIGGER (owner's question 1 of the design note's § 6): the input's
#: kept skip must pass at least this many story seconds before the cast are
#: asked to live through it. Below it the ordinary beat covers the stretch.
SKIP_LIVED_SECONDS = 3600.0

#: How sure the decision model must be that a written place IS one of the
#: places offered before the mind is put there. Below it the place stays the
#: mind's own words, an off-map label: a wrong room is a body put somewhere it
#: did not mean to go, and an off-map label is a body the world has not built
#: a place for yet. Named per the owner's rule on thresholds.
SKIP_PLACE_MIN_PROBABILITY = 0.5

#: How sure the decision model must be that a thing the mind means to use IS
#: one of the things offered before the words are read as that thing. Below
#: it the words name no thing the world holds, and are never missing
#: (`Reach.missing`): the world does not hand a body a thing, and it never
#: denies one on a guess either.
SKIP_THING_MIN_PROBABILITY = 0.5

#: How sure the decision model must be that a stretch CAN be done without the
#: things that were not to hand before it is told as far as it went
#: (`judge_without`) rather than failed. Below it the stretch fails
#: `not_held`: the decision model said no. A question it did not answer
#: leaves the row told as far as it went (`answered`): no answer never
#: invents a failure (the owner's ruling, 2026-10-22). Named per the owner's
#: rule on thresholds.
SKIP_WITHOUT_MIN_PROBABILITY = 0.5

#: `at_the_end` is where the stretch leaves the mind, and it is laid over the
#: last this-many story seconds of the span: the mind's own word for where it
#: ends wins over a routine repeated past what it thought through. Half an
#: hour; named per the owner's rule on caps.
AT_THE_END_SECONDS = 1800.0

#: How many rooms one off-screen walk may cross before it is no route at all.
#: The charter's own reach is eight (`charter_space.REACH_LIMIT`), sized for a
#: four-hour window; a skip's walk is a single leg of a day and may cross a
#: settlement. Named per the owner's rule on caps.
SKIP_ROUTE_ROOMS = 40

#: How many of the story's days are laid out day by day: the LAST this-many
#: days of a longer span. What came before them is one stretch where the
#: mind stood, nothing recorded -- "years later" is not lived hour by hour,
#: and laying a decade of routine out would build tens of thousands of
#: stretches no reader could use. A month; named per the owner's rule on
#: caps.
SKIP_DAYS_LAID = 31

#: How many entries of each part of an answer (`routine`, `plan`) are read:
#: an answer is one day and its exceptions, and a list longer than this is
#: not one. Named per the owner's rule on caps.
SKIP_ENTRIES_READ = 48

#: How many changes of sky one stretch's weather line names before it stops:
#: a long sleep under a turning sky reads "clear, then rain, then storm", and
#: a whole day of hourly drift would read as a list. Named per the owner's
#: rule on caps.
SKIP_WEATHER_CHANGES = 4

#: The outcomes a LOG row carries, protocol tokens (build spec), by ONE rule
#: for both executors -- this one and the town charter's
#: (`world/charter_skip`): `failed`, with a typed reason; else `not_known`
#: for a stretch that partly failed (a thing not to hand it could be done
#: without, or that no answer judged, `judge_without`; a place no answer
#: placed that the body could not follow); else `done` for a sleep; else
#: `not_known` for a stretch whose success is the world's to judge --
#: another's response (`with`) or a world off the map nobody simulates
#: (`away`); else `done` (`stretch_outcome`). What a stretch USES never makes
#: it unknown.
OUTCOME_DONE = "done"
OUTCOME_FAILED = "failed"
OUTCOME_NOT_KNOWN = "not_known"

#: Why a stretch failed, protocol tokens. The first three are the town
#: charter's too (`charter_skip.FAILURE_REASONS`): no way through the world
#: from where the mind stood to where it meant to be; a way that exists only
#: past a fastened door (`spatial.barrier_fastening`); a way so long the
#: stretch was spent walking it. The last two are this stage's alone: a way
#: there only across what a vessel crosses -- water, or the space a vessel
#: moves through -- and no crossing was made (`Ways`; a crossing of the
#: mind's own inside a skip is not built, so every such stretch fails so,
#: while the ride a journey already under way makes is no crossing of its
#: own, `rides`); and, laid over either executor's rows, a thing a body can
#: carry that the stretch uses and the world holds neither on the mind nor
#: within its reach (`Reach`: a fixture, a store too big to carry and a
#: vessel never fail it) and that the decision model says the stretch cannot
#: be done without (`judge_without`).
REASON_NO_ROUTE = "no_route"
REASON_SHUT_WAY = "shut_way"
REASON_TOO_FAR = "too_far"
REASON_NO_CROSSING = "no_crossing"
REASON_NOT_HELD = "not_held"
FAILURE_REASONS = (REASON_NO_ROUTE, REASON_SHUT_WAY, REASON_TOO_FAR,
                   REASON_NO_CROSSING, REASON_NOT_HELD)

#: The reasons that say the body never got where it meant to be. A row
#: failed for one of them says where the body WAS in `where_text` (filled in
#: words by `place_words`) and where it meant to be in `meant`, the mind's
#: own words; a row failed `not_held` got there, and says what was not to
#: hand in `missing` -- as does a row told as far as it went without them
#: (`judge_without`). Every row carries both fields, empty where they say
#: nothing, so a reader never mistakes the place it meant for the place it
#: stood (the memory writer reads `where_text` as where the stretch was).
ROUTE_REASONS = (REASON_NO_ROUTE, REASON_SHUT_WAY, REASON_TOO_FAR,
                 REASON_NO_CROSSING)

#: How many things one decision-model question about a thing offers: what
#: the mind has on it first, then the things and fixtures of the place it
#: stands in and the places its words name exactly, then of the rest of the
#: places it knows, then the world's other things. A choice over a whole
#: town's furniture is not a question. Named per the owner's rule on caps.
SKIP_THING_OPTIONS = 64

#: How much of a thing's or a fixture's own description rides beside its
#: name when the decision model is asked which thing a mind's words mean:
#: "the old lamp mechanism" meets a pedestal only through what the pedestal
#: carries, and "her sealed letter" a letter only through whose hand
#: addressed it. Named per the owner's rule on caps.
SKIP_THING_DESC_CHARS = 120

#: Which part of an answer a stretch came from. Internal: the build spec's
#: STRETCH has no field for it (`as_stretch` drops it); it says only how the
#: timeline was laid.
KIND_ROUTINE = "routine"
KIND_PLAN = "plan"
KIND_END = "end"
KIND_DEFAULT = "default"

#: How near the span's opening a sleep's start may stand and still be the
#: span's first moment: a span's ends are sums of floats.
SPAN_TOLERANCE_SECONDS = 1.0

#: The decision model's option for "none of the places offered".
NONE_OPTION = "none"


# --------------------------------------------------------------------------
# The span, in the story's own day
# --------------------------------------------------------------------------

class Span:
    """The stretch the cast live through: story seconds `from_s` to `until_s`,
    and where the story's day stands at `from_s` (`hour0`, None when the day
    has no anchor and no part of the day can be placed)."""

    def __init__(self, from_s, until_s, hour0=None, day_length=24.0):
        self.from_s = float(from_s)
        self.until_s = max(float(from_s), float(until_s))
        self.day_length = max(1e-9, float(day_length or 24.0))
        self.hour0 = None if hour0 is None else float(hour0) % self.day_length

    @property
    def anchored(self):
        return self.hour0 is not None

    def as_dict(self):
        return {"from_s": self.from_s, "until_s": self.until_s}

    def hour_at(self, t):
        """The hour of the story's day at story second `t`, or None."""
        if self.hour0 is None:
            return None
        return (self.hour0 + (float(t) - self.from_s) / 3600.0) % self.day_length

    def _turn_hour(self):
        from world.day_cycle import DAY_TURNS_AT
        return DAY_TURNS_AT * self.day_length

    def day0_start(self):
        """Story seconds at which day 0 -- the story's day `from_s` falls in
        -- began. A day turns where its night ends (`day_cycle.DAY_TURNS_AT`),
        so the night belongs to the day before it, as `seconds_until` counts
        days; read at the resolution `phase_of_hour` reads the day at."""
        from world.day_cycle import SPAN_RESOLUTION_SECONDS
        margin = SPAN_RESOLUTION_SECONDS / 3600.0
        since = (self.hour0 + margin - self._turn_hour()) % self.day_length - margin
        return self.from_s - since * 3600.0

    def day_start(self, day):
        return self.day0_start() + int(day) * self.day_length * 3600.0

    def day_of(self, t):
        """Which of the story's days (0 = the day the span begins in) story
        second `t` falls in."""
        if self.hour0 is None:
            return 0
        from world.day_cycle import SPAN_RESOLUTION_SECONDS
        offset = float(t) - self.day0_start() + SPAN_RESOLUTION_SECONDS
        return int(offset // (self.day_length * 3600.0))

    def phase_at(self, t):
        """The part of the day at story second `t`, or None."""
        from world.day_cycle import phase_of_hour
        hour = self.hour_at(t)
        return None if hour is None else phase_of_hour(hour, self.day_length)

    def offset_hours(self, token):
        """Hours after a day turns at which the part of the day `token`
        names begins -- a phase name, a clock reading, or a label the day
        cycle can read (`day_cycle.label_phase`) -- or None."""
        from world.day_cycle import (PHASE_NAMES, clock_reading_hour,
                                     label_phase, phase_bounds_hours)
        text = " ".join(str(token or "").split()).strip().casefold()
        if not text:
            return None
        hour = None
        if text in PHASE_NAMES:
            hour = phase_bounds_hours(text, self.day_length)[0]
        else:
            hour = clock_reading_hour(text, self.day_length)
            if hour is None:
                named = label_phase(text, self.day_length)
                if named:
                    hour = phase_bounds_hours(named, self.day_length)[0]
        if hour is None:
            return None
        return (float(hour) - self._turn_hour()) % self.day_length

    def phase_length_hours(self, token):
        """How long the part of the day `token` names lasts, in hours, or
        None when it names none."""
        from world.day_cycle import (PHASE_NAMES, label_phase,
                                     phase_bounds_hours)
        text = " ".join(str(token or "").split()).strip().casefold()
        name = text if text in PHASE_NAMES else label_phase(text, self.day_length)
        if not name:
            return None
        start, end = phase_bounds_hours(name, self.day_length)
        return float(end) - float(start)

    def window(self, day, start_token, end_token):
        """`(start_s, end_s)` for "from `start_token` until `end_token`" on
        story day `day`, or None when either end names no part of the day.
        An end at or before its start is on the next day ("night until
        pre-dawn"); an end naming the start's own part of the day is that
        part, whole ("night until night")."""
        if self.hour0 is None:
            return None
        begin = self.offset_hours(start_token)
        if begin is None:
            return None
        same = " ".join(str(end_token or "").split()).casefold() == \
            " ".join(str(start_token or "").split()).casefold()
        end = None if (same or not str(end_token or "").strip()) \
            else self.offset_hours(end_token)
        if end is None:
            length = self.phase_length_hours(start_token)
            if length is None:
                length = 1.0
            end = begin + length
        elif end <= begin:
            end += self.day_length
        base = self.day_start(day)
        return base + begin * 3600.0, base + end * 3600.0

    def until_words(self):
        """`{"day", "part_of_day"}` -- the span's end in the mind's own terms
        (the engine's `{days, until_phase}` vocabulary), or None unanchored."""
        if self.hour0 is None:
            return None
        return {"day": self.day_of(self.until_s),
                "part_of_day": self.phase_at(self.until_s)}

    def length_words(self):
        """`{"days", "hours"}` -- how long the span lasts, in whole days and
        the whole hours left over."""
        seconds = max(0.0, self.until_s - self.from_s)
        day = self.day_length * 3600.0
        days = int(seconds // day)
        hours = int(round((seconds - days * day) / 3600.0))
        if hours >= int(round(self.day_length)):
            days, hours = days + 1, 0
        return {"days": days, "hours": hours}


# --------------------------------------------------------------------------
# The itinerary
# --------------------------------------------------------------------------

def _text(value, limit=600):
    return " ".join(str(value or "").split())[:limit]


def _names(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [_text(v, 120) for v in value if _text(v, 120)]


def _flag(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in ("true", "yes", "1")


def _day(value):
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _stretch(start, end, entry, kind):
    """One internal stretch: the build spec's STRETCH fields, plus the kind
    of answer it came from (`KIND_ROUTINE` and its siblings)."""
    entry = entry if isinstance(entry, dict) else {}
    return {"from_s": float(start), "until_s": float(end), "room": None,
            "away": None, "where_text": _text(entry.get("where"), 240),
            "doing": _text(entry.get("doing")),
            "asleep": _flag(entry.get("asleep")),
            "with": _names(entry.get("with")),
            "why": _text(entry.get("why")), "uses": _names(entry.get("uses")),
            "kind": kind}


def _lay(timeline, stretch):
    """`timeline` with `stretch` laid over it: what it covers of every
    earlier stretch is cut away, and the parts either side stay."""
    out = []
    a, b = stretch["from_s"], stretch["until_s"]
    for item in timeline:
        if item["until_s"] <= a or item["from_s"] >= b:
            out.append(item)
            continue
        if item["from_s"] < a:
            out.append(dict(item, until_s=a))
        if item["until_s"] > b:
            out.append(dict(item, from_s=b))
    out.append(stretch)
    out.sort(key=lambda s: (s["from_s"], s["until_s"]))
    return out


def _laid_from(span):
    """Story seconds from which the span is laid out day by day: its last
    `SKIP_DAYS_LAID` days, or the whole of a shorter one."""
    return max(span.from_s,
               span.until_s - SKIP_DAYS_LAID * span.day_length * 3600.0)


def _phase_starts(span, start, end):
    """Every moment a part of the day begins strictly inside (`start`,
    `end`), in order: at most one per part of the day per day of the span,
    by construction."""
    from world.day_cycle import PHASE_NAMES
    out = []
    for day in range(span.day_of(start), span.day_of(end) + 1):
        base = span.day_start(day)
        for name in PHASE_NAMES:
            begin = span.offset_hours(name)
            if begin is None:
                continue
            at = base + begin * 3600.0
            if start < at < end:
                out.append(at)
    return sorted(set(out))


def default_day(span, start=None, end=None):
    """THE DEFAULT DAY: "silence is sleep" (Writers' Room plan, Phase D).
    Asleep through the resting parts of the day (`day_cycle.RESTING_PHASES`)
    and otherwise awake, wherever the mind stands -- `where_text` empty is
    "stay where you are". BOUNDED BY CONSTRUCTION: cut only where a part of
    the day begins (`_phase_starts`), and laid day by day only over the
    span's last `SKIP_DAYS_LAID` days, before which it is one stretch where
    the mind stood. A story whose day has no anchor gets one waking stretch:
    nothing says when its night is."""
    from world.day_cycle import RESTING_PHASES
    start = span.from_s if start is None else float(start)
    end = span.until_s if end is None else float(end)
    if end <= start:
        return []
    if not span.anchored:
        return [_stretch(start, end, {}, KIND_DEFAULT)]
    out = []
    laid = max(start, _laid_from(span))
    if laid > start:
        out.append(_stretch(start, min(laid, end), {}, KIND_DEFAULT))
    if laid >= end:
        return out
    edges = [laid] + _phase_starts(span, laid, end) + [end]
    for a, b in zip(edges, edges[1:]):
        resting = span.phase_at((a + b) / 2.0) in RESTING_PHASES
        if out and out[-1]["until_s"] == a and out[-1]["asleep"] == resting \
                and out[-1]["from_s"] >= laid:
            out[-1]["until_s"] = b
        else:
            out.append(_stretch(a, b, {"asleep": resting}, KIND_DEFAULT))
    return out


def _placed_in_order(span, window, previous):
    """A plan entry's window, moved on by whole days where the answer's own
    order says it must be later. Two readings of one rule -- the stretch
    asked about lies AHEAD, and the plan is written in order:

      * a part of the day already gone by the time the stretch begins is
        its next coming: "pre-dawn" said in the small hours of day 0 is the
        pre-dawn a few hours off, not the one a day behind, since a day
        turns where its night ends (`day_cycle.DAY_TURNS_AT`);
      * an entry that begins before the entry written before it is on a
        later day: a plan that runs from tonight round to "night" again
        means the next night.

    Bounded by the span's own days. Measured on the probe's farm daughter
    (2026-10-21, asked at night "until morning"): her plan's every entry
    said day 0 and ran round to the next night, so read against the
    calendar alone her bedtime landed on the night she was asked in, laid
    over the hours she had said she would sit up by the fire."""
    a, b = window
    day = span.day_length * 3600.0
    for _ in range(span.day_of(span.until_s) + 2):
        if b <= span.from_s or (previous is not None and a < previous):
            a, b = a + day, b + day
            continue
        break
    return a, b


def answer_is_readable(answer):
    """Does the answer say anything an itinerary can be built from?"""
    if not isinstance(answer, dict):
        return False
    end = answer.get("at_the_end") if isinstance(answer.get("at_the_end"), dict) else {}
    return bool([e for e in (answer.get("routine") or []) if isinstance(e, dict)]
                or [e for e in (answer.get("plan") or []) if isinstance(e, dict)]
                or _text(end.get("where")) or _text(end.get("doing")))


def expand_itinerary(answer, span):
    """The mind's answer as absolute stretches over the span, in time order.

    The `routine` is one ordinary day, repeated for every day the span
    touches; each `plan` entry, in order, is laid over whatever it covers;
    `at_the_end` is laid over the last `AT_THE_END_SECONDS`; every gap left
    is the default day; and the whole is clipped to the span. A part of the
    day this engine cannot read places nothing, so its entry is dropped
    rather than guessed at. Returns [] for an answer that says nothing an
    itinerary can be built from -- the caller's cue for the default day."""
    if not answer_is_readable(answer):
        return []
    timeline = []
    end = answer.get("at_the_end") if isinstance(answer.get("at_the_end"), dict) else {}
    routine = [e for e in (answer.get("routine") or []) if isinstance(e, dict)]
    plan = [e for e in (answer.get("plan") or []) if isinstance(e, dict)]
    if span.anchored:
        # Day by day over the span's last `SKIP_DAYS_LAID` days at most (the
        # day before the first is laid too: its night runs into it).
        laid = _laid_from(span)
        for day in range(max(0, span.day_of(laid) - 1), span.day_of(span.until_s) + 1):
            for entry in routine[:SKIP_ENTRIES_READ]:
                window = span.window(day, entry.get("from"), entry.get("until"))
                if window and window[1] > laid:
                    timeline = _lay(timeline, _stretch(*window, entry, KIND_ROUTINE))
        previous = None
        for entry in plan[:SKIP_ENTRIES_READ]:
            window = span.window(_day(entry.get("day")), entry.get("from"),
                                 entry.get("until"))
            if not window:
                continue
            window = _placed_in_order(span, window, previous)
            previous = window[0]
            if window[1] > laid and window[0] < span.until_s:
                timeline = _lay(timeline, _stretch(*window, entry, KIND_PLAN))
    if _text(end.get("where")) or _text(end.get("doing")):
        tail = max(span.from_s, span.until_s - AT_THE_END_SECONDS)
        timeline = _lay(timeline, _stretch(tail, span.until_s, end, KIND_END))
    return clip(_filled(timeline, span), span)


def _filled(timeline, span):
    """Every gap the answer left, filled by the default day."""
    out = []
    t = span.from_s
    for item in sorted(timeline, key=lambda s: (s["from_s"], s["until_s"])):
        if item["until_s"] <= span.from_s or item["from_s"] >= span.until_s:
            out.append(item)
            continue
        if item["from_s"] > t:
            out.extend(default_day(span, t, item["from_s"]))
        out.append(item)
        t = max(t, item["until_s"])
    if t < span.until_s:
        out.extend(default_day(span, t, span.until_s))
    return out


def clip(stretches, span):
    """Every stretch cut to the span; whatever lies wholly outside it, and
    whatever is left with no length, goes."""
    out = []
    for item in stretches:
        a = max(span.from_s, float(item["from_s"]))
        b = min(span.until_s, float(item["until_s"]))
        if b - a > 1e-6:
            out.append(dict(item, from_s=a, until_s=b))
    out.sort(key=lambda s: (s["from_s"], s["until_s"]))
    return out


def as_stretch(item):
    """An internal stretch as the build spec's STRETCH: its kind left out."""
    return {key: item.get(key) for key in (
        "from_s", "until_s", "room", "away", "where_text", "doing", "asleep",
        "with", "why", "uses")}


# --------------------------------------------------------------------------
# The places
# --------------------------------------------------------------------------

_PUNCT = re.compile(r"[\s\W_]+", re.UNICODE)


def _fold(text):
    """A place's words as code compares them: case and punctuation folded,
    an id's underscores read as the spaces they stand for."""
    return _PUNCT.sub(" ", str(text or "").casefold()).strip()


def _named_at(folded_text, folded_name):
    """Where a room's whole name stands in a text as words of its own, or
    -1: both folded (`_fold`), so the test is on word boundaries."""
    if not folded_name:
        return -1
    at = (" %s " % folded_text).rfind(" %s " % folded_name)
    return at


def rooms_named_in(texts, rooms):
    """`{room_id: name}` -- every room the world holds whose WHOLE NAME a
    mind's own words carry. A place the mind names by its name is a place it
    knows, whatever the engine's map of what it has seen says: a quay hand
    who works "Saltreach quay" knows the quay two doors from the tavern his
    story opened in.

    NOT THE INSIDE OF A THING. A room that is a thing's or a body's inside
    (`parent_entity`) carries the thing's name, and naming the thing is not
    being in it: measured on the probe's boatman (2026-10-21), "The quay,
    harbour town -- the Mary Ann loaded and made fast" put him inside his
    boat, out in the channel where the boat was last placed."""
    folded = [_fold(t) for t in texts if _fold(t)]
    out = {}
    for rid in sorted(rooms or {}):
        room = rooms[rid] if isinstance(rooms[rid], dict) else {}
        if str(room.get("parent_entity") or "").strip():
            continue
        name = str(room.get("name") or "")
        key = _fold(name)
        if key and any(_named_at(text, key) >= 0 for text in folded):
            out[str(rid)] = name
    return out


def resolve_exact(where_text, known):
    """The room id `where_text` names, among `known` (`{room_id: name}`),
    by IDENTIFIER RECOGNITION over a closed set, never prose reading: the
    whole text is a room's name or id, case and punctuation folded. None
    otherwise.

    WORDS THAT CARRY A NAME AND MORE ARE READ, NEVER MATCHED. They may put
    the body in that room ("Saltreach quay, among the stacked cargo"), in
    one of two it names ("from the hall to the kitchen"), or somewhere in or
    beside it the world does not hold -- and only reading tells which, so
    they are the decision model's (`place_questions`), over the same known
    places. Measured offline on the tavern night (2026-10-21): matched by
    the name alone, a lodger's "Gull and Anchor, rented room upstairs" put
    him to sleep at a taproom table, in his drinking companions' view."""
    folded = _fold(where_text)
    if not folded:
        return None
    for rid in sorted(known):
        if folded in (_fold(rid), _fold(known[rid])):
            return rid
    return None


def place_questions(name, texts, known, language=None):
    """`{key: question}` -- one `choice` per written place this mind's own
    map did not answer exactly, over the places it knows plus "none of
    these". Keys are stable per text (`place:<n>`). Empty when there is
    nothing to ask, or nothing to ask it over."""
    from llm.prompts import jev_question
    if not known:
        return {}
    options = {f"p{i}": str(known[rid]) for i, rid in enumerate(sorted(known))}
    none_text = jev_question("skip_place_none", language) or "none of these"
    out = {}
    for n, text in enumerate(texts):
        instructions = jev_question("skip_place", language, name=name, where=text)
        if not instructions:
            continue
        out[f"place:{n}"] = {"type": "choice", "instructions": instructions,
                             "criteria": {**options, NONE_OPTION: none_text}}
    return out


def read_place_answers(answers, texts, known,
                       threshold=SKIP_PLACE_MIN_PROBABILITY):
    """`{text: room_id}` for every question the decision model answered with
    one of the offered places at or above `threshold`."""
    ids = {f"p{i}": rid for i, rid in enumerate(sorted(known))}
    out = {}
    for n, text in enumerate(texts):
        answer = (answers or {}).get(f"place:{n}")
        choice = _choice(answer, threshold)
        if choice and choice in ids:
            out[text] = ids[choice]
    return out


def _choice(answer, threshold):
    """The key a `choice` answer picked, when its probability reaches
    `threshold`; None for "none", an unreadable answer, or a weak pick."""
    if not isinstance(answer, dict):
        return None
    pick = str(answer.get("choice") or "")
    if not pick or pick == NONE_OPTION:
        return None
    probabilities = answer.get("probabilities")
    if isinstance(probabilities, dict) and pick in probabilities:
        try:
            if float(probabilities[pick]) < float(threshold):
                return None
        except (TypeError, ValueError):
            return None
    return pick


def answered(answer):
    """Did the decision model answer a question? A `choice` that picked an
    option -- "none of these" is an answer -- or a `noul` carrying its
    probability, however low. No entry, an error, an unreadable shape or a
    request that failed is NO ANSWER, and NO ANSWER NEVER INVENTS A FAILURE:
    a stretch fails only where the world, or the decision model's own
    answer, says it could not be done (`judge_without`, `place_stretches`).
    Measured on the lighthouse replayed a fourth time (chat 3 turn 26,
    2026-10-22): an unanswered `without` left a row failed, as a "no" did."""
    if not isinstance(answer, dict):
        return False
    if str(answer.get("choice") or "").strip():
        return True
    value = answer.get("noul")
    if value is None or isinstance(value, bool):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def unanswered_places(answers, texts, questions):
    """`{text}` -- every written place a place question WAS asked about
    (`place_questions`' `place:<n>` keys in `questions`) that the decision
    model did not answer (`answered`). "None of these" and a weak pick are
    answers: those places are off-map labels the decision model read as
    such. A place no question was asked about -- nothing to ask over -- is
    not here either."""
    out = set()
    for n, text in enumerate(texts):
        key = f"place:{n}"
        if key in (questions or {}) and not answered((answers or {}).get(key)):
            out.add(text)
    return out


def thing_questions(name, texts, held, language=None):
    """`{key: question}` -- one `choice` per thing a stretch uses that no
    thing's name answered exactly, over the things offered plus "none of
    these". `held` is `{key: label}`: what the mind has on it and the things
    of the world it may mean (`Reach.options`)."""
    from llm.prompts import jev_question
    if not held:
        return {}
    options = {f"t{i}": str(held[key]) for i, key in enumerate(sorted(held))}
    none_text = jev_question("skip_thing_none", language) or "none of these"
    out = {}
    for n, text in enumerate(texts):
        instructions = jev_question("skip_thing", language, name=name, thing=text)
        if not instructions:
            continue
        out[f"thing:{n}"] = {"type": "choice", "instructions": instructions,
                             "criteria": {**options, NONE_OPTION: none_text}}
    return out


def read_thing_answers(answers, texts, held,
                       threshold=SKIP_THING_MIN_PROBABILITY):
    """`{text}` -- the things a stretch uses that the decision model found
    among what the mind has on it."""
    keys = {f"t{i}": key for i, key in enumerate(sorted(held))}
    out = set()
    for n, text in enumerate(texts):
        choice = _choice((answers or {}).get(f"thing:{n}"), threshold)
        if choice and choice in keys:
            out.add(text)
    return out


def read_thing_picks(answers, texts, offered,
                     threshold=SKIP_THING_MIN_PROBABILITY):
    """`{text: key}` -- each thing a stretch uses that the decision model
    found among the things offered (`{key: label}`, as `thing_questions`
    numbered them), picked at or above `threshold`. A text it found no
    thing for is absent: the world holds nothing those words name."""
    keys = {f"t{i}": key for i, key in enumerate(sorted(offered))}
    out = {}
    for n, text in enumerate(texts):
        choice = _choice((answers or {}).get(f"thing:{n}"), threshold)
        if choice and choice in keys:
            out[text] = keys[choice]
    return out


def held_exactly(text, held):
    """Does `text` name one of the held things (`{key: label}`) exactly?"""
    folded = _fold(text)
    return bool(folded) and any(folded in (_fold(key), _fold(label))
                                for key, label in held.items())


def place_stretches(stretches, resolved, unplaced=()):
    """Each stretch with its place set: a room the resolution found, else
    its own words as an off-map label. An empty `where_text` is "where I
    stand" and is left for the executor, which knows where that is. A label
    whose question the decision model never answered (`unanswered_places`)
    is marked `unplaced` -- internal, never on the build spec's STRETCH
    (`as_stretch`) -- so the executor never fails a crossing on it: nothing
    showed the place lay across the water (`live_through`)."""
    out = []
    for item in stretches:
        text = item.get("where_text") or ""
        if not text:
            out.append(dict(item, room=None, away=None))
        elif text in resolved:
            out.append(dict(item, room=resolved[text], away=None))
        elif text in unplaced:
            out.append(dict(item, room=None, away=text, unplaced=True))
        else:
            out.append(dict(item, room=None, away=text))
    return out


# --------------------------------------------------------------------------
# The things within reach
# --------------------------------------------------------------------------

#: How many containers deep a thing is followed to the room or the body that
#: holds it -- a letter in a satchel in a chest. Named per the owner's rule
#: on caps.
SKIP_CONTAINED_DEPTH = 8

#: The key a room's fixture (one of its `anchors`) is offered and judged
#: under: `fixture:<room id>:<anchor id>`, so two rooms' pedestals are two.
FIXTURE_PREFIX = "fixture:"


def _humane(identifier):
    return " ".join(str(identifier or "").replace("_", " ").split())


def _cut(text, limit):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.")


class Reach:
    """What a mind can lay a hand on, where and when a stretch finds it.

    WHAT A STRETCH USES IS MET BY WHAT THE MIND CARRIES AND BY WHAT IS WITHIN
    ITS REACH in the room the stretch finds it in: the room's things (each
    thing the scene stands there, and what lies inside them), its fixtures
    (the room's `anchors`), and a vessel it stands in -- one of the vessel's
    own rooms -- or beside, in the room the vessel stands in. A vessel is
    never held: one is aboard it or at it, and a vessel under way stands
    where its journey has brought it (`journeys`). A thing on another body is
    that body's, never the room's; and off the map nothing is within reach
    that the mind does not carry, because the world holds nothing there.
    Measured on the lighthouse (chat 3 turn 25, 2026-10-21): the keeper's
    first three stretches -- at the pedestal, lighting the lamp, keeping the
    watch -- all failed `not_held` in the lamp room with the lamp standing in
    it, and every stretch of the boatman's that used his boat failed so.

    A THING IS TO HAND WHEN THE MIND CAN GET IT WITHIN THE STRETCH: on it;
    within its reach where the stretch finds it; or lying where it can walk
    to and back inside the stretch's own time (`fetch`). Only what it cannot
    get in time is missing. Measured on the lighthouse replayed a third time
    (chat 3 turn 25, 2026-10-21): the keeper's lamp work failed `not_held`
    for two nights for want of "paraffin", which lay in a crate two flights
    down his own tower; his memories said "there was none in the stores",
    and the next beat gave him the line "The paraffin's spent".

    ONLY A THING THE WORLD HOLDS, AND HOLDS ELSEWHERE, IS MISSING. Words that
    name no thing the world holds -- a prop nobody minted -- are not this
    executor's to deny: the world never said the thing was not there, so the
    stretch is not failed for it, and nothing is put in the mind's hands
    either. The same turn: "the logbook" was no thing the world held, and the
    brass shim only a sound (`sensory_events`, source "shim"), with no thing
    behind it. And a thing that IS missing fails the stretch only where the
    stretch cannot be done without it (`judge_without`).

    A STRETCH FAILS ITS HOLDING CHECK ONLY ON POSITIVE EVIDENCE, AND ONLY A
    THING A BODY CAN CARRY IS EVER MISSING (`can_carry`). A fixture, a thing
    too big to carry -- a store, a pile of cargo -- and a vessel are never
    missing, on the map or off it: the mind goes to them and uses them where
    they stand, and whether it can be there is the stretch's PLACE, which
    routing decides (`no_route`, `no_crossing`), never this check. A thing a
    body can carry is missing only where the world holds it out of the
    mind's reach for the stretch: on another body (the decision model then
    judges whether the stretch could be done without it, `judge_without`),
    or where the mind cannot walk to and back for it inside the stretch
    (`fetch`) -- anywhere the world holds it, from a place off the map. Words
    that may name both kinds are never missing: one reading of them is used
    where it stands. A FALSE FAILURE BECOMES CANON -- the log is what the
    mind remembers and what its next beat is told -- so the executor never
    fails a stretch on what it cannot show. Measured on the lighthouse
    replayed a fourth time (chat 3, turns 25 and 26, 2026-10-22), with the
    fetch above in place: the decision model read the keeper's "paraffin" as
    the pile of stores on the steps (cargo, "a sloshing drum of paraffin"),
    so his lamp work failed on five rows and his memory kept "The lamp went
    dark on my watch for want of paraffin I should have had at hand"; his
    tea in the kitchen failed for the hall's stove; and the boatman's day at
    a harbour the world does not hold failed on every stretch that named the
    Mary Ann, docked at the mainland -- his dinner among them. The third
    replay (turn 26) had already shown the off-map half: the boatman's
    "kitchen table" at home was read as the lighthouse kitchen's and counted
    missing beside the letter that truly lay on the rock.

    `carried` is `{key: label}` of what the mind has on it
    (`skip_stage.held_things`); everything else is read from the scene.
    `ways` is the ways a body walks (`Ways`), over which a thing is fetched;
    without them nothing is (`fetch`)."""

    def __init__(self, scene, name, carried=None, journeys=None, ways=None):
        from world.spatial import _interior_rooms_of, _is_body_entity
        self.scene = scene if isinstance(scene, dict) else {}
        self.name = str(name or "")
        self.journeys = dict(journeys or {})
        self.ways = ways
        rooms = self.scene.get("rooms") or {}
        entities = self.scene.get("entities") or {}
        positions = self.scene.get("positions") or {}
        contained = self.scene.get("contained") or {}
        self.carried = {str(k): str(v) for k, v in (carried or {}).items()}
        self.labels = {}         # key -> [spellings], for an exact match
        self.option = {}         # key -> the words the decision model is shown
        self.where = {}          # key -> the room it stands in
        self.outer = {}          # key -> the thing it lies inside, outermost
        self.inside = {}         # vessel key -> its own rooms
        self.fixture_room = {}   # fixture key -> its room
        self.portable = set()    # keys the record says a body can carry
        self.on_a_body = set()   # keys a body carries now, this mind's or another's
        self._trips = {}         # (here, there) -> a walk there and back, seconds
        people = {str(k) for k, e in entities.items()
                  if not isinstance(e, dict) or _is_body_entity(self.scene, k, e)}

        def body_name(ref):
            """A body's name, where a ledger keyed it by its entity id."""
            record = entities.get(ref)
            return str(record.get("name") or ref) if isinstance(record, dict) else ref

        def holder(eid):
            """`(kind, where, outer)`: where a thing is held -- `("room",
            room id)`, `("body", name)` or `(None, None)` -- followed through
            the things it lies inside, and the outermost of those things
            (itself when it lies inside nothing)."""
            seen, here = set(), str(eid)
            for _ in range(SKIP_CONTAINED_DEPTH):
                record = contained.get(here)
                into = str(record.get("in") or "").strip() \
                    if isinstance(record, dict) else ""
                if into:
                    if into in rooms:
                        return "room", into, here
                    if into in entities and into not in people and into not in seen:
                        seen.add(into)
                        here = into
                        continue
                    return "body", body_name(into), here
                held_by = str((entities.get(here) or {}).get("held_by") or "").strip() \
                    if isinstance(entities.get(here), dict) else ""
                if held_by:
                    return "body", body_name(held_by), here
                room = positions.get(here)
                return (("room", str(room), here) if room in rooms
                        else (None, None, here))
            return None, None, here

        for eid in sorted(entities):
            ent = entities[eid]
            if str(eid) in people or not isinstance(ent, dict):
                continue
            key = str(eid)
            name_ = str(ent.get("name") or key)
            self.labels[key] = [name_, key] + [str(a) for a in ent.get("aliases") or ()
                                               if str(a or "").strip()]
            described = _cut(ent.get("description"), SKIP_THING_DESC_CHARS)
            self.option[key] = "%s (%s)" % (name_, described) if described else name_
            if ent.get("portable"):
                self.portable.add(key)
            inside = [str(r) for r in _interior_rooms_of(self.scene, key)]
            if inside:
                self.inside[key] = inside
            kind, where, outer = holder(key)
            if outer != key:
                self.outer[key] = outer
            if kind == "room":
                self.where[key] = where
            elif kind == "body":
                self.on_a_body.add(key)
                if _fold(where) == _fold(self.name):
                    self.carried.setdefault(key, name_)
        for rid in sorted(rooms):
            anchors = (rooms[rid] or {}).get("anchors") if isinstance(rooms[rid], dict) else None
            for aid in sorted(anchors or {}) if isinstance(anchors, dict) else ():
                key = "%s%s:%s" % (FIXTURE_PREFIX, rid, aid)
                said = (anchors.get(aid) or {}) if isinstance(anchors.get(aid), dict) else {}
                described = _cut(said.get("desc"), SKIP_THING_DESC_CHARS)
                self.labels[key] = [_humane(aid)]
                self.option[key] = "%s (%s)" % (_humane(aid), described) \
                    if described else _humane(aid)
                self.fixture_room[key] = str(rid)

    def named(self, text):
        """`{key}` -- every thing whose own name, an alias or its key the
        words ARE, case and punctuation folded: identifier recognition, never
        prose reading (`resolve_exact`'s rule for places)."""
        folded = _fold(text)
        if not folded:
            return set()
        out = {key for key, label in self.carried.items()
               if folded in (_fold(key), _fold(label))}
        out |= {key for key, spellings in self.labels.items()
                if any(folded == _fold(s) for s in spellings)}
        return out

    def options(self, first=(), known=()):
        """`{key: words}` for the decision model, at most
        `SKIP_THING_OPTIONS`: what the mind has on it, then the things and
        fixtures of the rooms in `first` (where it stands, where its words
        put it), then of the places it `known`s, then the rest of the world's
        things -- a thing it means may be anywhere the world holds it."""
        out = {}

        def add(key, words):
            if key not in out and len(out) < SKIP_THING_OPTIONS:
                out[key] = words

        for key in sorted(self.carried):
            add(key, self.carried[key])
        for rooms in (list(first), list(known)):
            for rid in rooms:
                for key in sorted(self.where):
                    if self.where[key] == rid:
                        add(key, self.option[key])
                for key in sorted(self.inside):
                    if rid in self.inside[key]:
                        add(key, self.option[key])
                for key in sorted(self.fixture_room):
                    if self.fixture_room[key] == rid:
                        add(key, self.option[key])
        for key in sorted(self.option):
            if not key.startswith(FIXTURE_PREFIX):
                add(key, self.option[key])
        return out

    def room_at(self, key, t):
        """The room a thing stands in at story second `t`: a vessel whose
        journey has ended by then stands where it ended (None off the map)."""
        journey = self.journeys.get(key)
        if journey and t is not None and float(t) >= float(journey["until_s"]):
            return journey.get("room")
        return self.where.get(key)

    def in_reach(self, key, room, away=None, t=None):
        """Is the thing `key` names on the mind, or within its reach in
        `room` at story second `t`? A thing lying inside another is within
        reach wherever the outermost thing holding it is -- a vessel's cargo
        goes where the vessel goes."""
        if key in self.carried:
            return True
        key = self.outer.get(key, key)
        if key in self.carried:
            return True
        if away or not room:
            return False
        if key in self.fixture_room:
            return self.fixture_room[key] == room
        if room in self.inside.get(key, ()):
            return True                         # aboard it
        return self.room_at(key, t) == room     # beside it, or it lies here

    def can_carry(self, key):
        """Does the world say a body can carry this thing? POSITIVE EVIDENCE
        only: the record marks it `portable`, a body carries it now (the
        engine's own reading of a carried thing, `spatial_routing.
        _is_carried_interior`), or it lies inside a thing that is either.
        Never a fixture; never a thing whose record says nothing, or says it
        stays -- a store, a pile of cargo, a vessel."""
        if key in self.fixture_room:
            return False
        return any(k in self.portable or k in self.on_a_body
                   for k in (key, self.outer.get(key, key)))

    def held_somewhere(self, key, t=None):
        """Does the world hold the thing anywhere at story second `t`: on a
        body, in a room, or aboard a vessel under way? A thing the world
        places nowhere is not held elsewhere -- nothing shows it out of
        reach -- so it is never missing."""
        if key in self.on_a_body or key in self.fixture_room:
            return True
        outer = self.outer.get(key, key)
        return bool(self.room_at(outer, t)) or outer in self.journeys

    def missing(self, uses, named, room, away=None, t=None):
        """The words of each thing `uses` names that the world holds out of
        reach -- held somewhere (`held_somewhere`), and neither on the mind
        nor where the stretch finds it -- and that a body can carry
        (`can_carry`), every thing the words may name, as the mind wrote
        them. `named` is `{words: {key}}` from the resolution; words naming
        no thing the world holds are never missing, and neither are words
        naming a fixture, a thing too big to carry or a vessel, on the map or
        off it: the mind uses them where they stand. What the mind can fetch
        is `fetch`'s, after this."""
        out = []
        for text in uses or ():
            keys = (named or {}).get(text) or ()
            if not keys or any(self.in_reach(k, room, away, t) for k in keys):
                continue
            if not all(self.can_carry(k) and self.held_somewhere(k, t) for k in keys):
                continue
            out.append(text)
        return out

    def _lies_in(self, key, t):
        """The room a thing the mind could FETCH lies in at story second `t`,
        or None: a thing a body can carry (`can_carry`), lying in a room --
        or inside things lying there -- never on another body, never a
        fixture, and never a thing too big to carry, a vessel among them."""
        if not self.can_carry(key):
            return None
        return self.room_at(self.outer.get(key, key), t)

    def fetch(self, words, named, room, away=None, t=None, until=None):
        """`(got, seconds)`: which of `words` -- what a stretch uses that is
        not to hand where it finds the mind (`missing`) -- the mind FETCHES,
        and how long the fetching takes.

        A THING LYING WHERE THE MIND CAN WALK TO AND BACK INSIDE THE
        STRETCH'S OWN TIME IS TO HAND. The walk is over the ways a body walks
        (`Ways`: never a frontier stub's join, never across what a vessel
        crosses), each way priced at its edge seconds (`walk_seconds`, the
        walk every stretch takes), and the thing must be one a body can carry
        (`_lies_in`): a fixture is used where it stands, a thing on another
        body is that body's, and a vessel is boarded, never fetched. Each room
        holding a thing it needs is walked to and back once, nearest first,
        for as long as what the round trips add up to leaves the mind back
        before the stretch ends (`until`); what lies further stays missing.
        Off the map nothing is fetched: the world holds no way from a place
        it does not hold. Nothing is moved -- the skip writes where minds
        end, never where things lie -- so a thing fetched by one stretch is
        fetched again by the next that needs it."""
        if self.ways is None or away or not room or t is None or until is None:
            return [], 0.0
        room = str(room)
        best = {}                   # words -> (round trip seconds, room to fetch from)
        for text in words or ():
            for key in sorted((named or {}).get(text) or ()):
                there = self._lies_in(key, t)
                trip = self._round_trip(room, there) if there and there != room else None
                if trip is not None and (text not in best or (trip, there) < best[text]):
                    best[text] = (trip, there)
        spent, got = 0.0, []
        budget = float(until) - float(t)
        for trip, there in sorted(set(best.values())):
            if spent + trip >= budget:
                break
            spent += trip
            got += [text for text in words if text in best and best[text][1] == there]
        return got, spent

    def _round_trip(self, here, there):
        """Seconds to walk from `here` to `there` and back over the ways a body
        walks, or None where either way is none. Kept per pair: the ways do not
        change while one stage runs."""
        if (here, there) not in self._trips:
            go, _why = self.ways.route(here, there)
            back, _why = self.ways.route(there, here) if go else (None, None)
            self._trips[(here, there)] = (walk_seconds(self.scene, go)
                                          + walk_seconds(self.scene, back)) if back else None
        return self._trips[(here, there)]


class Holding:
    """One mind's holding check, as both executors read it: called as
    `missing_from(uses, room, away, t)`, what a stretch uses that is not to
    hand where the stretch finds the mind (`Reach.missing`); and `fetch(words,
    room, away, t, until)`, which of those it fetches inside the stretch and
    in how many seconds (`Reach.fetch`). `named` is `{words: {key}}`, the
    resolution's (`skip_stage.resolve_mind`)."""

    def __init__(self, reach, named):
        self.reach = reach
        self.named = dict(named or {})

    def __call__(self, uses, room, away=None, t=None):
        return self.reach.missing(uses, self.named, room, away, t)

    def fetch(self, words, room, away=None, t=None, until=None):
        return self.reach.fetch(words, self.named, room, away, t, until)


# --------------------------------------------------------------------------
# The executor
# --------------------------------------------------------------------------

def _transit_of(entity):
    state = entity.get("state") if isinstance(entity, dict) else None
    transit = state.get("transit") if isinstance(state, dict) else None
    return transit if isinstance(transit, dict) else None


#: `{room id}` -- the rooms a body does not walk into, across or out of: the
#: space a vessel under way moves through (its transit's `route_room`, the
#: medium the engine names it -- the water, the sky, the shaft; see
#: `planning_needs`' `transit_route_unplanned`), and a room whose own floor is
#: water (`MEDIUM_FLOORS`). A way across either is a vessel's. The spatial
#: layer's reading itself (`spatial.medium_rooms`), under the name the skip's
#: executor has always called it by.
media = medium_rooms


def frontier_joins(stubs):
    """`{frozenset((stub, holder))}` -- the joins the plan's frontier drew
    between a room and the space it holds open beside it. `stubs` is
    `{stub room id: holder room id}`: every live planned room the registry
    marks `provisional`, by its `frontier_of.room` (`structure.mint_frontier`;
    the stage reads the registry, `skip_stage.frontier_stubs`)."""
    return {frozenset((str(stub), str(holder)))
            for stub, holder in (stubs or {}).items() if stub and holder}


class Ways:
    """The ways a body walks over a skip's hours, and why there is none.

    A BODY WALKS ONLY A WALKABLE WAY. The graph a person walks over hours --
    open ways and the doors a hand opens (`charter_space.people_neighbors`)
    -- less two kinds of join that are no walk:

      * A FRONTIER STUB'S JOIN IS NOT A WAY. Where the plan holds a space open
        (`provisional`, minted from an axis by `structure.mint_frontier`), the
        join it drew says what lies that way and never what stands between
        -- the mint's own words: "an opening, not a door". Measured on the
        lighthouse (chat 3 turn 25): the mainland's stub hangs an open door
        with no distance off the rock's landing, the channel's own ways to
        either shore are measured at 13 and 1.5 km, and the boatman's day
        walked him between the two shores in ten minutes a leg.
      * A WAY ACROSS WATER IS A VESSEL'S. Into, across or out of the space a
        vessel moves through, or a room whose floor is water (`media`), a body
        goes only by vessel; and a crossing of the mind's own inside a skip
        is not built, so the stretch fails `no_crossing` and the body stays
        where its last stretch that could happen left it. A body already
        under way with a vessel goes where the vessel goes
        (`journey_under_way`), and a stretch spent on that way is the ride
        the journey makes, never a crossing of its own (`rides`).

    A way only past a fastened door is `shut_way`, as it was; no way at all
    is `no_route`. A `remote` way over ground is walked: the tavern story's
    quay is a `remote` way from its market (2026-10-21), and the owner's two
    `remote` edges are a village lane's.

    A CROSSING PLUGS IN HERE: where `route` finds the way only through a
    medium, a crossing the mind's own vessel can make -- a vessel within its
    reach (`Reach`), a way priced at the vessel's own pace
    (`spatial.journey_seconds`'s terms) -- is the walk's place in
    `live_through`, and the vessel's own move goes to the far end beside the
    mind's."""

    def __init__(self, scene, *, joins=()):
        from world.charter_space import people_neighbors
        from world.spatial import _ROUTE_MEMORY_BARRIERS, neighbor_map
        self.scene = scene if isinstance(scene, dict) else {}
        self.media = media(self.scene)
        self.frontier = {frozenset(str(r) for r in join) for join in joins or ()}
        people = people_neighbors(self.scene)
        fastened = neighbor_map(self.scene, _ROUTE_MEMORY_BARRIERS, directional=True)
        self.walk = self._less(people, through_media=False)
        self.fastened = self._less(fastened, through_media=False)
        self.crossing = self._less(people, through_media=True)

    def _less(self, graph, *, through_media):
        out = {}
        for here, nexts in (graph or {}).items():
            here = str(here)
            if not through_media and here in self.media:
                continue
            out[here] = {str(n) for n in nexts or ()
                         if frozenset((here, str(n))) not in self.frontier
                         and (through_media or str(n) not in self.media)}
        return out

    @staticmethod
    def _with(graph, extra):
        if not extra:
            return graph
        out = {k: set(v) for k, v in graph.items()}
        for a, b in extra:
            out.setdefault(str(a), set()).add(str(b))
            out.setdefault(str(b), set()).add(str(a))
        return out

    def route(self, here, there, extra=()):
        """`(route, reason)`: the rooms a body walks from `here` to `there`,
        inclusive, or None with why there is none. `extra` are joins standing
        for this walk alone -- a vessel's door onto the place its journey
        brought it."""
        from world.charter_space import _route_on
        if not here or not there:
            return None, REASON_NO_ROUTE
        here, there = str(here), str(there)
        if here == there:
            return [here], None
        route = _route_on(self._with(self.walk, extra), here, there, SKIP_ROUTE_ROOMS)
        if route:
            return route, None
        if _route_on(self._with(self.fastened, extra), here, there, SKIP_ROUTE_ROOMS):
            return None, REASON_SHUT_WAY
        if _route_on(self._with(self.crossing, extra), here, there, SKIP_ROUTE_ROOMS):
            return None, REASON_NO_CROSSING
        return None, REASON_NO_ROUTE


def journeys(scene, span_from):
    """`{vessel key: journey}` -- every vessel under way toward a place as
    the span opens: `until_s`, when its way is done (the price the mechanics
    book for what remains of it, `spatial.journey_seconds`, from the span's
    first moment); `room`, the room it docks in, or None when the world does
    not hold its end, and `away`, then, the words of that end; `inside`, its
    own rooms; `at`, the room it stands in now; `route`, the space it moves
    through on its way (its transit's `route_room`, else the room it stands
    in when that is a medium); `dock`, the room of its own a body steps out
    of."""
    from world.spatial import (_interior_entry_room, _interior_rooms_of,
                               journey_seconds, room_of_record, scene_room_id)
    scene = scene if isinstance(scene, dict) else {}
    rooms = scene.get("rooms") or {}
    mediums = media(scene)
    out = {}
    for eid, ent in sorted((scene.get("entities") or {}).items()):
        if not isinstance(ent, dict):
            continue
        try:
            seconds = journey_seconds(scene, eid, ent)
        except Exception:  # noqa: BLE001 -- an unpriceable journey carries nobody
            seconds = None
        if not seconds:
            continue
        transit = _transit_of(ent) or {}
        bound = str(transit.get("destination_room") or "").strip()
        dest = bound if bound in rooms else scene_room_id(scene, bound)
        held = dest if isinstance(rooms.get(dest), dict) else None
        at = room_of_record(scene, eid, ent)
        way = str(transit.get("route_room") or "").strip()
        way = way if way in rooms else scene_room_id(scene, way)
        if way not in rooms:
            way = at if at in mediums else None
        out[str(eid)] = {
            "until_s": float(span_from) + float(seconds), "room": held,
            "away": None if held else (bound or None),
            "inside": [str(r) for r in _interior_rooms_of(scene, eid)],
            "at": at, "route": (str(way) if way else None),
            "dock": _interior_entry_room(scene, eid, ent)}
    return out


def rides(journey, room):
    """Is a stretch placed in `room` the RIDE `journey` makes? A RIDE IS A
    CROSSING MADE: a stretch whose place is the way a journey under way takes
    the mind -- the space its vessel moves through toward its destination
    (`route`), or one of the vessel's own rooms -- is the ride itself, and the
    journey fulfils it. It is no crossing of the mind's own (`Ways`), which
    is not built: the journey is the world's, already under way, priced by
    the mechanics. Measured on the lighthouse replayed a second time (chat 3
    turn 25, 2026-10-21): the boatman began the span beside the Mary Ann in
    the channel, bound for the mainland, and his first stretch -- "Run the
    Mary Ann east ahead of the squall", in "the channel" -- failed
    `no_crossing` while the journey carried him across that very channel;
    two of his three memories said he never got through."""
    if not journey or not room:
        return False
    room = str(room)
    return room == str(journey.get("route") or "") or \
        room in [str(r) for r in journey.get("inside") or ()]


def journey_under_way(scene, here, under_way, ways=None):
    """The journey a body standing in `here` goes on as the span opens, or
    None. A BODY UNDER WAY GOES WHERE ITS VESSEL GOES: aboard a vessel under
    way -- `here` one of its rooms -- or beside it in the space it moves
    through, it goes nowhere of its own until the vessel's way is done, and
    then stands where the vessel docks: beside it, in the room the journey
    ends in (off the map, at its words, when the world does not hold it);
    aboard, still aboard, with the vessel's door now onto that room. Its own
    crossing is not built; this is the journey the world already has under
    way and the mechanics already price. Measured on the lighthouse (chat 3
    turn 25): the boatman stood in the channel beside the Mary Ann, bound for
    the mainland -- the encoder writes a passenger into the route room
    (faba15b3's note) -- and his whole day was on the far shore.

    `under_way` is `journeys(scene, ...)`."""
    if not here:
        return None
    here = str(here)
    in_medium = here in (ways.media if ways is not None else media(scene))
    for key in sorted(under_way or {}):
        journey = under_way[key]
        if here in journey["inside"]:
            return dict(journey, vessel=key, aboard=True)
        if in_medium and here == str(journey.get("at") or ""):
            return dict(journey, vessel=key, aboard=False)
    return None


def walk_seconds(scene, route):
    """How long a walk along `route` takes: each leg's edge seconds."""
    from world.charter_move import edge_seconds
    total = 0.0
    for here, there in zip(route, route[1:]):
        total += float(edge_seconds(scene, here, there))
    return total


def reached_by(scene, route, seconds):
    """The last room of `route` a walk reaches within `seconds`: where a body
    stands when the stretch it walks in runs out before the way does."""
    from world.charter_move import edge_seconds
    at, spent = route[0], 0.0
    for here, there in zip(route, route[1:]):
        spent += float(edge_seconds(scene, here, there))
        if spent > seconds:
            break
        at = there
    return at


def stretch_outcome(stretch, reason=None, away=None, partial=False):
    """A row's outcome, by the one rule both executors write
    (`charter_skip._TownRun._stretch_row` is the other): `failed` when it
    failed; else `not_known` when it PARTLY failed -- things not to hand that
    it could be done without, or that no answer judged (`partial`,
    `judge_without`), or a place no answer placed that the body could not
    follow (`_row`'s `unplaced`) -- so it is told only as far as it went;
    else `done` for a sleep; else `not_known` when its
    success is the world's to judge: another's response (`with`), or a world
    off the map nobody simulates (`away`, where the body is as it runs); else
    `done`.

    WHAT A STRETCH USES NEVER MAKES IT UNKNOWN. A mind doing its own work
    with its own things did it: the holding check has already said whether
    the things were to hand, and nothing else waits on anyone. Measured on
    the lighthouse replayed a second time (chat 3 turn 25, 2026-10-21): the
    keeper's ordinary night watches were `not_known` for naming the station
    log, and his memories of them read "did not know what came of it"."""
    if reason:
        return OUTCOME_FAILED
    if partial:
        return OUTCOME_NOT_KNOWN
    if stretch.get("asleep"):
        return OUTCOME_DONE
    if away or stretch.get("with"):
        return OUTCOME_NOT_KNOWN
    return OUTCOME_DONE


class Skies:
    """The sky through the span, one drift window at a time
    (`weather.weather_course`, which walks at most the span's last
    `DRIFT_WINDOW_LIMIT` windows), and what of it reaches where a body
    stands. A scene with no weather has none to give."""

    def __init__(self, scene, span, seed, severity=None, written_at=None):
        from world.weather import DRIFT_STEP_KEY, drift_window, weather_course
        self.scene = scene if isinstance(scene, dict) else {}
        self.steps = []          # (window, record), in window order
        self.first = None
        self._words = {}
        self._drift_window = drift_window
        weather = self.scene.get("weather")
        if not weather:
            return
        closed, now = weather_course(weather, span.until_s, seed,
                                     severity=severity, written_at=written_at)
        for record in list(closed) + [now]:
            if not isinstance(record, dict):
                continue
            if self.first is None:
                self.first = record
            step = record.get(DRIFT_STEP_KEY)
            if isinstance(step, int) and not isinstance(step, bool):
                self.steps.append((step, record))
        self.steps.sort(key=lambda item: item[0])

    def sky_at(self, t):
        """The sky standing in the drift window story second `t` falls in."""
        if self.first is None:
            return None
        import bisect
        window = self._drift_window(t) or 0
        at = bisect.bisect_right([step for step, _ in self.steps], window)
        return self.steps[at - 1][1] if at else self.first

    def words(self, t, room=None, away=None):
        """What of the sky reached a body at story second `t`: in a room,
        as that room gets it (`weather.weather_for_room` -- sight first, and
        a sky only heard through the walls as sound); at an off-map label,
        the sky as it stands over the open world, since nothing says the
        place is roofed. None when nothing reaches."""
        from world.weather import weather_for_room, weather_words
        sky = self.sky_at(t)
        if not sky or not (room or away):
            return None
        key = (id(sky), room, None if room else str(away))
        if key not in self._words:
            if room:
                scoped = weather_for_room(dict(self.scene, weather=sky), room)
            else:
                rooms = {"__away__": {"name": str(away), "exposure": "open",
                                      "adjacent": []}}
                scoped = weather_for_room({"weather": sky, "rooms": rooms}, "__away__")
            words = weather_words(scoped, "sight") or weather_words(scoped, "sound")
            self._words[key] = ", ".join(words) if words else None
        return self._words[key]

    def over(self, start, end, room=None, away=None):
        """The weather line for a stretch: the sky in each drift window it
        crosses -- at most the last `DRIFT_WINDOW_LIMIT`, before which the
        sky never moved -- each change named once, at most
        `SKIP_WEATHER_CHANGES`."""
        from world.weather import DRIFT_SECONDS, DRIFT_WINDOW_LIMIT
        start, end = float(start), float(end)
        t = max(start, end - DRIFT_WINDOW_LIMIT * float(DRIFT_SECONDS))
        seen = []
        for _ in range(DRIFT_WINDOW_LIMIT + 1):
            if t >= end and seen:
                break
            line = self.words(t, room=room, away=away)
            if line and (not seen or seen[-1] != line):
                seen.append(line)
            if len(seen) >= SKIP_WEATHER_CHANGES or t >= end:
                break
            t = (int(t // DRIFT_SECONDS) + 1) * float(DRIFT_SECONDS)
        return " → ".join(seen) if seen else None


def _row(item, arrival, end, room, away, reason, missing, skies, unplaced=False):
    """One LOG row. A row failed for a reason in `ROUTE_REASONS` never got
    where it meant to be: its `where_text` is left for `place_words` to say
    where the body WAS, and `meant` keeps the mind's own words for where it
    meant to be. A row failed `not_held` names what was not to hand in
    `missing`, as the mind wrote it. A row whose place no answer placed and
    that the body could not follow (`unplaced`) is said the same way, and
    told as far as it went (`not_known`, no reason): nothing showed it
    failed."""
    where_text = item.get("where_text") or ""
    meant = None
    if reason in ROUTE_REASONS or unplaced:
        meant, where_text = (where_text or None), ""
    return {
        "from_s": arrival, "until_s": end, "room": room, "away": away,
        "where_text": where_text, "doing": item.get("doing") or "",
        "asleep": bool(item.get("asleep")), "seen": [],
        "weather": (skies.over(arrival, end, room=room, away=away)
                    if skies is not None else None),
        "outcome": stretch_outcome(item, reason, away, partial=unplaced), "reason": reason,
        "missing": list(missing or ()), "meant": meant}


def live_through(stretches, *, scene, start_room=None, start_away=None,
                 start_exit=None, asleep_since=None, uses_held=None,
                 missing_from=None, fetch_from=None, skies=None, ways=None,
                 journey=None):
    """`(log, far_end)`: one mind's stretches run in time order.

    Each stretch moves the mind to its place over the ways a body WALKS
    (`Ways`): a room by its route, the walk taking its edge seconds out of
    the start of the stretch it walks to; an off-map label with no
    arithmetic -- the world holds no way there to price -- from anywhere but
    the space a vessel moves through, whose every way out is a crossing; and
    BACK ONTO THE MAP BY WHERE IT LEFT IT: from off the map a body walks from
    the room it left by (`start_exit` for one that began the span away), and
    only where the world knows no such room does it come back with no walk.
    Measured on the lighthouse (chat 3 turn 25): off the map on the mainland,
    the boatman's last stretches put him on the rock's landing with no way
    walked at all. An empty place is where it stands.

    A BODY UNDER WAY (`journey`, `journey_under_way`) goes where its vessel
    goes: until the journey ends it moves only within the vessel, and a
    stretch that meant anywhere else spent itself on the way (`too_far`);
    the stretch the journey ends in begins where the journey brought it.
    A stretch placed on the journey's own way is THE RIDE (`rides`), and so
    is one with no place of its own while the journey carries the body: it
    is lived from its first moment where the body rides, and where the
    journey ends inside it, the body steps off where the journey brought it
    -- a row of its own, landed, with nothing declared.

    A stretch the world cannot carry out FAILS with a typed reason and leaves
    the mind where its last stretch that could happen left it: no route, one
    only past a fastened door, one only across what a vessel crosses, or a
    way it was still on when the stretch ran out. A place the decision model
    never answered (`unplaced`, `place_stretches`) fails no crossing: from
    the water, or under way, the body stays -- rides on -- and the row is
    told as far as it went, the words kept in `meant`; nothing showed the
    place lay across the water. A thing the stretch uses
    that the world holds neither on the mind nor within its reach where the
    stretch finds it (`missing_from(uses, room, away, t) -> [words]`, as
    `Reach.missing` answers; or `uses_held(words) -> bool`, a reader of what
    it has on it alone) and that it cannot fetch inside the stretch
    (`fetch_from(words, room, away, t, until) -> (got, seconds)`, as
    `Reach.fetch` answers) fails the stretch where it got to: it went, and
    those were not to hand -- until the decision model says the stretch could
    be done without them (`judge_without`, the stage's, after this). A FETCH
    TAKES ITS TIME OUT OF THE STRETCH, as a walk does: the row begins when
    the mind is back with what it fetched. Each row says what failed
    (`_row`).

    `asleep_since` is when the mind's sleep began if it is asleep as the
    span opens, so a sleep that runs on into the span keeps its true start.

    The far end carries `left_from`: where a day that ends off the map left
    the map, as this walk knows it -- the room the body last stood in on the
    map, a journey's landing among them. AFTER A RIDE THAT IS WHERE THE
    JOURNEY BROUGHT IT, never the space the vessel moved through: the moment
    ashore has no row of its own when the stretch it lands in goes on
    elsewhere, so the log alone cannot say it. Measured on the lighthouse
    replayed a fourth time (chat 3 turn 25, 2026-10-22): the boatman rode the
    Mary Ann to the mainland and spent his day at a harbour off the map, and
    his whereabouts kept `the_channel`.
    """
    ways = ways if ways is not None else Ways(scene)
    room = str(start_room) if start_room else None
    away = None if room else (start_away or None)
    left_by = room or (str(start_exit) if start_exit else None)
    carried = dict(journey) if journey else None
    joins = []
    log = []

    def short(item, where, off, t):
        """What the stretch uses that is not to hand where it finds the body."""
        uses = item.get("uses") or ()
        if missing_from is not None:
            return list(missing_from(uses, where, off, t) or ())
        if uses_held is not None:
            return [thing for thing in uses if not uses_held(thing)]
        return []

    for item in stretches:
        start, end = float(item["from_s"]), float(item["until_s"])
        arrival = start
        reason = None
        if carried is not None and float(carried["until_s"]) > start and (
                rides(carried, item.get("room"))
                or not (item.get("room") or item.get("away"))):
            # THE RIDE: the stretch is spent where the body rides, from its
            # first moment -- one placed on the journey's way, or one with no
            # place of its own ("where I stand", which under way IS the way);
            # where the journey ends inside it, the body is put off where the
            # journey brought it.
            done_at = float(carried["until_s"])
            landing = None
            if done_at < end:
                if carried.get("aboard"):
                    if carried.get("room") and carried.get("dock"):
                        joins.append((str(carried["dock"]), str(carried["room"])))
                else:
                    landing = ((str(carried["room"]), None) if carried.get("room")
                               else (None, carried.get("away") or away))
                carried = None
            missing = short(item, room, away, start)
            reason = REASON_NOT_HELD if missing else None
            if room:
                left_by = room
            log.append(_row(item, start, done_at if landing else end, room, away,
                            reason, missing, skies))
            if landing:
                room, away = landing
                if room:
                    left_by = room
                log.append(_row(_landed(item), done_at, end, room, away, None, (), skies))
            continue
        under_way = carried is not None and float(carried["until_s"]) >= end
        if carried is not None and not under_way:
            # The journey ends inside this stretch: it begins where the
            # vessel's way brought the body.
            arrival = max(start, float(carried["until_s"]))
            if carried.get("aboard"):
                if carried.get("room") and carried.get("dock"):
                    joins.append((str(carried["dock"]), str(carried["room"])))
            elif carried.get("room"):
                room, away = str(carried["room"]), None
            else:
                room, away = None, carried.get("away") or away
            carried = None
        if room:
            left_by = room
        target_room = str(item["room"]) if item.get("room") else None
        target_away = item.get("away") or None
        if target_room and target_room != room:
            begin = room or left_by
            if begin is None:
                # Off the map, left by nowhere the world knows: there is no
                # way back to price.
                room, away = target_room, None
            else:
                route, why_not = ways.route(begin, target_room, extra=joins)
                if route is None:
                    reason = why_not
                else:
                    seconds = walk_seconds(scene, route)
                    if arrival + seconds >= end:
                        # The way outlasts the stretch: it was spent walking,
                        # and the body is as far along the way as the stretch
                        # carried it.
                        reason = REASON_TOO_FAR
                        room, away = reached_by(scene, route, end - arrival), None
                    else:
                        arrival += seconds
                        room, away = target_room, None
        stayed = False
        if target_away and not target_room:
            if under_way or (room and room in ways.media):
                if item.get("unplaced"):
                    # No answer placed it: nothing shows the way there lies
                    # across the water, so the body stays -- rides on -- and
                    # the row is told as far as it went.
                    stayed = True
                else:
                    # Out of the space a vessel moves through is a crossing.
                    reason = REASON_NO_CROSSING
            else:
                room, away = None, target_away
        if under_way and reason in ROUTE_REASONS:
            # Still on its way with the vessel when the stretch ran out.
            reason = REASON_TOO_FAR
        missing = []
        if reason is None:
            missing = short(item, room, away, arrival)
            if missing and fetch_from is not None:
                got, seconds = fetch_from(missing, room, away, arrival, end)
                if got:
                    missing = [thing for thing in missing if thing not in got]
                    arrival += float(seconds)
            if missing:
                reason = REASON_NOT_HELD
        if room:
            left_by = room
        log.append(_row(item, arrival, end, room, away, reason, missing, skies,
                        unplaced=stayed))
    far = far_end_of(log, start_room, start_away, asleep_since)
    far["left_from"] = left_by if far.get("away") and not far.get("room") else None
    return log, far


def _landed(item):
    """The stretch a ride's journey ends inside, from the moment the body is
    put off: where the journey brought it, with nothing of its own declared
    (it keeps sleeping if it slept)."""
    return {"where_text": "", "doing": "", "asleep": bool(item.get("asleep")),
            "with": [], "uses": [], "why": ""}


def left_the_map_from(log, start_room=None, start_exit=None):
    """The room a body's day last stood in on the map before the off-map run
    its log ends in -- where it left the map, and so where it comes back by
    (`live_through`'s `start_exit`, kept on its whereabouts) -- or None when
    the log does not end off the map."""
    if log:
        last = log[-1]
        if last.get("room") or not last.get("away"):
            return None
        for row in reversed(log):
            if row.get("room"):
                return str(row["room"])
    return (str(start_room) if start_room else None) or \
        (str(start_exit) if start_exit else None)


def lay_over(log, stretches, *, uses_held=None, missing_from=None, fetch_from=None,
             skies=None):
    """What only this stage knows, laid in place over a log another executor
    wrote (`world/charter_skip`, whose rows carry the town's residents and
    nothing of these): the weather where each row stood (`Skies`); the
    holding check -- a row inside a stretch that uses a thing the world holds
    neither on the mind nor within its reach, and that it cannot fetch inside
    the row, fails `not_held` and names them in `missing`, as this stage's
    own executor fails it (`missing_from(uses, room, away, t)`, or
    `uses_held(words)`; `fetch_from(words, room, away, t, until)`, whose
    seconds come out of the row's start as they do out of a stretch's); and
    what a failed row says of where it was and where it meant to be (`_row`'s
    shape: `missing` and `meant` on every row). Company with the other asked
    minds and the player is shared over every log at once afterwards
    (`share_company`), beside the residents already there: ONE log a mind,
    either way."""
    for row in log or ():
        if not isinstance(row, dict):
            continue
        if skies is not None and not row.get("weather"):
            row["weather"] = skies.over(row["from_s"], row["until_s"],
                                        room=row.get("room"), away=row.get("away"))
        row.setdefault("missing", [])
        row.setdefault("meant", None)
        if row.get("outcome") == OUTCOME_FAILED:
            if row.get("reason") in ROUTE_REASONS and not row.get("meant"):
                row["meant"] = row.get("where_text") or None
                row["where_text"] = ""
            continue
        if uses_held is None and missing_from is None:
            continue
        stretch = _stretch_under(stretches, row)
        uses = (stretch or {}).get("uses") or ()
        if not uses:
            continue
        if missing_from is not None:
            missing = list(missing_from(uses, row.get("room"), row.get("away"),
                                        row.get("from_s")) or ())
        else:
            missing = [t for t in uses if not uses_held(t)]
        if missing and fetch_from is not None:
            got, seconds = fetch_from(missing, row.get("room"), row.get("away"),
                                      row.get("from_s"), row.get("until_s"))
            if got:
                missing = [t for t in missing if t not in got]
                row["from_s"] = float(row["from_s"]) + float(seconds)
        if missing:
            row["outcome"], row["reason"] = OUTCOME_FAILED, REASON_NOT_HELD
            row["missing"] = missing
    return log


def short_of(log):
    """`[index]` -- the rows a thing not to hand failed (`not_held`, naming
    what in `missing`): the rows `judge_without` asks about."""
    return [i for i, row in enumerate(log or ())
            if isinstance(row, dict) and row.get("outcome") == OUTCOME_FAILED
            and row.get("reason") == REASON_NOT_HELD and row.get("missing")]


def listed(items, language=None):
    """Words named one after another by the pack's own list: its `join`
    (`compositor.join`, "{first} and {last}" / ", and {last}") and its
    separator (`compositor.templates.skip_record_list_separator`)."""
    from language_runtime import compositor_text, compositor_value
    items = [str(item) for item in items if str(item or "").strip()]
    if len(items) <= 1:
        return "".join(items)
    join = compositor_value("join", language)
    if len(items) == 2:
        return str(join["two"]).format(first=items[0], last=items[1])
    separator = compositor_text("skip_record_list_separator", language)
    return separator.join(items[:-1]) + str(join["many"]).format(last=items[-1])


def without_questions(name, log, language=None):
    """`{key: question}` -- ONE yes/no per row a thing not to hand failed
    (`short_of`): can {name} do what the row says without what was missing
    (`jev_questions.skip_without`)? Keys are stable per row
    (`without:<index>`). Asked in ONE request per mind (`skip_stage.
    judge_what_was_missing`), as the places and things are."""
    from llm.prompts import jev_question
    out = {}
    for i in short_of(log):
        row = log[i]
        text = jev_question("skip_without", language, name=name,
                            doing=_text(row.get("doing")),
                            missing=listed(row.get("missing") or (), language))
        if text:
            out[f"without:{i}"] = {"type": "noul", "instructions": text}
    return out


def judge_without(log, answers, threshold=SKIP_WITHOUT_MIN_PROBABILITY):
    """A THING NOT TO HAND FAILS A STRETCH ONLY WHERE THE STRETCH CANNOT BE
    DONE WITHOUT IT. Each row a thing not to hand failed (`short_of`) that
    the decision model says can be done without them (`without_questions`,
    yes at or above `threshold`) partly failed: it is told as far as it went
    -- `not_known` by the one rule (`stretch_outcome`'s `partial`), its
    reason gone, `missing` kept to say what it went without. Only a row
    answered no stays failed `not_held`: one the decision model did not
    answer (`answered` -- no entry, an unreadable one, a request that failed
    or was never made) is told as far as it went too, because NO ANSWER
    NEVER INVENTS A FAILURE. In place; returns the indices of the rows it
    changed.

    Measured on the lighthouse replayed a second time (chat 3 turn 25,
    2026-10-21): the keeper's "Log the failure -- record the broken pinion
    ... sit with the logbook" failed whole for want of "the new clockwork
    mechanism", which stood one floor up; the boatman's walk to the post
    office with a letter that lay on the rock must still fail. And a fourth
    time (chat 3, turns 25 and 26, 2026-10-22): a false failure becomes what
    the mind remembers and says, so a row stays failed only on the decision
    model's own no."""
    from llm.decisions import probability
    changed = []
    for i in short_of(log):
        answer = (answers or {}).get(f"without:{i}")
        if answered(answer) and probability(answer) < float(threshold):
            continue
        row = log[i]
        row["outcome"] = stretch_outcome(row, None, row.get("away"), partial=True)
        row["reason"] = None
        changed.append(i)
    return changed


def _stretch_under(stretches, row):
    """The stretch a row was lived under: the one its midpoint falls in."""
    try:
        mid = (float(row["from_s"]) + float(row["until_s"])) / 2.0
    except (KeyError, TypeError, ValueError):
        return None
    for stretch in stretches or ():
        if float(stretch["from_s"]) <= mid < float(stretch["until_s"]):
            return stretch
    return None


def carry_sleep(far_end, span_from, asleep_since):
    """A far end asleep since the span's first moment, from an executor that
    knows nothing of what came before the span, keeps the sleep's TRUE start
    where the mind was already asleep as the span opened (`asleep_since`), as
    `far_end_of` keeps it -- so the natural waking floor counts from the hour
    the mind went under, not the hour the skip began."""
    far_end = dict(far_end or {})
    since = far_end.get("asleep_since_s")
    if (far_end.get("asleep") and asleep_since is not None
            and isinstance(since, (int, float))
            and float(since) <= float(span_from) + SPAN_TOLERANCE_SECONDS):
        far_end["asleep_since_s"] = float(asleep_since)
    return far_end


def place_words(log, scene):
    """Every row of a log says where it was IN WORDS, in place: the mind's
    own words for the place when it gave any; else the name its own view
    gives the room it stood in (`spatial_identity.room_display_name`, never
    the id -- a handle the engine holds, not a word of the story); else its
    off-map label. A stretch with no words is spent where the mind already
    stood, so the name is one its view has given it. For the log's readers
    that hold no scene to name a room by: the memory writer reads
    `where_text` or `away` (`mind/skip_memories.record_rows`), and a stretch
    spent where the mind stood would otherwise reach it with no place."""
    from world.spatial import room_display_name
    rooms = (scene or {}).get("rooms") or {}
    for row in log or ():
        if not isinstance(row, dict) or str(row.get("where_text") or "").strip():
            continue
        if row.get("room"):
            row["where_text"] = room_display_name(rooms.get(row["room"]), row["room"])
        elif row.get("away"):
            row["where_text"] = str(row["away"])
    return log


def far_end_of(log, start_room=None, start_away=None, asleep_since=None):
    """Where the last stretch left the mind: its room or off-map label,
    whether it is asleep, and since when -- the start of the unbroken sleep
    the span ends in, which is the mind's sleep from before the span when
    that sleep runs through from its first moment."""
    if not log:
        return {"room": start_room, "away": None if start_room else start_away,
                "asleep": asleep_since is not None,
                "asleep_since_s": asleep_since}
    last = log[-1]
    since = None
    if last.get("asleep"):
        index = len(log) - 1
        while index > 0 and log[index - 1].get("asleep"):
            index -= 1
        since = float(log[index]["from_s"])
        if index == 0 and asleep_since is not None:
            since = float(asleep_since)
    return {"room": last.get("room"), "away": None if last.get("room") else last.get("away"),
            "asleep": bool(last.get("asleep")), "asleep_since_s": since}


def _place_key(row):
    if row.get("room"):
        return ("room", str(row["room"]))
    folded = _fold(row.get("away"))
    return ("away", folded) if folded else None


def share_company(logs, label_for, scrub=None):
    """Co-presence, written into each observer's own log rows: every other
    body in the same room -- or at the same off-map label -- over time that
    overlaps an observer's waking stretch reaches it as `{who, doing}`.

    PER OBSERVER, THE FIREWALL'S SHAPE. `who` is the name the OBSERVER knows
    the other by (`label_for(observer, other)`: a stranger is a label, never
    a name it has not learned); `doing` is the other's visible surface and
    never its `why`, passed through the observer's own identity floor
    (`scrub(observer, text)`). An observer asleep receives nobody. Rows are
    met only at the same place, so the work is the company actually kept."""
    by_place = {}
    for name in sorted(logs):
        for row in logs[name]:
            key = _place_key(row)
            if key is not None:
                by_place.setdefault(key, []).append((name, row))
    for observer in sorted(logs):
        for row in logs[observer]:
            key = _place_key(row)
            if row.get("asleep") or key is None:
                continue
            for other, theirs in by_place.get(key, ()):
                if other == observer:
                    continue
                overlap = (min(row["until_s"], theirs["until_s"])
                           - max(row["from_s"], theirs["from_s"]))
                if overlap <= 0:
                    continue
                doing = theirs.get("doing") or ""
                if scrub is not None:
                    doing = scrub(observer, doing)
                entry = {"who": label_for(observer, other), "doing": doing}
                if entry not in row["seen"]:
                    row["seen"].append(entry)
    return logs
