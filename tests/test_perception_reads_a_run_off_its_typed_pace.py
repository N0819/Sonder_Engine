"""Perception's continuity floor reads a run where the Director's follow guard
does: off the declaration's typed pace first.

Two readers answer "did this body declare rapid movement" --
`director_movement._declares_rapid_movement` (the follow guard) and
`perception_conduct._declares_rapid_movement` (the open-group continuity
rescue). The Director's reads the typed `movement.pace` / an action's `pace`
first since 2026-11-01 (audit agents_director_prose_movement_rooms F10); the
perception one read only the verb against the pack's table, so a Japanese
declaration with an empty verb whose movement said `run` was a run to one
floor and a walk to the other (lane L7b's request).
"""

from agents.perception import _declares_rapid_movement


def test_a_typed_run_is_a_run_whatever_the_words():
    assert _declares_rapid_movement({
        "movement": {"to": "yard", "pace": "run"},
        "sequence": [{"type": "action", "verb": "",
                      "attempt": "中庭へ向かう"}]})
    assert _declares_rapid_movement([
        {"type": "action", "verb": "", "attempt": "中庭へ向かう",
         "pace": "run"}])


def test_a_typed_walk_and_no_pace_still_read_the_words():
    walk = {"movement": {"to": "yard", "pace": "walk"},
            "sequence": [{"type": "action", "verb": "walk",
                          "attempt": "walks to the yard"}]}
    assert not _declares_rapid_movement(walk)
    assert _declares_rapid_movement([
        {"type": "action", "verb": "sprint", "attempt": "sprints out"}])
