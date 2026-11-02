"""A time claim that is not a finite number is unreadable, never adopted.

world_offscreen_time F14 (audit 2026-11-01): `read_time_diff` took
`float(td[key])` at its word, and `float("NaN")`, `float("Infinity")` and a
JSON `NaN` all parse. With the clock at NaN every `due_at > elapsed` is
False, so every pending consequence, news arrival and transit arrival fires
on the next sweep, and the clock stays NaN for good (`nan + d`). The span
reader one screen away (`beat_time_from_spans`) already drops a non-finite
span; the block reader now does the same, and the two readers that must
agree with it (`time_diff_claims`, `time_diff_duration`) agree.
"""

import math

import pytest

from world import mechanics

FLOOR = mechanics.UNCLAIMED_BEAT_SECONDS


@pytest.mark.parametrize("block, refused", [
    ({"end_seconds": "NaN"}, ["end_seconds"]),
    ({"end_seconds": float("nan")}, ["end_seconds"]),
    ({"elapsed_seconds": "inf"}, ["elapsed_seconds"]),
    ({"duration_seconds": "Infinity"}, ["duration_seconds"]),
    ({"duration_seconds": float("-inf")}, ["duration_seconds"]),
    ({"duration_seconds": float("nan")}, ["duration_seconds"]),
])
def test_a_non_finite_claim_is_charged_the_floor_and_reported(block, refused):
    elapsed, displaced, got_refused, floored = mechanics.beat_end_elapsed(
        100.0, block, floor=True)
    assert math.isfinite(elapsed)
    assert elapsed == pytest.approx(100.0 + FLOOR)
    assert floored is True
    assert displaced is None
    assert got_refused == refused
    assert mechanics.time_diff_claims(block) is False


def test_a_non_finite_anchor_does_not_poison_a_readable_end():
    elapsed, displaced, refused, floored = mechanics.beat_end_elapsed(
        100.0, {"start_seconds": "NaN", "end_seconds": 130.0}, floor=True)
    assert elapsed == pytest.approx(130.0) and not floored and refused == []


def test_the_vitals_seam_never_ages_a_body_by_infinity():
    assert mechanics.time_diff_duration({"duration_seconds": "inf"}) == 0.0
    assert mechanics.time_diff_duration(
        {"start_seconds": 0.0, "end_seconds": float("inf")}) == 0.0


def test_a_finite_claim_reads_exactly_as_before():
    assert mechanics.beat_end_elapsed(100.0, {"duration_seconds": 30},
                                      floor=True)[0] == pytest.approx(130.0)
    assert mechanics.beat_end_elapsed(100.0, {"end_seconds": "160"},
                                      floor=True)[0] == pytest.approx(160.0)
