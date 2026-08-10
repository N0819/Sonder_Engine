"""The world off screen advances on elapsed time, and the clock never moved.

Measured across the whole corpus before this change:

  director_resolve outputs carrying a time block   2,130
  mode='action'                                    2,122
  mode='time_skip'                                     7   (0.3%)
  beats advancing under one minute                  96.9%
  median beat                                         20s
  beats advancing over an hour, corpus-wide             2

Seven of fifty stories have EVER crossed a single in-world hour. A 171-turn
story covers 1.48 hours of fiction. So `epoch_reasons`' hour bucket — the
trigger every off-screen mechanism is gated on — effectively never fires, and
the 8.0 machinery reads `no chances` in `tools/fire_rates.py` not because it
declines but because nothing ever asks it.

The trigger was not the defect. The prompt was: it documented only the case
where the PLAYER writes a skip, which is the rare one, so the Director inferred
`action` and 20 seconds for travel, sleep and a night's watch alike. This is
the "name concrete occasions" rule in CLAUDE.md, applied to a clause that named
one.

The opposite failure is equally real and is asserted here too: inflating an
ordinary exchange of dialogue into ten minutes would make the fiction
incoherent, so "most beats are seconds and should stay seconds" has to survive
any future edit as firmly as the skip cases do.
"""

from __future__ import annotations

import pytest

from prompts import DEFAULT_PROMPTS

CLAUSE_START = "TIME:"
CLAUSE_END = "WEATHER:"


def _time_clause():
    text = DEFAULT_PROMPTS["director_resolve"]
    start = text.find(CLAUSE_START)
    assert start >= 0, "the resolve prompt lost its TIME clause"
    end = text.find(CLAUSE_END, start)
    return text[start:end if end > start else None]


@pytest.mark.parametrize("occasion", [
    "travel", "sleep", "wait", "search", "shift",
])
def test_the_clause_names_the_occasion(occasion):
    """A clause that names only the player-explicit case gets the
    player-explicit case and nothing else — which is what 0.3% means."""
    assert occasion in _time_clause().lower(), (
        f"the TIME clause no longer names {occasion!r} as a span of time")


def test_an_ordinary_beat_is_still_seconds():
    """The over-correction guard. If every beat became minutes the fiction
    would stop making sense, and that failure is harder to see than a frozen
    clock because the prose still reads fine."""
    clause = _time_clause().lower()
    assert "seconds and should stay seconds" in clause
    assert "do not inflate" in clause


def test_the_clause_says_why_it_matters():
    """A rule with no stated consequence is a rule that gets traded away. The
    reason the clock matters is not bookkeeping — it is that everyone else's
    life is gated on it."""
    clause = _time_clause().lower()
    assert "off screen" in clause
    assert "elapsed time" in clause


def test_explicit_still_means_the_player_said_so():
    """`explicit` is the field that separates a skip the player asked for from
    one the Director inferred. Widening the inference must not widen that flag,
    or the record stops being able to tell them apart."""
    assert "explicit` true only when the player said so" in _time_clause()
