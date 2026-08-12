"""Ask the cheap question cheaply.

A semantic-similarity trigger is a REVIEW trigger, not proof of bad
repetition -- and the review it bought was a full second character call:
the same ~25k payload and another ~7k of decision, measured live at 58.0s
and 36.3s. Across stored variants that call ran and KEPT the draft 48
times. Paying a frontier model to re-author a whole decision in order to
be told the decision was fine is the expensive way to ask a cheap question.

The screen decides only whether the character is asked AGAIN. It never
decides FOR the character -- that would be hardening a guard by making a
mind conclude less, which is the one fix this codebase refuses.
"""
from __future__ import annotations

import json

import llm_quality


def _reply(monkeypatch, text, seen=None):
    def fake(role, system, user, **kwargs):
        if seen is not None:
            seen.append({"role": role, "user": json.loads(user),
                         "max_tokens": kwargs.get("max_tokens")})
        return text
    monkeypatch.setattr(llm_quality, "chat_complete", fake)


_MOVE = {"turn": 4, "move": "reaches for the sash",
         "current": "reaches for the sash again"}


def test_a_warranted_repetition_is_kept_without_a_full_re_ask(monkeypatch):
    seen = []
    _reply(monkeypatch, '{"verdict": "keep"}', seen)
    assert llm_quality.move_repeat_screen(
        None, None, _MOVE, "She asks you not to stop.") is True
    # Cheap lane, small ceiling, and only what the character already held.
    assert seen[0]["role"] == "utility"
    assert seen[0]["max_tokens"] <= 400
    assert set(seen[0]["user"]) == {"already_did", "draft_does", "what_is_new"}


def test_an_unmotivated_reset_still_buys_the_full_retry(monkeypatch):
    _reply(monkeypatch, '{"verdict": "redo"}')
    assert llm_quality.move_repeat_screen(
        None, None, _MOVE, "She has already stepped away.") is False


def test_anything_unclear_falls_through_to_the_retry(monkeypatch):
    """Undecidable, malformed, or erroring screens leave the existing
    behaviour exactly as it was -- the guard is never weakened by a screen
    that could not answer."""
    for reply in ('{"verdict": "maybe"}', "not json", "{}"):
        _reply(monkeypatch, reply)
        assert llm_quality.move_repeat_screen(
            None, None, _MOVE, "x") is None

    def boom(*a, **k):
        raise RuntimeError("provider down")
    monkeypatch.setattr(llm_quality, "chat_complete", boom)
    assert llm_quality.move_repeat_screen(None, None, _MOVE, "x") is None
    assert llm_quality.move_repeat_screen(None, None, None, "x") is None


def test_the_screen_sees_nothing_the_character_did_not_already_hold(monkeypatch):
    """A screen that widened what is visible would be a leak wearing an
    optimisation's clothes. Its entitlement is a strict subset: the
    character's own prior move, its own draft, its own view of the beat."""
    seen = []
    _reply(monkeypatch, '{"verdict": "keep"}', seen)
    llm_quality.move_repeat_screen(None, None, _MOVE, "her own view")
    blob = json.dumps(seen[0]["user"])
    assert "her own view" in blob
    assert seen[0]["user"]["already_did"] == _MOVE["move"]
    assert seen[0]["user"]["draft_does"] == _MOVE["current"]
