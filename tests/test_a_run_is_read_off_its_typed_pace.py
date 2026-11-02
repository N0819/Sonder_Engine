"""A run is read off the declaration's typed pace, in every language.

`director_movement._declares_rapid_movement` decides whether a willing
follower can keep up (`_apply_following_movement` refuses to carry one
through a pursuit) and whether a declared walk is walked at a run
(`walk_declared`, `_walk_short_of`). It read only an action's free-text
`verb` against a pack word list and an English-only regex over its
`attempt` -- so a Japanese declaration with an empty `verb`, or an English
one written "takes off down the lane", was a walk, while the interpretation
already carried the typed answer (`MovementDecl.pace`) and nothing read it
(audit of 2026-11-01, `agents_director_prose_movement_rooms` F10; the
prose half is a request to the language lane).
"""

from agents.director_movement import _declares_rapid_movement


def test_a_declared_movement_at_a_run_is_rapid_whatever_its_words():
    interp = {"movement": {"to_room": "lane", "pace": "run"},
              "sequence": [{"type": "action", "verb": "", "attempt": "路地へ駆けていく"}]}
    assert _declares_rapid_movement(interp) is True


def test_a_declared_walk_is_not():
    interp = {"movement": {"to_room": "lane", "pace": "walk"},
              "sequence": [{"type": "action", "verb": "", "attempt": "路地へ歩いていく"}]}
    assert _declares_rapid_movement(interp) is False


def test_an_action_marked_run_is_rapid():
    result = {"sequence": [{"type": "action", "verb": "", "pace": "run",
                            "attempt": "takes off down the lane"}]}
    assert _declares_rapid_movement(result) is True
