"""A body seen for the first time is not filed as a CHANGE.

`observations_from_render` set an observation's `phase` to "change" whenever
an appearance percept carried `force` -- and `force` is an objective fact
("this body's visible form moved this beat"), not this observer's. A woman
changed her coat in the hall; the player walked in that beat and saw her for
the first time; the view said `You see a woman in a grey wool coat.` and the
row went to `changes_noticed` for the character and the narrator alike -- one
bit of a past state handed to a mind that never held it (audit
agents_composer F2, 2026-11-01: `verdicts: {'described:...': 'first'} |
phase: ['change'] | changes_noticed: 1`). The renderer's own docstring names
the rule this broke ("`force` is an objective judgement ... and it was
deciding a per-observer question").

A change is the observer's when its own ledger says so: the `beat` mark a
renderer stamps from the observer's previous ledger, or -- on the tier that
marks no beat -- a body this observer HELD last beat whose form moved.
"""

import pytest

from agents import composer

COAT = "A woman in a grey wool coat."


def _phases(percept, mode, prev_standing):
    view = composer.render_view([percept], mode=mode, language="en",
                                prev_standing=prev_standing)
    rows = composer.observations_from_render("player", view)
    packet = composer.perception_packet(rows)
    return [r["phase"] for r in rows], packet


@pytest.mark.parametrize("mode", ["player", "character"])
def test_a_first_sight_on_the_beat_her_coat_changed_is_state(mode):
    first = composer.appearance_percept("Ilse Varn", "the woman", COAT,
                                        force=True)
    # A ledger that exists and does not hold her: first sight.
    prev = frozenset({"env:abc:def"})
    phases, packet = _phases(first, mode, prev)
    assert phases == ["state"], phases
    assert not packet.get("changes_noticed"), packet


def test_a_held_body_whose_form_moved_is_a_change_for_a_character():
    """The character tier marks no beat, so the observer's own record --
    it held this body at full sight last beat -- is what says so."""
    moved = composer.appearance_percept("Ilse Varn", "the woman", COAT,
                                        force=True, held=True)
    phases, packet = _phases(moved, "character", frozenset({"env:abc:def"}))
    assert phases == ["change"], phases
    assert packet.get("changes_noticed"), packet


def test_an_unmoved_body_is_state_on_either_tier():
    still = composer.appearance_percept("Ilse Varn", "the woman", COAT,
                                        held=True)
    for mode in ("player", "character"):
        phases, _packet = _phases(still, mode, frozenset())
        assert phases == ["state"], (mode, phases)
