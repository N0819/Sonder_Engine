"""A body facing a shut door must be told there is a shut door there.

`_BARRIER_ANCHOR_DESC` named `closed_door` "the doorway" -- the same noun an
opening gets, minus one adjective -- so the only thing a view ever said about
a shut door was what sight does NOT deliver through it:

    Through the open doorway is The River Road. ... Nothing shows through the
    doorway. Through the second open doorway is Mill Grain Loft.

That is the middle sentence of Emory Vane's view on every one of his thirty
beats (Aldermill, two-bubble run 2026-09-19). The obstacle his entire story
was about is in there, named as a doorway, described by an absence.

WHAT THIS DOES NOT ADD. Whether a shut door is LOCKED, jammed or swollen is
not a fact sight carries -- you find that out by trying it -- so the name
stays "the shut door" for every one of them and `barrier_fastening` is not
read here. The percept says what an eye delivers: there is a door, and it is
closed.
"""

from world.spatial import _BARRIER_ANCHOR_DESC, normalize_barrier


def test_a_closed_door_is_not_called_a_doorway():
    assert _BARRIER_ANCHOR_DESC["closed_door"] == "the shut door"
    assert _BARRIER_ANCHOR_DESC["open_door"] == "the open doorway"
    assert _BARRIER_ANCHOR_DESC["closed_door"] \
        != _BARRIER_ANCHOR_DESC["open_door"]


def test_a_fastened_door_is_still_only_a_shut_door_to_the_eye():
    """Locked, jammed and stuck all normalise to `closed_door`, and all three
    look the same from across the room."""
    for spelling in ("locked_door", "jammed_door", "stuck_door", "closed_door"):
        assert _BARRIER_ANCHOR_DESC[normalize_barrier(spelling)] \
            == "the shut door"


def test_the_two_boundaries_stay_tellable_apart():
    """`composer._render_openings` distinguishes two boundaries by ORDINAL
    only when their descriptions collide. A shut door and an open doorway
    must not collide, or a room with one of each renders "the doorway" and
    "the second doorway" and says nothing about which is which."""
    from agents.composer import _render_openings

    prose = _render_openings([
        {"desc": _BARRIER_ANCHOR_DESC["open_door"], "state": "seen",
         "room_name": "The River Road"},
        {"desc": _BARRIER_ANCHOR_DESC["closed_door"], "state": "blind"},
    ])
    assert "the open doorway" in prose
    assert "shut door" in prose
    assert "second" not in prose


def test_a_way_named_for_where_it_goes_is_not_said_twice():
    """Kirinoura (scratch chat 167, 2026-10-05): the room author named the
    stair's edge after the stair, and the view read "Through the long stone
    stair is the long stone stair." A way named for a room it joins -- where
    it goes, or where the observer stands -- names no boundary: the way goes
    on from HERE to the room, worded true of a place as much as a passage
    (review, 2026-10-05: "leads on from here" called an inn a passage); one
    with a name of its own keeps it."""
    from agents.composer import _render_openings
    prose = _render_openings([
        {"desc": "the torii gate", "state": "seen", "room_name": "the shrine forecourt"},
        {"desc": "the long stone stair", "state": "seen", "room_name": "The long stone stair",
         "vertical": "down"},
        {"desc": "the inn", "state": "seen", "room_name": "the inn"},
        {"desc": "the terrace", "state": "seen", "room_name": "the long gallery"}],
        here="the terrace")
    assert prose == ("Through the torii gate is the shrine forecourt. "
                     "Down from here is The long stone stair. "
                     "From here the way goes on to the inn. "
                     "From here the way goes on to the long gallery.")
