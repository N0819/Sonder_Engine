"""A thing standing in a room is not a character whose story has stalled.

`note_beat_movement` reads the frame's `scene.positions` to find bodies that
have not moved for `STALLED_AFTER_BEATS`, and files an open planning need for
each. `positions` is not a body roster -- CLAUDE.md names the class from
review 2026-09-07 A56, which found three sites -- and
`director.mint_unreferenced_things` made it a fourth by standing minted things
there so a contact has a referent to attach to.

Measured immediately (Aldermill, third run, 2026-09-19, turn 16): the beat
minted `crank_handle` for a winch Emory Vane was working, and three beats
later the engine filed

    {"kind": "room", "reason": "offscreen_thread_stalled",
     "subject": "crank_handle", "surface": {"who": "crank_handle", ...}}

-- the Writers' Room asked to unstick the narrative thread of a crank handle,
which had been lying in a mill yard exactly as crank handles do.
"""

import agents.offscreen_beat as offscreen


def test_only_bodies_can_stall(monkeypatch):
    scene = {
        "positions": {"Emory Vane": "mill_yard", "crank_handle": "mill_yard"},
        "entities": {"char_emory_vane": {"name": "Emory Vane", "kind": "person"},
                     "crank_handle": {"name": "crank handle", "kind": "fixture"}},
        "rooms": {"mill_yard": {"name": "Mill Yard"}},
    }
    assert offscreen.stalling_bodies(scene) == {"Emory Vane": "mill_yard"}, (
        "a fixture in positions is furniture, not a thread anybody is telling")


def test_a_scene_with_no_entity_records_still_answers():
    """`scene_names_body` is the predicate, and a story that never wrote an
    entity record for its cast must not lose its own people to this."""
    scene = {"positions": {"Sal Weatherby": "inn_taproom"}, "rooms": {}}
    assert "Sal Weatherby" in offscreen.stalling_bodies(scene)
