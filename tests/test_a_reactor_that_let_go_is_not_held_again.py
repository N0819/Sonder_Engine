"""A reactor's own contact endings count, as its material effects already do.

In a contested physical beat the reaction loop runs the reactor's character
step and stores it in `ctx.reaction_results`; the reactor is then left out
of the interaction loop (`loops`, `already_reacted`). Its declared
`contact_ops: [{op: remove, contact_ref: contact:0}]` -- wrenching free of a
grip -- was read from `ctx.character_results` alone, so it was never
validated, never shown to the encoder, and the Director's stale re-add of
the grip stood: a body that pulled free stayed held, with no warning. The
material-effects sibling has read both result sets all along (review
2026-11-01, director floors F6).
"""

from __future__ import annotations

import json

from agents.director import (_merge_character_contact_endings,
                             _validated_character_contact_endings)
from story.character_schema import default_character_data

SCENE = {
    "rooms": {"yard": {"name": "Yard", "adjacent": []}},
    "positions": {"Hinami": "yard", "Brute": "yard"},
    "entities": {},
    "contacts": [{"actor": "Brute", "actor_part": "hand", "target": "Hinami",
                  "target_part": "wrist", "manner": "grip", "relation": "surface",
                  "motion": "settled"}],
}


class _Ctx:
    cast = [{"id": 4, "sheet": json.dumps(default_character_data("Hinami"))}]
    character_results = {}
    reaction_results = {4: {"contact_ops": [{"op": "remove",
                                              "contact_ref": "contact:0"}]}}


def test_a_reactors_declared_ending_is_read_and_holds_against_a_re_add():
    endings = _validated_character_contact_endings(_Ctx(), SCENE)
    assert [(e["actor"], e["target_part"]) for e in endings] == [("Brute", "wrist")]
    stale = {"op": "add", "actor": "Brute", "actor_part": "hand",
             "target": "Hinami", "target_part": "wrist", "manner": "grip"}
    assert stale not in _merge_character_contact_endings(endings, [stale])


def test_an_ending_in_both_result_sets_is_one_ending():
    class Both(_Ctx):
        character_results = dict(_Ctx.reaction_results)
    assert len(_validated_character_contact_endings(Both(), SCENE)) == 1
