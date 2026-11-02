"""Three floors compared body identity by casefold string equality, where
their own siblings use the engine's resolver (`spatial.same_subject`).

A restraint row's `subject_id` is model-written and stored as written
(`commit_entities`: "Case-insensitive on subject because `subject_id` is a
model-written name"); a resolve contact op names its bodies however the
encoder reached for them. So a bound body written "Hinami Kurosawa" walked
out of the cell under her positions key "Hinami"; an alias-spelled resolve
op coarsened the player's asserted endpoint without the "preserved
player-declared contact endpoint" refusal; and a contact a character had
explicitly ended came back when the re-add spelled her full name (review
2026-11-01, director floors F4). One identity rule for all three, so each
floor applies to the body it already names -- no guard is widened.
"""

from __future__ import annotations

from agents.director import (_merge_character_contact_endings,
                             _merge_player_contact_assertions,
                             _restraint_blocked_moves)

SCENE = {
    "rooms": {"cell": {"name": "Cell", "adjacent": []},
              "hall": {"name": "Hall", "adjacent": []}},
    "positions": {"Hinami": "cell", "Mirelle": "cell"},
    "entities": {
        "Hinami": {"name": "Hinami", "kind": "person", "aliases": ["Hinami Kurosawa"]},
        "Mirelle": {"name": "Mirelle", "kind": "person", "aliases": ["Mirelle Sulmirath"]},
    },
    "contacts": [],
}


def test_a_bound_body_named_by_its_full_name_does_not_walk_out():
    record = {"subject": "Hinami Kurosawa", "standing": True, "level": "bound",
              "by": "", "condition_id": "c1"}
    blocked = _restraint_blocked_moves({"positions": {"Hinami": "hall"}}, SCENE,
                                       [record], {}, ["Hinami", "Mirelle"])
    assert [who for who, _r in blocked] == ["Hinami"]


def test_an_alias_spelled_resolve_op_cannot_coarsen_the_players_endpoint():
    assertion = {"op": "add", "actor": "Hinami", "actor_part": "hand",
                 "target": "Mirelle", "target_part": "wrist", "manner": "grip"}
    coarser = {"op": "add", "actor": "Hinami Kurosawa", "actor_part": "hand",
               "target": "Mirelle", "target_part": "arm", "manner": "grip"}
    notes = []
    merged = _merge_player_contact_assertions(
        [assertion], [coarser], report=notes.append, scene=SCENE,
        player_name="Hinami")
    assert coarser not in merged, merged
    assert [n for n in notes if "preserved player-declared contact endpoint" in n]


def test_a_contact_her_character_ended_is_not_re_added_under_her_full_name():
    ending = {"op": "remove", "actor": "Mirelle", "actor_part": "hand",
              "target": "Hinami", "target_part": "wrist",
              "source": "character_declaration", "declared_by": "Mirelle"}
    readd = {"op": "add", "actor": "Mirelle Sulmirath", "actor_part": "hand",
             "target": "Hinami", "target_part": "wrist", "manner": "grip"}
    notes = []
    merged = _merge_character_contact_endings([ending], [readd],
                                              report=notes.append, scene=SCENE)
    assert readd not in merged, merged
    assert notes == ["discarded Director re-add of character-ended contact"]
