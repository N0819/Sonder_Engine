"""One unit contract for the interior: review 2026-09-07 finding A81.

`elapsed_psych_units` is what every transient ledger relaxes on -- mood and
undercurrent through `affect.decay_affect`, drive strain through
`update_drive_strain`, the hedonic levels through `resolve_hedonic`. It reads
the story clock, and its `else` branch fell back to the one-unit-per-turn
cadence on *any* non-advance, which inverted the whole scale: a beat that
asserted zero duration relaxed those ledgers by a full unit (one minute),
where a beat that honestly took ten seconds relaxed them by 0.167 and one that
took fifty by 0.83. The engine's own clock says which case is which --
`mechanics.beat_end_elapsed` charges an unclaimed beat `UNCLAIMED_BEAT_SECONDS`
and treats any readable claim, `duration_seconds: 0` included, as the beat
saying no time passed -- so a still clock is an assertion and only an
unreadable one is a missing answer.
"""

from __future__ import annotations

import math

from mind import affect
from mind.psychology_runtime import elapsed_psych_units


def test_an_asserted_still_clock_relaxes_nothing():
    assert elapsed_psych_units(1200.0, 1200.0, fallback_turns=1) == 0.0


def test_a_short_beat_still_costs_less_than_a_long_one():
    """The inversion itself: every readable reading is ordered by duration."""
    still = elapsed_psych_units(100.0, 100.0)
    ten_seconds = elapsed_psych_units(100.0, 110.0)
    fifty_seconds = elapsed_psych_units(100.0, 150.0)
    an_hour = elapsed_psych_units(100.0, 3700.0)

    assert still < ten_seconds < fifty_seconds < an_hour
    assert ten_seconds == 10.0 / 60.0


def test_a_backwards_clock_relaxes_nothing_either():
    """`_monotonic_elapsed` already refuses a backwards beat; if one reaches
    here it is not evidence that time passed."""
    assert elapsed_psych_units(500.0, 100.0, fallback_turns=3) == 0.0


def test_the_turn_cadence_survives_where_the_clock_cannot_be_read():
    """The first beat of a character stores no clock at all, and that is the
    case the fallback exists for."""
    assert elapsed_psych_units(None, 240.0, fallback_turns=1) == 1.0
    assert elapsed_psych_units(240.0, "not a clock", fallback_turns=2) == 2.0
    assert elapsed_psych_units(
        float("nan"), 240.0, fallback_turns=1) == 1.0


def test_a_still_beat_leaves_the_mood_and_the_strain_where_they_were():
    """What the unit is FOR, at both ledgers the finding names -- the surface
    mood, which had no per-beat floor of its own, and the drive strain, which
    was given one to survive this."""
    units = elapsed_psych_units(600.0, 600.0)
    va = (0.6, 0.7)

    assert affect.decay_affect(va, (0.0, 0.0), units) == va
    assert affect.update_drive_strain(
        0.8, [], None, None, None, units)[0] == 0.8
    assert not math.isnan(units)
