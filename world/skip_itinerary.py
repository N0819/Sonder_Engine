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
    every charter body takes); a stretch the world cannot carry out fails with
    a typed reason; two minds in the same room, or at the same off-map label,
    over overlapping time each receive the other's `doing` -- never the
    other's `why`, and named only as the observer knows them; each stretch
    carries the sky where the mind stood, the weather walked once per drift
    window (`weather.weather_course`).

Nothing here reads or writes the database: the stage hands in the scene, the
mind's known places, what it holds, the decision model's answers and the
labels each observer may use, and takes back the log and the far end. The
shapes are fixed by the build spec (`STRETCH`, `LOG`, the far end).
"""

from __future__ import annotations

import re

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
#: one of the things it has on it. Below it the stretch fails as "it was not on
#: you" -- the same side the place threshold errs to: the world does not hand
#: a body a thing it was not carrying.
SKIP_THING_MIN_PROBABILITY = 0.5

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
#: (`world/charter_skip`): `failed`, with a typed reason; else `done` for a
#: sleep; else `not_known` for a stretch whose success waits on somebody else
#: (`with`), on a thing (`uses`) or on a world off the map nobody simulates
#: (`away`); else `done` (`stretch_outcome`).
OUTCOME_DONE = "done"
OUTCOME_FAILED = "failed"
OUTCOME_NOT_KNOWN = "not_known"

#: Why a stretch failed, protocol tokens. The first three are the town
#: charter's too (`charter_skip.FAILURE_REASONS`): no way through the world
#: from where the mind stood to where it meant to be; a way that exists only
#: past a fastened door (`spatial.barrier_fastening`); a way so long the
#: stretch was spent walking it. The last is this stage's alone, laid over
#: either executor's rows: a thing the stretch uses that the mind does not
#: have on it.
REASON_NO_ROUTE = "no_route"
REASON_SHUT_WAY = "shut_way"
REASON_TOO_FAR = "too_far"
REASON_NOT_HELD = "not_held"
FAILURE_REASONS = (REASON_NO_ROUTE, REASON_SHUT_WAY, REASON_TOO_FAR,
                   REASON_NOT_HELD)

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


def thing_questions(name, texts, held, language=None):
    """`{key: question}` -- one `choice` per thing a stretch uses that no
    held thing's name answered exactly, over the things this mind has on it
    plus "none of these". `held` is `{key: label}`."""
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


def held_exactly(text, held):
    """Does `text` name one of the held things (`{key: label}`) exactly?"""
    folded = _fold(text)
    return bool(folded) and any(folded in (_fold(key), _fold(label))
                                for key, label in held.items())


def place_stretches(stretches, resolved):
    """Each stretch with its place set: a room the resolution found, else
    its own words as an off-map label. An empty `where_text` is "where I
    stand" and is left for the executor, which knows where that is."""
    out = []
    for item in stretches:
        text = item.get("where_text") or ""
        if not text:
            out.append(dict(item, room=None, away=None))
        elif text in resolved:
            out.append(dict(item, room=resolved[text], away=None))
        else:
            out.append(dict(item, room=None, away=text))
    return out


# --------------------------------------------------------------------------
# The executor
# --------------------------------------------------------------------------

def _route(scene, here, there):
    """`(route, reason)`: the rooms a person walks from `here` to `there`,
    inclusive, on the graph a person walks over hours -- open ways and the
    doors a hand opens (`charter_space.people_neighbors`) -- or None with
    why there is none: a way that exists only past a fastened door, or no
    way at all."""
    from world.charter_space import _route_on, people_neighbors
    from world.spatial import _ROUTE_MEMORY_BARRIERS, neighbor_map
    if not here or not there:
        return None, REASON_NO_ROUTE
    if str(here) == str(there):
        return [str(here)], None
    route = _route_on(people_neighbors(scene), str(here), str(there),
                      SKIP_ROUTE_ROOMS)
    if route:
        return route, None
    fastened = neighbor_map(scene, _ROUTE_MEMORY_BARRIERS, directional=True)
    if _route_on(fastened, str(here), str(there), SKIP_ROUTE_ROOMS):
        return None, REASON_SHUT_WAY
    return None, REASON_NO_ROUTE


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


def stretch_outcome(stretch, reason=None, away=None):
    """A row's outcome, by the one rule both executors write
    (`charter_skip._TownRun._stretch_row` is the other): `failed` when it
    failed; else `done` for a sleep; else `not_known` when its success waits
    on somebody else, on a thing, or on a world off the map (`away`, where
    the body is as it runs); else `done`."""
    if reason:
        return OUTCOME_FAILED
    if stretch.get("asleep"):
        return OUTCOME_DONE
    if away or stretch.get("with") or stretch.get("uses"):
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


def live_through(stretches, *, scene, start_room=None, start_away=None,
                 asleep_since=None, uses_held=None, skies=None):
    """`(log, far_end)`: one mind's stretches run in time order.

    Each stretch moves the mind to its place: a room by the route a person
    walks, the walk taking its edge seconds out of the stretch's start; an
    off-map label with no arithmetic (the world holds no way there to
    price); an empty place is where it stands. A stretch the world cannot
    carry out FAILS with a typed reason and leaves the mind where it stood:
    no route, or one only past a fastened door. A thing the stretch uses
    that the mind does not have on it (`uses_held(text) -> bool`) fails the
    stretch where it got to -- it went, and the thing was not on it.

    `asleep_since` is when the mind's sleep began if it is asleep as the
    span opens, so a sleep that runs on into the span keeps its true start.
    """
    room, away = start_room, start_away
    log = []
    for item in stretches:
        start, end = float(item["from_s"]), float(item["until_s"])
        target_room, target_away = item.get("room"), item.get("away")
        if not target_room and not target_away:
            target_room, target_away = room, away
        reason = None
        arrival = start
        if target_room and room and target_room != room:
            route, why_not = _route(scene, room, target_room)
            if route is None:
                reason = why_not
                target_room, target_away = room, None
            elif start + walk_seconds(scene, route) >= end:
                # The way outlasts the stretch: it was spent walking, and the
                # body is as far along the way as the stretch carried it.
                reason = REASON_TOO_FAR
                target_room, target_away = reached_by(scene, route, end - start), None
            else:
                arrival = start + walk_seconds(scene, route)
        room, away = (target_room, None) if target_room else (None, target_away)
        if reason is None and uses_held is not None:
            missing = [thing for thing in item.get("uses") or ()
                       if not uses_held(thing)]
            if missing:
                reason = REASON_NOT_HELD
        outcome = stretch_outcome(item, reason, away)
        log.append({
            "from_s": arrival, "until_s": end, "room": room, "away": away,
            "where_text": item.get("where_text") or "",
            "doing": item.get("doing") or "",
            "asleep": bool(item.get("asleep")), "seen": [],
            "weather": (skies.over(arrival, end, room=room, away=away)
                        if skies is not None else None),
            "outcome": outcome, "reason": reason})
    return log, far_end_of(log, start_room, start_away, asleep_since)


def lay_over(log, stretches, *, uses_held=None, skies=None):
    """What only this stage knows, laid in place over a log another executor
    wrote (`world/charter_skip`, whose rows carry the town's residents and
    nothing of these): the weather where each row stood (`Skies`), and the
    holding check -- a row inside a stretch that uses a thing the mind does
    not have on it fails `not_held`, as this stage's own executor fails it.
    Company with the other asked minds and the player is shared over every
    log at once afterwards (`share_company`), beside the residents already
    there: ONE log a mind, either way."""
    for row in log or ():
        if not isinstance(row, dict):
            continue
        if skies is not None and not row.get("weather"):
            row["weather"] = skies.over(row["from_s"], row["until_s"],
                                        room=row.get("room"), away=row.get("away"))
        if uses_held is None or row.get("outcome") == OUTCOME_FAILED:
            continue
        stretch = _stretch_under(stretches, row)
        if stretch and any(not uses_held(t) for t in stretch.get("uses") or ()):
            row["outcome"], row["reason"] = OUTCOME_FAILED, REASON_NOT_HELD
    return log


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
