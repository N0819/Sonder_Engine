"""Regression tests for OutputGuard's check-stride throttle: the expensive
regex/control-char scan used to run on every single streamed delta once past
160 chars, rescanning nearly the same 4KB tail hundreds of times over one
response. Throttling to every _GUARD_CHECK_STRIDE new characters must not
weaken detection for real incremental (small-delta) streaming."""

from __future__ import annotations

import hashlib

import pytest

from llm.providers import DegenerateOutput, OutputGuard, _GUARD_CHECK_STRIDE


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

    # Filler that is varied AND aperiodic, fed one character at a time past
    # the initial 160-char floor; the count is how many times the internal
    # _checked_len watermark advances, which should be far less often than
    # once per feed().
    #
    # It used to cycle a 37-character alphabet, which reads as varied and is
    # exactly periodic -- harmless while the longest unit any rule looked for
    # was 16 characters, and a tripwire the moment the phrase-loop rule
    # arrived, because three consecutive passes through the alphabet ARE three
    # identical 37-character blocks. A model emitting that is degenerate; the
    # filler was simply never meant to be a claim about acceptable output.
    # A digest stream, because "varied" is easy to get wrong: cycling an
    # alphabet is periodic, and so is any polynomial index into one (i*7 + i*i
    # mod 37 repeats every 37 characters just as plainly as i does).
    filler = "".join(hashlib.sha256(str(n).encode()).hexdigest()
                     for n in range(_GUARD_CHECK_STRIDE // 8 + 4))
    for i in range(_GUARD_CHECK_STRIDE * 3):
        guard.feed(filler[i])
        if guard._checked_len != real_len:
            checked_lengths.append(guard._checked_len)
            real_len = guard._checked_len

    assert len(checked_lengths) < _GUARD_CHECK_STRIDE * 3
    assert len(checked_lengths) <= 4
