"""A transformed body must not tripwire on its old disguise's terms.

`_subject_disguise_context` drops the disguise when a transformation is active
-- one outward form, and the transformation is it -- and so returns
`known_to=None`. The tripwire terms used to be read straight off
`active_disguises`, which does not apply that precedence, so the two disagreed:
concealed features with nobody marked as knowing them, which made every
observer read as unaware.

Live (chat 74): Hinami's `glamour_dropped` transformation correctly overrode
three stale disguise rows, and perception_outcome still warned that 'fox ears'
leaked to The Doctor -- who is in `known_to`, looking at ears that were by then
genuinely there.
"""

from __future__ import annotations

import agents.perception as perception
from agents.perception import _disguise_leak_check, _subject_concealed_terms


class _Ctx:
    def __init__(self):
        self.warnings = []


DISGUISE = {
    "subject": "Hinami",
    "concealed_terms": ["fox ears", "six tails"],
    "known_to": ["The Doctor"],
    "presented_appearance": "An ordinary human traveler.",
}


def test_a_transformed_body_has_no_concealed_terms(monkeypatch):
    monkeypatch.setattr(perception, "active_disguises",
                        lambda _cid: {"hinami": DISGUISE})
    monkeypatch.setattr(perception, "active_transformations",
                        lambda _cid: {"hinami": {"true_appearance": "Fox ears."}})
    assert _subject_concealed_terms(74, "Hinami") == []


def test_an_undisturbed_disguise_still_yields_its_terms(monkeypatch):
    monkeypatch.setattr(perception, "active_disguises",
                        lambda _cid: {"hinami": DISGUISE})
    monkeypatch.setattr(perception, "active_transformations", lambda _cid: {})
    assert _subject_concealed_terms(74, "Hinami") == ["fox ears", "six tails"]


def test_the_tripwire_stays_silent_once_the_glamour_is_dropped(monkeypatch):
    """The whole bug, end to end: terms empty => no warning for anyone, even
    though the view now names the feature (which is correct -- it is real)."""
    monkeypatch.setattr(perception, "active_disguises",
                        lambda _cid: {"hinami": DISGUISE})
    monkeypatch.setattr(perception, "active_transformations",
                        lambda _cid: {"hinami": {"true_appearance": "Fox ears."}})
    ctx = _Ctx()
    _disguise_leak_check(
        ctx, "perception_outcome",
        {"2": "Her fox ears twitch as she turns toward the console."},
        [{"id": "2", "name": "The Doctor"}],
        "Hinami", _subject_concealed_terms(74, "Hinami"), None)
    assert ctx.warnings == []


def test_a_genuinely_unaware_observer_is_still_caught(monkeypatch):
    """The tripwire must not be defanged in general -- with a live disguise and
    an observer outside known_to, the warning still fires."""
    monkeypatch.setattr(perception, "active_disguises",
                        lambda _cid: {"hinami": DISGUISE})
    monkeypatch.setattr(perception, "active_transformations", lambda _cid: {})
    ctx = _Ctx()
    _disguise_leak_check(
        ctx, "perception_outcome",
        {"9": "A young woman with unmistakable fox ears steps through."},
        [{"id": "9", "name": "Security Guard"}],
        "Hinami", _subject_concealed_terms(74, "Hinami"), {"hinami"})
    assert len(ctx.warnings) == 1
    assert "Security Guard" in ctx.warnings[0]
    assert "fox ears" in ctx.warnings[0]
