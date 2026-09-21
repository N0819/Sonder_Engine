"""A body seen as shapes from ANOTHER room is somewhere, and the view says where.

`act_percept` has two sibling branches for a body whose conduct the observer
cannot read. The UNSEEN one -- a body in the rear arc -- already carried a
bearing and rendered "Something moves {where}." The SEEN-as-shapes one carried
`{"motion": True}` and nothing else, so a figure watched through an open
doorway arrived as a placeless "moves, too little of it to make out", and the
narrator, with nothing to anchor it, put the figure in the observer's own room.

Measured (chat 151 turns 9-10, 2026-09-21): Gushiga Toriki stood on the
Moonlit Beach while Hinami stood inside the TARDIS console room, the act
percept was admitted `shapes only -- motion without conduct`, and the prose
came back "whatever else is in here with you that isn't the Doctor and isn't
the ship". The room was never in the sentence to be got wrong -- it was never
in the sentence at all.

Naming the room opens no channel. It is the room the observer is already
looking into, and `_visible_room_label`'s own docstring calls it "the one
distance phrasing that is true through a doorway, a grille and a pane of glass
alike". The rule is the class, not the doorway: where the body stands is the
observer's when it is not standing where they are.
"""

from __future__ import annotations

import agents.composer as composer


def _two_rooms():
    """P is inside; Q stands in the next room, through an open door."""
    return {
        "rooms": {
            "inside": {"name": "TARDIS Console Room", "size": "medium",
                       "adjacent": [{"to": "beach", "barrier": "open"}]},
            "beach": {"name": "Moonlit Beach", "size": "large",
                      "adjacent": [{"to": "inside", "barrier": "open"}]},
        },
        "positions": {"P": "inside", "Q": "beach"},
        "entities": {"P": {"name": "P", "kind": "person"},
                     "Q": {"name": "Q", "kind": "person"}},
    }


def _one_room():
    return {
        "rooms": {"inside": {"name": "TARDIS Console Room", "size": "medium",
                             "adjacent": []}},
        "positions": {"P": "inside", "Q": "inside"},
        "entities": {"P": {"name": "P", "kind": "person"},
                     "Q": {"name": "Q", "kind": "person"}},
    }


def _act(scene, display="the unfamiliar person"):
    return composer.act_percept(
        scene, {"event_id": "e1", "actor": "Q", "targets": []},
        "P", "Q", {"same_room": False, "barrier": "open"},
        surface="shifts his weight on the sand",
        display=display, can_see=True, sight="shapes", order_key=0)


def test_a_shapes_figure_in_another_room_carries_that_room():
    percept = _act(_two_rooms())
    assert percept is not None, "the beat reached nobody at all"
    assert percept.fidelity == "shapes"
    assert percept.data.get("room") == "Moonlit Beach"


def test_the_rendered_line_says_which_room():
    line = composer.render_view([_act(_two_rooms())]).text
    assert "Moonlit Beach" in line, line
    # Still a shape: no conduct leaks through the placement.
    assert "sand" not in line and "weight" not in line, line


def test_a_shapes_figure_in_your_own_room_stays_unplaced():
    """The room is the answer to "not here"; naming the room an observer is
    standing in would be noise, and the bare template still owns that case."""
    percept = _act(_one_room())
    assert percept is not None
    assert "room" not in percept.data
    assert "TARDIS Console Room" not in composer.render_view([percept]).text


def test_the_memory_written_about_them_is_placed_too():
    """The episode line is what reaches `mind.memory`. A placeless figure is
    worse in a memory than in a view: the view is re-rendered next beat and
    the memory is not."""
    scene = _two_rooms()
    episode = composer.render_episode([_act(scene)])
    text = episode.text if hasattr(episode, "text") else str(episode)
    assert "Moonlit Beach" in text, text
