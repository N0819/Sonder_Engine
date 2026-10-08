"""A body that sets off is moving, whether or not it gets there this beat.

The encoder's core card said `movement` was written "only when a body
changes room" while its own `arrives` field says whether the beat ends
there -- so a body still on its way wrote no movement at all. Measured on
scratch story 166 (2026-10-07, idx 12 and 14): the pilot "walks on west
along the low walk toward the landing stage" on two beats running, each
resolved with no movement event and no travel record, and never reached the
stage. One clause, both packs: a walk begun is a movement, with `arrives`
false while it is under way.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PINS = {"en": ("whether or not it gets there this beat", "arrives false"),
        "ja": ("着くかどうかに関わらず", "arrives false")}


@pytest.mark.parametrize("lang", sorted(PINS))
def test_the_encoder_writes_a_walk_that_has_not_arrived(lang):
    path = ROOT / "language_packs" / lang / "cards" / "system_prompts" / "encoder" / "core.txt"
    text = path.read_text(encoding="utf-8")
    for pin in PINS[lang]:
        assert pin in text
    assert "only when a body changes room" not in text
