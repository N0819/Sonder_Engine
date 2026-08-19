"""A garment whose coverage nothing knew is said out loud.

`region_of` never fails — it falls back to the torso — and that is right,
because a garment on the torso is recoverable and a garment nowhere is not.
What was missing is that the fallback was SILENT. A qipao, a thawb, a sari or
a nagajuban the cue tables have not learnt lands on the torso alone, so the
body reports legs and groin bare while wearing a full-length garment, and the
wrong span is discovered twenty beats later when something undresses oddly.

`attire.guessed_spans` could spot exactly that and had **no production
caller**. Its own docstring described the hand-off in the present tense while
the loop stayed open — a reader met a closed feedback loop that was not closed.
Measured while it was open: 110 of 560 live worn garment records carry a
guessed span, twenty of them a nagajuban.

TOLD, NOT REPAIRED. The cue tables are the thing that does not know, so a
second deterministic guess is the same guess. The Director has the fiction in
front of it and can answer with `coverage` — and authored coverage is never
re-guessed, so this cannot nag about a choice somebody has already made.
"""

from __future__ import annotations

from types import SimpleNamespace

from persist import commit
from story import attire as attire_model


class _Ctx:
    def __init__(self):
        self.turn = SimpleNamespace(player_input="")
        self.cast = []
        self.told, self.warned = [], []

    def tell_director(self, msg):
        self.told.append(msg)

    def add_warning(self, msg):
        self.warned.append(msg)


def _wear(garment):
    sc = {"attire": {"Ayame": {"wearing": [], "state": [], "regions": {}}}}
    ctx = _Ctx()
    commit.apply_attire_diff(
        sc, {"attire": {"Ayame": {"add": [garment]}}}, ctx, {})
    return sc, ctx


def test_an_unrecognised_garment_is_reported_to_the_director():
    assert attire_model.span_is_a_guess("nagajuban")
    _sc, ctx = _wear("nagajuban")
    assert any("nagajuban" in m and "covers" in m for m in ctx.told), ctx.told


def test_a_garment_the_tables_know_says_nothing():
    assert not attire_model.span_is_a_guess("trousers")
    _sc, ctx = _wear("trousers")
    assert not [m for m in ctx.told if "covers" in m], ctx.told


def test_a_garment_somebody_placed_is_never_nagged_about():
    """Authored placement is the escape hatch, and nagging about a choice
    somebody already made is how a warning teaches people to stop reading
    warnings. Asserted against the detector directly, because the commit
    path's `placement` argument is a no-op today -- see `docs/UNBUILT.md`
    §1.72 -- so routing this through it would test the wrong thing."""
    placed = attire_model.apply_flat_change(
        {}, ["nagajuban"],
        placement={"nagajuban": ["torso", "legs", "groin"]})
    assert sorted(placed) == ["groin", "legs", "torso"]
    assert attire_model.guessed_spans(placed) == []


def test_the_perception_preview_stays_silent():
    """`report=False` is the mid-turn preview; it must not talk to anybody."""
    sc = {"attire": {"Ayame": {"wearing": [], "state": [], "regions": {}}}}
    ctx = _Ctx()
    commit.apply_attire_diff(
        sc, {"attire": {"Ayame": {"add": ["nagajuban"]}}}, ctx, {},
        report=False)
    assert ctx.told == [] and ctx.warned == []
