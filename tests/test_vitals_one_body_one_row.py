"""One body is one row in the vitals table (review 2026-09-07, B4 / A57).

`world.survival.vitals_entry_key` is the single answer to "which row is this
body's". Before it existed the question was answered twice: the condition tick
(`world/mechanics._vitals_entry_key`) matched a row case-insensitively while
`apply_vitals_diff` wrote under the exact spelling the Director sent -- so a
diff naming `mirela` where the row said `Mirela` opened a SECOND row,
`vitals_of` went on answering from the first, and both ticked.
"""

from __future__ import annotations

import world.mechanics as mechanics
from world.survival import (apply_vitals_diff, default_vitals, seed_vitals,
                            vitals_entry_key, vitals_of)


def _scene():
    return {"vitals": {"Mirela": default_vitals()}}


def test_diff_in_another_case_moves_the_existing_row():
    scene = _scene()
    apply_vitals_diff(scene, {"  mirela ": {"injury": 0.5}})
    assert list(scene["vitals"]) == ["Mirela"]
    assert vitals_of(scene, "Mirela")["injury"] == 0.5
    assert vitals_of(scene, "mirela")["injury"] == 0.5


def test_diff_for_an_unknown_body_still_opens_its_row():
    scene = _scene()
    apply_vitals_diff(scene, {"Ansel": {"stamina": 0.25}})
    assert sorted(scene["vitals"]) == ["Ansel", "Mirela"]
    assert vitals_of(scene, "Ansel")["stamina"] == 0.25


def test_null_patch_in_another_case_removes_the_existing_row():
    scene = _scene()
    apply_vitals_diff(scene, {"MIRELA": None})
    assert scene["vitals"] == {}


def test_seed_does_not_open_a_second_row_for_a_known_body():
    scene = _scene()
    seed_vitals(scene, ["mirela", "Ansel"])
    assert sorted(scene["vitals"]) == ["Ansel", "Mirela"]


def test_tick_and_diff_resolve_to_the_same_row():
    scene = _scene()
    scene["positions"] = {"Mirela": "cellar"}
    apply_vitals_diff(scene, {"mirela": {"air": 0.8}})
    cond = {
        "condition_id": "c1",
        "subject_id": "MIRELA",
        "payload": {"tick_interval_seconds": 10,
                    "tick": {"vitals": {"air": -0.2}}},
        "next_tick": 0.0,
    }
    ops, _notices = mechanics._tick_conditions(scene, [cond], 5.0)
    assert ops and list(scene["vitals"]) == ["Mirela"]
    assert round(vitals_of(scene, "Mirela")["air"], 4) == 0.6


def test_entry_key_answers_none_for_a_body_with_no_row():
    assert vitals_entry_key({"Mirela": default_vitals()}, "Ansel") is None
    assert vitals_entry_key(None, "Mirela") is None
    assert vitals_entry_key({"Mirela": default_vitals()}, "  ") is None
