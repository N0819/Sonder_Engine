"""A pose detail's possession claim is reconciled against the ledgers in
whatever script the story is written.

Audit world_spatial_truth F17 (2026-11-01, CONFIRMED, language pack): the three
pose-prose reconciliations (`invalidate_transferred_pose_details`,
`invalidate_moved_body_pose_details`, `invalidate_contact_bound_poses`) found
names with `\\b`/`(?<!\\w)` -- which never bound a Japanese name followed by a
particle, every kana and kanji being `\\w` -- split clauses on ASCII
punctuation only, and gated on an English verb list. The same transfer that
retires "holding the jar against her chest" retired nothing for
壺を胸に抱えて持っている, and `invalidate_moved_body_pose_details` returned `[]`
for ミレルを抱きかかえている: the measured chat 98/99 defects these exist to
close recurred in every Japanese story.

The class rule (stated, not a word list): the ledger moved the thing and the
clause names the thing. The English carriage list stays a REFINEMENT for the
script it can read; a clause it cannot read a word of is decided by the
structural rule alone.
"""

from world.spatial import (invalidate_moved_body_pose_details,
                           invalidate_transferred_pose_details)


def _scene(detail, *, subject="Hinami"):
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": []},
                  "yard": {"name": "Yard", "adjacent": []}},
        "positions": {"Hinami": "hall", "Mirelle": "hall", "ミレル": "hall",
                      "jar": "hall"},
        "entities": {"jar": {"name": "壺", "kind": "object", "aliases": ["jar"]}},
        "attire": {"Hinami": {}, "Mirelle": {}, "ミレル": {}},
        "poses": {subject: {"posture": "standing", "detail": detail}},
    }


def _hand_over():
    return [{"op": "transfer", "object_id": "jar", "from_id": "Hinami",
             "to_id": "Mirelle"}]


def test_a_japanese_possession_clause_is_retired_with_the_transfer():
    sc = _scene("壺を胸に抱えて持っている")
    assert invalidate_transferred_pose_details(sc, _hand_over()) == [("Hinami", "jar")]
    assert sc["poses"]["Hinami"]["detail"] == ""


def test_a_japanese_clause_about_something_else_is_kept():
    sc = _scene("窓の外を見つめている")
    assert invalidate_transferred_pose_details(sc, _hand_over()) == []
    assert sc["poses"]["Hinami"]["detail"] == "窓の外を見つめている"


def test_english_keeps_its_verb_refinement():
    sc = _scene("watching the jar, braced against the console")
    assert invalidate_transferred_pose_details(sc, _hand_over()) == []
    sc = _scene("holding the jar against her chest")
    assert invalidate_transferred_pose_details(sc, _hand_over()) == [("Hinami", "jar")]


def test_a_japanese_hold_on_a_body_that_moved_is_retired():
    sc = _scene("ミレルを抱きかかえている")
    before = dict(sc["positions"])
    sc["positions"]["ミレル"] = "yard"
    assert invalidate_moved_body_pose_details(sc, before) == [("Hinami", "ミレル")]
    assert sc["poses"]["Hinami"]["detail"] == ""


def test_a_name_inside_a_longer_name_is_not_that_name():
    sc = _scene("ミレルコを抱きかかえている")
    before = dict(sc["positions"])
    sc["positions"]["ミレル"] = "yard"
    assert invalidate_moved_body_pose_details(sc, before) == []
