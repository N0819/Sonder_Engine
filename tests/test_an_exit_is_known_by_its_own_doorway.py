"""An exit is the room behind THIS room's doorway, not the first room in the
scene that shares its name.

`_annotate_known_exits` mapped each digest exit back to a room id through
one scene-wide `{display name: rid}` map built with `setdefault`, so two
rooms with one name collapsed onto whichever the scene listed first.
Measured (review 2026-11-01, agents_character_background F11, the owner's
engine.db read-only): 8 of 156 scenes hold duplicate room names, all recent
stair rooms -- chats 172, 173, 174 and 179 ("Narrow wooden staircase" x2,
"Steep straight flight" x2, "ladder" x2) -- so the upper storey's stair exit
carried the lower stair's `been_there`, its `times_entered` and its verdict,
and the completeness test counted an untried doorway as walked. The exit is
now resolved among the doorways of the room the mind stands in.
"""

from __future__ import annotations

from agents.character import _annotate_known_exits


def _room(name, *edges):
    return {"name": name, "desc": name, "light": "lit",
            "adjacent": [{"to": to, "dir": d, "barrier": "open"} for to, d in edges]}


SCENE = {"rooms": {
    "stair_1": _room("Stair", ("landing_1", "n")),
    "landing_1": _room("Landing One", ("stair_1", "s"), ("stair_2", "u")),
    "stair_2": _room("Stair", ("landing_2", "n"), ("landing_1", "d")),
    "landing_2": _room("Landing Two", ("stair_2", "s")),
}}

# Standing on the upper landing: its one doorway leads to the UPPER stair.
DIGEST = {"unclassified": [{"room": "Stair", "barrier": "open", "bearing": "s"}]}


def test_the_upper_stair_reads_untried_though_the_lower_was_walked():
    out = _annotate_known_exits(
        DIGEST, SCENE, ["stair_1", "landing_1", "stair_1"],
        known_exits={"stair_1": ["landing_1"], "landing_1": ["stair_1"]},
        here_rid="landing_2")
    entry = out["unclassified"][0]
    assert entry.get("been_there") is False and "times_entered" not in entry
    assert entry.get("untried") is True


def test_the_lower_stair_still_reads_walked_from_its_own_landing():
    digest = {"unclassified": [{"room": "Stair", "barrier": "open", "bearing": "s"}]}
    out = _annotate_known_exits(
        digest, SCENE, ["stair_1", "landing_1", "stair_1"],
        known_exits={"stair_1": ["landing_1"], "landing_1": ["stair_1"]},
        here_rid="landing_1")
    entry = out["unclassified"][0]
    assert entry.get("been_there") is True and entry.get("entered_recently") == 2


def test_two_doorways_to_rooms_of_one_name_are_told_apart_by_bearing():
    scene = {"rooms": {
        "hub": _room("Hub", ("east_store", "e"), ("west_store", "w")),
        "east_store": _room("Store", ("hub", "w")),
        "west_store": _room("Store", ("hub", "e")),
    }}
    digest = {"unclassified": [
        {"room": "Store", "barrier": "open", "bearing": "e"},
        {"room": "Store", "barrier": "open", "bearing": "w"}]}
    out = _annotate_known_exits(digest, scene, ["west_store", "hub"],
                                known_exits={"hub": ["east_store", "west_store"]},
                                here_rid="hub")
    by_bearing = {e["bearing"]: e for e in out["unclassified"]}
    assert by_bearing["w"].get("been_there") is True
    assert by_bearing["e"].get("been_there") is False
