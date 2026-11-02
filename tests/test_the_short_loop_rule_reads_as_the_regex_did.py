"""The short-loop rule gives the regex's verdicts at a fraction of its cost.

`OutputGuard` runs on every streamed call, every 200 characters, with the GIL
held. Its short-loop rule was the regex `(.{2,23})\\1{80,}` searched over the
4 KB tail, and measured (review 2026-11-01, llm_providers_quality,
Efficiency 1) it was most of the guard's CPU: 2.41 s of 700 strides against
0.12 / 0.06 / 0.10 / 0.01 s for the other four rules -- roughly 0.1-0.4 s a
call, seconds on a long page, contending with parallel character streams.

`providers._short_loop` answers the same question without backtracking: a
phrase of p characters repeated 81 times is a p-periodic stretch of 81p
characters, so sampling every 79p characters must land inside one, and a
sample whose next p characters repeat is extended by slice comparison to its
whole periodic run. The regex stays HERE, as the specification: these tests
hold the replacement to its verdict, window by window and stream by stream.
"""
from __future__ import annotations

import random
import re

import pytest

from llm import providers

#: The rule as it was written, kept as the oracle.
SPEC = re.compile(r"(.{2,%d})\1{80,}" % (providers._LOOP_MIN_PERIOD - 1), re.S)

PROSE = (
    "The lamp burns low over the chart table. Mara traces the coastline with "
    "one finger, stopping where the soundings run out. \"Here,\" she says, "
    "\"and no further. Ha ha ha -- they told me the same thing in Brackwater.\" "
    "Outside, the rain keeps on at the shutters; somewhere below, a door bangs "
    "twice and is still. ...... -- -- -- She does not look up.\n\n")


def _corpus(seed=11, n=1500):
    rng = random.Random(seed)
    alphabet = "ab c.\n-*"
    out = []
    for _ in range(n):
        kind = rng.random()
        if kind < 0.25:
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(100, 4000)))
        elif kind < 0.65:
            p = rng.randint(1, 26)
            unit = "".join(rng.choice(alphabet + "xyz") for _ in range(p))
            reps = rng.randint(60, 100)
            text = (PROSE * 3)[:rng.randint(0, 1200)] + (unit * reps)[rng.randint(0, p):] \
                + (PROSE * 3)[:rng.randint(0, 1200)]
        else:
            text = (PROSE * 12)[rng.randint(0, 900):][:rng.randint(160, 4000)]
            if rng.random() < 0.4:
                p = rng.randint(2, 23)
                at = rng.randint(0, len(text))
                text = text[:at] + text[at:at + p] * rng.randint(70, 90) + text[at:]
        out.append(text[-4000:])
    return out


def test_every_window_gets_the_regex_verdict():
    rng = random.Random(5)
    for text in _corpus():
        for start in (0, rng.randint(0, len(text) // 2)):
            assert providers._short_loop(text, start, len(text)) == \
                (SPEC.search(text, start) is not None), (start, text[:120])


@pytest.mark.parametrize("period", range(2, 24))
def test_the_boundary_is_the_regex_s_at_every_period(period):
    unit = "".join(chr(ord("a") + (i % 26)) for i in range(period))
    for repeats, expected in ((80, False), (81, True)):
        for cut in range(0, period, max(1, period // 3)):
            text = PROSE[:300] + (unit * repeats)[cut:] + unit[:cut] + PROSE[:200]
            assert (SPEC.search(text) is not None) is expected
            assert providers._short_loop(text, 0, len(text)) is expected


def test_a_stream_raises_at_the_same_stride_as_before():
    """The guard as a whole, fed in pieces: same verdict, same moment."""
    class _Old(providers.OutputGuard):
        pass

    def first_raise(guard_cls, text, chunk):
        guard = guard_cls()
        for i in range(0, len(text), chunk):
            try:
                guard.feed(text[i:i + chunk])
            except providers.DegenerateOutput as exc:
                return i, exc.reason
        return None

    def old_feed(self, delta):
        # The rule as it stood: the regex over the 4 KB tail, in place of
        # `_short_loop`, everything else the guard does unchanged.
        real = providers._short_loop
        try:
            providers._short_loop = lambda text, start, end: \
                SPEC.search(text, start, end) is not None
            return providers.OutputGuard.feed(self, delta)
        finally:
            providers._short_loop = real

    _Old.feed = old_feed
    rng = random.Random(3)
    for text in _corpus(seed=23, n=300):
        chunk = rng.randint(3, 60)
        assert first_raise(_Old, text, chunk) == \
            first_raise(providers.OutputGuard, text, chunk)
