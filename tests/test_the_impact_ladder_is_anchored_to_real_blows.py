"""THE IMPACT LADDER'S `deafening` IS A REAL BLOW (DESIGN_SOUND_FIELD.md
§ 16, round 2 lane B, 2026-10-20).

The impact ladder (`EVENT_POWER`, authored at the source cell on
2026-09-06) put a `deafening` one-beat event at 80 dB, forty-three under
`thunderous` (123) and twenty-three under the emission ladder's own
`deafening` (103): a blow the story called deafening was quieter than a
household `loud` machine is a few paces off, dulled no ear and shook no
floor. Real: the loudest blow an ordinary thing gives or takes -- a steel
door slammed, an anvil dropped on stone, a hammer on steel -- is 100-110
dB(A) a metre off; a shot, a blast, a stun grenade are 120 and up a few
metres off, which is the ladder's `thunderous` and `catastrophic`.

The class, one test each:

  1. a `deafening` blow is 105 dB(A) a pace from where it is made, 108 at
     its cell, over the emission ladder's rung by the few decibels every
     shared word of the impact ladder stands over it (a blow is a peak, a
     running thing an average); the three lower rungs and the two far ones
     do not move;
  2. it is felt by a body a pace or two from it and by nobody across the
     yard; a shot (`thunderous`) rings an ear at a pace, a slammed door
     (`deafening`) rings nobody, because 105 dB(A) does not;
  3. it crosses one masonry wall into the next room, as a hammer on steel
     does; a `loud` blow still does not;
  4. an ordinary beat -- a `faint`, `audible` or `loud` sound -- is graded
     exactly as before.
"""

from __future__ import annotations

from world.spatial import (BLAST_DB, EVENT_DB, FELT_DB, SOUND_DB,
                           SOUND_LEVELS, SPEECH_DB, blast_possible,
                           distant_sounds, event_db, felt_vibrations,
                           loudest_at_ear, sound_field)


def _hall(cells, *, wall_to=None):
    """One stone hall ten paces by six; with `wall_to`, a second room of the
    same size beyond its east wall."""
    rooms = {"hall": {"name": "the hall", "exposure": "enclosed",
                      "extent": {"w": 10, "d": 6}, "anchors": {},
                      "adjacent": []}}
    if wall_to:
        rooms["hall"]["adjacent"] = [{"to": wall_to, "barrier": "wall",
                                      "dir": "e"}]
        rooms[wall_to] = {"name": "the next room", "exposure": "enclosed",
                          "extent": {"w": 10, "d": 6}, "anchors": {},
                          "adjacent": [{"to": "hall", "barrier": "wall",
                                        "dir": "w"}]}
    return {"rooms": rooms,
            "positions": {k: v[0] for k, v in cells.items()},
            "stations": {k: {"cell": list(v[1])} for k, v in cells.items()},
            "entities": {}, "poses": {}, "orientation": {}, "contained": {}}


def _blow(level, source="A"):
    return [{"kind": "sound", "room": "hall", "level": level, "source": source,
             "detail": "the iron door slams on its frame"}]


def test_a_deafening_blow_is_the_loudest_an_ordinary_thing_makes():
    """105 dB(A) a pace from the blow, 108 at its cell. The lower rungs and
    the two far ones are where they were; the ladder is monotone; and every
    word the two ladders share sits a few decibels higher on the impact
    ladder, a blow being a peak."""
    assert EVENT_DB["deafening"] == 108.0
    assert EVENT_DB["faint"] == 45.0
    assert EVENT_DB["audible"] == 58.0
    assert EVENT_DB["loud"] == 72.0
    assert EVENT_DB["thunderous"] == SOUND_DB["thunderous"]
    assert EVENT_DB["catastrophic"] == SOUND_DB["catastrophic"]
    assert abs(EVENT_DB["thunderous"] - 123.0) < 0.02
    assert abs(EVENT_DB["catastrophic"] - 143.0) < 0.02
    assert [EVENT_DB[w] for w in SOUND_LEVELS] == sorted(
        EVENT_DB[w] for w in SOUND_LEVELS)
    for word in ("faint", "audible", "loud", "deafening"):
        assert 1.9 <= EVENT_DB[word] - SOUND_DB[word] <= 5.1, word
    assert event_db({"level": "deafening"}) == 108.0
    assert event_db({"intensity": 1.0}) == 108.0


def test_a_deafening_blow_is_felt_at_a_pace_or_two_and_rings_nobody():
    """The door slams at A's cell: B two paces off feels the floor tremble,
    C eight paces off feels nothing. A shot (`thunderous`) at A's cell rings
    B's ear a pace off; the slammed door, at 105 dB(A), rings nobody's."""
    sc = _hall({"A": ("hall", (2, 2)), "B": ("hall", (4, 2)),
                "C": ("hall", (9, 2))})
    felt = lambda who, level: [r["felt"] for r in felt_vibrations(
        sc, who, events=_blow(level), turn_idx=3)]
    assert EVENT_DB["deafening"] - 3.0 >= FELT_DB
    assert felt("B", "deafening") == ["tremor"]
    assert felt("C", "deafening") == []
    assert felt("B", "loud") == []
    # The blast threshold: a slammed door is under it at its own cell; a
    # shot is over it a pace off.
    assert EVENT_DB["deafening"] < BLAST_DB <= EVENT_DB["thunderous"] - 3.0
    assert not blast_possible(sc, _blow("deafening"))
    assert blast_possible(sc, _blow("thunderous"))
    near = _hall({"A": ("hall", (2, 2)), "B": ("hall", (3, 2))})
    field = sound_field(near, "B", events=_blow("thunderous"), turn_idx=3)
    assert loudest_at_ear(field, "B", scene=near) >= BLAST_DB


def test_a_deafening_blow_crosses_one_masonry_wall():
    """Through a 45 dB wall a `deafening` blow is heard in the next room --
    108 less the wall and the two rooms' spans stands over a quiet room --
    where a `loud` one (72) does not; and a shot carries further still."""
    sc = _hall({"A": ("hall", (2, 2)), "L": ("next", (2, 2))}, wall_to="next")
    heard = lambda level: distant_sounds(sc, "L", events=_blow(level))
    assert heard("deafening"), "a hammer on steel is heard through a wall"
    assert not heard("loud")
    assert heard("thunderous")


def test_an_ordinary_beat_is_graded_as_before():
    """Nothing under `deafening` moved: the three lower rungs read the same
    levels, a speech volume on an event still reads as speech, and an
    unlevelled event is still `audible`."""
    assert (EVENT_DB["faint"], EVENT_DB["audible"], EVENT_DB["loud"]) \
        == (45.0, 58.0, 72.0)
    assert event_db({"intensity": "shout"}) == SPEECH_DB["shout"]
    assert event_db({}) == EVENT_DB["audible"]
    sc = _hall({"A": ("hall", (2, 2)), "B": ("hall", (4, 2))})
    for level in ("faint", "audible", "loud"):
        assert felt_vibrations(sc, "B", events=_blow(level), turn_idx=3) == []
        assert not blast_possible(sc, _blow(level))
