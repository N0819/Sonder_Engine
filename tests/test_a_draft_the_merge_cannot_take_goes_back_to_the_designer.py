"""A draft the merge cannot take goes back to the designer as the check's
error; it never ends the design run (`director_rooms._merge_or_none`).

The designer's check has always caught a merge failure and handed it back
-- "the draft could not be merged into the world: ..." -- so a designer that
wrote a field in the wrong form redrafted it on the next step. The passes the
packing round of 2026-10-08 put before the check -- the far sides, the
doorways, the packing, each merging the draft first -- raised instead, out of
`design_rooms`: the Director's room author failed open and the beat lost
every room it was building that step, and the job that builds rooms between
turns filed its run as failed (round two's review). Two shapes a model can
write did it: a doorway as one object rather than a list of them, and a
`parent_entity` as an object. None of the 260 `draft_room` calls of that
day's play database had either, so play never met it.
"""

from __future__ import annotations

import copy

import pytest

from agents import director_rooms


def _scene():
    return {"rooms": {"hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 6, "d": 4}}},
            "positions": {}}


#: The two shapes the merge raises on, each with what fixes it.
_MALFORMED = {
    "a doorway as one object": (
        {"adjacent": {"to": "hall", "barrier": "open_door", "dir": "n"}},
        {"adjacent": [{"to": "hall", "barrier": "open_door", "dir": "n"}]}),
    "parent_entity as an object": (
        {"parent_entity": {"id": "boat"},
         "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "n"}]},
        {"parent_entity": None}),
}

#: What the designer does with the bad draft in the step it writes it.
_THEN = {
    "nothing": [],
    "view_room": [{"tool": "view_room", "args": {"room_id": "shed"}}],
    "inspect_rooms": [{"tool": "inspect_rooms", "args": {"room_ids": ["hall", "shed"]}}],
    "check": [{"tool": "check", "args": {}}],
    "submit": [{"tool": "submit", "args": {}}],
}


@pytest.mark.parametrize("then", sorted(_THEN))
@pytest.mark.parametrize("shape", sorted(_MALFORMED))
def test_a_draft_the_merge_cannot_take_is_handed_back_and_the_run_goes_on(shape, then):
    bad, fix = _MALFORMED[shape]
    shed = dict({"name": "Shed", "desc": "A shed with a bench.", "extent": {"w": 3, "d": 3},
                 "anchors": {"bench": {"desc": "a bench", "dir": "e", "footprint": "small",
                                       "height": "waist"}}}, **bad)
    steps = iter([
        {"calls": [{"tool": "draft_room", "args": {"room_id": "shed", "room": shed}}]
         + _THEN[then]},
        {"calls": [{"tool": "draft_room", "args": {"room_id": "shed", "room": fix}}]},
        {"calls": [{"tool": "submit", "args": {}}]},
    ])
    seen = []

    def call(_sheet, payload):
        seen.append(copy.deepcopy(payload.get("transcript")))
        return next(steps)

    record = {}
    director_rooms.design_rooms(None, _scene(), {}, "sheet", ["shed"], call, record)
    assert record["stopped"] == "submitted", record
    assert record["final_check"]["clean"], record["final_check"]
    # What the designer read before its second step: the merge's error.
    told = [entry for entry in seen[1] if entry["step"] == 1 and entry["tool"] in
            ("check", "submit") and isinstance(entry.get("result"), dict)]
    assert any("could not be merged" in error for entry in told
               for error in entry["result"].get("errors") or ()), told


def test_codes_own_passes_leave_a_draft_the_merge_cannot_take_to_the_check(monkeypatch):
    """Each pass of code's own does nothing to such a draft -- no change, no
    error raised -- and the check says why."""
    from llm import decisions
    monkeypatch.setattr(decisions, "configured", lambda: True)
    scene = {"rooms": {"hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 6, "d": 4}},
                       "yard": {"name": "Yard", "desc": "A yard.", "extent": {"w": 6, "d": 6}}},
             "positions": {}}
    draft = {"rooms": {
        # A far side the derivation would turn, and a bench the packer would
        # place -- on a place whose `parent_entity` the merge cannot take.
        "shed": {"name": "Shed", "desc": "A shed.", "extent": {"w": 3, "d": 3},
                 "parent_entity": {"id": "boat"},
                 "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "e"},
                              {"to": "hall", "barrier": "open_door", "dir": "n"}],
                 "anchors": {"bench": {"desc": "a bench", "dir": "n", "footprint": "small"},
                             "shelf": {"desc": "a shelf", "dir": "n", "footprint": "small"}}},
        "yard": {"adjacent": [{"to": "shed", "barrier": "open_door", "dir": "s"}]},
        "hall": {"adjacent": [{"to": "shed", "barrier": "open_door", "dir": "s"}]}},
        "remove_rooms": [], "remove_adjacent": []}
    before = copy.deepcopy(draft)
    reading = director_rooms._Reading(scene)
    assert director_rooms._derive_far_bearings(scene, draft, ["shed"], reading) == []
    assert director_rooms._place_doorways(scene, draft, {}, reading) == []
    assert director_rooms._pack(scene, draft, {}, settle=True, reading=reading) == []
    assert director_rooms._agree_sizes(scene, draft, reading) == []
    assert director_rooms._finished("Prose.", scene, draft, ["shed"], None, {},
                                    reading) == (False, [])
    assert draft == before
    result = director_rooms._check(scene, draft, ["shed"], reading=reading)
    assert any("could not be merged" in error for error in result["errors"])
    assert not result.get("clean")
