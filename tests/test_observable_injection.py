"""Regression tests for the observable-injection run-on / duplication fix
(P2). Since alpha3.1.2 the deterministic delivery uses the director-authored
`observable` surface, which models write as a full third-person sentence
('Dr. Moon tilts the phone...'). The old `f"{display} {attempt}."` composition
then double-named ('Dr. Moon Dr. Moon tilts...', 'Dr. Moon The flashlight beam
moves...') and its exact-substring dedupe missed the LLM's paraphrase.
"""

from __future__ import annotations

from agents.common import (
    _action_already_rendered,
    _inject_action,
    _observable_predicate,
)


def test_actor_led_surface_not_double_named():
    # "Dr. Moon tilts..." must not become "Dr. Moon Dr. Moon tilts..."
    out = _observable_predicate("Dr. Moon", "Dr. Moon tilts the phone toward her face")
    assert out == "Dr. Moon tilts the phone toward her face."
    assert "Dr. Moon Dr. Moon" not in out


def test_independent_clause_surface_keeps_own_subject():
    # "The flashlight beam moves..." carries its own subject; no display prefix
    out = _observable_predicate("Dr. Moon", "The flashlight beam moves in a slow arc")
    assert out == "The flashlight beam moves in a slow arc."
    assert not out.startswith("Dr. Moon The")


def test_predicate_surface_gets_display_prefix():
    out = _observable_predicate("Dr. Moon", "tilts the phone toward her face")
    assert out == "Dr. Moon tilts the phone toward her face."


def test_leading_pronoun_stripped():
    out = _observable_predicate("Dr. Moon", "she presses her palms to the wall")
    assert out == "Dr. Moon presses her palms to the wall."


def test_already_rendered_catches_paraphrase():
    view = ("A young woman presses her hands flat against the fresh scratches "
            "on the steel wall.")
    # near-identical beat, different tense/wording
    assert _action_already_rendered(view, "the young woman",
                                    "presses her hands against the scratched wall")


def test_inject_action_skips_when_already_rendered():
    view = "Dr. Moon tilts the smartphone toward her face and reads the screen."
    out = _inject_action(view, "Dr. Moon", "tilts the phone toward her face",
                         can_see=True)
    assert out == view  # no duplicate appended


def test_inject_action_appends_genuine_omission():
    view = "You are in the elevator car."
    out = _inject_action(view, "Dr. Moon", "raises one hand", can_see=True)
    assert "Dr. Moon raises one hand." in out
    assert "Dr. Moon Dr. Moon" not in out
