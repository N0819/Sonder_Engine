"""Who perceived the act is not who may answer it.

`perception_act` built a perceiver only for characters in `flow.reactors` —
the Director's PACING judgement, whose real question is "who speaks this
beat". So a present, awake, watching character perceived the onset never and
then answered the aftermath. Measured over the corpus: a witness was missing
from `reactors` in 757 of 975 multi-witness beats (77.6%), and 1,639 of 4,292
character-presences (38.2%) got no act view at all. The alpha 6.9 prompt
sharpening moved it to 39.5% / 13.9% and did not close it.

IT IS FELT THROUGH THE LOOP. `loops.py` seeds `local_views` from these views,
so a body drawn in later — deferred, addressed, answering next beat — started
from an empty base and never held the act it was reacting to, only the
dialogue after it.

AND THE FIX IS FREE, which is the part the register had wrong. It reads as
expensive because widening `reactors` means more character-step calls; that is
true of pacing and false of perception, and the two separate cleanly.
Perception makes no model call at all, and `loops.py` reads `flow.reactors` for
itself — so who speaks, and what the beat costs, are byte-for-byte unchanged.
"""

from __future__ import annotations

import inspect

from agents import loops, perception


def _row(cid, name):
    """The slice of a cast row `sheet_state` reads."""
    return {"id": cid, "sheet": '{"identity": {"name": "%s"}}' % name,
            "cstate": "{}", "status": "active"}


def test_the_onset_audience_is_not_read_from_flow_reactors():
    """The gate this closes, pinned by absence at its own site."""
    source = inspect.getsource(perception.perception_act)
    assert "_present_cast_bodies" in source
    assert 'flow.get("reactors")' not in source, (
        "the onset audience is being decided by the Director's pacing list "
        "again")


def test_presence_is_a_room_in_the_scene():
    scene = {"positions": {"Watcher": "hall", "Speaker": "hall"},
             "rooms": {"hall": {"name": "Hall"}}}
    cast = [_row(1, "Watcher"), _row(2, "Speaker"), _row(3, "Absent")]

    present = perception._present_cast_bodies(scene, cast)

    assert [b["name"] for b in present] == ["Watcher", "Speaker"], \
        "a body the scene places nowhere is not present"
    assert all(b["room"] == "hall" for b in present)


def test_a_body_with_no_room_is_still_excluded():
    """The widening is presence, not everybody: an offscreen cast member has
    no room and perceives nothing."""
    scene = {"positions": {}, "rooms": {"hall": {"name": "Hall"}}}
    cast = [_row(1, "Offscreen")]

    assert perception._present_cast_bodies(scene, cast) == []


def test_pacing_still_belongs_to_the_director():
    """The other half of the split, and the reason this costs nothing: the
    loops read the Director's list themselves, so widening perception cannot
    add a character step or a provider call."""
    source = inspect.getsource(loops)
    assert 'flow.get("reactors")' in source, (
        "the interaction loop stopped reading the Director's pacing list, "
        "which is the half that must keep reading it")
