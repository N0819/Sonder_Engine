"""A design run merges its draft into the world once per change, reads the
world's own rows once, and tries a refused far side once until the draft's
layout changes (`director_rooms._Reading`).

Measured by round one's review (2026-10-08) on chat 166's 33-room turn-22
final draft: a check's passes -- the size words, the far sides, the
doorways, the packing, the check -- each merged the draft and read the
world's rows for themselves, 0.94 s against 0.28 s for the check alone, and
the Gale house door's far side, which the world refused (it laid the landing
onto the low walk), was tried again at every check: two merges and four
whole checks each time, about 0.6 s.
"""

from __future__ import annotations

import copy

from agents import director_rooms


def _house():
    """A house whose north wall a loft already uses; the landing drafted
    against it writes the doorway `s` from both sides. The far side's
    opposite would put the landing on the house's north wall beside the
    loft, both five paces wide on a five-pace wall: one lands on the other."""
    scene = {"rooms": {
        "walk": {"name": "the low walk", "desc": "A walk.", "exposure": "open",
                 "extent": {"w": 8, "d": 3},
                 "adjacent": [{"to": "house", "barrier": "closed_door", "dir": "n"}]},
        "house": {"name": "the house", "desc": "A house.", "extent": {"w": 5, "d": 5},
                  "adjacent": [{"to": "loft", "barrier": "open_door", "dir": "n"}]},
        "loft": {"name": "the loft", "desc": "A loft.", "extent": {"w": 5, "d": 4}}},
        "positions": {}}
    draft = {"rooms": {
        "landing": {"name": "the landing", "desc": "A landing.", "extent": {"w": 5, "d": 3},
                    "adjacent": [{"to": "house", "barrier": "closed_door", "dir": "s"}]},
        "house": {"adjacent": [{"to": "landing", "barrier": "closed_door", "dir": "s"}]}},
        "remove_rooms": [], "remove_adjacent": []}
    return scene, draft


def test_a_far_side_the_world_refused_is_not_tried_again_until_the_layout_changes(monkeypatch):
    scene, draft = _house()
    tried = []
    plane = director_rooms._plane_rows
    monkeypatch.setattr(director_rooms, "_plane_rows",
                        lambda *a, **k: tried.append(1) or plane(*a, **k))
    reading = director_rooms._Reading(scene)
    for _ in range(3):
        assert director_rooms._derive_far_bearings(scene, draft, ["landing"], reading) == []
    assert len(tried) == 2, "tried once: the layout before, and the layout it would make"
    assert draft["rooms"]["house"]["adjacent"][0]["dir"] == "s", "taken back"
    # Words move no room: still not tried.
    draft["rooms"]["landing"]["desc"] = "A landing, its boards worn grey."
    assert director_rooms._derive_far_bearings(scene, draft, ["landing"], reading) == []
    assert len(tried) == 2
    # Narrowed to fit beside the loft, the landing's layout is new: tried again.
    draft["rooms"]["landing"]["extent"] = {"w": 2, "d": 3}
    director_rooms._derive_far_bearings(scene, draft, ["landing"], reading)
    assert len(tried) > 2


def test_a_checks_passes_share_one_merge_of_the_draft(monkeypatch):
    """Drafted once and checked three times -- after the draft, by the
    designer, and at the submit -- the draft is merged into the world once:
    the packing, the plan, every pass of every check and the final check
    read that one merge."""
    scene = {"rooms": {"yard": {"name": "the yard", "desc": "A yard.", "exposure": "open",
                                "extent": {"w": 8, "d": 6}}}, "positions": {}}
    shed = {"name": "the shed", "desc": "A shed with a bench.", "extent": {"w": 4, "d": 3},
            "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "s"}],
            "anchors": {"bench": {"desc": "a bench", "dir": "n", "footprint": "small",
                                  "height": "waist"}}}
    merges = []
    merged = director_rooms._merged
    monkeypatch.setattr(director_rooms, "_merged",
                        lambda *a, **k: merges.append(1) or merged(*a, **k))
    steps = iter([{"calls": [{"tool": "draft_room", "args": {"room_id": "shed", "room": shed}}]},
                  {"calls": [{"tool": "check", "args": {}}]},
                  {"calls": [{"tool": "submit", "args": {}}]}])
    record = {}
    director_rooms.design_rooms(None, scene, {}, "sheet", ["shed"],
                                lambda s, p: next(steps), record)
    assert record["final_check"]["clean"], record["final_check"]
    assert record["stopped"] == "submitted"
    assert len(merges) == 1, len(merges)


def test_a_doorway_batch_the_world_refused_is_not_tried_again_until_the_layout_changes(
        monkeypatch):
    """The hall's door to the porch and the loft's door down onto it are
    seeded on one cell of the hall's three-pace north wall. Moved along it,
    the loft's door lays the loft onto the attic beside the porch: the batch
    is taken back -- once, then not tried again while the layout stands, as
    the far sides are not (round two's review: removing that memo left every
    test green)."""
    scene = {"rooms": {
        "porch": {"name": "Porch", "desc": "A porch.", "extent": {"w": 5, "d": 4},
                  "adjacent": [{"to": "attic", "barrier": "open_door", "dir": "w"}]},
        "attic": {"name": "Attic", "desc": "An attic.", "extent": {"w": 4, "d": 2}},
        "loft": {"name": "Loft", "desc": "A loft.", "extent": {"w": 5, "d": 3}}},
        "positions": {}}
    draft = {"rooms": {
        "hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 3, "d": 5},
                 "adjacent": [{"to": "porch", "barrier": "open_door", "dir": "n"}]},
        "loft": {"adjacent": [{"to": "hall", "barrier": "open_door", "dir": "s"}]}},
        "remove_rooms": [], "remove_adjacent": []}
    as_written = copy.deepcopy(draft["rooms"])
    tried = []
    plane = director_rooms._plane_rows
    monkeypatch.setattr(director_rooms, "_plane_rows",
                        lambda *a, **k: tried.append(1) or plane(*a, **k))
    reading = director_rooms._Reading(scene)
    for _ in range(3):
        assert director_rooms._place_doorways(scene, draft, {}, reading) == []
    assert len(tried) == 2, "tried once: the layout before, and the layout it would make"
    assert draft["rooms"] == as_written, "taken back"
    # Words move no room: still not tried.
    draft["rooms"]["hall"]["desc"] = "A hall, its plaster cracked."
    assert director_rooms._place_doorways(scene, draft, {}, reading) == []
    assert len(tried) == 2
    # A deeper hall lays out anew: tried again.
    draft["rooms"]["hall"]["extent"] = {"w": 3, "d": 6}
    director_rooms._place_doorways(scene, draft, {}, reading)
    assert len(tried) > 2
