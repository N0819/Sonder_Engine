"""Regression tests for OutputGuard's check-stride throttle: the expensive
regex/control-char scan used to run on every single streamed delta once past
160 chars, rescanning nearly the same 4KB tail hundreds of times over one
response. Throttling to every _GUARD_CHECK_STRIDE new characters must not
weaken detection for real incremental (small-delta) streaming."""

from __future__ import annotations

import pytest

from providers import DegenerateOutput, OutputGuard, _GUARD_CHECK_STRIDE


def test_incremental_small_deltas_still_detect_repetition():
    guard = OutputGuard()
    with pytest.raises(DegenerateOutput):
        # Feed one character at a time, as real token-level streaming
        # would, rather than the whole degenerate string in one call --
        # needs to clear the single-char-repetition threshold (351+ in a
        # row), not just the 160-char floor that gates checking at all.
        for _ in range(500):
            guard.feed("x")


def test_incremental_small_deltas_allow_normal_text():
    guard = OutputGuard()
    text = (
        "Tamamo steps into the garden, and the fox-fire drifts quietly "
        "around the stone lantern. The Doctor watches with interest, "
        "saying nothing for a long moment before he finally speaks."
    )
    for ch in text:
        guard.feed(ch)


def test_checks_are_throttled_not_run_on_every_delta():
    guard = OutputGuard()
    checked_lengths = []
    real_len = len(guard.text)

    # Cycle through varied characters (never repeating enough to trip any
    # degenerate-output pattern) one at a time past the initial 160-char
    # floor, and track how many times the internal _checked_len watermark
    # actually advances -- it should advance far less often than once per
    # feed().
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789 "
    for i in range(_GUARD_CHECK_STRIDE * 3):
        guard.feed(alphabet[i % len(alphabet)])
        if guard._checked_len != real_len:
            checked_lengths.append(guard._checked_len)
            real_len = guard._checked_len

    assert len(checked_lengths) < _GUARD_CHECK_STRIDE * 3
    assert len(checked_lengths) <= 4
