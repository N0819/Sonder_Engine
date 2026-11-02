"""A field a deterministic floor removed from the folded diff stays removed
when the program's steps are replayed.

world_misc_causal F7 (audit 2026-11-01, mechanism CONFIRMED): when a
corrected record differed from the fold, `program_steps` rewrote only the
LAST step that wrote the record. An earlier step that wrote the refused field
kept it, `merge_scene_with_diff` replays every step, and the refused field
came back -- the shape resolve's floors produce when they pop a walker's
`at` from `sd["stations"]` after `_run_specialists` built the steps
(`director_movement`'s fall-short floor), whenever two spans wrote that
walker's station.
"""

from copy import deepcopy

from world.causal_program import fold_steps, program_steps


def _diff(steps):
    diff = deepcopy(fold_steps(steps))
    diff["causal_steps"] = deepcopy(steps)
    return diff


def test_a_floor_popped_field_does_not_come_back_from_an_earlier_span():
    steps = [
        {"stage": "resolve", "chrono_id": 1, "events": ["e1"],
         "patch": {"stations": {"Ada": {"at": "door", "posture": "standing"}}}},
        {"stage": "resolve", "chrono_id": 2, "events": ["e2"],
         "patch": {"stations": {"Ada": {"posture": "crouching"}}}},
    ]
    diff = _diff(steps)
    assert diff["stations"]["Ada"]["at"] == "door"
    diff["stations"]["Ada"].pop("at")          # the walk fell short
    replayed = fold_steps(program_steps(diff))
    assert replayed["stations"]["Ada"] == {"posture": "crouching"}


def test_a_nested_field_a_floor_removed_stays_removed():
    steps = [
        {"stage": "resolve", "chrono_id": 1, "events": ["e1"],
         "patch": {"entities": {"box": {"held_by": "Mara",
                                        "state": {"open": True, "lit": True}}}}},
        {"stage": "resolve", "chrono_id": 2, "events": ["e2"],
         "patch": {"entities": {"box": {"state": {"open": False}}}}},
    ]
    diff = _diff(steps)
    diff["entities"]["box"].pop("held_by")
    diff["entities"]["box"]["state"].pop("lit")
    replayed = fold_steps(program_steps(diff))
    assert replayed["entities"]["box"] == {"state": {"open": False}}


def test_an_unchanged_record_keeps_its_chronology():
    steps = [
        {"stage": "resolve", "chrono_id": 1, "events": ["e1"],
         "patch": {"stations": {"Ada": {"at": "door"}}}},
        {"stage": "resolve", "chrono_id": 2, "events": ["e2"],
         "patch": {"stations": {"Ada": {"posture": "crouching"}}}},
    ]
    program = program_steps(_diff(steps))
    assert program[0]["patch"]["stations"]["Ada"] == {"at": "door"}
    assert program[1]["patch"]["stations"]["Ada"] == {"posture": "crouching"}


def test_the_merged_scene_carries_no_refused_field():
    from world.spatial import merge_scene_with_diff
    steps = [
        {"stage": "resolve", "chrono_id": 1, "events": ["e1"],
         "patch": {"stations": {"Ada": {"at": "door", "posture": "standing"}}}},
        {"stage": "resolve", "chrono_id": 2, "events": ["e2"],
         "patch": {"stations": {"Ada": {"posture": "crouching"}}}},
    ]
    diff = _diff(steps)
    diff["stations"]["Ada"].pop("at")
    scene = {"rooms": {"hall": {"name": "Hall", "anchors": {
        "door": {"desc": "the door"}}}}, "positions": {"Ada": "hall"},
        "entities": {}}
    merged = merge_scene_with_diff(scene, diff)
    assert "at" not in ((merged.get("stations") or {}).get("Ada") or {})
