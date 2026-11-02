"""A record both stages wrote is folded into the merged diff the way its
program's steps fold it, so the program reads no correction nobody made.

`merge_player_state_assertions` carries the interpret's assertions into the
resolve's diff: their `causal_steps` run first, and at the top level a subject
the resolve restated yielded WHOLE. Since `program_steps` strips from every
earlier step each field a corrected record lacks (`causal_program._strip_to`,
world_misc_causal F7, 2026-11-01), that whole yield read as a correction: a
room the beat opened on, built in by the interpret's leading step, its door
then pulled to by the resolve, lost every field the install gave it and was
committed as its stub -- three tests of
`tests/test_a_room_built_ahead_stands_before_the_beat_touches_it.py` went red
(the 2026-11-01 review's fallout lane). Where the merged diff is a program,
the top level is now the steps' fold of a record both stages wrote; a floor's
pop after the merge is still a correction, and strips both stages' writes.
"""

from __future__ import annotations

from agents.common import merge_player_state_assertions
from world.causal_program import fold_steps, program_steps

BUILT = {"name": "Lamp Gallery",
         "desc": "A narrow iron walk girdling the lantern.",
         "adjacent": [{"to": "keeper_room", "barrier": "open"}]}
DOOR_TO = {"adjacent": [{"to": "keeper_room", "barrier": "closed_door"}]}


def _program(stage, chrono, channel, subject, record):
    return {channel: {subject: dict(record)},
            "causal_steps": [{"stage": stage, "chrono_id": chrono, "events": [],
                              "patch": {channel: {subject: dict(record)}}}]}


def test_a_room_built_in_keeps_its_build_when_the_resolve_shuts_its_door():
    merged = merge_player_state_assertions(
        _program("interpret", 0, "rooms", "lamp_gallery", BUILT),
        _program("resolve", 1, "rooms", "lamp_gallery", DOOR_TO))
    room = fold_steps(program_steps(merged))["rooms"]["lamp_gallery"]
    assert room["desc"] == BUILT["desc"]
    assert room["name"] == BUILT["name"]
    assert [edge["barrier"] for edge in room["adjacent"]] == ["closed_door"]


def test_a_field_a_floor_pops_after_the_merge_is_gone_from_both_stages():
    """F7 across the two stages: a station the interpret asserted, a pose the
    resolve wrote, and the walk then found to fall short."""
    merged = merge_player_state_assertions(
        _program("interpret", 1, "stations", "Ada",
                 {"at": "door", "posture": "standing"}),
        _program("resolve", 1, "stations", "Ada", {"posture": "crouching"}))
    assert merged["stations"]["Ada"] == {"at": "door", "posture": "crouching"}
    merged["stations"]["Ada"].pop("at")          # the floor, after the merge
    assert fold_steps(program_steps(merged))["stations"]["Ada"] == {
        "posture": "crouching"}


def test_without_a_program_a_restated_subject_still_yields_whole():
    notes = []
    merged = merge_player_state_assertions(
        {"stations": {"Ada": {"at": "door"}}},
        {"stations": {"Ada": {"posture": "crouching"}}}, report=notes.append)
    assert merged["stations"]["Ada"] == {"posture": "crouching"}
    assert any("restated stations for Ada" in note for note in notes)
