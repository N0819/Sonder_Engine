"""A garment condition describes the garment, not the body wearing it.

Live, chat 82 "Sarah Moon — Hinami attempt 2", t1. The body specialist emitted,
in one `state_diff`:

    "overlays": {...: [{"subject": "Hinami",
                        "description": "golden fox ears drooping limply
                                        atop copper-gold hair"}], ...}
    "attire":   {"Hinami": {"conditions": {
                    "lightweight travel jacket":
                        "golden fox ears drooping limply atop copper-gold hair",
                    "fitted tank top":
                        "unfocused amber eyes blink open slowly"}}}

Both strings are body overlays and both were ALSO filed correctly as overlays.
The garment copies committed, so every observer's attire row rendered
"lightweight travel jacket (golden fox ears drooping limply atop copper-gold
hair)" and the ledger panel showed the same. Same class as the three
contradictory "bare at the" notes: the symptom is in the ledger, the origin is
`state_diff.attire`.

THE RULE IS NOT "a condition may not mention a body". "Soaked through" is a
true thing to write about a coat and about the person in it, and no reading of
the sentence separates them. What the engine can read without understanding
either sentence is the CONTRADICTION: one beat filed one string to two
channels that answer two different questions, and the channel whose question
is "what does this body look like" is the one that was right.
"""

from __future__ import annotations

from types import SimpleNamespace

from persist import commit

OVERLAY = "golden fox ears drooping limply atop copper-gold hair"


class _Ctx:
    def __init__(self):
        self.turn = SimpleNamespace(player_input="")
        self.cast = []
        self.told, self.warned = [], []

    def tell_director(self, msg):
        self.told.append(msg)

    def add_warning(self, msg):
        self.warned.append(msg)


def _scene():
    return {"attire": {"Hinami": {
        "wearing": ["travel jacket"], "state": [],
        "regions": {"torso": {"garments": [
            {"name": "travel jacket", "state": "worn",
             "covers": ["torso"]}]}}}}}


def _diff(condition, *, overlays=True):
    diff = {"attire": {"Hinami": {"conditions": {
        "travel jacket": condition}}}}
    if overlays:
        diff["overlays"] = {
            OVERLAY: [{"subject": "Hinami", "description": OVERLAY}]}
    return diff


def _condition_of(sc):
    regions = (sc["attire"]["Hinami"].get("regions") or {})
    for garment in (regions.get("torso") or {}).get("garments") or []:
        if "jacket" in str(garment.get("name") or ""):
            return str(garment.get("condition") or "")
    return ""


def test_a_condition_that_is_this_bodys_own_overlay_is_dropped():
    sc, ctx = _scene(), _Ctx()

    commit.apply_attire_diff(sc, _diff(OVERLAY), ctx, {})

    assert _condition_of(sc) == "", (
        "the body overlay committed onto the garment and renders as part of "
        "its name to everyone who sees them")
    assert any("describes the GARMENT" in m for m in ctx.told), ctx.told
    assert any("kept the overlay" in m for m in ctx.warned), ctx.warned


def test_a_real_garment_condition_is_untouched():
    sc, ctx = _scene(), _Ctx()

    commit.apply_attire_diff(sc, _diff("torn at the shoulder"), ctx, {})

    assert _condition_of(sc) == "torn at the shoulder"
    assert ctx.warned == []


def test_the_same_words_with_no_overlay_this_beat_are_untouched():
    """It fires on the contradiction, never on the sentence. Without the twin
    in `overlays` there are not two answers, and nothing here can tell a body
    description from a garment description by reading it."""
    sc, ctx = _scene(), _Ctx()

    commit.apply_attire_diff(sc, _diff(OVERLAY, overlays=False), ctx, {})

    assert _condition_of(sc) == OVERLAY
    assert ctx.warned == []


def test_another_bodys_overlay_does_not_censor_this_ones_condition():
    sc, ctx = _scene(), _Ctx()
    diff = _diff(OVERLAY, overlays=False)
    diff["overlays"] = {OVERLAY: [{"subject": "Sable", "description": OVERLAY}]}

    commit.apply_attire_diff(sc, diff, ctx, {})

    assert _condition_of(sc) == OVERLAY
    assert ctx.warned == []
