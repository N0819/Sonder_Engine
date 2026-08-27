"""How long ago something happened, in the units a mind actually has.

ONE ladder, one naming rule, one seam. Every payload that tells a fictional
mind when it formed a memory comes through here.

WHY THIS MODULE EXISTS. Minds were measuring their own past in BEATS. Across
one instrumented run, 94 recalls reached characters stamped "about 2 beats
ago" over 54 character calls, and they reasoned in the unit they were given --
one selected candidate cited "the same declaration about the door lock ten
beats ago". A beat is a turn index: global play order, engine vocabulary, a
frame of the story's CONSTRUCTION. Nobody inside a fiction can feel one. They
used it because it was the only working unit on offer -- in the same runs
`simulation_clock.display` read "now" on every call of every beat while
`elapsed_seconds` moved correctly, so the one channel carrying real duration
reached nothing that stamped a memory.

THE CALCULATION IS PRECISE AND THE PRESENTATION IS COARSE, and that pairing is
what makes plain arithmetic sufficient here rather than sloppy. Human memory
does not hold an exact interval; it holds "a few minutes", "yesterday", "years
ago". So the ladder names the LARGEST unit that fits and only that unit -- no
"2 hours 13 minutes", ever. A phrase this coarse cannot be wrong in a way a
mind would notice, which is precisely why it can be trusted.

THE WHOLE RANGE IS BUILT NOW, up to years, though a played scene's clock
currently tops out around three minutes. The upper rungs light up the first
time a time skip lands, and a ladder that stops at hours is found the hard way
-- by a character who was asleep for a week being told it was 10080 minutes.

AND THE LADDER IS NOT THE WHOLE RULE. `MemoryClock` below is where a delivered
"when" is actually decided, because two questions come before the arithmetic
and either can refuse it: is this row from the deciding turn or later (never
stamped -- the firewall's turn cutoff, stated in turn indices because that is
the unit play order is kept in), and is it from THIS frame (a clock reading is
a per-frame fiction time, so subtracting one frame's reading from another's is
arithmetic across two unrelated clocks). Where either refuses, the answer is a
qualitative phrase and never a number.
"""

from core.db import active_frame_id, q, wget

#: (singular unit name, seconds in one). Ascending, and walked from the top:
#: the largest rung that fits is the only one named. A year is 365.25 days and
#: a month is a twelfth of one -- calendar-free by design, because the engine
#: has no calendar and a mind saying "about three months ago" is not consulting
#: one either.
UNIT_LADDER = (
    ("second", 1.0),
    ("minute", 60.0),
    ("hour", 3600.0),
    ("day", 86400.0),
    ("week", 604800.0),
    ("month", 2629800.0),
    ("year", 31557600.0),
)

#: Under one second of fiction time. Its own phrase rather than "about 1 second
#: ago", and not an edge case: a memory is stamped with the clock its beat
#: ENDED at, and the next beat opens the mind at exactly that reading, so
#: everything the immediately preceding beat laid down lands here by
#: construction.
JUST_NOW = "just now"

#: A row with no place in play order -- a prestory seed, an imported bank, a
#: history carried in from another story. It belongs to no beat, so there is no
#: clock reading it could ever have had. The existing phrasing, kept verbatim.
WHEN_BEFORE_RECORD = "before this story's recorded turns"

#: Everything else this refuses to number: another frame's reading, a row that
#: predates the column, a window whose memories are all archived away. It
#: claims only that the thing is not happening now, which is the most any of
#: those cases supports. NEVER a number -- a confident wrong age is worse than
#: an honest shrug, because a mind will reason from whichever it is handed.
WHEN_UNPLACEABLE = "at a time you cannot place against now"


class _UnsetFrame:
    """Sentinel for "read the ambient frame contextvar".

    Distinct from a real ``frame_id`` of None, which means the present and is a
    value a caller passes deliberately. Same shape and the same reason as
    `mind/memory_write.py`'s.
    """

    __slots__ = ()


_UNSET_FRAME = _UnsetFrame()


def _rung(seconds):
    """The largest rung that fits, as (count, unit-name). Never zero count.

    Rounding is to the nearest whole unit with a floor of 1: an interval that
    reached this function is at least a second of fiction time, and "about 0
    minutes ago" is not a thing anyone thinks.
    """
    value = float(seconds)
    name, size = UNIT_LADDER[0]
    for candidate, candidate_size in UNIT_LADDER:
        if value >= candidate_size:
            name, size = candidate, candidate_size
    count = max(1, int(round(value / size)))
    return count, name


def _plural(count, name):
    return f"{count} {name}" if count == 1 else f"{count} {name}s"


def elapsed_phrase(seconds) -> str:
    """"3 minutes" -- a bare duration on the ladder, no direction, no hedge."""
    try:
        count, name = _rung(seconds)
    except (TypeError, ValueError):
        return ""
    return _plural(count, name)


def time_ago_phrase(seconds_ago) -> str:
    """"about 3 minutes ago", or "just now" inside the first second.

    Empty for a NEGATIVE interval, and only for that: a caller asking how long
    ago something happened that has not happened yet is asking a question with
    no honest answer, and every caller here treats "" as "say nothing". Zero is
    not that case -- it is the ordinary reading for the beat just gone.
    """
    try:
        value = float(seconds_ago)
    except (TypeError, ValueError):
        return ""
    if value < 0:
        return ""
    if value < 1.0:
        return JUST_NOW
    return f"about {elapsed_phrase(value)} ago"


def time_ago_span(oldest_seconds_ago, newest_seconds_ago) -> str:
    """"between about 4 and 9 minutes ago" -- one window, both ends.

    Each end takes its own rung, so a window that opened an hour back and
    closed a minute back reads "between about 1 minute and 1 hour ago" rather
    than being flattened onto one unit where the near end rounds to zero. When
    both ends land on the same count AND the same unit the window has closed to
    a point and it collapses to the single phrase.
    """
    try:
        oldest = float(oldest_seconds_ago)
        newest = float(newest_seconds_ago)
    except (TypeError, ValueError):
        return ""
    if oldest < newest:
        oldest, newest = newest, oldest
    if newest < 0:
        return ""
    if oldest < 1.0:
        return JUST_NOW
    old_count, old_name = _rung(oldest)
    if newest < 1.0:
        # The window is still open onto the present: it began some measurable
        # while back and closed at the reading the mind is standing on.
        return f"between about {_plural(old_count, old_name)} ago and {JUST_NOW}"
    new_count, new_name = _rung(newest)
    if (old_count, old_name) == (new_count, new_name):
        return f"about {_plural(old_count, old_name)} ago"
    if old_name == new_name:
        return (f"between about {new_count} and "
                f"{_plural(old_count, old_name)} ago")
    return (f"between about {_plural(new_count, new_name)} and "
            f"{_plural(old_count, old_name)} ago")


# ---- Where the clock stands, and where it stood -----------------------------

def current_clock_reading(chat_id):
    """This frame's simulation clock, in seconds, right now.

    Frame-scoped through `wget`, like every other reader of this key, which is
    the other half of why `MemoryClock` refuses to subtract across frames: the
    reading below belongs to the frame the mind is standing in, and the row's
    belongs to the frame it was written in.

    0.0 for a story whose clock has never been set, and that is a live case
    rather than a defensive one -- an instrumented run showed a fresh story
    reaching beat 20 with `display` still reading "now". Every memory then
    subtracts to zero or below, which reads as `JUST_NOW` or refuses; neither
    invents a duration the story never had.
    """
    clock = wget(chat_id, "simulation_clock", None) or {}
    try:
        return float(clock.get("elapsed_seconds", 0.0) or 0.0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


class MemoryClock:
    """One mind's reading position: who is remembering, when, from where.

    Bound once per payload and passed down, rather than each stamping site
    re-deriving the four values. Two of them are firewall inputs
    (`current_turn_idx`, `viewer_frame_id`) and a site that forgot either would
    still produce a plausible number, which is the failure this collapses into
    one object.
    """

    __slots__ = ("chat_id", "char_id", "current_turn_idx", "now_seconds",
                 "viewer_frame_id", "deciding_turn")

    def __init__(self, chat_id, char_id, current_turn_idx, *,
                 now_seconds=None, viewer_frame_id=_UNSET_FRAME,
                 deciding_turn=True):
        self.chat_id = chat_id
        self.char_id = char_id
        self.current_turn_idx = current_turn_idx
        self.now_seconds = (current_clock_reading(chat_id)
                            if now_seconds is None else float(now_seconds))
        self.viewer_frame_id = (active_frame_id.get()
                                if viewer_frame_id is _UNSET_FRAME
                                else viewer_frame_id)
        # DEFAULT TRUE, because the dangerous case is the common one. A mind
        # deciding turn N must never be stamped with a row from turn N: that
        # row is this beat's own outcome, and putting an age on it would say
        # the mind already lives after its own decision. An out-of-band reader
        # standing AFTER a committed turn (the tension pass) sets this False --
        # it is not deciding anything, and turn N's rows are its whole subject.
        self.deciding_turn = bool(deciding_turn)

    def _is_readable_turn(self, turn_idx):
        """Play order says this row is behind the reader's position.

        In TURN INDICES on purpose. Play order is the unit the cutoff is kept
        in, and the clock does not advance inside a beat -- so the clock cannot
        answer this question at all and must not be asked to.
        """
        if turn_idx is None or self.current_turn_idx is None:
            return False
        try:
            if self.deciding_turn:
                return int(turn_idx) < int(self.current_turn_idx)
            return int(turn_idx) <= int(self.current_turn_idx)
        except (TypeError, ValueError):
            return False

    def of_memory(self, memory) -> str:
        """The "when" one delivered memory carries."""
        memory = memory if isinstance(memory, dict) else {}
        turn_idx = memory.get("turn_idx")
        if turn_idx is None:
            return WHEN_BEFORE_RECORD
        if (self.current_turn_idx is not None
                and not self._is_readable_turn(turn_idx)):
            return WHEN_UNPLACEABLE
        if memory.get("frame_id") != self.viewer_frame_id:
            return WHEN_UNPLACEABLE
        reading = memory.get("encoded_at_seconds")
        if reading is None:
            return WHEN_UNPLACEABLE
        try:
            ago = float(self.now_seconds) - float(reading)
        except (TypeError, ValueError):
            return WHEN_UNPLACEABLE
        return time_ago_phrase(ago) or WHEN_UNPLACEABLE

    def of_window(self, start_turn_idx, end_turn_idx) -> str:
        """The "when" one summarised window of turns carries.

        "" -- say nothing at all -- for a window that closed at or after the
        deciding turn, which is the one answer this must keep giving in turn
        indices: that is future knowledge, and the callers already treat "" as
        a refusal rather than as a phrase.
        """
        if self.current_turn_idx is None:
            return ""
        if not self._is_readable_turn(
                end_turn_idx if end_turn_idx is not None else 0):
            return ""
        opened, closed = window_clock_readings(
            self.chat_id, self.char_id, start_turn_idx, end_turn_idx,
            frame_id=self.viewer_frame_id)
        if opened is None or closed is None:
            return WHEN_UNPLACEABLE
        return time_ago_span(
            float(self.now_seconds) - opened,
            float(self.now_seconds) - closed) or WHEN_UNPLACEABLE


# ---- When a past turn's clock stood where it did ----------------------------
#
# THE SEAM. A single memory carries its own stored reading, so it needs nothing
# from here. A SUMMARY does: it names a window of turn indices and no clock
# reading of its own, and the window's ends have to be resolved to fiction time
# before the ladder can say anything about them.
#
# Today that resolution reads the stored readings back off the memories the
# window actually consolidated -- real recorded values, not an estimate. The
# replacement is a stored per-turn clock history: one row per committed turn
# holding the reading that turn ended at, which would answer this for a window
# whose own memories have been archived away or never existed, and which would
# also retire the migration's `turn_idx * UNCLAIMED_BEAT_SECONDS` backfill.
# When that lands, this function's BODY changes and nothing downstream does.

def window_clock_readings(chat_id, char_id, start_turn_idx, end_turn_idx,
                          *, frame_id=None):
    """The (opened_at, closed_at) fiction-time readings of one turn window.

    `(None, None)` when nothing in the window carries a reading -- a caller
    that gets it must fall back to a qualitative phrase rather than invent a
    number. Both ends come from one query over the whole window rather than
    from its two endpoint turns individually, because a window's first or last
    beat may legitimately have minted this character no memory at all.

    Scoped to ONE frame, for the reason `MemoryClock` refuses to cross one: a
    window's turn range is global play order and can span two frames' rows,
    whose readings come off two unrelated clocks.
    """
    if chat_id is None or char_id is None:
        return (None, None)
    try:
        lo_idx = int(start_turn_idx or 0)
        hi_idx = int(end_turn_idx or 0)
    except (TypeError, ValueError):
        return (None, None)
    if hi_idx < lo_idx:
        lo_idx, hi_idx = hi_idx, lo_idx
    row = q("SELECT MIN(encoded_at_seconds) AS lo, MAX(encoded_at_seconds) AS hi "
            "FROM memories WHERE chat_id=? AND char_id=? "
            "AND turn_idx>=? AND turn_idx<=? AND encoded_at_seconds IS NOT NULL "
            "AND frame_id IS ?",
            (chat_id, char_id, lo_idx, hi_idx, frame_id), one=True)
    if not row or row["lo"] is None or row["hi"] is None:
        return (None, None)
    return (float(row["lo"]), float(row["hi"]))
