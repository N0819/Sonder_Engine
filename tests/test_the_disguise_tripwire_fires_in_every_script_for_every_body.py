"""The disguise tripwire can fire: in Japanese, and for every disguised body.

"Real leaks are guards that cannot fire." `_disguise_leak_check` matched a
concealed term with `\\b`, which never matches between Japanese characters,
and both stages passed it the PLAYER's terms alone and skipped the player
perceiver whoever the subject was -- so a Japanese leak was never warned,
and an NPC's disguise was never tripwired at all (audit agents_perception
F7, 2026-11-01: `en warnings: [...]`, `ja warnings: []` for 狐の耳 in
「彼女の狐の耳がぴくりと動くのが見える。」).

A warning, never a scrubber: the floor that keeps a concealed feature off the
page is the disguised appearance the view is composed from. This only catches
a leak that got past it.
"""

from __future__ import annotations

from agents.perception import _disguise_leak_check, _disguise_leak_checks
from tests.helpers import patch_seam


class _Ctx(dict):
    chat = {"id": 9}

    def __init__(self):
        super().__init__()
        self.warnings = []

    @property
    def _extra(self):
        return self


def test_a_japanese_leak_is_warned():
    ctx = _Ctx()
    _disguise_leak_check(
        ctx, "perception_outcome",
        {"g1": "彼女の狐の耳がぴくりと動くのが見える。"},
        [{"id": "g1", "name": "衛兵"}], "ヒナミ", ["狐の耳"], set())
    assert len(ctx.warnings) == 1 and "狐の耳" in ctx.warnings[0]


def test_a_word_that_only_contains_the_term_is_not_a_leak():
    ctx = _Ctx()
    _disguise_leak_check(
        ctx, "perception_outcome", {"g1": "The foxglove grows by the door."},
        [{"id": "g1", "name": "Guard"}], "Hinami", ["fox"], set())
    assert ctx.warnings == []


def test_the_player_is_checked_when_someone_else_is_disguised():
    """The exemption is the SUBJECT's, not the player's: the player watching
    a disguised NPC is an observer like any other."""
    ctx = _Ctx()
    _disguise_leak_check(
        ctx, "perception_act",
        {"player": "Mirelle's fox ears flick back."},
        [{"id": "player", "name": "Hinami"}], "Mirelle", ["fox ears"],
        {"mirelle"})
    assert len(ctx.warnings) == 1 and "Hinami" in ctx.warnings[0]


def test_the_subject_is_never_warned_about_itself():
    ctx = _Ctx()
    _disguise_leak_check(
        ctx, "perception_act", {"7": "You feel your fox ears under the hood."},
        [{"id": 7, "name": "Mirelle"}], "Mirelle", ["fox ears"], {"mirelle"})
    assert ctx.warnings == []


def test_every_disguised_body_is_tripwired(monkeypatch):
    disguises = {
        "mirelle": {"subject": "Mirelle", "concealed_terms": ["fox ears"],
                    "known_to": ["Bo"]},
        "hinami": {"subject": "Hinami", "concealed_terms": ["horns"],
                   "known_to": []},
    }
    patch_seam(monkeypatch, "agents.perception_bodies", "active_disguises",
               lambda _cid: disguises)
    patch_seam(monkeypatch, "agents.perception_bodies",
               "active_transformations", lambda _cid: {})
    ctx = _Ctx()
    views = {"player": "Mirelle's fox ears flick back.",
             "3": "Mirelle's fox ears flick back. Hinami's horns catch the light.",
             "4": "Hinami's horns catch the light."}
    perceivers = [{"id": "player", "name": "Hinami"},
                  {"id": 3, "name": "Bo"},
                  {"id": 4, "name": "Cy"}]
    _disguise_leak_checks(ctx, "perception_outcome", views, perceivers, {})
    said = sorted(ctx.warnings)
    # Hinami (the player) sees Mirelle's ears; Bo knows Mirelle but not
    # Hinami's horns; Cy sees the horns. Hinami is never warned about herself.
    assert len(said) == 3, said
    assert any("Hinami" in w and "fox ears" in w for w in said)
    assert any("Bo" in w and "horns" in w for w in said)
    assert any("Cy" in w and "horns" in w for w in said)
