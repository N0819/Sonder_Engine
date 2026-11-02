"""A card's acuity for tells is the acuity the world reads off it.

`_tell_acuity` kept its own vocabulary: a channel counted only when it was
spelled exactly `vision`, `hearing` or `general`, and the acuity came from a
nine-word table with everything else at 0.4. The engine's reader
(`spatial.sense_acuity_offset`) knows `sight`/`eyes`/`visual` and
`keen`/`acute`/`sharp`/..., so the two disagreed on 6 of 8 ordinary
spellings (audit agents_perception F5, 2026-11-01): a card written with the
engine's own channel word, or an ordinary synonym for keen, was graded an
ordinary observer and missed every `subtle` tell its author made it able to
catch. One reader now: the world's ladder offset, on the tell scale the
owner set -- ordinary 0.4, keen 0.65, exceptional 0.9 (`affect.TELL_ADVANTAGE`).
"""

import pytest

from agents.perception import _tell_acuity
from world.spatial import sense_acuity_offset

#: The owner's scale, by the world's ladder offset (dulled .. extraordinary).
SCALE = {-1: 0.2, 0: 0.4, 1: 0.65, 2: 0.9}


def _card(channel, acuity):
    return {"core": {}, "embodiment": {"senses": [
        {"channel": channel, "acuity": acuity}]}}


SPELLINGS = [
    ("vision", "keen"), ("sight", "keen"), ("eyes", "keen"),
    ("vision", "acute"), ("vision", "sharp"), ("hearing", "extraordinary"),
    ("vision", "supernatural"), ("vision", "exceptional"),
    ("audition", "expert"), ("vision", "failing"), ("hearing", "ordinary"),
]


@pytest.mark.parametrize("channel,acuity", SPELLINGS)
def test_the_tell_scale_follows_the_worlds_offset(channel, acuity):
    card = _card(channel, acuity)
    senses = card["embodiment"]["senses"]
    offsets = [sense_acuity_offset(senses, ch) for ch in ("sight", "hearing")]
    expected = max(0.0 if o is None else SCALE[o] for o in offsets)
    assert _tell_acuity(card) == expected


def test_the_owners_three_rungs_hold():
    assert _tell_acuity(_card("vision", "ordinary")) == 0.4
    assert _tell_acuity(_card("sight", "keen")) == 0.65
    assert _tell_acuity(_card("hearing", "extraordinary")) == 0.9


def test_no_card_is_an_ordinary_observer():
    assert _tell_acuity(None) == 0.4
    assert _tell_acuity({"core": {}, "embodiment": {"senses": []}}) == 0.4


def test_a_sense_the_card_lacks_is_no_acuity_and_the_other_still_counts():
    """A blind card with ordinary hearing still catches an ordinary heard
    tell; both absent catch nothing."""
    blind = _card("vision", "blind")
    assert _tell_acuity(blind) == 0.4
    both = {"core": {}, "embodiment": {"senses": [
        {"channel": "vision", "acuity": "blind"},
        {"channel": "hearing", "acuity": "deaf"}]}}
    assert _tell_acuity(both) == 0.0
