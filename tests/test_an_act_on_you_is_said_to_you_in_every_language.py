"""An act whose typed targets name the observer is directed at the observer,
in every language.

`act_percept` computes `targets_self` from the event's own `targets` -- the
structural answer -- and used it only to choose a rewrite, while the
observation's `directed_at_self` was decided by an English regex over the
surface (`\\byou\\b|\\byour\\b`). A Japanese act on the observer
(「葵の肩に手を置く」) therefore said False where the same English act said
True (audit agents_composer F10, 2026-11-01).
"""

from agents import composer
from language_runtime import language_scope


def _scene():
    return {"rooms": {"h": {"name": "広間", "light": "bright"}},
            "positions": {"葵": "h", "蓮": "h"}}


def _act(surface, targets):
    return {"type": "action", "attempt": surface, "observable": surface,
            "targets": targets, "visibility": "overt",
            "event_id": "turn:1:蓮:0:action"}


def test_a_japanese_act_on_the_observer_is_directed_at_them():
    with language_scope("ja"):
        p = composer.act_percept(
            _scene(), _act("葵の肩に手を置く", ["葵"]), "葵", "蓮",
            {"same_room": True}, display="蓮", can_see=True,
            self_forms=["葵"], surface="葵の肩に手を置く")
    assert p is not None
    assert p.data["directed_at_self"] is True, p.data


def test_an_act_on_somebody_else_is_not():
    with language_scope("ja"):
        p = composer.act_percept(
            {"rooms": {"h": {"name": "広間", "light": "bright"}},
             "positions": {"葵": "h", "蓮": "h", "凛": "h"}},
            _act("凛の肩に手を置く", ["凛"]), "葵", "蓮",
            {"same_room": True}, display="蓮", can_see=True,
            self_forms=["葵"], surface="凛の肩に手を置く")
    assert p is not None and p.data["directed_at_self"] is False, p.data
