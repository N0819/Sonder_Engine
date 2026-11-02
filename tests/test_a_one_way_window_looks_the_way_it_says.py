"""A one-way window declared from its blind side still lets its watching side
see through, in the list of rooms a body can see.

Audit world_spatial_movement_sight F10 (2026-11-01, CONFIRMED WRONG-SCENE):
`visible_adjacent_rooms`' reverse pass skipped EVERY reverse-declared
`one_way_window`, whatever `sight_from` named. `sight_direction` endorses
repairing a mirror "by naming a room rather than by deleting a declaration":
the cell declares `{to: annex, one_way_window, sight_from: annex}` and the
annex declares nothing. `spatial_rel(annex, cell)` read `one_way_window` and
`sees_across` True, but `visible_adjacent_rooms(annex) == []` -- the watcher's
view, `seen_onward` and the place graph lost the room the interviewer is there
to watch. Design.md says this reader "now asks [sees_across] too instead of its
own copy"; only its forward loop did.
"""

from world.spatial import visible_adjacent_rooms


def _scene():
    return {
        "rooms": {
            "cell": {"name": "Interview Cell", "desc": "A bare table.",
                     "adjacent": [{"to": "annex", "barrier": "one_way_window",
                                   "sight_from": "annex"}]},
            "annex": {"name": "Observation Annex", "desc": "Dark.", "adjacent": []},
        },
        "positions": {"Watcher": "annex", "Suspect": "cell"},
        "entities": {},
    }


def test_the_watching_side_sees_the_cell():
    seen = [r["room_id"] for r in visible_adjacent_rooms(_scene(), "annex")]
    assert seen == ["cell"]


def test_the_blind_side_does_not_see_the_annex():
    seen = [r["room_id"] for r in visible_adjacent_rooms(_scene(), "cell")]
    assert seen == []


def test_a_reverse_declared_mirror_with_no_direction_still_refuses_the_look_back():
    sc = _scene()
    sc["rooms"]["cell"]["adjacent"][0].pop("sight_from")
    # Declared from the cell, looking into the annex: the annex looks back
    # through nothing.
    assert [r["room_id"] for r in visible_adjacent_rooms(sc, "annex")] == []
